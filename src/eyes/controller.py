"""AppController — orchestrates the camera -> detect -> classify -> update-UI loop at 10 Hz."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .autostart import AutostartManager
from .camera import CameraSource
from .classifier import NeutralPose, PoseState, Thresholds
from .config_store import ConfigStore
from .detector import HeadPoseDetector
from .event_log import EventLog
from .icon_factory import create_eye_icon
from .main_window import MainWindow
from .overlay import NotifierOverlay
from .sense_loop import (
    AccumulatorConfig,
    CorrectionEvent,
    EyeRestEvent,
    GoodPostureEvent,
    SenseEvent,
    SenseLoop,
)
from .settings_dialog import SettingsDialog
from .snooze_manager import SnoozeManager
from .tray_controller import TrayController
from .types import AppEventKind, TrayIconState, WarningLevel, WarningLevelEvent

# Tick interval: 100 ms = 0.1 seconds
_DT_SECONDS = 0.1
# Camera retry interval: 5 seconds
_CAMERA_RETRY_INTERVAL_MS = 5000


class AppController:
    """Drives the 10 Hz tick loop and coordinates all components.

    Single QTimer at 100 ms interval:
      read frame -> detect head pose -> classify -> accumulate -> update UI -> repeat

    On camera/detector errors the loop keeps running but the UI shows
    the unavailable state. The window close event minimizes to tray (not quit).
    """

    def __init__(self, app: QApplication, camera_index: int | None = None) -> None:
        self._app = app

        # Load configuration
        self._config_store = ConfigStore()
        self._config = self._config_store.load()

        # Event logger
        self._event_log = EventLog()

        # Determine camera index: CLI arg > config > default 0
        if camera_index is None:
            camera_index = self._config.camera_index

        # Camera and detector (ownership moved from MainWindow)
        self._camera = CameraSource(index=camera_index)
        self._detector: Optional[HeadPoseDetector] = None

        # Pure view window
        self._window = MainWindow()
        self._timer = QTimer()
        self._timer.setInterval(100)  # 10 Hz

        # Camera retry timer: every 5 seconds when camera is unavailable
        self._camera_retry_timer = QTimer()
        self._camera_retry_timer.setInterval(_CAMERA_RETRY_INTERVAL_MS)
        self._camera_retry_timer.timeout.connect(self._try_reopen_camera)

        # Qt-free sensing loop for detect -> classify -> accumulate -> prompt events.
        self._sense_loop = SenseLoop(
            self._detector,
            **self._get_classify_kwargs(),
            accumulator_config=self._get_accumulator_config(),
        )
        self._accumulator = self._sense_loop.accumulator

        # Overlay for correction prompts
        self._overlay = NotifierOverlay()

        # Tray controller
        self._tray = TrayController()
        self._tray.show_window_requested.connect(self._on_show_window_requested)
        self._tray.settings_requested.connect(self._on_settings_requested)
        self._tray.quit_requested.connect(self._on_quit_requested)

        # Snooze manager - handles pause/resume lifecycle
        self._snooze_manager = SnoozeManager(
            self._config_store,
            self._accumulator,
            self._tray,
            on_snooze_end=lambda: self._event_log.append(AppEventKind.SNOOZE_END),
        )
        self._tray.pause_requested.connect(self._on_pause_requested)
        self._tray.resume_requested.connect(self._on_resume_requested)

        # Autostart manager
        self._autostart_manager = AutostartManager()

        # Track previous state for STATE_CHANGE events
        self._last_state: PoseState | None = None
        # Track camera availability for CAMERA_UNAVAILABLE/RESUMED events
        self._camera_was_available = False
        # Reference to open settings dialog (for calibration sampling)
        self._settings_dialog: SettingsDialog | None = None
        # Track if we've shown the unavailable message this session
        self._camera_unavailable_message_shown = False

        # Initialize snooze state from persisted config
        self._snooze_manager.restore_persisted_state()

        self._app.aboutToQuit.connect(self._on_about_to_quit)
        self._window.close_requested.connect(self._on_window_close_requested)

    def _on_pause_requested(self, duration_seconds: int | None) -> None:
        """Handle pause/snooze request from tray menu."""
        self._snooze_manager.pause(duration_seconds)
        self._event_log.append(AppEventKind.SNOOZE_START, duration_seconds=duration_seconds)

    def _on_resume_requested(self) -> None:
        """Handle resume request from tray menu."""
        self._snooze_manager.resume()
        self._event_log.append(AppEventKind.SNOOZE_END)

    def _on_show_window_requested(self) -> None:
        """Handle show-window request from tray left-click or menu item."""
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _on_settings_requested(self) -> None:
        """Handle settings request from tray menu - show settings dialog."""
        # Show the main window
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

        # Show settings dialog
        self._settings_dialog = SettingsDialog(self._config_store, self._window)
        self._settings_dialog.settings_changed.connect(self._on_settings_changed)
        self._settings_dialog.calibration_completed.connect(self._on_calibration_completed)
        self._settings_dialog.exec()

        # Check if camera needs to be switched
        new_camera_index = self._settings_dialog.get_pending_camera_index()
        if new_camera_index is not None and new_camera_index != self._camera._index:
            self._switch_camera(new_camera_index)
        self._settings_dialog = None

    def _on_settings_changed(self) -> None:
        """Handle settings changed - reload config and apply autostart."""
        self._config = self._config_store.load()
        self._sense_loop.update_classifier(**self._get_classify_kwargs())
        self._autostart_manager.apply_config(self._config.autostart_enabled)

    def _on_calibration_completed(self, yaw: float, roll: float) -> None:
        """Handle calibration completed - reload config to get updated neutral pose."""
        # Log the calibration event
        self._event_log.append(
            AppEventKind.STATE_CHANGE,
            state=f"CALIBRATED: yaw={yaw:+.1f}°, roll={roll:+.1f}°"
        )
        self._config = self._config_store.load()
        self._sense_loop.update_classifier(**self._get_classify_kwargs())

    def _switch_camera(self, index: int) -> None:
        """Switch to a different camera using set_index()."""
        self._camera.set_index(index)

    def _on_quit_requested(self) -> None:
        """Handle quit request from tray menu."""
        # Log if we were snoozed
        if self._accumulator.is_snoozed:
            self._event_log.append(AppEventKind.SNOOZE_END)
        self._app.quit()

    def _on_window_close_requested(self) -> None:
        """Window close minimizes to tray instead of quitting."""
        # Hide the window but keep camera/detector resources for background monitoring
        self._window.hide()

    def close(self) -> None:
        """Close window and release resources (for app quit)."""
        self._window.close()
        self._camera.close()
        if self._detector is not None:
            self._detector.close()

    def _on_about_to_quit(self) -> None:
        """Stop all timers and close the window before the application exits."""
        self._timer.stop()
        self._camera_retry_timer.stop()
        self._window.close()

    def _get_classify_kwargs(self) -> dict:
        """Return classify() kwargs from current config."""
        return {
            "neutral": NeutralPose(yaw=self._config.neutral_yaw, roll=self._config.neutral_roll),
            "thresholds": Thresholds(yaw_deg=self._config.yaw_threshold, roll_deg=self._config.roll_threshold),
        }

    def _get_accumulator_config(self) -> AccumulatorConfig:
        """Return accumulator config from current config."""
        return AccumulatorConfig(
            off_axis_streak_threshold_seconds=self._config.off_axis_streak_threshold_seconds,
            off_axis_repeat_interval_seconds=self._config.off_axis_repeat_interval_seconds,
            facing_threshold_seconds=self._config.facing_threshold_seconds,
            eyest_threshold_seconds=self._config.eyest_threshold_seconds,
        )

    def _log_state_change(self, state: PoseState) -> None:
        """Log STATE_CHANGE event if state differs from last."""
        if state != self._last_state:
            self._event_log.append(AppEventKind.STATE_CHANGE, state=state.value)
            self._last_state = state

    def _dispatch_prompt_event(self, event: SenseEvent) -> None:
        """Dispatch a SenseLoop event to logging, overlay, and UI output."""
        match event:
            case CorrectionEvent(direction=direction):
                dir_str = "LEFT" if direction == PoseState.OFF_AXIS_LEFT else "RIGHT"
                self._event_log.append(AppEventKind.PROMPT_FIRED, prompt="adjust", direction=dir_str)
                self._overlay.show_correction(direction)
            case GoodPostureEvent():
                self._event_log.append(AppEventKind.PROMPT_FIRED, prompt="good_posture")
                self._overlay.show_good_posture()
            case EyeRestEvent():
                self._event_log.append(AppEventKind.PROMPT_FIRED, prompt="eye_rest")
                self._overlay.show_eye_rest()
            case WarningLevelEvent():
                self._event_log.append(AppEventKind.WARNING_LEVEL_CHANGED, level=event.level.value, direction=event.direction)
                self._window.set_warning_level(event)
                if event.level == WarningLevel.CORRECTED:
                    self._overlay.show_corrected()
                elif event.level == WarningLevel.NORMAL:
                    self._overlay.hide()

    def _ensure_detector(self) -> bool:
        """Lazily create the HeadPoseDetector if not yet initialized.

        Returns False (and logs the error) if model loading fails.
        """
        if self._detector is not None:
            self._sense_loop.detector = self._detector
            return True
        try:
            self._detector = HeadPoseDetector()
        except RuntimeError as exc:
            self._event_log.append(AppEventKind.STATE_CHANGE, state=f"MODEL_LOAD_FAILED: {exc}")
            self._sense_loop.detector = None
            return False
        self._sense_loop.detector = self._detector
        return True

    def _init_camera_and_detector(self) -> bool:
        """Open the camera and build the detector. Returns True on success."""
        if not self._camera.open():
            return False
        if not self._ensure_detector():
            self._camera.close()
            return False
        return True

    def run(self) -> None:
        """Show the window, open camera + detector, start the tick loop."""
        self._window.setWindowIcon(create_eye_icon(TrayIconState.ACTIVE))
        self._window.show()
        self._tray.show()

        if not self._init_camera_and_detector():
            # Camera unavailable — still show the window
            self._event_log.append(AppEventKind.CAMERA_UNAVAILABLE)
            self._camera_was_available = False
            self._camera_unavailable_message_shown = True
            self._tray.set_state(TrayIconState.UNAVAILABLE)
            self._window.show_camera_unavailable_message()
            self._camera_retry_timer.start()
        else:
            self._camera_was_available = True

        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self._app.exec()

    def _try_reopen_camera(self) -> None:
        """Attempt to reopen the camera. Called every 5 seconds when unavailable."""
        if not self._camera.retry_open():
            return
        if not self._ensure_detector():
            self._camera.close()
            return

        # Camera is now available
        self._event_log.append(AppEventKind.CAMERA_RESUMED)
        self._camera_was_available = True
        self._camera_unavailable_message_shown = False
        self._camera_retry_timer.stop()
        # Restore to active/paused state
        self._tray.set_state(
            TrayIconState.ACTIVE if not self._accumulator.is_snoozed else TrayIconState.PAUSED
        )
        self._window.clear_camera_unavailable_message()

    def _tick(self) -> None:
        """One 10 Hz tick: read, detect, classify, accumulate, update UI."""
        # Check if timed snooze has expired
        self._snooze_manager.check_expiry()

        # If camera is unavailable, show message if not already shown
        if not self._camera.is_available:
            self._window.set_warning_level(WarningLevelEvent(level=WarningLevel.NORMAL, direction=None))
            self._window.set_state(None, None, None)
            if self._camera_was_available:
                self._event_log.append(AppEventKind.CAMERA_UNAVAILABLE)
                self._camera_was_available = False
                self._tray.set_state(TrayIconState.UNAVAILABLE)
                self._camera_retry_timer.start()
            if not self._camera_unavailable_message_shown:
                self._window.show_camera_unavailable_message()
                self._camera_unavailable_message_shown = True
            return

        frame = self._camera.read()
        self._window.update_frame(frame)

        events = self._sense_loop.tick(frame, _DT_SECONDS)
        current_yaw = self._sense_loop.current_yaw
        current_roll = self._sense_loop.current_roll
        current_state = self._sense_loop.current_state

        if current_yaw is None or current_roll is None:
            self._window.set_state(None, None, None)
        else:
            self._window.set_state(current_yaw, current_roll, current_state)

        # Collect calibration samples if settings dialog is open and calibrating
        if self._settings_dialog is not None and current_yaw is not None and current_roll is not None:
            self._settings_dialog.add_calibration_sample(current_yaw, current_roll)

        # Log state changes
        self._log_state_change(current_state)

        for event in events:
            self._dispatch_prompt_event(event)

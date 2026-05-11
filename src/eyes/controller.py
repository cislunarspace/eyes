"""AppController — orchestrates the camera -> detect -> classify -> update-UI loop at 10 Hz."""

from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .accumulator import AccumulatorEngine
from .autostart import AutostartManager
from .classifier import NeutralPose, PoseState, Thresholds, classify
from .config_store import ConfigStore
from .event_log import EventLog
from .main_window import MainWindow
from .overlay import NotifierOverlay
from .settings_dialog import SettingsDialog
from .tray_controller import TrayController, TrayIconState
from .types import AppEventKind

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

        self._window = MainWindow(camera_index=camera_index)
        self._timer = QTimer()
        self._timer.setInterval(100)  # 10 Hz

        # Camera retry timer: every 5 seconds when camera is unavailable
        self._camera_retry_timer = QTimer()
        self._camera_retry_timer.setInterval(_CAMERA_RETRY_INTERVAL_MS)
        self._camera_retry_timer.timeout.connect(self._try_reopen_camera)

        # Accumulator engine for off-axis streak tracking
        self._accumulator = AccumulatorEngine(
            off_axis_streak_threshold_seconds=self._config.off_axis_streak_threshold_seconds,
            off_axis_repeat_interval_seconds=self._config.off_axis_repeat_interval_seconds,
            facing_threshold_seconds=self._config.facing_threshold_seconds,
            eyest_threshold_seconds=self._config.eyest_threshold_seconds,
        )

        # Overlay for correction prompts
        self._overlay = NotifierOverlay()

        # Tray controller
        self._tray = TrayController()
        self._tray.pause_requested.connect(self._on_pause_requested)
        self._tray.resume_requested.connect(self._on_resume_requested)
        self._tray.settings_requested.connect(self._on_settings_requested)
        self._tray.quit_requested.connect(self._on_quit_requested)

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
        self._check_persisted_snooze()

        self._app.aboutToQuit.connect(self._on_about_to_quit)
        self._window.close_requested.connect(self._on_window_close_requested)

    def _check_persisted_snooze(self) -> None:
        """Check if snooze is still active from previous session."""
        snooze_until = self._config.snooze_until_iso
        if snooze_until is None:
            return
        if snooze_until == "indefinite":
            self._accumulator.snooze()
            self._tray.set_state(TrayIconState.PAUSED)
            return
        # Check if timed snooze has expired
        try:
            snooze_time = datetime.fromisoformat(snooze_until)
            if snooze_time.tzinfo is None:
                snooze_time = snooze_time.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if now >= snooze_time:
                # Snooze expired, clear it
                self._config_store.update(snooze_until_iso=None)
            else:
                # Still snoozed
                self._accumulator.snooze()
                self._tray.set_state(TrayIconState.PAUSED)
        except ValueError:
            # Invalid timestamp, clear it
            self._config_store.update(snooze_until_iso=None)

    def _on_pause_requested(self, duration_seconds: int | None) -> None:
        """Handle pause/snooze request from tray menu."""
        if duration_seconds is None:
            # Indefinite snooze
            self._config_store.update(snooze_until_iso="indefinite")
        else:
            # Timed snooze - calculate expiry time
            from datetime import timedelta
            now = datetime.now(timezone.utc)
            expires = now + timedelta(seconds=duration_seconds)
            self._config_store.update(snooze_until_iso=expires.isoformat())

        self._accumulator.snooze()
        self._tray.set_state(TrayIconState.PAUSED)
        self._event_log.append(AppEventKind.SNOOZE_START, duration_seconds=duration_seconds)

    def _on_resume_requested(self) -> None:
        """Handle resume request from tray menu."""
        self._accumulator.resume()
        self._tray.set_state(TrayIconState.ACTIVE)
        self._config_store.update(snooze_until_iso=None)
        self._event_log.append(AppEventKind.SNOOZE_END)

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
        if new_camera_index is not None and new_camera_index != self._window.camera()._index:
            self._switch_camera(new_camera_index)
        self._settings_dialog = None

    def _on_settings_changed(self) -> None:
        """Handle settings changed - reload config and apply autostart."""
        self._config = self._config_store.load()
        self._autostart_manager.apply_config(self._config.autostart_enabled)

    def _on_calibration_completed(self, yaw: float, roll: float) -> None:
        """Handle calibration completed - reload config to get updated neutral pose."""
        # Log the calibration event
        self._event_log.append(
            AppEventKind.STATE_CHANGE,
            state=f"CALIBRATED: yaw={yaw:+.1f}°, roll={roll:+.1f}°"
        )
        self._config = self._config_store.load()

    def _switch_camera(self, index: int) -> None:
        """Switch to a different camera."""
        camera = self._window.camera()
        camera.close()
        camera._index = index
        camera.open()

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
        camera = self._window.camera()
        camera.close()
        detector = self._window.detector()
        if detector is not None:
            detector.close()

    def _on_about_to_quit(self) -> None:
        self._timer.stop()
        self._camera_retry_timer.stop()
        self._window.close()

    def _get_classify_kwargs(self) -> dict:
        """Return classify() kwargs from current config."""
        return {
            "neutral": NeutralPose(yaw=self._config.neutral_yaw, roll=self._config.neutral_roll),
            "thresholds": Thresholds(yaw_deg=self._config.yaw_threshold, roll_deg=self._config.roll_threshold),
        }

    def _log_state_change(self, state: PoseState) -> None:
        """Log STATE_CHANGE event if state differs from last."""
        if state != self._last_state:
            self._event_log.append(AppEventKind.STATE_CHANGE, state=state.value)
            self._last_state = state

    def run(self) -> None:
        """Show the window, open camera + detector, start the tick loop."""
        self._window.show()

        if not self._window.init_camera_and_detector():
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
        camera = self._window.camera()
        if camera.retry_open():
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
        self._check_snooze_expiry()

        camera = self._window.camera()
        detector = self._window.detector()

        # If camera is unavailable, show message if not already shown
        if not camera.is_available:
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

        frame = camera.read()
        self._window.update_frame(frame)

        current_yaw: float | None = None
        current_roll: float | None = None

        if frame is None or detector is None:
            self._window.set_state(None, None, None)
            current_state = PoseState.NO_FACE
        else:
            pose = detector.detect(frame)
            if pose is None:
                self._window.set_state(None, None, None)
                current_state = PoseState.NO_FACE
            else:
                current_yaw, current_roll = pose
                state = classify(current_yaw, current_roll, **self._get_classify_kwargs())
                self._window.set_state(current_yaw, current_roll, state)
                current_state = state

        # Collect calibration samples if settings dialog is open and calibrating
        if self._settings_dialog is not None and current_yaw is not None and current_roll is not None:
            self._settings_dialog.add_calibration_sample(current_yaw, current_roll)

        # Log state changes
        self._log_state_change(current_state)

        # Accumulate off-axis time and trigger overlay if correction due
        # (AccumulatorEngine.tick() returns None during snooze automatically)
        correction = self._accumulator.tick(current_state, _DT_SECONDS)
        if correction is not None:
            direction = "LEFT" if correction == PoseState.OFF_AXIS_LEFT else "RIGHT"
            self._event_log.append(AppEventKind.PROMPT_FIRED, prompt="adjust", direction=direction)
            self._overlay.show_correction(correction)

        # S4: good posture encouragement when facing threshold reached
        if self._accumulator.good_posture_due:
            self._event_log.append(AppEventKind.PROMPT_FIRED, prompt="good_posture")
            self._overlay.show_good_posture()
            self._accumulator.acknowledge()

        # S5: eye rest reminder when presence threshold reached
        if self._accumulator.eye_rest_due:
            self._event_log.append(AppEventKind.PROMPT_FIRED, prompt="eye_rest")
            self._overlay.show_eye_rest()
            self._accumulator.acknowledge()

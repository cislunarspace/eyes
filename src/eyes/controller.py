"""AppController — orchestrates the camera -> detect -> classify -> update-UI loop at 10 Hz."""

from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .accumulator import AccumulatorEngine
from .classifier import NeutralPose, PoseState, Thresholds, classify
from .config_store import ConfigStore
from .event_log import EventLog
from .main_window import MainWindow
from .overlay import NotifierOverlay
from .tray_controller import TrayController, TrayIconState
from .types import AppEventKind

# Tick interval: 100 ms = 0.1 seconds
_DT_SECONDS = 0.1


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

        # Accumulator engine for off-axis streak tracking
        self._accumulator = AccumulatorEngine()

        # Overlay for correction prompts
        self._overlay = NotifierOverlay()

        # Tray controller
        self._tray = TrayController()
        self._tray.pause_requested.connect(self._on_pause_requested)
        self._tray.resume_requested.connect(self._on_resume_requested)
        self._tray.settings_requested.connect(self._on_settings_requested)
        self._tray.quit_requested.connect(self._on_quit_requested)

        # Track previous state for STATE_CHANGE events
        self._last_state: PoseState | None = None
        # Track camera availability for CAMERA_UNAVAILABLE/RESUMED events
        self._camera_was_available = False

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
        """Handle settings request from tray menu (placeholder)."""
        # Show the main window
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

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
            # Camera unavailable — still show the window; tick loop will
            # keep retrying via camera.retry_open()
            self._event_log.append(AppEventKind.CAMERA_UNAVAILABLE)
            self._camera_was_available = False
            self._tray.set_state(TrayIconState.UNAVAILABLE)
        else:
            self._camera_was_available = True

        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self._app.exec()

    def _tick(self) -> None:
        """One 10 Hz tick: read, detect, classify, accumulate, update UI."""
        # Check if timed snooze has expired
        self._check_snooze_expiry()

        camera = self._window.camera()
        detector = self._window.detector()

        # Try to open camera if not available
        if not camera.is_available:
            camera.retry_open()
            self._window.set_state(None, None, None)
            if self._camera_was_available:
                self._event_log.append(AppEventKind.CAMERA_UNAVAILABLE)
                self._camera_was_available = False
                self._tray.set_state(TrayIconState.UNAVAILABLE)
            return

        if not self._camera_was_available:
            self._event_log.append(AppEventKind.CAMERA_RESUMED)
            self._camera_was_available = True
            # Restore to active/paused state (not unavailable)
            self._tray.set_state(TrayIconState.ACTIVE if not self._accumulator.is_snoozed else TrayIconState.PAUSED)

        frame = camera.read()
        self._window.update_frame(frame)

        if frame is None or detector is None:
            self._window.set_state(None, None, None)
            current_state = PoseState.NO_FACE
        else:
            pose = detector.detect(frame)
            if pose is None:
                self._window.set_state(None, None, None)
                current_state = PoseState.NO_FACE
            else:
                yaw, roll = pose
                state = classify(yaw, roll, **self._get_classify_kwargs())
                self._window.set_state(yaw, roll, state)
                current_state = state

        # Log state changes
        self._log_state_change(current_state)

        # Accumulate off-axis time and trigger overlay if correction due
        # (AccumulatorEngine.tick() returns None during snooze automatically)
        correction = self._accumulator.tick(current_state, _DT_SECONDS)
        if correction is not None:
            direction = "LEFT" if correction == PoseState.OFF_AXIS_LEFT else "RIGHT"
            self._event_log.append(AppEventKind.PROMPT_FIRED, prompt="adjust", direction=direction)
            self._overlay.show_correction(correction)

    def _check_snooze_expiry(self) -> None:
        """Check if timed snooze has expired and resume if needed."""
        if not self._accumulator.is_snoozed:
            return
        snooze_until = self._config.snooze_until_iso
        if snooze_until is None or snooze_until == "indefinite":
            return
        # Check expiry
        try:
            snooze_time = datetime.fromisoformat(snooze_until)
            if snooze_time.tzinfo is None:
                snooze_time = snooze_time.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if now >= snooze_time:
                self._accumulator.resume()
                self._tray.set_state(TrayIconState.ACTIVE)
                self._config_store.update(snooze_until_iso=None)
                self._event_log.append(AppEventKind.SNOOZE_END)
        except ValueError:
            pass

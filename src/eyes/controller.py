"""AppController — thin assembler for the monitoring stack.

Wires VisionInput, SenseLoop, SenseEventBus,
SnoozeManager, SettingsBridge, and the Qt UI together. The 10 Hz tick
calls `_tick`; per-event fan-out is handled by SenseEventBus; the
config-rebuild sequence is handled by SettingsBridge. This module
only assembles those pieces and connects them to the Qt lifecycle.
"""

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
from .i18n import set_language
from .icon_factory import create_eye_icon
from .main_window import MainWindow
from .overlay import NotifierOverlay
from .sense_event_bus import FrameProcessed, SenseEventBus
from .sense_loop import AccumulatorConfig, SenseLoop
from .settings_bridge import SettingsBridge
from .settings_dialog import SettingsDialog
from .snooze_manager import SnoozeManager
from .tray_controller import TrayController
from .types import AppEventKind, TrayIconState, WarningLevel, WarningLevelEvent
from .runtime_timings import CAMERA_RETRY_INTERVAL_TICKS, TICK_INTERVAL_MS, TICK_INTERVAL_SECONDS
from .vision_input import FrameReady, VisionInput, VisionUnavailable


class AppController:
    """Assembles the monitoring stack and owns the Qt lifecycle."""

    def __init__(self, app: QApplication, camera_index: int | None = None) -> None:
        self._app = app
        self._config_store = ConfigStore()
        self._config = self._config_store.load()
        set_language(self._config.language)
        self._event_log = EventLog()
        if camera_index is None:
            camera_index = self._config.camera_index
        self._vision = VisionInput(
            camera=CameraSource(index=camera_index),
            detector_factory=HeadPoseDetector,
            retry_interval_ticks=CAMERA_RETRY_INTERVAL_TICKS,
        )
        self._window = MainWindow()
        self._timer = QTimer()
        self._timer.setInterval(TICK_INTERVAL_MS)  # 10 Hz
        self._sense_loop = SenseLoop(
            None,
            neutral=NeutralPose(yaw=self._config.neutral_yaw, pitch=self._config.neutral_pitch),
            thresholds=Thresholds(
                yaw_deg=self._config.yaw_threshold,
                pitch_deg=self._config.pitch_threshold,
                pitch_hysteresis_deg=self._config.pitch_hysteresis,
            ),
            accumulator_config=AccumulatorConfig(
                off_axis_streak_threshold_seconds=self._config.off_axis_streak_threshold_seconds,
                off_axis_repeat_interval_seconds=self._config.off_axis_repeat_interval_seconds,
                facing_threshold_seconds=self._config.facing_threshold_seconds,
                eyest_threshold_seconds=self._config.eyest_threshold_seconds,
            ),
        )
        self._accumulator = self._sense_loop.engine
        self._overlay = NotifierOverlay()
        self._tray = TrayController()
        self._tray.show_window_requested.connect(self._show_window)
        self._tray.settings_requested.connect(self._on_settings_requested)
        self._tray.quit_requested.connect(self._on_quit_requested)
        self._tray.pause_requested.connect(self._on_pause_requested)
        self._tray.resume_requested.connect(self._on_resume_requested)
        self._bus = SenseEventBus(event_log=self._event_log, overlay=self._overlay, window=self._window)
        self._autostart_manager = AutostartManager()
        self._settings_bridge = SettingsBridge(
            config_store=self._config_store,
            sense_loop=self._sense_loop,
            autostart=self._autostart_manager,
            window=self._window,
            overlay=self._overlay,
            tray=self._tray,
        )
        self._snooze_manager = SnoozeManager(
            self._config_store,
            self._accumulator,
            self._tray,
            on_snooze_end=lambda: self._event_log.append(AppEventKind.SNOOZE_END),
        )
        self._last_state: PoseState | None = None
        self._settings_dialog: SettingsDialog | None = None
        self._snooze_manager.restore_persisted_state()
        self._app.aboutToQuit.connect(self._on_about_to_quit)
        self._window.close_requested.connect(self._window.hide)

    # --- Tray signal handlers ---
    def _show_window(self) -> None:
        self._window.show(), self._window.raise_(), self._window.activateWindow()

    def _on_pause_requested(self, duration_seconds: int | None) -> None:
        self._snooze_manager.pause(duration_seconds)
        self._event_log.append(AppEventKind.SNOOZE_START, duration_seconds=duration_seconds)

    def _on_resume_requested(self) -> None:
        self._snooze_manager.resume()
        self._event_log.append(AppEventKind.SNOOZE_END)

    def _on_quit_requested(self) -> None:
        if self._accumulator.is_snoozed:
            self._event_log.append(AppEventKind.SNOOZE_END)
        self._app.quit()

    def _on_settings_requested(self) -> None:
        self._show_window()
        self._settings_dialog = SettingsDialog(self._config_store, self._window)
        self._settings_dialog.settings_changed.connect(self._on_settings_changed)
        self._settings_dialog.calibration_completed.connect(self._on_calibration_completed)
        self._settings_dialog.exec()
        new_camera_index = self._settings_dialog.get_pending_camera_index()
        if new_camera_index is not None:
            self._vision.set_camera_index(new_camera_index)
        self._settings_dialog = None

    def _on_settings_changed(self) -> None:
        self._config = self._config_store.load()
        self._settings_bridge.apply_config()

    def _on_calibration_completed(self, yaw: float, pitch: float) -> None:
        self._event_log.append(
            AppEventKind.STATE_CHANGE,
            state=f"CALIBRATED: yaw={yaw:+.1f}°, pitch={pitch:+.1f}°",
        )
        self._config = self._config_store.load()
        self._settings_bridge.apply_calibration(yaw, pitch)

    def _feed_calibration(self, yaw: float | None, pitch: float | None) -> None:
        if self._settings_dialog is None:
            return
        self._settings_dialog.update_current_pose(yaw, pitch)
        if yaw is not None and pitch is not None:
            self._settings_dialog.add_calibration_sample(yaw, pitch)

    # --- Lifecycle ---
    def close(self) -> None:
        self._window.close()
        self._vision.close()

    def _on_about_to_quit(self) -> None:
        self._timer.stop()
        self._window.close()

    def run(self) -> None:
        self._window.setWindowIcon(create_eye_icon(TrayIconState.ACTIVE))
        self._window.show()
        self._tray.show()
        result = self._vision.start()
        if result is not None:
            self._on_vision_unavailable(result)
        else:
            self._sense_loop.detector = self._vision.detector
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._app.exec()

    # --- Vision transitions ---
    def _on_vision_resumed(self) -> None:
        self._event_log.append(AppEventKind.CAMERA_RESUMED)
        self._tray.set_state(
            TrayIconState.ACTIVE if not self._accumulator.is_snoozed else TrayIconState.PAUSED
        )
        self._window.clear_camera_unavailable_message()

    def _on_vision_unavailable(self, result: VisionUnavailable) -> None:
        if result.detector_error is not None:
            self._event_log.append(AppEventKind.STATE_CHANGE, state=result.detector_error)
        else:
            self._event_log.append(AppEventKind.CAMERA_UNAVAILABLE)
        self._tray.set_state(TrayIconState.UNAVAILABLE)
        self._window.show_camera_unavailable_message()

    def _reset_window_to_neutral(self) -> None:
        self._window.set_warning_level(WarningLevelEvent(level=WarningLevel.NORMAL, direction=None))
        self._window.set_state(None, None, None)

    # --- Tick ---
    def _log_state_change(self, state: PoseState) -> None:
        if state != self._last_state:
            self._event_log.append(AppEventKind.STATE_CHANGE, state=state.value)
            self._last_state = state

    def _tick(self) -> None:
        self._snooze_manager.check_expiry()
        result = self._vision.tick()
        if isinstance(result, FrameReady):
            just_resumed = result.just_resumed
            if just_resumed:
                self._sense_loop.detector = self._vision.detector
            events = self._sense_loop.tick(result.frame, TICK_INTERVAL_SECONDS)
            processed = FrameProcessed(
                frame=result.frame,
                yaw=self._sense_loop.current_yaw,
                pitch=self._sense_loop.current_pitch,
                state=self._sense_loop.current_state,
                events=list(events),
                vision_resumed=just_resumed,
                vision_just_failed=False,
                vision_detector_error=None,
            )
            if just_resumed:
                self._on_vision_resumed()
            self._window.update_frame(processed.frame)
            self._window.set_state(processed.yaw, processed.pitch, processed.state)
            self._feed_calibration(processed.yaw, processed.pitch)
            self._log_state_change(processed.state)
            self._bus.dispatch(processed.events)
        else:
            just_failed = bool(getattr(result, "just_failed", False))
            detector_error = getattr(result, "detector_error", None)
            if just_failed or detector_error is not None:
                self._on_vision_unavailable(result)
            else:
                self._reset_window_to_neutral()
            self._window.set_state(None, None, PoseState.NO_FACE)
            self._feed_calibration(None, None)
            self._log_state_change(PoseState.NO_FACE)
            self._bus.dispatch([])

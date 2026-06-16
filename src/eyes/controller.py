"""AppController — thin assembler for the monitoring stack.

Wires VisionInput, SenseLoop, MonitoringLoop, SenseEventBus,
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
from .monitoring_loop import MonitoringLoop
from .overlay import NotifierOverlay
from .sense_event_bus import SenseEventBus
from .sense_loop import AccumulatorConfig, SenseLoop
from .settings_bridge import SettingsBridge
from .settings_dialog import SettingsDialog
from .snooze_manager import SnoozeManager
from .tray_controller import TrayController
from .types import AppEventKind, TrayIconState, WarningLevel, WarningLevelEvent
from .runtime_timings import CAMERA_RETRY_INTERVAL_TICKS, TICK_INTERVAL_MS, TICK_INTERVAL_SECONDS
from .vision_input import VisionInput, VisionUnavailable


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
            neutral=NeutralPose(yaw=self._config.neutral_yaw, roll=self._config.neutral_roll),
            thresholds=Thresholds(yaw_deg=self._config.yaw_threshold, roll_deg=self._config.roll_threshold),
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
        self._monitoring_loop = MonitoringLoop(
            vision=self._vision,
            sense_loop=self._sense_loop,
            dt_seconds=TICK_INTERVAL_SECONDS,
            calibration_sink=self._feed_calibration,
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

    def _on_calibration_completed(self, yaw: float, roll: float) -> None:
        self._event_log.append(
            AppEventKind.STATE_CHANGE,
            state=f"CALIBRATED: yaw={yaw:+.1f}°, roll={roll:+.1f}°",
        )
        self._config = self._config_store.load()
        self._settings_bridge.apply_calibration(yaw, roll)

    def _feed_calibration(self, yaw: float | None, roll: float | None) -> None:
        if self._settings_dialog is None:
            return
        self._settings_dialog.update_current_pose(yaw, roll)
        if yaw is not None and roll is not None:
            self._settings_dialog.add_calibration_sample(yaw, roll)

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
        processed = self._monitoring_loop.process_one()
        if processed.vision_resumed:
            self._on_vision_resumed()
        elif processed.vision_just_failed or processed.vision_detector_error is not None:
            self._on_vision_unavailable(
                VisionUnavailable(
                    just_failed=processed.vision_just_failed,
                    detector_error=processed.vision_detector_error,
                )
            )
        elif processed.frame is None:
            self._reset_window_to_neutral()
        if processed.frame is not None:
            self._window.update_frame(processed.frame)
        self._window.set_state(processed.yaw, processed.roll, processed.state)
        self._monitoring_loop.feed_calibration(processed.yaw, processed.roll)
        self._log_state_change(processed.state)
        self._bus.dispatch(processed.events)

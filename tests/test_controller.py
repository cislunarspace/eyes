"""Tests for AppController prompt event dispatch."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from eyes.classifier import HeadPose, NeutralPose, PoseState, Thresholds
from eyes.controller import AppController
from eyes.main_window import MainWindow
from eyes.overlay import NotifierOverlay
from eyes.sense_loop import (
    AccumulatorConfig,
    CorrectionEvent,
    EyeRestEvent,
    GoodPostureEvent,
    SenseLoop,
)
from eyes.types import AppEventKind, TrayIconState, WarningLevel, WarningLevelEvent
from eyes.vision_input import FrameReady, VisionUnavailable


class TestShowWindowSignal:
    """Verify AppController connects tray.show_window_requested to window."""

    def test_show_window_requested_shows_and_activates_window(self) -> None:
        controller = object.__new__(AppController)
        controller._window = MagicMock()
        controller._tray = MagicMock()
        controller._on_show_window_requested()
        controller._window.show.assert_called_once()
        controller._window.raise_.assert_called_once()
        controller._window.activateWindow.assert_called_once()


class TestMainWindowAsPureView:
    """Verify MainWindow is a pure view with no hardware resource ownership."""

    def test_main_window_has_no_camera_attribute(self, qtbot) -> None:
        """MainWindow should not have a _camera attribute (ownership moved to controller)."""
        window = MainWindow()
        qtbot.addWidget(window)
        assert not hasattr(window, "_camera")

    def test_main_window_has_no_detector_attribute(self, qtbot) -> None:
        """MainWindow should not have a _detector attribute (ownership moved to controller)."""
        window = MainWindow()
        qtbot.addWidget(window)
        assert not hasattr(window, "_detector")

    def test_main_window_has_no_camera_method(self, qtbot) -> None:
        """MainWindow should not have a camera() method."""
        window = MainWindow()
        qtbot.addWidget(window)
        assert not hasattr(window, "camera")

    def test_main_window_has_no_detector_method(self, qtbot) -> None:
        """MainWindow should not have a detector() method."""
        window = MainWindow()
        qtbot.addWidget(window)
        assert not hasattr(window, "detector")

    def test_main_window_has_no_init_camera_and_detector_method(self, qtbot) -> None:
        """MainWindow should not have init_camera_and_detector() method."""
        window = MainWindow()
        qtbot.addWidget(window)
        assert not hasattr(window, "init_camera_and_detector")


class TestPromptDispatchBehavior:
    """Verify SenseEvent values are dispatched to overlay, window, and event log."""

    def test_good_posture_due_calls_overlay_show_good_posture(self) -> None:
        """When good_posture_due is True, overlay.show_good_posture() is called."""
        controller = object.__new__(AppController)
        overlay = MagicMock(spec=NotifierOverlay)
        event_log = MagicMock()
        controller._overlay = overlay
        controller._event_log = event_log

        controller._dispatch_prompt_event(GoodPostureEvent())

        overlay.show_good_posture.assert_called_once()
        overlay.show_eye_rest.assert_not_called()
        event_log.append.assert_called_once_with(AppEventKind.PROMPT_FIRED, prompt="good_posture")

    def test_eye_rest_due_calls_overlay_show_eye_rest(self) -> None:
        """When eye_rest_due is True, overlay.show_eye_rest() is called."""
        controller = object.__new__(AppController)
        overlay = MagicMock(spec=NotifierOverlay)
        event_log = MagicMock()
        controller._overlay = overlay
        controller._event_log = event_log

        controller._dispatch_prompt_event(EyeRestEvent())

        overlay.show_eye_rest.assert_called_once()
        overlay.show_good_posture.assert_not_called()
        event_log.append.assert_called_once_with(AppEventKind.PROMPT_FIRED, prompt="eye_rest")

    def test_both_due_calls_both_overlay_methods(self) -> None:
        """When both events are returned, both overlay methods are called."""
        controller = object.__new__(AppController)
        overlay = MagicMock(spec=NotifierOverlay)
        event_log = MagicMock()
        controller._overlay = overlay
        controller._event_log = event_log

        controller._dispatch_prompt_event(GoodPostureEvent())
        controller._dispatch_prompt_event(EyeRestEvent())

        overlay.show_good_posture.assert_called_once()
        overlay.show_eye_rest.assert_called_once()
        assert event_log.append.call_count == 2

    def test_warning_level_event_dispatches_to_window(self) -> None:
        """WarningLevelEvent is dispatched to window.set_warning_level and event log."""
        controller = object.__new__(AppController)
        overlay = MagicMock(spec=NotifierOverlay)
        event_log = MagicMock()
        window = MagicMock(spec=MainWindow)
        controller._overlay = overlay
        controller._event_log = event_log
        controller._window = window

        controller._dispatch_prompt_event(WarningLevelEvent(level=WarningLevel.WARNING, direction="left"))

        overlay.show_good_posture.assert_not_called()
        overlay.show_eye_rest.assert_not_called()
        overlay.show_correction.assert_not_called()
        window.set_warning_level.assert_called_once_with(WarningLevelEvent(level=WarningLevel.WARNING, direction="left"))
        event_log.append.assert_called_once_with(AppEventKind.WARNING_LEVEL_CHANGED, level="WARNING", direction="left")

    def test_correction_event_calls_overlay_show_correction(self) -> None:
        controller = object.__new__(AppController)
        overlay = MagicMock(spec=NotifierOverlay)
        event_log = MagicMock()
        controller._overlay = overlay
        controller._event_log = event_log

        controller._dispatch_prompt_event(
            CorrectionEvent(direction=PoseState.OFF_AXIS_RIGHT)
        )

        overlay.show_correction.assert_called_once_with(PoseState.OFF_AXIS_RIGHT)
        event_log.append.assert_called_once_with(
            AppEventKind.PROMPT_FIRED, prompt="adjust", direction="RIGHT"
        )

    def test_corrected_event_calls_overlay_show_corrected(self) -> None:
        controller = object.__new__(AppController)
        overlay = MagicMock(spec=NotifierOverlay)
        event_log = MagicMock()
        window = MagicMock(spec=MainWindow)
        controller._overlay = overlay
        controller._event_log = event_log
        controller._window = window

        controller._dispatch_prompt_event(
            WarningLevelEvent(level=WarningLevel.CORRECTED, direction=None)
        )

        overlay.show_corrected.assert_called_once()
        overlay.show_correction.assert_not_called()
        window.set_warning_level.assert_called_once()
        event_log.append.assert_called_once_with(
            AppEventKind.WARNING_LEVEL_CHANGED, level="CORRECTED", direction=None
        )

    def test_normal_event_hides_overlay(self) -> None:
        controller = object.__new__(AppController)
        overlay = MagicMock(spec=NotifierOverlay)
        event_log = MagicMock()
        window = MagicMock(spec=MainWindow)
        controller._overlay = overlay
        controller._event_log = event_log
        controller._window = window

        controller._dispatch_prompt_event(
            WarningLevelEvent(level=WarningLevel.NORMAL, direction=None)
        )

        overlay.hide.assert_called_once()
        window.set_warning_level.assert_called_once()
        event_log.append.assert_called_once_with(
            AppEventKind.WARNING_LEVEL_CHANGED, level="NORMAL", direction=None
        )


class _FixedPoseDetector:
    def __init__(self, pose: HeadPose | None) -> None:
        self.pose = pose

    def detect(self, frame: np.ndarray) -> HeadPose | None:
        return self.pose


class TestCameraRecovery:
    """Verify _tick() routes VisionInput results to event log, tray, and window."""

    def _make_controller(self) -> AppController:
        controller = object.__new__(AppController)
        controller._vision = MagicMock()
        controller._sense_loop = MagicMock()
        controller._sense_loop.tick.return_value = []
        controller._sense_loop.current_yaw = None
        controller._sense_loop.current_roll = None
        controller._sense_loop.current_state = PoseState.NO_FACE
        controller._event_log = MagicMock()
        controller._tray = MagicMock()
        controller._window = MagicMock()
        controller._overlay = MagicMock()
        controller._snooze_manager = MagicMock()
        controller._accumulator = MagicMock(is_snoozed=False)
        controller._settings_dialog = None
        controller._last_state = None
        return controller

    def test_tick_resumes_from_unavailable_logs_camera_resumed_and_clears_window(self) -> None:
        controller = self._make_controller()
        detector = object()
        controller._vision.detector = detector
        frame = np.zeros((1, 1, 3), dtype=np.uint8)
        controller._vision.tick.return_value = FrameReady(frame=frame, just_resumed=True)

        controller._tick()

        assert controller._sense_loop.detector is detector
        controller._event_log.append.assert_any_call(AppEventKind.CAMERA_RESUMED)
        controller._tray.set_state.assert_called_with(TrayIconState.ACTIVE)
        controller._window.clear_camera_unavailable_message.assert_called_once()

    def test_tick_resumes_with_paused_tray_when_snoozed(self) -> None:
        controller = self._make_controller()
        controller._accumulator.is_snoozed = True
        controller._vision.detector = object()
        frame = np.zeros((1, 1, 3), dtype=np.uint8)
        controller._vision.tick.return_value = FrameReady(frame=frame, just_resumed=True)

        controller._tick()

        controller._tray.set_state.assert_called_with(TrayIconState.PAUSED)

    def test_tick_just_failed_logs_camera_unavailable_and_shows_message(self) -> None:
        controller = self._make_controller()
        controller._vision.tick.return_value = VisionUnavailable(just_failed=True)

        controller._tick()

        controller._event_log.append.assert_called_once_with(AppEventKind.CAMERA_UNAVAILABLE)
        controller._tray.set_state.assert_called_with(TrayIconState.UNAVAILABLE)
        controller._window.show_camera_unavailable_message.assert_called_once()

    def test_tick_steady_unavailable_does_not_log_or_re_show(self) -> None:
        controller = self._make_controller()
        controller._vision.tick.return_value = VisionUnavailable(just_failed=False)

        controller._tick()

        controller._event_log.append.assert_not_called()
        controller._window.show_camera_unavailable_message.assert_not_called()
        controller._tray.set_state.assert_not_called()
        # UI is reset to a neutral state
        controller._window.set_warning_level.assert_called_once()
        controller._window.set_state.assert_called_once_with(None, None, None)

    def test_tick_detector_error_logs_state_change_with_model_load_failed(self) -> None:
        controller = self._make_controller()
        controller._vision.tick.return_value = VisionUnavailable(
            just_failed=False, detector_error="MODEL_LOAD_FAILED: boom"
        )

        controller._tick()

        controller._event_log.append.assert_called_once_with(
            AppEventKind.STATE_CHANGE, state="MODEL_LOAD_FAILED: boom"
        )
        controller._tray.set_state.assert_called_with(TrayIconState.UNAVAILABLE)
        controller._window.show_camera_unavailable_message.assert_called_once()


class TestWarningBannerEndToEnd:
    """Verify WarningLevelEvent flows from SenseLoop through AppController to MainWindow banner."""

    def test_continuous_off_axis_shows_warning_then_severe_banner(self, qtbot) -> None:
        loop = SenseLoop(
            _FixedPoseDetector(HeadPose(-2.0, 0.0)),
            neutral=NeutralPose(),
            thresholds=Thresholds(yaw_deg=1.0, roll_deg=90.0),
            accumulator_config=AccumulatorConfig(
                off_axis_streak_threshold_seconds=5.0,
                off_axis_repeat_interval_seconds=1.0,
                facing_threshold_seconds=300.0,
                eyest_threshold_seconds=900.0,
            ),
        )

        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        controller = object.__new__(AppController)
        controller._overlay = MagicMock()
        controller._event_log = MagicMock()
        controller._window = window

        # First tick: WARNING
        events = loop.tick(np.zeros((1, 1, 3), dtype=np.uint8), dt=0.1)
        warning_events = [e for e in events if isinstance(e, WarningLevelEvent)]
        assert len(warning_events) == 1
        assert warning_events[0].level == WarningLevel.WARNING

        controller._dispatch_prompt_event(warning_events[0])

        assert window._warning_banner.isVisible()
        assert "#FFD700" in window._warning_banner.styleSheet()
        assert "请正视屏幕" in window._warning_banner.text()

        # Second tick after repeat interval: SEVERE
        events = loop.tick(np.zeros((1, 1, 3), dtype=np.uint8), dt=1.0)
        warning_events = [e for e in events if isinstance(e, WarningLevelEvent)]
        assert len(warning_events) == 1
        assert warning_events[0].level == WarningLevel.SEVERE

        controller._dispatch_prompt_event(warning_events[0])

        assert window._warning_banner.isVisible()
        assert "#FF0000" in window._warning_banner.styleSheet()
        assert "请正视屏幕" in window._warning_banner.text()

    def test_corrected_timer_does_not_hide_new_warning_banner(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.set_warning_level(WarningLevelEvent(level=WarningLevel.CORRECTED, direction=None))
        assert window._warning_banner.isVisible()

        window.set_warning_level(WarningLevelEvent(level=WarningLevel.WARNING, direction="left"))

        qtbot.wait(2100)

        assert window._warning_banner.isVisible()
        assert "#FFD700" in window._warning_banner.styleSheet()

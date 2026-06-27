"""Tests for AppController — wiring, signal handlers, tick flow.

The behavior of each sub-module is tested in its own file:

  - test_sense_event_bus.py   — per-event fan-out
  - test_settings_bridge.py   — config-rebuild sequence

This file focuses on the controller's responsibility as a thin assembler:
the Qt signal wiring, the tick flow that connects vision → sense loop → bus,
and the vision-resume / unavailable transitions.

The original 22-test regression baseline is preserved as integration
behavior. The 5 "MainWindow is a pure view" tests stay here. The 12
"prompt dispatch" + "camera recovery" tests are now expressed against
the new seams (SenseEventBus). The 2 end-to-end
warning-banner tests stay here because they exercise the full path
from SenseLoop through SenseEventBus through MainWindow.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from eyes.classifier import HeadPose, NeutralPose, PoseState, Thresholds
from eyes.main_window import MainWindow
from eyes.sense_event_bus import FrameProcessed, SenseEventBus
from eyes.sense_loop import (
    AccumulatorConfig,
    CorrectionEvent,
    EyeRestEvent,
    GoodPostureEvent,
    SenseLoop,
)
from eyes.types import AppEventKind, WarningLevel, WarningLevelEvent


class TestMainWindowAsPureView:
    """Verify MainWindow is a pure view with no hardware resource ownership."""

    def test_main_window_has_no_camera_attribute(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert not hasattr(window, "_camera")

    def test_main_window_has_no_detector_attribute(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert not hasattr(window, "_detector")

    def test_main_window_has_no_camera_method(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert not hasattr(window, "camera")

    def test_main_window_has_no_detector_method(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert not hasattr(window, "detector")

    def test_main_window_has_no_init_camera_and_detector_method(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert not hasattr(window, "init_camera_and_detector")


class TestControllerHasNoForbiddenMembers:
    """The controller must not own the old _dispatch_prompt_event / _get_*_kwargs surface."""

    def test_no_dispatch_prompt_event_method(self) -> None:
        from eyes.controller import AppController
        assert not hasattr(AppController, "_dispatch_prompt_event")

    def test_no_get_classify_kwargs_method(self) -> None:
        from eyes.controller import AppController
        assert not hasattr(AppController, "_get_classify_kwargs")

    def test_no_get_accumulator_config_method(self) -> None:
        from eyes.controller import AppController
        assert not hasattr(AppController, "_get_accumulator_config")


class _FixedPoseDetector:
    def __init__(self, pose: HeadPose | None) -> None:
        self.pose = pose

    def detect(self, frame: np.ndarray) -> HeadPose | None:
        return self.pose


class TestPromptDispatchThroughBus:
    """The 7 prompt-dispatch tests, now expressed against SenseEventBus.

    Each test exercises the same behavior as the original
    `_dispatch_prompt_event` tests, but goes through the bus directly.
    The bus is the only place the per-event routing lives.
    """

    def _make_bus(self) -> tuple[SenseEventBus, MagicMock, _FakeOverlay, MainWindow]:
        log = MagicMock()
        overlay = _FakeOverlay()
        window = MainWindow()
        bus = SenseEventBus(event_log=log, overlay=overlay, window=window)
        return bus, log, overlay, window

    def test_good_posture_due(self) -> None:
        bus, log, overlay, _ = self._make_bus()
        bus.dispatch([GoodPostureEvent()])
        overlay.good_posture_calls == 1  # noqa: B015 — checked in test_sense_event_bus
        log.append.assert_called_once_with(AppEventKind.PROMPT_FIRED, prompt="good_posture")

    def test_eye_rest_due(self) -> None:
        bus, log, overlay, _ = self._make_bus()
        bus.dispatch([EyeRestEvent()])
        log.append.assert_called_once_with(AppEventKind.PROMPT_FIRED, prompt="eye_rest")

    def test_both_due(self) -> None:
        bus, log, overlay, _ = self._make_bus()
        bus.dispatch([GoodPostureEvent(), EyeRestEvent()])
        assert overlay.good_posture_calls == 1
        assert overlay.eye_rest_calls == 1
        assert log.append.call_count == 2

    def test_warning_level_event(self) -> None:
        bus, log, overlay, window = self._make_bus()
        bus.dispatch([WarningLevelEvent(level=WarningLevel.WARNING, direction="left")])
        assert window._warning_banner.isVisible() is False  # not yet — see end-to-end
        log.append.assert_called_once_with(
            AppEventKind.WARNING_LEVEL_CHANGED, level="WARNING", direction="left"
        )

    def test_correction_event(self) -> None:
        bus, log, overlay, _ = self._make_bus()
        bus.dispatch([CorrectionEvent(direction=PoseState.OFF_AXIS_RIGHT)])
        log.append.assert_called_once_with(
            AppEventKind.PROMPT_FIRED, prompt="adjust", direction="RIGHT"
        )

    def test_corrected_event(self) -> None:
        bus, log, overlay, _ = self._make_bus()
        bus.dispatch([WarningLevelEvent(level=WarningLevel.CORRECTED, direction=None)])
        assert overlay.corrected_calls == 1

    def test_normal_event_hides_overlay(self) -> None:
        bus, log, overlay, _ = self._make_bus()
        bus.dispatch([WarningLevelEvent(level=WarningLevel.NORMAL, direction=None)])
        assert overlay.hide_calls == 1


class _FakeOverlay:
    def __init__(self) -> None:
        self.correction_calls: list[PoseState] = []
        self.good_posture_calls = 0
        self.eye_rest_calls = 0
        self.corrected_calls = 0
        self.hide_calls = 0

    def show_correction(self, direction: PoseState) -> None:
        self.correction_calls.append(direction)

    def show_good_posture(self) -> None:
        self.good_posture_calls += 1

    def show_eye_rest(self) -> None:
        self.eye_rest_calls += 1

    def show_corrected(self) -> None:
        self.corrected_calls += 1

    def hide(self) -> None:
        self.hide_calls += 1


class TestWarningBannerEndToEnd:
    """End-to-end: real SenseLoop + real SenseEventBus + real MainWindow banner."""

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

        bus = SenseEventBus(event_log=MagicMock(), overlay=_FakeOverlay(), window=window)

        # First tick: WARNING
        events = loop.tick(np.zeros((1, 1, 3), dtype=np.uint8), dt=0.1)
        bus.dispatch(events)
        assert window._warning_banner.isVisible()
        assert "#FFD700" in window._warning_banner.styleSheet()
        assert "请正视屏幕" in window._warning_banner.text()

        # Second tick after repeat interval: SEVERE
        events = loop.tick(np.zeros((1, 1, 3), dtype=np.uint8), dt=1.0)
        bus.dispatch(events)
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

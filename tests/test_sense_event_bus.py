"""Tests for SenseEventBus — the per-event fan-out module."""

from __future__ import annotations

from unittest.mock import MagicMock

from eyes.classifier import PoseState
from eyes.sense_event_bus import SenseEventBus
from eyes.sense_loop import (
    CorrectionEvent,
    EyeRestEvent,
    GoodPostureEvent,
)
from eyes.types import AppEventKind, WarningLevel, WarningLevelEvent


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


class _FakeWindow:
    def __init__(self) -> None:
        self.warning_levels: list[WarningLevelEvent] = []

    def set_warning_level(self, event: WarningLevelEvent) -> None:
        self.warning_levels.append(event)


class TestGoodPostureDispatch:
    def test_logs_good_posture_event(self) -> None:
        log = MagicMock()
        bus = SenseEventBus(event_log=log, overlay=_FakeOverlay(), window=_FakeWindow())
        bus.dispatch([GoodPostureEvent()])
        log.append.assert_called_once_with(AppEventKind.PROMPT_FIRED, prompt="good_posture")

    def test_calls_overlay_show_good_posture(self) -> None:
        overlay = _FakeOverlay()
        bus = SenseEventBus(event_log=MagicMock(), overlay=overlay, window=_FakeWindow())
        bus.dispatch([GoodPostureEvent()])
        assert overlay.good_posture_calls == 1
        assert overlay.eye_rest_calls == 0


class TestEyeRestDispatch:
    def test_logs_eye_rest_event(self) -> None:
        log = MagicMock()
        bus = SenseEventBus(event_log=log, overlay=_FakeOverlay(), window=_FakeWindow())
        bus.dispatch([EyeRestEvent()])
        log.append.assert_called_once_with(AppEventKind.PROMPT_FIRED, prompt="eye_rest")

    def test_calls_overlay_show_eye_rest(self) -> None:
        overlay = _FakeOverlay()
        bus = SenseEventBus(event_log=MagicMock(), overlay=overlay, window=_FakeWindow())
        bus.dispatch([EyeRestEvent()])
        assert overlay.eye_rest_calls == 1
        assert overlay.good_posture_calls == 0


class TestBothDueDispatch:
    def test_dispatches_both_events_in_order(self) -> None:
        log = MagicMock()
        overlay = _FakeOverlay()
        bus = SenseEventBus(event_log=log, overlay=overlay, window=_FakeWindow())
        bus.dispatch([GoodPostureEvent(), EyeRestEvent()])
        assert overlay.good_posture_calls == 1
        assert overlay.eye_rest_calls == 1
        assert log.append.call_count == 2


class TestWarningLevelDispatch:
    def test_warning_routes_to_window(self) -> None:
        log = MagicMock()
        window = _FakeWindow()
        bus = SenseEventBus(event_log=log, overlay=_FakeOverlay(), window=window)
        event = WarningLevelEvent(level=WarningLevel.WARNING, direction="left")
        bus.dispatch([event])
        assert window.warning_levels == [event]
        log.append.assert_called_once_with(
            AppEventKind.WARNING_LEVEL_CHANGED, level="WARNING", direction="left"
        )

    def test_corrected_calls_overlay_show_corrected(self) -> None:
        log = MagicMock()
        overlay = _FakeOverlay()
        window = _FakeWindow()
        bus = SenseEventBus(event_log=log, overlay=overlay, window=window)
        bus.dispatch([WarningLevelEvent(level=WarningLevel.CORRECTED, direction=None)])
        assert overlay.corrected_calls == 1
        assert overlay.correction_calls == []
        assert window.warning_levels == [WarningLevelEvent(level=WarningLevel.CORRECTED, direction=None)]

    def test_normal_hides_overlay_and_routes_to_window(self) -> None:
        log = MagicMock()
        overlay = _FakeOverlay()
        window = _FakeWindow()
        bus = SenseEventBus(event_log=log, overlay=overlay, window=window)
        bus.dispatch([WarningLevelEvent(level=WarningLevel.NORMAL, direction=None)])
        assert overlay.hide_calls == 1
        assert window.warning_levels == [WarningLevelEvent(level=WarningLevel.NORMAL, direction=None)]


class TestCorrectionDispatch:
    def test_left_direction(self) -> None:
        log = MagicMock()
        overlay = _FakeOverlay()
        bus = SenseEventBus(event_log=log, overlay=overlay, window=_FakeWindow())
        bus.dispatch([CorrectionEvent(direction=PoseState.OFF_AXIS_LEFT, dimension="yaw")])
        assert overlay.correction_calls == [PoseState.OFF_AXIS_LEFT]
        log.append.assert_called_once_with(
            AppEventKind.PROMPT_FIRED, prompt="adjust", direction="OFF_AXIS_LEFT", dimension="yaw"
        )

    def test_right_direction(self) -> None:
        log = MagicMock()
        overlay = _FakeOverlay()
        bus = SenseEventBus(event_log=log, overlay=overlay, window=_FakeWindow())
        bus.dispatch([CorrectionEvent(direction=PoseState.OFF_AXIS_RIGHT, dimension="yaw")])
        assert overlay.correction_calls == [PoseState.OFF_AXIS_RIGHT]
        log.append.assert_called_once_with(
            AppEventKind.PROMPT_FIRED, prompt="adjust", direction="OFF_AXIS_RIGHT", dimension="yaw"
        )

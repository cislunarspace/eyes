"""Tests for MonitoringLoop — the per-tick match driver.

These tests do not spin up QApplication. The loop does not own a
QTimer; the caller drives `process_one` directly.
"""

from __future__ import annotations

from typing import Optional
from unittest.mock import MagicMock

import numpy as np

from eyes.classifier import HeadPose, PoseState
from eyes.monitoring_loop import MonitoringLoop
from eyes.sense_event_bus import FrameProcessed
from eyes.vision_input import FrameReady, VisionUnavailable


class _FakeVision:
    """VisionInput double that returns a queued sequence of results."""

    def __init__(self, results: list[object]) -> None:
        self._results = list(results)
        self.detector = object()

    def tick(self) -> object:
        if not self._results:
            raise AssertionError("tick called more times than queued results")
        return self._results.pop(0)


class _FakeSenseLoop:
    """SenseLoop double that records detector assignments and returns canned events."""

    def __init__(self) -> None:
        self.detector: object = None
        self.current_yaw: Optional[float] = None
        self.current_roll: Optional[float] = None
        self.current_state: PoseState = PoseState.NO_FACE
        self.tick_calls: list[object] = []

    def tick(self, frame: object, dt: float) -> list[object]:
        self.tick_calls.append((frame, dt))
        return []


def _frame() -> np.ndarray:
    return np.zeros((1, 1, 3), dtype=np.uint8)


class TestProcessOneFrameReady:
    def test_returns_frame_processed_with_pose(self) -> None:
        frame = _frame()
        sense_loop = _FakeSenseLoop()
        sense_loop.current_yaw = 0.5
        sense_loop.current_roll = 0.1
        sense_loop.current_state = PoseState.FACING_SCREEN
        vision = _FakeVision([FrameReady(frame=frame, just_resumed=False)])
        loop = MonitoringLoop(vision=vision, sense_loop=sense_loop, dt_seconds=0.1)

        processed = loop.process_one()

        assert isinstance(processed, FrameProcessed)
        assert processed.frame is frame
        assert processed.yaw == 0.5
        assert processed.roll == 0.1
        assert processed.state == PoseState.FACING_SCREEN
        assert processed.vision_resumed is False
        assert processed.vision_just_failed is False

    def test_just_resumed_attaches_detector(self) -> None:
        frame = _frame()
        sense_loop = _FakeSenseLoop()
        vision = _FakeVision([FrameReady(frame=frame, just_resumed=True)])
        new_detector = object()
        vision.detector = new_detector
        loop = MonitoringLoop(vision=vision, sense_loop=sense_loop)

        processed = loop.process_one()

        assert sense_loop.detector is new_detector
        assert processed.vision_resumed is True


class TestProcessOneVisionUnavailable:
    def test_returns_neutral_frame_processed(self) -> None:
        sense_loop = _FakeSenseLoop()
        vision = _FakeVision([VisionUnavailable(just_failed=True)])
        loop = MonitoringLoop(vision=vision, sense_loop=sense_loop)

        processed = loop.process_one()

        assert processed.frame is None
        assert processed.yaw is None
        assert processed.roll is None
        assert processed.state == PoseState.NO_FACE
        assert processed.vision_resumed is False
        assert processed.vision_just_failed is True
        assert processed.vision_detector_error is None

    def test_propagates_detector_error(self) -> None:
        sense_loop = _FakeSenseLoop()
        vision = _FakeVision(
            [VisionUnavailable(just_failed=False, detector_error="MODEL_LOAD_FAILED: boom")]
        )
        loop = MonitoringLoop(vision=vision, sense_loop=sense_loop)

        processed = loop.process_one()

        assert processed.vision_detector_error == "MODEL_LOAD_FAILED: boom"


class TestFeedCalibration:
    def test_calls_calibration_sink(self) -> None:
        sink = MagicMock()
        loop = MonitoringLoop(
            vision=_FakeVision([]), sense_loop=_FakeSenseLoop(), calibration_sink=sink
        )
        loop.feed_calibration(0.5, 0.1)
        sink.assert_called_once_with(0.5, 0.1)

    def test_no_sink_does_not_raise(self) -> None:
        loop = MonitoringLoop(vision=_FakeVision([]), sense_loop=_FakeSenseLoop())
        loop.feed_calibration(0.5, 0.1)  # should not raise

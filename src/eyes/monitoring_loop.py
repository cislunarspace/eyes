"""MonitoringLoop — one sense cycle: vision tick → sense loop → FrameProcessed.

Pulled out of AppController so the orchestration of one tick
(camera tick → frame ready / unavailable → sense loop → frame processed)
lives in one place. The loop does not own a QTimer; the caller (the
controller) drives `process_one` on its own timer, which keeps the loop
trivially testable without a Qt event loop.

The loop emits a `FrameProcessed` value per tick, which the caller
hands to a `SenseEventBus` for fan-out.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Optional, Protocol, Union

import numpy as np

from .classifier import PoseState
from .sense_event_bus import FrameProcessed
from .sense_loop import SenseLoop
from .vision_input import FrameReady, VisionInput, VisionUnavailable


VisionTickResult = Union[FrameReady, VisionUnavailable]


class VisionInputLike(Protocol):
    """Minimal interface the loop needs from the vision pipeline."""

    def tick(self) -> VisionTickResult: ...
    @property
    def detector(self) -> object: ...


class SenseLoopLike(Protocol):
    """Minimal interface the loop needs from the sense loop."""

    detector: object
    def tick(self, frame: object, dt: float) -> list[object]: ...
    @property
    def current_yaw(self) -> Optional[float]: ...
    @property
    def current_roll(self) -> Optional[float]: ...
    @property
    def current_state(self) -> PoseState: ...


class MonitoringLoop:
    """Drives one sense cycle and returns a FrameProcessed value.

    The loop does NOT log, render, or persist anything — that's the
    controller's job (via the SenseEventBus). It only:
      1. Ticks `VisionInput` once and matches on the result.
      2. On FrameReady: hands the frame to `SenseLoop`, captures the
         latest pose + state + emitted events, returns a
         `FrameProcessed` value.
      3. On VisionUnavailable: returns a `FrameProcessed` with
         frame=None and empty events. The caller decides what UI/state
         to reset.
    """

    CalibrationSink = Callable[[Optional[float], Optional[float]], None]

    def __init__(
        self,
        vision: VisionInputLike,
        sense_loop: SenseLoopLike,
        *,
        dt_seconds: float = 0.1,
        calibration_sink: Optional[CalibrationSink] = None,
    ) -> None:
        self._vision = vision
        self._sense_loop = sense_loop
        self._dt_seconds = dt_seconds
        self._calibration_sink = calibration_sink

    def process_one(self) -> FrameProcessed:
        """Run one sense cycle and return a FrameProcessed value."""
        result = self._vision.tick()
        if isinstance(result, FrameReady):
            just_resumed = result.just_resumed
            if just_resumed:
                self._sense_loop.detector = self._vision.detector
            processed = self._build_processed(result)
            return FrameProcessed(
                frame=processed.frame,
                yaw=processed.yaw,
                roll=processed.roll,
                state=processed.state,
                events=processed.events,
                vision_resumed=just_resumed,
                vision_just_failed=False,
                vision_detector_error=None,
            )
        # VisionUnavailable or any unknown type.
        just_failed = bool(getattr(result, "just_failed", False))
        detector_error = getattr(result, "detector_error", None)
        return FrameProcessed(
            frame=None,
            yaw=None,
            roll=None,
            state=PoseState.NO_FACE,
            events=[],
            vision_resumed=False,
            vision_just_failed=just_failed,
            vision_detector_error=detector_error,
        )

    def feed_calibration(self, yaw: Optional[float], roll: Optional[float]) -> None:
        """Forward a pose sample to the calibration sink if one is wired."""
        if self._calibration_sink is not None:
            self._calibration_sink(yaw, roll)

    def _build_processed(self, result: FrameReady) -> FrameProcessed:
        events = self._sense_loop.tick(result.frame, self._dt_seconds)
        return FrameProcessed(
            frame=result.frame,
            yaw=self._sense_loop.current_yaw,
            roll=self._sense_loop.current_roll,
            state=self._sense_loop.current_state,
            events=list(events),
        )

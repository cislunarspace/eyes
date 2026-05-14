"""Qt-free detect -> classify -> accumulate loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

import numpy as np

from .accumulator import AccumulatorEngine
from .classifier import HeadPose, NeutralPose, PoseState, Thresholds, classify
from .facing_time_accumulator import FacingTimeAccumulator
from .presence_time_accumulator import PresenceTimeAccumulator
from .types import WarningLevelEvent


class HeadPoseDetectorLike(Protocol):
    """Structural interface that any head-pose detector must satisfy.

    The sense loop depends on this protocol rather than a concrete detector
    class, allowing test doubles and alternative backends without coupling.
    Implementations receive a raw camera frame and return a :class:`HeadPose`
    with absolute yaw/roll angles (in degrees) when a face is found, or
    ``None`` when no face is detected.
    """

    def detect(self, frame: np.ndarray) -> Optional[HeadPose]:
        """Return a ``HeadPose`` when a face is detected, otherwise ``None``."""


@dataclass(frozen=True)
class AccumulatorConfig:
    off_axis_streak_threshold_seconds: float | None = None
    off_axis_repeat_interval_seconds: float | None = None
    facing_threshold_seconds: float | None = None
    eyest_threshold_seconds: float | None = None


@dataclass(frozen=True)
class CorrectionEvent:
    direction: PoseState


@dataclass(frozen=True)
class GoodPostureEvent:
    pass


@dataclass(frozen=True)
class EyeRestEvent:
    pass


SenseEvent = CorrectionEvent | GoodPostureEvent | EyeRestEvent | WarningLevelEvent


class SenseLoop:
    """Run head-pose sensing without depending on Qt widgets."""

    def __init__(
        self,
        detector: HeadPoseDetectorLike | None,
        neutral: NeutralPose,
        thresholds: Thresholds,
        accumulator_config: AccumulatorConfig,
    ) -> None:
        self.detector = detector
        self.neutral = neutral
        self.thresholds = thresholds
        self.accumulator = AccumulatorEngine(
            off_axis_streak_threshold_seconds=accumulator_config.off_axis_streak_threshold_seconds,
            off_axis_repeat_interval_seconds=accumulator_config.off_axis_repeat_interval_seconds,
        )
        self.facing_time_accumulator = FacingTimeAccumulator(
            threshold_seconds=accumulator_config.facing_threshold_seconds,
        )
        self.presence_time_accumulator = PresenceTimeAccumulator(
            threshold_seconds=accumulator_config.eyest_threshold_seconds,
        )
        self.accumulator.register_snooze_target(self.facing_time_accumulator)
        self.accumulator.register_snooze_target(self.presence_time_accumulator)
        self.current_pose: Optional[HeadPose] = None
        self.current_state: PoseState = PoseState.NO_FACE

    @property
    def current_yaw(self) -> float | None:
        return self.current_pose.yaw if self.current_pose is not None else None

    @property
    def current_roll(self) -> float | None:
        return self.current_pose.roll if self.current_pose is not None else None

    def update_classifier(self, neutral: NeutralPose, thresholds: Thresholds) -> None:
        """Replace the calibration reference used by the classify step.

        Takes effect on the next :meth:`tick` call.  Typically called after
        the user completes a calibration gesture or when settings change.
        """
        self.neutral = neutral
        self.thresholds = thresholds

    def tick(self, frame: np.ndarray | None, dt: float) -> list[SenseEvent]:
        """Execute one sensing cycle and return emitted events.

        Pipeline
        --------
        1. **Detect** — feed the frame to the detector (or clear pose if
           frame/detector is absent).
        2. **Classify** — map the raw pose to a :class:`PoseState` using
           the current calibration.
        3. **Accumulate** — fan out the state to three independent
           accumulators:
           - ``AccumulatorEngine`` — streak tracking → :class:`CorrectionEvent`
             and :class:`WarningLevelEvent`.
           - ``FacingTimeAccumulator`` — cumulative facing time →
             :class:`GoodPostureEvent`.
           - ``PresenceTimeAccumulator`` — cumulative presence time →
             :class:`EyeRestEvent`.

        Parameters
        ----------
        frame:
            Camera frame for detection, or ``None`` to signal absence.
        dt:
            Seconds elapsed since the last tick.

        Returns
        -------
        list[SenseEvent]
            Zero or more events generated this cycle.
        """
        if frame is None or self.detector is None:
            self.current_pose = None
            self.current_state = PoseState.NO_FACE
        else:
            prev = self.current_state
            self.current_pose = self.detector.detect(frame)
            self.current_state = classify(
                self.current_pose,
                neutral=self.neutral,
                thresholds=self.thresholds,
                prev_state=prev,
            )

        events: list[SenseEvent] = []
        correction = self.accumulator.tick(self.current_state, dt)
        if correction is not None:
            events.append(CorrectionEvent(direction=correction))
        warning = self.accumulator.warning_event
        if warning is not None:
            events.append(warning)
        if self.facing_time_accumulator.tick(self.current_state, dt):
            events.append(GoodPostureEvent())
        if self.presence_time_accumulator.tick(self.current_state, dt):
            events.append(EyeRestEvent())
        return events

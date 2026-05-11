"""Qt-free detect -> classify -> accumulate loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

import numpy as np

from .accumulator import AccumulatorEngine
from .classifier import NeutralPose, PoseState, Thresholds, classify
from .types import WarningLevelEvent


class HeadPoseDetectorLike(Protocol):
    def detect(self, frame: np.ndarray) -> tuple[float, float] | None:
        """Return (yaw, roll) when a face is detected, otherwise None."""


@dataclass(frozen=True)
class AccumulatorConfig:
    off_axis_streak_threshold_seconds: float | None = None
    off_axis_repeat_interval_seconds: float | None = None
    facing_threshold_seconds: float | None = None
    eyest_threshold_seconds: float | None = None


@dataclass(frozen=True)
class PromptEvent:
    kind: str
    direction: Optional[PoseState] = None
    warning_level_event: Optional[WarningLevelEvent] = None


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
            facing_threshold_seconds=accumulator_config.facing_threshold_seconds,
            eyest_threshold_seconds=accumulator_config.eyest_threshold_seconds,
        )
        self.current_yaw: float | None = None
        self.current_roll: float | None = None
        self.current_state: PoseState = PoseState.NO_FACE

    def update_classifier(self, neutral: NeutralPose, thresholds: Thresholds) -> None:
        self.neutral = neutral
        self.thresholds = thresholds

    def tick(self, frame: np.ndarray | None, dt: float) -> list[PromptEvent]:
        if frame is None or self.detector is None:
            self.current_yaw = None
            self.current_roll = None
            self.current_state = PoseState.NO_FACE
        else:
            pose = self.detector.detect(frame)
            if pose is None:
                self.current_yaw = None
                self.current_roll = None
                self.current_state = PoseState.NO_FACE
            else:
                self.current_yaw, self.current_roll = pose
                self.current_state = classify(
                    self.current_yaw,
                    self.current_roll,
                    neutral=self.neutral,
                    thresholds=self.thresholds,
                )

        events: list[PromptEvent] = []
        correction = self.accumulator.tick(self.current_state, dt)
        if correction is not None:
            events.append(PromptEvent(kind="correction", direction=correction))
        warning = self.accumulator.warning_event
        if warning is not None:
            events.append(PromptEvent(kind="warning_level", warning_level_event=warning))
        if self.accumulator.good_posture_due:
            events.append(PromptEvent(kind="good_posture"))
        if self.accumulator.eye_rest_due:
            events.append(PromptEvent(kind="eye_rest"))
        if self.accumulator.good_posture_due or self.accumulator.eye_rest_due:
            self.accumulator.acknowledge()
        return events

"""Qt-free detect -> classify -> accumulate loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

import numpy as np

from .classifier import HeadPose, NeutralPose, PoseClassification, PoseState, Thresholds, classify
from .posture_tick_engine import (
    CorrectionEvent,
    EyeRestEvent,
    GoodPostureEvent,
    PostureTickEngine,
    SenseEvent,
)
from .types import WarningLevelEvent

__all__ = [
    "AccumulatorConfig",
    "CorrectionEvent",
    "EyeRestEvent",
    "GoodPostureEvent",
    "SenseEvent",
    "SenseLoop",
    "WarningLevelEvent",
]


class HeadPoseDetectorLike(Protocol):
    """Structural interface that any head-pose detector must satisfy."""

    def detect(self, frame: np.ndarray) -> Optional[HeadPose]:
        """Return a ``HeadPose`` when a face is detected, otherwise ``None``."""


@dataclass(frozen=True)
class AccumulatorConfig:
    off_axis_streak_threshold_seconds: float | None = None
    off_axis_repeat_interval_seconds: float | None = None
    facing_threshold_seconds: float | None = None
    eyest_threshold_seconds: float | None = None


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
        self.engine = PostureTickEngine(
            off_axis_streak_threshold_seconds=accumulator_config.off_axis_streak_threshold_seconds,
            off_axis_repeat_interval_seconds=accumulator_config.off_axis_repeat_interval_seconds,
            facing_threshold_seconds=accumulator_config.facing_threshold_seconds,
            eyest_threshold_seconds=accumulator_config.eyest_threshold_seconds,
        )
        self.current_pose: Optional[HeadPose] = None
        self.current_classification: PoseClassification = PoseClassification(
            PoseState.NO_FACE, PoseState.NO_FACE
        )

    @property
    def accumulator(self) -> PostureTickEngine:
        """Backward-compatible alias for the unified engine."""
        return self.engine

    @property
    def current_state(self) -> PoseState:
        """Backward-compatible accessor returning yaw axis state."""
        return self.current_classification.yaw_state

    @property
    def current_yaw(self) -> float | None:
        return self.current_pose.yaw if self.current_pose is not None else None

    @property
    def current_roll(self) -> float | None:
        return self.current_pose.roll if self.current_pose is not None else None

    def update_classifier(self, neutral: NeutralPose, thresholds: Thresholds) -> None:
        """Replace the calibration reference used by the classify step."""
        self.neutral = neutral
        self.thresholds = thresholds

    def tick(self, frame: np.ndarray | None, dt: float) -> list[SenseEvent]:
        """Execute one sensing cycle and return emitted events.

        Pipeline: detect -> classify -> accumulate via PostureTickEngine.
        """
        if frame is None or self.detector is None:
            self.current_pose = None
            self.current_classification = PoseClassification(
                PoseState.NO_FACE, PoseState.NO_FACE
            )
        else:
            prev = self.current_classification
            self.current_pose = self.detector.detect(frame)
            self.current_classification = classify(
                self.current_pose,
                neutral=self.neutral,
                thresholds=self.thresholds,
                prev_classification=prev,
            )

        return self.engine.tick(self.current_classification.yaw_state, dt)

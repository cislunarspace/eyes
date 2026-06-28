"""PoseClassifier — pure function mapping head angles to pose state.

Sign convention (per CONTEXT.md and detector.py boundary docs):
  Positive yaw   = head turned to the user's own RIGHT  → OFF_AXIS_RIGHT
  Negative yaw   = head turned to the user's own LEFT   → OFF_AXIS_LEFT
  Positive pitch = head tilted UP (仰头)
  Negative pitch = head tilted DOWN (低头)
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional


class PoseState(enum.Enum):
    """Discrete head-pose states used throughout the sensing pipeline.

    The sense loop produces one ``PoseState`` per axis via :func:`classify`.
    Downstream accumulators (streak, facing-time, presence-time) consume
    these states to drive warnings and corrective events.

    States
    ------
    FACING_SCREEN
        Head is within tolerance of the calibrated neutral pose on this axis.
        Counts as "good posture" for facing-time accumulation.
    OFF_AXIS_LEFT
        Head yaw deviates left beyond the yaw threshold.
        Triggers streak accumulation toward a correction event.
    OFF_AXIS_RIGHT
        Head yaw deviates right beyond the yaw threshold.
        Triggers streak accumulation toward a correction event.
    HEAD_UP
        Head pitch deviates upward beyond the pitch threshold.
    HEAD_DOWN
        Head pitch deviates downward beyond the pitch threshold.
    NO_FACE
        No face was detected in the frame. Pauses streak
        accumulation and contributes to presence-time tracking.
    """

    FACING_SCREEN = "FACING SCREEN"
    OFF_AXIS_LEFT = "OFF-AXIS LEFT"
    OFF_AXIS_RIGHT = "OFF-AXIS RIGHT"
    HEAD_UP = "HEAD UP"
    HEAD_DOWN = "HEAD DOWN"
    NO_FACE = "NO FACE"


@dataclass(frozen=True)
class PoseClassification:
    """Per-axis classification of head pose.

    yaw_state and pitch_state are independent; both can deviate simultaneously.
    """

    yaw_state: PoseState
    pitch_state: PoseState


@dataclass(frozen=True)
class HeadPose:
    """A single head-pose sample produced by ``HeadPoseDetector``.

    Fields
    ------
    yaw:
        Rotation of the head about the vertical (up) axis, in degrees.
    pitch:
        Pitch (up/down tilt) of the head in degrees, derived from landmark
        geometry.  Positive = looking up (仰头), negative = looking down (低头).

    Sign convention (ADR-0001 and CONTEXT.md)
    -----------------------------------------
    Positive yaw   = head turned to the user's own RIGHT
                    (camera sees the face rotated to its left).
    Negative yaw   = head turned to the user's own LEFT.
    Positive pitch = looking up (仰头).
    Negative pitch = looking down (低头).

    Immutability
    ------------
    ``HeadPose`` is a frozen value type — instances are safe to share between
    the detector, sense loop, and classifier without defensive copies.
    """

    yaw: float
    pitch: float


@dataclass(frozen=True)
class NeutralPose:
    yaw: float = 0.0
    pitch: float = 0.0


@dataclass(frozen=True)
class Thresholds:
    yaw_deg: float = 1.0
    yaw_hysteresis_deg: float = 0.5
    pitch_deg: float = 5.0
    pitch_hysteresis_deg: float = 2.5


def _classify_axis(
    dev: float,
    threshold: float,
    hysteresis: float,
    prev_state: PoseState,
    negative_state: PoseState,
    positive_state: PoseState,
) -> PoseState:
    """按单轴做迟滞分类。"""
    abs_dev = abs(dev)
    was_off_axis = prev_state in (
        PoseState.OFF_AXIS_LEFT,
        PoseState.OFF_AXIS_RIGHT,
        PoseState.HEAD_UP,
        PoseState.HEAD_DOWN,
    )

    if was_off_axis:
        outside = abs_dev > hysteresis
    else:
        outside = abs_dev > threshold

    if not outside:
        return PoseState.FACING_SCREEN

    if dev < 0:
        return negative_state
    else:
        return positive_state


def classify(
    pose: Optional[HeadPose],
    neutral: NeutralPose = NeutralPose(),
    thresholds: Thresholds = Thresholds(),
    prev_classification: PoseClassification = PoseClassification(
        PoseState.NO_FACE, PoseState.NO_FACE
    ),
) -> PoseClassification:
    """Classify the current head pose.

    Parameters
    ----------
    pose:
        The current head-pose sample, or ``None`` when no face is detected.
    neutral:
        The canonical yaw/pitch for "facing the screen" (default 0,0).
    thresholds:
        Tolerance thresholds (default yaw ±1°, pitch ±5°).
    prev_classification:
        The previous frame's PoseClassification, used for hysteresis. Each
        axis uses its own previous state.

    Returns
    -------
    PoseClassification

    Sign convention
    ---------------
    Positive yaw = head turned to the user's own right → OFF_AXIS_RIGHT.
    Negative yaw = head turned to the user's own left  → OFF_AXIS_LEFT.
    Positive pitch = looking up → HEAD_UP.
    Negative pitch = looking down → HEAD_DOWN.
    """

    if pose is None:
        return PoseClassification(PoseState.NO_FACE, PoseState.NO_FACE)

    yaw_dev = pose.yaw - neutral.yaw
    pitch_dev = pose.pitch - neutral.pitch

    yaw_state = _classify_axis(
        yaw_dev,
        thresholds.yaw_deg,
        thresholds.yaw_hysteresis_deg,
        prev_classification.yaw_state,
        PoseState.OFF_AXIS_LEFT,
        PoseState.OFF_AXIS_RIGHT,
    )

    pitch_state = _classify_axis(
        pitch_dev,
        thresholds.pitch_deg,
        thresholds.pitch_hysteresis_deg,
        prev_classification.pitch_state,
        PoseState.HEAD_DOWN,
        PoseState.HEAD_UP,
    )

    return PoseClassification(yaw_state, pitch_state)

"""PoseClassifier — pure function mapping head angles to pose state.

Sign convention (per CONTEXT.md and detector.py boundary docs):
  Positive yaw  = head turned to the user's own RIGHT  → OFF_AXIS_RIGHT
  Negative yaw  = head turned to the user's own LEFT   → OFF_AXIS_LEFT
  Positive roll = head tilted clockwise (right ear → right shoulder)
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional


class PoseState(enum.Enum):
    """Discrete head-pose states used throughout the sensing pipeline.

    The sense loop produces one ``PoseState`` per frame via :func:`classify`.
    Downstream accumulators (streak, facing-time, presence-time) consume
    these states to drive warnings and corrective events.

    States
    ------
    FACING_SCREEN
        Head is within tolerance of the calibrated neutral pose.
        Counts as "good posture" for facing-time accumulation.
    OFF_AXIS_LEFT
        Head yaw deviates left beyond the yaw threshold.
        Triggers streak accumulation toward a correction event.
    OFF_AXIS_RIGHT
        Head yaw deviates right beyond the yaw threshold.
        Triggers streak accumulation toward a correction event.
    OFF_AXIS_OTHER
        Roll-only deviation (yaw within threshold). Reserved for
        future use; currently unreachable because roll threshold is
        disabled by default.
    NO_FACE
        No face was detected in the frame. Pauses streak
        accumulation and contributes to presence-time tracking.
    """

    FACING_SCREEN = "FACING SCREEN"
    OFF_AXIS_LEFT = "OFF-AXIS LEFT"
    OFF_AXIS_RIGHT = "OFF-AXIS RIGHT"
    OFF_AXIS_OTHER = "OFF-AXIS OTHER"  # roll-only deviation
    NO_FACE = "NO FACE"


@dataclass(frozen=True)
class HeadPose:
    """A single head-pose sample produced by ``HeadPoseDetector``.

    Fields
    ------
    yaw:
        Rotation of the head about the vertical (up) axis, in degrees.
    roll:
        Tilt of the head about the forward (camera-facing) axis, in degrees.

    Sign convention (ADR-0001 and CONTEXT.md)
    -----------------------------------------
    Positive yaw   = head turned to the user's own RIGHT
                    (camera sees the face rotated to its left).
    Negative yaw   = head turned to the user's own LEFT.
    Positive roll  = head tilted clockwise (right ear → right shoulder).
    Pitch is intentionally omitted; callers MUST use this convention.

    Immutability
    ------------
    ``HeadPose`` is a frozen value type — instances are safe to share between
    the detector, sense loop, and classifier without defensive copies.
    """

    yaw: float
    roll: float


@dataclass(frozen=True)
class NeutralPose:
    yaw: float = 0.0
    roll: float = 0.0


@dataclass(frozen=True)
class Thresholds:
    yaw_deg: float = 1.0
    roll_deg: float = 90.0  # Disabled: roll no longer affects classification
    yaw_hysteresis_deg: float = 0.5


def classify(
    pose: Optional[HeadPose],
    neutral: NeutralPose = NeutralPose(),
    thresholds: Thresholds = Thresholds(),
    prev_state: PoseState = PoseState.NO_FACE,
) -> PoseState:
    """Classify the current head pose.

    Parameters
    ----------
    pose:
        The current head-pose sample, or ``None`` when no face is detected.
    neutral:
        The canonical yaw/roll for "facing the screen" (default 0,0).
    thresholds:
        Tolerance thresholds (default yaw ±1°, roll disabled).
    prev_state:
        The previous frame's PoseState, used for hysteresis. When the
        previous state was OFF_AXIS, a looser threshold
        (``yaw_hysteresis_deg``) is used to return to FACING_SCREEN,
        preventing flickering near the boundary.

    Returns
    -------
    PoseState

    Sign convention
    ---------------
    Positive yaw = head turned to the user's own right → OFF_AXIS_RIGHT.
    Negative yaw = head turned to the user's own left  → OFF_AXIS_LEFT.
    """
    if pose is None:
        return PoseState.NO_FACE

    yaw_dev = pose.yaw - neutral.yaw
    abs_yaw_dev = abs(yaw_dev)

    was_off_axis = prev_state in (PoseState.OFF_AXIS_LEFT, PoseState.OFF_AXIS_RIGHT)

    if was_off_axis:
        yaw_outside = abs_yaw_dev > thresholds.yaw_hysteresis_deg
    else:
        yaw_outside = abs_yaw_dev > thresholds.yaw_deg

    if not yaw_outside:
        return PoseState.FACING_SCREEN

    if yaw_dev < 0:
        return PoseState.OFF_AXIS_LEFT
    else:
        return PoseState.OFF_AXIS_RIGHT

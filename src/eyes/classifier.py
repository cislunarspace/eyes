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
    FACING_SCREEN = "FACING SCREEN"
    OFF_AXIS_LEFT = "OFF-AXIS LEFT"
    OFF_AXIS_RIGHT = "OFF-AXIS RIGHT"
    OFF_AXIS_OTHER = "OFF-AXIS OTHER"  # roll-only deviation
    NO_FACE = "NO FACE"


@dataclass(frozen=True)
class NeutralPose:
    yaw: float = 0.0
    roll: float = 0.0


@dataclass(frozen=True)
class Thresholds:
    yaw_deg: float = 15.0
    roll_deg: float = 10.0


def classify(
    yaw: Optional[float],
    roll: Optional[float],
    neutral: NeutralPose = NeutralPose(),
    thresholds: Thresholds = Thresholds(),
) -> PoseState:
    """Classify the current head pose.

    Parameters
    ----------
    yaw:
        Current yaw angle in degrees, or None if no face detected.
    roll:
        Current roll angle in degrees, or None if no face detected.
    neutral:
        The canonical yaw/roll for "facing the screen" (default 0,0).
    thresholds:
        Tolerance thresholds (default yaw ±15°, roll ±10°).

    Returns
    -------
    PoseState

    Sign convention
    ---------------
    Positive yaw = head turned to the user's own right → OFF_AXIS_RIGHT.
    Negative yaw = head turned to the user's own left  → OFF_AXIS_LEFT.
    """
    if yaw is None or roll is None:
        return PoseState.NO_FACE

    yaw_dev = yaw - neutral.yaw
    roll_dev = roll - neutral.roll

    yaw_outside = abs(yaw_dev) > thresholds.yaw_deg
    roll_outside = abs(roll_dev) > thresholds.roll_deg

    if not yaw_outside and not roll_outside:
        return PoseState.FACING_SCREEN

    if yaw_outside:
        if yaw_dev < 0:
            return PoseState.OFF_AXIS_LEFT
        else:
            return PoseState.OFF_AXIS_RIGHT

    # yaw within threshold but roll outside
    return PoseState.OFF_AXIS_OTHER

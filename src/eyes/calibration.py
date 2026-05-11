"""Calibration module for computing neutral pose from samples."""

from __future__ import annotations

from typing import NamedTuple


class PoseSample(NamedTuple):
    """A single yaw/roll sample from head pose detection."""

    yaw: float
    roll: float


def compute_median_pose(samples: list[PoseSample]) -> PoseSample:
    """Compute median yaw and roll from a list of pose samples.

    Sorts samples by yaw and returns the middle sample's yaw and roll.
    For even count (2 samples), returns the average of both samples.

    Args:
        samples: List of (yaw, roll) pose samples.

    Returns:
        PoseSample with median yaw and roll.

    Raises:
        ValueError: If samples list is empty.
    """
    if not samples:
        raise ValueError("At least one sample is required to compute median pose")

    sorted_by_yaw = sorted(samples, key=lambda s: s.yaw)
    n = len(sorted_by_yaw)

    if n == 1:
        return sorted_by_yaw[0]

    if n % 2 == 1:
        # Odd count: return the middle element
        mid = n // 2
        return sorted_by_yaw[mid]

    # Even count: average the two middle elements
    mid1 = n // 2 - 1
    mid2 = n // 2
    median_yaw = (sorted_by_yaw[mid1].yaw + sorted_by_yaw[mid2].yaw) / 2
    median_roll = (sorted_by_yaw[mid1].roll + sorted_by_yaw[mid2].roll) / 2
    return PoseSample(yaw=median_yaw, roll=median_roll)

"""Calibration module for computing neutral pose from samples."""

from __future__ import annotations

from dataclasses import dataclass
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


# Epsilon for floating-point countdown comparisons. 10 ticks of 0.1s leaves
# residue around 1e-16; choose a value comfortably above that yet far below
# any meaningful sampling interval.
_COUNTDOWN_EPSILON = 1e-9


@dataclass(frozen=True)
class CalibrationResult:
    """Final outcome of a calibration session."""

    yaw: float
    roll: float
    sample_count: int


class CalibrationSession:
    """Qt-free 5-second calibration session.

    Lifecycle:
        1. Construct with duration (default 5s); session starts inactive.
        2. Call start() to begin the countdown.
        3. Call feed(yaw, roll) from each pose update while active.
        4. Call tick(dt) on each timer tick; countdown decrements.
        5. Once countdown reaches 0, session is finished and inactive.
        6. result() returns the median pose, or None if no samples collected
           or session not finished.

    Independent of Qt — drive it from any timer or test harness.
    """

    def __init__(self, duration_seconds: float = 5.0) -> None:
        self._duration = duration_seconds
        self._countdown = 0.0
        self._samples: list[PoseSample] = []
        self._active = False
        self._finished = False

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def countdown_seconds(self) -> float:
        return self._countdown

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    def start(self) -> None:
        """Begin a fresh calibration session: clear samples and seed countdown."""
        self._samples = []
        self._countdown = self._duration
        self._active = True
        self._finished = False

    def feed(self, yaw: float, roll: float) -> None:
        """Record a pose sample. No-op when the session is inactive."""
        if not self._active:
            return
        self._samples.append(PoseSample(yaw=yaw, roll=roll))

    def tick(self, dt: float) -> None:
        """Advance the countdown. No-op when the session is inactive.

        When the countdown reaches zero the session deactivates and marks
        itself finished so that result() becomes available.
        """
        if not self._active:
            return
        self._countdown -= dt
        # Tolerate floating-point drift from accumulated 0.1s ticks.
        if self._countdown <= _COUNTDOWN_EPSILON:
            self._countdown = 0.0
            self._active = False
            self._finished = True

    def result(self) -> CalibrationResult | None:
        if not self._finished or not self._samples:
            return None
        median = compute_median_pose(self._samples)
        return CalibrationResult(
            yaw=median.yaw, roll=median.roll, sample_count=len(self._samples)
        )

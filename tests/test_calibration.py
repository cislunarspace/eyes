"""Tests for calibration module."""

from __future__ import annotations

from typing import NamedTuple

import pytest


class PoseSample(NamedTuple):
    """A single yaw/roll sample from head pose detection."""

    yaw: float
    roll: float


class TestCalibrationMedian:
    """Unit tests for calibration median computation."""

    def test_median_single_sample(self) -> None:
        """Median of one sample returns that sample."""
        from eyes.calibration import compute_median_pose

        samples = [PoseSample(yaw=5.0, roll=3.0)]
        result = compute_median_pose(samples)
        assert result.yaw == pytest.approx(5.0)
        assert result.roll == pytest.approx(3.0)

    def test_median_two_samples_odd_count(self) -> None:
        """Median of 2 samples returns the average of both."""
        from eyes.calibration import compute_median_pose

        samples = [PoseSample(yaw=2.0, roll=1.0), PoseSample(yaw=4.0, roll=3.0)]
        result = compute_median_pose(samples)
        assert result.yaw == pytest.approx(3.0)
        assert result.roll == pytest.approx(2.0)

    def test_median_three_samples(self) -> None:
        """Median of 3 samples returns the middle value when sorted."""
        from eyes.calibration import compute_median_pose

        samples = [
            PoseSample(yaw=1.0, roll=0.0),
            PoseSample(yaw=5.0, roll=10.0),
            PoseSample(yaw=3.0, roll=5.0),
        ]
        result = compute_median_pose(samples)
        # After sorting by yaw: (1,0), (3,5), (5,10) -> median is (3,5)
        assert result.yaw == pytest.approx(3.0)
        assert result.roll == pytest.approx(5.0)

    def test_median_five_samples(self) -> None:
        """Median of 5 samples returns the middle value."""
        from eyes.calibration import compute_median_pose

        samples = [
            PoseSample(yaw=10.0, roll=20.0),
            PoseSample(yaw=2.0, roll=4.0),
            PoseSample(yaw=8.0, roll=16.0),
            PoseSample(yaw=4.0, roll=8.0),
            PoseSample(yaw=6.0, roll=12.0),
        ]
        result = compute_median_pose(samples)
        # After sorting by yaw: (2,4), (4,8), (6,12), (8,16), (10,20) -> median is (6,12)
        assert result.yaw == pytest.approx(6.0)
        assert result.roll == pytest.approx(12.0)

    def test_median_with_negative_angles(self) -> None:
        """Median computation handles negative angles correctly."""
        from eyes.calibration import compute_median_pose

        samples = [
            PoseSample(yaw=-10.0, roll=5.0),
            PoseSample(yaw=10.0, roll=-5.0),
            PoseSample(yaw=0.0, roll=0.0),
        ]
        result = compute_median_pose(samples)
        # After sorting by yaw: (-10,5), (0,0), (10,-5) -> median is (0,0)
        assert result.yaw == pytest.approx(0.0)
        assert result.roll == pytest.approx(0.0)

    def test_median_with_float_values(self) -> None:
        """Median computation handles float values with precision."""
        from eyes.calibration import compute_median_pose

        samples = [
            PoseSample(yaw=1.234, roll=5.678),
            PoseSample(yaw=9.876, roll=3.456),
            PoseSample(yaw=5.555, roll=4.444),
        ]
        result = compute_median_pose(samples)
        assert result.yaw == pytest.approx(5.555, abs=0.001)
        assert result.roll == pytest.approx(4.444, abs=0.001)

    def test_median_empty_samples_raises(self) -> None:
        """Median of empty samples raises ValueError."""
        from eyes.calibration import compute_median_pose

        with pytest.raises(ValueError, match="At least one sample"):
            compute_median_pose([])

    def test_median_returns_named_tuple(self) -> None:
        """Median result is a PoseSample named tuple."""
        from eyes.calibration import compute_median_pose

        samples = [PoseSample(yaw=1.0, roll=2.0)]
        result = compute_median_pose(samples)
        assert isinstance(result, PoseSample)
        assert hasattr(result, "yaw")
        assert hasattr(result, "roll")

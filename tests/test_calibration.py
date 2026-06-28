"""Tests for calibration module."""

from __future__ import annotations

from typing import NamedTuple

import pytest


class PoseSample(NamedTuple):
    """A single yaw/pitch sample from head pose detection."""

    yaw: float
    pitch: float


class TestCalibrationMedian:
    """Unit tests for calibration median computation."""

    def test_median_single_sample(self) -> None:
        """Median of one sample returns that sample."""
        from eyes.calibration import compute_median_pose

        samples = [PoseSample(yaw=5.0, pitch=3.0)]
        result = compute_median_pose(samples)
        assert result.yaw == pytest.approx(5.0)
        assert result.pitch == pytest.approx(3.0)

    def test_median_two_samples_odd_count(self) -> None:
        """Median of 2 samples returns the average of both."""
        from eyes.calibration import compute_median_pose

        samples = [PoseSample(yaw=2.0, pitch=1.0), PoseSample(yaw=4.0, pitch=3.0)]
        result = compute_median_pose(samples)
        assert result.yaw == pytest.approx(3.0)
        assert result.pitch == pytest.approx(2.0)

    def test_median_three_samples(self) -> None:
        """Median of 3 samples returns the middle value when sorted."""
        from eyes.calibration import compute_median_pose

        samples = [
            PoseSample(yaw=1.0, pitch=0.0),
            PoseSample(yaw=5.0, pitch=10.0),
            PoseSample(yaw=3.0, pitch=5.0),
        ]
        result = compute_median_pose(samples)
        # After sorting by yaw: (1,0), (3,5), (5,10) -> median is (3,5)
        assert result.yaw == pytest.approx(3.0)
        assert result.pitch == pytest.approx(5.0)

    def test_median_five_samples(self) -> None:
        """Median of 5 samples returns the middle value."""
        from eyes.calibration import compute_median_pose

        samples = [
            PoseSample(yaw=10.0, pitch=20.0),
            PoseSample(yaw=2.0, pitch=4.0),
            PoseSample(yaw=8.0, pitch=16.0),
            PoseSample(yaw=4.0, pitch=8.0),
            PoseSample(yaw=6.0, pitch=12.0),
        ]
        result = compute_median_pose(samples)
        # After sorting by yaw: (2,4), (4,8), (6,12), (8,16), (10,20) -> median is (6,12)
        assert result.yaw == pytest.approx(6.0)
        assert result.pitch == pytest.approx(12.0)

    def test_median_with_negative_angles(self) -> None:
        """Median computation handles negative angles correctly."""
        from eyes.calibration import compute_median_pose

        samples = [
            PoseSample(yaw=-10.0, pitch=5.0),
            PoseSample(yaw=10.0, pitch=-5.0),
            PoseSample(yaw=0.0, pitch=0.0),
        ]
        result = compute_median_pose(samples)
        # After sorting by yaw: (-10,5), (0,0), (10,-5) -> median is (0,0)
        assert result.yaw == pytest.approx(0.0)
        assert result.pitch == pytest.approx(0.0)

    def test_median_with_float_values(self) -> None:
        """Median computation handles float values with precision."""
        from eyes.calibration import compute_median_pose

        samples = [
            PoseSample(yaw=1.234, pitch=5.678),
            PoseSample(yaw=9.876, pitch=3.456),
            PoseSample(yaw=5.555, pitch=4.444),
        ]
        result = compute_median_pose(samples)
        assert result.yaw == pytest.approx(5.555, abs=0.001)
        assert result.pitch == pytest.approx(4.444, abs=0.001)

    def test_median_empty_samples_raises(self) -> None:
        """Median of empty samples raises ValueError."""
        from eyes.calibration import compute_median_pose

        with pytest.raises(ValueError, match="At least one sample"):
            compute_median_pose([])

    def test_median_returns_named_tuple(self) -> None:
        """Median result is a PoseSample named tuple."""
        from eyes.calibration import compute_median_pose

        samples = [PoseSample(yaw=1.0, pitch=2.0)]
        result = compute_median_pose(samples)
        assert isinstance(result, PoseSample)
        assert hasattr(result, "yaw")
        assert hasattr(result, "pitch")


class TestCalibrationSessionLifecycle:
    """Unit tests for CalibrationSession — Qt-free lifecycle behavior.

    Behaviors verified through the public interface only:
        - Session is inactive until started.
        - start() activates the session and seeds the countdown.
        - feed() collects samples only while active.
        - tick(dt) decrements the countdown and finishes the session at 0.
        - result() yields the median pose once finished, None otherwise.
    """

    def test_new_session_is_inactive(self) -> None:
        """A freshly constructed session is not yet collecting samples."""
        from eyes.calibration import CalibrationSession

        session = CalibrationSession(duration_seconds=5.0)
        assert session.is_active is False
        assert session.sample_count == 0
        assert session.result() is None

    def test_start_activates_session_and_seeds_countdown(self) -> None:
        """start() flips is_active and exposes the full duration as countdown."""
        from eyes.calibration import CalibrationSession

        session = CalibrationSession(duration_seconds=5.0)
        session.start()

        assert session.is_active is True
        assert session.countdown_seconds == pytest.approx(5.0)

    def test_feed_collects_samples_only_while_active(self) -> None:
        """feed() records samples while active, is a no-op before start()."""
        from eyes.calibration import CalibrationSession

        session = CalibrationSession(duration_seconds=5.0)

        # Inactive: feed is ignored.
        session.feed(yaw=1.0, pitch=2.0)
        assert session.sample_count == 0

        # Active: feed accumulates.
        session.start()
        session.feed(yaw=1.0, pitch=2.0)
        session.feed(yaw=3.0, pitch=4.0)
        assert session.sample_count == 2

    def test_tick_decrements_countdown_while_active(self) -> None:
        """tick(dt) shrinks countdown_seconds by dt without finishing prematurely."""
        from eyes.calibration import CalibrationSession

        session = CalibrationSession(duration_seconds=5.0)
        session.start()
        session.tick(0.1)
        session.tick(0.4)

        assert session.is_active is True
        assert session.countdown_seconds == pytest.approx(4.5)

    def test_session_finishes_when_countdown_reaches_zero(self) -> None:
        """Once the countdown drains, the session deactivates and is_active is False."""
        from eyes.calibration import CalibrationSession

        session = CalibrationSession(duration_seconds=1.0)
        session.start()
        session.feed(yaw=2.0, pitch=1.0)

        # Drain the full duration in 10 ticks of 0.1s each.
        for _ in range(10):
            session.tick(0.1)

        assert session.is_active is False
        assert session.countdown_seconds <= 0

    def test_result_returns_median_of_fed_samples_after_finish(self) -> None:
        """After the session finishes, result() exposes the median pose."""
        from eyes.calibration import CalibrationResult, CalibrationSession

        session = CalibrationSession(duration_seconds=1.0)
        session.start()
        # Sorted by yaw: (1,0), (3,5), (5,10) -> median is (3,5)
        session.feed(yaw=1.0, pitch=0.0)
        session.feed(yaw=5.0, pitch=10.0)
        session.feed(yaw=3.0, pitch=5.0)

        for _ in range(10):
            session.tick(0.1)

        result = session.result()
        assert isinstance(result, CalibrationResult)
        assert result.yaw == pytest.approx(3.0)
        assert result.pitch == pytest.approx(5.0)
        assert result.sample_count == 3

    def test_result_is_none_when_no_samples_were_fed(self) -> None:
        """A session that finishes without samples yields no result."""
        from eyes.calibration import CalibrationSession

        session = CalibrationSession(duration_seconds=1.0)
        session.start()
        for _ in range(10):
            session.tick(0.1)

        assert session.is_active is False
        assert session.result() is None

    def test_result_is_none_while_session_still_active(self) -> None:
        """result() must not leak a partial median while sampling is ongoing."""
        from eyes.calibration import CalibrationSession

        session = CalibrationSession(duration_seconds=5.0)
        session.start()
        session.feed(yaw=3.0, pitch=5.0)
        session.tick(0.1)

        assert session.is_active is True
        assert session.result() is None

    def test_tick_is_noop_before_start(self) -> None:
        """Calling tick() on an unstarted session does not change state."""
        from eyes.calibration import CalibrationSession

        session = CalibrationSession(duration_seconds=5.0)
        session.tick(0.1)

        assert session.is_active is False
        assert session.countdown_seconds == pytest.approx(0.0)
        assert session.result() is None

    def test_restart_clears_previous_samples_and_countdown(self) -> None:
        """A second start() begins a clean session, discarding earlier samples."""
        from eyes.calibration import CalibrationSession

        session = CalibrationSession(duration_seconds=1.0)
        session.start()
        session.feed(yaw=42.0, pitch=42.0)
        for _ in range(10):
            session.tick(0.1)
        assert session.result() is not None  # previous run finished

        session.start()
        assert session.is_active is True
        assert session.sample_count == 0
        assert session.countdown_seconds == pytest.approx(1.0)
        assert session.result() is None

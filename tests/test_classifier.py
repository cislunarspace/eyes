"""Tests for PoseClassifier."""

from __future__ import annotations

import pytest

from eyes.classifier import (
    HeadPose,
    NeutralPose,
    PoseState,
    Thresholds,
    classify,
)


class TestHeadPose:
    """HeadPose is the named value type that flows through detect → classify."""

    def test_fields_are_readable(self) -> None:
        pose = HeadPose(yaw=12.5, roll=-4.0)
        assert pose.yaw == 12.5
        assert pose.roll == -4.0

    def test_is_frozen(self) -> None:
        pose = HeadPose(yaw=0.0, roll=0.0)
        with pytest.raises(AttributeError):
            pose.yaw = 1.0  # type: ignore[misc]

    def test_equality_is_value_based(self) -> None:
        assert HeadPose(1.0, 2.0) == HeadPose(1.0, 2.0)
        assert HeadPose(1.0, 2.0) != HeadPose(1.0, 2.5)


class TestClassifyNoFace:
    def test_returns_no_face_when_pose_is_none(self) -> None:
        assert classify(None) == PoseState.NO_FACE


class TestClassifyFacingScreen:
    def test_zero_deviation(self) -> None:
        assert classify(HeadPose(0.0, 0.0)) == PoseState.FACING_SCREEN

    def test_within_yaw_threshold(self) -> None:
        assert classify(HeadPose(0.5, 0.0)) == PoseState.FACING_SCREEN

    def test_at_yaw_threshold_boundary(self) -> None:
        assert classify(HeadPose(1.0, 0.0)) == PoseState.FACING_SCREEN
        assert classify(HeadPose(-1.0, 0.0)) == PoseState.FACING_SCREEN

    def test_roll_does_not_affect_classification(self) -> None:
        """Roll is disabled and should not affect classification."""
        assert classify(HeadPose(0.0, 80.0)) == PoseState.FACING_SCREEN
        assert classify(HeadPose(0.5, 80.0)) == PoseState.FACING_SCREEN

    def test_within_both_thresholds(self) -> None:
        assert classify(HeadPose(0.5, 80.0)) == PoseState.FACING_SCREEN


class TestClassifyOffAxisLeft:
    """Negative yaw = head turned to the user's own left → OFF_AXIS_LEFT."""

    def test_negative_yaw_exceeds_threshold(self) -> None:
        assert classify(HeadPose(-5.0, 0.0)) == PoseState.OFF_AXIS_LEFT

    def test_just_past_negative_yaw_threshold(self) -> None:
        assert classify(HeadPose(-2.0, 0.0)) == PoseState.OFF_AXIS_LEFT

    def test_at_exact_negative_yaw_boundary_is_still_facing(self) -> None:
        assert classify(HeadPose(-1.0, 0.0)) == PoseState.FACING_SCREEN

    def test_negative_yaw_ignores_roll(self) -> None:
        """Roll should not affect off-axis classification."""
        assert classify(HeadPose(-5.0, 80.0)) == PoseState.OFF_AXIS_LEFT


class TestClassifyOffAxisRight:
    """Positive yaw = head turned to the user's own right → OFF_AXIS_RIGHT."""

    def test_positive_yaw_exceeds_threshold(self) -> None:
        assert classify(HeadPose(5.0, 0.0)) == PoseState.OFF_AXIS_RIGHT

    def test_just_past_positive_yaw_threshold(self) -> None:
        assert classify(HeadPose(2.0, 0.0)) == PoseState.OFF_AXIS_RIGHT

    def test_at_exact_positive_yaw_boundary_is_still_facing(self) -> None:
        assert classify(HeadPose(1.0, 0.0)) == PoseState.FACING_SCREEN

    def test_positive_yaw_ignores_roll(self) -> None:
        """Roll should not affect off-axis classification."""
        assert classify(HeadPose(5.0, 80.0)) == PoseState.OFF_AXIS_RIGHT


class TestClassifyOffAxisOther:
    """OFF_AXIS_OTHER is no longer used since roll is disabled."""

    def test_large_roll_does_not_trigger_off_axis_other(self) -> None:
        """Roll is disabled, so large roll values should still be FACING_SCREEN."""
        assert classify(HeadPose(0.0, 80.0)) == PoseState.FACING_SCREEN
        assert classify(HeadPose(0.5, -80.0)) == PoseState.FACING_SCREEN

    def test_yaw_within_threshold_large_roll_is_still_facing(self) -> None:
        """Even large roll deviations should be ignored."""
        assert classify(HeadPose(0.5, 45.0)) == PoseState.FACING_SCREEN


class TestClassifyBothAxesDeviation:
    """Both yaw and roll outside threshold simultaneously."""

    def test_yaw_wins_over_roll(self) -> None:
        """When yaw exceeds threshold, roll is ignored."""
        assert classify(HeadPose(-5.0, 80.0)) == PoseState.OFF_AXIS_LEFT
        assert classify(HeadPose(5.0, -80.0)) == PoseState.OFF_AXIS_RIGHT


class TestClassifyNonZeroNeutral:
    """Neutral pose offset shifts the comparison baseline."""

    def test_non_zero_neutral_shifts_facing_window(self) -> None:
        neutral = NeutralPose(yaw=10.0, roll=5.0)
        # yaw_dev = 10 - 10 = 0 → within 1° → FACING_SCREEN
        assert classify(HeadPose(10.0, 0.0), neutral=neutral) == PoseState.FACING_SCREEN

    def test_non_zero_neutral_roll_is_ignored(self) -> None:
        """Roll in neutral pose should not affect classification."""
        neutral = NeutralPose(yaw=10.0, roll=5.0)
        # yaw_dev = 10 - 10 = 0 → within 1° → FACING_SCREEN (roll ignored)
        assert classify(HeadPose(10.0, 0.0), neutral=neutral) == PoseState.FACING_SCREEN
        # Large roll deviations are ignored
        assert classify(HeadPose(10.0, 90.0), neutral=neutral) == PoseState.FACING_SCREEN

    def test_non_zero_neutral_triggers_off_axis(self) -> None:
        neutral = NeutralPose(yaw=10.0, roll=5.0)
        # yaw_dev = 15 - 10 = 5 → exceeds 1° → OFF_AXIS_RIGHT
        assert classify(HeadPose(15.0, 90.0), neutral=neutral) == PoseState.OFF_AXIS_RIGHT

    def test_negative_values_in_neutral(self) -> None:
        neutral = NeutralPose(yaw=-10.0, roll=-5.0)
        # Centered relative to the offset neutral
        assert classify(HeadPose(-10.0, -5.0), neutral=neutral) == PoseState.FACING_SCREEN
        # yaw_dev = -15 - (-10) = -5 → exceeds 1° → OFF_AXIS_LEFT
        assert classify(HeadPose(-15.0, -5.0), neutral=neutral) == PoseState.OFF_AXIS_LEFT


class TestClassifyCustomThresholds:
    """Custom thresholds change the comparison boundaries."""

    def test_strict_thresholds(self) -> None:
        thresholds = Thresholds(yaw_deg=0.5, roll_deg=0.1)
        # 1° yaw → exceeds 0.5° → OFF_AXIS_RIGHT
        assert classify(HeadPose(1.0, 0.0), thresholds=thresholds) == PoseState.OFF_AXIS_RIGHT
        # 0.3° yaw → within 0.5° → FACING_SCREEN
        assert classify(HeadPose(0.3, 0.0), thresholds=thresholds) == PoseState.FACING_SCREEN

    def test_lenient_thresholds(self) -> None:
        thresholds = Thresholds(yaw_deg=30.0, roll_deg=20.0)
        # 25° yaw < 30° threshold → FACING_SCREEN
        assert classify(HeadPose(25.0, 0.0), thresholds=thresholds) == PoseState.FACING_SCREEN
        # Large roll is ignored
        assert classify(HeadPose(0.0, 90.0), thresholds=thresholds) == PoseState.FACING_SCREEN


class TestClassifyHysteresis:
    """Hysteresis prevents state flickering near the yaw threshold."""

    def test_default_prev_state_behaves_identically(self) -> None:
        """Without prev_state, classify behaves the same as before."""
        assert classify(HeadPose(0.5, 0.0)) == PoseState.FACING_SCREEN
        assert classify(HeadPose(1.5, 0.0)) == PoseState.OFF_AXIS_RIGHT

    def test_off_axis_stays_off_axis_in_hysteresis_zone(self) -> None:
        """When prev was OFF_AXIS, yaw_dev in hysteresis zone keeps OFF_AXIS."""
        assert (
            classify(HeadPose(0.7, 0.0), prev_state=PoseState.OFF_AXIS_RIGHT)
            == PoseState.OFF_AXIS_RIGHT
        )

    def test_off_axis_returns_to_facing_below_hysteresis(self) -> None:
        """When prev was OFF_AXIS, yaw_dev ≤ hysteresis returns FACING_SCREEN."""
        assert (
            classify(HeadPose(0.5, 0.0), prev_state=PoseState.OFF_AXIS_RIGHT)
            == PoseState.FACING_SCREEN
        )

    def test_facing_stays_facing_in_hysteresis_zone(self) -> None:
        """When prev was FACING_SCREEN, yaw_dev in hysteresis zone stays FACING_SCREEN."""
        assert (
            classify(HeadPose(0.7, 0.0), prev_state=PoseState.FACING_SCREEN)
            == PoseState.FACING_SCREEN
        )

    def test_custom_hysteresis_threshold(self) -> None:
        """Custom yaw_hysteresis_deg controls the return-to-facing boundary."""
        thresholds = Thresholds(yaw_deg=1.0, yaw_hysteresis_deg=0.3)
        # 0.5° > 0.3° hysteresis → stays OFF_AXIS
        assert (
            classify(
                HeadPose(0.5, 0.0),
                thresholds=thresholds,
                prev_state=PoseState.OFF_AXIS_RIGHT,
            )
            == PoseState.OFF_AXIS_RIGHT
        )
        # 0.3° ≤ 0.3° hysteresis → returns FACING_SCREEN
        assert (
            classify(
                HeadPose(0.3, 0.0),
                thresholds=thresholds,
                prev_state=PoseState.OFF_AXIS_RIGHT,
            )
            == PoseState.FACING_SCREEN
        )

    def test_hysteresis_applies_to_left_direction(self) -> None:
        """Hysteresis works symmetrically for OFF_AXIS_LEFT."""
        assert (
            classify(HeadPose(-0.7, 0.0), prev_state=PoseState.OFF_AXIS_LEFT)
            == PoseState.OFF_AXIS_LEFT
        )
        assert (
            classify(HeadPose(-0.5, 0.0), prev_state=PoseState.OFF_AXIS_LEFT)
            == PoseState.FACING_SCREEN
        )

    def test_no_face_prev_state_has_no_hysteresis(self) -> None:
        """NO_FACE prev_state uses strict threshold (no special treatment)."""
        assert (
            classify(HeadPose(0.7, 0.0), prev_state=PoseState.NO_FACE)
            == PoseState.FACING_SCREEN
        )


class TestClassifyPureFunction:
    """Verify classify is a pure function (no mutation, no side effects)."""

    def test_does_not_mutate_thresholds(self) -> None:
        t = Thresholds(yaw_deg=15.0, roll_deg=10.0)
        classify(HeadPose(20.0, 0.0), thresholds=t)
        assert t.yaw_deg == 15.0
        assert t.roll_deg == 10.0

    def test_does_not_mutate_neutral(self) -> None:
        n = NeutralPose(yaw=5.0, roll=5.0)
        classify(HeadPose(20.0, 0.0), neutral=n)
        assert n.yaw == 5.0
        assert n.roll == 5.0

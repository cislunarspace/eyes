"""Tests for PoseClassifier."""

from __future__ import annotations

import pytest

from eyes.classifier import (
    NeutralPose,
    PoseState,
    Thresholds,
    classify,
)


class TestClassifyNoFace:
    def test_returns_no_face_when_yaw_is_none(self) -> None:
        assert classify(None, 0.0) == PoseState.NO_FACE

    def test_returns_no_face_when_roll_is_none(self) -> None:
        assert classify(0.0, None) == PoseState.NO_FACE

    def test_returns_no_face_when_both_none(self) -> None:
        assert classify(None, None) == PoseState.NO_FACE


class TestClassifyFacingScreen:
    def test_zero_deviation(self) -> None:
        assert classify(0.0, 0.0) == PoseState.FACING_SCREEN

    def test_within_yaw_threshold(self) -> None:
        assert classify(10.0, 0.0) == PoseState.FACING_SCREEN

    def test_at_yaw_threshold_boundary(self) -> None:
        assert classify(15.0, 0.0) == PoseState.FACING_SCREEN
        assert classify(-15.0, 0.0) == PoseState.FACING_SCREEN

    def test_within_roll_threshold(self) -> None:
        assert classify(0.0, 8.0) == PoseState.FACING_SCREEN

    def test_at_roll_threshold_boundary(self) -> None:
        assert classify(0.0, 10.0) == PoseState.FACING_SCREEN
        assert classify(0.0, -10.0) == PoseState.FACING_SCREEN

    def test_within_both_thresholds(self) -> None:
        assert classify(10.0, 5.0) == PoseState.FACING_SCREEN


class TestClassifyOffAxisLeft:
    """Negative yaw = head turned to the user's own left → OFF_AXIS_LEFT."""

    def test_negative_yaw_exceeds_threshold(self) -> None:
        assert classify(-20.0, 0.0) == PoseState.OFF_AXIS_LEFT

    def test_just_past_negative_yaw_threshold(self) -> None:
        assert classify(-16.0, 0.0) == PoseState.OFF_AXIS_LEFT

    def test_at_exact_negative_yaw_boundary_is_still_facing(self) -> None:
        assert classify(-15.0, 0.0) == PoseState.FACING_SCREEN

    def test_negative_yaw_within_roll_threshold(self) -> None:
        assert classify(-20.0, 5.0) == PoseState.OFF_AXIS_LEFT


class TestClassifyOffAxisRight:
    """Positive yaw = head turned to the user's own right → OFF_AXIS_RIGHT."""

    def test_positive_yaw_exceeds_threshold(self) -> None:
        assert classify(20.0, 0.0) == PoseState.OFF_AXIS_RIGHT

    def test_just_past_positive_yaw_threshold(self) -> None:
        assert classify(16.0, 0.0) == PoseState.OFF_AXIS_RIGHT

    def test_at_exact_positive_yaw_boundary_is_still_facing(self) -> None:
        assert classify(15.0, 0.0) == PoseState.FACING_SCREEN

    def test_positive_yaw_within_roll_threshold(self) -> None:
        assert classify(20.0, 5.0) == PoseState.OFF_AXIS_RIGHT


class TestClassifyOffAxisOther:
    """Roll-only deviation (within yaw threshold, exceeding roll threshold)."""

    def test_positive_roll_exceeds_threshold(self) -> None:
        assert classify(0.0, 15.0) == PoseState.OFF_AXIS_OTHER

    def test_negative_roll_exceeds_threshold(self) -> None:
        assert classify(0.0, -15.0) == PoseState.OFF_AXIS_OTHER

    def test_roll_just_past_threshold(self) -> None:
        assert classify(5.0, 11.0) == PoseState.OFF_AXIS_OTHER

    def test_roll_at_boundary_is_facing(self) -> None:
        assert classify(0.0, 10.0) == PoseState.FACING_SCREEN


class TestClassifyBothAxesDeviation:
    """Both yaw and roll outside threshold simultaneously."""

    def test_both_exceed(self) -> None:
        # yaw wins — OFF_AXIS_LEFT takes priority over OFF_AXIS_OTHER
        assert classify(-20.0, 15.0) == PoseState.OFF_AXIS_LEFT
        assert classify(20.0, -15.0) == PoseState.OFF_AXIS_RIGHT


class TestClassifyNonZeroNeutral:
    """Neutral pose offset shifts the comparison baseline."""

    def test_non_zero_neutral_shifts_facing_window(self) -> None:
        neutral = NeutralPose(yaw=10.0, roll=5.0)
        # yaw_dev = 10 - 10 = 0, roll_dev = 0 - 5 = -5 → both within threshold
        assert classify(10.0, 0.0, neutral=neutral) == PoseState.FACING_SCREEN

    def test_non_zero_neutral_triggers_off_axis(self) -> None:
        neutral = NeutralPose(yaw=10.0, roll=5.0)
        # yaw_dev = 20 - 10 = 10 → within 15°
        # roll_dev = 20 - 5 = 15 → exceeds 10° → roll-only → OFF_AXIS_OTHER
        assert classify(20.0, 20.0, neutral=neutral) == PoseState.OFF_AXIS_OTHER

    def test_negative_values_in_neutral(self) -> None:
        neutral = NeutralPose(yaw=-10.0, roll=-5.0)
        # Centered relative to the offset neutral
        assert classify(-10.0, -5.0, neutral=neutral) == PoseState.FACING_SCREEN
        # yaw_dev = -20 - (-10) = -10 → within 15° → FACING_SCREEN
        assert classify(-20.0, -5.0, neutral=neutral) == PoseState.FACING_SCREEN


class TestClassifyCustomThresholds:
    """Custom thresholds change the comparison boundaries."""

    def test_strict_thresholds(self) -> None:
        thresholds = Thresholds(yaw_deg=5.0, roll_deg=5.0)
        # 8° yaw → exceeds 5° → OFF_AXIS_RIGHT
        assert classify(8.0, 0.0, thresholds=thresholds) == PoseState.OFF_AXIS_RIGHT
        # 4° yaw → within 5° → FACING_SCREEN
        assert classify(4.0, 0.0, thresholds=thresholds) == PoseState.FACING_SCREEN

    def test_lenient_thresholds(self) -> None:
        thresholds = Thresholds(yaw_deg=30.0, roll_deg=20.0)
        # 25° yaw < 30° threshold → FACING_SCREEN
        assert classify(25.0, 0.0, thresholds=thresholds) == PoseState.FACING_SCREEN
        # 15° roll < 20° threshold → FACING_SCREEN
        assert classify(0.0, 15.0, thresholds=thresholds) == PoseState.FACING_SCREEN


class TestClassifyPureFunction:
    """Verify classify is a pure function (no mutation, no side effects)."""

    def test_does_not_mutate_thresholds(self) -> None:
        t = Thresholds(yaw_deg=15.0, roll_deg=10.0)
        classify(20.0, 0.0, thresholds=t)
        assert t.yaw_deg == 15.0
        assert t.roll_deg == 10.0

    def test_does_not_mutate_neutral(self) -> None:
        n = NeutralPose(yaw=5.0, roll=5.0)
        classify(20.0, 0.0, neutral=n)
        assert n.yaw == 5.0
        assert n.roll == 5.0

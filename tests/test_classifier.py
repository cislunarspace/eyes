"""Tests for PoseClassifier."""

from __future__ import annotations

import pytest

from eyes.classifier import (
    HeadPose,
    NeutralPose,
    PoseClassification,
    PoseState,
    Thresholds,
    classify,
)


class TestHeadPose:
    """HeadPose is the named value type that flows through detect → classify."""

    def test_fields_are_readable(self) -> None:
        pose = HeadPose(yaw=12.5, pitch=-4.0)
        assert pose.yaw == 12.5
        assert pose.pitch == -4.0

    def test_is_frozen(self) -> None:
        pose = HeadPose(yaw=0.0, pitch=0.0)
        with pytest.raises(AttributeError):
            pose.yaw = 1.0  # type: ignore[misc]

    def test_equality_is_value_based(self) -> None:
        assert HeadPose(1.0, 2.0) == HeadPose(1.0, 2.0)
        assert HeadPose(1.0, 2.0) != HeadPose(1.0, 2.5)


class TestPoseClassification:
    """PoseClassification holds per-axis states."""

    def test_fields_are_readable(self) -> None:
        pc = PoseClassification(
            yaw_state=PoseState.FACING_SCREEN, pitch_state=PoseState.HEAD_UP
        )
        assert pc.yaw_state == PoseState.FACING_SCREEN
        assert pc.pitch_state == PoseState.HEAD_UP

    def test_is_frozen(self) -> None:
        pc = PoseClassification(PoseState.NO_FACE, PoseState.NO_FACE)
        with pytest.raises(AttributeError):
            pc.yaw_state = PoseState.FACING_SCREEN  # type: ignore[misc]


class TestClassifyNoFace:
    def test_returns_no_face_for_both_axes_when_pose_is_none(self) -> None:
        result = classify(None)
        assert result.yaw_state == PoseState.NO_FACE
        assert result.pitch_state == PoseState.NO_FACE


class TestClassifyFacingScreen:
    def test_zero_deviation(self) -> None:
        result = classify(HeadPose(0.0, 0.0))
        assert result.yaw_state == PoseState.FACING_SCREEN
        assert result.pitch_state == PoseState.FACING_SCREEN

    def test_within_yaw_threshold(self) -> None:
        result = classify(HeadPose(0.5, 0.0))
        assert result.yaw_state == PoseState.FACING_SCREEN

    def test_at_yaw_threshold_boundary(self) -> None:
        result = classify(HeadPose(1.0, 0.0))
        assert result.yaw_state == PoseState.FACING_SCREEN
        result = classify(HeadPose(-1.0, 0.0))
        assert result.yaw_state == PoseState.FACING_SCREEN

    def test_within_pitch_threshold(self) -> None:
        result = classify(HeadPose(0.0, 3.0))
        assert result.pitch_state == PoseState.FACING_SCREEN

    def test_at_pitch_threshold_boundary(self) -> None:
        result = classify(HeadPose(0.0, 5.0))
        assert result.pitch_state == PoseState.FACING_SCREEN
        result = classify(HeadPose(0.0, -5.0))
        assert result.pitch_state == PoseState.FACING_SCREEN

    def test_within_both_thresholds(self) -> None:
        result = classify(HeadPose(0.5, 3.0))
        assert result.yaw_state == PoseState.FACING_SCREEN
        assert result.pitch_state == PoseState.FACING_SCREEN


class TestClassifyOffAxisLeft:
    """Negative yaw = head turned to the user's own left → OFF_AXIS_LEFT."""

    def test_negative_yaw_exceeds_threshold(self) -> None:
        result = classify(HeadPose(-5.0, 0.0))
        assert result.yaw_state == PoseState.OFF_AXIS_LEFT

    def test_just_past_negative_yaw_threshold(self) -> None:
        result = classify(HeadPose(-2.0, 0.0))
        assert result.yaw_state == PoseState.OFF_AXIS_LEFT

    def test_at_exact_negative_yaw_boundary_is_still_facing(self) -> None:
        result = classify(HeadPose(-1.0, 0.0))
        assert result.yaw_state == PoseState.FACING_SCREEN

    def test_negative_yaw_with_pitch_deviation(self) -> None:
        result = classify(HeadPose(-5.0, 10.0))
        assert result.yaw_state == PoseState.OFF_AXIS_LEFT
        assert result.pitch_state == PoseState.HEAD_UP


class TestClassifyOffAxisRight:
    """Positive yaw = head turned to the user's own right → OFF_AXIS_RIGHT."""

    def test_positive_yaw_exceeds_threshold(self) -> None:
        result = classify(HeadPose(5.0, 0.0))
        assert result.yaw_state == PoseState.OFF_AXIS_RIGHT

    def test_just_past_positive_yaw_threshold(self) -> None:
        result = classify(HeadPose(2.0, 0.0))
        assert result.yaw_state == PoseState.OFF_AXIS_RIGHT

    def test_at_exact_positive_yaw_boundary_is_still_facing(self) -> None:
        result = classify(HeadPose(1.0, 0.0))
        assert result.yaw_state == PoseState.FACING_SCREEN

    def test_positive_yaw_with_pitch_deviation(self) -> None:
        result = classify(HeadPose(5.0, -10.0))
        assert result.yaw_state == PoseState.OFF_AXIS_RIGHT
        assert result.pitch_state == PoseState.HEAD_DOWN


class TestClassifyHeadUp:
    """Positive pitch = looking up → HEAD_UP."""

    def test_positive_pitch_exceeds_threshold(self) -> None:
        result = classify(HeadPose(0.0, 10.0))
        assert result.pitch_state == PoseState.HEAD_UP

    def test_just_past_positive_pitch_threshold(self) -> None:
        result = classify(HeadPose(0.0, 6.0))
        assert result.pitch_state == PoseState.HEAD_UP

    def test_at_exact_positive_pitch_boundary_is_still_facing(self) -> None:
        result = classify(HeadPose(0.0, 5.0))
        assert result.pitch_state == PoseState.FACING_SCREEN

    def test_head_up_with_yaw_deviation(self) -> None:
        result = classify(HeadPose(-5.0, 10.0))
        assert result.yaw_state == PoseState.OFF_AXIS_LEFT
        assert result.pitch_state == PoseState.HEAD_UP


class TestClassifyHeadDown:
    """Negative pitch = looking down → HEAD_DOWN."""

    def test_negative_pitch_exceeds_threshold(self) -> None:
        result = classify(HeadPose(0.0, -10.0))
        assert result.pitch_state == PoseState.HEAD_DOWN

    def test_just_past_negative_pitch_threshold(self) -> None:
        result = classify(HeadPose(0.0, -6.0))
        assert result.pitch_state == PoseState.HEAD_DOWN

    def test_at_exact_negative_pitch_boundary_is_still_facing(self) -> None:
        result = classify(HeadPose(0.0, -5.0))
        assert result.pitch_state == PoseState.FACING_SCREEN

    def test_head_down_with_yaw_deviation(self) -> None:
        result = classify(HeadPose(5.0, -10.0))
        assert result.yaw_state == PoseState.OFF_AXIS_RIGHT
        assert result.pitch_state == PoseState.HEAD_DOWN


class TestClassifyYawAndPitchCombined:
    """Both axes can deviate simultaneously."""

    def test_both_axes_off_axis(self) -> None:
        result = classify(HeadPose(-5.0, 10.0))
        assert result.yaw_state == PoseState.OFF_AXIS_LEFT
        assert result.pitch_state == PoseState.HEAD_UP

    def test_yaw_off_axis_pitch_facing(self) -> None:
        result = classify(HeadPose(5.0, 3.0))
        assert result.yaw_state == PoseState.OFF_AXIS_RIGHT
        assert result.pitch_state == PoseState.FACING_SCREEN

    def test_pitch_off_axis_yaw_facing(self) -> None:
        result = classify(HeadPose(0.5, -10.0))
        assert result.yaw_state == PoseState.FACING_SCREEN
        assert result.pitch_state == PoseState.HEAD_DOWN


class TestClassifyNonZeroNeutral:
    """Neutral pose offset shifts the comparison baseline."""

    def test_non_zero_neutral_shifts_facing_window(self) -> None:
        neutral = NeutralPose(yaw=10.0, pitch=5.0)
        result = classify(HeadPose(10.0, 5.0), neutral=neutral)
        assert result.yaw_state == PoseState.FACING_SCREEN
        assert result.pitch_state == PoseState.FACING_SCREEN

    def test_non_zero_neutral_triggers_off_axis(self) -> None:
        neutral = NeutralPose(yaw=10.0, pitch=5.0)
        result = classify(HeadPose(15.0, 5.0), neutral=neutral)
        assert result.yaw_state == PoseState.OFF_AXIS_RIGHT
        result = classify(HeadPose(10.0, 12.0), neutral=neutral)
        assert result.pitch_state == PoseState.HEAD_UP

    def test_negative_values_in_neutral(self) -> None:
        neutral = NeutralPose(yaw=-10.0, pitch=-5.0)
        result = classify(HeadPose(-10.0, -5.0), neutral=neutral)
        assert result.yaw_state == PoseState.FACING_SCREEN
        assert result.pitch_state == PoseState.FACING_SCREEN
        result = classify(HeadPose(-15.0, -5.0), neutral=neutral)
        assert result.yaw_state == PoseState.OFF_AXIS_LEFT
        result = classify(HeadPose(-10.0, -12.0), neutral=neutral)
        assert result.pitch_state == PoseState.HEAD_DOWN


class TestClassifyCustomThresholds:
    """Custom thresholds change the comparison boundaries."""

    def test_strict_yaw_threshold(self) -> None:
        thresholds = Thresholds(yaw_deg=0.5)
        result = classify(HeadPose(1.0, 0.0), thresholds=thresholds)
        assert result.yaw_state == PoseState.OFF_AXIS_RIGHT
        result = classify(HeadPose(0.3, 0.0), thresholds=thresholds)
        assert result.yaw_state == PoseState.FACING_SCREEN

    def test_lenient_yaw_threshold(self) -> None:
        thresholds = Thresholds(yaw_deg=30.0)
        result = classify(HeadPose(25.0, 0.0), thresholds=thresholds)
        assert result.yaw_state == PoseState.FACING_SCREEN

    def test_custom_pitch_threshold(self) -> None:
        thresholds = Thresholds(pitch_deg=3.0)
        result = classify(HeadPose(0.0, 4.0), thresholds=thresholds)
        assert result.pitch_state == PoseState.HEAD_UP
        result = classify(HeadPose(0.0, 2.0), thresholds=thresholds)
        assert result.pitch_state == PoseState.FACING_SCREEN


class TestClassifyYawHysteresis:
    """Hysteresis prevents state flickering near the yaw threshold."""

    def test_off_axis_stays_off_axis_in_hysteresis_zone(self) -> None:
        prev = PoseClassification(
            yaw_state=PoseState.OFF_AXIS_RIGHT, pitch_state=PoseState.FACING_SCREEN
        )
        result = classify(HeadPose(0.7, 0.0), prev_classification=prev)
        assert result.yaw_state == PoseState.OFF_AXIS_RIGHT

    def test_off_axis_returns_to_facing_below_hysteresis(self) -> None:
        prev = PoseClassification(
            yaw_state=PoseState.OFF_AXIS_RIGHT, pitch_state=PoseState.FACING_SCREEN
        )
        result = classify(HeadPose(0.5, 0.0), prev_classification=prev)
        assert result.yaw_state == PoseState.FACING_SCREEN

    def test_facing_stays_facing_in_hysteresis_zone(self) -> None:
        prev = PoseClassification(
            yaw_state=PoseState.FACING_SCREEN, pitch_state=PoseState.FACING_SCREEN
        )
        result = classify(HeadPose(0.7, 0.0), prev_classification=prev)
        assert result.yaw_state == PoseState.FACING_SCREEN

    def test_custom_hysteresis_threshold(self) -> None:
        thresholds = Thresholds(yaw_deg=1.0, yaw_hysteresis_deg=0.3)
        prev = PoseClassification(
            yaw_state=PoseState.OFF_AXIS_RIGHT, pitch_state=PoseState.FACING_SCREEN
        )
        result = classify(HeadPose(0.5, 0.0), thresholds=thresholds, prev_classification=prev)
        assert result.yaw_state == PoseState.OFF_AXIS_RIGHT
        result = classify(HeadPose(0.3, 0.0), thresholds=thresholds, prev_classification=prev)
        assert result.yaw_state == PoseState.FACING_SCREEN

    def test_hysteresis_applies_to_left_direction(self) -> None:
        prev = PoseClassification(
            yaw_state=PoseState.OFF_AXIS_LEFT, pitch_state=PoseState.FACING_SCREEN
        )
        result = classify(HeadPose(-0.7, 0.0), prev_classification=prev)
        assert result.yaw_state == PoseState.OFF_AXIS_LEFT
        result = classify(HeadPose(-0.5, 0.0), prev_classification=prev)
        assert result.yaw_state == PoseState.FACING_SCREEN

    def test_no_face_prev_state_has_no_hysteresis(self) -> None:
        prev = PoseClassification(
            yaw_state=PoseState.NO_FACE, pitch_state=PoseState.NO_FACE
        )
        result = classify(HeadPose(0.7, 0.0), prev_classification=prev)
        assert result.yaw_state == PoseState.FACING_SCREEN


class TestClassifyPitchHysteresis:
    """Hysteresis prevents state flickering near the pitch threshold."""

    def test_head_up_stays_head_up_in_hysteresis_zone(self) -> None:
        prev = PoseClassification(
            yaw_state=PoseState.FACING_SCREEN, pitch_state=PoseState.HEAD_UP
        )
        result = classify(HeadPose(0.0, 3.0), prev_classification=prev)
        assert result.pitch_state == PoseState.HEAD_UP

    def test_head_up_returns_to_facing_below_hysteresis(self) -> None:
        prev = PoseClassification(
            yaw_state=PoseState.FACING_SCREEN, pitch_state=PoseState.HEAD_UP
        )
        result = classify(HeadPose(0.0, 2.5), prev_classification=prev)
        assert result.pitch_state == PoseState.FACING_SCREEN

    def test_facing_stays_facing_in_pitch_hysteresis_zone(self) -> None:
        prev = PoseClassification(
            yaw_state=PoseState.FACING_SCREEN, pitch_state=PoseState.FACING_SCREEN
        )
        result = classify(HeadPose(0.0, 3.0), prev_classification=prev)
        assert result.pitch_state == PoseState.FACING_SCREEN

    def test_head_down_stays_head_down_in_hysteresis_zone(self) -> None:
        prev = PoseClassification(
            yaw_state=PoseState.FACING_SCREEN, pitch_state=PoseState.HEAD_DOWN
        )
        result = classify(HeadPose(0.0, -3.0), prev_classification=prev)
        assert result.pitch_state == PoseState.HEAD_DOWN

    def test_head_down_returns_to_facing_below_hysteresis(self) -> None:
        prev = PoseClassification(
            yaw_state=PoseState.FACING_SCREEN, pitch_state=PoseState.HEAD_DOWN
        )
        result = classify(HeadPose(0.0, -2.5), prev_classification=prev)
        assert result.pitch_state == PoseState.FACING_SCREEN

    def test_custom_pitch_hysteresis(self) -> None:
        thresholds = Thresholds(pitch_deg=5.0, pitch_hysteresis_deg=1.0)
        prev = PoseClassification(
            yaw_state=PoseState.FACING_SCREEN, pitch_state=PoseState.HEAD_UP
        )
        result = classify(HeadPose(0.0, 3.0), thresholds=thresholds, prev_classification=prev)
        assert result.pitch_state == PoseState.HEAD_UP
        result = classify(HeadPose(0.0, 1.0), thresholds=thresholds, prev_classification=prev)
        assert result.pitch_state == PoseState.FACING_SCREEN


class TestClassifyPureFunction:
    """Verify classify is a pure function (no mutation, no side effects)."""

    def test_does_not_mutate_thresholds(self) -> None:
        t = Thresholds(yaw_deg=15.0, pitch_deg=10.0)
        classify(HeadPose(20.0, 0.0), thresholds=t)
        assert t.yaw_deg == 15.0
        assert t.pitch_deg == 10.0

    def test_does_not_mutate_neutral(self) -> None:
        n = NeutralPose(yaw=5.0, pitch=5.0)
        classify(HeadPose(20.0, 0.0), neutral=n)
        assert n.yaw == 5.0
        assert n.pitch == 5.0

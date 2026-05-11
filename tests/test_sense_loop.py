"""Tests for the Qt-free sensing loop."""

from __future__ import annotations

import numpy as np

from eyes.classifier import NeutralPose, PoseState, Thresholds
from eyes.sense_loop import AccumulatorConfig, PromptEvent, SenseLoop


class FixedPoseDetector:
    def __init__(self, pose: tuple[float, float] | None) -> None:
        self.pose = pose

    def detect(self, frame: np.ndarray) -> tuple[float, float] | None:
        return self.pose


def test_tick_emits_correction_event_for_off_axis_streak() -> None:
    loop = SenseLoop(
        FixedPoseDetector((-2.0, 0.0)),
        neutral=NeutralPose(),
        thresholds=Thresholds(yaw_deg=1.0, roll_deg=90.0),
        accumulator_config=AccumulatorConfig(
            off_axis_streak_threshold_seconds=0.1,
            off_axis_repeat_interval_seconds=10.0,
            facing_threshold_seconds=300.0,
            eyest_threshold_seconds=900.0,
        ),
    )

    events = loop.tick(np.zeros((1, 1, 3), dtype=np.uint8), dt=0.1)

    corrections = [e for e in events if e.kind == "correction"]
    assert corrections == [PromptEvent(kind="correction", direction=PoseState.OFF_AXIS_LEFT)]


def test_tick_emits_good_posture_event_for_facing_time() -> None:
    loop = SenseLoop(
        FixedPoseDetector((0.0, 0.0)),
        neutral=NeutralPose(),
        thresholds=Thresholds(yaw_deg=1.0, roll_deg=90.0),
        accumulator_config=AccumulatorConfig(
            off_axis_streak_threshold_seconds=5.0,
            off_axis_repeat_interval_seconds=10.0,
            facing_threshold_seconds=0.1,
            eyest_threshold_seconds=900.0,
        ),
    )

    events = loop.tick(np.zeros((1, 1, 3), dtype=np.uint8), dt=0.1)

    assert events == [PromptEvent(kind="good_posture")]


def test_tick_emits_eye_rest_event_for_face_detected_time() -> None:
    loop = SenseLoop(
        FixedPoseDetector((2.0, 0.0)),
        neutral=NeutralPose(),
        thresholds=Thresholds(yaw_deg=1.0, roll_deg=90.0),
        accumulator_config=AccumulatorConfig(
            off_axis_streak_threshold_seconds=5.0,
            off_axis_repeat_interval_seconds=10.0,
            facing_threshold_seconds=300.0,
            eyest_threshold_seconds=0.1,
        ),
    )

    events = loop.tick(np.zeros((1, 1, 3), dtype=np.uint8), dt=0.1)

    eye_rest_events = [e for e in events if e.kind == "eye_rest"]
    assert eye_rest_events == [PromptEvent(kind="eye_rest")]


def test_tick_tracks_no_face_when_frame_is_missing() -> None:
    loop = SenseLoop(
        FixedPoseDetector((0.0, 0.0)),
        neutral=NeutralPose(),
        thresholds=Thresholds(yaw_deg=1.0, roll_deg=90.0),
        accumulator_config=AccumulatorConfig(),
    )

    events = loop.tick(None, dt=0.1)

    assert events == []
    assert loop.current_yaw is None
    assert loop.current_roll is None
    assert loop.current_state == PoseState.NO_FACE


def test_tick_emits_warning_level_event_on_off_axis() -> None:
    from eyes.types import WarningLevel

    loop = SenseLoop(
        FixedPoseDetector((-2.0, 0.0)),
        neutral=NeutralPose(),
        thresholds=Thresholds(yaw_deg=1.0, roll_deg=90.0),
        accumulator_config=AccumulatorConfig(),
    )

    events = loop.tick(np.zeros((1, 1, 3), dtype=np.uint8), dt=0.1)

    warning_events = [e for e in events if e.kind == "warning_level"]
    assert len(warning_events) == 1
    assert warning_events[0].warning_level_event.level == WarningLevel.WARNING
    assert warning_events[0].warning_level_event.direction == "left"


def test_tick_emits_severe_after_continuous_off_axis() -> None:
    from eyes.types import WarningLevel

    loop = SenseLoop(
        FixedPoseDetector((-2.0, 0.0)),
        neutral=NeutralPose(),
        thresholds=Thresholds(yaw_deg=1.0, roll_deg=90.0),
        accumulator_config=AccumulatorConfig(
            off_axis_repeat_interval_seconds=1.0,
        ),
    )
    dt = 0.5

    # First tick: WARNING, continuous=0.5
    loop.tick(np.zeros((1, 1, 3), dtype=np.uint8), dt=dt)

    # Second tick: continuous=1.0 >= 1.0 threshold → SEVERE
    events = loop.tick(np.zeros((1, 1, 3), dtype=np.uint8), dt=dt)
    warning_events = [e for e in events if e.kind == "warning_level"]
    assert len(warning_events) == 1
    assert warning_events[0].warning_level_event.level == WarningLevel.SEVERE


def test_tick_no_warning_event_when_facing_screen() -> None:
    loop = SenseLoop(
        FixedPoseDetector((0.0, 0.0)),
        neutral=NeutralPose(),
        thresholds=Thresholds(yaw_deg=1.0, roll_deg=90.0),
        accumulator_config=AccumulatorConfig(),
    )

    events = loop.tick(np.zeros((1, 1, 3), dtype=np.uint8), dt=0.1)

    warning_events = [e for e in events if e.kind == "warning_level"]
    assert len(warning_events) == 0


def test_update_classifier_changes_classification() -> None:
    loop = SenseLoop(
        FixedPoseDetector((5.0, 0.0)),
        neutral=NeutralPose(),
        thresholds=Thresholds(yaw_deg=1.0, roll_deg=90.0),
        accumulator_config=AccumulatorConfig(),
    )

    # Initially OFF_AXIS_RIGHT
    loop.tick(np.zeros((1, 1, 3), dtype=np.uint8), dt=0.1)
    assert loop.current_state == PoseState.OFF_AXIS_RIGHT

    # Recalibrate neutral to 5.0 — now facing
    loop.update_classifier(NeutralPose(yaw=5.0), Thresholds(yaw_deg=1.0, roll_deg=90.0))
    loop.tick(np.zeros((1, 1, 3), dtype=np.uint8), dt=0.1)
    assert loop.current_state == PoseState.FACING_SCREEN


def test_tick_handles_detector_returning_none() -> None:
    loop = SenseLoop(
        FixedPoseDetector(None),
        neutral=NeutralPose(),
        thresholds=Thresholds(yaw_deg=1.0, roll_deg=90.0),
        accumulator_config=AccumulatorConfig(),
    )

    events = loop.tick(np.zeros((1, 1, 3), dtype=np.uint8), dt=0.1)

    assert events == []
    assert loop.current_yaw is None
    assert loop.current_roll is None
    assert loop.current_state == PoseState.NO_FACE


def test_tick_classifies_relative_to_neutral_pose() -> None:
    loop = SenseLoop(
        FixedPoseDetector((10.5, -4.0)),
        neutral=NeutralPose(yaw=10.0, roll=-4.0),
        thresholds=Thresholds(yaw_deg=1.0, roll_deg=90.0),
        accumulator_config=AccumulatorConfig(),
    )

    loop.tick(np.zeros((1, 1, 3), dtype=np.uint8), dt=0.1)

    assert loop.current_yaw == 10.5
    assert loop.current_roll == -4.0
    assert loop.current_state == PoseState.FACING_SCREEN

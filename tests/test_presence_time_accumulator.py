from __future__ import annotations

from eyes.classifier import PoseState
from eyes.presence_time_accumulator import PresenceTimeAccumulator


def test_face_detected_states_accumulate_time() -> None:
    accumulator = PresenceTimeAccumulator(threshold_seconds=10.0)

    accumulator.tick(PoseState.FACING_SCREEN, 1.0)
    accumulator.tick(PoseState.OFF_AXIS_LEFT, 1.0)
    accumulator.tick(PoseState.OFF_AXIS_RIGHT, 1.0)
    accumulator.tick(PoseState.OFF_AXIS_OTHER, 1.0)

    assert accumulator.accumulated_seconds == 4.0


def test_no_face_pauses_without_reset() -> None:
    accumulator = PresenceTimeAccumulator(threshold_seconds=10.0)

    for _ in range(5):
        accumulator.tick(PoseState.FACING_SCREEN, 1.0)

    assert accumulator.tick(PoseState.NO_FACE, 1.0) is False

    assert accumulator.accumulated_seconds == 5.0


def test_fires_at_threshold_and_resets() -> None:
    accumulator = PresenceTimeAccumulator(threshold_seconds=2.0)

    assert accumulator.tick(PoseState.FACING_SCREEN, 1.0) is False
    assert accumulator.tick(PoseState.OFF_AXIS_LEFT, 1.0) is True

    assert accumulator.accumulated_seconds == 0.0


def test_snooze_freezes_accumulation_without_reset() -> None:
    accumulator = PresenceTimeAccumulator(threshold_seconds=10.0)

    for _ in range(5):
        accumulator.tick(PoseState.FACING_SCREEN, 1.0)

    accumulator.snooze()
    assert accumulator.is_snoozed is True
    for _ in range(10):
        assert accumulator.tick(PoseState.FACING_SCREEN, 1.0) is False

    assert accumulator.accumulated_seconds == 5.0

    accumulator.resume()
    assert accumulator.is_snoozed is False
    accumulator.tick(PoseState.FACING_SCREEN, 1.0)

    assert accumulator.accumulated_seconds == 6.0


def test_acknowledge_is_supported() -> None:
    accumulator = PresenceTimeAccumulator(threshold_seconds=1.0)

    assert accumulator.tick(PoseState.FACING_SCREEN, 1.0) is True
    accumulator.acknowledge()

    assert accumulator.tick(PoseState.FACING_SCREEN, 1.0) is True

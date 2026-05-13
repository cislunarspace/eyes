from __future__ import annotations

from eyes.classifier import PoseState
from eyes.facing_time_accumulator import FacingTimeAccumulator


def test_facing_screen_accumulates_time() -> None:
    accumulator = FacingTimeAccumulator(threshold_seconds=300.0)

    fired = accumulator.tick(PoseState.FACING_SCREEN, 1.0)

    assert fired is False
    assert accumulator.accumulated_seconds == 1.0


def test_fires_at_threshold_and_resets() -> None:
    accumulator = FacingTimeAccumulator(threshold_seconds=2.0)

    assert accumulator.tick(PoseState.FACING_SCREEN, 1.0) is False
    assert accumulator.tick(PoseState.FACING_SCREEN, 1.0) is True

    assert accumulator.accumulated_seconds == 0.0


def test_non_facing_states_pause_without_reset() -> None:
    accumulator = FacingTimeAccumulator(threshold_seconds=10.0)

    for _ in range(5):
        accumulator.tick(PoseState.FACING_SCREEN, 1.0)

    accumulator.tick(PoseState.OFF_AXIS_LEFT, 1.0)
    accumulator.tick(PoseState.OFF_AXIS_RIGHT, 1.0)
    accumulator.tick(PoseState.OFF_AXIS_OTHER, 1.0)
    accumulator.tick(PoseState.NO_FACE, 1.0)

    assert accumulator.accumulated_seconds == 5.0


def test_snooze_freezes_accumulation_without_reset() -> None:
    accumulator = FacingTimeAccumulator(threshold_seconds=10.0)

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
    accumulator = FacingTimeAccumulator(threshold_seconds=1.0)

    assert accumulator.tick(PoseState.FACING_SCREEN, 1.0) is True
    accumulator.acknowledge()

    assert accumulator.tick(PoseState.FACING_SCREEN, 1.0) is True

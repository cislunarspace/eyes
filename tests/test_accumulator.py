"""Tests for AccumulatorEngine."""

from __future__ import annotations

from eyes.accumulator import AccumulatorEngine
from eyes.classifier import PoseState


class TestAccumulatorFirstPrompt:
    """5s first prompt fires after accumulating 5 seconds of off-axis time."""

    def test_first_prompt_fires_after_5_seconds(self) -> None:
        """Holding off-axis for exactly 5 seconds should trigger correction."""
        engine = AccumulatorEngine()
        dt = 1.0  # 1 second per tick

        # Accumulate 4 seconds - should NOT fire
        for _ in range(4):
            result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert result is None

        # Accumulate 5th second - should fire
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result == PoseState.OFF_AXIS_LEFT

    def test_first_prompt_does_not_fire_at_4_9_seconds(self) -> None:
        """Just under 5 seconds should not trigger correction."""
        engine = AccumulatorEngine()
        dt = 0.98  # 0.98 * 5 = 4.9 seconds

        for _ in range(5):
            result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert result is None


class TestAccumulatorRepeatPrompt:
    """Repeat prompts every 30 seconds after the first."""

    def test_repeat_fires_30_seconds_after_first(self) -> None:
        """After first prompt, repeat fires 30 seconds later (at 35s total)."""
        engine = AccumulatorEngine()
        dt = 1.0

        # Accumulate to 5 seconds (first prompt at 5s)
        for _ in range(4):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        first_result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert first_result == PoseState.OFF_AXIS_LEFT

        # Accumulate 29 more seconds (total 34s) - should NOT fire yet
        for _ in range(29):
            result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert result is None

        # Accumulate 30th second (total 35s) - should fire repeat
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result == PoseState.OFF_AXIS_LEFT


class TestAccumulatorReset:
    """Returning to facing resets the streak."""

    def test_facing_screen_resets_streak(self) -> None:
        """Returning to FACING_SCREEN resets streak, requires fresh 5s for next prompt."""
        engine = AccumulatorEngine()
        dt = 1.0

        # Accumulate 3 seconds off-axis
        for _ in range(3):
            result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert result is None

        # Return to facing - should reset
        engine.tick(PoseState.FACING_SCREEN, dt)

        # Accumulate 4 more seconds - should NOT fire (need fresh 5s)
        for _ in range(4):
            result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert result is None

        # Accumulate 5th second - should fire
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result == PoseState.OFF_AXIS_LEFT

    def test_multiple_cycles(self) -> None:
        """Multiple off-axis → facing → off-axis cycles work correctly."""
        engine = AccumulatorEngine()
        dt = 1.0

        # First cycle: 3 seconds
        for _ in range(3):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        engine.tick(PoseState.FACING_SCREEN, dt)

        # Second cycle: 6 seconds total (need fresh 5s)
        for _ in range(4):
            result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert result is None
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result == PoseState.OFF_AXIS_LEFT

        # Third cycle: reset and do 2 seconds
        engine.tick(PoseState.FACING_SCREEN, dt)
        engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)  # 3s total
        assert result is None


class TestAccumulatorOtherStatesReset:
    """OFF_AXIS_OTHER and NO_FACE reset the streak (no L/R correction for these)."""

    def test_off_axis_other_resets_streak(self) -> None:
        """OFF_AXIS_OTHER does not trigger L/R prompt and resets streak."""
        engine = AccumulatorEngine()
        dt = 1.0

        # Accumulate 3 seconds off-axis LEFT
        for _ in range(3):
            result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert result is None

        # Switch to OFF_AXIS_OTHER - should reset streak
        engine.tick(PoseState.OFF_AXIS_OTHER, dt)

        # Switch back to OFF_AXIS_LEFT - need fresh 5s
        for _ in range(4):
            result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert result is None
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result == PoseState.OFF_AXIS_LEFT

    def test_off_axis_other_never_triggers(self) -> None:
        """OFF_AXIS_OTHER alone never triggers correction."""
        engine = AccumulatorEngine()
        dt = 1.0

        # Accumulate 100 seconds in OFF_AXIS_OTHER - should never fire
        for _ in range(100):
            result = engine.tick(PoseState.OFF_AXIS_OTHER, dt)
            assert result is None

    def test_no_face_resets_streak(self) -> None:
        """NO_FACE resets streak like FACING_SCREEN."""
        engine = AccumulatorEngine()
        dt = 1.0

        # Accumulate 3 seconds off-axis
        for _ in range(3):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)

        # Face disappears
        engine.tick(PoseState.NO_FACE, dt)

        # Face returns - need fresh 5s
        for _ in range(4):
            result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert result is None
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result == PoseState.OFF_AXIS_LEFT


class TestFacingTimeAccumulator:
    """S4: Facing Time Accumulator — cumulative good posture tracking.

    The accumulator advances +1s/s while FACING_SCREEN.
    Brief deviations (OFF_AXIS_*, NO_FACE) pause accumulation but do NOT reset.
    At 300s threshold (configurable), emits GoodPostureDue and resets to 0.
    """

    def test_facing_screen_accumulates_time(self) -> None:
        """FACING_SCREEN advances the facing time counter."""
        from eyes.accumulator import AccumulatorEngine
        engine = AccumulatorEngine()
        dt = 1.0

        # Accumulate 10 seconds of facing - good_posture_due should remain False
        for _ in range(10):
            engine.tick(PoseState.FACING_SCREEN, dt)
            assert engine.good_posture_due is False

        # After 10s, still not at threshold (300s default)
        assert engine.facing_accumulator_seconds < 300

    def test_good_posture_due_fires_at_threshold(self) -> None:
        """At exactly threshold, good_posture_due becomes True."""
        from eyes.accumulator import AccumulatorEngine
        # Use 5s threshold for faster test
        engine = AccumulatorEngine(facing_threshold_seconds=5.0)
        dt = 1.0

        # Accumulate 4 seconds - should NOT fire
        for _ in range(4):
            engine.tick(PoseState.FACING_SCREEN, dt)
            assert engine.good_posture_due is False

        # 5th second - should fire
        engine.tick(PoseState.FACING_SCREEN, dt)
        assert engine.good_posture_due is True

    def test_off_axis_pauses_accumulator_no_reset(self) -> None:
        """OFF_AXIS_* and NO_FACE pause accumulation but do NOT reset."""
        from eyes.accumulator import AccumulatorEngine
        engine = AccumulatorEngine(facing_threshold_seconds=15.0)  # Higher threshold
        dt = 1.0

        # Accumulate 5 seconds facing
        for _ in range(5):
            engine.tick(PoseState.FACING_SCREEN, dt)
        assert engine.facing_accumulator_seconds == 5.0

        # Pause for 3 seconds (off-axis)
        for _ in range(3):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert engine.facing_accumulator_seconds == 5.0  # Paused, not reset

        # Resume facing - continue from where we left off (5 + 4 = 9)
        for _ in range(4):
            engine.tick(PoseState.FACING_SCREEN, dt)
        assert engine.facing_accumulator_seconds == 9.0
        assert engine.good_posture_due is False

    def test_no_face_pauses_accumulator(self) -> None:
        """NO_FACE pauses accumulation without resetting."""
        from eyes.accumulator import AccumulatorEngine
        engine = AccumulatorEngine(facing_threshold_seconds=10.0)
        dt = 1.0

        # Accumulate 5 seconds facing
        for _ in range(5):
            engine.tick(PoseState.FACING_SCREEN, dt)

        # Face disappears
        engine.tick(PoseState.NO_FACE, dt)
        assert engine.facing_accumulator_seconds == 5.0  # Paused

    def test_reset_after_fire_starts_new_cycle(self) -> None:
        """After GoodPostureDue fires, accumulator resets to 0 for new cycle."""
        from eyes.accumulator import AccumulatorEngine
        engine = AccumulatorEngine(facing_threshold_seconds=5.0)
        dt = 1.0

        # First cycle: accumulate to threshold
        for _ in range(5):
            engine.tick(PoseState.FACING_SCREEN, dt)
        assert engine.good_posture_due is True
        assert engine.facing_accumulator_seconds == 0.0  # Auto-reset to 0

        # Continue facing - starts fresh accumulation
        engine.tick(PoseState.FACING_SCREEN, dt)
        assert engine.facing_accumulator_seconds == 1.0

    def test_accumulated_time_across_alternating_cycles(self) -> None:
        """Brief deviations accumulate correctly across facing/off-axis cycles."""
        from eyes.accumulator import AccumulatorEngine
        engine = AccumulatorEngine(facing_threshold_seconds=10.0)
        dt = 1.0

        # Cycle 1: 5s facing
        for _ in range(5):
            engine.tick(PoseState.FACING_SCREEN, dt)

        # Brief deviation: 3s off-axis (paused)
        for _ in range(3):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)

        # Cycle 2: 5s more facing = 10s total = fires
        for _ in range(5):
            engine.tick(PoseState.FACING_SCREEN, dt)
        assert engine.good_posture_due is True

    def test_acknowledge_clears_flag(self) -> None:
        """Calling acknowledge() clears the good_posture_due flag."""
        from eyes.accumulator import AccumulatorEngine
        engine = AccumulatorEngine(facing_threshold_seconds=2.0)
        dt = 1.0

        # Accumulate to threshold
        engine.tick(PoseState.FACING_SCREEN, dt)
        engine.tick(PoseState.FACING_SCREEN, dt)
        assert engine.good_posture_due is True

        # Acknowledge
        engine.acknowledge()
        assert engine.good_posture_due is False

    def test_env_var_invalid_falls_back_to_default(self) -> None:
        """Invalid EYES_FACING_THRESHOLD_SECONDS falls back to 300s default."""
        import os
        from eyes.accumulator import AccumulatorEngine
        old_env = os.environ.get("EYES_FACING_THRESHOLD_SECONDS")

        try:
            os.environ["EYES_FACING_THRESHOLD_SECONDS"] = "not_a_number"
            engine = AccumulatorEngine()  # Should not raise, uses default
            assert engine._facing_threshold == 300.0
        finally:
            if old_env is not None:
                os.environ["EYES_FACING_THRESHOLD_SECONDS"] = old_env
            else:
                del os.environ["EYES_FACING_THRESHOLD_SECONDS"]


class TestOverlayMessages:
    """NotifierOverlay shows correct arrow and text for each direction."""

    def test_off_axis_left_message(self) -> None:
        from eyes.overlay import _MESSAGES
        arrow, text = _MESSAGES[PoseState.OFF_AXIS_LEFT]
        assert arrow == "←"
        assert text == "向左调整"

    def test_off_axis_right_message(self) -> None:
        from eyes.overlay import _MESSAGES
        arrow, text = _MESSAGES[PoseState.OFF_AXIS_RIGHT]
        assert arrow == "→"
        assert text == "向右调整"

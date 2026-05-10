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

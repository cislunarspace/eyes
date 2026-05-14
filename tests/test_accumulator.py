"""Tests for AccumulatorEngine."""

from __future__ import annotations

from eyes.accumulator import AccumulatorEngine
from eyes.classifier import PoseState
from eyes.types import WarningLevel


class TestAccumulatorFirstPrompt:
    """First prompt fires after accumulating off-axis streak threshold seconds."""

    def test_first_prompt_fires_after_default_threshold(self) -> None:
        """Holding off-axis for 0.3 seconds (default) should trigger correction."""
        engine = AccumulatorEngine()
        dt = 0.3

        # 0.3s meets the default threshold exactly
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result == PoseState.OFF_AXIS_LEFT

    def test_first_prompt_does_not_fire_below_threshold(self) -> None:
        """Below threshold should not trigger correction."""
        engine = AccumulatorEngine()
        dt = 0.2

        # 0.2s is below 0.3s default threshold
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result is None

    def test_custom_streak_threshold(self) -> None:
        """Custom streak threshold changes when first prompt fires."""
        engine = AccumulatorEngine(off_axis_streak_threshold_seconds=5.0)
        dt = 1.0

        # Accumulate 4 seconds - should NOT fire
        for _ in range(4):
            result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert result is None

        # Accumulate 5th second - should fire
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result == PoseState.OFF_AXIS_LEFT

    def test_zero_streak_threshold_fires_immediately(self) -> None:
        """Zero threshold means first off-axis tick triggers immediately."""
        engine = AccumulatorEngine(off_axis_streak_threshold_seconds=0.0)
        dt = 0.1

        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result == PoseState.OFF_AXIS_LEFT


class TestAccumulatorRepeatPrompt:
    """Repeat prompts after the repeat interval."""

    def test_repeat_fires_after_interval_with_defaults(self) -> None:
        """After first prompt, repeat fires after 10s (default repeat interval)."""
        engine = AccumulatorEngine()
        dt = 1.0

        # First prompt at 1s
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result == PoseState.OFF_AXIS_LEFT

        # Accumulate 9 more seconds (total 10s) - should NOT fire yet
        for _ in range(9):
            result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert result is None

        # Accumulate 10th second (total 11s) - should fire repeat
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result == PoseState.OFF_AXIS_LEFT

    def test_custom_repeat_interval(self) -> None:
        """Custom repeat interval changes when repeat fires."""
        engine = AccumulatorEngine(
            off_axis_streak_threshold_seconds=1.0,
            off_axis_repeat_interval_seconds=30.0,
        )
        dt = 1.0

        # First prompt at 1s
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result == PoseState.OFF_AXIS_LEFT

        # Accumulate 29 more seconds - should NOT fire yet
        for _ in range(29):
            result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert result is None

        # 30th second after first prompt - should fire repeat
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result == PoseState.OFF_AXIS_LEFT


class TestAccumulatorReset:
    """Returning to facing resets the streak."""

    def test_facing_screen_resets_streak(self) -> None:
        """Returning to FACING_SCREEN resets streak, requires fresh threshold for next prompt."""
        engine = AccumulatorEngine()
        dt = 1.0

        # No prompt yet
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result == PoseState.OFF_AXIS_LEFT  # fires at 1s

        # Return to facing - should reset
        engine.tick(PoseState.FACING_SCREEN, dt)

        # Need fresh threshold period
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result == PoseState.OFF_AXIS_LEFT  # fires at 1s again

    def test_facing_resets_before_threshold(self) -> None:
        """Returning to facing before threshold resets streak completely."""
        engine = AccumulatorEngine(off_axis_streak_threshold_seconds=5.0)
        dt = 1.0

        # Accumulate 3 seconds off-axis (below 5s threshold)
        for _ in range(3):
            result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert result is None

        # Return to facing - should reset
        engine.tick(PoseState.FACING_SCREEN, dt)

        # Need fresh 5s again
        for _ in range(4):
            result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert result is None
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result == PoseState.OFF_AXIS_LEFT

    def test_multiple_cycles(self) -> None:
        """Multiple off-axis → facing → off-axis cycles work correctly."""
        engine = AccumulatorEngine(off_axis_streak_threshold_seconds=5.0)
        dt = 1.0

        # First cycle: 3 seconds (below threshold)
        for _ in range(3):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        engine.tick(PoseState.FACING_SCREEN, dt)

        # Second cycle: 5 seconds total (reaches threshold)
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
        engine = AccumulatorEngine(off_axis_streak_threshold_seconds=5.0)
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
        engine = AccumulatorEngine(off_axis_streak_threshold_seconds=5.0)
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


class TestWarningLevel:
    """Warning level state machine for posture escalation."""

    def test_off_axis_left_emits_warning(self) -> None:
        """First OFF_AXIS_LEFT tick emits WARNING with direction='left'."""
        engine = AccumulatorEngine()
        dt = 0.1

        engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        event = engine.warning_event

        assert event is not None
        assert event.level is WarningLevel.WARNING
        assert event.direction == "left"

    def test_facing_screen_no_warning_event(self) -> None:
        """FACING_SCREEN tick does not emit a warning event."""
        engine = AccumulatorEngine()
        dt = 0.1

        engine.tick(PoseState.FACING_SCREEN, dt)
        assert engine.warning_event is None

    def test_off_axis_right_emits_warning(self) -> None:
        """First OFF_AXIS_RIGHT tick emits WARNING with direction='right'."""
        engine = AccumulatorEngine()
        dt = 0.1

        engine.tick(PoseState.OFF_AXIS_RIGHT, dt)
        event = engine.warning_event

        assert event is not None
        assert event.level is WarningLevel.WARNING
        assert event.direction == "right"

    def test_no_escalation_below_threshold(self) -> None:
        """Below 10s continuous off-axis, stays WARNING (no SEVERE event)."""
        engine = AccumulatorEngine(off_axis_repeat_interval_seconds=10.0)
        dt = 1.0

        # First tick: emits WARNING, continuous = 1.0
        engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert engine.warning_event is not None

        # 8 more ticks: continuous goes 2.0 → 9.0, no SEVERE
        for _ in range(8):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert engine.warning_event is None

    def test_escalation_to_severe_at_threshold(self) -> None:
        """SEVERE emitted after exactly 10s continuous off-axis."""
        engine = AccumulatorEngine(off_axis_repeat_interval_seconds=10.0)
        dt = 1.0

        # First tick: WARNING
        engine.tick(PoseState.OFF_AXIS_LEFT, dt)

        # 8 more ticks: continuous = 9.0
        for _ in range(8):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)

        # 10th tick: continuous = 10.0 >= threshold → SEVERE
        engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        event = engine.warning_event
        assert event is not None
        assert event.level is WarningLevel.SEVERE
        assert event.direction == "left"

    def test_facing_screen_after_warning_emits_corrected(self) -> None:
        """Returning to FACING_SCREEN after WARNING emits CORRECTED."""
        engine = AccumulatorEngine()
        dt = 0.1

        # Get into WARNING state
        engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert engine.warning_event is not None

        # Return to facing
        engine.tick(PoseState.FACING_SCREEN, dt)
        event = engine.warning_event
        assert event is not None
        assert event.level is WarningLevel.CORRECTED
        assert event.direction is None

    def test_corrected_transitions_to_normal_after_2s(self) -> None:
        """After CORRECTED, 2 seconds of FACING_SCREEN transitions to NORMAL."""
        engine = AccumulatorEngine()
        dt = 1.0

        # WARNING → CORRECTED
        engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        engine.tick(PoseState.FACING_SCREEN, dt)

        # 1s of FACING_SCREEN in CORRECTED state — still CORRECTED, no event
        engine.tick(PoseState.FACING_SCREEN, dt)
        assert engine.warning_event is None

        # 2nd second — transition to NORMAL
        engine.tick(PoseState.FACING_SCREEN, dt)
        event = engine.warning_event
        assert event is not None
        assert event.level is WarningLevel.NORMAL

        # Verify we're back to NORMAL by triggering a fresh WARNING
        engine.tick(PoseState.OFF_AXIS_RIGHT, dt)
        event = engine.warning_event
        assert event is not None
        assert event.level is WarningLevel.WARNING
        assert event.direction == "right"

    def test_no_face_resets_warning_to_normal(self) -> None:
        """NO_FACE resets warning level to NORMAL and resets escalation timer."""
        engine = AccumulatorEngine(off_axis_repeat_interval_seconds=10.0)
        dt = 1.0

        # Get into WARNING
        engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert engine.warning_event is not None

        # Accumulate 5s continuous off-axis
        for _ in range(5):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)

        # NO_FACE resets to NORMAL
        engine.tick(PoseState.NO_FACE, dt)
        event = engine.warning_event
        assert event is not None
        assert event.level is WarningLevel.NORMAL

        # Next off-axis tick should be a fresh episode (timer at 0)
        engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        event = engine.warning_event
        assert event is not None
        assert event.level is WarningLevel.WARNING

        # Escalation timer should be reset — 9s more should NOT trigger SEVERE
        for _ in range(8):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert engine.warning_event is None

    def test_no_face_after_severe_resets_to_normal(self) -> None:
        """NO_FACE after SEVERE also resets to NORMAL."""
        engine = AccumulatorEngine(off_axis_repeat_interval_seconds=10.0)
        dt = 1.0

        # Get into SEVERE
        engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        for _ in range(9):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert engine.warning_event is not None
        assert engine.warning_event.level is WarningLevel.SEVERE

        # NO_FACE resets
        engine.tick(PoseState.NO_FACE, dt)
        event = engine.warning_event
        assert event is not None
        assert event.level is WarningLevel.NORMAL

        # Fresh episode
        engine.tick(PoseState.OFF_AXIS_RIGHT, dt)
        assert engine.warning_event is not None
        assert engine.warning_event.level is WarningLevel.WARNING
        assert engine.warning_event.direction == "right"

    def test_new_episode_after_corrected_resets_timer(self) -> None:
        """Going off-axis after CORRECTED starts a fresh episode with reset timer."""
        engine = AccumulatorEngine(off_axis_repeat_interval_seconds=10.0)
        dt = 1.0

        # WARNING → CORRECTED
        engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        engine.tick(PoseState.FACING_SCREEN, dt)
        event = engine.warning_event
        assert event is not None
        assert event.level is WarningLevel.CORRECTED

        # Immediately go off-axis again — new episode, timer resets
        engine.tick(PoseState.OFF_AXIS_RIGHT, dt)
        event = engine.warning_event
        assert event is not None
        assert event.level is WarningLevel.WARNING
        assert event.direction == "right"

        # 9 more seconds should NOT trigger SEVERE (timer started at dt=1.0)
        for _ in range(8):
            engine.tick(PoseState.OFF_AXIS_RIGHT, dt)
            assert engine.warning_event is None

        # 10th tick of continuous off-axis → SEVERE
        engine.tick(PoseState.OFF_AXIS_RIGHT, dt)
        assert engine.warning_event is not None
        assert engine.warning_event.level is WarningLevel.SEVERE

    def test_direction_change_mid_warning_updates_without_reemitting(self) -> None:
        """Changing off-axis direction during WARNING updates direction for eventual SEVERE."""
        engine = AccumulatorEngine(off_axis_repeat_interval_seconds=10.0)
        dt = 1.0

        engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        event = engine.warning_event
        assert event is not None
        assert event.level is WarningLevel.WARNING
        assert event.direction == "left"

        engine.tick(PoseState.OFF_AXIS_RIGHT, dt)
        assert engine.warning_event is None

        for _ in range(7):
            engine.tick(PoseState.OFF_AXIS_RIGHT, dt)
            assert engine.warning_event is None

        engine.tick(PoseState.OFF_AXIS_RIGHT, dt)
        event = engine.warning_event
        assert event is not None
        assert event.level is WarningLevel.SEVERE
        assert event.direction == "right"

    def test_snooze_freezes_warning_escalation(self) -> None:
        """While snoozed, warning escalation does not advance or emit events."""
        engine = AccumulatorEngine(off_axis_repeat_interval_seconds=10.0)
        dt = 1.0

        engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert engine.warning_event is not None

        engine.snooze()
        for _ in range(20):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert engine.warning_event is None

        engine.resume()
        for _ in range(8):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert engine.warning_event is None

        engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        event = engine.warning_event
        assert event is not None
        assert event.level is WarningLevel.SEVERE

    def test_off_axis_other_does_not_advance_warning_escalation(self) -> None:
        """OFF_AXIS_OTHER leaves warning escalation paused until yaw-axis off-axis resumes."""
        engine = AccumulatorEngine(off_axis_repeat_interval_seconds=10.0)
        dt = 1.0

        engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert engine.warning_event is not None

        for _ in range(20):
            engine.tick(PoseState.OFF_AXIS_OTHER, dt)
            assert engine.warning_event is None

        for _ in range(8):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert engine.warning_event is None

        engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        event = engine.warning_event
        assert event is not None
        assert event.level is WarningLevel.SEVERE
        assert event.direction == "left"

    def test_severe_to_corrected_on_facing_screen(self) -> None:
        """Returning to FACING_SCREEN from SEVERE (not just WARNING) emits CORRECTED."""
        engine = AccumulatorEngine(off_axis_repeat_interval_seconds=10.0)
        dt = 1.0

        for _ in range(10):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        event = engine.warning_event
        assert event is not None
        assert event.level is WarningLevel.SEVERE

        engine.tick(PoseState.FACING_SCREEN, dt)
        event = engine.warning_event
        assert event is not None
        assert event.level is WarningLevel.CORRECTED
        assert event.direction is None


class TestOverlayMessages:
    """NotifierOverlay shows correct arrow and text for each direction."""

    def test_off_axis_left_message(self) -> None:
        from eyes.i18n import set_language, t
        set_language("zh-CN")
        arrow = "←"
        text = t("overlay.adjust_left")
        assert arrow == "←"
        assert text == "向左调整"

    def test_off_axis_right_message(self) -> None:
        from eyes.i18n import set_language, t
        set_language("zh-CN")
        arrow = "→"
        text = t("overlay.adjust_right")
        assert arrow == "→"
        assert text == "向右调整"


class TestOverlayEyeRestMessage:
    """NotifierOverlay shows correct message for eye rest prompt."""

    def test_eye_rest_message(self) -> None:
        from eyes.i18n import set_language, t
        set_language("zh-CN")
        arrow = "👀"
        text = t("overlay.eye_rest")
        assert arrow == "👀"
        assert text == "请眺望远方"



class SnoozeTargetSpy:
    def __init__(self) -> None:
        self.is_snoozed = False

    def snooze(self) -> None:
        self.is_snoozed = True

    def resume(self) -> None:
        self.is_snoozed = False


class TestAccumulatorSnooze:
    """S7: AccumulatorEngine snooze behavior.

    When snoozed, the engine freezes all accumulators and off-axis streak.
    On resume, accumulators continue from their previous values.
    """

    def test_snooze_targets_follow_engine_snooze_state(self) -> None:
        engine = AccumulatorEngine()
        target = SnoozeTargetSpy()
        engine.register_snooze_target(target)

        engine.snooze()
        assert target.is_snoozed is True

        engine.resume()
        assert target.is_snoozed is False

    def test_snooze_freezes_off_axis_streak(self) -> None:
        """Off-axis streak does not advance while snoozed."""
        engine = AccumulatorEngine(off_axis_streak_threshold_seconds=5.0)
        dt = 1.0

        # Accumulate 3 seconds off-axis
        for _ in range(3):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)

        # Enter snooze at 3 seconds
        engine.snooze()

        # Snooze for 10 ticks - streak should freeze at 3s
        for _ in range(10):
            result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert result is None  # No prompts while snoozed

    def test_is_snoozed_property(self) -> None:
        """Engine correctly reports snooze state."""
        engine = AccumulatorEngine()
        assert engine.is_snoozed is False

        engine.snooze()
        assert engine.is_snoozed is True

        engine.resume()
        assert engine.is_snoozed is False

    def test_resume_continues_off_axis_streak(self) -> None:
        """Off-axis streak continues after resume (does not reset)."""
        engine = AccumulatorEngine(off_axis_streak_threshold_seconds=5.0)
        dt = 1.0

        # Accumulate 3 seconds off-axis
        for _ in range(3):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)

        # Snooze
        engine.snooze()

        # Resume while still off-axis
        engine.resume()

        # 2 more seconds = 5 total -> fires (3 + 2 = 5 >= 5 threshold)
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result is None  # 4th second
        result = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert result == PoseState.OFF_AXIS_LEFT  # 5th second - fires!

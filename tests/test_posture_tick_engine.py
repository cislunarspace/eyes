"""Tests for PostureTickEngine — unified posture timing engine."""

from __future__ import annotations

from eyes.classifier import PoseState
from eyes.posture_tick_engine import PostureTickEngine
from eyes.sense_loop import CorrectionEvent, EyeRestEvent, GoodPostureEvent, WarningLevelEvent
from eyes.types import WarningLevel


class TestReconfigure:
    """reconfigure() updates thresholds and affects tick() behavior."""

    def test_reconfigure_streak_threshold_affects_tick(self) -> None:
        engine = PostureTickEngine()
        # Default threshold is 0.3, so 0.2 dt does NOT fire.
        events = engine.tick(PoseState.OFF_AXIS_LEFT, 0.2)
        assert all(not isinstance(e, CorrectionEvent) for e in events)

        engine.reconfigure(off_axis_streak_threshold_seconds=0.1)
        events = engine.tick(PoseState.OFF_AXIS_LEFT, 0.2)
        assert any(isinstance(e, CorrectionEvent) for e in events)

    def test_reconfigure_facing_threshold_affects_tick(self) -> None:
        engine = PostureTickEngine(
            off_axis_streak_threshold_seconds=5.0,
        )
        # Default facing threshold is 300s, override to 2s.
        engine.reconfigure(facing_threshold_seconds=2.0)

        events = engine.tick(PoseState.FACING_SCREEN, 1.0)
        assert all(not isinstance(e, GoodPostureEvent) for e in events)
        events = engine.tick(PoseState.FACING_SCREEN, 1.0)
        assert any(isinstance(e, GoodPostureEvent) for e in events)

    def test_reconfigure_eyest_threshold_affects_tick(self) -> None:
        engine = PostureTickEngine(
            off_axis_streak_threshold_seconds=5.0,
        )
        engine.reconfigure(eyest_threshold_seconds=2.0)

        events = engine.tick(PoseState.FACING_SCREEN, 1.0)
        assert all(not isinstance(e, EyeRestEvent) for e in events)
        events = engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        assert any(isinstance(e, EyeRestEvent) for e in events)


class TestOffAxisStreak:
    """Off-axis streak triggers CorrectionEvent at threshold."""

    def test_first_correction_fires_at_default_threshold(self) -> None:
        engine = PostureTickEngine()

        events = engine.tick(PoseState.OFF_AXIS_LEFT, 0.3)

        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert corrections == [CorrectionEvent(direction=PoseState.OFF_AXIS_LEFT)]

    def test_below_threshold_no_correction(self) -> None:
        engine = PostureTickEngine()

        events = engine.tick(PoseState.OFF_AXIS_LEFT, 0.2)

        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert corrections == []

    def test_custom_streak_threshold(self) -> None:
        engine = PostureTickEngine(off_axis_streak_threshold_seconds=5.0)

        for _ in range(4):
            events = engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
            assert all(not isinstance(e, CorrectionEvent) for e in events)

        events = engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert len(corrections) == 1
        assert corrections[0].direction == PoseState.OFF_AXIS_LEFT

    def test_zero_streak_threshold_fires_immediately(self) -> None:
        engine = PostureTickEngine(off_axis_streak_threshold_seconds=0.0)

        events = engine.tick(PoseState.OFF_AXIS_LEFT, 0.1)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert len(corrections) == 1

    def test_repeat_correction_after_interval(self) -> None:
        engine = PostureTickEngine()
        dt = 1.0

        # First prompt at 1s
        events = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        assert any(isinstance(e, CorrectionEvent) for e in events)

        # 9 more seconds — no repeat yet
        for _ in range(9):
            events = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert all(not isinstance(e, CorrectionEvent) for e in events)

        # 10th second — repeat fires
        events = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert len(corrections) == 1

    def test_facing_screen_resets_streak(self) -> None:
        engine = PostureTickEngine()
        dt = 1.0

        engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        engine.tick(PoseState.FACING_SCREEN, dt)
        events = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert len(corrections) == 1

    def test_no_face_resets_streak(self) -> None:
        engine = PostureTickEngine(off_axis_streak_threshold_seconds=5.0)
        dt = 1.0

        for _ in range(3):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)

        engine.tick(PoseState.NO_FACE, dt)

        for _ in range(4):
            events = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert all(not isinstance(e, CorrectionEvent) for e in events)
        events = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert len(corrections) == 1

    def test_head_up_resets_streak(self) -> None:
        engine = PostureTickEngine(off_axis_streak_threshold_seconds=5.0)
        dt = 1.0

        for _ in range(3):
            engine.tick(PoseState.OFF_AXIS_LEFT, dt)

        engine.tick(PoseState.HEAD_UP, dt)

        for _ in range(4):
            events = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
            assert all(not isinstance(e, CorrectionEvent) for e in events)
        events = engine.tick(PoseState.OFF_AXIS_LEFT, dt)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert len(corrections) == 1

    def test_head_up_never_triggers_correction(self) -> None:
        engine = PostureTickEngine()
        dt = 1.0

        for _ in range(100):
            events = engine.tick(PoseState.HEAD_UP, dt)
            assert all(not isinstance(e, CorrectionEvent) for e in events)


class TestFacingTime:
    """Facing time accumulation triggers GoodPostureEvent at threshold."""

    def test_facing_screen_accumulates_and_fires(self) -> None:
        engine = PostureTickEngine(
            facing_threshold_seconds=2.0,
            off_axis_streak_threshold_seconds=5.0,
        )

        events = engine.tick(PoseState.FACING_SCREEN, 1.0)
        assert all(not isinstance(e, GoodPostureEvent) for e in events)

        events = engine.tick(PoseState.FACING_SCREEN, 1.0)
        assert any(isinstance(e, GoodPostureEvent) for e in events)

    def test_non_facing_states_pause_without_reset(self) -> None:
        engine = PostureTickEngine(
            facing_threshold_seconds=10.0,
            off_axis_streak_threshold_seconds=5.0,
        )

        for _ in range(5):
            engine.tick(PoseState.FACING_SCREEN, 1.0)

        engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        engine.tick(PoseState.NO_FACE, 1.0)
        events = engine.tick(PoseState.FACING_SCREEN, 1.0)
        assert all(not isinstance(e, GoodPostureEvent) for e in events)

    def test_facing_resets_after_fire(self) -> None:
        engine = PostureTickEngine(
            facing_threshold_seconds=1.0,
            off_axis_streak_threshold_seconds=5.0,
        )

        events = engine.tick(PoseState.FACING_SCREEN, 1.0)
        assert any(isinstance(e, GoodPostureEvent) for e in events)

        events = engine.tick(PoseState.FACING_SCREEN, 1.0)
        assert any(isinstance(e, GoodPostureEvent) for e in events)


class TestPresenceTime:
    """Presence time accumulation triggers EyeRestEvent at threshold."""

    def test_face_detected_states_accumulate(self) -> None:
        engine = PostureTickEngine(
            eyest_threshold_seconds=10.0,
            off_axis_streak_threshold_seconds=5.0,
        )

        engine.tick(PoseState.FACING_SCREEN, 1.0)
        engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        engine.tick(PoseState.OFF_AXIS_RIGHT, 1.0)
        events = engine.tick(PoseState.HEAD_UP, 1.0)
        assert all(not isinstance(e, EyeRestEvent) for e in events)

        # After 5 more seconds of presence (total 9s), still no fire
        for _ in range(5):
            events = engine.tick(PoseState.FACING_SCREEN, 1.0)
        assert all(not isinstance(e, EyeRestEvent) for e in events)

        # 10th second fires
        events = engine.tick(PoseState.FACING_SCREEN, 1.0)
        assert any(isinstance(e, EyeRestEvent) for e in events)

    def test_no_face_pauses_without_reset(self) -> None:
        engine = PostureTickEngine(
            eyest_threshold_seconds=10.0,
            off_axis_streak_threshold_seconds=5.0,
        )

        for _ in range(5):
            engine.tick(PoseState.FACING_SCREEN, 1.0)

        events = engine.tick(PoseState.NO_FACE, 1.0)
        assert all(not isinstance(e, EyeRestEvent) for e in events)

    def test_fires_at_threshold_and_resets(self) -> None:
        engine = PostureTickEngine(
            eyest_threshold_seconds=2.0,
            off_axis_streak_threshold_seconds=5.0,
        )

        events = engine.tick(PoseState.FACING_SCREEN, 1.0)
        assert all(not isinstance(e, EyeRestEvent) for e in events)
        events = engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        assert any(isinstance(e, EyeRestEvent) for e in events)


class TestWarningLevel:
    """Warning level state machine: NORMAL → WARNING → SEVERE → CORRECTED → NORMAL."""

    def test_off_axis_left_emits_warning(self) -> None:
        engine = PostureTickEngine()

        events = engine.tick(PoseState.OFF_AXIS_LEFT, 0.1)
        warnings = [e for e in events if isinstance(e, WarningLevelEvent)]
        assert len(warnings) == 1
        assert warnings[0].level == WarningLevel.WARNING
        assert warnings[0].direction == "left"

    def test_off_axis_right_emits_warning(self) -> None:
        engine = PostureTickEngine()

        events = engine.tick(PoseState.OFF_AXIS_RIGHT, 0.1)
        warnings = [e for e in events if isinstance(e, WarningLevelEvent)]
        assert len(warnings) == 1
        assert warnings[0].level == WarningLevel.WARNING
        assert warnings[0].direction == "right"

    def test_facing_screen_no_warning_event(self) -> None:
        engine = PostureTickEngine()

        events = engine.tick(PoseState.FACING_SCREEN, 0.1)
        assert all(not isinstance(e, WarningLevelEvent) for e in events)

    def test_escalation_to_severe_at_threshold(self) -> None:
        engine = PostureTickEngine(off_axis_repeat_interval_seconds=10.0)

        events = engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.WARNING for e in events)

        for _ in range(8):
            events = engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
            assert all(not isinstance(e, WarningLevelEvent) for e in events)

        events = engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.SEVERE for e in events)

    def test_no_escalation_below_threshold(self) -> None:
        engine = PostureTickEngine(off_axis_repeat_interval_seconds=10.0)

        engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        for _ in range(8):
            events = engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
            assert all(not isinstance(e, WarningLevelEvent) for e in events)

    def test_facing_screen_after_warning_emits_corrected(self) -> None:
        engine = PostureTickEngine()

        engine.tick(PoseState.OFF_AXIS_LEFT, 0.1)
        events = engine.tick(PoseState.FACING_SCREEN, 0.1)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.CORRECTED for e in events)

    def test_corrected_transitions_to_normal_after_2s(self) -> None:
        engine = PostureTickEngine()

        engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        engine.tick(PoseState.FACING_SCREEN, 1.0)
        events = engine.tick(PoseState.FACING_SCREEN, 1.0)
        assert all(not isinstance(e, WarningLevelEvent) for e in events)
        events = engine.tick(PoseState.FACING_SCREEN, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.NORMAL for e in events)

    def test_no_face_resets_warning_to_normal(self) -> None:
        engine = PostureTickEngine(off_axis_repeat_interval_seconds=10.0)

        engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        for _ in range(5):
            engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)

        events = engine.tick(PoseState.NO_FACE, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.NORMAL for e in events)

        # Fresh episode
        events = engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.WARNING for e in events)

    def test_new_episode_after_corrected_resets_timer(self) -> None:
        engine = PostureTickEngine(off_axis_repeat_interval_seconds=10.0)

        engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        engine.tick(PoseState.FACING_SCREEN, 1.0)
        engine.tick(PoseState.OFF_AXIS_RIGHT, 1.0)

        for _ in range(8):
            events = engine.tick(PoseState.OFF_AXIS_RIGHT, 1.0)
            assert all(not isinstance(e, WarningLevelEvent) for e in events)

        events = engine.tick(PoseState.OFF_AXIS_RIGHT, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.SEVERE for e in events)

    def test_direction_change_mid_warning_updates_for_severe(self) -> None:
        engine = PostureTickEngine(off_axis_repeat_interval_seconds=10.0)

        engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        engine.tick(PoseState.OFF_AXIS_RIGHT, 1.0)

        for _ in range(7):
            engine.tick(PoseState.OFF_AXIS_RIGHT, 1.0)

        events = engine.tick(PoseState.OFF_AXIS_RIGHT, 1.0)
        warnings = [e for e in events if isinstance(e, WarningLevelEvent)]
        assert len(warnings) == 1
        assert warnings[0].level == WarningLevel.SEVERE
        assert warnings[0].direction == "right"

    def test_severe_to_corrected_on_facing_screen(self) -> None:
        engine = PostureTickEngine(off_axis_repeat_interval_seconds=10.0)

        for _ in range(10):
            engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        events = engine.tick(PoseState.FACING_SCREEN, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.CORRECTED for e in events)

    def test_head_up_does_not_advance_warning_escalation(self) -> None:
        engine = PostureTickEngine(off_axis_repeat_interval_seconds=10.0)

        engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        for _ in range(20):
            events = engine.tick(PoseState.HEAD_UP, 1.0)
            assert all(not isinstance(e, WarningLevelEvent) for e in events)

        for _ in range(8):
            events = engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
            assert all(not isinstance(e, WarningLevelEvent) for e in events)

        events = engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.SEVERE for e in events)


class TestUnifiedSnooze:
    """Unified snooze freezes all accumulations; resume continues from where left off."""

    def test_snooze_freezes_off_axis_streak(self) -> None:
        engine = PostureTickEngine(off_axis_streak_threshold_seconds=5.0)

        for _ in range(3):
            engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)

        engine.snooze()
        assert engine.is_snoozed is True
        for _ in range(10):
            events = engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
            assert events == []

        engine.resume()
        assert engine.is_snoozed is False
        result = engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        assert all(not isinstance(e, CorrectionEvent) for e in result)
        result = engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        assert any(isinstance(e, CorrectionEvent) for e in result)

    def test_snooze_freezes_facing_time(self) -> None:
        engine = PostureTickEngine(
            facing_threshold_seconds=10.0,
            off_axis_streak_threshold_seconds=5.0,
        )

        for _ in range(5):
            engine.tick(PoseState.FACING_SCREEN, 1.0)

        engine.snooze()
        for _ in range(10):
            events = engine.tick(PoseState.FACING_SCREEN, 1.0)
            assert events == []

        engine.resume()
        for _ in range(4):
            events = engine.tick(PoseState.FACING_SCREEN, 1.0)
            assert all(not isinstance(e, GoodPostureEvent) for e in events)

        events = engine.tick(PoseState.FACING_SCREEN, 1.0)
        assert any(isinstance(e, GoodPostureEvent) for e in events)

    def test_snooze_freezes_presence_time(self) -> None:
        engine = PostureTickEngine(
            eyest_threshold_seconds=10.0,
            off_axis_streak_threshold_seconds=5.0,
        )

        for _ in range(5):
            engine.tick(PoseState.FACING_SCREEN, 1.0)

        engine.snooze()
        for _ in range(10):
            events = engine.tick(PoseState.FACING_SCREEN, 1.0)
            assert events == []

        engine.resume()
        for _ in range(4):
            events = engine.tick(PoseState.FACING_SCREEN, 1.0)
            assert all(not isinstance(e, EyeRestEvent) for e in events)

        events = engine.tick(PoseState.FACING_SCREEN, 1.0)
        assert any(isinstance(e, EyeRestEvent) for e in events)

    def test_snooze_freezes_warning_escalation(self) -> None:
        engine = PostureTickEngine(off_axis_repeat_interval_seconds=10.0)

        engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        engine.snooze()
        for _ in range(20):
            events = engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
            assert events == []

        engine.resume()
        for _ in range(8):
            events = engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
            assert all(not isinstance(e, WarningLevelEvent) for e in events)

        events = engine.tick(PoseState.OFF_AXIS_LEFT, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.SEVERE for e in events)

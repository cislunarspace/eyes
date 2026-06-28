"""Tests for PostureTickEngine — unified posture timing engine."""

from __future__ import annotations

from eyes.classifier import PoseState
from eyes.posture_tick_engine import PostureTickEngine
from eyes.sense_loop import CorrectionEvent, EyeRestEvent, GoodPostureEvent, WarningLevelEvent
from eyes.types import WarningLevel

# 便捷别名：两个轴都正对
_FACING = PoseState.FACING_SCREEN
_NO_FACE = PoseState.NO_FACE
_LEFT = PoseState.OFF_AXIS_LEFT
_RIGHT = PoseState.OFF_AXIS_RIGHT
_UP = PoseState.HEAD_UP
_DOWN = PoseState.HEAD_DOWN


class TestReconfigure:
    def test_reconfigure_streak_threshold_affects_tick(self) -> None:
        engine = PostureTickEngine()
        events = engine.tick(_LEFT, _FACING, 0.2)
        assert all(not isinstance(e, CorrectionEvent) for e in events)

        engine.reconfigure(off_axis_streak_threshold_seconds=0.1)
        events = engine.tick(_LEFT, _FACING, 0.2)
        assert any(isinstance(e, CorrectionEvent) for e in events)

    def test_reconfigure_facing_threshold_affects_tick(self) -> None:
        engine = PostureTickEngine(off_axis_streak_threshold_seconds=5.0)
        engine.reconfigure(facing_threshold_seconds=2.0)

        events = engine.tick(_FACING, _FACING, 1.0)
        assert all(not isinstance(e, GoodPostureEvent) for e in events)
        events = engine.tick(_FACING, _FACING, 1.0)
        assert any(isinstance(e, GoodPostureEvent) for e in events)

    def test_reconfigure_eyest_threshold_affects_tick(self) -> None:
        engine = PostureTickEngine(off_axis_streak_threshold_seconds=5.0)
        engine.reconfigure(eyest_threshold_seconds=2.0)

        events = engine.tick(_FACING, _FACING, 1.0)
        assert all(not isinstance(e, EyeRestEvent) for e in events)
        events = engine.tick(_LEFT, _FACING, 1.0)
        assert any(isinstance(e, EyeRestEvent) for e in events)


class TestOffAxisStreak:
    def test_first_correction_fires_at_default_threshold(self) -> None:
        engine = PostureTickEngine()
        events = engine.tick(_LEFT, _FACING, 0.3)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert corrections == [CorrectionEvent(direction=_LEFT, dimension="yaw")]

    def test_below_threshold_no_correction(self) -> None:
        engine = PostureTickEngine()
        events = engine.tick(_LEFT, _FACING, 0.2)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert corrections == []

    def test_custom_streak_threshold(self) -> None:
        engine = PostureTickEngine(off_axis_streak_threshold_seconds=5.0)

        for _ in range(4):
            events = engine.tick(_LEFT, _FACING, 1.0)
            assert all(not isinstance(e, CorrectionEvent) for e in events)

        events = engine.tick(_LEFT, _FACING, 1.0)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert len(corrections) == 1
        assert corrections[0].direction == _LEFT

    def test_zero_streak_threshold_fires_immediately(self) -> None:
        engine = PostureTickEngine(off_axis_streak_threshold_seconds=0.0)
        events = engine.tick(_LEFT, _FACING, 0.1)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert len(corrections) == 1

    def test_repeat_correction_after_interval(self) -> None:
        engine = PostureTickEngine()
        dt = 1.0

        events = engine.tick(_LEFT, _FACING, dt)
        assert any(isinstance(e, CorrectionEvent) for e in events)

        for _ in range(9):
            events = engine.tick(_LEFT, _FACING, dt)
            assert all(not isinstance(e, CorrectionEvent) for e in events)

        events = engine.tick(_LEFT, _FACING, dt)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert len(corrections) == 1

    def test_facing_screen_resets_streak(self) -> None:
        engine = PostureTickEngine()
        dt = 1.0

        engine.tick(_LEFT, _FACING, dt)
        engine.tick(_FACING, _FACING, dt)
        events = engine.tick(_LEFT, _FACING, dt)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert len(corrections) == 1

    def test_no_face_resets_streak(self) -> None:
        engine = PostureTickEngine(off_axis_streak_threshold_seconds=5.0)
        dt = 1.0

        for _ in range(3):
            engine.tick(_LEFT, _FACING, dt)

        engine.tick(_NO_FACE, _NO_FACE, dt)

        for _ in range(4):
            events = engine.tick(_LEFT, _FACING, dt)
            assert all(not isinstance(e, CorrectionEvent) for e in events)
        events = engine.tick(_LEFT, _FACING, dt)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert len(corrections) == 1

    def test_facing_yaw_resets_streak_when_pitch_off(self) -> None:
        """yaw 正对 + pitch 偏离时，yaw streak 重置。"""
        engine = PostureTickEngine(off_axis_streak_threshold_seconds=5.0)
        dt = 1.0

        for _ in range(3):
            engine.tick(_LEFT, _FACING, dt)

        # yaw 回到正对，pitch 偏离
        engine.tick(_FACING, _UP, dt)

        # yaw streak 重置，需要重新积累
        for _ in range(4):
            events = engine.tick(_LEFT, _FACING, dt)
            assert all(not isinstance(e, CorrectionEvent) for e in events)
        events = engine.tick(_LEFT, _FACING, dt)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert len(corrections) == 1


class TestPitchStreak:
    def test_pitch_correction_fires_at_threshold(self) -> None:
        engine = PostureTickEngine()
        events = engine.tick(_FACING, _UP, 0.3)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert corrections == [CorrectionEvent(direction=_UP, dimension="pitch")]

    def test_pitch_down_correction(self) -> None:
        engine = PostureTickEngine()
        events = engine.tick(_FACING, _DOWN, 0.3)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert corrections == [CorrectionEvent(direction=_DOWN, dimension="pitch")]

    def test_pitch_repeat_correction_after_interval(self) -> None:
        engine = PostureTickEngine()
        dt = 1.0

        events = engine.tick(_FACING, _UP, dt)
        assert any(isinstance(e, CorrectionEvent) for e in events)

        for _ in range(9):
            events = engine.tick(_FACING, _UP, dt)
            assert all(not isinstance(e, CorrectionEvent) for e in events)

        events = engine.tick(_FACING, _UP, dt)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert len(corrections) == 1
        assert corrections[0].dimension == "pitch"

    def test_yaw_and_pitch_independent_streaks(self) -> None:
        """yaw 和 pitch 各自独立追踪 streak，互不干扰。"""
        engine = PostureTickEngine(off_axis_streak_threshold_seconds=5.0)
        dt = 1.0

        # yaw 积累 3 秒
        for _ in range(3):
            engine.tick(_LEFT, _FACING, dt)

        # pitch 也开始偏离，yaw 继续
        engine.tick(_LEFT, _UP, dt)
        events = engine.tick(_LEFT, _UP, dt)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        # yaw 达到 5s 触发，pitch 只有 2s 不触发
        assert len(corrections) == 1
        assert corrections[0].dimension == "yaw"

    def test_pitch_resets_when_pitch_returns_to_facing(self) -> None:
        engine = PostureTickEngine(off_axis_streak_threshold_seconds=5.0)
        dt = 1.0

        for _ in range(3):
            engine.tick(_FACING, _UP, dt)

        # pitch 回到正对
        engine.tick(_FACING, _FACING, dt)

        # pitch streak 重置
        for _ in range(4):
            events = engine.tick(_FACING, _UP, dt)
            assert all(not isinstance(e, CorrectionEvent) for e in events)
        events = engine.tick(_FACING, _UP, dt)
        corrections = [e for e in events if isinstance(e, CorrectionEvent)]
        assert len(corrections) == 1


class TestFacingTime:
    def test_facing_screen_accumulates_and_fires(self) -> None:
        engine = PostureTickEngine(
            facing_threshold_seconds=2.0,
            off_axis_streak_threshold_seconds=5.0,
        )

        events = engine.tick(_FACING, _FACING, 1.0)
        assert all(not isinstance(e, GoodPostureEvent) for e in events)

        events = engine.tick(_FACING, _FACING, 1.0)
        assert any(isinstance(e, GoodPostureEvent) for e in events)

    def test_non_facing_states_pause_without_reset(self) -> None:
        engine = PostureTickEngine(
            facing_threshold_seconds=10.0,
            off_axis_streak_threshold_seconds=5.0,
        )

        for _ in range(5):
            engine.tick(_FACING, _FACING, 1.0)

        engine.tick(_LEFT, _FACING, 1.0)
        engine.tick(_NO_FACE, _NO_FACE, 1.0)
        events = engine.tick(_FACING, _FACING, 1.0)
        assert all(not isinstance(e, GoodPostureEvent) for e in events)

    def test_facing_resets_after_fire(self) -> None:
        engine = PostureTickEngine(
            facing_threshold_seconds=1.0,
            off_axis_streak_threshold_seconds=5.0,
        )

        events = engine.tick(_FACING, _FACING, 1.0)
        assert any(isinstance(e, GoodPostureEvent) for e in events)

        events = engine.tick(_FACING, _FACING, 1.0)
        assert any(isinstance(e, GoodPostureEvent) for e in events)

    def test_facing_requires_both_axes(self) -> None:
        """只有两个轴都正对才算 facing。"""
        engine = PostureTickEngine(
            facing_threshold_seconds=2.0,
            off_axis_streak_threshold_seconds=5.0,
        )

        # yaw 正对但 pitch 偏离 — 不算 facing
        for _ in range(5):
            events = engine.tick(_FACING, _UP, 1.0)
            assert all(not isinstance(e, GoodPostureEvent) for e in events)

        # pitch 正对但 yaw 偏离 — 不算 facing
        for _ in range(5):
            events = engine.tick(_LEFT, _FACING, 1.0)
            assert all(not isinstance(e, GoodPostureEvent) for e in events)


class TestPresenceTime:
    def test_face_detected_states_accumulate(self) -> None:
        engine = PostureTickEngine(
            eyest_threshold_seconds=10.0,
            off_axis_streak_threshold_seconds=5.0,
        )

        engine.tick(_FACING, _FACING, 1.0)
        engine.tick(_LEFT, _FACING, 1.0)
        engine.tick(_RIGHT, _FACING, 1.0)
        events = engine.tick(_FACING, _UP, 1.0)
        assert all(not isinstance(e, EyeRestEvent) for e in events)

        for _ in range(5):
            events = engine.tick(_FACING, _FACING, 1.0)
        assert all(not isinstance(e, EyeRestEvent) for e in events)

        events = engine.tick(_FACING, _FACING, 1.0)
        assert any(isinstance(e, EyeRestEvent) for e in events)

    def test_no_face_pauses_without_reset(self) -> None:
        engine = PostureTickEngine(
            eyest_threshold_seconds=10.0,
            off_axis_streak_threshold_seconds=5.0,
        )

        for _ in range(5):
            engine.tick(_FACING, _FACING, 1.0)

        events = engine.tick(_NO_FACE, _NO_FACE, 1.0)
        assert all(not isinstance(e, EyeRestEvent) for e in events)

    def test_fires_at_threshold_and_resets(self) -> None:
        engine = PostureTickEngine(
            eyest_threshold_seconds=2.0,
            off_axis_streak_threshold_seconds=5.0,
        )

        events = engine.tick(_FACING, _FACING, 1.0)
        assert all(not isinstance(e, EyeRestEvent) for e in events)
        events = engine.tick(_LEFT, _FACING, 1.0)
        assert any(isinstance(e, EyeRestEvent) for e in events)


class TestWarningLevel:
    def test_off_axis_left_emits_warning(self) -> None:
        engine = PostureTickEngine()
        events = engine.tick(_LEFT, _FACING, 0.1)
        warnings = [e for e in events if isinstance(e, WarningLevelEvent)]
        assert len(warnings) == 1
        assert warnings[0].level == WarningLevel.WARNING
        assert warnings[0].direction == "left"

    def test_off_axis_right_emits_warning(self) -> None:
        engine = PostureTickEngine()
        events = engine.tick(_RIGHT, _FACING, 0.1)
        warnings = [e for e in events if isinstance(e, WarningLevelEvent)]
        assert len(warnings) == 1
        assert warnings[0].level == WarningLevel.WARNING
        assert warnings[0].direction == "right"

    def test_facing_screen_no_warning_event(self) -> None:
        engine = PostureTickEngine()
        events = engine.tick(_FACING, _FACING, 0.1)
        assert all(not isinstance(e, WarningLevelEvent) for e in events)

    def test_escalation_to_severe_at_threshold(self) -> None:
        engine = PostureTickEngine(off_axis_repeat_interval_seconds=10.0)

        events = engine.tick(_LEFT, _FACING, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.WARNING for e in events)

        for _ in range(8):
            events = engine.tick(_LEFT, _FACING, 1.0)
            assert all(not isinstance(e, WarningLevelEvent) for e in events)

        events = engine.tick(_LEFT, _FACING, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.SEVERE for e in events)

    def test_no_escalation_below_threshold(self) -> None:
        engine = PostureTickEngine(off_axis_repeat_interval_seconds=10.0)

        engine.tick(_LEFT, _FACING, 1.0)
        for _ in range(8):
            events = engine.tick(_LEFT, _FACING, 1.0)
            assert all(not isinstance(e, WarningLevelEvent) for e in events)

    def test_facing_screen_after_warning_emits_corrected(self) -> None:
        engine = PostureTickEngine()

        engine.tick(_LEFT, _FACING, 0.1)
        events = engine.tick(_FACING, _FACING, 0.1)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.CORRECTED for e in events)

    def test_corrected_transitions_to_normal_after_2s(self) -> None:
        engine = PostureTickEngine()

        engine.tick(_LEFT, _FACING, 1.0)
        engine.tick(_FACING, _FACING, 1.0)
        events = engine.tick(_FACING, _FACING, 1.0)
        assert all(not isinstance(e, WarningLevelEvent) for e in events)
        events = engine.tick(_FACING, _FACING, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.NORMAL for e in events)

    def test_no_face_resets_warning_to_normal(self) -> None:
        engine = PostureTickEngine(off_axis_repeat_interval_seconds=10.0)

        engine.tick(_LEFT, _FACING, 1.0)
        for _ in range(5):
            engine.tick(_LEFT, _FACING, 1.0)

        events = engine.tick(_NO_FACE, _NO_FACE, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.NORMAL for e in events)

        events = engine.tick(_LEFT, _FACING, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.WARNING for e in events)

    def test_new_episode_after_corrected_resets_timer(self) -> None:
        engine = PostureTickEngine(off_axis_repeat_interval_seconds=10.0)

        engine.tick(_LEFT, _FACING, 1.0)
        engine.tick(_FACING, _FACING, 1.0)
        engine.tick(_RIGHT, _FACING, 1.0)

        for _ in range(8):
            events = engine.tick(_RIGHT, _FACING, 1.0)
            assert all(not isinstance(e, WarningLevelEvent) for e in events)

        events = engine.tick(_RIGHT, _FACING, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.SEVERE for e in events)

    def test_direction_change_mid_warning_updates_for_severe(self) -> None:
        engine = PostureTickEngine(off_axis_repeat_interval_seconds=10.0)

        engine.tick(_LEFT, _FACING, 1.0)
        engine.tick(_RIGHT, _FACING, 1.0)

        for _ in range(7):
            engine.tick(_RIGHT, _FACING, 1.0)

        events = engine.tick(_RIGHT, _FACING, 1.0)
        warnings = [e for e in events if isinstance(e, WarningLevelEvent)]
        assert len(warnings) == 1
        assert warnings[0].level == WarningLevel.SEVERE
        assert warnings[0].direction == "right"

    def test_severe_to_corrected_on_facing_screen(self) -> None:
        engine = PostureTickEngine(off_axis_repeat_interval_seconds=10.0)

        for _ in range(10):
            engine.tick(_LEFT, _FACING, 1.0)
        events = engine.tick(_FACING, _FACING, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.CORRECTED for e in events)

    def test_pitch_off_does_not_advance_warning(self) -> None:
        """pitch 偏离不驱动 warning level 升级。"""
        engine = PostureTickEngine(off_axis_repeat_interval_seconds=10.0)

        engine.tick(_LEFT, _FACING, 1.0)
        for _ in range(20):
            events = engine.tick(_FACING, _UP, 1.0)
            assert all(not isinstance(e, WarningLevelEvent) for e in events)

        for _ in range(8):
            events = engine.tick(_LEFT, _FACING, 1.0)
            assert all(not isinstance(e, WarningLevelEvent) for e in events)

        events = engine.tick(_LEFT, _FACING, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.SEVERE for e in events)


class TestUnifiedSnooze:
    def test_snooze_freezes_off_axis_streak(self) -> None:
        engine = PostureTickEngine(off_axis_streak_threshold_seconds=5.0)

        for _ in range(3):
            engine.tick(_LEFT, _FACING, 1.0)

        engine.snooze()
        assert engine.is_snoozed is True
        for _ in range(10):
            events = engine.tick(_LEFT, _FACING, 1.0)
            assert events == []

        engine.resume()
        assert engine.is_snoozed is False
        result = engine.tick(_LEFT, _FACING, 1.0)
        assert all(not isinstance(e, CorrectionEvent) for e in result)
        result = engine.tick(_LEFT, _FACING, 1.0)
        assert any(isinstance(e, CorrectionEvent) for e in result)

    def test_snooze_freezes_facing_time(self) -> None:
        engine = PostureTickEngine(
            facing_threshold_seconds=10.0,
            off_axis_streak_threshold_seconds=5.0,
        )

        for _ in range(5):
            engine.tick(_FACING, _FACING, 1.0)

        engine.snooze()
        for _ in range(10):
            events = engine.tick(_FACING, _FACING, 1.0)
            assert events == []

        engine.resume()
        for _ in range(4):
            events = engine.tick(_FACING, _FACING, 1.0)
            assert all(not isinstance(e, GoodPostureEvent) for e in events)

        events = engine.tick(_FACING, _FACING, 1.0)
        assert any(isinstance(e, GoodPostureEvent) for e in events)

    def test_snooze_freezes_presence_time(self) -> None:
        engine = PostureTickEngine(
            eyest_threshold_seconds=10.0,
            off_axis_streak_threshold_seconds=5.0,
        )

        for _ in range(5):
            engine.tick(_FACING, _FACING, 1.0)

        engine.snooze()
        for _ in range(10):
            events = engine.tick(_FACING, _FACING, 1.0)
            assert events == []

        engine.resume()
        for _ in range(4):
            events = engine.tick(_FACING, _FACING, 1.0)
            assert all(not isinstance(e, EyeRestEvent) for e in events)

        events = engine.tick(_FACING, _FACING, 1.0)
        assert any(isinstance(e, EyeRestEvent) for e in events)

    def test_snooze_freezes_warning_escalation(self) -> None:
        engine = PostureTickEngine(off_axis_repeat_interval_seconds=10.0)

        engine.tick(_LEFT, _FACING, 1.0)
        engine.snooze()
        for _ in range(20):
            events = engine.tick(_LEFT, _FACING, 1.0)
            assert events == []

        engine.resume()
        for _ in range(8):
            events = engine.tick(_LEFT, _FACING, 1.0)
            assert all(not isinstance(e, WarningLevelEvent) for e in events)

        events = engine.tick(_LEFT, _FACING, 1.0)
        assert any(isinstance(e, WarningLevelEvent) and e.level == WarningLevel.SEVERE for e in events)

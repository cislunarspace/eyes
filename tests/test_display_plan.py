"""Pure-function tests for the DisplayPlan reducers (issue #62).

These tests exercise the display-plan module without instantiating Qt.
They describe the behavior of the badge + warning-banner state machine
in terms of values, not stylesheets or QLabel state.
"""

from __future__ import annotations

from eyes.classifier import PoseState
from eyes.display_plan import (
    BADGE_COLORS_BY_POSE,
    BANNER_BG_CORRECTED,
    BANNER_BG_SEVERE,
    BANNER_BG_WARNING,
    BANNER_FG_CORRECTED,
    BANNER_FG_SEVERE,
    BANNER_FG_WARNING,
    CORRECTED_AUTO_DISMISS_MS,
    DisplayState,
    initial_state,
    reduce_auto_dismiss,
    reduce_pose,
    reduce_warning,
    display_plan,
)
from eyes.types import WarningLevel, WarningLevelEvent


class TestInitialState:
    def test_initial_pose_is_no_face(self) -> None:
        state = initial_state()
        assert state.pose_state == PoseState.NO_FACE

    def test_initial_warning_level_is_normal(self) -> None:
        state = initial_state()
        assert state.warning_level == WarningLevel.NORMAL

    def test_initial_direction_is_none(self) -> None:
        state = initial_state()
        assert state.direction is None


class TestNormalDisplayPlan:
    """At NORMAL warning level, badge follows pose; banner is hidden."""

    def test_no_face_badge_uses_pose_colors(self) -> None:
        state = DisplayState(
            pose_state=PoseState.NO_FACE,
            warning_level=WarningLevel.NORMAL,
            direction=None,
        )
        plan = display_plan(state)
        bg, fg = BADGE_COLORS_BY_POSE[PoseState.NO_FACE]
        assert plan.badge.bg == bg
        assert plan.badge.fg == fg
        assert plan.badge.text_key == "badge.no_face"

    def test_facing_screen_badge_uses_pose_colors(self) -> None:
        state = DisplayState(
            pose_state=PoseState.FACING_SCREEN,
            warning_level=WarningLevel.NORMAL,
            direction=None,
        )
        plan = display_plan(state)
        bg, fg = BADGE_COLORS_BY_POSE[PoseState.FACING_SCREEN]
        assert plan.badge.bg == bg
        assert plan.badge.fg == fg
        assert plan.badge.text_key == "badge.facing_screen"

    def test_normal_banner_hidden(self) -> None:
        state = DisplayState(
            pose_state=PoseState.FACING_SCREEN,
            warning_level=WarningLevel.NORMAL,
            direction=None,
        )
        plan = display_plan(state)
        assert plan.banner.visible is False
        assert plan.banner.auto_dismiss_ms is None


class TestWarningDisplayPlan:
    """WARNING level: yellow banner with directional hint, badge tinted yellow."""

    def test_warning_left_banner_visible_yellow_with_left_hint(self) -> None:
        state = DisplayState(
            pose_state=PoseState.OFF_AXIS_LEFT,
            warning_level=WarningLevel.WARNING,
            direction="left",
        )
        plan = display_plan(state)
        assert plan.banner.visible is True
        assert plan.banner.bg == BANNER_BG_WARNING
        assert plan.banner.fg == BANNER_FG_WARNING
        assert plan.banner.text_keys == (
            "main_window.please_face_screen",
            "main_window.adjust_left_hint",
        )
        assert plan.banner.auto_dismiss_ms is None

    def test_warning_right_banner_uses_right_hint(self) -> None:
        state = DisplayState(
            pose_state=PoseState.OFF_AXIS_RIGHT,
            warning_level=WarningLevel.WARNING,
            direction="right",
        )
        plan = display_plan(state)
        assert plan.banner.text_keys == (
            "main_window.please_face_screen",
            "main_window.adjust_right_hint",
        )

    def test_warning_badge_tinted_yellow_text_still_pose(self) -> None:
        state = DisplayState(
            pose_state=PoseState.OFF_AXIS_LEFT,
            warning_level=WarningLevel.WARNING,
            direction="left",
        )
        plan = display_plan(state)
        assert plan.badge.bg == BANNER_BG_WARNING
        assert plan.badge.fg == BANNER_FG_WARNING
        assert plan.badge.text_key == "badge.off_axis_left"


class TestSevereDisplayPlan:
    """SEVERE level: red banner with directional hint."""

    def test_severe_left_banner_visible_red_with_left_hint(self) -> None:
        state = DisplayState(
            pose_state=PoseState.OFF_AXIS_LEFT,
            warning_level=WarningLevel.SEVERE,
            direction="left",
        )
        plan = display_plan(state)
        assert plan.banner.visible is True
        assert plan.banner.bg == BANNER_BG_SEVERE
        assert plan.banner.fg == BANNER_FG_SEVERE
        assert plan.banner.text_keys == (
            "main_window.please_face_screen",
            "main_window.adjust_left_hint",
        )

    def test_severe_right_banner_uses_right_hint(self) -> None:
        state = DisplayState(
            pose_state=PoseState.OFF_AXIS_RIGHT,
            warning_level=WarningLevel.SEVERE,
            direction="right",
        )
        plan = display_plan(state)
        assert plan.banner.text_keys[1] == "main_window.adjust_right_hint"

    def test_severe_badge_tinted_red(self) -> None:
        state = DisplayState(
            pose_state=PoseState.OFF_AXIS_RIGHT,
            warning_level=WarningLevel.SEVERE,
            direction="right",
        )
        plan = display_plan(state)
        assert plan.badge.bg == BANNER_BG_SEVERE
        assert plan.badge.fg == BANNER_FG_SEVERE


class TestCorrectedDisplayPlan:
    """CORRECTED level: green banner that auto-dismisses after 2 s."""

    def test_corrected_banner_green_with_posture_good_text(self) -> None:
        state = DisplayState(
            pose_state=PoseState.FACING_SCREEN,
            warning_level=WarningLevel.CORRECTED,
            direction=None,
        )
        plan = display_plan(state)
        assert plan.banner.visible is True
        assert plan.banner.bg == BANNER_BG_CORRECTED
        assert plan.banner.fg == BANNER_FG_CORRECTED
        assert plan.banner.text_keys == ("main_window.posture_good",)

    def test_corrected_banner_carries_auto_dismiss_ms(self) -> None:
        state = DisplayState(
            pose_state=PoseState.FACING_SCREEN,
            warning_level=WarningLevel.CORRECTED,
            direction=None,
        )
        plan = display_plan(state)
        assert plan.banner.auto_dismiss_ms == CORRECTED_AUTO_DISMISS_MS

    def test_corrected_badge_tinted_green(self) -> None:
        state = DisplayState(
            pose_state=PoseState.FACING_SCREEN,
            warning_level=WarningLevel.CORRECTED,
            direction=None,
        )
        plan = display_plan(state)
        assert plan.badge.bg == BANNER_BG_CORRECTED
        assert plan.badge.fg == BANNER_FG_CORRECTED


class TestReducePose:
    """`reduce_pose` updates pose_state without disturbing warning state."""

    def test_pose_update_replaces_pose_state(self) -> None:
        state = initial_state()
        new_state = reduce_pose(state, PoseState.FACING_SCREEN)
        assert new_state.pose_state == PoseState.FACING_SCREEN

    def test_pose_update_preserves_warning_level(self) -> None:
        state = DisplayState(
            pose_state=PoseState.NO_FACE,
            warning_level=WarningLevel.WARNING,
            direction="left",
        )
        new_state = reduce_pose(state, PoseState.OFF_AXIS_LEFT)
        assert new_state.warning_level == WarningLevel.WARNING
        assert new_state.direction == "left"

    def test_pose_update_returns_new_object(self) -> None:
        state = initial_state()
        new_state = reduce_pose(state, PoseState.FACING_SCREEN)
        assert new_state is not state


class TestReduceWarning:
    """`reduce_warning` advances the warning lifecycle."""

    def test_warning_event_sets_level_and_direction(self) -> None:
        state = initial_state()
        new_state = reduce_warning(
            state, WarningLevelEvent(level=WarningLevel.WARNING, direction="left")
        )
        assert new_state.warning_level == WarningLevel.WARNING
        assert new_state.direction == "left"

    def test_severe_event_sets_level_and_direction(self) -> None:
        state = initial_state()
        new_state = reduce_warning(
            state, WarningLevelEvent(level=WarningLevel.SEVERE, direction="right")
        )
        assert new_state.warning_level == WarningLevel.SEVERE
        assert new_state.direction == "right"

    def test_normal_event_clears_warning(self) -> None:
        state = DisplayState(
            pose_state=PoseState.FACING_SCREEN,
            warning_level=WarningLevel.WARNING,
            direction="left",
        )
        new_state = reduce_warning(
            state, WarningLevelEvent(level=WarningLevel.NORMAL, direction=None)
        )
        assert new_state.warning_level == WarningLevel.NORMAL
        assert new_state.direction is None

    def test_corrected_event_keeps_last_direction(self) -> None:
        """CORRECTED has no direction of its own; we don't fabricate one."""
        state = DisplayState(
            pose_state=PoseState.FACING_SCREEN,
            warning_level=WarningLevel.WARNING,
            direction="left",
        )
        new_state = reduce_warning(
            state, WarningLevelEvent(level=WarningLevel.CORRECTED, direction=None)
        )
        assert new_state.warning_level == WarningLevel.CORRECTED

    def test_warning_event_preserves_pose_state(self) -> None:
        state = DisplayState(
            pose_state=PoseState.OFF_AXIS_LEFT,
            warning_level=WarningLevel.NORMAL,
            direction=None,
        )
        new_state = reduce_warning(
            state, WarningLevelEvent(level=WarningLevel.WARNING, direction="left")
        )
        assert new_state.pose_state == PoseState.OFF_AXIS_LEFT


class TestReduceAutoDismiss:
    """`reduce_auto_dismiss` clears CORRECTED → NORMAL after the timer fires."""

    def test_corrected_becomes_normal(self) -> None:
        state = DisplayState(
            pose_state=PoseState.FACING_SCREEN,
            warning_level=WarningLevel.CORRECTED,
            direction=None,
        )
        new_state = reduce_auto_dismiss(state)
        assert new_state.warning_level == WarningLevel.NORMAL

    def test_corrected_dismiss_clears_direction(self) -> None:
        state = DisplayState(
            pose_state=PoseState.FACING_SCREEN,
            warning_level=WarningLevel.CORRECTED,
            direction="left",
        )
        new_state = reduce_auto_dismiss(state)
        assert new_state.direction is None

    def test_dismiss_only_acts_on_corrected(self) -> None:
        state = DisplayState(
            pose_state=PoseState.OFF_AXIS_LEFT,
            warning_level=WarningLevel.WARNING,
            direction="left",
        )
        new_state = reduce_auto_dismiss(state)
        assert new_state == state

    def test_dismiss_preserves_pose_state(self) -> None:
        state = DisplayState(
            pose_state=PoseState.FACING_SCREEN,
            warning_level=WarningLevel.CORRECTED,
            direction=None,
        )
        new_state = reduce_auto_dismiss(state)
        assert new_state.pose_state == PoseState.FACING_SCREEN


class TestLifecycleProjection:
    """End-to-end: drive state through reducers and check the rendered plan."""

    def test_warning_then_normal_hides_banner_and_reverts_badge(self) -> None:
        state = initial_state()
        state = reduce_pose(state, PoseState.OFF_AXIS_LEFT)
        state = reduce_warning(
            state, WarningLevelEvent(level=WarningLevel.WARNING, direction="left")
        )
        assert display_plan(state).banner.visible is True

        state = reduce_warning(
            state, WarningLevelEvent(level=WarningLevel.NORMAL, direction=None)
        )
        plan = display_plan(state)
        assert plan.banner.visible is False
        bg, fg = BADGE_COLORS_BY_POSE[PoseState.OFF_AXIS_LEFT]
        assert plan.badge.bg == bg

    def test_warning_then_corrected_then_dismiss_returns_to_normal(self) -> None:
        state = initial_state()
        state = reduce_pose(state, PoseState.OFF_AXIS_LEFT)
        state = reduce_warning(
            state, WarningLevelEvent(level=WarningLevel.WARNING, direction="left")
        )
        state = reduce_warning(
            state, WarningLevelEvent(level=WarningLevel.CORRECTED, direction=None)
        )
        plan = display_plan(state)
        assert plan.banner.bg == BANNER_BG_CORRECTED
        assert plan.banner.auto_dismiss_ms == CORRECTED_AUTO_DISMISS_MS

        state = reduce_pose(state, PoseState.FACING_SCREEN)
        state = reduce_auto_dismiss(state)
        plan = display_plan(state)
        assert plan.banner.visible is False
        bg, fg = BADGE_COLORS_BY_POSE[PoseState.FACING_SCREEN]
        assert plan.badge.bg == bg

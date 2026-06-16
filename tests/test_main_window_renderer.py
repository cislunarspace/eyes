"""Tests for MainWindowRenderer.apply_plan — the renderer's contract.

Each test exercises one warning level through the renderer's
`apply_plan` method. The renderer takes a `DisplayPlan` value object
and turns it into widget tree updates; this is the surface the
`MainWindow` shell calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtWidgets import QWidget

from eyes.classifier import PoseState
from eyes.display_plan import (
    BadgePlan,
    BannerPlan,
    DisplayPlan,
    DisplayState,
    display_plan,
    initial_state,
    reduce_warning,
)
from eyes.main_window_renderer import MainWindowRenderer
from eyes.types import WarningLevel, WarningLevelEvent


def _make_renderer(qtbot) -> tuple[MainWindowRenderer, QWidget]:
    central = QWidget()
    qtbot.addWidget(central)
    return MainWindowRenderer(central), central


class TestApplyPlanNormalPose:
    def test_badge_uses_pose_color_no_banner(self, qtbot) -> None:
        renderer, _ = _make_renderer(qtbot)
        plan = display_plan(
            DisplayState(
                pose_state=PoseState.FACING_SCREEN,
                warning_level=WarningLevel.NORMAL,
                direction=None,
            )
        )
        renderer.apply_plan(plan)
        # NORMAL with FACING_SCREEN: green badge, banner hidden.
        assert "#1a4d1a" in renderer._badge_label.styleSheet()
        assert "#00cc44" in renderer._badge_label.styleSheet()
        assert not renderer._warning_banner.isVisible()
        assert not renderer._auto_dismiss_timer.isActive()

    def test_no_face_state(self, qtbot) -> None:
        renderer, _ = _make_renderer(qtbot)
        plan = display_plan(
            DisplayState(
                pose_state=PoseState.NO_FACE,
                warning_level=WarningLevel.NORMAL,
                direction=None,
            )
        )
        renderer.apply_plan(plan)
        assert "#1a1a1a" in renderer._badge_label.styleSheet()
        assert "#888888" in renderer._badge_label.styleSheet()


class TestApplyPlanWarning:
    def test_warning_banner_shown_with_yellow_color(self, qtbot) -> None:
        renderer, _ = _make_renderer(qtbot)
        plan = display_plan(
            DisplayState(
                pose_state=PoseState.OFF_AXIS_LEFT,
                warning_level=WarningLevel.WARNING,
                direction="left",
            )
        )
        renderer.apply_plan(plan)
        assert renderer._warning_banner.isVisibleTo(renderer._camera_status_label.parent())
        assert "#FFD700" in renderer._warning_banner.styleSheet()
        assert "#000000" in renderer._warning_banner.styleSheet()
        assert not renderer._auto_dismiss_timer.isActive()

    def test_warning_banner_text_contains_hints(self, qtbot) -> None:
        renderer, _ = _make_renderer(qtbot)
        plan = display_plan(
            DisplayState(
                pose_state=PoseState.OFF_AXIS_LEFT,
                warning_level=WarningLevel.WARNING,
                direction="left",
            )
        )
        renderer.apply_plan(plan)
        text = renderer._warning_banner.text()
        assert "请正视屏幕" in text
        assert "向左调整" in text


class TestApplyPlanSevere:
    def test_severe_banner_shown_with_red_color(self, qtbot) -> None:
        renderer, _ = _make_renderer(qtbot)
        plan = display_plan(
            DisplayState(
                pose_state=PoseState.OFF_AXIS_LEFT,
                warning_level=WarningLevel.SEVERE,
                direction="left",
            )
        )
        renderer.apply_plan(plan)
        assert renderer._warning_banner.isVisibleTo(renderer._camera_status_label.parent())
        assert "#FF0000" in renderer._warning_banner.styleSheet()
        assert "#FFFFFF" in renderer._warning_banner.styleSheet()
        assert not renderer._auto_dismiss_timer.isActive()


class TestApplyPlanCorrected:
    def test_corrected_banner_starts_auto_dismiss_timer(self, qtbot) -> None:
        renderer, _ = _make_renderer(qtbot)
        plan = display_plan(
            DisplayState(
                pose_state=PoseState.FACING_SCREEN,
                warning_level=WarningLevel.CORRECTED,
                direction=None,
            )
        )
        renderer.apply_plan(plan)
        assert renderer._warning_banner.isVisibleTo(renderer._camera_status_label.parent())
        assert "#00AA00" in renderer._warning_banner.styleSheet()
        assert renderer._auto_dismiss_timer.isActive()
        # CORRECTED_AUTO_DISMISS_MS = 2000ms.
        assert renderer._auto_dismiss_timer.interval() == 2000

    def test_corrected_text_is_posture_good(self, qtbot) -> None:
        renderer, _ = _make_renderer(qtbot)
        plan = display_plan(
            DisplayState(
                pose_state=PoseState.FACING_SCREEN,
                warning_level=WarningLevel.CORRECTED,
                direction=None,
            )
        )
        renderer.apply_plan(plan)
        assert "姿势良好" in renderer._warning_banner.text()


class TestAutoDismissCallback:
    def test_callback_fires_after_timer(self, qtbot) -> None:
        renderer, _ = _make_renderer(qtbot)
        callback = MagicMock()
        renderer.set_auto_dismiss_callback(callback)
        # Apply a CORRECTED plan to start the auto-dismiss timer.
        plan = display_plan(
            DisplayState(
                pose_state=PoseState.FACING_SCREEN,
                warning_level=WarningLevel.CORRECTED,
                direction=None,
            )
        )
        renderer.apply_plan(plan)
        qtbot.wait(2100)
        callback.assert_called_once()

    def test_no_callback_does_not_raise(self, qtbot) -> None:
        renderer, _ = _make_renderer(qtbot)
        # No callback registered — auto-dismiss timer should silently
        # do nothing when it fires.
        plan = display_plan(
            DisplayState(
                pose_state=PoseState.FACING_SCREEN,
                warning_level=WarningLevel.CORRECTED,
                direction=None,
            )
        )
        renderer.apply_plan(plan)
        qtbot.wait(2100)
        # No assertion needed — the test is that nothing raised.


class TestBannerHiddenForNormal:
    def test_normal_warning_hides_banner(self, qtbot) -> None:
        renderer, _ = _make_renderer(qtbot)
        # First show a warning so the banner is visible.
        renderer.apply_plan(
            display_plan(
                DisplayState(
                    pose_state=PoseState.OFF_AXIS_LEFT,
                    warning_level=WarningLevel.WARNING,
                    direction="left",
                )
            )
        )
        assert renderer._warning_banner.isVisibleTo(renderer._camera_status_label.parent())
        # Then return to NORMAL.
        renderer.apply_plan(
            display_plan(
                DisplayState(
                    pose_state=PoseState.FACING_SCREEN,
                    warning_level=WarningLevel.NORMAL,
                    direction=None,
                )
            )
        )
        assert not renderer._warning_banner.isVisibleTo(renderer._camera_status_label.parent())


class TestSetReadoutText:
    def test_updates_readout_label(self, qtbot) -> None:
        renderer, _ = _make_renderer(qtbot)
        renderer.set_readout_text("yaw: +1.5°   roll: -0.3°")
        assert renderer._readout_label.text() == "yaw: +1.5°   roll: -0.3°"


class TestCameraStatusVisible:
    def test_shows_and_hides(self, qtbot) -> None:
        renderer, _ = _make_renderer(qtbot)
        renderer.set_camera_status_visible(True)
        assert renderer._camera_status_label.isVisibleTo(renderer._camera_status_label.parent())
        renderer.set_camera_status_visible(False)
        assert not renderer._camera_status_label.isVisibleTo(renderer._camera_status_label.parent())


# Sanity check the BadgePlan / BannerPlan / DisplayPlan shapes that the
# renderer is contracted to consume.
class TestDisplayPlanContract:
    def test_badge_plan_carries_text_key_and_colors(self) -> None:
        badge = BadgePlan(text_key="badge.facing_screen", bg="#1a4d1a", fg="#00cc44")
        assert badge.text_key == "badge.facing_screen"
        assert badge.bg == "#1a4d1a"
        assert badge.fg == "#00cc44"

    def test_banner_plan_carries_visibility_and_auto_dismiss(self) -> None:
        banner = BannerPlan(
            visible=True,
            text_keys=("main_window.please_face_screen", "main_window.adjust_left_hint"),
            bg="#FFD700",
            fg="#000000",
            auto_dismiss_ms=None,
        )
        assert banner.visible is True
        assert banner.auto_dismiss_ms is None
        assert len(banner.text_keys) == 2

    def test_reduce_warning_to_normal(self) -> None:
        # The reducer lives in display_plan.py, but a smoke test here
        # makes the dependency explicit and documents intent.
        state = DisplayState(
            pose_state=PoseState.OFF_AXIS_LEFT,
            warning_level=WarningLevel.WARNING,
            direction="left",
        )
        new_state = reduce_warning(
            state, WarningLevelEvent(level=WarningLevel.NORMAL, direction=None)
        )
        assert new_state.warning_level == WarningLevel.NORMAL
        assert new_state.direction is None

    def test_initial_state_is_no_face_normal(self) -> None:
        state = initial_state()
        assert state.pose_state == PoseState.NO_FACE
        assert state.warning_level == WarningLevel.NORMAL
        assert state.direction is None


# Keep references so static analyzers don't flag the imports.
_ = DisplayPlan

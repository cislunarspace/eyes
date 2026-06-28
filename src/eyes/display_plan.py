"""Pure-function display plan for the main window (issue #62).

Maps `(PoseState, WarningLevel, direction)` → `DisplayPlan`. The plan is
a value object describing what the badge and warning banner should look
like — colors, i18n text keys, visibility, and the auto-dismiss timeout
for the CORRECTED banner. The main window renders the plan into Qt
widgets; all policy lives here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, assert_never

from .classifier import PoseState
from .runtime_timings import CORRECTED_AUTO_DISMISS_MS  # noqa: F401 — re-exported
from .types import WarningLevel, WarningLevelEvent

# Badge colours when the warning level is NORMAL (badge follows pose state).
BADGE_COLORS_BY_POSE: dict[PoseState, tuple[str, str]] = {
    PoseState.FACING_SCREEN: ("#1a4d1a", "#00cc44"),
    PoseState.OFF_AXIS_LEFT: ("#4d1a1a", "#ff4444"),
    PoseState.OFF_AXIS_RIGHT: ("#4d1a1a", "#ff4444"),
    PoseState.HEAD_UP: ("#4d3d1a", "#ffaa00"),
    PoseState.HEAD_DOWN: ("#4d3d1a", "#ffaa00"),
    PoseState.NO_FACE: ("#1a1a1a", "#888888"),
}

_BADGE_TEXT_KEY_BY_POSE: dict[PoseState, str] = {
    PoseState.FACING_SCREEN: "badge.facing_screen",
    PoseState.OFF_AXIS_LEFT: "badge.off_axis_left",
    PoseState.OFF_AXIS_RIGHT: "badge.off_axis_right",
    PoseState.HEAD_UP: "badge.head_up",
    PoseState.HEAD_DOWN: "badge.head_down",
    PoseState.NO_FACE: "badge.no_face",
}

BANNER_BG_WARNING = "#FFD700"
BANNER_FG_WARNING = "#000000"
BANNER_BG_SEVERE = "#FF0000"
BANNER_FG_SEVERE = "#FFFFFF"
BANNER_BG_CORRECTED = "#00AA00"
BANNER_FG_CORRECTED = "#FFFFFF"


@dataclass(frozen=True)
class BadgePlan:
    text_key: str
    bg: str
    fg: str


@dataclass(frozen=True)
class BannerPlan:
    visible: bool
    text_keys: tuple[str, ...]
    bg: str
    fg: str
    auto_dismiss_ms: Optional[int]


@dataclass(frozen=True)
class DisplayPlan:
    badge: BadgePlan
    banner: BannerPlan


@dataclass(frozen=True)
class DisplayState:
    pose_state: PoseState
    warning_level: WarningLevel
    direction: Optional[str]


_HIDDEN_BANNER = BannerPlan(
    visible=False,
    text_keys=(),
    bg="",
    fg="",
    auto_dismiss_ms=None,
)


def initial_state() -> DisplayState:
    return DisplayState(
        pose_state=PoseState.NO_FACE,
        warning_level=WarningLevel.NORMAL,
        direction=None,
    )


def reduce_pose(state: DisplayState, pose_state: PoseState) -> DisplayState:
    return DisplayState(
        pose_state=pose_state,
        warning_level=state.warning_level,
        direction=state.direction,
    )


def reduce_warning(state: DisplayState, event: WarningLevelEvent) -> DisplayState:
    if event.level == WarningLevel.NORMAL:
        return DisplayState(
            pose_state=state.pose_state,
            warning_level=WarningLevel.NORMAL,
            direction=None,
        )
    if event.level == WarningLevel.CORRECTED:
        return DisplayState(
            pose_state=state.pose_state,
            warning_level=WarningLevel.CORRECTED,
            direction=None,
        )
    return DisplayState(
        pose_state=state.pose_state,
        warning_level=event.level,
        direction=event.direction,
    )


def reduce_auto_dismiss(state: DisplayState) -> DisplayState:
    if state.warning_level != WarningLevel.CORRECTED:
        return state
    return DisplayState(
        pose_state=state.pose_state,
        warning_level=WarningLevel.NORMAL,
        direction=None,
    )


def display_plan(state: DisplayState) -> DisplayPlan:
    if state.warning_level == WarningLevel.NORMAL:
        bg, fg = BADGE_COLORS_BY_POSE[state.pose_state]
        return DisplayPlan(
            badge=BadgePlan(
                text_key=_BADGE_TEXT_KEY_BY_POSE[state.pose_state],
                bg=bg,
                fg=fg,
            ),
            banner=_HIDDEN_BANNER,
        )

    if state.warning_level == WarningLevel.WARNING:
        banner_bg, banner_fg = BANNER_BG_WARNING, BANNER_FG_WARNING
        banner_text_keys = _direction_banner_text_keys(state.direction)
        auto_dismiss_ms: Optional[int] = None
    elif state.warning_level == WarningLevel.SEVERE:
        banner_bg, banner_fg = BANNER_BG_SEVERE, BANNER_FG_SEVERE
        banner_text_keys = _direction_banner_text_keys(state.direction)
        auto_dismiss_ms = None
    elif state.warning_level == WarningLevel.CORRECTED:
        banner_bg, banner_fg = BANNER_BG_CORRECTED, BANNER_FG_CORRECTED
        banner_text_keys = ("main_window.posture_good",)
        auto_dismiss_ms = CORRECTED_AUTO_DISMISS_MS
    else:
        assert_never(state.warning_level)

    return DisplayPlan(
        badge=BadgePlan(
            text_key=_BADGE_TEXT_KEY_BY_POSE[state.pose_state],
            bg=banner_bg,
            fg=banner_fg,
        ),
        banner=BannerPlan(
            visible=True,
            text_keys=banner_text_keys,
            bg=banner_bg,
            fg=banner_fg,
            auto_dismiss_ms=auto_dismiss_ms,
        ),
    )


def _direction_banner_text_keys(direction: Optional[str]) -> tuple[str, str]:
    hint = (
        "main_window.adjust_left_hint"
        if direction == "left"
        else "main_window.adjust_right_hint"
    )
    return ("main_window.please_face_screen", hint)

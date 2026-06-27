use super::{classifier::PoseState, posture_tick_engine::WarningLevel};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BadgePlan {
    pub text_key: String,
    pub bg: String,
    pub fg: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BannerPlan {
    pub visible: bool,
    pub text_keys: Vec<String>,
    pub bg: String,
    pub fg: String,
    pub auto_dismiss_ms: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DisplayPlan {
    pub badge: BadgePlan,
    pub banner: BannerPlan,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DisplayState {
    pub pose_state: PoseState,
    pub warning_level: WarningLevel,
    pub direction: Option<String>,
}

pub fn initial_state() -> DisplayState {
    DisplayState {
        pose_state: PoseState::NoFace,
        warning_level: WarningLevel::Normal,
        direction: None,
    }
}

pub fn reduce_pose(state: DisplayState, pose_state: PoseState) -> DisplayState {
    DisplayState {
        pose_state,
        ..state
    }
}

pub fn reduce_warning(
    state: DisplayState,
    warning_level: WarningLevel,
    direction: Option<&str>,
) -> DisplayState {
    match warning_level {
        WarningLevel::Normal => DisplayState {
            warning_level,
            direction: None,
            ..state
        },
        WarningLevel::Corrected => DisplayState {
            warning_level,
            direction: None,
            ..state
        },
        WarningLevel::Warning | WarningLevel::Severe => DisplayState {
            warning_level,
            direction: direction.map(str::to_string),
            ..state
        },
    }
}

pub fn reduce_auto_dismiss(state: DisplayState) -> DisplayState {
    if state.warning_level != WarningLevel::Corrected {
        return state;
    }
    DisplayState {
        warning_level: WarningLevel::Normal,
        direction: None,
        ..state
    }
}

pub fn display_plan(state: &DisplayState) -> DisplayPlan {
    if state.warning_level == WarningLevel::Normal {
        let (bg, fg) = badge_colors(state.pose_state);
        return DisplayPlan {
            badge: BadgePlan {
                text_key: badge_text_key(state.pose_state).to_string(),
                bg: bg.to_string(),
                fg: fg.to_string(),
            },
            banner: hidden_banner(),
        };
    }

    let (banner_bg, banner_fg, text_keys, auto_dismiss_ms) = match state.warning_level {
        WarningLevel::Warning => (
            "#FFD700",
            "#000000",
            direction_banner_text_keys(state.direction.as_deref()),
            None,
        ),
        WarningLevel::Severe => (
            "#FF0000",
            "#FFFFFF",
            direction_banner_text_keys(state.direction.as_deref()),
            None,
        ),
        WarningLevel::Corrected => (
            "#00AA00",
            "#FFFFFF",
            vec!["main_window.posture_good".to_string()],
            Some(2000),
        ),
        WarningLevel::Normal => unreachable!(),
    };

    DisplayPlan {
        badge: BadgePlan {
            text_key: badge_text_key(state.pose_state).to_string(),
            bg: banner_bg.to_string(),
            fg: banner_fg.to_string(),
        },
        banner: BannerPlan {
            visible: true,
            text_keys,
            bg: banner_bg.to_string(),
            fg: banner_fg.to_string(),
            auto_dismiss_ms,
        },
    }
}

fn hidden_banner() -> BannerPlan {
    BannerPlan {
        visible: false,
        text_keys: Vec::new(),
        bg: String::new(),
        fg: String::new(),
        auto_dismiss_ms: None,
    }
}

fn badge_colors(pose_state: PoseState) -> (&'static str, &'static str) {
    match pose_state {
        PoseState::FacingScreen => ("#1a4d1a", "#00cc44"),
        PoseState::OffAxisLeft | PoseState::OffAxisRight => ("#4d1a1a", "#ff4444"),
        PoseState::OffAxisOther => ("#4d3d1a", "#ffaa00"),
        PoseState::NoFace => ("#1a1a1a", "#888888"),
    }
}

fn badge_text_key(pose_state: PoseState) -> &'static str {
    match pose_state {
        PoseState::FacingScreen => "badge.facing_screen",
        PoseState::OffAxisLeft => "badge.off_axis_left",
        PoseState::OffAxisRight => "badge.off_axis_right",
        PoseState::OffAxisOther => "badge.off_axis_other",
        PoseState::NoFace => "badge.no_face",
    }
}

fn direction_banner_text_keys(direction: Option<&str>) -> Vec<String> {
    let hint = if direction == Some("left") {
        "main_window.adjust_right_hint"
    } else {
        "main_window.adjust_left_hint"
    };
    vec![
        "main_window.please_face_screen".to_string(),
        hint.to_string(),
    ]
}

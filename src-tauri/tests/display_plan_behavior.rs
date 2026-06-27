use eyes_lib::domain::{
    classifier::PoseState,
    display_plan::{display_plan, initial_state, reduce_auto_dismiss, reduce_pose, reduce_warning},
    posture_tick_engine::WarningLevel,
};

#[test]
fn normal_badge_follows_pose_and_banner_is_hidden() {
    let state = reduce_pose(initial_state(), PoseState::FacingScreen);
    let plan = display_plan(&state);

    assert_eq!(plan.badge.text_key, "badge.facing_screen");
    assert_eq!(plan.badge.bg, "#1a4d1a");
    assert_eq!(plan.badge.fg, "#00cc44");
    assert!(!plan.banner.visible);
    assert!(plan.banner.auto_dismiss_ms.is_none());
}

#[test]
fn warning_and_severe_banners_use_directional_hints_and_tint_badge() {
    let state = reduce_warning(
        reduce_pose(initial_state(), PoseState::OffAxisLeft),
        WarningLevel::Warning,
        Some("left"),
    );
    let plan = display_plan(&state);
    assert!(plan.banner.visible);
    assert_eq!(plan.banner.bg, "#FFD700");
    assert_eq!(
        plan.banner.text_keys,
        vec![
            "main_window.please_face_screen",
            "main_window.adjust_right_hint"
        ]
    );
    assert_eq!(plan.badge.bg, "#FFD700");
    assert_eq!(plan.badge.text_key, "badge.off_axis_left");

    let state = reduce_warning(state, WarningLevel::Severe, Some("right"));
    let plan = display_plan(&state);
    assert_eq!(plan.banner.bg, "#FF0000");
    assert_eq!(plan.banner.text_keys[1], "main_window.adjust_left_hint");
}

#[test]
fn corrected_banner_auto_dismisses_to_normal() {
    let state = reduce_warning(
        reduce_pose(initial_state(), PoseState::FacingScreen),
        WarningLevel::Corrected,
        None,
    );
    let plan = display_plan(&state);
    assert_eq!(plan.banner.bg, "#00AA00");
    assert_eq!(plan.banner.text_keys, vec!["main_window.posture_good"]);
    assert_eq!(plan.banner.auto_dismiss_ms, Some(2000));

    let state = reduce_auto_dismiss(state);
    let plan = display_plan(&state);
    assert!(!plan.banner.visible);
    assert_eq!(plan.badge.text_key, "badge.facing_screen");
}

#[test]
fn normal_warning_event_clears_direction_and_non_corrected_auto_dismiss_is_noop() {
    let state = reduce_warning(initial_state(), WarningLevel::Warning, Some("left"));
    let unchanged = reduce_auto_dismiss(state.clone());
    assert_eq!(unchanged, state);

    let state = reduce_warning(state, WarningLevel::Normal, None);
    assert_eq!(state.warning_level, WarningLevel::Normal);
    assert!(state.direction.is_none());
}

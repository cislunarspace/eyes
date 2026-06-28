use eyes_lib::domain::{
    classifier::PoseState,
    posture_tick_engine::{PostureTickEngine, SenseEvent, WarningLevel},
};

fn has_correction(events: &[SenseEvent]) -> bool {
    events
        .iter()
        .any(|event| matches!(event, SenseEvent::Correction { .. }))
}

fn has_good_posture(events: &[SenseEvent]) -> bool {
    events
        .iter()
        .any(|event| matches!(event, SenseEvent::GoodPosture))
}

fn has_eye_rest(events: &[SenseEvent]) -> bool {
    events
        .iter()
        .any(|event| matches!(event, SenseEvent::EyeRest))
}

fn has_warning(events: &[SenseEvent], level: WarningLevel) -> bool {
    events.iter().any(|event| matches!(event, SenseEvent::WarningLevelChanged { level: actual, .. } if *actual == level))
}

#[test]
fn off_axis_streak_fires_correction_at_threshold_and_repeats() {
    let mut engine = PostureTickEngine::default();

    assert!(!has_correction(&engine.tick(PoseState::OffAxisLeft, 0.2)));
    assert!(has_correction(&engine.tick(PoseState::OffAxisLeft, 0.1)));

    for _ in 0..9 {
        assert!(!has_correction(&engine.tick(PoseState::OffAxisLeft, 1.0)));
    }
    assert!(has_correction(&engine.tick(PoseState::OffAxisLeft, 1.0)));
}

#[test]
fn zero_streak_threshold_fires_immediately() {
    let mut engine = PostureTickEngine::new(Some(0.0), None, None, None);
    assert!(has_correction(&engine.tick(PoseState::OffAxisLeft, 0.1)));
}

#[test]
fn non_off_axis_left_right_states_reset_or_skip_correction_streak() {
    let mut engine = PostureTickEngine::new(Some(5.0), None, None, None);
    for _ in 0..3 {
        engine.tick(PoseState::OffAxisLeft, 1.0);
    }
    engine.tick(PoseState::NoFace, 1.0);
    for _ in 0..4 {
        assert!(!has_correction(&engine.tick(PoseState::OffAxisLeft, 1.0)));
    }
    assert!(has_correction(&engine.tick(PoseState::OffAxisLeft, 1.0)));

    for _ in 0..20 {
        assert!(!has_correction(&engine.tick(PoseState::HeadUp, 1.0)));
    }
}

#[test]
fn facing_and_presence_accumulators_fire_and_reset_at_thresholds() {
    let mut engine = PostureTickEngine::new(Some(5.0), None, Some(2.0), Some(3.0));

    assert!(!has_good_posture(
        &engine.tick(PoseState::FacingScreen, 1.0)
    ));
    let events = engine.tick(PoseState::FacingScreen, 1.0);
    assert!(has_good_posture(&events));
    assert!(!has_eye_rest(&events));

    let events = engine.tick(PoseState::OffAxisLeft, 1.0);
    assert!(has_eye_rest(&events));
}

#[test]
fn non_facing_and_no_face_pause_accumulators_without_resetting() {
    let mut engine = PostureTickEngine::new(Some(5.0), None, Some(10.0), Some(10.0));

    for _ in 0..5 {
        engine.tick(PoseState::FacingScreen, 1.0);
    }
    engine.tick(PoseState::OffAxisLeft, 1.0);
    engine.tick(PoseState::NoFace, 1.0);
    assert!(!has_good_posture(
        &engine.tick(PoseState::FacingScreen, 1.0)
    ));

    for _ in 0..3 {
        engine.tick(PoseState::FacingScreen, 1.0);
    }
    let events = engine.tick(PoseState::FacingScreen, 1.0);
    assert!(has_good_posture(&events));
    assert!(!has_eye_rest(&events));
}

#[test]
fn warning_level_lifecycle_matches_python_oracle() {
    let mut engine = PostureTickEngine::new(None, Some(10.0), None, None);

    let events = engine.tick(PoseState::OffAxisLeft, 1.0);
    assert!(has_warning(&events, WarningLevel::Warning));

    for _ in 0..8 {
        assert!(!has_warning(
            &engine.tick(PoseState::OffAxisRight, 1.0),
            WarningLevel::Severe
        ));
    }
    let events = engine.tick(PoseState::OffAxisRight, 1.0);
    assert!(events.iter().any(|event| matches!(event, SenseEvent::WarningLevelChanged { level: WarningLevel::Severe, direction: Some(direction) } if direction == "right")));

    assert!(has_warning(
        &engine.tick(PoseState::FacingScreen, 1.0),
        WarningLevel::Corrected
    ));
    assert!(!has_warning(
        &engine.tick(PoseState::FacingScreen, 1.0),
        WarningLevel::Normal
    ));
    assert!(has_warning(
        &engine.tick(PoseState::FacingScreen, 1.0),
        WarningLevel::Normal
    ));
}

#[test]
fn warning_does_not_escalate_below_threshold_and_no_face_starts_fresh_episode() {
    let mut engine = PostureTickEngine::new(None, Some(10.0), None, None);

    engine.tick(PoseState::OffAxisLeft, 1.0);
    for _ in 0..8 {
        assert!(!has_warning(
            &engine.tick(PoseState::OffAxisLeft, 1.0),
            WarningLevel::Severe
        ));
    }

    let events = engine.tick(PoseState::NoFace, 1.0);
    assert!(has_warning(&events, WarningLevel::Normal));
    let events = engine.tick(PoseState::OffAxisRight, 1.0);
    assert!(has_warning(&events, WarningLevel::Warning));
}

#[test]
fn head_up_does_not_advance_warning_escalation() {
    let mut engine = PostureTickEngine::new(None, Some(10.0), None, None);

    engine.tick(PoseState::OffAxisLeft, 1.0);
    for _ in 0..20 {
        assert!(engine.tick(PoseState::HeadUp, 1.0).is_empty());
    }
    for _ in 0..8 {
        assert!(!has_warning(
            &engine.tick(PoseState::OffAxisLeft, 1.0),
            WarningLevel::Severe
        ));
    }
    assert!(has_warning(
        &engine.tick(PoseState::OffAxisLeft, 1.0),
        WarningLevel::Severe
    ));
}

#[test]
fn snooze_freezes_all_accumulators_until_resume() {
    let mut engine = PostureTickEngine::new(Some(5.0), Some(10.0), Some(10.0), Some(10.0));
    for _ in 0..5 {
        engine.tick(PoseState::FacingScreen, 1.0);
    }
    for _ in 0..3 {
        engine.tick(PoseState::OffAxisLeft, 1.0);
    }

    engine.snooze();
    assert!(engine.is_snoozed());
    for _ in 0..20 {
        assert!(engine.tick(PoseState::OffAxisLeft, 1.0).is_empty());
    }

    engine.resume();
    assert!(!engine.is_snoozed());
    assert!(!has_correction(&engine.tick(PoseState::OffAxisLeft, 1.0)));
    let events = engine.tick(PoseState::OffAxisLeft, 1.0);
    assert!(has_correction(&events));
    assert!(has_eye_rest(&events));
}

#[test]
fn snooze_freezes_facing_presence_and_warning_escalation_independently() {
    let mut engine = PostureTickEngine::new(Some(5.0), Some(10.0), Some(10.0), Some(10.0));
    for _ in 0..5 {
        engine.tick(PoseState::FacingScreen, 1.0);
    }
    engine.tick(PoseState::OffAxisLeft, 1.0);

    engine.snooze();
    for _ in 0..20 {
        assert!(engine.tick(PoseState::FacingScreen, 1.0).is_empty());
    }
    engine.resume();

    for _ in 0..3 {
        let events = engine.tick(PoseState::FacingScreen, 1.0);
        assert!(!has_good_posture(&events));
        assert!(!has_eye_rest(&events));
    }
    let events = engine.tick(PoseState::FacingScreen, 1.0);
    assert!(has_eye_rest(&events));
    assert!(!has_good_posture(&events));
    let events = engine.tick(PoseState::FacingScreen, 1.0);
    assert!(has_good_posture(&events));

    let mut engine = PostureTickEngine::new(None, Some(10.0), None, None);
    engine.tick(PoseState::OffAxisLeft, 1.0);
    engine.snooze();
    for _ in 0..20 {
        assert!(engine.tick(PoseState::OffAxisLeft, 1.0).is_empty());
    }
    engine.resume();
    for _ in 0..8 {
        assert!(!has_warning(
            &engine.tick(PoseState::OffAxisLeft, 1.0),
            WarningLevel::Severe
        ));
    }
    assert!(has_warning(
        &engine.tick(PoseState::OffAxisLeft, 1.0),
        WarningLevel::Severe
    ));
}

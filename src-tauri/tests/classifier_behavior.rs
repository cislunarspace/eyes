use eyes_lib::domain::classifier::{classify, HeadPose, NeutralPose, PoseState, Thresholds};

#[test]
fn classifies_missing_pose_as_no_face() {
    assert_eq!(classify(None, None, None, None), PoseState::NoFace);
}

#[test]
fn classifies_yaw_relative_to_neutral_and_ignores_roll() {
    assert_eq!(
        classify(
            Some(HeadPose {
                yaw: 0.0,
                roll: 80.0
            }),
            None,
            None,
            None
        ),
        PoseState::FacingScreen,
    );
    assert_eq!(
        classify(
            Some(HeadPose {
                yaw: 1.0,
                roll: 0.0
            }),
            None,
            None,
            None
        ),
        PoseState::FacingScreen,
    );
    assert_eq!(
        classify(
            Some(HeadPose {
                yaw: -1.0,
                roll: 0.0
            }),
            None,
            None,
            None
        ),
        PoseState::FacingScreen,
    );
    assert_eq!(
        classify(
            Some(HeadPose {
                yaw: 10.0,
                roll: 80.0
            }),
            None,
            None,
            None
        ),
        PoseState::OffAxisRight,
    );
    assert_eq!(
        classify(
            Some(HeadPose {
                yaw: -10.0,
                roll: -80.0
            }),
            None,
            None,
            None
        ),
        PoseState::OffAxisLeft,
    );

    let neutral = NeutralPose {
        yaw: 10.0,
        roll: 5.0,
    };
    assert_eq!(
        classify(
            Some(HeadPose {
                yaw: 10.0,
                roll: 90.0
            }),
            Some(neutral),
            None,
            None
        ),
        PoseState::FacingScreen,
    );
    assert_eq!(
        classify(
            Some(HeadPose {
                yaw: 15.0,
                roll: 90.0
            }),
            Some(neutral),
            None,
            None
        ),
        PoseState::OffAxisRight,
    );
}

#[test]
fn custom_thresholds_change_yaw_boundaries_but_roll_stays_disabled() {
    let strict = Thresholds {
        yaw_deg: 0.5,
        roll_deg: 0.1,
        yaw_hysteresis_deg: 0.5,
    };
    assert_eq!(
        classify(
            Some(HeadPose {
                yaw: 1.0,
                roll: 0.0
            }),
            None,
            Some(strict),
            None
        ),
        PoseState::OffAxisRight,
    );
    assert_eq!(
        classify(
            Some(HeadPose {
                yaw: 0.3,
                roll: 0.0
            }),
            None,
            Some(strict),
            None
        ),
        PoseState::FacingScreen,
    );

    let lenient = Thresholds {
        yaw_deg: 30.0,
        roll_deg: 20.0,
        yaw_hysteresis_deg: 0.5,
    };
    assert_eq!(
        classify(
            Some(HeadPose {
                yaw: 25.0,
                roll: 0.0
            }),
            None,
            Some(lenient),
            None
        ),
        PoseState::FacingScreen,
    );
    assert_eq!(
        classify(
            Some(HeadPose {
                yaw: 0.0,
                roll: 90.0
            }),
            None,
            Some(lenient),
            None
        ),
        PoseState::FacingScreen,
    );
}

#[test]
fn keeps_off_axis_state_inside_hysteresis_zone_until_return_threshold() {
    let thresholds = Thresholds {
        yaw_deg: 1.0,
        roll_deg: 90.0,
        yaw_hysteresis_deg: 0.5,
    };

    assert_eq!(
        classify(
            Some(HeadPose {
                yaw: 0.7,
                roll: 0.0
            }),
            None,
            Some(thresholds),
            Some(PoseState::OffAxisRight),
        ),
        PoseState::OffAxisRight,
    );
    assert_eq!(
        classify(
            Some(HeadPose {
                yaw: 0.5,
                roll: 0.0
            }),
            None,
            Some(thresholds),
            Some(PoseState::OffAxisRight),
        ),
        PoseState::FacingScreen,
    );
    assert_eq!(
        classify(
            Some(HeadPose {
                yaw: -0.7,
                roll: 0.0
            }),
            None,
            Some(thresholds),
            Some(PoseState::OffAxisLeft),
        ),
        PoseState::OffAxisLeft,
    );
    assert_eq!(
        classify(
            Some(HeadPose {
                yaw: -0.5,
                roll: 0.0
            }),
            None,
            Some(thresholds),
            Some(PoseState::OffAxisLeft),
        ),
        PoseState::FacingScreen,
    );
}

#[test]
fn no_face_previous_state_has_no_hysteresis() {
    assert_eq!(
        classify(
            Some(HeadPose {
                yaw: 0.7,
                roll: 0.0
            }),
            None,
            None,
            Some(PoseState::NoFace),
        ),
        PoseState::FacingScreen,
    );
}

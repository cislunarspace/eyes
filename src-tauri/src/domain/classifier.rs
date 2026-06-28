#[derive(Debug, Clone, Copy, PartialEq)]
pub struct HeadPose {
    pub yaw: f64,
    pub pitch: f64,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct NeutralPose {
    pub yaw: f64,
    pub pitch: f64,
}

impl Default for NeutralPose {
    fn default() -> Self {
        Self {
            yaw: 0.0,
            pitch: 0.0,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Thresholds {
    pub yaw_deg: f64,
    pub yaw_hysteresis_deg: f64,
    pub pitch_deg: f64,
    pub pitch_hysteresis_deg: f64,
}

impl Default for Thresholds {
    fn default() -> Self {
        Self {
            yaw_deg: 1.0,
            yaw_hysteresis_deg: 0.5,
            pitch_deg: 5.0,
            pitch_hysteresis_deg: 2.5,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
pub enum PoseState {
    FacingScreen,
    OffAxisLeft,
    OffAxisRight,
    HeadUp,
    HeadDown,
    NoFace,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
pub struct PoseClassification {
    pub yaw_state: PoseState,
    pub pitch_state: PoseState,
}

impl Default for PoseClassification {
    fn default() -> Self {
        Self {
            yaw_state: PoseState::NoFace,
            pitch_state: PoseState::NoFace,
        }
    }
}

fn classify_axis(
    dev: f64,
    threshold: f64,
    hysteresis: f64,
    prev_state: PoseState,
    negative_state: PoseState,
    positive_state: PoseState,
) -> PoseState {
    let abs_dev = dev.abs();
    let was_off_axis = matches!(
        prev_state,
        PoseState::OffAxisLeft | PoseState::OffAxisRight | PoseState::HeadUp | PoseState::HeadDown
    );

    let outside = if was_off_axis {
        abs_dev > hysteresis
    } else {
        abs_dev > threshold
    };

    if !outside {
        return PoseState::FacingScreen;
    }

    if dev < 0.0 {
        negative_state
    } else {
        positive_state
    }
}

pub fn classify(
    pose: Option<HeadPose>,
    neutral: Option<NeutralPose>,
    thresholds: Option<Thresholds>,
    prev_classification: Option<PoseClassification>,
) -> PoseClassification {
    let Some(pose) = pose else {
        return PoseClassification {
            yaw_state: PoseState::NoFace,
            pitch_state: PoseState::NoFace,
        };
    };

    let neutral = neutral.unwrap_or_default();
    let thresholds = thresholds.unwrap_or_default();
    let prev = prev_classification.unwrap_or_default();

    let yaw_dev = pose.yaw - neutral.yaw;
    let pitch_dev = pose.pitch - neutral.pitch;

    let yaw_state = classify_axis(
        yaw_dev,
        thresholds.yaw_deg,
        thresholds.yaw_hysteresis_deg,
        prev.yaw_state,
        PoseState::OffAxisLeft,
        PoseState::OffAxisRight,
    );

    let pitch_state = classify_axis(
        pitch_dev,
        thresholds.pitch_deg,
        thresholds.pitch_hysteresis_deg,
        prev.pitch_state,
        PoseState::HeadDown,
        PoseState::HeadUp,
    );

    PoseClassification {
        yaw_state,
        pitch_state,
    }
}

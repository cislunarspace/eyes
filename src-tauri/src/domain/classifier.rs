#[derive(Debug, Clone, Copy, PartialEq)]
pub struct HeadPose {
    pub yaw: f64,
    pub roll: f64,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct NeutralPose {
    pub yaw: f64,
    pub roll: f64,
}

impl Default for NeutralPose {
    fn default() -> Self {
        Self { yaw: 0.0, roll: 0.0 }
    }
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Thresholds {
    pub yaw_deg: f64,
    pub roll_deg: f64,
    pub yaw_hysteresis_deg: f64,
}

impl Default for Thresholds {
    fn default() -> Self {
        Self {
            yaw_deg: 1.0,
            roll_deg: 90.0,
            yaw_hysteresis_deg: 0.5,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PoseState {
    FacingScreen,
    OffAxisLeft,
    OffAxisRight,
    OffAxisOther,
    NoFace,
}

pub fn classify(
    pose: Option<HeadPose>,
    neutral: Option<NeutralPose>,
    thresholds: Option<Thresholds>,
    prev_state: Option<PoseState>,
) -> PoseState {
    let Some(pose) = pose else {
        return PoseState::NoFace;
    };

    let neutral = neutral.unwrap_or_default();
    let thresholds = thresholds.unwrap_or_default();
    let previous = prev_state.unwrap_or(PoseState::NoFace);
    let yaw_dev = pose.yaw - neutral.yaw;
    let abs_yaw_dev = yaw_dev.abs();
    let was_off_axis = matches!(previous, PoseState::OffAxisLeft | PoseState::OffAxisRight);
    let yaw_outside = if was_off_axis {
        abs_yaw_dev > thresholds.yaw_hysteresis_deg
    } else {
        abs_yaw_dev > thresholds.yaw_deg
    };

    if !yaw_outside {
        return PoseState::FacingScreen;
    }

    if yaw_dev < 0.0 {
        PoseState::OffAxisLeft
    } else {
        PoseState::OffAxisRight
    }
}

use std::sync::Mutex;

use crate::domain::calibration::CalibrationSession;
use crate::domain::classifier::PoseState;
use crate::domain::config::AppConfig;
use crate::domain::posture_tick_engine::WarningLevel;
use crate::domain::snooze::SnoozeState;

#[derive(Debug, Clone, Copy, PartialEq, Eq, serde::Serialize)]
pub enum CameraState {
    Starting,
    Available,
    Unavailable,
}

#[derive(Debug, Clone)]
pub struct StatusSnapshot {
    pub pose_state: PoseState,
    pub yaw: Option<f64>,
    pub roll: Option<f64>,
    pub warning_level: WarningLevel,
    pub camera_state: CameraState,
    pub snooze_state: SnoozeState,
    pub calibration_active: bool,
}

#[derive(Debug)]
pub struct AppState {
    pub config: AppConfig,
    pub status: StatusSnapshot,
    pub calibration: CalibrationSession,
}

impl AppState {
    pub fn new(config: AppConfig) -> Self {
        Self {
            config,
            status: StatusSnapshot {
                pose_state: PoseState::NoFace,
                yaw: None,
                roll: None,
                warning_level: WarningLevel::Normal,
                camera_state: CameraState::Starting,
                snooze_state: SnoozeState::Inactive,
                calibration_active: false,
            },
            calibration: CalibrationSession::new(5.0),
        }
    }
}

pub type SharedAppState = Mutex<AppState>;

use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex, RwLock};

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
    pub pitch: Option<f64>,
    pub warning_level: WarningLevel,
    pub camera_state: CameraState,
    pub snooze_state: SnoozeState,
    pub calibration_active: bool,
}

#[derive(Debug)]
pub struct AppState {
    pub config: AppConfig,
    pub status: StatusSnapshot,
}

/// 跨线程共享的配置，worker 和 command 都可读写。
pub type SharedConfig = Arc<RwLock<AppConfig>>;

/// 跨线程共享的校准会话。
pub type SharedCalibration = Arc<Mutex<CalibrationSession>>;

/// 跨线程共享的 snooze 标志。
pub type SharedSnooze = Arc<AtomicBool>;

impl AppState {
    pub fn new(config: AppConfig) -> Self {
        Self {
            config,
            status: StatusSnapshot {
                pose_state: PoseState::NoFace,
                yaw: None,
                pitch: None,
                warning_level: WarningLevel::Normal,
                camera_state: CameraState::Starting,
                snooze_state: SnoozeState::Inactive,
                calibration_active: false,
            },
        }
    }
}

pub type SharedAppState = Mutex<AppState>;

pub mod worker_command;

use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Emitter, State};

use crate::app_shell::desktop::rebuild_tray;
use crate::app_state::{CameraState, SharedAppState, SharedCalibration, SharedConfig};
use crate::commands::worker_command::{WorkerCommand, WorkerSender};
use crate::domain::calibration::CalibrationSession;
use crate::domain::config::{AppConfig, ConfigStore};
use crate::domain::event_log::{AppEventKind, EventLog};
use crate::domain::snooze;
use crate::domain::posture_tick_engine::PostureTickEngine;
use crate::monitoring::camera_enumerator;
use crate::monitoring::preview::PreviewFrame;
use crate::monitoring::worker::{MonitoringWorker};
use crate::monitoring::worker_loop::{
    CameraFactory, DetectorFactory, EventSink, MonitorFactory, WorkerOrchestrator,
};

// ── Tauri EventSink ──────────────────────────────────────────────

struct TauriEventSink {
    app: AppHandle,
    event_log: Arc<EventLog>,
}

impl EventSink for TauriEventSink {
    fn emit_camera_state_changed(&self, state: &str) {
        let _ = self.app.emit(
            "camera-state-changed",
            serde_json::json!({ "state": state }),
        );
    }

    fn emit_pose_updated(&self, yaw: Option<f64>, pitch: Option<f64>, pose_state: &str) {
        let _ = self.app.emit(
            "pose-updated",
            serde_json::json!({
                "pose_state": pose_state,
                "yaw": yaw,
                "pitch": pitch,
            }),
        );
    }

    fn emit_preview_frame(&self, preview: &PreviewFrame) {
        let _ = self.app.emit(
            "preview-frame",
            serde_json::json!({
                "image_data_url": preview.image_data_url,
                "width": preview.width,
                "height": preview.height,
            }),
        );
    }

    fn emit_sound_alert(&self, alert_type: &str) {
        let _ = self.app.emit("play-sound-alert", alert_type);
    }

    fn emit_warning_level_changed(&self, level: &str, direction: Option<&str>) {
        let _ = self.app.emit(
            "warning-level-changed",
            serde_json::json!({ "level": level, "direction": direction }),
        );
    }

    fn show_dialog(&self, title: &str, body: &str) {
        // 简化实现：通过 Tauri 对话框 API 显示消息
        // TODO: 使用 tauri-plugin-dialog 或自定义窗口实现
        let _ = (title, body);
    }

    fn log_event(&self, kind: AppEventKind, data: serde_json::Value) {
        let _ = self.event_log.append(kind, data);
    }

    fn log_info(&self, message: &str) {
        // 使用 eprintln 避免依赖 log crate
        eprintln!("[eyes] {}", message);
    }
}

// ── Worker 状态 ──────────────────────────────────────────────────

pub struct WorkerState {
    pub command_tx: Mutex<Option<WorkerSender>>,
    pub config_store: ConfigStore,
    pub monitoring_active: Arc<Mutex<bool>>,
    pub snooze_until: Arc<Mutex<Option<std::time::Instant>>>,
}

// ── Tauri 命令 ───────────────────────────────────────────────────

#[tauri::command]
pub fn get_status(state: State<'_, SharedAppState>) -> Result<serde_json::Value, String> {
    let app = state.lock().map_err(|e| e.to_string())?;
    Ok(serde_json::json!({
        "pose_state": app.status.pose_state,
        "yaw": app.status.yaw,
        "pitch": app.status.pitch,
        "warning_level": app.status.warning_level,
        "camera_state": app.status.camera_state,
        "snooze_state": app.status.snooze_state,
        "calibration_active": app.status.calibration_active,
    }))
}

#[tauri::command]
pub fn get_config(state: State<'_, SharedAppState>) -> Result<AppConfig, String> {
    let app = state.lock().map_err(|e| e.to_string())?;
    Ok(app.config.clone())
}

#[tauri::command]
pub fn set_config(
    new_config: AppConfig,
    app_state: State<'_, SharedAppState>,
    shared_config: State<'_, SharedConfig>,
    worker_tx: State<'_, Mutex<WorkerSender>>,
    app_handle: AppHandle,
) -> Result<(), String> {
    // 写入磁盘
    let store = ConfigStore::new(dirs::config_dir().unwrap_or_default());
    store.save(&new_config).map_err(|e| e.to_string())?;

    // 更新本地状态
    {
        let mut app = app_state.lock().map_err(|e| e.to_string())?;
        app.config = new_config.clone();
    }

    // 更新共享配置
    {
        let mut cfg = shared_config.write().map_err(|e| e.to_string())?;
        *cfg = new_config.clone();
    }

    // 通知 worker 更新配置
    if let Ok(tx) = worker_tx.lock() {
        let _ = tx.send(WorkerCommand::SetConfig(Box::new(new_config.clone())));
    }

    // 通知前端
    let _ = app_handle.emit("config-changed", ());
    rebuild_tray(&app_handle, &new_config.language);

    Ok(())
}

// ── 摄像头 ──────────────────────────────────────────────────────

#[tauri::command]
pub fn list_cameras() -> Result<Vec<camera_enumerator::CameraDevice>, String> {
    camera_enumerator::list_cameras()
}

#[tauri::command]
pub fn set_camera_index(
    index: u32,
    state: State<'_, SharedAppState>,
    shared_config: State<'_, SharedConfig>,
    worker_tx: State<'_, Mutex<WorkerSender>>,
) -> Result<(), String> {
    {
        let mut app = state.lock().map_err(|e| e.to_string())?;
        app.config.camera_index = index;
        app.status.camera_state = CameraState::Starting;
    }
    if let Ok(mut cfg) = shared_config.write() {
        cfg.camera_index = index;
    }
    let tx = worker_tx.lock().map_err(|e| e.to_string())?;
    tx.send(WorkerCommand::SetCameraIndex(index))?;
    Ok(())
}

// ── 暂停/恢复 ───────────────────────────────────────────────────

#[tauri::command]
pub fn snooze(
    minutes: u32,
    state: State<'_, SharedAppState>,
    worker_tx: State<'_, Mutex<WorkerSender>>,
) -> Result<(), String> {
    {
        let mut app = state.lock().map_err(|e| e.to_string())?;
        app.status.snooze_state = if minutes == 0 {
            snooze::SnoozeState::Indefinite
        } else {
            let until =
                time::OffsetDateTime::now_utc() + time::Duration::minutes(minutes as i64);
            let until_iso = until
                .format(&time::format_description::well_known::Iso8601::DEFAULT)
                .unwrap_or_default();
            snooze::SnoozeState::Active {
                until_iso: until_iso.clone(),
            }
        };
    }
    let seconds = if minutes == 0 {
        f64::INFINITY
    } else {
        (minutes as f64) * 60.0
    };
    let tx = worker_tx.lock().map_err(|e| e.to_string())?;
    tx.send(WorkerCommand::Snooze(seconds))?;
    Ok(())
}

#[tauri::command]
pub fn resume(
    state: State<'_, SharedAppState>,
    worker_tx: State<'_, Mutex<WorkerSender>>,
) -> Result<(), String> {
    {
        let mut app = state.lock().map_err(|e| e.to_string())?;
        app.status.snooze_state = snooze::SnoozeState::Inactive;
    }
    let tx = worker_tx.lock().map_err(|e| e.to_string())?;
    tx.send(WorkerCommand::Resume)?;
    Ok(())
}

// ── 校准 ────────────────────────────────────────────────────────

#[tauri::command]
pub fn start_calibration(
    calibration: State<'_, SharedCalibration>,
    state: State<'_, SharedAppState>,
) -> Result<(), String> {
    let mut session = calibration.lock().map_err(|e| e.to_string())?;
    session.start();
    drop(session);
    let mut app = state.lock().map_err(|e| e.to_string())?;
    app.status.calibration_active = true;
    Ok(())
}

#[tauri::command]
pub fn feed_calibration(
    yaw: f64,
    pitch: f64,
    calibration: State<'_, SharedCalibration>,
    state: State<'_, SharedAppState>,
) -> Result<(), String> {
    let mut session = calibration.lock().map_err(|e| e.to_string())?;
    if !session.is_active() {
        return Ok(());
    }
    session.feed(yaw, pitch);
    session.tick(0.1);
    let is_active = session.is_active();
    let result = session.result();
    drop(session);

    if !is_active {
        let mut app = state.lock().map_err(|e| e.to_string())?;
        app.status.calibration_active = false;
        if let Some(res) = result {
            if res.sample_count > 0 {
                app.config.neutral_yaw = res.yaw;
                app.config.neutral_pitch = res.pitch;
            }
        }
    }
    Ok(())
}

#[tauri::command]
pub fn cancel_calibration(
    calibration: State<'_, SharedCalibration>,
    state: State<'_, SharedAppState>,
) -> Result<(), String> {
    let mut session = calibration.lock().map_err(|e| e.to_string())?;
    *session = CalibrationSession::new(5.0);
    drop(session);
    let mut app = state.lock().map_err(|e| e.to_string())?;
    app.status.calibration_active = false;
    Ok(())
}

// ── 后台 worker ─────────────────────────────────────────────────

/// 启动后台监控 worker。返回 `WorkerSender`，前端命令通过它向 worker 发指令。
pub fn spawn_worker(
    app_handle: AppHandle,
    shared_config: SharedConfig,
    shared_calibration: SharedCalibration,
    shared_state: SharedAppState,
) -> WorkerSender {
    let (tx, rx) = worker_command::channel();

    let config = shared_config
        .read()
        .map(|c| c.clone())
        .unwrap_or_default();

    let config_dir = dirs::config_dir().unwrap_or_default();
    let event_log = Arc::new(EventLog::new(config_dir.clone()));

    // 相机工厂（feature-gated）
    let camera_factory: CameraFactory = Box::new(move |camera_index: u32| {
        #[cfg(feature = "opencv-camera")]
        {
            use crate::monitoring::opencv_camera::OpenCvCamera;
            let cam = OpenCvCamera::open(camera_index as i32)?;
            Ok(Box::new(cam))
        }

        #[cfg(not(feature = "opencv-camera"))]
        {
            let _ = camera_index;
            Err("No camera backend available".into())
        }
    });

    // 检测器工厂
    let detector_factory: DetectorFactory = {
        let app_handle = app_handle.clone();
        Box::new(move || load_detector(&app_handle))
    };

    // 监控器工厂
    let monitor_factory: MonitorFactory = Box::new(|camera, detector| {
        let engine = PostureTickEngine::default();
        Box::new(MonitoringWorker::new(camera, detector, engine))
    });

    let orchestrator = WorkerOrchestrator::new(
        config,
        shared_state,
        shared_calibration,
        Box::new(TauriEventSink { app: app_handle, event_log: event_log.clone() }),
        camera_factory,
        detector_factory,
        monitor_factory,
        event_log,
    );

    std::thread::spawn(move || {
        orchestrator.run(rx);
    });

    tx
}

// ── 检测器加载（feature-gated） ──────────────────────────────────

#[cfg(all(feature = "opencv-camera", feature = "onnx-detector"))]
fn load_detector(app_handle: &AppHandle) -> Option<Box<dyn crate::monitoring::detector::Detector>> {
    let resource_dir = app_handle.path().resource_dir().ok()?;
    let model_path = resource_dir.join("face_detection_yunet_2023mar.onnx");
    if !model_path.exists() {
        return None;
    }
    let path_str = model_path.to_string_lossy().to_string();
    match crate::monitoring::onnx_detector::YuNetDetector::new(&path_str) {
        Ok(det) => Some(Box::new(det)),
        Err(_) => None,
    }
}

#[cfg(all(feature = "opencv-camera", not(feature = "onnx-detector")))]
fn load_detector(_app_handle: &AppHandle) -> Option<Box<dyn crate::monitoring::detector::Detector>> {
    None
}

#[cfg(not(feature = "opencv-camera"))]
fn load_detector(_app_handle: &AppHandle) -> Option<Box<dyn crate::monitoring::detector::Detector>> {
    None
}

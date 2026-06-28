pub mod worker_command;

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Emitter, State};

use crate::app_shell::desktop::rebuild_tray;
use crate::app_state::{CameraState, SharedAppState, SharedCalibration, SharedConfig};
use crate::commands::worker_command::{WorkerCommand, WorkerSender};
use crate::domain::calibration::CalibrationSession;
use crate::domain::config::{AppConfig, ConfigStore};
use crate::domain::snooze;
#[cfg(feature = "opencv-camera")]
use crate::domain::event_log::{AppEventKind, EventLog};
#[cfg(feature = "opencv-camera")]
use crate::domain::posture_tick_engine::SenseEvent;
#[cfg(feature = "opencv-camera")]
use crate::monitoring::worker::WorkerOutput;

/// 从 Tauri 资源目录加载 ONNX 检测器。
///
/// 模型文件通过 `bundle.resources` 打包在资源目录中。
#[cfg(all(feature = "opencv-camera", feature = "onnx-detector"))]
fn load_detector(app_handle: &AppHandle) -> Option<Box<dyn crate::monitoring::detector::Detector>> {
    use tauri::Manager;
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

// ── 查询命令 ─────────────────────────────────────────────────────

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

// ── 配置写入 ─────────────────────────────────────────────────────

/// 前端保存设置时调用，写入 YAML 并同步到共享配置和运行中的 worker。
#[tauri::command]
pub fn set_config(
    new_config: AppConfig,
    app_state: State<'_, SharedAppState>,
    shared_config: State<'_, SharedConfig>,
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

    // 更新共享配置（worker 下次 tick 自动读取）
    {
        let mut cfg = shared_config.write().map_err(|e| e.to_string())?;
        *cfg = new_config.clone();
    }

    // 通知前端配置已更新
    let _ = app_handle.emit("config-changed", ());

    // 语言变更时重建托盘菜单
    rebuild_tray(&app_handle, &new_config.language);

    Ok(())
}

// ── 摄像头 ──────────────────────────────────────────────────────

/// 切换摄像头索引（不持久化，仅影响当前运行）。
/// 前端保存设置时应使用 `set_config` 整体写入。
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
    // 通知 worker 立即切换摄像头
    let tx = worker_tx.lock().map_err(|e| e.to_string())?;
    tx.send(WorkerCommand::SetCameraIndex(index))?;
    Ok(())
}

// ── 暂停/恢复 ───────────────────────────────────────────────────

/// 暂停提醒（30 分钟 / 1 小时 / 不限时）。
/// `minutes` = 0 表示不限时。
#[tauri::command]
pub fn snooze(
    minutes: u32,
    state: State<'_, SharedAppState>,
    worker_tx: State<'_, Mutex<WorkerSender>>,
) -> Result<(), String> {
    // 更新本地状态快照（前端 get_status 立即可读）
    {
        let mut app = state.lock().map_err(|e| e.to_string())?;
        app.status.snooze_state = if minutes == 0 {
            snooze::SnoozeState::Indefinite
        } else {
            let until = time::OffsetDateTime::now_utc()
                + time::Duration::minutes(minutes as i64);
            let until_iso = until
                .format(&time::format_description::well_known::Iso8601::DEFAULT)
                .unwrap_or_default();
            snooze::SnoozeState::Active {
                until_iso: until_iso.clone(),
            }
        };
    }
    // 通过 channel 通知 worker 暂停提醒
    let seconds = if minutes == 0 {
        f64::INFINITY
    } else {
        (minutes as f64) * 60.0
    };
    let tx = worker_tx.lock().map_err(|e| e.to_string())?;
    tx.send(WorkerCommand::Snooze(seconds))?;
    Ok(())
}

/// 恢复提醒。
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

/// 开始校准（5 秒采样）。
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

/// 喂入姿态样本（由前端在 pose-updated 事件回调中调用）。
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

    // 校准完成
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

/// 取消校准。
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

/// 后台工作线程，约 10 Hz 驱动 tick，向前端发送事件。
/// setup 时调用一次，运行在独立线程上。
/// 返回 `WorkerSender`，前端命令通过它向 worker 发送控制指令。
#[allow(unused_variables)]
pub fn spawn_worker(
    app_handle: AppHandle,
    shared_config: SharedConfig,
    shared_calibration: SharedCalibration,
    shared_state: SharedAppState,
) -> WorkerSender {
    use std::time::Duration;

    let (worker_tx, worker_rx) = worker_command::channel();
    let running = Arc::new(AtomicBool::new(true));
    let running_clone = running.clone();

    std::thread::spawn(move || {
        #[cfg(feature = "opencv-camera")]
        {
            use crate::monitoring::opencv_camera::OpenCvCamera;
            use crate::domain::posture_tick_engine::PostureTickEngine;
            use crate::monitoring::worker::MonitoringWorker;

            // 事件日志
            let config_dir =
                crate::domain::config::ConfigStore::new(dirs::config_dir().unwrap_or_default());
            let event_log = EventLog::new(config_dir.config_dir().to_path_buf());

            let mut retry_at: Option<std::time::Instant> = None;
            let mut camera_index = shared_config
                .read()
                .map(|c| c.camera_index)
                .unwrap_or(0);
            let mut snooze_remaining: f64 = 0.0;

            let mut worker: Option<MonitoringWorker<OpenCvCamera>> =
                match OpenCvCamera::open(camera_index) {
                    Ok(cam) => {
                        if let Ok(mut s) = shared_state.lock() {
                            s.status.camera_state = CameraState::Available;
                        }
                        let engine = PostureTickEngine::default();
                        let detector = load_detector(&app_handle);
                        Some(MonitoringWorker::new(cam, detector, engine))
                    }
                    Err(_) => {
                        if let Ok(mut s) = shared_state.lock() {
                            s.status.camera_state = CameraState::Unavailable;
                        }
                        retry_at = Some(std::time::Instant::now() + Duration::from_secs(5));
                        None
                    }
                };

            while running_clone.load(Ordering::Relaxed) {
                let tick_start = std::time::Instant::now();

                // 处理前端命令
                while let Ok(cmd) = worker_rx.try_recv() {
                    match cmd {
                        WorkerCommand::SetCameraIndex(idx) => {
                            camera_index = idx;
                            worker = None;
                            retry_at = Some(tick_start);
                        }
                        WorkerCommand::Snooze(seconds) => {
                            snooze_remaining = seconds;
                            if let Some(ref mut w) = worker {
                                w.set_snoozed(true);
                            }
                        }
                        WorkerCommand::Resume => {
                            snooze_remaining = 0.0;
                            if let Some(ref mut w) = worker {
                                w.set_snoozed(false);
                            }
                            if let Ok(mut s) = shared_state.lock() {
                                s.status.snooze_state = snooze::SnoozeState::Inactive;
                            }
                        }
                    }
                }

                // snooze 倒计时
                if snooze_remaining > 0.0 && snooze_remaining < f64::INFINITY {
                    snooze_remaining -= 0.1;
                    if snooze_remaining <= 0.0 {
                        snooze_remaining = 0.0;
                        if let Some(ref mut w) = worker {
                            w.set_snoozed(false);
                        }
                        if let Ok(mut s) = shared_state.lock() {
                            s.status.snooze_state = snooze::SnoozeState::Inactive;
                        }
                    }
                }

                // 重试摄像头
                if worker.is_none() && retry_at.is_some_and(|due| tick_start >= due) {
                    match OpenCvCamera::open(camera_index) {
                        Ok(cam) => {
                            if let Ok(mut s) = shared_state.lock() {
                                s.status.camera_state = CameraState::Available;
                            }
                            let engine = PostureTickEngine::default();
                            let detector = load_detector(&app_handle);
                            let mut w = MonitoringWorker::new(cam, detector, engine);
                            w.set_snoozed(snooze_remaining > 0.0);
                            worker = Some(w);
                        }
                        Err(_) => {
                            retry_at = Some(tick_start + Duration::from_secs(5));
                        }
                    }
                }

                if let Some(ref mut w) = worker {
                    let output = w.tick(0.1);

                    // 校准中：喂样本
                    if let Ok(mut session) = shared_calibration.try_lock() {
                        if session.is_active() {
                            if let (Some(y), Some(p)) = (output.yaw, output.pitch) {
                                session.feed(y, p);
                            }
                            session.tick(0.1);
                        }
                    }

                    // StatusSnapshot 回写
                    if let Ok(mut s) = shared_state.lock() {
                        s.status.pose_state = output.pose_state;
                        s.status.yaw = output.yaw;
                        s.status.pitch = output.pitch;
                        s.status.warning_level = output.warning_level;
                        if !output.camera_ok {
                            s.status.camera_state = CameraState::Unavailable;
                        }
                    }

                    handle_tick_output(&app_handle, &event_log, &output);
                    if !output.camera_ok {
                        worker = None;
                        retry_at = Some(tick_start + Duration::from_secs(5));
                    }
                }

                let elapsed = tick_start.elapsed();
                let window = Duration::from_millis(100);
                if elapsed < window {
                    std::thread::sleep(window - elapsed);
                }
            }
        }

        #[cfg(not(feature = "opencv-camera"))]
        {
            // 无摄像头时仅维持心跳
            while running_clone.load(Ordering::Relaxed) {
                std::thread::sleep(Duration::from_millis(100));
            }
        }
    });

    std::mem::forget(running);
    worker_tx
}

/// 将单次 tick 输出转化为 Tauri 事件和 JSONL 日志。
#[cfg(feature = "opencv-camera")]
fn handle_tick_output(app: &AppHandle, log: &EventLog, output: &WorkerOutput) {
    // 预览帧
    if let Some(ref preview) = output.preview {
        let _ = app.emit("preview-frame", serde_json::json!({
            "image_data_url": preview.image_data_url,
            "width": preview.width,
            "height": preview.height,
        }));
    }

    // 摄像头状态
    if !output.camera_ok {
        let _ = app.emit("camera-state-changed", serde_json::json!({ "state": "unavailable" }));
        let _ = log.append(AppEventKind::CameraUnavailable, serde_json::json!({}));
        return;
    }

    // 姿态更新
    let _ = app.emit("pose-updated", serde_json::json!({
        "pose_state": output.pose_state,
        "yaw": output.yaw,
        "pitch": output.pitch,
    }));

    // SenseEvent → Tauri 事件 + JSONL
    for event in &output.sense_events {
        emit_sense_event(app, log, event);
    }
}

/// 将单个 SenseEvent 转化为前端事件和日志。
#[cfg(feature = "opencv-camera")]
fn emit_sense_event(app: &AppHandle, log: &EventLog, event: &SenseEvent) {
    match event {
        SenseEvent::Correction { direction } => {
            let dir = match *direction {
                crate::domain::classifier::PoseState::OffAxisLeft => "left",
                crate::domain::classifier::PoseState::OffAxisRight => "right",
                crate::domain::classifier::PoseState::HeadUp => "up",
                crate::domain::classifier::PoseState::HeadDown => "down",
                _ => "unknown",
            };
            let _ = app.emit("correction", serde_json::json!({ "direction": dir }));
            let _ = log.append(AppEventKind::PromptFired, serde_json::json!({
                "prompt": "correction",
                "direction": dir,
            }));
        }
        SenseEvent::GoodPosture => {
            let _ = app.emit("good-posture", serde_json::json!({}));
            let _ = log.append(AppEventKind::PromptFired, serde_json::json!({
                "prompt": "good_posture",
            }));
        }
        SenseEvent::EyeRest => {
            let _ = app.emit("eye-rest", serde_json::json!({}));
            let _ = log.append(AppEventKind::PromptFired, serde_json::json!({
                "prompt": "eye_rest",
            }));
        }
        SenseEvent::WarningLevelChanged { level, direction } => {
            let _ = app.emit("warning-level-changed", serde_json::json!({
                "level": level,
                "direction": direction,
            }));
            let _ = log.append(AppEventKind::WarningLevelChanged, serde_json::json!({
                "level": format!("{:?}", level),
                "direction": direction,
            }));
        }
    }
}

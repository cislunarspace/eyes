use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use tauri::{AppHandle, Emitter, State};

use crate::app_state::{CameraState, SharedAppState};
use crate::domain::config::AppConfig;
use crate::domain::event_log::{AppEventKind, EventLog};
use crate::domain::posture_tick_engine::{PostureTickEngine, SenseEvent};
use crate::domain::snooze;
#[allow(unused_imports)]
use crate::monitoring::worker::{MonitoringWorker, WorkerOutput};

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
pub fn set_camera_index(index: u32, state: State<'_, SharedAppState>) -> Result<(), String> {
    let mut app = state.lock().map_err(|e| e.to_string())?;
    app.config.camera_index = index;
    app.status.camera_state = CameraState::Starting;
    Ok(())
}

/// 暂停提醒（30 分钟 / 1 小时 / 不限时）。
/// `minutes` = 0 表示不限时。
#[tauri::command]
pub fn snooze(minutes: u32, state: State<'_, SharedAppState>) -> Result<(), String> {
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
    Ok(())
}

/// 恢复提醒。
#[tauri::command]
pub fn resume(state: State<'_, SharedAppState>) -> Result<(), String> {
    let mut app = state.lock().map_err(|e| e.to_string())?;
    app.status.snooze_state = snooze::SnoozeState::Inactive;
    Ok(())
}

/// 后台工作线程，约 10 Hz 驱动 tick，向前端发送事件。
/// setup 时调用一次，运行在独立线程上。
pub fn spawn_worker(app_handle: AppHandle) {
    use std::time::Duration;

    let running = Arc::new(AtomicBool::new(true));
    let running_clone = running.clone();
    let snoozed = Arc::new(AtomicBool::new(false));

    // 事件日志
    let config_dir = crate::domain::config::ConfigStore::new(
        dirs::config_dir().unwrap_or_default(),
    );
    let event_log = EventLog::new(config_dir.config_dir().to_path_buf());

    std::thread::spawn(move || {
        #[cfg(feature = "opencv-camera")]
        {
            use crate::monitoring::opencv_camera::OpenCvCamera;
            let mut retry_at: Option<std::time::Instant> = None;

            let mut worker: Option<MonitoringWorker<OpenCvCamera>> =
                match OpenCvCamera::open(0) {
                    Ok(cam) => {
                        let _ = app_handle.emit("camera-state-changed",
                            serde_json::json!({ "state": "available" }));
                        let engine = PostureTickEngine::default();
                        Some(MonitoringWorker::new(cam, None, engine, snoozed.clone()))
                    }
                    Err(_) => {
                        let _ = app_handle.emit("camera-state-changed",
                            serde_json::json!({ "state": "unavailable" }));
                        retry_at = Some(std::time::Instant::now() + Duration::from_secs(5));
                        None
                    }
                };

            while running_clone.load(Ordering::Relaxed) {
                let tick_start = std::time::Instant::now();

                // 重试摄像头
                if worker.is_none() && retry_at.is_some_and(|due| tick_start >= due) {
                    match OpenCvCamera::open(0) {
                        Ok(cam) => {
                            let _ = app_handle.emit("camera-state-changed",
                                serde_json::json!({ "state": "available" }));
                            let engine = PostureTickEngine::default();
                            worker = Some(MonitoringWorker::new(
                                cam, None, engine, snoozed.clone(),
                            ));
                        }
                        Err(_) => {
                            retry_at = Some(tick_start + Duration::from_secs(5));
                        }
                    }
                }

                if let Some(ref mut w) = worker {
                    let output = w.tick(0.1);
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
}

/// 将单次 tick 输出转化为 Tauri 事件和 JSONL 日志。
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
        let _ = app.emit("camera-state-changed",
            serde_json::json!({ "state": "unavailable" }));
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
fn emit_sense_event(app: &AppHandle, log: &EventLog, event: &SenseEvent) {
    match event {
        SenseEvent::Correction { direction } => {
            let dir = if *direction == crate::domain::classifier::PoseState::OffAxisLeft {
                "left"
            } else {
                "right"
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

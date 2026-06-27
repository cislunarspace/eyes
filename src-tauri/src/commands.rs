use std::sync::Arc;
use tauri::{AppHandle, State};

use crate::app_state::{CameraState, SharedAppState};
use crate::domain::config::AppConfig;

#[tauri::command]
pub fn get_status(state: State<'_, SharedAppState>) -> Result<serde_json::Value, String> {
    let app = state.lock().map_err(|e| e.to_string())?;
    Ok(serde_json::json!({
        "pose_state": app.status.pose_state,
        "yaw": app.status.yaw,
        "roll": app.status.roll,
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

/// 后台工作线程，约 10 Hz 驱动 tick，向前端发送事件。
/// setup 时调用一次，运行在独立线程上。
#[allow(unused_variables)]
pub fn spawn_worker(app_handle: AppHandle) {
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::time::Duration;

    #[cfg(feature = "opencv-camera")]
    use crate::app_shell::events::emit_worker_event;
    #[cfg(feature = "opencv-camera")]
    use crate::monitoring::opencv_camera::OpenCvCamera;

    let running = Arc::new(AtomicBool::new(true));
    let running_clone = running.clone();

    std::thread::spawn(move || {
        #[cfg(feature = "opencv-camera")]
        let mut retry_at: Option<std::time::Instant> = None;

        #[cfg(feature = "opencv-camera")]
        let mut worker: Option<MonitoringWorker<OpenCvCamera>> = match OpenCvCamera::open(0) {
            Ok(cam) => {
                let _ = app_handle.emit(
                    "camera-state-changed",
                    serde_json::json!({
                        "state": "available"
                    }),
                );
                Some(MonitoringWorker::new(cam))
            }
            Err(_) => {
                let _ = app_handle.emit(
                    "camera-state-changed",
                    serde_json::json!({
                        "state": "unavailable"
                    }),
                );
                retry_at = Some(std::time::Instant::now() + Duration::from_secs(5));
                None
            }
        };

        while running_clone.load(Ordering::Relaxed) {
            let tick_start = std::time::Instant::now();

            #[cfg(feature = "opencv-camera")]
            {
                // ponytail: 5 秒摄像头重试 — 丢失或未打开时重新尝试
                if worker.is_none() && retry_at.is_some_and(|due| tick_start >= due) {
                    match OpenCvCamera::open(0) {
                        Ok(cam) => {
                            let _ = app_handle.emit(
                                "camera-state-changed",
                                serde_json::json!({
                                    "state": "available"
                                }),
                            );
                            worker = Some(MonitoringWorker::new(cam));
                        }
                        Err(_) => {
                            retry_at = Some(tick_start + Duration::from_secs(5));
                        }
                    }
                }

                if let Some(ref mut w) = worker {
                    let events = w.tick();
                    let mut disconnected = false;
                    for event in &events {
                        match event {
                            crate::monitoring::worker::WorkerEvent::CameraUnavailable => {
                                let _ = app_handle.emit(
                                    "camera-state-changed",
                                    serde_json::json!({ "state": "unavailable" }),
                                );
                                disconnected = true;
                            }
                            _ => {
                                emit_worker_event(&app_handle, event.clone());
                            }
                        }
                    }
                    if disconnected {
                        worker = None;
                        retry_at = Some(tick_start + Duration::from_secs(5));
                    }
                }
            }

            // 补足 100ms tick 窗口的剩余时间
            let elapsed = tick_start.elapsed();
            let window = Duration::from_millis(100);
            if elapsed < window {
                std::thread::sleep(window - elapsed);
            }
        }
    });

    // ponytail: 泄漏 Arc 实现简单关闭 — 需要清理时再加 Drop 实现
    std::mem::forget(running);
}

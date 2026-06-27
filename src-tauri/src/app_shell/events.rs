use serde::Serialize;
use tauri::{AppHandle, Emitter, Runtime};

use crate::monitoring::worker::WorkerEvent;

#[derive(Debug, Clone, Serialize)]
struct PreviewFramePayload {
    image_data_url: String,
    width: u32,
    height: u32,
}

#[derive(Debug, Clone, Serialize)]
struct CameraStatePayload {
    state: &'static str,
}

pub fn emit_worker_event<R: Runtime>(app: &AppHandle<R>, event: WorkerEvent) {
    match event {
        WorkerEvent::PreviewFrame(preview) => {
            let _ = app.emit(
                "preview-frame",
                PreviewFramePayload {
                    image_data_url: preview.image_data_url,
                    width: preview.width,
                    height: preview.height,
                },
            );
        }
        WorkerEvent::CameraUnavailable => {
            let _ = app.emit(
                "camera-state-changed",
                CameraStatePayload {
                    state: "unavailable",
                },
            );
        }
        WorkerEvent::PreviewUnavailable => {
            // preview encoding failed — still have camera, just can't show frame
            // no UI event needed for this internal state
        }
    }
}

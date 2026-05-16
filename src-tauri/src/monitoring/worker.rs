use super::preview::{encode_preview, Frame, PreviewFrame};

pub trait FrameSource {
    fn read_frame(&mut self) -> Result<Option<Frame>, String>;
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WorkerEvent {
    PreviewFrame(PreviewFrame),
    CameraUnavailable,
    PreviewUnavailable,
}

pub struct MonitoringWorker<C> {
    camera: C,
}

impl<C: FrameSource> MonitoringWorker<C> {
    pub fn new(camera: C) -> Self {
        Self { camera }
    }

    pub fn tick(&mut self) -> Vec<WorkerEvent> {
        match self.camera.read_frame() {
            Ok(Some(frame)) => match encode_preview(&frame) {
                Ok(preview) => vec![WorkerEvent::PreviewFrame(preview)],
                Err(_) => vec![WorkerEvent::PreviewUnavailable],
            },
            Ok(None) | Err(_) => vec![WorkerEvent::CameraUnavailable],
        }
    }
}

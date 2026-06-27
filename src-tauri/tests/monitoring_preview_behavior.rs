use eyes_lib::monitoring::{
    preview::Frame,
    worker::{FrameSource, MonitoringWorker, WorkerEvent},
};

#[derive(Debug)]
struct FakeCamera {
    frames: Vec<Frame>,
}

impl FrameSource for FakeCamera {
    fn read_frame(&mut self) -> Result<Option<Frame>, String> {
        Ok(self.frames.pop())
    }
}

#[test]
fn worker_tick_emits_preview_frame_from_camera_source() {
    let frame = Frame::rgb(2, 1, vec![255, 0, 0, 0, 255, 0]).unwrap();
    let mut worker = MonitoringWorker::new(FakeCamera {
        frames: vec![frame],
    });

    let events = worker.tick();

    assert_eq!(events.len(), 1);
    let WorkerEvent::PreviewFrame(preview) = &events[0] else {
        panic!("expected preview frame event");
    };
    assert_eq!(preview.width, 2);
    assert_eq!(preview.height, 1);
    assert!(preview.image_data_url.starts_with("data:image/png;base64,"));
}

#[test]
fn frame_constructor_rejects_invalid_dimensions_and_lengths() {
    assert!(Frame::rgb(0, 1, Vec::new()).is_err());
    assert!(Frame::rgb(1, 1, Vec::new()).is_err());
}

#[test]
fn worker_tick_reports_camera_unavailable_without_crashing() {
    struct UnavailableCamera;
    impl FrameSource for UnavailableCamera {
        fn read_frame(&mut self) -> Result<Option<Frame>, String> {
            Ok(None)
        }
    }

    let mut worker = MonitoringWorker::new(UnavailableCamera);

    assert_eq!(worker.tick(), vec![WorkerEvent::CameraUnavailable]);
}

#[test]
fn worker_reports_camera_unavailable_when_read_fails_after_success() {
    struct FailingAfterOne {
        remaining: usize,
    }

    impl FrameSource for FailingAfterOne {
        fn read_frame(&mut self) -> Result<Option<Frame>, String> {
            if self.remaining > 0 {
                self.remaining -= 1;
                Ok(Some(Frame::rgb(1, 1, vec![0, 0, 0]).unwrap()))
            } else {
                Err("disconnected".to_string())
            }
        }
    }

    let mut worker = MonitoringWorker::new(FailingAfterOne { remaining: 1 });

    let events = worker.tick();
    assert!(matches!(events[0], WorkerEvent::PreviewFrame(_)));

    let events = worker.tick();
    assert_eq!(events, vec![WorkerEvent::CameraUnavailable]);
}

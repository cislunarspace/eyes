use eyes_lib::monitoring::{
    preview::Frame,
    worker::{FrameSource, MonitoringWorker},
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
fn worker_tick_returns_preview_frame_from_camera_source() {
    let frame = Frame::rgb(2, 1, vec![255, 0, 0, 0, 255, 0]).unwrap();
    let mut worker = MonitoringWorker::new(FakeCamera {
        frames: vec![frame],
    }, None, Default::default());

    let output = worker.tick(0.1);

    assert!(output.camera_ok);
    let preview = output.preview.expect("expected preview frame");
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

    let mut worker = MonitoringWorker::new(UnavailableCamera, None, Default::default());
    let output = worker.tick(0.1);

    assert!(!output.camera_ok);
    assert!(output.sense_events.is_empty());
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

    let mut worker = MonitoringWorker::new(FailingAfterOne { remaining: 1 }, None, Default::default());

    let output = worker.tick(0.1);
    assert!(output.camera_ok);
    assert!(output.preview.is_some());

    let output = worker.tick(0.1);
    assert!(!output.camera_ok);
}

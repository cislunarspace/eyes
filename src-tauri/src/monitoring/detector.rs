use crate::domain::classifier::HeadPose;

/// Seam between detection and the rest of the monitoring worker.
///
/// Implementations: `OnnxDetector` (M4 spike), fakes for integration tests.
pub trait Detector {
    /// Returns `Some(HeadPose)` when a face is found, `None` otherwise.
    fn detect(&mut self, rgb: &[u8], width: u32, height: u32) -> Option<HeadPose>;
}

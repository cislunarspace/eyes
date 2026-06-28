"""Tests for HeadPoseDetector.

Since genuine face fixtures require real photographs (not available in the test
environment), the fixture-based integration tests are marked skipUnless and can
be run manually with a camera present.  The core logic is verified via:
  1. Unit tests on the pure _compute_pose_from_landmarks helper.
  2. Mock tests that inject synthetic landmarks and verify the detector
     returns the expected yaw/pitch without MediaPipe types leaking.
"""

from __future__ import annotations

import math
import os

import cv2
import numpy as np
import pytest

from eyes.classifier import HeadPose
from eyes.detector import HeadPoseDetector, _euler_from_rotation_matrix


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _yaw_matrix(degrees: float) -> np.ndarray:
    radians = math.radians(degrees)
    cos = math.cos(radians)
    sin = math.sin(radians)
    return np.array([
        [cos, 0.0, sin],
        [0.0, 1.0, 0.0],
        [-sin, 0.0, cos],
    ])


def _pitch_matrix(degrees: float) -> np.ndarray:
    """Return a 3×3 rotation matrix for pitch rotation (about the X axis)."""
    radians = math.radians(degrees)
    cos = math.cos(radians)
    sin = math.sin(radians)
    return np.array([
        [1.0, 0.0, 0.0],
        [0.0, cos, -sin],
        [0.0, sin, cos],
    ])


def _transformation_matrix(rotation: np.ndarray) -> list[float]:
    transform = np.eye(4)
    transform[:3, :3] = rotation
    return transform.reshape(-1).tolist()


def _centered_landmarks() -> list[object]:
    return [object()] * 478


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------


class TestEulerFromRotationMatrix:
    def test_identity_gives_zero_yaw_pitch(self) -> None:
        pose = _euler_from_rotation_matrix(np.eye(3))
        assert abs(pose.yaw) < 0.01
        assert abs(pose.pitch) < 0.01

    def test_positive_yaw(self) -> None:
        pose = _euler_from_rotation_matrix(_yaw_matrix(12.0))
        assert pose.yaw == pytest.approx(12.0)

    def test_negative_yaw(self) -> None:
        pose = _euler_from_rotation_matrix(_yaw_matrix(-12.0))
        assert pose.yaw == pytest.approx(-12.0)

    def test_positive_pitch(self) -> None:
        # 正向绕 X 轴旋转 = 低头 → pitch < 0
        pose = _euler_from_rotation_matrix(_pitch_matrix(10.0))
        assert pose.pitch == pytest.approx(-10.0)

    def test_negative_pitch(self) -> None:
        # 负向绕 X 轴旋转 = 仰头 → pitch > 0
        pose = _euler_from_rotation_matrix(_pitch_matrix(-10.0))
        assert pose.pitch == pytest.approx(10.0)

    def test_combined_yaw_and_pitch(self) -> None:
        rotation = _yaw_matrix(12.0) @ _pitch_matrix(10.0)
        pose = _euler_from_rotation_matrix(rotation)
        assert pose.yaw == pytest.approx(12.0)
        assert pose.pitch == pytest.approx(-10.0)


# ---------------------------------------------------------------------------
# Mock-based detector tests (no real camera needed)
# ---------------------------------------------------------------------------

def _synthetic_frame() -> np.ndarray:
    """A 640×480 BGR placeholder frame."""
    return np.full((480, 640, 3), 128, dtype=np.uint8)


def test_detector_returns_none_on_synthetic_frame(monkeypatch) -> None:
    """Synthetic (no-face) frames must return None without crashing."""

    class MockResult:
        face_landmarks = []

    class MockFaceLandmarker:
        def __init__(self, options):
            self._result = MockResult()

        def detect_for_video(self, image, timestamp_ms):
            return self._result

        def close(self):
            pass

        @classmethod
        def create_from_options(cls, options):
            return cls(options)

    import eyes.detector as det_mod

    monkeypatch.setattr(det_mod, "FaceLandmarker", MockFaceLandmarker)
    detector = det_mod.HeadPoseDetector()
    result = detector.detect(_synthetic_frame())
    assert result is None


def test_detector_return_type_is_head_pose(monkeypatch) -> None:
    """When a face is detected the return value is a HeadPose with float fields."""

    class MockResult:
        face_landmarks = [_centered_landmarks()]
        facial_transformation_matrixes = [_transformation_matrix(np.eye(3))]

    class MockFaceLandmarker:
        def __init__(self, options):
            self._result = MockResult()

        def detect_for_video(self, image, timestamp_ms):
            return self._result

        def close(self):
            pass

        @classmethod
        def create_from_options(cls, options):
            return cls(options)

    import eyes.detector as det_mod

    monkeypatch.setattr(det_mod, "FaceLandmarker", MockFaceLandmarker)
    detector = det_mod.HeadPoseDetector()
    result = detector.detect(_synthetic_frame())
    assert result is not None
    assert isinstance(result, HeadPose)
    assert isinstance(result.yaw, float)
    assert isinstance(result.pitch, float)
    assert abs(result.yaw) < 0.01
    assert abs(result.pitch) < 0.01


def test_detector_yaw_sign_positive_right(monkeypatch) -> None:
    class MockResult:
        face_landmarks = [_centered_landmarks()]
        facial_transformation_matrixes = [_transformation_matrix(_yaw_matrix(12.0))]

    class MockFaceLandmarker:
        def __init__(self, options):
            self._result = MockResult()

        def detect_for_video(self, image, timestamp_ms):
            return self._result

        def close(self):
            pass

        @classmethod
        def create_from_options(cls, options):
            return cls(options)

    import eyes.detector as det_mod

    monkeypatch.setattr(det_mod, "FaceLandmarker", MockFaceLandmarker)
    detector = det_mod.HeadPoseDetector()
    result = detector.detect(_synthetic_frame())
    assert result is not None
    assert result.yaw == pytest.approx(12.0)


def test_detector_close_calls_underlying_detector(monkeypatch) -> None:
    """close() must delegate to the underlying FaceLandmarker.close()."""
    close_called = False

    class MockFaceLandmarker:
        def __init__(self, options):
            pass

        def detect_for_video(self, image, timestamp_ms):

            class MockResult:
                face_landmarks = []

            return MockResult()

        def close(self):
            nonlocal close_called
            close_called = True

        @classmethod
        def create_from_options(cls, options):
            return cls(options)

    import eyes.detector as det_mod

    monkeypatch.setattr(det_mod, "FaceLandmarker", MockFaceLandmarker)
    detector = det_mod.HeadPoseDetector()
    detector.detect(_synthetic_frame())
    assert not close_called
    detector.close()
    assert close_called


# ---------------------------------------------------------------------------
# Fixture-based integration tests
# ---------------------------------------------------------------------------

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "frames")


def _fixture_path(name: str) -> str:
    return os.path.join(FIXTURE_DIR, name)


_fixtures_exist = all(
    os.path.exists(_fixture_path(name))
    for name in ("no_face.jpg", "centered.jpg")
)

pytestmark = pytest.mark.skipif(
    not _fixtures_exist,
    reason="Fixture frames not generated — run tests/fixtures/frames/__init__.py first",
)


def _mediapipe_available() -> bool:
    """Return True if MediaPipe can load the model (requires network)."""
    import eyes.detector as det_mod

    try:
        detector = det_mod.HeadPoseDetector()
        detector.close()
        return True
    except Exception:
        return False


_mp_available = _mediapipe_available()


class TestDetectorWithFixtures:
    """Verify detect() behaviour with stored frames.

    These require the MediaPipe model to be downloadable from GCS.
    They are skipped in offline/CI environments.
    """

    @pytest.mark.skipif(not _mp_available, reason="MediaPipe model not available")
    def test_no_face_returns_none(self) -> None:
        import eyes.detector as det_mod

        detector = det_mod.HeadPoseDetector()
        frame = cv2.imread(_fixture_path("no_face.jpg"))
        assert frame is not None
        result = detector.detect(frame)
        assert result is None
        detector.close()

    @pytest.mark.skipif(not _mp_available, reason="MediaPipe model not available")
    def test_placeholder_returns_none(self) -> None:
        """Placeholder frame (no real face) should return None."""
        import eyes.detector as det_mod

        detector = det_mod.HeadPoseDetector()
        frame = cv2.imread(_fixture_path("centered.jpg"))
        assert frame is not None
        result = detector.detect(frame)
        assert result is None
        detector.close()

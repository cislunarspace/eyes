"""Tests for HeadPoseDetector.

Since genuine face fixtures require real photographs (not available in the test
environment), the fixture-based integration tests are marked skipUnless and can
be run manually with a camera present.  The core logic is verified via:
  1. Unit tests on the pure _euler_from_rotation_matrix helper.
  2. Mock tests that inject a synthetic transformation matrix and verify
     the detector returns the expected yaw/roll without MediaPipe types leaking.
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
# Pure function tests
# ---------------------------------------------------------------------------

class TestEulerFromRotationMatrix:
    """Parametric tests for the yaw/roll extraction from a 3×3 rotation matrix."""

    def test_identity_gives_zero_yaw_roll(self) -> None:
        R = np.eye(3)
        pose = _euler_from_rotation_matrix(R)
        assert abs(pose.yaw) < 0.01
        assert abs(pose.roll) < 0.01

    def test_positive_yaw(self) -> None:
        """Positive yaw = head turned to user's right = Rz rotation."""
        angle = math.radians(30)
        R = np.array([
            [ math.cos(angle), -math.sin(angle), 0],
            [ math.sin(angle),  math.cos(angle), 0],
            [0,               0,              1],
        ])
        pose = _euler_from_rotation_matrix(R)
        assert abs(pose.yaw - 30.0) < 0.1
        assert abs(pose.roll) < 0.1

    def test_negative_yaw(self) -> None:
        """Negative yaw = head turned to user's left."""
        angle = math.radians(-20)
        R = np.array([
            [ math.cos(angle), -math.sin(angle), 0],
            [ math.sin(angle),  math.cos(angle), 0],
            [0,               0,              1],
        ])
        pose = _euler_from_rotation_matrix(R)
        assert abs(pose.yaw + 20.0) < 0.1
        assert abs(pose.roll) < 0.1

    def test_positive_roll(self) -> None:
        """Positive roll = head tilted clockwise (right ear toward right shoulder)."""
        angle = math.radians(15)
        # Rx(angle): standard 3×3 rotation about the x-axis
        R = np.array([
            [1, 0,              0],
            [0,  math.cos(angle), -math.sin(angle)],
            [0,  math.sin(angle),  math.cos(angle)],
        ])
        pose = _euler_from_rotation_matrix(R)
        assert abs(pose.yaw) < 0.1
        assert abs(pose.roll - 15.0) < 0.1

    def test_negative_roll(self) -> None:
        """Negative roll = head tilted counter-clockwise."""
        angle = math.radians(-10)
        R = np.array([
            [1, 0,              0],
            [0,  math.cos(angle), -math.sin(angle)],
            [0,  math.sin(angle),  math.cos(angle)],
        ])
        pose = _euler_from_rotation_matrix(R)
        assert abs(pose.yaw) < 0.1
        assert abs(pose.roll + 10.0) < 0.1

    def test_combined_yaw_and_roll_zxy(self) -> None:
        """Combined yaw + roll built with ZXY Tait-Bryan convention.

        Compose R = Rz(yaw) @ Rx(roll) so that the decomposition
        _euler_from_rotation_matrix (which extracts ZXY) reverses it correctly.
        """
        yaw_deg, roll_deg = 25.0, -10.0
        yaw_r = math.radians(yaw_deg)
        roll_r = math.radians(roll_deg)
        # Rz(yaw)
        Rz = np.array([
            [ math.cos(yaw_r), -math.sin(yaw_r), 0],
            [ math.sin(yaw_r),  math.cos(yaw_r), 0],
            [0,               0,              1],
        ])
        # Rx(roll)
        Rx = np.array([
            [1, 0,              0],
            [0,  math.cos(roll_r), -math.sin(roll_r)],
            [0,  math.sin(roll_r),  math.cos(roll_r)],
        ])
        R = Rz @ Rx
        pose = _euler_from_rotation_matrix(R)
        assert abs(pose.yaw - yaw_deg) < 1.0
        assert abs(pose.roll - roll_deg) < 1.0

    def test_threshold_boundary(self) -> None:
        """At exactly the default thresholds (yaw 15°, roll 10°) the function
        returns values that can be compared against the thresholds."""
        yaw_deg, roll_deg = 15.0, 10.0
        yaw_r, roll_r = math.radians(yaw_deg), math.radians(roll_deg)
        Rz = np.array([
            [ math.cos(yaw_r), -math.sin(yaw_r), 0],
            [ math.sin(yaw_r),  math.cos(yaw_r), 0],
            [0,               0,              1],
        ])
        Rx = np.array([
            [1, 0,              0],
            [0,  math.cos(roll_r), -math.sin(roll_r)],
            [0,  math.sin(roll_r),  math.cos(roll_r)],
        ])
        R = Rz @ Rx
        pose = _euler_from_rotation_matrix(R)
        assert pose.yaw >= 14.0  # within 1° tolerance
        assert pose.roll >= 9.0


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
        facial_transformation_matrixes = []

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

    det_mod._instance = None
    try:
        detector = det_mod.HeadPoseDetector()
        result = detector.detect(_synthetic_frame())
        assert result is None
    finally:
        det_mod._instance = None


def test_detector_return_type_is_head_pose(monkeypatch) -> None:
    """When a face is detected the return value is a HeadPose with float fields."""

    class MockResult:
        face_landmarks = [[0]]  # non-empty to signal "face found"
        facial_transformation_matrixes = [
            [1, 0, 0, 0,
             0, 1, 0, 0,
             0, 0, 1, 0,
             0, 0, 0, 1]  # identity rotation
        ]

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
    det_mod._instance = None
    try:
        detector = det_mod.HeadPoseDetector()
        result = detector.detect(_synthetic_frame())
        assert result is not None
        assert isinstance(result, HeadPose)
        assert isinstance(result.yaw, float)
        assert isinstance(result.roll, float)
        # Identity matrix → yaw and roll should be near zero
        assert abs(result.yaw) < 0.01
        assert abs(result.roll) < 0.01
    finally:
        det_mod._instance = None


def test_detector_yaw_sign_positive_right(monkeypatch) -> None:
    """Positive yaw (right turn) gives positive output."""
    class MockResult:
        face_landmarks = [[0]]
        yaw_r = math.radians(20)
        yaw_arr = [
             math.cos(yaw_r), -math.sin(yaw_r), 0, 0,
             math.sin(yaw_r),  math.cos(yaw_r), 0, 0,
             0,               0,              1, 0,
             0,               0,              0, 1,
        ]
        facial_transformation_matrixes = [yaw_arr]

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
    det_mod._instance = None
    try:
        detector = det_mod.HeadPoseDetector()
        result = detector.detect(_synthetic_frame())
        assert result is not None
        assert result.yaw > 0  # positive yaw = head turned right
    finally:
        det_mod._instance = None


def test_detector_close_calls_underlying_detector(monkeypatch) -> None:
    """close() must delegate to the underlying FaceLandmarker.close()."""
    close_called = False

    class MockFaceLandmarker:
        def __init__(self, options):
            pass

        def detect_for_video(self, image, timestamp_ms):
            class MockResult:
                face_landmarks = []
                facial_transformation_matrixes = []
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
    detector.detect(_synthetic_frame())  # ensure init
    assert not close_called
    detector.close()
    assert close_called


def test_detector_returns_none_when_matrices_empty(monkeypatch) -> None:
    """When face landmarks exist but transformation matrices are empty, return None."""

    class MockResult:
        face_landmarks = [[0]]  # face detected
        facial_transformation_matrixes = []  # but no matrix

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


# ---------------------------------------------------------------------------
# Fixture-based integration tests
# ---------------------------------------------------------------------------

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "frames")


def _fixture_path(name: str) -> str:
    return os.path.join(FIXTURE_DIR, name)


# Check if fixtures exist; if not, skip all fixture tests
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
    det_mod._instance = None
    try:
        det_mod.HeadPoseDetector()
        return True
    except Exception:
        return False
    finally:
        if det_mod._instance is not None:
            det_mod._instance.close()
            det_mod._instance = None


# Only run fixture tests if MediaPipe model is downloadable
_mp_available = _mediapipe_available()


class TestDetectorWithFixtures:
    """Verify detect() behaviour with stored frames.

    These require the MediaPipe model to be downloadable from GCS.
    They are skipped in offline/CI environments.
    """

    @pytest.mark.skipif(not _mp_available, reason="MediaPipe model not available")
    def test_no_face_returns_none(self) -> None:
        import eyes.detector as det_mod
        det_mod._instance = None
        try:
            detector = det_mod.HeadPoseDetector()
            frame = cv2.imread(_fixture_path("no_face.jpg"))
            assert frame is not None
            result = detector.detect(frame)
            assert result is None
        finally:
            if det_mod._instance is not None:
                det_mod._instance.close()
                det_mod._instance = None

    @pytest.mark.skipif(not _mp_available, reason="MediaPipe model not available")
    def test_placeholder_returns_none(self) -> None:
        """Placeholder frame (no real face) should return None."""
        import eyes.detector as det_mod
        det_mod._instance = None
        try:
            detector = det_mod.HeadPoseDetector()
            frame = cv2.imread(_fixture_path("centered.jpg"))
            assert frame is not None
            result = detector.detect(frame)
            assert result is None
        finally:
            if det_mod._instance is not None:
                det_mod._instance.close()
                det_mod._instance = None

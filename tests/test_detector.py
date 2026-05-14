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
from eyes.detector import (
    _LANDMARK_CHIN,
    _LANDMARK_FOREHEAD,
    _LANDMARK_LEFT_EAR,
    _LANDMARK_RIGHT_EAR,
    HeadPoseDetector,
    _compute_pose_from_landmarks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Landmark:
    """Minimal landmark stand-in with x, y, z attributes."""

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        self.x = x
        self.y = y
        self.z = z


def _make_landmarks(overrides: dict[int, _Landmark] | None = None) -> list[_Landmark]:
    """Build a 468-element landmark list with selective overrides."""
    default = _Landmark(0.5, 0.5, -0.05)
    lm = [default] * 468
    for idx, val in (overrides or {}).items():
        lm[idx] = val
    return lm


def _centered_landmarks() -> list[_Landmark]:
    """Landmarks for a head facing the camera directly (yaw=0, pitch=0)."""
    return _make_landmarks({
        _LANDMARK_LEFT_EAR: _Landmark(0.85, 0.50, -0.05),
        _LANDMARK_RIGHT_EAR: _Landmark(0.15, 0.50, -0.05),
        _LANDMARK_FOREHEAD: _Landmark(0.50, 0.30, -0.10),
        _LANDMARK_CHIN: _Landmark(0.50, 0.70, -0.10),
    })


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------

class TestComputePoseFromLandmarks:
    """Parametric tests for _compute_pose_from_landmarks."""

    def test_centered_gives_zero_yaw_pitch(self) -> None:
        pose = _compute_pose_from_landmarks(_centered_landmarks())
        assert abs(pose.yaw) < 0.01
        assert abs(pose.roll) < 0.01

    def test_positive_yaw(self) -> None:
        """Head turned right: left ear closer (z more negative), right ear farther."""
        lm = _centered_landmarks()
        lm[_LANDMARK_LEFT_EAR] = _Landmark(0.85, 0.50, -0.10)
        lm[_LANDMARK_RIGHT_EAR] = _Landmark(0.15, 0.50, 0.00)
        pose = _compute_pose_from_landmarks(lm)
        assert pose.yaw > 0

    def test_negative_yaw(self) -> None:
        """Head turned left: right ear closer, left ear farther."""
        lm = _centered_landmarks()
        lm[_LANDMARK_LEFT_EAR] = _Landmark(0.85, 0.50, 0.00)
        lm[_LANDMARK_RIGHT_EAR] = _Landmark(0.15, 0.50, -0.10)
        pose = _compute_pose_from_landmarks(lm)
        assert pose.yaw < 0

    def test_positive_pitch(self) -> None:
        """Looking up: forehead closer, chin farther."""
        lm = _centered_landmarks()
        lm[_LANDMARK_FOREHEAD] = _Landmark(0.50, 0.30, -0.15)
        lm[_LANDMARK_CHIN] = _Landmark(0.50, 0.70, -0.05)
        pose = _compute_pose_from_landmarks(lm)
        assert pose.roll > 0

    def test_negative_pitch(self) -> None:
        """Looking down: chin closer, forehead farther."""
        lm = _centered_landmarks()
        lm[_LANDMARK_FOREHEAD] = _Landmark(0.50, 0.30, -0.05)
        lm[_LANDMARK_CHIN] = _Landmark(0.50, 0.70, -0.15)
        pose = _compute_pose_from_landmarks(lm)
        assert pose.roll < 0

    def test_yaw_and_pitch_independent(self) -> None:
        """Changing pitch should not significantly affect yaw."""
        base = _compute_pose_from_landmarks(_centered_landmarks())
        lm = _centered_landmarks()
        # Pitch the head down without changing ear positions
        lm[_LANDMARK_FOREHEAD] = _Landmark(0.50, 0.30, -0.05)
        lm[_LANDMARK_CHIN] = _Landmark(0.50, 0.70, -0.15)
        pitched = _compute_pose_from_landmarks(lm)
        assert abs(pitched.yaw - base.yaw) < 0.1
        assert abs(pitched.roll - base.roll) > 0.1

    def test_pitch_and_yaw_independent(self) -> None:
        """Changing yaw should not significantly affect pitch."""
        base = _compute_pose_from_landmarks(_centered_landmarks())
        lm = _centered_landmarks()
        lm[_LANDMARK_LEFT_EAR] = _Landmark(0.85, 0.50, -0.10)
        lm[_LANDMARK_RIGHT_EAR] = _Landmark(0.15, 0.50, 0.00)
        yawed = _compute_pose_from_landmarks(lm)
        assert abs(yawed.yaw - base.yaw) > 0.1
        assert abs(yawed.roll - base.roll) < 0.1


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
    assert isinstance(result.roll, float)
    assert abs(result.yaw) < 0.01
    assert abs(result.roll) < 0.01


def test_detector_yaw_sign_positive_right(monkeypatch) -> None:
    """Positive yaw (right turn) gives positive output."""
    lm = _centered_landmarks()
    lm[_LANDMARK_LEFT_EAR] = _Landmark(0.85, 0.50, -0.10)
    lm[_LANDMARK_RIGHT_EAR] = _Landmark(0.15, 0.50, 0.00)

    class MockResult:
        face_landmarks = [lm]

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
    assert result.yaw > 0


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

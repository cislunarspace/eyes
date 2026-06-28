"""Tests for head_pose_geometry — the pure rotation-math module.

These tests exercise `rotation_to_yaw_pitch` and `transform_to_yaw_pitch`
in isolation from any detector model. They use hand-constructed rotation
matrices (identity, pure yaw, pure pitch, combined) to verify the sign
convention documented on `HeadPose`.

Sign convention:
  Positive yaw   = head turned to the user's own RIGHT.
  Negative yaw   = head turned to the user's own LEFT.
  Positive pitch = head tilted UP (仰头).
  Negative pitch = head tilted DOWN (低头).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from eyes.classifier import HeadPose
from eyes.head_pose_geometry import rotation_to_yaw_pitch, transform_to_yaw_pitch


# ---------------------------------------------------------------------------
# Helpers — rotation matrix builders
# ---------------------------------------------------------------------------


def _yaw_matrix(degrees: float) -> np.ndarray:
    """Return a 3×3 rotation matrix for yaw rotation (about the Y axis)."""
    r = math.radians(degrees)
    c, s = math.cos(r), math.sin(r)
    return np.array([
        [c, 0.0, s],
        [0.0, 1.0, 0.0],
        [-s, 0.0, c],
    ])


def _pitch_matrix(degrees: float) -> np.ndarray:
    """Return a 3×3 rotation matrix for pitch rotation (about the X axis)."""
    r = math.radians(degrees)
    c, s = math.cos(r), math.sin(r)
    return np.array([
        [1.0, 0.0, 0.0],
        [0.0, c, -s],
        [0.0, s, c],
    ])


# ---------------------------------------------------------------------------
# rotation_to_yaw_pitch — pure 3×3 rotation tests
# ---------------------------------------------------------------------------


class TestRotationToYawPitch:
    """Sign-convention tests for the 3×3 rotation → yaw/pitch helper."""

    def test_identity_gives_zero_yaw_pitch(self) -> None:
        pose = rotation_to_yaw_pitch(np.eye(3))
        assert abs(pose.yaw) < 0.01
        assert abs(pose.pitch) < 0.01

    def test_positive_yaw(self) -> None:
        pose = rotation_to_yaw_pitch(_yaw_matrix(12.0))
        assert pose.yaw == pytest.approx(12.0, abs=0.1)

    def test_negative_yaw(self) -> None:
        pose = rotation_to_yaw_pitch(_yaw_matrix(-12.0))
        assert pose.yaw == pytest.approx(-12.0, abs=0.1)

    def test_positive_pitch(self) -> None:
        pose = rotation_to_yaw_pitch(_pitch_matrix(10.0))
        assert pose.pitch == pytest.approx(10.0, abs=0.1)

    def test_negative_pitch(self) -> None:
        pose = rotation_to_yaw_pitch(_pitch_matrix(-10.0))
        assert pose.pitch == pytest.approx(-10.0, abs=0.1)

    def test_combined_yaw_and_pitch(self) -> None:
        rotation = _yaw_matrix(12.0) @ _pitch_matrix(10.0)
        pose = rotation_to_yaw_pitch(rotation)
        assert pose.yaw == pytest.approx(12.0, abs=0.2)
        assert pose.pitch == pytest.approx(10.0, abs=0.2)

    def test_large_positive_yaw(self) -> None:
        pose = rotation_to_yaw_pitch(_yaw_matrix(45.0))
        assert pose.yaw == pytest.approx(45.0, abs=0.5)

    def test_large_negative_pitch(self) -> None:
        pose = rotation_to_yaw_pitch(_pitch_matrix(-45.0))
        assert pose.pitch == pytest.approx(-45.0, abs=0.5)

    def test_return_type_is_head_pose(self) -> None:
        pose = rotation_to_yaw_pitch(np.eye(3))
        assert isinstance(pose, HeadPose)
        assert isinstance(pose.yaw, float)
        assert isinstance(pose.pitch, float)

    def test_rejects_non_3x3_matrix(self) -> None:
        with pytest.raises(ValueError, match="Expected a 3×3"):
            rotation_to_yaw_pitch(np.eye(4))

    def test_rejects_2x2_matrix(self) -> None:
        with pytest.raises(ValueError, match="Expected a 3×3"):
            rotation_to_yaw_pitch(np.eye(2))


# ---------------------------------------------------------------------------
# transform_to_yaw_pitch — 4×4 convenience wrapper
# ---------------------------------------------------------------------------


class TestTransformToYawPitch:
    """Tests for the 4×4 → HeadPose convenience wrapper."""

    def test_4x4_identity_gives_zero_yaw_pitch(self) -> None:
        pose = transform_to_yaw_pitch(np.eye(4))
        assert abs(pose.yaw) < 0.01
        assert abs(pose.pitch) < 0.01

    def test_4x4_yaw_rotation(self) -> None:
        transform = np.eye(4)
        transform[:3, :3] = _yaw_matrix(20.0)
        pose = transform_to_yaw_pitch(transform)
        assert pose.yaw == pytest.approx(20.0, abs=0.1)

    def test_4x4_pitch_rotation(self) -> None:
        transform = np.eye(4)
        transform[:3, :3] = _pitch_matrix(15.0)
        pose = transform_to_yaw_pitch(transform)
        assert pose.pitch == pytest.approx(15.0, abs=0.1)

    def test_flat_16_element_list(self) -> None:
        """MediaPipe returns the matrix as a flat list; reshaping should work."""
        transform = np.eye(4)
        transform[:3, :3] = _yaw_matrix(8.0)
        flat: list[float] = transform.reshape(-1).tolist()
        pose = transform_to_yaw_pitch(flat)
        assert pose.yaw == pytest.approx(8.0, abs=0.2)

    def test_4x4_with_translation_preserves_yaw(self) -> None:
        """Translation entries (column 3, row 3) should be ignored."""
        transform = np.eye(4)
        transform[:3, :3] = _yaw_matrix(15.0)
        transform[0, 3] = 10.0  # translation X
        transform[1, 3] = -5.0  # translation Y
        transform[2, 3] = 3.0   # translation Z
        pose = transform_to_yaw_pitch(transform)
        assert pose.yaw == pytest.approx(15.0, abs=0.2)


# ---------------------------------------------------------------------------
# Geometry module structure — acceptance criteria checks
# ---------------------------------------------------------------------------


class TestGeometryModuleDoesNotImportMediaPipe:
    """head_pose_geometry.py must not import mediapipe or cv2."""

    def test_no_mediapipe_import(self) -> None:
        from eyes import head_pose_geometry as module
        source = open(module.__file__, encoding="utf-8").read()
        assert "import mediapipe" not in source
        assert "from mediapipe" not in source

    def test_no_cv2_import(self) -> None:
        from eyes import head_pose_geometry as module
        source = open(module.__file__, encoding="utf-8").read()
        assert "import cv2" not in source
        assert "from cv2" not in source


class TestDetectorStillExportsLegacyName:
    """The re-export `_euler_from_rotation_matrix` from detector.py keeps
    existing test imports working."""

    def test_legacy_name_still_importable(self) -> None:
        from eyes.detector import _euler_from_rotation_matrix
        assert callable(_euler_from_rotation_matrix)

    def test_legacy_name_same_as_rotation_to_yaw_pitch(self) -> None:
        from eyes.detector import _euler_from_rotation_matrix
        from eyes.head_pose_geometry import rotation_to_yaw_pitch
        assert _euler_from_rotation_matrix is rotation_to_yaw_pitch

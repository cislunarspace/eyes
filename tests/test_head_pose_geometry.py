"""Tests for head_pose_geometry — the pure rotation-math module.

Sign convention:
  Positive yaw   = head turned to the user's own RIGHT.
  Negative yaw   = head turned to the user's own LEFT.
  Positive pitch = head tilted UP (仰头).
  Negative pitch = head tilted DOWN (低头).

坐标系：camera Y 轴向下。
_pitch_matrix(θ) 对应绕 X 轴正向旋转（右手定则），在 camera Y-down 坐标系下
表现为低头（下巴向胸部方向），因此提取出的 pitch 为负值。
"""
from __future__ import annotations
import math
import numpy as np
import pytest
from eyes.classifier import HeadPose
from eyes.head_pose_geometry import rotation_to_yaw_pitch, transform_to_yaw_pitch

def _yaw_matrix(degrees: float) -> np.ndarray:
    r = math.radians(degrees)
    c, s = math.cos(r), math.sin(r)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])

def _pitch_matrix(degrees: float) -> np.ndarray:
    r = math.radians(degrees)
    c, s = math.cos(r), math.sin(r)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])

class TestRotationToYawPitch:
    def test_identity_gives_zero(self) -> None:
        pose = rotation_to_yaw_pitch(np.eye(3))
        assert abs(pose.yaw) < 0.01
        assert abs(pose.pitch) < 0.01

    def test_positive_yaw(self) -> None:
        pose = rotation_to_yaw_pitch(_yaw_matrix(12.0))
        assert pose.yaw == pytest.approx(12.0, abs=0.1)

    def test_negative_yaw(self) -> None:
        pose = rotation_to_yaw_pitch(_yaw_matrix(-12.0))
        assert pose.yaw == pytest.approx(-12.0, abs=0.1)

    def test_negative_pitch_for_positive_rotation(self) -> None:
        """正向绕 X 轴旋转 = 低头 → pitch < 0"""
        pose = rotation_to_yaw_pitch(_pitch_matrix(10.0))
        assert pose.pitch == pytest.approx(-10.0, abs=0.1)

    def test_positive_pitch_for_negative_rotation(self) -> None:
        """负向绕 X 轴旋转 = 仰头 → pitch > 0"""
        pose = rotation_to_yaw_pitch(_pitch_matrix(-10.0))
        assert pose.pitch == pytest.approx(10.0, abs=0.1)

    def test_combined_yaw_and_pitch(self) -> None:
        rotation = _yaw_matrix(12.0) @ _pitch_matrix(10.0)
        pose = rotation_to_yaw_pitch(rotation)
        assert pose.yaw == pytest.approx(12.0, abs=0.2)
        assert pose.pitch == pytest.approx(-10.0, abs=0.2)

    def test_large_positive_yaw(self) -> None:
        pose = rotation_to_yaw_pitch(_yaw_matrix(45.0))
        assert pose.yaw == pytest.approx(45.0, abs=0.5)

    def test_large_positive_pitch_for_negative_rotation(self) -> None:
        pose = rotation_to_yaw_pitch(_pitch_matrix(-45.0))
        assert pose.pitch == pytest.approx(45.0, abs=0.5)

    def test_return_type(self) -> None:
        pose = rotation_to_yaw_pitch(np.eye(3))
        assert isinstance(pose, HeadPose)
        assert isinstance(pose.pitch, float)

    def test_rejects_non_3x3(self) -> None:
        with pytest.raises(ValueError, match="Expected a 3×3"):
            rotation_to_yaw_pitch(np.eye(4))

class TestTransformToYawPitch:
    def test_4x4_identity(self) -> None:
        pose = transform_to_yaw_pitch(np.eye(4))
        assert abs(pose.yaw) < 0.01
        assert abs(pose.pitch) < 0.01

    def test_4x4_yaw(self) -> None:
        t = np.eye(4); t[:3, :3] = _yaw_matrix(20.0)
        pose = transform_to_yaw_pitch(t)
        assert pose.yaw == pytest.approx(20.0, abs=0.1)

    def test_4x4_pitch(self) -> None:
        t = np.eye(4); t[:3, :3] = _pitch_matrix(15.0)
        pose = transform_to_yaw_pitch(t)
        assert pose.pitch == pytest.approx(-15.0, abs=0.1)

    def test_flat_16_element(self) -> None:
        t = np.eye(4); t[:3, :3] = _yaw_matrix(8.0)
        pose = transform_to_yaw_pitch(t.reshape(-1).tolist())
        assert pose.yaw == pytest.approx(8.0, abs=0.2)

    def test_translation_ignored(self) -> None:
        t = np.eye(4); t[:3, :3] = _yaw_matrix(15.0)
        t[0, 3] = 10.0; t[1, 3] = -5.0; t[2, 3] = 3.0
        pose = transform_to_yaw_pitch(t)
        assert pose.yaw == pytest.approx(15.0, abs=0.2)

class TestNoMediaPipe:
    def test_no_mediapipe_import(self) -> None:
        from eyes import head_pose_geometry as m
        assert "import mediapipe" not in open(m.__file__, encoding="utf-8").read()

    def test_no_cv2(self) -> None:
        from eyes import head_pose_geometry as m
        assert "import cv2" not in open(m.__file__, encoding="utf-8").read()

class TestLegacyName:
    def test_importable(self) -> None:
        from eyes.detector import _euler_from_rotation_matrix
        assert callable(_euler_from_rotation_matrix)

    def test_same_as_pitch(self) -> None:
        from eyes.detector import _euler_from_rotation_matrix
        from eyes.head_pose_geometry import rotation_to_yaw_pitch
        assert _euler_from_rotation_matrix is rotation_to_yaw_pitch

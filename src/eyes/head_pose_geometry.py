"""Pure geometry for head-pose estimation.

Extracted from `detector.py` so the rotation-matrix → yaw/pitch
math is testable in isolation without MediaPipe. The only external
dependency is `numpy` and the `HeadPose` value object.

The function `rotation_to_yaw_pitch` takes a 3×3 rotation matrix
and returns a `HeadPose` with `yaw` and `pitch` in degrees.

Sign convention (see `classifier.HeadPose` docstring for the full story):
  Positive yaw   = head turned to the user's own RIGHT.
  Negative yaw   = head turned to the user's own LEFT.
  Positive pitch = head tilted UP (仰头).
  Negative pitch = head tilted DOWN (低头).
"""

from __future__ import annotations

import math

import numpy as np

from .classifier import HeadPose


def rotation_to_yaw_pitch(rotation: np.ndarray) -> HeadPose:
    """Extract yaw and pitch (in degrees) from a 3×3 rotation matrix.

    The matrix is the upper-left 3×3 of the 4×4 transformation
    matrix returned by MediaPipe (or any other face landmark model).
    Yaw is extracted from the (0,2) and (2,2) entries (rotation about
    the vertical axis). Pitch is extracted from the (2,1) and (2,2)
    entries (rotation about the horizontal/left-right axis).

    Args:
        rotation: A 3×3 numpy array representing the rotation component
            of the face transformation matrix.

    Returns:
        A `HeadPose` with `yaw` and `pitch` in degrees.

    Raises:
        ValueError: If `rotation` is not a 3×3 matrix.
    """
    if rotation.shape != (3, 3):
        raise ValueError(
            f"Expected a 3×3 rotation matrix, got shape {rotation.shape}"
        )
    yaw = math.atan2(rotation[0, 2], rotation[2, 2])
    pitch = math.atan2(rotation[2, 1], rotation[2, 2])
    return HeadPose(yaw=math.degrees(yaw), pitch=math.degrees(pitch))


# 向后兼容别名
rotation_to_yaw_roll = rotation_to_yaw_pitch


def transform_to_yaw_pitch(transform_4x4: np.ndarray) -> HeadPose:
    """Extract yaw and pitch from a 4×4 transformation matrix.

    Convenience wrapper that extracts the 3×3 rotation submatrix
    and delegates to `rotation_to_yaw_pitch`. This is the shape
    MediaPipe returns.

    Args:
        transform_4x4: A 4×4 numpy array (the facial transformation
            matrix from MediaPipe, or a 16-element flat array that
            can be reshaped to 4×4).

    Returns:
        A `HeadPose` with `yaw` and `pitch` in degrees.

    Raises:
        ValueError: If `transform_4x4` cannot be reshaped to 4×4.
    """
    mat = np.array(transform_4x4).reshape(4, 4)
    return rotation_to_yaw_pitch(mat[:3, :3])


# 向后兼容别名
transform_to_yaw_roll = transform_to_yaw_pitch

"""Pure geometry for head-pose estimation.

Extracted from `detector.py` so the rotation-matrix → yaw/roll
math is testable in isolation without MediaPipe. The only external
dependency is `numpy` and the `HeadPose` value object.

The function `rotation_to_yaw_roll` takes a 3×3 rotation matrix
and returns a `HeadPose` with `yaw` and `roll` in degrees.

Sign convention (see `classifier.HeadPose` docstring for the full story):
  Positive yaw   = head turned to the user's own RIGHT.
  Negative yaw   = head turned to the user's own LEFT.
  Positive roll  = head tilted clockwise (right ear → right shoulder).
  Negative roll  = head tilted counter-clockwise.
"""

from __future__ import annotations

import math

import numpy as np

from .classifier import HeadPose


def rotation_to_yaw_roll(rotation: np.ndarray) -> HeadPose:
    """Extract yaw and roll (in degrees) from a 3×3 rotation matrix.

    The matrix is the upper-left 3×3 of the 4×4 transformation
    matrix returned by MediaPipe (or any other face landmark model).
    Yaw is extracted from the (0,2) and (2,2) entries (rotation about
    the vertical axis). Roll is extracted from the (1,0) and (1,1)
    entries (rotation about the forward/camera-facing axis).

    Args:
        rotation: A 3×3 numpy array representing the rotation component
            of the face transformation matrix.

    Returns:
        A `HeadPose` with `yaw` and `roll` in degrees.

    Raises:
        ValueError: If `rotation` is not a 3×3 matrix.
    """
    if rotation.shape != (3, 3):
        raise ValueError(
            f"Expected a 3×3 rotation matrix, got shape {rotation.shape}"
        )
    yaw = math.atan2(rotation[0, 2], rotation[2, 2])
    roll = math.atan2(rotation[1, 0], rotation[1, 1])
    return HeadPose(yaw=math.degrees(yaw), roll=math.degrees(roll))


def transform_to_yaw_roll(transform_4x4: np.ndarray) -> HeadPose:
    """Extract yaw and roll from a 4×4 transformation matrix.

    Convenience wrapper that extracts the 3×3 rotation submatrix
    and delegates to `rotation_to_yaw_roll`. This is the shape
    MediaPipe returns.

    Args:
        transform_4x4: A 4×4 numpy array (the facial transformation
            matrix from MediaPipe, or a 16-element flat array that
            can be reshaped to 4×4).

    Returns:
        A `HeadPose` with `yaw` and `roll` in degrees.

    Raises:
        ValueError: If `transform_4x4` cannot be reshaped to 4×4.
    """
    mat = np.array(transform_4x4).reshape(4, 4)
    return rotation_to_yaw_roll(mat[:3, :3])

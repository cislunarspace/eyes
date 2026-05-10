"""Generate and save synthetic fixture frames for HeadPoseDetector tests.

These are placeholder BGR images (solid-color frames with no actual face data).
They are used to test the no-face code path.  Real face fixtures would require
actual photographs, which are out of scope for this automated test suite.
"""

from __future__ import annotations

import os

import cv2
import numpy as np

FIXTURE_DIR = os.path.join(os.path.dirname(__file__))


def _save(name: str, frame: np.ndarray) -> str:
    path = os.path.join(FIXTURE_DIR, name)
    cv2.imwrite(path, frame)
    return path


def generate_all() -> list[str]:
    """Generate and persist all synthetic fixture frames. Returns paths."""
    paths: list[str] = []

    # No-face: blue-ish placeholder
    no_face = np.full((480, 640, 3), (200, 100, 50), dtype=np.uint8)
    paths.append(_save("no_face.jpg", no_face))

    # Centered: neutral gray
    centered = np.full((480, 640, 3), (128, 128, 128), dtype=np.uint8)
    paths.append(_save("centered.jpg", centered))

    # Yawed-left: green tint
    yawed_left = np.full((480, 640, 3), (100, 200, 100), dtype=np.uint8)
    paths.append(_save("yawed_left.jpg", yawed_left))

    # Yawed-right: red tint
    yawed_right = np.full((480, 640, 3), (100, 100, 200), dtype=np.uint8)
    paths.append(_save("yawed_right.jpg", yawed_right))

    # Rolled: purple tint
    rolled = np.full((480, 640, 3), (150, 80, 150), dtype=np.uint8)
    paths.append(_save("rolled.jpg", rolled))

    return paths


if __name__ == "__main__":
    p = generate_all()
    print("Generated fixtures:", p)

"""Head-pose detector wrapping MediaPipe FaceLandmarker.

See ``eyes.classifier.HeadPose`` for the canonical sign convention and field
documentation. This module produces ``HeadPose`` values from raw camera frames.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    RunningMode,
)

from .classifier import HeadPose

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
# Prefer a local model bundled in the project; fall back to the GCS URL
# which MediaPipe auto-downloads on first use.
_MODEL_DIR = Path(__file__).parent.parent.parent / "models"
_MODEL_LOCAL = _MODEL_DIR / "face_landmarker.task"
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
_MODEL_ASSET = str(_MODEL_LOCAL) if _MODEL_LOCAL.exists() else _MODEL_URL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _euler_from_rotation_matrix(R: np.ndarray) -> HeadPose:
    """Return a ``HeadPose`` extracted from a 3×3 rotation matrix.

    Yaw   = rotation about the vertical (up) axis  → nose direction
    Roll  = rotation about the forward (camera-facing) axis → ear-over-shoulder

    Pitch (nod) is intentionally omitted per ADR-0001.
    """
    # yaw (Rz) — rotation about the vertical (up) axis
    yaw = math.atan2(R[1, 0], R[0, 0])
    # roll (Rx) — rotation about the forward (camera-facing) axis
    roll = math.atan2(R[2, 1], R[2, 2])
    return HeadPose(yaw=math.degrees(yaw), roll=math.degrees(roll))


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class HeadPoseDetector:
    """Wraps MediaPipe FaceLandmarker; emits a ``HeadPose`` per frame.

    Interface contract
    -----------------
    ``detect(frame) -> Optional[HeadPose]``

    * Returns ``None`` when no face is detected.
    * Returns a ``HeadPose`` when a face is found; the sign convention is
      documented on ``HeadPose`` itself.
    * No MediaPipe types appear in the return value.
    * Thread-safe after init; the Python GIL serialises calls.
    """

    def __init__(self) -> None:
        base_options = mp.tasks.BaseOptions(model_asset_path=_MODEL_ASSET)
        options = FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=True,
        )
        self._detector = FaceLandmarker.create_from_options(options)

    def detect(self, frame: np.ndarray) -> Optional[HeadPose]:
        """Run head-pose estimation on a BGR frame.

        Args:
            frame: BGR image from OpenCV (H×W×3), uint8.

        Returns:
            ``None`` if no face detected, otherwise a ``HeadPose`` carrying
            the sign convention documented on the class.
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        # Use get_current_timestamp() for video-mode timestamps
        timestamp_ms = int(cv2.getTickCount() / cv2.getTickFrequency() * 1000)
        result = self._detector.detect_for_video(mp_image, timestamp_ms)
        if not result.face_landmarks:
            return None
        matrices = result.facial_transformation_matrixes
        if not matrices:
            return None
        # 4×4 homogeneous transform; take the 3×3 rotation block
        T = np.array(matrices[0]).reshape(4, 4)
        R = T[:3, :3]
        return _euler_from_rotation_matrix(R)

    def close(self) -> None:
        self._detector.close()

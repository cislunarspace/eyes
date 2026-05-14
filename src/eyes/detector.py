"""Head-pose detector wrapping MediaPipe FaceLandmarker.

See ``eyes.classifier.HeadPose`` for the canonical sign convention and field
documentation. This module produces ``HeadPose`` values from raw camera frames.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from typing import Any

import cv2
import mediapipe as mp
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    RunningMode,
)

from .classifier import HeadPose

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------
_MODEL_DIR = Path(__file__).parent.parent.parent / "models"
_MODEL_LOCAL = _MODEL_DIR / "face_landmarker.task"
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
_MODEL_ASSET = str(_MODEL_LOCAL) if _MODEL_LOCAL.exists() else _MODEL_URL

# Landmark indices for geometric pose estimation
_LANDMARK_LEFT_EAR = 234
_LANDMARK_RIGHT_EAR = 454
_LANDMARK_FOREHEAD = 10
_LANDMARK_CHIN = 152


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_pose_from_landmarks(landmarks: Any) -> HeadPose:
    """Compute yaw and pitch from face landmark 3D coordinates.

    Uses geometric relationships between key face landmarks to derive
    yaw (left/right turn) and pitch (up/down tilt) independently,
    avoiding the euler-angle coupling inherent in rotation-matrix
    decomposition.

    Sign convention
    ---------------
    Positive yaw  = head turned to user's RIGHT.
    Positive roll = looking UP (仰头).

    MediaPipe coordinate system
    ---------------------------
    x → right (image), y → down, z → depth (negative = closer to camera,
    origin at head center).
    """
    left_ear = landmarks[_LANDMARK_LEFT_EAR]
    right_ear = landmarks[_LANDMARK_RIGHT_EAR]
    forehead = landmarks[_LANDMARK_FOREHEAD]
    chin = landmarks[_LANDMARK_CHIN]

    # Yaw: angle of the ear-to-ear line in the horizontal (xz) plane.
    # When head turns right, left ear comes forward (z ↓), right ear
    # goes back (z ↑) → ear_dz becomes negative → yaw positive.
    ear_dx = left_ear.x - right_ear.x
    ear_dz = left_ear.z - right_ear.z
    yaw = -math.atan2(ear_dz, ear_dx) * (180.0 / math.pi)

    # Pitch: angle of the forehead-to-chin line in the sagittal (yz) plane.
    # Looking down → chin forward (z ↓) → fc_dz positive → pitch negative.
    fc_dy = chin.y - forehead.y
    fc_dz = forehead.z - chin.z
    pitch = -math.atan2(fc_dz, fc_dy) * (180.0 / math.pi)

    return HeadPose(yaw=yaw, roll=pitch)


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
            output_facial_transformation_matrixes=False,
        )
        self._detector = FaceLandmarker.create_from_options(options)

    def detect(self, frame: Any) -> Optional[HeadPose]:
        """Run head-pose estimation on a BGR frame.

        Args:
            frame: BGR image from OpenCV (H×W×3), uint8.

        Returns:
            ``None`` if no face detected, otherwise a ``HeadPose`` carrying
            the sign convention documented on the class.
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms = int(cv2.getTickCount() / cv2.getTickFrequency() * 1000)
        result = self._detector.detect_for_video(mp_image, timestamp_ms)
        if not result.face_landmarks:
            return None
        return _compute_pose_from_landmarks(result.face_landmarks[0])

    def close(self) -> None:
        self._detector.close()

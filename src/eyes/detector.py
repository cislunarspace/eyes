"""Head-pose detector wrapping MediaPipe FaceLandmarker.

See ``eyes.classifier.HeadPose`` for the canonical sign convention and field
documentation. This module produces ``HeadPose`` values from raw camera frames.

The detector composes three private pieces:
  - An ``AssetResolver`` that picks the model file path (local or remote).
  - A ``DetectorBackend`` (here: ``MediaPipeBackend``) that owns the
    FaceLandmarker and does frame preprocessing + inference.
  - ``head_pose_geometry.rotation_to_yaw_roll`` — the pure rotation math,
    tested in isolation without MediaPipe.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python.vision import (
    FaceLandmarker,
    FaceLandmarkerOptions,
    RunningMode,
)

from .classifier import HeadPose
from .head_pose_geometry import transform_to_yaw_roll

# ---------------------------------------------------------------------------
# Asset resolution — seams for the model path
# ---------------------------------------------------------------------------

_MODEL_DIR = Path(__file__).parent.parent.parent / "models"
_MODEL_LOCAL = _MODEL_DIR / "face_landmarker.task"
_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)


class AssetResolver(Protocol):
    """Protocol for resolving the path to a model asset file."""

    def resolve(self) -> str:
        """Return the model asset path (local file or remote URL)."""
        ...


class LocalAsset:
    """Returns a local file path if it exists."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def resolve(self) -> str:
        return str(self._path)


class RemoteAsset:
    """Returns a remote URL as the model asset path."""

    def __init__(self, url: str) -> None:
        self._url = url

    def resolve(self) -> str:
        return self._url


def _default_asset_resolver() -> AssetResolver:
    """Pick the local model if it exists, otherwise the remote URL."""
    if _MODEL_LOCAL.exists():
        return LocalAsset(_MODEL_LOCAL)
    return RemoteAsset(_MODEL_URL)


# ---------------------------------------------------------------------------
# DetectorBackend protocol and MediaPipe implementation
# ---------------------------------------------------------------------------

class DetectorBackend(Protocol):
    """Protocol for a frame → 4×4 transformation matrix backend.

    The backend handles frame preprocessing (colour space conversion,
    timestamp extraction) and model inference. It returns the raw
    4×4 transformation matrix from the landmark model, or None when
    no face is detected.

    The caller is responsible for converting the matrix to a
    HeadPose via ``head_pose_geometry.transform_to_yaw_roll``.
    """

    def infer(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Run inference on a BGR frame.

        Returns:
            A 4×4 numpy array (the facial transformation matrix)
            when a face is detected, or None otherwise.
        """
        ...

    def close(self) -> None:
        """Release backend resources."""
        ...


class MediaPipeBackend:
    """Concrete backend using MediaPipe FaceLandmarker.

    ``cv2`` is used only for BGR→RGB conversion inside ``infer``;
    it is not needed at import time. The backend is constructed
    once and reused across frames.
    """

    def __init__(self, asset_path: str) -> None:
        base_options = mp.tasks.BaseOptions(model_asset_path=asset_path)
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

    def infer(self, frame: np.ndarray) -> Optional[np.ndarray]:
        """Run head-pose estimation on a BGR frame.

        Returns a 4×4 numpy array when a face is found, otherwise None.
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        timestamp_ms = int(cv2.getTickCount() / cv2.getTickFrequency() * 1000)
        result = self._detector.detect_for_video(mp_image, timestamp_ms)
        if not result.face_landmarks:
            return None
        matrices = result.facial_transformation_matrixes
        if not matrices:
            return None
        return np.array(matrices[0]).reshape(4, 4)

    def close(self) -> None:
        self._detector.close()


# ---------------------------------------------------------------------------
# Public detector
# ---------------------------------------------------------------------------

class HeadPoseDetector:
    """Wraps MediaPipe FaceLandmarker; emits a ``HeadPose`` per frame.

    The public interface is unchanged: ``detect(frame) -> HeadPose | None``.
    Internally it composes an ``AssetResolver`` (picks the model path) and
    a ``DetectorBackend`` (does the inference). The rotation math lives
    in ``head_pose_geometry`` and is tested in isolation.

    Constructor accepts optional resolver/backend for dependency injection;
    defaults are the production MediaPipe adapter.
    """

    def __init__(
        self,
        resolver: Optional[AssetResolver] = None,
        backend: Optional[DetectorBackend] = None,
    ) -> None:
        if backend is not None:
            self._backend = backend
        else:
            _resolver = resolver or _default_asset_resolver()
            self._backend = MediaPipeBackend(_resolver.resolve())

    def detect(self, frame: np.ndarray) -> Optional[HeadPose]:
        """Run head-pose estimation on a BGR frame.

        Args:
            frame: BGR image from OpenCV (H×W×3), uint8.

        Returns:
            ``None`` if no face detected, otherwise a ``HeadPose`` carrying
            the sign convention documented on the class.
        """
        matrix = self._backend.infer(frame)
        if matrix is None:
            return None
        return transform_to_yaw_roll(matrix)

    def close(self) -> None:
        self._backend.close()


# ---------------------------------------------------------------------------
# Backward compatibility re-export
# ---------------------------------------------------------------------------
# The original tests import `_euler_from_rotation_matrix` from
# `eyes.detector`. Re-export it so existing tests continue to work
# without changing their import lines. New tests should import from
# `eyes.head_pose_geometry.rotation_to_yaw_roll` directly.
from .head_pose_geometry import rotation_to_yaw_roll as _euler_from_rotation_matrix  # noqa: E402

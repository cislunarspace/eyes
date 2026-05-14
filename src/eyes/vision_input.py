"""VisionInput — encapsulates camera + detector lifecycle.

Owns a CameraSource and a lazily-built HeadPoseDetector, exposing a unified
"frame ready" or "unavailable" stream. Retry attempts are throttled internally
by tick count so the host loop can call ``tick()`` every cycle without
hammering ``cv2.VideoCapture``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional, Union

import numpy as np

from .camera import CameraSource
from .detector import HeadPoseDetector


@dataclass(frozen=True)
class FrameReady:
    """Tick result when the vision pipeline produced a frame."""
    frame: np.ndarray
    just_resumed: bool = False


@dataclass(frozen=True)
class VisionUnavailable:
    """Tick result when the camera or detector cannot deliver a frame."""
    just_failed: bool = False
    detector_error: Optional[str] = None


VisionTickResult = Union[FrameReady, VisionUnavailable]


class VisionInput:
    """Camera + detector pair with availability tracking and throttled retry."""

    def __init__(
        self,
        camera: CameraSource,
        detector_factory: Callable[[], HeadPoseDetector],
        retry_interval_ticks: int = 50,
    ) -> None:
        self._camera = camera
        self._detector_factory = detector_factory
        self._detector: Optional[HeadPoseDetector] = None
        self._was_available = False
        self._retry_interval_ticks = retry_interval_ticks
        self._ticks_since_retry = 0

    @property
    def detector(self) -> Optional[HeadPoseDetector]:
        return self._detector

    @property
    def is_available(self) -> bool:
        return self._was_available

    def _ensure_detector(self) -> Optional[str]:
        """Lazily build the detector. Returns an error string on failure, else None."""
        if self._detector is not None:
            return None
        try:
            self._detector = self._detector_factory()
        except RuntimeError as exc:
            return f"MODEL_LOAD_FAILED: {exc}"
        return None

    def start(self) -> Optional[VisionUnavailable]:
        """Open the camera and build the detector. Returns None on success."""
        if not self._camera.open():
            return VisionUnavailable(just_failed=True)
        err = self._ensure_detector()
        if err is not None:
            self._camera.close()
            return VisionUnavailable(just_failed=True, detector_error=err)
        self._was_available = True
        return None

    def tick(self) -> VisionTickResult:
        """Read one frame; throttled retry when unavailable."""
        if self._camera.is_available:
            return self._read_frame()

        was_available = self._was_available
        self._was_available = False
        if was_available:
            self._ticks_since_retry = 0
            return VisionUnavailable(just_failed=True)

        self._ticks_since_retry += 1
        if self._ticks_since_retry < self._retry_interval_ticks:
            return VisionUnavailable(just_failed=False)
        self._ticks_since_retry = 0
        if not self._camera.retry_open():
            return VisionUnavailable(just_failed=False)
        err = self._ensure_detector()
        if err is not None:
            self._camera.close()
            return VisionUnavailable(just_failed=False, detector_error=err)
        result = self._read_frame()
        if isinstance(result, FrameReady):
            return FrameReady(frame=result.frame, just_resumed=True)
        return result

    def _read_frame(self) -> VisionTickResult:
        frame = self._camera.read()
        if frame is None:
            was_available = self._was_available
            self._was_available = False
            if was_available:
                self._ticks_since_retry = 0
            return VisionUnavailable(just_failed=was_available)
        was_available = self._was_available
        self._was_available = True
        return FrameReady(frame=frame, just_resumed=not was_available)

    def set_camera_index(self, index: int) -> None:
        """Switch the underlying camera to a new device index. No-op if unchanged."""
        if index == self._camera.index:
            return
        self._camera.set_index(index)

    def close(self) -> None:
        """Release camera and detector."""
        self._camera.close()
        if self._detector is not None:
            self._detector.close()
            self._detector = None
        self._was_available = False

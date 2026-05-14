"""Camera source wrapping OpenCV VideoCapture."""

from __future__ import annotations

import cv2
from typing import Optional

import numpy as np


class CameraSource:
    """Wraps cv2.VideoCapture with open/retry/close semantics.

    On read failure or open failure the source is marked unavailable.
    The caller drives re-opening via retry_open(); no internal thread is used.
    """

    def __init__(self, index: int = 0) -> None:
        self._index = index
        self._cap: Optional[cv2.VideoCapture] = None
        self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def index(self) -> int:
        """Current device index."""
        return self._index

    def open(self) -> bool:
        """Open the camera. Returns True on success."""
        self.close()
        cap = cv2.VideoCapture(self._index)
        if cap.isOpened():
            self._cap = cap
            self._available = True
            return True
        cap.release()
        self._available = False
        return False

    def retry_open(self) -> bool:
        """Attempt to (re-)open the camera. Idempotent when already open."""
        if self._available:
            return True
        return self.open()

    def read(self) -> Optional[np.ndarray]:
        """Read a frame. Returns None on failure or when unavailable."""
        if not self._available or self._cap is None:
            return None
        ok, frame = self._cap.read()
        if not ok:
            self._available = False
            return None
        # OpenCV returns BGR; keep as-is for MediaPipe
        return frame

    def close(self) -> None:
        """Release the camera."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._available = False

    def set_index(self, index: int) -> bool:
        """Close current camera and open with new index. Returns True on success."""
        self.close()
        self._index = index
        return self.open()

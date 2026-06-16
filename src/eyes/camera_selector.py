"""CameraSelector — QComboBox-backed camera picker behind a `CameraProbe` protocol.

Pulled out of `SettingsDialog._populate_camera_list` so the dialog
no longer imports `cv2` and the camera-detection logic is testable
with a fake probe. The protocol has one method:

  - `available_indices() -> list[int]` — return the camera device
    indices the OS exposes, in user-facing order.

A concrete `OpenCVCameraProbe` adapter does the actual `cv2.VideoCapture`
work (with `cv2` imported lazily so headless test runs don't need
OpenCV).
"""

from __future__ import annotations

import logging
from typing import Protocol

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox

from .i18n import t

logger = logging.getLogger(__name__)

# Maximum number of camera indices to probe. 5 is the historical value
# from the previous in-place implementation; kept as a module constant
# so tests and future tweaks don't have to grep for the magic number.
_PROBE_RANGE_SIZE = 5


class CameraProbe(Protocol):
    """Adapter for detecting available camera device indices."""

    def available_indices(self) -> list[int]:
        """Return the camera device indices the OS exposes."""
        ...


class OpenCVCameraProbe:
    """Concrete probe that uses `cv2.VideoCapture` to enumerate cameras.

    `cv2` is imported lazily so importing this module does not require
    OpenCV at module load. Tests can pass a fake `CameraProbe` to the
    selector and skip OpenCV entirely.
    """

    def __init__(self, max_index: int = _PROBE_RANGE_SIZE) -> None:
        self._max_index = max_index

    def available_indices(self) -> list[int]:
        import cv2  # noqa: PLC0415 — lazy import

        indices: list[int] = []
        for i in range(self._max_index):
            try:
                cap = cv2.VideoCapture(i)
            except Exception as exc:  # cv2 import-time failures
                logger.debug("Camera probe failed at index %d: %s", i, exc)
                break
            try:
                if cap.isOpened():
                    indices.append(i)
            finally:
                cap.release()
        return indices


class CameraSelector(QComboBox):
    """A `QComboBox` populated from a `CameraProbe` and a current selection."""

    def __init__(
        self,
        probe: CameraProbe,
        current_index: int = 0,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._probe = probe
        self.refresh(current_index)

    def refresh(self, current_index: int = 0) -> None:
        """Re-probe the cameras and re-populate the combo box.

        Selects `current_index` if present, otherwise leaves the
        combo on the first available entry.
        """
        self.clear()
        try:
            available = self._probe.available_indices()
        except Exception as exc:
            logger.error("Camera probe raised during refresh: %s", exc)
            available = []
        for idx in available:
            self.addItem(t("settings.camera_index").format(index=idx), idx)
        if available:
            target_idx = self.findData(current_index)
            if target_idx >= 0:
                self.setCurrentIndex(target_idx)
            else:
                # Current selection no longer available — fall back to
                # the first entry without changing the persisted
                # config. The settings dialog will detect this on
                # accept if the user keeps the new value.
                self.setCurrentIndex(0)

"""Main window — live webcam preview with yaw/roll readout and pose-state badge."""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCloseEvent, QImage, QPixmap
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from .camera import CameraSource
from .classifier import PoseState
from .detector import HeadPoseDetector

# Badge colour scheme per acceptance criteria
_BADGE_COLORS: dict[PoseState, tuple[str, str]] = {
    PoseState.FACING_SCREEN: ("#1a4d1a", "#00cc44"),   # dark green bg, bright green text
    PoseState.OFF_AXIS_LEFT: ("#4d1a1a", "#ff4444"),   # dark red bg, bright red text
    PoseState.OFF_AXIS_RIGHT: ("#4d1a1a", "#ff4444"),  # dark red bg, bright red text
    PoseState.OFF_AXIS_OTHER: ("#4d3d1a", "#ffaa00"),  # dark amber bg, amber text
    PoseState.NO_FACE: ("#1a1a1a", "#888888"),         # dark grey bg, grey text
}


class MainWindow(QMainWindow):
    """PySide6 main window with live preview, yaw/roll readout, and pose badge.

    Closing the window triggers QApplication quit so the process terminates
    cleanly with no orphan threads.
    """

    def __init__(self, camera_index: int = 0) -> None:
        super().__init__()
        self.setWindowTitle("Eyes")
        self.resize(QSize(800, 600))

        # Core components
        self._camera = CameraSource(index=camera_index)
        self._detector: Optional[HeadPoseDetector] = None

        # UI
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self._video_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._video_label.setMinimumSize(QSize(640, 480))
        self._video_label.setStyleSheet("background-color: #1a1a1a; color: #00ff88; font-size: 18px;")
        self._readout_label = QLabel(
            "yaw: —   roll: —",
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self._readout_label.setStyleSheet("color: #cccccc; font-size: 14px; background-color: #1a1a1a; padding: 4px;")

        self._badge_label = QLabel(
            PoseState.NO_FACE.value,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self._apply_badge_style(PoseState.NO_FACE)

        layout.addWidget(self._badge_label)
        layout.addWidget(self._video_label, stretch=1)
        layout.addWidget(self._readout_label)

    def _apply_badge_style(self, state: PoseState) -> None:
        bg, fg = _BADGE_COLORS.get(state, ("#1a1a1a", "#888888"))
        self._badge_label.setStyleSheet(
            f"background-color: {bg}; color: {fg}; "
            f"font-size: 16px; font-weight: bold; padding: 6px;"
        )

    def init_camera_and_detector(self) -> bool:
        """Open the camera and build the detector. Returns True on success."""
        if not self._camera.open():
            return False
        try:
            self._detector = HeadPoseDetector()
        except RuntimeError as exc:
            self._readout_label.setText(f"模型加载失败: {exc}")
            return False
        return True

    def set_state(
        self,
        yaw: Optional[float],
        roll: Optional[float],
        state: Optional[PoseState],
    ) -> None:
        """Update the readout label and badge from the tick loop."""
        if yaw is None or roll is None:
            self._readout_label.setText("yaw: —   roll: —")
            self._badge_label.setText(PoseState.NO_FACE.value)
            self._apply_badge_style(PoseState.NO_FACE)
        else:
            self._readout_label.setText(f"yaw: {yaw:+.1f}°   roll: {roll:+.1f}°")
            if state is not None:
                self._badge_label.setText(state.value)
                self._apply_badge_style(state)

    def update_frame(self, frame: Optional[np.ndarray]) -> None:
        """Display a BGR frame from OpenCV as a QPixmap on the video label."""
        if frame is None:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        scaled = img.scaled(
            self._video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._video_label.setPixmap(QPixmap.fromImage(scaled))

    def camera(self) -> CameraSource:
        return self._camera

    def detector(self) -> Optional[HeadPoseDetector]:
        return self._detector

    def closeEvent(self, event: QCloseEvent) -> None:
        """Clean up on window close: release camera and detector, then quit."""
        self._camera.close()
        if self._detector is not None:
            self._detector.close()
            self._detector = None
        event.accept()

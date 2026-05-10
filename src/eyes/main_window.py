"""Main window — live webcam preview with yaw/roll readout."""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCloseEvent, QImage, QPixmap
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from .camera import CameraSource
from .detector import HeadPoseDetector


class MainWindow(QMainWindow):
    """PySide6 main window with live preview and head-pose readout.

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
        layout.addWidget(self._video_label, stretch=1)
        layout.addWidget(self._readout_label)

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

    def set_pose(self, yaw: Optional[float], roll: Optional[float]) -> None:
        """Update the yaw/roll readout label from the tick loop."""
        if yaw is None or roll is None:
            self._readout_label.setText("yaw: —   roll: —")
        else:
            self._readout_label.setText(f"yaw: {yaw:+.1f}°   roll: {roll:+.1f}°")

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
        # QCoreApplication.exit is called by the controller's quit hook

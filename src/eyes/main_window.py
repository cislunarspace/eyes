"""Main window — live webcam preview with yaw/roll readout and pose-state badge."""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QImage, QPixmap
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from .classifier import PoseState
from .display_plan import (
    DisplayPlan,
    DisplayState,
    display_plan,
    initial_state,
    reduce_auto_dismiss,
    reduce_pose,
    reduce_warning,
)
from .i18n import t
from .types import WarningLevel, WarningLevelEvent


class MainWindow(QMainWindow):
    """PySide6 main window with live preview, yaw/roll readout, and pose badge.

    Closing the window emits close_requested signal. The controller decides
    whether to minimize to tray or quit.
    """

    close_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Eyes")
        self.resize(QSize(800, 600))

        self._state: DisplayState = initial_state()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self._video_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._video_label.setMinimumSize(QSize(640, 480))
        self._video_label.setStyleSheet("background-color: #1a1a1a; color: #00ff88; font-size: 18px;")
        self._readout_label = QLabel(
            t("main_window.readout_placeholder"),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self._readout_label.setStyleSheet("color: #cccccc; font-size: 14px; background-color: #1a1a1a; padding: 4px;")

        self._badge_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)

        self._camera_status_label = QLabel(
            t("main_window.camera_unavailable"),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self._camera_status_label.setStyleSheet(
            "background-color: #2a2a1a; color: #ffcc00; font-size: 16px; padding: 10px;"
        )
        self._camera_status_label.setVisible(False)
        layout.addWidget(self._camera_status_label)

        self._warning_banner = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._warning_banner.setVisible(False)
        self._auto_dismiss_timer = QTimer(self)
        self._auto_dismiss_timer.setSingleShot(True)
        self._auto_dismiss_timer.timeout.connect(self._on_auto_dismiss)

        layout.addWidget(self._badge_label)
        layout.addWidget(self._video_label, stretch=1)
        layout.addWidget(self._warning_banner)
        layout.addWidget(self._readout_label)

        self._render(display_plan(self._state))

    def _render(self, plan: DisplayPlan) -> None:
        self._badge_label.setText(t(plan.badge.text_key))
        self._badge_label.setStyleSheet(
            f"background-color: {plan.badge.bg}; color: {plan.badge.fg}; "
            f"font-size: 16px; font-weight: bold; padding: 6px;"
        )

        if plan.banner.visible:
            self._warning_banner.setText(
                "\n".join(t(key) for key in plan.banner.text_keys)
            )
            self._warning_banner.setStyleSheet(
                f"background-color: {plan.banner.bg}; color: {plan.banner.fg}; "
                f"font-size: 20px; font-weight: bold; padding: 12px;"
            )
            self._warning_banner.setVisible(True)
        else:
            self._warning_banner.setVisible(False)
            self._warning_banner.setText("")
            self._warning_banner.setStyleSheet("")

        if plan.banner.auto_dismiss_ms is not None:
            if not self._auto_dismiss_timer.isActive():
                self._auto_dismiss_timer.start(plan.banner.auto_dismiss_ms)
        else:
            self._auto_dismiss_timer.stop()

    def _on_auto_dismiss(self) -> None:
        self._state = reduce_auto_dismiss(self._state)
        self._render(display_plan(self._state))

    def show_camera_unavailable_message(self) -> None:
        self._camera_status_label.setVisible(True)

    def clear_camera_unavailable_message(self) -> None:
        self._camera_status_label.setVisible(False)

    def set_state(
        self,
        yaw: Optional[float],
        roll: Optional[float],
        state: Optional[PoseState],
    ) -> None:
        if yaw is None or roll is None:
            self._readout_label.setText(t("main_window.readout_placeholder"))
            self._state = reduce_pose(self._state, PoseState.NO_FACE)
        else:
            self._readout_label.setText(f"yaw: {yaw:+.1f}°   roll: {roll:+.1f}°")
            if state is not None:
                self._state = reduce_pose(self._state, state)
        self._render(display_plan(self._state))

    def update_frame(self, frame: Optional[np.ndarray]) -> None:
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

    def refresh_language(self) -> None:
        self._camera_status_label.setText(t("main_window.camera_unavailable"))
        if (
            self._state.warning_level == WarningLevel.NORMAL
            and self._state.pose_state == PoseState.NO_FACE
        ):
            self._readout_label.setText(t("main_window.readout_placeholder"))
        self._render(display_plan(self._state))

    def closeEvent(self, event: QCloseEvent) -> None:
        self.close_requested.emit()
        event.ignore()

    def set_warning_level(self, event: WarningLevelEvent) -> None:
        self._state = reduce_warning(self._state, event)
        self._render(display_plan(self._state))

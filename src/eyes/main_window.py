"""Main window — live webcam preview with yaw/roll readout and pose-state badge."""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QImage, QPixmap
from PySide6.QtWidgets import QLabel, QMainWindow, QVBoxLayout, QWidget

from .classifier import PoseState
from .i18n import t
from .types import WarningLevel, WarningLevelEvent

# Badge colour scheme per acceptance criteria
_BADGE_COLORS: dict[PoseState, tuple[str, str]] = {
    PoseState.FACING_SCREEN: ("#1a4d1a", "#00cc44"),   # dark green bg, bright green text
    PoseState.OFF_AXIS_LEFT: ("#4d1a1a", "#ff4444"),   # dark red bg, bright red text
    PoseState.OFF_AXIS_RIGHT: ("#4d1a1a", "#ff4444"),  # dark red bg, bright red text
    PoseState.OFF_AXIS_OTHER: ("#4d3d1a", "#ffaa00"),  # dark amber bg, amber text
    PoseState.NO_FACE: ("#1a1a1a", "#888888"),         # dark grey bg, grey text
}

_BADGE_KEYS: dict[PoseState, str] = {
    PoseState.FACING_SCREEN: "badge.facing_screen",
    PoseState.OFF_AXIS_LEFT: "badge.off_axis_left",
    PoseState.OFF_AXIS_RIGHT: "badge.off_axis_right",
    PoseState.OFF_AXIS_OTHER: "badge.off_axis_other",
    PoseState.NO_FACE: "badge.no_face",
}


def _badge_text(state: PoseState) -> str:
    return t(_BADGE_KEYS[state])


class MainWindow(QMainWindow):
    """PySide6 main window with live preview, yaw/roll readout, and pose badge.

    Closing the window emits close_requested signal. The controller decides
    whether to minimize to tray or quit.
    """

    # Signal emitted when user tries to close the window
    close_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Eyes")
        self.resize(QSize(800, 600))

        # Track last pose state for refresh_language
        self._last_pose_state: PoseState = PoseState.NO_FACE
        self._active_warning_level = WarningLevel.NORMAL
        self._last_direction: Optional[str] = None

        # UI
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

        self._badge_label = QLabel(
            _badge_text(PoseState.NO_FACE),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self._apply_badge_style(PoseState.NO_FACE)

        # Camera unavailable status label (hidden by default)
        self._camera_status_label = QLabel(
            t("main_window.camera_unavailable"),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self._camera_status_label.setStyleSheet(
            "background-color: #2a2a1a; color: #ffcc00; font-size: 16px; padding: 10px;"
        )
        self._camera_status_label.setVisible(False)
        layout.addWidget(self._camera_status_label)

        # Warning banner (hidden by default, overlaid at bottom of video area)
        self._warning_banner = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._warning_banner.setVisible(False)
        self._corrected_timer = QTimer(self)
        self._corrected_timer.setSingleShot(True)
        self._corrected_timer.setInterval(2000)
        self._corrected_timer.timeout.connect(self._hide_warning_banner)

        layout.addWidget(self._badge_label)
        layout.addWidget(self._video_label, stretch=1)
        layout.addWidget(self._warning_banner)
        layout.addWidget(self._readout_label)

    def _apply_badge_style(self, state: PoseState) -> None:
        """Apply colour scheme for the pose-state badge based on current state."""
        bg, fg = _BADGE_COLORS.get(state, ("#1a1a1a", "#888888"))
        self._badge_label.setStyleSheet(
            f"background-color: {bg}; color: {fg}; "
            f"font-size: 16px; font-weight: bold; padding: 6px;"
        )

    def show_camera_unavailable_message(self) -> None:
        """Show the camera unavailable status message."""
        self._camera_status_label.setVisible(True)

    def clear_camera_unavailable_message(self) -> None:
        """Hide the camera unavailable status message."""
        self._camera_status_label.setVisible(False)

    def set_state(
        self,
        yaw: Optional[float],
        roll: Optional[float],
        state: Optional[PoseState],
    ) -> None:
        """Update the readout label and badge from the tick loop."""
        if yaw is None or roll is None:
            self._last_pose_state = PoseState.NO_FACE
            self._readout_label.setText(t("main_window.readout_placeholder"))
            self._badge_label.setText(_badge_text(PoseState.NO_FACE))
            self._apply_badge_style(PoseState.NO_FACE)
        else:
            self._readout_label.setText(f"yaw: {yaw:+.1f}°   roll: {roll:+.1f}°")
            if state is not None:
                self._last_pose_state = state
                self._badge_label.setText(_badge_text(state))
                if self._active_warning_level == WarningLevel.NORMAL:
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

    def refresh_language(self) -> None:
        """Update all display text after language change."""
        self._badge_label.setText(_badge_text(self._last_pose_state))
        self._camera_status_label.setText(t("main_window.camera_unavailable"))
        if self._active_warning_level == WarningLevel.NORMAL:
            if self._last_pose_state == PoseState.NO_FACE:
                self._readout_label.setText(t("main_window.readout_placeholder"))
        elif self._active_warning_level == WarningLevel.CORRECTED:
            self._warning_banner.setText(t("main_window.posture_good"))
        elif self._active_warning_level in (WarningLevel.WARNING, WarningLevel.SEVERE):
            self._warning_banner.setText(self._rebuild_warning_text())

    def closeEvent(self, event: QCloseEvent) -> None:
        """Emit close_requested signal instead of accepting the event directly."""
        self.close_requested.emit()
        event.ignore()

    def _hide_warning_banner(self) -> None:
        """Dismiss the banner only when the level is still CORRECTED."""
        if self._active_warning_level != WarningLevel.CORRECTED:
            return
        self._active_warning_level = WarningLevel.NORMAL
        self._warning_banner.setVisible(False)
        self._apply_badge_style(self._last_pose_state)

    def _rebuild_warning_text(self) -> str:
        """Build warning banner text from current state."""
        line1 = t("main_window.please_face_screen")
        if self._last_direction == "left":
            line2 = t("main_window.adjust_left_hint")
        else:
            line2 = t("main_window.adjust_right_hint")
        return f"{line1}\n{line2}"

    def set_warning_level(self, event: WarningLevelEvent) -> None:
        """Drive the warning banner through its full lifecycle."""
        level, direction = event.level, event.direction

        if level == WarningLevel.NORMAL:
            self._active_warning_level = WarningLevel.NORMAL
            self._corrected_timer.stop()
            self._warning_banner.setVisible(False)
            self._apply_badge_style(self._last_pose_state)
            return

        if level in (WarningLevel.WARNING, WarningLevel.SEVERE):
            self._corrected_timer.stop()
            self._last_direction = direction

        if level == WarningLevel.WARNING:
            bg = "#FFD700"
            fg = "#000000"
            text = self._rebuild_warning_text()
        elif level == WarningLevel.SEVERE:
            bg = "#FF0000"
            fg = "#FFFFFF"
            text = self._rebuild_warning_text()
        elif level == WarningLevel.CORRECTED:
            bg = "#00AA00"
            fg = "#FFFFFF"
            text = t("main_window.posture_good")
        else:
            return

        self._active_warning_level = level
        self._warning_banner.setText(text)
        self._warning_banner.setStyleSheet(
            f"background-color: {bg}; color: {fg}; "
            f"font-size: 20px; font-weight: bold; padding: 12px;"
        )
        self._warning_banner.setVisible(True)

        self._badge_label.setStyleSheet(
            f"background-color: {bg}; color: {fg}; "
            f"font-size: 16px; font-weight: bold; padding: 6px;"
        )

        if level == WarningLevel.CORRECTED:
            self._corrected_timer.start()

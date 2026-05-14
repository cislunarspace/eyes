"""NotifierOverlay — always-on-top floating window for correction prompts."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from .classifier import PoseState

# Message and arrow mapping
_MESSAGES: dict[PoseState, tuple[str, str]] = {
    PoseState.OFF_AXIS_LEFT: ("←", "向左调整"),
    PoseState.OFF_AXIS_RIGHT: ("→", "向右调整"),
}

# Special event messages (not tied to PoseState)
_EVENT_MESSAGES: dict[str, tuple[str, str]] = {
    "GOOD_POSTURE": ("✓", "当前姿势良好"),
    "EYE_REST": ("👀", "请眺望远方"),
}

_AUTO_DISMISS_MS = 4000


class NotifierOverlay(QWidget):
    """Frameless, always-on-top notification window for corrective prompts.

    Shows directional arrow and Chinese text for off-axis corrections.
    Auto-dismisses after a few seconds.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._setup_ui()
        self._dismiss_timer = QTimer()
        self._dismiss_timer.timeout.connect(self.hide)
        self._move_to_active_screen()

    def _setup_ui(self) -> None:
        """Create the overlay layout with a large arrow label and a text label below it."""
        self.setMinimumWidth(260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        self._arrow_label = QLabel()
        self._arrow_label.setStyleSheet(
            "font-size: 48px; color: #ff4444; background: transparent;"
        )
        self._arrow_label.setAlignment(Qt.AlignCenter)

        self._text_label = QLabel()
        self._text_label.setStyleSheet(
            "font-size: 20px; color: #ffffff; background: transparent; font-weight: bold;"
        )
        self._text_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self._arrow_label)
        layout.addWidget(self._text_label)

        self.setStyleSheet(
            "background-color: rgba(20, 20, 20, 0.92); "
            "border-radius: 12px; border: 1px solid rgba(255, 68, 68, 0.6);"
        )

    def _move_to_active_screen(self) -> None:
        """Position the overlay at bottom-center of the primary screen."""
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + geo.height() - self.height() - 24
        self.move(x, y)

    def show_correction(self, direction: PoseState) -> None:
        """Show correction prompt for the given direction."""
        if direction not in _MESSAGES:
            return

        arrow, text = _MESSAGES[direction]
        self._arrow_label.setText(arrow)
        self._text_label.setText(text)

        self._move_to_active_screen()
        self.show()
        self.raise_()
        self.activateWindow()

        self._dismiss_timer.start(_AUTO_DISMISS_MS)

    def show_good_posture(self) -> None:
        """Show good posture encouragement."""
        arrow, text = _EVENT_MESSAGES["GOOD_POSTURE"]
        self._arrow_label.setText(arrow)
        self._text_label.setText(text)

        self._move_to_active_screen()
        self.show()
        self.raise_()
        self.activateWindow()

        self._dismiss_timer.start(_AUTO_DISMISS_MS)

    def show_eye_rest(self) -> None:
        """Show eye rest reminder."""
        arrow, text = _EVENT_MESSAGES["EYE_REST"]
        self._arrow_label.setText(arrow)
        self._text_label.setText(text)

        self._move_to_active_screen()
        self.show()
        self.raise_()
        self.activateWindow()

        self._dismiss_timer.start(_AUTO_DISMISS_MS)

    def hide(self) -> None:
        """Hide the overlay and stop the dismiss timer."""
        self._dismiss_timer.stop()
        super().hide()

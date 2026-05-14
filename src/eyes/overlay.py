"""NotifierOverlay — always-on-top floating window for correction prompts."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from .classifier import PoseState
from .i18n import t

# Arrow mapping (language-independent symbols)
_ARROWS: dict[PoseState, str] = {
    PoseState.OFF_AXIS_LEFT: "←",
    PoseState.OFF_AXIS_RIGHT: "→",
}

_EVENT_ARROWS: dict[str, str] = {
    "GOOD_POSTURE": "✓",
    "EYE_REST": "👀",
    "CORRECTED": "✓",
}

_AUTO_DISMISS_MS = 4000
_CORRECTED_DISMISS_MS = 1500


class NotifierOverlay(QWidget):
    """Frameless, always-on-top notification window for corrective prompts.

    Shows directional arrow and translated text for off-axis corrections.
    Auto-dismisses after a few seconds.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.Tool)
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus)
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

    @staticmethod
    def _correction_text(direction: PoseState) -> str:
        mapping = {
            PoseState.OFF_AXIS_LEFT: t("overlay.adjust_left"),
            PoseState.OFF_AXIS_RIGHT: t("overlay.adjust_right"),
        }
        return mapping[direction]

    @staticmethod
    def _event_text(event_type: str) -> str:
        mapping = {
            "GOOD_POSTURE": t("overlay.good_posture"),
            "EYE_REST": t("overlay.eye_rest"),
            "CORRECTED": t("overlay.corrected"),
        }
        return mapping[event_type]

    def show_correction(self, direction: PoseState) -> None:
        """Show correction prompt for the given direction."""
        if direction not in _ARROWS:
            return

        self._arrow_label.setText(_ARROWS[direction])
        self._text_label.setText(self._correction_text(direction))

        self._move_to_active_screen()
        self.show()
        self.raise_()

    def show_good_posture(self) -> None:
        """Show good posture encouragement."""
        self._arrow_label.setText(_EVENT_ARROWS["GOOD_POSTURE"])
        self._text_label.setText(self._event_text("GOOD_POSTURE"))

        self._move_to_active_screen()
        self.show()
        self.raise_()

        self._dismiss_timer.start(_AUTO_DISMISS_MS)

    def show_eye_rest(self) -> None:
        """Show eye rest reminder."""
        self._arrow_label.setText(_EVENT_ARROWS["EYE_REST"])
        self._text_label.setText(self._event_text("EYE_REST"))

        self._move_to_active_screen()
        self.show()
        self.raise_()

        self._dismiss_timer.start(_AUTO_DISMISS_MS)

    def show_corrected(self) -> None:
        """Show posture corrected feedback, auto-dismisses after 1.5 seconds."""
        self._arrow_label.setText(_EVENT_ARROWS["CORRECTED"])
        self._text_label.setText(self._event_text("CORRECTED"))

        self._move_to_active_screen()
        self.show()
        self.raise_()

        self._dismiss_timer.start(_CORRECTED_DISMISS_MS)

    def hide(self) -> None:
        """Hide the overlay and stop the dismiss timer."""
        self._dismiss_timer.stop()
        super().hide()

    def refresh_language(self) -> None:
        """Refresh overlay text after language change.

        Text is updated dynamically via t() on each show_*() call,
        so no cached state needs updating.
        """
        pass

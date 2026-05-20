"""NotifierOverlay — always-on-top floating window for correction prompts."""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPoint, QPropertyAnimation, Qt, QTimer
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
_ANIMATION_MS = 180
_SLIDE_OFFSET_PX = 10


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
        self._setup_animation()
        self._dismiss_timer = QTimer()
        self._dismiss_timer.timeout.connect(self.hide)
        self._move_to_active_screen()

    def _setup_ui(self) -> None:
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(6)

        self._arrow_label = QLabel()
        self._arrow_label.setStyleSheet(
            "font-size: 40px; color: #46D3B5; background: transparent; font-weight: 700;"
        )
        self._arrow_label.setAlignment(Qt.AlignCenter)

        self._text_label = QLabel()
        self._text_label.setStyleSheet(
            "font-size: 18px; color: #EAFBF7; background: transparent; font-weight: 600;"
        )
        self._text_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self._arrow_label)
        layout.addWidget(self._text_label)

        self.setStyleSheet(
            "background-color: rgba(8, 20, 22, 0.94); "
            "border-radius: 18px; "
            "border: 1px solid rgba(70, 211, 181, 0.5);"
        )

    def _setup_animation(self) -> None:
        self._fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self._fade_animation.setDuration(_ANIMATION_MS)
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._slide_animation = QPropertyAnimation(self, b"pos")
        self._slide_animation.setDuration(_ANIMATION_MS)
        self._slide_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._show_animation = QParallelAnimationGroup(self)
        self._show_animation.addAnimation(self._fade_animation)
        self._show_animation.addAnimation(self._slide_animation)

    def _move_to_active_screen(self) -> None:
        """Position the overlay at bottom-center of the primary screen."""
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + geo.height() - self.height() - 24
        self.move(x, y)

    def _show_with_animation(self) -> None:
        self.adjustSize()
        self._move_to_active_screen()
        end_pos = self.pos()
        start_pos = QPoint(end_pos.x(), end_pos.y() + _SLIDE_OFFSET_PX)

        self._show_animation.stop()
        self.setWindowOpacity(0.0)
        self.move(start_pos)
        self._slide_animation.setStartValue(start_pos)
        self._slide_animation.setEndValue(end_pos)

        self.show()
        self.raise_()
        self._show_animation.start()

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

        self._show_with_animation()

    def show_good_posture(self) -> None:
        """Show good posture encouragement."""
        self._arrow_label.setText(_EVENT_ARROWS["GOOD_POSTURE"])
        self._text_label.setText(self._event_text("GOOD_POSTURE"))

        self._show_with_animation()

        self._dismiss_timer.start(_AUTO_DISMISS_MS)

    def show_eye_rest(self) -> None:
        """Show eye rest reminder."""
        self._arrow_label.setText(_EVENT_ARROWS["EYE_REST"])
        self._text_label.setText(self._event_text("EYE_REST"))

        self._show_with_animation()

        self._dismiss_timer.start(_AUTO_DISMISS_MS)

    def show_corrected(self) -> None:
        """Show posture corrected feedback, auto-dismisses after 1.5 seconds."""
        self._arrow_label.setText(_EVENT_ARROWS["CORRECTED"])
        self._text_label.setText(self._event_text("CORRECTED"))

        self._show_with_animation()

        self._dismiss_timer.start(_CORRECTED_DISMISS_MS)

    def hide(self) -> None:
        """Hide the overlay and stop the dismiss timer."""
        self._show_animation.stop()
        self.setWindowOpacity(1.0)
        self._dismiss_timer.stop()
        super().hide()

    def refresh_language(self) -> None:
        """Refresh overlay text after language change.

        Text is updated dynamically via t() on each show_*() call,
        so no cached state needs updating.
        """
        pass

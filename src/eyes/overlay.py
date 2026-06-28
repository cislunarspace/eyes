"""NotifierOverlay — altgo-style always-on-top floating prompt.

A frameless, always-on-top island that shows posture prompts as a single
horizontal pill: a small status indicator (arrow / check / eye) on the
left, the translated text on the right. The visual design is borrowed
from altgo's overlay:

  - Pill shape (border-radius: 9999px), small padding, single line.
  - Token-based dark theme: a solid deep base, subtle 1px border, soft
    shadow. No alpha-over-alpha compositing with the shadow (the altgo
    bug we explicitly inherited the fix for).
  - 180 ms enter/exit animation: translateY(8px) + opacity 0→1, easing
    curve OutCubic. Only transform and opacity are animated (composite
    layer only).
  - Status indicator: a small circle with an inner glyph; color is
    semantic per variant (warning amber / success green / neutral).

The overlay's public surface is unchanged: `show_correction`,
`show_good_posture`, `show_eye_rest`, `show_corrected`, `hide`,
`refresh_language`. Auto-dismiss timing for `show_corrected` is
1.5 s; the others stay until the next call (or `hide`).
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QWidget

from .classifier import PoseState
from .i18n import t

# Auto-dismiss timing.
_AUTO_DISMISS_MS = 4000
_CORRECTED_DISMISS_MS = 1500

# Animation timing — keep aligned with altgo's --duration-normal.
_ANIMATION_MS = 180
_SLIDE_OFFSET_PX = 8

# Visual tokens — altgo-style dark island. Light theme comes from a
# light-mode override applied via a single stylesheet swap.
_DARK_BASE = "rgb(22, 22, 28)"  # overlay-surface-solid (altgo dark)
_DARK_BORDER = "rgba(255, 255, 255, 0.12)"
_DARK_TEXT = "rgba(244, 244, 245, 0.94)"
_LIGHT_BASE = "rgb(248, 248, 250)"
_LIGHT_BORDER = "rgba(24, 24, 27, 0.12)"
_LIGHT_TEXT = "rgba(24, 24, 27, 0.92)"

# Variant palette — semantic, not raw hex strings.
_VARIANT_BG = {
    "correction": "rgba(251, 191, 36, 0.12)",  # amber
    "good_posture": "rgba(52, 211, 153, 0.12)",  # green
    "eye_rest": "rgba(129, 140, 248, 0.12)",  # indigo (altgo's accent)
    "corrected": "rgba(52, 211, 153, 0.12)",  # green
}
_VARIANT_GLYPH = {
    "correction": "#fbbf24",  # amber
    "good_posture": "#34d399",  # green
    "eye_rest": "#818cf8",  # indigo
    "corrected": "#34d399",  # green
}

# Variant → arrow / glyph text shown in the indicator.
_VARIANT_GLYPH_TEXT = {
    "correction_left": "←",
    "correction_right": "→",
    "correction_up": "↑",
    "correction_down": "↓",
    "good_posture": "✓",
    "eye_rest": "◌",  # empty ring to read as a distant gaze hint
    "corrected": "✓",
}

# Variant → i18n key. Kept aligned with the existing translation table.
_VARIANT_TEXT_KEY = {
    "correction_left": "overlay.adjust_left",
    "correction_right": "overlay.adjust_right",
    "correction_up": "overlay.adjust_down",  # 仰头 → 向下看
    "correction_down": "overlay.adjust_up",  # 低头 → 向上看
    "good_posture": "overlay.good_posture",
    "eye_rest": "overlay.eye_rest",
    "corrected": "overlay.corrected",
}


class NotifierOverlay(QWidget):
    """Frameless, always-on-top notification island for posture prompts."""

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

    # --- UI setup ---

    def _setup_ui(self) -> None:
        """Build the pill: a 16x16 status circle on the left, label on the right."""
        self.setMinimumWidth(220)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 18, 10)
        layout.setSpacing(10)

        self._indicator = QLabel()
        self._indicator.setFixedSize(20, 20)
        self._indicator.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        self._indicator.setFont(font)

        self._text_label = QLabel()
        self._text_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        text_font = QFont()
        text_font.setPointSize(10)
        text_font.setWeight(QFont.Weight.DemiBold)
        self._text_label.setFont(text_font)

        layout.addWidget(self._indicator)
        layout.addWidget(self._text_label)
        layout.addStretch(1)

        self._apply_theme("dark")

    def _apply_theme(self, theme: str) -> None:
        """Apply the altgo island stylesheet for the requested theme.

        Qt stylesheets don't support box-shadow, so depth comes from the
        solid surface (avoids alpha-over-alpha compositing with the WA
        shadow, which produced black fringes in altgo) plus the 1px
        subtle border.
        """
        if theme == "light":
            base, border, text = _LIGHT_BASE, _LIGHT_BORDER, _LIGHT_TEXT
        else:
            base, border, text = _DARK_BASE, _DARK_BORDER, _DARK_TEXT
        self.setStyleSheet(
            f"background-color: {base}; "
            f"border-radius: 9999px; "
            f"border: 1px solid {border};"
        )
        self._text_label.setStyleSheet(f"color: {text}; background: transparent;")
        self._indicator.setStyleSheet("background: transparent;")

    def _apply_variant(self, variant: str) -> None:
        """Set the indicator background and glyph for a prompt variant."""
        bg = _VARIANT_BG.get(variant, _VARIANT_BG["good_posture"])
        glyph_color = _VARIANT_GLYPH.get(variant, _VARIANT_GLYPH["good_posture"])
        self._indicator.setStyleSheet(
            f"background-color: {bg}; "
            f"color: {glyph_color}; "
            f"border-radius: 10px;"
        )
        glyph = _VARIANT_GLYPH_TEXT.get(variant, "")
        self._indicator.setText(glyph)

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

    # --- Public surface (unchanged contract) ---

    def show_correction(self, direction: PoseState) -> None:
        """Show correction prompt for the given direction."""
        if direction == PoseState.OFF_AXIS_LEFT:
            variant = "correction_left"
        elif direction == PoseState.OFF_AXIS_RIGHT:
            variant = "correction_right"
        elif direction == PoseState.HEAD_UP:
            variant = "correction_up"
        elif direction == PoseState.HEAD_DOWN:
            variant = "correction_down"
        else:
            return

        self._apply_variant("correction")
        self._indicator.setText(_VARIANT_GLYPH_TEXT[variant])
        self._text_label.setText(t(_VARIANT_TEXT_KEY[variant]))
        self._dismiss_timer.stop()
        self._show_with_animation()

    def show_good_posture(self) -> None:
        """Show good-posture encouragement; auto-dismisses."""
        self._apply_variant("good_posture")
        self._indicator.setText(_VARIANT_GLYPH_TEXT["good_posture"])
        self._text_label.setText(t(_VARIANT_TEXT_KEY["good_posture"]))
        self._show_with_animation()
        self._dismiss_timer.start(_AUTO_DISMISS_MS)

    def show_eye_rest(self) -> None:
        """Show eye-rest reminder; auto-dismisses."""
        self._apply_variant("eye_rest")
        self._indicator.setText(_VARIANT_GLYPH_TEXT["eye_rest"])
        self._text_label.setText(t(_VARIANT_TEXT_KEY["eye_rest"]))
        self._show_with_animation()
        self._dismiss_timer.start(_AUTO_DISMISS_MS)

    def show_corrected(self) -> None:
        """Show posture-corrected feedback; auto-dismisses after 1.5 s."""
        self._apply_variant("corrected")
        self._indicator.setText(_VARIANT_GLYPH_TEXT["corrected"])
        self._text_label.setText(t(_VARIANT_TEXT_KEY["corrected"]))
        self._show_with_animation()
        self._dismiss_timer.start(_CORRECTED_DISMISS_MS)

    def hide(self) -> None:  # type: ignore[override]
        """Hide the overlay and stop the dismiss timer."""
        self._show_animation.stop()
        self.setWindowOpacity(1.0)
        self._dismiss_timer.stop()
        super().hide()

    def refresh_language(self) -> None:
        """No-op: text is read from t() on every show_*() call."""
        pass

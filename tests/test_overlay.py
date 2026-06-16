"""Tests for NotifierOverlay — pill-style island overlay (altgo design).

Behavior under test (preserved from the previous design):

  - show_correction has no auto-dismiss timer; stays visible until next call.
  - show_corrected auto-dismisses after 1.5 s.
  - show_good_posture / show_eye_rest auto-dismiss after 4 s.
  - Overlay never accepts keyboard focus.
  - Overlay is positioned at bottom-center of the primary screen.
  - All prompts go through t() for translation; refresh_language()
    re-reads t() on the next show_*() call.
  - Enter/exit animation is 180 ms (altgo --duration-normal).

Visual contract (updated to the altgo pill design):

  - Single horizontal pill: small status indicator + label.
  - Border radius 9999px (full pill).
  - Dark surface: rgb(22, 22, 28) (overlay-surface-solid).
  - 1px subtle border, soft shadow.
  - Status indicator is a 20x20 circle with a glyph; the glyph is
    direction-aware for corrections.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from eyes.classifier import PoseState
from eyes.i18n import set_language
from eyes.overlay import NotifierOverlay


# Variant → expected indicator glyph (text inside the small circle).
_EXPECTED_GLYPH = {
    "correction_left": "←",
    "correction_right": "→",
    "good_posture": "✓",
    "eye_rest": "◌",
    "corrected": "✓",
}


class TestOverlayLayout:
    """Verify the pill layout properties."""

    def test_minimum_width_is_220(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)

        assert overlay.minimumWidth() == 220

    def test_uses_altgo_island_styling(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)

        stylesheet = overlay.styleSheet()
        # Pill shape (altgo: --radius-full / 9999px).
        assert "border-radius: 9999px" in stylesheet
        # Solid dark surface (altgo overlay-surface-solid).
        assert "rgb(22, 22, 28)" in stylesheet
        # 1px subtle border.
        assert "1px solid" in stylesheet
        assert "rgba(255, 255, 255, 0.12)" in stylesheet

    def test_show_animation_is_altgo_timing(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)

        # altgo's --duration-normal is 180ms.
        assert overlay._fade_animation.duration() == 180
        assert overlay._slide_animation.duration() == 180

    def test_has_status_indicator_and_label(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)

        assert hasattr(overlay, "_indicator")
        assert hasattr(overlay, "_text_label")
        assert overlay._indicator.width() == 20
        assert overlay._indicator.height() == 20


class TestCorrectionDismissBehavior:
    """Auto-dismiss timing."""

    def test_show_correction_does_not_start_dismiss_timer(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_correction(PoseState.OFF_AXIS_LEFT)

        assert not overlay._dismiss_timer.isActive()

    def test_show_correction_stays_visible_beyond_4s(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_correction(PoseState.OFF_AXIS_LEFT)

        qtbot.wait(4200)

        assert overlay.isVisible()

    def test_show_corrected_starts_1_5s_timer(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_corrected()

        assert overlay._dismiss_timer.isActive()
        assert overlay._dismiss_timer.interval() == 1500

    def test_show_corrected_displays_corrected_glyph_and_text(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_corrected()

        assert overlay._indicator.text() == _EXPECTED_GLYPH["corrected"]
        assert "姿势良好" in overlay._text_label.text()

    def test_show_corrected_auto_hides_after_1_5s(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_corrected()

        qtbot.wait(1600)

        assert not overlay.isVisible()

    def test_show_good_posture_still_auto_dismisses(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_good_posture()

        qtbot.wait(4200)

        assert not overlay.isVisible()

    def test_show_eye_rest_still_auto_dismisses(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_eye_rest()

        qtbot.wait(4200)

        assert not overlay.isVisible()


class TestOverlayNoFocus:
    """Verify overlay never accepts keyboard focus (issue #49)."""

    def test_has_window_does_not_accept_focus_flag(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)

        assert overlay.windowFlags() & Qt.WindowType.WindowDoesNotAcceptFocus


class TestOverlayPositioning:
    """Verify overlay is positioned at bottom-center of primary screen."""

    def test_positioned_at_bottom_center(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show()
        overlay.adjustSize()
        overlay._move_to_active_screen()

        screen = QApplication.primaryScreen()
        assert screen is not None
        geo = screen.availableGeometry()

        expected_x = geo.x() + (geo.width() - overlay.width()) // 2
        expected_y = geo.y() + geo.height() - overlay.height() - 24

        assert overlay.x() == expected_x
        assert overlay.y() == expected_y

    def test_show_correction_repositions_to_bottom_center(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show()

        overlay.show_correction(PoseState.OFF_AXIS_LEFT)
        qtbot.wait(220)

        screen = QApplication.primaryScreen()
        assert screen is not None
        geo = screen.availableGeometry()

        expected_x = geo.x() + (geo.width() - overlay.width()) // 2
        expected_y = geo.y() + geo.height() - overlay.height() - 24

        assert overlay.x() == expected_x
        assert overlay.y() == expected_y

    def test_first_show_correction_repositions_to_bottom_center(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)

        overlay.show_correction(PoseState.OFF_AXIS_LEFT)
        qtbot.wait(220)

        screen = QApplication.primaryScreen()
        assert screen is not None
        geo = screen.availableGeometry()

        expected_x = geo.x() + (geo.width() - overlay.width()) // 2
        expected_y = geo.y() + geo.height() - overlay.height() - 24

        assert overlay.x() == expected_x
        assert overlay.y() == expected_y


class TestOverlayI18n:
    """Verify overlay messages use t() for translations."""

    def teardown_method(self) -> None:
        set_language("zh-CN")

    def test_correction_left_in_chinese(self, qtbot) -> None:
        set_language("zh-CN")
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_correction(PoseState.OFF_AXIS_LEFT)
        assert overlay._indicator.text() == "←"
        assert overlay._text_label.text() == "向左调整"

    def test_correction_left_in_english(self, qtbot) -> None:
        set_language("en")
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_correction(PoseState.OFF_AXIS_LEFT)
        assert overlay._indicator.text() == "←"
        assert overlay._text_label.text() == "Adjust Left"

    def test_correction_right_in_english(self, qtbot) -> None:
        set_language("en")
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_correction(PoseState.OFF_AXIS_RIGHT)
        assert overlay._indicator.text() == "→"
        assert overlay._text_label.text() == "Adjust Right"

    def test_good_posture_in_english(self, qtbot) -> None:
        set_language("en")
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_good_posture()
        assert overlay._indicator.text() == "✓"
        assert overlay._text_label.text() == "Good Posture"

    def test_eye_rest_in_english(self, qtbot) -> None:
        set_language("en")
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_eye_rest()
        assert overlay._indicator.text() == "◌"
        assert overlay._text_label.text() == "Look Into the Distance"

    def test_corrected_in_english(self, qtbot) -> None:
        set_language("en")
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_corrected()
        assert overlay._indicator.text() == "✓"
        assert overlay._text_label.text() == "Posture Corrected"

    def test_refresh_language_updates_correction_text(self, qtbot) -> None:
        set_language("zh-CN")
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_correction(PoseState.OFF_AXIS_LEFT)
        assert overlay._text_label.text() == "向左调整"

        set_language("en")
        overlay.refresh_language()
        overlay.show_correction(PoseState.OFF_AXIS_LEFT)
        assert overlay._text_label.text() == "Adjust Left"

    def test_refresh_language_updates_good_posture_text(self, qtbot) -> None:
        set_language("zh-CN")
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_good_posture()
        assert overlay._text_label.text() == "当前姿势良好"

        set_language("en")
        overlay.refresh_language()
        overlay.show_good_posture()
        assert overlay._text_label.text() == "Good Posture"

    def test_arrows_unchanged_by_language(self, qtbot) -> None:
        set_language("en")
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_correction(PoseState.OFF_AXIS_LEFT)
        assert overlay._indicator.text() == "←"
        overlay.show_correction(PoseState.OFF_AXIS_RIGHT)
        assert overlay._indicator.text() == "→"

"""Tests for NotifierOverlay positioning, layout, and i18n (issues #40, #56)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from eyes.classifier import PoseState
from eyes.i18n import set_language
from eyes.overlay import NotifierOverlay


class TestOverlayLayout:
    """Verify overlay layout properties."""

    def test_minimum_width_is_260(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)

        assert overlay.minimumWidth() == 260


class TestCorrectionDismissBehavior:
    """Verify show_correction() stays visible (no auto-dismiss) and show_corrected() auto-dismisses."""

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

    def test_show_corrected_displays_good_posture_text(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_corrected()

        assert "✓" in overlay._arrow_label.text()
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
        assert overlay._arrow_label.text() == "←"
        assert overlay._text_label.text() == "向左调整"

    def test_correction_left_in_english(self, qtbot) -> None:
        set_language("en")
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_correction(PoseState.OFF_AXIS_LEFT)
        assert overlay._arrow_label.text() == "←"
        assert overlay._text_label.text() == "Adjust Left"

    def test_correction_right_in_english(self, qtbot) -> None:
        set_language("en")
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_correction(PoseState.OFF_AXIS_RIGHT)
        assert overlay._arrow_label.text() == "→"
        assert overlay._text_label.text() == "Adjust Right"

    def test_good_posture_in_english(self, qtbot) -> None:
        set_language("en")
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_good_posture()
        assert overlay._arrow_label.text() == "✓"
        assert overlay._text_label.text() == "Good Posture"

    def test_eye_rest_in_english(self, qtbot) -> None:
        set_language("en")
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_eye_rest()
        assert overlay._arrow_label.text() == "👀"
        assert overlay._text_label.text() == "Look Into the Distance"

    def test_corrected_in_english(self, qtbot) -> None:
        set_language("en")
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        overlay.show_corrected()
        assert overlay._arrow_label.text() == "✓"
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
        assert overlay._arrow_label.text() == "←"
        overlay.show_correction(PoseState.OFF_AXIS_RIGHT)
        assert overlay._arrow_label.text() == "→"

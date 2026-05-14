"""Tests for NotifierOverlay positioning and layout (issue #40)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from eyes.classifier import PoseState
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

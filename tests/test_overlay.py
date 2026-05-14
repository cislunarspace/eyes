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

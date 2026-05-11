"""Tests for MainWindow warning banner behavior (issue #26)."""

from __future__ import annotations

import pytest

from eyes.main_window import MainWindow
from eyes.types import WarningLevel, WarningLevelEvent


class TestWarningBanner:
    """Verify banner visibility, color, and text per warning level."""

    def test_warning_left_shows_yellow_banner(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.set_warning_level(WarningLevelEvent(level=WarningLevel.WARNING, direction="left"))

        banner = window._warning_banner
        assert banner.isVisible()
        assert "#FFD700" in banner.styleSheet()  # yellow background
        assert "请正视屏幕" in banner.text()
        assert "← 请向左调整" in banner.text()

    def test_severe_right_shows_red_banner(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.set_warning_level(WarningLevelEvent(level=WarningLevel.SEVERE, direction="right"))

        banner = window._warning_banner
        assert banner.isVisible()
        assert "#FF0000" in banner.styleSheet()
        assert "请正视屏幕" in banner.text()
        assert "→ 请向右调整" in banner.text()

    def test_corrected_shows_green_banner_then_hides(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.set_warning_level(WarningLevelEvent(level=WarningLevel.CORRECTED, direction=None))

        banner = window._warning_banner
        assert banner.isVisible()
        assert "#00AA00" in banner.styleSheet()
        assert "姿势良好 ✓" in banner.text()

        qtbot.wait(2100)
        assert not banner.isVisible()

    def test_normal_hides_banner_immediately(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.set_warning_level(WarningLevelEvent(level=WarningLevel.WARNING, direction="left"))
        assert window._warning_banner.isVisible()

        window.set_warning_level(WarningLevelEvent(level=WarningLevel.NORMAL, direction=None))
        assert not window._warning_banner.isVisible()

    def test_normal_cancels_corrected_timer(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.set_warning_level(WarningLevelEvent(level=WarningLevel.CORRECTED, direction=None))
        assert window._warning_banner.isVisible()

        window.set_warning_level(WarningLevelEvent(level=WarningLevel.NORMAL, direction=None))
        assert not window._warning_banner.isVisible()

        qtbot.wait(2100)
        assert not window._warning_banner.isVisible()


class TestBadgeColorSync:
    """Verify pose state badge color changes with warning level."""

    def test_warning_sets_badge_yellow(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.set_warning_level(WarningLevelEvent(level=WarningLevel.WARNING, direction="left"))

        badge_style = window._badge_label.styleSheet()
        assert "#FFD700" in badge_style

    def test_severe_sets_badge_red(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.set_warning_level(WarningLevelEvent(level=WarningLevel.SEVERE, direction="right"))

        badge_style = window._badge_label.styleSheet()
        assert "#FF0000" in badge_style

    def test_corrected_sets_badge_green(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.set_warning_level(WarningLevelEvent(level=WarningLevel.CORRECTED, direction=None))

        badge_style = window._badge_label.styleSheet()
        assert "#00AA00" in badge_style

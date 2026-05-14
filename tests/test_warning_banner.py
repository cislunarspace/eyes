"""Tests for MainWindow warning banner behavior and i18n (issues #26, #58)."""

from __future__ import annotations

from eyes.classifier import PoseState
from eyes.i18n import set_language
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

    def test_warning_right_shows_yellow_banner(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.set_warning_level(WarningLevelEvent(level=WarningLevel.WARNING, direction="right"))

        banner = window._warning_banner
        assert banner.isVisible()
        assert "#FFD700" in banner.styleSheet()
        assert "请正视屏幕" in banner.text()
        assert "→ 请向右调整" in banner.text()

    def test_severe_left_shows_red_banner(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.set_warning_level(WarningLevelEvent(level=WarningLevel.SEVERE, direction="left"))

        banner = window._warning_banner
        assert banner.isVisible()
        assert "#FF0000" in banner.styleSheet()
        assert "请正视屏幕" in banner.text()
        assert "← 请向左调整" in banner.text()


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


class TestMainWindowI18n:
    """Verify main window badge, readout, banner, and camera status use t()."""

    def teardown_method(self) -> None:
        set_language("zh-CN")

    def test_badge_text_in_chinese(self, qtbot) -> None:
        set_language("zh-CN")
        window = MainWindow()
        qtbot.addWidget(window)
        window.set_state(5.0, -1.0, PoseState.FACING_SCREEN)
        assert window._badge_label.text() == "头正对"

    def test_badge_text_in_english(self, qtbot) -> None:
        set_language("en")
        window = MainWindow()
        qtbot.addWidget(window)
        window.set_state(5.0, -1.0, PoseState.FACING_SCREEN)
        assert window._badge_label.text() == "Facing Screen"

    def test_badge_no_face_in_english(self, qtbot) -> None:
        set_language("en")
        window = MainWindow()
        qtbot.addWidget(window)
        window.set_state(None, None, None)
        assert window._badge_label.text() == "No Face Detected"

    def test_badge_off_axis_left_in_english(self, qtbot) -> None:
        set_language("en")
        window = MainWindow()
        qtbot.addWidget(window)
        window.set_state(-5.0, 0.0, PoseState.OFF_AXIS_LEFT)
        assert window._badge_label.text() == "Turned Left"

    def test_badge_off_axis_right_in_english(self, qtbot) -> None:
        set_language("en")
        window = MainWindow()
        qtbot.addWidget(window)
        window.set_state(5.0, 0.0, PoseState.OFF_AXIS_RIGHT)
        assert window._badge_label.text() == "Turned Right"

    def test_badge_off_axis_other_in_english(self, qtbot) -> None:
        set_language("en")
        window = MainWindow()
        qtbot.addWidget(window)
        window.set_state(0.0, 5.0, PoseState.OFF_AXIS_OTHER)
        assert window._badge_label.text() == "Tilted"

    def test_readout_placeholder_in_chinese(self, qtbot) -> None:
        set_language("zh-CN")
        window = MainWindow()
        qtbot.addWidget(window)
        window.set_state(None, None, None)
        assert "—" in window._readout_label.text()

    def test_camera_unavailable_in_english(self, qtbot) -> None:
        set_language("en")
        window = MainWindow()
        qtbot.addWidget(window)
        window.show_camera_unavailable_message()
        assert window._camera_status_label.text() == "Camera is in use by another app… Waiting"

    def test_camera_unavailable_in_chinese(self, qtbot) -> None:
        set_language("zh-CN")
        window = MainWindow()
        qtbot.addWidget(window)
        window.show_camera_unavailable_message()
        assert "摄像头" in window._camera_status_label.text()

    def test_warning_banner_in_english(self, qtbot) -> None:
        set_language("en")
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()
        window.set_warning_level(WarningLevelEvent(level=WarningLevel.WARNING, direction="left"))
        assert "Please Face the Screen" in window._warning_banner.text()
        assert "← Adjust Left" in window._warning_banner.text()

    def test_corrected_banner_in_english(self, qtbot) -> None:
        set_language("en")
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()
        window.set_warning_level(WarningLevelEvent(level=WarningLevel.CORRECTED, direction=None))
        assert "Good Posture ✓" in window._warning_banner.text()

    def test_refresh_language_updates_badge(self, qtbot) -> None:
        set_language("zh-CN")
        window = MainWindow()
        qtbot.addWidget(window)
        window.set_state(5.0, -1.0, PoseState.FACING_SCREEN)
        assert window._badge_label.text() == "头正对"

        set_language("en")
        window.refresh_language()
        assert window._badge_label.text() == "Facing Screen"

    def test_refresh_language_updates_camera_status(self, qtbot) -> None:
        set_language("zh-CN")
        window = MainWindow()
        qtbot.addWidget(window)
        window.show_camera_unavailable_message()

        set_language("en")
        window.refresh_language()
        assert "Camera" in window._camera_status_label.text()

    def test_window_title_stays_eyes(self, qtbot) -> None:
        set_language("en")
        window = MainWindow()
        qtbot.addWidget(window)
        assert window.windowTitle() == "Eyes"

    def test_refresh_language_updates_warning_banner(self, qtbot) -> None:
        set_language("zh-CN")
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()
        window.set_warning_level(WarningLevelEvent(level=WarningLevel.WARNING, direction="left"))
        assert "请正视屏幕" in window._warning_banner.text()

        set_language("en")
        window.refresh_language()
        # Banner text should be updated to English
        assert "Please Face the Screen" in window._warning_banner.text()

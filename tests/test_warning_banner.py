"""Smoke tests for MainWindow rendering of DisplayPlan + i18n (issues #26, #58, #62).

Pure DisplayPlan logic is covered in test_display_plan.py. These tests
verify only that MainWindow correctly pushes DisplayPlan values into
QLabel widgets and that language switching refreshes rendered text.
"""

from __future__ import annotations

from eyes.classifier import PoseState
from eyes.i18n import set_language
from eyes.main_window import MainWindow
from eyes.types import WarningLevel, WarningLevelEvent


class TestRendererSmoke:
    """Verify DisplayPlan values reach the badge and banner widgets."""

    def test_warning_event_makes_banner_visible(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.set_warning_level(
            WarningLevelEvent(level=WarningLevel.WARNING, direction="left")
        )

        assert window._warning_banner.isVisible()
        assert window._warning_banner.text()
        assert window._badge_label.styleSheet()

    def test_normal_event_hides_banner(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.set_warning_level(
            WarningLevelEvent(level=WarningLevel.WARNING, direction="left")
        )
        assert window._warning_banner.isVisible()

        window.set_warning_level(
            WarningLevelEvent(level=WarningLevel.NORMAL, direction=None)
        )
        assert not window._warning_banner.isVisible()

    def test_corrected_banner_auto_dismisses(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.set_warning_level(
            WarningLevelEvent(level=WarningLevel.CORRECTED, direction=None)
        )
        assert window._warning_banner.isVisible()

        qtbot.wait(2100)
        assert not window._warning_banner.isVisible()

    def test_normal_after_corrected_cancels_pending_dismiss(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.set_warning_level(
            WarningLevelEvent(level=WarningLevel.CORRECTED, direction=None)
        )
        window.set_warning_level(
            WarningLevelEvent(level=WarningLevel.NORMAL, direction=None)
        )
        assert not window._warning_banner.isVisible()

        qtbot.wait(2100)
        assert not window._warning_banner.isVisible()

    def test_pose_updates_during_corrected_do_not_postpone_dismiss(self, qtbot) -> None:
        """Regression: pose ticks while CORRECTED must not restart the auto-dismiss timer.

        Real usage drives `set_state` at ~30 fps. If `_render` restarted the
        timer every call, the CORRECTED banner would never dismiss.
        """
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()

        window.set_warning_level(
            WarningLevelEvent(level=WarningLevel.CORRECTED, direction=None)
        )

        for _ in range(20):
            window.set_state(0.0, 0.0, PoseState.FACING_SCREEN)
            qtbot.wait(50)
        qtbot.wait(1200)

        assert not window._warning_banner.isVisible()


class TestMainWindowI18n:
    """Verify badge, readout, banner, and camera status all flow through t()."""

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

    def test_badge_head_up_in_english(self, qtbot) -> None:
        set_language("en")
        window = MainWindow()
        qtbot.addWidget(window)
        window.set_state(0.0, 5.0, PoseState.HEAD_UP)
        assert window._badge_label.text() == "Looking Up"

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
        window.set_warning_level(
            WarningLevelEvent(level=WarningLevel.WARNING, direction="left")
        )
        assert "Please Face the Screen" in window._warning_banner.text()
        assert "← Adjust Left" in window._warning_banner.text()

    def test_corrected_banner_in_english(self, qtbot) -> None:
        set_language("en")
        window = MainWindow()
        qtbot.addWidget(window)
        window.show()
        window.set_warning_level(
            WarningLevelEvent(level=WarningLevel.CORRECTED, direction=None)
        )
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
        window.set_warning_level(
            WarningLevelEvent(level=WarningLevel.WARNING, direction="left")
        )
        assert "请正视屏幕" in window._warning_banner.text()

        set_language("en")
        window.refresh_language()
        assert "Please Face the Screen" in window._warning_banner.text()

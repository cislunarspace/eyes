"""Tests for TrayController: tooltips, left-click, and menu enhancements (issue #42)."""

from __future__ import annotations

from PySide6.QtWidgets import QSystemTrayIcon

from eyes.tray_controller import TrayController
from eyes.types import TrayIconState


class TestLeftClickShowWindow:
    """Verify left-click on tray icon emits show_window_requested."""

    def test_left_click_emits_signal(self, qtbot) -> None:
        tray = TrayController()
        with qtbot.waitSignal(tray.show_window_requested, timeout=1000):
            tray.activated.emit(QSystemTrayIcon.ActivationReason.Trigger)

    def test_right_click_does_not_emit_signal(self, qtbot) -> None:
        tray = TrayController()
        emitted = []
        tray.show_window_requested.connect(lambda: emitted.append(True))
        tray.activated.emit(QSystemTrayIcon.ActivationReason.Context)
        assert emitted == []


class TestShowWindowMenuItem:
    """Verify '显示窗口' menu item exists and emits show_window_requested."""

    def test_show_window_action_is_first_menu_item(self, qtbot) -> None:
        tray = TrayController()
        actions = tray._menu.actions()
        assert actions[0].text() == "显示窗口"

    def test_show_window_action_emits_signal(self, qtbot) -> None:
        tray = TrayController()
        actions = tray._menu.actions()
        show_action = actions[0]
        with qtbot.waitSignal(tray.show_window_requested, timeout=1000):
            show_action.trigger()


class TestExistingMenuUnaffected:
    """Verify existing pause/resume/settings/quit menu items still work."""

    def test_pause_actions_still_present(self, qtbot) -> None:
        tray = TrayController()
        texts = [a.text() for a in tray._menu.actions() if not a.isSeparator()]
        assert "Pause 30 minutes" in texts
        assert "Pause 1 hour" in texts
        assert "Pause until I resume" in texts

    def test_resume_action_still_present(self, qtbot) -> None:
        tray = TrayController()
        texts = [a.text() for a in tray._menu.actions() if not a.isSeparator()]
        assert "Resume" in texts

    def test_settings_action_still_present(self, qtbot) -> None:
        tray = TrayController()
        texts = [a.text() for a in tray._menu.actions() if not a.isSeparator()]
        assert "Open Settings" in texts

    def test_quit_action_still_present(self, qtbot) -> None:
        tray = TrayController()
        texts = [a.text() for a in tray._menu.actions() if not a.isSeparator()]
        assert "Quit" in texts

    def test_pause_30_emits_pause_requested(self, qtbot) -> None:
        tray = TrayController()
        pause_30 = next(a for a in tray._menu.actions() if a.text() == "Pause 30 minutes")
        with qtbot.waitSignal(tray.pause_requested, timeout=1000) as blocker:
            pause_30.trigger()
        assert blocker.args == [1800]

    def test_resume_emits_resume_requested_when_enabled(self, qtbot) -> None:
        tray = TrayController()
        tray.set_state(TrayIconState.PAUSED)
        resume_action = next(a for a in tray._menu.actions() if a.text() == "Resume")
        with qtbot.waitSignal(tray.resume_requested, timeout=1000):
            resume_action.trigger()

    def test_settings_emits_settings_requested(self, qtbot) -> None:
        tray = TrayController()
        settings_action = next(a for a in tray._menu.actions() if a.text() == "Open Settings")
        with qtbot.waitSignal(tray.settings_requested, timeout=1000):
            settings_action.trigger()

    def test_quit_emits_quit_requested(self, qtbot) -> None:
        tray = TrayController()
        quit_action = next(a for a in tray._menu.actions() if a.text() == "Quit")
        with qtbot.waitSignal(tray.quit_requested, timeout=1000):
            quit_action.trigger()


class TestDynamicTooltip:
    """Verify tooltip text changes with TrayIconState."""

    def test_active_tooltip(self, qtbot) -> None:
        tray = TrayController()
        tray.set_state(TrayIconState.ACTIVE)
        assert tray.toolTip() == "Eyes — 监控中"

    def test_paused_tooltip(self, qtbot) -> None:
        tray = TrayController()
        tray.set_state(TrayIconState.PAUSED)
        assert tray.toolTip() == "Eyes — 已暂停"

    def test_unavailable_tooltip(self, qtbot) -> None:
        tray = TrayController()
        tray.set_state(TrayIconState.UNAVAILABLE)
        assert tray.toolTip() == "Eyes — 摄像头不可用"

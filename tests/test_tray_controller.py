"""Tests for TrayController: tooltips, left-click, menu enhancements, and i18n."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QSystemTrayIcon

from eyes.i18n import set_language
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
    """Verify menu item exists and emits show_window_requested."""

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
        assert "暂停 30 分钟" in texts
        assert "暂停 1 小时" in texts
        assert "暂停至恢复" in texts

    def test_resume_action_still_present(self, qtbot) -> None:
        tray = TrayController()
        texts = [a.text() for a in tray._menu.actions() if not a.isSeparator()]
        assert "恢复" in texts

    def test_settings_action_still_present(self, qtbot) -> None:
        tray = TrayController()
        texts = [a.text() for a in tray._menu.actions() if not a.isSeparator()]
        assert "打开设置" in texts

    def test_quit_action_still_present(self, qtbot) -> None:
        tray = TrayController()
        texts = [a.text() for a in tray._menu.actions() if not a.isSeparator()]
        assert "退出" in texts

    def test_pause_30_emits_pause_requested(self, qtbot) -> None:
        tray = TrayController()
        pause_30 = next(a for a in tray._menu.actions() if "30" in a.text())
        with qtbot.waitSignal(tray.pause_requested, timeout=1000) as blocker:
            pause_30.trigger()
        assert blocker.args == [1800]

    def test_resume_emits_resume_requested_when_enabled(self, qtbot) -> None:
        tray = TrayController()
        tray.set_state(TrayIconState.PAUSED)
        resume_action = next(a for a in tray._menu.actions() if a.text() == "恢复")
        with qtbot.waitSignal(tray.resume_requested, timeout=1000):
            resume_action.trigger()

    def test_settings_emits_settings_requested(self, qtbot) -> None:
        tray = TrayController()
        settings_action = next(a for a in tray._menu.actions() if a.text() == "打开设置")
        with qtbot.waitSignal(tray.settings_requested, timeout=1000):
            settings_action.trigger()

    def test_quit_emits_quit_requested(self, qtbot) -> None:
        tray = TrayController()
        quit_action = next(a for a in tray._menu.actions() if a.text() == "退出")
        with qtbot.waitSignal(tray.quit_requested, timeout=1000):
            quit_action.trigger()


class TestColorSchemeIntegration:
    """Verify TrayController responds to system color scheme changes (issue #48)."""

    def _style_hints(self):
        from PySide6.QtGui import QGuiApplication

        return QGuiApplication.styleHints()

    def _pixel_color_at_center(self, icon, size=48):
        pm = icon.pixmap(size)
        dpr = pm.devicePixelRatio()
        cx = int(pm.width() / dpr / 2 * dpr)
        cy = int(pm.height() / dpr / 2 * dpr)
        img = pm.toImage()
        return QColor(img.pixelColor(cx, cy))

    def test_dark_mode_icon_after_scheme_change(self, qtbot) -> None:
        tray = TrayController()
        hints = self._style_hints()
        hints.colorSchemeChanged.emit(Qt.ColorScheme.Dark)
        color = self._pixel_color_at_center(tray.icon())
        assert color == QColor("#FFFFFF")

    def test_light_mode_icon_after_scheme_change(self, qtbot) -> None:
        tray = TrayController()
        hints = self._style_hints()
        hints.colorSchemeChanged.emit(Qt.ColorScheme.Light)
        color = self._pixel_color_at_center(tray.icon())
        assert color == QColor("#222222")

    def test_icon_updates_on_each_scheme_toggle(self, qtbot) -> None:
        tray = TrayController()
        hints = self._style_hints()
        hints.colorSchemeChanged.emit(Qt.ColorScheme.Dark)
        assert self._pixel_color_at_center(tray.icon()) == QColor("#FFFFFF")
        hints.colorSchemeChanged.emit(Qt.ColorScheme.Light)
        assert self._pixel_color_at_center(tray.icon()) == QColor("#222222")
        hints.colorSchemeChanged.emit(Qt.ColorScheme.Dark)
        assert self._pixel_color_at_center(tray.icon()) == QColor("#FFFFFF")

    def test_existing_menu_unaffected_by_scheme_change(self, qtbot) -> None:
        tray = TrayController()
        hints = self._style_hints()
        hints.colorSchemeChanged.emit(Qt.ColorScheme.Dark)
        texts = [a.text() for a in tray._menu.actions() if not a.isSeparator()]
        assert "暂停 30 分钟" in texts
        assert "恢复" in texts
        assert "退出" in texts


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


class TestTrayI18n:
    """Verify tray menu items and tooltips use t() for translations."""

    def teardown_method(self) -> None:
        set_language("zh-CN")

    def test_menu_items_in_english(self, qtbot) -> None:
        set_language("en")
        tray = TrayController()
        texts = [a.text() for a in tray._menu.actions() if not a.isSeparator()]
        assert "Show Window" in texts
        assert "Pause 30 Minutes" in texts
        assert "Pause 1 Hour" in texts
        assert "Pause Until I Resume" in texts
        assert "Resume" in texts
        assert "Open Settings" in texts
        assert "Quit" in texts

    def test_menu_items_in_chinese(self, qtbot) -> None:
        set_language("zh-CN")
        tray = TrayController()
        texts = [a.text() for a in tray._menu.actions() if not a.isSeparator()]
        assert "显示窗口" in texts
        assert "暂停 30 分钟" in texts
        assert "暂停 1 小时" in texts
        assert "暂停至恢复" in texts
        assert "恢复" in texts
        assert "打开设置" in texts
        assert "退出" in texts

    def test_tooltips_in_english(self, qtbot) -> None:
        set_language("en")
        tray = TrayController()
        tray.set_state(TrayIconState.ACTIVE)
        assert tray.toolTip() == "Eyes — Monitoring"
        tray.set_state(TrayIconState.PAUSED)
        assert tray.toolTip() == "Eyes — Paused"
        tray.set_state(TrayIconState.UNAVAILABLE)
        assert tray.toolTip() == "Eyes — Camera Unavailable"

    def test_refresh_language_rebuilds_menu(self, qtbot) -> None:
        set_language("zh-CN")
        tray = TrayController()
        texts_zh = [a.text() for a in tray._menu.actions() if not a.isSeparator()]
        assert "显示窗口" in texts_zh

        set_language("en")
        tray.refresh_language()
        texts_en = [a.text() for a in tray._menu.actions() if not a.isSeparator()]
        assert "Show Window" in texts_en

    def test_refresh_language_updates_tooltips(self, qtbot) -> None:
        set_language("zh-CN")
        tray = TrayController()
        tray.set_state(TrayIconState.ACTIVE)
        assert tray.toolTip() == "Eyes — 监控中"

        set_language("en")
        tray.refresh_language()
        tray.set_state(TrayIconState.ACTIVE)
        assert tray.toolTip() == "Eyes — Monitoring"

    def test_refresh_language_preserves_resume_enabled_state(self, qtbot) -> None:
        set_language("zh-CN")
        tray = TrayController()
        tray.set_state(TrayIconState.PAUSED)

        set_language("en")
        tray.refresh_language()

        resume_action = next(a for a in tray._menu.actions() if a.text() == "Resume")
        assert resume_action.isEnabled()

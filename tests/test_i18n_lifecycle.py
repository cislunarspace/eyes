"""Tests for i18n lifecycle integration — startup init and language switch propagation."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import eyes.i18n as i18n
from eyes.controller import AppController
from eyes.i18n import set_language
from eyes.main_window import MainWindow
from eyes.overlay import NotifierOverlay
from eyes.tray_controller import TrayController


def _make_config(**overrides) -> MagicMock:
    defaults = dict(
        language="zh-CN",
        camera_index=0,
        autostart_enabled=False,
        yaw_threshold=1.0,
        roll_threshold=90.0,
        neutral_yaw=0.0,
        neutral_roll=0.0,
        off_axis_streak_threshold_seconds=0.3,
        off_axis_repeat_interval_seconds=10.0,
        facing_threshold_seconds=300.0,
        eyest_threshold_seconds=900.0,
    )
    defaults.update(overrides)
    config = MagicMock()
    for k, v in defaults.items():
        setattr(config, k, v)
    return config


@contextmanager
def _mock_controller_deps(config: MagicMock | None = None):
    if config is None:
        config = _make_config()
    with (
        patch("eyes.controller.ConfigStore") as MockConfigStore,
        patch("eyes.controller.CameraSource"),
        patch("eyes.controller.MainWindow"),
        patch("eyes.controller.NotifierOverlay"),
        patch("eyes.controller.TrayController"),
        patch("eyes.controller.SenseLoop"),
        patch("eyes.controller.EventLog"),
        patch("eyes.controller.SnoozeManager"),
        patch("eyes.controller.AutostartManager"),
        patch("eyes.controller.QTimer"),
        patch("eyes.controller.create_eye_icon"),
        patch("eyes.controller.SenseEventBus"),
        patch("eyes.controller.SettingsBridge"),
    ):
        MockConfigStore.return_value.load.return_value = config
        yield config


class TestStartupLanguageInit:
    """AppController initializes i18n from ConfigStore on startup."""

    def teardown_method(self) -> None:
        set_language("zh-CN")

    def test_calls_set_language_with_config_language(self) -> None:
        with _mock_controller_deps(config=_make_config(language="en")):
            AppController(MagicMock())

        assert i18n.current_language == "en"

    def test_defaults_to_zh_cn(self) -> None:
        with _mock_controller_deps(config=_make_config(language="zh-CN")):
            AppController(MagicMock())

        assert i18n.current_language == "zh-CN"


class TestRefreshLanguagePlaceholder:
    """Each UI component has a refresh_language() placeholder method."""

    def test_main_window_has_refresh_language(self, qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        assert hasattr(window, "refresh_language")
        assert callable(window.refresh_language)

    def test_overlay_has_refresh_language(self, qtbot) -> None:
        overlay = NotifierOverlay()
        qtbot.addWidget(overlay)
        assert hasattr(overlay, "refresh_language")
        assert callable(overlay.refresh_language)

    def test_tray_controller_has_refresh_language(self, qtbot) -> None:
        tray = TrayController()
        assert hasattr(tray, "refresh_language")
        assert callable(tray.refresh_language)


class TestSettingsChangePropagation:
    """Settings change triggers set_language() and refresh_language() on components."""

    def teardown_method(self) -> None:
        set_language("zh-CN")

    def test_set_language_called_with_new_config_language(self) -> None:
        # The bridge now owns the call to set_language; assert the bridge
        # was invoked. The set_language side effect is covered in
        # test_settings_bridge.py.
        controller = object.__new__(AppController)
        controller._config_store = MagicMock()
        controller._config_store.load.return_value = _make_config(language="en")
        controller._settings_bridge = MagicMock()

        controller._on_settings_changed()

        controller._settings_bridge.apply_config.assert_called_once()

    def test_refresh_language_called_on_window_overlay_tray(self) -> None:
        # Same: the bridge now owns the refresh calls.
        controller = object.__new__(AppController)
        controller._config_store = MagicMock()
        controller._config_store.load.return_value = _make_config(language="en")
        controller._settings_bridge = MagicMock()

        controller._on_settings_changed()

        controller._settings_bridge.apply_config.assert_called_once()

"""Tests for i18n mid-session refresh.

Acceptance criteria for issue #81:
  1. Module-level t() and set_language() work.
  2. Settings dialog refreshes mid-session when language changes.
  3. No behavior change for the existing single-language-per-process flow.
"""

from __future__ import annotations

from pathlib import Path

import eyes.i18n as i18n
from eyes.i18n import set_language, t


class TestModuleLevelT:
    """Module-level t() uses the process-wide language."""

    def teardown_method(self) -> None:
        set_language("zh-CN")

    def test_t_returns_default_language_translation(self) -> None:
        set_language("zh-CN")
        assert t("badge.facing_screen") == "头正对"

    def test_set_language_affects_t(self) -> None:
        set_language("en")
        assert t("badge.facing_screen") == "Facing Screen"

    def test_current_language_reflects_set_language(self) -> None:
        set_language("en")
        assert i18n.current_language == "en"
        set_language("zh-CN")
        assert i18n.current_language == "zh-CN"


class TestSettingsDialogMidSessionRefresh:
    """Criterion 3: settings dialog refreshes mid-session on language change."""

    def test_refresh_language_updates_window_title(self, qtbot, tmp_path: Path) -> None:
        from eyes.config_store import ConfigStore
        from eyes.settings_dialog import SettingsDialog

        set_language("zh-CN")
        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()
        dialog = SettingsDialog(config_store)
        qtbot.addWidget(dialog)
        assert "设置" in dialog.windowTitle()

        set_language("en")
        dialog.refresh_language()
        assert "Settings" in dialog.windowTitle()
        set_language("zh-CN")

    def test_refresh_language_updates_calibrate_button(self, qtbot, tmp_path: Path) -> None:
        from eyes.config_store import ConfigStore
        from eyes.settings_dialog import SettingsDialog

        set_language("zh-CN")
        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()
        dialog = SettingsDialog(config_store)
        qtbot.addWidget(dialog)
        assert dialog._calibrate_button.text() == "校准中立姿态"

        set_language("en")
        dialog.refresh_language()
        assert dialog._calibrate_button.text() == "Calibrate Neutral Pose"
        set_language("zh-CN")

    def test_refresh_language_updates_open_dir_button(self, qtbot, tmp_path: Path) -> None:
        from eyes.config_store import ConfigStore
        from eyes.settings_dialog import SettingsDialog

        set_language("zh-CN")
        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()
        dialog = SettingsDialog(config_store)
        qtbot.addWidget(dialog)
        assert dialog._open_dir_button.text() == "打开数据目录"

        set_language("en")
        dialog.refresh_language()
        assert dialog._open_dir_button.text() == "Open Data Directory"
        set_language("zh-CN")

    def test_refresh_language_updates_form_row_labels(self, qtbot, tmp_path: Path) -> None:
        """Form row labels (stored as explicit QLabel refs) should update."""
        from eyes.config_store import ConfigStore
        from eyes.settings_dialog import SettingsDialog

        set_language("zh-CN")
        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()
        dialog = SettingsDialog(config_store)
        qtbot.addWidget(dialog)

        # The yaw slider's form row label should be in Chinese.
        assert dialog._row_label_yaw.text() == "偏航阈值"

        set_language("en")
        dialog.refresh_language()
        assert dialog._row_label_yaw.text() == "Yaw Threshold"
        set_language("zh-CN")


class TestExistingSingleLanguageFlow:
    """Criterion 5: existing single-language-per-process flow is unchanged."""

    def teardown_method(self) -> None:
        set_language("zh-CN")

    def test_zh_cn_default(self) -> None:
        assert t("badge.facing_screen") == "头正对"

    def test_en_after_switch(self) -> None:
        set_language("en")
        assert t("badge.facing_screen") == "Facing Screen"

    def test_roundtrip(self) -> None:
        set_language("en")
        assert t("overlay.good_posture") == "Good Posture"
        set_language("zh-CN")
        assert t("overlay.good_posture") == "当前姿势良好"

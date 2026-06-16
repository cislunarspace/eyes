"""Tests for the Translator class and i18n mid-session refresh.

Acceptance criteria for issue #81:
  1. Translator is a small class with t(key) and set_language(code).
  2. Module-level t() is preserved (delegates to a default translator).
  3. Settings dialog refreshes mid-session when language changes.
  4. Two Translator instances in one process are independent.
  5. No behavior change for the existing single-language-per-process flow.
"""

from __future__ import annotations

from pathlib import Path

import eyes.i18n as i18n
from eyes.i18n import Translator, set_language, t


class TestTranslatorClass:
    """Criterion 1: Translator has t(key) and set_language(code)."""

    def test_t_returns_translation(self) -> None:
        translator = Translator("zh-CN")
        assert translator.t("badge.facing_screen") == "头正对"

    def test_set_language_changes_t_output(self) -> None:
        translator = Translator("zh-CN")
        assert translator.t("badge.facing_screen") == "头正对"
        translator.set_language("en")
        assert translator.t("badge.facing_screen") == "Facing Screen"

    def test_language_property(self) -> None:
        translator = Translator("en")
        assert translator.language == "en"
        translator.set_language("zh-CN")
        assert translator.language == "zh-CN"


class TestModuleLevelT:
    """Criterion 2: module-level t() delegates to the default translator."""

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


class TestTwoTranslatorsIndependent:
    """Criterion 4: two Translator instances in one process are independent."""

    def test_different_languages_yield_different_translations(self) -> None:
        zh = Translator("zh-CN")
        en = Translator("en")
        assert zh.t("badge.facing_screen") == "头正对"
        assert en.t("badge.facing_screen") == "Facing Screen"

    def test_changing_one_does_not_affect_the_other(self) -> None:
        zh = Translator("zh-CN")
        en = Translator("en")
        en.set_language("zh-CN")
        assert en.t("badge.facing_screen") == "头正对"
        # zh was never changed.
        assert zh.t("badge.facing_screen") == "头正对"
        assert zh.language == "zh-CN"

    def test_translator_does_not_affect_module_level_t(self) -> None:
        set_language("en")
        t2 = Translator("zh-CN")
        # Creating t2 with zh-CN doesn't change the process-wide default.
        assert t("badge.facing_screen") == "Facing Screen"
        assert t2.t("badge.facing_screen") == "头正对"
        set_language("zh-CN")  # restore


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

"""Tests for i18n module — translation lookup and language switching."""

from __future__ import annotations

import pytest

import eyes.i18n as i18n
from eyes.i18n import set_language, t

_SUPPORTED_LANGUAGES = ["zh-CN", "en"]

_EXPECTED_KEYS = [
    # overlay
    "overlay.adjust_left",
    "overlay.adjust_right",
    "overlay.good_posture",
    "overlay.eye_rest",
    "overlay.corrected",
    # settings
    "settings.title",
    "settings.yaw_threshold",
    "settings.first_prompt_delay",
    "settings.repeat_prompt_interval",
    "settings.roll_threshold_disabled",
    "settings.neutral_pose",
    "settings.calibrate_button",
    "settings.camera",
    "settings.camera_index",
    "settings.sound",
    "settings.autostart",
    "settings.language",
    "settings.data_directory",
    "settings.open_data_directory",
    "settings.on",
    "settings.off",
    # tray
    "tray.show_window",
    "tray.pause_30",
    "tray.pause_1h",
    "tray.pause_indefinite",
    "tray.resume",
    "tray.open_settings",
    "tray.quit",
    "tray.tooltip_active",
    "tray.tooltip_paused",
    "tray.tooltip_unavailable",
    # main_window
    "main_window.camera_unavailable",
    "main_window.please_face_screen",
    "main_window.adjust_left_hint",
    "main_window.adjust_right_hint",
    "main_window.posture_good",
    "main_window.readout_placeholder",
    # badge
    "badge.facing_screen",
    "badge.off_axis_left",
    "badge.off_axis_right",
    "badge.off_axis_other",
    "badge.no_face",
    # calibration
    "calibration.in_progress",
    "calibration.complete",
    # readout
    "readout.label",
]


class TestDefaultLanguageLookup:
    """t() returns Chinese text by default (zh-CN)."""

    def test_returns_chinese_for_known_key(self) -> None:
        assert t("overlay.adjust_left") == "向左调整"


class TestLanguageSwitching:
    """set_language() switches t() output language."""

    def setup_method(self) -> None:
        set_language("zh-CN")

    def teardown_method(self) -> None:
        set_language("zh-CN")

    def test_switches_to_english(self) -> None:
        set_language("en")
        assert t("overlay.adjust_left") == "Adjust Left"

    def test_switches_back_to_chinese(self) -> None:
        set_language("en")
        set_language("zh-CN")
        assert t("overlay.adjust_left") == "向左调整"

    def test_current_language_reflects_switch(self) -> None:
        assert i18n.current_language == "zh-CN"
        set_language("en")
        assert i18n.current_language == "en"


class TestMissingKey:
    """t() raises KeyError for missing keys."""

    def test_raises_key_error_for_unknown_key(self) -> None:
        with pytest.raises(KeyError):
            t("nonexistent.key")


class TestDictionaryCompleteness:
    """All expected keys exist with non-empty values in every supported language."""

    @pytest.mark.parametrize("lang", _SUPPORTED_LANGUAGES)
    def test_all_keys_present_and_nonempty(self, lang: str) -> None:
        set_language(lang)
        missing = []
        empty = []
        for key in _EXPECTED_KEYS:
            try:
                value = t(key)
                if not value:
                    empty.append(key)
            except KeyError:
                missing.append(key)
        assert not missing, f"Missing keys in {lang}: {missing}"
        assert not empty, f"Empty values in {lang}: {empty}"

    def test_expected_key_count(self) -> None:
        zh_keys = set(i18n._TRANSLATIONS["zh-CN"].keys())
        en_keys = set(i18n._TRANSLATIONS["en"].keys())
        assert zh_keys == en_keys, f"Key mismatch: zh only={zh_keys - en_keys}, en only={en_keys - zh_keys}"
        assert len(zh_keys) >= len(_EXPECTED_KEYS)

"""Tests for SettingsDialog and calibration integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from eyes.calibration import PoseSample, compute_median_pose


class TestCalibrationIntegration:
    """Integration tests for calibration flow."""

    def test_compute_median_returns_correct_for_sampling_scenario(self) -> None:
        """Simulate a 5-second calibration session with 10 Hz sampling."""
        # 5 seconds at 10 Hz = 50 samples
        # Simulate slight drift in head position during calibration
        samples = []
        for i in range(50):
            yaw = 5.0 + (i * 0.02)  # drift from 5.0 to 5.98
            pitch = 2.0 + (i * 0.01)  # drift from 2.0 to 2.49
            samples.append(PoseSample(yaw=yaw, pitch=pitch))

        result = compute_median_pose(samples)
        # The median should be around the middle of the range
        assert 5.3 < result.yaw < 5.7
        assert 2.15 < result.pitch < 2.35

    def test_compute_median_stable_for_noisy_samples(self) -> None:
        """Median is robust to outliers from head movement."""
        # Add some outliers to simulate sudden head movements
        samples = [
            PoseSample(yaw=5.0, pitch=2.0),
            PoseSample(yaw=5.1, pitch=2.1),
            PoseSample(yaw=5.2, pitch=2.2),
            PoseSample(yaw=50.0, pitch=30.0),  # outlier - sudden movement
            PoseSample(yaw=5.3, pitch=2.3),
        ]

        result = compute_median_pose(samples)
        # Median should be (5.1, 2.1) since it sorts by yaw: 5.0, 5.1, 5.2, 5.3, 50.0
        assert result.yaw == pytest.approx(5.2)  # middle of sorted list
        assert result.pitch == pytest.approx(2.2)


class TestSettingsPersistence:
    """Tests for settings persistence through ConfigStore."""

    def test_settings_update_persists(self, tmp_path: Path) -> None:
        """Changing settings via ConfigStore persists to disk."""
        from eyes.config_store import ConfigStore

        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()

        # Update yaw threshold
        updated = config_store.update(yaw_threshold=20.0)
        assert updated.yaw_threshold == 20.0

        # Reload and verify persistence
        config_store2 = ConfigStore(config_dir=tmp_path)
        reloaded = config_store2.load()
        assert reloaded.yaw_threshold == 20.0

    def test_neutral_pose_update_persists(self, tmp_path: Path) -> None:
        """Neutral pose calibration result persists."""
        from eyes.config_store import ConfigStore

        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()

        # Simulate calibration result
        calibrated_yaw = 3.5
        calibrated_roll = -1.2
        config_store.update(neutral_yaw=calibrated_yaw, neutral_pitch=calibrated_roll)

        # Reload and verify
        config_store2 = ConfigStore(config_dir=tmp_path)
        reloaded = config_store2.load()
        assert reloaded.neutral_yaw == pytest.approx(calibrated_yaw)
        assert reloaded.neutral_pitch == pytest.approx(calibrated_roll)

    def test_camera_index_update_persists(self, tmp_path: Path) -> None:
        """Camera selection persists across restarts."""
        from eyes.config_store import ConfigStore

        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()

        config_store.update(camera_index=2)

        config_store2 = ConfigStore(config_dir=tmp_path)
        reloaded = config_store2.load()
        assert reloaded.camera_index == 2

    def test_sound_enabled_update_persists(self, tmp_path: Path) -> None:
        """Sound toggle state persists."""
        from eyes.config_store import ConfigStore

        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()

        config_store.update(sound_enabled=True)

        config_store2 = ConfigStore(config_dir=tmp_path)
        reloaded = config_store2.load()
        assert reloaded.sound_enabled is True


class TestSettingsDialogI18n:
    """Verify settings dialog uses t() for all labels and has language combo box."""

    def test_language_control_is_combo_box(self, qtbot, tmp_path: Path) -> None:
        from PySide6.QtWidgets import QComboBox

        from eyes.config_store import ConfigStore
        from eyes.settings_dialog import SettingsDialog

        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()
        dialog = SettingsDialog(config_store)
        qtbot.addWidget(dialog)

        assert isinstance(dialog._language_combo, QComboBox)

    def test_language_combo_has_zh_and_en_options(self, qtbot, tmp_path: Path) -> None:
        from eyes.config_store import ConfigStore
        from eyes.settings_dialog import SettingsDialog

        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()
        dialog = SettingsDialog(config_store)
        qtbot.addWidget(dialog)

        texts = [dialog._language_combo.itemText(i) for i in range(dialog._language_combo.count())]
        assert "中文" in texts
        assert "English" in texts

    def test_language_combo_data_values(self, qtbot, tmp_path: Path) -> None:
        from eyes.config_store import ConfigStore
        from eyes.settings_dialog import SettingsDialog

        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()
        dialog = SettingsDialog(config_store)
        qtbot.addWidget(dialog)

        data_values = [dialog._language_combo.itemData(i) for i in range(dialog._language_combo.count())]
        assert "zh-CN" in data_values
        assert "en" in data_values

    def test_language_change_is_pending_change(self, qtbot, tmp_path: Path) -> None:
        from eyes.config_store import ConfigStore
        from eyes.settings_dialog import SettingsDialog

        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()
        dialog = SettingsDialog(config_store)
        qtbot.addWidget(dialog)

        en_idx = dialog._language_combo.findData("en")
        dialog._language_combo.setCurrentIndex(en_idx)

        assert dialog._pending_changes.get("language") == "en"

    def test_all_labels_use_t_in_zh_cn(self, qtbot, tmp_path: Path) -> None:
        from eyes.config_store import ConfigStore
        from eyes.i18n import set_language
        from eyes.settings_dialog import SettingsDialog

        set_language("zh-CN")
        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()
        dialog = SettingsDialog(config_store)
        qtbot.addWidget(dialog)

        assert dialog.windowTitle() == "Eyes — 设置"
        assert dialog._calibrate_button.text() == "校准中立姿态"
        assert dialog._open_dir_button.text() == "打开数据目录"
        assert dialog._language_combo.itemText(0) == "中文"
        assert dialog._language_combo.itemText(1) == "English"

    def test_all_labels_use_t_in_en(self, qtbot, tmp_path: Path) -> None:
        from eyes.config_store import ConfigStore
        from eyes.i18n import set_language
        from eyes.settings_dialog import SettingsDialog

        set_language("en")
        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()
        dialog = SettingsDialog(config_store)
        qtbot.addWidget(dialog)

        assert dialog.windowTitle() == "Eyes — Settings"
        assert dialog._calibrate_button.text() == "Calibrate Neutral Pose"
        assert dialog._open_dir_button.text() == "Open Data Directory"
        assert dialog._language_combo.itemText(0) == "中文"
        assert dialog._language_combo.itemText(1) == "English"

    def test_calibrate_button_uses_t(self, qtbot, tmp_path: Path) -> None:
        from eyes.config_store import ConfigStore
        from eyes.i18n import set_language
        from eyes.settings_dialog import SettingsDialog

        set_language("zh-CN")
        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()
        dialog = SettingsDialog(config_store)
        qtbot.addWidget(dialog)

        assert dialog._calibrate_button.text() == "校准中立姿态"

    def test_sound_toggle_uses_t(self, qtbot, tmp_path: Path) -> None:
        from eyes.config_store import ConfigStore
        from eyes.i18n import set_language
        from eyes.settings_dialog import SettingsDialog

        set_language("en")
        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()
        dialog = SettingsDialog(config_store)
        qtbot.addWidget(dialog)

        assert dialog._sound_toggle.text() in ("On", "Off")

    def teardown_method(self) -> None:
        from eyes.i18n import set_language
        set_language("zh-CN")

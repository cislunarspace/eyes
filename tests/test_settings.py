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
            roll = 2.0 + (i * 0.01)  # drift from 2.0 to 2.49
            samples.append(PoseSample(yaw=yaw, roll=roll))

        result = compute_median_pose(samples)
        # The median should be around the middle of the range
        assert 5.3 < result.yaw < 5.7
        assert 2.15 < result.roll < 2.35

    def test_compute_median_stable_for_noisy_samples(self) -> None:
        """Median is robust to outliers from head movement."""
        # Add some outliers to simulate sudden head movements
        samples = [
            PoseSample(yaw=5.0, roll=2.0),
            PoseSample(yaw=5.1, roll=2.1),
            PoseSample(yaw=5.2, roll=2.2),
            PoseSample(yaw=50.0, roll=30.0),  # outlier - sudden movement
            PoseSample(yaw=5.3, roll=2.3),
        ]

        result = compute_median_pose(samples)
        # Median should be (5.1, 2.1) since it sorts by yaw: 5.0, 5.1, 5.2, 5.3, 50.0
        assert result.yaw == pytest.approx(5.2)  # middle of sorted list
        assert result.roll == pytest.approx(2.2)


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
        config_store.update(neutral_yaw=calibrated_yaw, neutral_roll=calibrated_roll)

        # Reload and verify
        config_store2 = ConfigStore(config_dir=tmp_path)
        reloaded = config_store2.load()
        assert reloaded.neutral_yaw == pytest.approx(calibrated_yaw)
        assert reloaded.neutral_roll == pytest.approx(calibrated_roll)

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

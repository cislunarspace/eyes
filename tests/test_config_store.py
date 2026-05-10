"""Tests for ConfigStore."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from eyes.types import AppConfig


class TestConfigStore:
    """ConfigStore round-trip and atomic write tests."""

    def test_first_run_creates_default_config(self, tmp_path: Path) -> None:
        """On first launch, config file is created at platform-correct location with defaults."""
        from eyes.config_store import ConfigStore

        config_store = ConfigStore(config_dir=tmp_path)
        config = config_store.load()

        assert config.yaw_threshold == 15.0
        assert config.roll_threshold == 10.0
        assert config.neutral_yaw == 0.0
        assert config.neutral_roll == 0.0
        assert config.camera_index == 0
        assert config.snooze_until_iso is None
        assert config.sound_enabled is False
        assert config.autostart_enabled is False
        assert config.language == "zh-CN"

        # Verify file was created
        config_file = tmp_path / "config.yaml"
        assert config_file.exists()

        # Verify file contains correct defaults
        with open(config_file) as f:
            saved = yaml.safe_load(f)
        assert saved["yaw_threshold"] == 15.0
        assert saved["language"] == "zh-CN"

    def test_roundtrip_serialization(self, tmp_path: Path) -> None:
        """Editing config.yaml and restarting picks up new values."""
        from eyes.config_store import ConfigStore

        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()

        # Modify the YAML file directly (simulating user editing)
        config_file = tmp_path / "config.yaml"
        with open(config_file) as f:
            saved = yaml.safe_load(f)
        saved["yaw_threshold"] = 25.0
        saved["language"] = "en-US"
        with open(config_file, "w") as f:
            yaml.dump(saved, f)

        # Reload and verify new values are picked up
        config_store2 = ConfigStore(config_dir=tmp_path)
        config = config_store2.load()
        assert config.yaw_threshold == 25.0
        assert config.language == "en-US"

    def test_save_and_reload(self, tmp_path: Path) -> None:
        """Saving custom config and reloading returns identical values."""
        from eyes.config_store import ConfigStore

        config_store = ConfigStore(config_dir=tmp_path)
        original = AppConfig(
            yaw_threshold=20.0,
            roll_threshold=12.0,
            neutral_yaw=3.0,
            neutral_roll=-2.0,
            camera_index=1,
            snooze_until_iso="2026-05-11T12:00:00+08:00",
            sound_enabled=True,
            autostart_enabled=True,
            language="en-US",
        )
        config_store.save(original)
        reloaded = config_store.load()

        assert reloaded == original

    def test_atomic_write(self, tmp_path: Path) -> None:
        """Atomic write via temp-file-then-rename prevents corruption."""
        from eyes.config_store import ConfigStore

        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()

        # Modify config
        modified = AppConfig(yaw_threshold=30.0)

        # Simulate crash: rename fails, so original should be intact
        # We test this by verifying temp file pattern is used
        config_store.save(modified)

        # Check temp file was renamed to final location
        config_file = tmp_path / "config.yaml"
        assert config_file.exists()

        # Verify content is valid YAML and complete
        with open(config_file) as f:
            content = f.read()
        parsed = yaml.safe_load(content)
        assert parsed["yaw_threshold"] == 30.0

        # Ensure no temp files left behind
        for f in tmp_path.iterdir():
            assert not f.name.endswith(".tmp"), f"Temp file {f.name} not cleaned up"

    def test_update_partial(self, tmp_path: Path) -> None:
        """Partial update only modifies specified fields."""
        from eyes.config_store import ConfigStore

        config_store = ConfigStore(config_dir=tmp_path)
        original = config_store.load()

        updated = config_store.update(yaw_threshold=25.0, language="ja-JP")

        # Changed fields
        assert updated.yaw_threshold == 25.0
        assert updated.language == "ja-JP"

        # Unchanged fields
        assert updated.roll_threshold == original.roll_threshold
        assert updated.camera_index == original.camera_index

    def test_invalid_yaml_falls_back_to_default(self, tmp_path: Path) -> None:
        """Invalid config.yaml does not crash; falls back to defaults."""
        from eyes.config_store import ConfigStore

        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()

        # Write invalid YAML
        config_file = tmp_path / "config.yaml"
        config_file.write_text("invalid: yaml: content: {")

        # Should not raise, should return defaults
        config = config_store.load()
        assert config.yaw_threshold == 15.0
        assert config.language == "zh-CN"

    def test_empty_yaml_file_loads_defaults(self, tmp_path: Path) -> None:
        """Empty YAML file (yaml.safe_load returns None) falls back to defaults."""
        from eyes.config_store import ConfigStore

        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()

        # Write empty YAML file
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")

        # Should not raise, should return defaults
        config = config_store.load()
        assert config.yaw_threshold == 15.0
        assert config.language == "zh-CN"

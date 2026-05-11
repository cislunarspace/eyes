"""ConfigStore — atomic YAML configuration storage."""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path
from typing import Any

import platformdirs
import yaml

from .types import AppConfig


class ConfigStore:
    """Atomic YAML config storage with temp-file-then-rename writes."""

    def __init__(self, config_dir: Path | None = None) -> None:
        if config_dir is None:
            config_dir = Path(platformdirs.user_config_dir("eyes"))
        self._config_dir = config_dir
        self._config_file = config_dir / "config.yaml"

    def _ensure_dir(self) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> AppConfig:
        """Load config from YAML file, creating with defaults on first run."""
        self._ensure_dir()

        if not self._config_file.exists():
            default_config = AppConfig()
            self.save(default_config)
            return default_config

        try:
            with open(self._config_file) as f:
                data = yaml.safe_load(f)
            if data is None:
                data = {}
            return self._dict_to_config(data)
        except (yaml.YAMLError, OSError):
            # Invalid or corrupted config — return defaults
            return AppConfig()

    def save(self, config: AppConfig) -> None:
        """Atomically write config to YAML via temp-file-then-rename."""
        self._ensure_dir()

        data = self._config_to_dict(config)
        temp_file = self._config_file.with_suffix(".yaml.tmp")

        # Write to temp file first
        with open(temp_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)

        # Atomic rename
        shutil.move(str(temp_file), str(self._config_file))

    def update(self, **kwargs: Any) -> AppConfig:
        """Partial update: modify specified fields and save."""
        current = self.load()
        updated_data = self._config_to_dict(current)
        updated_data.update(kwargs)
        updated = self._dict_to_config(updated_data)
        self.save(updated)
        return updated

    def _config_to_dict(self, config: AppConfig) -> dict[str, Any]:
        """Convert AppConfig to dict for YAML serialization."""
        return {
            "yaw_threshold": config.yaw_threshold,
            "roll_threshold": config.roll_threshold,
            "neutral_yaw": config.neutral_yaw,
            "neutral_roll": config.neutral_roll,
            "camera_index": config.camera_index,
            "snooze_until_iso": config.snooze_until_iso,
            "sound_enabled": config.sound_enabled,
            "autostart_enabled": config.autostart_enabled,
            "language": config.language,
            "off_axis_streak_threshold_seconds": config.off_axis_streak_threshold_seconds,
            "off_axis_repeat_interval_seconds": config.off_axis_repeat_interval_seconds,
        }

    def _dict_to_config(self, data: dict[str, Any]) -> AppConfig:
        """Convert dict from YAML to AppConfig, using AppConfig defaults for missing keys."""
        defaults = AppConfig()
        return dataclasses.replace(defaults, **data)

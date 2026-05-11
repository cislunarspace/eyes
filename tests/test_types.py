"""Tests for persistence types."""

from __future__ import annotations

import pytest

from eyes.types import AppConfig, AppEventKind


class TestAppConfig:
    def test_default_values(self) -> None:
        config = AppConfig()
        assert config.yaw_threshold == 1.0
        assert config.roll_threshold == 90.0  # Disabled
        assert config.neutral_yaw == 0.0
        assert config.neutral_roll == 0.0
        assert config.camera_index == 0
        assert config.snooze_until_iso is None
        assert config.sound_enabled is False
        assert config.autostart_enabled is False
        assert config.language == "zh-CN"
        assert config.off_axis_streak_threshold_seconds == 1.0
        assert config.off_axis_repeat_interval_seconds == 10.0

    def test_custom_values(self) -> None:
        config = AppConfig(
            yaw_threshold=20.0,
            roll_threshold=15.0,
            neutral_yaw=5.0,
            neutral_roll=-3.0,
            camera_index=1,
            snooze_until_iso="2026-05-11T12:00:00+08:00",
            sound_enabled=True,
            autostart_enabled=True,
            language="en-US",
            off_axis_streak_threshold_seconds=3.0,
            off_axis_repeat_interval_seconds=20.0,
        )
        assert config.yaw_threshold == 20.0
        assert config.roll_threshold == 15.0
        assert config.neutral_yaw == 5.0
        assert config.neutral_roll == -3.0
        assert config.camera_index == 1
        assert config.snooze_until_iso == "2026-05-11T12:00:00+08:00"
        assert config.sound_enabled is True
        assert config.autostart_enabled is True
        assert config.language == "en-US"
        assert config.off_axis_streak_threshold_seconds == 3.0
        assert config.off_axis_repeat_interval_seconds == 20.0

    def test_is_frozen(self) -> None:
        config = AppConfig()
        with pytest.raises(AttributeError):
            config.yaw_threshold = 30.0  # type: ignore[index]


class TestAppEventKind:
    def test_all_event_kinds_exist(self) -> None:
        assert AppEventKind.STATE_CHANGE.value == "STATE_CHANGE"
        assert AppEventKind.PROMPT_FIRED.value == "PROMPT_FIRED"
        assert AppEventKind.CAMERA_UNAVAILABLE.value == "CAMERA_UNAVAILABLE"
        assert AppEventKind.CAMERA_RESUMED.value == "CAMERA_RESUMED"
        assert AppEventKind.SNOOZE_START.value == "SNOOZE_START"
        assert AppEventKind.SNOOZE_END.value == "SNOOZE_END"

    def test_kinds_are_strings(self) -> None:
        for kind in AppEventKind:
            assert isinstance(kind.value, str)


class TestWarningLevel:
    def test_enum_values(self) -> None:
        from eyes.types import WarningLevel

        assert WarningLevel.NORMAL.value == "NORMAL"
        assert WarningLevel.WARNING.value == "WARNING"
        assert WarningLevel.SEVERE.value == "SEVERE"
        assert WarningLevel.CORRECTED.value == "CORRECTED"

    def test_enum_members_count(self) -> None:
        from eyes.types import WarningLevel

        assert len(WarningLevel) == 4


class TestWarningLevelChanged:
    def test_event_kind_exists(self) -> None:
        assert AppEventKind.WARNING_LEVEL_CHANGED.value == "WARNING_LEVEL_CHANGED"


class TestWarningLevelEvent:
    def test_create_with_direction(self) -> None:
        from eyes.types import WarningLevel, WarningLevelEvent

        event = WarningLevelEvent(level=WarningLevel.WARNING, direction="left")
        assert event.level is WarningLevel.WARNING
        assert event.direction == "left"

    def test_create_without_direction(self) -> None:
        from eyes.types import WarningLevel, WarningLevelEvent

        event = WarningLevelEvent(level=WarningLevel.NORMAL, direction=None)
        assert event.level is WarningLevel.NORMAL
        assert event.direction is None

    def test_is_frozen(self) -> None:
        from eyes.types import WarningLevel, WarningLevelEvent

        event = WarningLevelEvent(level=WarningLevel.SEVERE, direction="right")
        with pytest.raises(AttributeError):
            event.level = WarningLevel.NORMAL  # type: ignore[index]

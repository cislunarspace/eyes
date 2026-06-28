"""Shared types for persistence layer."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AppConfig:
    """Application-wide configuration persisted to disk.

    Attributes:
        yaw_threshold: Yaw angle (degrees) beyond which the user is
            considered off-axis.
        pitch_threshold: Pitch angle (degrees) beyond which the user is
            considered looking up or down.
        pitch_hysteresis: Hysteresis band for pitch classification.
        neutral_yaw: Calibration baseline for yaw.
        neutral_pitch: Calibration baseline for pitch.
        camera_index: System camera device index.
        snooze_until_iso: ISO-8601 timestamp until which alerts are
            silenced, or ``None`` when not snoozed.
        sound_enabled: Whether audible alerts are enabled.
        autostart_enabled: Whether the app launches on system startup.
        language: UI locale string (e.g. ``"zh-CN"``).
        off_axis_streak_threshold_seconds: How long the user must be
            continuously off-axis before the streak accumulator fires.
        off_axis_repeat_interval_seconds: Minimum interval between
            consecutive off-axis alerts.
        facing_threshold_seconds: Continuous screen-facing time that
            triggers a posture reminder.
        eyest_threshold_seconds: Cumulative screen-facing time (within
            a sliding window) that triggers an eyestrain reminder.
    """

    yaw_threshold: float = 1.0
    pitch_threshold: float = 5.0
    pitch_hysteresis: float = 2.5
    neutral_yaw: float = 0.0
    neutral_pitch: float = 0.0
    camera_index: int = 0
    snooze_until_iso: Optional[str] = None
    sound_enabled: bool = False
    autostart_enabled: bool = False
    language: str = "zh-CN"
    off_axis_streak_threshold_seconds: float = 0.3
    off_axis_repeat_interval_seconds: float = 10.0
    facing_threshold_seconds: float = 300.0
    eyest_threshold_seconds: float = 900.0


class AppEventKind(enum.Enum):
    STATE_CHANGE = "STATE_CHANGE"
    PROMPT_FIRED = "PROMPT_FIRED"
    CAMERA_UNAVAILABLE = "CAMERA_UNAVAILABLE"
    CAMERA_RESUMED = "CAMERA_RESUMED"
    SNOOZE_START = "SNOOZE_START"
    SNOOZE_END = "SNOOZE_END"
    WARNING_LEVEL_CHANGED = "WARNING_LEVEL_CHANGED"


class WarningLevel(enum.Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    SEVERE = "SEVERE"
    CORRECTED = "CORRECTED"


class TrayIconState(enum.Enum):
    """Tray icon variants."""

    ACTIVE = "active"
    PAUSED = "paused"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class WarningLevelEvent:
    """A warning-level transition emitted by the accumulator engine.

    Attributes:
        level: Current warning severity.
        direction: Head direction that triggered the warning —
            ``"left"`` or ``"right"`` when the user is off-axis,
            ``None`` when facing the screen or the level is
            ``NORMAL``/``CORRECTED``.
    """

    level: WarningLevel
    direction: Optional[str]

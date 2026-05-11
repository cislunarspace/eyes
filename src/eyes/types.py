"""Shared types for persistence layer."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AppConfig:
    yaw_threshold: float = 1.0
    roll_threshold: float = 90.0  # Disabled: roll no longer affects classification
    neutral_yaw: float = 0.0
    neutral_roll: float = 0.0
    camera_index: int = 0
    snooze_until_iso: Optional[str] = None
    sound_enabled: bool = False
    autostart_enabled: bool = False
    language: str = "zh-CN"


class AppEventKind(enum.Enum):
    STATE_CHANGE = "STATE_CHANGE"
    PROMPT_FIRED = "PROMPT_FIRED"
    CAMERA_UNAVAILABLE = "CAMERA_UNAVAILABLE"
    CAMERA_RESUMED = "CAMERA_RESUMED"
    SNOOZE_START = "SNOOZE_START"
    SNOOZE_END = "SNOOZE_END"

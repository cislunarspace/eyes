"""PostureTickEngine — unified posture timing engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from .classifier import PoseState
from .types import WarningLevel, WarningLevelEvent


@dataclass(frozen=True)
class CorrectionEvent:
    direction: PoseState


@dataclass(frozen=True)
class GoodPostureEvent:
    pass


@dataclass(frozen=True)
class EyeRestEvent:
    pass


SenseEvent = Union[CorrectionEvent, GoodPostureEvent, EyeRestEvent, WarningLevelEvent]

_DEFAULT_OFF_AXIS_STREAK_THRESHOLD = 0.3
_DEFAULT_OFF_AXIS_REPEAT_INTERVAL = 10.0
_DEFAULT_FACING_THRESHOLD = 300.0
_DEFAULT_EYEREST_THRESHOLD = 900.0


class PostureTickEngine:
    """Unified engine tracking off-axis streaks, facing time, presence time, and warning levels."""

    def __init__(
        self,
        *,
        off_axis_streak_threshold_seconds: float | None = None,
        off_axis_repeat_interval_seconds: float | None = None,
        facing_threshold_seconds: float | None = None,
        eyest_threshold_seconds: float | None = None,
    ) -> None:
        self._off_axis_streak_threshold = (
            off_axis_streak_threshold_seconds
            if off_axis_streak_threshold_seconds is not None
            else _DEFAULT_OFF_AXIS_STREAK_THRESHOLD
        )
        self._off_axis_repeat_interval = (
            off_axis_repeat_interval_seconds
            if off_axis_repeat_interval_seconds is not None
            else _DEFAULT_OFF_AXIS_REPEAT_INTERVAL
        )
        self._facing_threshold = (
            facing_threshold_seconds
            if facing_threshold_seconds is not None
            else _DEFAULT_FACING_THRESHOLD
        )
        self._eyest_threshold = (
            eyest_threshold_seconds
            if eyest_threshold_seconds is not None
            else _DEFAULT_EYEREST_THRESHOLD
        )
        self._off_axis_streak: float = 0.0
        self._repeat_due_at: Optional[float] = None
        self._last_emit_at: Optional[float] = None
        self._facing_seconds: float = 0.0
        self._presence_seconds: float = 0.0
        self._snoozed: bool = False
        self._warning_level: WarningLevel = WarningLevel.NORMAL
        self._warning_direction: Optional[str] = None
        self._warning_event: Optional[WarningLevelEvent] = None
        self._off_axis_continuous_seconds: float = 0.0
        self._corrected_remaining_seconds: float = 0.0

    @property
    def is_snoozed(self) -> bool:
        return self._snoozed

    def snooze(self) -> None:
        self._snoozed = True

    def resume(self) -> None:
        self._snoozed = False

    def tick(self, state: PoseState, dt: float) -> list[SenseEvent]:
        events: list[SenseEvent] = []
        self._warning_event = None

        if self._snoozed:
            return events

        # Off-axis streak tracking
        if state in (PoseState.OFF_AXIS_LEFT, PoseState.OFF_AXIS_RIGHT):
            self._off_axis_streak += dt
            if self._off_axis_streak >= self._off_axis_streak_threshold:
                if self._last_emit_at is None:
                    self._last_emit_at = self._off_axis_streak
                    self._repeat_due_at = self._off_axis_streak + self._off_axis_repeat_interval
                    events.append(CorrectionEvent(direction=state))
                elif self._repeat_due_at is not None and self._off_axis_streak >= self._repeat_due_at:
                    self._repeat_due_at = self._off_axis_streak + self._off_axis_repeat_interval
                    events.append(CorrectionEvent(direction=state))
        else:
            self._off_axis_streak = 0.0
            self._repeat_due_at = None
            self._last_emit_at = None

        # Facing time accumulation
        if state == PoseState.FACING_SCREEN:
            self._facing_seconds += dt
            if self._facing_seconds >= self._facing_threshold:
                self._facing_seconds = 0.0
                events.append(GoodPostureEvent())

        # Presence time accumulation
        if state != PoseState.NO_FACE:
            self._presence_seconds += dt
            if self._presence_seconds >= self._eyest_threshold:
                self._presence_seconds = 0.0
                events.append(EyeRestEvent())

        # Warning level state machine
        if state in (PoseState.OFF_AXIS_LEFT, PoseState.OFF_AXIS_RIGHT):
            direction = "left" if state == PoseState.OFF_AXIS_LEFT else "right"
            if self._warning_level in (WarningLevel.NORMAL, WarningLevel.CORRECTED):
                self._warning_level = WarningLevel.WARNING
                self._warning_direction = direction
                self._off_axis_continuous_seconds = dt
                self._warning_event = WarningLevelEvent(
                    level=WarningLevel.WARNING,
                    direction=direction,
                )
                events.append(self._warning_event)
            else:
                self._warning_direction = direction
                self._off_axis_continuous_seconds += dt
                if (
                    self._warning_level == WarningLevel.WARNING
                    and self._off_axis_continuous_seconds >= self._off_axis_repeat_interval
                ):
                    self._warning_level = WarningLevel.SEVERE
                    self._warning_event = WarningLevelEvent(
                        level=WarningLevel.SEVERE,
                        direction=direction,
                    )
                    events.append(self._warning_event)
        elif state == PoseState.FACING_SCREEN:
            if self._warning_level in (WarningLevel.WARNING, WarningLevel.SEVERE):
                self._warning_level = WarningLevel.CORRECTED
                self._corrected_remaining_seconds = 2.0
                self._warning_event = WarningLevelEvent(
                    level=WarningLevel.CORRECTED,
                    direction=None,
                )
                events.append(self._warning_event)
                self._off_axis_continuous_seconds = 0.0
            elif self._warning_level == WarningLevel.CORRECTED:
                self._corrected_remaining_seconds -= dt
                if self._corrected_remaining_seconds <= 0:
                    self._warning_level = WarningLevel.NORMAL
                    self._warning_event = WarningLevelEvent(
                        level=WarningLevel.NORMAL,
                        direction=None,
                    )
                    events.append(self._warning_event)
                    self._corrected_remaining_seconds = 0.0
        elif state == PoseState.NO_FACE:
            if self._warning_level in (WarningLevel.WARNING, WarningLevel.SEVERE, WarningLevel.CORRECTED):
                self._warning_level = WarningLevel.NORMAL
                self._warning_event = WarningLevelEvent(
                    level=WarningLevel.NORMAL,
                    direction=None,
                )
                events.append(self._warning_event)
                self._off_axis_continuous_seconds = 0.0
                self._corrected_remaining_seconds = 0.0

        return events

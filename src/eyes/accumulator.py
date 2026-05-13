"""AccumulatorEngine — pure state machine for off-axis time tracking."""

from __future__ import annotations

from typing import Optional, Protocol

from .classifier import PoseState
from .types import WarningLevel, WarningLevelEvent

_DEFAULT_OFF_AXIS_STREAK_THRESHOLD = 1.0
_DEFAULT_OFF_AXIS_REPEAT_INTERVAL = 10.0


class SnoozeTarget(Protocol):
    def snooze(self) -> None: ...
    def resume(self) -> None: ...


class AccumulatorEngine:
    """Tracks off-axis streak time and emits correction events."""

    def __init__(
        self,
        *,
        off_axis_streak_threshold_seconds: float | None = None,
        off_axis_repeat_interval_seconds: float | None = None,
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
        self._off_axis_streak: float = 0.0
        self._repeat_due_at: Optional[float] = None
        self._last_emit_at: Optional[float] = None
        self._snoozed: bool = False
        self._snooze_targets: list[SnoozeTarget] = []
        self._warning_level: WarningLevel = WarningLevel.NORMAL
        self._warning_direction: Optional[str] = None
        self._warning_event: Optional[WarningLevelEvent] = None
        self._off_axis_continuous_seconds: float = 0.0
        self._corrected_remaining_seconds: float = 0.0

    @property
    def is_snoozed(self) -> bool:
        return self._snoozed

    def register_snooze_target(self, target: SnoozeTarget) -> None:
        self._snooze_targets.append(target)

    def snooze(self) -> None:
        self._snoozed = True
        for target in self._snooze_targets:
            target.snooze()

    def resume(self) -> None:
        self._snoozed = False
        for target in self._snooze_targets:
            target.resume()

    @property
    def warning_event(self) -> Optional[WarningLevelEvent]:
        return self._warning_event

    def tick(self, state: PoseState, dt: float) -> Optional[PoseState]:
        self._warning_event = None

        if self._snoozed:
            return None

        correction: Optional[PoseState] = None

        if state in (PoseState.OFF_AXIS_LEFT, PoseState.OFF_AXIS_RIGHT):
            self._off_axis_streak += dt

            if self._off_axis_streak >= self._off_axis_streak_threshold:
                if self._last_emit_at is None:
                    self._last_emit_at = self._off_axis_streak
                    self._repeat_due_at = self._off_axis_streak + self._off_axis_repeat_interval
                    correction = state
                elif self._repeat_due_at is not None and self._off_axis_streak >= self._repeat_due_at:
                    self._repeat_due_at = self._off_axis_streak + self._off_axis_repeat_interval
                    correction = state
        else:
            self._off_axis_streak = 0.0
            self._repeat_due_at = None
            self._last_emit_at = None

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
        elif state == PoseState.FACING_SCREEN:
            if self._warning_level in (WarningLevel.WARNING, WarningLevel.SEVERE):
                self._warning_level = WarningLevel.CORRECTED
                self._corrected_remaining_seconds = 2.0
                self._warning_event = WarningLevelEvent(
                    level=WarningLevel.CORRECTED,
                    direction=None,
                )
                self._off_axis_continuous_seconds = 0.0
            elif self._warning_level == WarningLevel.CORRECTED:
                self._corrected_remaining_seconds -= dt
                if self._corrected_remaining_seconds <= 0:
                    self._warning_level = WarningLevel.NORMAL
                    self._warning_event = WarningLevelEvent(
                        level=WarningLevel.NORMAL,
                        direction=None,
                    )
                    self._corrected_remaining_seconds = 0.0
        elif state == PoseState.NO_FACE:
            if self._warning_level in (WarningLevel.WARNING, WarningLevel.SEVERE, WarningLevel.CORRECTED):
                self._warning_level = WarningLevel.NORMAL
                self._warning_event = WarningLevelEvent(
                    level=WarningLevel.NORMAL,
                    direction=None,
                )
                self._off_axis_continuous_seconds = 0.0
                self._corrected_remaining_seconds = 0.0

        return correction

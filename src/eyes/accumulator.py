"""AccumulatorEngine — pure state machine for off-axis time tracking."""

from __future__ import annotations

from typing import Optional

from .classifier import PoseState
from .types import WarningLevel, WarningLevelEvent

# Default constants (can be overridden via constructor)
_DEFAULT_OFF_AXIS_STREAK_THRESHOLD = 1.0
_DEFAULT_OFF_AXIS_REPEAT_INTERVAL = 10.0
_DEFAULT_FACING_THRESHOLD = 300.0
_DEFAULT_EYEREST_THRESHOLD = 900.0


class AccumulatorEngine:
    """Tracks off-axis streak time and emits correction events.

    Public interface:
      tick(state, dt) -> Optional[PoseState]  # Returns state that triggered, or None
      warning_event: Optional[WarningLevelEvent]  # Set when warning level changes
      good_posture_due: bool  # True when facing accumulator reaches threshold (S4)
      eye_rest_due: bool  # True when presence accumulator reaches threshold (S5)
      facing_accumulator_seconds: float  # Current accumulated facing time
      presence_accumulator_seconds: float  # Current accumulated presence time
      acknowledge() -> None  # Clear good_posture_due and eye_rest_due flags

    No time.time() inside — pure state machine driven by external dt ticks.

    Note on Facing Time Accumulator (S4):
      CUMULATIVE, not wall-clock and not strict-streak.
      Advances at +1s/s while FACING_SCREEN.
      Brief deviations (OFF_AXIS_*, NO_FACE) PAUSE but do NOT reset.

    Note on Presence Time Accumulator (S5):
      CUMULATIVE, independent of yaw/roll.
      Advances at +1s/s while any face is detected (not NO_FACE).
      NO_FACE PAUSES but does NOT reset.
    """

    def __init__(
        self,
        *,
        facing_threshold_seconds: float | None = None,
        eyest_threshold_seconds: float | None = None,
        off_axis_streak_threshold_seconds: float | None = None,
        off_axis_repeat_interval_seconds: float | None = None,
    ) -> None:
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
        # S4: Facing Time Accumulator — cumulative facing screen time
        self._facing_seconds: float = 0.0
        self._good_posture_due: bool = False
        # S5: Presence Time Accumulator — cumulative face-detected time
        self._presence_seconds: float = 0.0
        self._eye_rest_due: bool = False
        # S7: Snooze state
        self._snoozed: bool = False
        # Warning level state machine
        self._warning_level: WarningLevel = WarningLevel.NORMAL
        self._warning_direction: Optional[str] = None
        self._warning_event: Optional[WarningLevelEvent] = None
        self._off_axis_continuous_seconds: float = 0.0
        self._corrected_remaining_seconds: float = 0.0

    @property
    def good_posture_due(self) -> bool:
        """True if GoodPostureDue event should be shown."""
        return self._good_posture_due

    @property
    def eye_rest_due(self) -> bool:
        """True if EyeRestDue event should be shown."""
        return self._eye_rest_due

    @property
    def facing_accumulator_seconds(self) -> float:
        """Current accumulated facing time in seconds."""
        return self._facing_seconds

    @property
    def presence_accumulator_seconds(self) -> float:
        """Current accumulated presence time in seconds."""
        return self._presence_seconds

    def acknowledge(self) -> None:
        """Clear good_posture_due and eye_rest_due flags after showing overlay."""
        self._good_posture_due = False
        self._eye_rest_due = False

    @property
    def is_snoozed(self) -> bool:
        """True if snooze is active (accumulator frozen)."""
        return self._snoozed

    def snooze(self) -> None:
        """Enter snooze mode: freeze all accumulators and off-axis streak."""
        self._snoozed = True

    def resume(self) -> None:
        """Exit snooze mode: resume accumulating from current values."""
        self._snoozed = False

    @property
    def warning_event(self) -> Optional[WarningLevelEvent]:
        """Warning level event from last tick, or None if no change."""
        return self._warning_event

    def tick(self, state: PoseState, dt: float) -> Optional[PoseState]:
        """Process one tick and return if correction is due."""
        self._warning_event = None

        # S7: During snooze, accumulate nothing but do not reset anything
        if self._snoozed:
            return None

        correction: Optional[PoseState] = None

        if state in (PoseState.OFF_AXIS_LEFT, PoseState.OFF_AXIS_RIGHT):
            self._off_axis_streak += dt

            if self._off_axis_streak >= self._off_axis_streak_threshold:
                if self._last_emit_at is None:
                    # First prompt
                    self._last_emit_at = self._off_axis_streak
                    self._repeat_due_at = self._off_axis_streak + self._off_axis_repeat_interval
                    correction = state
                elif self._repeat_due_at is not None and self._off_axis_streak >= self._repeat_due_at:
                    # Repeat prompt
                    self._repeat_due_at = self._off_axis_streak + self._off_axis_repeat_interval
                    correction = state
        else:
            self._off_axis_streak = 0.0
            self._repeat_due_at = None
            self._last_emit_at = None

        # S4: Facing Time Accumulator
        if state == PoseState.FACING_SCREEN:
            self._facing_seconds += dt
            if self._facing_seconds >= self._facing_threshold:
                self._good_posture_due = True
                self._facing_seconds = 0.0  # Reset for new cycle

        # S5: Presence Time Accumulator — advances for any face-detected state
        if state != PoseState.NO_FACE:
            self._presence_seconds += dt
            if self._presence_seconds >= self._eyest_threshold:
                self._eye_rest_due = True
                self._presence_seconds = 0.0  # Reset for new cycle

        # Warning level state machine
        if state in (PoseState.OFF_AXIS_LEFT, PoseState.OFF_AXIS_RIGHT):
            direction = "left" if state == PoseState.OFF_AXIS_LEFT else "right"
            if self._warning_level == WarningLevel.NORMAL or self._warning_level == WarningLevel.CORRECTED:
                self._warning_level = WarningLevel.WARNING
                self._warning_direction = direction
                self._off_axis_continuous_seconds = dt
                self._warning_event = WarningLevelEvent(
                    level=WarningLevel.WARNING, direction=direction,
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
                        level=WarningLevel.SEVERE, direction=direction,
                    )
        elif state == PoseState.FACING_SCREEN:
            if self._warning_level in (WarningLevel.WARNING, WarningLevel.SEVERE):
                self._warning_level = WarningLevel.CORRECTED
                self._corrected_remaining_seconds = 2.0
                self._warning_event = WarningLevelEvent(
                    level=WarningLevel.CORRECTED, direction=None,
                )
                self._off_axis_continuous_seconds = 0.0
            elif self._warning_level == WarningLevel.CORRECTED:
                self._corrected_remaining_seconds -= dt
                if self._corrected_remaining_seconds <= 0:
                    self._warning_level = WarningLevel.NORMAL
                    self._corrected_remaining_seconds = 0.0
        elif state == PoseState.NO_FACE:
            if self._warning_level in (WarningLevel.WARNING, WarningLevel.SEVERE, WarningLevel.CORRECTED):
                self._warning_level = WarningLevel.NORMAL
                self._off_axis_continuous_seconds = 0.0
                self._corrected_remaining_seconds = 0.0

        return correction

"""AccumulatorEngine — pure state machine for off-axis time tracking."""

from __future__ import annotations

import os
from typing import Optional

from .classifier import PoseState

# Constants
_FIRST_PROMPT_SECONDS = 5.0
_REPEAT_INTERVAL_SECONDS = 30.0
_FACING_THRESHOLD_SECONDS = 300.0
_EYEREST_THRESHOLD_SECONDS = 900.0


def _get_facing_threshold() -> float:
    """Get facing threshold from env var for dev convenience, or use default."""
    env_val = os.environ.get("EYES_FACING_THRESHOLD_SECONDS")
    if env_val is not None:
        try:
            return float(env_val)
        except ValueError:
            return _FACING_THRESHOLD_SECONDS
    return _FACING_THRESHOLD_SECONDS


def _get_eyest_threshold() -> float:
    """Get eye-rest threshold from env var for dev convenience, or use default."""
    env_val = os.environ.get("EYES_EYEREST_THRESHOLD_SECONDS")
    if env_val is not None:
        try:
            return float(env_val)
        except ValueError:
            return _EYEREST_THRESHOLD_SECONDS
    return _EYEREST_THRESHOLD_SECONDS


class AccumulatorEngine:
    """Tracks off-axis streak time and emits correction events.

    Public interface:
      tick(state, dt) -> Optional[PoseState]  # Returns state that triggered, or None
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
    ) -> None:
        self._facing_threshold = facing_threshold_seconds or _get_facing_threshold()
        self._eyest_threshold = eyest_threshold_seconds or _get_eyest_threshold()
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

    def tick(self, state: PoseState, dt: float) -> Optional[PoseState]:
        """Process one tick and return if correction is due."""
        # S7: During snooze, accumulate nothing but do not reset anything
        if self._snoozed:
            return None

        if state in (PoseState.OFF_AXIS_LEFT, PoseState.OFF_AXIS_RIGHT):
            self._off_axis_streak += dt

            if self._off_axis_streak >= _FIRST_PROMPT_SECONDS:
                if self._last_emit_at is None:
                    # First prompt
                    self._last_emit_at = self._off_axis_streak
                    self._repeat_due_at = self._off_axis_streak + _REPEAT_INTERVAL_SECONDS
                    return state
                elif self._repeat_due_at is not None and self._off_axis_streak >= self._repeat_due_at:
                    # Repeat prompt
                    self._repeat_due_at = self._off_axis_streak + _REPEAT_INTERVAL_SECONDS
                    return state
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

        return None

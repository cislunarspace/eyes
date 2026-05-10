"""AccumulatorEngine — pure state machine for off-axis time tracking."""

from __future__ import annotations

import os
from typing import Optional

from .classifier import PoseState

# Constants
_FIRST_PROMPT_SECONDS = 5.0
_REPEAT_INTERVAL_SECONDS = 30.0
_FACING_THRESHOLD_SECONDS = 300.0


def _get_facing_threshold() -> float:
    """Get facing threshold from env var for dev convenience, or use default."""
    env_val = os.environ.get("EYES_FACING_THRESHOLD_SECONDS")
    if env_val is not None:
        try:
            return float(env_val)
        except ValueError:
            return _FACING_THRESHOLD_SECONDS
    return _FACING_THRESHOLD_SECONDS


class AccumulatorEngine:
    """Tracks off-axis streak time and emits correction events.

    Public interface:
      tick(state, dt) -> Optional[PoseState]  # Returns state that triggered, or None
      good_posture_due: bool  # True when facing accumulator reaches threshold
      facing_accumulator_seconds: float  # Current accumulated facing time
      acknowledge() -> None  # Clear good_posture_due flag after showing overlay

    No time.time() inside — pure state machine driven by external dt ticks.

    Note on Facing Time Accumulator:
      The threshold timer is CUMULATIVE, not wall-clock and not strict-streak.
      While the user is FACING_SCREEN, the accumulator advances at +1s/s.
      Brief deviations (OFF_AXIS_*, NO_FACE) PAUSE accumulation but do NOT reset it.
      This means short interruptions (water sip, glance at phone) do not penalize the user.
    """

    def __init__(
        self,
        *,
        facing_threshold_seconds: float | None = None,
    ) -> None:
        self._facing_threshold = facing_threshold_seconds or _get_facing_threshold()
        self._off_axis_streak: float = 0.0
        self._repeat_due_at: Optional[float] = None  # Accumulated time when next repeat is due
        self._last_emit_at: Optional[float] = None
        # Facing Time Accumulator (S4) — cumulative, not wall-clock
        self._facing_seconds: float = 0.0
        self._good_posture_due: bool = False

    @property
    def good_posture_due(self) -> bool:
        """True if GoodPostureDue event should be shown."""
        return self._good_posture_due

    @property
    def facing_accumulator_seconds(self) -> float:
        """Current accumulated facing time in seconds."""
        return self._facing_seconds

    def acknowledge(self) -> None:
        """Clear the good_posture_due flag after showing the overlay."""
        self._good_posture_due = False

    def tick(self, state: PoseState, dt: float) -> Optional[PoseState]:
        """Process one tick and return if correction is due."""
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

        return None

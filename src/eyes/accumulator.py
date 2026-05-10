"""AccumulatorEngine — pure state machine for off-axis time tracking."""

from __future__ import annotations

from typing import Optional

from .classifier import PoseState

# Constants
_FIRST_PROMPT_SECONDS = 5.0
_REPEAT_INTERVAL_SECONDS = 30.0


class AccumulatorEngine:
    """Tracks off-axis streak time and emits correction events.

    Public interface:
      tick(state, dt) -> Optional[PoseState]  # Returns state that triggered, or None

    No time.time() inside — pure state machine driven by external dt ticks.
    """

    def __init__(self) -> None:
        self._off_axis_streak: float = 0.0
        self._repeat_due_at: Optional[float] = None  # Accumulated time when next repeat is due
        self._last_emit_at: Optional[float] = None

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

        return None

"""FacingTimeAccumulator — tracks continuous screen-facing time and fires at a threshold."""

from __future__ import annotations

from .classifier import PoseState

_DEFAULT_FACING_THRESHOLD = 300.0


class FacingTimeAccumulator:
    """Accumulates time spent facing the screen; emits True when the threshold is reached."""
    def __init__(self, *, threshold_seconds: float | None = None) -> None:
        self._threshold = threshold_seconds if threshold_seconds is not None else _DEFAULT_FACING_THRESHOLD
        self._accumulated_seconds = 0.0
        self._snoozed = False

    @property
    def accumulated_seconds(self) -> float:
        return self._accumulated_seconds

    @property
    def is_snoozed(self) -> bool:
        return self._snoozed

    def tick(self, state: PoseState, dt: float) -> bool:
        """Accumulate *dt* while facing the screen.  Resets and returns True at threshold."""
        if self._snoozed or state != PoseState.FACING_SCREEN:
            return False

        self._accumulated_seconds += dt
        if self._accumulated_seconds >= self._threshold:
            self._accumulated_seconds = 0.0
            return True
        return False

    def acknowledge(self) -> None:
        """No-op. Exists to satisfy the SnoozeTarget protocol used by AccumulatorEngine."""

    def snooze(self) -> None:
        self._snoozed = True

    def resume(self) -> None:
        self._snoozed = False

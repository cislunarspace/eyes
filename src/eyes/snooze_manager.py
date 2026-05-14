"""SnoozeManager — handles pause/resume lifecycle for accumulator and tray."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from .tray_controller import TrayIconState


class ConfigStoreLike(Protocol):
    """Minimal interface for reading and persisting snooze timestamps."""
    def load(self) -> Any: ...
    def update(self, **kwargs: Any) -> Any: ...


class AccumulatorLike(Protocol):
    """Interface for freezing and unfreezing the accumulation engine."""
    def snooze(self) -> None: ...
    def resume(self) -> None: ...


class TrayLike(Protocol):
    """Interface for updating the system-tray icon to reflect current state."""
    def set_state(self, state: TrayIconState) -> None: ...


class SnoozeManager:
    """Manages snooze lifecycle: persistence, expiry checking, and component coordination.

    Coordinates AccumulatorEngine (freeze/unfreeze) and TrayController (icon state)
    based on persisted snooze timestamps in ConfigStore.

    Public interface:
      pause(duration_seconds: int | None) -> None
          Start a timed or indefinite snooze.
      resume() -> None
          End snooze immediately.
      check_expiry() -> None
          Check if timed snooze has expired; if so, resume. Call each tick.
      restore_persisted_state() -> None
          On startup, check if a snooze was persisted from a previous session.
    """

    def __init__(
        self,
        config_store: ConfigStoreLike,
        accumulator: AccumulatorLike,
        tray: TrayLike,
        on_snooze_end: Callable[[], None] | None = None,
    ) -> None:
        self._config_store = config_store
        self._accumulator = accumulator
        self._tray = tray
        self._on_snooze_end = on_snooze_end

    def pause(self, duration_seconds: int | None) -> None:
        """Start a timed or indefinite snooze."""
        if duration_seconds is None:
            self._config_store.update(snooze_until_iso="indefinite")
        else:
            now = datetime.now(timezone.utc)
            expires = now + timedelta(seconds=duration_seconds)
            self._config_store.update(snooze_until_iso=expires.isoformat())

        self._accumulator.snooze()
        self._tray.set_state(TrayIconState.PAUSED)

    def resume(self) -> None:
        """End snooze immediately."""
        self._accumulator.resume()
        self._tray.set_state(TrayIconState.ACTIVE)
        self._config_store.update(snooze_until_iso=None)

    def check_expiry(self) -> None:
        """Check if timed snooze has expired; if so, resume and clear."""
        snooze_until = self._config_store.load().snooze_until_iso
        if snooze_until is None or snooze_until == "indefinite":
            return

        try:
            snooze_time = datetime.fromisoformat(snooze_until)
            if snooze_time.tzinfo is None:
                snooze_time = snooze_time.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if now >= snooze_time:
                self._accumulator.resume()
                self._tray.set_state(TrayIconState.ACTIVE)
                self._config_store.update(snooze_until_iso=None)
                if self._on_snooze_end is not None:
                    self._on_snooze_end()
        except ValueError:
            self._config_store.update(snooze_until_iso=None)

    def restore_persisted_state(self) -> None:
        """On startup, restore snooze state from previous session."""
        snooze_until = self._config_store.load().snooze_until_iso
        if snooze_until is None:
            return

        if snooze_until == "indefinite":
            self._accumulator.snooze()
            self._tray.set_state(TrayIconState.PAUSED)
            return

        try:
            snooze_time = datetime.fromisoformat(snooze_until)
            if snooze_time.tzinfo is None:
                snooze_time = snooze_time.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if now >= snooze_time:
                self._config_store.update(snooze_until_iso=None)
            else:
                self._accumulator.snooze()
                self._tray.set_state(TrayIconState.PAUSED)
        except ValueError:
            self._config_store.update(snooze_until_iso=None)

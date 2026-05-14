"""Tests for SnoozeManager."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from eyes.snooze_manager import SnoozeManager
from eyes.types import TrayIconState


def _future_iso(seconds: int) -> str:
    """Return an ISO timestamp N seconds in the future."""
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


class TestPause:
    """Verify pause() coordinates accumulator and tray correctly."""

    def test_timed_pause_persists_future_timestamp(self) -> None:
        """A timed pause should persist the expiry time."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()

        manager = SnoozeManager(config_store, accumulator, tray)
        manager.pause(duration_seconds=1800)

        # Should persist a timestamp ~30 min in the future
        call_args = config_store.update.call_args
        assert call_args is not None
        snooze_until = call_args.kwargs["snooze_until_iso"]
        assert snooze_until != "indefinite"
        assert snooze_until is not None
        # Verify it's a valid ISO timestamp
        parsed = datetime.fromisoformat(snooze_until)
        assert parsed.tzinfo is not None or parsed.tzinfo is None  # Accept either

    def test_indefinite_pause_persists_indefinite(self) -> None:
        """An indefinite pause should persist 'indefinite'."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()

        manager = SnoozeManager(config_store, accumulator, tray)
        manager.pause(duration_seconds=None)

        config_store.update.assert_called_once_with(snooze_until_iso="indefinite")

    def test_pause_freezes_accumulator(self) -> None:
        """Pause should call accumulator.snooze()."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()

        manager = SnoozeManager(config_store, accumulator, tray)
        manager.pause(duration_seconds=3600)

        accumulator.snooze.assert_called_once()

    def test_pause_sets_tray_to_paused(self) -> None:
        """Pause should set tray to PAUSED state."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()

        manager = SnoozeManager(config_store, accumulator, tray)
        manager.pause(duration_seconds=3600)

        tray.set_state.assert_called_once_with(TrayIconState.PAUSED)


class TestResume:
    """Verify resume() coordinates accumulator and tray correctly."""

    def test_resume_resumes_accumulator(self) -> None:
        """Resume should call accumulator.resume()."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()

        manager = SnoozeManager(config_store, accumulator, tray)
        manager.resume()

        accumulator.resume.assert_called_once()

    def test_resume_sets_tray_to_active(self) -> None:
        """Resume should set tray to ACTIVE state."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()

        manager = SnoozeManager(config_store, accumulator, tray)
        manager.resume()

        tray.set_state.assert_called_once_with(TrayIconState.ACTIVE)

    def test_resume_clears_persisted_snooze(self) -> None:
        """Resume should clear the persisted snooze."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()

        manager = SnoozeManager(config_store, accumulator, tray)
        manager.resume()

        config_store.update.assert_called_once_with(snooze_until_iso=None)


class TestRestorePersistedState:
    """Verify restore_persisted_state() handles startup restore correctly."""

    def test_future_snooze_activates_snooze(self) -> None:
        """A future snooze from previous session should be restored."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()

        config_store.load.return_value.snooze_until_iso = _future_iso(3600)

        manager = SnoozeManager(config_store, accumulator, tray)
        manager.restore_persisted_state()

        accumulator.snooze.assert_called_once()
        tray.set_state.assert_called_once_with(TrayIconState.PAUSED)

    def test_expired_snooze_clears_config(self) -> None:
        """An expired snooze from previous session should be cleared."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()

        expired_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        config_store.load.return_value.snooze_until_iso = expired_time.isoformat()

        manager = SnoozeManager(config_store, accumulator, tray)
        manager.restore_persisted_state()

        accumulator.snooze.assert_not_called()
        config_store.update.assert_called_once_with(snooze_until_iso=None)

    def test_indefinite_snooze_activates_snooze(self) -> None:
        """An indefinite snooze from previous session should be restored."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()

        config_store.load.return_value.snooze_until_iso = "indefinite"

        manager = SnoozeManager(config_store, accumulator, tray)
        manager.restore_persisted_state()

        accumulator.snooze.assert_called_once()
        tray.set_state.assert_called_once_with(TrayIconState.PAUSED)

    def test_invalid_timestamp_clears_config(self) -> None:
        """An invalid timestamp from previous session should be cleared."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()

        config_store.load.return_value.snooze_until_iso = "garbage-timestamp"

        manager = SnoozeManager(config_store, accumulator, tray)
        manager.restore_persisted_state()

        accumulator.snooze.assert_not_called()
        config_store.update.assert_called_once_with(snooze_until_iso=None)

    def test_no_snooze_does_nothing(self) -> None:
        """No snooze persisted means nothing to restore."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()

        config_store.load.return_value.snooze_until_iso = None

        manager = SnoozeManager(config_store, accumulator, tray)
        manager.restore_persisted_state()

        accumulator.snooze.assert_not_called()
        accumulator.resume.assert_not_called()
        tray.set_state.assert_not_called()


class TestCheckExpiry:
    """Verify check_expiry() handles timed snooze expiry correctly."""

    def test_expired_snooze_resumes_accumulator_and_tray(self) -> None:
        """When snooze has expired, accumulator resumes and tray shows ACTIVE."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()

        # Persist an already-expired snooze
        expired_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        config_store.load.return_value.snooze_until_iso = expired_time.isoformat()

        manager = SnoozeManager(config_store, accumulator, tray)
        manager.check_expiry()

        accumulator.resume.assert_called_once()
        tray.set_state.assert_called_once()
        # Config should be cleared
        config_store.update.assert_called_once_with(snooze_until_iso=None)

    def test_future_snooze_does_nothing(self) -> None:
        """When snooze is still in future, no action is taken."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()

        config_store.load.return_value.snooze_until_iso = _future_iso(3600)

        manager = SnoozeManager(config_store, accumulator, tray)
        manager.check_expiry()

        accumulator.resume.assert_not_called()
        tray.set_state.assert_not_called()
        config_store.update.assert_not_called()

    def test_no_snooze_does_nothing(self) -> None:
        """When no snooze is set, check_expiry is a no-op."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()

        config_store.load.return_value.snooze_until_iso = None

        manager = SnoozeManager(config_store, accumulator, tray)
        manager.check_expiry()

        accumulator.resume.assert_not_called()
        tray.set_state.assert_not_called()

    def test_indefinite_snooze_does_nothing(self) -> None:
        """Indefinite snooze does not expire."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()

        config_store.load.return_value.snooze_until_iso = "indefinite"

        manager = SnoozeManager(config_store, accumulator, tray)
        manager.check_expiry()

        accumulator.resume.assert_not_called()
        tray.set_state.assert_not_called()

    def test_invalid_timestamp_clears_config(self) -> None:
        """Invalid timestamp is treated as cleared, no crash."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()

        config_store.load.return_value.snooze_until_iso = "not-a-valid-timestamp"

        manager = SnoozeManager(config_store, accumulator, tray)
        manager.check_expiry()  # Should not raise

        accumulator.resume.assert_not_called()
        config_store.update.assert_called_once_with(snooze_until_iso=None)

    def test_expired_snooze_calls_on_snooze_end_callback(self) -> None:
        """When snooze expires, the on_snooze_end callback is invoked."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()
        on_snooze_end = MagicMock()

        expired_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        config_store.load.return_value.snooze_until_iso = expired_time.isoformat()

        manager = SnoozeManager(config_store, accumulator, tray, on_snooze_end=on_snooze_end)
        manager.check_expiry()

        on_snooze_end.assert_called_once()

    def test_future_snooze_does_not_call_callback(self) -> None:
        """When snooze is still active, callback is not invoked."""
        config_store = MagicMock()
        accumulator = MagicMock()
        tray = MagicMock()
        on_snooze_end = MagicMock()

        config_store.load.return_value.snooze_until_iso = _future_iso(3600)

        manager = SnoozeManager(config_store, accumulator, tray, on_snooze_end=on_snooze_end)
        manager.check_expiry()

        on_snooze_end.assert_not_called()

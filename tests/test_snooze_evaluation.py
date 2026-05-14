"""Tests for evaluate_snooze pure function.

These tests deliberately avoid mocking ConfigStoreLike / AccumulatorLike / TrayLike.
The function under test is pure: (iso_string, now) -> SnoozeState.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from eyes.snooze_evaluation import (
    Active,
    Expired,
    Indefinite,
    Inactive,
    Malformed,
    evaluate_snooze,
)


NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


class TestEvaluateSnooze:
    """evaluate_snooze maps a persisted ISO string to a SnoozeState."""

    def test_none_yields_inactive(self) -> None:
        assert evaluate_snooze(None, NOW) == Inactive()

    def test_indefinite_string_yields_indefinite(self) -> None:
        assert evaluate_snooze("indefinite", NOW) == Indefinite()

    def test_future_timestamp_yields_active_with_until(self) -> None:
        future = NOW + timedelta(hours=1)
        result = evaluate_snooze(future.isoformat(), NOW)
        assert result == Active(until=future)

    def test_past_timestamp_yields_expired(self) -> None:
        past = NOW - timedelta(seconds=10)
        assert evaluate_snooze(past.isoformat(), NOW) == Expired()

    def test_naive_future_timestamp_is_treated_as_utc(self) -> None:
        """Legacy timestamps without tzinfo are interpreted as UTC."""
        future_naive = (NOW + timedelta(hours=1)).replace(tzinfo=None)
        result = evaluate_snooze(future_naive.isoformat(), NOW)
        assert isinstance(result, Active)
        assert result.until == NOW + timedelta(hours=1)

    def test_boundary_equals_now_yields_expired(self) -> None:
        """now == snooze_time is considered expired (matches >= semantics)."""
        assert evaluate_snooze(NOW.isoformat(), NOW) == Expired()

    def test_garbage_string_yields_malformed(self) -> None:
        assert evaluate_snooze("not-a-valid-timestamp", NOW) == Malformed()

    def test_empty_string_yields_malformed(self) -> None:
        assert evaluate_snooze("", NOW) == Malformed()

    @pytest.mark.parametrize(
        ("iso_string", "expected_type"),
        [
            (None, Inactive),
            ("indefinite", Indefinite),
            ("garbage", Malformed),
            ("2026-01-01T13:00:00+00:00", Active),  # future relative to NOW
            ("2026-01-01T11:00:00+00:00", Expired),  # past relative to NOW
        ],
    )
    def test_parametrized_dispatch(self, iso_string: str | None, expected_type: type) -> None:
        result = evaluate_snooze(iso_string, NOW)
        assert isinstance(result, expected_type)

"""Pure evaluation of persisted snooze timestamps.

This module exposes :func:`evaluate_snooze`, which interprets the
``snooze_until_iso`` field persisted by :class:`SnoozeManager` and returns a
small sum type describing the current snooze state. The function is pure: it
has no side effects, performs no I/O, and depends only on its arguments.

Keeping the parsing/classification logic separate from side-effect routing
lets us:

* Test the timestamp interpretation rules without mocking ConfigStoreLike,
  AccumulatorLike, or TrayLike protocols.
* Share the exact same rules between :meth:`SnoozeManager.check_expiry` and
  :meth:`SnoozeManager.restore_persisted_state`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

__all__ = [
    "Active",
    "Expired",
    "Indefinite",
    "Inactive",
    "Malformed",
    "SnoozeState",
    "evaluate_snooze",
]


@dataclass(frozen=True)
class Inactive:
    """No snooze is persisted."""


@dataclass(frozen=True)
class Indefinite:
    """An indefinite snooze is persisted (no expiry time)."""


@dataclass(frozen=True)
class Active:
    """A timed snooze is still in the future."""

    until: datetime


@dataclass(frozen=True)
class Expired:
    """A timed snooze whose expiry time has been reached or passed."""


@dataclass(frozen=True)
class Malformed:
    """The persisted value could not be parsed as an ISO timestamp."""


SnoozeState = Inactive | Indefinite | Active | Expired | Malformed


def evaluate_snooze(iso_string: str | None, now: datetime) -> SnoozeState:
    """Classify a persisted ``snooze_until_iso`` value against ``now``.

    Args:
        iso_string: The value loaded from the config store. ``None`` means no
            snooze is set. The sentinel ``"indefinite"`` means an indefinite
            snooze. Any other value is expected to be an ISO-8601 timestamp.
        now: The reference time to compare against. Must be timezone-aware.

    Returns:
        A :data:`SnoozeState` describing the interpretation.

    Notes:
        * Naive timestamps (without ``tzinfo``) are interpreted as UTC, matching
          the legacy behaviour of :class:`SnoozeManager`.
        * The boundary ``now == until`` is classified as :class:`Expired`,
          matching the original ``now >= snooze_time`` comparison.
    """
    if iso_string is None:
        return Inactive()
    if iso_string == "indefinite":
        return Indefinite()

    try:
        snooze_time = datetime.fromisoformat(iso_string)
    except ValueError:
        return Malformed()

    if snooze_time.tzinfo is None:
        snooze_time = snooze_time.replace(tzinfo=timezone.utc)

    if now >= snooze_time:
        return Expired()
    return Active(until=snooze_time)

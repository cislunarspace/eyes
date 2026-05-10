"""EventLog — thread-safe append-only JSONL event logging."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import platformdirs

from .types import AppEventKind


class AppEvent:
    """A single logged event."""

    def __init__(
        self,
        timestamp_iso: str,
        kind: AppEventKind,
        state: str | None = None,
        **extra: Any,
    ) -> None:
        self.timestamp_iso = timestamp_iso
        self.kind = kind
        self.state = state
        self.extra = extra if extra else None

    def __repr__(self) -> str:
        return f"AppEvent({self.timestamp_iso}, {self.kind.value})"


class EventLog:
    """Thread-safe append-only JSONL event logger."""

    def __init__(self, config_dir: Path | None = None) -> None:
        if config_dir is None:
            config_dir = Path(platformdirs.user_config_dir("eyes"))
        self._config_dir = config_dir
        self._events_file = config_dir / "events.jsonl"
        self._lock = threading.Lock()

    def append(self, kind: AppEventKind, **data: Any) -> None:
        """Thread-safe append of an event to the JSONL file."""
        # Extract state for top-level field if present
        state = data.pop("state", None)

        event_data: dict[str, Any] = {
            "ts": self._timestamp_iso(),
            "kind": kind.value,
        }
        if state is not None:
            event_data["state"] = state
        if data:
            event_data.update(data)

        with self._lock:
            self._ensure_dir()
            with open(self._events_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event_data, ensure_ascii=False) + "\n")

    def events(self) -> Iterator[AppEvent]:
        """Generator yielding all historical events."""
        if not self._events_file.exists():
            return

        with self._lock:
            with open(self._events_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        yield AppEvent(
                            timestamp_iso=data["ts"],
                            kind=AppEventKind(data["kind"]),
                            state=data.get("state"),
                            **{k: v for k, v in data.items() if k not in ("ts", "kind", "state")},
                        )
                    except (json.JSONDecodeError, KeyError, ValueError):
                        # Skip malformed lines
                        continue

    def _ensure_dir(self) -> None:
        self._config_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _timestamp_iso() -> str:
        """Return current UTC time as ISO 8601 string with offset."""
        return datetime.now(timezone.utc).isoformat()

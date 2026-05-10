"""Tests for EventLog."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from eyes.types import AppEventKind


class TestEventLog:
    """EventLog append and read tests."""

    def test_append_creates_file(self, tmp_path: Path) -> None:
        """Appending an event creates the events.jsonl file."""
        from eyes.event_log import EventLog

        log = EventLog(config_dir=tmp_path)
        log.append(AppEventKind.CAMERA_UNAVAILABLE)

        events_file = tmp_path / "events.jsonl"
        assert events_file.exists()

    def test_state_change_event_format(self, tmp_path: Path) -> None:
        """STATE_CHANGE events contain timestamp, kind, and state."""
        from eyes.event_log import EventLog

        log = EventLog(config_dir=tmp_path)
        log.append(AppEventKind.STATE_CHANGE, state="FACING SCREEN")

        events_file = tmp_path / "events.jsonl"
        content = events_file.read_text()
        assert "STATE_CHANGE" in content
        assert "FACING SCREEN" in content
        # Should have ISO timestamp
        assert "T" in content

    def test_prompt_fired_event(self, tmp_path: Path) -> None:
        """PROMPT_FIRED events record prompt details."""
        from eyes.event_log import EventLog

        log = EventLog(config_dir=tmp_path)
        log.append(AppEventKind.PROMPT_FIRED, prompt="adjust", direction="LEFT")

        events_file = tmp_path / "events.jsonl"
        content = events_file.read_text()
        assert "PROMPT_FIRED" in content
        assert "adjust" in content
        assert "LEFT" in content

    def test_camera_events(self, tmp_path: Path) -> None:
        """CAMERA_UNAVAILABLE and CAMERA_RESUMED events log correctly."""
        from eyes.event_log import EventLog

        log = EventLog(config_dir=tmp_path)
        log.append(AppEventKind.CAMERA_UNAVAILABLE)
        log.append(AppEventKind.CAMERA_RESUMED)

        events_file = tmp_path / "events.jsonl"
        content = events_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 2
        assert "CAMERA_UNAVAILABLE" in lines[0]
        assert "CAMERA_RESUMED" in lines[1]

    def test_snooze_events(self, tmp_path: Path) -> None:
        """SNOOZE_START and SNOOZE_END events log correctly."""
        from eyes.event_log import EventLog

        log = EventLog(config_dir=tmp_path)
        log.append(AppEventKind.SNOOZE_START, duration_seconds=300)
        log.append(AppEventKind.SNOOZE_END)

        events_file = tmp_path / "events.jsonl"
        content = events_file.read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 2
        assert "SNOOZE_START" in lines[0]
        assert "SNOOZE_END" in lines[1]

    def test_append_only_mode(self, tmp_path: Path) -> None:
        """Multiple appends do not overwrite; events accumulate."""
        from eyes.event_log import EventLog

        log = EventLog(config_dir=tmp_path)
        for i in range(5):
            log.append(AppEventKind.STATE_CHANGE, state=f"STATE_{i}")

        events_file = tmp_path / "events.jsonl"
        content = events_file.read_text()
        lines = [l for l in content.strip().split("\n") if l]
        assert len(lines) == 5
        assert "STATE_0" in lines[0]
        assert "STATE_4" in lines[4]

    def test_events_read_back(self, tmp_path: Path) -> None:
        """events() generator yields all appended events."""
        from eyes.event_log import EventLog

        log = EventLog(config_dir=tmp_path)
        log.append(AppEventKind.CAMERA_UNAVAILABLE)
        log.append(AppEventKind.STATE_CHANGE, state="FACING SCREEN")
        log.append(AppEventKind.CAMERA_RESUMED)

        events = list(log.events())
        assert len(events) == 3
        assert events[0].kind == AppEventKind.CAMERA_UNAVAILABLE
        assert events[1].kind == AppEventKind.STATE_CHANGE
        assert events[2].kind == AppEventKind.CAMERA_RESUMED

    def test_thread_safety(self, tmp_path: Path) -> None:
        """Concurrent appends from multiple threads remain valid JSONL."""
        from eyes.event_log import EventLog

        log = EventLog(config_dir=tmp_path)
        num_threads = 10
        events_per_thread = 20

        def append_events(thread_id: int) -> None:
            for i in range(events_per_thread):
                log.append(AppEventKind.STATE_CHANGE, state=f"T{thread_id}_E{i}")

        threads = [threading.Thread(target=append_events, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All events should be present
        events = list(log.events())
        assert len(events) == num_threads * events_per_thread

        # All lines should be valid JSON
        import json

        events_file = tmp_path / "events.jsonl"
        content = events_file.read_text()
        for i, line in enumerate(content.strip().split("\n")):
            if line:
                try:
                    json.loads(line)
                except json.JSONDecodeError as e:
                    pytest.fail(f"Line {i} is not valid JSON: {e}")

    def test_no_biometric_data_in_events(self, tmp_path: Path) -> None:
        """Events never contain frames, landmarks, or biometric data."""
        from eyes.event_log import EventLog

        log = EventLog(config_dir=tmp_path)
        # Log various events
        log.append(AppEventKind.STATE_CHANGE, state="OFF_AXIS_LEFT")
        log.append(AppEventKind.PROMPT_FIRED, prompt="调整")

        events_file = tmp_path / "events.jsonl"
        content = events_file.read_text().lower()

        # These field names should never appear
        forbidden = ["frame", "landmark", "face", "image", "pixel", "yaw", "roll", "angle"]
        for field in forbidden:
            assert field not in content, f"Biometric field '{field}' should not be in event log"

    def test_jsonl_format(self, tmp_path: Path) -> None:
        """Events are stored as one JSON object per line (JSONL)."""
        import json

        from eyes.event_log import EventLog

        log = EventLog(config_dir=tmp_path)
        log.append(AppEventKind.STATE_CHANGE, state="FACING SCREEN")

        events_file = tmp_path / "events.jsonl"
        content = events_file.read_text()

        lines = [l for l in content.strip().split("\n") if l]
        assert len(lines) == 1

        # Each line should be valid JSON
        obj = json.loads(lines[0])
        assert "ts" in obj
        assert "kind" in obj

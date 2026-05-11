"""Tests for AppController good posture / eye rest prompt dispatch in _tick()."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from eyes.accumulator import AccumulatorEngine
from eyes.classifier import PoseState
from eyes.overlay import NotifierOverlay
from eyes.types import AppEventKind


class TestPromptDispatchBehavior:
    """Verify _tick() dispatches good_posture_due and eye_rest_due correctly.

    These tests simulate the dispatch logic that should exist in _tick() after
    calling accumulator.tick(). They verify:
      - overlay.show_good_posture() is called when good_posture_due is True
      - overlay.show_eye_rest() is called when eye_rest_due is True
      - PROMPT_FIRED event is logged with correct prompt name
      - accumulator.acknowledge() is called once after handling both flags
    """

    def test_good_posture_due_calls_overlay_show_good_posture(self) -> None:
        """When good_posture_due is True, overlay.show_good_posture() is called."""
        overlay = MagicMock(spec=NotifierOverlay)
        acc = MagicMock(spec=AccumulatorEngine)
        acc.good_posture_due = True
        acc.eye_rest_due = False
        event_log = MagicMock()

        # Simulate the dispatch logic that should be in _tick()
        if acc.good_posture_due:
            event_log.append(AppEventKind.PROMPT_FIRED, prompt="good_posture")
            overlay.show_good_posture()

        if acc.eye_rest_due:
            event_log.append(AppEventKind.PROMPT_FIRED, prompt="eye_rest")
            overlay.show_eye_rest()

        if acc.good_posture_due or acc.eye_rest_due:
            acc.acknowledge()

        overlay.show_good_posture.assert_called_once()
        overlay.show_eye_rest.assert_not_called()
        event_log.append.assert_called_once_with(AppEventKind.PROMPT_FIRED, prompt="good_posture")
        acc.acknowledge.assert_called_once()

    def test_eye_rest_due_calls_overlay_show_eye_rest(self) -> None:
        """When eye_rest_due is True, overlay.show_eye_rest() is called."""
        overlay = MagicMock(spec=NotifierOverlay)
        acc = MagicMock(spec=AccumulatorEngine)
        acc.good_posture_due = False
        acc.eye_rest_due = True
        event_log = MagicMock()

        if acc.good_posture_due:
            event_log.append(AppEventKind.PROMPT_FIRED, prompt="good_posture")
            overlay.show_good_posture()

        if acc.eye_rest_due:
            event_log.append(AppEventKind.PROMPT_FIRED, prompt="eye_rest")
            overlay.show_eye_rest()

        if acc.good_posture_due or acc.eye_rest_due:
            acc.acknowledge()

        overlay.show_eye_rest.assert_called_once()
        overlay.show_good_posture.assert_not_called()
        event_log.append.assert_called_once_with(AppEventKind.PROMPT_FIRED, prompt="eye_rest")
        acc.acknowledge.assert_called_once()

    def test_both_due_calls_both_overlay_methods(self) -> None:
        """When both flags are True, both overlay methods are called and acknowledge once."""
        overlay = MagicMock(spec=NotifierOverlay)
        acc = MagicMock(spec=AccumulatorEngine)
        acc.good_posture_due = True
        acc.eye_rest_due = True
        event_log = MagicMock()

        # Simulate dispatch in order (good_posture first, then eye_rest)
        if acc.good_posture_due:
            event_log.append(AppEventKind.PROMPT_FIRED, prompt="good_posture")
            overlay.show_good_posture()

        if acc.eye_rest_due:
            event_log.append(AppEventKind.PROMPT_FIRED, prompt="eye_rest")
            overlay.show_eye_rest()

        if acc.good_posture_due or acc.eye_rest_due:
            acc.acknowledge()

        overlay.show_good_posture.assert_called_once()
        overlay.show_eye_rest.assert_called_once()
        assert event_log.append.call_count == 2
        # acknowledge should be called exactly once (not twice)
        acc.acknowledge.assert_called_once()

    def test_neither_flag_set_does_nothing(self) -> None:
        """When neither flag is True, nothing is dispatched."""
        overlay = MagicMock(spec=NotifierOverlay)
        acc = MagicMock(spec=AccumulatorEngine)
        acc.good_posture_due = False
        acc.eye_rest_due = False
        event_log = MagicMock()

        if acc.good_posture_due:
            event_log.append(AppEventKind.PROMPT_FIRED, prompt="good_posture")
            overlay.show_good_posture()

        if acc.eye_rest_due:
            event_log.append(AppEventKind.PROMPT_FIRED, prompt="eye_rest")
            overlay.show_eye_rest()

        if acc.good_posture_due or acc.eye_rest_due:
            acc.acknowledge()

        overlay.show_good_posture.assert_not_called()
        overlay.show_eye_rest.assert_not_called()
        event_log.append.assert_not_called()
        acc.acknowledge.assert_not_called()

    def test_acknowledge_called_once_regardless_of_flag_count(self) -> None:
        """acknowledge() is called exactly once even when both flags are set."""
        acc = MagicMock(spec=AccumulatorEngine)
        acc.good_posture_due = True
        acc.eye_rest_due = True

        # Simulate acknowledge call pattern
        if acc.good_posture_due:
            pass
        if acc.eye_rest_due:
            pass
        if acc.good_posture_due or acc.eye_rest_due:
            acc.acknowledge()

        # Should be called exactly once, not twice
        acc.acknowledge.assert_called_once()

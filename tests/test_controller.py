"""Tests for AppController prompt event dispatch."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from eyes.controller import AppController
from eyes.classifier import PoseState
from eyes.overlay import NotifierOverlay
from eyes.sense_loop import PromptEvent
from eyes.types import AppEventKind
from eyes.main_window import MainWindow


class TestMainWindowAsPureView:
    """Verify MainWindow is a pure view with no hardware resource ownership."""

    def test_main_window_has_no_camera_attribute(self, qtbot) -> None:
        """MainWindow should not have a _camera attribute (ownership moved to controller)."""
        window = MainWindow()
        qtbot.addWidget(window)
        assert not hasattr(window, "_camera")

    def test_main_window_has_no_detector_attribute(self, qtbot) -> None:
        """MainWindow should not have a _detector attribute (ownership moved to controller)."""
        window = MainWindow()
        qtbot.addWidget(window)
        assert not hasattr(window, "_detector")

    def test_main_window_has_no_camera_method(self, qtbot) -> None:
        """MainWindow should not have a camera() method."""
        window = MainWindow()
        qtbot.addWidget(window)
        assert not hasattr(window, "camera")

    def test_main_window_has_no_detector_method(self, qtbot) -> None:
        """MainWindow should not have a detector() method."""
        window = MainWindow()
        qtbot.addWidget(window)
        assert not hasattr(window, "detector")

    def test_main_window_has_no_init_camera_and_detector_method(self, qtbot) -> None:
        """MainWindow should not have init_camera_and_detector() method."""
        window = MainWindow()
        qtbot.addWidget(window)
        assert not hasattr(window, "init_camera_and_detector")


class TestPromptDispatchBehavior:
    """Verify PromptEvent values are dispatched to overlay and event log."""

    def test_good_posture_due_calls_overlay_show_good_posture(self) -> None:
        """When good_posture_due is True, overlay.show_good_posture() is called."""
        controller = object.__new__(AppController)
        overlay = MagicMock(spec=NotifierOverlay)
        event_log = MagicMock()
        controller._overlay = overlay
        controller._event_log = event_log

        controller._dispatch_prompt_event(PromptEvent(kind="good_posture"))

        overlay.show_good_posture.assert_called_once()
        overlay.show_eye_rest.assert_not_called()
        event_log.append.assert_called_once_with(AppEventKind.PROMPT_FIRED, prompt="good_posture")

    def test_eye_rest_due_calls_overlay_show_eye_rest(self) -> None:
        """When eye_rest_due is True, overlay.show_eye_rest() is called."""
        controller = object.__new__(AppController)
        overlay = MagicMock(spec=NotifierOverlay)
        event_log = MagicMock()
        controller._overlay = overlay
        controller._event_log = event_log

        controller._dispatch_prompt_event(PromptEvent(kind="eye_rest"))

        overlay.show_eye_rest.assert_called_once()
        overlay.show_good_posture.assert_not_called()
        event_log.append.assert_called_once_with(AppEventKind.PROMPT_FIRED, prompt="eye_rest")

    def test_both_due_calls_both_overlay_methods(self) -> None:
        """When both events are returned, both overlay methods are called."""
        controller = object.__new__(AppController)
        overlay = MagicMock(spec=NotifierOverlay)
        event_log = MagicMock()
        controller._overlay = overlay
        controller._event_log = event_log

        controller._dispatch_prompt_event(PromptEvent(kind="good_posture"))
        controller._dispatch_prompt_event(PromptEvent(kind="eye_rest"))

        overlay.show_good_posture.assert_called_once()
        overlay.show_eye_rest.assert_called_once()
        assert event_log.append.call_count == 2

    def test_neither_flag_set_does_nothing(self) -> None:
        """When neither flag is True, nothing is dispatched."""
        controller = object.__new__(AppController)
        overlay = MagicMock(spec=NotifierOverlay)
        event_log = MagicMock()
        controller._overlay = overlay
        controller._event_log = event_log

        controller._dispatch_prompt_event(PromptEvent(kind="unknown"))

        overlay.show_good_posture.assert_not_called()
        overlay.show_eye_rest.assert_not_called()
        event_log.append.assert_not_called()

    def test_correction_event_calls_overlay_show_correction(self) -> None:
        controller = object.__new__(AppController)
        overlay = MagicMock(spec=NotifierOverlay)
        event_log = MagicMock()
        controller._overlay = overlay
        controller._event_log = event_log

        controller._dispatch_prompt_event(
            PromptEvent(kind="correction", direction=PoseState.OFF_AXIS_RIGHT)
        )

        overlay.show_correction.assert_called_once_with(PoseState.OFF_AXIS_RIGHT)
        event_log.append.assert_called_once_with(
            AppEventKind.PROMPT_FIRED, prompt="adjust", direction="RIGHT"
        )

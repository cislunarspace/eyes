"""SenseEventBus — fan-out dispatch of SenseEvent values to sinks.

Pulled out of AppController so the per-event routing lives in one place.
The bus consumes a list of `SenseEvent` values (the union from
posture_tick_engine) and fans each one out to:
  - the event log
  - the notifier overlay
  - the main window (for warning-level transitions)

The bus is intentionally a small, testable module. It does not own
any state beyond the sinks it's wired to.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, assert_never

import numpy as np

from .classifier import PoseState
from .event_log import EventLog
from .main_window import MainWindow
from .overlay import NotifierOverlay
from .posture_tick_engine import (
    CorrectionEvent,
    EyeRestEvent,
    GoodPostureEvent,
    SenseEvent,
)
from .types import AppEventKind, WarningLevel, WarningLevelEvent


@dataclass(frozen=True)
class FrameProcessed:
    """The result of one sense-loop tick, ready for fan-out.

    Attributes:
        frame: The original BGR camera frame, or None if the camera was
            unavailable this tick.
        yaw: Latest classified yaw, or None if no face.
        roll: Latest classified roll, or None if no face.
        state: Latest PoseState.
        events: SenseEvent values emitted by the posture engine this tick.
        vision_resumed: True if the camera/detector pipeline just
            transitioned from unavailable to available on this tick.
        vision_just_failed: True if the camera/detector pipeline just
            transitioned from available to unavailable on this tick.
            Steady-unavailable ticks have this False.
        vision_detector_error: Error string from a failed detector
            build, or None.
    """

    frame: Optional[np.ndarray]
    yaw: Optional[float]
    roll: Optional[float]
    state: PoseState
    events: list[SenseEvent]
    vision_resumed: bool = False
    vision_just_failed: bool = False
    vision_detector_error: Optional[str] = None


class EventLogLike(Protocol):
    """Minimal interface the bus needs from the event log."""

    def append(self, kind: AppEventKind, **data: object) -> object: ...


class OverlayLike(Protocol):
    """Minimal interface the bus needs from the notifier overlay."""

    def show_correction(self, direction: PoseState) -> object: ...
    def show_good_posture(self) -> object: ...
    def show_eye_rest(self) -> object: ...
    def show_corrected(self) -> object: ...
    def hide(self) -> object: ...


class MainWindowLike(Protocol):
    """Minimal interface the bus needs from the main window."""

    def set_warning_level(self, event: WarningLevelEvent) -> object: ...


class SenseEventBus:
    """Routes each SenseEvent to the right sinks.

    One fan-out point; the `match` is encapsulated here so the controller
    (and any test) doesn't have to reproduce the routing table.
    """

    def __init__(
        self,
        event_log: EventLogLike,
        overlay: OverlayLike,
        window: MainWindowLike,
    ) -> None:
        self._event_log = event_log
        self._overlay = overlay
        self._window = window

    def dispatch(self, events: list[SenseEvent]) -> None:
        """Fan each event out to the appropriate sinks."""
        for event in events:
            self._dispatch_one(event)

    def _dispatch_one(self, event: SenseEvent) -> None:
        match event:
            case CorrectionEvent(direction=direction):
                dir_str = "LEFT" if direction == PoseState.OFF_AXIS_LEFT else "RIGHT"
                self._event_log.append(
                    AppEventKind.PROMPT_FIRED, prompt="adjust", direction=dir_str
                )
                self._overlay.show_correction(direction)
            case GoodPostureEvent():
                self._event_log.append(AppEventKind.PROMPT_FIRED, prompt="good_posture")
                self._overlay.show_good_posture()
            case EyeRestEvent():
                self._event_log.append(AppEventKind.PROMPT_FIRED, prompt="eye_rest")
                self._overlay.show_eye_rest()
            case WarningLevelEvent():
                self._event_log.append(
                    AppEventKind.WARNING_LEVEL_CHANGED,
                    level=event.level.value,
                    direction=event.direction,
                )
                self._window.set_warning_level(event)
                if event.level == WarningLevel.CORRECTED:
                    self._overlay.show_corrected()
                elif event.level == WarningLevel.NORMAL:
                    self._overlay.hide()
            case _:
                assert_never(event)

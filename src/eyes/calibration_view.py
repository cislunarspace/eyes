"""CalibrationView — owns the calibration countdown QTimer and forwards samples.

A small QWidget that wraps `CalibrationSession` (Qt-free) with the Qt
timer mechanics the controller used to embed in `SettingsDialog`. The
view exposes a `feed(yaw, roll)` method for the controller to call
when a new pose sample arrives, and a `started` / `completed` signal
pair for the dialog to react to UI changes.

The 100ms tick interval comes from a single source — the constructor
parameter `tick_interval_ms`, defaulting to 100ms. The dialog (or
caller) supplies the value; the view does not hardcode it.

Emitted signals:
  - `calibration_started()` — fired when `start()` is called.
  - `calibration_completed(yaw: float, roll: float)` — fired when the
    countdown reaches zero and a result is available.

The view exposes the underlying `CalibrationSession` via a `session`
property so the dialog can read `countdown_seconds` and `is_active`
without going through QTimer proxies.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QWidget

from .calibration import CalibrationSession


class CalibrationView(QWidget):
    """A QWidget that hosts a `CalibrationSession` and a Qt countdown timer.

    The view does not draw anything itself; the dialog composes it
    into its form layout and reads its state via the `session` property.
    """

    calibration_started = Signal()
    calibration_completed = Signal(float, float)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        duration_seconds: float = 5.0,
        tick_interval_ms: int = 100,
    ) -> None:
        super().__init__(parent)
        self._session = CalibrationSession(duration_seconds=duration_seconds)
        self._tick_interval_ms = tick_interval_ms
        self._timer: QTimer | None = None

    @property
    def session(self) -> CalibrationSession:
        """The underlying Qt-free calibration session."""
        return self._session

    def start(self) -> None:
        """Begin a fresh calibration session and start the countdown timer."""
        self._session.start()
        self.calibration_started.emit()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start(self._tick_interval_ms)

    def feed(self, yaw: float, roll: float) -> None:
        """Forward a pose sample to the active session.

        No-op when the session is inactive (the dialog's
        `add_calibration_sample` returns False in that case; the
        caller decides what to do).
        """
        self._session.feed(yaw, roll)

    @property
    def is_calibrating(self) -> bool:
        return self._session.is_active

    def _on_tick(self) -> None:
        """Advance the session and finish when the countdown reaches zero."""
        dt_seconds = self._tick_interval_ms / 1000.0
        self._session.tick(dt_seconds)
        if not self._session.is_active:
            self._finish()

    def _finish(self) -> None:
        """Stop the timer and emit the completed signal with the result."""
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        result = self._session.result()
        if result is not None:
            self.calibration_completed.emit(result.yaw, result.roll)

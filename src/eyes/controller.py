"""AppController — orchestrates the camera → detect → classify → update-UI loop at 10 Hz."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .accumulator import AccumulatorEngine
from .classifier import PoseState, classify
from .main_window import MainWindow
from .overlay import NotifierOverlay

# Tick interval: 100 ms = 0.1 seconds
_DT_SECONDS = 0.1


class AppController:
    """Drives the 10 Hz tick loop and coordinates all components.

    Single QTimer at 100 ms interval:
      read frame → detect head pose → classify → accumulate → update UI → repeat

    On camera/detector errors the loop keeps running but the UI shows
    the unavailable state. The window close event triggers full cleanup.
    """

    def __init__(self, app: QApplication, camera_index: int = 0) -> None:
        self._app = app
        self._window = MainWindow(camera_index=camera_index)
        self._timer = QTimer()
        self._timer.setInterval(100)  # 10 Hz

        # Accumulator engine for off-axis streak tracking
        self._accumulator = AccumulatorEngine()

        # Overlay for correction prompts
        self._overlay = NotifierOverlay()

        self._app.aboutToQuit.connect(self._on_about_to_quit)

    def _on_about_to_quit(self) -> None:
        self._timer.stop()

    def run(self) -> None:
        """Show the window, open camera + detector, start the tick loop."""
        self._window.show()

        if not self._window.init_camera_and_detector():
            # Camera unavailable — still show the window; tick loop will
            # keep retrying via camera.retry_open()
            pass

        self._timer.timeout.connect(self._tick)
        self._timer.start()

        self._app.exec()

    def _tick(self) -> None:
        """One 10 Hz tick: read, detect, classify, accumulate, update UI."""
        camera = self._window.camera()
        detector = self._window.detector()

        # Try to open camera if not available
        if not camera.is_available:
            camera.retry_open()
            self._window.set_state(None, None, None)
            return

        frame = camera.read()
        self._window.update_frame(frame)

        if frame is None or detector is None:
            self._window.set_state(None, None, None)
            return

        pose = detector.detect(frame)
        if pose is None:
            self._window.set_state(None, None, None)
            current_state = PoseState.NO_FACE
        else:
            yaw, roll = pose
            state = classify(yaw, roll)
            self._window.set_state(yaw, roll, state)
            current_state = state

        # Accumulate off-axis time and trigger overlay if correction due
        correction = self._accumulator.tick(current_state, _DT_SECONDS)
        if correction is not None:
            self._overlay.show_correction(correction)

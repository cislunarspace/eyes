"""AppController — orchestrates the camera → detect → classify → update-UI loop at 10 Hz."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .classifier import classify
from .main_window import MainWindow


class AppController:
    """Drives the 10 Hz tick loop and coordinates all components.

    Single QTimer at 100 ms interval:
      read frame → detect head pose → classify → update window → repeat

    On camera/detector errors the loop keeps running but the UI shows
    the unavailable state. The window close event triggers full cleanup.
    """

    def __init__(self, app: QApplication, camera_index: int = 0) -> None:
        self._app = app
        self._window = MainWindow(camera_index=camera_index)
        self._timer = QTimer()
        self._timer.setInterval(100)  # 10 Hz

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
        """One 10 Hz tick: read, detect, classify, update UI."""
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
        else:
            yaw, roll = pose
            state = classify(yaw, roll)
            self._window.set_state(yaw, roll, state)

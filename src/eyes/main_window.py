"""MainWindow — QMainWindow that holds the DisplayState and composes a renderer.

The window owns:
  - the central widget (a plain QWidget)
  - the DisplayState reducer state
  - the public API: `set_state`, `set_warning_level`, `update_frame`,
    `show_camera_unavailable_message`, `clear_camera_unavailable_message`,
    `refresh_language`, `closeEvent`
  - the close_requested signal (controller decides what to do)

The actual widget tree (badge, banner, video, readout) and the
DisplayPlan → QWidget rendering live in `MainWindowRenderer`. The
window holds DisplayState and calls reducers + `apply_plan` to render.

Re-exported attributes (preserved from the previous implementation so
existing tests that read `window._warning_banner` / `window._badge_label`
continue to work):

  - `window._warning_banner` → the renderer's banner QLabel
  - `window._badge_label`    → the renderer's badge QLabel
  - `window._video_label`    → the renderer's video QLabel
  - `window._readout_label`  → the renderer's readout QLabel
  - `window._camera_status_label` → the renderer's camera-status QLabel
  - `window._auto_dismiss_timer`   → the renderer's auto-dismiss timer
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, QTimer, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QLabel, QMainWindow, QWidget

from .classifier import PoseState
from .display_plan import (
    DisplayState,
    display_plan,
    initial_state,
    reduce_auto_dismiss,
    reduce_pose,
    reduce_warning,
)
from .i18n import t
from .main_window_renderer import MainWindowRenderer
from .types import WarningLevel, WarningLevelEvent


class MainWindow(QMainWindow):
    """QMainWindow shell — owns DisplayState, delegates rendering to a renderer."""

    close_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Eyes")
        self.resize(QSize(800, 600))

        self._central = QWidget()
        self.setCentralWidget(self._central)
        self._renderer = MainWindowRenderer(self._central)
        self._renderer.set_auto_dismiss_callback(self._on_auto_dismiss)

        self._state: DisplayState = initial_state()
        self._renderer.apply_plan(display_plan(self._state))

    # --- Re-exports for tests and the controller ---

    @property
    def _warning_banner(self) -> QLabel:
        return self._renderer._warning_banner

    @property
    def _badge_label(self) -> QLabel:
        return self._renderer._badge_label

    @property
    def _video_label(self) -> QLabel:
        return self._renderer._video_label

    @property
    def _readout_label(self) -> QLabel:
        return self._renderer._readout_label

    @property
    def _camera_status_label(self) -> QLabel:
        return self._renderer._camera_status_label

    @property
    def _auto_dismiss_timer(self) -> QTimer:
        return self._renderer._auto_dismiss_timer

    # --- Public surface (preserved) ---

    def set_state(
        self,
        yaw: Optional[float],
        roll: Optional[float],
        state: Optional[PoseState],
    ) -> None:
        """Update the pose readout and the badge via the reducer."""
        if yaw is None or roll is None:
            self._renderer.set_readout_text(t("main_window.readout_placeholder"))
            self._state = reduce_pose(self._state, PoseState.NO_FACE)
        else:
            self._renderer.set_readout_text(
                f"yaw: {yaw:+.1f}°   roll: {roll:+.1f}°"
            )
            if state is not None:
                self._state = reduce_pose(self._state, state)
        self._renderer.apply_plan(display_plan(self._state))

    def update_frame(self, frame: Optional[object]) -> None:
        """Forward a BGR frame to the renderer for preview."""
        self._renderer.update_frame(frame)

    def refresh_language(self) -> None:
        """Re-read i18n strings and re-render the placeholder.

        The renderer reads `t()` lazily for the badge text (via
        DisplayPlan), so most of the language refresh happens
        automatically on the next `apply_plan`. This method handles
        the placeholders that are set once at startup
        (camera-unavailable message) and the readout text.
        """
        self._renderer.refresh_placeholder_text()
        if (
            self._state.warning_level == WarningLevel.NORMAL
            and self._state.pose_state == PoseState.NO_FACE
        ):
            self._renderer.set_readout_text(t("main_window.readout_placeholder"))
        self._renderer.apply_plan(display_plan(self._state))

    def set_warning_level(self, event: WarningLevelEvent) -> None:
        """Reduce a warning-level event into the state and re-render."""
        self._state = reduce_warning(self._state, event)
        self._renderer.apply_plan(display_plan(self._state))

    def show_camera_unavailable_message(self) -> None:
        self._renderer.set_camera_status_visible(True)

    def clear_camera_unavailable_message(self) -> None:
        self._renderer.set_camera_status_visible(False)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Forward Qt close to the controller via the close_requested signal."""
        self.close_requested.emit()
        event.ignore()

    def _on_auto_dismiss(self) -> None:
        """Renderer told us the auto-dismiss timer fired.

        Reduce the DisplayState back to NORMAL and re-render.
        """
        self._state = reduce_auto_dismiss(self._state)
        self._renderer.apply_plan(display_plan(self._state))

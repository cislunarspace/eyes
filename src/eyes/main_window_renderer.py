"""MainWindowRenderer — owns the QWidget tree and consumes DisplayPlan values.

The renderer is the "pure view" half of the main window. It does not
own reducer state, does not know about `PoseState` or `WarningLevel`:
all that branching lives in `display_plan.py` reducers and the
`DisplayPlan` value object. The renderer's interface is a function of
`DisplayPlan` (and a few primitive operations like showing a frame).

This module is what `main_window.py` used to be, minus the reducer
state and the policy. The original `MainWindow` becomes a thin
QMainWindow shell that holds the DisplayState and forwards to this
renderer.

The private frame pipeline (mirror + BGR→RGB + QImage) lives here
instead of being a module-level helper in `main_window.py`. The
renderer does NOT import `cv2` at the top level — `cv2` is imported
lazily inside `_build_preview_pixmap` so a test that never calls
`update_frame` doesn't need OpenCV.
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .display_plan import DisplayPlan
from .i18n import t


def _mirror_preview_frame(frame: np.ndarray) -> np.ndarray:
    """Mirror a BGR frame horizontally for selfie-style preview.

    Private to this module — exposed only because the existing test
    suite checks its behavior directly. New code should not depend
    on this helper.
    """
    # cv2 is imported lazily so importing this module does not
    # require OpenCV to be available (matters for headless test runs
    # that never invoke the preview pipeline).
    import cv2  # noqa: PLC0415 — lazy import

    return cv2.flip(frame, 1)


class MainWindowRenderer:
    """Owns the QWidget tree and renders `DisplayPlan` values into it.

    The renderer is a plain class (not a QWidget) — the QMainWindow
    shell composes it with the central widget. This keeps the
    renderer unit-testable without instantiating a full QMainWindow.
    """

    def __init__(self, central: QWidget) -> None:
        self._auto_dismiss_callback: Optional[Callable[[], None]] = None
        self._build_widgets(central)
        self._auto_dismiss_timer = QTimer(central)
        self._auto_dismiss_timer.setSingleShot(True)
        self._auto_dismiss_timer.timeout.connect(self._on_auto_dismiss)

    # --- Widget tree construction ---

    def _build_widgets(self, central: QWidget) -> None:
        central.setMinimumSize(QSize(640, 480))
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self._camera_status_label = QLabel(
            t("main_window.camera_unavailable"),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self._camera_status_label.setStyleSheet(
            "background-color: #2a2a1a; color: #ffcc00; "
            "font-size: 16px; padding: 10px;"
        )
        self._camera_status_label.setVisible(False)
        layout.addWidget(self._camera_status_label)

        self._badge_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._badge_label)

        self._video_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._video_label.setMinimumSize(QSize(640, 480))
        self._video_label.setStyleSheet(
            "background-color: #1a1a1a; color: #00ff88; font-size: 18px;"
        )
        layout.addWidget(self._video_label, stretch=1)

        self._warning_banner = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._warning_banner.setVisible(False)
        layout.addWidget(self._warning_banner)

        self._readout_label = QLabel(
            t("main_window.readout_placeholder"),
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        self._readout_label.setStyleSheet(
            "color: #cccccc; font-size: 14px; "
            "background-color: #1a1a1a; padding: 4px;"
        )
        layout.addWidget(self._readout_label)

    # --- Public surface ---

    def set_auto_dismiss_callback(self, callback: Callable[[], None]) -> None:
        """Register a callable to invoke when the auto-dismiss timer fires.

        The callback takes no arguments. It is the parent shell's
        opportunity to reduce the DisplayState back to NORMAL after
        the CORRECTED banner auto-dismisses.
        """
        self._auto_dismiss_callback = callback

    def apply_plan(self, plan: DisplayPlan) -> None:
        """Render a `DisplayPlan` into the widget tree.

        Updates the badge text and stylesheet, the banner
        (visibility, text, stylesheet), and starts/stops the
        auto-dismiss timer.
        """
        self._badge_label.setText(t(plan.badge.text_key))
        self._badge_label.setStyleSheet(
            f"background-color: {plan.badge.bg}; color: {plan.badge.fg}; "
            f"font-size: 16px; font-weight: bold; padding: 6px;"
        )

        if plan.banner.visible:
            self._warning_banner.setText(
                "\n".join(t(key) for key in plan.banner.text_keys)
            )
            self._warning_banner.setStyleSheet(
                f"background-color: {plan.banner.bg}; color: {plan.banner.fg}; "
                f"font-size: 20px; font-weight: bold; padding: 12px;"
            )
            self._warning_banner.setVisible(True)
        else:
            self._warning_banner.setVisible(False)
            self._warning_banner.setText("")
            self._warning_banner.setStyleSheet("")

        if plan.banner.auto_dismiss_ms is not None:
            if not self._auto_dismiss_timer.isActive():
                self._auto_dismiss_timer.start(plan.banner.auto_dismiss_ms)
        else:
            self._auto_dismiss_timer.stop()

    def update_frame(self, frame: Optional[np.ndarray]) -> None:
        """Render a BGR camera frame into the video label."""
        if frame is None:
            return
        pixmap = self._build_preview_pixmap(frame)
        if pixmap is not None:
            self._video_label.setPixmap(pixmap)

    def set_readout_text(self, text: str) -> None:
        """Update the bottom readout (e.g. 'yaw: +1.5°   roll: -0.3°')."""
        self._readout_label.setText(text)

    def set_camera_status_visible(self, visible: bool) -> None:
        """Show or hide the camera-unavailable banner."""
        self._camera_status_label.setVisible(visible)

    def refresh_placeholder_text(self) -> None:
        """Re-read the placeholder i18n strings and re-apply them.

        Used when the language changes mid-session.
        """
        self._camera_status_label.setText(t("main_window.camera_unavailable"))

    # --- Internal helpers ---

    def _build_preview_pixmap(self, frame: np.ndarray) -> Optional[QPixmap]:
        import cv2  # noqa: PLC0415 — lazy import

        preview_frame = _mirror_preview_frame(frame)
        rgb = cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        scaled = img.scaled(
            self._video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        return QPixmap.fromImage(scaled)

    def _on_auto_dismiss(self) -> None:
        """Notify the parent that the auto-dismiss timer fired.

        The renderer does not own reducer state; the parent (MainWindow)
        registers a callback to reduce the DisplayState back to NORMAL
        after the CORRECTED banner auto-dismisses.
        """
        if self._auto_dismiss_callback is not None:
            self._auto_dismiss_callback()

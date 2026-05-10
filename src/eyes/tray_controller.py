"""TrayController — system tray icon with snooze menu."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

# Icon paths relative to the package
_ICON_DIR = Path(__file__).parent / "icons"
_ICON_ACTIVE_PATH = _ICON_DIR / "tray_active.png"
_ICON_PAUSED_PATH = _ICON_DIR / "tray_paused.png"
_ICON_UNAVAILABLE_PATH = _ICON_DIR / "tray_unavailable.png"


class TrayIconState(Enum):
    """Tray icon variants."""

    ACTIVE = "active"
    PAUSED = "paused"
    UNAVAILABLE = "unavailable"


class TrayController(QSystemTrayIcon):
    """System tray icon with snooze menu.

    Signals:
        pause_requested(duration_seconds: int | None)
            Emitted when user selects a snooze duration.
            None means indefinite snooze.
        resume_requested()
            Emitted when user clicks Resume.
        settings_requested()
            Emitted when user clicks Open Settings.
        quit_requested()
            Emitted when user clicks Quit.
    """

    pause_requested = Signal(object)  # int | None
    resume_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._state = TrayIconState.ACTIVE
        self._create_menu()
        self.setContextMenu(self._menu)
        self._set_icon()

    def _create_menu(self) -> None:
        """Build the tray context menu."""
        self._menu = QMenu()

        # Pause submenu items
        pause_30_action = QAction("Pause 30 minutes", self._menu)
        pause_30_action.triggered.connect(lambda: self.pause_requested.emit(1800))
        self._menu.addAction(pause_30_action)

        pause_1h_action = QAction("Pause 1 hour", self._menu)
        pause_1h_action.triggered.connect(lambda: self.pause_requested.emit(3600))
        self._menu.addAction(pause_1h_action)

        pause_indefinite_action = QAction("Pause until I resume", self._menu)
        pause_indefinite_action.triggered.connect(lambda: self.pause_requested.emit(None))
        self._menu.addAction(pause_indefinite_action)

        self._menu.addSeparator()

        # Resume action (disabled by default)
        self._resume_action = QAction("Resume", self._menu)
        self._resume_action.setEnabled(False)
        self._resume_action.triggered.connect(self.resume_requested.emit)
        self._menu.addAction(self._resume_action)

        self._menu.addSeparator()

        # Settings placeholder
        settings_action = QAction("Open Settings", self._menu)
        settings_action.triggered.connect(self.settings_requested.emit)
        self._menu.addAction(settings_action)

        self._menu.addSeparator()

        # Quit action
        quit_action = QAction("Quit", self._menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(quit_action)

    def _set_icon(self) -> None:
        """Set the tray icon based on current state."""
        icon_paths = {
            TrayIconState.ACTIVE: _ICON_ACTIVE_PATH,
            TrayIconState.PAUSED: _ICON_PAUSED_PATH,
            TrayIconState.UNAVAILABLE: _ICON_UNAVAILABLE_PATH,
        }
        icon_path = icon_paths.get(self._state, _ICON_ACTIVE_PATH)
        # Fall back to system icon if custom icon doesn't exist
        if icon_path.exists():
            self.setIcon(QIcon(str(icon_path)))
        else:
            self.setIcon(self._create_fallback_icon())

    def _create_fallback_icon(self) -> QIcon:
        """Create a simple colored icon as fallback."""
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QBrush, QColor, QPainter, QPixmap

        # Use different colors based on state
        colors = {
            TrayIconState.ACTIVE: "#00cc44",
            TrayIconState.PAUSED: "#ffaa00",
            TrayIconState.UNAVAILABLE: "#888888",
        }
        color = colors.get(self._state, colors[TrayIconState.ACTIVE])

        # Create a simple 16x16 pixmap
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor("transparent"))

        # Draw a filled circle
        painter = QPainter(pixmap)
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QRect(2, 2, 12, 12))
        painter.end()

        return QIcon(pixmap)

    @property
    def state(self) -> TrayIconState:
        """Current tray icon state."""
        return self._state

    def set_state(self, state: TrayIconState) -> None:
        """Change tray icon state and update menu accordingly."""
        self._state = state
        self._set_icon()

        # Update resume action enabled state
        self._resume_action.setEnabled(state == TrayIconState.PAUSED)

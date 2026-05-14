"""TrayController — system tray icon with snooze menu."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .i18n import t
from .icon_factory import create_eye_icon
from .types import TrayIconState


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
        show_window_requested()
            Emitted on tray left-click or "显示窗口" menu item.
        quit_requested()
            Emitted when user clicks Quit.
    """

    pause_requested = Signal(object)  # int | None
    resume_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()
    show_window_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._state = TrayIconState.ACTIVE
        self._create_menu()
        self.setContextMenu(self._menu)
        self._set_icon()
        self.setToolTip(self._get_tooltip_text(self._state))
        self.activated.connect(self._on_activated)
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._set_icon)

    def _create_menu(self) -> None:
        """Build the tray context menu."""
        self._menu = QMenu()

        show_window_action = QAction(t("tray.show_window"), self._menu)
        show_window_action.triggered.connect(self.show_window_requested.emit)
        self._menu.addAction(show_window_action)

        self._menu.addSeparator()

        # Pause submenu items
        pause_30_action = QAction(t("tray.pause_30"), self._menu)
        pause_30_action.triggered.connect(lambda: self.pause_requested.emit(1800))
        self._menu.addAction(pause_30_action)

        pause_1h_action = QAction(t("tray.pause_1h"), self._menu)
        pause_1h_action.triggered.connect(lambda: self.pause_requested.emit(3600))
        self._menu.addAction(pause_1h_action)

        pause_indefinite_action = QAction(t("tray.pause_indefinite"), self._menu)
        pause_indefinite_action.triggered.connect(lambda: self.pause_requested.emit(None))
        self._menu.addAction(pause_indefinite_action)

        self._menu.addSeparator()

        # Resume action (disabled by default)
        self._resume_action = QAction(t("tray.resume"), self._menu)
        self._resume_action.setEnabled(self._state == TrayIconState.PAUSED)
        self._resume_action.triggered.connect(self.resume_requested.emit)
        self._menu.addAction(self._resume_action)

        self._menu.addSeparator()

        # Settings
        settings_action = QAction(t("tray.open_settings"), self._menu)
        settings_action.triggered.connect(self.settings_requested.emit)
        self._menu.addAction(settings_action)

        self._menu.addSeparator()

        # Quit action
        quit_action = QAction(t("tray.quit"), self._menu)
        quit_action.triggered.connect(self.quit_requested.emit)
        self._menu.addAction(quit_action)

    def _set_icon(self, scheme: Qt.ColorScheme = Qt.ColorScheme.Unknown) -> None:
        """Set the tray icon based on current state and system color scheme."""
        if scheme == Qt.ColorScheme.Unknown:
            scheme = QGuiApplication.styleHints().colorScheme()
        dark_mode = scheme == Qt.ColorScheme.Dark
        self.setIcon(create_eye_icon(self._state, dark_mode=dark_mode))

    @staticmethod
    def _get_tooltip_text(state: TrayIconState) -> str:
        mapping = {
            TrayIconState.ACTIVE: t("tray.tooltip_active"),
            TrayIconState.PAUSED: t("tray.tooltip_paused"),
            TrayIconState.UNAVAILABLE: t("tray.tooltip_unavailable"),
        }
        return mapping[state]

    @property
    def state(self) -> TrayIconState:
        """Current tray icon state."""
        return self._state

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window_requested.emit()

    def set_state(self, state: TrayIconState) -> None:
        """Change tray icon state and update menu accordingly."""
        self._state = state
        self._set_icon()
        self.setToolTip(self._get_tooltip_text(state))

        # Update resume action enabled state
        self._resume_action.setEnabled(state == TrayIconState.PAUSED)

    def refresh_language(self) -> None:
        """Rebuild menu and update tooltip with current language."""
        was_paused = self._resume_action.isEnabled()
        self._create_menu()
        self.setContextMenu(self._menu)
        self._resume_action.setEnabled(was_paused)
        self.setToolTip(self._get_tooltip_text(self._state))

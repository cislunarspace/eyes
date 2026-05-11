r"""Autostart manager — wires autostart_enabled config to OS-level autostart.

Windows: writes/removes a value under HKCU\Software\Microsoft\Windows\CurrentVersion\Run.
Linux:   writes/removes ~/.config/autostart/eyes.desktop (XDG autostart).
"""

from __future__ import annotations

import logging
import sys
from abc import ABC, abstractmethod
from pathlib import Path

import platformdirs

logger = logging.getLogger(__name__)


class AutostartError(Exception):
    """Raised when autostart operation fails."""


class AutostartBackend(ABC):
    """Abstract autostart backend."""

    @abstractmethod
    def enable(self, exec_path: str | None = None) -> None:
        """Enable autostart with the given executable path."""

    @abstractmethod
    def disable(self) -> None:
        """Disable autostart."""

    @abstractmethod
    def is_enabled(self) -> bool:
        """Return True if autostart is currently enabled."""


class WindowsAutostartBackend(AutostartBackend):
    """Windows autostart via HKCU registry."""

    REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    VALUE_NAME = "Eyes"

    def __init__(self) -> None:
        self._winreg: type | None = None
        try:
            import winreg
            self._winreg = winreg
        except ImportError:
            pass

    def _get_exec_path(self) -> str | None:
        """Return executable path for autostart, or None if unavailable."""
        if getattr(sys, "frozen", False):
            return sys.executable
        # On Windows, source-install autostart is not practical; return None
        return None

    def enable(self, exec_path: str | None = None) -> None:
        if self._winreg is None:
            return
        if exec_path is None:
            exec_path = self._get_exec_path()
        if exec_path is None:
            logger.warning("Cannot enable autostart: no executable path available")
            return
        try:
            key = self._winreg.OpenKey(
                self._winreg.HKEY_CURRENT_USER,
                self.REG_KEY,
                0,
                self._winreg.KEY_SET_VALUE,
            )
            try:
                self._winreg.SetValueEx(key, self.VALUE_NAME, 0, self._winreg.REG_SZ, exec_path)
            finally:
                self._winreg.CloseKey(key)
        except OSError as e:
            logger.error("Failed to enable Windows autostart: %s", e)
            raise AutostartError(f"Failed to enable autostart: {e}") from e

    def disable(self) -> None:
        if self._winreg is None:
            return
        try:
            key = self._winreg.OpenKey(
                self._winreg.HKEY_CURRENT_USER,
                self.REG_KEY,
                0,
                self._winreg.KEY_SET_VALUE,
            )
            try:
                self._winreg.DeleteValue(key, self.VALUE_NAME)
            except FileNotFoundError:
                pass
            finally:
                self._winreg.CloseKey(key)
        except OSError as e:
            logger.error("Failed to disable Windows autostart: %s", e)
            raise AutostartError(f"Failed to disable autostart: {e}") from e

    def is_enabled(self) -> bool:
        if self._winreg is None:
            return False
        try:
            key = self._winreg.OpenKey(
                self._winreg.HKEY_CURRENT_USER,
                self.REG_KEY,
                0,
                self._winreg.KEY_READ,
            )
            try:
                self._winreg.QueryValueEx(key, self.VALUE_NAME)
                return True
            except FileNotFoundError:
                return False
            finally:
                self._winreg.CloseKey(key)
        except OSError:
            return False


class LinuxAutostartBackend(AutostartBackend):
    """Linux autostart via XDG desktop entry."""

    DESKTOP_FILE = "eyes.desktop"

    def __init__(self) -> None:
        self._autostart_dir = Path(platformdirs.user_config_dir("eyes")).parent / "autostart"
        self._desktop_file = self._autostart_dir / self.DESKTOP_FILE

    def _get_exec_path(self) -> str:
        """Return the executable path for autostart."""
        if getattr(sys, "frozen", False):
            return sys.executable
        return f"{sys.executable} -m eyes"

    def enable(self, exec_path: str | None = None) -> None:
        if exec_path is None:
            exec_path = self._get_exec_path()
        try:
            self._autostart_dir.mkdir(parents=True, exist_ok=True)
            content = self._build_desktop_entry(exec_path)
            self._desktop_file.write_text(content, encoding="utf-8")
        except OSError as e:
            logger.error("Failed to enable Linux autostart: %s", e)
            raise AutostartError(f"Failed to enable autostart: {e}") from e

    def disable(self) -> None:
        if self._desktop_file.exists():
            try:
                self._desktop_file.unlink()
            except OSError as e:
                logger.error("Failed to disable Linux autostart: %s", e)
                raise AutostartError(f"Failed to disable autostart: {e}") from e

    def is_enabled(self) -> bool:
        if not self._desktop_file.exists():
            return False
        try:
            content = self._desktop_file.read_text(encoding="utf-8")
            return "Exec=" in content
        except OSError:
            return False

    def _build_desktop_entry(self, exec_path: str) -> str:
        return (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Exec={exec_path}\n"
            "Hidden=false\n"
            "X-GNOME-Autostart-enabled=true\n"
            "X-GNOME-Autostart-Delay=0\n"
            "Name=Eyes\n"
            "Comment=Eye rest reminder\n"
        )


class AutostartManager:
    """Unified autostart manager that selects the correct backend."""

    def __init__(self) -> None:
        self._backend: AutostartBackend
        if sys.platform == "win32":
            self._backend = WindowsAutostartBackend()
        else:
            self._backend = LinuxAutostartBackend()

    def enable(self) -> None:
        try:
            self._backend.enable()
        except AutostartError as e:
            logger.error("Autostart enable failed: %s", e)

    def disable(self) -> None:
        try:
            self._backend.disable()
        except AutostartError as e:
            logger.error("Autostart disable failed: %s", e)

    def is_enabled(self) -> bool:
        return self._backend.is_enabled()

    def apply_config(self, enabled: bool) -> None:
        """Apply autostart configuration state."""
        if enabled:
            self.enable()
        else:
            self.disable()

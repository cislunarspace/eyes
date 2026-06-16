"""PlatformShell — protocol for opening a directory in the OS file manager.

Pulled out of `SettingsDialog._open_data_directory` so the platform
branch lives in one place and the dialog does not import `subprocess`
or `sys`. Three concrete adapters ship in this module:

  - `WindowsShell` — uses `explorer` on `sys.platform == "win32"`.
  - `MacShell`    — uses `open` on `sys.platform == "darwin"`.
  - `LinuxShell`  — uses `xdg-open` on Linux.

`select_shell(platform_name)` returns the adapter matching the given
platform string (the caller passes `sys.platform` from its own
boundary — the shells themselves do not import `sys`).

Each adapter returns the command list it would invoke, so tests can
inspect it without spawning a subprocess. The `open_directory(path)`
helper actually calls `subprocess.Popen` on the command list and
catches errors via the `logger` module rather than the silent
`except: pass` of the previous implementation.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from typing import Protocol

logger = logging.getLogger(__name__)


class PlatformShell(Protocol):
    """Protocol for opening a directory in the OS file manager.

    A shell is selected once at app construction. The dialog keeps
    a reference to one shell and calls `open(path)` on it.
    """

    def command_for(self, path: str) -> list[str]:
        """Return the subprocess command list that opens `path`."""
        ...

    def open(self, path: str) -> None:
        """Spawn the file manager at `path`. Errors are logged, not swallowed."""
        ...


class WindowsShell:
    """Opens a directory in Windows Explorer."""

    def command_for(self, path: str) -> list[str]:
        return ["explorer", path]

    def open(self, path: str) -> None:
        try:
            subprocess.Popen(self.command_for(path))
        except OSError as exc:
            logger.error("Failed to open data directory in Explorer: %s", exc)


class MacShell:
    """Opens a directory in macOS Finder."""

    def command_for(self, path: str) -> list[str]:
        return ["open", path]

    def open(self, path: str) -> None:
        try:
            subprocess.Popen(self.command_for(path))
        except OSError as exc:
            logger.error("Failed to open data directory in Finder: %s", exc)


class LinuxShell:
    """Opens a directory in the Linux default file manager via xdg-open."""

    def command_for(self, path: str) -> list[str]:
        return ["xdg-open", path]

    def open(self, path: str) -> None:
        try:
            subprocess.Popen(self.command_for(path))
        except OSError as exc:
            logger.error("Failed to open data directory via xdg-open: %s", exc)


def select_shell(platform_name: str = sys.platform) -> PlatformShell:
    """Return the platform-appropriate shell adapter.

    The caller passes `sys.platform` (or a custom string for tests).
    Defaults to the current process's platform.

    Falls back to `LinuxShell` for any platform other than win32/darwin
    so the app still works on less common Unix variants.
    """
    if platform_name == "win32":
        return WindowsShell()
    if platform_name == "darwin":
        return MacShell()
    return LinuxShell()

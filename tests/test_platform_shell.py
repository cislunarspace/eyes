"""Tests for PlatformShell — the file-manager-opening adapter.

These tests verify that:
  - `select_shell` returns the right concrete adapter per platform.
  - Each adapter produces the correct command list for a given path.
  - `open()` calls `subprocess.Popen` (tested with a mock).
  - Errors are logged, not silently swallowed.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from eyes.platform_shell import LinuxShell, MacShell, WindowsShell, select_shell


class TestSelectShell:
    def test_win32_returns_windows_shell(self) -> None:
        assert isinstance(select_shell("win32"), WindowsShell)

    def test_darwin_returns_mac_shell(self) -> None:
        assert isinstance(select_shell("darwin"), MacShell)

    def test_linux_returns_linux_shell(self) -> None:
        assert isinstance(select_shell("linux"), LinuxShell)

    def test_unknown_platform_returns_linux_shell(self) -> None:
        # Any platform other than win32/darwin falls back to LinuxShell.
        assert isinstance(select_shell("haiku"), LinuxShell)


class TestWindowsShell:
    def test_command_for(self) -> None:
        shell = WindowsShell()
        assert shell.command_for("/some/path") == ["explorer", "/some/path"]

    def test_open_calls_popen(self) -> None:
        shell = WindowsShell()
        with patch("eyes.platform_shell.subprocess") as mock_sub:
            shell.open("/some/path")
            mock_sub.Popen.assert_called_once_with(["explorer", "/some/path"])

    def test_open_logs_on_os_error(self, caplog) -> None:
        shell = WindowsShell()
        with patch("eyes.platform_shell.subprocess", MagicMock()) as mock_sub:
            mock_sub.Popen.side_effect = OSError("no explorer")
            with caplog.at_level(logging.ERROR, logger="eyes.platform_shell"):
                shell.open("/broken/path")
            assert "Failed to open data directory in Explorer" in caplog.text
            assert "no explorer" in caplog.text


class TestMacShell:
    def test_command_for(self) -> None:
        shell = MacShell()
        assert shell.command_for("/some/path") == ["open", "/some/path"]

    def test_open_calls_popen(self) -> None:
        shell = MacShell()
        with patch("eyes.platform_shell.subprocess") as mock_sub:
            shell.open("/some/path")
            mock_sub.Popen.assert_called_once_with(["open", "/some/path"])

    def test_open_logs_on_os_error(self, caplog) -> None:
        shell = MacShell()
        with patch("eyes.platform_shell.subprocess", MagicMock()) as mock_sub:
            mock_sub.Popen.side_effect = OSError("no open")
            with caplog.at_level(logging.ERROR, logger="eyes.platform_shell"):
                shell.open("/broken/path")
            assert "Failed to open data directory in Finder" in caplog.text


class TestLinuxShell:
    def test_command_for(self) -> None:
        shell = LinuxShell()
        assert shell.command_for("/some/path") == ["xdg-open", "/some/path"]

    def test_open_calls_popen(self) -> None:
        shell = LinuxShell()
        with patch("eyes.platform_shell.subprocess") as mock_sub:
            shell.open("/some/path")
            mock_sub.Popen.assert_called_once_with(["xdg-open", "/some/path"])

    def test_open_logs_on_os_error(self, caplog) -> None:
        shell = LinuxShell()
        with patch("eyes.platform_shell.subprocess", MagicMock()) as mock_sub:
            mock_sub.Popen.side_effect = OSError("no xdg-open")
            with caplog.at_level(logging.ERROR, logger="eyes.platform_shell"):
                shell.open("/broken/path")
            assert "Failed to open data directory via xdg-open" in caplog.text


class TestSettingsDialogNoSubprocessOrSys:
    """settings_dialog.py must not import subprocess, sys, or cv2."""

    def test_no_subprocess_import(self) -> None:
        from eyes import settings_dialog as module
        source = open(module.__file__, encoding="utf-8").read()
        assert "import subprocess" not in source
        assert "from subprocess" not in source

    def test_no_sys_import(self) -> None:
        from eyes import settings_dialog as module
        source = open(module.__file__, encoding="utf-8").read()
        assert "import sys" not in source
        assert "from sys" not in source

    def test_no_cv2_import(self) -> None:
        from eyes import settings_dialog as module
        source = open(module.__file__, encoding="utf-8").read()
        assert "import cv2" not in source
        assert "from cv2" not in source


class TestNewModulesExist:
    """Acceptance criterion 2: the three adapter modules exist."""

    def test_calibration_view_imports(self) -> None:
        from eyes.calibration_view import CalibrationView
        assert CalibrationView is not None

    def test_camera_selector_imports(self) -> None:
        from eyes.camera_selector import CameraSelector, OpenCVCameraProbe
        assert CameraSelector is not None
        assert OpenCVCameraProbe is not None

    def test_platform_shell_imports(self) -> None:
        from eyes.platform_shell import PlatformShell, select_shell
        assert select_shell is not None

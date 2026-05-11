"""Tests for autostart module."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestLinuxAutostartBackend:
    """Tests for Linux XDG desktop entry autostart."""

    def test_enable_creates_desktop_file(self, tmp_path: Path) -> None:
        """Enabling autostart creates ~/.config/autostart/eyes.desktop."""
        from eyes.autostart import LinuxAutostartBackend

        backend = LinuxAutostartBackend.__new__(LinuxAutostartBackend)
        backend._autostart_dir = tmp_path / ".config" / "autostart"
        backend._desktop_file = backend._autostart_dir / "eyes.desktop"

        backend.enable("/usr/bin/eyes")

        desktop_file = tmp_path / ".config" / "autostart" / "eyes.desktop"
        assert desktop_file.exists()

    def test_enable_writes_valid_desktop_entry(self, tmp_path: Path) -> None:
        """Desktop entry contains required XDG fields."""
        from eyes.autostart import LinuxAutostartBackend

        backend = LinuxAutostartBackend.__new__(LinuxAutostartBackend)
        backend._autostart_dir = tmp_path / ".config" / "autostart"
        backend._desktop_file = backend._autostart_dir / "eyes.desktop"

        backend.enable("/usr/bin/eyes")

        content = backend._desktop_file.read_text()
        assert "[Desktop Entry]" in content
        assert "Type=Application" in content
        assert "Exec=/usr/bin/eyes" in content
        assert "X-GNOME-Autostart-enabled=true" in content
        assert "Hidden=false" in content

    def test_disable_removes_desktop_file(self, tmp_path: Path) -> None:
        """Disabling autostart removes the desktop entry file."""
        from eyes.autostart import LinuxAutostartBackend

        backend = LinuxAutostartBackend.__new__(LinuxAutostartBackend)
        backend._autostart_dir = tmp_path / ".config" / "autostart"
        backend._desktop_file = backend._autostart_dir / "eyes.desktop"

        # First enable
        backend.enable("/usr/bin/eyes")
        assert backend._desktop_file.exists()

        # Then disable
        backend.disable()
        assert not backend._desktop_file.exists()

    def test_disable_idempotent_when_not_enabled(self, tmp_path: Path) -> None:
        """Disabling when not enabled does not raise."""
        from eyes.autostart import LinuxAutostartBackend

        backend = LinuxAutostartBackend.__new__(LinuxAutostartBackend)
        backend._autostart_dir = tmp_path / ".config" / "autostart"
        backend._desktop_file = backend._autostart_dir / "eyes.desktop"

        # Disable when not enabled - should not raise
        backend.disable()
        assert not backend._desktop_file.exists()

    def test_enable_idempotent(self, tmp_path: Path) -> None:
        """Enabling twice does not raise and creates valid entry."""
        from eyes.autostart import LinuxAutostartBackend

        backend = LinuxAutostartBackend.__new__(LinuxAutostartBackend)
        backend._autostart_dir = tmp_path / ".config" / "autostart"
        backend._desktop_file = backend._autostart_dir / "eyes.desktop"

        backend.enable("/usr/bin/eyes")
        backend.enable("/usr/bin/eyes")  # idempotent

        content = backend._desktop_file.read_text()
        assert "Exec=/usr/bin/eyes" in content

    def test_is_enabled_returns_true_when_file_exists(self, tmp_path: Path) -> None:
        """is_enabled returns True when desktop file exists."""
        from eyes.autostart import LinuxAutostartBackend

        backend = LinuxAutostartBackend.__new__(LinuxAutostartBackend)
        backend._autostart_dir = tmp_path / ".config" / "autostart"
        backend._desktop_file = backend._autostart_dir / "eyes.desktop"

        assert backend.is_enabled() is False

        backend._desktop_file.parent.mkdir(parents=True)
        backend._desktop_file.write_text("[Desktop Entry]\nExec=test\n")

        assert backend.is_enabled() is True


class TestAutostartManager:
    """Tests for AutostartManager apply_config method."""

    def test_apply_config_enable_calls_backend(self) -> None:
        """apply_config(True) calls backend.enable()."""
        from eyes.autostart import AutostartManager

        mock_backend = MagicMock()
        with patch.object(AutostartManager, "__init__", lambda self: setattr(self, "_backend", mock_backend)):
            manager = AutostartManager.__new__(AutostartManager)
            manager._backend = mock_backend

        manager.apply_config(True)
        mock_backend.enable.assert_called_once()

    def test_apply_config_disable_calls_backend(self) -> None:
        """apply_config(False) calls backend.disable()."""
        from eyes.autostart import AutostartManager

        mock_backend = MagicMock()
        with patch.object(AutostartManager, "__init__", lambda self: setattr(self, "_backend", mock_backend)):
            manager = AutostartManager.__new__(AutostartManager)
            manager._backend = mock_backend

        manager.apply_config(False)
        mock_backend.disable.assert_called_once()

    def test_is_enabled_delegates_to_backend(self) -> None:
        """is_enabled() returns backend's state."""
        from eyes.autostart import AutostartManager

        mock_backend = MagicMock()
        mock_backend.is_enabled.return_value = True
        with patch.object(AutostartManager, "__init__", lambda self: setattr(self, "_backend", mock_backend)):
            manager = AutostartManager.__new__(AutostartManager)
            manager._backend = mock_backend

        assert manager.is_enabled() is True
        mock_backend.is_enabled.assert_called_once()


class TestAutostartConfigIntegration:
    """Integration tests for autostart config persistence."""

    def test_autostart_setting_roundtrips_through_config_store(self, tmp_path: Path) -> None:
        """Toggling autostart_enabled persists correctly."""
        from eyes.autostart import AutostartManager
        from eyes.config_store import ConfigStore

        # Setup
        config_store = ConfigStore(config_dir=tmp_path)
        config_store.load()

        # Mock the backend to avoid actual OS calls
        mock_backend = MagicMock()
        with patch.object(AutostartManager, "__init__", lambda self: setattr(self, "_backend", mock_backend)):
            manager = AutostartManager.__new__(AutostartManager)
            manager._backend = mock_backend

        # Toggle on
        config_store.update(autostart_enabled=True)
        manager.apply_config(config_store.load().autostart_enabled)
        mock_backend.enable.assert_called_once()

        # Toggle off
        config_store.update(autostart_enabled=False)
        manager.apply_config(config_store.load().autostart_enabled)
        mock_backend.disable.assert_called_once()

    def test_default_config_has_autostart_disabled(self, tmp_path: Path) -> None:
        """Default AppConfig has autostart_enabled=False."""
        from eyes.config_store import ConfigStore

        config_store = ConfigStore(config_dir=tmp_path)
        config = config_store.load()

        assert config.autostart_enabled is False


class TestAutostartErrorHandling:
    """Tests for AutostartError exception handling."""

    def test_linux_disable_raises_autostart_error_on_oserror(self, tmp_path: Path) -> None:
        """Linux backend raises AutostartError when unlink fails on parent dir."""
        from eyes.autostart import AutostartError
        from eyes.autostart import LinuxAutostartBackend

        backend = LinuxAutostartBackend.__new__(LinuxAutostartBackend)
        # Create a directory instead of a file, so unlink will fail
        backend._autostart_dir = tmp_path / ".config" / "autostart"
        backend._desktop_file = backend._autostart_dir / "eyes.desktop"
        backend._autostart_dir.mkdir(parents=True, exist_ok=True)
        backend._desktop_file.mkdir()  # File is actually a directory

        with pytest.raises(AutostartError):
            backend.disable()

    def test_autostart_manager_enable_catches_autostart_error_and_logs(self, caplog) -> None:
        """AutostartManager.enable() catches AutostartError and logs it."""
        import logging
        from eyes.autostart import AutostartError, AutostartManager

        mock_backend = MagicMock()
        mock_backend.enable.side_effect = AutostartError("Simulated error")
        with patch.object(AutostartManager, "__init__", lambda self: setattr(self, "_backend", mock_backend)):
            manager = AutostartManager.__new__(AutostartManager)
            manager._backend = mock_backend

        with caplog.at_level(logging.ERROR):
            manager.enable()  # Should not raise, just log

        assert len(caplog.records) >= 1
        assert any("enable failed" in record.message.lower() for record in caplog.records)

    def test_autostart_manager_disable_catches_autostart_error_and_logs(self, caplog) -> None:
        """AutostartManager.disable() catches AutostartError and logs it."""
        import logging
        from eyes.autostart import AutostartError, AutostartManager

        mock_backend = MagicMock()
        mock_backend.disable.side_effect = AutostartError("Simulated error")
        with patch.object(AutostartManager, "__init__", lambda self: setattr(self, "_backend", mock_backend)):
            manager = AutostartManager.__new__(AutostartManager)
            manager._backend = mock_backend

        with caplog.at_level(logging.ERROR):
            manager.disable()  # Should not raise, just log

        assert len(caplog.records) >= 1
        assert any("disable failed" in record.message.lower() for record in caplog.records)


class TestGetExecPath:
    """Tests for _get_exec_path behavior."""

    def test_linux_get_exec_path_source_mode(self) -> None:
        """Linux backend returns 'python -m eyes' in source mode."""
        from eyes.autostart import LinuxAutostartBackend

        backend = LinuxAutostartBackend.__new__(LinuxAutostartBackend)
        backend._autostart_dir = Path("/tmp")
        backend._desktop_file = Path("/tmp/eyes.desktop")

        with patch.object(sys, "frozen", False, create=True):
            exec_path = backend._get_exec_path()

        assert "-m eyes" in exec_path
        assert "python" in exec_path or "python3" in exec_path

    def test_linux_get_exec_path_frozen_mode(self) -> None:
        """Linux backend returns sys.executable when frozen."""
        from eyes.autostart import LinuxAutostartBackend

        backend = LinuxAutostartBackend.__new__(LinuxAutostartBackend)
        backend._autostart_dir = Path("/tmp")
        backend._desktop_file = Path("/tmp/eyes.desktop")

        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", "/usr/bin/eyes"):
                exec_path = backend._get_exec_path()

        assert exec_path == "/usr/bin/eyes"

    def test_build_desktop_entry_format(self, tmp_path: Path) -> None:
        """_build_desktop_entry produces valid desktop entry format."""
        from eyes.autostart import LinuxAutostartBackend

        backend = LinuxAutostartBackend.__new__(LinuxAutostartBackend)
        backend._autostart_dir = tmp_path
        backend._desktop_file = tmp_path / "eyes.desktop"

        content = backend._build_desktop_entry("/usr/bin/eyes")

        lines = content.split("\n")
        assert "[Desktop Entry]" in lines
        assert "Type=Application" in lines
        assert "Exec=/usr/bin/eyes" in lines
        assert "Name=Eyes" in lines
        assert "Comment=Eye rest reminder" in lines


class TestWindowsAutostartBackend:
    """Tests for Windows registry autostart backend."""

    def test_is_enabled_returns_true_when_registry_key_exists(self) -> None:
        """is_enabled returns True when registry value exists."""
        from eyes.autostart import WindowsAutostartBackend

        backend = WindowsAutostartBackend.__new__(WindowsAutostartBackend)

        # Mock winreg
        mock_key = MagicMock()
        mock_key.QueryValueEx.return_value = ("C:\\path\\to\\eyes.exe", None)
        mock_winreg = MagicMock()
        mock_winreg.HKEY_CURRENT_USER = 0
        mock_winreg.KEY_READ = 1
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.QueryValueEx.return_value = ("C:\\path\\to\\eyes.exe", None)
        backend._winreg = mock_winreg

        result = backend.is_enabled()

        assert result is True
        mock_winreg.OpenKey.assert_called()
        mock_winreg.QueryValueEx.assert_called()

    def test_is_enabled_returns_false_when_registry_key_missing(self) -> None:
        """is_enabled returns False when registry value does not exist."""
        from eyes.autostart import WindowsAutostartBackend

        backend = WindowsAutostartBackend.__new__(WindowsAutostartBackend)

        # Mock winreg with FileNotFoundError
        mock_winreg = MagicMock()
        mock_winreg.HKEY_CURRENT_USER = 0
        mock_winreg.KEY_READ = 1
        mock_winreg.OpenKey.side_effect = FileNotFoundError()
        backend._winreg = mock_winreg

        result = backend.is_enabled()

        assert result is False

    def test_is_enabled_returns_false_when_oserror(self) -> None:
        """is_enabled returns False when registry access fails."""
        from eyes.autostart import WindowsAutostartBackend

        backend = WindowsAutostartBackend.__new__(WindowsAutostartBackend)

        mock_winreg = MagicMock()
        mock_winreg.HKEY_CURRENT_USER = 0
        mock_winreg.KEY_READ = 1
        mock_winreg.OpenKey.side_effect = OSError("Access denied")
        backend._winreg = mock_winreg

        result = backend.is_enabled()

        assert result is False

    def test_enable_sets_registry_value(self) -> None:
        """enable() writes executable path to registry."""
        from eyes.autostart import WindowsAutostartBackend

        backend = WindowsAutostartBackend.__new__(WindowsAutostartBackend)

        mock_key = MagicMock()
        mock_winreg = MagicMock()
        mock_winreg.HKEY_CURRENT_USER = 0
        mock_winreg.KEY_SET_VALUE = 1
        mock_winreg.REG_SZ = 1
        mock_winreg.OpenKey.return_value = mock_key
        backend._winreg = mock_winreg

        backend.enable("C:\\path\\to\\eyes.exe")

        mock_winreg.SetValueEx.assert_called_once()
        call_args = mock_winreg.SetValueEx.call_args
        assert call_args[0][0] == mock_key
        assert call_args[0][1] == "Eyes"
        assert call_args[0][2] == 0  # reserved
        assert call_args[0][3] == 1  # REG_SZ
        assert call_args[0][4] == "C:\\path\\to\\eyes.exe"
        mock_winreg.CloseKey.assert_called_with(mock_key)

    def test_enable_raises_autostart_error_on_oserror(self) -> None:
        """enable() raises AutostartError when registry access fails."""
        from eyes.autostart import AutostartError, WindowsAutostartBackend

        backend = WindowsAutostartBackend.__new__(WindowsAutostartBackend)

        mock_winreg = MagicMock()
        mock_winreg.HKEY_CURRENT_USER = 0
        mock_winreg.KEY_SET_VALUE = 1
        mock_winreg.OpenKey.side_effect = OSError("Access denied")
        backend._winreg = mock_winreg

        with pytest.raises(AutostartError) as exc_info:
            backend.enable("C:\\path\\to\\eyes.exe")

        assert "Access denied" in str(exc_info.value)

    def test_disable_deletes_registry_value(self) -> None:
        """disable() removes registry value."""
        from eyes.autostart import WindowsAutostartBackend

        backend = WindowsAutostartBackend.__new__(WindowsAutostartBackend)

        mock_key = MagicMock()
        mock_winreg = MagicMock()
        mock_winreg.HKEY_CURRENT_USER = 0
        mock_winreg.KEY_SET_VALUE = 1
        mock_winreg.OpenKey.return_value = mock_key
        backend._winreg = mock_winreg

        backend.disable()

        mock_winreg.DeleteValue.assert_called_once()
        mock_winreg.CloseKey.assert_called_with(mock_key)

    def test_disable_ignores_missing_value(self) -> None:
        """disable() does not raise when registry value does not exist."""
        from eyes.autostart import WindowsAutostartBackend

        backend = WindowsAutostartBackend.__new__(WindowsAutostartBackend)

        mock_key = MagicMock()
        mock_winreg = MagicMock()
        mock_winreg.HKEY_CURRENT_USER = 0
        mock_winreg.KEY_SET_VALUE = 1
        mock_winreg.OpenKey.return_value = mock_key
        mock_winreg.DeleteValue.side_effect = FileNotFoundError()
        backend._winreg = mock_winreg

        # Should not raise
        backend.disable()

        mock_winreg.CloseKey.assert_called_with(mock_key)

    def test_disable_raises_autostart_error_on_oserror(self) -> None:
        """disable() raises AutostartError when registry access fails."""
        from eyes.autostart import AutostartError, WindowsAutostartBackend

        backend = WindowsAutostartBackend.__new__(WindowsAutostartBackend)

        mock_winreg = MagicMock()
        mock_winreg.HKEY_CURRENT_USER = 0
        mock_winreg.KEY_SET_VALUE = 1
        mock_winreg.OpenKey.side_effect = OSError("Access denied")
        backend._winreg = mock_winreg

        with pytest.raises(AutostartError) as exc_info:
            backend.disable()

        assert "Access denied" in str(exc_info.value)

    def test_no_winreg_returns_false_on_is_enabled(self) -> None:
        """is_enabled returns False when winreg is unavailable."""
        from eyes.autostart import WindowsAutostartBackend

        backend = WindowsAutostartBackend.__new__(WindowsAutostartBackend)
        backend._winreg = None

        result = backend.is_enabled()

        assert result is False

    def test_no_winreg_returns_early_on_enable(self) -> None:
        """enable() returns early when winreg is unavailable."""
        from eyes.autostart import WindowsAutostartBackend

        backend = WindowsAutostartBackend.__new__(WindowsAutostartBackend)
        backend._winreg = None

        # Should not raise
        backend.enable("C:\\path\\to\\eyes.exe")

    def test_no_winreg_returns_early_on_disable(self) -> None:
        """disable() returns early when winreg is unavailable."""
        from eyes.autostart import WindowsAutostartBackend

        backend = WindowsAutostartBackend.__new__(WindowsAutostartBackend)
        backend._winreg = None

        # Should not raise
        backend.disable()

    def test_get_exec_path_frozen(self) -> None:
        """_get_exec_path returns sys.executable when frozen."""
        from eyes.autostart import WindowsAutostartBackend

        backend = WindowsAutostartBackend.__new__(WindowsAutostartBackend)
        backend._winreg = None

        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "executable", "C:\\path\\to\\eyes.exe"):
                exec_path = backend._get_exec_path()

        assert exec_path == "C:\\path\\to\\eyes.exe"

    def test_get_exec_path_source_returns_none(self) -> None:
        """_get_exec_path returns None in source mode on Windows."""
        from eyes.autostart import WindowsAutostartBackend

        backend = WindowsAutostartBackend.__new__(WindowsAutostartBackend)
        backend._winreg = None

        with patch.object(sys, "frozen", False, create=True):
            exec_path = backend._get_exec_path()

        assert exec_path is None

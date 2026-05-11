"""Tests for autostart module."""

from __future__ import annotations

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
        from eyes.types import AppConfig

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

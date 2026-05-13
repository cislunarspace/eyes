"""Tests for Linux packaging (TDD RED phase).

These tests verify the Linux-specific packaging requirements:
- Linux spec file exists and is valid
- Build script works correctly
- Desktop entry handles frozen executable paths
- Config directory uses XDG conventions
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

import platformdirs
import pytest


PROJECT_ROOT = Path(__file__).parent.parent.resolve()
LINUX_SPEC_FILE = PROJECT_ROOT / "eyes-linux.spec"
LINUX_BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build-linux.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def linux_spec_source() -> str:
    """Parse and return the Linux spec file contents."""
    if not LINUX_SPEC_FILE.exists():
        pytest.fail(f"Linux spec file not found at {LINUX_SPEC_FILE}")
    return LINUX_SPEC_FILE.read_text(encoding="utf-8")


@pytest.fixture
def linux_build_source() -> str:
    """Parse and return the Linux build script contents."""
    if not LINUX_BUILD_SCRIPT.exists():
        pytest.fail(f"Linux build script not found at {LINUX_BUILD_SCRIPT}")
    return LINUX_BUILD_SCRIPT.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1: Linux spec file exists and is valid Python syntax
# ---------------------------------------------------------------------------

def test_linux_spec_file_exists():
    """Linux spec file must exist at the project root."""
    assert LINUX_SPEC_FILE.exists(), f"Expected Linux spec file at {LINUX_SPEC_FILE}"


def test_linux_spec_file_has_valid_python_syntax(linux_spec_source: str):
    """Linux spec file must parse as valid Python."""
    try:
        ast.parse(linux_spec_source)
    except SyntaxError as exc:
        pytest.fail(f"Linux spec file has syntax error: {exc}")


# ---------------------------------------------------------------------------
# Test 2: Linux spec references the correct entry point
# ---------------------------------------------------------------------------

def test_linux_spec_references_main_py_as_entry_point(linux_spec_source: str):
    """Spec file's Analysis must reference main.py as the entry point script."""
    assert "main.py" in linux_spec_source, (
        "Linux spec must reference 'main.py' as the entry point script"
    )


# ---------------------------------------------------------------------------
# Test 3: Linux spec includes necessary collections
# ---------------------------------------------------------------------------

def test_linux_spec_collects_mediapipe(linux_spec_source: str):
    """Linux spec must collect all mediapipe resources."""
    assert "mediapipe" in linux_spec_source, (
        "Linux spec must include mediapipe collection"
    )


def test_linux_spec_collects_pyside6(linux_spec_source: str):
    """Linux spec must collect all PySide6 resources."""
    assert "PySide6" in linux_spec_source, (
        "Linux spec must include PySide6 collection"
    )


def test_linux_spec_includes_cv2_hidden_import(linux_spec_source: str):
    """Linux spec must include cv2 as a hidden import."""
    normalized = linux_spec_source.replace("\\", "/")
    assert "cv2" in normalized, (
        "Linux spec must include cv2 hidden import"
    )


# ---------------------------------------------------------------------------
# Test 4: Linux spec excludes Windows-specific settings
# ---------------------------------------------------------------------------

def test_linux_spec_does_not_reference_windows_registry(linux_spec_source: str):
    """Linux spec should not reference Windows registry paths."""
    assert "winreg" not in linux_spec_source, (
        "Linux spec should not reference Windows registry"
    )


def test_linux_spec_uses_console_false_for_gui_app(linux_spec_source: str):
    """Linux spec should use console=False for GUI app (or handle it appropriately)."""
    normalized = linux_spec_source.replace("\\", "/")
    # Either console=False or it's not present (defaults to False)
    has_console_false = "console=False" in normalized
    assert has_console_false, (
        "Linux spec should explicitly set console=False for GUI app"
    )


# ---------------------------------------------------------------------------
# Test 5: Linux build script exists and is valid
# ---------------------------------------------------------------------------

def test_linux_build_script_exists():
    """Linux build script must exist at scripts/build-linux.py."""
    assert LINUX_BUILD_SCRIPT.exists(), (
        f"Expected Linux build script at {LINUX_BUILD_SCRIPT}"
    )


def test_linux_build_script_is_valid_python(linux_build_source: str):
    """Linux build script must parse as valid Python."""
    try:
        ast.parse(linux_build_source)
    except SyntaxError as exc:
        pytest.fail(f"Linux build script has syntax error: {exc}")


def test_linux_build_script_invokes_pyinstaller(linux_build_source: str):
    """Linux build script must call pyinstaller."""
    assert "pyinstaller" in linux_build_source.lower() or "subprocess" in linux_build_source, (
        "Linux build script must invoke pyinstaller"
    )


def test_linux_build_script_references_linux_spec(linux_build_source: str):
    """Linux build script must reference the Linux spec file."""
    assert "eyes-linux.spec" in linux_build_source, (
        "Linux build script must reference eyes-linux.spec"
    )


# ---------------------------------------------------------------------------
# Test 6: Build script output is Linux-compatible
# ---------------------------------------------------------------------------

def test_linux_build_script_output_name_is_unix_compatible(linux_build_source: str):
    """Build script should output to a Unix-compatible directory name."""
    # Look for output directory naming
    normalized = linux_build_source.replace("\\", "/")
    # On Linux, we typically use lowercase without .exe
    # Should not reference .exe in output name
    if "name=" in normalized:
        # If there's a name= parameter, it should be lowercase
        assert "Eyes.exe" not in normalized, (
            "Linux build script should not output Eyes.exe"
        )


# ---------------------------------------------------------------------------
# Test 7: Desktop entry works with frozen executable
# ---------------------------------------------------------------------------

def test_linux_autostart_handles_frozen_executable():
    """Linux autostart should correctly report frozen executable path."""
    from eyes.autostart import LinuxAutostartBackend

    backend = LinuxAutostartBackend.__new__(LinuxAutostartBackend)

    # Simulate frozen environment (create=True because sys.frozen only exists in PyInstaller)
    with patch.object(sys, "frozen", True, create=True):
        with patch.object(sys, "executable", "/usr/bin/eyes"):
            exec_path = backend._get_exec_path()
            assert exec_path == "/usr/bin/eyes"


def test_linux_autostart_handles_dev_executable():
    """Linux autostart should use python -m eyes in dev environment."""
    from eyes.autostart import LinuxAutostartBackend

    backend = LinuxAutostartBackend.__new__(LinuxAutostartBackend)

    # Simulate non-frozen (dev) environment (create=True because sys.frozen only exists in PyInstaller)
    with patch.object(sys, "frozen", False, create=True):
        with patch.object(sys, "executable", "/usr/bin/python"):
            exec_path = backend._get_exec_path()
            # In dev mode, should use python -m eyes
            assert "python" in exec_path.lower() and "-m eyes" in exec_path


def test_linux_autostart_desktop_entry_content():
    """Desktop entry should have correct XDG format."""
    from eyes.autostart import LinuxAutostartBackend

    backend = LinuxAutostartBackend.__new__(LinuxAutostartBackend)

    content = backend._build_desktop_entry("/usr/bin/eyes")
    lines = content.strip().split("\n")

    # Check required XDG fields
    assert any("Type=Application" in line for line in lines), (
        "Desktop entry must have Type=Application"
    )
    assert any("Exec=/usr/bin/eyes" in line for line in lines), (
        "Desktop entry must have Exec field"
    )
    assert any("X-GNOME-Autostart-enabled=true" in line for line in lines), (
        "Desktop entry should have X-GNOME-Autostart-enabled=true"
    )


# ---------------------------------------------------------------------------
# Test 8: Config directory uses XDG conventions
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    sys.platform != "linux", reason="platformdirs Linux paths are host-platform specific"
)
def test_config_store_uses_platformdirs():
    """ConfigStore should use platformdirs for XDG compliance on Linux."""
    from eyes.config_store import ConfigStore

    store = ConfigStore()

    assert store._config_dir == Path(platformdirs.user_config_dir("eyes"))


def test_config_store_config_dir_uses_dot_config_eyes(tmp_path: Path):
    """ConfigStore should create ~/.config/eyes on Linux."""
    from eyes.config_store import ConfigStore

    with patch("platformdirs.user_config_dir", return_value=str(tmp_path / ".config" / "eyes")):
        store = ConfigStore(config_dir=tmp_path / ".config" / "eyes")
        store._ensure_dir()

        # Verify the directory is created
        assert store._config_dir.exists(), (
            f"Config directory should be created at {store._config_dir}"
        )

        # Verify config file path is within it
        assert str(store._config_file).startswith(str(store._config_dir)), (
            "Config file should be within config directory"
        )


# ---------------------------------------------------------------------------
# Test 9: GitHub Actions workflow exists
# ---------------------------------------------------------------------------

def test_linux_ci_workflow_exists():
    """GitHub Actions workflow for Linux build should exist."""
    workflow_path = PROJECT_ROOT / ".github" / "workflows" / "linux-build.yml"
    if not workflow_path.exists():
        # Also check for alternative names
        alternative_paths = [
            PROJECT_ROOT / ".github" / "workflows" / "linux.yml",
            PROJECT_ROOT / ".github" / "workflows" / "release.yml",
        ]
        workflow_exists = any(p.exists() for p in alternative_paths)
        assert workflow_exists, (
            f"Linux CI workflow not found at {workflow_path} or alternatives"
        )


# ---------------------------------------------------------------------------
# Test 10: Linux build output tarball naming
# ---------------------------------------------------------------------------

def test_linux_build_script_produces_tarball_naming(linux_build_source: str):
    """Linux build script should produce a .tar.gz output."""
    normalized = linux_build_source.replace("\\", "/")
    # Should reference tar.gz or tarball creation
    has_tarball_output = (
        ".tar.gz" in normalized
        or "tar" in normalized
        or "shutil.make_archive" in normalized
        or "compress" in normalized.lower()
    )
    assert has_tarball_output, (
        "Linux build script should produce a .tar.gz tarball"
    )

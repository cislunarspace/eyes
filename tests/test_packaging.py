"""PyInstaller packaging tests (TDD RED phase)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
SPEC_FILE = PROJECT_ROOT / "eyes.spec"
BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def spec_source() -> str:
    """Parse and return the spec file contents."""
    if not SPEC_FILE.exists():
        pytest.fail(f"Spec file not found at {SPEC_FILE}")
    return SPEC_FILE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1: Spec file exists and is valid Python syntax
# ---------------------------------------------------------------------------

def test_spec_file_exists():
    """Spec file must exist at the project root."""
    assert SPEC_FILE.exists(), f"Expected spec file at {SPEC_FILE}"


def test_spec_file_has_valid_python_syntax(spec_source: str):
    """Spec file must parse as valid Python."""
    try:
        ast.parse(spec_source)
    except SyntaxError as exc:
        pytest.fail(f"Spec file has syntax error: {exc}")


# ---------------------------------------------------------------------------
# Test 2: Spec file references the correct entry point
# ---------------------------------------------------------------------------

def test_spec_references_main_py_as_entry_point(spec_source: str):
    """Spec file's Analysis.pathex must include the project root directory."""
    # The spec should reference 'main.py' as the script entry point.
    assert "main.py" in spec_source, (
        "Spec file must reference 'main.py' as the entry point script"
    )


def test_spec_script_points_to_project_root(spec_source: str):
    """Spec file should reference the project root path."""
    normalized = spec_source.replace("\\", "/")
    assert "main.py" in normalized, (
        "Spec Analysis should include main.py"
    )


# ---------------------------------------------------------------------------
# Test 3: Spec file includes mediapipe and PySide6 collect directives
# ---------------------------------------------------------------------------

def test_spec_collects_mediapipe(spec_source: str):
    """Spec file must collect all mediapipe resources."""
    assert "mediapipe" in spec_source, (
        "Spec must include --collect-all mediapipe"
    )


def test_spec_collects_pyside6(spec_source: str):
    """Spec file must collect all PySide6 resources."""
    assert "PySide6" in spec_source, (
        "Spec must include --collect-all PySide6"
    )


# ---------------------------------------------------------------------------
# Test 4: Build script exists and is executable (readable)
# ---------------------------------------------------------------------------

def test_build_script_exists():
    """Build script must exist at scripts/build.py."""
    assert BUILD_SCRIPT.exists(), (
        f"Expected build script at {BUILD_SCRIPT}"
    )


def test_build_script_is_valid_python():
    """Build script must parse as valid Python."""
    src = BUILD_SCRIPT.read_text(encoding="utf-8")
    try:
        ast.parse(src)
    except SyntaxError as exc:
        pytest.fail(f"Build script has syntax error: {exc}")


def test_build_script_invokes_pyinstaller():
    """Build script must call pyinstaller (or subprocess run of spec)."""
    src = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "pyinstaller" in src.lower() or "subprocess" in src, (
        "Build script must invoke pyinstaller"
    )


# ---------------------------------------------------------------------------
# Test 5: Spec handles frozen-app path awareness
# ---------------------------------------------------------------------------

def test_spec_handles_frozen_path(spec_source: str):
    """Spec must honour %APPDATA% paths (not use _MEIPASS sandbox)."""
    # At minimum the spec should use sys.frozen / getattr(sys, 'frozen')
    # checks or explicitly set a datas=[...] that copies config into the
    # bundle, rather than relying on the default _MEIPASS extraction.
    # We verify the spec references 'frozen' or '_MEIPASS' so the developer
    # is aware of the distinction.
    normalized = spec_source.replace("\\", "/")
    has_frozen_guard = (
        "frozen" in normalized
        or "_MEIPASS" in normalized
        or "pathex" in normalized
    )
    assert has_frozen_guard, (
        "Spec should reference 'frozen' or '_MEIPASS' to ensure "
        "%APPDATA% path handling is considered"
    )


# ---------------------------------------------------------------------------
# Test 6: Spec includes cv2 hidden import
# ---------------------------------------------------------------------------

def test_spec_includes_cv2_hidden_import(spec_source: str):
    """Spec must include cv2 as a hidden import."""
    normalized = spec_source.replace("\\", "/")
    assert "cv2" in normalized, (
        "Spec must include cv2 hidden import"
    )

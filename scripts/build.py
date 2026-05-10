#!/usr/bin/env python3
"""
Build script for Eyes PyInstaller distribution.

Usage:
    python scripts/build.py          # one-folder (onedir) build
    python scripts/build.py --clean  # clean build directory first

Output:
    dist/Eyes/   <- one-folder distribution
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
SPEC_FILE = PROJECT_ROOT / "eyes.spec"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Eyes distribution.")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove existing dist/ and build/ before building.",
    )
    return parser.parse_args()


def clean() -> None:
    """Remove any previous build artifacts."""
    for path in (DIST_DIR, BUILD_DIR):
        if path.exists():
            shutil.rmtree(path)
            print(f"[build] Removed {path}")


def build() -> None:
    """Run PyInstaller with the eyes.spec spec file."""
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(SPEC_FILE),
    ]
    print(f"[build] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    if result.returncode != 0:
        print("[build] PyInstaller build failed.", file=sys.stderr)
        sys.exit(result.returncode)

    exe_path = DIST_DIR / "Eyes" / "Eyes.exe"
    if exe_path.exists():
        print(f"[build] Success! Executable at {exe_path}")
    else:
        print(f"[build] Warning: expected exe not found at {exe_path}")


def main() -> None:
    args = parse_args()
    if args.clean:
        clean()
    build()


if __name__ == "__main__":
    main()

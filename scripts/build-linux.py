#!/usr/bin/env python3
"""
Build script for Eyes PyInstaller distribution on Linux.

Usage:
    python scripts/build-linux.py          # one-folder (onedir) build
    python scripts/build-linux.py --clean # clean build directory first

Output:
    dist/eyes/           <- one-folder distribution
    dist/eyes-linux-x86_64.tar.gz  <- redistributable tarball
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
SPEC_FILE = PROJECT_ROOT / "eyes-linux.spec"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Eyes distribution for Linux.")
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
    """Run PyInstaller with the eyes-linux.spec spec file."""
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

    exe_path = DIST_DIR / "eyes" / "eyes"
    if exe_path.exists():
        print(f"[build] Success! Executable at {exe_path}")
    else:
        print(f"[build] Warning: expected executable not found at {exe_path}")


def create_tarball() -> Path:
    """Create a redistributable tarball from the onedir build."""
    dist_dir = DIST_DIR / "eyes"
    if not dist_dir.exists():
        print("[build] Error: dist/eyes/ not found. Run build first.", file=sys.stderr)
        sys.exit(1)

    tarball_name = "eyes-linux-x86_64.tar.gz"
    tarball_path = DIST_DIR / tarball_name

    # Remove existing tarball if present
    if tarball_path.exists():
        tarball_path.unlink()

    # Create tarball using shutil
    print(f"[build] Creating tarball: {tarball_path}")
    shutil.make_archive(
        base_name=str(DIST_DIR / "eyes"),
        format="gztar",
        root_dir=str(DIST_DIR),
        base_dir="eyes",
    )

    # shutil.make_archive appends .tar.gz automatically
    # Verify the tarball was created
    if tarball_path.exists():
        size_mb = tarball_path.stat().st_size / (1024 * 1024)
        print(f"[build] Tarball created: {tarball_path} ({size_mb:.1f} MB)")
    else:
        print(f"[build] Warning: tarball not found at {tarball_path}", file=sys.stderr)

    return tarball_path


def main() -> None:
    args = parse_args()
    if args.clean:
        clean()
    build()
    tarball = create_tarball()
    print(f"[build] Done! Distributable: {tarball}")


if __name__ == "__main__":
    main()

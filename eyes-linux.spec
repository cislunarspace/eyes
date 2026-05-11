# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for the Eyes desktop application on Linux.
Produces a one-folder distribution (onedir) that works with XDG
user directories (~/.config/eyes/) instead of the frozen-app sandbox.

Requirements:
  --collect-all mediapipe
  --collect-all PySide6
  hidden import: cv2
  entry point: main.py

Tested on: Ubuntu 22.04 LTS (X11)
"""

from pathlib import Path

from PyInstaller.building.build_main import Analysis, PYZ
from PyInstaller.building.datastruct import Tree
from PyInstaller.building.make_bundle import EXECUTABLE

block_cipher = None

# Project root (where main.py and this spec file live)
project_root = Path(__file__).parent.resolve()

# ---------------------------------------------------------------------------
# Packages not detected statically by PyInstaller — must be declared
# ---------------------------------------------------------------------------
hidden_imports = [
    "cv2",
    "mediapipe",
    "mediapipe.python",
    "mediapipe.python._version",
    "mediapipe.tasks.python",
]

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    key=block_cipher,
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy.f2py",
        "scipy",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

# --collect-all mediapipe
a.datas += Tree("mediapipe", stripsrc=None, excludes=None, remove_na=True)

# --collect-all PySide6
a.datas += Tree("PySide6", stripsrc=None, excludes=None, remove_na=True)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXECUTABLE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=False,
    name="eyes",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

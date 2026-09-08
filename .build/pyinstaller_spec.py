# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for OpenBoard chess GUI.

This spec file is optimized for wxPython applications and includes
proper handling of all OpenBoard dependencies including:
- wxPython GUI framework
- accessible-output3 for screen reader support
- chess library for game logic
- blinker for signal-based MVC communication
"""

import platform
import tomllib
from pathlib import Path

# PyInstaller imports
from PyInstaller.building.api import EXE, PYZ, COLLECT
from PyInstaller.building.build_main import Analysis
from PyInstaller.building.osx import BUNDLE

# Application metadata
APP_NAME = "OpenBoard"

# Platform-specific settings
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"

# build.py invokes PyInstaller from the checkout root.
BASE_DIR = Path.cwd()
with (BASE_DIR / "pyproject.toml").open("rb") as metadata:
    APP_VERSION = tomllib.load(metadata)["project"]["version"]

# Data files to include
DATA_FILES = [
    # Include any configuration files or assets if they exist
    # Note: Add actual data files here if the application uses them
]

# Binaries to exclude (we'll handle engines separately)
EXCLUDE_BINARIES = []

# Hook directories
HOOK_DIRS = [str(BASE_DIR / ".build" / "hooks")]

# Analysis configuration
a = Analysis(
    # Entry point script - create a simple launcher
    [str(BASE_DIR / "openboard" / "__main__.py")],
    pathex=[str(BASE_DIR)],
    binaries=[],
    datas=DATA_FILES,
    hiddenimports=[],
    hookspath=HOOK_DIRS,
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce bundle size
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "IPython",
        "jupyter",
        "notebook",
        "qt5",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "gtk",
    ],
    noarchive=False,
)

# PYZ (Python ZIP archive)
pyz = PYZ(a.pure)

# Executable configuration
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # Console mode for accessibility and debugging
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Platform-specific options
    icon=str(BASE_DIR / "assets" / "icons" / "openboard.ico") if IS_WINDOWS else None,
    version=None,
)

# Bundle configuration (for macOS app bundle or Linux directory)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

# macOS app bundle (only on macOS)
if IS_MACOS:
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=str(BASE_DIR / "assets" / "icons" / "openboard.icns"),
        bundle_identifier=f"com.openboard.{APP_NAME.lower()}",
        version=APP_VERSION,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleVersion": APP_VERSION,
            "CFBundleShortVersionString": APP_VERSION,
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
        },
    )

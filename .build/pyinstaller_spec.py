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
from pathlib import Path

# PyInstaller imports
from PyInstaller.building.api import EXE, PYZ, COLLECT
from PyInstaller.building.build_main import Analysis
from PyInstaller.building.osx import BUNDLE

# Application metadata
APP_NAME = "OpenBoard"
APP_VERSION = "0.1.0"
ENTRY_POINT = "openboard.views.views:main"

# Platform-specific settings
IS_WINDOWS = platform.system() == "Windows"
IS_MACOS = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"

# Base directory (project root)
try:
    BASE_DIR = Path(__file__).parent.parent
except NameError:
    # When executed directly, use current working directory assumption
    BASE_DIR = Path.cwd()

# Hidden imports required for dynamic loading
# Note: OpenBoard-specific imports are handled by hook-openboard.py
HIDDEN_IMPORTS = [
    # wxPython modules that may not be auto-detected
    "wx",
    "wx.lib",
    "wx.lib.newevent",
    "wx.adv",
    "wx.grid",
    "wx.html",
    "wx.media",
    "wx.propgrid",
    "wx.ribbon",
    "wx.richtext",
    "wx.stc",
    "wx.webkit",
    "wx.xml",
    # accessible-output3 modules
    "accessible_output3",
    "accessible_output3.outputs",
    "accessible_output3.outputs.auto",
    "accessible_output3.outputs.base",
    "accessible_output3.outputs.nvda",
    "accessible_output3.outputs.jaws",
    "accessible_output3.outputs.sapi",
    "accessible_output3.outputs.speechd",
    "accessible_output3.outputs.voiceover",
    # Chess library modules
    "chess",
    "chess.engine",
    "chess.polyglot",
    "chess.pgn",
    "chess.svg",
    "chess.syzygy",
    # Blinker for signals
    "blinker",
    # Standard library modules that might be missed
    "asyncio",
    "concurrent.futures",
    "threading",
    "multiprocessing",
    "json",
    "pathlib",
    "platform",
    "subprocess",
    "shutil",
    # Pydantic for configuration
    "pydantic",
    "pydantic.dataclasses",
    "pydantic.json",
    "pydantic.types",
    "pydantic.validators",
]

# Platform-specific hidden imports
if IS_WINDOWS:
    HIDDEN_IMPORTS.extend(
        [
            "accessible_output3.outputs.sapi",
            "accessible_output3.outputs.nvda",
            "accessible_output3.outputs.jaws",
            "win32api",
            "win32con",
            "win32gui",
            "winsound",
        ]
    )
elif IS_MACOS:
    HIDDEN_IMPORTS.extend(
        [
            "accessible_output3.outputs.voiceover",
            "Foundation",
            "AppKit",
            "Cocoa",
        ]
    )
elif IS_LINUX:
    HIDDEN_IMPORTS.extend(
        [
            "accessible_output3.outputs.speechd",
        ]
    )

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
    hiddenimports=HIDDEN_IMPORTS,
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
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# PYZ (Python ZIP archive)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

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
    upx=True,
    console=True,  # Console mode for accessibility and debugging
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Platform-specific options
    icon=str(BASE_DIR / "assets" / "icons" / "openboard.ico") if IS_WINDOWS else None,
    version=None,  # TODO: Add version info file for Windows
)

# Bundle configuration (for macOS app bundle or Linux directory)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
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

# -*- mode: python ; coding: utf-8 -*-
"""
Main PyInstaller spec file for OpenBoard chess GUI.

This spec file imports and executes the detailed configuration from
.build/pyinstaller_spec.py to keep the main spec file clean.
"""

exec(open('./.build/pyinstaller_spec.py').read())
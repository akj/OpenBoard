"""
PyInstaller hook for blinker package.

This hook ensures that all blinker modules are properly included
for the signal-based MVC communication system.
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules

# Collect all blinker modules
datas, binaries, hiddenimports = collect_all("blinker")

# Ensure all submodules are included
hiddenimports += collect_submodules("blinker")

# Core blinker modules
hiddenimports += [
    "blinker.base",
]

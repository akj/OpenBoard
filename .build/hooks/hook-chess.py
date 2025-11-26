"""
PyInstaller hook for chess package.

This hook ensures that all chess library modules are properly
included, especially modules that might be dynamically imported.
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules

# Collect all chess modules
datas, binaries, hiddenimports = collect_all("chess")

# Ensure all submodules are included
hiddenimports += collect_submodules("chess")

# Core chess modules that might be dynamically imported
hiddenimports += [
    "chess.engine",
    "chess.polyglot",
    "chess.pgn",
    "chess.svg",
    "chess.syzygy",
    "chess.variant",
    "chess.gaviota",
]

# Include any chess data files (like piece sets, opening books)
# Note: Add actual chess data files here if the library includes them

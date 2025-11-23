"""
PyInstaller hook for OpenBoard package.

This hook ensures that all OpenBoard modules and their dependencies
are properly included in the built executable.
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules

# Collect all OpenBoard modules
datas, binaries, hiddenimports = collect_all('openboard')

# Ensure all submodules are included
hiddenimports += collect_submodules('openboard')

# Additional hidden imports for dynamically loaded modules
hiddenimports += [
    'openboard.views.views',
    'openboard.models.game',
    'openboard.models.board_state',
    'openboard.models.game_mode',
    'openboard.models.opening_book',
    'openboard.controllers.chess_controller',
    'openboard.engine.engine_adapter',
    'openboard.engine.engine_detection',
    'openboard.engine.stockfish_manager',
    'openboard.engine.downloader',
    'openboard.config.settings',
    'openboard.config.keyboard_config',
    'openboard.logging_config',
    'openboard.exceptions',
    'openboard.views.game_dialogs',
    'openboard.views.engine_dialogs',
]
"""
PyInstaller hook for accessible_output3 package.

This hook ensures that all accessible_output3 modules are properly
included, especially the platform-specific output modules that may
be dynamically imported at runtime.
"""

import platform
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Collect all accessible_output3 modules
datas, binaries, hiddenimports = collect_all('accessible_output3')

# Ensure all submodules are included
hiddenimports += collect_submodules('accessible_output3')

# Platform-specific screen reader modules
system = platform.system().lower()

# Core modules always needed
hiddenimports += [
    'accessible_output3.outputs',
    'accessible_output3.outputs.auto',
    'accessible_output3.outputs.base',
]

# Platform-specific screen reader support
if system == 'windows':
    hiddenimports += [
        'accessible_output3.outputs.sapi',
        'accessible_output3.outputs.nvda',
        'accessible_output3.outputs.jaws',
        'accessible_output3.outputs.window_eyes',
        'accessible_output3.outputs.system_access',
    ]
elif system == 'darwin':  # macOS
    hiddenimports += [
        'accessible_output3.outputs.voiceover',
    ]
elif system == 'linux':
    hiddenimports += [
        'accessible_output3.outputs.speechd',
        'accessible_output3.outputs.espeak',
    ]

# Generic fallback modules
hiddenimports += [
    'accessible_output3.outputs.dummy',
]
"""Include dynamically discovered speech backends and their native libraries."""

import importlib.util
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules


datas, binaries, hiddenimports = collect_all("accessible_output3")

if sys.platform == "linux":
    if importlib.util.find_spec("speechd") is None:
        raise RuntimeError(
            "Linux builds require python3-speechd. Install the system package and "
            "use a virtual environment with system-site-packages enabled."
        )
    hiddenimports += collect_submodules("speechd")
elif sys.platform == "darwin":
    hiddenimports += collect_submodules("appscript")
    hiddenimports += ["AppKit"]

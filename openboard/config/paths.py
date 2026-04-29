"""Platform-aware persistent file paths for OpenBoard.

All persistent files in OpenBoard resolve through this module. Tests can
override the resolution by setting OPENBOARD_PROFILE_DIR in the environment;
when set, every path is rooted under that directory.

Filename note (Phase 1, Codex HIGH): the canonical settings filename is
`config.json` — the legacy name is preserved in the new platformdirs location.
The rename to a different name is DEFERRED.
(TD-12 / D-09 / D-11)
"""

import os
from pathlib import Path

import platformdirs

from ..logging_config import get_logger

logger = get_logger(__name__)

APP_NAME = "openboard"
ENV_OVERRIDE = "OPENBOARD_PROFILE_DIR"


def _override_root() -> Path | None:
    """Return the override root from OPENBOARD_PROFILE_DIR, or None if not set."""
    value = os.environ.get(ENV_OVERRIDE)
    return Path(value) if value else None


def user_config_dir() -> Path:
    """Return the user config dir (e.g., ~/.config/openboard on Linux).

    Honors OPENBOARD_PROFILE_DIR for test isolation. The directory is created
    if it does not exist.
    (TD-12 / D-09)
    """
    override = _override_root()
    if override is not None:
        target_path = override / "config"
    else:
        target_path = Path(platformdirs.user_config_dir(APP_NAME))
    target_path.mkdir(parents=True, exist_ok=True)
    return target_path


def user_data_dir() -> Path:
    """Return the user data dir (e.g., ~/.local/share/openboard on Linux).

    Honors OPENBOARD_PROFILE_DIR for test isolation. The directory is created
    if it does not exist.
    (TD-12 / D-09)
    """
    override = _override_root()
    if override is not None:
        target_path = override / "data"
    else:
        target_path = Path(platformdirs.user_data_dir(APP_NAME))
    target_path.mkdir(parents=True, exist_ok=True)
    return target_path


def user_state_dir() -> Path:
    """Return the user state dir (e.g., ~/.local/state/openboard on Linux).

    Honors OPENBOARD_PROFILE_DIR for test isolation. The directory is created
    if it does not exist.
    (TD-12 / D-09)
    """
    override = _override_root()
    if override is not None:
        target_path = override / "state"
    else:
        target_path = Path(platformdirs.user_state_dir(APP_NAME))
    target_path.mkdir(parents=True, exist_ok=True)
    return target_path


def engines_dir() -> Path:
    """Return the engines install dir (under user_data_dir/engines).

    Note: this CREATES the directory eagerly via mkdir. The migration helper
    must NOT call this function before deciding whether to move a legacy
    engines/ directory — see <engines_dir_migration_policy> in 01-04-PLAN.md.
    (TD-12 / D-09 / D-11)
    """
    target_path = user_data_dir() / "engines"
    target_path.mkdir(parents=True, exist_ok=True)
    return target_path


def settings_path() -> Path:
    """Return the canonical settings file path.

    Filename: `config.json` — the legacy name is preserved in the new
    platformdirs location per Codex HIGH (no rename in Phase 1).
    (TD-12 / D-09)
    """
    return user_config_dir() / "config.json"


def keyboard_config_path() -> Path:
    """Return the canonical keyboard_config.json path.

    (TD-12 / D-09)
    """
    return user_config_dir() / "keyboard_config.json"


def autosave_path() -> Path:
    """Return the canonical autosave.json path (used by Phase 4b).

    (TD-12 / D-09)
    """
    return user_state_dir() / "autosave.json"

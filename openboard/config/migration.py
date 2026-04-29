"""One-shot migration of legacy cwd-relative files to platformdirs locations.

Called once at startup BEFORE the _settings singleton initialises, before any
code reads from cwd-relative paths. After migration, subsequent launches find
the new paths and skip the move.

Codex HIGH constraints (see <engines_dir_migration_policy> in 01-04-PLAN.md):
- The engines-dir branch is CONDITIONAL: it only computes / moves the destination
  when a legacy `engines/` directory actually exists in cwd. It does NOT call
  `paths.engines_dir()` (which would eagerly mkdir the destination, complicating
  the move).
- Idempotent: a second run on a fresh install creates NO directories and emits
  NO logs.
- Codex MEDIUM: cwd file copy is REMOVED after a successful move (natural
  shutil.move semantics on a file). Not backed up.

(TD-12 / D-10 / Pitfall 3 / Codex HIGH)
"""

import shutil
from pathlib import Path

from ..logging_config import get_logger
from . import paths

logger = get_logger(__name__)


def _migrate_file(legacy_path: Path, new_path: Path) -> None:
    """Move a single legacy file to its new location if conditions allow.

    Conditions:
    - legacy must exist
    - new must NOT exist (never clobber)
    On success, log INFO. On skip, silent.
    """
    if not legacy_path.exists():
        return
    if new_path.exists():
        return  # Never clobber.
    new_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy_path), str(new_path))
    logger.info(f"Migrated {legacy_path} -> {new_path}")


def _migrate_engines_dir() -> None:
    """Conditional move for the legacy engines/ directory (Codex HIGH).

    IMPORTANT: do NOT call paths.engines_dir() here — it would eagerly mkdir the
    destination and break the conditional semantics. Compute the destination
    manually using paths.user_data_dir() (which mkdirs only the data dir, NOT
    the engines/ subdir).
    (Codex HIGH / T-04-08)
    """
    legacy_engines = Path.cwd() / "engines"
    if not legacy_engines.exists():
        # Step 3 of the policy: directory will be created lazily on first download.
        return
    # Step 1: legacy exists — compute destination WITHOUT calling paths.engines_dir().
    destination = paths.user_data_dir() / "engines"
    if destination.exists():
        return  # Already migrated; idempotent.
    # Step 2: single shutil.move; ensure parent exists.
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(legacy_engines), str(destination))
    logger.info(f"Migrated {legacy_engines} -> {destination}")


def migrate_legacy_paths() -> None:
    """Migrate legacy cwd-relative files to platformdirs locations once.

    Files migrated:
    - config.json (settings) -> user_config_dir/config.json (filename preserved per Codex HIGH)
    - keyboard_config.json -> user_config_dir/keyboard_config.json
    - engines/ (directory) -> user_data_dir/engines/ — CONDITIONAL (Codex HIGH)

    Idempotent: if all legacy paths are absent OR all new paths already exist,
    the call is a silent no-op. Never overwrites an existing new file.
    (TD-12 / D-10)
    """
    # Files: simple conditional moves.
    _migrate_file(Path.cwd() / "config.json", paths.settings_path())
    _migrate_file(Path.cwd() / "keyboard_config.json", paths.keyboard_config_path())

    # Engines directory: conditional with no eager mkdir (Codex HIGH).
    _migrate_engines_dir()

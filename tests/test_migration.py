"""Tests for openboard/config/migration.py — TD-12 / D-10.

Covers (Codex MEDIUM/HIGH):
- config.json migration (canonical case)
- keyboard_config.json migration (NEW MUST-HAVE — Codex MEDIUM)
- engines-dir migration is CONDITIONAL: no eager mkdir if legacy absent (Codex HIGH)
- idempotency (second run is silent no-op)
- never overwrites existing new files
"""

import json
from pathlib import Path

import pytest


class TestLegacyConfigJsonMigration:
    """Verifies TD-12 / D-10: legacy config.json relocates."""

    def test_one_shot_migration_moves_legacy_config_json(
        self, isolated_profile: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies D-10: legacy config.json migrates to user_config_dir/config.json on first run.

        Codex HIGH: filename is preserved as config.json in the new location (no rename).
        """
        monkeypatch.chdir(isolated_profile)  # legacy lookups happen relative to cwd
        legacy_settings = isolated_profile / "config.json"
        legacy_settings.write_text(json.dumps({"announcement_mode": "verbose"}))

        from openboard.config import paths
        from openboard.config.migration import migrate_legacy_paths

        migrate_legacy_paths()

        assert not legacy_settings.exists(), "legacy config.json must be moved away"
        new_settings = paths.settings_path()
        assert new_settings.exists()
        assert new_settings.name == "config.json", "Codex HIGH: filename preserved"
        assert json.loads(new_settings.read_text()) == {"announcement_mode": "verbose"}


class TestLegacyKeyboardConfigJsonMigration:
    """Verifies TD-12 / D-10 / Codex MEDIUM new must-have: legacy keyboard_config.json relocates."""

    def test_one_shot_migration_moves_legacy_keyboard_config_json(
        self, isolated_profile: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies Codex MEDIUM: legacy keyboard_config.json migrates to user_config_dir/keyboard_config.json.

        Decision (per <engines_dir_migration_policy>): cwd copy is REMOVED after move
        (natural shutil.move semantics on a file). Not backed up.
        """
        monkeypatch.chdir(isolated_profile)
        legacy_keyboard = isolated_profile / "keyboard_config.json"
        legacy_keyboard.write_text(json.dumps({"version": "1.0", "bindings": []}))

        from openboard.config import paths
        from openboard.config.migration import migrate_legacy_paths

        migrate_legacy_paths()

        assert not legacy_keyboard.exists(), (
            "Codex MEDIUM: legacy keyboard_config.json must be REMOVED from cwd after move"
        )
        new_keyboard = paths.keyboard_config_path()
        assert new_keyboard.exists()
        assert new_keyboard.name == "keyboard_config.json"
        assert json.loads(new_keyboard.read_text()) == {"version": "1.0", "bindings": []}


class TestEnginesDirMigrationConditional:
    """Verifies TD-12 / D-10 / Codex HIGH: engines-dir migration is conditional."""

    def test_migration_engines_dir_conditional_when_legacy_absent(
        self, isolated_profile: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies Codex HIGH: when no legacy engines/ dir exists in cwd, migration creates NOTHING.

        Specifically: migrate_legacy_paths() must NOT eagerly call paths.engines_dir() and
        create an empty engines/ subdirectory. The directory is created lazily on first download.
        """
        monkeypatch.chdir(isolated_profile)
        assert not (isolated_profile / "engines").exists(), "test setup: no legacy engines/"

        from openboard.config.migration import migrate_legacy_paths

        migrate_legacy_paths()

        # The new engines dir must NOT exist yet — migration is no-op.
        new_engines = isolated_profile / "data" / "engines"
        assert not new_engines.exists(), (
            "Codex HIGH: migration must NOT eagerly create engines/ when no legacy dir exists. "
            f"Found {new_engines} after migration ran on a fresh profile."
        )

    def test_migration_engines_dir_moves_when_legacy_present(
        self, isolated_profile: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies Codex HIGH: when legacy engines/ exists, it is moved to user_data_dir/engines/."""
        monkeypatch.chdir(isolated_profile)
        legacy_engines = isolated_profile / "engines"
        legacy_engines.mkdir()
        (legacy_engines / "stockfish").write_bytes(b"fake stockfish binary")

        from openboard.config.migration import migrate_legacy_paths

        migrate_legacy_paths()

        assert not legacy_engines.exists(), "legacy engines/ must be moved away"
        new_engines = isolated_profile / "data" / "engines"
        assert new_engines.exists() and new_engines.is_dir()
        assert (new_engines / "stockfish").read_bytes() == b"fake stockfish binary"


class TestMigrationIdempotency:
    """Verifies TD-12 / D-10 / Codex HIGH: second run is a silent no-op."""

    def test_migration_idempotent(
        self, isolated_profile: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verifies Codex HIGH: a second run with no legacy files is a SILENT no-op.

        Acceptance: zero INFO logs containing 'Migrated', zero new directories created.
        """
        monkeypatch.chdir(isolated_profile)
        from openboard.config.migration import migrate_legacy_paths

        with caplog.at_level("INFO"):
            migrate_legacy_paths()  # first run, nothing to migrate
            migrate_legacy_paths()  # second run — must also be silent

        migrated_lines = [r for r in caplog.records if "Migrated" in r.message]
        assert migrated_lines == [], (
            f"Codex HIGH idempotent: second run must NOT log any 'Migrated' INFO. "
            f"Got: {[r.message for r in migrated_lines]}"
        )

        # Belt-and-suspenders: no extraneous engines/ directory should have been created.
        assert not (isolated_profile / "data" / "engines").exists(), (
            "Codex HIGH idempotent: idempotent run must not create engines/"
        )

    def test_migration_no_overwrite(
        self, isolated_profile: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verifies D-10: if both legacy and new paths exist, migration does NOT clobber the new file."""
        monkeypatch.chdir(isolated_profile)
        from openboard.config import paths
        from openboard.config.migration import migrate_legacy_paths

        # New path pre-exists
        new_settings = paths.settings_path()
        new_settings.parent.mkdir(parents=True, exist_ok=True)
        new_settings.write_text('{"new": true}')

        # Legacy path also exists
        legacy_settings = isolated_profile / "config.json"
        legacy_settings.write_text('{"legacy": true}')

        migrate_legacy_paths()

        assert legacy_settings.exists(), "legacy must NOT be moved when new already exists"
        assert json.loads(new_settings.read_text()) == {"new": True}, "new path must NOT be clobbered"

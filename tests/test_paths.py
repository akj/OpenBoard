"""Tests for openboard/config/paths.py — TD-12 / D-09."""

from pathlib import Path

import pytest


class TestPathsModule:
    """Verifies TD-12 / D-09: paths.py wrappers honor OPENBOARD_PROFILE_DIR."""

    def test_paths_resolve_under_override(self, isolated_profile: Path) -> None:
        """Verifies TD-12 / D-09: OPENBOARD_PROFILE_DIR routes every helper to a tmp_path subtree."""
        from openboard.config import paths

        assert paths.user_config_dir() == isolated_profile / "config"
        assert paths.user_data_dir() == isolated_profile / "data"
        assert paths.user_state_dir() == isolated_profile / "state"
        assert paths.engines_dir() == isolated_profile / "data" / "engines"
        assert paths.keyboard_config_path() == isolated_profile / "config" / "keyboard_config.json"
        assert paths.autosave_path() == isolated_profile / "state" / "autosave.json"

    def test_settings_path_uses_legacy_config_json_filename(self, isolated_profile: Path) -> None:
        """Verifies TD-12 / Codex HIGH: settings_path() returns config.json (legacy name preserved).

        Phase 1 explicitly preserves the legacy config.json filename in the new platformdirs
        location. Any rename is deferred to a later phase.
        See <filename_decision> in 01-04-PLAN.md.
        """
        from openboard.config import paths

        assert paths.settings_path() == isolated_profile / "config" / "config.json", (
            "TD-12 / Codex HIGH: settings_path() must return config.json in the new "
            "platformdirs location — the legacy filename is preserved in Phase 1."
        )
        # Belt-and-suspenders: the path object literally ends in 'config.json'.
        assert paths.settings_path().name == "config.json"

    def test_paths_directories_are_created(self, isolated_profile: Path) -> None:
        """Verifies TD-12 / D-09: helpers ensure the directory exists (mkdir parents=True, exist_ok=True)."""
        from openboard.config import paths

        config_dir = paths.user_config_dir()
        assert config_dir.exists() and config_dir.is_dir()

        data_dir = paths.user_data_dir()
        assert data_dir.exists() and data_dir.is_dir()

        engines = paths.engines_dir()
        assert engines.exists() and engines.is_dir()

    def test_paths_default_resolves_via_platformdirs(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Verifies TD-12 / D-09: without OPENBOARD_PROFILE_DIR, paths come from platformdirs."""
        monkeypatch.delenv("OPENBOARD_PROFILE_DIR", raising=False)
        import platformdirs

        from openboard.config import paths

        expected_config = Path(platformdirs.user_config_dir("openboard"))
        actual_config = paths.user_config_dir()
        assert actual_config == expected_config, (
            "TD-12: without OPENBOARD_PROFILE_DIR, user_config_dir must equal platformdirs.user_config_dir('openboard')"
        )

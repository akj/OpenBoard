"""Tests for the settings configuration system."""

import pytest
from pathlib import Path

from openboard.config.settings import (
    Settings,
    UISettings,
    EngineSettings,
    get_settings,
    set_settings,
)


def test_ui_settings_default():
    """Test UISettings with default values."""
    ui = UISettings()

    assert ui.square_size == 60
    assert ui.board_size == 480  # 8 * 60
    assert ui.announcement_mode == "brief"
    assert "P" in ui.piece_unicode
    assert ui.piece_unicode["P"] == "♙"


def test_ui_settings_validation():
    """Test UISettings validation."""
    # Test valid settings
    ui = UISettings(square_size=50, announcement_mode="verbose")
    settings = Settings(ui=ui)
    settings.validate()  # Should not raise

    # Test invalid square size
    ui_bad = UISettings(square_size=-10)
    settings_bad = Settings(ui=ui_bad)
    with pytest.raises(ValueError, match="square_size must be positive"):
        settings_bad.validate()

    # Test invalid announcement mode
    ui_bad2 = UISettings(announcement_mode="invalid")
    settings_bad2 = Settings(ui=ui_bad2)
    with pytest.raises(ValueError, match="announcement_mode must be"):
        settings_bad2.validate()


def test_engine_settings_default():
    """Test EngineSettings with default values."""
    from openboard.config import paths

    engine = EngineSettings()

    assert engine.default_timeout_ms == 30000
    # TD-12 / D-11: engines_dir now resolves via paths.engines_dir(), not Path.cwd().
    assert engine.engines_dir == paths.engines_dir()
    assert engine.stockfish_dir == paths.engines_dir() / "stockfish" / "bin"
    assert len(engine.search_paths) > 0


def test_engine_settings_validation():
    """Test EngineSettings validation."""
    # Test invalid timeout
    engine_bad = EngineSettings(default_timeout_ms=-1000)
    settings_bad = Settings(engine=engine_bad)
    with pytest.raises(ValueError, match="default_timeout_ms must be positive"):
        settings_bad.validate()


def test_settings_global_instance():
    """Test global settings instance management."""
    # Get default settings
    settings1 = get_settings()
    settings2 = get_settings()

    # Should be the same instance
    assert settings1 is settings2

    # Test setting new settings
    new_settings = Settings()
    new_settings.ui.square_size = 80
    set_settings(new_settings)

    retrieved = get_settings()
    assert retrieved.ui.square_size == 80


def test_settings_platform_paths():
    """Test that platform-specific paths are generated."""
    engine = EngineSettings()

    # Should have platform-specific paths
    assert len(engine.search_paths) > 0

    # All paths should be Path objects
    for path in engine.search_paths:
        assert isinstance(path, Path)


class TestEnginesDirViaPaths:
    """Verifies TD-12 / D-11: EngineSettings.engines_dir routes through paths.engines_dir()."""

    def test_engines_dir_resolves_via_paths(self, isolated_profile: Path) -> None:
        """Verifies D-11: a fresh EngineSettings yields paths.engines_dir() — no Path.cwd() leak."""
        from openboard.config import paths
        from openboard.config.settings import EngineSettings

        settings = EngineSettings()
        assert settings.engines_dir == paths.engines_dir(), (
            f"TD-12 / D-11: engines_dir must equal paths.engines_dir(); got {settings.engines_dir}"
        )
        # Sanity: should be under the isolated profile, NOT the cwd
        assert isolated_profile in settings.engines_dir.parents

"""Configuration management for OpenBoard application."""

import platform
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class UISettings:
    """UI configuration settings."""

    square_size: int = 60
    piece_unicode: dict[str, str] = field(default_factory=dict)
    announcement_mode: str = "brief"  # "brief" | "verbose"

    def __post_init__(self):
        """Initialize default values that require computation."""
        if not self.piece_unicode:
            self.piece_unicode = {
                "P": "♙",
                "N": "♘",
                "B": "♗",
                "R": "♖",
                "Q": "♕",
                "K": "♔",
                "p": "♟",
                "n": "♞",
                "b": "♝",
                "r": "♜",
                "q": "♛",
                "k": "♚",
            }

    @property
    def board_size(self) -> int:
        """Calculate total board size in pixels."""
        return 8 * self.square_size


@dataclass
class EngineSettings:
    """Engine configuration settings."""

    engines_dir: Path = field(default_factory=lambda: Path.cwd() / "engines")
    default_timeout_ms: int = 30000
    search_paths: list[Path] = field(default_factory=list)

    def __post_init__(self):
        """Initialize platform-specific search paths if not provided."""
        if not self.search_paths:
            self.search_paths = self._get_default_search_paths()

    def _get_default_search_paths(self) -> list[Path]:
        """Get platform-specific search paths for engines."""
        system = platform.system().lower()

        match system:
            case "linux":
                return [
                    Path("/usr/bin"),
                    Path("/usr/local/bin"),
                    Path("/opt/stockfish/bin"),
                    Path.home() / ".local" / "bin",
                ]
            case "darwin":  # macOS
                return [
                    Path("/usr/local/bin"),
                    Path("/opt/homebrew/bin"),
                    Path("/usr/bin"),
                    Path.home() / "Applications" / "Stockfish",
                ]
            case "windows":
                return [
                    Path("C:/Program Files/Stockfish"),
                    Path("C:/Program Files (x86)/Stockfish"),
                    Path("C:/stockfish"),
                    Path.home() / "AppData" / "Local" / "Stockfish",
                ]
            case _:
                return []

    @property
    def stockfish_dir(self) -> Path:
        """Get the local Stockfish installation directory."""
        return self.engines_dir / "stockfish" / "bin"


@dataclass
class Settings:
    """Application settings container."""

    ui: UISettings = field(default_factory=UISettings)
    engine: EngineSettings = field(default_factory=EngineSettings)

    @classmethod
    def default(cls) -> "Settings":
        """Create settings with default values."""
        return cls()

    def validate(self) -> None:
        """Validate all settings."""
        if self.ui.square_size <= 0:
            raise ValueError("UI square_size must be positive")

        if self.ui.announcement_mode not in ["brief", "verbose"]:
            raise ValueError("UI announcement_mode must be 'brief' or 'verbose'")

        if self.engine.default_timeout_ms <= 0:
            raise ValueError("Engine default_timeout_ms must be positive")


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.default()
        _settings.validate()
    return _settings


def set_settings(settings: Settings) -> None:
    """Set the global settings instance."""
    global _settings
    settings.validate()
    _settings = settings

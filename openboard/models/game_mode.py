"""Game mode definitions and configuration."""

from enum import StrEnum
from dataclasses import dataclass, field
import chess

from ..exceptions import GameModeError


class GameMode(StrEnum):
    """Supported game modes."""

    HUMAN_VS_HUMAN = "human_vs_human"
    HUMAN_VS_COMPUTER = "human_vs_computer"
    COMPUTER_VS_COMPUTER = "computer_vs_computer"


class DifficultyLevel(StrEnum):
    """Difficulty levels for computer opponent."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    MASTER = "master"


@dataclass
class DifficultyConfig:
    """Configuration for a difficulty level."""

    name: str
    description: str
    time_ms: int = field(
        metadata={"min": 1, "max": 30000}
    )  # Thinking time in milliseconds
    depth: int | None = field(
        default=None, metadata={"min": 1, "max": 20}
    )  # Search depth (None for time-based only)

    def __post_init__(self):
        """Validate configuration values."""
        if self.time_ms < 1 or self.time_ms > 30000:
            raise ValueError(f"time_ms must be between 1 and 30000, got {self.time_ms}")
        if self.depth is not None and (self.depth < 1 or self.depth > 20):
            raise ValueError(f"depth must be between 1 and 20, got {self.depth}")


@dataclass
class GameConfig:
    """Configuration for a game session."""

    mode: GameMode
    human_color: chess.Color = chess.WHITE
    difficulty: DifficultyLevel | None = None
    white_difficulty: DifficultyLevel | None = None
    black_difficulty: DifficultyLevel | None = None

    @property
    def requires_engine(self) -> bool:
        """Check if this configuration requires an engine."""
        return self.mode in [GameMode.HUMAN_VS_COMPUTER, GameMode.COMPUTER_VS_COMPUTER]

    def __post_init__(self):
        """Validate configuration."""
        if self.mode == GameMode.HUMAN_VS_COMPUTER and self.difficulty is None:
            raise GameModeError(
                "Difficulty must be specified for human vs computer mode"
            )
        elif self.mode == GameMode.COMPUTER_VS_COMPUTER:
            if self.white_difficulty is None or self.black_difficulty is None:
                raise GameModeError(
                    "Both white_difficulty and black_difficulty must be specified for computer vs computer mode"
                )


# Difficulty level configurations
DIFFICULTY_CONFIGS = {
    DifficultyLevel.BEGINNER: DifficultyConfig(
        name="Beginner",
        description="Easy opponent, good for learning",
        time_ms=150,
        depth=2,
    ),
    DifficultyLevel.INTERMEDIATE: DifficultyConfig(
        name="Intermediate", description="Moderate challenge", time_ms=500, depth=4
    ),
    DifficultyLevel.ADVANCED: DifficultyConfig(
        name="Advanced", description="Strong opponent", time_ms=1500, depth=6
    ),
    DifficultyLevel.MASTER: DifficultyConfig(
        name="Master", description="Very strong opponent", time_ms=5000, depth=10
    ),
}


def get_difficulty_config(level: DifficultyLevel) -> DifficultyConfig:
    """Get configuration for a difficulty level."""
    return DIFFICULTY_CONFIGS[level]


def get_computer_color(human_color: chess.Color) -> chess.Color:
    """Get the computer's color based on human's choice."""
    return not human_color

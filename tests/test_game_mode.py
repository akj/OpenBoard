"""Tests for game mode functionality."""

import pytest
import chess
from unittest.mock import Mock

from openboard.models.game import Game
from openboard.models.game_mode import (
    GameMode, GameConfig, DifficultyLevel, 
    get_difficulty_config, get_computer_color,
    DIFFICULTY_CONFIGS
)
from openboard.engine.engine_adapter import EngineAdapter


def test_game_mode_enum():
    """Test GameMode enum values."""
    assert GameMode.HUMAN_VS_HUMAN.value == "human_vs_human"
    assert GameMode.HUMAN_VS_COMPUTER.value == "human_vs_computer"


def test_difficulty_level_enum():
    """Test DifficultyLevel enum values."""
    assert DifficultyLevel.BEGINNER.value == "beginner"
    assert DifficultyLevel.INTERMEDIATE.value == "intermediate"
    assert DifficultyLevel.ADVANCED.value == "advanced"
    assert DifficultyLevel.MASTER.value == "master"


def test_game_config_human_vs_human():
    """Test GameConfig for human vs human mode."""
    config = GameConfig(mode=GameMode.HUMAN_VS_HUMAN)
    assert config.mode == GameMode.HUMAN_VS_HUMAN
    assert config.human_color == chess.WHITE
    assert config.difficulty is None


def test_game_config_human_vs_computer():
    """Test GameConfig for human vs computer mode."""
    config = GameConfig(
        mode=GameMode.HUMAN_VS_COMPUTER,
        human_color=chess.BLACK,
        difficulty=DifficultyLevel.INTERMEDIATE
    )
    assert config.mode == GameMode.HUMAN_VS_COMPUTER
    assert config.human_color == chess.BLACK
    assert config.difficulty == DifficultyLevel.INTERMEDIATE


def test_game_config_validation():
    """Test GameConfig validation."""
    # Should raise error if human vs computer without difficulty
    with pytest.raises(ValueError, match="Difficulty must be specified"):
        GameConfig(mode=GameMode.HUMAN_VS_COMPUTER)


def test_get_computer_color():
    """Test get_computer_color function."""
    assert get_computer_color(chess.WHITE) == chess.BLACK
    assert get_computer_color(chess.BLACK) == chess.WHITE


def test_get_difficulty_config():
    """Test get_difficulty_config function."""
    config = get_difficulty_config(DifficultyLevel.BEGINNER)
    assert config.name == "Beginner"
    assert config.time_ms == 100
    assert config.depth == 1


def test_difficulty_configs_complete():
    """Test that all difficulty levels have configurations."""
    for level in DifficultyLevel:
        config = DIFFICULTY_CONFIGS[level]
        assert config.name
        assert config.description
        assert config.time_ms > 0


def test_game_initialization_human_vs_human():
    """Test Game initialization in human vs human mode."""
    config = GameConfig(mode=GameMode.HUMAN_VS_HUMAN)
    game = Game(config=config)
    
    assert game.config.mode == GameMode.HUMAN_VS_HUMAN
    assert game.computer_color is None


def test_game_initialization_human_vs_computer():
    """Test Game initialization in human vs computer mode."""
    config = GameConfig(
        mode=GameMode.HUMAN_VS_COMPUTER,
        human_color=chess.WHITE,
        difficulty=DifficultyLevel.BEGINNER
    )
    game = Game(config=config)
    
    assert game.config.mode == GameMode.HUMAN_VS_COMPUTER
    assert game.computer_color == chess.BLACK


def test_game_is_computer_turn():
    """Test is_computer_turn method."""
    config = GameConfig(
        mode=GameMode.HUMAN_VS_COMPUTER,
        human_color=chess.WHITE,
        difficulty=DifficultyLevel.BEGINNER
    )
    game = Game(config=config)
    
    # White (human) moves first
    assert not game.is_computer_turn()
    
    # After human move, it's computer's turn
    game.apply_move(chess.E2, chess.E4)
    assert game.is_computer_turn()


def test_game_is_computer_turn_human_vs_human():
    """Test is_computer_turn returns False in human vs human mode."""
    config = GameConfig(mode=GameMode.HUMAN_VS_HUMAN)
    game = Game(config=config)
    
    assert not game.is_computer_turn()
    game.apply_move(chess.E2, chess.E4)
    assert not game.is_computer_turn()


def test_game_request_computer_move_no_engine():
    """Test request_computer_move without engine raises error."""
    config = GameConfig(
        mode=GameMode.HUMAN_VS_COMPUTER,
        human_color=chess.WHITE,
        difficulty=DifficultyLevel.BEGINNER
    )
    game = Game(config=config)  # No engine
    
    with pytest.raises(RuntimeError, match="No chess engine available"):
        game.request_computer_move()


def test_game_request_computer_move_wrong_mode():
    """Test request_computer_move in wrong mode raises error."""
    config = GameConfig(mode=GameMode.HUMAN_VS_HUMAN)
    game = Game(config=config)
    
    with pytest.raises(RuntimeError, match="Not in a computer vs mode"):
        game.request_computer_move()


def test_game_request_computer_move_success():
    """Test successful computer move request."""
    # Mock engine
    mock_engine = Mock(spec=EngineAdapter)
    mock_engine.get_best_move.return_value = chess.Move.from_uci("e7e5")
    
    config = GameConfig(
        mode=GameMode.HUMAN_VS_COMPUTER,
        human_color=chess.WHITE,
        difficulty=DifficultyLevel.BEGINNER
    )
    game = Game(engine_adapter=mock_engine, config=config)
    
    # Make human move first
    game.apply_move(chess.E2, chess.E4)
    
    # Request computer move
    move = game.request_computer_move()
    
    assert move == chess.Move.from_uci("e7e5")
    mock_engine.get_best_move.assert_called_once()
    
    # Check that difficulty time and depth were used
    call_args = mock_engine.get_best_move.call_args
    difficulty_config = get_difficulty_config(DifficultyLevel.BEGINNER)
    # call_args is (args, kwargs), we want the second and third positional arguments
    assert call_args[0][1] == difficulty_config.time_ms
    assert call_args[0][2] == difficulty_config.depth


def test_game_new_game_with_config():
    """Test new_game method with configuration."""
    game = Game()
    
    config = GameConfig(
        mode=GameMode.HUMAN_VS_COMPUTER,
        human_color=chess.BLACK,
        difficulty=DifficultyLevel.ADVANCED
    )
    
    game.new_game(config)
    
    assert game.config == config
    assert game.computer_color == chess.WHITE
    assert game.player_color == chess.BLACK  # Backward compatibility


def test_computer_vs_computer_config():
    """Test computer vs computer game configuration."""
    config = GameConfig(
        mode=GameMode.COMPUTER_VS_COMPUTER,
        white_difficulty=DifficultyLevel.BEGINNER,
        black_difficulty=DifficultyLevel.ADVANCED
    )
    
    assert config.mode == GameMode.COMPUTER_VS_COMPUTER
    assert config.white_difficulty == DifficultyLevel.BEGINNER
    assert config.black_difficulty == DifficultyLevel.ADVANCED


def test_computer_vs_computer_config_validation():
    """Test computer vs computer config validation."""
    # Missing white difficulty
    with pytest.raises(ValueError, match="Both white_difficulty and black_difficulty must be specified"):
        GameConfig(
            mode=GameMode.COMPUTER_VS_COMPUTER,
            black_difficulty=DifficultyLevel.INTERMEDIATE
        )
    
    # Missing black difficulty
    with pytest.raises(ValueError, match="Both white_difficulty and black_difficulty must be specified"):
        GameConfig(
            mode=GameMode.COMPUTER_VS_COMPUTER,
            white_difficulty=DifficultyLevel.INTERMEDIATE
        )


def test_computer_vs_computer_is_computer_turn():
    """Test is_computer_turn for computer vs computer mode."""
    config = GameConfig(
        mode=GameMode.COMPUTER_VS_COMPUTER,
        white_difficulty=DifficultyLevel.BEGINNER,
        black_difficulty=DifficultyLevel.ADVANCED
    )
    game = Game(config=config)
    
    # Should always be computer turn in computer vs computer mode
    assert game.is_computer_turn()


def test_computer_vs_computer_move_white():
    """Test computer move for white in computer vs computer mode."""
    mock_engine = Mock(spec=EngineAdapter)
    mock_engine.get_best_move.return_value = chess.Move.from_uci("e2e4")
    
    config = GameConfig(
        mode=GameMode.COMPUTER_VS_COMPUTER,
        white_difficulty=DifficultyLevel.BEGINNER,
        black_difficulty=DifficultyLevel.ADVANCED
    )
    game = Game(engine_adapter=mock_engine, config=config)
    
    # Request white's first move
    move = game.request_computer_move()
    
    assert move == chess.Move.from_uci("e2e4")
    # Should use white difficulty (BEGINNER = 150ms, depth=2)
    difficulty_config = get_difficulty_config(DifficultyLevel.BEGINNER)
    call_args = mock_engine.get_best_move.call_args
    assert call_args[0][1] == difficulty_config.time_ms
    assert call_args[0][2] == difficulty_config.depth


def test_computer_vs_computer_move_black():
    """Test computer move for black in computer vs computer mode."""
    mock_engine = Mock(spec=EngineAdapter)
    mock_engine.get_best_move.return_value = chess.Move.from_uci("e7e5")
    
    config = GameConfig(
        mode=GameMode.COMPUTER_VS_COMPUTER,
        white_difficulty=DifficultyLevel.BEGINNER,
        black_difficulty=DifficultyLevel.ADVANCED
    )
    game = Game(engine_adapter=mock_engine, config=config)
    
    # Make white's move first
    game.apply_move(chess.E2, chess.E4)
    
    # Request black's move
    move = game.request_computer_move()
    
    assert move == chess.Move.from_uci("e7e5")
    # Should use black difficulty (ADVANCED = 1500ms, depth=6)
    difficulty_config = get_difficulty_config(DifficultyLevel.ADVANCED)
    call_args = mock_engine.get_best_move.call_args
    assert call_args[0][1] == difficulty_config.time_ms
    assert call_args[0][2] == difficulty_config.depth
"""Tests for the exception hierarchy."""

import pytest

from openboard.exceptions import (
    OpenBoardError,
    ConfigurationError,
    GameModeError,
    EngineError,
    EngineNotFoundError,
    EngineInitializationError,
    EngineTimeoutError,
    EngineProcessError,
    GameError,
    IllegalMoveError,
    GameStateError,
    UIError,
    DialogError,
    AccessibilityError,
    SettingsError,
    NetworkError,
    DownloadError,
)


def test_exception_hierarchy():
    """Test that exception hierarchy is correctly structured."""
    # Test base exception
    assert issubclass(OpenBoardError, Exception)

    # Test configuration errors
    assert issubclass(ConfigurationError, OpenBoardError)
    assert issubclass(GameModeError, ConfigurationError)
    assert issubclass(SettingsError, ConfigurationError)

    # Test engine errors
    assert issubclass(EngineError, OpenBoardError)
    assert issubclass(EngineNotFoundError, EngineError)
    assert issubclass(EngineInitializationError, EngineError)
    assert issubclass(EngineTimeoutError, EngineError)
    assert issubclass(EngineProcessError, EngineError)

    # Test game errors
    assert issubclass(GameError, OpenBoardError)
    assert issubclass(IllegalMoveError, GameError)
    assert issubclass(GameStateError, GameError)

    # Test UI errors
    assert issubclass(UIError, OpenBoardError)
    assert issubclass(DialogError, UIError)
    assert issubclass(AccessibilityError, UIError)

    # Test network errors
    assert issubclass(NetworkError, OpenBoardError)
    assert issubclass(DownloadError, NetworkError)


def test_openboard_error_basic():
    """Test basic OpenBoardError functionality."""
    error = OpenBoardError("Test message")
    assert str(error) == "Test message"
    assert error.message == "Test message"
    assert error.details is None


def test_openboard_error_with_details():
    """Test OpenBoardError with details."""
    error = OpenBoardError("Test message", "Additional details")
    assert str(error) == "Test message: Additional details"
    assert error.message == "Test message"
    assert error.details == "Additional details"


def test_engine_not_found_error():
    """Test EngineNotFoundError with engine name and paths."""
    error = EngineNotFoundError("Stockfish", ["/usr/bin", "/usr/local/bin"])
    assert "Stockfish not found" in str(error)
    assert "Searched in: /usr/bin, /usr/local/bin" in str(error)
    assert error.engine_name == "Stockfish"
    assert error.search_paths == ["/usr/bin", "/usr/local/bin"]


def test_engine_timeout_error():
    """Test EngineTimeoutError with operation and timeout."""
    error = EngineTimeoutError("move calculation", 5000)
    assert str(error) == "Engine move calculation timed out after 5000ms"
    assert error.operation == "move calculation"
    assert error.timeout_ms == 5000


def test_engine_process_error():
    """Test EngineProcessError with return code and stderr."""
    error = EngineProcessError("Process failed", return_code=1, stderr="Error output")
    assert "Process failed" in str(error)
    assert "exit code: 1" in str(error)
    assert "stderr: Error output" in str(error)
    assert error.return_code == 1
    assert error.stderr == "Error output"


def test_illegal_move_error():
    """Test IllegalMoveError with move and position."""
    error = IllegalMoveError(
        "e2e5", "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    )
    assert "Illegal move: e2e5" in str(error)
    assert "in position:" in str(error)
    assert error.move == "e2e5"
    assert (
        error.position_fen == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    )


def test_download_error():
    """Test DownloadError with URL and reason."""
    error = DownloadError("https://example.com/file.zip", "Connection timeout")
    assert "Failed to download from https://example.com/file.zip" in str(error)
    assert "Connection timeout" in str(error)
    assert error.url == "https://example.com/file.zip"
    assert error.reason == "Connection timeout"


def test_exception_catching():
    """Test that specific exceptions can be caught as base types."""
    # Test that EngineNotFoundError can be caught as EngineError
    with pytest.raises(EngineError):
        raise EngineNotFoundError("test")

    # Test that EngineError can be caught as OpenBoardError
    with pytest.raises(OpenBoardError):
        raise EngineError("test")

    # Test that GameModeError can be caught as ConfigurationError
    with pytest.raises(ConfigurationError):
        raise GameModeError("test")


def test_inheritance_chain():
    """Test complete inheritance chain for key exceptions."""
    error = EngineNotFoundError("test")

    # Should be instance of all parent classes
    assert isinstance(error, EngineNotFoundError)
    assert isinstance(error, EngineError)
    assert isinstance(error, OpenBoardError)
    assert isinstance(error, Exception)

    # Test with IllegalMoveError
    move_error = IllegalMoveError("e2e5")
    assert isinstance(move_error, IllegalMoveError)
    assert isinstance(move_error, GameError)
    assert isinstance(move_error, OpenBoardError)
    assert isinstance(move_error, Exception)

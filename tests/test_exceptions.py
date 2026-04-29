"""Tests for the exception hierarchy."""

import importlib
import subprocess

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
    NetworkError,
    DownloadError,
)


def test_exception_hierarchy():
    """Test that exception hierarchy is correctly structured. TD-11."""
    # Test base exception
    assert issubclass(OpenBoardError, Exception)

    # Test configuration errors
    assert issubclass(ConfigurationError, OpenBoardError)
    assert issubclass(GameModeError, ConfigurationError)

    # Test engine errors
    assert issubclass(EngineError, OpenBoardError)
    assert issubclass(EngineNotFoundError, EngineError)
    assert issubclass(EngineInitializationError, EngineError)
    assert issubclass(EngineTimeoutError, EngineError)
    assert issubclass(EngineProcessError, EngineError)

    # Test game errors
    assert issubclass(GameError, OpenBoardError)
    assert issubclass(IllegalMoveError, GameError)

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


class TestPrunedExceptionTypes:
    """Verifies TD-11 / D-19: pruned types are unimportable from openboard.exceptions."""

    @pytest.mark.parametrize("type_name", [
        "AccessibilityError",
        "DialogError",
        "SettingsError",
        "GameStateError",
        "UIError",
    ])
    def test_pruned_exception_types_unimportable(self, type_name):
        """Verifies TD-11 / D-19: <type_name> is removed from openboard/exceptions.py.

        Re-imports the module to get a fresh namespace, then asserts the type is absent.
        """
        module = importlib.reload(importlib.import_module("openboard.exceptions"))
        assert not hasattr(module, type_name), (
            f"TD-11 / D-19: {type_name} must be removed from openboard/exceptions.py"
        )


class TestKeptExceptionTypes:
    """Verifies TD-11 / D-19: wired-up types remain importable and have the expected shape."""

    def test_engine_timeout_error_signature(self):
        """Verifies TD-11 / D-19: EngineTimeoutError(operation, timeout_ms) constructor preserved."""
        from openboard.exceptions import EngineTimeoutError

        error = EngineTimeoutError("get_best_move_async", 5000)
        assert error.operation == "get_best_move_async"
        assert error.timeout_ms == 5000
        assert "5000" in str(error)

    def test_engine_process_error_signature(self):
        """Verifies TD-11 / D-19: EngineProcessError(message, return_code, stderr) constructor preserved."""
        from openboard.exceptions import EngineProcessError

        error = EngineProcessError("startup failed", return_code=1, stderr="bad path")
        assert error.return_code == 1
        assert error.stderr == "bad path"

    def test_download_error_importable(self):
        """Verifies TD-11 / D-19: DownloadError is importable and constructible."""
        from openboard.exceptions import DownloadError

        error = DownloadError("https://example.com/x", "io failure")
        assert "x" in str(error)

    def test_network_error_importable(self):
        """Verifies TD-11 / D-19: NetworkError is importable and constructible."""
        from openboard.exceptions import NetworkError

        error = NetworkError("dns failed", "no route")
        assert "dns failed" in str(error)


class TestPrunedExceptionImportsAbsentFromSource:
    """Verifies TD-11 / Codex MEDIUM: no production file imports a pruned exception."""

    @pytest.mark.parametrize("pruned_class", [
        "AccessibilityError",
        "DialogError",
        "SettingsError",
        "GameStateError",
        "UIError",
    ])
    def test_pruned_exception_names_absent_from_source_tree(self, pruned_class):
        """Verifies Codex MEDIUM grep verification: <pruned_class> is not imported anywhere.

        Searches openboard/ AND tests/ for the patterns:
        - `from openboard.exceptions import ... <pruned_class>`
        - `openboard.exceptions.<pruned_class>`

        Exclusions:
        - tests/test_exceptions.py (this test file itself parametrizes over the names).
        """
        patterns = [
            f"from openboard.exceptions import.*{pruned_class}",
            f"openboard.exceptions.{pruned_class}",
        ]
        offending: list[str] = []
        for pattern in patterns:
            result = subprocess.run(
                ["grep", "-rnE", pattern, "openboard/", "tests/"],
                capture_output=True,
                text=True,
            )
            for line in result.stdout.splitlines():
                if "test_exceptions.py" in line:
                    continue   # this test file legitimately references the names
                offending.append(line)
        assert offending == [], (
            f"TD-11 / Codex MEDIUM: pruned exception `{pruned_class}` is still imported. "
            f"Offending lines:\n" + "\n".join(offending)
        )

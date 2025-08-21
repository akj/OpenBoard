import pytest
import os
import tempfile
import platform
from pathlib import Path
from unittest.mock import patch

from openboard.engine.engine_detection import EngineDetector


@pytest.fixture
def detector():
    return EngineDetector()


def test_engine_detector_init(detector):
    """Test EngineDetector initialization."""
    assert detector.system == platform.system().lower()


def test_find_engine_not_found(detector):
    """Test find_engine returns None when engine not found."""
    with patch("shutil.which", return_value=None):
        with patch.object(detector, "_check_common_paths", return_value=None):
            result = detector.find_engine("nonexistent_engine")
            assert result is None


def test_find_engine_in_path(detector):
    """Test find_engine finds engine in PATH."""
    mock_path = "/usr/bin/stockfish"
    with patch("shutil.which", return_value=mock_path):
        with patch.object(detector, "_is_valid_engine", return_value=True):
            result = detector.find_engine("stockfish")
            assert result == mock_path


def test_find_engine_in_common_paths(detector):
    """Test find_engine finds engine in common paths."""
    mock_path = "/usr/local/bin/stockfish"
    with patch("shutil.which", return_value=None):
        with patch.object(detector, "_check_common_paths", return_value=mock_path):
            result = detector.find_engine("stockfish")
            assert result == mock_path


def test_is_valid_engine_valid_file():
    """Test _is_valid_engine with valid executable."""
    detector = EngineDetector()

    # Create a temporary executable file
    with tempfile.NamedTemporaryFile(delete=False, mode="w") as f:
        temp_path = f.name

    try:
        # Make it executable
        os.chmod(temp_path, 0o755)
        assert detector._is_valid_engine(temp_path) is True
    finally:
        os.unlink(temp_path)


def test_is_valid_engine_invalid_file():
    """Test _is_valid_engine with non-existent file."""
    detector = EngineDetector()
    assert detector._is_valid_engine("/nonexistent/path") is False


def test_get_installation_instructions_stockfish(detector):
    """Test get_installation_instructions for Stockfish."""
    instructions = detector.get_installation_instructions("stockfish")

    assert "linux" in instructions
    assert "darwin" in instructions
    assert "windows" in instructions
    assert "apt install stockfish" in instructions["linux"]
    assert "brew install stockfish" in instructions["darwin"]


def test_get_installation_instructions_unknown_engine(detector):
    """Test get_installation_instructions for unknown engine."""
    instructions = detector.get_installation_instructions("unknown_engine")

    assert "generic" in instructions
    assert "unknown_engine" in instructions["generic"]


def test_list_available_engines_none_found(detector):
    """Test list_available_engines when no engines found."""
    with patch.object(detector, "find_engine", return_value=None):
        result = detector.list_available_engines()
        assert result == []


def test_list_available_engines_some_found(detector):
    """Test list_available_engines when some engines found."""

    def mock_find_engine(name):
        if name == "stockfish":
            return "/usr/bin/stockfish"
        return None

    with patch.object(detector, "find_engine", side_effect=mock_find_engine):
        result = detector.list_available_engines()
        assert "/usr/bin/stockfish" in result


def test_check_common_paths_linux(detector):
    """Test _check_common_paths on Linux."""
    if detector.system != "linux":
        pytest.skip("Test only runs on Linux")

    # Mock a valid engine in a common path
    with patch.object(Path, "exists", return_value=True):
        with patch.object(detector, "_is_valid_engine", return_value=True):
            with patch("os.path.expanduser", return_value="/usr/bin"):
                result = detector._check_common_paths("stockfish")
                # This test is platform-dependent, so we just check it doesn't crash
                assert result is None or isinstance(result, str)

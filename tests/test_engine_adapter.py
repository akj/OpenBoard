import pytest
from unittest.mock import patch, MagicMock

from openboard.engine.engine_adapter import EngineAdapter


def test_engine_adapter_auto_detection_success():
    """Test EngineAdapter with successful auto-detection."""
    mock_path = "/usr/bin/stockfish"

    with patch("openboard.engine.engine_adapter.EngineDetector") as mock_detector_class:
        mock_detector = MagicMock()
        mock_detector.find_engine.return_value = mock_path
        mock_detector_class.return_value = mock_detector

        adapter = EngineAdapter()
        assert adapter.engine_path == mock_path
        mock_detector.find_engine.assert_called_once_with("stockfish")


def test_engine_adapter_auto_detection_failure():
    """Test EngineAdapter when auto-detection fails."""
    with patch("openboard.engine.engine_adapter.EngineDetector") as mock_detector_class:
        mock_detector = MagicMock()
        mock_detector.find_engine.return_value = None
        mock_detector.system = "linux"
        mock_detector.get_installation_instructions.return_value = {
            "linux": "Install instructions here"
        }
        mock_detector_class.return_value = mock_detector

        with pytest.raises(RuntimeError, match="No Stockfish engine found"):
            EngineAdapter()


def test_engine_adapter_explicit_path():
    """Test EngineAdapter with explicit engine path."""
    explicit_path = "/custom/path/to/stockfish"
    adapter = EngineAdapter(engine_path=explicit_path)
    assert adapter.engine_path == explicit_path


def test_create_with_auto_detection_success():
    """Test create_with_auto_detection class method success."""
    mock_path = "/usr/bin/stockfish"

    with patch("openboard.engine.engine_adapter.EngineDetector") as mock_detector_class:
        mock_detector = MagicMock()
        mock_detector.find_engine.return_value = mock_path
        mock_detector_class.return_value = mock_detector

        adapter = EngineAdapter.create_with_auto_detection("stockfish", {"Threads": 4})
        assert adapter.engine_path == mock_path
        assert adapter.options == {"Threads": 4}


def test_create_with_auto_detection_failure():
    """Test create_with_auto_detection class method failure."""
    with patch("openboard.engine.engine_adapter.EngineDetector") as mock_detector_class:
        mock_detector = MagicMock()
        mock_detector.find_engine.return_value = None
        mock_detector.system = "windows"
        mock_detector.get_installation_instructions.return_value = {
            "windows": "Windows install instructions"
        }
        mock_detector_class.return_value = mock_detector

        with pytest.raises(RuntimeError, match="No stockfish engine found"):
            EngineAdapter.create_with_auto_detection("stockfish")

from unittest.mock import Mock

import pytest

from openboard.engine.engine_adapter import EngineAdapter
from openboard.exceptions import EngineNotFoundError


def test_engine_auto_detection(monkeypatch):
    detector = Mock()
    detector.find_engine.return_value = "/test/stockfish"
    monkeypatch.setattr(
        "openboard.engine.engine_adapter.EngineDetector", lambda: detector
    )
    adapter = EngineAdapter(options={"Hash": 32})
    assert adapter.engine_path == "/test/stockfish"
    assert adapter.options == {"Hash": 32}
    detector.find_engine.assert_called_once_with("stockfish")


def test_missing_engine_reports_installation_instructions(monkeypatch):
    detector = Mock()
    detector.find_engine.return_value = None
    detector.system = "windows"
    detector.get_installation_instructions.return_value = {
        "windows": "Install Stockfish here"
    }
    monkeypatch.setattr(
        "openboard.engine.engine_adapter.EngineDetector", lambda: detector
    )
    with pytest.raises(EngineNotFoundError, match="Install Stockfish here"):
        EngineAdapter()


def test_explicit_path_skips_detection(monkeypatch):
    detector = Mock()
    monkeypatch.setattr("openboard.engine.engine_adapter.EngineDetector", detector)
    assert EngineAdapter("/custom/engine").engine_path == "/custom/engine"
    detector.assert_not_called()

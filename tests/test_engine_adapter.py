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


import subprocess


class TestSimpleApiRemoved:
    """Verifies TD-06 / CONCERNS.md "Dead `_simple` API surface": _simple methods are deleted."""

    def test_simple_api_removed(self):
        """Verifies TD-06 / D-12: EngineAdapter exposes no `_simple` family methods."""
        from openboard.engine.engine_adapter import EngineAdapter

        removed_names = [
            "start_simple",
            "stop_simple",
            "get_best_move_simple",
            "get_best_move_simple_async",
            "_start_engine_simple",
        ]
        for method_name in removed_names:
            assert not hasattr(EngineAdapter, method_name), (
                f"TD-06: {method_name} must be removed from EngineAdapter"
            )

    def test_simple_token_absent_from_source_tree(self):
        """[guardrail] Verifies TD-06 / Codex LOW: no `_simple` token anywhere in openboard/ or tests/.

        Stronger than the attribute-absence test: catches any lingering import, reference,
        or alias to the deleted API surface in the entire source tree.
        """
        result = subprocess.run(
            ["grep", "-rE", r"\b_simple\b", "openboard/", "tests/"],
            capture_output=True,
            text=True,
        )
        # returncode 1 = no matches found (success); returncode 0 = matches found (failure).
        # Filter out this test file itself, which legitimately contains the token.
        offending_lines = [
            line for line in result.stdout.splitlines()
            if "test_engine_adapter.py" not in line
        ]
        assert offending_lines == [], (
            f"TD-06 [guardrail]: `_simple` token still present in source tree:\n"
            + "\n".join(offending_lines)
        )


class TestExceptionWiring:
    """Verifies TD-11 / D-19: EngineAdapter raises EngineTimeoutError and EngineProcessError (STRICT)."""

    def test_engine_timeout_error_raised_on_compute_timeout(self):
        """Verifies TD-11 / D-19 (Codex MEDIUM strict): a future.result() timeout in get_best_move() surfaces as EngineTimeoutError, NOT RuntimeError."""
        from concurrent.futures import TimeoutError as FutureTimeoutError
        from unittest.mock import MagicMock, patch

        import chess

        from openboard.engine.engine_adapter import EngineAdapter
        from openboard.exceptions import EngineTimeoutError

        adapter = EngineAdapter(engine_path="/fake/stockfish")
        # Make is_running() return True without launching a real subprocess. The three
        # private attributes below are exactly what is_running() inspects; mocking them
        # avoids the engine boot path.
        adapter._engine = MagicMock()
        adapter._loop = MagicMock()
        adapter._loop.is_closed.return_value = False
        adapter._shutdown_event.clear()

        fake_future = MagicMock()
        fake_future.result.side_effect = FutureTimeoutError()

        with patch(
            "openboard.engine.engine_adapter.asyncio.run_coroutine_threadsafe",
            return_value=fake_future,
        ):
            # Codex MEDIUM strict: ONLY EngineTimeoutError is acceptable. No RuntimeError tolerance.
            with pytest.raises(EngineTimeoutError):
                adapter.get_best_move(chess.Board(), time_ms=100)

    def test_engine_process_error_raised_on_startup_failure(self):
        """Verifies TD-11 / D-19 (Codex MEDIUM strict): engine startup failure surfaces as EngineProcessError with the message substring 'startup failed'.

        Codex MEDIUM: assertion verifies BOTH the specific exception type AND the message
        substring 'startup failed' — not "any exception" tolerance.
        """
        from unittest.mock import patch

        from openboard.engine.engine_adapter import EngineAdapter
        from openboard.exceptions import EngineProcessError

        adapter = EngineAdapter(engine_path="/fake/that/does/not/exist")
        # Use OSError(EACCES) instead of FileNotFoundError so the existing EngineNotFoundError
        # path does NOT intercept. The wire-up at _start_engine must raise EngineProcessError.
        with patch(
            "openboard.engine.engine_adapter.chess.engine.popen_uci",
            side_effect=OSError(13, "permission denied — cannot exec engine binary"),
        ):
            with pytest.raises(EngineProcessError) as excinfo:
                adapter.start()

        # Codex MEDIUM specific message: the message must contain 'startup failed'.
        error_message = str(excinfo.value).lower()
        assert "startup failed" in error_message, (
            f"TD-11 / D-19 / Codex MEDIUM: EngineProcessError message must contain "
            f"'startup failed' substring. Got: {excinfo.value!r}"
        )

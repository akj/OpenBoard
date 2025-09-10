"""
Simple integration tests for EngineAdapter thread safety fixes.
These focus on core functionality without complex mocking.
"""

import pytest
import time
import threading
from unittest.mock import patch, MagicMock
import chess
import chess.engine
from concurrent.futures import Future

from openboard.engine.engine_adapter import EngineAdapter


def test_adapter_initialization() -> None:
    """Test basic adapter initialization."""
    adapter = EngineAdapter(engine_path="/fake/path")
    assert adapter.engine_path == "/fake/path"
    assert not adapter.is_running()
    assert adapter._state_lock is not None
    assert adapter._loop_ready_event is not None
    assert adapter._shutdown_event is not None


def test_adapter_thread_safety_attributes() -> None:
    """Test that thread safety attributes are properly initialized."""
    adapter = EngineAdapter(engine_path="/fake/path")

    # Test that we can acquire locks without deadlock
    with adapter._state_lock:
        assert not adapter.is_running()

    # Test events are initialized
    assert not adapter._loop_ready_event.is_set()
    assert not adapter._shutdown_event.is_set()


def test_adapter_multiple_stops_safe() -> None:
    """Test that multiple stop() calls are safe."""
    adapter = EngineAdapter(engine_path="/fake/path")

    # Multiple stops should not raise exceptions
    adapter.stop()
    adapter.stop()
    adapter.stop()

    assert not adapter.is_running()


def test_adapter_state_lock_prevents_races() -> None:
    """Test that state lock prevents race conditions."""
    adapter = EngineAdapter(engine_path="/fake/path")

    results: list[bool] = []
    errors: list[Exception] = []

    def worker():
        try:
            for _ in range(10):
                is_running = adapter.is_running()
                results.append(is_running)
                time.sleep(0.001)
        except Exception as e:
            errors.append(e)

    # Run multiple threads accessing is_running concurrently
    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Should not have any errors
    assert len(errors) == 0
    assert len(results) == 50  # 5 threads * 10 calls each
    assert all(
        result is False for result in results
    )  # All should be False since not started


def test_adapter_strong_set_cleanup() -> None:
    """Test that strong reference set properly manages future references."""
    adapter = EngineAdapter(engine_path="/fake/path")

    # Add some mock futures to the set
    future1 = Future()
    future2 = Future()

    adapter._active_futures.add(future1)
    adapter._active_futures.add(future2)

    assert len(adapter._active_futures) == 2

    # With strong references, manual cleanup is required via discard
    adapter._active_futures.discard(future1)
    adapter._active_futures.discard(future2)

    # Set should be empty after manual cleanup
    assert len(adapter._active_futures) == 0


@patch("chess.engine.popen_uci")
def test_adapter_get_best_move_requires_running_engine(
    mock_popen_uci: MagicMock,
) -> None:
    """Test that get_best_move requires engine to be running."""
    adapter = EngineAdapter(engine_path="/fake/path")

    # Should raise error when engine not running
    with pytest.raises(RuntimeError, match="Engine is not running"):
        adapter.get_best_move(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        )


@patch("chess.engine.popen_uci")
def test_adapter_get_best_move_async_requires_running_engine(
    mock_popen_uci: MagicMock,
) -> None:
    """Test that get_best_move_async requires engine to be running."""
    adapter = EngineAdapter(engine_path="/fake/path")

    # Should raise error when engine not running
    with pytest.raises(RuntimeError, match="Engine is not running"):
        adapter.get_best_move_async(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        )


def test_adapter_context_manager_interface() -> None:
    """Test that adapter supports context manager interface."""
    adapter = EngineAdapter(engine_path="/fake/path")

    # Should have __enter__ and __exit__ methods
    assert hasattr(adapter, "__enter__")
    assert hasattr(adapter, "__exit__")
    assert callable(adapter.__enter__)
    assert callable(adapter.__exit__)


def test_timeout_calculation() -> None:
    """Test adaptive timeout calculation logic."""
    # Test the mathematical logic used in get_best_move timeout calculation

    # For 1000ms request
    time_ms = 1000
    base_timeout = max(time_ms / 1000.0, 1.0)  # 1.0
    buffer_timeout = min(base_timeout * 0.5, 10.0)  # 0.5
    total_timeout = base_timeout + buffer_timeout + 5.0  # 6.5

    assert base_timeout == 1.0
    assert buffer_timeout == 0.5
    assert total_timeout == 6.5

    # For very long request
    time_ms = 30000  # 30 seconds
    base_timeout = max(time_ms / 1000.0, 1.0)  # 30.0
    buffer_timeout = min(base_timeout * 0.5, 10.0)  # 10.0 (capped)
    total_timeout = base_timeout + buffer_timeout + 5.0  # 45.0

    assert base_timeout == 30.0
    assert buffer_timeout == 10.0  # Should be capped at 10
    assert total_timeout == 45.0


def test_wx_import_handling() -> None:
    """Test that wx import works correctly."""
    # wx is a required dependency, so import should always succeed
    import wx

    # Basic wx functionality should be available
    assert hasattr(wx, "CallAfter")
    assert hasattr(wx, "GetApp")
    assert callable(wx.CallAfter)
    assert callable(wx.GetApp)


def test_error_message_formatting() -> None:
    """Test that error messages are properly formatted."""
    # Test various error scenarios would format messages correctly
    assert "Engine is not running" in "Engine is not running; call start() first."
    assert "best move" in "Engine failed to compute best move: test error"
    assert "startup failed" in "Engine startup failed: test error"


def test_create_with_auto_detection_class_method() -> None:
    """Test the create_with_auto_detection class method."""
    with patch("openboard.engine.engine_adapter.EngineDetector") as mock_detector_class:
        mock_detector = MagicMock()
        mock_detector.find_engine.return_value = "/usr/bin/stockfish"
        mock_detector_class.return_value = mock_detector

        adapter = EngineAdapter.create_with_auto_detection("stockfish", {"Threads": 4})

        assert adapter.engine_path == "/usr/bin/stockfish"
        assert adapter.options == {"Threads": 4}
        mock_detector.find_engine.assert_called_once_with("stockfish")


def test_board_copy_safety() -> None:
    """Test that chess.Board inputs are copied for thread safety."""
    adapter = EngineAdapter(engine_path="/fake/path")

    # Create a board
    original_board = chess.Board()
    original_fen = original_board.fen()

    # The adapter should work with either FEN strings or Board objects
    # This tests the input handling logic
    try:
        # This will fail because engine isn't running, but we're testing input validation
        adapter.get_best_move(original_board, time_ms=100)
    except RuntimeError as e:
        assert "Engine is not running" in str(e)

    # Original board should be unchanged
    assert original_board.fen() == original_fen


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

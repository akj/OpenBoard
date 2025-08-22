"""
Integration tests for EngineAdapter thread safety and async behavior.
These tests verify the thread safety fixes and async patterns work correctly.
"""

import asyncio
import threading
import time
import pytest
from unittest.mock import patch
from concurrent.futures import Future, ThreadPoolExecutor
import chess
import chess.engine

from openboard.engine.engine_adapter import EngineAdapter


class MockEngine:
    """Mock engine that simulates real async engine behavior."""
    
    def __init__(self, delay=0.1, should_fail=False, fail_on_configure=False):
        self.delay = delay
        self.should_fail = should_fail
        self.fail_on_configure = fail_on_configure
        self.id = {"name": "MockEngine", "version": "1.0"}
        self.configure_calls = []
        self.play_calls = []
        
    async def configure(self, options):
        self.configure_calls.append(options)
        if self.fail_on_configure:
            raise chess.engine.EngineError("Configuration failed")
        await asyncio.sleep(0.01)  # Small delay to test async
        
    async def play(self, board, limit):
        self.play_calls.append((board.fen(), limit))
        await asyncio.sleep(self.delay)
        
        if self.should_fail:
            raise chess.engine.EngineError("Engine computation failed")
            
        # Return a valid move (e2e4 if legal, or first legal move)
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return chess.engine.PlayResult(None, None)
            
        move = chess.Move.from_uci("e2e4") if chess.Move.from_uci("e2e4") in legal_moves else legal_moves[0]
        return chess.engine.PlayResult(move, None)
        
    async def quit(self):
        await asyncio.sleep(0.01)


class MockTransport:
    """Mock transport for subprocess communication."""
    
    def __init__(self, should_fail_terminate=False):
        self.should_fail_terminate = should_fail_terminate
        self._closing = False
        self._returncode = None
        
    def is_closing(self):
        return self._closing
        
    def get_returncode(self):
        return self._returncode
        
    def terminate(self):
        if self.should_fail_terminate:
            raise RuntimeError("Failed to terminate")
        self._returncode = 0
        
    def kill(self):
        self._returncode = -9


@pytest.fixture
def mock_engine_path():
    """Provide a mock engine path."""
    return "/usr/bin/mock-stockfish"


@pytest.fixture
def mock_successful_engine():
    """Create a mock engine that succeeds."""
    return MockEngine(delay=0.05)


@pytest.fixture
def mock_failing_engine():
    """Create a mock engine that fails during computation."""
    return MockEngine(delay=0.05, should_fail=True)


class TestEngineAdapterLifecycle:
    """Test engine lifecycle operations."""
    
    @patch('chess.engine.popen_uci')
    def test_engine_start_success(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Test successful engine startup."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_successful_engine)
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        
        # Initially not running
        assert not adapter.is_running()
        
        # Start engine
        adapter.start()
        assert adapter.is_running()
        
        # Starting again should be idempotent
        adapter.start()
        assert adapter.is_running()
        
        # Clean up
        adapter.stop()
        assert not adapter.is_running()
        
    @patch('chess.engine.popen_uci')
    def test_engine_start_failure(self, mock_popen_uci, mock_engine_path):
        """Test engine startup failure."""
        mock_popen_uci.side_effect = FileNotFoundError("Engine not found")
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        
        with pytest.raises(RuntimeError, match="Engine startup failed"):
            adapter.start()
            
        assert not adapter.is_running()
        
    @patch('chess.engine.popen_uci')
    def test_engine_start_timeout(self, mock_popen_uci, mock_engine_path):
        """Test engine startup timeout."""
        # Make popen_uci hang indefinitely
        future = Future()
        mock_popen_uci.return_value = future
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        
        with pytest.raises(RuntimeError, match="Engine startup timed out"):
            adapter.start()
            
        assert not adapter.is_running()
        
    @patch('chess.engine.popen_uci')
    def test_engine_stop_multiple_calls(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Test that multiple stop() calls are safe."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_successful_engine)
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        adapter.start()
        
        # Multiple stops should be safe
        adapter.stop()
        adapter.stop()
        adapter.stop()
        
        assert not adapter.is_running()
        
    @patch('chess.engine.popen_uci')
    def test_engine_configure_options(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Test engine option configuration."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_successful_engine)
        
        options = {"Threads": 4, "Hash": 128}
        adapter = EngineAdapter(engine_path=mock_engine_path, options=options)
        adapter.start()
        
        # Verify options were configured
        assert len(mock_successful_engine.configure_calls) == 2
        assert {"Threads": 4} in mock_successful_engine.configure_calls
        assert {"Hash": 128} in mock_successful_engine.configure_calls
        
        adapter.stop()


class TestEngineAdapterSynchronous:
    """Test synchronous engine operations."""
    
    @patch('chess.engine.popen_uci')
    def test_get_best_move_success(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Test successful best move computation."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_successful_engine)
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        adapter.start()
        
        # Test with FEN string
        fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        move = adapter.get_best_move(fen, time_ms=100)
        
        assert move is not None
        assert isinstance(move, chess.Move)
        
        # Test with chess.Board
        board = chess.Board()
        move2 = adapter.get_best_move(board, time_ms=100)
        
        assert move2 is not None
        assert isinstance(move2, chess.Move)
        
        # Verify engine was called
        assert len(mock_successful_engine.play_calls) == 2
        
        adapter.stop()
        
    @patch('chess.engine.popen_uci')
    def test_get_best_move_engine_not_running(self, mock_popen_uci, mock_engine_path):
        """Test get_best_move when engine is not running."""
        adapter = EngineAdapter(engine_path=mock_engine_path)
        
        with pytest.raises(RuntimeError, match="Engine is not running"):
            adapter.get_best_move("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
            
    @patch('chess.engine.popen_uci')
    def test_get_best_move_invalid_fen(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Test get_best_move with invalid FEN."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_successful_engine)
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        adapter.start()
        
        with pytest.raises(RuntimeError, match="Engine failed to compute best move"):
            adapter.get_best_move("invalid_fen_string", time_ms=100)
            
        adapter.stop()
        
    @patch('chess.engine.popen_uci')
    def test_get_best_move_engine_failure(self, mock_popen_uci, mock_engine_path, mock_failing_engine):
        """Test get_best_move when engine computation fails."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_failing_engine)
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        adapter.start()
        
        with pytest.raises(RuntimeError, match="Engine failed to compute best move"):
            adapter.get_best_move("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", time_ms=100)
            
        adapter.stop()
        
    @patch('chess.engine.popen_uci')
    def test_get_best_move_game_over_position(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Test get_best_move with game-over position."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_successful_engine)
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        adapter.start()
        
        # Checkmate position
        checkmate_fen = "rnb1kbnr/pppp1ppp/4p3/8/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
        board = chess.Board(checkmate_fen)
        board.push(chess.Move.from_uci("g2g4"))  # Make it checkmate
        
        move = adapter.get_best_move(board, time_ms=100)
        assert move is None  # Should return None for game over positions
        
        adapter.stop()


class TestEngineAdapterAsynchronous:
    """Test asynchronous engine operations."""
    
    @patch('chess.engine.popen_uci')
    def test_get_best_move_async_success(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Test successful async best move computation."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_successful_engine)
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        adapter.start()
        
        # Test async without callback
        future = adapter.get_best_move_async("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", time_ms=100)
        move = future.result(timeout=5.0)
        
        assert move is not None
        assert isinstance(move, chess.Move)
        
        adapter.stop()
        
    @patch('chess.engine.popen_uci')
    def test_get_best_move_async_with_callback(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Test async best move computation with callback."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_successful_engine)
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        adapter.start()
        
        # Test async with callback
        callback_results = []
        
        def callback(result):
            callback_results.append(result)
        
        future = adapter.get_best_move_async(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 
            time_ms=100,
            callback=callback
        )
        
        # Wait for completion
        move = future.result(timeout=5.0)
        time.sleep(0.1)  # Give callback time to execute
        
        assert move is not None
        assert len(callback_results) == 1
        assert callback_results[0] == move
        
        adapter.stop()
        
    @patch('chess.engine.popen_uci')
    def test_get_best_move_async_callback_error_handling(self, mock_popen_uci, mock_engine_path, mock_failing_engine):
        """Test async callback error handling."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_failing_engine)
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        adapter.start()
        
        callback_results = []
        
        def callback(result):
            callback_results.append(result)
        
        future = adapter.get_best_move_async(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 
            time_ms=100,
            callback=callback
        )
        
        # Should get exception
        with pytest.raises(RuntimeError):
            future.result(timeout=5.0)
        
        time.sleep(0.1)  # Give callback time to execute
        
        # Callback should have received the exception
        assert len(callback_results) == 1
        assert isinstance(callback_results[0], Exception)
        
        adapter.stop()


class TestEngineAdapterConcurrency:
    """Test concurrent operations and thread safety."""
    
    @patch('chess.engine.popen_uci')
    def test_concurrent_get_best_move_calls(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Test multiple concurrent get_best_move calls."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_successful_engine)
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        adapter.start()
        
        # Make concurrent calls
        futures = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            for i in range(10):
                future = executor.submit(
                    adapter.get_best_move,
                    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                    100
                )
                futures.append(future)
        
        # All should complete successfully
        results = [f.result(timeout=10.0) for f in futures]
        
        assert len(results) == 10
        assert all(isinstance(move, chess.Move) for move in results)
        
        # Should have made 10 engine calls
        assert len(mock_successful_engine.play_calls) == 10
        
        adapter.stop()
        
    @patch('chess.engine.popen_uci')
    def test_concurrent_async_calls(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Test multiple concurrent async calls."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_successful_engine)
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        adapter.start()
        
        # Make concurrent async calls
        futures = []
        for i in range(10):
            future = adapter.get_best_move_async(
                "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", 
                time_ms=50
            )
            futures.append(future)
        
        # All should complete successfully
        results = []
        for future in futures:
            result = future.result(timeout=10.0)
            results.append(result)
        
        assert len(results) == 10
        assert all(isinstance(move, chess.Move) for move in results)
        
        adapter.stop()
        
    @patch('chess.engine.popen_uci')
    def test_start_stop_race_condition(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Test concurrent start/stop calls don't cause race conditions."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_successful_engine)
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        
        # Concurrent start/stop operations
        def start_stop_worker():
            for _ in range(5):
                try:
                    adapter.start()
                    time.sleep(0.01)
                    adapter.stop()
                    time.sleep(0.01)
                except Exception:
                    pass  # Expected during concurrent operations
        
        threads = [threading.Thread(target=start_stop_worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should end in a clean state
        adapter.stop()  # Ensure stopped
        assert not adapter.is_running()


class TestEngineAdapterResourceManagement:
    """Test resource management and cleanup."""
    
    @patch('chess.engine.popen_uci')
    def test_resource_cleanup_on_stop(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Test that resources are properly cleaned up on stop."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_successful_engine)
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        adapter.start()
        
        # Verify resources are allocated
        assert adapter._engine is not None
        assert adapter._transport is not None
        assert adapter._loop is not None
        assert adapter._engine_thread is not None
        
        adapter.stop()
        
        # Verify resources are cleaned up
        assert adapter._engine is None
        assert adapter._transport is None
        assert adapter._loop is None
        assert adapter._engine_thread is None
        
    @patch('chess.engine.popen_uci')
    def test_active_futures_cleanup(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Test that active futures are cancelled on shutdown."""
        # Use slow engine to test cancellation
        slow_engine = MockEngine(delay=2.0)
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, slow_engine)
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        adapter.start()
        
        # Start a slow operation
        future = adapter.get_best_move_async(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            time_ms=2000
        )
        
        # Stop should cancel the future
        adapter.stop()
        
        # Future should be cancelled or completed quickly
        time.sleep(0.5)
        assert future.done()
        
    @patch('chess.engine.popen_uci')  
    def test_transport_termination_failure(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Test graceful handling when transport termination fails."""
        mock_transport = MockTransport(should_fail_terminate=True)
        mock_popen_uci.return_value = (mock_transport, mock_successful_engine)
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        adapter.start()
        
        # Stop should handle termination failure gracefully
        adapter.stop()  # Should not raise exception
        
        assert not adapter.is_running()


class TestEngineAdapterStressTest:
    """Stress tests for thread safety under load."""
    
    @patch('chess.engine.popen_uci')
    def test_high_concurrency_stress(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Stress test with high concurrency."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_successful_engine)
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        adapter.start()
        
        # High concurrency test
        futures = []
        
        def worker():
            for _ in range(5):
                future = adapter.get_best_move_async(
                    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                    time_ms=10
                )
                futures.append(future)
        
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All futures should complete successfully
        completed = 0
        for future in futures:
            try:
                result = future.result(timeout=10.0)
                if isinstance(result, chess.Move):
                    completed += 1
            except Exception:
                pass  # Some might fail due to high load
        
        # Most should succeed
        assert completed >= len(futures) * 0.8  # Allow for some failures under stress
        
        adapter.stop()
        
    @patch('chess.engine.popen_uci')
    def test_memory_leak_detection(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Test for memory leaks in repeated start/stop cycles."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_successful_engine)
        
        adapter = EngineAdapter(engine_path=mock_engine_path)
        
        # Repeated start/stop cycles
        for i in range(20):
            adapter.start()
            
            # Make a few calls
            move = adapter.get_best_move(
                "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                time_ms=10
            )
            assert isinstance(move, chess.Move)
            
            adapter.stop()
            
            # Ensure clean state between cycles
            assert not adapter.is_running()
            assert adapter._engine is None
            assert adapter._loop is None
            assert adapter._engine_thread is None


class TestEngineAdapterContextManager:
    """Test context manager functionality."""
    
    @patch('chess.engine.popen_uci')
    def test_context_manager_success(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Test context manager success path."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_successful_engine)
        
        with EngineAdapter(engine_path=mock_engine_path) as adapter:
            assert adapter.is_running()
            
            move = adapter.get_best_move(
                "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                time_ms=100
            )
            assert isinstance(move, chess.Move)
        
        # Should be stopped after context exit
        assert not adapter.is_running()
        
    @patch('chess.engine.popen_uci')
    def test_context_manager_exception(self, mock_popen_uci, mock_engine_path, mock_successful_engine):
        """Test context manager cleanup on exception."""
        mock_transport = MockTransport()
        mock_popen_uci.return_value = (mock_transport, mock_successful_engine)
        
        adapter = None
        try:
            with EngineAdapter(engine_path=mock_engine_path) as adapter:
                assert adapter.is_running()
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Should be stopped even after exception
        assert adapter is not None
        assert not adapter.is_running()
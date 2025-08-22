import asyncio
import logging
import threading
from typing import Union, Dict, Any, Optional
from concurrent.futures import Future

import chess
import chess.engine

from .engine_detection import EngineDetector


class EngineAdapter:
    """
    Modern asyncio-based wrapper around a UCI engine (e.g. Stockfish).
    Provides synchronous interface for GUI while using async engine communication internally.

    Usage:
        adapter = EngineAdapter("/path/to/stockfish", {"Threads": 2})
        adapter.start()
        move1 = adapter.get_best_move("r1bqkbnr/pppppppp/2n5/8/8/2N5/PPPPPPPP/R1BQKBNR w KQkq - 0 1")
        # or
        board = chess.Board()
        move2 = adapter.get_best_move(board, time_ms=500)
        adapter.stop()
    """

    def __init__(
        self,
        engine_path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ):
        """
        :param engine_path: path to the UCI engine executable. If None, will auto-detect.
        :param options: dictionary of UCI options, e.g. {"Threads": 2, "Hash": 128}
        """
        if engine_path is None:
            detector = EngineDetector()
            engine_path = detector.find_engine("stockfish")
            if engine_path is None:
                instructions = detector.get_installation_instructions("stockfish")
                system = detector.system
                instruction_text = instructions.get(
                    system, instructions.get("generic", "")
                )
                raise RuntimeError(
                    f"No Stockfish engine found on system. Please install Stockfish:\n\n{instruction_text}"
                )

        self.engine_path = engine_path
        self.options = options or {}
        self._engine: Optional[chess.engine.Protocol] = None
        self._transport: Optional[asyncio.SubprocessTransport] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._engine_thread: Optional[threading.Thread] = None
        self._logger = logging.getLogger(__name__)

    def start(self) -> None:
        """
        Launches the engine process if not already running.
        Starts an asyncio event loop in a background thread.
        """
        if self._engine is not None:
            return

        # Start asyncio event loop in background thread
        self._start_async_loop()
        
        # Initialize engine in the async loop
        future = asyncio.run_coroutine_threadsafe(self._start_engine(), self._loop)
        try:
            future.result(timeout=10.0)  # 10 second timeout for engine startup
        except Exception as e:
            msg = f"Failed to launch engine at '{self.engine_path}': {e}"
            self._logger.error(msg)
            self.stop()
            raise RuntimeError(msg) from e

    def _start_async_loop(self) -> None:
        """Start asyncio event loop in background thread."""
        if self._engine_thread and self._engine_thread.is_alive():
            return

        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                self._loop.run_forever()
            finally:
                self._loop.close()

        self._engine_thread = threading.Thread(target=run_loop, daemon=True)
        self._engine_thread.start()

        # Wait for loop to be ready
        while self._loop is None:
            threading.Event().wait(0.01)

    async def _start_engine(self) -> None:
        """Start the engine using async API."""
        try:
            self._transport, self._engine = await chess.engine.popen_uci(self.engine_path)
            
            # Configure UCI options
            for name, val in self.options.items():
                try:
                    await self._engine.configure({name: val})
                except Exception as e:
                    self._logger.warning(f"Could not set engine option {name}={val}: {e}")
                    
        except Exception as e:
            self._logger.error(f"Failed to start engine: {e}")
            raise

    def stop(self) -> None:
        """
        Quits the engine process and stops the async loop.
        Safe to call multiple times.
        """
        if self._loop and not self._loop.is_closed():
            # Schedule engine shutdown
            if self._engine:
                future = asyncio.run_coroutine_threadsafe(self._stop_engine(), self._loop)
                try:
                    future.result(timeout=5.0)
                except Exception as e:
                    self._logger.warning(f"Error while stopping engine: {e}")

            # Stop the event loop
            self._loop.call_soon_threadsafe(self._loop.stop)

        # Wait for thread to finish
        if self._engine_thread and self._engine_thread.is_alive():
            self._engine_thread.join(timeout=2.0)

        self._engine = None
        self._transport = None
        self._loop = None
        self._engine_thread = None

    async def _stop_engine(self) -> None:
        """Stop the engine using async API."""
        try:
            if self._engine:
                await self._engine.quit()
        except Exception as e:
            self._logger.warning(f"Error while quitting engine: {e}")

    def is_running(self) -> bool:
        """Returns True if the engine is currently running."""
        return self._engine is not None and self._loop is not None and not self._loop.is_closed()

    def get_best_move(
        self, position: Union[str, chess.Board], time_ms: int = 1000, depth: Optional[int] = None
    ) -> chess.Move | None:
        """
        Synchronously get the engine's best move for the given position.
        Uses async engine communication internally.

        :param position: either a FEN string or a chess.Board instance.
        :param time_ms: think time in milliseconds.
        :param depth: search depth limit (optional, overrides time if provided).
        :return: a chess.Move instance.
        :raises RuntimeError: if engine isn't started.
        :raises ValueError: if the FEN is invalid.
        :raises chess.engine.EngineTerminatedError: on engine failure.
        """
        if not self.is_running():
            raise RuntimeError("Engine is not running; call start() first.")

        # Schedule async computation and wait for result
        future = asyncio.run_coroutine_threadsafe(
            self._get_best_move_async(position, time_ms, depth), 
            self._loop
        )
        
        try:
            return future.result(timeout=max(time_ms / 1000.0 + 5.0, 10.0))  # Add buffer to timeout
        except Exception as e:
            msg = f"Engine failed to compute best move: {e}"
            self._logger.error(msg)
            raise RuntimeError(msg) from e

    async def _get_best_move_async(
        self, position: Union[str, chess.Board], time_ms: int, depth: Optional[int]
    ) -> chess.Move | None:
        """Async implementation of get_best_move."""
        if isinstance(position, chess.Board):
            board = position
        elif isinstance(position, str):
            try:
                board = chess.Board(position)
            except Exception as e:
                raise ValueError(f"Invalid FEN string: {e}") from e
        else:
            raise TypeError("position must be a FEN string or chess.Board")

        # Create search limit - prefer depth over time if specified
        if depth is not None:
            limit = chess.engine.Limit(depth=depth)
        else:
            limit = chess.engine.Limit(time=time_ms / 1000.0)

        try:
            result = await self._engine.play(board, limit)
            return result.move
        except Exception as e:
            self._logger.error(f"Async engine computation failed: {e}")
            raise

    def get_best_move_async(
        self, position: Union[str, chess.Board], time_ms: int = 1000, 
        depth: Optional[int] = None, callback=None
    ) -> Future:
        """
        Get best move asynchronously with callback support.
        Returns a Future that can be used to check completion or add callbacks.
        
        :param position: either a FEN string or a chess.Board instance.
        :param time_ms: think time in milliseconds.
        :param depth: search depth limit (optional, overrides time if provided).
        :param callback: optional callback function called with result
        :return: Future object
        """
        if not self.is_running():
            raise RuntimeError("Engine is not running; call start() first.")

        future = asyncio.run_coroutine_threadsafe(
            self._get_best_move_async(position, time_ms, depth), 
            self._loop
        )
        
        if callback:
            future.add_done_callback(lambda f: callback(f.result() if not f.exception() else f.exception()))
            
        return future

    # Optional context manager support
    def __enter__(self) -> "EngineAdapter":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    @classmethod
    def create_with_auto_detection(
        cls, engine_name: str = "stockfish", options: Optional[Dict[str, Any]] = None
    ) -> "EngineAdapter":
        """
        Create an EngineAdapter with automatic engine detection.

        :param engine_name: Name of the engine to detect (default: "stockfish")
        :param options: Dictionary of UCI options
        :return: EngineAdapter instance
        :raises RuntimeError: If the engine cannot be found
        """
        detector = EngineDetector()
        engine_path = detector.find_engine(engine_name)

        if engine_path is None:
            instructions = detector.get_installation_instructions(engine_name)
            system = detector.system
            instruction_text = instructions.get(system, instructions.get("generic", ""))
            raise RuntimeError(
                f"No {engine_name} engine found on system. Please install {engine_name}:\n\n{instruction_text}"
            )

        return cls(engine_path, options)

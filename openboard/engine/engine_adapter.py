import asyncio
import logging
import threading
from typing import Any, Self, AsyncIterator
from concurrent.futures import Future
from contextlib import asynccontextmanager

import chess
import chess.engine

from .engine_detection import EngineDetector
from ..exceptions import (
    EngineNotFoundError,
    EngineInitializationError,
)


class CallbackExecutor:
    """Base callback executor for handling async callback execution."""

    def execute(self, callback, *args, **kwargs):
        """Execute callback directly."""
        if callback:
            callback(*args, **kwargs)


class WxCallbackExecutor(CallbackExecutor):
    """Wx-aware callback executor that uses CallAfter for thread safety."""

    def execute(self, callback, *args, **kwargs):
        """Execute callback using wx.CallAfter if not on main thread."""
        if not callback:
            return

        if threading.current_thread() != threading.main_thread():
            try:
                if HAS_WX and hasattr(wx, "GetApp") and wx.GetApp() is not None:
                    wx.CallAfter(callback, *args, **kwargs)
                    return
            except (RuntimeError, AttributeError):
                # Fallback if wx is shutting down or not properly initialized
                pass

        # Direct execution if on main thread or wx unavailable
        callback(*args, **kwargs)


try:
    import wx

    HAS_WX = True
except ImportError:
    HAS_WX = False


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
        engine_path: str | None = None,
        options: dict[str, Any] | None = None,
        callback_executor: CallbackExecutor | None = None,
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
        self._engine: chess.engine.Protocol | None = None
        self._transport: asyncio.SubprocessTransport | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._engine_thread: threading.Thread | None = None
        self._logger = logging.getLogger(__name__)

        # Thread synchronization
        self._state_lock = threading.RLock()
        self._loop_ready_event = threading.Event()
        self._shutdown_event = threading.Event()
        self._active_futures = set()
        self._cleanup_futures = set()  # Track cleanup operations with strong references

        # Callback execution strategy
        if callback_executor is None:
            # Auto-detect best callback executor
            self._callback_executor = (
                WxCallbackExecutor() if HAS_WX else CallbackExecutor()
            )
        else:
            self._callback_executor = callback_executor

    def start(self) -> None:
        """
        Launches the engine process if not already running.
        Starts an asyncio event loop in a background thread.
        """
        with self._state_lock:
            if self._engine is not None:
                return

            # Start asyncio event loop in background thread
            self._start_async_loop()

            # Initialize engine in the async loop
            if self._loop is None:
                raise RuntimeError("Event loop not initialized")
            future = asyncio.run_coroutine_threadsafe(self._start_engine(), self._loop)
            self._active_futures.add(future)

            try:
                future.result(timeout=15.0)  # Increased timeout for engine startup
            except Exception as e:
                msg = f"Failed to launch engine at '{self.engine_path}': {e}"
                self._logger.error(msg)
                self.stop()
                raise RuntimeError(msg) from e
            finally:
                self._active_futures.discard(future)

    def _start_async_loop(self) -> None:
        """Start asyncio event loop in background thread."""
        with self._state_lock:
            if self._engine_thread and self._engine_thread.is_alive():
                return

            self._loop_ready_event.clear()
            self._shutdown_event.clear()

            def run_loop():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    # Assign loop to instance variable
                    self._loop = loop
                    self._loop_ready_event.set()

                    # Simple loop lifecycle - run until shutdown event
                    async def shutdown_monitor():
                        while not self._shutdown_event.is_set():
                            await asyncio.sleep(0.1)
                        loop.stop()

                    # Schedule the monitor and run the loop
                    loop.create_task(shutdown_monitor())
                    loop.run_forever()

                except Exception as e:
                    self._logger.error(f"Event loop thread failed: {e}")
                    self._loop_ready_event.set()
                finally:
                    # Simple cleanup - cancel tasks then close loop
                    if self._loop and not self._loop.is_closed():
                        try:
                            pending = asyncio.all_tasks(self._loop)
                            for task in pending:
                                task.cancel()
                            if pending:
                                # Wait briefly for cancellation
                                try:
                                    self._loop.run_until_complete(
                                        asyncio.gather(*pending, return_exceptions=True)
                                    )
                                except Exception:
                                    pass  # Ignore cancellation errors
                        except Exception:
                            pass  # Ignore cleanup errors
                        finally:
                            try:
                                self._loop.close()
                            except Exception:
                                pass  # Ignore close errors
                    self._loop = None

            self._engine_thread = threading.Thread(target=run_loop, daemon=True)
            self._engine_thread.start()

        # Wait for loop to be ready
        if not self._loop_ready_event.wait(timeout=10.0):
            self._shutdown_event.set()
            if self._engine_thread and self._engine_thread.is_alive():
                self._engine_thread.join(timeout=2.0)
            with self._state_lock:
                self._loop = None
                self._engine_thread = None
            raise RuntimeError("Failed to start async event loop within timeout")

    async def _start_engine(self) -> None:
        """Start the engine using async API with enhanced error handling."""
        try:
            self._logger.info(f"Starting engine: {self.engine_path}")

            # Signal startup completion when done

            # Start engine with timeout
            try:
                self._transport, self._engine = await asyncio.wait_for(
                    chess.engine.popen_uci(self.engine_path), timeout=10.0
                )
            except asyncio.TimeoutError:
                raise RuntimeError(
                    f"Engine startup timed out after 10 seconds: {self.engine_path}"
                )

            self._logger.info(
                f"Engine started successfully: {self._engine.id if hasattr(self._engine, 'id') else 'Unknown'}"
            )

            # Configure UCI options with validation
            if self.options:
                self._logger.debug(f"Configuring engine options: {self.options}")

            for name, val in self.options.items():
                try:
                    await self._engine.configure({name: val})
                    self._logger.debug(f"Successfully set {name}={val}")
                except chess.engine.EngineError as e:
                    self._logger.warning(f"Engine rejected option {name}={val}: {e}")
                except Exception as e:
                    self._logger.warning(
                        f"Could not set engine option {name}={val}: {e}"
                    )

        except FileNotFoundError:
            raise EngineNotFoundError(f"Engine at {self.engine_path}")
        except PermissionError:
            raise RuntimeError(
                f"Permission denied executing engine: {self.engine_path}"
            )
        except chess.engine.EngineTerminatedError as e:
            raise EngineInitializationError(f"Engine terminated during startup: {e}")

        except Exception as e:
            self._logger.error(f"Failed to start engine at '{self.engine_path}': {e}")
            raise RuntimeError(f"Engine startup failed: {e}") from e

    def _validate_board_state(self, position: str | chess.Board) -> chess.Board:
        """Validate and convert position to chess.Board."""
        if isinstance(position, str):
            try:
                return chess.Board(position)
            except ValueError as e:
                raise ValueError(f"Invalid FEN string: {position}") from e
        elif isinstance(position, chess.Board):
            return position
        else:
            raise ValueError(
                f"Position must be FEN string or chess.Board, got {type(position)}"
            )

    def _create_engine_limit(
        self, time_ms: int, depth: int | None
    ) -> chess.engine.Limit:
        """Create engine search limit from time and depth parameters."""
        if depth is not None:
            return chess.engine.Limit(depth=depth)
        else:
            return chess.engine.Limit(time=time_ms / 1000.0)

    def stop(self) -> None:
        """
        Simplified shutdown: signal -> join thread -> reset state.
        Safe to call multiple times.
        """
        # Step 1: Signal shutdown (set threading.Event)
        with self._state_lock:
            self._shutdown_event.set()

        # Cancel active futures
        with self._state_lock:
            for future in list(self._active_futures):
                if not future.done():
                    try:
                        future.cancel()
                    except Exception:
                        pass  # Ignore cancellation errors

        # Step 2: Join thread (with minimal timeout only if absolutely needed)
        if self._engine_thread and self._engine_thread.is_alive():
            self._engine_thread.join(timeout=3.0)
            if self._engine_thread.is_alive():
                self._logger.warning("Engine thread did not terminate within timeout")

        # Step 3: Reset state (clear explicit references)
        with self._state_lock:
            self._engine = None
            self._transport = None
            self._loop = None
            self._engine_thread = None
            self._active_futures.clear()
            self._cleanup_futures.clear()

    async def _shutdown_engine_gracefully(self) -> None:
        """Gracefully shutdown engine with proper resource cleanup order."""
        try:
            # Step 1: Stop the engine properly and wait for completion
            if self._engine:
                self._logger.debug("Sending quit command to engine")
                try:
                    # Give engine a moment to finish current operations
                    await asyncio.sleep(0.05)
                    await asyncio.wait_for(self._engine.quit(), timeout=2.0)
                    self._logger.debug("Engine quit command completed")
                except asyncio.TimeoutError:
                    self._logger.debug(
                        "Engine quit command timed out - continuing with cleanup"
                    )
                except Exception as e:
                    self._logger.debug(f"Error sending quit to engine: {e}")

            # Step 2: Clean up transport synchronously to avoid event loop issues
            if self._transport and not self._transport.is_closing():
                self._logger.debug("Cleaning up engine transport")
                try:
                    # Close transport immediately to prevent it from trying to use closed loop later
                    if hasattr(self._transport, "close"):
                        self._transport.close()

                    # Then terminate process
                    try:
                        self._transport.terminate()
                        # Brief wait for termination
                        await asyncio.sleep(0.1)

                        # Force kill if needed
                        if self._transport.get_returncode() is None:
                            self._transport.kill()
                    except Exception:
                        pass  # Ignore termination errors after close()

                    self._logger.debug("Engine transport cleanup completed")

                except Exception as e:
                    self._logger.debug(f"Transport cleanup warning: {e}")

            # Step 3: Final small delay to ensure all async operations complete
            await asyncio.sleep(0.05)

        except Exception as e:
            self._logger.debug(f"Engine shutdown completed with warnings: {e}")

    async def _safe_cleanup(self) -> None:
        """
        Safe cleanup method that can be called during exceptions.
        Performs minimal cleanup without raising additional exceptions.
        """
        try:
            with self._state_lock:
                self._shutdown_event.set()

            # Cancel any active futures
            with self._state_lock:
                for future in list(self._active_futures):
                    if not future.done():
                        try:
                            future.cancel()
                        except Exception:
                            pass

            # Basic engine cleanup
            if self._engine:
                try:
                    await asyncio.wait_for(self._engine.quit(), timeout=1.0)
                except Exception:
                    pass  # Ignore quit errors during emergency cleanup

            # Basic transport cleanup
            if self._transport and not self._transport.is_closing():
                try:
                    self._transport.close()
                    self._transport.terminate()
                except Exception:
                    pass  # Ignore transport errors during emergency cleanup

            # Final small delay for I/O completion
            try:
                await asyncio.sleep(0.05)
            except Exception:
                pass

        except Exception as e:
            # Log but never raise during safe cleanup
            self._logger.debug(f"Error in safe cleanup: {e}")

    def is_running(self) -> bool:
        """Returns True if the engine is currently running."""
        with self._state_lock:
            return (
                self._engine is not None
                and self._loop is not None
                and not self._loop.is_closed()
                and not self._shutdown_event.is_set()
            )

    def get_best_move(
        self,
        position: str | chess.Board,
        time_ms: int = 1000,
        depth: int | None = None,
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

        with self._state_lock:
            if not self._loop or self._loop.is_closed():
                raise RuntimeError("Engine event loop is not available")

            # Schedule async computation and wait for result
            future = asyncio.run_coroutine_threadsafe(
                self._get_best_move_async(position, time_ms, depth), self._loop
            )
            self._active_futures.add(future)

        try:
            # Calculate adaptive timeout based on complexity
            base_timeout = max(time_ms / 1000.0, 1.0)
            buffer_timeout = min(base_timeout * 0.5, 10.0)  # Up to 10s buffer
            total_timeout = base_timeout + buffer_timeout + 5.0  # Minimum 5s buffer

            return future.result(timeout=total_timeout)
        except Exception as e:
            msg = f"Engine failed to compute best move: {e}"
            self._logger.error(msg)
            raise RuntimeError(msg) from e
        finally:
            self._active_futures.discard(future)

    async def _get_best_move_async(
        self, position: str | chess.Board, time_ms: int, depth: int | None
    ) -> chess.Move | None:
        """Async implementation of get_best_move with enhanced error handling."""
        board = self._validate_board_state(position)

        # Return None for game-over positions
        if board.is_game_over():
            return None

        limit = self._create_engine_limit(time_ms, depth)

        try:
            # Check if engine is still available
            if not self._engine:
                raise RuntimeError("Engine became unavailable during computation")

            result = await self._engine.play(board, limit)

            if result.move is None:
                self._logger.warning(
                    f"Engine returned no move for position: {board.fen()[:50]}..."
                )
                return None

            # Validate the move is legal
            if result.move not in board.legal_moves:
                self._logger.error(
                    f"Engine returned illegal move {result.move} for position {board.fen()[:50]}..."
                )
                return None

            self._logger.debug(
                f"Engine found move: {result.move} (eval: {getattr(result, 'score', 'N/A')})"
            )
            return result.move

        except asyncio.CancelledError:
            self._logger.info("Engine computation was cancelled")
            raise
        except chess.engine.EngineTerminatedError as e:
            self._logger.error(f"Engine process terminated unexpectedly: {e}")
            raise RuntimeError(f"Chess engine crashed: {e}") from e
        except chess.engine.EngineError as e:
            self._logger.error(f"Engine error during computation: {e}")
            raise RuntimeError(f"Engine computation failed: {e}") from e
        except Exception as e:
            self._logger.error(f"Unexpected error in engine computation: {e}")
            raise RuntimeError(f"Unexpected engine error: {e}") from e

    def get_best_move_async(
        self,
        position: str | chess.Board,
        time_ms: int = 1000,
        depth: int | None = None,
        callback=None,
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

        with self._state_lock:
            if not self._loop or self._loop.is_closed():
                raise RuntimeError("Engine event loop is not available")

            future = asyncio.run_coroutine_threadsafe(
                self._get_best_move_async(position, time_ms, depth), self._loop
            )
            self._active_futures.add(future)

        def safe_callback(f):
            """Wrapper to safely handle callback exceptions and cleanup."""
            try:
                if f.exception():
                    self._callback_executor.execute(callback, f.exception())
                else:
                    self._callback_executor.execute(callback, f.result())
            except Exception as e:
                self._logger.error(f"Callback error in get_best_move_async: {e}")
            finally:
                self._active_futures.discard(f)

        if callback:
            future.add_done_callback(safe_callback)
        else:
            future.add_done_callback(lambda f: self._active_futures.discard(f))

        return future

    async def astart(self) -> None:
        """
        Async version of start() - launches engine without blocking.
        More efficient than sync version as it doesn't need thread synchronization.
        """
        with self._state_lock:
            if self._engine is not None:
                return

        # For async start, use the current running event loop directly
        # This avoids the complexity of managing a separate background thread
        try:
            current_loop = asyncio.get_running_loop()
            # Store reference to current loop for consistency
            with self._state_lock:
                self._loop = current_loop

            # Start engine directly in current loop
            await self._start_engine()
            self._logger.debug("Async engine startup completed")

        except Exception as e:
            msg = f"Failed to launch engine at '{self.engine_path}': {e}"
            self._logger.error(msg)
            await self.astop()
            raise RuntimeError(msg) from e

    async def astop(self) -> None:
        """
        Async version of stop() - gracefully shuts down engine.
        Never raises exceptions to ensure context manager robustness.
        """
        try:
            with self._state_lock:
                self._shutdown_event.set()

            # Cancel active futures
            with self._state_lock:
                for future in list(self._active_futures):
                    if not future.done():
                        try:
                            future.cancel()
                        except Exception:
                            pass  # Ignore cancellation errors

            # Graceful engine shutdown
            if self._engine:
                try:
                    await self._shutdown_engine_gracefully()
                    self._logger.debug("Async engine shutdown completed")
                except Exception as e:
                    self._logger.debug(
                        f"Async engine shutdown completed with warnings: {e}"
                    )

            # Clean up state
            with self._state_lock:
                self._engine = None
                self._transport = None
                # Note: we don't clean up _loop here as it might be external
                self._active_futures.clear()

        except Exception as e:
            # Never raise from astop - just log
            self._logger.debug(f"Error during async stop: {e}")

    async def get_best_move_native(
        self,
        position: str | chess.Board,
        time_ms: int = 1000,
        depth: int | None = None,
    ) -> chess.Move | None:
        """
        Native async version of get_best_move - no thread synchronization overhead.
        Use this when already in an async context for best performance.

        :param position: either a FEN string or a chess.Board instance.
        :param time_ms: think time in milliseconds.
        :param depth: search depth limit (optional, overrides time if provided).
        :return: a chess.Move instance.
        :raises RuntimeError: if engine isn't started.
        :raises ValueError: if the FEN is invalid.
        :raises chess.engine.EngineTerminatedError: on engine failure.
        """
        if not self.is_running():
            raise RuntimeError("Engine is not running; call astart() first.")

        return await self._get_best_move_async(position, time_ms, depth)

    # Context manager support (synchronous)
    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    # Robust async context manager support
    async def __aenter__(self) -> Self:
        """
        Async context manager entry - starts engine with robust error handling.
        """
        try:
            await self.astart()
            return self
        except BaseException:
            # If startup fails, still attempt cleanup to prevent resource leaks
            try:
                await self._safe_cleanup()
            except Exception as cleanup_error:
                self._logger.debug(f"Cleanup during startup failure: {cleanup_error}")
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Async context manager exit - stops engine gracefully.
        Never raises exceptions to ensure robust cleanup.
        """
        try:
            await self.astop()
        except Exception as cleanup_error:
            self._logger.debug(f"Error during context cleanup: {cleanup_error}")
            # Don't raise cleanup errors - let original exception propagate

    @asynccontextmanager
    async def managed_engine(self) -> AsyncIterator[Self]:
        """
        Convenience alias for the main context manager.
        Provides a cleaner API name for users.

        Usage:
            adapter = EngineAdapter("/path/to/stockfish")
            async with adapter.managed_engine() as engine:
                move = await engine.get_best_move_native("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        """
        async with self as engine:
            yield engine

    @classmethod
    def create_with_auto_detection(
        cls, engine_name: str = "stockfish", options: dict[str, Any] | None = None
    ) -> Self:
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
            # Use a static version since this is a class method
            instructions = detector.get_installation_instructions(engine_name)
            system = detector.system
            instruction_text = instructions.get(system, instructions.get("generic", ""))
            raise RuntimeError(
                f"No {engine_name} engine found on system. Please install {engine_name}:\n\n{instruction_text}"
            )

        return cls(engine_path, options)

    @classmethod
    @asynccontextmanager
    async def create_managed(
        cls,
        engine_name: str = "stockfish",
        options: dict[str, Any] | None = None,
        engine_path: str | None = None,
    ):
        """
        Modern factory method that creates and manages an engine using async context manager.

        Usage:
            async with EngineAdapter.create_managed("stockfish", {"Threads": 4}) as adapter:
                move = await adapter.get_best_move_native(board)
                # Engine is automatically cleaned up when exiting the context

        :param engine_name: Name of the engine to detect (default: "stockfish")
        :param options: Dictionary of UCI options
        :param engine_path: Explicit path to engine (overrides auto-detection)
        :return: Async context manager yielding EngineAdapter
        :raises RuntimeError: If the engine cannot be found
        """
        if engine_path is None:
            detector = EngineDetector()
            engine_path = detector.find_engine(engine_name)

            if engine_path is None:
                instructions = detector.get_installation_instructions(engine_name)
                system = detector.system
                instruction_text = instructions.get(
                    system, instructions.get("generic", "")
                )
                raise RuntimeError(
                    f"No {engine_name} engine found on system. Please install {engine_name}:\n\n{instruction_text}"
                )

        adapter = cls(engine_path, options)
        await adapter.astart()
        try:
            yield adapter
        finally:
            await adapter.astop()

    async def _ping_engine(self) -> bool:
        """Check if engine is responsive."""
        if not self._engine:
            return False

        try:
            # Send a quick position analysis as a health check
            board = chess.Board()  # Starting position
            limit = chess.engine.Limit(time=0.001)  # Very short time limit
            await asyncio.wait_for(self._engine.analyse(board, limit), timeout=1.0)
            return True
        except Exception:
            return False

    def is_healthy(self) -> bool:
        """Check if engine is running and responsive."""
        if not self.is_running():
            return False

        try:
            if self._loop is None:
                return False
            future = asyncio.run_coroutine_threadsafe(self._ping_engine(), self._loop)
            return future.result(timeout=2.0)
        except Exception:
            return False

    # Simplified integration methods for GUI applications
    def start_simple(self) -> None:
        """
        Simplified start method using shared background loop.
        Better for GUI applications that don't want to manage their own asyncio event loop.
        """
        if self.is_running():
            return

        # Use the existing proven start() method
        self.start()
        self._logger.info("Engine started using simplified mode")

    async def _start_engine_simple(self) -> None:
        """Start engine using the shared background loop."""
        self._logger.info(f"Starting engine in simple mode: {self.engine_path}")

        try:
            self._transport, self._engine = await asyncio.wait_for(
                chess.engine.popen_uci(self.engine_path), timeout=10.0
            )

            self._logger.info(
                f"Engine started successfully: {self._engine.id if hasattr(self._engine, 'id') else 'Unknown'}"
            )

            # Configure options
            for name, val in self.options.items():
                try:
                    await self._engine.configure({name: val})
                    self._logger.debug(f"Successfully set {name}={val}")
                except Exception as e:
                    self._logger.warning(
                        f"Could not set engine option {name}={val}: {e}"
                    )

        except Exception as e:
            self._logger.error(f"Failed to start engine: {e}")
            raise RuntimeError(f"Engine startup failed: {e}") from e

    def stop_simple(self) -> None:
        """
        Simplified stop method for GUI applications.
        Uses the existing proven stop() method.
        """
        if not self.is_running():
            return

        # Use the existing proven stop() method
        self.stop()
        self._logger.info("Engine stopped using simplified mode")

    def get_best_move_simple(
        self,
        position: str | chess.Board,
        time_ms: int = 1000,
        depth: int | None = None,
    ) -> chess.Move | None:
        """
        Simplified synchronous get_best_move - convenience alias for get_best_move.
        Provides a cleaner API name for GUI applications.
        """
        if not self.is_running():
            raise RuntimeError("Engine is not running; call start_simple() first.")

        # Use the existing proven get_best_move method
        return self.get_best_move(position, time_ms, depth)

    def get_best_move_simple_async(
        self,
        position: str | chess.Board,
        time_ms: int = 1000,
        depth: int | None = None,
        callback=None,
    ):
        """
        Simplified async get_best_move with callback - convenience alias for get_best_move_async.
        Perfect for GUI applications using wx.CallAfter patterns.
        """
        if not self.is_running():
            raise RuntimeError("Engine is not running; call start_simple() first.")

        # Use the existing proven get_best_move_async method
        return self.get_best_move_async(position, time_ms, depth, callback)

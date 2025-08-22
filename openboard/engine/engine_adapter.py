import asyncio
import logging
import threading
from typing import Union, Dict, Any, Optional
from concurrent.futures import Future
import weakref

import chess
import chess.engine

from .engine_detection import EngineDetector


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
        engine_path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        callback_executor: Optional[CallbackExecutor] = None,
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

        # Thread synchronization
        self._state_lock = threading.RLock()
        self._loop_ready_event = threading.Event()
        self._shutdown_event = threading.Event()
        self._active_futures = weakref.WeakSet()

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

                    # Assign loop to instance variable (no lock needed here)
                    self._loop = loop

                    # Signal that loop is ready
                    self._loop_ready_event.set()

                    # Run the event loop with proper shutdown handling
                    try:
                        # Create a task to monitor shutdown event
                        async def monitor_shutdown():
                            while not self._shutdown_event.is_set():
                                await asyncio.sleep(0.1)
                            loop.stop()

                        # Schedule the monitor task
                        loop.create_task(monitor_shutdown())

                        # Run the event loop
                        loop.run_forever()
                    except Exception as e:
                        self._logger.error(f"Event loop error: {e}")

                except Exception as e:
                    self._logger.error(f"Event loop thread failed: {e}")
                    self._loop_ready_event.set()  # Unblock waiters even on error
                finally:
                    with self._state_lock:
                        if self._loop and not self._loop.is_closed():
                            try:
                                # Cancel all pending tasks
                                pending = asyncio.all_tasks(self._loop)
                                for task in pending:
                                    task.cancel()
                                if pending:
                                    self._loop.run_until_complete(
                                        asyncio.gather(*pending, return_exceptions=True)
                                    )
                            except Exception as e:
                                self._logger.warning(
                                    f"Error cleaning up event loop tasks: {e}"
                                )
                            finally:
                                self._loop.close()
                        self._loop = None

            self._engine_thread = threading.Thread(target=run_loop, daemon=True)
            self._engine_thread.start()

        # Wait for loop to be ready with timeout
        if not self._loop_ready_event.wait(timeout=10.0):
            # Clean up failed thread
            if self._engine_thread and self._engine_thread.is_alive():
                self._shutdown_event.set()
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
            raise RuntimeError(f"Engine executable not found: {self.engine_path}")
        except PermissionError:
            raise RuntimeError(
                f"Permission denied executing engine: {self.engine_path}"
            )
        except chess.engine.EngineTerminatedError as e:
            raise RuntimeError(f"Engine terminated during startup: {e}")

        except Exception as e:
            self._logger.error(f"Failed to start engine at '{self.engine_path}': {e}")
            raise RuntimeError(f"Engine startup failed: {e}") from e

    def _validate_board_state(self, position: Union[str, chess.Board]) -> chess.Board:
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
        self, time_ms: int, depth: Optional[int]
    ) -> chess.engine.Limit:
        """Create engine search limit from time and depth parameters."""
        if depth is not None:
            return chess.engine.Limit(depth=depth)
        else:
            return chess.engine.Limit(time=time_ms / 1000.0)

    def stop(self) -> None:
        """
        Quits the engine process and stops the async loop.
        Safe to call multiple times.
        """
        with self._state_lock:
            # Signal shutdown to prevent new operations
            self._shutdown_event.set()

        # Cancel all active futures first
        with self._state_lock:
            for future in list(self._active_futures):
                if not future.done():
                    future.cancel()

        # Phase 1: Graceful engine shutdown with proper cleanup order
        if self._loop and not self._loop.is_closed() and self._engine:
            try:
                # Schedule engine shutdown and wait for completion
                future = asyncio.run_coroutine_threadsafe(
                    self._shutdown_engine_gracefully(), self._loop
                )
                future.result(timeout=8.0)  # Allow time for proper cleanup
                self._logger.debug("Engine shutdown completed successfully")
            except Exception as e:
                # Expected during shutdown - just continue with cleanup
                self._logger.debug(
                    f"Engine shutdown completed with expected cleanup warnings: {e}"
                )
                # Continue with forced cleanup

        # Phase 2: Allow event loop to finish pending operations
        if self._loop and not self._loop.is_closed():
            try:
                # Give event loop time to finish transport cleanup
                cleanup_future = asyncio.run_coroutine_threadsafe(
                    self._finalize_cleanup(), self._loop
                )
                cleanup_future.result(timeout=2.0)
                self._logger.debug("Event loop cleanup completed")
            except Exception as e:
                # Cleanup warnings are expected during shutdown
                self._logger.debug(f"Event loop cleanup warning: {e}")
                pass  # Continue with shutdown

        # Phase 3: Stop event loop after all cleanup is done
        if self._loop and not self._loop.is_closed():
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except RuntimeError:
                pass  # Loop may already be stopped

        # Phase 4: Wait for thread termination
        if self._engine_thread and self._engine_thread.is_alive():
            self._engine_thread.join(timeout=3.0)
            if self._engine_thread.is_alive():
                self._logger.warning("Engine thread did not terminate within timeout")

        # Phase 5: Final state cleanup
        with self._state_lock:
            self._engine = None
            self._transport = None
            self._loop = None
            self._engine_thread = None
            self._active_futures.clear()

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

    async def _finalize_cleanup(self) -> None:
        """Final cleanup phase - minimal wait for pending operations."""
        try:
            # Give event loop a moment to finish any remaining I/O operations
            await asyncio.sleep(0.1)
        except Exception:
            pass  # Ignore any errors during final cleanup

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
        position: Union[str, chess.Board],
        time_ms: int = 1000,
        depth: Optional[int] = None,
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
        self, position: Union[str, chess.Board], time_ms: int, depth: Optional[int]
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
        position: Union[str, chess.Board],
        time_ms: int = 1000,
        depth: Optional[int] = None,
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
            # Use a static version since this is a class method
            instructions = detector.get_installation_instructions(engine_name)
            system = detector.system
            instruction_text = instructions.get(system, instructions.get("generic", ""))
            raise RuntimeError(
                f"No {engine_name} engine found on system. Please install {engine_name}:\n\n{instruction_text}"
            )

        return cls(engine_path, options)

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

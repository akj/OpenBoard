import asyncio
import logging
import threading
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Any, Self

import chess
import chess.engine

from .engine_detection import EngineDetector
from ..exceptions import (
    EngineInitializationError,
    EngineNotFoundError,
    EngineProcessError,
    EngineTimeoutError,
)

try:
    import wx
except ImportError:
    wx = None


class CallbackExecutor:
    """Deliver a result on the completing thread, for headless callers."""

    def execute(self, callback, *args, **kwargs):
        if callback:
            callback(*args, **kwargs)


class WxCallbackExecutor(CallbackExecutor):
    """Queue GUI callbacks on the wx event loop."""

    def execute(self, callback, *args, **kwargs):
        if not callback:
            return
        if threading.current_thread() != threading.main_thread() and wx is not None:
            try:
                if wx.GetApp() is not None:
                    wx.CallAfter(callback, *args, **kwargs)
                    return
            except RuntimeError:
                return
        callback(*args, **kwargs)


class EngineAdapter:
    """Own a UCI process and its asyncio loop on one worker thread.

    GUI callers use get_best_move_async and receive callbacks through the supplied
    executor. start, stop and get_best_move block; keep them off the GUI thread.
    Async context managers use the same worker and lifecycle as synchronous ones.
    """

    STARTUP_TIMEOUT = 10.0
    SEARCH_GRACE = 5.0
    SHUTDOWN_TIMEOUT = 2.0

    def __init__(
        self,
        engine_path: str | list[str] | None = None,
        options: dict[str, Any] | None = None,
        callback_executor: CallbackExecutor | None = None,
    ):
        if engine_path is None:
            detector = EngineDetector()
            engine_path = detector.find_engine("stockfish")
            if engine_path is None:
                instructions = detector.get_installation_instructions("stockfish")
                instruction = instructions.get(
                    detector.system, instructions.get("generic", "")
                )
                raise EngineNotFoundError(
                    f"Stockfish. Please install Stockfish: {instruction}"
                )
        self.engine_path = engine_path
        self.options = dict(options or {})
        self._engine: chess.engine.Protocol | None = None
        self._transport: asyncio.SubprocessTransport | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._engine_thread: threading.Thread | None = None
        self._search_lock: asyncio.Lock | None = None
        self._state_lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()
        self._loop_ready_event = threading.Event()
        self._shutdown_event = threading.Event()
        self._active_futures: set[Future] = set()
        self._logger = logging.getLogger(__name__)
        self._callback_executor = callback_executor or (
            WxCallbackExecutor() if wx is not None else CallbackExecutor()
        )

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._search_lock = asyncio.Lock()
        self._loop_ready_event.set()
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    def start(self) -> None:
        """Start the engine, serializing concurrent lifecycle calls."""
        with self._lifecycle_lock:
            if self.is_running():
                return
            if self._engine_thread is not None:
                self.stop()
            self._shutdown_event.clear()
            self._loop_ready_event.clear()
            self._engine_thread = threading.Thread(
                target=self._run_loop, name="OpenBoard engine", daemon=True
            )
            self._engine_thread.start()
            if not self._loop_ready_event.wait(timeout=self.STARTUP_TIMEOUT):
                raise EngineInitializationError("Engine event loop did not start")
            loop = self._loop
            if loop is None:
                raise EngineInitializationError("Engine event loop is unavailable")
            future = asyncio.run_coroutine_threadsafe(self._start_engine(), loop)
            try:
                future.result(timeout=self.STARTUP_TIMEOUT + 1)
            except FutureTimeoutError as error:
                future.cancel()
                self.stop()
                raise EngineTimeoutError(
                    "startup", int((self.STARTUP_TIMEOUT + 1) * 1000)
                ) from error
            except Exception:
                future.cancel()
                self.stop()
                raise

    async def _start_engine(self) -> None:
        try:
            self._transport, self._engine = await asyncio.wait_for(
                chess.engine.popen_uci(self.engine_path), timeout=self.STARTUP_TIMEOUT
            )
            for name, value in self.options.items():
                try:
                    await asyncio.wait_for(
                        self._engine.configure({name: value}),
                        timeout=self.STARTUP_TIMEOUT,
                    )
                except chess.engine.EngineError as error:
                    self._logger.warning("Engine rejected option %s: %s", name, error)
        except FileNotFoundError as error:
            raise EngineNotFoundError(f"Engine at {self.engine_path}") from error
        except chess.engine.EngineTerminatedError as error:
            raise EngineInitializationError(
                f"Engine terminated during startup: {error}"
            ) from error
        except Exception as error:
            raise EngineProcessError(f"Engine startup failed: {error}") from error

    def stop(self) -> None:
        """Cancel searches, quit the process, then close and join its worker loop."""
        if threading.current_thread() is self._engine_thread:
            raise RuntimeError(
                "Cannot synchronously stop the engine from its callback thread"
            )
        with self._lifecycle_lock:
            with self._state_lock:
                self._shutdown_event.set()
                futures = list(self._active_futures)
                loop = self._loop
                thread = self._engine_thread
            for future in futures:
                future.cancel()
            if loop is not None and loop.is_running():
                shutdown = asyncio.run_coroutine_threadsafe(
                    self._shutdown_engine(), loop
                )
                try:
                    shutdown.result(timeout=self.SHUTDOWN_TIMEOUT + 1)
                except Exception as error:
                    self._logger.warning("Engine shutdown failed: %s", error)
                    shutdown.cancel()
                finally:
                    loop.call_soon_threadsafe(loop.stop)
            if thread is not None:
                thread.join(timeout=self.SHUTDOWN_TIMEOUT + 1)
                if thread.is_alive():
                    raise EngineProcessError("Engine worker did not stop")
            with self._state_lock:
                self._engine = None
                self._transport = None
                self._loop = None
                self._engine_thread = None
                self._search_lock = None
                self._active_futures.clear()

    async def _shutdown_engine(self) -> None:
        try:
            if self._engine is not None:
                await asyncio.wait_for(
                    self._engine.quit(), timeout=self.SHUTDOWN_TIMEOUT
                )
        except (TimeoutError, chess.engine.EngineError) as error:
            self._logger.debug("Engine quit failed: %s", error)
        finally:
            if self._transport is not None:
                self._transport.close()
            # Let subprocess connection-lost callbacks run before the loop closes.
            if self._engine is not None:
                returncode = getattr(self._engine, "returncode", None)
                if returncode is not None:
                    await asyncio.wait_for(
                        asyncio.shield(returncode), timeout=self.SHUTDOWN_TIMEOUT
                    )

    def is_running(self) -> bool:
        with self._state_lock:
            return (
                self._engine is not None
                and self._loop is not None
                and self._loop.is_running()
                and not self._shutdown_event.is_set()
                and self._transport is not None
                and self._transport.get_returncode() is None
            )

    def _validate_board_state(self, position: str | chess.Board) -> chess.Board:
        if isinstance(position, str):
            board = chess.Board(position)
        elif isinstance(position, chess.Board):
            board = position.copy()
        else:
            raise ValueError("Position must be a FEN string or chess.Board")
        if not board.is_valid():
            raise ValueError("Invalid chess position")
        return board

    def _create_engine_limit(
        self, time_ms: int, depth: int | None
    ) -> chess.engine.Limit:
        if time_ms <= 0 or (depth is not None and depth <= 0):
            raise ValueError("Engine search time and depth must be positive")
        return chess.engine.Limit(time=time_ms / 1000.0, depth=depth)

    async def _get_best_move_async(self, board, time_ms, depth):
        if board.is_game_over():
            return None
        engine, search_lock = self._engine, self._search_lock
        if engine is None or search_lock is None:
            raise EngineProcessError("Engine is unavailable")
        # python-chess cancels a previous command when another starts. Serialize
        # searches so a hint cannot cancel a computer move on the same engine.
        async with search_lock:
            try:
                result = await asyncio.wait_for(
                    engine.play(board, self._create_engine_limit(time_ms, depth)),
                    timeout=time_ms / 1000.0 + self.SEARCH_GRACE,
                )
            except TimeoutError as error:
                raise EngineTimeoutError(
                    "get_best_move", int(time_ms + self.SEARCH_GRACE * 1000)
                ) from error
            except chess.engine.EngineError as error:
                raise EngineProcessError(
                    f"Engine failed to compute best move: {error}"
                ) from error
            if result.move is not None and result.move not in board.legal_moves:
                raise EngineProcessError(
                    f"Engine returned an illegal move: {result.move}"
                )
            return result.move

    def get_best_move_async(
        self,
        position: str | chess.Board,
        time_ms: int = 1000,
        depth: int | None = None,
        callback=None,
    ) -> Future:
        """Snapshot a position before crossing threads and submit a cancellable search."""
        with self._state_lock:
            loop = self._loop
            if not self.is_running() or loop is None:
                raise RuntimeError("Engine is not running; call start() first.")
            board = self._validate_board_state(position)
            self._create_engine_limit(time_ms, depth)
            future = asyncio.run_coroutine_threadsafe(
                self._get_best_move_async(board, time_ms, depth), loop
            )
            self._active_futures.add(future)

        def completed(result):
            with self._state_lock:
                self._active_futures.discard(result)
                if result.cancelled() or self._shutdown_event.is_set():
                    return
            if callback is not None:
                value = result.exception() or result.result()
                try:
                    self._callback_executor.execute(callback, value)
                except Exception:
                    self._logger.exception("Engine result callback failed")

        future.add_done_callback(completed)
        return future

    def get_best_move(self, position, time_ms=1000, depth=None) -> chess.Move | None:
        """Block for a move. GUI commands must use get_best_move_async instead."""
        if threading.current_thread() is self._engine_thread:
            raise RuntimeError(
                "Cannot wait for an engine search from its callback thread"
            )
        future = self.get_best_move_async(position, time_ms, depth)
        timeout = time_ms / 1000.0 + self.SEARCH_GRACE + 1
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError as error:
            future.cancel()
            raise EngineTimeoutError("get_best_move", int(timeout * 1000)) from error

    async def astart(self) -> None:
        try:
            await asyncio.to_thread(self.start)
        except asyncio.CancelledError:
            await self.astop()
            raise

    async def astop(self) -> None:
        await asyncio.to_thread(self.stop)

    async def get_best_move_native(self, position, time_ms=1000, depth=None):
        return await asyncio.wrap_future(
            self.get_best_move_async(position, time_ms, depth)
        )

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    async def __aenter__(self) -> Self:
        try:
            await self.astart()
        except BaseException:
            await self.astop()
            raise
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.astop()

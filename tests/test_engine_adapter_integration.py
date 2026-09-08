"""Exercise the real worker loop with a deterministic asynchronous engine."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, Mock

import chess
import chess.engine
import pytest

from openboard.engine.engine_adapter import CallbackExecutor, EngineAdapter
from openboard.exceptions import (
    EngineNotFoundError,
    EngineProcessError,
    EngineTimeoutError,
)


class RecordingEngine:
    def __init__(self, delay=0):
        self.delay = delay
        self.calls = []
        self.loops = []
        self.active = 0
        self.max_active = 0
        self.cancelled = threading.Event()
        self.entered = threading.Event()
        self.quit_called = False

    async def configure(self, options):
        self.calls.append(options)
        self.loops.append(asyncio.get_running_loop())

    async def play(self, board, limit):
        self.calls.append((board, limit))
        self.loops.append(asyncio.get_running_loop())
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.entered.set()
        try:
            await asyncio.sleep(self.delay)
            return chess.engine.PlayResult(next(iter(board.legal_moves), None), None)
        except asyncio.CancelledError:
            self.cancelled.set()
            raise
        finally:
            self.active -= 1

    async def quit(self):
        self.loops.append(asyncio.get_running_loop())
        self.quit_called = True


@pytest.fixture
def engine_setup(monkeypatch):
    engine = RecordingEngine()
    transport = Mock()
    transport.get_returncode.return_value = None
    monkeypatch.setattr(
        chess.engine, "popen_uci", AsyncMock(return_value=(transport, engine))
    )
    adapter = EngineAdapter(
        "test-engine", options={"Hash": 32}, callback_executor=CallbackExecutor()
    )
    yield adapter, engine, transport
    adapter.stop()


def test_lifecycle_quits_and_closes_transport_before_loop(engine_setup):
    adapter, engine, transport = engine_setup
    adapter.start()
    worker = adapter._engine_thread
    loop = adapter._loop
    transport.close.side_effect = lambda: (
        pytest.fail("transport closed after loop") if loop.is_closed() else None
    )
    assert adapter.get_best_move(chess.Board()) in chess.Board().legal_moves
    adapter.stop()
    assert engine.quit_called
    transport.close.assert_called_once()
    assert not worker.is_alive()
    assert loop.is_closed()
    assert len(set(engine.loops)) == 1
    assert not adapter.is_running()
    adapter.stop()


def test_concurrent_searches_do_not_cancel_each_other(engine_setup):
    adapter, engine, _ = engine_setup
    engine.delay = 0.01
    with adapter:
        with ThreadPoolExecutor(max_workers=4) as pool:
            moves = list(
                pool.map(lambda _: adapter.get_best_move(chess.Board()), range(8))
            )
    assert all(move in chess.Board().legal_moves for move in moves)
    assert engine.max_active == 1
    assert not engine.cancelled.is_set()


def test_board_snapshot_is_taken_before_submission(engine_setup):
    adapter, engine, _ = engine_setup
    engine.delay = 0.01
    board = chess.Board()
    board.push_uci("e2e4")
    original = board.copy()
    with adapter:
        future = adapter.get_best_move_async(board)
        board.push_uci("e7e5")
        assert future.result(timeout=2) in original.legal_moves
    submitted, _ = engine.calls[-1]
    assert submitted.fen() == original.fen()
    assert submitted.move_stack == original.move_stack


def test_cancel_stops_search_without_notifying_callback(engine_setup):
    adapter, engine, _ = engine_setup
    engine.delay = 10
    callback = Mock()
    with adapter:
        future = adapter.get_best_move_async(chess.Board(), callback=callback)
        assert engine.entered.wait(timeout=2)
        assert future.cancel()
        assert engine.cancelled.wait(timeout=2)
    callback.assert_not_called()


def test_stop_cancels_search_and_quits_process(engine_setup):
    adapter, engine, transport = engine_setup
    engine.delay = 10
    adapter.start()
    future = adapter.get_best_move_async(chess.Board())
    assert engine.entered.wait(timeout=2)
    adapter.stop()
    assert future.cancelled()
    assert engine.cancelled.is_set()
    assert engine.quit_called
    transport.close.assert_called_once()


def test_async_search_has_a_timeout_and_cancels_engine(engine_setup, monkeypatch):
    adapter, engine, _ = engine_setup
    engine.delay = 10
    monkeypatch.setattr(adapter, "SEARCH_GRACE", 0.01)
    with adapter:
        future = adapter.get_best_move_async(chess.Board(), time_ms=1)
        with pytest.raises(EngineTimeoutError):
            future.result(timeout=2)
    assert engine.cancelled.is_set()


def test_search_uses_time_and_depth_limits(engine_setup):
    adapter, engine, _ = engine_setup
    with adapter:
        adapter.get_best_move(chess.Board(), time_ms=125, depth=2)
    _, limit = engine.calls[-1]
    assert limit.time == 0.125
    assert limit.depth == 2


@pytest.mark.parametrize("position", ["invalid", "8/8/8/8/8/8/8/8 w - - 0 1"])
def test_invalid_position_never_reaches_engine(engine_setup, position):
    adapter, engine, _ = engine_setup
    with adapter:
        with pytest.raises(ValueError):
            adapter.get_best_move_async(position)
    assert engine.calls == [{"Hash": 32}]


def test_terminal_position_does_not_start_search(engine_setup):
    adapter, engine, _ = engine_setup
    with adapter:
        assert adapter.get_best_move("4k3/8/8/8/8/8/8/4K3 w - - 0 1") is None
    assert engine.calls == [{"Hash": 32}]


def test_callback_delivers_failure(engine_setup):
    adapter, engine, _ = engine_setup
    engine.play = AsyncMock(side_effect=chess.engine.EngineTerminatedError("crashed"))
    delivered = threading.Event()
    results = []

    def callback(result):
        results.append(result)
        delivered.set()

    with adapter:
        adapter.get_best_move_async(chess.Board(), callback=callback)
        assert delivered.wait(timeout=2)
    assert isinstance(results[0], EngineProcessError)


@pytest.mark.asyncio
async def test_async_context_restarts_without_changing_protocol_loop(engine_setup):
    adapter, engine, _ = engine_setup
    caller_loop = asyncio.get_running_loop()
    for _ in range(2):
        engine.loops.clear()
        async with adapter:
            assert (
                await adapter.get_best_move_native(chess.Board())
                in chess.Board().legal_moves
            )
            loop = adapter._loop
            assert loop is not caller_loop
        assert set(engine.loops) == {loop}
        assert loop.is_closed()
        assert caller_loop.is_running()


@pytest.mark.asyncio
async def test_async_waiter_cancellation_cancels_worker_search(engine_setup):
    adapter, engine, _ = engine_setup
    engine.delay = 10
    async with adapter:
        task = asyncio.create_task(adapter.get_best_move_native(chess.Board()))
        assert await asyncio.to_thread(engine.entered.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await asyncio.to_thread(engine.cancelled.wait, 2)


@pytest.mark.parametrize(
    "error, expected",
    [
        (FileNotFoundError("missing"), EngineNotFoundError),
        (PermissionError("denied"), EngineProcessError),
    ],
)
def test_start_failure_releases_worker(monkeypatch, error, expected):
    monkeypatch.setattr(chess.engine, "popen_uci", AsyncMock(side_effect=error))
    adapter = EngineAdapter("missing")
    with pytest.raises(expected):
        adapter.start()
    assert not adapter.is_running()
    assert adapter._engine_thread is None


def test_start_timeout_releases_worker(monkeypatch):
    cancelled = threading.Event()

    async def start(*args):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    monkeypatch.setattr(chess.engine, "popen_uci", start)
    adapter = EngineAdapter("hanging")
    adapter.STARTUP_TIMEOUT = 0.02
    with pytest.raises(EngineProcessError):
        adapter.start()
    assert cancelled.is_set()
    assert adapter._engine_thread is None


def test_total_startup_timeout_cleans_up_and_reports_engine_error(engine_setup):
    adapter, engine, transport = engine_setup
    adapter.STARTUP_TIMEOUT = 0.2
    adapter.options = {f"option_{index}": index for index in range(100)}
    cancelled = threading.Event()

    async def configure(options):
        try:
            # Each option fits its deadline, but configuring them all exceeds
            # the caller's total startup budget.
            await asyncio.sleep(0.02)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    engine.configure = configure
    with pytest.raises(EngineTimeoutError, match="startup"):
        adapter.start()
    assert cancelled.is_set()
    assert engine.quit_called
    transport.close.assert_called_once()
    assert adapter._engine_thread is None
    assert not adapter.is_running()


def test_stop_during_startup_waits_then_releases_engine(engine_setup, monkeypatch):
    adapter, engine, transport = engine_setup
    launching = threading.Event()
    release_launch = threading.Event()
    stopping = threading.Event()

    async def launch(*args):
        launching.set()
        while not release_launch.is_set():
            await asyncio.sleep(0.001)
        return transport, engine

    def stop():
        stopping.set()
        adapter.stop()

    monkeypatch.setattr(chess.engine, "popen_uci", launch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        started = pool.submit(adapter.start)
        try:
            assert launching.wait(timeout=2)
            stopped = pool.submit(stop)
            assert stopping.wait(timeout=2)
        finally:
            release_launch.set()
        started.result(timeout=2)
        stopped.result(timeout=2)
    assert engine.quit_called
    transport.close.assert_called_once()
    assert adapter._engine_thread is None
    assert not adapter.is_running()

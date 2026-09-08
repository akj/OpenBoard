"""Exercise the installed Stockfish process with the application's engine adapter."""

import shutil
import threading

import chess
import pytest

from openboard.engine.engine_adapter import CallbackExecutor, EngineAdapter


STOCKFISH = shutil.which("stockfish")


@pytest.mark.skipif(STOCKFISH is None, reason="Stockfish is not on PATH")
def test_stockfish_search_cancellation_and_shutdown(monkeypatch):
    assert STOCKFISH is not None
    board = chess.Board()
    board.push_uci("e2e4")
    adapter = EngineAdapter(
        STOCKFISH,
        options={"Threads": 1, "Hash": 16},
        callback_executor=CallbackExecutor(),
    )
    cancelled_results = []

    with adapter:
        protocol = adapter._engine
        transport = adapter._transport
        worker = adapter._engine_thread
        loop = adapter._loop
        assert protocol is not None
        assert transport is not None
        assert worker is not None
        assert loop is not None
        move = adapter.get_best_move(board, time_ms=100, depth=5)
        assert move is not None and move in board.legal_moves

        search_started = threading.Event()
        send_line = protocol.send_line

        def record_search(line):
            send_line(line)
            if line.startswith("go "):
                search_started.set()

        monkeypatch.setattr(protocol, "send_line", record_search)
        pending = adapter.get_best_move_async(
            board, time_ms=30_000, callback=cancelled_results.append
        )
        assert search_started.wait(timeout=10)
        assert pending.cancel()
        next_move = adapter.get_best_move(board, time_ms=100, depth=5)
        assert next_move is not None and next_move in board.legal_moves
        assert pending.cancelled()
        assert cancelled_results == []

    assert transport.get_returncode() == 0
    assert not worker.is_alive()
    assert loop.is_closed()
    assert not adapter.is_running()

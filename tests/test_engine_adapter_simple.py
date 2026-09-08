"""UCI subprocess integration, independent of a system Stockfish installation."""

import sys
from pathlib import Path

import chess

from openboard.engine.engine_adapter import EngineAdapter


def test_uci_subprocess_receives_history_and_exits_on_stop(tmp_path: Path):
    commands = tmp_path / "commands.txt"
    script = tmp_path / "engine.py"
    script.write_text(
        "import sys\n"
        f"log = open({str(commands)!r}, 'w', buffering=1)\n"
        "for line in sys.stdin:\n"
        "    line = line.strip()\n"
        "    log.write(line + '\\n')\n"
        "    if line == 'uci':\n"
        "        print('id name TestEngine\\nuciok', flush=True)\n"
        "    elif line == 'isready':\n"
        "        print('readyok', flush=True)\n"
        "    elif line.startswith('go'):\n"
        "        print('bestmove e7e5', flush=True)\n"
        "    elif line == 'quit':\n"
        "        break\n"
    )
    adapter = EngineAdapter([sys.executable, "-u", str(script)])
    board = chess.Board()
    board.push_uci("e2e4")
    with adapter:
        transport = adapter._transport
        loop = adapter._loop
        assert transport is not None
        assert loop is not None
        assert adapter.get_best_move(board, time_ms=25, depth=2) == chess.Move.from_uci(
            "e7e5"
        )
    assert transport.get_returncode() == 0
    assert loop.is_closed()
    transcript = commands.read_text()
    assert "position startpos moves e2e4" in transcript
    assert "go depth 2 movetime 25" in transcript
    assert transcript.endswith("quit\n")

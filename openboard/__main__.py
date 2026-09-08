"""Launch the app or check that a packaged build can load its dependencies."""

import argparse
import importlib
import json
import sys


def startup_smoke_check() -> dict[str, str | int]:
    """Load the application and make a move without opening a window or speaking."""
    if sys.platform == "linux":
        importlib.import_module("speechd")
    elif sys.platform == "darwin":
        importlib.import_module("appscript")
        importlib.import_module("AppKit")
    for module in (
        "openboard.views.views",
        "openboard.engine.engine_adapter",
        "openboard.config.settings",
        "accessible_output3.outputs.auto",
    ):
        importlib.import_module(module)

    import chess

    from openboard.models.board_state import BoardState

    state = BoardState()
    legal_moves = state.legal_moves()
    move = chess.Move.from_uci("e2e4")
    state.make_move(move)
    if state.board.peek() != move or len(legal_moves) != 20:
        raise RuntimeError("Chess move smoke check failed")
    return {"check": "startup", "status": "ok", "legal_moves": 20, "move": "e2e4"}


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenBoard accessible chess")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Check startup and chess logic without opening the GUI or speaking",
    )
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps(startup_smoke_check()))
        return

    from openboard.views.views import main as run_app

    run_app()


if __name__ == "__main__":
    main()

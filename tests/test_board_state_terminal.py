"""Tests for BoardState terminal states and signal emissions.

Uses deterministic FEN positions from conftest.py for stalemate and insufficient
material, and constructs FEN strings directly for checkmate, fifty-move, and
in-progress states. (ref: DL-001, DL-002)
"""

import pytest
import chess

from openboard.models.board_state import BoardState


class TestBoardStateTerminalStates:
    """Tests for game_status() return values covering all terminal states."""

    def test_game_status_checkmate(self):
        # Fool's mate: white is already mated in this position
        bs = BoardState("rnb1kbnr/pppp1ppp/4p3/8/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
        assert bs.game_status() == "Checkmate"

    def test_game_status_stalemate(self, stalemate_fen):
        bs = BoardState(stalemate_fen)
        assert bs.game_status() == "Stalemate"

    def test_game_status_insufficient_material(self, insufficient_material_fen):
        bs = BoardState(insufficient_material_fen)
        assert bs.game_status() == "Draw by insufficient material"

    def test_game_status_fifty_move_rule(self):
        # Manufacture a fifty-move position using halfmove clock in FEN
        # KR vs K - kings and rook but halfmove clock at 100 (fifty-move claimable)
        bs = BoardState("8/8/8/8/8/5k2/8/4K1R1 w - - 100 150")
        assert bs.game_status() == "Draw by fifty-move rule"

    def test_game_status_in_progress(self):
        bs = BoardState()
        assert bs.game_status() == "In progress"


class TestBoardStateLoadPgn:
    """Tests for load_pgn signal emissions."""

    def test_load_pgn_emits_move_made_for_each_move(self):
        bs = BoardState()
        moves_received = []

        def on_move(sender, move=None, **kw):
            moves_received.append(move)

        bs.move_made.connect(on_move, weak=False)
        bs.load_pgn("1. e4 e5 2. Nf3 Nc6 *")
        # 4 moves played; move_made emits once per move
        move_objects = [m for m in moves_received if m is not None]
        assert len(move_objects) == 4

    def test_load_pgn_emits_final_status_changed(self):
        bs = BoardState()
        statuses = []

        def on_status(sender, status=None, **kw):
            statuses.append(status)

        bs.status_changed.connect(on_status, weak=False)
        bs.load_pgn("1. e4 e5 *")
        assert len(statuses) >= 1
        assert statuses[-1] == "In progress"

    def test_load_pgn_with_invalid_pgn_raises_value_error(self):
        bs = BoardState()
        # Empty string causes chess.pgn.read_game to return None, triggering ValueError
        with pytest.raises(ValueError):
            bs.load_pgn("")


class TestBoardStateUndoVerifiesPosition:
    """Tests verifying undo restores piece positions, not just stack length."""

    def test_undo_move_restores_piece_positions(self):
        bs = BoardState()
        bs.make_move(chess.Move.from_uci("e2e4"))
        bs.undo_move()
        # E4 must be empty after undo
        assert bs.board.piece_at(chess.E4) is None
        # E2 must have a white pawn restored
        piece = bs.board.piece_at(chess.E2)
        assert piece is not None
        assert piece.piece_type == chess.PAWN
        assert piece.color == chess.WHITE


class TestBoardStateSignals:
    """Tests for signal emission correctness."""

    def test_make_move_emits_move_made_with_correct_move_object(self):
        bs = BoardState()
        received_moves = []

        def on_move(sender, move=None, **kw):
            received_moves.append(move)

        bs.move_made.connect(on_move, weak=False)
        move = chess.Move.from_uci("e2e4")
        bs.make_move(move)
        assert move in received_moves

    def test_make_move_emits_status_changed(self):
        bs = BoardState()
        statuses = []

        def on_status(sender, status=None, **kw):
            statuses.append(status)

        bs.status_changed.connect(on_status, weak=False)
        bs.make_move(chess.Move.from_uci("e2e4"))
        assert len(statuses) >= 1

    def test_undo_move_emits_move_undone_with_correct_move_object(self):
        bs = BoardState()
        move = chess.Move.from_uci("e2e4")
        bs.make_move(move)
        undone_moves = []

        def on_undone(sender, move=None, **kw):
            undone_moves.append(move)

        bs.move_undone.connect(on_undone, weak=False)
        bs.undo_move()
        assert move in undone_moves

    def test_load_fen_emits_move_made_with_none_and_status_changed(self):
        bs = BoardState()
        move_events = []
        status_events = []

        def on_move(sender, move=None, **kw):
            move_events.append(move)

        def on_status(sender, status=None, **kw):
            status_events.append(status)

        bs.move_made.connect(on_move, weak=False)
        bs.status_changed.connect(on_status, weak=False)
        bs.load_fen(chess.STARTING_FEN)
        assert None in move_events
        assert len(status_events) >= 1

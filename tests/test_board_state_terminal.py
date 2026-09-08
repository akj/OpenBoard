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

    def test_claimable_fifty_move_draw_does_not_end_game(self):
        # Manufacture a fifty-move position using halfmove clock in FEN
        # KR vs K - kings and rook but halfmove clock at 100 (fifty-move claimable)
        bs = BoardState("8/8/8/8/8/5k2/8/4K1R1 w - - 100 150")
        assert bs.game_status() == "In progress"
        assert bs.board.can_claim_fifty_moves()

    def test_game_status_in_progress(self):
        bs = BoardState()
        assert bs.game_status() == "In progress"


class TestBoardStateLoadPgn:
    """Tests for load_pgn signal emissions."""

    def test_load_pgn_emits_one_completed_position(self):
        bs = BoardState()
        moves_received = []

        def on_move(sender, move=None, **kw):
            moves_received.append(move)

        bs.move_made.connect(on_move, weak=False)
        bs.load_pgn("1. e4 e5 2. Nf3 Nc6 *")
        assert moves_received == [None]
        assert len(bs.board.move_stack) == 4

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


class TestBoardRefProperty:
    """Verifies TD-13 / CONCERNS.md Performance #3: BoardState.board_ref is a live read-only reference."""

    def test_board_ref_returns_live_reference(self):
        """Verifies D-18: board_ref returns self._board (no copy)."""
        board_state = BoardState()
        ref_one = board_state.board_ref
        ref_two = board_state.board_ref
        assert ref_one is board_state._board, (
            "board_ref must return the live underlying chess.Board"
        )
        assert ref_two is ref_one, (
            "board_ref must be idempotent (same object on every call)"
        )

    def test_board_property_still_returns_copy(self):
        """Verifies D-18: BoardState.board snapshot semantics are preserved."""
        board_state = BoardState()
        snapshot = board_state.board
        assert snapshot is not board_state._board, (
            "board property must keep returning a copy"
        )


def test_invalid_pgn_does_not_replace_the_current_game():
    state = BoardState()
    state.make_move(chess.Move.from_uci("d2d4"))
    previous = state.board
    events = []
    state.move_made.connect(lambda sender, **kw: events.append(kw), weak=False)
    with pytest.raises(ValueError, match="Invalid PGN"):
        state.load_pgn("1. e4 e5 2. Bh6 *")
    assert state.board == previous
    assert state.board.move_stack == previous.move_stack
    assert events == []


def test_pgn_setup_position_and_history_survive_import():
    state = BoardState()
    state.load_pgn('[SetUp "1"]\n[FEN "4k3/8/8/8/8/8/8/R3K3 b - - 0 4"]\n\n4... Kf7 *')
    assert state.board.piece_at(chess.F7) == chess.Piece(chess.KING, chess.BLACK)
    state.undo_move()
    assert state.board.fen() == "4k3/8/8/8/8/8/8/R3K3 b - - 0 4"


def test_automatic_draws_end_the_game():
    state = BoardState("8/8/8/8/8/5k2/8/4K1R1 w - - 150 150")
    assert state.game_status() == "Draw by seventy-five-move rule"
    state = BoardState()
    for move in ["g1f3", "g8f6", "f3g1", "f6g8"] * 4:
        state.make_move(chess.Move.from_uci(move))
    assert state.game_status() == "Draw by fivefold repetition"


def test_move_event_snapshot_does_not_copy_entire_history():
    state = BoardState()
    state.make_move(chess.Move.from_uci("e2e4"))
    events = []
    state.move_made.connect(lambda sender, **kw: events.append(kw), weak=False)
    state.make_move(chess.Move.from_uci("e7e5"))
    snapshot = events[0]["old_board"]
    assert snapshot.turn == chess.BLACK
    assert snapshot.is_legal(chess.Move.from_uci("e7e5"))
    assert snapshot.move_stack == []
    assert len(state.board.move_stack) == 2

import pytest
import chess
from openboard.models.game import Game
from openboard.models.board_state import BoardState


class DummyEngineAdapter:
    def __init__(self):
        self.last_fen = None
        self.last_time_ms = None
        self.return_move = chess.Move.from_uci("e2e4")

    def get_best_move(self, fen, time_ms=1000):
        self.last_fen = fen
        self.last_time_ms = time_ms
        return self.return_move


def test_boardstate_make_and_undo_move():
    bs = BoardState()
    move = chess.Move.from_uci("e2e4")
    bs.make_move(move)
    assert bs.board.move_stack[-1] == move
    bs.undo_move()
    assert len(bs.board.move_stack) == 0


def test_boardstate_illegal_move():
    bs = BoardState()
    move = chess.Move.from_uci("e2e5")  # illegal in starting position
    with pytest.raises(ValueError):
        bs.make_move(move)


def test_game_apply_move():
    game = Game()
    game.apply_move(chess.E2, chess.E4)
    piece = game.board_state.board.piece_at(chess.E4)
    assert piece is not None and piece.symbol().lower() == "p"


def test_game_request_hint_emits_signal(monkeypatch):
    class FakeEngineAdapter:
        def __init__(self):
            self.last_fen = None
            self.last_time_ms = None
            self.return_move = chess.Move.from_uci("e2e4")

        def get_best_move(self, fen, time_ms=1000):
            self.last_fen = fen
            self.last_time_ms = time_ms
            return self.return_move

    fake_engine = FakeEngineAdapter()
    game = Game(engine_adapter=fake_engine)
    moves = []

    def on_hint(sender, move):
        moves.append(move)

    game.hint_ready.connect(on_hint)
    result = game.request_hint()
    assert result == fake_engine.return_move
    assert moves[0] == fake_engine.return_move


def test_game_request_hint_no_engine():
    game = Game(engine_adapter=None)
    with pytest.raises(RuntimeError):
        game.request_hint()


def test_pawn_promotion_default_queen():
    """Test that pawn promotion defaults to queen when no promotion specified."""
    game = Game()
    # Set up position with white pawn on 7th rank ready to promote
    fen = "8/7P/8/8/8/8/8/8 w - - 0 1"
    game.board_state.load_fen(fen)
    
    # Move pawn to 8th rank without specifying promotion piece
    game.apply_move(chess.H7, chess.H8)
    
    # Should automatically promote to queen
    promoted_piece = game.board_state.board.piece_at(chess.H8)
    assert promoted_piece is not None
    assert promoted_piece.piece_type == chess.QUEEN
    assert promoted_piece.color == chess.WHITE


def test_pawn_promotion_explicit_piece():
    """Test explicit pawn promotion to different pieces."""
    for promotion_piece in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]:
        game = Game()
        # Set up position with white pawn on 7th rank ready to promote
        fen = "8/7P/8/8/8/8/8/8 w - - 0 1"
        game.board_state.load_fen(fen)
        
        # Move pawn to 8th rank with explicit promotion
        game.apply_move(chess.H7, chess.H8, promotion=promotion_piece)
        
        # Should promote to specified piece
        promoted_piece = game.board_state.board.piece_at(chess.H8)
        assert promoted_piece is not None
        assert promoted_piece.piece_type == promotion_piece
        assert promoted_piece.color == chess.WHITE



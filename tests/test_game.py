import pytest
import chess
from unittest.mock import Mock
from openboard.models.game import Game
from openboard.models.board_state import BoardState
from openboard.models.opening_book import OpeningBook
from openboard.exceptions import IllegalMoveError, EngineError


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
    # Verify board squares reflect the undo, not just stack metadata.
    assert bs.board.piece_at(chess.E4) is None
    piece_at_e2 = bs.board.piece_at(chess.E2)
    assert piece_at_e2 is not None
    assert piece_at_e2.piece_type == chess.PAWN
    assert piece_at_e2.color == chess.WHITE


def test_boardstate_illegal_move():
    bs = BoardState()
    move = chess.Move.from_uci("e2e5")  # illegal in starting position
    with pytest.raises(IllegalMoveError):
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
    game = Game(engine_adapter=fake_engine)  # type: ignore
    moves = []

    def on_hint(sender, move):
        moves.append(move)

    game.hint_ready.connect(on_hint)
    result = game.request_hint()
    assert result == fake_engine.return_move
    assert moves[0] == fake_engine.return_move


def test_game_request_hint_no_engine():
    game = Game(engine_adapter=None)
    with pytest.raises(EngineError):
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


def test_request_book_move_no_book():
    """Test request_book_move returns None when no opening book is loaded."""
    game = Game()
    result = game.request_book_move()
    assert result is None


def test_request_book_move_with_book():
    """Test request_book_move returns move when opening book has moves."""
    mock_book = Mock(spec=OpeningBook)
    mock_book.is_loaded = True
    expected_move = chess.Move.from_uci("e2e4")
    mock_book.get_move.return_value = expected_move

    game = Game(opening_book=mock_book)
    result = game.request_book_move()

    assert result == expected_move
    mock_book.get_move.assert_called_once_with(game.board_state.board, minimum_weight=1)


def test_has_book_moves_no_book():
    """Test has_book_moves returns False when no opening book is loaded."""
    game = Game()
    assert game.has_book_moves() is False


def test_has_book_moves_book_not_loaded():
    """Test has_book_moves returns False when opening book exists but is not loaded."""
    mock_book = Mock(spec=OpeningBook)
    mock_book.is_loaded = False

    game = Game(opening_book=mock_book)
    assert game.has_book_moves() is False


def test_has_book_moves_with_moves():
    """Test has_book_moves returns True when opening book has moves for current position."""
    mock_book = Mock(spec=OpeningBook)
    mock_book.is_loaded = True
    mock_book.get_move.return_value = chess.Move.from_uci("e2e4")

    game = Game(opening_book=mock_book)
    assert game.has_book_moves() is True


def test_has_book_moves_no_moves():
    """Test has_book_moves returns False when opening book has no moves for current position."""
    mock_book = Mock(spec=OpeningBook)
    mock_book.is_loaded = True
    mock_book.get_move.return_value = None

    game = Game(opening_book=mock_book)
    assert game.has_book_moves() is False


def test_has_book_moves_exception_handling():
    """Test has_book_moves returns False when an exception occurs during lookup."""
    mock_book = Mock(spec=OpeningBook)
    mock_book.is_loaded = True
    mock_book.get_move.side_effect = Exception("Book error")

    game = Game(opening_book=mock_book)
    assert game.has_book_moves() is False


def test_unload_opening_book_calls_close():
    """Test unload_opening_book calls close_opening_book."""
    mock_book = Mock(spec=OpeningBook)
    game = Game(opening_book=mock_book)

    game.unload_opening_book()

    mock_book.close.assert_called_once()


def test_unload_opening_book_no_book():
    """Test unload_opening_book works when no opening book is loaded."""
    game = Game()
    # Should not raise an exception
    game.unload_opening_book()

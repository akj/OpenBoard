import chess
import pytest
from concurrent.futures import Future
from unittest.mock import Mock

from openboard.controllers.chess_controller import ChessController
from openboard.models.game import Game
from openboard.models.game_mode import GameConfig, GameMode, DifficultyLevel


@pytest.fixture
def controller():
    return ChessController(Game())


def test_controller_events_are_scoped_to_one_game(controller):
    messages = []
    controller.announce.connect(lambda sender, text: messages.append(text), weak=False)
    other = ChessController(Game())
    other.navigate("up")
    assert messages == []
    controller.start()
    assert any("Human vs Human" in message for message in messages)


def test_new_game_resets_replay_selection_and_board(controller):
    boards = []
    controller.board_updated.connect(
        lambda sender, board: boards.append(board), weak=False
    )
    controller.load_pgn("1. e4 e5 *")
    controller.replay_next()
    controller.selected_square = chess.E4
    controller.new_game(GameConfig(mode=GameMode.HUMAN_VS_HUMAN))
    assert not controller.in_replay
    assert controller.selected_square is None
    assert boards[-1].fen() == chess.STARTING_FEN


def test_replay_preserves_fen_start_and_complete_history(controller):
    fen = "4k3/8/8/8/8/8/4P3/4K3 b - - 0 12"
    controller.load_pgn(f'[SetUp "1"]\n[FEN "{fen}"]\n\n12... Kd7 13. e4 *')
    assert controller.game.board_state.board.fen() == fen
    controller.replay_to_position(1)
    final = controller.game.board_state.board.fen()
    controller.replay_to_position(-1)
    start, moves, index = controller.move_history()
    assert start.fen() == fen
    assert len(moves) == 2
    assert index == -1
    controller.replay_to_position(1)
    assert controller.game.board_state.board.fen() == final


def test_live_history_can_return_forward_after_review(controller):
    controller.game.apply_move(chess.E2, chess.E4)
    controller.game.apply_move(chess.E7, chess.E5)
    final = controller.game.board_state.board.fen()
    controller.replay_to_position(-1)
    controller.replay_to_position(1)
    assert controller.game.board_state.board.fen() == final


@pytest.mark.parametrize(
    "kind,text",
    [
        ("pgn", "1. e4 e5 2. Qh8 *"),
        ("fen", "invalid"),
        ("pgn", '[Variant "Crazyhouse"]\n\n1. e4 *'),
        ("pgn", '[Variant "Atomic"]\n\n1. e4 *'),
        ("pgn", '[Variant "Chess960"]\n\n1. e4 *'),
    ],
)
def test_invalid_import_preserves_current_replay(controller, kind, text):
    controller.load_pgn("1. e4 e5 *")
    controller.replay_next()
    controller.selected_square = chess.E4
    engine = Mock()
    pending_hint = Future()
    engine.get_best_move_async.return_value = pending_hint
    controller.game.engine_adapter = engine
    controller.game.request_hint_async()
    before = controller.game.board_state.board
    history = controller.move_history()
    messages = []
    controller.announce.connect(lambda sender, text: messages.append(text), weak=False)
    getattr(controller, f"load_{kind}")(text)
    assert controller.in_replay
    assert controller.game.board_state.board == before
    assert controller.move_history() == history
    assert controller.selected_square == chess.E4
    assert not pending_hint.cancelled()
    assert len(messages) == 1
    assert messages[0].startswith(f"Invalid {kind.upper()}:")
    controller.game.close()


def test_illegal_move_keeps_selection_for_retry(controller):
    controller.focus_square(chess.E2)
    controller.select()
    controller.focus_square(chess.E5)
    controller.select()
    assert controller.selected_square == chess.E2
    controller.focus_square(chess.E4)
    controller.select()
    assert controller.selected_square is None
    assert controller.game.board_state.board.piece_at(chess.E4) == chess.Piece(
        chess.PAWN, chess.WHITE
    )


def test_promotion_waits_for_choice_and_allows_knight(controller):
    controller.load_fen("4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
    requests = []
    controller.promotion_requested.connect(
        lambda sender, **request: requests.append(request), weak=False
    )
    controller.focus_square(chess.A7)
    controller.select()
    controller.focus_square(chess.A8)
    controller.select()
    assert requests == [{"source": chess.A7, "destination": chess.A8}]
    assert controller.game.board_state.board.piece_at(chess.A7)
    controller.promote(chess.A7, chess.A8, chess.KNIGHT)
    assert controller.game.board_state.board.piece_at(chess.A8) == chess.Piece(
        chess.KNIGHT, chess.WHITE
    )
    assert controller.selected_square is None


def test_undo_computer_reply_returns_to_human_turn():
    game = Game(
        config=GameConfig(
            mode=GameMode.HUMAN_VS_COMPUTER,
            human_color=chess.WHITE,
            difficulty=DifficultyLevel.BEGINNER,
        )
    )
    game.apply_move(chess.E2, chess.E4)
    game.apply_move(chess.E7, chess.E5)
    controller = ChessController(game)
    controller.undo()
    assert game.board_state.board.fen() == chess.STARTING_FEN
    assert not game.is_computer_turn()

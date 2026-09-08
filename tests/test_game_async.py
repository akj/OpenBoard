"""Tests for async game paths: request_hint_async and request_computer_move_async.

Uses a synchronous mock engine that invokes the callback inline, eliminating
real async I/O. pytest-asyncio is not required here because the production code
is async only at the engine boundary which the mock replaces synchronously.
(ref: DL-001)
"""

import pytest
import chess
from unittest.mock import Mock

from openboard.models.game import Game
from openboard.models.game_mode import (
    GameConfig,
    GameMode,
    DifficultyLevel,
    get_difficulty_config,
)
from openboard.engine.engine_adapter import EngineAdapter
from openboard.exceptions import EngineError, GameModeError


def _make_mock_engine(move_uci="e7e5"):
    """Return a Mock EngineAdapter that invokes callbacks synchronously.

    Replaces the async engine boundary with a synchronous shim so tests
    run without event loop setup. The default move e7e5 is a legal black
    response after white plays e2e4. (ref: RSK-001)
    """
    engine = Mock(spec=EngineAdapter)
    engine.get_best_move.return_value = chess.Move.from_uci(move_uci)

    def sync_get_best_move_async(fen, time_ms=1000, depth=None, callback=None):
        if callback:
            callback(chess.Move.from_uci(move_uci))

    engine.get_best_move_async.side_effect = sync_get_best_move_async
    return engine


class TestGameRequestHintAsync:
    """Tests for Game.request_hint_async()."""

    def setup_method(self):
        # Hint tests use starting position (white to move), so e2e4 is valid
        self.mock_engine = _make_mock_engine(move_uci="e2e4")

    def test_request_hint_async_calls_engine_with_board_and_time_ms(self):
        game = Game(engine_adapter=self.mock_engine)
        game.request_hint_async(time_ms=500)
        call_args = self.mock_engine.get_best_move_async.call_args
        assert call_args is not None
        assert isinstance(call_args[0][0], chess.Board)
        assert call_args[0][1] == 500
        assert call_args[1].get("callback") is not None

    def test_request_hint_async_callback_emits_hint_ready_on_success(self):
        game = Game(engine_adapter=self.mock_engine)
        hint_moves = []

        def on_hint(sender, move=None, **kw):
            hint_moves.append(move)

        game.hint_ready.connect(on_hint, weak=False)
        game.request_hint_async()
        assert len(hint_moves) == 1
        assert hint_moves[0] == chess.Move.from_uci("e2e4")

    def test_request_hint_async_callback_emits_hint_ready_with_error_on_exception(self):
        engine = Mock(spec=EngineAdapter)

        def error_callback(fen, time_ms=1000, depth=None, callback=None):
            if callback:
                callback(RuntimeError("engine crashed"))

        engine.get_best_move_async.side_effect = error_callback
        game = Game(engine_adapter=engine)
        error_events = []

        def on_hint_error(sender, move=None, error=None, **kw):
            error_events.append(error)

        game.hint_ready.connect(on_hint_error, weak=False)
        game.request_hint_async()
        assert len(error_events) == 1
        assert error_events[0] is not None

    def test_request_hint_async_raises_engine_error_when_no_engine(self):
        game = Game(engine_adapter=None)
        with pytest.raises(EngineError):
            game.request_hint_async()


class TestGameRequestComputerMoveAsync:
    """Tests for Game.request_computer_move_async()."""

    def setup_method(self):
        # Computer is black; after white plays e2e4, e7e5 is a valid black response
        self.mock_engine = _make_mock_engine(move_uci="e7e5")

    def _make_hvc_game(self, difficulty=DifficultyLevel.BEGINNER):
        config = GameConfig(
            mode=GameMode.HUMAN_VS_COMPUTER,
            human_color=chess.WHITE,
            difficulty=difficulty,
        )
        return Game(engine_adapter=self.mock_engine, config=config)

    def test_request_computer_move_async_hvc_calls_engine_with_difficulty_params(self):
        game = self._make_hvc_game(DifficultyLevel.BEGINNER)
        # Push white move first so it's black's (computer's) turn
        game.board_state._board.push(chess.Move.from_uci("e2e4"))
        game.request_computer_move_async()
        call_args = self.mock_engine.get_best_move_async.call_args
        assert call_args is not None

    def test_request_computer_move_async_callback_applies_move_and_emits_signal(self):
        game = self._make_hvc_game()
        game.board_state._board.push(chess.Move.from_uci("e2e4"))
        move_events = []

        def on_move_ready(sender, move=None, source=None, **kw):
            move_events.append((move, source))

        game.computer_move_ready.connect(on_move_ready, weak=False)
        game.request_computer_move_async()
        assert len(move_events) == 1
        move, source = move_events[0]
        assert source == "engine"

    def test_request_computer_move_async_with_book_move_uses_book(self):
        mock_book = Mock()
        mock_book.is_loaded = True
        book_move = chess.Move.from_uci("d7d5")
        mock_book.get_move.return_value = book_move

        config = GameConfig(
            mode=GameMode.HUMAN_VS_COMPUTER,
            human_color=chess.WHITE,
            difficulty=DifficultyLevel.BEGINNER,
        )
        game = Game(
            engine_adapter=self.mock_engine, opening_book=mock_book, config=config
        )
        # Push white move so it's computer's turn
        game.board_state._board.push(chess.Move.from_uci("e2e4"))

        move_events = []

        def on_move_ready(sender, move=None, source=None, **kw):
            move_events.append((move, source))

        game.computer_move_ready.connect(on_move_ready, weak=False)
        game.request_computer_move_async()

        assert len(move_events) == 1
        move, source = move_events[0]
        assert source == "book"
        self.mock_engine.get_best_move_async.assert_not_called()

    def test_request_computer_move_async_callback_handles_engine_returning_none(self):
        engine = Mock(spec=EngineAdapter)

        def none_callback(fen, time_ms=1000, depth=None, callback=None):
            if callback:
                callback(None)

        engine.get_best_move_async.side_effect = none_callback
        config = GameConfig(
            mode=GameMode.HUMAN_VS_COMPUTER,
            human_color=chess.WHITE,
            difficulty=DifficultyLevel.BEGINNER,
        )
        game = Game(engine_adapter=engine, config=config)
        game.board_state._board.push(chess.Move.from_uci("e2e4"))

        error_events = []

        def on_error(sender, move=None, error=None, **kw):
            error_events.append(error)

        game.computer_move_ready.connect(on_error, weak=False)
        game.request_computer_move_async()
        assert len(error_events) == 1
        assert error_events[0] is not None

    def test_request_computer_move_async_raises_game_mode_error_in_hvh_mode(self):
        game = Game(config=GameConfig(mode=GameMode.HUMAN_VS_HUMAN))
        with pytest.raises(GameModeError):
            game.request_computer_move_async()

    def test_request_computer_move_async_raises_engine_error_when_no_engine(self):
        config = GameConfig(
            mode=GameMode.HUMAN_VS_COMPUTER,
            human_color=chess.WHITE,
            difficulty=DifficultyLevel.BEGINNER,
        )
        game = Game(engine_adapter=None, config=config)
        game.make_move(chess.Move.from_uci("e2e4"))
        with pytest.raises(EngineError):
            game.request_computer_move_async()

    def test_request_computer_move_async_cvc_uses_correct_difficulty_per_turn(self):
        white_engine = Mock(spec=EngineAdapter)
        white_difficulty = DifficultyLevel.BEGINNER
        black_difficulty = DifficultyLevel.ADVANCED

        captured_time_ms = []

        def capture_call(fen, time_ms=1000, depth=None, callback=None):
            captured_time_ms.append(time_ms)
            if callback:
                callback(chess.Move.from_uci("e2e4"))

        white_engine.get_best_move_async.side_effect = capture_call

        config = GameConfig(
            mode=GameMode.COMPUTER_VS_COMPUTER,
            white_difficulty=white_difficulty,
            black_difficulty=black_difficulty,
        )
        game = Game(engine_adapter=white_engine, config=config)

        white_config = get_difficulty_config(white_difficulty)
        game.request_computer_move_async()
        assert captured_time_ms[0] == white_config.time_ms

    def test_request_computer_move_async_callback_provides_old_board(self):
        game = self._make_hvc_game()
        game.board_state._board.push(chess.Move.from_uci("e2e4"))

        old_board_events = []

        def on_move_ready(sender, move=None, source=None, old_board=None, **kw):
            old_board_events.append(old_board)

        game.computer_move_ready.connect(on_move_ready, weak=False)
        game.request_computer_move_async()
        assert len(old_board_events) == 1
        assert old_board_events[0] is not None
        assert isinstance(old_board_events[0], chess.Board)


class TestRequestComputerMoveEngineOptional:
    """Verifies engine-optional behavior (Codex MEDIUM): no engine + no book → typed engine error."""

    def test_request_computer_move_async_raises_when_no_engine_and_no_book(self):
        """Verifies Codex MEDIUM: engine_adapter=None and no book hit must raise EngineError, not AttributeError.

        Phase 1 contract: the app starts and runs without an engine. When the user explicitly
        requests a computer move and there is no engine AND no book move, the call must surface
        a typed EngineError so the controller can announce it accessibly. Silent no-op is forbidden
        (the user would not hear feedback). AttributeError is forbidden (it is not the documented
        failure mode and leaks implementation detail).
        """
        from openboard.exceptions import EngineError
        from openboard.models.game import Game
        from openboard.models.game_mode import GameConfig, GameMode

        # HvC mode is required for request_computer_move_async to make sense.
        from openboard.models.game_mode import DifficultyLevel

        game = Game(
            config=GameConfig(
                mode=GameMode.HUMAN_VS_COMPUTER,
                human_color=chess.WHITE,
                difficulty=DifficultyLevel.BEGINNER,
            ),
            engine_adapter=None,
        )
        # Ensure no opening book is configured.
        game.opening_book = None

        game.make_move(chess.Move.from_uci("e2e4"))
        with pytest.raises(EngineError):
            game.request_computer_move_async()


class DeferredEngine:
    """Keep callbacks pending, including results already queued for GUI delivery."""

    def __init__(self):
        self.requests = []

    def get_best_move_async(self, board, time_ms=1000, depth=None, callback=None):
        from concurrent.futures import Future

        future = Future()
        self.requests.append((board, callback, future))
        return future


def make_deferred_game():
    engine = DeferredEngine()
    game = Game(
        engine_adapter=Mock(spec=EngineAdapter, wraps=engine),
        config=GameConfig(
            mode=GameMode.HUMAN_VS_COMPUTER,
            human_color=chess.BLACK,
            difficulty=DifficultyLevel.BEGINNER,
        ),
    )
    return game, engine


@pytest.mark.parametrize(
    "reset",
    [
        lambda game: game.new_game(),
        lambda game: game.load_fen(chess.STARTING_FEN),
        lambda game: game.board_state.load_pgn('[Event "Empty"]\n\n*'),
        lambda game: game.close(),
    ],
)
def test_late_computer_move_is_discarded_even_when_still_legal(reset):
    game, engine = make_deferred_game()
    events = []
    game.computer_move_ready.connect(lambda sender, **kw: events.append(kw), weak=False)
    game.request_computer_move_async()
    reset(game)
    _, callback, future = engine.requests[0]
    assert future.cancelled()
    callback(chess.Move.from_uci("e2e4"))
    assert game.board_state.board.fen() == chess.STARTING_FEN
    assert events == []


def test_undo_and_redo_do_not_revive_old_computer_result():
    game, engine = make_deferred_game()
    game.request_computer_move_async()
    game.make_move(chess.Move.from_uci("e2e4"))
    game.undo_move()
    engine.requests[0][1](chess.Move.from_uci("e2e4"))
    assert game.board_state.board.fen() == chess.STARTING_FEN


def test_new_hint_supersedes_previous_hint_and_position_change_cancels_it():
    game, engine = make_deferred_game()
    hints = []
    game.hint_ready.connect(lambda sender, **kw: hints.append(kw), weak=False)
    game.request_hint_async()
    game.request_hint_async()
    assert engine.requests[0][2].cancelled()
    engine.requests[0][1](chess.Move.from_uci("e2e4"))
    assert hints == []
    engine.requests[1][1](chess.Move.from_uci("d2d4"))
    assert hints == [{"move": chess.Move.from_uci("d2d4")}]
    game.request_hint_async()
    game.new_game()
    engine.requests[2][1](RuntimeError("stale error"))
    assert len(hints) == 1


def test_duplicate_computer_request_does_not_start_another_search():
    game, engine = make_deferred_game()
    game.request_computer_move_async()
    game.request_computer_move_async()
    assert len(engine.requests) == 1
    engine.requests[0][1](chess.Move.from_uci("e2e4"))
    engine.requests[0][1](chess.Move.from_uci("e2e4"))
    assert game.board_state.board.move_stack == [chess.Move.from_uci("e2e4")]


def test_hint_snapshot_retains_repetition_history():
    game, engine = make_deferred_game()
    for move in ["g1f3", "g8f6", "f3g1", "f6g8"] * 2:
        game.make_move(chess.Move.from_uci(move))
    game.request_hint_async()
    snapshot = engine.requests[0][0]
    game.make_move(chess.Move.from_uci("e2e4"))
    assert snapshot.is_repetition(3)
    assert len(snapshot.move_stack) == 8


def test_computer_search_rejects_human_turn():
    game, engine = make_deferred_game()
    game.make_move(chess.Move.from_uci("e2e4"))
    with pytest.raises(GameModeError, match="computer's turn"):
        game.request_computer_move_async()
    assert engine.requests == []


def test_illegal_engine_move_announces_error_without_changing_position():
    game, engine = make_deferred_game()
    events = []
    game.computer_move_ready.connect(lambda sender, **kw: events.append(kw), weak=False)
    game.request_computer_move_async()
    engine.requests[0][1](chess.Move.from_uci("e2e5"))
    assert game.board_state.board.fen() == chess.STARTING_FEN
    assert events[0]["move"] is None
    assert "illegal move" in events[0]["error"]

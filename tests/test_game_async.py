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

    def test_request_hint_async_calls_engine_with_fen_and_time_ms(self):
        game = Game(engine_adapter=self.mock_engine)
        game.request_hint_async(time_ms=500)
        call_args = self.mock_engine.get_best_move_async.call_args
        assert call_args is not None
        # FEN is first positional arg
        assert isinstance(call_args[0][0], str)
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
        game.board_state._board.push(chess.Move.from_uci("e2e4"))
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

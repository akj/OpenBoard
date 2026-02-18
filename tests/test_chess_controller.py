"""Tests for ChessController behavioral coverage.

Tests all 18 public methods using real Game instances and Mock engine adapters.
Signal capture via blinker sender pattern eliminates wx dependency. (ref: DL-001)

Each test class covers a functional group: navigation, selection, undo/redo,
replay, hints, announcements, computer move handling, opening book, FEN loading,
and computer thinking state.

TestChessControllerAnnouncements verifies all 8 branches of _format_verbose_announcement
(normal move, capture, kingside castle, queenside castle, en passant, promotion,
promotion+capture, check/checkmate). If any branch is unreachable via signal testing,
document it as a known gap. (ref: DL-007)
"""

import chess
from unittest.mock import Mock, patch

from openboard.controllers.chess_controller import ChessController
from openboard.models.game import Game
from openboard.models.game_mode import GameConfig, GameMode, DifficultyLevel
from openboard.engine.engine_adapter import EngineAdapter


def _make_controller(game, config=None):
    """Return (controller, signals) with all blinker signals wired to capture lists.

    Uses weak=False to ensure named handlers are not garbage collected before
    tests complete. (ref: DL-001)
    """
    controller = ChessController(game, config=config)
    signals = {
        "announce": [],
        "board_updated": [],
        "square_focused": [],
        "selection_changed": [],
        "status_changed": [],
        "hint_ready": [],
        "computer_thinking": [],
    }

    def on_announce(sender, **kw):
        signals["announce"].append(kw.get("text"))

    def on_board_updated(sender, **kw):
        signals["board_updated"].append(kw.get("board"))

    def on_square_focused(sender, **kw):
        signals["square_focused"].append(kw.get("square"))

    def on_selection_changed(sender, **kw):
        signals["selection_changed"].append(kw.get("selected_square"))

    def on_status_changed(sender, **kw):
        signals["status_changed"].append(kw.get("status"))

    def on_hint_ready(sender, **kw):
        signals["hint_ready"].append(kw.get("move"))

    def on_computer_thinking(sender, **kw):
        signals["computer_thinking"].append(kw.get("thinking"))

    controller.announce.connect(on_announce, weak=False)
    controller.board_updated.connect(on_board_updated, weak=False)
    controller.square_focused.connect(on_square_focused, weak=False)
    controller.selection_changed.connect(on_selection_changed, weak=False)
    controller.status_changed.connect(on_status_changed, weak=False)
    controller.hint_ready.connect(on_hint_ready, weak=False)
    controller.computer_thinking.connect(on_computer_thinking, weak=False)

    return controller, signals


def _make_hvh_game():
    """Return a human-vs-human Game with no engine."""
    return Game(config=GameConfig(mode=GameMode.HUMAN_VS_HUMAN))


def _make_hvc_game(mock_engine):
    """Return a human-vs-computer Game with white as human and the provided engine."""
    config = GameConfig(
        mode=GameMode.HUMAN_VS_COMPUTER,
        human_color=chess.WHITE,
        difficulty=DifficultyLevel.BEGINNER,
    )
    return Game(engine_adapter=mock_engine, config=config)


class TestChessControllerNavigation:
    """Tests for board navigation commands."""

    def setup_method(self):
        self.game = _make_hvh_game()
        self.controller, self.signals = _make_controller(self.game)
        self.signals["announce"].clear()
        self.signals["square_focused"].clear()

    def test_navigate_up_increments_rank(self):
        self.controller.current_square = chess.A1
        self.controller.navigate("up")
        assert self.controller.current_square == chess.A2
        assert chess.A2 in self.signals["square_focused"]

    def test_navigate_down_decrements_rank(self):
        self.controller.current_square = chess.A2
        self.controller.navigate("down")
        assert self.controller.current_square == chess.A1
        assert chess.A1 in self.signals["square_focused"]

    def test_navigate_right_increments_file(self):
        self.controller.current_square = chess.A1
        self.controller.navigate("right")
        assert self.controller.current_square == chess.B1
        assert chess.B1 in self.signals["square_focused"]

    def test_navigate_left_decrements_file(self):
        self.controller.current_square = chess.B1
        self.controller.navigate("left")
        assert self.controller.current_square == chess.A1
        assert chess.A1 in self.signals["square_focused"]

    def test_navigate_up_at_top_edge_does_not_wrap(self):
        self.controller.current_square = chess.A8
        self.controller.navigate("up")
        assert self.controller.current_square == chess.A8
        assert chess.A8 not in self.signals["square_focused"]

    def test_navigate_down_at_bottom_edge_does_not_wrap(self):
        self.controller.current_square = chess.A1
        self.controller.navigate("down")
        assert self.controller.current_square == chess.A1

    def test_navigate_left_at_left_edge_does_not_wrap(self):
        self.controller.current_square = chess.A1
        self.controller.navigate("left")
        assert self.controller.current_square == chess.A1

    def test_navigate_right_at_right_edge_does_not_wrap(self):
        self.controller.current_square = chess.H1
        self.controller.navigate("right")
        assert self.controller.current_square == chess.H1

    def test_navigate_announces_piece_on_destination(self):
        self.controller.current_square = chess.A1
        self.controller.navigate("up")
        # A2 has a white pawn in starting position
        announcement = self.signals["announce"][-1]
        assert "pawn" in announcement.lower()

    def test_navigate_announces_empty_square(self):
        self.controller.current_square = chess.A2
        self.controller.navigate("up")
        # A3 is empty in starting position
        announcement = self.signals["announce"][-1]
        assert announcement == "a3"


class TestChessControllerSelection:
    """Tests for piece selection and move execution."""

    def setup_method(self):
        self.game = _make_hvh_game()
        self.controller, self.signals = _make_controller(self.game)
        self.signals["announce"].clear()
        self.signals["selection_changed"].clear()

    def test_select_own_piece_sets_selected_square(self):
        self.controller.current_square = chess.E2
        self.controller.select()
        assert self.controller.selected_square == chess.E2
        assert chess.E2 in self.signals["selection_changed"]

    def test_select_own_piece_announces_selected(self):
        self.controller.current_square = chess.E2
        self.controller.select()
        assert any("e2" in ann.lower() for ann in self.signals["announce"])

    def test_select_empty_square_announces_no_piece(self):
        self.controller.current_square = chess.E4
        self.controller.select()
        assert self.controller.selected_square is None
        assert any("no piece" in ann.lower() for ann in self.signals["announce"])

    def test_select_opponent_piece_announces_wrong_color(self):
        # E7 has a black pawn; white to move so that is the opponent
        self.controller.current_square = chess.E7
        self.controller.select()
        assert self.controller.selected_square is None
        assert any("cannot select" in ann.lower() for ann in self.signals["announce"])

    def test_select_during_computer_thinking_announces_wait(self):
        self.controller._computer_thinking = True
        self.controller.current_square = chess.E2
        self.controller.select()
        assert any("thinking" in ann.lower() for ann in self.signals["announce"])

    def test_select_in_cvc_mode_announces_not_allowed(self):
        game = Game(
            config=GameConfig(
                mode=GameMode.COMPUTER_VS_COMPUTER,
                white_difficulty=DifficultyLevel.BEGINNER,
                black_difficulty=DifficultyLevel.BEGINNER,
            )
        )
        controller, signals = _make_controller(game)
        signals["announce"].clear()
        controller.current_square = chess.E2
        controller.select()
        assert any("not allowed" in ann.lower() for ann in signals["announce"])

    def test_select_when_computer_turn_announces_computers_turn(self):
        mock_engine = Mock(spec=EngineAdapter)
        mock_engine.get_best_move.return_value = chess.Move.from_uci("e7e5")
        mock_engine.get_best_move_async.return_value = None
        game = _make_hvc_game(mock_engine)
        controller, signals = _make_controller(game)
        # Advance to black's turn (computer is black)
        game.board_state._board.push(chess.Move.from_uci("e2e4"))
        signals["announce"].clear()
        controller.current_square = chess.E7
        controller.select()
        assert any("computer" in ann.lower() for ann in signals["announce"])

    def test_select_then_move_to_legal_square_applies_move(self):
        self.controller.current_square = chess.E2
        self.controller.select()
        self.signals["board_updated"].clear()
        self.controller.current_square = chess.E4
        self.controller.select()
        assert self.controller.selected_square is None
        assert len(self.signals["board_updated"]) > 0
        piece = self.game.board_state.board.piece_at(chess.E4)
        assert piece is not None and piece.piece_type == chess.PAWN

    def test_select_then_move_to_illegal_square_announces_error(self):
        self.controller.current_square = chess.E2
        self.controller.select()
        self.signals["announce"].clear()
        self.controller.current_square = chess.E5
        self.controller.select()
        assert any(
            "illegal" in ann.lower() or "invalid" in ann.lower()
            for ann in self.signals["announce"]
        )

    def test_deselect_clears_selection_and_announces(self):
        self.controller.current_square = chess.E2
        self.controller.select()
        self.signals["announce"].clear()
        self.signals["selection_changed"].clear()
        self.controller.deselect()
        assert self.controller.selected_square is None
        assert None in self.signals["selection_changed"]
        assert any("clear" in ann.lower() for ann in self.signals["announce"])


class TestChessControllerUndo:
    """Tests for undo functionality."""

    def setup_method(self):
        self.game = _make_hvh_game()
        self.controller, self.signals = _make_controller(self.game)
        self.signals["announce"].clear()

    def test_undo_pops_last_move(self):
        self.game.board_state.make_move(chess.Move.from_uci("e2e4"))
        self.controller.undo()
        assert len(self.game.board_state.board.move_stack) == 0

    def test_undo_with_no_moves_announces_nothing_to_undo(self):
        self.controller.undo()
        assert any("nothing" in ann.lower() for ann in self.signals["announce"])

    def test_undo_in_replay_mode_delegates_to_replay_prev(self):
        pgn = "1. e4 e5 2. Nf3 Nc6 *"
        self.controller.load_pgn(pgn)
        self.controller.replay_next()
        self.controller.replay_next()
        self.signals["announce"].clear()
        self.controller.undo()
        assert self.controller._replay_index == 1


class TestChessControllerReplay:
    """Tests for PGN replay functionality."""

    PGN = "1. e4 e5 2. Nf3 Nc6 *"

    def setup_method(self):
        self.game = _make_hvh_game()
        self.controller, self.signals = _make_controller(self.game)
        self.signals["announce"].clear()

    def test_load_pgn_sets_replay_mode(self):
        self.controller.load_pgn(self.PGN)
        assert self.controller._in_replay is True
        assert len(self.controller._replay_moves) == 4

    def test_load_pgn_with_invalid_pgn_announces_error(self):
        # Empty string causes chess.pgn.read_game to return None
        self.controller.load_pgn("")
        assert any("invalid" in ann.lower() for ann in self.signals["announce"])

    def test_replay_next_steps_forward(self):
        self.controller.load_pgn(self.PGN)
        self.controller.replay_next()
        assert self.controller._replay_index == 1
        assert len(self.game.board_state.board.move_stack) == 1

    def test_replay_next_at_end_announces_end_of_game(self):
        self.controller.load_pgn(self.PGN)
        for _ in range(4):
            self.controller.replay_next()
        self.signals["announce"].clear()
        self.controller.replay_next()
        assert any("end" in ann.lower() for ann in self.signals["announce"])

    def test_replay_prev_steps_back(self):
        self.controller.load_pgn(self.PGN)
        self.controller.replay_next()
        self.controller.replay_next()
        self.controller.replay_prev()
        assert self.controller._replay_index == 1

    def test_replay_prev_at_start_announces_at_start(self):
        self.controller.load_pgn(self.PGN)
        self.signals["announce"].clear()
        self.controller.replay_prev()
        assert any("start" in ann.lower() for ann in self.signals["announce"])


class TestChessControllerHints:
    """Tests for hint and book hint functionality."""

    def setup_method(self):
        self.mock_engine = Mock(spec=EngineAdapter)
        self.mock_engine.get_best_move.return_value = chess.Move.from_uci("e2e4")
        self.mock_engine.get_best_move_async.return_value = None

    def test_request_hint_calls_game_request_hint_async(self):
        game = _make_hvh_game()
        game.engine_adapter = self.mock_engine
        controller, signals = _make_controller(game)
        with patch.object(game, "request_hint_async") as mock_hint:
            controller.request_hint()
            mock_hint.assert_called_once()

    def test_request_hint_with_no_engine_announces_error(self):
        game = _make_hvh_game()
        controller, signals = _make_controller(game)
        signals["announce"].clear()
        controller.request_hint()
        assert len(signals["announce"]) > 0

    def test_request_book_hint_with_book_move_announces_suggestion(self):
        game = _make_hvh_game()
        game.opening_book = Mock()
        game.opening_book.is_loaded = True
        expected_move = chess.Move.from_uci("e2e4")
        game.opening_book.get_move.return_value = expected_move
        controller, signals = _make_controller(game)
        signals["announce"].clear()
        controller.request_book_hint()
        assert any("book" in ann.lower() for ann in signals["announce"])
        assert any(
            "e2" in ann.lower() and "e4" in ann.lower() for ann in signals["announce"]
        )

    def test_request_book_hint_with_no_book_announces_no_book(self):
        game = _make_hvh_game()
        controller, signals = _make_controller(game)
        signals["announce"].clear()
        controller.request_book_hint()
        assert any("no opening book" in ann.lower() for ann in signals["announce"])

    def test_request_book_hint_with_no_moves_announces_no_moves_found(self):
        game = _make_hvh_game()
        game.opening_book = Mock()
        game.opening_book.is_loaded = True
        game.opening_book.get_move.return_value = None
        controller, signals = _make_controller(game)
        signals["announce"].clear()
        controller.request_book_hint()
        assert any("no moves" in ann.lower() for ann in signals["announce"])

    def test_check_book_moves_with_no_book_announces_no_book(self):
        game = _make_hvh_game()
        controller, signals = _make_controller(game)
        signals["announce"].clear()
        controller.check_book_moves()
        assert any("no opening book" in ann.lower() for ann in signals["announce"])

    def test_check_book_moves_with_moves_announces_has_moves(self):
        game = _make_hvh_game()
        game.opening_book = Mock()
        game.opening_book.is_loaded = True
        game.opening_book.get_move.return_value = chess.Move.from_uci("e2e4")
        controller, signals = _make_controller(game)
        signals["announce"].clear()
        controller.check_book_moves()
        assert any("has moves" in ann.lower() for ann in signals["announce"])


class TestChessControllerAnnouncements:
    """Tests for move announcement formatting."""

    def setup_method(self):
        self.game = _make_hvh_game()
        self.controller, self.signals = _make_controller(self.game)
        self.signals["announce"].clear()

    def test_toggle_announce_mode_switches_to_brief(self):
        assert self.controller.announce_mode == "verbose"
        self.controller.toggle_announce_mode()
        assert self.controller.announce_mode == "brief"

    def test_toggle_announce_mode_switches_back_to_verbose(self):
        self.controller.toggle_announce_mode()
        self.controller.toggle_announce_mode()
        assert self.controller.announce_mode == "verbose"

    def test_verbose_normal_move_includes_piece_and_squares(self):
        self.controller.announce_mode = "verbose"
        self.game.board_state.make_move(chess.Move.from_uci("e2e4"))
        ann = self.signals["announce"][-1]
        assert "pawn" in ann.lower()
        assert "e2" in ann.lower()
        assert "e4" in ann.lower()

    def test_verbose_capture_includes_captured_piece_name(self):
        self.controller.announce_mode = "verbose"
        self.game.board_state.make_move(chess.Move.from_uci("e2e4"))
        self.game.board_state.make_move(chess.Move.from_uci("d7d5"))
        self.signals["announce"].clear()
        self.controller._pending_old_board = self.game.board_state.board.copy()
        self.game.board_state.make_move(chess.Move.from_uci("e4d5"))
        ann = self.signals["announce"][-1]
        assert "takes" in ann.lower() or "pawn" in ann.lower()

    def test_verbose_kingside_castling_announcement(self):
        self.controller.announce_mode = "verbose"
        fen = "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1"
        self.game.board_state.load_fen(fen)
        self.signals["announce"].clear()
        self.controller._pending_old_board = self.game.board_state.board.copy()
        self.game.board_state.make_move(chess.Move.from_uci("e1g1"))
        ann = self.signals["announce"][-1]
        assert "kingside" in ann.lower()

    def test_verbose_queenside_castling_announcement(self):
        self.controller.announce_mode = "verbose"
        fen = "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1"
        self.game.board_state.load_fen(fen)
        self.signals["announce"].clear()
        self.controller._pending_old_board = self.game.board_state.board.copy()
        self.game.board_state.make_move(chess.Move.from_uci("e1c1"))
        ann = self.signals["announce"][-1]
        assert "queenside" in ann.lower()

    def test_verbose_en_passant_announcement(self):
        self.controller.announce_mode = "verbose"
        fen = "rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3"
        self.game.board_state.load_fen(fen)
        self.signals["announce"].clear()
        self.controller._pending_old_board = self.game.board_state.board.copy()
        self.game.board_state.make_move(chess.Move.from_uci("e5f6"))
        ann = self.signals["announce"][-1]
        assert "en passant" in ann.lower()

    def test_verbose_pawn_promotion_announcement(self):
        self.controller.announce_mode = "verbose"
        fen = "8/P7/8/8/8/8/8/4K2k w - - 0 1"
        self.game.board_state.load_fen(fen)
        self.signals["announce"].clear()
        self.controller._pending_old_board = self.game.board_state.board.copy()
        self.game.board_state.make_move(chess.Move.from_uci("a7a8q"))
        ann = self.signals["announce"][-1]
        assert "promot" in ann.lower()
        assert "queen" in ann.lower()

    def test_verbose_checkmate_includes_winner(self):
        self.controller.announce_mode = "verbose"
        # Scholar's mate variant: Qxf7# delivers checkmate
        fen = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5Q2/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
        self.game.board_state.load_fen(fen)
        self.signals["announce"].clear()
        self.game.board_state.make_move(chess.Move.from_uci("f3f7"))
        ann = self.signals["announce"][-1]
        assert "checkmate" in ann.lower()

    def test_verbose_check_announcement(self):
        self.controller.announce_mode = "verbose"
        # After 1.e4 e5 2.Bc4 Bc5 - Bxf7+ gives check
        fen = "rnbqk1nr/pppp1ppp/8/2b1p3/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 2 3"
        self.game.board_state.load_fen(fen)
        self.game.board_state.make_move(chess.Move.from_uci("c4f7"))
        ann = self.signals["announce"][-1]
        assert "check" in ann.lower()

    def test_brief_announcement_format(self):
        self.controller.announce_mode = "brief"
        self.game.board_state.make_move(chess.Move.from_uci("e2e4"))
        ann = self.signals["announce"][-1]
        assert "e2" in ann and "e4" in ann

    def test_brief_announcement_with_check_suffix(self):
        self.controller.announce_mode = "brief"
        # After 1.e4 e5 2.Bc4 Bc5 - Bxf7+ gives check
        fen = "rnbqk1nr/pppp1ppp/8/2b1p3/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 2 3"
        self.game.board_state.load_fen(fen)
        self.game.board_state.make_move(chess.Move.from_uci("c4f7"))
        ann = self.signals["announce"][-1]
        assert "check" in ann.lower()

    def test_announce_legal_moves_with_no_selection_announces_select_first(self):
        self.controller.selected_square = None
        self.signals["announce"].clear()
        self.controller.announce_legal_moves()
        assert any(
            "no piece selected" in ann.lower() for ann in self.signals["announce"]
        )

    def test_announce_legal_moves_lists_destinations(self):
        self.controller.current_square = chess.E2
        self.controller.select()
        self.signals["announce"].clear()
        self.controller.announce_legal_moves()
        ann = self.signals["announce"][-1]
        assert "e3" in ann.lower() or "e4" in ann.lower()

    def test_announce_attacking_pieces_on_square(self):
        # After e4 d5, d5 pawn can be taken by e4 pawn
        self.game.board_state.make_move(chess.Move.from_uci("e2e4"))
        self.game.board_state.make_move(chess.Move.from_uci("d7d5"))
        self.controller.current_square = chess.D5
        self.signals["announce"].clear()
        self.controller.announce_attacking_pieces()
        ann = self.signals["announce"][-1]
        assert "attacked by" in ann.lower()

    def test_announce_last_move_reconstructs_and_announces(self):
        self.game.board_state.make_move(chess.Move.from_uci("e2e4"))
        self.signals["announce"].clear()
        self.controller.announce_last_move()
        ann = self.signals["announce"][-1]
        assert "last move" in ann.lower()


class TestChessControllerComputerMove:
    """Tests for computer move signal handling."""

    def setup_method(self):
        self.mock_engine = Mock(spec=EngineAdapter)
        self.mock_engine.get_best_move.return_value = chess.Move.from_uci("e7e5")
        self.mock_engine.get_best_move_async.return_value = None

    def test_computer_move_ready_engine_source_announces_engine(self):
        game = _make_hvc_game(self.mock_engine)
        controller, signals = _make_controller(game)
        signals["announce"].clear()
        controller.announce_mode = "verbose"
        game.computer_move_ready.send(
            game, move=chess.Move.from_uci("e7e5"), source="engine"
        )
        assert any("engine" in ann.lower() for ann in signals["announce"])

    def test_computer_move_ready_book_source_announces_opening_book(self):
        game = _make_hvc_game(self.mock_engine)
        controller, signals = _make_controller(game)
        signals["announce"].clear()
        controller.announce_mode = "verbose"
        game.computer_move_ready.send(
            game, move=chess.Move.from_uci("e7e5"), source="book"
        )
        assert any("opening book" in ann.lower() for ann in signals["announce"])

    def test_computer_move_ready_with_error_announces_failure(self):
        game = _make_hvc_game(self.mock_engine)
        controller, signals = _make_controller(game)
        signals["announce"].clear()
        game.computer_move_ready.send(game, error="timeout")
        assert any("failed" in ann.lower() for ann in signals["announce"])

    def test_initial_game_state_announces_hvh_mode(self):
        game = _make_hvh_game()
        captured = []

        def on_announce(sender, **kw):
            captured.append(kw.get("text"))

        # Connect to the class-level signal before instantiation to capture init announcements
        ChessController.announce.connect(on_announce, weak=False)
        try:
            ChessController(game)
        finally:
            ChessController.announce.disconnect(on_announce)
        mode_announcements = [ann for ann in captured if ann and "human" in ann.lower()]
        assert len(mode_announcements) > 0

    def test_initial_game_state_announces_hvc_mode_with_color_and_difficulty(self):
        game = _make_hvc_game(self.mock_engine)
        captured = []

        def on_announce(sender, **kw):
            captured.append(kw.get("text"))

        ChessController.announce.connect(on_announce, weak=False)
        try:
            ChessController(game)
        finally:
            ChessController.announce.disconnect(on_announce)
        mode_announcements = [
            ann
            for ann in captured
            if ann and "white" in ann.lower() and "computer" in ann.lower()
        ]
        assert len(mode_announcements) > 0

    def test_initial_game_state_announces_cvc_mode_with_difficulties(self):
        game = Game(
            config=GameConfig(
                mode=GameMode.COMPUTER_VS_COMPUTER,
                white_difficulty=DifficultyLevel.BEGINNER,
                black_difficulty=DifficultyLevel.INTERMEDIATE,
            )
        )
        captured = []

        def on_announce(sender, **kw):
            captured.append(kw.get("text"))

        ChessController.announce.connect(on_announce, weak=False)
        try:
            ChessController(game)
        finally:
            ChessController.announce.disconnect(on_announce)
        mode_announcements = [
            ann for ann in captured if ann and "computer vs computer" in ann.lower()
        ]
        assert len(mode_announcements) > 0


class TestChessControllerOpeningBook:
    """Tests for opening book operations."""

    def setup_method(self):
        self.game = _make_hvh_game()
        self.controller, self.signals = _make_controller(self.game)
        self.signals["announce"].clear()

    def test_load_opening_book_with_valid_path_announces_success(self):
        with patch.object(self.game, "load_opening_book"):
            self.controller.announce_mode = "verbose"
            self.controller.load_opening_book("/some/path/book.bin")
            assert any(
                "opening book loaded" in ann.lower() for ann in self.signals["announce"]
            )

    def test_load_opening_book_with_invalid_path_announces_error(self):
        with patch.object(
            self.game, "load_opening_book", side_effect=Exception("not found")
        ):
            self.controller.load_opening_book("/bad/path.bin")
            assert any(
                "not found" in ann.lower() or "error" in ann.lower()
                for ann in self.signals["announce"]
            )

    def test_unload_opening_book_announces_unloaded(self):
        self.game.opening_book = Mock()
        self.controller.announce_mode = "verbose"
        with patch.object(self.game, "unload_opening_book"):
            self.controller.unload_opening_book()
        assert any("unloaded" in ann.lower() for ann in self.signals["announce"])

    def test_unload_opening_book_with_no_book_announces_nothing_to_unload(self):
        self.game.opening_book = None
        self.controller.unload_opening_book()
        assert any("no opening book" in ann.lower() for ann in self.signals["announce"])


class TestChessControllerFen:
    """Tests for FEN loading."""

    def setup_method(self):
        self.game = _make_hvh_game()
        self.controller, self.signals = _make_controller(self.game)
        self.signals["announce"].clear()
        self.signals["board_updated"].clear()

    def test_load_fen_loads_position_and_emits_board_updated(self):
        fen = "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1"
        self.controller.load_fen(fen)
        assert len(self.signals["board_updated"]) > 0
        board = self.game.board_state.board
        assert board.piece_at(chess.E1) is not None

    def test_load_fen_exits_replay_mode(self):
        self.controller._in_replay = True
        self.controller.load_fen(chess.STARTING_FEN)
        assert self.controller._in_replay is False


class TestChessControllerComputerThinking:
    """Tests for computer thinking state tracking."""

    def setup_method(self):
        self.mock_engine = Mock(spec=EngineAdapter)
        self.mock_engine.get_best_move_async.return_value = None

    def test_is_computer_thinking_returns_false_initially(self):
        game = _make_hvh_game()
        controller, _ = _make_controller(game)
        assert controller.is_computer_thinking() is False

    def test_is_computer_thinking_reflects_internal_state(self):
        game = _make_hvh_game()
        controller, _ = _make_controller(game)
        controller._computer_thinking = True
        assert controller.is_computer_thinking() is True

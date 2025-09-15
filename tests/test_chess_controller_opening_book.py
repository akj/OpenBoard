"""Tests for ChessController integration with opening book functionality."""

import tempfile
import os
from unittest.mock import Mock, patch

import chess

from openboard.controllers.chess_controller import ChessController
from openboard.models.game import Game
from openboard.models.game_mode import GameMode, GameConfig, DifficultyLevel


class TestChessControllerOpeningBookIntegration:
    """Tests for ChessController integration with opening book functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.signals_received = []
        self.mock_engine = Mock()
        self.mock_engine.get_best_move.return_value = chess.Move.from_uci("d2d4")

    def _capture_signal(self, sender, **kwargs):
        """Helper to capture emitted signals."""
        self.signals_received.append((type(sender).__name__, kwargs))

    def test_controller_with_opening_book_game(self):
        """Test that controller can work with games that have opening books."""
        # This is more of a smoke test to ensure the controller doesn't break
        # when the game has an opening book attached
        game = Game()

        # Create a temporary book file for testing
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            with patch("chess.polyglot.MemoryMappedReader") as mock_reader:
                mock_reader.return_value = Mock()
                game.load_opening_book(temp_path)

            controller = ChessController(game)

            # Ensure controller initializes successfully with a book-enabled game
            assert controller.game is game
            assert controller.game.opening_book is not None

        finally:
            os.unlink(temp_path)

    def test_controller_with_no_opening_book(self):
        """Test that controller works normally when game has no opening book."""
        game = Game()
        controller = ChessController(game)

        assert controller.game is game
        assert controller.game.opening_book is None

    def test_computer_move_integration_with_book(self):
        """Test that computer moves work correctly when book is present."""
        config = GameConfig(
            mode=GameMode.HUMAN_VS_COMPUTER,
            human_color=chess.WHITE,
            difficulty=DifficultyLevel.INTERMEDIATE,
        )
        game = Game(engine_adapter=self.mock_engine, config=config)

        # Load a mock opening book
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            with patch("chess.polyglot.MemoryMappedReader") as mock_reader:
                mock_instance = Mock()
                mock_reader.return_value = mock_instance
                game.load_opening_book(temp_path)

                # Mock book move available
                mock_entry = Mock()
                mock_entry.move = chess.Move.from_uci("d7d5")  # Legal move for black
                mock_entry.weight = 100
                mock_instance.find_all.return_value = [mock_entry]

            controller = ChessController(game)
            game.computer_move_ready.connect(self._capture_signal)

            # Make it computer's turn (black)
            game.board_state._board.push(
                chess.Move.from_uci("d2d4")
            )  # White plays first

            # Request computer move - should use book
            result = game.request_computer_move()

            assert result == chess.Move.from_uci("d7d5")
            assert controller.game is game  # Ensure controller is properly initialized
            # Engine should not have been called since book move was used
            self.mock_engine.get_best_move.assert_not_called()

        finally:
            os.unlink(temp_path)

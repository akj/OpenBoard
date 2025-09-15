"""Integration tests for Game class with OpeningBook functionality."""

import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import chess

from openboard.models.game import Game
from openboard.models.opening_book import OpeningBook
from openboard.models.game_mode import GameMode, GameConfig, DifficultyLevel
from openboard.exceptions import OpeningBookError


class TestGameOpeningBookIntegration:
    """Tests for Game class integration with OpeningBook."""

    def setup_method(self):
        """Set up test fixtures."""
        self.signals_received = []
        self.mock_engine = Mock()
        self.mock_engine.get_best_move.return_value = chess.Move.from_uci(
            "d7d5"
        )  # Legal move for black

    def _capture_signal(self, sender, **kwargs):
        """Helper to capture emitted signals."""
        self.signals_received.append((type(sender).__name__, kwargs))

    def test_game_init_with_opening_book(self):
        """Test Game initialization with opening book."""
        book = OpeningBook()
        game = Game(opening_book=book)

        assert game.opening_book is book

    def test_game_init_without_opening_book(self):
        """Test Game initialization without opening book."""
        game = Game()

        assert game.opening_book is None

    def test_get_book_move_no_book(self):
        """Test getting book move when no book is loaded."""
        game = Game()

        result = game.get_book_move()

        assert result is None

    def test_get_book_move_with_book(self):
        """Test getting book move when book is loaded."""
        book = OpeningBook()
        game = Game(opening_book=book)

        # Mock a book move
        mock_reader = Mock()
        mock_entry = Mock()
        mock_entry.move = chess.Move.from_uci("e2e4")
        mock_entry.weight = 100
        mock_reader.find_all.return_value = [mock_entry]
        book._reader = mock_reader
        book._book_file_path = Path("/test/book.bin")

        result = game.get_book_move()

        assert result == chess.Move.from_uci("e2e4")

    def test_get_book_move_error_handling(self):
        """Test error handling when book move lookup fails."""
        book = OpeningBook()
        game = Game(opening_book=book)

        # Mock reader to raise error
        mock_reader = Mock()
        mock_reader.find_all.side_effect = Exception("Reader error")
        book._reader = mock_reader
        book._book_file_path = Path("/test/book.bin")

        with pytest.raises(OpeningBookError):
            game.get_book_move()

    def test_load_opening_book_success(self):
        """Test successfully loading an opening book."""
        game = Game()

        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            with patch("chess.polyglot.MemoryMappedReader") as mock_reader:
                mock_reader.return_value = Mock()

                game.load_opening_book(temp_path)

                assert game.opening_book is not None
                assert game.opening_book.is_loaded
                assert str(game.opening_book.book_file_path) == temp_path
        finally:
            os.unlink(temp_path)

    def test_load_opening_book_error(self):
        """Test error handling when opening book fails to load."""
        game = Game()

        with pytest.raises(OpeningBookError):
            game.load_opening_book("/nonexistent/path/book.bin")

    def test_load_opening_book_creates_book_instance(self):
        """Test that loading book creates OpeningBook instance if none exists."""
        game = Game()
        assert game.opening_book is None

        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            with patch("chess.polyglot.MemoryMappedReader") as mock_reader:
                mock_reader.return_value = Mock()

                game.load_opening_book(temp_path)

                assert game.opening_book is not None
                assert isinstance(game.opening_book, OpeningBook)
        finally:
            os.unlink(temp_path)

    def test_close_opening_book(self):
        """Test closing opening book."""
        book = OpeningBook()
        game = Game(opening_book=book)

        # Mock loaded book
        mock_reader = Mock()
        book._reader = mock_reader
        book._book_file_path = Path("/test/book.bin")

        game.close_opening_book()

        mock_reader.close.assert_called_once()
        assert not book.is_loaded

    def test_close_opening_book_no_book(self):
        """Test closing opening book when no book exists."""
        game = Game()

        # Should not raise error
        game.close_opening_book()

    def test_computer_move_with_book_move(self):
        """Test computer move using opening book."""
        config = GameConfig(
            mode=GameMode.HUMAN_VS_COMPUTER,
            human_color=chess.WHITE,
            difficulty=DifficultyLevel.INTERMEDIATE,
        )
        book = OpeningBook()
        game = Game(engine_adapter=self.mock_engine, opening_book=book, config=config)
        game.computer_move_ready.connect(self._capture_signal)

        # Mock book move available (legal move for black)
        mock_reader = Mock()
        mock_entry = Mock()
        mock_entry.move = chess.Move.from_uci("d7d5")
        mock_entry.weight = 100
        mock_reader.find_all.return_value = [mock_entry]
        book._reader = mock_reader
        book._book_file_path = Path("/test/book.bin")

        # Make it computer's turn (black)
        game.board_state._board.push(chess.Move.from_uci("d2d4"))  # White plays first

        result = game.request_computer_move()

        assert result == chess.Move.from_uci("d7d5")
        assert len(self.signals_received) == 1
        assert self.signals_received[0][1]["move"] == chess.Move.from_uci("d7d5")
        assert self.signals_received[0][1]["source"] == "book"

        # Engine should not have been called
        self.mock_engine.get_best_move.assert_not_called()

    def test_computer_move_fallback_to_engine(self):
        """Test computer move falls back to engine when no book move available."""
        config = GameConfig(
            mode=GameMode.HUMAN_VS_COMPUTER,
            human_color=chess.WHITE,
            difficulty=DifficultyLevel.INTERMEDIATE,
        )
        book = OpeningBook()
        game = Game(engine_adapter=self.mock_engine, opening_book=book, config=config)
        game.computer_move_ready.connect(self._capture_signal)

        # Mock no book moves available
        mock_reader = Mock()
        mock_reader.find_all.return_value = []
        book._reader = mock_reader
        book._book_file_path = Path("/test/book.bin")

        # Make it computer's turn (black)
        game.board_state._board.push(chess.Move.from_uci("d2d4"))  # White plays first

        result = game.request_computer_move()

        assert result == chess.Move.from_uci("d7d5")
        assert len(self.signals_received) == 1
        assert self.signals_received[0][1]["move"] == chess.Move.from_uci("d7d5")
        assert self.signals_received[0][1]["source"] == "engine"

        # Engine should have been called
        self.mock_engine.get_best_move.assert_called_once()

    def test_computer_move_book_error_fallback(self):
        """Test computer move falls back to engine when book has error."""
        config = GameConfig(
            mode=GameMode.HUMAN_VS_COMPUTER,
            human_color=chess.WHITE,
            difficulty=DifficultyLevel.INTERMEDIATE,
        )
        book = OpeningBook()
        game = Game(engine_adapter=self.mock_engine, opening_book=book, config=config)
        game.computer_move_ready.connect(self._capture_signal)

        # Mock book error
        mock_reader = Mock()
        mock_reader.find_all.side_effect = Exception("Book error")
        book._reader = mock_reader
        book._book_file_path = Path("/test/book.bin")

        # Make it computer's turn (black)
        game.board_state._board.push(chess.Move.from_uci("d2d4"))  # White plays first

        result = game.request_computer_move()

        assert result == chess.Move.from_uci("d7d5")
        assert len(self.signals_received) == 1
        assert self.signals_received[0][1]["source"] == "engine"

        # Engine should have been called as fallback
        self.mock_engine.get_best_move.assert_called_once()

    def test_computer_move_no_book_uses_engine(self):
        """Test computer move uses engine when no book is loaded."""
        config = GameConfig(
            mode=GameMode.HUMAN_VS_COMPUTER,
            human_color=chess.WHITE,
            difficulty=DifficultyLevel.INTERMEDIATE,
        )
        game = Game(engine_adapter=self.mock_engine, config=config)
        game.computer_move_ready.connect(self._capture_signal)

        # Make it computer's turn (black)
        game.board_state._board.push(chess.Move.from_uci("d2d4"))  # White plays first

        result = game.request_computer_move()

        assert result == chess.Move.from_uci("d7d5")
        assert len(self.signals_received) == 1
        assert self.signals_received[0][1]["source"] == "engine"

        # Engine should have been called
        self.mock_engine.get_best_move.assert_called_once()

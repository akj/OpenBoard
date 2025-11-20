"""Tests for OpeningBook model."""

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import chess
import chess.polyglot

from openboard.models.opening_book import OpeningBook
from openboard.exceptions import OpeningBookError


class TestOpeningBookInitialization:
    """Tests for OpeningBook initialization."""

    def test_init_without_book_path(self):
        """Test initialization without a book file."""
        book = OpeningBook()
        assert not book.is_loaded
        assert book.book_file_path is None

    def test_init_with_nonexistent_book_path(self):
        """Test initialization with nonexistent book file raises error."""
        with pytest.raises(OpeningBookError):
            OpeningBook("/nonexistent/path/book.bin")

    def test_init_with_valid_book_path(self):
        """Test initialization with a valid book file."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            # Mock the MemoryMappedReader to avoid needing real polyglot file
            with patch("chess.polyglot.MemoryMappedReader") as mock_reader:
                mock_reader.return_value = Mock()
                book = OpeningBook(temp_path)
                assert book.is_loaded
                assert str(book.book_file_path) == temp_path
                mock_reader.assert_called_once_with(temp_path)
        finally:
            os.unlink(temp_path)


class TestOpeningBookLoading:
    """Tests for opening book loading functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.book = OpeningBook()

    def test_load_nonexistent_file(self):
        """Test loading a nonexistent book file."""
        with pytest.raises(OpeningBookError) as exc_info:
            self.book.load("/nonexistent/path/book.bin")

        assert "not found" in str(exc_info.value)

    @pytest.mark.skipif(os.name == "nt", reason="chmod doesn't work the same on Windows")
    def test_load_unreadable_file(self):
        """Test loading an unreadable book file."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            # Make file unreadable
            os.chmod(temp_path, 0o000)

            with pytest.raises(OpeningBookError) as exc_info:
                self.book.load(temp_path)

            assert "not readable" in str(exc_info.value)

        finally:
            os.chmod(temp_path, 0o644)  # Restore permissions for cleanup
            os.unlink(temp_path)

    def test_load_invalid_format(self):
        """Test loading an invalid polyglot book file."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp_file:
            temp_path = temp_file.name
            temp_file.write(b"invalid polyglot data")
            temp_file.flush()  # Ensure data is written

        try:
            with pytest.raises(OpeningBookError) as exc_info:
                self.book.load(temp_path)

            assert temp_path in str(exc_info.value)

        finally:
            # Ensure the book is closed before deleting on Windows
            if self.book.is_loaded:
                self.book.close()
            # On Windows, give a moment for file handles to be released
            if os.name == "nt":
                time.sleep(0.1)
            try:
                os.unlink(temp_path)
            except PermissionError:
                # On Windows, if the file is still locked, try again after a brief delay
                if os.name == "nt":
                    time.sleep(0.5)
                    os.unlink(temp_path)
                else:
                    raise

    def test_load_success(self):
        """Test successfully loading a book."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            with patch("chess.polyglot.MemoryMappedReader") as mock_reader:
                mock_instance = Mock()
                mock_reader.return_value = mock_instance

                self.book.load(temp_path)

                assert self.book.is_loaded
                assert str(self.book.book_file_path) == temp_path
                mock_reader.assert_called_once_with(temp_path)

        finally:
            os.unlink(temp_path)

    def test_load_replaces_existing(self):
        """Test that loading a new book replaces the existing one."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp_file1:
            temp_path1 = temp_file1.name
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp_file2:
            temp_path2 = temp_file2.name

        try:
            with patch("chess.polyglot.MemoryMappedReader") as mock_reader:
                mock_instance1 = Mock()
                mock_instance2 = Mock()
                mock_reader.side_effect = [mock_instance1, mock_instance2]

                # Load first book
                self.book.load(temp_path1)
                assert str(self.book.book_file_path) == temp_path1

                # Load second book (should close first)
                self.book.load(temp_path2)
                assert str(self.book.book_file_path) == temp_path2

                # First reader should have been closed
                mock_instance1.close.assert_called_once()

        finally:
            os.unlink(temp_path1)
            os.unlink(temp_path2)

    def test_close(self):
        """Test closing a book."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            with patch("chess.polyglot.MemoryMappedReader") as mock_reader:
                mock_instance = Mock()
                mock_reader.return_value = mock_instance

                self.book.load(temp_path)
                assert self.book.is_loaded

                self.book.close()
                assert not self.book.is_loaded
                assert self.book.book_file_path is None
                mock_instance.close.assert_called_once()

        finally:
            os.unlink(temp_path)


class TestOpeningBookMoveRetrieval:
    """Tests for opening book move retrieval."""

    def setup_method(self):
        """Set up test fixtures."""
        self.book = OpeningBook()
        self.board = chess.Board()

        # Mock reader with some test data
        self.mock_reader = Mock()
        self.book._reader = self.mock_reader
        self.book._book_file_path = Path("/test/book.bin")

    def test_get_move_no_book_loaded(self):
        """Test getting a move when no book is loaded."""
        book = OpeningBook()  # Fresh instance with no book

        result = book.get_move(self.board)

        assert result is None

    def test_get_move_highest_weight(self):
        """Test getting the highest-weighted book move."""
        # Mock entries with different weights
        mock_entry1 = Mock()
        mock_entry1.move = chess.Move.from_uci("e2e4")
        mock_entry1.weight = 100

        mock_entry2 = Mock()
        mock_entry2.move = chess.Move.from_uci("d2d4")
        mock_entry2.weight = 200

        self.mock_reader.find_all.return_value = [mock_entry1, mock_entry2]

        result = self.book.get_move(self.board)

        assert result == chess.Move.from_uci("d2d4")  # Higher weight

    def test_get_move_no_moves_found(self):
        """Test when no moves are found in the book."""
        self.mock_reader.find_all.return_value = []

        result = self.book.get_move(self.board)

        assert result is None

    def test_get_move_with_minimum_weight(self):
        """Test getting a move with minimum weight threshold."""
        mock_entry = Mock()
        mock_entry.move = chess.Move.from_uci("e2e4")
        mock_entry.weight = 100
        self.mock_reader.find_all.return_value = [mock_entry]

        result = self.book.get_move(self.board, minimum_weight=50)

        assert result == chess.Move.from_uci("e2e4")

        # Check that minimum_weight was passed
        call_args = self.mock_reader.find_all.call_args
        assert call_args.kwargs["minimum_weight"] == 50

    def test_get_move_reader_error(self):
        """Test handling of reader errors."""
        self.mock_reader.find_all.side_effect = Exception("Reader error")

        with pytest.raises(OpeningBookError) as exc_info:
            self.book.get_move(self.board)

        assert "Reader error" in str(exc_info.value)


# Edge case tests
class TestOpeningBookEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_empty_book_file(self):
        """Test handling of empty book files."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp_file:
            temp_path = temp_file.name
            # File is created but empty

        try:
            book = OpeningBook()
            # Empty polyglot files are actually valid (just contain no entries)
            book.load(temp_path)
            assert book.is_loaded
            assert book.book_file_path == Path(temp_path)
        finally:
            os.unlink(temp_path)

    def test_destructor_cleanup(self):
        """Test that destructor properly cleans up resources."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            with patch("chess.polyglot.MemoryMappedReader") as mock_reader:
                mock_instance = Mock()
                mock_reader.return_value = mock_instance

                book = OpeningBook(temp_path)
                assert book.is_loaded

                # Delete the book object
                del book

                # Reader should have been closed
                mock_instance.close.assert_called_once()

        finally:
            os.unlink(temp_path)

    def test_load_path_object(self):
        """Test loading book with Path object instead of string."""
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            with patch("chess.polyglot.MemoryMappedReader") as mock_reader:
                mock_reader.return_value = Mock()
                book = OpeningBook()
                book.load(temp_path)
                assert book.is_loaded
                assert book.book_file_path == temp_path
        finally:
            temp_path.unlink()

    def test_close_reader_error_handling(self):
        """Test error handling during reader cleanup."""
        book = OpeningBook()
        mock_reader = Mock()
        mock_reader.close.side_effect = Exception("Close error")
        book._reader = mock_reader
        book._book_file_path = Path("/test/book.bin")

        # Should not raise exception, just log warning
        book._close_reader()

        assert book._reader is None
        assert book._book_file_path is None
        mock_reader.close.assert_called_once()

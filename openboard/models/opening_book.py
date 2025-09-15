"""Opening book integration using Polyglot format files."""

import os
from pathlib import Path

import chess
import chess.polyglot

from ..exceptions import OpeningBookError
from ..logging_config import get_logger

logger = get_logger(__name__)


class OpeningBook:
    """
    Manages polyglot opening book files and provides move suggestions.

    Simple, synchronous interface for opening book operations.
    """

    def __init__(self, book_file_path: str | Path | None = None):
        """
        Initialize the opening book.

        Args:
            book_file_path: Path to the polyglot (.bin) opening book file.
                          If None, the book will be unloaded initially.
        """
        self._reader: chess.polyglot.MemoryMappedReader | None = None
        self._book_file_path: Path | None = None

        logger.debug("OpeningBook initialized")

        if book_file_path:
            self.load(book_file_path)

    @property
    def is_loaded(self) -> bool:
        """Check if an opening book is currently loaded."""
        return self._reader is not None

    @property
    def book_file_path(self) -> Path | None:
        """Get the path to the currently loaded book file."""
        return self._book_file_path

    def load(self, book_file_path: str | Path) -> None:
        """
        Load a polyglot opening book from file.

        Args:
            book_file_path: Path to the polyglot (.bin) file

        Raises:
            OpeningBookError: If the book fails to load
        """
        book_path = Path(book_file_path)

        # Check if file exists
        if not book_path.exists():
            error_msg = f"Opening book file not found: {book_path}"
            logger.error(error_msg)
            raise OpeningBookError(error_msg)

        # Check if file is readable
        if not os.access(book_path, os.R_OK):
            error_msg = f"Opening book file is not readable: {book_path}"
            logger.error(error_msg)
            raise OpeningBookError(error_msg)

        # Close existing reader if any
        self._close_reader()

        # Try to open the polyglot book
        try:
            self._reader = chess.polyglot.MemoryMappedReader(str(book_path))
            self._book_file_path = book_path
            logger.info(f"Opening book loaded: {book_path}")
        except Exception as e:
            error_msg = f"Failed to load opening book: {book_path} - {e}"
            logger.error(error_msg)
            raise OpeningBookError(error_msg) from e

    def close(self) -> None:
        """
        Close the current opening book and free resources.
        """
        self._close_reader()
        logger.info("Opening book closed")

    def _close_reader(self) -> None:
        """Internal method to close the book reader."""
        if self._reader:
            try:
                self._reader.close()
            except Exception as e:
                logger.warning(f"Error closing book reader: {e}")
            finally:
                self._reader = None
                self._book_file_path = None

    def get_move(
        self,
        board: chess.Board,
        minimum_weight: int = 1,
    ) -> chess.Move | None:
        """
        Get the highest-weighted move from the opening book for the given position.

        Args:
            board: Current chess position
            minimum_weight: Minimum weight threshold for book entries

        Returns:
            A chess.Move if found in the book, None if no suitable move exists

        Raises:
            OpeningBookError: If an error occurs during lookup
        """
        if not self._reader:
            logger.debug("No opening book loaded")
            return None

        try:
            # Get all entries and find the highest-weighted one
            entries = list(
                self._reader.find_all(
                    board,
                    minimum_weight=minimum_weight,
                )
            )

            if not entries:
                logger.debug(f"No book moves found for position {board.fen()}")
                return None

            # Sort by weight (descending) and take the highest
            entries.sort(key=lambda e: e.weight, reverse=True)
            move = entries[0].move

            logger.debug(
                f"Book move found for {board.fen()}: {move} (weight: {entries[0].weight})"
            )
            return move

        except Exception as e:
            error_msg = f"Error getting book move: {e}"
            logger.error(error_msg)
            raise OpeningBookError(error_msg) from e

    def __del__(self):
        """Destructor - ensure resources are cleaned up."""
        try:
            self.close()
        except Exception:
            # Ignore errors during cleanup
            pass

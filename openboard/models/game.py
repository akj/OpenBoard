import chess
from blinker import Signal

from .board_state import BoardState
from .opening_book import OpeningBook
from .game_mode import (
    GameMode,
    GameConfig,
    DifficultyConfig,
    get_difficulty_config,
    get_computer_color,
)
from ..engine.engine_adapter import EngineAdapter
from ..logging_config import get_logger
from ..exceptions import EngineError, GameModeError, OpeningBookError

logger = get_logger(__name__)


class Game:
    """
    High-level game orchestrator.
    Wraps a BoardState and an optional EngineAdapter to:
      - start/reset games
      - apply human moves
      - request engine hints
      - handle different game modes (human vs human, human vs computer)
      - re-emit signals for views/controllers
    """

    def __init__(
        self,
        engine_adapter: EngineAdapter | None = None,
        opening_book: OpeningBook | None = None,
        config: GameConfig | None = None,
    ):
        """
        :param engine_adapter: if supplied, used to generate hints via UCI.
        :param opening_book: if supplied, used for opening move suggestions
        :param config: game configuration including mode and difficulty
        """
        self.engine_adapter = engine_adapter
        self.opening_book = opening_book
        self.board_state = BoardState()
        self.config = config or GameConfig(mode=GameMode.HUMAN_VS_HUMAN)
        self.computer_color: chess.Color | None = None

        # Set up computer color if in human vs computer mode
        if self.config.mode == GameMode.HUMAN_VS_COMPUTER:
            self.computer_color = get_computer_color(self.config.human_color)

        engine_status = "with engine" if engine_adapter else "without engine"
        book_status = "with opening book" if opening_book else "without opening book"
        mode_status = f"mode: {self.config.mode}"
        logger.info(f"Game initialized {engine_status}, {book_status}, {mode_status}")

        # Signals:
        #   move_made: forwarded from BoardState
        #   hint_ready: emitted when engine returns a best move
        #   computer_move_ready: emitted when computer makes a move
        #   status_changed: forwarded from BoardState
        self.move_made = Signal()
        self.hint_ready = Signal()
        self.computer_move_ready = Signal()
        self.status_changed = Signal()

        # wire up board_state signals to our own
        self.board_state.move_made.connect(self._on_board_move)
        self.board_state.status_changed.connect(self._on_status)

    @property
    def engine(self) -> EngineAdapter | None:
        """Alias for engine_adapter for backward compatibility."""
        return self.engine_adapter

    def _on_board_move(self, sender, move):
        """Forward board_state.move_made to Game.move_made."""
        self.move_made.send(self, move=move)

    def _on_status(self, sender, status):
        """Forward board_state.status_changed to Game.status_changed."""
        self.status_changed.send(self, status=status)

    def new_game(self, config: GameConfig | None = None):
        """
        Reset to a fresh starting position with new game configuration.
        """
        if config:
            self.config = config
            if self.config.mode == GameMode.HUMAN_VS_COMPUTER:
                self.computer_color = get_computer_color(self.config.human_color)
            else:
                self.computer_color = None

        # reinitialize board_state and re-hook signals
        self.board_state = BoardState()
        self.board_state.move_made.connect(self._on_board_move)
        self.board_state.status_changed.connect(self._on_status)

        # For backward compatibility
        self.player_color = self.config.human_color

        # announce new status
        self.status_changed.send(self, status=self.board_state.game_status())

    def apply_move(
        self,
        src_square: chess.Square,
        dst_square: chess.Square,
        promotion: chess.PieceType | None = None,
    ):
        """
        Create a Move from two square indexes and push it.
        For pawn promotions, defaults to queen if no promotion piece specified.
        :param promotion: piece type to promote to (defaults to queen for pawn promotions)
        :raises ValueError if the move is illegal.
        """
        # Check if this is a pawn promotion move
        board = self.board_state.board
        piece = board.piece_at(src_square)

        # Detect pawn promotion: pawn moving to back rank
        if (
            piece
            and piece.piece_type == chess.PAWN
            and (
                (piece.color == chess.WHITE and chess.square_rank(dst_square) == 7)
                or (piece.color == chess.BLACK and chess.square_rank(dst_square) == 0)
            )
        ):
            # Default to queen promotion if not specified
            if promotion is None:
                promotion = chess.QUEEN
            mv = chess.Move(src_square, dst_square, promotion=promotion)
        else:
            mv = chess.Move(src_square, dst_square)

        self.board_state.make_move(mv)

    def get_book_move(
        self,
        minimum_weight: int = 1,
    ) -> chess.Move | None:
        """
        Get a move from the opening book for the current position.

        Args:
            minimum_weight: Minimum weight threshold for book entries

        Returns:
            A chess.Move if found in the book, None if no suitable move exists

        Raises:
            OpeningBookError: If an error occurs during lookup
        """
        if not self.opening_book:
            logger.debug("No opening book available")
            return None

        return self.opening_book.get_move(
            self.board_state.board,
            minimum_weight=minimum_weight,
        )

    def request_book_move(self) -> chess.Move | None:
        """
        Request a move from the opening book for the current position.
        Simplified version of get_book_move() for controller compatibility.

        Returns:
            A chess.Move if found in the book, None if no suitable move exists

        Raises:
            OpeningBookError: If an error occurs during lookup
        """
        return self.get_book_move()

    def has_book_moves(self) -> bool:
        """
        Check if the current position has available moves in the opening book.

        Returns:
            True if book moves are available, False otherwise
        """
        if not self.opening_book or not self.opening_book.is_loaded:
            return False

        try:
            move = self.get_book_move()
            return move is not None
        except Exception:
            return False

    def unload_opening_book(self) -> None:
        """
        Unload the current opening book.
        Alias for close_opening_book() for controller compatibility.
        """
        self.close_opening_book()

    def load_opening_book(self, book_file_path: str) -> None:
        """
        Load an opening book from a file path.

        Args:
            book_file_path: Path to the polyglot (.bin) opening book file

        Raises:
            OpeningBookError: If the book fails to load
        """
        if not self.opening_book:
            self.opening_book = OpeningBook()

        try:
            self.opening_book.load(book_file_path)
        except OpeningBookError as e:
            logger.error(f"Failed to load opening book: {e}")
            raise

    def close_opening_book(self) -> None:
        """
        Close the current opening book.
        """
        if self.opening_book:
            self.opening_book.close()
            logger.info("Opening book closed")

    def request_hint(self, time_ms: int = 1000) -> chess.Move | None:
        """
        Ask the engine adapter for the best move in the current position.
        Emits hint_ready when done.
        :raises RuntimeError if no engine_adapter is set.
        """
        if not self.engine_adapter:
            raise EngineError(
                "No chess engine available. Please install Stockfish to get hints."
            )
        fen = self.board_state._board.fen()
        best_move = self.engine_adapter.get_best_move(fen, time_ms)
        self.hint_ready.send(self, move=best_move)
        return best_move

    def request_hint_async(self, time_ms: int = 1000) -> None:
        """
        Ask the engine adapter for the best move asynchronously.
        Emits hint_ready signal when computation is complete.
        :raises RuntimeError if no engine_adapter is set.
        """
        if not self.engine_adapter:
            raise EngineError(
                "No chess engine available. Please install Stockfish to get hints."
            )

        fen = self.board_state._board.fen()

        def on_hint_ready(result):
            """Callback when hint computation is complete."""
            if isinstance(result, Exception):
                logger.error(f"Hint computation failed: {result}")
                self.hint_ready.send(self, move=None, error=str(result))
            else:
                self.hint_ready.send(self, move=result)

        # Use async version with callback
        self.engine_adapter.get_best_move_async(fen, time_ms, callback=on_hint_ready)

    def is_computer_turn(self) -> bool:
        """
        Check if it's the computer's turn.
        """
        match self.config.mode:
            case GameMode.HUMAN_VS_COMPUTER:
                return self.board_state.board.turn == self.computer_color
            case GameMode.COMPUTER_VS_COMPUTER:
                return True  # Always computer turn in computer vs computer mode
            case _:
                return False

    def request_computer_move(self) -> chess.Move | None:
        """
        Request a move from the computer opponent.
        First checks opening book, then falls back to engine if no book move available.
        Uses difficulty-based timing and emits computer_move_ready signal.
        :raises RuntimeError if no engine_adapter is set or not in computer mode.
        """
        if self.config.mode not in [
            GameMode.HUMAN_VS_COMPUTER,
            GameMode.COMPUTER_VS_COMPUTER,
        ]:
            raise GameModeError("Not in a computer vs mode")

        # First try to get a move from the opening book
        if self.opening_book and self.opening_book.is_loaded:
            try:
                book_move = self.opening_book.get_move(
                    self.board_state.board,
                    minimum_weight=1,
                )
                if book_move:
                    logger.info(f"Using opening book move: {book_move}")
                    # Capture board state before move for proper announcement
                    old_board = self.board_state.board.copy()
                    # Apply the book move
                    self.board_state.make_move(book_move)
                    self.computer_move_ready.send(
                        self, move=book_move, source="book", old_board=old_board
                    )
                    return book_move
            except Exception as e:
                logger.warning(f"Error getting book move, falling back to engine: {e}")

        # Fallback to engine if no book move or book unavailable
        if not self.engine_adapter:
            raise EngineError("No chess engine available for computer opponent")

        # Determine which difficulty to use based on whose turn it is
        difficulty_config: DifficultyConfig
        match self.config.mode:
            case GameMode.HUMAN_VS_COMPUTER:
                if not self.config.difficulty:
                    raise GameModeError("No difficulty level set for computer opponent")
                difficulty_config = get_difficulty_config(self.config.difficulty)
            case GameMode.COMPUTER_VS_COMPUTER:
                current_turn = self.board_state.board.turn
                match current_turn:
                    case chess.WHITE:
                        if not self.config.white_difficulty:
                            raise GameModeError(
                                "No difficulty level set for white computer"
                            )
                        difficulty_config = get_difficulty_config(
                            self.config.white_difficulty
                        )
                    case _:  # chess.BLACK
                        if not self.config.black_difficulty:
                            raise GameModeError(
                                "No difficulty level set for black computer"
                            )
                        difficulty_config = get_difficulty_config(
                            self.config.black_difficulty
                        )
            case _:
                raise GameModeError(
                    f"Computer moves not supported for mode: {self.config.mode}"
                )

        fen = self.board_state._board.fen()

        # Use difficulty-based timing and/or depth
        best_move = self.engine_adapter.get_best_move(
            fen, difficulty_config.time_ms, difficulty_config.depth
        )

        if best_move:
            logger.info(f"Using engine move: {best_move}")
            # Capture board state before move for proper announcement
            old_board = self.board_state.board.copy()
            # Apply the engine move
            self.board_state.make_move(best_move)
            self.computer_move_ready.send(
                self, move=best_move, source="engine", old_board=old_board
            )

        return best_move

    def request_computer_move_async(self) -> None:
        """
        Request a computer move asynchronously.
        First checks opening book, then falls back to engine if no book move available.
        Emits computer_move_ready signal when computation is complete.
        :raises RuntimeError if no engine_adapter is set or not in computer mode.
        """
        if self.config.mode not in [
            GameMode.HUMAN_VS_COMPUTER,
            GameMode.COMPUTER_VS_COMPUTER,
        ]:
            raise GameModeError("Not in a computer vs mode")

        # First try to get a move from the opening book
        if self.opening_book and self.opening_book.is_loaded:
            try:
                book_move = self.opening_book.get_move(
                    self.board_state.board,
                    minimum_weight=1,
                )
                if book_move:
                    logger.info(f"Using opening book move (async): {book_move}")
                    # Capture board state before move for proper announcement
                    old_board = self.board_state.board.copy()
                    # Apply the book move and emit signal
                    self.board_state.make_move(book_move)
                    self.computer_move_ready.send(
                        self, move=book_move, source="book", old_board=old_board
                    )
                    return
            except Exception as e:
                logger.warning(f"Error getting book move, falling back to engine: {e}")

        # Fallback to engine if no book move or book unavailable
        if not self.engine_adapter:
            raise EngineError("No chess engine available for computer opponent")

        # Determine which difficulty to use based on whose turn it is
        difficulty_config: DifficultyConfig
        match self.config.mode:
            case GameMode.HUMAN_VS_COMPUTER:
                if not self.config.difficulty:
                    raise GameModeError("No difficulty level set for computer opponent")
                difficulty_config = get_difficulty_config(self.config.difficulty)
            case GameMode.COMPUTER_VS_COMPUTER:
                current_turn = self.board_state.board.turn
                match current_turn:
                    case chess.WHITE:
                        if not self.config.white_difficulty:
                            raise GameModeError(
                                "No difficulty level set for white computer"
                            )
                        difficulty_config = get_difficulty_config(
                            self.config.white_difficulty
                        )
                    case _:  # chess.BLACK
                        if not self.config.black_difficulty:
                            raise GameModeError(
                                "No difficulty level set for black computer"
                            )
                        difficulty_config = get_difficulty_config(
                            self.config.black_difficulty
                        )
            case _:
                raise GameModeError(
                    f"Computer moves not supported for mode: {self.config.mode}"
                )

        fen = self.board_state._board.fen()

        def on_move_ready(result):
            """Callback when computer move computation is complete."""
            if isinstance(result, Exception):
                logger.error(f"Computer move computation failed: {result}")
                self.computer_move_ready.send(self, move=None, error=str(result))
            else:
                if result:
                    logger.info(f"Using engine move (async): {result}")
                    # Capture board state before move for proper announcement
                    old_board = self.board_state.board.copy()
                    # Apply move first to ensure consistent board state, then send signal
                    self.board_state.make_move(result)
                    self.computer_move_ready.send(
                        self, move=result, source="engine", old_board=old_board
                    )
                else:
                    logger.warning("Engine returned no move")
                    self.computer_move_ready.send(
                        self, move=None, error="Engine returned no move"
                    )

        # Use async version with callback
        self.engine_adapter.get_best_move_async(
            fen,
            difficulty_config.time_ms,
            difficulty_config.depth,
            callback=on_move_ready,
        )

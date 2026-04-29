import chess
from blinker import Signal
from typing import NamedTuple

from .board_state import BoardState
from .move_kind import MoveKind
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


class MoveContext(NamedTuple):
    """Resolved context for the next computer move — output of Game._resolve_move_context().

    Pure data; immutable. Three fields:
      difficulty_config: the resolved DifficultyConfig from self.config.difficulty
      fen_before: snapshot of self.board_state.board.fen() taken before any move
      book_move: optional opening-book hit; None if no book or no hit
    """

    difficulty_config: DifficultyConfig
    fen_before: str
    book_move: chess.Move | None

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
        #   move_made: forwarded from BoardState (enriched with old_board and move_kind)
        #   move_undone: forwarded from BoardState (D-04 / TD-01)
        #   hint_ready: emitted when engine returns a best move
        #   computer_move_ready: emitted when computer makes a move
        #   status_changed: forwarded from BoardState
        self.move_made = Signal()
        self.move_undone = Signal()
        self.hint_ready = Signal()
        self.computer_move_ready = Signal()
        self.status_changed = Signal()

        # wire up board_state signals to our own via canonical forwarder helper (D-05)
        self._connect_board_signals()

    @property
    def engine(self) -> EngineAdapter | None:
        """Alias for engine_adapter for backward compatibility."""
        return self.engine_adapter

    def _connect_board_signals(self) -> None:
        """Wire BoardState signals to Game-level forwarders.

        Called from __init__ and new_game() so subscribers bound to Game.move_made,
        Game.move_undone, Game.status_changed never need to re-subscribe across new_game.
        (D-04 / D-05: canonical forwarder pattern for v1.)
        """
        self.board_state.move_made.connect(self._on_board_move)
        self.board_state.move_undone.connect(self._on_board_undo)
        self.board_state.status_changed.connect(self._on_status)

    def _on_board_move(self, sender, move=None, old_board=None, **kwargs):
        """Forward board_state.move_made to Game.move_made with enriched payload (D-02)."""
        if move is None:
            # Special case for load_fen / programmatic emission with no move
            self.move_made.send(self, move=None, old_board=old_board, move_kind=MoveKind.QUIET)
            return

        post_push_board = self.board_state.board  # snapshot is fine; MoveKind doesn't mutate
        move_kind = MoveKind.QUIET
        if old_board is not None and old_board.is_capture(move):
            move_kind |= MoveKind.CAPTURE
        if old_board is not None and old_board.is_castling(move):
            move_kind |= MoveKind.CASTLE
        if old_board is not None and old_board.is_en_passant(move):
            move_kind |= MoveKind.EN_PASSANT
        if move.promotion is not None:
            move_kind |= MoveKind.PROMOTION
        # CHECK / CHECKMATE computed POST-push (Pitfall 1: never check before push)
        if post_push_board.is_check():
            move_kind |= MoveKind.CHECK
        if post_push_board.is_checkmate():
            move_kind |= MoveKind.CHECKMATE

        self.move_made.send(
            self, move=move, old_board=old_board, move_kind=move_kind
        )

    def _on_board_undo(self, sender, move=None, **kwargs):
        """Forward board_state.move_undone to Game.move_undone."""
        self.move_undone.send(self, move=move)

    def _on_status(self, sender, status=None, **kwargs):
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

        # reinitialize board_state and re-hook signals via canonical helper (D-04 / D-05)
        self.board_state = BoardState()
        self._connect_board_signals()

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

    def _resolve_move_context(self) -> MoveContext:
        """Resolve mode-validation + difficulty-config + FEN + book-hit for the next computer move.

        PURE preamble with no side effects (TD-07 / D-14 / Codex MEDIUM):
        - validates self.config.mode (raises GameModeError if not a computer mode)
        - resolves difficulty_config from self.config.difficulty
        - captures fen_before as a board FEN snapshot BEFORE any move is applied
        - optionally returns book_move from self.opening_book (None if no book or no hit)

        This method is side-effect-free: it reads state only and returns a MoveContext.
        No signals are emitted, no moves are applied, no threading primitives are used.
        (TD-07 / D-14)
        """
        if self.config.mode not in (
            GameMode.HUMAN_VS_COMPUTER,
            GameMode.COMPUTER_VS_COMPUTER,
        ):
            raise GameModeError("Not in a computer vs mode")

        # Resolve difficulty config based on mode and current turn
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

        # Snapshot FEN before any move is applied
        fen_before = self.board_state.board.fen()

        # Optionally consult opening book (pure lookup — no move applied here)
        book_move: chess.Move | None = None
        if self.opening_book is not None and self.opening_book.is_loaded:
            try:
                book_move = self.opening_book.get_move(
                    self.board_state.board,
                    minimum_weight=1,
                )
            except Exception as book_error:
                logger.warning(f"Opening book lookup failed, will use engine: {book_error}")
                book_move = None

        return MoveContext(
            difficulty_config=difficulty_config,
            fen_before=fen_before,
            book_move=book_move,
        )

    def request_computer_move_async(self, callback=None) -> None:
        """Request a computer move asynchronously.

        First checks opening book, then falls back to engine if no book move available.
        Emits computer_move_ready signal when computation is complete.

        :param callback: Optional callback called with the move when complete.
        :raises GameModeError: If not in a computer mode.
        :raises EngineNotFoundError: If engine_adapter is None and no book move available.
        (TD-07 / TD-08 / Codex MEDIUM)
        """
        context = self._resolve_move_context()

        # Book-hit short-circuit: apply book move synchronously and return
        if context.book_move is not None:
            logger.info(f"Using opening book move (async): {context.book_move}")
            old_board = self.board_state.board.copy()
            self.board_state.make_move(context.book_move)
            self.computer_move_ready.send(
                self, move=context.book_move, source="book", old_board=old_board
            )
            if callback:
                callback(context.book_move)
            return

        # Engine-optional: raise typed error if no engine AND no book hit (Codex MEDIUM)
        if self.engine_adapter is None:
            raise EngineError(
                "No chess engine available for computer opponent",
                "No engine adapter configured and no opening book move available",
            )

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
            if callback:
                callback(result)

        # Use async version with callback
        self.engine_adapter.get_best_move_async(
            context.fen_before,
            context.difficulty_config.time_ms,
            context.difficulty_config.depth,
            callback=on_move_ready,
        )

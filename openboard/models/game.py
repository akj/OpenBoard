import chess
from blinker import Signal
from concurrent.futures import Future

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


logger = get_logger(__name__)


class Game:
    """Own the game position and requests that belong to it.

    GUI callers and engine callbacks mutate this model on the wx thread.
    EngineAdapter receives snapshots and delivers results through its executor.
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
        self._requests: dict[str, tuple[object, Future | None]] = {}

        # Set up computer color if in human vs computer mode
        if self.config.mode == GameMode.HUMAN_VS_COMPUTER:
            self.computer_color = get_computer_color(self.config.human_color)

        engine_status = "with engine" if engine_adapter else "without engine"
        book_status = "with opening book" if opening_book else "without opening book"
        mode_status = f"mode: {self.config.mode}"
        logger.info(f"Game initialized {engine_status}, {book_status}, {mode_status}")

        # Signals:
        #   move_made: forwarded from BoardState (enriched with old_board and move_kind)
        #   move_undone: forwarded from BoardState
        #   hint_ready: emitted when engine returns a best move
        #   computer_move_ready: emitted when computer makes a move
        #   status_changed: forwarded from BoardState
        self.move_made = Signal()
        self.move_undone = Signal()
        self.hint_ready = Signal()
        self.computer_move_ready = Signal()
        self.status_changed = Signal()

        self._connect_board_signals()

    def _connect_board_signals(self) -> None:
        """Keep subscribers connected as the position changes and games restart."""
        self.board_state.move_made.connect(self._on_board_move)
        self.board_state.move_undone.connect(self._on_board_undo)
        self.board_state.status_changed.connect(self._on_status)

    def _on_board_move(self, sender, move=None, old_board=None, **kwargs):
        """Classify a completed move and notify game observers."""
        self.cancel_pending_requests()
        if move is None:
            # Special case for load_fen / programmatic emission with no move
            self.move_made.send(
                self, move=None, old_board=old_board, move_kind=MoveKind.QUIET
            )
            return

        post_push_board = self.board_state.board_ref
        move_kind = MoveKind.QUIET
        if old_board is not None and old_board.is_capture(move):
            move_kind |= MoveKind.CAPTURE
        if old_board is not None and old_board.is_castling(move):
            move_kind |= MoveKind.CASTLE
        if old_board is not None and old_board.is_en_passant(move):
            move_kind |= MoveKind.EN_PASSANT
        if move.promotion is not None:
            move_kind |= MoveKind.PROMOTION
        # Checks describe the resulting position; captures describe the old one.
        if post_push_board.is_check():
            move_kind |= MoveKind.CHECK
        if post_push_board.is_checkmate():
            move_kind |= MoveKind.CHECKMATE

        self.move_made.send(self, move=move, old_board=old_board, move_kind=move_kind)

    def _on_board_undo(self, sender, move=None, **kwargs):
        """Forward board_state.move_undone to Game.move_undone."""
        self.cancel_pending_requests()
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

        self.load_fen(chess.STARTING_FEN)

    def cancel_pending_requests(self) -> None:
        """Discard results belonging to a position the user has left."""
        requests, self._requests = self._requests, {}
        for _, future in requests.values():
            if future is not None:
                future.cancel()

    def _begin_request(self, kind: str) -> object:
        previous = self._requests.pop(kind, None)
        if previous is not None and previous[1] is not None:
            previous[1].cancel()
        token = object()
        self._requests[kind] = (token, None)
        return token

    def _finish_request(self, kind: str, token: object) -> bool:
        if self._requests.get(kind, (None, None))[0] is not token:
            return False
        self._requests.pop(kind)
        return True

    def _track_request(self, kind: str, token: object, future: Future) -> None:
        # An injected adapter can complete inline before returning its future.
        if self._requests.get(kind, (None, None))[0] is token:
            self._requests[kind] = (token, future)

    def make_move(self, move: chess.Move) -> None:
        self.board_state.make_move(move)

    def undo_move(self) -> None:
        self.board_state.undo_move()

    def load_fen(self, fen: str) -> None:
        self.board_state.load_fen(fen)

    def close(self) -> None:
        self.cancel_pending_requests()
        self.close_opening_book()

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
        board = self.board_state.board_ref
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

        self.make_move(mv)

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
            self.board_state.board_ref,
            minimum_weight=minimum_weight,
        )

    def has_book_moves(self) -> bool:
        """
        Check if the current position has available moves in the opening book.

        Returns:
            True if book moves are available, False otherwise
        """
        if not self.opening_book or not self.opening_book.is_loaded:
            return False

        try:
            return self.get_book_move() is not None
        except OpeningBookError:
            return False

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

    def request_hint_async(self, time_ms: int = 1000) -> None:
        """Request a hint for a snapshot of the current position and history."""
        if not self.engine_adapter:
            raise EngineError(
                "No chess engine available. Please install Stockfish to get hints."
            )
        token = self._begin_request("hint")

        def on_hint_ready(result):
            if not self._finish_request("hint", token):
                return
            if isinstance(result, Exception):
                self.hint_ready.send(self, move=None, error=str(result))
            else:
                self.hint_ready.send(self, move=result)

        try:
            future = self.engine_adapter.get_best_move_async(
                self.board_state.board, time_ms, callback=on_hint_ready
            )
        except Exception:
            self._finish_request("hint", token)
            raise
        self._track_request("hint", token, future)

    def is_computer_turn(self) -> bool:
        if self.board_state.board_ref.is_game_over():
            return False
        if self.config.mode == GameMode.HUMAN_VS_COMPUTER:
            return self.board_state.current_turn() == self.computer_color
        return self.config.mode == GameMode.COMPUTER_VS_COMPUTER

    def _computer_difficulty(self) -> DifficultyConfig:
        if self.config.mode == GameMode.HUMAN_VS_COMPUTER:
            difficulty = self.config.difficulty
        elif self.config.mode == GameMode.COMPUTER_VS_COMPUTER:
            difficulty = (
                self.config.white_difficulty
                if self.board_state.current_turn() == chess.WHITE
                else self.config.black_difficulty
            )
        else:
            raise GameModeError("Not in a computer vs mode")
        if difficulty is None:
            raise GameModeError("No difficulty level set for computer opponent")
        return get_difficulty_config(difficulty)

    def request_computer_move_async(self, callback=None) -> None:
        """Choose a book or engine move, ignoring results after the position changes."""
        difficulty = self._computer_difficulty()
        if not self.is_computer_turn():
            raise GameModeError("It is not the computer's turn")
        if "computer" in self._requests:
            return

        board = self.board_state.board
        book_move = None
        if self.opening_book is not None and self.opening_book.is_loaded:
            try:
                book_move = self.opening_book.get_move(board, minimum_weight=1)
            except OpeningBookError as error:
                logger.warning("Opening book lookup failed, will use engine: %s", error)
        if book_move is not None and book_move not in board.legal_moves:
            logger.warning("Opening book returned an illegal move: %s", book_move)
            book_move = None
        if book_move is None and self.engine_adapter is None:
            raise EngineError("No chess engine available for computer opponent")

        token = self._begin_request("computer")

        def on_move_ready(result):
            if not self._finish_request("computer", token):
                return
            if not isinstance(result, Exception):
                if result is None:
                    result = EngineError("Engine returned no move")
                elif result not in self.board_state.board_ref.legal_moves:
                    result = EngineError(f"Engine returned an illegal move: {result}")
            if isinstance(result, Exception):
                self.computer_move_ready.send(self, move=None, error=str(result))
            else:
                self.make_move(result)
                self.computer_move_ready.send(
                    self,
                    move=result,
                    source="book" if book_move else "engine",
                    old_board=board,
                )
            if callback:
                callback(result)

        if book_move is not None:
            on_move_ready(book_move)
            return
        engine = self.engine_adapter
        if engine is None:
            self._finish_request("computer", token)
            raise EngineError("No chess engine available for computer opponent")
        try:
            future = engine.get_best_move_async(
                board, difficulty.time_ms, difficulty.depth, callback=on_move_ready
            )
        except Exception:
            self._finish_request("computer", token)
            raise
        self._track_request("computer", token, future)

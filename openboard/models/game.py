from typing import Optional
import chess
from blinker import Signal

from .board_state import BoardState
from .game_mode import GameMode, GameConfig, DifficultyLevel, get_difficulty_config, get_computer_color
from ..engine.engine_adapter import EngineAdapter
from ..logging_config import get_logger

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

    def __init__(self, engine_adapter: Optional[EngineAdapter] = None, config: Optional[GameConfig] = None):
        """
        :param engine_adapter: if supplied, used to generate hints via UCI.
        :param config: game configuration including mode and difficulty
        """
        self.engine_adapter = engine_adapter
        self.board_state = BoardState()
        self.config = config or GameConfig(mode=GameMode.HUMAN_VS_HUMAN)
        self.computer_color: Optional[chess.Color] = None
        
        # Set up computer color if in human vs computer mode
        if self.config.mode == GameMode.HUMAN_VS_COMPUTER:
            self.computer_color = get_computer_color(self.config.human_color)
        
        engine_status = "with engine" if engine_adapter else "without engine"
        mode_status = f"mode: {self.config.mode.value}"
        logger.info(f"Game initialized {engine_status}, {mode_status}")
        
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
    def engine(self) -> Optional[EngineAdapter]:
        """Alias for engine_adapter for backward compatibility."""
        return self.engine_adapter

    def _on_board_move(self, sender, move):
        """Forward board_state.move_made to Game.move_made."""
        self.move_made.send(self, move=move)

    def _on_status(self, sender, status):
        """Forward board_state.status_changed to Game.status_changed."""
        self.status_changed.send(self, status=status)

    def new_game(self, config: Optional[GameConfig] = None):
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

    def apply_move(self, src_square: chess.Square, dst_square: chess.Square, promotion: Optional[chess.PieceType] = None):
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
        if (piece and piece.piece_type == chess.PAWN and 
            ((piece.color == chess.WHITE and chess.square_rank(dst_square) == 7) or
             (piece.color == chess.BLACK and chess.square_rank(dst_square) == 0))):
            # Default to queen promotion if not specified
            if promotion is None:
                promotion = chess.QUEEN
            mv = chess.Move(src_square, dst_square, promotion=promotion)
        else:
            mv = chess.Move(src_square, dst_square)
            
        self.board_state.make_move(mv)

    def request_hint(self, time_ms: int = 1000) -> chess.Move | None:
        """
        Ask the engine adapter for the best move in the current position.
        Emits hint_ready when done.
        :raises RuntimeError if no engine_adapter is set.
        """
        if not self.engine_adapter:
            raise RuntimeError("No chess engine available. Please install Stockfish to get hints.")
        fen = self.board_state._board.fen()
        best_move = self.engine_adapter.get_best_move(fen, time_ms)
        self.hint_ready.send(self, move=best_move)
        return best_move

    def is_computer_turn(self) -> bool:
        """
        Check if it's the computer's turn in human vs computer mode.
        """
        if self.config.mode != GameMode.HUMAN_VS_COMPUTER:
            return False
        return self.board_state.board.turn == self.computer_color

    def request_computer_move(self) -> chess.Move | None:
        """
        Request a move from the computer opponent.
        Uses difficulty-based timing and emits computer_move_ready signal.
        :raises RuntimeError if no engine_adapter is set or not in computer mode.
        """
        if self.config.mode != GameMode.HUMAN_VS_COMPUTER:
            raise RuntimeError("Not in human vs computer mode")
        if not self.engine_adapter:
            raise RuntimeError("No chess engine available for computer opponent")
        if not self.config.difficulty:
            raise RuntimeError("No difficulty level set for computer opponent")
        
        difficulty_config = get_difficulty_config(self.config.difficulty)
        fen = self.board_state._board.fen()
        
        # Use difficulty-based timing
        best_move = self.engine_adapter.get_best_move(fen, difficulty_config.time_ms)
        
        if best_move:
            # Apply the computer's move
            self.board_state.make_move(best_move)
            self.computer_move_ready.send(self, move=best_move)
        
        return best_move

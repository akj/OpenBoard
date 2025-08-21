import chess
import chess.pgn
from io import StringIO
from blinker import Signal
from typing import Optional, List
import threading

from ..models.game import Game
from ..logging_config import get_logger

logger = get_logger(__name__)


PIECE_NAMES = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}


class ChessController:
    """
    Controller in an MVC pattern.  Connects the Game model to a view
    layer via signals, tracks keyboard focus/selection, and handles
    user commands, replay, hints, undo, load, etc.
    """

    # Signals the VIEW should subscribe to:
    board_updated = Signal()  # args: board (chess.Board)
    square_focused = Signal()  # args: square (int 0..63)
    selection_changed = Signal()  # args: selected_square (int|None)
    announce = Signal()  # args: text (str)
    status_changed = Signal()  # args: status (str)
    hint_ready = Signal()  # args: move (chess.Move)
    computer_thinking = Signal()  # args: thinking (bool)

    def __init__(self, game: Game, config: Optional[dict] = None):
        """
        :param game: the Game model
        :param config: e.g. {"announce_mode": "verbose" or "brief"}
        """
        self.game = game
        self.config = config or {}
        self.announce_mode = self.config.get("announce_mode", "verbose")
        
        logger.info(f"ChessController initialized with announce mode: {self.announce_mode}")

        # board navigation & selection
        self.current_square: int = chess.A1  # 0
        self.selected_square: Optional[int] = None

        # for PGN replay
        self._in_replay: bool = False
        self._replay_moves: List[chess.Move] = []
        self._replay_index: int = 0

        # to help generate captures, we stash the pre‐move board when
        # apply_move is called by the controller:
        self._pending_old_board: Optional[chess.Board] = None

        # computer move handling
        self._computer_thinking: bool = False
        self._computer_move_thread: Optional[threading.Thread] = None

        # hook model signals
        game.move_made.connect(self._on_model_move)
        game.board_state.move_undone.connect(self._on_model_undo)
        game.status_changed.connect(self._on_status_changed)
        game.hint_ready.connect(self._on_hint_ready)
        
        # Hook computer move signal if it exists
        if hasattr(game, 'computer_move_ready'):
            game.computer_move_ready.connect(self._on_computer_move_ready)

        # announce initial board
        self._emit_board_update()
        self._announce_square(self.current_square)

    # —— Model signal handlers —— #

    def _on_model_move(self, sender, move: chess.Move):
        """Fired whenever either side (or replay) pushes a move."""
        # tell view the board changed
        self._emit_board_update()

        # announce the move
        ann = self._format_move_announcement(move)
        self.announce.send(self, text=ann)
        
        # Check if computer should move next (but not during replay)
        if not self._in_replay and self.game.is_computer_turn() and not self.game.board_state.board.is_game_over():
            self._request_computer_move_async()

    def _on_model_undo(self, sender, move: chess.Move):
        """Fired whenever a move is undone in model."""
        self._emit_board_update()
        self.announce.send(self, text="Move undone")

    def _on_status_changed(self, sender, status: str):
        """Forward game status changes."""
        self.status_changed.send(self, status=status)
        # If game over, repeat it
        if status != "In progress":
            self.announce.send(self, text=f"Game over: {status}")

    def _on_hint_ready(self, sender, move: chess.Move):
        """Forward engine hints to the view."""
        self.hint_ready.send(self, move=move)

    def _on_computer_move_ready(self, sender, move: chess.Move):
        """Handle computer move completion."""
        self._computer_thinking = False
        self.computer_thinking.send(self, thinking=False)
        # Move announcement is handled by _on_model_move

    # —— Public methods for view events —— #

    def navigate(self, direction: str):
        """
        Move focus one step. direction in {'up','down','left','right'}.
        """
        x = self.current_square % 8
        y = self.current_square // 8

        if direction == "up" and y < 7:
            y += 1
        if direction == "down" and y > 0:
            y -= 1
        if direction == "left" and x > 0:
            x -= 1
        if direction == "right" and x < 7:
            x += 1

        new_sq = y * 8 + x
        if new_sq != self.current_square:
            self.current_square = new_sq
            self.square_focused.send(self, square=new_sq)
            self._announce_square(new_sq)

    def select(self):
        """
        Select or, if already selected on a different square, confirm move.
        Bound to SPACE.
        """
        # Prevent moves during computer thinking
        if self._computer_thinking:
            self.announce.send(self, text="Computer is thinking, please wait")
            return
            
        # Prevent human moves when it's computer's turn
        if self.game.is_computer_turn():
            self.announce.send(self, text="It's the computer's turn")
            return
            
        if self.selected_square is None:
            # pick up a piece
            self.selected_square = self.current_square
            self.selection_changed.send(self, selected_square=self.current_square)
            sq_name = chess.square_name(self.current_square)
            self.announce.send(self, text=f"Selected {sq_name}")
        else:
            # confirm move from selected_square -> current_square
            src = self.selected_square
            dst = self.current_square
            self._do_move(src, dst)
            # clear selection
            self.selected_square = None
            self.selection_changed.send(self, selected_square=None)

    def deselect(self):
        """
        Cancel any selection.  Bound to SHIFT+SPACE.
        """
        if self.selected_square is not None:
            self.selected_square = None
            self.selection_changed.send(self, selected_square=None)
            self.announce.send(self, text="Selection cleared")

    def undo(self):
        """
        Bound to e.g. Ctrl+Z.  Undoes last move if any.
        """
        # in replay mode, stepping back is handled by replay_prev()
        if self._in_replay:
            self.replay_prev()
        else:
            try:
                self.game.board_state.undo_move()
            except IndexError:
                self.announce.send(self, text="Nothing to undo")

    def request_hint(self):
        """
        Bound to e.g. 'H'.  Fires engine hint.
        """
        try:
            self.game.request_hint()
        except RuntimeError as e:
            self.announce.send(self, text=str(e))

    def load_fen(self, fen: str):
        """
        Bound to a menu/button.  Immediately loads a FEN.
        Exits replay mode.
        """
        self._in_replay = False
        self.game.board_state.load_fen(fen)

    def load_pgn(self, pgn_text: str):
        """
        Loads a PGN for manual replay.  Does NOT play out all moves at once.
        """
        self._in_replay = True
        self._replay_moves = []
        self._replay_index = 0

        # parse and store moves
        stream = StringIO(pgn_text)
        pg = chess.pgn.read_game(stream)
        if pg is None:
            self.announce.send(self, text="Invalid PGN")
            return

        for mv in pg.mainline_moves():
            self._replay_moves.append(mv)

        # reset to start
        self.game.board_state.load_fen(chess.STARTING_FEN)
        self._emit_board_update()
        self.announce.send(self, text="PGN loaded; ready to replay")

    def replay_next(self):
        """Bound to F6: step forward one move in PGN replay."""
        if not self._in_replay:
            return
        if self._replay_index < len(self._replay_moves):
            mv = self._replay_moves[self._replay_index]
            self._replay_index += 1
            self.game.board_state.make_move(mv)
        else:
            self.announce.send(self, text="End of game")

    def replay_prev(self):
        """Bound to F5: step back one move in PGN replay."""
        if not self._in_replay:
            return
        if self._replay_index > 0:
            self._replay_index -= 1
            self.game.board_state.undo_move()
        else:
            self.announce.send(self, text="At start of game")

    def toggle_announce_mode(self):
        """
        Switches between brief and verbose announcements.
        """
        self.announce_mode = "brief" if self.announce_mode == "verbose" else "verbose"
        self.announce.send(self, text=f"Announce mode: {self.announce_mode}")

    # —— Internal helpers —— #

    def _do_move(self, src: int, dst: int):
        """
        Wraps Game.apply_move so we can remember the old board for capture detection.
        """
        # stash a copy of the board *before* move
        self._pending_old_board = self.game.board_state.board
        try:
            self.game.apply_move(src, dst)
        except ValueError as e:
            self.announce.send(self, text=str(e))
        finally:
            # clear stash; _on_model_move will read it if present
            self._pending_old_board = None

    def _emit_board_update(self):
        """Pulls a fresh copy of the chess.Board and sends it to the view."""
        b = self.game.board_state.board  # copy()
        self.board_updated.send(self, board=b)

    def _announce_square(self, square: int):
        """
        When focus moves, we say e.g. "White rook on a1" or just "a1 rook"
        depending on mode.
        """
        b = self.game.board_state.board
        piece = b.piece_at(square)
        fname = chess.square_name(square)
        if piece:
            color = "White" if piece.color else "Black"
            name = PIECE_NAMES[piece.piece_type]
            text = (
                f"{color} {name} on {fname}"
                if self.announce_mode == "verbose"
                else f"{name} {fname}"
            )
        else:
            text = fname
        self.announce.send(self, text=text)

    def _format_move_announcement(self, move: chess.Move) -> str:
        """
        Builds either a brief ("e2 e4") or verbose
        ("White pawn from e2 to e4 [takes]") announcement.
        """
        src, dst = move.from_square, move.to_square
        fname_src = chess.square_name(src)
        fname_dst = chess.square_name(dst)
        # determine piece name
        # after move, b.piece_at(dst) is the moved piece:
        bnew = self.game.board_state.board
        p = bnew.piece_at(dst)
        name = PIECE_NAMES[p.piece_type] if p else "piece"
        color = "White" if p.color else "Black"

        # detect captures if we have old board stashed
        took = ""
        if self._pending_old_board:
            if self._pending_old_board.is_capture(move):
                took = " takes"

        # verbose vs brief
        if self.announce_mode == "brief":
            return f"{fname_src} {fname_dst}"
        else:
            return f"{color} {name} from {fname_src} to {fname_dst}{took}"

    # —— Computer move handling —— #

    def _request_computer_move_async(self):
        """Request a computer move in a background thread."""
        if self._computer_thinking:
            return  # Already thinking
            
        if self._computer_move_thread and self._computer_move_thread.is_alive():
            return  # Thread still running
            
        self._computer_thinking = True
        self.computer_thinking.send(self, thinking=True)
        
        # Start computer move in background thread
        self._computer_move_thread = threading.Thread(target=self._compute_computer_move)
        self._computer_move_thread.daemon = True
        self._computer_move_thread.start()

    def _compute_computer_move(self):
        """Compute computer move in background thread."""
        try:
            self.game.request_computer_move()
        except Exception as e:
            logger.error(f"Computer move computation failed: {e}")
            # Signal thinking stopped even on error
            self._computer_thinking = False
            self.computer_thinking.send(self, thinking=False)
            self.announce.send(self, text=f"Computer move failed: {e}")

    def is_computer_thinking(self) -> bool:
        """Check if computer is currently thinking."""
        return self._computer_thinking

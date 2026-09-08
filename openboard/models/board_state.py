import chess
import chess.pgn
from io import StringIO
from blinker import Signal

from ..exceptions import IllegalMoveError


class BoardState:
    """
    Wraps a python-chess Board, centralizes PGN/FEN I/O, move history,
    and emits signals when the position or status changes.
    """

    def __init__(self, fen: str = chess.STARTING_FEN):
        """
        :param fen: initial position in FEN notation (defaults to standard start)
        """
        self._board = chess.Board(fen)
        # Signals:
        #   move_made: sent after a push(move)
        #   move_undone: sent after a pop()
        #   status_changed: sent whenever the game status may have changed
        self.move_made = Signal()
        self.move_undone = Signal()
        self.status_changed = Signal()

    @property
    def board(self) -> chess.Board:
        """
        Return a copy of the current internal board.
        The copy includes move history for repetition detection and engine analysis.
        """
        return self._board.copy()

    @property
    def board_ref(self) -> chess.Board:
        """Read the current position without copying its history. Do not mutate it."""
        return self._board

    def load_fen(self, fen: str):
        """
        Replace the position with the one given by FEN.
        Emits status_changed.
        """
        self._board = chess.Board(fen)
        self.move_made.send(self, move=None, old_board=None)
        self.status_changed.send(self, status=self.game_status())

    def load_pgn(self, pgn_text: str):
        """
        Validate a PGN and replace the position with the end of its mainline.
        Observers see one completed update, never partially imported moves.
        """
        stream = StringIO(pgn_text)
        game = chess.pgn.read_game(stream)
        if game is None:
            raise ValueError("Could not parse PGN data")
        if game.errors:
            raise ValueError(f"Invalid PGN: {game.errors[0]}")
        board = game.board()
        for move in game.mainline_moves():
            board.push(move)
        self._board = board
        self.move_made.send(self, move=None, old_board=None)
        self.status_changed.send(self, status=self.game_status())

    def make_move(self, move: chess.Move):
        """
        Push a move to the board if it is legal.
        Emits move_made and status_changed.
        """
        if move not in self._board.legal_moves:
            raise IllegalMoveError(str(move), self._board.fen())
        old_board = self._board.copy(stack=False)
        self._board.push(move)
        self.move_made.send(
            self, move=move, old_board=old_board
        )  # carry old_board kwarg
        self.status_changed.send(self, status=self.game_status())

    def undo_move(self):
        """
        Pop the last move. Emits move_undone and status_changed.
        """
        if not self._board.move_stack:
            raise IndexError("No moves to undo")
        mv = self._board.pop()
        self.move_undone.send(self, move=mv)
        self.status_changed.send(self, status=self.game_status())

    def legal_moves(self) -> list:
        """Return a list of all legal moves in the current position."""
        return list(self._board.legal_moves)

    def current_turn(self) -> chess.Color:
        """Return chess.WHITE or chess.BLACK for whose turn it is."""
        return self._board.turn

    def game_status(self) -> str:
        """Describe automatic game endings. A claimable draw has not ended the game."""
        outcome = self._board.outcome()
        if outcome is None:
            return "In progress"
        return {
            chess.Termination.CHECKMATE: "Checkmate",
            chess.Termination.STALEMATE: "Stalemate",
            chess.Termination.INSUFFICIENT_MATERIAL: "Draw by insufficient material",
            chess.Termination.SEVENTYFIVE_MOVES: "Draw by seventy-five-move rule",
            chess.Termination.FIVEFOLD_REPETITION: "Draw by fivefold repetition",
        }[outcome.termination]

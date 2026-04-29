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
        # announce initial status
        self.status_changed.send(self, status=self.game_status())

    @property
    def board(self) -> chess.Board:
        """
        Return a copy of the current internal board.
        Use this for inspection or engine‐analysis only; do not mutate.
        """
        return self._board.copy()

    @property
    def board_ref(self) -> chess.Board:
        """Returns the live `chess.Board` for read-only access by controller/view layers.

        Callers MUST NOT mutate (no `push`, `pop`, `set_fen`, etc.).
        Use `board` (snapshot copy) when mutation is possible.

        Performance: avoids the 64-square Board.copy() per access. Use cases include
        paint loops, navigation handlers, and read-only attacker queries.
        (TD-13 / D-18 / CONCERNS.md Performance #3)
        """
        return self._board

    def load_fen(self, fen: str):
        """
        Replace the position with the one given by FEN.
        Emits status_changed.
        """
        self._board.set_fen(fen)
        self.move_made.send(self, move=None, old_board=None)
        self.status_changed.send(self, status=self.game_status())

    def load_pgn(self, pgn_text: str):
        """
        Parse a PGN (possibly with headers) and play out its mainline moves.
        Emits move_made for each move and a final status_changed.
        """
        stream = StringIO(pgn_text)
        game = chess.pgn.read_game(stream)
        if game is None:
            raise ValueError("Could not parse PGN data")
        # reset board to starting position
        self._board = game.board()
        for move in game.mainline_moves():
            old_board = self._board.copy()
            self._board.push(move)
            self.move_made.send(self, move=move, old_board=old_board)
        self.status_changed.send(self, status=self.game_status())

    def make_move(self, move: chess.Move):
        """
        Push a move to the board if it is legal.
        Emits move_made and status_changed.
        """
        if move not in self._board.legal_moves:
            raise IllegalMoveError(str(move), self._board.fen())
        old_board = self._board.copy()  # snapshot for downstream MoveKind computation
        self._board.push(move)
        self.move_made.send(self, move=move, old_board=old_board)  # carry old_board kwarg
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
        """
        Return a human-readable game status:
         - 'Checkmate'
         - 'Stalemate'
         - 'Draw by insufficient material'
         - 'Draw by fifty-move rule'
         - 'In progress'
        """
        b = self._board
        if b.is_checkmate():
            return "Checkmate"
        if b.is_stalemate():
            return "Stalemate"
        if b.is_insufficient_material():
            return "Draw by insufficient material"
        if b.can_claim_fifty_moves():
            return "Draw by fifty-move rule"
        return "In progress"

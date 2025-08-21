import json
import wx

# ...existing code...
import accessible_output3.outputs.auto as ao2

from ..engine.engine_adapter import EngineAdapter
from ..models.game import Game
from ..controllers.chess_controller import ChessController

# Unicode glyphs for pieces:
PIECE_UNICODE = {
    "P": "♙",
    "N": "♘",
    "B": "♗",
    "R": "♖",
    "Q": "♕",
    "K": "♔",
    "p": "♟",
    "n": "♞",
    "b": "♝",
    "r": "♜",
    "q": "♛",
    "k": "♚",
}

SQUARE_SIZE = 60  # pixels


class BoardPanel(wx.Panel):
    """
    Panel that draws the chessboard, pieces, and highlights focus/selection/hint.
    """

    def __init__(self, parent, controller: "ChessController"):
        # wx.Size expects a wx.Size object, not a tuple
        super().__init__(parent, size=wx.Size(8 * SQUARE_SIZE, 8 * SQUARE_SIZE))
        self.controller: "ChessController" = controller
        self.board = controller.game.board_state.board
        self.focus = controller.current_square
        self.selected = None
        self.hint_move = None

        # subscribe to controller signals
        controller.board_updated.connect(self.on_board_updated)
        controller.square_focused.connect(self.on_square_focused)
        self.controller = controller

    def _get_piece(self, square):
        """Safely get the piece at a given square, or None if out of bounds or empty."""
        if self.board is None:
            return None
        try:
            return self.board.piece_at(square)
        except Exception:
            return None

    def _get_piece_color(self, square):
        """Return the color of the piece at the given square, or None if no piece."""
        piece = self._get_piece(square)
        return getattr(piece, "color", None)
        self.controller.selection_changed.connect(self.on_selection_changed)
        self.controller.hint_ready.connect(self.on_hint_ready)

        # enable keyboard focus
        self.SetFocus()
        self.Bind(wx.EVT_PAINT, self.on_paint)

    def on_board_updated(self, sender, board):
        """Model pushed a new board position."""
        self.board = board
        self.Refresh()

    def on_square_focused(self, sender, square):
        """Controller moved the focus."""
        self.focus = square
        self.Refresh()

    def on_selection_changed(self, sender, selected_square):
        """Controller changed selection state."""
        self.selected = selected_square
        self.Refresh()

    def on_hint_ready(self, sender, move):
        """Controller has a hint to show."""
        self.hint_move = move
        self.Refresh()

    def on_paint(self, event):
        dc = wx.PaintDC(self)
        for rank in range(8):
            for file in range(8):
                sq = rank * 8 + file
                x, y = file * SQUARE_SIZE, (7 - rank) * SQUARE_SIZE

                # square color
                light = (file + rank) % 2 == 0
                color = wx.Colour(240, 240, 200) if light else wx.Colour(100, 150, 100)
                dc.SetBrush(wx.Brush(color))
                dc.SetPen(wx.Pen(color))
                dc.DrawRectangle(x, y, SQUARE_SIZE, SQUARE_SIZE)

                # highlight focus
                if sq == self.focus:
                    dc.SetBrush(wx.Brush(wx.Colour(255, 255, 0, 64)))
                    dc.SetPen(wx.Pen(wx.Colour(255, 255, 0)))
                    dc.DrawRectangle(x, y, SQUARE_SIZE, SQUARE_SIZE)

                # highlight selection
                if self.selected == sq:
                    dc.SetBrush(wx.Brush(wx.Colour(0, 128, 255, 96)))
                    dc.SetPen(wx.Pen(wx.Colour(0, 128, 255), 2))
                    dc.DrawRectangle(x + 2, y + 2, SQUARE_SIZE - 4, SQUARE_SIZE - 4)

                # highlight hint move destination
                if self.hint_move and sq == self.hint_move.to_square:
                    dc.SetBrush(wx.Brush(wx.Colour(255, 0, 0, 96)))
                    dc.SetPen(wx.Pen(wx.Colour(255, 0, 0), 2))
                    dc.DrawRectangle(x + 2, y + 2, SQUARE_SIZE - 4, SQUARE_SIZE - 4)

                # draw piece
                piece = self.board.piece_at(sq)
                if piece:
                    glyph = PIECE_UNICODE[piece.symbol()]
                    dc.SetFont(
                        wx.Font(
                            32,
                            wx.FONTFAMILY_SWISS,
                            wx.FONTSTYLE_NORMAL,
                            wx.FONTWEIGHT_BOLD,
                        )
                    )
                    dc.DrawText(glyph, x + 10, y + 8)


class ChessFrame(wx.Frame):
    """
    Main application window.  Wires menus, status bar, key events,
    and instantiates BoardPanel.
    """

    def __init__(self, controller: ChessController):
        # wx.Size expects a wx.Size object, not a tuple
        super().__init__(None, title="Accessible Chess", size=wx.Size(500, 550))
        self.controller = controller
        # Use the correct attribute for accessible_output3
        self.speech = ao2.Auto()

        # create menu
        menu_bar = wx.MenuBar()
        file_menu = wx.Menu()
        file_menu.Append(wx.ID_OPEN, "&Load FEN...\tCtrl-F")
        file_menu.Append(wx.ID_ANY, "Load &PGN...\tCtrl-G")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "E&xit\tCtrl-Q")
        menu_bar.Append(file_menu, "&File")

        options_menu = wx.Menu()
        options_menu.Append(wx.ID_ANY, "&Toggle Announce Mode\tCtrl-T")
        menu_bar.Append(options_menu, "&Options")

        self.SetMenuBar(menu_bar)
        self.status = self.CreateStatusBar()

        # board panel
        self.board_panel = BoardPanel(self, controller)

        # Bind menu events
        self.Bind(wx.EVT_MENU, self.on_load_fen, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self.on_load_pgn, id=wx.ID_ANY)
        self.Bind(wx.EVT_MENU, lambda e: self.Close(), id=wx.ID_EXIT)
        self.Bind(
            wx.EVT_MENU,
            lambda e: controller.toggle_announce_mode(),
            id=options_menu.GetMenuItems()[0].GetId(),
        )

        # Bind key events for navigation & commands
        self.board_panel.Bind(wx.EVT_CHAR_HOOK, self.on_key)

        # Subscribe to controller signals
        controller.announce.connect(self.on_announce)
        controller.status_changed.connect(self.on_status_changed)

        self.Show()

    def on_load_fen(self, event):
        with wx.TextEntryDialog(self, "Enter FEN:", "Load FEN") as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                fen = dlg.GetValue().strip()
                self.controller.load_fen(fen)

    def on_load_pgn(self, event):
        with wx.FileDialog(
            self,
            "Open PGN file",
            wildcard="PGN files (*.pgn)|*.pgn",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                path = dlg.GetPath()
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
                self.controller.load_pgn(text)

    def on_key(self, event):
        """
        Map arrow keys, space, shift+space, F5/F6, Ctrl+Z, H to controller.
        """
        key = event.GetKeyCode()
        shift = event.ShiftDown()
        ctrl = event.ControlDown()

        # navigation
        if key == wx.WXK_UP:
            self.controller.navigate("up")
        elif key == wx.WXK_DOWN:
            self.controller.navigate("down")
        elif key == wx.WXK_LEFT:
            self.controller.navigate("left")
        elif key == wx.WXK_RIGHT:
            self.controller.navigate("right")
        # select / deselect
        elif key == ord(" ") and not shift:
            self.controller.select()
        elif key == ord(" ") and shift:
            self.controller.deselect()
        # undo
        elif key == ord("Z") and ctrl:
            self.controller.undo()
        # hint
        elif key == ord("H"):
            self.controller.request_hint()
        # PGN replay
        elif key == wx.WXK_F5:
            self.controller.replay_prev()
        elif key == wx.WXK_F6:
            self.controller.replay_next()
        # toggle announce
        elif key == ord("T") and ctrl:
            self.controller.toggle_announce_mode()
        else:
            # skip unhandled
            event.Skip()

    def on_announce(self, sender, text: str):
        """Speak and echo the announcement."""
        self.speech.speak(text)
        self.status.SetStatusText(text)

    def on_status_changed(self, sender, status: str):
        """Update the status bar on game-status changes."""
        self.status.SetStatusText(status)


def main():
    # load config
    try:
        with open("config.json") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {"announce_mode": "verbose"}

    # set up engine & game
    try:
        engine = EngineAdapter(options={"Threads": 2, "Hash": 128})
        engine.start()
        game = Game(engine)
    except RuntimeError as e:
        print(f"Engine initialization failed: {e}")
        # Fall back to no engine mode
        game = Game()

    # controller
    controller = ChessController(game, config=cfg)

    # wx App
    app = wx.App(False)
    ChessFrame(controller)
    app.MainLoop()

    # Clean up engine if it was created
    if game.engine:
        game.engine.stop()


if __name__ == "__main__":
    main()

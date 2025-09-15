import json
import wx
import chess
from pathlib import Path

import accessible_output3.outputs.auto as ao2

from ..engine.engine_adapter import EngineAdapter
from ..models.game import Game
from ..models.game_mode import GameMode, GameConfig
from ..controllers.chess_controller import ChessController
from ..logging_config import get_logger, setup_logging
from ..config.settings import get_settings
from ..config.keyboard_config import (
    GameKeyboardConfig,
    KeyboardCommandHandler,
    KeyAction,
    load_keyboard_config_from_json,
)
from ..exceptions import EngineError, EngineNotFoundError, EngineInitializationError
from .game_dialogs import (
    show_game_setup_dialog,
    show_difficulty_info_dialog,
    show_computer_vs_computer_dialog,
    show_move_list_dialog,
)

logger = get_logger(__name__)

# Get application settings
settings = get_settings()


class BoardPanel(wx.Panel):
    """
    Panel that draws the chessboard, pieces, and highlights focus/selection/hint.
    """

    def __init__(self, parent, controller: "ChessController"):
        # wx.Size expects a wx.Size object, not a tuple
        super().__init__(
            parent, size=wx.Size(settings.ui.board_size, settings.ui.board_size)
        )
        self.controller: "ChessController" = controller
        self.board = controller.game.board_state.board
        self.focus = controller.current_square
        self.selected = None
        self.hint_move = None

        # Set accessible name based on game mode
        accessible_name = self._get_accessible_panel_name()
        self.SetName(accessible_name)
        self.SetLabel(accessible_name)

        # subscribe to controller signals
        controller.board_updated.connect(self.on_board_updated)
        controller.square_focused.connect(self.on_square_focused)
        controller.selection_changed.connect(self.on_selection_changed)
        controller.hint_ready.connect(self.on_hint_ready)

        # enable keyboard focus
        self.SetFocus()
        self.Bind(wx.EVT_PAINT, self.on_paint)

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
                x, y = (
                    file * settings.ui.square_size,
                    (7 - rank) * settings.ui.square_size,
                )

                # square color
                light = (file + rank) % 2 == 0
                color = wx.Colour(240, 240, 200) if light else wx.Colour(100, 150, 100)
                dc.SetBrush(wx.Brush(color))
                dc.SetPen(wx.Pen(color))
                dc.DrawRectangle(x, y, settings.ui.square_size, settings.ui.square_size)

                # highlight focus
                if sq == self.focus:
                    dc.SetBrush(wx.Brush(wx.Colour(255, 255, 0, 64)))
                    dc.SetPen(wx.Pen(wx.Colour(255, 255, 0)))
                    dc.DrawRectangle(
                        x, y, settings.ui.square_size, settings.ui.square_size
                    )

                # highlight selection
                if self.selected == sq:
                    dc.SetBrush(wx.Brush(wx.Colour(0, 128, 255, 96)))
                    dc.SetPen(wx.Pen(wx.Colour(0, 128, 255), 2))
                    dc.DrawRectangle(
                        x + 2,
                        y + 2,
                        settings.ui.square_size - 4,
                        settings.ui.square_size - 4,
                    )

                # highlight hint move destination
                if self.hint_move and sq == self.hint_move.to_square:
                    dc.SetBrush(wx.Brush(wx.Colour(255, 0, 0, 96)))
                    dc.SetPen(wx.Pen(wx.Colour(255, 0, 0), 2))
                    dc.DrawRectangle(
                        x + 2,
                        y + 2,
                        settings.ui.square_size - 4,
                        settings.ui.square_size - 4,
                    )

                # draw piece
                piece = self.board.piece_at(sq)
                if piece:
                    glyph = settings.ui.piece_unicode[piece.symbol()]
                    dc.SetFont(
                        wx.Font(
                            32,
                            wx.FONTFAMILY_SWISS,
                            wx.FONTSTYLE_NORMAL,
                            wx.FONTWEIGHT_BOLD,
                        )
                    )
                    dc.DrawText(glyph, x + 10, y + 8)

    def _get_accessible_panel_name(self):
        """Generate accessible panel name based on game mode."""
        from ..models.game_mode import GameMode

        mode = self.controller.game.config.mode

        match mode:
            case GameMode.HUMAN_VS_HUMAN:
                return "Chess board - Human vs Human"
            case GameMode.HUMAN_VS_COMPUTER:
                difficulty = self.controller.game.config.difficulty
                if difficulty:
                    return f"Chess board - Human vs Computer ({difficulty})"
                else:
                    return "Chess board - Human vs Computer"
            case GameMode.COMPUTER_VS_COMPUTER:
                white_diff = self.controller.game.config.white_difficulty
                black_diff = self.controller.game.config.black_difficulty
                if white_diff and black_diff:
                    return f"Chess board - Computer vs Computer (White: {white_diff}, Black: {black_diff})"
                else:
                    return "Chess board - Computer vs Computer"
            case _:
                return "Chess board"


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

        # Initialize keyboard configuration
        self.keyboard_config = self._load_keyboard_config()
        self.keyboard_handler = self._create_keyboard_handler()

        # create menu
        menu_bar = wx.MenuBar()
        file_menu = wx.Menu()
        file_menu.Append(wx.ID_OPEN, "&Load FEN...\tCtrl-F")
        file_menu.Append(wx.ID_ANY, "Load &PGN...\tCtrl-G")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, "E&xit\tCtrl-Q")
        menu_bar.Append(file_menu, "&File")

        # Game menu
        game_menu = wx.Menu()
        game_menu.Append(wx.ID_ANY, "New Game: &Human vs Human\tCtrl-N")
        game_menu.Append(wx.ID_ANY, "New Game: Human vs &Computer\tCtrl-M")
        game_menu.Append(wx.ID_ANY, "New Game: Computer vs Computer\tCtrl-K")
        game_menu.AppendSeparator()
        game_menu.Append(wx.ID_ANY, "&Difficulty Info...")
        menu_bar.Append(game_menu, "&Game")

        options_menu = wx.Menu()
        options_menu.Append(wx.ID_ANY, "&Toggle Announce Mode\tCtrl-T")
        menu_bar.Append(options_menu, "&Options")

        # Engine menu
        engine_menu = wx.Menu()
        engine_menu.Append(wx.ID_ANY, "&Install Stockfish...")
        engine_menu.Append(wx.ID_ANY, "&Update Stockfish...")
        engine_menu.AppendSeparator()
        engine_menu.Append(wx.ID_ANY, "Check Engine &Status...")
        menu_bar.Append(engine_menu, "&Engine")

        # Opening Book menu
        book_menu = wx.Menu()
        book_menu.Append(wx.ID_ANY, "&Load Opening Book...\tCtrl-B")
        book_menu.Append(wx.ID_ANY, "&Unload Opening Book")
        book_menu.AppendSeparator()
        book_menu.Append(wx.ID_ANY, "&Book Hint\tB")
        book_menu.Append(wx.ID_ANY, "Check Book &Moves")
        menu_bar.Append(book_menu, "Opening &Book")

        self.SetMenuBar(menu_bar)
        self.status = self.CreateStatusBar()

        # board panel
        self.board_panel = BoardPanel(self, controller)

        # Bind menu events
        self.Bind(wx.EVT_MENU, self.on_load_fen, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self.on_load_pgn, id=wx.ID_ANY)
        self.Bind(wx.EVT_MENU, lambda e: self.Close(), id=wx.ID_EXIT)

        # Bind game menu events
        self.Bind(
            wx.EVT_MENU,
            self.on_new_human_vs_human,
            id=game_menu.GetMenuItems()[0].GetId(),
        )
        self.Bind(
            wx.EVT_MENU,
            self.on_new_human_vs_computer,
            id=game_menu.GetMenuItems()[1].GetId(),
        )
        self.Bind(
            wx.EVT_MENU,
            self.on_new_computer_vs_computer,
            id=game_menu.GetMenuItems()[2].GetId(),
        )
        self.Bind(
            wx.EVT_MENU, self.on_difficulty_info, id=game_menu.GetMenuItems()[4].GetId()
        )

        self.Bind(
            wx.EVT_MENU,
            lambda e: controller.toggle_announce_mode(),
            id=options_menu.GetMenuItems()[0].GetId(),
        )

        # Bind engine menu events
        self.Bind(
            wx.EVT_MENU,
            self.on_install_stockfish,
            id=engine_menu.GetMenuItems()[0].GetId(),
        )
        self.Bind(
            wx.EVT_MENU,
            self.on_update_stockfish,
            id=engine_menu.GetMenuItems()[1].GetId(),
        )
        self.Bind(
            wx.EVT_MENU,
            self.on_check_engine_status,
            id=engine_menu.GetMenuItems()[3].GetId(),
        )

        # Bind opening book menu events
        self.Bind(
            wx.EVT_MENU,
            self.on_load_opening_book,
            id=book_menu.GetMenuItems()[0].GetId(),
        )
        self.Bind(
            wx.EVT_MENU,
            self.on_unload_opening_book,
            id=book_menu.GetMenuItems()[1].GetId(),
        )
        self.Bind(
            wx.EVT_MENU,
            self.on_book_hint,
            id=book_menu.GetMenuItems()[3].GetId(),
        )
        self.Bind(
            wx.EVT_MENU,
            self.on_check_book_moves,
            id=book_menu.GetMenuItems()[4].GetId(),
        )

        # Bind key events for navigation & commands
        self.board_panel.Bind(wx.EVT_CHAR_HOOK, self.on_key)

        # Subscribe to controller signals
        controller.announce.connect(self.on_announce)
        controller.status_changed.connect(self.on_status_changed)
        controller.hint_ready.connect(self.on_hint_ready)
        controller.computer_thinking.connect(self.on_computer_thinking)

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
        """Handle keyboard events using configuration-based system."""
        key = event.GetKeyCode()
        shift = event.ShiftDown()
        ctrl = event.ControlDown()
        alt = event.AltDown()

        # Try to handle the key event using the configuration system
        if self.keyboard_handler.handle_key_event(key, shift, ctrl, alt):
            return  # Event was handled

        # If not handled, skip the event
        event.Skip()

    def on_announce(self, sender, text: str):
        """Speak and echo the announcement."""
        self.speech.speak(text)
        self.status.SetStatusText(text)

    def on_status_changed(self, sender, status: str):
        """Update the status bar on game-status changes."""
        self.status.SetStatusText(status)

    def on_hint_ready(self, sender, move):
        """Handle hint ready signal and announce the suggested move."""
        if move:
            # Convert the move to a human-readable format
            move_text = self._format_move_for_speech(move)
            hint_message = f"Hint: {move_text}"

            # Announce the hint using the controller's announce system
            self.controller.announce.send(self.controller, text=hint_message)
        else:
            # No move available (shouldn't happen, but handle gracefully)
            no_hint_message = "No hint available"
            self.controller.announce.send(self.controller, text=no_hint_message)

    def _format_move_for_speech(self, move):
        """Format a chess move for speech output."""
        import chess

        # Get basic move notation
        if move is None:
            return "no move"

        # Use algebraic notation for the move
        board = self.controller.game.board_state.board

        try:
            # Get standard algebraic notation (SAN) - e.g. "Nf3", "e4", "O-O"
            san = board.san(move)

            # Make it more speech-friendly
            san_speech = san.replace("+", " check").replace("#", " checkmate")
            san_speech = san_speech.replace("O-O-O", "castle queenside").replace(
                "O-O", "castle kingside"
            )

            # Add "from" and "to" squares for clarity
            from_square = chess.square_name(move.from_square)
            to_square = chess.square_name(move.to_square)

            # Format: "Knight f3 (from g1 to f3)" or "e4 (from e2 to e4)"
            return f"{san_speech}, from {from_square} to {to_square}"

        except Exception:
            # Fallback to basic UCI notation if SAN fails
            return f"from {chess.square_name(move.from_square)} to {chess.square_name(move.to_square)}"

    def on_install_stockfish(self, event):
        """Handle Engine > Install Stockfish menu selection."""
        from ..engine.stockfish_manager import StockfishManager
        from .engine_dialogs import EngineInstallationRunner

        manager = StockfishManager()

        if not manager.can_install():
            instructions = manager.get_installation_instructions()
            wx.MessageBox(
                f"Automatic installation is not supported on this platform.\n\n{instructions}",
                "Manual Installation Required",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        # Check if already installed
        status = manager.get_status()
        if status["local_installed"] and not status["update_available"]:
            result = wx.MessageBox(
                f"Stockfish {status['local_version']} is already installed.\n\nDo you want to reinstall?",
                "Already Installed",
                wx.YES_NO | wx.ICON_QUESTION,
            )
            if result != wx.YES:
                return

        # Run installation
        runner = EngineInstallationRunner(self, manager)
        runner.start_installation()

    def on_update_stockfish(self, event):
        """Handle Engine > Update Stockfish menu selection."""
        from ..engine.stockfish_manager import StockfishManager
        from .engine_dialogs import EngineInstallationRunner

        manager = StockfishManager()
        status = manager.get_status()

        if not status["local_installed"]:
            result = wx.MessageBox(
                "No local Stockfish installation found.\n\nWould you like to install it now?",
                "Not Installed",
                wx.YES_NO | wx.ICON_QUESTION,
            )
            if result == wx.YES:
                self.on_install_stockfish(event)
            return

        if not status["update_available"]:
            wx.MessageBox(
                f"Stockfish {status['local_version']} is already up to date.",
                "Up to Date",
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        # Run update
        runner = EngineInstallationRunner(self, manager)
        runner.start_installation()

    def on_check_engine_status(self, event):
        """Handle Engine > Check Engine Status menu selection."""
        from ..engine.stockfish_manager import StockfishManager
        from .engine_dialogs import EngineStatusDialog

        manager = StockfishManager()

        with EngineStatusDialog(self, manager) as dialog:
            result = dialog.ShowModal()

            # If user clicked Install/Update, trigger installation
            if result == wx.ID_OK:
                status = manager.get_status()
                if status["update_available"]:
                    self.on_update_stockfish(event)
                else:
                    self.on_install_stockfish(event)

    def on_load_opening_book(self, event):
        """Handle Opening Book > Load Opening Book menu selection."""
        with wx.FileDialog(
            self,
            "Select Opening Book File",
            wildcard="Polyglot opening book files (*.bin)|*.bin|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_OK:
                book_path = file_dialog.GetPath()
                try:
                    self.controller.load_opening_book(book_path)
                except Exception as e:
                    wx.MessageBox(
                        f"Failed to load opening book:\n{e}",
                        "Opening Book Error",
                        wx.OK | wx.ICON_ERROR,
                    )

    def on_unload_opening_book(self, event):
        """Handle Opening Book > Unload Opening Book menu selection."""
        self.controller.unload_opening_book()

    def on_book_hint(self, event):
        """Handle Opening Book > Book Hint menu selection."""
        self.controller.request_book_hint()

    def on_check_book_moves(self, event):
        """Handle Opening Book > Check Book Moves menu selection."""
        self.controller.check_book_moves()

    def on_new_human_vs_human(self, event):
        """Handle Game > New Game: Human vs Human menu selection."""
        config = GameConfig(mode=GameMode.HUMAN_VS_HUMAN, human_color=chess.WHITE)
        self.controller.game.new_game(config)
        self.controller.announce.send(
            self.controller, text="New human vs human game started"
        )

    def on_new_human_vs_computer(self, event):
        """Handle Game > New Game: Human vs Computer menu selection."""
        if not self.controller.game.engine_adapter:
            wx.MessageBox(
                "No chess engine available. Please install Stockfish to play against the computer.",
                "Engine Required",
                wx.OK | wx.ICON_WARNING,
            )
            return

        # Show game setup dialog
        result = show_game_setup_dialog(self)
        if result:
            human_color, difficulty = result
            config = GameConfig(
                mode=GameMode.HUMAN_VS_COMPUTER,
                human_color=human_color,
                difficulty=difficulty,
            )
            self.controller.game.new_game(config)

            color_name = "White" if human_color == chess.WHITE else "Black"
            difficulty_name = difficulty.title()
            message = f"New game started: You are {color_name}, Computer is {difficulty_name} level"
            self.controller.announce.send(self.controller, text=message)

            # If computer plays white, start its move
            if self.controller.game.is_computer_turn():
                self.controller._request_computer_move_async()

    def on_new_computer_vs_computer(self, event):
        """Handle Game > New Game: Computer vs Computer menu selection."""
        if not self.controller.game.engine_adapter:
            wx.MessageBox(
                "No chess engine available. Please install Stockfish to play computer vs computer games.",
                "Engine Required",
                wx.OK | wx.ICON_WARNING,
            )
            return

        result = show_computer_vs_computer_dialog(self)
        if result:
            white_difficulty, black_difficulty = result
            config = GameConfig(
                mode=GameMode.COMPUTER_VS_COMPUTER,
                white_difficulty=white_difficulty,
                black_difficulty=black_difficulty,
            )
            self.controller.game.new_game(config)
            self.controller.announce.send(
                self.controller,
                text=f"New computer vs computer game started. White: {white_difficulty}, Black: {black_difficulty}",
            )

            # Start the first computer move if it's white's turn
            if self.controller.game.is_computer_turn():
                self.controller._request_computer_move_async()

    def on_difficulty_info(self, event):
        """Handle Game > Difficulty Info menu selection."""
        show_difficulty_info_dialog(self)

    def on_computer_thinking(self, sender, thinking: bool):
        """Handle computer thinking status changes."""
        # No longer show thinking message - just handle the signal
        pass

    def on_show_move_list(self):
        """Show the move list dialog (Ctrl+L)."""
        # Get current move list from board state
        move_list = list(self.controller.game.board_state.board.move_stack)

        if not move_list:
            # Use controller's announce system instead of direct speech
            self.controller.announce.send(
                self.controller, text="No moves in current game"
            )
            return

        # Check if game is ongoing (not finished) and not in replay mode
        board = self.controller.game.board_state.board
        is_in_replay = self.controller._in_replay
        game_is_ongoing = not board.is_game_over() and not is_in_replay

        # Calculate current position (number of moves played)
        current_position = len(move_list) - 1

        # Show dialog with navigation disabled only for ongoing non-replay games
        selected_position = show_move_list_dialog(
            self,
            move_list,
            current_position,
            allow_navigation=not game_is_ongoing,
            is_ongoing_game=game_is_ongoing,
        )

        # Only navigate if game is finished or in replay mode and user selected a position
        if selected_position is not None and game_is_ongoing:
            self.controller.announce.send(
                self.controller,
                text="Cannot navigate to different positions during an ongoing game",
            )
        elif selected_position is not None:
            # Navigate to the selected position (game is finished or in replay mode)
            self._navigate_to_position(selected_position, move_list)

    def _navigate_to_position(self, target_position: int, move_list):
        """Navigate to a specific position in the game."""
        current_position = len(self.controller.game.board_state.board.move_stack) - 1

        if target_position == current_position:
            self.controller.announce.send(
                self.controller, text="Already at selected position"
            )
            return

        # Calculate how many moves to undo or redo
        if target_position < current_position:
            # Need to undo moves
            moves_to_undo = current_position - target_position
            for _ in range(moves_to_undo):
                try:
                    self.controller.undo()
                except IndexError:
                    break

            if target_position < 0:
                self.controller.announce.send(
                    self.controller, text="Navigated to starting position"
                )
            else:
                self.controller.announce.send(
                    self.controller,
                    text=f"Navigated to position after move {target_position + 1}",
                )

        elif target_position > current_position:
            # Need to replay moves
            board = self.controller.game.board_state.board
            moves_to_replay = target_position - current_position

            for i in range(moves_to_replay):
                move_index = current_position + 1 + i
                if move_index < len(move_list):
                    move = move_list[move_index]
                    try:
                        board.push(move)
                        # Emit the move signal manually to update the view
                        self.controller.game.board_state.move_made.send(
                            self.controller.game.board_state, move=move
                        )
                    except (ValueError, IndexError):
                        break

            self.controller.announce.send(
                self.controller,
                text=f"Navigated to position after move {target_position + 1}",
            )

    def _load_keyboard_config(self) -> GameKeyboardConfig:
        """Load keyboard configuration from JSON file or use default."""
        config_path = (
            Path(__file__).parent.parent.parent / "config" / "keyboard_config.json"
        )

        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    json_data = f.read()
                return load_keyboard_config_from_json(json_data)
            except Exception as e:
                logger.warning(
                    f"Failed to load keyboard config from {config_path}: {e}"
                )

        # Return default configuration
        return GameKeyboardConfig()

    def _create_keyboard_handler(self) -> KeyboardCommandHandler:
        """Create keyboard command handler with action mappings."""
        action_handlers = {
            KeyAction.NAVIGATE_UP: lambda: self.controller.navigate("up"),
            KeyAction.NAVIGATE_DOWN: lambda: self.controller.navigate("down"),
            KeyAction.NAVIGATE_LEFT: lambda: self.controller.navigate("left"),
            KeyAction.NAVIGATE_RIGHT: lambda: self.controller.navigate("right"),
            KeyAction.SELECT: lambda: self.controller.select(),
            KeyAction.DESELECT: lambda: self.controller.deselect(),
            KeyAction.UNDO: lambda: self.controller.undo(),
            KeyAction.REQUEST_HINT: lambda: self.controller.request_hint(),
            KeyAction.REQUEST_BOOK_HINT: lambda: self.controller.request_book_hint(),
            KeyAction.REPLAY_PREV: lambda: self.controller.replay_prev(),
            KeyAction.REPLAY_NEXT: lambda: self.controller.replay_next(),
            KeyAction.TOGGLE_ANNOUNCE_MODE: lambda: self.controller.toggle_announce_mode(),
            KeyAction.SHOW_MOVE_LIST: lambda: self.on_show_move_list(),
            KeyAction.ANNOUNCE_LAST_MOVE: lambda: self.controller.announce_last_move(),
            KeyAction.ANNOUNCE_LEGAL_MOVES: lambda: self.controller.announce_legal_moves(),
            KeyAction.ANNOUNCE_ATTACKING_PIECES: lambda: self.controller.announce_attacking_pieces(),
        }

        return KeyboardCommandHandler(self.keyboard_config, action_handlers)


def main():
    # Initialize logging
    setup_logging(log_level="INFO", console_output=True)
    logger.info("Starting OpenBoard")

    # load config
    try:
        with open("config.json") as f:
            cfg = json.load(f)
        logger.info("Configuration loaded from config.json")
    except Exception as e:
        cfg = {"announce_mode": "verbose"}
        logger.info(
            f"Using default configuration (config.json not found or invalid: {e})"
        )

    # set up engine & game
    try:
        engine = EngineAdapter(options={"Threads": 2, "Hash": 128})
        engine.start()
        game = Game(engine)
        logger.info("Engine initialized successfully")
    except (EngineError, EngineNotFoundError, EngineInitializationError) as e:
        logger.warning(f"Engine initialization failed: {e}")
        # Fall back to no engine mode
        game = Game()
        logger.info("Running in engine-free mode")

    # controller
    controller = ChessController(game, config=cfg)

    # wx App
    logger.info("Initializing GUI")
    app = wx.App(False)
    ChessFrame(controller)
    logger.info("Starting main event loop")
    app.MainLoop()

    # Clean up engine if it was created
    if game.engine:
        logger.info("Shutting down engine")
        game.engine.stop()

    logger.info("OpenBoard shutdown complete")


if __name__ == "__main__":
    main()

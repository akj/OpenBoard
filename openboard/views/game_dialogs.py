"""Dialogs for game setup and configuration."""

import wx
import chess
from typing import Tuple, List

from ..models.game_mode import DifficultyLevel, DIFFICULTY_CONFIGS


class GameSetupDialog(wx.Dialog):
    """Dialog for setting up a new human vs computer game."""

    def __init__(self, parent):
        super().__init__(
            parent,
            title="New Game vs Computer",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.human_color: chess.Color = chess.WHITE
        self.difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE

        self._create_controls()
        self._layout_controls()
        self._bind_events()

        # Set initial focus
        self.color_white_radio.SetFocus()

    def _create_controls(self):
        """Create dialog controls."""
        # Color selection
        self.color_label = wx.StaticText(self, label="Choose your color:")
        self.color_white_radio = wx.RadioButton(
            self, label="Play as White", style=wx.RB_GROUP
        )
        self.color_black_radio = wx.RadioButton(self, label="Play as Black")
        self.color_white_radio.SetValue(True)

        # Difficulty selection
        self.difficulty_label = wx.StaticText(self, label="Choose difficulty:")
        self.difficulty_choice = wx.Choice(self)

        # Populate difficulty choices
        for level in DifficultyLevel:
            config = DIFFICULTY_CONFIGS[level]
            label = f"{config.name} - {config.description}"
            self.difficulty_choice.Append(label, level)

        # Set default to Intermediate
        for i, level in enumerate(DifficultyLevel):
            if level == DifficultyLevel.INTERMEDIATE:
                self.difficulty_choice.SetSelection(i)
                break

        # Buttons
        self.ok_button = wx.Button(self, wx.ID_OK, "Start Game")
        self.cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")

        # Make OK button default
        self.ok_button.SetDefault()

    def _layout_controls(self):
        """Layout dialog controls."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Color selection section
        color_box = wx.StaticBoxSizer(wx.VERTICAL, self, "Color Selection")
        color_box.Add(self.color_label, 0, wx.ALL, 5)
        color_box.Add(self.color_white_radio, 0, wx.ALL, 5)
        color_box.Add(self.color_black_radio, 0, wx.ALL, 5)

        # Difficulty selection section
        difficulty_box = wx.StaticBoxSizer(wx.VERTICAL, self, "Difficulty")
        difficulty_box.Add(self.difficulty_label, 0, wx.ALL, 5)
        difficulty_box.Add(self.difficulty_choice, 0, wx.ALL | wx.EXPAND, 5)

        # Button section
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.Add(self.ok_button, 0, wx.ALL, 5)
        button_sizer.Add(self.cancel_button, 0, wx.ALL, 5)

        # Main layout
        main_sizer.Add(color_box, 0, wx.ALL | wx.EXPAND, 10)
        main_sizer.Add(difficulty_box, 0, wx.ALL | wx.EXPAND, 10)
        main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.SetSizer(main_sizer)
        self.Fit()

    def _bind_events(self):
        """Bind event handlers."""
        self.color_white_radio.Bind(wx.EVT_RADIOBUTTON, self._on_color_change)
        self.color_black_radio.Bind(wx.EVT_RADIOBUTTON, self._on_color_change)
        self.difficulty_choice.Bind(wx.EVT_CHOICE, self._on_difficulty_change)

    def _on_color_change(self, event):
        """Handle color selection change."""
        if self.color_white_radio.GetValue():
            self.human_color = chess.WHITE
        else:
            self.human_color = chess.BLACK

    def _on_difficulty_change(self, event):
        """Handle difficulty selection change."""
        selection = self.difficulty_choice.GetSelection()
        if selection != wx.NOT_FOUND:
            self.difficulty = self.difficulty_choice.GetClientData(selection)

    def get_game_config(self) -> Tuple[chess.Color, DifficultyLevel]:
        """Get the selected game configuration."""
        return self.human_color, self.difficulty


class DifficultyInfoDialog(wx.Dialog):
    """Dialog showing detailed information about difficulty levels."""

    def __init__(self, parent):
        super().__init__(
            parent,
            title="Difficulty Levels",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self._create_controls()
        self._layout_controls()

        # Set minimum size
        self.SetMinSize(wx.Size(400, 300))

    def _create_controls(self):
        """Create dialog controls."""
        # Info text
        info_text = []
        for level in DifficultyLevel:
            config = DIFFICULTY_CONFIGS[level]
            info_text.append(f"**{config.name}**")
            info_text.append(f"  {config.description}")
            info_text.append(f"  Think time: {config.time_ms}ms")
            if config.depth:
                info_text.append(f"  Search depth: {config.depth}")
            info_text.append("")

        self.info_text = wx.TextCtrl(
            self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP
        )
        self.info_text.SetValue("\n".join(info_text))

        # Close button
        self.close_button = wx.Button(self, wx.ID_OK, "Close")
        self.close_button.SetDefault()

    def _layout_controls(self):
        """Layout dialog controls."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        main_sizer.Add(
            wx.StaticText(self, label="Difficulty Level Information:"), 0, wx.ALL, 10
        )
        main_sizer.Add(self.info_text, 1, wx.ALL | wx.EXPAND, 10)
        main_sizer.Add(self.close_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.SetSizer(main_sizer)


def show_game_setup_dialog(parent) -> Tuple[chess.Color, DifficultyLevel] | None:
    """
    Show the game setup dialog and return the selected configuration.

    Returns:
        Tuple of (human_color, difficulty) if OK was clicked, None if cancelled.
    """
    with GameSetupDialog(parent) as dialog:
        if dialog.ShowModal() == wx.ID_OK:
            return dialog.get_game_config()
    return None


class ComputerVsComputerDialog(wx.Dialog):
    """Dialog for setting up a computer vs computer game."""

    def __init__(self, parent):
        super().__init__(
            parent,
            title="New Computer vs Computer Game",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.white_difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE
        self.black_difficulty: DifficultyLevel = DifficultyLevel.INTERMEDIATE

        self._create_controls()
        self._layout_controls()
        self._bind_events()

        # Set initial focus
        self.white_choice.SetFocus()

    def _create_controls(self):
        """Create dialog controls."""
        # White computer difficulty selection
        self.white_label = wx.StaticText(self, label="White computer difficulty:")
        self.white_choice = wx.Choice(self)

        # Black computer difficulty selection
        self.black_label = wx.StaticText(self, label="Black computer difficulty:")
        self.black_choice = wx.Choice(self)

        # Populate difficulty choices for both
        for choice in [self.white_choice, self.black_choice]:
            for level in DifficultyLevel:
                config = DIFFICULTY_CONFIGS[level]
                label = f"{config.name} - {config.description}"
                choice.Append(label, level)

            # Set default to Intermediate
            for i, level in enumerate(DifficultyLevel):
                if level == DifficultyLevel.INTERMEDIATE:
                    choice.SetSelection(i)
                    break

        # Buttons
        self.ok_button = wx.Button(self, wx.ID_OK, "Start Game")
        self.cancel_button = wx.Button(self, wx.ID_CANCEL, "Cancel")

        # Make OK button default
        self.ok_button.SetDefault()

    def _layout_controls(self):
        """Layout dialog controls."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # White difficulty selection section
        white_box = wx.StaticBoxSizer(wx.VERTICAL, self, "White Computer")
        white_box.Add(self.white_label, 0, wx.ALL, 5)
        white_box.Add(self.white_choice, 0, wx.ALL | wx.EXPAND, 5)

        # Black difficulty selection section
        black_box = wx.StaticBoxSizer(wx.VERTICAL, self, "Black Computer")
        black_box.Add(self.black_label, 0, wx.ALL, 5)
        black_box.Add(self.black_choice, 0, wx.ALL | wx.EXPAND, 5)

        # Button section
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.Add(self.ok_button, 0, wx.ALL, 5)
        button_sizer.Add(self.cancel_button, 0, wx.ALL, 5)

        # Main layout
        main_sizer.Add(white_box, 0, wx.ALL | wx.EXPAND, 10)
        main_sizer.Add(black_box, 0, wx.ALL | wx.EXPAND, 10)
        main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        self.SetSizer(main_sizer)
        self.Fit()

    def _bind_events(self):
        """Bind event handlers."""
        self.white_choice.Bind(wx.EVT_CHOICE, self._on_white_difficulty_change)
        self.black_choice.Bind(wx.EVT_CHOICE, self._on_black_difficulty_change)

    def _on_white_difficulty_change(self, event):
        """Handle white difficulty selection change."""
        selection = self.white_choice.GetSelection()
        if selection != wx.NOT_FOUND:
            self.white_difficulty = self.white_choice.GetClientData(selection)

    def _on_black_difficulty_change(self, event):
        """Handle black difficulty selection change."""
        selection = self.black_choice.GetSelection()
        if selection != wx.NOT_FOUND:
            self.black_difficulty = self.black_choice.GetClientData(selection)

    def get_game_config(self) -> Tuple[DifficultyLevel, DifficultyLevel]:
        """Get the selected game configuration."""
        return self.white_difficulty, self.black_difficulty


def show_computer_vs_computer_dialog(
    parent,
) -> Tuple[DifficultyLevel, DifficultyLevel] | None:
    """
    Show the computer vs computer setup dialog and return the selected configuration.

    Returns:
        Tuple of (white_difficulty, black_difficulty) if OK was clicked, None if cancelled.
    """
    with ComputerVsComputerDialog(parent) as dialog:
        if dialog.ShowModal() == wx.ID_OK:
            return dialog.get_game_config()
    return None


def show_difficulty_info_dialog(parent):
    """Show the difficulty information dialog."""
    with DifficultyInfoDialog(parent) as dialog:
        dialog.ShowModal()


class MoveListDialog(wx.Dialog):
    """Dialog showing the complete list of game moves for navigation."""

    def __init__(
        self,
        parent,
        move_list: List[chess.Move],
        current_position: int = -1,
        allow_navigation: bool = True,
        is_ongoing_game: bool = False,
    ):
        super().__init__(
            parent,
            title="Move List",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
            size=(400, 500),
        )

        self.move_list = move_list
        self.current_position = (
            current_position if current_position >= 0 else len(move_list) - 1
        )
        self.selected_position = self.current_position
        self.allow_navigation = allow_navigation
        self.is_ongoing_game = is_ongoing_game

        self._create_controls()
        self._layout_controls()
        self._bind_events()
        self._populate_moves()

        # Set initial selection and focus
        if self.move_list:
            self.list_ctrl.SetFocus()
            self._update_selection()

    def _create_controls(self):
        """Create dialog controls."""
        # Header label
        if self.allow_navigation:
            header_text = "Game Moves:"
        else:
            if self.is_ongoing_game:
                header_text = "Game Moves (Read-only - active game in progress):"
            else:
                header_text = "Game Moves (Read-only):"
        self.header_label = wx.StaticText(self, label=header_text)

        # Move list control
        self.list_ctrl = wx.ListCtrl(
            self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_HRULES
        )

        # Add columns
        self.list_ctrl.AppendColumn("Move #", width=60)
        self.list_ctrl.AppendColumn("Color", width=60)
        self.list_ctrl.AppendColumn("Move", width=80)
        self.list_ctrl.AppendColumn("Position", width=180)

        # Status label
        self.status_label = wx.StaticText(self, label="")

        # Navigation buttons
        self.goto_start_btn = wx.Button(self, label="Start")
        self.goto_prev_btn = wx.Button(self, label="Previous")
        self.goto_next_btn = wx.Button(self, label="Next")
        self.goto_end_btn = wx.Button(self, label="End")

        # Action buttons
        self.goto_position_btn = wx.Button(self, label="Go to Position")
        self.close_btn = wx.Button(self, wx.ID_CLOSE, "Close")

        # Disable navigation controls if not allowed
        if not self.allow_navigation:
            self.goto_start_btn.Enable(False)
            self.goto_prev_btn.Enable(False)
            self.goto_next_btn.Enable(False)
            self.goto_end_btn.Enable(False)
            self.goto_position_btn.Enable(False)

        # Make close button default
        self.close_btn.SetDefault()

    def _layout_controls(self):
        """Layout dialog controls."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Header
        main_sizer.Add(self.header_label, 0, wx.ALL, 5)

        # Move list
        main_sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        # Status
        main_sizer.Add(self.status_label, 0, wx.ALL, 5)

        # Navigation buttons
        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)
        nav_sizer.Add(self.goto_start_btn, 0, wx.ALL, 5)
        nav_sizer.Add(self.goto_prev_btn, 0, wx.ALL, 5)
        nav_sizer.Add(self.goto_next_btn, 0, wx.ALL, 5)
        nav_sizer.Add(self.goto_end_btn, 0, wx.ALL, 5)
        main_sizer.Add(nav_sizer, 0, wx.CENTER)

        # Action buttons
        action_sizer = wx.BoxSizer(wx.HORIZONTAL)
        action_sizer.Add(self.goto_position_btn, 0, wx.ALL, 5)
        action_sizer.AddStretchSpacer()
        action_sizer.Add(self.close_btn, 0, wx.ALL, 5)
        main_sizer.Add(action_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)

    def _bind_events(self):
        """Bind dialog events."""
        # List selection
        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_move_selected, self.list_ctrl)

        # Navigation buttons
        self.Bind(wx.EVT_BUTTON, self._on_goto_start, self.goto_start_btn)
        self.Bind(wx.EVT_BUTTON, self._on_goto_prev, self.goto_prev_btn)
        self.Bind(wx.EVT_BUTTON, self._on_goto_next, self.goto_next_btn)
        self.Bind(wx.EVT_BUTTON, self._on_goto_end, self.goto_end_btn)

        # Action buttons
        self.Bind(wx.EVT_BUTTON, self._on_goto_position, self.goto_position_btn)

        # Keyboard navigation
        self.list_ctrl.Bind(wx.EVT_CHAR_HOOK, self._on_list_key)

    def _populate_moves(self):
        """Populate the move list control."""
        if not self.move_list:
            self.status_label.SetLabel("No moves in current game")
            return

        # Clear existing items
        self.list_ctrl.DeleteAllItems()

        # Add each half-move as a separate row
        for i, move in enumerate(self.move_list):
            move_num = (i // 2) + 1
            is_white = i % 2 == 0
            color = "White" if is_white else "Black"
            move_str = str(move)

            # Create position description
            if is_white:
                position = f"After {move_num}.{move_str}"
            else:
                position = f"After {move_num}...{move_str}"

            # Add to list
            index = self.list_ctrl.InsertItem(i, str(move_num))
            self.list_ctrl.SetItem(index, 1, color)
            self.list_ctrl.SetItem(index, 2, move_str)
            self.list_ctrl.SetItem(index, 3, position)

        self._update_status()

    def _update_selection(self):
        """Update the list selection based on current position."""
        if not self.move_list:
            return

        # Each move has its own row now
        if self.selected_position < 0:
            # Before first move - clear selection
            self.list_ctrl.SetItemState(-1, 0, wx.LIST_STATE_SELECTED)
        else:
            # Select the row corresponding to the move position
            row = self.selected_position
            if row < self.list_ctrl.GetItemCount():
                self.list_ctrl.SetItemState(
                    row, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED
                )
                self.list_ctrl.EnsureVisible(row)

    def _update_status(self):
        """Update the status label."""
        if not self.move_list:
            self.status_label.SetLabel("No moves in current game")
            return

        total_moves = len(self.move_list)
        if self.selected_position < 0:
            self.status_label.SetLabel(f"Starting position (0 of {total_moves} moves)")
        else:
            self.status_label.SetLabel(
                f"Position after move {self.selected_position + 1} of {total_moves}"
            )

        # Update button states (only if navigation is allowed)
        if self.allow_navigation:
            self.goto_start_btn.Enable(self.selected_position >= 0)
            self.goto_prev_btn.Enable(self.selected_position >= 0)
            self.goto_next_btn.Enable(self.selected_position < len(self.move_list) - 1)
            self.goto_end_btn.Enable(self.selected_position < len(self.move_list) - 1)
        else:
            # Keep all navigation buttons disabled
            self.goto_start_btn.Enable(False)
            self.goto_prev_btn.Enable(False)
            self.goto_next_btn.Enable(False)
            self.goto_end_btn.Enable(False)

    def _on_move_selected(self, event):
        """Handle move selection in the list."""
        selection = event.GetIndex()
        if selection >= 0:
            # Each row now directly corresponds to a move position
            self.selected_position = selection

        self._update_status()

    def _on_goto_start(self, event):
        """Go to start position."""
        self.selected_position = -1
        self._update_selection()
        self._update_status()

    def _on_goto_prev(self, event):
        """Go to previous move."""
        if self.selected_position >= 0:
            self.selected_position -= 1
            self._update_selection()
            self._update_status()

    def _on_goto_next(self, event):
        """Go to next move."""
        if self.selected_position < len(self.move_list) - 1:
            self.selected_position += 1
            self._update_selection()
            self._update_status()

    def _on_goto_end(self, event):
        """Go to end position."""
        if self.move_list:
            self.selected_position = len(self.move_list) - 1
            self._update_selection()
            self._update_status()

    def _on_goto_position(self, event):
        """Apply the selected position to the game."""
        if not self.allow_navigation:
            return  # Do nothing if navigation is disabled
        # This will be handled by the parent dialog
        self.EndModal(wx.ID_OK)

    def _on_list_key(self, event):
        """Handle keyboard navigation in the list."""
        key = event.GetKeyCode()

        if key == wx.WXK_RETURN or key == wx.WXK_SPACE:
            # Apply position only if navigation is allowed
            if self.allow_navigation:
                self._on_goto_position(event)
        elif key == wx.WXK_HOME:
            if self.allow_navigation:
                self._on_goto_start(event)
        elif key == wx.WXK_END:
            if self.allow_navigation:
                self._on_goto_end(event)
        elif key == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()

    def get_selected_position(self) -> int:
        """Get the selected move position."""
        return self.selected_position


def show_move_list_dialog(
    parent,
    move_list: List[chess.Move],
    current_position: int = -1,
    allow_navigation: bool = True,
    is_ongoing_game: bool = False,
) -> int | None:
    """
    Show the move list dialog and return the selected position.

    Args:
        parent: Parent window
        move_list: List of chess moves
        current_position: Current position in the move list
        allow_navigation: Whether to allow navigation to different positions
        is_ongoing_game: Whether this is an active game (for display purposes)

    Returns:
        Selected position if OK was clicked, None if cancelled.
    """
    with MoveListDialog(
        parent, move_list, current_position, allow_navigation, is_ongoing_game
    ) as dialog:
        if dialog.ShowModal() == wx.ID_OK:
            return dialog.get_selected_position()
    return None

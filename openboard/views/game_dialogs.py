"""Dialogs for game setup and configuration."""

import wx
import chess
from typing import Optional, Tuple

from ..models.game_mode import DifficultyLevel, DIFFICULTY_CONFIGS


class GameSetupDialog(wx.Dialog):
    """Dialog for setting up a new human vs computer game."""
    
    def __init__(self, parent):
        super().__init__(parent, title="New Game vs Computer", 
                        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        
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
        self.color_white_radio = wx.RadioButton(self, label="Play as White", style=wx.RB_GROUP)
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
        super().__init__(parent, title="Difficulty Levels", 
                        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        
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
        
        self.info_text = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP)
        self.info_text.SetValue("\n".join(info_text))
        
        # Close button
        self.close_button = wx.Button(self, wx.ID_OK, "Close")
        self.close_button.SetDefault()

    def _layout_controls(self):
        """Layout dialog controls."""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        main_sizer.Add(wx.StaticText(self, label="Difficulty Level Information:"), 
                      0, wx.ALL, 10)
        main_sizer.Add(self.info_text, 1, wx.ALL | wx.EXPAND, 10)
        main_sizer.Add(self.close_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        self.SetSizer(main_sizer)


def show_game_setup_dialog(parent) -> Optional[Tuple[chess.Color, DifficultyLevel]]:
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
        super().__init__(parent, title="New Computer vs Computer Game", 
                        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        
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


def show_computer_vs_computer_dialog(parent) -> Optional[Tuple[DifficultyLevel, DifficultyLevel]]:
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
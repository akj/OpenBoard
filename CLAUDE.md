# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenBoard is an accessible, cross-platform chess GUI written in Python. It uses wxPython for the GUI and provides keyboard navigation, screen reader support, and UCI engine integration (specifically Stockfish).

## Development Commands

### Environment Setup
```bash
# Install dependencies
uv sync

# Install development dependencies
uv sync --group dev
```

### Testing
```bash
# Run all tests
uv run python -m pytest

# Run specific test file
uv run python -m pytest tests/test_game.py

# Run with verbose output
uv run python -m pytest -v

# Run specific test
uv run python -m pytest tests/test_game_mode.py::test_computer_vs_computer_config -v
```

### Code Quality
```bash
# Run linting
uv run ruff check .

# Fix auto-fixable linting issues
uv run ruff check --fix .

# Run type checking
uv run python -m pyright
```

### Running the Application
```bash
# From project root
uv run python -m openboard.views.views

# Or using the entry point
uv run openboard
```

## Architecture

The project follows an MVC (Model-View-Controller) pattern with signal-based communication:

### Models (`openboard/models/`)
- `board_state.py`: Wraps python-chess Board with signal-based updates for move/status changes
- `game.py`: High-level game orchestrator that manages BoardState and optional EngineAdapter
- `game_mode.py`: Defines game modes (Human vs Human, Human vs Computer, Computer vs Computer) and difficulty configurations

### Views (`openboard/views/`)
- `views.py`: wxPython-based GUI with BoardPanel for chess board display and ChessFrame for the main window
- `game_dialogs.py`: Dialogs for game setup (human vs computer, computer vs computer)
- `engine_dialogs.py`: Dialogs for engine installation and status

### Controllers (`openboard/controllers/`)
- `chess_controller.py`: Mediates between Game model and View, handles keyboard navigation, selection, and user commands

### Engine (`openboard/engine/`)
- `engine_adapter.py`: Synchronous wrapper around UCI engines (Stockfish) using python-chess
- `engine_detection.py`: Auto-detection of installed chess engines
- `stockfish_manager.py`: Installation and management of Stockfish engines

### Key Dependencies
- `chess`: Python chess library for move validation and board representation
- `wxpython`: GUI framework
- `blinker`: Signal system for event handling between MVC components
- `accessible-output3`: Screen reader support
- `ruff`: Linting and formatting tool
- `pyright`: Static type checking tool

## Common Development Workflows

### Adding a New Game Mode
1. Add enum value to `GameMode` in `game_mode.py`
2. Update `GameConfig` validation in `__post_init__`
3. Modify `Game.is_computer_turn()` logic
4. Update `ChessController.select()` to handle mode-specific behavior
5. Add UI dialog in `game_dialogs.py` if needed
6. Add menu item and handler in `views.py`
7. Add comprehensive tests in `tests/test_game_mode.py`

### Adding Engine Configuration Options
1. Update `EngineAdapter.__init__` to accept new options
2. Modify `engine_detection.py` if auto-detection changes needed
3. Update difficulty configs in `game_mode.py` if relevant
4. Add UI controls in engine dialogs if user-configurable

### Adding New Signals
1. Define signal in appropriate class: `new_signal = Signal()`
2. Connect signal in subscriber's `__init__`: `sender.new_signal.connect(self._handler)`
3. Emit signal: `self.new_signal.send(self, arg1=value1, arg2=value2)`
4. Add signal forwarding in controllers if needed
5. Test signal emission and subscription

## Signal-Based Architecture

The application uses blinker signals extensively for communication between components:

### Signal Naming Convention
- Models emit: `move_made`, `status_changed`, `hint_ready`
- Controllers emit: `board_updated`, `square_focused`, `announce`
- Use past tense for completed actions, present for states

### Signal Flow
- **BoardState signals**: `move_made`, `move_undone`, `status_changed`
- **Game signals**: Forwards BoardState signals plus `hint_ready` for engine responses, `computer_move_ready` for computer moves
- **ChessController signals**: `board_updated`, `square_focused`, `selection_changed`, `announce`, `status_changed`, `hint_ready`, `computer_thinking`

## Game Modes and Difficulty System

The application supports three game modes:
- **Human vs Human**: Manual play for both sides
- **Human vs Computer**: Human plays against engine with selectable difficulty
- **Computer vs Computer**: Two engines play against each other with independent difficulty settings

Difficulty levels control both thinking time and search depth:
- **Beginner**: 150ms, depth=2
- **Intermediate**: 500ms, depth=4  
- **Advanced**: 1500ms, depth=6
- **Master**: 5000ms, depth=10

## Engine Integration

OpenBoard automatically detects and uses Stockfish engines installed on your system. The EngineAdapter class provides a modern asyncio-based interface to UCI engines while maintaining synchronous API compatibility for the GUI. It uses async engine communication internally for better performance and resource management.

### Engine Installation

**Linux:**
```bash
# Ubuntu/Debian
sudo apt install stockfish

# Fedora
sudo dnf install stockfish

# Arch Linux
sudo pacman -S stockfish
```

**macOS:**
```bash
brew install stockfish
```

**Windows:**
Download from https://stockfishchess.org/download/ and ensure it's in your PATH.

If no engine is found, the application will run in engine-free mode (manual play only).

## Debugging

### Engine Issues
- Check engine detection: `EngineDetector().find_engine("stockfish")`
- View engine logs in console when `log_level="DEBUG"`
- Test engine manually: `EngineAdapter.create_with_auto_detection()`

### Signal Flow Debugging
- All signals are logged at DEBUG level
- Use `logger.debug()` in signal handlers to trace execution
- Check signal subscription in `__init__` methods

### UI Issues
- wxPython errors often silent - check console output
- Focus issues: verify `SetFocus()` calls in dialogs
- Accessibility: test with `self.speech.speak()` calls

## Configuration

### Logging Configuration
- Modify `logging_config.py` to change log levels
- Console output controlled by `console_output` parameter
- Engine operations logged at INFO level, signals at DEBUG

### Accessibility Customization
- Announcement verbosity: `controller.announce_mode = "brief|verbose"`
- Screen reader integration via `accessible_output3.outputs.auto.Auto()`
- Keyboard shortcuts defined in `ChessFrame.on_key()`

## Code Organization Patterns

### Import Organization
```python
# Standard library
import threading
from typing import Optional

# Third-party
import chess
import wx
from blinker import Signal

# Local imports
from ..models.game import Game
from .dialogs import SomeDialog
```

### Error Handling Patterns
- Engine errors: Wrap in `RuntimeError` with descriptive messages
- Game logic errors: Use `ValueError` for invalid moves/configs
- UI errors: Show `wx.MessageBox` with user-friendly text

### Async/Threading Rules
- Only UI operations on main thread
- Engine communication uses asyncio internally with background event loop
- Async methods available: `game.request_hint_async()`, `game.request_computer_move_async()`
- Synchronous wrappers maintain API compatibility
- Use signals to communicate async results back to main thread

### Test Organization
- One test file per module: `test_game.py` for `game.py`
- Mock engines using `unittest.mock.Mock(spec=EngineAdapter)`
- Test both success and error paths for engine operations
- Use descriptive test names: `test_computer_vs_computer_move_white`

## Performance Considerations

### Engine Performance
- Depth limits more predictable than time limits for difficulty
- Master level (depth=15) can take 10+ seconds on complex positions
- Async engine communication with proper resource management
- Background asyncio event loop prevents UI freezing
- Callback-based async API enables concurrent analysis

### UI Responsiveness
- Board redraws on every move - keep `on_paint` efficient
- Minimize signal emissions in tight loops
- Use `wx.CallAfter()` for cross-thread UI updates if needed

## Accessibility Features

- Keyboard-only navigation (arrow keys, space for selection)
- Screen reader announcements via accessible-output3
- Configurable verbose/brief announcement modes
- Focus highlighting and square-by-square board navigation

## Testing Strategy

Uses pytest with mock engine adapters for testing game logic without requiring actual engine processes. Tests cover move validation, signal emission, game state management, and all game modes including computer vs computer functionality.

## Important Development Notes

- The MVC pattern is strictly enforced - models emit signals, controllers listen and coordinate, views display and handle user input
- Engine communication uses modern asyncio patterns internally with synchronous API wrappers
- All computer move calculations happen asynchronously to avoid blocking the UI
- Game state is managed entirely through the signal system - avoid direct coupling between components
- When adding new game modes or features, ensure proper signal emission and subscription patterns
- Prefer async methods (`request_hint_async()`, `request_computer_move_async()`) for better performance
- The engine adapter maintains backwards compatibility while providing modern async capabilities
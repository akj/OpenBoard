# OpenBoard

OpenBoard is an accessible, cross-platform chess GUI written in Python. It uses wxPython for the GUI and provides keyboard navigation, screen reader support, and UCI engine integration (specifically Stockfish).

## Architecture

The project follows an MVC (Model-View-Controller) pattern with signal-based communication using blinker for loose coupling between components.

### Models (`openboard/models/`)

**board_state.py**: Wraps python-chess Board with signal-based updates
- Emits signals: `move_made`, `move_undone`, `status_changed`
- Handles move validation, PGN/FEN I/O, and game status determination
- Provides `legal_moves()`, `current_turn()`, `game_status()` interfaces

**game.py**: High-level game orchestrator
- Wraps BoardState and optional EngineAdapter
- Manages game modes (Human vs Human, Human vs Computer, Computer vs Computer)
- Signals: `move_made`, `status_changed`, `hint_ready`, `computer_move_ready`
- Implements automatic pawn promotion (defaults to Queen)
- Provides both sync and async methods for hint and computer move requests
- Integrates opening book with fallback to engine

**game_mode.py**: Game mode and difficulty configuration system
- Defines `GameMode` enum: HUMAN_VS_HUMAN, HUMAN_VS_COMPUTER, COMPUTER_VS_COMPUTER
- Defines `DifficultyLevel` enum: BEGINNER, INTERMEDIATE, ADVANCED, MASTER
- Provides difficulty configurations with time_ms and depth parameters
- Validates configurations in `__post_init__`

**opening_book.py**: Polyglot opening book support
- Synchronous interface for opening book operations
- Uses chess.polyglot.MemoryMappedReader for efficient access
- Returns highest-weighted move for a position

### Views (`openboard/views/`)

**views.py**: wxPython-based GUI
- **BoardPanel**: Renders 8x8 chessboard with unicode piece glyphs, highlights focus (yellow), selection (blue), and hint moves (red)
- **ChessFrame**: Main window with menu bar, status bar, keyboard event handling, and text-to-speech integration
- Subscribes to controller signals for updates

**game_dialogs.py**: Game setup dialogs
- GameSetupDialog: color selection and difficulty for Human vs Computer
- ComputerVsComputerDialog: independent difficulty settings for both sides

**engine_dialogs.py**: Engine management dialogs
- Engine installation and status dialogs

### Controllers (`openboard/controllers/`)

**chess_controller.py**: MVC mediator
- Emits signals to views: `board_updated`, `square_focused`, `selection_changed`, `announce`, `status_changed`, `hint_ready`, `computer_thinking`
- Core methods: `navigate()`, `select()`, `deselect()`, `undo()`, `request_hint()`, `request_book_hint()`
- Implements PGN replay system
- Provides comprehensive move announcement with brief/verbose modes
- Coordinates computer moves with proper capture detection
- Analyzes legal moves and attacking pieces for accessibility

### Engine (`openboard/engine/`)

**engine_adapter.py**: Modern async wrapper for UCI engines
- Runs asyncio event loop in background thread for non-blocking communication
- Synchronous API: `get_best_move(position, time_ms, depth)` blocks until result
- Asynchronous API: `get_best_move_async()` with callback support, returns Future
- Uses `chess.engine.popen_uci()` for UCI protocol communication
- Thread-safe with RLock, Future tracking, graceful shutdown
- WxCallbackExecutor for thread-safe wx.CallAfter() on result

**engine_detection.py**: Cross-platform engine discovery
- Checks local OpenBoard installation, system PATH, common paths
- Platform-specific search paths (Linux: /usr/bin, /usr/local/bin; macOS: Homebrew; Windows: Program Files)
- Validates executables via `os.access(path, os.X_OK)`
- Supports Stockfish (primary), Leela, Komodo, Dragon

**stockfish_manager.py**: Stockfish installation and updates
- Manages local Stockfish binary in settings.engine.stockfish_dir
- Platform-specific binary selection and download

**downloader.py**: Utility for downloading engine binaries

### Configuration (`openboard/config/`)

**settings.py**: Application settings
- **UISettings**: square_size, piece_unicode dict, announcement_mode
- **EngineSettings**: search paths, default timeout, local installation dir
- Platform-specific search paths via pattern matching
- Dataclass-based with validation

**keyboard_config.py**: Keyboard binding configuration
- **KeyBinding** dataclass: key, action, modifiers, enabled flag
- **KeyModifier**: none, ctrl, shift, alt, and combinations
- **KeyAction** enum: 15+ actions (navigate, select, hint, replay, announce, etc.)
- **GameKeyboardConfig**: Default bindings with pydantic dataclass validation
- Matcher system: `find_binding()`, `get_bindings_by_action()`

### Logging (`openboard/logging/`)

**logging_config.py**: Centralized logging configuration
- Rotating file handler: 10MB max, 5 backups
- Console + file output configurable
- Development vs production modes with DEBUG/INFO level differences
- Default log file: `~/openboard.log`

## Design Decisions

### Signal-Based Architecture

The application uses blinker signals extensively for communication between components to maintain loose coupling.

**Signal Naming Convention:**
- Models emit past-tense signals: `move_made`, `status_changed`, `hint_ready`
- Controllers emit present-tense signals: `board_updated`, `square_focused`, `announce`

**Signal Flow:**
- **BoardState**: `move_made`, `move_undone`, `status_changed`
- **Game**: Forwards BoardState signals plus `hint_ready`, `computer_move_ready`
- **ChessController**: `board_updated`, `square_focused`, `selection_changed`, `announce`, `status_changed`, `hint_ready`, `computer_thinking`

All signal handlers are prefixed with `_on_*` for clarity and logged at DEBUG level.

### Game Modes and Difficulty System

**Three Supported Modes:**
1. **Human vs Human**: Manual moves only, no engine needed
2. **Human vs Computer**: Human plays against engine with selectable difficulty
3. **Computer vs Computer**: Two engines play each other with independent difficulty per side

**Difficulty Levels (time_ms, depth):**
- Beginner: 150ms, depth=2 - Good for learning
- Intermediate: 500ms, depth=4 - Moderate challenge (default)
- Advanced: 1500ms, depth=6 - Strong opponent
- Master: 5000ms, depth=10 - Very strong play

Depth limits are more predictable than time limits for consistent difficulty. Master level can take 10+ seconds on complex positions.

### Async/Threading Architecture

**Design rationale**: Engine operations are computationally intensive and must not block the GUI.

- Engine runs in background asyncio event loop in separate thread
- Main GUI thread remains responsive
- `wx.CallAfter()` ensures callbacks execute on main thread
- Computer moves execute async, signal back when ready
- Game.move_made applies move AND emits signal (move already applied in BoardState)

**Threading Rules:**
- Only UI operations on main thread
- Engine communication uses asyncio internally with background event loop
- Async methods available: `game.request_hint_async()`, `game.request_computer_move_async()`
- Synchronous wrappers maintain API compatibility
- Use signals to communicate async results back to main thread

### Move Announcement System

**Dual announcement modes for accessibility:**
- **Brief mode**: Concise announcements (e.g., "e2 e4, check")
- **Verbose mode**: Detailed descriptions with piece names and capture information

**Pattern matching for special moves:**
- Castling (kingside/queenside)
- En passant captures
- Pawn promotion
- Standard captures (detected via `old_board.is_capture()` to show captured piece name)
- Game state suffixes: checkmate, check, stalemate, draws

### Code Organization Patterns

**Import Organization:**
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

**Error Handling:**
- Engine errors: Wrap in `RuntimeError` with descriptive messages
- Game logic errors: Use `ValueError` for invalid moves/configs
- UI errors: Show `wx.MessageBox` with user-friendly text
- Comprehensive exception hierarchy in `exceptions.py`

**Test Organization:**
- One test file per module: `test_game.py` for `game.py`
- Mock engines using `unittest.mock.Mock(spec=EngineAdapter)`
- Test both success and error paths for engine operations
- Use descriptive test names: `test_computer_vs_computer_move_white`

## Invariants

**MVC Pattern Enforcement:**
- Models emit signals only (no direct view/controller coupling)
- Controllers listen to models and coordinate actions
- Views display state and handle user input
- All inter-component communication goes through signals

**Game State Management:**
- Game state is managed entirely through the signal system
- Avoid direct coupling between components
- When adding new game modes or features, ensure proper signal emission and subscription patterns

**Async Method Preference:**
- Prefer async methods (`request_hint_async()`, `request_computer_move_async()`) for better performance
- The engine adapter maintains backwards compatibility while providing modern async capabilities
- All computer move calculations happen asynchronously to avoid blocking the UI

**Pawn Promotion:**
- Automatic pawn promotion defaults to Queen
- This design decision simplifies keyboard navigation (no modal dialog interruption)
- Future enhancement could add preference setting for interactive promotion

## Performance Considerations

### Engine Performance
- Depth limits more predictable than time limits for difficulty
- Master level (depth=10) can take 10+ seconds on complex positions
- Async engine communication with proper resource management
- Background asyncio event loop prevents UI freezing
- Callback-based async API enables concurrent analysis

### UI Responsiveness
- Board redraws on every move - keep `on_paint` efficient
- Minimize signal emissions in tight loops
- Use `wx.CallAfter()` for cross-thread UI updates

## Accessibility Features

- **Keyboard-only navigation**: Arrow keys for board navigation, space for selection
- **Screen reader announcements**: Via accessible-output3 library
- **Configurable announcement modes**: Brief/verbose for different user preferences
- **Focus highlighting**: Visual feedback for current square selection
- **Square-by-square navigation**: Complete board traversal without mouse

Configuration:
- Announcement verbosity: `controller.announce_mode = "brief|verbose"`
- Screen reader integration via `accessible_output3.outputs.auto.Auto()`
- Keyboard shortcuts defined in `keyboard_config.py`

## Debugging

### Engine Issues
- Check engine detection: `EngineDetector().find_engine("stockfish")`
- View engine logs in console when `log_level="DEBUG"`
- Test engine manually: `EngineAdapter.create_with_auto_detection()`
- Adaptive timeout handling: buffer based on thinking time
- Thread-safe with graceful shutdown

### Signal Flow Debugging
- All signals are logged at DEBUG level
- Use `logger.debug()` in signal handlers to trace execution
- Check signal subscription in `__init__` methods
- Signal handlers prefixed with `_on_*`

### UI Issues
- wxPython errors often silent - check console output
- Focus issues: verify `SetFocus()` calls in dialogs
- Accessibility: test with `self.speech.speak()` calls
- Board redraws: keep `on_paint` efficient

### Logging Configuration
- Modify `logging_config.py` to change log levels
- Console output controlled by `console_output` parameter
- Engine operations logged at INFO level, signals at DEBUG

## Common Development Workflows

### Adding a New Game Mode
1. Add enum value to `GameMode` in `game_mode.py`
2. Update `GameConfig` validation in `__post_init__`
3. Modify `Game.is_computer_turn()` logic using pattern matching
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
6. Follow naming convention: past tense for models, present for controllers

## Key Dependencies

- **chess** (>= 1.11.2): Python chess library for move validation and board representation
- **wxpython** (>= 4.2.4): GUI framework
- **blinker** (>= 1.9.0): Signal system for event handling between MVC components
- **accessible-output3**: Screen reader support
- **pydantic** (>= 2.12.4): Configuration validation
- **ruff** (>= 0.14.5): Linting and formatting tool
- **ty** (>= 0.0.11): Modern type checking
- **pytest** (>= 9.0.1): Testing framework

## Testing Strategy

Uses pytest with mock engine adapters for testing game logic without requiring actual engine processes. Tests cover:
- Move validation and application
- Signal emission and subscription
- Game state management
- All game modes including computer vs computer functionality
- Engine adapter async operations
- Opening book integration

Mock engines using `unittest.mock.Mock(spec=EngineAdapter)` to avoid subprocess overhead.

## Important Development Notes

- The MVC pattern is strictly enforced - models emit signals, controllers listen and coordinate, views display and handle user input
- Engine communication uses modern asyncio patterns internally with synchronous API wrappers
- All computer move calculations happen asynchronously to avoid blocking the UI
- Game state is managed entirely through the signal system - avoid direct coupling between components
- When adding new game modes or features, ensure proper signal emission and subscription patterns
- Prefer async methods (`request_hint_async()`, `request_computer_move_async()`) for better performance
- The engine adapter maintains backwards compatibility while providing modern async capabilities
- Pattern matching (Python 3.10+) used extensively for game modes, difficulties, move types

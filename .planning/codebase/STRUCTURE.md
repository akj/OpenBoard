# Codebase Structure

**Analysis Date:** 2026-04-27

## Directory Layout

```
openboard/                        # repo root
├── openboard/                    # Main Python package
│   ├── __init__.py               # Version declaration (__version__ = "0.1.0")
│   ├── __main__.py               # Entry point for `python -m openboard`
│   ├── exceptions.py             # Full exception hierarchy (OpenBoardError → subclasses)
│   ├── logging_config.py         # Logging setup: rotating file + console handlers
│   ├── models/                   # Game state and logic (Model layer)
│   │   ├── board_state.py        # BoardState: chess.Board wrapper with signals
│   │   ├── game.py               # Game: orchestrator for board + engine + opening book
│   │   ├── game_mode.py          # GameMode enum, DifficultyLevel enum, GameConfig dataclass
│   │   └── opening_book.py       # OpeningBook: polyglot .bin reader (synchronous)
│   ├── controllers/              # MVC controller (Controller layer)
│   │   └── chess_controller.py   # ChessController: navigation, selection, announcements, PGN replay
│   ├── views/                    # wxPython GUI (View layer)
│   │   ├── views.py              # ChessFrame (main window), BoardPanel (canvas), main()
│   │   ├── game_dialogs.py       # Game setup dialogs (HvC, CvC, difficulty, move list)
│   │   └── engine_dialogs.py     # Engine install/status dialogs, EngineInstallationRunner
│   ├── engine/                   # UCI engine integration (Engine layer)
│   │   ├── engine_adapter.py     # EngineAdapter: asyncio UCI wrapper + WxCallbackExecutor
│   │   ├── engine_detection.py   # EngineDetector: cross-platform engine path discovery
│   │   ├── stockfish_manager.py  # StockfishManager: install/update lifecycle + signals
│   │   └── downloader.py         # StockfishDownloader: binary download utility
│   └── config/                   # Application configuration (Config layer)
│       ├── __init__.py
│       ├── settings.py           # Settings, UISettings, EngineSettings dataclasses (singleton)
│       └── keyboard_config.py    # KeyBinding, KeyAction, GameKeyboardConfig, KeyboardCommandHandler
├── config/                       # Runtime config files (not the Python package)
│   └── keyboard_config.json      # Default key bindings (loaded by ChessFrame at startup)
├── assets/                       # Static assets
│   └── icons/                    # Application icons (SVG, PNG, ICO, ICNS)
│       ├── openboard.svg
│       ├── openboard.png
│       ├── openboard.ico
│       ├── openboard.icns
│       └── generate_icons.py     # Script to regenerate raster icons from SVG
├── tests/                        # Test suite (flat, co-located with test helpers)
│   ├── conftest.py               # Shared pytest fixtures
│   ├── test_board_state_terminal.py
│   ├── test_build_validation.py
│   ├── test_chess_controller.py
│   ├── test_chess_controller_opening_book.py
│   ├── test_engine_adapter.py
│   ├── test_engine_adapter_integration.py
│   ├── test_engine_adapter_simple.py
│   ├── test_engine_detection.py
│   ├── test_exceptions.py
│   ├── test_game.py
│   ├── test_game_async.py
│   ├── test_game_mode.py
│   ├── test_game_opening_book_integration.py
│   ├── test_keyboard_config.py
│   ├── test_opening_book.py
│   ├── test_settings.py
│   └── test_stockfish_manager.py
├── .build/                       # Build tooling (not application code)
│   ├── pyinstaller_spec.py       # Detailed PyInstaller configuration
│   ├── installers/               # Platform-specific installer scripts (Linux .deb/.rpm, macOS, Windows)
│   ├── scripts/                  # Build helper scripts
│   ├── utils/                    # Build utilities
│   └── validation/               # Post-build validation scripts
├── .github/workflows/            # CI/CD pipeline definitions
│   ├── ci.yml                    # Main CI (lint + test)
│   ├── build-and-validate.yml    # Build binary and validate executable
│   ├── release.yml               # Release workflow
│   └── setup-*.yml               # Reusable workflow fragments
├── .claude/                      # Claude/GSD tooling (not application code)
├── .planning/                    # GSD planning documents
├── pyproject.toml                # Project metadata, dependencies, scripts, dev tools
├── uv.lock                       # Locked dependency tree (managed by uv)
├── openboard.spec                # PyInstaller spec entry (delegates to .build/pyinstaller_spec.py)
└── README.md                     # User-facing project overview
```

## Directory Purposes

**`openboard/` (package root):**
- Purpose: Application entry point and shared cross-cutting utilities
- Contains: `__main__.py`, `__init__.py`, `exceptions.py`, `logging_config.py`
- Key files: `openboard/exceptions.py` (all custom exception types), `openboard/logging_config.py` (logging setup)

**`openboard/models/`:**
- Purpose: All game state, rules, and logic — the M in MVC
- Contains: `BoardState`, `Game`, `GameMode`/`GameConfig`/`DifficultyConfig`, `OpeningBook`
- Key files: `openboard/models/game.py` (primary game orchestrator), `openboard/models/board_state.py` (move authority)

**`openboard/controllers/`:**
- Purpose: Single controller mediating views and models
- Contains: `ChessController` only
- Key files: `openboard/controllers/chess_controller.py`

**`openboard/views/`:**
- Purpose: All wxPython UI — windows, panels, dialogs
- Contains: `ChessFrame`, `BoardPanel`, game setup dialogs, engine dialogs
- Key files: `openboard/views/views.py` (main window + `main()` entry point), `openboard/views/game_dialogs.py`

**`openboard/engine/`:**
- Purpose: All chess engine communication and management
- Contains: `EngineAdapter`, `EngineDetector`, `StockfishManager`, `StockfishDownloader`
- Key files: `openboard/engine/engine_adapter.py` (UCI communication core)

**`openboard/config/`:**
- Purpose: Settings and keyboard configuration Python classes
- Contains: `Settings` dataclass singleton, `GameKeyboardConfig`, `KeyBinding`, `KeyAction`
- Key files: `openboard/config/settings.py`, `openboard/config/keyboard_config.py`

**`config/` (repo root):**
- Purpose: Runtime JSON configuration files (separate from Python package)
- Contains: `keyboard_config.json` (default key bindings, user-editable)
- Key files: `config/keyboard_config.json`

**`tests/`:**
- Purpose: All automated tests; flat layout, one file per module under test
- Contains: `conftest.py` plus `test_*.py` files
- Key files: `tests/conftest.py`, `tests/test_chess_controller.py` (largest, most comprehensive)

**`assets/icons/`:**
- Purpose: Application icon files in all required formats
- Generated: PNG/ICO/ICNS are generated from the SVG via `generate_icons.py`
- Committed: Yes

**`.build/`:**
- Purpose: Build system — PyInstaller spec, platform installers, validation scripts
- Generated: No (source-controlled build scripts)
- Committed: Yes

## Key File Locations

**Entry Points:**
- `openboard/__main__.py`: Invoked by `python -m openboard` — delegates to `main()`
- `openboard/views/views.py:743`: `main()` function — wires up engine, game, controller, wx app
- `pyproject.toml:16`: `openboard = "openboard.views.views:main"` — console script entry point

**Configuration:**
- `pyproject.toml`: Project dependencies, dev tools, Python version constraint (`>=3.12`)
- `config/keyboard_config.json`: Default key bindings (loaded at runtime; user can replace)
- `openboard/config/settings.py`: `get_settings()` singleton accessor
- `openboard/config/keyboard_config.py`: `GameKeyboardConfig` and `KeyboardCommandHandler`

**Core Logic:**
- `openboard/models/board_state.py`: All move validation and chess board state
- `openboard/models/game.py`: Game orchestration (engine, opening book, computer moves)
- `openboard/controllers/chess_controller.py`: Keyboard navigation, selection, announcement
- `openboard/engine/engine_adapter.py`: Async UCI engine communication

**Exception Hierarchy:**
- `openboard/exceptions.py`: All custom exception types

**Logging:**
- `openboard/logging_config.py`: `get_logger()` and `setup_logging()`

**Testing:**
- `tests/conftest.py`: Shared fixtures
- `tests/test_chess_controller.py`: Most extensive controller tests
- `tests/test_engine_adapter_integration.py`: Integration tests requiring a real engine

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `board_state.py`, `engine_adapter.py`, `game_mode.py`)
- Test files: `test_<module_name>.py` (e.g., `test_board_state_terminal.py`, `test_engine_adapter.py`)
- Config files: `snake_case.json` (e.g., `keyboard_config.json`)

**Directories:**
- Python packages: `snake_case/` (e.g., `models/`, `controllers/`, `views/`, `engine/`, `config/`)
- Build/tool directories: lowercase with dots for hidden dirs (`.build/`, `.claude/`, `.planning/`)

**Classes:**
- PascalCase (e.g., `ChessController`, `BoardState`, `EngineAdapter`, `WxCallbackExecutor`)

**Functions/methods:**
- `snake_case` for all functions and methods

**Signals (blinker):**
- `snake_case` instance attributes on the owning class (e.g., `self.move_made = Signal()`, `self.board_updated = Signal()`)

**Enums:**
- Class name: PascalCase (e.g., `GameMode`, `DifficultyLevel`, `KeyAction`, `KeyModifier`)
- Members: SCREAMING_SNAKE_CASE (e.g., `GameMode.HUMAN_VS_COMPUTER`, `KeyAction.NAVIGATE_UP`)

## Where to Add New Code

**New game rule or move logic:**
- Primary code: `openboard/models/board_state.py` or `openboard/models/game.py`
- Tests: `tests/test_game.py` or `tests/test_board_state_terminal.py`

**New game mode:**
- Model: add to `GameMode` enum in `openboard/models/game_mode.py`, add `GameConfig` validation
- Controller: handle new mode in `ChessController.select()` guard and `_on_model_move`
- View: add menu item in `ChessFrame.__init__` in `openboard/views/views.py`

**New keyboard action:**
- Add value to `KeyAction` enum in `openboard/config/keyboard_config.py`
- Add default binding in `config/keyboard_config.json`
- Add handler lambda in `ChessFrame._create_keyboard_handler()` in `openboard/views/views.py:713`
- Add controller method in `openboard/controllers/chess_controller.py`

**New dialog:**
- Implementation: `openboard/views/game_dialogs.py` (game-related) or `openboard/views/engine_dialogs.py` (engine-related)
- Wire menu item in `ChessFrame.__init__` in `openboard/views/views.py`

**New configuration option:**
- Add field to `UISettings` or `EngineSettings` in `openboard/config/settings.py`
- Update `Settings.validate()` if constraints apply

**New exception type:**
- Add to `openboard/exceptions.py` inheriting from the appropriate parent class

**New engine feature:**
- Add method to `EngineAdapter` in `openboard/engine/engine_adapter.py`
- Expose via `Game` in `openboard/models/game.py` (async pattern with callback)
- Hook in `ChessController` in `openboard/controllers/chess_controller.py`

**New test:**
- Location: `tests/test_<module_name>.py` (flat, no subdirectories)
- Fixtures: add to `tests/conftest.py` if shared across multiple test files

## Special Directories

**`.build/`:**
- Purpose: PyInstaller spec, cross-platform installer scripts, build validation
- Generated: No
- Committed: Yes

**`.claude/`:**
- Purpose: Claude/GSD agent tooling, skills, hooks, command definitions
- Generated: No
- Committed: Yes

**`.planning/`:**
- Purpose: GSD planning documents (codebase maps, phase plans)
- Generated: Yes (by GSD agents)
- Committed: Yes (when explicitly committed)

**`.venv/`:**
- Purpose: Virtual environment managed by `uv`
- Generated: Yes
- Committed: No

**`htmlcov/`:**
- Purpose: pytest-cov HTML coverage report output
- Generated: Yes
- Committed: No

---

*Structure analysis: 2026-04-27*

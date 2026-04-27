<!-- refreshed: 2026-04-27 -->
# Architecture

**Analysis Date:** 2026-04-27

## System Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│                         View Layer (wxPython)                    │
│  ChessFrame / BoardPanel    game_dialogs    engine_dialogs       │
│  `openboard/views/views.py` `views/game_dialogs.py`             │
└──────────┬──────────────────────────────────┬───────────────────┘
           │ blinker signals (subscribe)       │ direct calls
           │ wx events (bind)                  │ (menu/key actions)
           ▼                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Controller Layer                             │
│              ChessController                                     │
│         `openboard/controllers/chess_controller.py`             │
│  Signals OUT: board_updated, square_focused, selection_changed, │
│               announce, status_changed, hint_ready,             │
│               computer_thinking                                  │
└──────────┬────────────────────────────────────────────────────┬─┘
           │ direct calls + signal subscription                 │
           ▼                                                    ▼
┌──────────────────────────────────┐   ┌───────────────────────────┐
│        Model Layer               │   │     Engine Layer           │
│  Game  `openboard/models/game.py`│   │  EngineAdapter             │
│  BoardState  `models/board_      │   │  `engine/engine_adapter.py`│
│              state.py`           │   │  (asyncio loop in bg       │
│  OpeningBook `models/opening_    │   │   thread, WxCallbackExec.) │
│              book.py`            │   │                            │
│  GameMode/Config `models/game_   │   │  EngineDetector            │
│              mode.py`            │   │  `engine/engine_detection.py`│
│  Signals: move_made, move_undone │   │  StockfishManager          │
│           status_changed,        │   │  `engine/stockfish_manager.py`│
│           hint_ready,            │   │  Downloader                │
│           computer_move_ready    │   │  `engine/downloader.py`    │
└──────────────────────────────────┘   └───────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Config Layer                                   │
│  Settings `openboard/config/settings.py`                        │
│  KeyboardConfig `openboard/config/keyboard_config.py`           │
│  keyboard_config.json `config/keyboard_config.json`             │
└─────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| `BoardPanel` | wxPython canvas: renders board, pieces, highlights. Subscribes to controller signals. | `openboard/views/views.py` |
| `ChessFrame` | Main window: menus, status bar, keyboard dispatch, instantiates BoardPanel. | `openboard/views/views.py` |
| `ChessController` | MVC mediator: keyboard navigation state, selection, move dispatch, PGN replay, announcements. Emits signals to view. | `openboard/controllers/chess_controller.py` |
| `Game` | High-level orchestrator: wraps `BoardState` + `EngineAdapter`, coordinates game modes, emits `move_made`, `hint_ready`, `computer_move_ready`. | `openboard/models/game.py` |
| `BoardState` | python-chess `Board` wrapper: validates/applies moves, emits `move_made`, `move_undone`, `status_changed`. | `openboard/models/board_state.py` |
| `OpeningBook` | Polyglot `.bin` reader: synchronous highest-weight move lookup. | `openboard/models/opening_book.py` |
| `GameMode` / `GameConfig` | Enums and dataclasses for mode (HvH, HvC, CvC) and difficulty. | `openboard/models/game_mode.py` |
| `EngineAdapter` | UCI engine wrapper: asyncio event loop on a background thread, synchronous and async `get_best_move*` API, wx-safe callbacks via `WxCallbackExecutor`. | `openboard/engine/engine_adapter.py` |
| `EngineDetector` | Cross-platform engine path discovery (local install, PATH, common dirs). | `openboard/engine/engine_detection.py` |
| `StockfishManager` | Install/update lifecycle; emits blinker named signals (`installation_started`, `installation_progress`, etc.). | `openboard/engine/stockfish_manager.py` |
| `Settings` | Singleton dataclasses (`UISettings`, `EngineSettings`) with platform-aware defaults. | `openboard/config/settings.py` |
| `GameKeyboardConfig` | Pydantic dataclass-based key binding registry; `KeyboardCommandHandler` maps `KeyAction` → callables. | `openboard/config/keyboard_config.py` |

## Pattern Overview

**Overall:** MVC (Model-View-Controller) with signal-based decoupling using `blinker`.

**Key Characteristics:**
- View and model never reference each other directly; all communication goes through the controller or signals.
- Signals are `blinker.Signal` instance attributes on model and controller objects (not module-level named signals), except `StockfishManager` which uses module-level named signals.
- The engine runs in a dedicated asyncio loop on a background thread; results are marshalled back to the wx main thread via `wx.CallAfter` (wrapped in `WxCallbackExecutor`).
- Opening book access is fully synchronous (no background thread needed).

## Layers

**View Layer:**
- Purpose: Render the board, handle wx events, forward user intent to controller
- Location: `openboard/views/`
- Contains: `BoardPanel` (canvas rendering), `ChessFrame` (window + menus), modal dialogs
- Depends on: controller (direct calls + signal subscription), `accessible_output3` for speech
- Used by: nothing (top of stack)

**Controller Layer:**
- Purpose: Mediate between view events and model state; own all keyboard navigation and UI announcement logic
- Location: `openboard/controllers/chess_controller.py`
- Contains: navigation/selection state, PGN replay cursor, accessibility announcement formatting
- Depends on: `Game` model (direct calls), `blinker` signals from model
- Used by: view layer

**Model Layer:**
- Purpose: Authoritative game state; all move logic lives here
- Location: `openboard/models/`
- Contains: `BoardState` (board + move validation), `Game` (mode/engine/book coordination), `OpeningBook`, `GameMode`/`GameConfig`
- Depends on: `EngineAdapter`, `python-chess`
- Used by: controller

**Engine Layer:**
- Purpose: UCI engine lifecycle and async communication
- Location: `openboard/engine/`
- Contains: `EngineAdapter` (async wrapper), `EngineDetector` (path discovery), `StockfishManager` (install/update), `StockfishDownloader` (download utility)
- Depends on: `python-chess.engine`, `asyncio`, `threading`
- Used by: `Game` model

**Config Layer:**
- Purpose: Application-wide settings and keyboard binding definitions
- Location: `openboard/config/`, `config/`
- Contains: `Settings` singleton, `GameKeyboardConfig`, `KeyBinding`, `keyboard_config.json`
- Depends on: `pydantic`, `platform`
- Used by: views, engine layer, controller

## Data Flow

### Human Move Path

1. User presses arrow key → `ChessFrame.on_key` dispatches via `KeyboardCommandHandler` (`openboard/views/views.py:348`)
2. `KeyboardCommandHandler` resolves `KeyAction` → calls `controller.navigate()` or `controller.select()` (`openboard/controllers/chess_controller.py:181`)
3. On second space press (`select`), controller calls `game.apply_move(src, dst)` (`chess_controller.py:239`)
4. `Game.apply_move` → `BoardState.make_move` validates against `board.legal_moves`, pushes to `chess.Board` (`models/board_state.py:63`)
5. `BoardState` emits `move_made` and `status_changed` signals
6. `Game._on_board_move` forwards `move_made` upward as `Game.move_made`
7. `ChessController._on_model_move` receives signal → calls `_emit_board_update()` (emits `board_updated`) and `announce.send()` (`chess_controller.py:90`)
8. `BoardPanel.on_board_updated` receives `board_updated` → calls `Refresh()` to repaint (`views.py:79`)
9. `ChessFrame.on_announce` receives `announce` → calls `self.speech.speak(text)` and updates status bar

### Computer Move Path (Async)

1. After human move, `_on_model_move` checks `game.is_computer_turn()` → calls `_request_computer_move_async()` (`chess_controller.py:118`)
2. Controller emits `computer_thinking` signal (thinking=True), calls `game.request_computer_move_async()`
3. `Game` first checks opening book synchronously; if no book move, calls `engine_adapter.get_best_move_async(fen, time_ms, depth, callback)` (`models/game.py:458`)
4. `EngineAdapter` submits coroutine to asyncio background loop via `asyncio.run_coroutine_threadsafe` (`engine/engine_adapter.py`)
5. When result arrives on background thread, `WxCallbackExecutor.execute` uses `wx.CallAfter(callback, result)` to dispatch to main thread
6. Callback in `Game.request_computer_move_async` applies the move to `BoardState`, emits `computer_move_ready` with `old_board` context
7. `ChessController._on_computer_move_ready` formats and announces the move, emits `computer_thinking` (thinking=False)

### PGN Replay Path

1. User selects File → Load PGN → `ChessFrame.on_load_pgn` → `controller.load_pgn(text)` (`chess_controller.py:369`)
2. Controller parses PGN, stores moves in `_replay_moves`, resets board to starting FEN, sets `_in_replay = True`
3. F6 / F5 keys call `replay_next()` / `replay_prev()` to step through `_replay_moves` one at a time

**State Management:**
- `BoardState._board` (`chess.Board`) is the single source of truth for the game position.
- `ChessController` owns UI navigation state (`current_square`, `selected_square`, `_in_replay`, `_replay_moves`, `_replay_index`).
- `Settings` is a module-level singleton accessed via `get_settings()` (`openboard/config/settings.py:116`).

## Key Abstractions

**`blinker.Signal` (instance):**
- Purpose: Decouple senders from receivers without circular imports
- Examples: `BoardState.move_made`, `Game.hint_ready`, `ChessController.board_updated`, `ChessController.announce`
- Pattern: Sender calls `signal.send(self, **kwargs)`; receivers connect with `signal.connect(handler)`

**`GameConfig` dataclass:**
- Purpose: Validated configuration bundle for a game session (mode + colors + difficulty)
- File: `openboard/models/game_mode.py`
- Pattern: Pydantic-style `__post_init__` validation; passed to `Game.new_game()`

**`KeyAction` enum + `KeyboardCommandHandler`:**
- Purpose: Decouple key bindings from controller method names; support JSON-configurable key maps
- File: `openboard/config/keyboard_config.py`
- Pattern: `ChessFrame._create_keyboard_handler()` maps each `KeyAction` to a lambda calling a controller method

**`WxCallbackExecutor`:**
- Purpose: Thread-safe callback delivery from engine background thread to wx main thread
- File: `openboard/engine/engine_adapter.py`
- Pattern: Checks `threading.current_thread() != threading.main_thread()` → uses `wx.CallAfter`

## Entry Points

**GUI application:**
- Location: `openboard/views/views.py:743` (`main()` function)
- Triggers: `python -m openboard` (via `openboard/__main__.py`), or `openboard` console script (defined in `pyproject.toml`)
- Responsibilities: Sets up logging, loads `config.json`, attempts engine startup (falls back to engine-free mode on failure), creates `Game`, `ChessController`, `wx.App`, `ChessFrame`, runs `app.MainLoop()`

**Module entry point:**
- Location: `openboard/__main__.py`
- Triggers: `python -m openboard`

## Architectural Constraints

- **Threading:** Single wxPython main thread for all UI and signal handling. Engine runs asyncio loop on one daemon background thread (`EngineAdapter._engine_thread`). All engine callbacks are marshalled back to main thread via `wx.CallAfter`.
- **Global state:** `_settings: Settings | None` singleton in `openboard/config/settings.py:113`. No other module-level mutable state in core layers.
- **Engine optional:** App starts without a chess engine; `Game.engine_adapter` may be `None`. All engine-dependent paths guard with `if not self.engine_adapter`.
- **Opening book synchronous:** `OpeningBook.get_move` is synchronous/blocking. It must remain fast (memory-mapped file). Do not perform book lookups on large files without considering latency.
- **Circular imports:** Views import controllers, controllers import models, models import engine. No reverse imports allowed.

## Anti-Patterns

### Calling `game.board_state.board` in the view

**What happens:** `ChessFrame` and `BoardPanel` occasionally reach into `self.controller.game.board_state.board` directly (e.g., `views.py:605`, `views.py:394`).
**Why it's wrong:** Bypasses the MVC boundary; view directly reads model state rather than receiving it through controller signals.
**Do this instead:** Add a method or signal to `ChessController` that exposes the needed data, or use `controller.game.board_state.board` only as a last resort when the controller has no suitable accessor.

### Directly pushing moves to `board` in position navigation

**What happens:** `_navigate_to_position` in `ChessFrame` calls `board.push(move)` and manually fires `board_state.move_made` (`views.py:682`).
**Why it's wrong:** Bypasses `BoardState.make_move`, skipping legality validation and proper signal sequencing.
**Do this instead:** Add a `replay_to_position(index)` method on `ChessController` that uses `BoardState.make_move` / `BoardState.undo_move`.

## Error Handling

**Strategy:** Typed exception hierarchy rooted at `OpenBoardError` (`openboard/exceptions.py`). Engine errors are non-fatal at startup (app falls back to engine-free mode).

**Patterns:**
- All custom exceptions inherit from `OpenBoardError` with `message` and optional `details` fields.
- Controller methods catch exceptions and convert them to accessibility announcements via `self.announce.send(...)` rather than surfacing tracebacks.
- Engine startup failure is caught in `main()` and gracefully degrades to `Game()` without an adapter.

## Cross-Cutting Concerns

**Logging:** `get_logger(__name__)` from `openboard/logging_config.py` used in every module. Rotating file handler (`~/openboard.log`, 10MB × 5 backups) + optional console output, configured at startup in `main()`.

**Validation:** `GameConfig.__post_init__` and `DifficultyConfig.__post_init__` validate game configuration at construction time. `Settings.validate()` validates UI/engine settings at singleton creation.

**Accessibility:** `accessible_output3.outputs.auto.Auto` (`ao2.Auto`) used in `ChessFrame` to route speech to screen readers. All user-facing state changes flow through `controller.announce` signal to ensure screen reader coverage.

---

*Architecture analysis: 2026-04-27*

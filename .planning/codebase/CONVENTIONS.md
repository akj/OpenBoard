# Coding Conventions

**Analysis Date:** 2026-04-27

## User-Defined Requirements (CLAUDE.local.md)

These rules override defaults and must be followed:

- **Descriptive variable names:** Always use full, readable names — no abbreviations like `e`, `s`, `m`.
- **Modern union/optional typing:** Use `str | None` and `str | int`, never `Optional[str]` or `Union[str, int]`.

## Naming Patterns

**Files:**
- `snake_case.py` for all Python modules (e.g., `chess_controller.py`, `game_mode.py`, `engine_adapter.py`)
- `test_<module_name>.py` for test files (e.g., `test_chess_controller.py`, `test_engine_adapter.py`)

**Classes:**
- `PascalCase` — `ChessController`, `EngineAdapter`, `BoardState`, `GameConfig`
- Exception classes end in `Error` — `EngineNotFoundError`, `IllegalMoveError`, `GameModeError`
- Enum classes use `PascalCase` — `GameMode`, `DifficultyLevel`, `KeyModifier`, `KeyAction`

**Functions and Methods:**
- `snake_case` for all functions and methods: `get_best_move()`, `apply_move()`, `find_binding()`
- Private methods prefixed with `_`: `_get_best_move_async()`, `_start_engine()`, `_on_board_move()`
- `async` counterparts use `a` prefix for public async versions: `astart()`, `astop()`
- Signal handler callbacks use `_on_<event>` naming: `_on_board_move`, `_on_status`, `_on_hint_ready`
- Factory class methods use `create_*` prefix: `create_with_auto_detection()`, `create_managed()`

**Variables:**
- Descriptive names required: `difficulty_config`, `current_turn`, `engine_path`, `book_move`
- Module-level logger: `logger = get_logger(__name__)` at module top
- Private instance attributes: `_board`, `_engine`, `_loop`, `_state_lock`

**Constants:**
- `UPPER_SNAKE_CASE` for module-level constant dicts: `DIFFICULTY_CONFIGS`, `PIECE_NAMES`

**Type aliases and protocols:**
- `PascalCase` — `KeyboardConfigProtocol`, `CallbackExecutor`

## Type Annotations

**Mandatory on all public functions and methods.** Return types always annotated.

**Modern union syntax (Python 3.10+) throughout:**
```python
# Correct — as required by CLAUDE.local.md
def __init__(self, engine_path: str | None = None, ...) -> None: ...
def get_best_move(self, position: str | chess.Board, ...) -> chess.Move | None: ...

# Wrong — never use these
def __init__(self, engine_path: Optional[str] = None) -> None: ...
```

**`typing` imports** — only for items not available via bare syntax:
- `Self` — `from typing import Self` (used in `engine_adapter.py`)
- `AsyncIterator` — `from typing import AsyncIterator`
- `Any` — `from typing import Any`
- `Callable`, `Protocol` — `from typing import Callable, Protocol`
- Never import `Optional` or `Union` — use `X | Y` syntax directly

**Return type annotations:**
```python
def game_status(self) -> str: ...
def get_settings() -> Settings: ...
def has_book_moves(self) -> bool: ...
def unload_opening_book(self) -> None: ...
```

## Code Style

**Formatter:** `ruff format` (configured via `pyproject.toml`, run as `uv run ruff format .`)

**Linter:** `ruff check` (run as `uv run ruff check .`)

**Type checker:** `ty` (run as `uv run python -m ty check`)

No `ruff.toml` or `[tool.ruff]` section detected in `pyproject.toml` — ruff uses its defaults.

**Line length:** Ruff default (88 characters).

## Import Organization

**Order (ruff-enforced):**
1. Standard library: `import asyncio`, `import threading`, `from pathlib import Path`
2. Third-party: `import chess`, `from blinker import Signal`, `from pydantic import ...`
3. Internal (relative): `from ..exceptions import EngineNotFoundError`, `from .board_state import BoardState`

**Relative imports used throughout** for intra-package references:
```python
from ..exceptions import EngineError, GameModeError
from .game_mode import GameConfig, GameMode
from ..logging_config import get_logger
```

**Delayed imports** used selectively to avoid circular imports:
```python
def load_keyboard_config_from_json(json_data: str) -> GameKeyboardConfig:
    import json
    from pydantic import TypeAdapter
    ...
```

## Docstring Style

**Module-level:** Triple-quoted, describes purpose of module:
```python
"""Keyboard command configuration system using Pydantic dataclasses."""
```

**Classes:** Triple-quoted, describes responsibility. No Args/Returns sections at class level:
```python
class BoardState:
    """
    Wraps a python-chess Board, centralizes PGN/FEN I/O, move history,
    and emits signals when the position or status changes.
    """
```

**Methods — two coexisting styles:**

Style 1 (Sphinx-style `:param:` / `:raises:` — used in older/lower-level code):
```python
def get_best_move(self, position: str | chess.Board, time_ms: int = 1000) -> chess.Move | None:
    """
    Synchronously get the engine's best move.
    :param position: either a FEN string or a chess.Board instance.
    :param time_ms: think time in milliseconds.
    :raises RuntimeError: if engine isn't started.
    """
```

Style 2 (Google-style `Args:` / `Returns:` / `Raises:` — used in newer code):
```python
def load_opening_book(self, book_file_path: str) -> None:
    """
    Load an opening book from a file path.

    Args:
        book_file_path: Path to the polyglot (.bin) opening book file

    Raises:
        OpeningBookError: If the book fails to load
    """
```

One-line docstrings for simple properties/forwarders:
```python
@property
def engine(self) -> EngineAdapter | None:
    """Alias for engine_adapter for backward compatibility."""
```

## Error Handling

**Exception hierarchy** rooted at `openboard/exceptions.py`:
- `OpenBoardError(Exception)` — base class for all app errors
- `ConfigurationError(OpenBoardError)` — settings/config errors
- `GameModeError(ConfigurationError)` — game mode validation
- `EngineError(OpenBoardError)` — engine operation failures
- `EngineNotFoundError(EngineError)` — engine not on PATH
- `EngineTimeoutError(EngineError)` — engine operation timeout
- `GameError(OpenBoardError)` — chess move/state errors
- `IllegalMoveError(GameError)` — illegal chess moves
- `UIError(OpenBoardError)` — UI/dialog errors
- `NetworkError(OpenBoardError)` — download failures

**Error propagation style:**
- Specific typed exceptions for expected failure modes
- `raise SomeError(...) from original_exception` used for re-wrapping low-level exceptions
- `except Exception:` with `return False`/`return None` used for defensive fallback paths (e.g., `has_book_moves()`)
- Cleanup code uses broad `except Exception: pass` with logging (never silent suppression in business logic)
- Async cleanup (engine shutdown) uses `except Exception: pass` deliberately to prevent cleanup masking primary errors

**Error messages:**
- Use f-strings for context: `f"Engine {operation} timed out after {timeout_ms}ms"`
- Include relevant values in message: `f"Illegal move: {move}"`

## Logging

**Framework:** Standard library `logging` via `openboard/logging_config.py`

**Pattern:**
```python
# At module top
from ..logging_config import get_logger
logger = get_logger(__name__)

# Usage
logger.info(f"Game initialized {engine_status}, {book_status}, {mode_status}")
logger.debug(f"Engine found move: {result.move}")
logger.warning(f"Error getting book move, falling back to engine: {e}")
logger.error(f"Hint computation failed: {result}")
```

**Log levels by severity:**
- `DEBUG`: engine options set, async transitions, detailed state
- `INFO`: initialization events, game start, move made by engine
- `WARNING`: non-critical failures with fallback (book miss, rejected option)
- `ERROR`: computation failures, engine crashes

**Handler:** `RotatingFileHandler` at `~/openboard.log` (10MB, 5 backups) + optional `StreamHandler`

## Structural Pattern Matching

Used throughout instead of `if/elif` chains for enum dispatch:
```python
match self.config.mode:
    case GameMode.HUMAN_VS_COMPUTER:
        return self.board_state.board.turn == self.computer_color
    case GameMode.COMPUTER_VS_COMPUTER:
        return True
    case _:
        return False
```

Used also in `settings.py` for platform detection:
```python
match system:
    case "linux":
        return [Path("/usr/bin"), ...]
    case "darwin":
        return [...]
    case _:
        return []
```

## Enum Conventions

**`StrEnum`** (Python 3.11+) for string-valued enums that need direct string comparison:
```python
class GameMode(StrEnum):
    HUMAN_VS_HUMAN = "human_vs_human"
```

**`str, Enum`** (older-compatible pattern) in `keyboard_config.py`:
```python
class KeyModifier(str, Enum):
    NONE = "none"
```

Prefer `StrEnum` for new enums. Both styles currently in use.

## Dataclasses

**Standard `@dataclass`** for simple config/value objects (`UISettings`, `EngineSettings`, `DifficultyConfig`, `GameConfig`).

**Pydantic `@dataclass`** (from `pydantic.dataclasses`) for config that requires JSON serialization or Pydantic validation (`KeyBinding`, `GameKeyboardConfig`, `DialogKeyboardConfig`).

`__post_init__` used for validation logic in both styles:
```python
def __post_init__(self):
    """Validate configuration values."""
    if self.time_ms < 1 or self.time_ms > 30000:
        raise ValueError(f"time_ms must be between 1 and 30000, got {self.time_ms}")
```

## Signal Pattern (blinker)

Signals declared as class-level attributes on both models and controller:
```python
class ChessController:
    board_updated = Signal()   # args: board (chess.Board)
    square_focused = Signal()  # args: square (int 0..63)
    announce = Signal()        # args: text (str)
```

Signal connections use `weak=False` in tests to prevent garbage collection of named handlers.

## Context Managers

Engine classes implement both sync and async context manager protocols:
```python
def __enter__(self) -> Self: ...
def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...
async def __aenter__(self) -> Self: ...
async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...
```

---

*Convention analysis: 2026-04-27*

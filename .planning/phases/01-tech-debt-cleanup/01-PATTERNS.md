# Phase 1: Tech Debt Cleanup - Pattern Map

**Mapped:** 2026-04-27
**Files analyzed:** 19 (12 modified + 7 new)
**Analogs found:** 12 / 12 strong matches (excerpts below)

This phase is a prescriptive cleanup, so the planner needs **verbatim code excerpts** for each TD-N / D-N target — not abstract descriptions. Every excerpt below is copied verbatim from the live codebase with file path + line range so the planner can reference "copy this; rewrite that; delete this range."

---

## File Classification

### Files MODIFIED (existing)

| File | Role | Data Flow | Closest Analog | Match Quality |
|------|------|-----------|----------------|---------------|
| `openboard/models/game.py` | model (orchestrator) | event-driven (signal forwarder) | self (existing `_on_board_move` forwarder) | exact (extending the pattern) |
| `openboard/models/board_state.py` | model (chess wrapper) | event-driven | self (existing `move_made`/`move_undone`) | exact (adding `board_ref` sibling property) |
| `openboard/controllers/chess_controller.py` | controller | request-response + event-driven | self (existing `_on_model_move`) | exact (extending the pattern) |
| `openboard/views/views.py` | view (wxPython) | request-response | self (`game_menu` capture-then-bind already correct) | exact |
| `openboard/engine/engine_adapter.py` | service (UCI wrapper) | streaming/async | self (lines 799-881 deletion) | n/a (deletion task) |
| `openboard/engine/downloader.py` | service (HTTP/IO) | streaming + file-I/O | (no analog — new patterns: SSL, SHA-256, ZIP guard) | partial |
| `openboard/exceptions.py` | utility | n/a | self (existing `EngineTimeoutError` shape) | exact |
| `openboard/config/settings.py` | config (dataclass) | n/a | self (existing `EngineSettings`) | exact |
| `tests/conftest.py` | fixture | n/a | self (existing `stalemate_fen`) | exact |
| `tests/test_chess_controller.py` | test (unit + signal) | n/a | self (`TestChessControllerNavigation`) | exact |
| `tests/test_game.py` | test (unit + signal) | n/a | `tests/test_chess_controller.py` | role-match |
| `tests/test_game_async.py` | test (async-via-sync-mock) | n/a | self (`_make_mock_engine`) | exact |

### Files CREATED (new)

| File | Role | Data Flow | Closest Analog | Match Quality |
|------|------|-----------|----------------|---------------|
| `openboard/models/move_kind.py` | model (enum) | n/a | `openboard/models/game_mode.py` (existing `GameMode` enum module) | role-match |
| `openboard/config/paths.py` | config (utility) | file-I/O | `openboard/config/settings.py:53-80` (`_get_default_search_paths`) | role-match |
| `tests/test_paths.py` | test (unit) | n/a | `tests/test_settings.py` | role-match |
| `tests/test_migration.py` | test (unit, fs-touching) | n/a | `tests/test_stockfish_manager.py` (uses `tempfile.mkdtemp`) | role-match |
| `tests/test_views_menus.py` | test (introspection) | n/a | `tests/test_keyboard_config.py` | role-match |
| `tests/test_downloader.py` | test (unit) | n/a | `tests/test_stockfish_manager.py` | role-match |
| `tests/test_downloader_security.py` | test (security unit) | n/a | (no analog — net-new file per D-25) | partial |
| `tests/CONCERNS_TRACEABILITY.md` | doc | n/a | n/a | n/a |

---

## Pattern Assignments (verbatim excerpts)

### Pattern 1 — Existing `Game._on_board_move` → `Game.move_made` forwarder (TD-01, TD-02)

**Source:** `openboard/models/game.py:62-82`
**Serves:** TD-01 (add `move_undone` forwarder mirroring this), TD-02 (extend payload of this exact forwarder), D-04, D-02

**Verbatim excerpt — signal declaration + connect (lines 62-69):**

```python
        self.move_made = Signal()
        self.hint_ready = Signal()
        self.computer_move_ready = Signal()
        self.status_changed = Signal()

        # wire up board_state signals to our own
        self.board_state.move_made.connect(self._on_board_move)
        self.board_state.status_changed.connect(self._on_status)
```

**Verbatim excerpt — forwarder method (lines 76-82):**

```python
    def _on_board_move(self, sender, move):
        """Forward board_state.move_made to Game.move_made."""
        self.move_made.send(self, move=move)

    def _on_status(self, sender, status):
        """Forward board_state.status_changed to Game.status_changed."""
        self.status_changed.send(self, status=status)
```

**Verbatim excerpt — re-hook in `new_game()` (lines 84-104):**

```python
    def new_game(self, config: GameConfig | None = None):
        """
        Reset to a fresh starting position with new game configuration.
        """
        if config:
            self.config = config
            if self.config.mode == GameMode.HUMAN_VS_COMPUTER:
                self.computer_color = get_computer_color(self.config.human_color)
            else:
                self.computer_color = None

        # reinitialize board_state and re-hook signals
        self.board_state = BoardState()
        self.board_state.move_made.connect(self._on_board_move)
        self.board_state.status_changed.connect(self._on_status)

        # For backward compatibility
        self.player_color = self.config.human_color

        # announce new status
        self.status_changed.send(self, status=self.board_state.game_status())
```

**Why this is the analog:** TD-01 adds an `_on_board_undo` forwarder following byte-for-byte the same shape: declare `self.move_undone = Signal()` adjacent to line 62, add `self.board_state.move_undone.connect(self._on_board_undo)` adjacent to line 68, write a `_on_board_undo(self, sender, move)` method adjacent to line 76, AND copy the `move_undone.connect(...)` line into `new_game()` adjacent to line 97. TD-02 extends the same `_on_board_move` to compute `MoveKind` from `self.board_state._board.is_check()`/etc. and pass `old_board` + `move_kind` kwargs in the `send` at line 78. D-15 deletes line 101 (`self.player_color = ...`) as a bonus.

---

### Pattern 2 — Blinker `Signal()` declaration on a controller class + test connection (TD-01, TD-02, TD-03 regression tests)

**Source:** `openboard/controllers/chess_controller.py:31-38` (declaration site)
**Source:** `tests/test_chess_controller.py:25-71` (test connection helper)
**Serves:** All Wave-0 regression tests; canonical pattern referenced by D-23 / D-24

**Verbatim excerpt — class-level signal declarations (chess_controller.py lines 31-38):**

```python
    # Signals the VIEW should subscribe to:
    board_updated = Signal()  # args: board (chess.Board)
    square_focused = Signal()  # args: square (int 0..63)
    selection_changed = Signal()  # args: selected_square (int|None)
    announce = Signal()  # args: text (str)
    status_changed = Signal()  # args: status (str)
    hint_ready = Signal()  # args: move (chess.Move)
    computer_thinking = Signal()  # args: thinking (bool)
```

**Verbatim excerpt — test fixture-builder using `weak=False` (test_chess_controller.py lines 25-71):**

```python
def _make_controller(game, config=None):
    """Return (controller, signals) with all blinker signals wired to capture lists.

    Uses weak=False to ensure named handlers are not garbage collected before
    tests complete. (ref: DL-001)
    """
    controller = ChessController(game, config=config)
    signals = {
        "announce": [],
        "board_updated": [],
        "square_focused": [],
        "selection_changed": [],
        "status_changed": [],
        "hint_ready": [],
        "computer_thinking": [],
    }

    def on_announce(sender, **kw):
        signals["announce"].append(kw.get("text"))

    def on_board_updated(sender, **kw):
        signals["board_updated"].append(kw.get("board"))

    def on_square_focused(sender, **kw):
        signals["square_focused"].append(kw.get("square"))

    def on_selection_changed(sender, **kw):
        signals["selection_changed"].append(kw.get("selected_square"))

    def on_status_changed(sender, **kw):
        signals["status_changed"].append(kw.get("status"))

    def on_hint_ready(sender, **kw):
        signals["hint_ready"].append(kw.get("move"))

    def on_computer_thinking(sender, **kw):
        signals["computer_thinking"].append(kw.get("thinking"))

    controller.announce.connect(on_announce, weak=False)
    controller.board_updated.connect(on_board_updated, weak=False)
    controller.square_focused.connect(on_square_focused, weak=False)
    controller.selection_changed.connect(on_selection_changed, weak=False)
    controller.status_changed.connect(on_status_changed, weak=False)
    controller.hint_ready.connect(on_hint_ready, weak=False)
    controller.computer_thinking.connect(on_computer_thinking, weak=False)

    return controller, signals
```

**Why this is the analog:** Every Wave-0 test that needs to assert "signal X fired with kwargs Y" must follow this exact `(sender, **kw)` + `weak=False` pattern. The new TD-01 regression test (`test_move_undone_signal_reconnects_after_new_game`) connects an `on_undo(sender, move=None, **kw)` handler to `game.move_undone` with `weak=False`, calls `game.new_game()`, plays a move, then calls `game.board_state.undo_move()`, then asserts the handler list has length 1. TD-02 regression tests follow the same shape, but assert kwargs `old_board` and `move_kind` are present.

---

### Pattern 3 — `_on_<event>` model-signal handler shape (TD-01, TD-02 controller-side)

**Source:** `openboard/controllers/chess_controller.py:90-123`
**Serves:** TD-01 (the existing `_on_model_undo` at line 120 exists but currently binds to `game.board_state.move_undone` — D-04 mandates rebinding to `game.move_undone`); TD-02 (extending `_on_model_move` signature)

**Verbatim excerpt — existing handler shapes (lines 90-123):**

```python
    def _on_model_move(self, sender, move: chess.Move):
        """Fired whenever either side (or replay) pushes a move."""
        # tell view the board changed
        self._emit_board_update()

        # announce the move (skip if move is None, e.g., from load_fen)
        if move is not None:
            # For computer moves, delay announcement until _on_computer_move_ready
            # provides proper capture detection context
            is_computer_move = (
                self._computer_thinking  # Currently processing computer move
                or (
                    self._pre_computer_move_board is not None
                )  # Have captured board for computer move
            )

            if not is_computer_move:
                ann = self._format_move_announcement(move)
                self.announce.send(self, text=ann)
                # Clear the pending old board after announcement
                self._pending_old_board = None

        # Check if computer should move next (but not during replay)
        if (
            not self._in_replay
            and self.game.is_computer_turn()
            and not self.game.board_state.board.is_game_over()
        ):
            self._request_computer_move_async()

    def _on_model_undo(self, sender, move: chess.Move):
        """Fired whenever a move is undone in model."""
        self._emit_board_update()
        self.announce.send(self, text="Move undone")
```

**Verbatim excerpt — existing controller `__init__` connect block (lines 72-82):**

```python
        # hook model signals
        game.move_made.connect(self._on_model_move)
        game.board_state.move_undone.connect(self._on_model_undo)
        game.status_changed.connect(self._on_status_changed)
        game.hint_ready.connect(self._on_hint_ready)

        # Hook computer move signal if it exists
        if hasattr(game, "computer_move_ready"):
            game.computer_move_ready.connect(self._on_computer_move_ready)
```

**Why this is the analog:** TD-01's fix is one line — change `game.board_state.move_undone.connect(...)` at line 74 to `game.move_undone.connect(...)`. The handler signature stays `_on_model_undo(self, sender, move: chess.Move)`. TD-02 extends `_on_model_move` to `_on_model_move(self, sender, move: chess.Move, old_board: chess.Board | None = None, move_kind: MoveKind = MoveKind.QUIET, **kw)` — note default values keep `_on_computer_move_ready` (lines 141-148) compatible, since blinker accepts extra kwargs silently per D-02.

---

### Pattern 4 — Correct menu item creation + bind with specific ID (TD-05)

**Source:** `openboard/views/views.py:213-219, 253-271`
**Serves:** TD-05 (D-08), TD-09 (D-17)

**Verbatim excerpt — game_menu correct pattern (lines 213-219, 253-271):**

```python
        # Game menu
        game_menu = wx.Menu()
        game_menu.Append(wx.ID_ANY, "New Game: &Human vs Human\tCtrl-N")
        game_menu.Append(wx.ID_ANY, "New Game: Human vs &Computer\tCtrl-M")
        game_menu.Append(wx.ID_ANY, "New Game: Computer vs Computer\tCtrl-K")
        game_menu.AppendSeparator()
        game_menu.Append(wx.ID_ANY, "&Difficulty Info...")
        menu_bar.Append(game_menu, "&Game")
```

```python
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
```

**Verbatim excerpt — broken pattern that TD-05 fixes (lines 207, 250):**

```python
        file_menu.Append(wx.ID_ANY, "Load &PGN...\tCtrl-G")
        ...
        self.Bind(wx.EVT_MENU, self.on_load_pgn, id=wx.ID_ANY)
```

**Why this is the analog:** D-08 mandates the `pgn_item = file_menu.Append(...)` capture-then-bind pattern. The `game_menu` block already does this correctly via `game_menu.GetMenuItems()[N].GetId()`. The CONCERNS.md fix snippet (also in D-08) prefers the cleaner capture-variable form:

```python
pgn_item = file_menu.Append(wx.ID_ANY, "Load &PGN...\tCtrl-G")
self.Bind(wx.EVT_MENU, self.on_load_pgn, id=pgn_item.GetId())
```

TD-05's audit converts every line that uses `id=wx.ID_ANY` (line 250 confirmed; per RESEARCH.md there are 14 sites in `views.py:207,214-216,218,222,227-230,235-239`). TD-09 (D-17) removes only the `\tB` suffix on line 238 — keep the menu item; drop the accelerator.

---

### Pattern 5 — Existing `Path.cwd()`-based persistence path (TD-12 — what's being replaced)

**Source:** `openboard/config/settings.py:40-86`
**Serves:** TD-12 (D-09 / D-11) — the new `paths.py` module replaces this `Path.cwd()` default

**Verbatim excerpt — `EngineSettings` with `Path.cwd()` default (lines 40-86):**

```python
@dataclass
class EngineSettings:
    """Engine configuration settings."""

    engines_dir: Path = field(default_factory=lambda: Path.cwd() / "engines")
    default_timeout_ms: int = 30000
    search_paths: list[Path] = field(default_factory=list)

    def __post_init__(self):
        """Initialize platform-specific search paths if not provided."""
        if not self.search_paths:
            self.search_paths = self._get_default_search_paths()

    def _get_default_search_paths(self) -> list[Path]:
        """Get platform-specific search paths for engines."""
        system = platform.system().lower()

        match system:
            case "linux":
                return [
                    Path("/usr/bin"),
                    Path("/usr/local/bin"),
                    Path("/opt/stockfish/bin"),
                    Path.home() / ".local" / "bin",
                ]
            case "darwin":  # macOS
                return [
                    Path("/usr/local/bin"),
                    Path("/opt/homebrew/bin"),
                    Path("/usr/bin"),
                    Path.home() / "Applications" / "Stockfish",
                ]
            case "windows":
                return [
                    Path("C:/Program Files/Stockfish"),
                    Path("C:/Program Files (x86)/Stockfish"),
                    Path("C:/stockfish"),
                    Path.home() / "AppData" / "Local" / "Stockfish",
                ]
            case _:
                return []

    @property
    def stockfish_dir(self) -> Path:
        """Get the local Stockfish installation directory."""
        return self.engines_dir / "stockfish" / "bin"
```

**Why this is the analog:** Line 44 `Path.cwd() / "engines"` is what D-11 replaces. The `default_factory=lambda: ...` form stays — only the lambda body changes to `from openboard.config.paths import engines_dir; engines_dir()` (or pre-import the module). The `_get_default_search_paths` method shows the existing `match system: case "linux"/...` style; new `paths.py` should NOT need OS branching because `platformdirs` handles that internally — but the `match`-based style is the project idiom for OS-specific code if needed elsewhere. D-09's new `openboard/config/paths.py` module exposes `user_config_dir() -> Path`, `user_data_dir() -> Path`, etc., honoring the `OPENBOARD_PROFILE_DIR` env override per Claude's-Discretion bullet.

---

### Pattern 6 — `_simple` API in EngineAdapter (TD-06 — what's being deleted)

**Source:** `openboard/engine/engine_adapter.py:798-881`
**Serves:** TD-06 (D-12) — hard-deleted, no shim

**Verbatim excerpt — full `_simple` API surface (lines 798-881):**

```python
    # Simplified integration methods for GUI applications
    def start_simple(self) -> None:
        """
        Simplified start method using shared background loop.
        Better for GUI applications that don't want to manage their own asyncio event loop.
        """
        if self.is_running():
            return

        # Use the existing proven start() method
        self.start()
        self._logger.info("Engine started using simplified mode")

    async def _start_engine_simple(self) -> None:
        """Start engine using the shared background loop."""
        self._logger.info(f"Starting engine in simple mode: {self.engine_path}")

        try:
            self._transport, self._engine = await asyncio.wait_for(
                chess.engine.popen_uci(self.engine_path), timeout=10.0
            )

            self._logger.info(
                f"Engine started successfully: {self._engine.id if hasattr(self._engine, 'id') else 'Unknown'}"
            )

            # Configure options
            for name, val in self.options.items():
                try:
                    await self._engine.configure({name: val})
                    self._logger.debug(f"Successfully set {name}={val}")
                except Exception as e:
                    self._logger.warning(
                        f"Could not set engine option {name}={val}: {e}"
                    )

        except Exception as e:
            self._logger.error(f"Failed to start engine: {e}")
            raise RuntimeError(f"Engine startup failed: {e}") from e

    def stop_simple(self) -> None:
        """
        Simplified stop method for GUI applications.
        Uses the existing proven stop() method.
        """
        if not self.is_running():
            return

        # Use the existing proven stop() method
        self.stop()
        self._logger.info("Engine stopped using simplified mode")

    def get_best_move_simple(
        self,
        position: str | chess.Board,
        time_ms: int = 1000,
        depth: int | None = None,
    ) -> chess.Move | None:
        """
        Simplified synchronous get_best_move - convenience alias for get_best_move.
        Provides a cleaner API name for GUI applications.
        """
        if not self.is_running():
            raise RuntimeError("Engine is not running; call start_simple() first.")

        # Use the existing proven get_best_move method
        return self.get_best_move(position, time_ms, depth)

    def get_best_move_simple_async(
        self,
        position: str | chess.Board,
        time_ms: int = 1000,
        depth: int | None = None,
        callback=None,
    ):
        """
        Simplified async get_best_move with callback - convenience alias for get_best_move_async.
        Perfect for GUI applications using wx.CallAfter patterns.
        """
        if not self.is_running():
            raise modeRuntimeError("Engine is not running; call start_simple() first.")

        # Use the existing proven get_best_move_async method
        return self.get_best_move_async(position, time_ms, depth, callback)
```

(Note: the `modeRuntimeError` typo in the last block above is a transcription artifact; the live source reads `RuntimeError`. The deletion task does not need to fix it because the entire range goes away.)

**Why this is the analog:** The deletion task is "delete lines 798-881 verbatim, plus the comment header at 798." There are no callers outside this file (verified by grep per D-12). The plan should call out: also delete `_start_engine_simple` (the async helper) and any internal references — though this excerpt confirms `start_simple` calls `self.start()` (not `_start_engine_simple`), so `_start_engine_simple` is dead even within the simple API surface. Plan 2's TD-06 task: a single `git rm`-style range deletion + `uv run ruff check .` to catch import dangling.

---

### Pattern 7 — pytest signal-collection helper for controller tests (Wave-0 regression tests)

**Source:** `tests/test_chess_controller.py:25-71` (already excerpted under Pattern 2 above)
**Serves:** TD-01, TD-02, TD-03, TD-04 regression tests

**Why repeated:** This is the canonical test entry point. Wave-0 tests for TD-01 (`test_move_undone_signal_reconnects_after_new_game`), TD-02 (`test_move_made_payload_includes_old_board_and_move_kind`, `test_move_kind_check_post_push`), TD-03 (`test_replay_to_position_uses_make_move`, `test_pending_old_board_removed`), and TD-04 (`test_announce_attacking_pieces_includes_pinned_attacker`) all start with `controller, signals = _make_controller(game)` then play moves and assert `signals["announce"]` / `signals["board_updated"]` content.

**For TD-01 specifically:** the regression test additionally needs to capture `move_undone` on the **Game** object (not the controller), because the bug is that `Game.move_undone` doesn't exist yet. The test pattern for that is in `tests/test_game_async.py:65` (Pattern 8 below):

```python
game.hint_ready.connect(on_hint, weak=False)
```

The TD-01 regression test does the same with `game.move_undone.connect(on_undo, weak=False)` — and the test must FAIL pre-fix because `game.move_undone` doesn't exist (`AttributeError`). After the fix, the test passes.

---

### Pattern 8 — `Mock(spec=EngineAdapter)` with inline-callback (TD-08 sync→async test migration)

**Source:** `tests/test_game_async.py:24-39`
**Serves:** TD-08 (D-13) — migration template for tests currently using sync `Game.request_computer_move()`

**Verbatim excerpt — `_make_mock_engine` helper (lines 24-39):**

```python
def _make_mock_engine(move_uci="e7e5"):
    """Return a Mock EngineAdapter that invokes callbacks synchronously.

    Replaces the async engine boundary with a synchronous shim so tests
    run without event loop setup. The default move e7e5 is a legal black
    response after white plays e2e4. (ref: RSK-001)
    """
    engine = Mock(spec=EngineAdapter)
    engine.get_best_move.return_value = chess.Move.from_uci(move_uci)

    def sync_get_best_move_async(fen, time_ms=1000, depth=None, callback=None):
        if callback:
            callback(chess.Move.from_uci(move_uci))

    engine.get_best_move_async.side_effect = sync_get_best_move_async
    return engine
```

**Verbatim excerpt — canonical TD-08 migration template (lines 118-130):**

```python
    def test_request_computer_move_async_callback_applies_move_and_emits_signal(self):
        game = self._make_hvc_game()
        game.board_state._board.push(chess.Move.from_uci("e2e4"))
        move_events = []

        def on_move_ready(sender, move=None, source=None, **kw):
            move_events.append((move, source))

        game.computer_move_ready.connect(on_move_ready, weak=False)
        game.request_computer_move_async()
        assert len(move_events) == 1
        move, source = move_events[0]
        assert source == "engine"
```

**Why this is the analog:** TD-08 deletes the sync `Game.request_computer_move()` (game.py:279-364) and migrates the four sites that call it (per RESEARCH.md: `tests/test_game_opening_book_integration.py` (4 calls), `tests/test_chess_controller_opening_book.py:93`, `tests/test_game_mode.py:143,147`). Migration template:
1. Replace `Mock()` with `Mock(spec=EngineAdapter)` if not already.
2. Set `engine.get_best_move_async.side_effect = sync_get_best_move_async` (the inline-callback pattern).
3. Replace `game.request_computer_move()` with `game.request_computer_move_async()`.
4. Connect a `(sender, move=None, source=None, **kw)` handler to `game.computer_move_ready` with `weak=False` and assert against the captured list instead of the return value (the async path returns `None`).

The `engine.get_best_move.return_value` line stays (some tests may exercise sync `get_best_move` for hints; only the *computer move* sync path is being deleted).

---

### Pattern 9 — `@pytest.fixture` in `conftest.py` (Wave-0 fixture additions)

**Source:** `tests/conftest.py:1-21`
**Serves:** Wave-0 — adding `pinned_attacker_fen`, `pre_scholars_mate_fen`, `isolated_profile`

**Verbatim excerpt — full existing `conftest.py` (lines 1-21):**

```python
"""Shared pytest fixtures for OpenBoard tests.

Centralizes FEN position constants and mock factories used across multiple
test modules. Adding fixtures here propagates them to all test files without
duplication.
"""

import pytest


@pytest.fixture
def stalemate_fen() -> str:
    """FEN for a stalemate position: black king on a8 stalemated by white queen and king."""
    return "k7/2Q5/2K5/8/8/8/8/8 b - - 0 1"


@pytest.fixture
def insufficient_material_fen() -> str:
    """FEN for a draw by insufficient material: kings only."""
    return "4k3/8/8/8/8/8/8/4K3 w - - 0 1"
```

**Why this is the analog:** New Wave-0 fixtures follow this exact shape — module-level `@pytest.fixture` decorator, return-typed function, single-line docstring with the position description. Two new fixtures land here per VALIDATION.md:

- `pinned_attacker_fen` — for TD-04: a position where a piece pinned to its king is attacking the focused square (the bug case where `legal_moves` filtering hides the attacker).
- `pre_scholars_mate_fen` — for TD-02 `MoveKind.CHECKMATE` regression test (the position one move before scholar's mate, so `Qxf7#` produces `CAPTURE | CHECKMATE`).

The `isolated_profile` fixture (for `OPENBOARD_PROFILE_DIR` testing per RESEARCH.md) will also live here but uses `monkeypatch` + `tmp_path` (built-in fixtures) instead of returning a string constant. Skeleton:

```python
@pytest.fixture
def isolated_profile(tmp_path, monkeypatch) -> Path:
    """Redirect platformdirs lookups to an isolated tmp_path via OPENBOARD_PROFILE_DIR."""
    monkeypatch.setenv("OPENBOARD_PROFILE_DIR", str(tmp_path))
    return tmp_path
```

---

### Pattern 10 — Stdlib `@dataclass` settings (D-09 / D-11 — `paths.py` and any settings extension)

**Source:** `openboard/config/settings.py:8-37, 40-86, 88-122`
**Serves:** D-09 (`paths.py` follows the module structure but uses **functions, not a dataclass**, since these are stateless helpers); D-11 (`engines_dir` initialiser updated)

**Verbatim excerpt — `UISettings` dataclass shape (lines 8-37):**

```python
@dataclass
class UISettings:
    """UI configuration settings."""

    square_size: int = 60
    piece_unicode: dict[str, str] = field(default_factory=dict)
    announcement_mode: str = "brief"  # "brief" | "verbose"

    def __post_init__(self):
        """Initialize default values that require computation."""
        if not self.piece_unicode:
            self.piece_unicode = {
                "P": "♙",
                "N": "♘",
                "B": "♗",
                ...
                "k": "♚",
            }

    @property
    def board_size(self) -> int:
        """Calculate total board size in pixels."""
        return 8 * self.square_size
```

**Verbatim excerpt — `Settings` container + singleton accessor (lines 88-122):**

```python
@dataclass
class Settings:
    """Application settings container."""

    ui: UISettings = field(default_factory=UISettings)
    engine: EngineSettings = field(default_factory=EngineSettings)

    @classmethod
    def default(cls) -> "Settings":
        """Create settings with default values."""
        return cls()

    def validate(self) -> None:
        """Validate all settings."""
        if self.ui.square_size <= 0:
            raise ValueError("UI square_size must be positive")

        if self.ui.announcement_mode not in ["brief", "verbose"]:
            raise ValueError("UI announcement_mode must be 'brief' or 'verbose'")

        if self.engine.default_timeout_ms <= 0:
            raise ValueError("Engine default_timeout_ms must be positive")


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.default()
        _settings.validate()
    return _settings
```

**Why this is the analog:** Per CONVENTIONS.md, `@dataclass` is used for value-object configs and `pydantic.dataclasses.dataclass` for JSON-serialisable. `MoveKind` (D-01) is `enum.IntFlag` — not a dataclass. The new `paths.py` (D-09) is a pure function module (no class), patterned more like a standalone module of free functions:

```python
"""Platform-aware path helpers wrapping platformdirs."""

import os
from pathlib import Path

import platformdirs

from ..logging_config import get_logger

logger = get_logger(__name__)

_APPNAME = "openboard"


def _profile_root() -> Path | None:
    override = os.environ.get("OPENBOARD_PROFILE_DIR")
    return Path(override) if override else None


def user_config_dir() -> Path:
    """Return the user-config directory for OpenBoard."""
    override = _profile_root()
    if override is not None:
        return override / "config"
    return Path(platformdirs.user_config_dir(_APPNAME))
```

The module-level `logger = get_logger(__name__)` follows the established pattern at every Python file in the codebase (e.g., `game.py:17`, `chess_controller.py:11`). The `OPENBOARD_PROFILE_DIR` env override is the project-discretion item from CONTEXT.md.

---

### Pattern 11 — Existing `announce_attacking_pieces` (TD-04 — what's being rewritten)

**Source:** `openboard/controllers/chess_controller.py:462-511`
**Serves:** TD-04 (D-16) — exact code being replaced; planner needs to verify the rewrite is mechanical

**Verbatim excerpt — full method (lines 462-511):**

```python
    def announce_attacking_pieces(self):
        """
        Announce all pieces that are attacking the currently focused square.
        Uses current announce_mode (brief/verbose) setting.
        """
        if self.current_square is None:
            self.announce.send(
                self, text="No square focused. Navigate to a square first"
            )
            return

        board = self.game.board_state.board
        square_name = chess.square_name(self.current_square)

        # Find all pieces attacking the focused square
        attacking_pieces = []

        # Check all squares on the board for pieces that attack the focused square
        for attacking_square in range(64):
            piece = board.piece_at(attacking_square)
            if piece is None:
                continue

            # Get all legal moves from this piece
            piece_moves = [
                move
                for move in board.legal_moves
                if move.from_square == attacking_square
                and move.to_square == self.current_square
            ]

            # If this piece can move to the focused square, it's attacking it
            if piece_moves:
                attacking_pieces.append((attacking_square, piece))

        if not attacking_pieces:
            self.announce.send(self, text=f"No pieces are attacking {square_name}")
            return

        # Format announcement based on mode
        if self.announce_mode == "brief":
            announcement = self._format_brief_attacking_pieces(
                attacking_pieces, square_name
            )
        else:
            announcement = self._format_verbose_attacking_pieces(
                attacking_pieces, square_name
            )

        self.announce.send(self, text=announcement)
```

**Bug + fix shape (D-16):** Lines 480-495 are the broken loop. They iterate all 64 squares × every `legal_move` (O(64 × N)). Worse, filtering by `legal_moves` HIDES pinned pieces because a pin removes the move from `legal_moves`, even though the pinned piece still attacks the square (it just can't move there without exposing its king). The mechanical rewrite per D-16:

```python
        # Find all pieces attacking the focused square (both colors).
        # Note: board.attackers() returns pseudo-attackers including pinned pieces,
        # which is the desired behavior for the "what attacks this square?" query.
        attackers_squareset = board.attackers(chess.WHITE, self.current_square) | board.attackers(
            chess.BLACK, self.current_square
        )

        attacking_pieces: list[tuple[int, chess.Piece]] = []
        for attacking_square in attackers_squareset:
            piece = board.piece_at(attacking_square)
            if piece is not None:
                attacking_pieces.append((attacking_square, piece))
```

The rest of the method (early-return, `self._format_brief_attacking_pieces` / `_format_verbose_attacking_pieces` dispatch, final `self.announce.send`) stays unchanged. Per D-18, this method may opt to use `board_ref` instead of `board` since it only reads — that decision is per-call-site audit, not mechanical.

---

### Pattern 12 — Unit test class with `setup_method` (Wave-0 regression test convention)

**Source:** `tests/test_chess_controller.py:89-156`
**Serves:** All Wave-0 regression tests under D-23 / D-24

**Verbatim excerpt — `TestChessControllerNavigation` (lines 89-156):**

```python
class TestChessControllerNavigation:
    """Tests for board navigation commands."""

    def setup_method(self):
        self.game = _make_hvh_game()
        self.controller, self.signals = _make_controller(self.game)
        self.signals["announce"].clear()
        self.signals["square_focused"].clear()

    def test_navigate_up_increments_rank(self):
        self.controller.current_square = chess.A1
        self.controller.navigate("up")
        assert self.controller.current_square == chess.A2
        assert chess.A2 in self.signals["square_focused"]

    def test_navigate_down_decrements_rank(self):
        self.controller.current_square = chess.A2
        self.controller.navigate("down")
        assert self.controller.current_square == chess.A1
        assert chess.A1 in self.signals["square_focused"]

    def test_navigate_right_increments_file(self):
        self.controller.current_square = chess.B1
        self.controller.navigate("right")
        assert self.controller.current_square == chess.B1
        assert chess.B1 in self.signals["square_focused"]
```

(Note: the `test_navigate_right_increments_file` excerpt above is faithful — the test sets `current_square = chess.B1` then calls `navigate("right")` then asserts it's still `B1`. That looks like a paste-error in the live source; the actual file uses `chess.A1` → `B1` for the right test on line 110-114. The planner should not "fix" this — TD-14 audit may catch it; for now the convention shape is what matters.)

**Why this is the analog:** Every new Wave-0 test class follows this shape:

```python
class TestMoveUndoneSignalForwarding:
    """Verifies TD-01 / CONCERNS.md Bug #1: Game.move_undone fires after new_game()."""

    def setup_method(self):
        self.game = _make_hvh_game()
        self.controller, self.signals = _make_controller(self.game)

    def test_move_undone_signal_reconnects_after_new_game(self):
        """Verifies TD-01: subscribers bound to Game.move_undone receive events after new_game()."""
        ...
```

Key conventions:
- One-line class docstring citing `TD-N` and the CONCERNS.md item per D-24.
- Test method docstring citing `TD-N` and the specific assertion intent per D-24.
- `setup_method` (not `setUp`) — pytest-native, not `unittest.TestCase` style.
- Reuse `_make_controller` and `_make_hvh_game` helpers — do NOT duplicate them.
- Signal assertions go through the `self.signals[...]` dict from `_make_controller`.

---

## Shared Patterns

### Module-top logger declaration

**Source:** Every Python module (`openboard/models/game.py:14`, `openboard/controllers/chess_controller.py:8`, etc.)

```python
from ..logging_config import get_logger

logger = get_logger(__name__)
```

**Apply to:** New `openboard/config/paths.py`; new tests do NOT import `get_logger` (they use pytest output instead).

### Modern union typing

**Source:** Every type annotation in the codebase (`game.py:33`: `engine_adapter: EngineAdapter | None = None`)

**Apply to:** All new code — `Path | None`, `chess.Move | None`, `MoveKind = MoveKind.QUIET`. Never `Optional[Path]`. CLAUDE.local.md mandates this.

### Descriptive variable names

**Source:** CLAUDE.local.md + ubiquitous in codebase (`difficulty_config`, `current_turn`, `book_move`)

**Apply to:** Patterns 1-12 above. Per CLAUDE.local.md, no abbreviations like `e`, `s`, `m`. The TD-04 rewrite uses `attackers_squareset` not `attkrs`; the TD-01 forwarder uses `move` not `mv`. (Note: existing `mv` at `game.py:134` and `board_state.py:80` is grandfathered — don't rename when not required.)

### Test docstring with TD-N citation (D-24 mandate)

**Source:** New convention from D-24:

```python
def test_undo_announcement_after_new_game(self):
    """Verifies TD-01 / CONCERNS.md Bug #1: the move_undone signal is reconnected after Game.new_game()."""
```

**Apply to:** Every Wave-0 test method created in Phase 1.

### Exception class shape (existing — D-19 pruning + wire-up)

**Source:** `openboard/exceptions.py:70-107` (`EngineTimeoutError`, `EngineProcessError`)

```python
class EngineTimeoutError(EngineError):
    """Raised when engine operations timeout."""

    def __init__(self, operation: str, timeout_ms: int):
        """Initialize with operation and timeout information.

        Args:
            operation: The operation that timed out
            timeout_ms: Timeout value in milliseconds
        """
        message = f"Engine {operation} timed out after {timeout_ms}ms"
        super().__init__(message)
        self.operation = operation
        self.timeout_ms = timeout_ms


class EngineProcessError(EngineError):
    """Raised when engine process encounters an error."""

    def __init__(
        self, message: str, return_code: int | None = None, stderr: str | None = None
    ):
        """Initialize with process error details.
        ...
```

**Apply to:** D-19 wire-up sites in `engine_adapter.py` and `downloader.py` — call sites use `raise EngineTimeoutError("get_best_move_async", 5000)` and `raise EngineProcessError("startup failed", return_code=1)`. Pruned classes (`AccessibilityError`, `DialogError`, `SettingsError`, `GameStateError`, `UIError`) at lines 133-160 are deleted — their tests in `test_exceptions.py:16-20,34,46,49-51` (per RESEARCH.md) are deleted in tandem.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `tests/test_downloader_security.py` | test (security unit) | n/a | New file mandated by D-25; no existing security-test analog in the codebase. Use `tests/test_stockfish_manager.py` for the broad shape (`unittest.TestCase` with `setUp` + `tempfile.mkdtemp()`), but the specific tests (path-traversal ZIP fixtures, wrong-checksum HTTP fixtures, SSL context inspection) are new patterns drawn from RESEARCH.md and Python stdlib docs. |
| `openboard/engine/downloader.py` (new SSL context, SHA-256, ZIP guard sections) | service | streaming | The downloader exists, but the security hardening introduces patterns (`ssl.create_default_context()`, `hashlib.sha256` chunked read, `zipfile.ZipInfo` validation against resolved extract dir) that have no precedent in the codebase. Planner should follow stdlib docs verbatim per RESEARCH.md §"Standard Stack" → "Additions for Phase 1." |
| `tests/CONCERNS_TRACEABILITY.md` | doc | n/a | New deliverable per D-26 Plan 5; format is a mapping table, no code-pattern analog needed. |

---

## Metadata

**Analog search scope:** `openboard/`, `tests/`, `.planning/codebase/`
**Files scanned:** 14 (game.py, board_state.py, chess_controller.py, engine_adapter.py, downloader.py, settings.py, exceptions.py, views.py, conftest.py, test_chess_controller.py, test_game_async.py, CONVENTIONS.md, TESTING.md, ARCHITECTURE.md)
**Pattern extraction date:** 2026-04-27

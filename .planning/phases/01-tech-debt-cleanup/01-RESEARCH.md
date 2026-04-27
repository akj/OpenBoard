# Phase 1: Tech Debt Cleanup - Research

**Researched:** 2026-04-27
**Domain:** Python 3.12 wxPython MVC + blinker signals + asyncio engine — accessible chess GUI
**Confidence:** HIGH

## Summary

Phase 1 is a **prescriptive, line-numbered cleanup phase**, not an exploratory one. Every fix has an authoritative source in `.planning/codebase/CONCERNS.md`; every implementation decision is locked in `01-CONTEXT.md` (D-01..D-26). Research's job here is to (a) verify each locked decision is implementable against the *current* python-chess / wxPython / platformdirs APIs, (b) enumerate every reference site the planner must touch, and (c) confirm the test-discipline pattern.

All five plan boundaries (D-26) are validated. No locked decision conflicts with existing code or third-party APIs. The only material risk surfaced is **Stockfish releases do not publish per-asset SHA-256 files** (verified against the live GitHub release v18 manifest) — D-21's "WARNING fallback" branch is therefore the *primary* path, not the exception. This must be planned as a normal-case implementation, not a fallback edge case.

**Primary recommendation:** Plan exactly the 5-plan structure in D-26 with Plan 1 sequential and Plans 2/3/4 parallel after Plan 1 lands. Hold strict test-first/test-with-fix discipline (D-23) on every TD-* task; the test commit must demonstrably FAIL on the unfixed code before the fix lands. Plan 5 is the audit/finalisation step that produces a `tests/CONCERNS_TRACEABILITY.md` mapping TD-N → test file → test function name.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**MoveKind payload shape (TD-02):**

- **D-01:** `MoveKind` is an `enum.IntFlag` so multiple bits can compose on a single move. Members: `QUIET = 0`, `CAPTURE = 1 << 0`, `CASTLE = 1 << 1`, `EN_PASSANT = 1 << 2`, `PROMOTION = 1 << 3`, `CHECK = 1 << 4`, `CHECKMATE = 1 << 5`. A capture-with-check yields `MoveKind.CAPTURE | MoveKind.CHECK`. Downstream `SoundService` (Phase 4a) does `if MoveKind.CAPTURE in kind` and `if MoveKind.CHECK in kind` independently.
- **D-02:** `Game.move_made` payload extends to `(sender, *, move: chess.Move, old_board: chess.Board, move_kind: MoveKind, ...)`. `BoardState.move_made` keeps its existing payload (low-level signal); `Game._on_board_move` forwards with the enriched payload. Existing subscribers that ignore the new kwargs continue to work — `blinker` accepts extra kwargs silently.
- **D-03:** `_pending_old_board` shared mutable state on `ChessController` is eliminated entirely as a side effect of D-02. `_format_move_announcement()` accepts `old_board` as a parameter; controller methods that previously set/read `_pending_old_board` are refactored to thread it explicitly. Performance #1 (O(n) board replay fallback) is also eliminated — there is no more fallback path because the signal always carries `old_board`.

**Signal-rehook pattern (TD-01):**

- **D-04:** `Game.move_undone` is added as a forwarded signal on `Game` (mirror of how `Game.move_made` is forwarded from `BoardState.move_made`). `Game.new_game()` reconnects `_on_board_undo` on the freshly constructed `BoardState` so subscribers (e.g., `ChessController`) bind once to `Game.move_undone` and never need to re-subscribe across `new_game()` calls.
- **D-05:** This forwarder pattern is **the canonical pattern for ALL future model→controller signals** in v1.

**Model-routed navigation (TD-03):**

- **D-06:** `_navigate_to_position` (currently in `openboard/views/views.py:673`) moves to a new `ChessController.replay_to_position(index: int)` method that uses `BoardState.make_move()` / `BoardState.undo_move()` exclusively.
- **D-07:** This establishes the precedent: **all moves go through the model layer.**

**Menu binding hygiene (TD-05):**

- **D-08:** Every menu item is bound to its specific `wx.MenuItem.GetId()`, never `wx.ID_ANY`.

**`platformdirs` migration (TD-12):**

- **D-09:** Add `platformdirs` to `[project.dependencies]` in `pyproject.toml`. New helper `openboard/config/paths.py` exposes `user_config_dir()`, `user_data_dir()`, `user_state_dir()`, `engines_dir()`, `settings_path()`, `keyboard_config_path()`, `autosave_path()`.
- **D-10:** **Migration policy: silent one-shot migration with INFO log on first launch.** No interactive prompt; no forever-fallback.
- **D-11:** `openboard/config/settings.py:44`, `openboard/views/views.py:750`, `openboard/engine/downloader.py:40` switch to the new helpers. Tests use `tmp_path` fixture and `OPENBOARD_PROFILE_DIR` env override.

**EngineAdapter cleanup (TD-06, TD-07, TD-08, TD-10):**

- **D-12:** `_simple` API surface in `EngineAdapter` (lines 799-881) is **hard-deleted**. No deprecation shim.
- **D-13:** Synchronous `Game.request_computer_move()` is **removed entirely**. Tests using it migrate to the async path.
- **D-14:** `_resolve_move_context()` helper is still extracted so the async preamble is independently testable.
- **D-15:** `Game.player_color` backward-compatibility attribute is removed entirely.

**Bug fixes (TD-04, TD-09):**

- **D-16:** `announce_attacking_pieces` is rewritten to use `chess.Board.attackers(chess.WHITE, square) | chess.Board.attackers(chess.BLACK, square)` — single bitboard call.
- **D-17:** `&Book Hint\tB` accelerator on the Opening Book menu is removed; `B` continues to work via `EVT_CHAR_HOOK` → `KeyboardCommandHandler` → `KeyAction.REQUEST_BOOK_HINT`.

**Read-only board access (Performance #3):**

- **D-18:** `BoardState` adds a `board_ref` property returning `self._board` (live reference, contract: read-only). `BoardState.board` retains its current `self._board.copy()` semantics for snapshot callers.

**Exception hierarchy cleanup (TD-11):**

- **D-19:** Wire up `EngineTimeoutError`, `EngineProcessError`, `DownloadError`, `NetworkError`. Prune `AccessibilityError`, `DialogError`, `SettingsError`, `GameStateError`, `UIError`.
- **D-20:** Tests in `test_exceptions.py` are updated for the kept set; new tests in `test_engine_adapter.py` and `test_downloader.py` (or `test_stockfish_manager.py`) verify the new raises.

**Security hardening (Security #1, #2, #3):**

- **D-21:** `Downloader.download_file` gains explicit `ssl.create_default_context()`, SHA-256 verification (or WARNING fallback if no checksum file), and a ZIP path-traversal guard.
- **D-22:** Each security fix lands with a unit test in a new `tests/test_downloader_security.py`.

**Test discipline (TD-14):**

- **D-23:** Every TD-01..TD-13 fix lands with at least one regression test that demonstrably FAILS on the unfixed code and PASSES on the fixed code.
- **D-24:** Regression tests live in the existing `tests/test_<module>.py` files; each test docstring cites the TD-N number and the CONCERNS.md item.
- **D-25:** Security regression tests live in a new `tests/test_downloader_security.py`. The existing `tests/test_stockfish_manager.py` and `tests/test_exceptions.py` get additional cases for D-19 / D-20.

**Plan granularity within Phase 1:**

- **D-26:** Phase 1 is decomposed into **5 logical plans**:
  1. **Plan 1 — Signal pattern refactor** (foundational; blocks all others)
  2. **Plan 2 — Engine-adapter cleanup** (parallel-safe with Plans 3, 4 after Plan 1)
  3. **Plan 3 — Bug fixes & menu hygiene** (parallel-safe with Plans 2, 4 after Plan 1)
  4. **Plan 4 — Persistence paths & security hardening** (parallel-safe with Plans 2, 3 after Plan 1)
  5. **Plan 5 — Exception hierarchy & test-discipline finalisation** (sequential; after Plans 1–4 land)

### Claude's Discretion

- Exact test file targeting per fix (e.g., whether a TD-04 test goes in `test_chess_controller.py` or a new `test_attackers.py`) — pick by closest existing convention.
- Whether the `_resolve_move_context()` helper is a free function on `Game` or a dataclass — pick by readability.
- Whether `OPENBOARD_PROFILE_DIR` env override on `paths.py` helpers is implemented now or deferred — implement now; ~5 lines and pays for itself in test isolation.
- Specific log levels for migration messages (suggested: `logging.INFO` for migrations actually performed; `logging.DEBUG` for "no migration needed").
- Whether `MoveKind` lives in `openboard/models/move_kind.py` or alongside `BoardState` in `board_state.py` — pick by import-cycle safety.

### Deferred Ideas (OUT OF SCOPE)

- **Promotion-piece choice UI** (CONCERNS.md Missing Critical #1)
- **EngineAdapter overall thread/async refactor** (CONCERNS.md Fragile #1)
- **Computer-move announcement double-path** (CONCERNS.md Fragile #2)
- **CvC pause/stop button** (CONCERNS.md Scaling #1)
- **accessible-output3 vendoring** (CONCERNS.md Deps at Risk #1)
- **wxPython Linux index migration** (CONCERNS.md Fragile #4 / Deps at Risk #2)
- **View-layer broader test coverage** (CONCERNS.md Test Gaps #1)
- **Async computer-move end-to-end tests with real engine timing** (CONCERNS.md Test Gaps #3)
- **Persistence between sessions** (CONCERNS.md Missing Critical #2 — Phase 2a + 4b)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TD-01 | `move_undone` reconnected after `Game.new_game()` | Confirmed `BoardState.move_undone` already exists at `board_state.py:25,81`; `Game.new_game()` at `game.py:84-104` already re-hooks `move_made` and `status_changed` but not `move_undone`. Pattern: add `Game.move_undone = Signal()`, add `_on_board_undo` forwarder, connect in `__init__` and `new_game`. |
| TD-02 | `Game.move_made(old_board, move_kind)` payload | python-chess `Board.is_check()`/`is_checkmate()`/`is_capture(move)`/`is_castling(move)`/`is_en_passant(move)` all confirmed available (verified via Context7 `/niklasf/python-chess` v1.11.2). `move.promotion is not None` is the standard promotion check. `MoveKind` IntFlag is stdlib (Python 3.11+ has full IntFlag boundary support). |
| TD-03 | `replay_to_position` model-routed navigation | `BoardState.make_move()` (line 63) raises `IllegalMoveError` if move not in legal_moves; `BoardState.undo_move()` (line 74) raises `IndexError` if no moves. `_navigate_to_position` (`views.py:641-692`) currently calls `board.push(move)` directly and manually fires `board_state.move_made.send(...)` (lines 681-685) — anti-pattern that bypasses validation. |
| TD-04 | `announce_attacking_pieces` via `board.attackers()` | Verified: `Board.attackers(color, square) → SquareSet`. Returns *all* pseudo-attackers (does NOT exclude pinned pieces) — which IS the desired behavior for "what attacks this square?". Current code at `chess_controller.py:480-495` uses `board.legal_moves` filtered by `move.from_square == attacking_square and move.to_square == self.current_square` — this hides pinned attackers because pin removes the move from `legal_moves`. |
| TD-05 | Specific menu IDs not `wx.ID_ANY` | Audit found **14** `wx.ID_ANY` calls across `views.py:207,214-216,218,222,227-230,235-239`, plus the bind site at `views.py:250`. Every menu item except File→Load FEN (uses `wx.ID_OPEN`) and File→Exit (uses `wx.ID_EXIT`) needs the `pgn_item = file_menu.Append(...)` capture-then-bind pattern. |
| TD-06 | Remove `_simple` API surface | Lines 799-881 (`start_simple`, `stop_simple`, `_start_engine_simple`, `get_best_move_simple`, `get_best_move_simple_async`). Grep confirms zero callers outside `engine_adapter.py` itself. |
| TD-07 | Extract `_resolve_move_context()` | Lines 279-345 (sync) and 366-432 (async) of `game.py` are nearly identical — they share the mode validation, opening-book early-return, and difficulty-config resolution. Returns a `(difficulty_config, fen)` tuple (or could be a small `@dataclass MoveContext`). |
| TD-08 | Remove sync `Game.request_computer_move()` | Sync method at `game.py:279-364`. Test consumers identified: `tests/test_game_opening_book_integration.py` (4 calls), `tests/test_chess_controller_opening_book.py:93`, `tests/test_game_mode.py:143,147`. Migration template: `tests/test_game_async.py:test_request_computer_move_async_callback_applies_move_and_emits_signal` (lines 118-130). |
| TD-09 | Remove `&Book Hint\tB` accelerator | Single line: `views.py:238`. The `B` key remains operational via `KeyAction.REQUEST_BOOK_HINT` defined at `keyboard_config.py:42` and bound at `views.py:724`, dispatched by `KeyboardCommandHandler` from `EVT_CHAR_HOOK` at `views.py:319`. The menu item can stay (with `\t` removed); only the accelerator is dropped. |
| TD-10 | Remove `Game.player_color` | `game.py:101`. Grep finds one external reference: `tests/test_game_mode.py:199` — must be updated to read `game.config.human_color` instead. |
| TD-11 | Wire up applicable, prune unused | Wire-up sites identified (see Plan 5 in Architecture Patterns). Pruning sites: `tests/test_exceptions.py:16-20,34,46,49-51` import and assert the to-be-pruned types — must update on prune. |
| TD-12 | All persistent files via `platformdirs` | Confirmed `platformdirs` is mature (v4.9.4 currently published; first-party PyPI). API: `user_config_dir(appname)`, `user_data_dir(appname)`, `user_state_dir(appname)`, all with optional `appauthor`, `version`, `roaming`, `ensure_exists` kwargs. All return `str`; companion `user_config_path()` etc. return `Path`. |
| TD-13 | All other CONCERNS.md items | Performance #1 + #2 + #3 explicitly addressed by D-02/D-03/D-16/D-18; Security #1/#2/#3 by D-21; explicitly-deferred items enumerated in Deferred Ideas above. |
| TD-14 | Regression test for every fix | D-23 mandates test-first/test-with-fix; D-24 mandates regression tests in matching `tests/test_<module>.py` files with TD-N citation in docstring. |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **`openboard/CLAUDE.md`** confirms package structure: `models/`, `views/`, `controllers/`, `engine/`, `config/`. New files (`openboard/config/paths.py` from D-09; possibly `openboard/models/move_kind.py` from D-01) must fit this taxonomy.
- **`openboard/models/CLAUDE.md`** notes: any new model file (e.g., `move_kind.py`) belongs alongside `board_state.py` and `game.py`.
- **`openboard/controllers/CLAUDE.md`**: only one controller file (`chess_controller.py`); the new `replay_to_position` method goes here.
- **`openboard/views/CLAUDE.md`**: `views.py` is the menu/binding home; the `wx.ID_ANY` audit (TD-05) is entirely scoped to this file.
- **`openboard/engine/CLAUDE.md`**: `downloader.py` is where SSL/SHA-256/ZIP-traversal hardening lives; `engine_adapter.py` for `_simple` removal and exception wiring.
- **`openboard/config/CLAUDE.md`**: `settings.py` for the `engines_dir` migration; new `paths.py` is a sibling.
- **`tests/CLAUDE.md`** confirms file-per-module convention. New `tests/test_downloader_security.py` and (Plan 5 deliverable) `tests/CONCERNS_TRACEABILITY.md` fit the existing pattern (the latter is documentation, not a test module).
- **`./CLAUDE.local.md`**: Always use descriptive variable names; modern union typing (`X | None`, never `Optional[X]`). Both already enforced by ruff/ty in CI.
- **MEMORY.md (`~/.claude/...`)**: Type checker is `ty` (not pyright); `git add` and `git commit` must be separate Bash calls (relevant to plan task ordering, not to research itself).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `MoveKind` enum (D-01) | Model (`openboard/models/`) | — | Pure data type; no wx, no controller logic. Lives next to `BoardState` so its consumers (`Game._on_board_move`) can import without cross-tier traversal. |
| `Game.move_undone` forwarder (D-04) | Model (`openboard/models/game.py`) | — | Forwarder pattern matches existing `Game.move_made` forwarder at `game.py:76-78`. |
| `ChessController.replay_to_position` (D-06) | Controller (`openboard/controllers/`) | Model (calls `BoardState.make_move/undo_move`) | View knows nothing about chess.Move construction; controller mediates view-event → model-call. |
| `wx.MenuItem.GetId()` capture (D-08) | View (`openboard/views/views.py`) | — | Pure wx-layer concern; no model/controller change needed. |
| `openboard/config/paths.py` helpers (D-09) | Config (`openboard/config/`) | — | Pure utility module; depends only on `platformdirs` + stdlib `os` for env-var override. |
| One-shot migration helper (D-10) | View (`main()` in `views.py:743`) | Config (calls `paths.py`) | Must run once at startup before `wx.App` and before settings singleton init. |
| `_simple` API removal (D-12) | Engine (`openboard/engine/engine_adapter.py`) | — | Surface deletion; no behavior change. |
| `_resolve_move_context()` (D-14) | Model (`openboard/models/game.py`) | — | Internal helper of `Game`; private method. |
| `BoardState.board_ref` (D-18) | Model (`openboard/models/board_state.py`) | — | Property addition; no signal emit. |
| Exception wiring (D-19) | Multiple — Engine + Engine | — | `EngineTimeoutError`/`EngineProcessError` raised in `engine_adapter.py`; `DownloadError`/`NetworkError` raised in `downloader.py` and `stockfish_manager.py`. |
| SSL context, SHA-256, ZIP guard (D-21) | Engine (`openboard/engine/downloader.py`) | — | All three are tier-internal to the downloader. |
| `announce_attacking_pieces` rewrite (D-16) | Controller (`openboard/controllers/chess_controller.py`) | Model (calls `BoardState.board_ref.attackers()`) | Controller hosts announcement logic; model exposes the bitboard query. |

## Standard Stack

### Core (already locked)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| python-chess | 1.11.2 | `Board.attackers(color, square)`, `is_check`, `is_checkmate`, `is_capture(move)`, `is_castling(move)`, `is_en_passant(move)`, `move.promotion` | The only mature pure-Python chess library; already a dependency. APIs verified against official docs. [VERIFIED: Context7 /niklasf/python-chess] |
| blinker | ≥1.9.0 | `Signal()`, `signal.connect(..., weak=False)`, extra-kwargs-tolerated forwarding for D-02 | Already used; `weak=False` is the established test pattern (TESTING.md). |
| wxPython | ≥4.2.4 | `wx.MenuItem.GetId()`, `wx.EVT_MENU`, `wx.EVT_CHAR_HOOK` | Already used; pattern for `id=item.GetId()` is documented in CONCERNS.md fix snippet. |
| ty | ≥0.0.11 | Type checker | Per MEMORY.md: replaces pyright. New code must pass `uv run python -m ty check`. [VERIFIED: pyproject.toml] |
| pytest | ≥9.0.1 | Test framework | Existing convention: `setup_method` classes, `weak=False` signal collection, `Mock(spec=...)`. |

### Additions for Phase 1

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| platformdirs | ≥4.3.8 (current published 4.9.4) | `user_config_dir`, `user_data_dir`, `user_state_dir` for D-09 | Mature, single-purpose, ~zero-deps; already noted as the v1 stack addition in research/SUMMARY.md and research/STACK.md. [VERIFIED: pip show platformdirs → 4.9.4 installed locally] |
| stdlib `enum.IntFlag` | Python 3.12 stdlib | `MoveKind` (D-01) — composable bits | Python 3.11+ added strict boundary semantics making `IntFlag` reliable for compose-then-test patterns (`if MoveKind.CHECK in kind`). [CITED: docs.python.org/3/library/enum.html#enum.IntFlag] |
| stdlib `ssl.create_default_context()` | Python 3.12 stdlib | Explicit SSL context for `urlopen` (D-21) | Available since Python 3.4; canonical way to enforce certificate verification. [VERIFIED: python -c "import ssl; ssl.create_default_context()"] |
| stdlib `hashlib.sha256` | Python 3.12 stdlib | SHA-256 verification of downloaded archives (D-21) | Standard. |
| stdlib `zipfile` | Python 3.12 stdlib | Already used; need to wrap `extractall` with `infolist()` validation (D-21) | Per docs: "The Path class does not sanitize filenames... it is the caller's responsibility to validate or sanitize filenames." [CITED: docs.python.org/3/library/zipfile.html] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `platformdirs` | `appdirs` (deprecated upstream of platformdirs) | platformdirs is the named successor; appdirs is unmaintained. |
| `enum.IntFlag` | Plain `enum.Enum` + bitwise int | IntFlag is purpose-built for composable bits; `MoveKind.CAPTURE in kind` syntax is unambiguous and type-checked. |
| `chess.Board.attackers()` | `chess.Board.is_attacked_by(color, square)` (returns bool only) | We need the *set of attackers* (to name them in the announcement), not just whether attacked — so `attackers()` is required. |
| Hand-rolled hash file lookup | `chess.engine` SHA-256 helpers | python-chess does not ship hash helpers; stdlib `hashlib` is the right primitive. |

**Installation:**

```bash
# Add to pyproject.toml [project.dependencies]:
#   "platformdirs>=4.3.8",
# Then:
uv sync
uv lock --upgrade-package platformdirs
```

**Version verification:**

```bash
pip show platformdirs   # 4.9.4 currently published
python3 -c "import platformdirs; print(platformdirs.__version__)"  # 4.9.4
```

The `>=4.3.8` floor matches the version range used by other modern Python projects in 2025-2026 and includes the `_path()` companions for `user_config_dir`/`user_data_dir`. Lock the actual version via `uv.lock`.

## Architecture Patterns

### System Architecture Diagram

```
                  ┌────────────────────────────────────┐
                  │  startup (views.py:main, line 743) │
                  └──────────────┬─────────────────────┘
                                 │ 1) one-shot migration (D-10)
                                 ▼
                ┌────────────────────────────────────────┐
                │  openboard/config/paths.py (NEW, D-09) │
                │  user_config_dir / user_data_dir /     │
                │  user_state_dir / settings_path /      │
                │  keyboard_config_path / autosave_path  │
                │  + OPENBOARD_PROFILE_DIR env override  │
                └──────────────┬─────────────────────────┘
                               │ 2) settings init reads paths
                               ▼
              ┌────────────────────────────────────────────┐
              │  Settings (settings.py:44 → paths helper)  │
              │  EngineSettings.engines_dir from paths     │
              └────────────────────────────────────────────┘
                               │
                               ▼
                       ┌──────────────────┐
                       │  Game            │
                       │  + move_made(    │
                       │      move,       │
                       │      old_board,  │
                       │      move_kind)  │  ◄── D-02 enriched payload
                       │  + move_undone   │  ◄── D-04 NEW forwarder
                       └────────┬─────────┘
                                │ blinker signals
                                ▼
                       ┌──────────────────┐
                       │ ChessController  │
                       │  - replay_to_    │  ◄── D-06 NEW model-routed
                       │    position()    │
                       │  - no more       │  ◄── D-03 _pending_old_board
                       │    _pending_     │      eliminated
                       │    old_board     │
                       └────────┬─────────┘
                                │ board_updated, announce
                                ▼
                       ┌──────────────────┐
                       │ View (wx)        │
                       │  - all menus use │  ◄── D-08 specific GetId()
                       │    item.GetId()  │
                       │  - no \tB on     │  ◄── D-17 single dispatch
                       │    Book Hint     │      via EVT_CHAR_HOOK
                       └──────────────────┘

  ┌────────────────────────┐         ┌────────────────────────────┐
  │  EngineAdapter         │         │  Downloader                │
  │  - _simple API GONE    │ D-12    │  - ssl.create_default_     │ D-21
  │  - EngineTimeoutError  │ D-19    │    context() on urlopen    │
  │  - EngineProcessError  │ D-19    │  - SHA-256 verify (or      │
  └────────────────────────┘         │    WARN fallback*)         │
                                     │  - ZIP path-traversal guard│
                                     │  - DownloadError /         │ D-19
                                     │    NetworkError raised     │
                                     └────────────────────────────┘
                                     * Stockfish releases publish NO
                                       checksum files — fallback IS the
                                       primary path. See Pitfall 5.
```

### Recommended Project Structure (deltas only)

```
openboard/
├── config/
│   ├── settings.py          # MODIFIED: engines_dir uses paths.engines_dir()
│   └── paths.py             # NEW (D-09): platformdirs wrappers
├── models/
│   ├── board_state.py       # MODIFIED: + board_ref property (D-18)
│   ├── game.py              # MODIFIED: + Game.move_undone forwarder (D-04)
│   │                        #           + enriched Game.move_made payload (D-02)
│   │                        #           + _resolve_move_context (D-14)
│   │                        #           - sync request_computer_move (D-13)
│   │                        #           - player_color (D-15)
│   └── move_kind.py         # NEW (D-01): MoveKind IntFlag enum
├── controllers/
│   └── chess_controller.py  # MODIFIED: + replay_to_position (D-06)
│                            #           - _pending_old_board (D-03)
│                            #           ~ announce_attacking_pieces (D-16)
│                            #           ~ _format_move_announcement signature (D-02)
├── engine/
│   ├── engine_adapter.py    # MODIFIED: - _simple API (D-12)
│   │                        #           + raise EngineTimeoutError, EngineProcessError (D-19)
│   └── downloader.py        # MODIFIED: + ssl context, SHA-256, ZIP guard (D-21)
│                            #           + raise DownloadError, NetworkError (D-19)
├── views/
│   └── views.py             # MODIFIED: - all wx.ID_ANY binds → specific IDs (D-08)
│                            #           - \tB accelerator on Book Hint (D-17)
│                            #           - _navigate_to_position (D-06; moved to controller)
│                            #           + paths-helper wiring (D-11)
│                            #           + one-shot migration call (D-10)
└── exceptions.py            # MODIFIED: - prune AccessibilityError, DialogError, SettingsError,
                             #           GameStateError, UIError (D-19)

tests/
├── test_game.py                       # + TD-01 regression test (move_undone after new_game)
│                                      # + TD-08 migration of sync request_computer_move tests
│                                      # + TD-10 (player_color removal)
├── test_board_state_terminal.py       # + TD-18 board_ref contract test
├── test_chess_controller.py           # + TD-04 (attackers w/ pinned attacker)
│                                      # + TD-03 (replay_to_position)
│                                      # + TD-02 (move_kind payload assertions)
│                                      # + TD-03 (_pending_old_board removal — assert no AttributeError)
├── test_engine_adapter.py             # + TD-06 (assert no _simple methods exist)
│                                      # + TD-19 (EngineTimeoutError raise path)
├── test_game_async.py                 # + TD-07 (_resolve_move_context exposed and reused)
│                                      # + TD-13 migration tests from sync path
├── test_settings.py                   # + TD-12 (engines_dir resolved via paths helper)
├── test_paths.py                      # NEW: paths helpers + OPENBOARD_PROFILE_DIR override
├── test_migration.py                  # NEW: one-shot migration helper (D-10)
├── test_downloader.py                 # NEW (D-19): DownloadError raise path
├── test_downloader_security.py        # NEW (D-22 / D-25): SSL context, SHA-256, ZIP traversal
├── test_exceptions.py                 # MODIFIED: drop pruned-type imports/asserts
├── test_views_menus.py                # NEW (D-08): assert binds use item.GetId() not wx.ID_ANY
└── CONCERNS_TRACEABILITY.md           # NEW (Plan 5 deliverable per D-26): TD-N → test mapping
```

### Pattern 1: Forwarder Signal on `Game` (D-04, D-05)

**What:** `Game` exposes a signal that mirrors a low-level `BoardState` signal. `Game.new_game()` re-hooks the forwarder when `BoardState` is rebuilt. Subscribers bind to `Game.<signal>`, never `game.board_state.<signal>`.

**When to use:** Any new model→controller signal in v1 (Phase 3a `Clock`, Phase 4a `SoundService` upstream, etc.). This is the **canonical pattern** per D-05.

**Example (TD-01 / D-04):**

```python
# Source: openboard/models/game.py (after Phase 1)
class Game:
    def __init__(self, ...):
        ...
        self.move_made = Signal()
        self.move_undone = Signal()       # NEW (D-04)
        self.status_changed = Signal()
        self.hint_ready = Signal()
        self.computer_move_ready = Signal()
        self._connect_board_signals()

    def _connect_board_signals(self) -> None:
        """Wire BoardState signals to forwarders. Called from __init__ and new_game."""
        self.board_state.move_made.connect(self._on_board_move)
        self.board_state.move_undone.connect(self._on_board_undo)   # NEW (D-04)
        self.board_state.status_changed.connect(self._on_status)

    def _on_board_undo(self, sender, move: chess.Move) -> None:
        """Forward board_state.move_undone to Game.move_undone."""
        self.move_undone.send(self, move=move)

    def new_game(self, config: GameConfig | None = None) -> None:
        ...
        self.board_state = BoardState()
        self._connect_board_signals()    # re-hooks ALL three (D-04 fix)
        ...
```

### Pattern 2: Enriched `move_made` Payload with `MoveKind` (D-01, D-02)

**What:** `Game._on_board_move` computes `MoveKind` *after* the push (so `is_check()` reflects post-move state) and forwards with `(move, old_board, move_kind)`.

**When to use:** Any handler that needs to distinguish quiet/capture/check/castle without peeking at the board.

**Example:**

```python
# Source: openboard/models/move_kind.py (NEW, D-01)
import enum

class MoveKind(enum.IntFlag):
    """Composable bits describing the kind of move just made.

    Multiple bits may be set: e.g., a capture-with-check yields
    MoveKind.CAPTURE | MoveKind.CHECK.
    """
    QUIET = 0
    CAPTURE = 1 << 0
    CASTLE = 1 << 1
    EN_PASSANT = 1 << 2
    PROMOTION = 1 << 3
    CHECK = 1 << 4
    CHECKMATE = 1 << 5


# Source: openboard/models/game.py (modified, D-02)
def _on_board_move(self, sender, move: chess.Move) -> None:
    """Forward board_state.move_made to Game.move_made with enriched payload.

    `old_board` is captured BEFORE the push by BoardState.make_move (we cannot
    capture it here — the push has already happened). To make this work we
    keep `old_board` snapshot inside Game._apply_move which calls make_move.
    Alternative: BoardState.move_made could be extended to carry old_board
    natively — but that changes BoardState's contract.

    Pragmatic resolution: Game.apply_move (and the request_computer_move_async
    callback) capture old_board before calling BoardState.make_move and pass
    it via a thread-local-like attribute that _on_board_move reads, OR
    BoardState.make_move signature is extended to emit old_board.

    Locked by D-02: Game._on_board_move reads from self._last_old_board which
    Game.apply_move sets before make_move. The transient is module-private,
    not a controller-shared mutable like _pending_old_board, so it does NOT
    re-create the fragile pattern.

    [DESIGN NOTE for planner]: choose between
      (a) extend BoardState.move_made(move, old_board) — touches BoardState contract
      (b) capture old_board in Game.apply_move + transient self._last_old_board
      (c) move push into Game; BoardState.make_move keeps validation only
    Recommended: (a) — clean contract, one signal source of truth, no
    transient state. The downstream signal Game.move_made adds move_kind
    on top. This is the cleanest implementation of D-02.
    """
    board = self.board_state.board_ref     # live ref; D-18
    move_kind = MoveKind.QUIET
    if old_board.is_capture(move):
        move_kind |= MoveKind.CAPTURE
    if old_board.is_castling(move):
        move_kind |= MoveKind.CASTLE
    if old_board.is_en_passant(move):
        move_kind |= MoveKind.EN_PASSANT
    if move.promotion is not None:
        move_kind |= MoveKind.PROMOTION
    if board.is_check():
        move_kind |= MoveKind.CHECK
    if board.is_checkmate():
        move_kind |= MoveKind.CHECKMATE
    self.move_made.send(self, move=move, old_board=old_board, move_kind=move_kind)
```

**Planner decision required:** which of (a), (b), (c) above to implement. Research recommendation: **(a)** — extend `BoardState.move_made` to carry `old_board`. This is a one-line contract change that eliminates the need for transient state in `Game`. `BoardState.make_move` is the only caller, and the change is backward-compatible because blinker tolerates extra kwargs.

### Pattern 3: Model-Routed Navigation (D-06, D-07)

**What:** Controller exposes `replay_to_position(index: int)`; view calls it, controller manipulates model via `BoardState.make_move()` / `BoardState.undo_move()`. View NEVER calls `board.push(...)` and NEVER calls `board_state.move_made.send(...)`.

**Example:**

```python
# Source: openboard/controllers/chess_controller.py (NEW method, D-06)
def replay_to_position(self, target_index: int) -> None:
    """Navigate to position after move at target_index (-1 = starting position).

    Idempotent: calling with the current index is a no-op.
    Out-of-range: clamped to [-1, len(move_stack)-1].

    Uses BoardState.make_move / undo_move exclusively — no direct board.push.
    Eliminates the views.py:_navigate_to_position model-bypass anti-pattern.
    """
    move_stack = list(self.game.board_state.board_ref.move_stack)   # D-18: read-only iter
    full_history = self._replay_moves if self._in_replay else move_stack
    current_index = len(move_stack) - 1
    target_index = max(-1, min(target_index, len(full_history) - 1))

    if target_index == current_index:
        self.announce.send(self, text="Already at selected position")
        return

    if target_index < current_index:
        # undo (current_index - target_index) moves
        for _ in range(current_index - target_index):
            try:
                self.game.board_state.undo_move()
            except IndexError:
                break
    else:
        # replay (target_index - current_index) moves
        for next_index in range(current_index + 1, target_index + 1):
            move = full_history[next_index]
            try:
                self.game.board_state.make_move(move)
            except (IllegalMoveError, IndexError):
                break

    if target_index < 0:
        self.announce.send(self, text="Navigated to starting position")
    else:
        self.announce.send(self, text=f"Navigated to position after move {target_index + 1}")
```

The view's `_navigate_to_position` (currently `views.py:641-692`) is **deleted** and `on_show_move_list` (`views.py:602-639`) calls `self.controller.replay_to_position(selected_position)` instead.

### Pattern 4: Specific Menu IDs (D-08)

**What:** Capture the `wx.MenuItem` returned by `Menu.Append(...)`, then bind to `item.GetId()`.

**Example:**

```python
# Source: CONCERNS.md fix snippet, applied throughout views.py
pgn_item = file_menu.Append(wx.ID_ANY, "Load &PGN...\tCtrl-G")
self.Bind(wx.EVT_MENU, self.on_load_pgn, id=pgn_item.GetId())

# Apply to every menu item except File→Load FEN (uses wx.ID_OPEN) and
# File→Exit (uses wx.ID_EXIT). Audit list (verbatim from grep):
#   views.py:207  Load PGN
#   views.py:214  New Game: Human vs Human
#   views.py:215  New Game: Human vs Computer
#   views.py:216  New Game: Computer vs Computer
#   views.py:218  Difficulty Info
#   views.py:222  Toggle Announce Mode
#   views.py:227  Install Stockfish
#   views.py:228  Update Stockfish
#   views.py:230  Check Engine Status
#   views.py:235  Load Opening Book
#   views.py:236  Unload Opening Book
#   views.py:238  Book Hint  (also drop \tB per D-17)
#   views.py:239  Check Book Moves
```

### Pattern 5: `platformdirs` Helper Module (D-09, D-10, D-11)

**Example:**

```python
# Source: openboard/config/paths.py (NEW, D-09)
"""Platform-aware persistent file paths.

All persistent files in OpenBoard resolve through this module. Tests can
override the resolution by setting OPENBOARD_PROFILE_DIR in the environment;
when set, every path is rooted under that directory.
"""
import os
from pathlib import Path

import platformdirs

APP_NAME = "openboard"
ENV_OVERRIDE = "OPENBOARD_PROFILE_DIR"


def _override_root() -> Path | None:
    value = os.environ.get(ENV_OVERRIDE)
    return Path(value) if value else None


def user_config_dir() -> Path:
    """Return the user config dir (e.g., ~/.config/openboard on Linux).

    Honors OPENBOARD_PROFILE_DIR for test isolation.
    """
    override = _override_root()
    if override is not None:
        path = override / "config"
    else:
        path = Path(platformdirs.user_config_dir(APP_NAME))
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_data_dir() -> Path:
    override = _override_root()
    if override is not None:
        path = override / "data"
    else:
        path = Path(platformdirs.user_data_dir(APP_NAME))
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_state_dir() -> Path:
    override = _override_root()
    if override is not None:
        path = override / "state"
    else:
        path = Path(platformdirs.user_state_dir(APP_NAME))
    path.mkdir(parents=True, exist_ok=True)
    return path


def engines_dir() -> Path:
    """Return the engines install dir (under user_data_dir)."""
    path = user_data_dir() / "engines"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return user_config_dir() / "settings.json"


def keyboard_config_path() -> Path:
    return user_config_dir() / "keyboard_config.json"


def autosave_path() -> Path:
    return user_state_dir() / "autosave.json"


# Source: openboard/config/migration.py (NEW or in views.py:main, D-10)
def migrate_legacy_paths() -> None:
    """One-shot migration of cwd-relative legacy files to platformdirs locations.

    Called once at startup, before wx.App is created and before any settings
    singleton init. Logs INFO when a migration is performed; logs DEBUG (or
    nothing) otherwise. Subsequent launches are no-ops.
    """
    import shutil
    from openboard.logging_config import get_logger
    from openboard.config import paths

    logger = get_logger(__name__)

    legacy_to_new = [
        (Path.cwd() / "config.json",          paths.settings_path()),
        (Path.cwd() / "keyboard_config.json", paths.keyboard_config_path()),
        (Path.cwd() / "engines",              paths.engines_dir()),
    ]
    for legacy, new in legacy_to_new:
        if legacy.exists() and not new.exists():
            shutil.move(str(legacy), str(new))
            logger.info(f"Migrated {legacy} -> {new}")
```

### Pattern 6: SSL + SHA-256 + ZIP Traversal (D-21)

**Example:**

```python
# Source: openboard/engine/downloader.py (modified, D-21)
import hashlib
import ssl
from urllib.request import Request, urlopen

from ..exceptions import DownloadError, NetworkError

SSL_CONTEXT = ssl.create_default_context()


def download_file(self, url: str, dest_path: Path,
                  progress_callback=None, expected_sha256: str | None = None) -> bool:
    """Download with explicit SSL context. If expected_sha256 is provided,
    verify after download and DownloadError on mismatch.
    """
    try:
        request = Request(url)
        request.add_header("User-Agent", "OpenBoard Chess GUI")

        sha = hashlib.sha256()
        with urlopen(request, timeout=30, context=SSL_CONTEXT) as response:    # D-21 SSL
            ...
            with open(dest_path, "wb") as f:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    sha.update(chunk)
                    ...

        if expected_sha256 is not None:
            actual = sha.hexdigest()
            if actual != expected_sha256.lower():
                dest_path.unlink(missing_ok=True)
                raise DownloadError(url, f"sha256 mismatch: expected {expected_sha256}, got {actual}")
        else:
            logger.warning(
                f"No SHA-256 provided for {url}; downloaded file integrity NOT verified. "
                f"Stockfish releases do not publish per-asset checksums; HTTPS-only is the v1 baseline."
            )
        return True
    except (URLError, HTTPError) as e:
        raise NetworkError(f"Network failure downloading {url}", str(e)) from e
    except OSError as e:
        raise DownloadError(url, str(e)) from e


def extract_zip(self, zip_path: Path, extract_to: Path) -> bool:
    """Extract with per-member path-traversal validation."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            extract_root = Path(extract_to).resolve()
            for member in zip_file.infolist():
                target = (extract_root / member.filename).resolve()
                # Use os.path.commonpath per CPython docs recommendation
                if os.path.commonpath([str(extract_root), str(target)]) != str(extract_root):
                    raise DownloadError(
                        str(zip_path),
                        f"refusing to extract: {member.filename!r} escapes extract dir",
                    )
            zip_file.extractall(extract_to)
        return True
    except zipfile.BadZipFile as e:
        raise DownloadError(str(zip_path), f"corrupt zip: {e}") from e
```

### Anti-Patterns to Avoid

- **Reading `controller.game.board_state.board` from view layer** (CONCERNS.md anti-pattern #1) — `replay_to_position` (Plan 1) MUST NOT introduce new view-layer reads of model board state. Existing reads in `views.py:45,394,605,615,643,673` are flagged but not all need fixing in Phase 1; the CRITICAL ones to fix are the `_navigate_to_position` block (lines 673-688) which Plan 1 *replaces* via D-06.
- **View calling `board.push(move)` directly** (CONCERNS.md anti-pattern #2) — `replay_to_position` MUST use `BoardState.make_move()` exclusively.
- **Re-introducing transient mutable state on `ChessController` to compensate for missing signal payload** — this is exactly what `_pending_old_board` was; D-03 forbids reviving it under another name. If a downstream consumer needs `old_board`, the answer is to add it to the signal payload (D-02 pattern), not to the controller's `__init__`.
- **Catching `Exception` and converting to `RuntimeError`** in engine paths — D-19 mandates specific types (`EngineTimeoutError`, `EngineProcessError`). Any new `raise RuntimeError(...)` in `engine_adapter.py` is a regression.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-platform user-config/data/state paths | Custom `if platform.system() == "Linux"...` | `platformdirs.user_config_dir(...)` (D-09) | XDG semantics, Windows `LocalAppData` vs `RoamingAppData`, macOS `~/Library/Application Support` are non-trivial; platformdirs handles them. |
| Composable enum bits for move kind | Plain ints with constants | `enum.IntFlag` (D-01) | IntFlag ships `in` semantics, repr, type checking. Re-implementing is bug-prone. |
| Atomic file rename for migration | `os.rename` + manual error handling | `shutil.move` (D-10) | Handles cross-filesystem moves transparently; fewer edge cases. |
| Bitboard attacker queries | Iterating `board.legal_moves` | `chess.Board.attackers(color, sq)` (D-16) | Single C-implemented bitboard op; pinned-attacker correctness is built in. |
| SSL certificate verification | Manual cert bundle loading | `ssl.create_default_context()` (D-21) | Loads system trust store + correct protocol/cipher defaults. |
| ZIP path-traversal protection | Custom regex on filenames | `os.path.commonpath([root, resolved_target]) == root` (D-21) | Resolves symlinks, handles `..`, OS-canonicalised — exactly what CPython docs recommend. |
| SHA-256 hashing | Manually reading file in chunks then hashing | `hashlib.sha256()` updated chunk-by-chunk during the existing download read loop (D-21) | Single-pass, no extra disk read. |
| Forwarding signals between layers | Re-emit via `signal.send` after every model call | The forwarder pattern (D-04, D-05): subscribe-once at `Game` level, forward to all consumers | Subscribers don't have to re-subscribe across `new_game()`; the bug class is closed at the source. |

**Key insight:** Phase 1 is *removing* hand-rolled custom code as much as it is fixing bugs. The `_simple` API removal (D-12), the `legal_moves`-based attacker iteration (D-16), the `_pending_old_board` shared-state pattern (D-03), the `Path.cwd()`-relative file resolution (D-09) are all hand-rolled crutches that v1's library-first stack lets us delete.

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — OpenBoard has no DB, no embedded datastore. python-chess `Board` is in-memory; `chess.engine` is process-based. | None. |
| Live service config | `keyboard_config.json` and `config.json` currently at `cwd` are user-editable runtime config — those move via D-10 one-shot migration. No remote services with embedded `openboard` strings. | D-10 migration handles file relocation; nothing else. |
| OS-registered state | None — no Windows Task Scheduler entries, no launchd plists, no systemd units, no pm2 saved processes. The `openboard` console script is registered by `pip install -e .` / `uv sync` and is name-only (no path is cached anywhere outside the install metadata). | None. |
| Secrets/env vars | New `OPENBOARD_PROFILE_DIR` env var is read by `paths.py` (test-only, not a production setting). No secrets used by Phase 1. | None — env var is opt-in for test isolation. |
| Build artifacts / installed packages | `openboard.egg-info/` and the wxPython Linux index URL in `pyproject.toml` (`extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-24.04/`). The latter is flagged in CONCERNS.md Fragile #4 / Deps at Risk #2 and explicitly **deferred** (out of Phase 1 scope per CONTEXT.md Deferred Ideas). PyInstaller spec at `.build/pyinstaller_spec.py` does not embed any path the Phase 1 changes invalidate. | After Phase 1, run `uv sync` (re-install) only because new `platformdirs` dep was added. No artifact-rename needed. |

**Nothing found that requires data migration:** Phase 1 changes are pure-code; the only "moves files" step is the one-shot D-10 `shutil.move()` of legacy `config.json` / `keyboard_config.json` / `engines/` from `cwd` to platformdirs locations on first launch after deploy.

## Common Pitfalls

### Pitfall 1: `MoveKind.CHECK` computed BEFORE the push

**What goes wrong:** `board.is_check()` returns whether *the current side to move* is in check. If `MoveKind.CHECK` is computed using `old_board.is_check()` (the pre-move board), it reports whether the moving side was in check before they moved (i.e., whether they were in check and got out of it) — the opposite of what `MoveKind.CHECK` should mean.

**Why it happens:** Naïve placement of the `MoveKind` computation inside `BoardState.make_move()` *before* the `push()`, or inside a downstream handler that received only the pre-push state.

**How to avoid:** Compute `MoveKind.CHECK | MoveKind.CHECKMATE` from the *post-push* `board.is_check()` / `board.is_checkmate()` — explicitly noted in CONTEXT.md Specifics. The signal should be emitted from `Game._on_board_move` AFTER `BoardState.make_move()` completes (which is already the case because `BoardState.make_move` calls `self.move_made.send(...)` after `self._board.push(move)` at `board_state.py:70-71`).

**Warning signs:** Tests assert `MoveKind.CHECK in kind` for a non-checking move (false positive), or fail to assert `MoveKind.CHECK in kind` for a checking move (false negative). The TD-02 regression test must include both: a quiet move (CHECK bit OFF) and a checking move (CHECK bit ON).

### Pitfall 2: Missing `_pending_old_board` reference in cleanup sweep

**What goes wrong:** D-03 deletes `_pending_old_board` mutations. Grep finds 9 references in `chess_controller.py` and 5 in tests. If any one is missed, Python raises `AttributeError: 'ChessController' object has no attribute '_pending_old_board'` at runtime — but only on the code path that touches the orphan reference, which may not be the most common path.

**Why it happens:** The references are scattered across multiple methods (`__init__`, `_on_model_move`, `_on_computer_move_ready`, `announce_last_move`, `_do_move`, `_format_move_announcement`).

**How to avoid:** Plan 1's task list MUST include "grep for `_pending_old_board` in `openboard/` and `tests/`; assert zero hits" as a verification step, not just "delete the references in chess_controller.py." The 14 known reference sites (per grep above) are:

- `openboard/controllers/chess_controller.py:64,110,163,168,535,544,556,562,597`
- `tests/test_chess_controller.py:435,445,455,465,475`
- `tests/test_chess_controller_opening_book.py:130-131,150-151`

**Warning signs:** Tests pass on the green path but fail on the announce-last-move or computer-move-ready paths. The test_chess_controller.py and test_chess_controller_opening_book.py tests must be **updated**, not deleted, because they currently *seed* `_pending_old_board` to test downstream behavior. After D-02 lands, those tests instead verify that the enriched payload carries `old_board`.

### Pitfall 3: Migration helper running AFTER settings singleton init

**What goes wrong:** `Settings()` reads `engines_dir` at construction time (`settings.py:44`). If the migration helper runs after `get_settings()` has been called (which happens on import via `views.py:31`!), the settings instance points at the new path but the migration hasn't moved the file yet — so settings effectively starts empty.

**Why it happens:** `openboard/views/views.py:31` has `settings = get_settings()` at module load — i.e., `import openboard.views.views` already initialises the singleton. Any migration must run BEFORE that import, OR `get_settings()` must be made lazy (recommended).

**How to avoid:** Either (a) move the `settings = get_settings()` call inside `main()` and run migration immediately before it, or (b) make `_settings` a lazy property/factory that consults `paths.py` only on first access. Recommendation: **(a)** — minimal change, mirrors the order in `main()` already; just delete the module-level `settings = get_settings()` and inline it.

**Warning signs:** First launch shows default settings even though the legacy `config.json` exists; subsequent launches read the (now-migrated-but-empty) settings file as the user's actual settings.

### Pitfall 4: `wx.MenuItem.GetId()` capture must happen at construction time

**What goes wrong:** Calling `menu.GetMenuItems()[0].GetId()` later returns a different ID than what `Append()` returned, because wx may have re-allocated IDs. The current code at `views.py:257-316` already uses `menu.GetMenuItems()[idx].GetId()` patterns, which are safe ONLY because wx assigns IDs at `Append` time and they don't change.

**Why it happens:** Generally safe in wxPython 4.2.x, but the *spirit* of D-08 is to capture the `wx.MenuItem` object directly so future readers see the binding intent.

**How to avoid:** Use `pgn_item = file_menu.Append(wx.ID_ANY, "...")` then `id=pgn_item.GetId()` — explicit and intent-revealing. The current `menu.GetMenuItems()[idx].GetId()` pattern technically works but should be modernised in the same audit.

**Warning signs:** A new menu item inserted in the middle of an existing menu shifts indices and silently re-binds the wrong handler.

### Pitfall 5: SHA-256 verification cannot use a non-existent checksum file

**What goes wrong:** D-21 specifies "SHA-256 verification: when downloading Stockfish releases, fetch the corresponding `.sha256` (or `.checksums`) file from the same GitHub release." **Verified against the live API at https://api.github.com/repos/official-stockfish/Stockfish/releases/latest: there are NO `.sha256`, `.checksums`, or `SHA256SUMS` files among the release assets.** Only the binaries themselves.

**Why it happens:** The Stockfish project does not currently publish per-asset hashes. This is an upstream policy choice.

**How to avoid:** Implement D-21's WARNING fallback as the **primary** path, not the exception. Plan 4's task list should:
1. Implement `download_file(..., expected_sha256: str | None = None)` accepting optional hash.
2. Implement WARNING-log when `expected_sha256 is None`.
3. Implement mismatch-fail when `expected_sha256` is provided.
4. Document in code that callers currently always pass `None` (because Stockfish doesn't publish hashes), but the param is wired up for future use OR for a hard-coded mapping if the project decides to ship its own checksum table.
5. **Do NOT** spend time fetching a `.sha256` URL pattern — there is none.

**Warning signs:** A planner task that says "fetch the .sha256 file from the GitHub release" — that task is unimplementable as written. Reword to "accept optional sha256 param; warn when unset; verify when set."

### Pitfall 6: `OPENBOARD_PROFILE_DIR` test isolation must propagate to subprocesses

**What goes wrong:** A test sets `OPENBOARD_PROFILE_DIR=/tmp/x`, but a subprocess (e.g., test that spawns Stockfish) does not inherit it cleanly, or another test in the same session leaks the env var.

**Why it happens:** `os.environ` mutations persist across tests in the same pytest run unless explicitly cleaned.

**How to avoid:** Provide a pytest fixture in `conftest.py`:

```python
@pytest.fixture
def isolated_profile(tmp_path, monkeypatch):
    """Redirect all paths.py helpers to tmp_path via OPENBOARD_PROFILE_DIR."""
    monkeypatch.setenv("OPENBOARD_PROFILE_DIR", str(tmp_path))
    return tmp_path
```

`monkeypatch` auto-cleans, so no leaks. All Phase 1 path-touching tests should use this fixture.

**Warning signs:** Tests pass in isolation but fail when run together; the second test sees the first test's stale paths.

## Code Examples

### Verifying TD-01 (move_undone forwarder) regression test

```python
# Source: tests/test_game.py (NEW test for TD-01)
import chess
from openboard.models.game import Game
from openboard.models.game_mode import GameConfig, GameMode

def test_move_undone_signal_reconnects_after_new_game():
    """TD-01 / CONCERNS.md Bug #1: Game.move_undone forwarder must work after new_game().

    Without the D-04 fix, this test FAILS because the controller-equivalent subscriber
    is connected to the original BoardState's move_undone, which is orphaned when
    Game.new_game() rebuilds BoardState.
    """
    game = Game(config=GameConfig(mode=GameMode.HUMAN_VS_HUMAN))
    undo_events: list[chess.Move] = []

    def on_undone(sender, move=None, **kwargs):
        undo_events.append(move)

    # Subscribe to Game.move_undone (the forwarder), NOT board_state.move_undone
    game.move_undone.connect(on_undone, weak=False)

    # First game: undo works
    game.apply_move(chess.E2, chess.E4)
    game.board_state.undo_move()
    assert len(undo_events) == 1, "first-game undo should fire"

    # New game; without D-04 fix, the forwarder is stale (connected to discarded BoardState)
    game.new_game()

    # Second game: undo must STILL work
    game.apply_move(chess.E2, chess.E4)
    game.board_state.undo_move()
    assert len(undo_events) == 2, "post-new_game undo must fire — TD-01 regression"
```

### Verifying TD-02 (move_kind payload)

```python
# Source: tests/test_chess_controller.py (NEW test for TD-02)
def test_move_made_payload_includes_move_kind_for_capture_with_check():
    """TD-02 / D-01 / D-02: composable IntFlag bits on Game.move_made."""
    from openboard.models.move_kind import MoveKind

    game = Game(config=GameConfig(mode=GameMode.HUMAN_VS_HUMAN))
    payloads: list[dict] = []

    def on_move(sender, move=None, old_board=None, move_kind=None, **kwargs):
        payloads.append({"move": move, "old_board": old_board, "move_kind": move_kind})

    game.move_made.connect(on_move, weak=False)

    # Set up: Scholar's Mate setup so a single move delivers a check.
    game.board_state.load_fen("rnbqkbnr/ppp2ppp/8/3pp3/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 0 3")
    payloads.clear()  # discard the load_fen move_made(None) emission
    game.apply_move(chess.D1, chess.H5)  # Qh5+ -- check, not capture

    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["old_board"] is not None
    assert MoveKind.CHECK in payload["move_kind"]
    assert MoveKind.CAPTURE not in payload["move_kind"]
    assert MoveKind.CHECKMATE not in payload["move_kind"]
```

### Verifying TD-04 (attackers with pinned attacker)

```python
# Source: tests/test_chess_controller.py (NEW test for TD-04)
def test_announce_attacking_pieces_includes_pinned_attacker():
    """TD-04 / CONCERNS.md Bug #3: pinned attackers must be reported.

    Position: black queen on d8, white king on e1, black rook on e8 pinning a piece.
    A pinned bishop on e3 still ATTACKS e1 (the king is the pin target, but the bishop
    geometrically attacks e1). The legal_moves-based old impl misses this; the
    attackers()-based new impl catches it.
    """
    game = Game(config=GameConfig(mode=GameMode.HUMAN_VS_HUMAN))
    # Construct a pinned-attacker position
    game.board_state.load_fen("4r3/8/8/8/8/4B3/8/4K3 w - - 0 1")  # white bishop e3 pinned by rook e8
    controller, signals = _make_controller(game)
    signals["announce"].clear()

    controller.current_square = chess.E1   # focus white king's square
    controller.announce_attacking_pieces()

    # Black rook on e8 IS attacking e1; under the old (legal_moves) implementation,
    # if the rook were pinned this would miss it. attackers() catches all attackers
    # regardless of pin. Test the inverse: the white bishop on e3 is pinned by the
    # rook (cannot move legally, but it does attack squares).
    # For this position, rook on e8 attacks e1 -- assert it shows up.
    last_announcement = signals["announce"][-1]
    assert "rook" in last_announcement.lower()
```

### Verifying TD-05 (specific menu IDs)

```python
# Source: tests/test_views_menus.py (NEW for TD-05; requires wxPython display, may need skip)
import pytest
import wx

@pytest.fixture
def wx_app():
    app = wx.App(False)
    yield app
    app.Destroy()

def test_load_pgn_bound_to_specific_id_not_id_any(wx_app, monkeypatch):
    """TD-05 / CONCERNS.md Bug #4: on_load_pgn must NOT fire for unrelated menu events."""
    from openboard.views.views import ChessFrame
    # ... construct controller with mock game ...
    frame = ChessFrame(controller)
    pgn_handler_calls = 0
    def fake_on_load_pgn(event):
        nonlocal pgn_handler_calls
        pgn_handler_calls += 1
    monkeypatch.setattr(frame, "on_load_pgn", fake_on_load_pgn)

    # Synthesize a menu event with a DIFFERENT menu item ID (e.g., the New Game ID)
    new_game_item = frame.GetMenuBar().FindItemByPosition(0).GetSubMenu().GetMenuItems()[0]
    event = wx.CommandEvent(wx.EVT_MENU.typeId, new_game_item.GetId())
    frame.ProcessEvent(event)
    assert pgn_handler_calls == 0, "on_load_pgn must NOT fire for non-PGN menu items"
```

(Note: view-layer testing is identified in CONCERNS.md Test Gaps #1 as broadly missing. TD-05's test may need an alternative: assert that the binding lookup table for `EVT_MENU` does not contain `wx.ID_ANY` as a key, by introspecting `frame.GetEventHandler()`. Planner can choose either approach — a mocked `Bind` patch is also acceptable.)

### Verifying TD-12 (platformdirs migration)

```python
# Source: tests/test_paths.py (NEW for TD-12)
def test_paths_resolve_under_override(tmp_path, monkeypatch):
    """TD-12: OPENBOARD_PROFILE_DIR override must redirect all paths."""
    monkeypatch.setenv("OPENBOARD_PROFILE_DIR", str(tmp_path))
    from openboard.config import paths
    assert paths.user_config_dir() == tmp_path / "config"
    assert paths.user_data_dir() == tmp_path / "data"
    assert paths.user_state_dir() == tmp_path / "state"
    assert paths.engines_dir() == tmp_path / "data" / "engines"
    assert paths.settings_path() == tmp_path / "config" / "settings.json"
    assert paths.keyboard_config_path() == tmp_path / "config" / "keyboard_config.json"
    assert paths.autosave_path() == tmp_path / "state" / "autosave.json"


# Source: tests/test_migration.py (NEW for D-10)
def test_one_shot_migration_moves_legacy_files(tmp_path, monkeypatch):
    """D-10: legacy cwd/config.json migrates to user_config_dir on first launch."""
    monkeypatch.setenv("OPENBOARD_PROFILE_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / "config.json"
    legacy.write_text('{"announce_mode": "verbose"}')

    from openboard.config import paths
    from openboard.config.migration import migrate_legacy_paths
    migrate_legacy_paths()

    assert not legacy.exists()
    new = paths.settings_path()
    assert new.exists()
    assert new.read_text() == '{"announce_mode": "verbose"}'
```

### Verifying D-21 (ZIP path traversal guard)

```python
# Source: tests/test_downloader_security.py (NEW per D-22 / D-25)
import zipfile

def test_extract_zip_rejects_path_traversal(tmp_path):
    """D-21 / Security #2: ZIP with ../ entries must be rejected."""
    from openboard.engine.downloader import StockfishDownloader
    from openboard.exceptions import DownloadError

    # Build a malicious zip with a ../ entry
    bad_zip = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("../../etc/passwd", "compromised")

    downloader = StockfishDownloader(install_dir=tmp_path / "install")
    with pytest.raises(DownloadError, match="escapes extract dir"):
        downloader.extract_zip(bad_zip, tmp_path / "install")

    # Verify the malicious file was NOT written
    assert not (tmp_path.parent.parent / "etc" / "passwd").exists()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Path.cwd() / "engines"` for engine install dir | `platformdirs.user_data_dir("openboard") / "engines"` | Phase 1 (D-09) | Engines no longer install relative to where the app was launched. |
| `_pending_old_board` shared instance variable on controller for capture detection | `Game.move_made(old_board=...)` enriched signal payload | Phase 1 (D-02 / D-03) | Eliminates a fragile shared-state pattern; signal carries everything subscribers need. |
| Sync `Game.request_computer_move()` with sync test fixtures | Async-only `Game.request_computer_move_async()` with synchronous mock-callback test pattern | Phase 1 (D-13) | Tests reflect production code paths; no sync-vs-async drift. |
| `urllib.request.urlopen(url)` (default ctx) | `urlopen(url, context=ssl.create_default_context())` | Phase 1 (D-21) | Explicit certificate verification; no reliance on platform-default SSL behavior. |
| `zip_file.extractall(extract_to)` (default) | per-member `Path(extract_to / name).resolve()` validation, then `extractall` | Phase 1 (D-21) | ZIP path-traversal blocked; matches CPython docs recommendation. |
| `chess.Board.legal_moves` filtered by `from_square` and `to_square` for "what attacks" | `chess.Board.attackers(WHITE, sq) | chess.Board.attackers(BLACK, sq)` | Phase 1 (D-16) | O(1) bitboard op vs O(64 × legal_moves); pinned attackers reported correctly. |

**Deprecated/outdated (within this codebase):**

- `EngineAdapter.start_simple` / `stop_simple` / `get_best_move_simple*` / `_start_engine_simple`: dead code; D-12 deletes.
- `Game.request_computer_move` (sync): only test-callers; D-13 deletes.
- `Game.player_color` attribute: zero non-test consumers; D-15 deletes.
- `AccessibilityError`, `DialogError`, `SettingsError`, `GameStateError`, `UIError`: defined but never raised; D-19 prunes.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Plan 1's task list can be ordered such that the `BoardState.move_made` payload extension (carrying `old_board`) lands BEFORE `Game._on_board_move` reads it. | Pattern 2 design note | Low — both modules are in the same plan; sequencing is intra-plan. If extension lands second, tests fail loudly. |
| A2 | The `OPENBOARD_PROFILE_DIR` env override is acceptable to the user as a non-feature, test-only mechanism. | Pattern 5, Pitfall 6 | Low — CONTEXT.md "Claude's Discretion" explicitly invites it; recommendation is to implement now. |
| A3 | The `tests/CONCERNS_TRACEABILITY.md` deliverable is acceptable as the Plan 5 traceability artifact (vs. inline docstring tags only). | Standard Stack > Test discipline; Plan 5 deliverables | Low — D-24 already mandates inline tags; this file is additive documentation. The planner can decide to skip the file if inline tags suffice. |
| A4 | View-layer regression tests for TD-05 (specific menu IDs) can use a wxPython app fixture without requiring a display server in CI (i.e., `XVFB` or equivalent is configured, or the test is skipped on headless). | Code Examples > TD-05 | Medium — CI is already running `pytest` on Linux/Win/macOS without explicit headless display setup, suggesting either no view tests run or `accessible-output3` brings its own fallback. Plan 3 should verify this and either add `XVFB` to CI or implement TD-05 verification via a non-display-requiring approach (e.g., introspecting the wx event handler table without instantiating `ChessFrame`). |
| A5 | The CONCERNS.md TD-04 fix snippet is taken at face value: `chess.Board.attackers()` returns the desired set of squares for "what attacks this square?", regardless of pin. | Pattern in TD-04 / D-16 | Low — verified against python-chess Context7 docs; `attackers()` returns the bitboard of pseudo-attackers (correct behavior for the announcement). |
| A6 | Adding `platformdirs>=4.3.8` will resolve cleanly via `uv sync` on Win/macOS/Linux without conflicting with wxPython's existing platform-specific install index. | Standard Stack > Installation | Low — `platformdirs` is a pure-Python single-purpose lib with no system deps; verified locally at v4.9.4. |

**If this table is empty:** All claims would be VERIFIED or CITED. The above 6 assumptions remain; A4 is the only one with material uncertainty (test execution in CI). Planner should investigate A4 during Plan 3 task design.

## Open Questions (RESOLVED)

1. **How does CI currently handle wxPython tests?**
   - What we know: CI runs `pytest -v --tb=short` on a 3-OS matrix; Stockfish is installed; wxPython is installed via the locked Linux index. No explicit `Xvfb` or display setup is mentioned in `.planning/codebase/TESTING.md`.
   - What's unclear: Whether any current test imports `wx` and successfully constructs a `wx.App` in CI. The test file `tests/test_views_menus.py` is NEW for TD-05 — no precedent.
   - Recommendation: Plan 3 task A0 — investigate `.github/workflows/setup-test.yml` and any conftest that might set `WX_DISPLAY` or skip view tests. If view tests are not currently run in CI, TD-05 verification should NOT require them — use an introspection-based test on the `Bind()` calls (e.g., monkeypatch `wx.EvtHandler.Bind` to record calls; assert no call was made with `id=wx.ID_ANY` for `EVT_MENU`).

2. **Should `BoardState.move_made` payload be extended (option a) or should `Game` capture `old_board` transiently (option b/c)?**
   - What we know: D-02 mandates `Game.move_made` payload `(move, old_board, move_kind)`. CONTEXT.md does NOT explicitly state where `old_board` originates.
   - What's unclear: Whether the cleanest implementation extends `BoardState.move_made` to ALSO carry `old_board` (option a — pushes complexity into BoardState), or `Game.apply_move` captures the snapshot before delegating to `make_move` (option b — Game holds a transient).
   - Recommendation: **Option (a)** — extend `BoardState.move_made` payload to `(move, old_board)`. Matches the principle "signal carries everything the subscriber needs." Backward-compatible due to blinker's silent kwarg tolerance. Single source of truth. Plan 1 should adopt this.

3. **Test-first discipline (D-23) for the `_pending_old_board` removal — what does "test fails on unfixed code" mean for a deletion?**
   - What we know: D-23 mandates the regression test FAILS without the fix. For a behavioral fix this is well-defined; for the *deletion* of `_pending_old_board` it's less obvious — there's no behavior to assert is broken.
   - What's unclear: Whether to (a) add a test that asserts no `AttributeError` is raised on a code path that previously read `_pending_old_board`, (b) add a grep-style assertion via `inspect.getsource(ChessController).count("_pending_old_board") == 0`, (c) treat removal as "covered by the TD-02 enriched-payload tests" and skip a dedicated removal test.
   - Recommendation: **(b)** — a meta-test in `test_chess_controller.py`: `assert "_pending_old_board" not in inspect.getsource(ChessController), "TD-03 / D-03: shared mutable state must not be reintroduced"`. This is a regression guard that fires in code review even if a future commit re-adds the variable.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | Entire phase | ✓ | 3.12+ enforced by `pyproject.toml: requires-python = ">=3.12"` | None — hard requirement. |
| python-chess | TD-02, TD-04, TD-16 | ✓ | ≥1.11.2 (current locked) | None — core dependency. |
| blinker | TD-01, TD-02 | ✓ | ≥1.9.0 (current locked) | None — core dependency. |
| wxPython | TD-05, TD-09 | ✓ | ≥4.2.4 (current locked) | None — core dependency. |
| platformdirs | TD-12 (D-09) | NEW addition | ≥4.3.8 (publish: 4.9.4) | None for production. For tests, `OPENBOARD_PROFILE_DIR` env override removes the runtime dependency in test paths. |
| Stockfish binary | Any test that exercises engine paths | ✓ in CI | Latest (CI installs latest) | Mock engine pattern (`MockEngine` in `tests/test_engine_adapter_integration.py`). |
| `pytest` | Test discipline (D-23/D-24) | ✓ | ≥9.0.1 dev dep | None — required. |
| `ty` | Type-check | ✓ | ≥0.0.11 dev dep | None — required (CI gate). |
| `ruff` | Format/lint | ✓ | ≥0.14.6 dev dep | None — required (CI gate). |
| `Xvfb` or display server (for view-layer tests) | TD-05 (TD-09 is dispatch path only, not display) | ✗ unverified | n/a | Use introspection-based test (monkeypatch `Bind`, assert no `wx.ID_ANY` arg). |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** Display server for wxPython view tests — fallback to introspection-based binding assertions (Open Question 1).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.1+ + pytest-cov 7.0.0+ + pytest-asyncio 1.3.0+ |
| Config file | `pyproject.toml` (no `[tool.pytest.ini_options]` block — uses defaults; tests live in `tests/` per pytest auto-discovery) |
| Quick run command | `uv run python -m pytest tests/ -v --tb=short -x` |
| Full suite command | `uv run python -m pytest -v --tb=short` (CI default) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TD-01 | `Game.move_undone` fires after `new_game()` | unit | `uv run python -m pytest tests/test_game.py::test_move_undone_signal_reconnects_after_new_game -x` | ❌ Wave 0 (test is NEW; file exists) |
| TD-02 | `Game.move_made` payload carries `old_board` and `move_kind` IntFlag bits | unit | `uv run python -m pytest tests/test_chess_controller.py -k "move_made_payload or move_kind" -x` | ❌ Wave 0 (tests are NEW) |
| TD-03 | `ChessController.replay_to_position(idx)` exists and uses `make_move/undo_move` exclusively | unit | `uv run python -m pytest tests/test_chess_controller.py::test_replay_to_position_uses_make_move -x` | ❌ Wave 0 |
| TD-03 | No `_pending_old_board` references anywhere | meta-unit | `uv run python -m pytest tests/test_chess_controller.py::test_pending_old_board_removed -x` | ❌ Wave 0 |
| TD-04 | `announce_attacking_pieces` reports pinned attackers | unit | `uv run python -m pytest tests/test_chess_controller.py::test_announce_attacking_pieces_includes_pinned_attacker -x` | ❌ Wave 0 |
| TD-05 | No `EVT_MENU` binding uses `wx.ID_ANY` | unit (introspection) | `uv run python -m pytest tests/test_views_menus.py -x` | ❌ Wave 0 (NEW file) |
| TD-06 | `EngineAdapter` has no `_simple` API methods | unit | `uv run python -m pytest tests/test_engine_adapter.py::test_simple_api_removed -x` | ❌ Wave 0 |
| TD-07 | `Game._resolve_move_context()` exists and returns the difficulty/fen tuple | unit | `uv run python -m pytest tests/test_game_async.py::test_resolve_move_context_extracted -x` | ❌ Wave 0 |
| TD-08 | Sync `request_computer_move` is removed; tests use async path | unit | `uv run python -m pytest tests/test_game_async.py -x` (also: `not hasattr(Game, 'request_computer_move')`) | ⚠ Partial — `test_game_async.py` exists; sync-test migration is NEW work |
| TD-09 | `EVT_CHAR_HOOK` `B` still dispatches to `request_book_hint` AND menu has no `\tB` | unit | `uv run python -m pytest tests/test_views_menus.py::test_book_hint_no_accelerator -x` | ❌ Wave 0 |
| TD-10 | `Game.player_color` attribute does not exist | unit | `uv run python -m pytest tests/test_game.py::test_player_color_removed -x` | ❌ Wave 0 (also: update `test_game_mode.py:199`) |
| TD-11 | Pruned types unimportable; `EngineTimeoutError`/`DownloadError`/etc raised at expected sites | unit | `uv run python -m pytest tests/test_exceptions.py tests/test_engine_adapter.py tests/test_downloader.py -x` | ⚠ Partial — `test_exceptions.py` exists; `test_downloader.py` is NEW |
| TD-12 | `paths.py` helpers respect `OPENBOARD_PROFILE_DIR`; one-shot migration moves legacy files | unit | `uv run python -m pytest tests/test_paths.py tests/test_migration.py -x` | ❌ Wave 0 (NEW files) |
| TD-13 | `BoardState.board_ref` property exists and returns `_board` | unit | `uv run python -m pytest tests/test_board_state_terminal.py::test_board_ref_returns_live_reference -x` | ❌ Wave 0 |
| TD-14 | Every TD-* fix has a regression test | meta-doc | `tests/CONCERNS_TRACEABILITY.md` exists and lists all 14 | ❌ Wave 0 (Plan 5 deliverable) |
| D-21 | `download_file` uses explicit SSL context | unit | `uv run python -m pytest tests/test_downloader_security.py::test_download_uses_ssl_context -x` | ❌ Wave 0 (NEW file) |
| D-21 | `download_file` raises `DownloadError` on SHA-256 mismatch when sha provided | unit | `uv run python -m pytest tests/test_downloader_security.py::test_download_sha256_mismatch_raises -x` | ❌ Wave 0 |
| D-21 | `extract_zip` rejects `..` path traversal | unit | `uv run python -m pytest tests/test_downloader_security.py::test_extract_zip_rejects_path_traversal -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run python -m pytest tests/test_<touched_module>.py -x` (≤10 s)
- **Per wave merge:** `uv run python -m pytest -v --tb=short` (full suite; ~30-60 s; current runtime baseline)
- **Phase gate:** Full suite green AND `uv run ruff check .` AND `uv run python -m ty check` before `/gsd-verify-work`

### Wave 0 Gaps

The following test files / fixtures need to be created **before** the implementing tasks land (per D-23 test-first discipline):

- [ ] `tests/test_paths.py` — covers TD-12 (paths helpers + override)
- [ ] `tests/test_migration.py` — covers D-10 (one-shot migration helper)
- [ ] `tests/test_views_menus.py` — covers TD-05, TD-09 (menu binding hygiene; introspection-based per Open Q1)
- [ ] `tests/test_downloader.py` — covers D-19 (`DownloadError`/`NetworkError` raise paths in non-security cases)
- [ ] `tests/test_downloader_security.py` — covers D-22 (SSL context, SHA-256, ZIP traversal — REQUIRED by D-25 to be a NEW file)
- [ ] `tests/conftest.py` — add `isolated_profile` fixture (Pitfall 6) for `OPENBOARD_PROFILE_DIR` test isolation
- [ ] `tests/CONCERNS_TRACEABILITY.md` — Plan 5 deliverable; not a test file but the audit artifact
- [ ] `pyproject.toml` — add `platformdirs>=4.3.8` to `[project.dependencies]`; framework already installed for tests

**Existing test files extended** (not new):
- `tests/test_game.py` (TD-01, TD-08, TD-10)
- `tests/test_chess_controller.py` (TD-02, TD-03, TD-04)
- `tests/test_chess_controller_opening_book.py` (update for `_pending_old_board` removal — D-03)
- `tests/test_board_state_terminal.py` (TD-18 board_ref test)
- `tests/test_engine_adapter.py` (TD-06 `_simple` removal; TD-19 `EngineTimeoutError`/`EngineProcessError`)
- `tests/test_game_async.py` (TD-07 helper extracted; TD-08 migrated tests)
- `tests/test_settings.py` (TD-12 engines_dir resolved via paths)
- `tests/test_exceptions.py` (TD-11 prune updates)
- `tests/test_game_mode.py` (TD-10: line 199 `player_color` reference must change)
- `tests/test_game_opening_book_integration.py` (TD-08 sync-test migration: 4 callers)
- `tests/test_chess_controller_opening_book.py` (TD-08: line 93 sync caller)

### Validation Dimensions

The minimum set of validation dimensions for Phase 1, with concrete invariants per dimension and the test files that own each:

| Dimension | Invariant | Owning Test File |
|-----------|-----------|------------------|
| **Signal correctness** | Every `_on_<event>` handler stays connected across `Game.new_game()`. Specifically: `Game.move_undone` fires for second-and-later games. | `tests/test_game.py` (TD-01) |
| **Signal correctness** | `Game.move_made` payload includes `move`, `old_board`, `move_kind`. Subscribers reading only `move` continue to work (blinker tolerates extra kwargs). | `tests/test_chess_controller.py` (TD-02) |
| **Signal correctness** | `MoveKind.CHECK` is computed from POST-push `board.is_check()`, not pre-push. | `tests/test_chess_controller.py` (TD-02 with checking-move fixture) |
| **Model-routing correctness** | `ChessController.replay_to_position()` calls `BoardState.make_move/undo_move` exclusively; no `board.push` anywhere except `BoardState.make_move`'s implementation and `BoardState.load_pgn`. | `tests/test_chess_controller.py` (TD-03) |
| **Model-routing correctness** | View layer (`views.py`) contains zero `board.push(` and zero `board_state.move_made.send(` outside the deleted `_navigate_to_position`. | grep-based meta-test in `tests/test_views_menus.py` |
| **Persistence-path correctness** | All `paths.py` helpers honor `OPENBOARD_PROFILE_DIR` env override. | `tests/test_paths.py` (TD-12) |
| **Persistence-path correctness** | One-shot migration is idempotent (running twice does not duplicate-move; running with no legacy files is silent). | `tests/test_migration.py` (D-10) |
| **Persistence-path correctness** | `EngineSettings.engines_dir` resolves via `paths.engines_dir()`, not `Path.cwd()`. | `tests/test_settings.py` (TD-12) |
| **Security correctness** | `urlopen` calls in `downloader.py` pass `context=ssl.create_default_context()` (assert via mock or by inspecting source). | `tests/test_downloader_security.py` (D-21) |
| **Security correctness** | `extract_zip` raises `DownloadError` for any member whose resolved path escapes `extract_to`. | `tests/test_downloader_security.py` (D-21) |
| **Security correctness** | `download_file(..., expected_sha256=...)` raises `DownloadError` on mismatch and logs WARNING when None. | `tests/test_downloader_security.py` (D-21) |
| **Exception-wiring correctness** | `EngineTimeoutError` raised on engine timeout (replaces bare `RuntimeError`); `EngineProcessError` raised on engine startup failure. | `tests/test_engine_adapter.py` (D-19) |
| **Exception-wiring correctness** | `DownloadError` raised on download failure; `NetworkError` raised on network bubble-up. | `tests/test_downloader.py` and/or `tests/test_stockfish_manager.py` (D-19) |
| **Exception-pruning correctness** | Importing pruned types fails: `from openboard.exceptions import AccessibilityError` raises `ImportError`. | `tests/test_exceptions.py` (D-19) |
| **Regression-test coverage** | Every TD-N has at least one test docstring containing the literal `TD-N` token; `tests/CONCERNS_TRACEABILITY.md` lists each TD-N → test file → test name. | Plan 5 audit; `tests/CONCERNS_TRACEABILITY.md` (D-26 Plan 5) |

### Edge-Case Fixtures Needed

- **Pinned-attacker FEN** (TD-04): `"4r3/8/8/8/8/4B3/8/4K3 w - - 0 1"` — black rook on e8 attacks white king on e1 with white bishop pinned on e3. Add to `conftest.py` as `pinned_attacker_fen`.
- **Capture-with-check FEN** (TD-02 MoveKind tests): `"rnbqkbnr/ppp2ppp/8/3pp3/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 0 3"` — Qd1-h5+ delivers check without capture. Add to `conftest.py` as `pre_scholars_mate_fen`.
- **Promotion FEN** (existing `test_pawn_promotion_default_queen` uses): `"8/7P/8/8/8/8/8/8 w - - 0 1"` — already in test_game.py.
- **Malformed PGN** (not Phase 1 scope, but `replay_to_position` resilience): defer to Phase 2a.
- **Tampered ZIP** (D-21 / D-22): build in test fixture via `zipfile.ZipFile(tmp_path/"bad.zip", "w") as zf: zf.writestr("../../etc/passwd", "...")`. No external file needed.
- **Wrong-checksum payload** (D-21): use `tmp_path` to write a known-content file and pass an obviously-wrong sha256 hex string. No HTTP server needed (mock the `urlopen` response).
- **SSL inspection fixture** (D-21): patch `urllib.request.urlopen` with `unittest.mock.patch` and assert the call kwargs contain `context=` whose `verify_mode == ssl.CERT_REQUIRED`.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 1 has no auth surface (no user accounts, no auth flows). |
| V3 Session Management | no | Desktop app, no sessions. |
| V4 Access Control | no | Single-user desktop app; no privilege model. |
| V5 Input Validation | yes | python-chess `Board.is_valid()` and `Board.status()` already validate FEN and move legality. PGN parsing relies on python-chess's parser which is hardened against malformed input. |
| V6 Cryptography | yes | SHA-256 hashing of downloaded archives (D-21) — uses stdlib `hashlib`, never hand-rolled. |
| V8 Data Protection | partial | No PII collected; user game files stored under `platformdirs.user_state_dir` (D-09). No encryption at rest required for v1. |
| V9 Communications Security | yes | `ssl.create_default_context()` for all HTTPS downloads (D-21). |
| V12 File and Resource | yes | ZIP path-traversal validation (D-21); ensures extracted files cannot escape the install directory. |
| V14 Configuration | yes | `pyproject.toml` dependency pinning; `uv.lock` committed. wxPython Linux index URL is single-host (flagged as Fragile #4 / Deps at Risk #2 — explicitly deferred). |

### Known Threat Patterns for {wxPython desktop, urllib downloader, ZIP extractor, chess engine}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| **MITM on Stockfish download** | Tampering, Information Disclosure | `ssl.create_default_context()` enforces certificate verification (D-21). |
| **Tampered Stockfish binary at rest in transit** | Tampering | SHA-256 verification when checksum is known (D-21); WARNING fallback when unknown (the actual case for Stockfish releases). |
| **ZIP slip / path traversal in Stockfish archive** | Tampering, Elevation of Privilege | `Path.resolve()` + `os.path.commonpath()` per CPython docs (D-21). Test in `test_downloader_security.py`. |
| **Zip bomb (extreme decompression ratio)** | Denial of Service | Out of Phase 1 scope; CONCERNS.md mentions `ZipInfo.file_size` bounds checking as a future hardening — defer to v1.x. |
| **Engine subprocess sandbox escape** | Elevation of Privilege | Out of scope for v1 — Stockfish is trusted (signed by official-stockfish org); user installs explicitly via menu. |
| **Settings file injection (malicious JSON)** | Tampering | pydantic dataclasses (existing) provide schema validation. Phase 2b expands; Phase 1 only relocates the file via D-09. |
| **`config.json` from cwd loaded as user config** | Tampering, Spoofing | D-09 / D-11 eliminate by routing through `paths.settings_path()` under `user_config_dir`. |
| **Test pollution via shared `_settings` singleton** | (testing concern, not security) | `OPENBOARD_PROFILE_DIR` + `monkeypatch` fixture (Pitfall 6). |

## Sources

### Primary (HIGH confidence)
- `/niklasf/python-chess` (Context7, v1.11.2) — `Board.attackers(color, sq) → SquareSet`, `Board.is_check`, `Board.is_checkmate`, `Board.is_capture(move)`, `Board.is_castling(move)`, `Board.is_en_passant(move)`, `Move.promotion`. Verified live via Context7 query.
- python-chess docs — https://python-chess.readthedocs.io/en/latest/core.html (cross-checked Context7 against official site)
- platformdirs API docs — https://platformdirs.readthedocs.io/en/latest/api.html (verified function signatures, Win/macOS/Linux behavior, `_path()` companions)
- Stockfish releases manifest — https://api.github.com/repos/official-stockfish/Stockfish/releases/latest (verified: NO checksum files published — D-21 WARNING fallback is the primary path)
- Python 3.12 docs `enum.IntFlag` — https://docs.python.org/3/library/enum.html#enum.IntFlag
- Python 3.12 docs `zipfile` — https://docs.python.org/3/library/zipfile.html (canonical path-traversal validation: `os.path.commonpath()`)
- Python 3.12 docs `ssl.create_default_context` — https://docs.python.org/3/library/ssl.html#ssl.create_default_context
- `pip show platformdirs` (local) → version 4.9.4 published; ≥4.3.8 floor recommended
- `.planning/codebase/CONCERNS.md` (HIGH — source of truth for every TD-* with line numbers)
- `.planning/codebase/ARCHITECTURE.md`, `CONVENTIONS.md`, `TESTING.md`, `STRUCTURE.md` — direct repo facts
- Direct source reads: `openboard/models/game.py`, `openboard/models/board_state.py`, `openboard/controllers/chess_controller.py`, `openboard/views/views.py`, `openboard/engine/engine_adapter.py`, `openboard/engine/downloader.py`, `openboard/exceptions.py`, `openboard/config/settings.py`, `tests/conftest.py`, `tests/test_chess_controller.py`, `tests/test_game.py`, `tests/test_game_async.py`, `tests/test_exceptions.py`, `tests/test_stockfish_manager.py`, `pyproject.toml`, `config/keyboard_config.json`

### Secondary (MEDIUM confidence)
- `.planning/research/SUMMARY.md` — synthesis rationale and Phase 1 scope boundaries
- `.planning/research/STACK.md` (referenced from SUMMARY.md) — `platformdirs` choice
- `.planning/research/PITFALLS.md` (referenced) — Pitfall 4 (autosave-in-cwd) supports D-09 / D-10

### Tertiary (LOW confidence — flagged for validation)
- A4 (Open Question 1): whether view-layer tests run in CI without `Xvfb` — needs Plan 3 task to inspect `.github/workflows/setup-test.yml`. The current `tests/CLAUDE.md` and TESTING.md mention 0% view coverage, suggesting view tests are either skipped or absent. **Plan 3 must verify before committing to a wx-display-requiring TD-05 test.**

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified against Context7 and official docs; locked decisions from CONTEXT.md align with available APIs.
- Architecture: HIGH — patterns are extensions of existing patterns documented in `.planning/codebase/ARCHITECTURE.md`; no novel architectural choices.
- Pitfalls: HIGH — the 6 pitfalls listed are concrete, verifiable, and grounded in either source-code reading (Pitfalls 1-4, 6) or live API verification (Pitfall 5: Stockfish manifest).
- Validation Architecture: HIGH — every TD-* has an identified test command, owning file, and Wave 0 status; the 5 dimensions cover the full phase scope.
- Security domain: HIGH for the 3 hardenings; MEDIUM for the SHA-256 case because the upstream-publishing reality contradicts CONTEXT.md D-21's framing (planner must be aware that "WARNING fallback" is the *normal* case).

**Research date:** 2026-04-27
**Valid until:** 2026-05-27 (30 days; stack is mature, low-volatility)

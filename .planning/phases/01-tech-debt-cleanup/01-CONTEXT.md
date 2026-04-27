# Phase 1: Tech Debt Cleanup - Context

**Gathered:** 2026-04-27 (auto mode)
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 is a Tier-0 structural prerequisite. It fixes every documented bug and tech-debt item in `.planning/codebase/CONCERNS.md` that v1 commits to (TD-01..TD-14 in `REQUIREMENTS.md`) **and** establishes the canonical patterns — `Game` signal forwarders, model-routed navigation, `move_made(old_board, MoveKind)` payload, `platformdirs`-resolved persistence paths, specific menu IDs — that every later phase (Tiers 1–3) inherits.

Phase 1 does NOT ship new user-visible capabilities. It ships **correctness, cleaner surfaces, and reusable patterns** so the next seven phases can build on a stable substrate. New capabilities (clocks, sound, theme, save/load, etc.) belong in their own phases.

</domain>

<decisions>
## Implementation Decisions

### MoveKind payload shape (TD-02)

- **D-01:** `MoveKind` is an `enum.IntFlag` so multiple bits can compose on a single move. Members: `QUIET = 0`, `CAPTURE = 1 << 0`, `CASTLE = 1 << 1`, `EN_PASSANT = 1 << 2`, `PROMOTION = 1 << 3`, `CHECK = 1 << 4`, `CHECKMATE = 1 << 5`. A capture-with-check yields `MoveKind.CAPTURE | MoveKind.CHECK`. Downstream `SoundService` (Phase 4a) does `if MoveKind.CAPTURE in kind` and `if MoveKind.CHECK in kind` independently — no need for a separate `is_check: bool`.
- **D-02:** `Game.move_made` signal payload extends to `(sender, *, move: chess.Move, old_board: chess.Board, move_kind: MoveKind, ...)`. `BoardState.move_made` keeps its existing payload (low-level signal); `Game._on_board_move` forwards with the enriched payload. Existing subscribers that ignore the new kwargs continue to work — `blinker` accepts extra kwargs silently.
- **D-03:** `_pending_old_board` shared mutable state on `ChessController` (CONCERNS.md "Fragile Areas" entry) is eliminated entirely as a side effect of D-02. `_format_move_announcement()` accepts `old_board` as a parameter; controller methods that previously set/read `_pending_old_board` are refactored to thread it explicitly. Performance #1 (O(n) board replay fallback in `_format_move_announcement`) is also eliminated — there is no more fallback path because the signal always carries `old_board`.

### Signal-rehook pattern (TD-01)

- **D-04:** `Game.move_undone` is added as a forwarded signal on `Game` (mirror of how `Game.move_made` is forwarded from `BoardState.move_made`). `Game.new_game()` reconnects `_on_board_undo` on the freshly constructed `BoardState` so subscribers (e.g., `ChessController`) bind once to `Game.move_undone` and never need to re-subscribe across `new_game()` calls.
- **D-05:** This forwarder pattern is **the canonical pattern for ALL future model→controller signals** in v1 (`Clock` signals in Phase 3a follow it: subscribers bind to `Game.clock_tick`, never `game.clock.tick`). New signals introduced in later phases MUST forward through `Game`.

### Model-routed navigation (TD-03)

- **D-06:** `_navigate_to_position` (currently in `openboard/views/views.py:673`) moves to a new `ChessController.replay_to_position(index: int)` method that uses `BoardState.make_move()` / `BoardState.undo_move()` exclusively. The view calls the controller method; the controller is the only mover of pieces. No `board.push(move)` and no manual `board_state.move_made.send(...)` from the view layer.
- **D-07:** This establishes the precedent: **all moves go through the model layer.** PGN load (Phase 2a) and FEN load (Phase 2a) inherit this — they construct `chess.Move` objects and call `BoardState.make_move()`, never `board.push()` directly.

### Menu binding hygiene (TD-05)

- **D-08:** Every menu item is bound to its specific `wx.MenuItem.GetId()`, never `wx.ID_ANY`. Pattern (from CONCERNS.md fix snippet):
  ```python
  pgn_item = file_menu.Append(wx.ID_ANY, "Load &PGN...\tCtrl-G")
  self.Bind(wx.EVT_MENU, self.on_load_pgn, id=pgn_item.GetId())
  ```
  All existing menu bindings in `openboard/views/views.py` are audited and converted in this phase. Future menu items (Save PGN, Save FEN, Clock controls, Theme toggle, Settings, Key Rebinding) inherit this pattern.

### `platformdirs` migration (TD-12)

- **D-09:** Add `platformdirs` to `[project.dependencies]` in `pyproject.toml`. New helper `openboard/config/paths.py` exposes:
  - `user_config_dir() -> Path` — wraps `platformdirs.user_config_dir("openboard")`
  - `user_data_dir() -> Path` — wraps `platformdirs.user_data_dir("openboard")`
  - `user_state_dir() -> Path` — wraps `platformdirs.user_state_dir("openboard")`
  - `engines_dir() -> Path` — `user_data_dir() / "engines"`
  - `settings_path() -> Path`, `keyboard_config_path() -> Path`, `autosave_path() -> Path` — concrete file paths used by Phase 2b (Settings) and Phase 4b (Autosave).
- **D-10:** **Migration policy: silent one-shot migration with INFO log on first launch.** On startup, if any of the legacy paths (`Path.cwd() / "engines"`, `Path.cwd() / "config.json"`, `Path.cwd() / "keyboard_config.json"`) exists AND the new path does not, move the file to the new location and log `INFO: Migrated <legacy> → <new>`. Subsequent launches find the new path and skip migration. No interactive prompt; no forever-fallback. The user (project author) currently has files at cwd; one-shot migration is the lowest-friction path.
- **D-11:** `openboard/config/settings.py` (`engines_dir` initialiser at line 44, `open("config.json")` at view layer line 750), `openboard/engine/downloader.py:40` all switch to the new helpers. Tests use `tmp_path` fixture and a monkeypatch of the helpers (or a `OPENBOARD_PROFILE_DIR` env override that the helpers honor when set — recommended for testability).

### EngineAdapter cleanup (TD-06, TD-07, TD-08, TD-10)

- **D-12:** `_simple` API surface in `EngineAdapter` (lines 799-881) is **hard-deleted**. No deprecation shim. These are internal aliases never exposed as a public stable API; no external consumers; CI grep confirms no callers outside `engine_adapter.py` itself.
- **D-13:** Synchronous `Game.request_computer_move()` is **removed entirely**. Tests using it migrate to the async path with synchronous mock callbacks (the existing `test_game_async.py` pattern — mock engine invokes the callback inline, so the test is still synchronous from pytest's perspective even though the production code path is async). No `_test_only` suffix; no `@deprecated`.
- **D-14:** Duplicate difficulty-resolution logic between `Game.request_computer_move` (removed in D-13) and `Game.request_computer_move_async` is consolidated. After D-13, only `request_computer_move_async` remains; the helper extraction (`_resolve_move_context()`) becomes optional. **Decision:** still extract `_resolve_move_context()` so the async path's preamble is independently testable and so future "request engine analysis" code paths (Phase v2 ANL-*) can reuse it without copy-paste.
- **D-15:** `Game.player_color` backward-compatibility attribute is removed entirely.

### Bug fixes (TD-04, TD-09)

- **D-16:** `announce_attacking_pieces` is rewritten to use `chess.Board.attackers(chess.WHITE, square) | chess.Board.attackers(chess.BLACK, square)` — single bitboard call. Removes the O(64 × legal_moves) iteration AND fixes the pinned-attacker bug in one change (Performance #2 and Bug #3 from CONCERNS.md are the same fix).
- **D-17:** `&Book Hint\tB` accelerator on the Opening Book menu is removed; `B` continues to work via `EVT_CHAR_HOOK` → `KeyboardCommandHandler` → `KeyAction.REQUEST_BOOK_HINT`. Single dispatch path; no double-fire risk; clean substrate for the in-app rebinding dialog (Phase 3c).

### Read-only board access (Performance #3 under TD-13)

- **D-18:** `BoardState` adds a `board_ref` property returning `self._board` (live reference, contract: read-only — caller must not mutate). `BoardState.board` retains its current `self._board.copy()` semantics for callers that need a stable snapshot. Existing call sites are audited:
  - View `on_paint` and navigation handlers iterating all 64 squares → switch to `board_ref` (read-only).
  - Controller methods that take a snapshot for announcement formatting → keep `.board` (snapshot needed because announcement may run after a subsequent move).
  - All other call sites are inspected case-by-case during planning.
- The contract is documented in `BoardState.board_ref`'s docstring and tested with one `mypy`/`ty`-friendly assertion that mutating through `board_ref` is detectable in CI (e.g., a sentinel test that `BoardState.board_ref is BoardState._board` after construction).

### Exception hierarchy cleanup (TD-11)

- **D-19:** Wire up the obviously-belonging types where they fit; prune the rest.
  - **Wire up:** `EngineTimeoutError` (raise from `EngineAdapter` on `chess.engine.EngineTerminatedError` / asyncio timeout in `get_best_move_async`); `EngineProcessError` (raise from `EngineAdapter` on engine startup failures currently caught as bare `RuntimeError`); `DownloadError` (raise from `Downloader.download_file` on HTTP / IO failures); `NetworkError` (raise from `StockfishManager` on download failures bubbled up).
  - **Prune:** `AccessibilityError`, `DialogError`, `SettingsError`, `GameStateError`, `UIError` — no clear wire-up site; remove from `openboard/exceptions.py` and from `test_exceptions.py`.
- **D-20:** Tests in `test_exceptions.py` are updated for the kept set. New tests in `test_engine_adapter.py` and `test_downloader.py` (or `test_stockfish_manager.py`) verify the new raises.

### Security hardening (Security #1, #2, #3 under TD-13)

- **D-21:** `Downloader.download_file` (`openboard/engine/downloader.py`) gains:
  - **Explicit SSL context**: every `urllib.request.urlopen(...)` call passes `context=ssl.create_default_context()`. Applies to lines 62, 127, 244 per CONCERNS.md.
  - **SHA-256 verification**: when downloading Stockfish releases, fetch the corresponding `.sha256` (or `.checksums`) file from the same GitHub release, verify the downloaded archive's hash before extracting, and fail with `DownloadError` on mismatch. If GitHub does not publish per-asset checksums for the Stockfish release in question, document the gap with a TODO and fall back to HTTPS-only with a clearly-logged WARNING (this is acceptable v1 scope; full release-signing is a v1.x concern).
  - **ZIP path-traversal guard**: `extract_zip()` validates every `ZipInfo.filename` against the extract directory:
    ```python
    extract_root = Path(extract_to).resolve()
    for member in zip_file.infolist():
        target = (extract_root / member.filename).resolve()
        if not str(target).startswith(str(extract_root)):
            raise DownloadError(f"Refusing to extract: {member.filename} escapes extract dir")
    ```
- **D-22:** Each security fix lands with a unit test in a new `tests/test_downloader_security.py`: fixture archives with `..` path entries, fixture HTTP servers serving wrong-checksum payloads, fixture URLs forcing SSL context inspection.

### TD-13 catch-all enumeration

**In scope for Phase 1 under TD-13** (these are the "all other documented items" that this phase commits to fixing):

- Performance #1: O(n) board replay in `_format_move_announcement` — eliminated by D-02 / D-03 (no fallback path remains).
- Performance #3: `BoardState.board` copy-per-property-access — `board_ref` added (D-18).
- Security #1: SHA-256 verification on Stockfish downloads (D-21).
- Security #2: ZIP path-traversal validation (D-21).
- Security #3: Explicit `ssl.create_default_context()` on `urlopen` (D-21).

**Explicitly DEFERRED out of Phase 1** (CONCERNS.md items NOT addressed here):

- Fragile #1 (EngineAdapter overall thread/async refactor) — too large for v1; touch surgically only if a TD-* fix intersects (e.g., D-19's `EngineTimeoutError` wiring may require minor `_state_lock` discipline). No standalone refactor.
- Fragile #2 (Computer-move announcement double-path) — reassess after D-02 / D-03 land. If the new `MoveKind` payload makes the `_computer_thinking` flag unnecessary, file a follow-up; if not, accept current shape.
- Fragile #4 (wxPython Linux index pinned to ubuntu-24.04) — operational concern beyond v1 scope; revisit during a build/release pass.
- Scaling #1 (CvC pause/stop button) — UX feature, belongs in its own phase.
- Deps at Risk #1 (accessible-output3 git pin) — separate v1.x effort; vendoring is not a Phase 1 concern.
- Missing Critical #1 (promotion-piece choice UI) — new user-visible capability; gets its own phase or bundles with Phase 3c if scope permits.
- Missing Critical #2 (persistence between sessions) — that's the entire Phase 2a + 4b mandate.
- Test Gaps #1–4 — TD-14 covers narrow regression tests for TD-01..13; broader coverage (especially view-layer) is opportunistic, not a Phase 1 commitment.

### Test discipline (TD-14)

- **D-23:** Every TD-01..TD-13 fix lands with at least one regression test that demonstrably FAILS on the unfixed code and PASSES on the fixed code. Test-first or test-with-fix discipline (test commit precedes or accompanies the fix commit; not after).
- **D-24:** Regression tests live in the existing `tests/test_<module>.py` files (matching the project's `tests/test_<module_or_feature>.py` convention from `.planning/codebase/TESTING.md`), not in a single `test_phase1_regressions.py`. Each test docstring cites the TD-N number and the CONCERNS.md item:
  ```python
  def test_undo_announcement_after_new_game(self):
      """Verifies TD-01 / CONCERNS.md Bug #1: the move_undone signal is reconnected after Game.new_game()."""
  ```
- **D-25:** Security regression tests (D-22) live in a new `tests/test_downloader_security.py` (no existing equivalent file). The existing `tests/test_stockfish_manager.py` and `tests/test_exceptions.py` get additional cases for D-19 / D-20.

### Plan granularity within Phase 1

- **D-26:** Phase 1 is decomposed into **5 logical plans** (matching `granularity = standard` in `.planning/config.json`). Plan dependencies are sequential first, then parallel:
  1. **Plan 1 — Signal pattern refactor** (foundational; blocks all others):
     - TD-01 (`Game.move_undone` forwarder)
     - TD-02 (`Game.move_made(old_board, move_kind)` payload + `MoveKind` IntFlag)
     - TD-03 (`ChessController.replay_to_position` model-routed navigation)
     - Eliminate `_pending_old_board` (Fragile #3)
     - Eliminate `_format_move_announcement` O(n) replay fallback (Performance #1)
     - Regression tests: TD-01, TD-02, TD-03
  2. **Plan 2 — Engine-adapter cleanup** (parallel-safe with Plans 3, 4 after Plan 1):
     - TD-06 (remove `_simple` API surface)
     - TD-07 (extract `_resolve_move_context()`)
     - TD-08 (remove sync `Game.request_computer_move()`; migrate tests)
     - TD-10 (remove `Game.player_color`)
     - Regression tests for the kept signature stability
  3. **Plan 3 — Bug fixes & menu hygiene** (parallel-safe with Plans 2, 4 after Plan 1):
     - TD-04 (`announce_attacking_pieces` via `board.attackers()`)
     - TD-05 (specific menu IDs not `wx.ID_ANY`)
     - TD-09 (remove `&Book Hint\tB` accelerator)
     - Performance #3 (`BoardState.board_ref` property)
     - Regression tests: TD-04, TD-05, board_ref contract
  4. **Plan 4 — Persistence paths & security hardening** (parallel-safe with Plans 2, 3 after Plan 1):
     - TD-12 (platformdirs migration + one-shot helper)
     - Security #1, #2, #3 (SHA-256, path traversal, SSL context)
     - Regression tests: migration helper, security cases
  5. **Plan 5 — Exception hierarchy & test-discipline finalisation** (sequential; after Plans 1–4 land):
     - TD-11 (wire up applicable, prune unused)
     - TD-14 (audit: every TD-01..13 has a regression test; close any gaps; document the test→TD mapping in a final `tests/CONCERNS_TRACEABILITY.md` or in-line block comments)

### Claude's Discretion

- Exact test file targeting per fix (e.g., whether a TD-04 test goes in `test_chess_controller.py` or a new `test_attackers.py`) — pick by closest existing convention.
- Whether the `_resolve_move_context()` helper is a free function on `Game` or a dataclass — pick by readability.
- Whether `OPENBOARD_PROFILE_DIR` env override on `paths.py` helpers is implemented now or deferred — implement now; it's ~5 lines and pays for itself in test isolation.
- Specific log levels for migration messages (suggested: `logging.INFO` for migrations actually performed; `logging.DEBUG` for "no migration needed").
- Whether `MoveKind` lives in `openboard/models/move_kind.py` or alongside `BoardState` in `board_state.py` — pick by import-cycle safety.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents (gsd-phase-researcher, gsd-planner) MUST read these before planning or implementing.**

### Source-of-truth bug list (load-bearing — TD-01..TD-14 trace directly to specific items)
- `.planning/codebase/CONCERNS.md` — every TD-* fix references a specific section with line numbers; this is the authoritative bug catalog
- `.planning/REQUIREMENTS.md` §Tech Debt (TD) — TD-01..TD-14 specifications

### Architecture and conventions (must respect)
- `.planning/codebase/ARCHITECTURE.md` — existing MVC + blinker signal model; the patterns established in Phase 1 are inherited by all later phases
- `.planning/codebase/CONVENTIONS.md` — `ty` typechecker, modern union typing (`X | None`), descriptive names (no abbreviations), `ruff` format/check, `_on_<event>` signal handler naming, blinker `weak=False` in tests
- `.planning/codebase/STRUCTURE.md` — file layout (`openboard/{models,views,controllers,engine,config}/`)
- `.planning/codebase/TESTING.md` — pytest, `tests/test_<module>.py`, blinker signal testing pattern, `Mock(spec=...)`, `conftest.py` fixtures, async testing strategy

### Research synthesis (rationale for sequencing and patterns)
- `.planning/research/SUMMARY.md` §"Phase 1 (Tier 0): Tech-debt prerequisites — must come first" — explains why patterns established here are load-bearing for Tier 1–3
- `.planning/research/ARCHITECTURE.md` §1 (Clock) — Phase 3a will subscribe to `Game.clock_tick`; Phase 1's TD-01 forwarder pattern is the precedent
- `.planning/research/ARCHITECTURE.md` §2 (SoundService) — Phase 4a depends on `Game.move_made(old_board, move_kind)` from TD-02
- `.planning/research/PITFALLS.md` §"Pitfall 4 (autosave-in-cwd)" — TD-12 platformdirs migration prevents this for Phases 2b and 4b
- `.planning/research/STACK.md` §"platformdirs" — confirms platformdirs is the library choice for D-09

### Project context
- `.planning/PROJECT.md` §Validated (preserve existing capabilities), §Constraints (engine optional, threading model, ty typechecker)
- `.planning/ROADMAP.md` §"Phase 1: Tech Debt Cleanup" — phase goal and success criteria

### User-defined non-negotiables
- `CLAUDE.local.md` — descriptive variable names; `X | None` not `Optional[X]`
- `CLAUDE.md` (gitignored, local) — generated GSD workflow guidance for this project

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `openboard/models/board_state.py` — `BoardState` is the single source of truth for `chess.Board`; `make_move()` and `undo_move()` are the only legitimate movers. Phase 1's TD-03 fix (model-routed navigation) reuses these.
- `openboard/models/game.py` — `Game._on_board_move` already forwards `BoardState.move_made` upward as `Game.move_made`. TD-01 follows the same pattern for `move_undone`. TD-02 enriches the existing forwarder with `old_board` and `move_kind`.
- `openboard/controllers/chess_controller.py:90` — `_on_model_move` is the existing handler that consumes `Game.move_made`. After TD-02, it accepts `old_board` and `move_kind` kwargs from the signal.
- `openboard/exceptions.py` — `OpenBoardError` hierarchy already exists; D-19 wires up `EngineTimeoutError`, `EngineProcessError`, `DownloadError`, `NetworkError` into the call sites that currently raise bare `RuntimeError`.
- `tests/conftest.py` — shared FEN fixtures (`stalemate_fen`, `insufficient_material_fen`); regression tests (especially TD-04 attacker tests) reuse them.
- `tests/test_engine_adapter_integration.py:MockEngine` — full async mock; Plan 2 / Plan 5 reuse for tests of D-19 (`EngineTimeoutError` raising path).

### Established Patterns
- **Signal forwarding through `Game`** — already the pattern for `move_made` and `status_changed`. TD-01 extends to `move_undone`. This is the canonical pattern for ALL future model→controller signals (Clock in Phase 3a; nothing else introduces new model signals in v1).
- **`blinker.Signal` instance attributes**, not module-level — except `StockfishManager` which uses module-level signals (preserve that exception).
- **`wx.CallAfter` for thread marshalling** — engine asyncio thread → main thread. `WxCallbackExecutor` (`engine/engine_adapter.py`) already encapsulates this. No new threading patterns introduced in Phase 1.
- **Modern union typing** — `X | None`, never `Optional[X]`. Pydantic dataclasses use the same.
- **`@dataclass` (stdlib) for value objects, `@pydantic.dataclasses.dataclass` for JSON-serialisable config** — `MoveKind` (D-01) is `enum.IntFlag`, not a dataclass.
- **`logger = get_logger(__name__)` at module top** — D-10 migration logs follow this.
- **Tests in `tests/test_<module>.py`, classes via `setup_method`, signals collected with `weak=False`** — Plans 1–5 land regression tests in the matching file per D-24.

### Integration Points
- `openboard/views/views.py:main()` (line 743) — startup; D-10 migration helper runs here on first launch (after settings load, before `wx.App` creation).
- `openboard/views/views.py:_navigate_to_position` (line 673-688) — TD-03 site; deletes here, replaces with `controller.replay_to_position(index)` call.
- `openboard/views/views.py:207, 250` — TD-05 site; `wx.ID_ANY` bind→specific menu ID.
- `openboard/views/views.py:238` — TD-09 site; remove `\tB` accelerator.
- `openboard/controllers/chess_controller.py:74` — TD-01 site; existing `_on_model_undo` connects to `game.board_state.move_undone` — switch to `game.move_undone`.
- `openboard/controllers/chess_controller.py:90, 163, 535, 544, 64` — `_pending_old_board` mutations; D-03 deletes these.
- `openboard/controllers/chess_controller.py:480-495` — TD-04 site; `announce_attacking_pieces` rewrite.
- `openboard/controllers/chess_controller.py:598-606, 528-535` — Performance #1 sites; eliminated by D-02 / D-03.
- `openboard/models/board_state.py:31-36` — `.board` property; D-18 adds `board_ref` sibling.
- `openboard/models/game.py:84-104` — `Game.new_game`; D-04 fix lives here (rehook `move_undone`).
- `openboard/models/game.py:101` — `self.player_color = ...`; D-15 deletes this line.
- `openboard/models/game.py:128-134` — auto-promotion to queen; flagged in CONCERNS.md "Missing Critical #1" but explicitly DEFERRED — do not touch in Phase 1.
- `openboard/models/game.py:279-363` (sync request_computer_move) and `:366-463` (async) — TD-08 deletes the sync method; TD-07 extracts the shared preamble from the remaining async path.
- `openboard/engine/engine_adapter.py:799-881` — `_simple` API; TD-06 deletes the entire range.
- `openboard/engine/downloader.py:62, 106-149, 152-172, 217-329, 244` — D-21 / D-22 sites for SSL context, ZIP traversal, SHA-256 verification.
- `openboard/config/settings.py:44, 116` — `engines_dir` initialiser; `get_settings()` singleton; D-09 / D-11 paths migration.
- `openboard/exceptions.py:70-188` — D-19 / D-20 wire-up and pruning.
- `pyproject.toml` — D-09 adds `platformdirs` to `[project.dependencies]`. wxPython Linux index marker (Fragile #4) is NOT touched in Phase 1.

</code_context>

<specifics>
## Specific Ideas

- **The `move_undone` regression test (D-04)** is the canonical example downstream agents should reference for the test-first / test-with-fix discipline (D-23). The bug class is "signal connected to a discarded object" — the test must construct a game, play a move, call `Game.new_game()` to swap `BoardState`, then assert that pressing undo on the new game reaches `_on_model_undo` with the expected payload. Without the TD-01 fix, the assertion fails silently because the original handler is bound to a now-orphaned `BoardState`.
- **The `_pending_old_board` removal (D-03) is implicit, not explicit, in TD-02.** Once `Game.move_made` always carries `old_board`, there is no remaining code path that needs to read or write `_pending_old_board`. Plan 1's task list should explicitly call out "delete every `_pending_old_board` reference" as a verification step — otherwise the variable can drift and re-grow uses.
- **`MoveKind.CHECK` and `MoveKind.CHECKMATE` are computed at signal-emission time, not at move-application time.** `BoardState.make_move()` pushes the move first; `Game._on_board_move` (running on the same thread) inspects `board.is_check()` / `board.is_checkmate()` after the push, builds the `MoveKind` flag, and includes it in `Game.move_made`. This avoids leaking check-detection responsibility into `BoardState`.
- **TD-08 test migration** — the sync tests are in `tests/test_game.py` (and possibly a `test_game_async.py` parallel). Use the inline-callback Mock pattern from `tests/test_game_async.py:test_request_hint_async_callback_emits_hint_ready_on_success` as the template.
- **Ordering note for Plan 4**: the platformdirs migration (D-10) MUST run before any Phase 1 test touches `Path.cwd()`-relative files; otherwise a test could spuriously trigger the migration. Use `OPENBOARD_PROFILE_DIR` env override in tests to redirect to `tmp_path`.

</specifics>

<deferred>
## Deferred Ideas

- **Promotion-piece choice UI** (CONCERNS.md Missing Critical #1) — explicitly deferred. New user-visible capability; belongs in its own phase or bundles with Phase 3c (theme/scale/rebind UI work) if scope permits. Roadmap backlog.
- **EngineAdapter overall thread/async refactor** (CONCERNS.md Fragile #1) — too large for v1. Phase 1 touches the file only where TD-* fixes intersect (D-19's `EngineTimeoutError` wiring may require minor `_state_lock` discipline). Roadmap backlog as a v1.x or v2 candidate.
- **Computer-move announcement double-path** (CONCERNS.md Fragile #2) — reassess after D-02 / D-03 land. If `MoveKind` payload makes the `_computer_thinking` flag unnecessary, file a follow-up; if not, document the current shape and accept it for v1.
- **CvC pause/stop button** (CONCERNS.md Scaling #1) — UX feature; its own phase. Roadmap backlog.
- **accessible-output3 vendoring** (CONCERNS.md Deps at Risk #1) — vendoring or fork-and-pin discussion belongs in v1.x; not Phase 1 scope.
- **wxPython Linux index migration** (CONCERNS.md Fragile #4 / Deps at Risk #2) — operational; build/release pass concern, not a coding-phase concern.
- **View-layer broader test coverage** (CONCERNS.md Test Gaps #1) — TD-14 covers narrow regression tests for TD-01..13; broad view-layer tests (`ChessFrame`, `BoardPanel`, menu binding correctness beyond TD-05) are opportunistic. Roadmap backlog.
- **Async computer-move end-to-end tests with real engine timing** (CONCERNS.md Test Gaps #3) — opportunistic; not a Phase 1 commitment.
- **Persistence between sessions** (CONCERNS.md Missing Critical #2) — that is the entire Phase 2a + 4b mandate. Not Phase 1.

</deferred>

---

*Phase: 01-tech-debt-cleanup*
*Context gathered: 2026-04-27 (auto mode)*

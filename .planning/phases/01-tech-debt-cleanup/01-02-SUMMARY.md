---
phase: 01-tech-debt-cleanup
plan: "02"
subsystem: engine-model
tags:
  - engine
  - asyncio
  - python-chess
  - test-migration
  - api-cleanup
dependency_graph:
  requires:
    - Plan 01-01 (Game.move_made enriched payload, MoveKind, _connect_board_signals)
  provides:
    - EngineAdapter without _simple API surface (TD-06)
    - Game._resolve_move_context() pure NamedTuple helper (TD-07)
    - Async-only computer-move path via request_computer_move_async (TD-08)
    - Game.player_color attribute removed (TD-10)
  affects:
    - openboard/engine/engine_adapter.py
    - openboard/models/game.py
    - tests/test_engine_adapter.py
    - tests/test_game.py
    - tests/test_game_async.py
    - tests/test_game_mode.py
    - tests/test_game_opening_book_integration.py
    - tests/test_chess_controller_opening_book.py
tech_stack:
  added:
    - "typing.NamedTuple (MoveContext class in openboard/models/game.py)"
  patterns:
    - D-12: _simple API surface hard-deleted from EngineAdapter (no deprecation shim)
    - D-13: sync Game.request_computer_move deleted; all callers migrated to async via Mock(spec=EngineAdapter) inline-callback
    - D-14: Game._resolve_move_context() extracted as pure NamedTuple-returning preamble helper
    - D-15: Game.player_color backward-compat attribute removed; consumers read game.config.human_color
    - D-24: regression tests in TD-correlated test modules; docstrings cite TD-N
key_files:
  created: []
  modified:
    - openboard/engine/engine_adapter.py
    - openboard/models/game.py
    - tests/test_engine_adapter.py
    - tests/test_game.py
    - tests/test_game_async.py
    - tests/test_game_mode.py
    - tests/test_game_opening_book_integration.py
    - tests/test_chess_controller_opening_book.py
decisions:
  - "D-12: _simple API surface hard-deleted from EngineAdapter; no backward-compat shim"
  - "D-13: sync Game.request_computer_move() removed; async-only path from now on"
  - "D-14: _resolve_move_context() is a pure preamble helper returning MoveContext(NamedTuple); reusable for Phase v2 ANL-* analysis paths"
  - "D-15: Game.player_color backward-compat attribute removed; read game.config.human_color"
  - "D-24: regression tests in TD-correlated modules with TD-N docstring citations"
metrics:
  duration: "14m"
  completed_date: "2026-04-29"
  tasks_completed: 3
  files_modified: 8
  files_created: 0
---

# Phase 01 Plan 02: Engine API Cleanup Summary

Hard-deleted the `_simple` EngineAdapter aliases (~85 LOC), extracted a pure `_resolve_move_context()` NamedTuple helper from the duplicated computer-move preamble, removed the synchronous `request_computer_move()` method, and stripped the `player_color` backward-compat attribute — consolidating the engine layer to a single async path with an honest, testable contract.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | RED tests for TD-06/TD-07/TD-08/TD-10 | c82034d | test_engine_adapter.py, test_game.py, test_game_async.py |
| 2 | Delete _simple API + remove player_color (TD-06, TD-10) | 08872cc | engine_adapter.py, game.py, test_game_mode.py |
| 3 | Extract _resolve_move_context + delete sync + migrate callers (TD-07, TD-08) | 8e7b17a | game.py, test_game_mode.py, test_game_opening_book_integration.py, test_chess_controller_opening_book.py |

## Decisions Made

### D-12: _simple API Surface Hard-Deleted
Five methods — `start_simple`, `_start_engine_simple`, `stop_simple`, `get_best_move_simple`, `get_best_move_simple_async` — deleted from `EngineAdapter` with no deprecation shim. These were thin aliases that added no value and provided a confusion surface. Net: -85 LOC from engine_adapter.py.

### D-13: Synchronous request_computer_move Removed
`Game.request_computer_move()` deleted entirely. All 10 test call sites migrated to `request_computer_move_async()` via the `Mock(spec=EngineAdapter)` inline-callback pattern. The async path is now the only computer-move entry point.

### D-14: _resolve_move_context as Pure NamedTuple Helper
The duplicated preamble (mode validation, difficulty resolution, FEN capture, book lookup) extracted into `_resolve_move_context()` returning `MoveContext(NamedTuple)`. Per Codex MEDIUM: the helper is a `typing.NamedTuple` (not `@dataclass`), with three fields `(difficulty_config, fen_before, book_move)`. The purity contract is verified by source introspection in `test_resolve_move_context_is_pure`.

### D-15: Game.player_color Removed
The `self.player_color = self.config.human_color` backward-compat line deleted from `Game.new_game()`. The single external consumer (`tests/test_game_mode.py:199`) updated to read `game.config.human_color`.

## MoveContext Return Shape (TD-07 / Codex MEDIUM)

```python
class MoveContext(NamedTuple):
    difficulty_config: DifficultyConfig
    fen_before: str
    book_move: chess.Move | None
```

- `typing.NamedTuple` (confirmed by `issubclass(type(context), tuple)` and `hasattr(type(context), "_fields")`)
- Immutable by construction
- Tuple-unpacking works: `difficulty_config, fen_before, book_move = self._resolve_move_context()`

## Purity Contract (Codex MEDIUM) — Verified

`_resolve_move_context()` source contains NONE of:
- `.send(` — no signal emission
- `wx.CallAfter` — no wx thread marshalling
- `make_move(` — no move application via BoardState
- `get_best_move_async` — no engine async path invocation
- `get_best_move(` — no engine sync path invocation
- `board_state._board.push` — no direct board mutation

Verified by `TestResolveMoveContextExtracted::test_resolve_move_context_is_pure` (source introspection).

## Engine-Optional Behavior (Codex MEDIUM) — Verified

`request_computer_move_async()` with `engine_adapter=None` and no book hit raises `EngineError` (not `AttributeError`, not silent no-op). Verified by `TestRequestComputerMoveEngineOptional::test_request_computer_move_async_raises_when_no_engine_and_no_book`.

## TD-08 Sync Caller Migration — Full List

| File | Old Call Site(s) | Migration Pattern |
|------|-----------------|-------------------|
| tests/test_game_mode.py | lines 143, 152, 172, 264, 290 (5 sites) | `_make_sync_mock_engine` + signal capture + `request_computer_move_async()` |
| tests/test_game_opening_book_integration.py | lines 175, 205, 235, 257 (4 sites) | `_make_sync_mock_engine_book` + signal capture + `request_computer_move_async()` |
| tests/test_chess_controller_opening_book.py | line 93 (1 site) | `_make_sync_mock_engine_controller` + signal capture + `request_computer_move_async()` |

Total migrated: 10 call sites.

## Net LOC Delta

| File | Before | After | Change |
|------|--------|-------|--------|
| openboard/engine/engine_adapter.py | 882 | 796 | -86 (5 _simple methods deleted) |
| openboard/models/game.py | 503 (post-Plan01) | net change: +78/-203 | -85 sync method, +30 MoveContext NamedTuple + helper, refactored async path |

Net source deletion: ~125 LOC from production code.

## TD-N to Test Traceability (Plan 05)

| TD | Test | Class | Method |
|----|------|-------|--------|
| TD-06 | tests/test_engine_adapter.py | TestSimpleApiRemoved | test_simple_api_removed |
| TD-06 (guardrail) | tests/test_engine_adapter.py | TestSimpleApiRemoved | test_simple_token_absent_from_source_tree |
| TD-07 | tests/test_game_async.py | TestResolveMoveContextExtracted | test_resolve_move_context_extracted |
| TD-07 (purity) | tests/test_game_async.py | TestResolveMoveContextExtracted | test_resolve_move_context_is_pure |
| TD-08 | tests/test_game.py | TestSyncRequestComputerMoveRemoved | test_request_computer_move_sync_removed |
| TD-10 | tests/test_game.py | TestPlayerColorRemoved | test_player_color_removed |
| Codex MEDIUM engine-optional | tests/test_game_async.py | TestRequestComputerMoveEngineOptional | test_request_computer_move_async_raises_when_no_engine_and_no_book |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] _resolve_move_context docstring contained forbidden patterns**
- **Found during:** Task 3 GREEN phase (test_resolve_move_context_is_pure failing)
- **Issue:** The method docstring mentioned `".send("` and `"wx.CallAfter"` as things the method must NOT do — but the source introspection test checks the entire method source including docstring, causing false positives.
- **Fix:** Rewrote docstring to describe the purity contract without embedding the forbidden token strings.
- **Files modified:** openboard/models/game.py
- **Commit:** 8e7b17a

**2. [Rule 1 - Bug] EngineNotFoundError constructor doesn't accept keyword details=**
- **Found during:** Task 3 initial implementation
- **Issue:** `EngineNotFoundError(engine_name, search_paths)` signature does not accept `details=` kwarg. Attempted to pass `EngineNotFoundError("chess engine", details=...)`.
- **Fix:** Used `EngineError(message, details)` directly (base class with the correct signature) instead of the subclass.
- **Files modified:** openboard/models/game.py
- **Commit:** 8e7b17a

**3. [Rule 1 - Bug] test_request_computer_move_async_raises_when_no_engine_and_no_book used HvC without difficulty**
- **Found during:** Task 1 RED phase (test raised GameModeError instead of EngineError)
- **Issue:** The test created `GameConfig(mode=HUMAN_VS_COMPUTER, human_color=chess.WHITE)` without `difficulty=`, causing `GameModeError` at config construction before reaching the engine-optional guard.
- **Fix:** Added `difficulty=DifficultyLevel.BEGINNER` to the test's GameConfig.
- **Files modified:** tests/test_game_async.py
- **Commit:** c82034d

**4. [Rule 2 - Missing] test_game_mode.py had 5 sync callers, not 2 as RESEARCH.md stated**
- **Found during:** grep audit in Task 1
- **Issue:** RESEARCH.md documented 2 sync callers in test_game_mode.py (lines 143, 147) but grep found 5 (lines 143, 152, 172, 264, 290). All 5 migrated.
- **Fix:** All 5 sites migrated to async pattern.
- **Files modified:** tests/test_game_mode.py
- **Commit:** 8e7b17a

## Known Stubs

None — all engine paths fully implemented and tested.

## Threat Flags

None — this plan is a pure deletion/refactoring pass. No new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries. The engine-optional guard (T-02-03) is now properly implemented.

## Self-Check: PASSED

- [x] openboard/engine/engine_adapter.py exists with 796 lines (was 882)
- [x] openboard/models/game.py contains `class MoveContext(NamedTuple)`
- [x] openboard/models/game.py contains `def _resolve_move_context`
- [x] openboard/models/game.py contains `self._resolve_move_context(`
- [x] `def request_computer_move` absent from openboard/models/game.py (only `request_computer_move_async` present)
- [x] `self.player_color` absent from openboard/models/game.py
- [x] tests/test_engine_adapter.py contains TestSimpleApiRemoved (both tests)
- [x] tests/test_game.py contains TestPlayerColorRemoved and TestSyncRequestComputerMoveRemoved
- [x] tests/test_game_async.py contains TestResolveMoveContextExtracted and TestRequestComputerMoveEngineOptional
- [x] All 46 Plan 02 cohort tests pass
- [x] Full pytest suite: 337 passed, 6 pre-existing Plan 01-03 RED failures, 1 skipped
- [x] ruff check clean for all touched source files
- [x] ty check clean for all touched source files
- [x] Commits exist: c82034d (RED), 08872cc (TD-06/TD-10 GREEN), 8e7b17a (TD-07/TD-08 GREEN)

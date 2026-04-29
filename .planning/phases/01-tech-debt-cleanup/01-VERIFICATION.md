---
phase: 01-tech-debt-cleanup
verified: 2026-04-29T00:00:00Z
status: passed
score: 14/14 must-haves verified
overrides_applied: 0
re_verification: null
gaps: []
human_verification: []
---

# Phase 1: Tech Debt Cleanup Verification Report

**Phase Goal:** Every documented bug from `.planning/codebase/CONCERNS.md` is fixed, and the structural patterns (signal forwarders on `Game`, model-routed navigation, `platformdirs` for persistence, specific menu IDs, `move_made(old_board, move_kind)` payload) that every later phase inherits are established once, correctly.
**Verified:** 2026-04-29
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | After starting a new game and pressing undo, the user hears the undo announcement (TD-01: `move_undone` reconnected after `Game.new_game()`) | VERIFIED | `Game.move_undone = Signal()` at line 80; `_on_board_undo` forwarder at line 131; `_connect_board_signals()` called from both `__init__` and `new_game()` at lines 86 and 152; `TestMoveUndoneForwarder::test_move_undone_signal_reconnects_after_new_game` PASSES |
| 2 | "What attacks this square?" with a pinned attacker correctly names the pinned attacker (TD-04: uses `board.attackers()`) | VERIFIED | `announce_attacking_pieces` at line 486 uses `board = self.game.board_state.board_ref` then `board.attackers(chess.WHITE, self.current_square) | board.attackers(chess.BLACK, self.current_square)` — bitboard union; `TestAnnounceAttackingPieces::test_announce_attacking_pieces_includes_pinned_attacker` PASSES with canonical FEN |
| 3 | Menu items other than "Load PGN" never trigger the PGN load handler (TD-05: bound to specific menu ID) | VERIFIED | Zero `id=wx.ID_ANY` binds in `views.py`; `_build_menu_bar()` extracted at line 219; all 13 EVT_MENU binds use captured `.GetId()`; `TestMenuBindingHygieneBehavioral::test_bind_records_specific_ids_for_menu_items` PASSES |
| 4 | On fresh install, settings/keyboard_config/engines_dir live under OS-standard user-data location; cwd files migrated automatically (TD-12) | VERIFIED | `openboard/config/paths.py` with `user_config_dir()`, `user_data_dir()`, `user_state_dir()`, `engines_dir()`; `migrate_legacy_paths()` called before `get_settings()` at lines 670-674 in `main()`; `TestPathsModule`, `TestLegacyConfigJsonMigration`, `TestStartupOrdering` all PASS |
| 5 | Each fix from TD-01..TD-13 has a regression test that fails on buggy code and passes on fixed code (TD-14) | VERIFIED | `tests/CONCERNS_TRACEABILITY.md` exists with locked `\| REQ-ID \| Concern \| Test path \| Test name \|` format; 14 TD rows; 14 `^- TD-` bullets; `TestConcernsTraceability::test_concerns_traceability_doc_exists_and_lists_all_td` PASSES |

**Score:** 5/5 roadmap success criteria verified

### Requirement-Level Truths (All 14 TD requirements)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| TD-01 | `move_undone` signal reconnected after `Game.new_game()` | VERIFIED | `Game._connect_board_signals()` called in `new_game()`; `_on_board_undo` forwarder wired; `TestMoveUndoneForwarder` passes |
| TD-02 | `Game.move_made` carries `old_board` and `move_kind: MoveKind` payload; backward-compat broad subscriber works | VERIFIED | `BoardState.make_move()` captures `old_board = self._board.copy()` at line 84; `Game._on_board_move` computes `move_kind` and emits `self.move_made.send(self, move=move, old_board=old_board, move_kind=move_kind)`; `MoveKind` IntFlag at `openboard/models/move_kind.py:14` with QUIET/CAPTURE/CASTLE/EN_PASSANT/PROMOTION/CHECK/CHECKMATE; `TestMoveMadePayload::test_broad_subscriber_signature_compatible` PASSES |
| TD-03 | `replay_to_position` uses `BoardState.make_move`/`undo_move` exclusively; `_pending_old_board` removed; `_navigate_to_position` deleted | VERIFIED | `ChessController.replay_to_position` at line 388 uses `self.game.board_state.make_move/undo_move`; grep returns 0 hits for `_pending_old_board` in `openboard/`; `TestReplayToPosition`, `TestPendingOldBoardRemoved` PASS |
| TD-04 | `announce_attacking_pieces` uses `board.attackers()`; pinned attackers reported; O(1) bitboard | VERIFIED | Lines 499-500 in `chess_controller.py`; canonical fixture `pinned_attacker_fen` (`4r3/8/8/8/8/8/8/4K3 w - - 0 1`) in `tests/conftest.py`; `TestAnnounceAttackingPieces` PASSES |
| TD-05 | `on_load_pgn` bound to specific menu ID, not `wx.ID_ANY` | VERIFIED | Zero `id=wx.ID_ANY` EVT_MENU binds in `views.py`; `TestMenuBindingHygieneBehavioral` (behavioral primary) and `TestMenuBindingHygieneSourceGrep` ([guardrail]) both PASS |
| TD-06 | `_simple` API surface deleted from `EngineAdapter` | VERIFIED | Zero `_simple` method definitions in `engine_adapter.py`; `TestSimpleApiRemoved::test_simple_api_removed` and `::test_simple_token_absent_from_source_tree` both PASS |
| TD-07 | Duplicate difficulty-resolution extracted into `Game._resolve_move_context()` returning `MoveContext(NamedTuple)` | VERIFIED | `class MoveContext(NamedTuple)` at line 20 of `game.py`; `def _resolve_move_context` at line 330; called by `request_computer_move_async` at line 412; purity contract verified by `test_resolve_move_context_is_pure` (no `.send(`, `wx.CallAfter`, `make_move(`, `get_best_move*`, `board_state._board.push` in source) |
| TD-08 | Synchronous `Game.request_computer_move()` removed; tests use async path | VERIFIED | `def request_computer_move\b` returns 0 matches in `game.py`; `request_computer_move_async` exists; `TestSyncRequestComputerMoveRemoved::test_request_computer_move_sync_removed` PASSES |
| TD-09 | `&Book Hint\tB` accelerator removed; `B` dispatches via `EVT_CHAR_HOOK` only | VERIFIED | Zero matches for `Book Hint\tB` in `views.py`; `KeyAction.REQUEST_BOOK_HINT` still present in `keyboard_config.py`; `TestBookHintAccelerator::test_book_hint_menu_no_accelerator` PASSES |
| TD-10 | `Game.player_color` backward-compat attribute removed | VERIFIED | Zero `self.player_color` assignments in `game.py`; `TestPlayerColorRemoved::test_player_color_removed` PASSES |
| TD-11 | Unused exception types pruned; `EngineTimeoutError`/`EngineProcessError`/`NetworkError` wired | VERIFIED | `AccessibilityError`, `DialogError`, `UIError`, `GameStateError`, `SettingsError` absent from `exceptions.py`; `raise EngineTimeoutError("get_best_move", time_ms)` at line 475 of `engine_adapter.py`; `raise EngineProcessError(f"Engine startup failed: ...")` at lines 261 and 270; `TestPrunedExceptionTypes`, `TestExceptionWiring`, `TestDownloadFileExceptionWiring`, `TestStockfishManagerExceptionBubbleUp` all PASS |
| TD-12 | All persistent files resolve via `platformdirs`; one-shot migration; startup ordering correct | VERIFIED | `openboard/config/paths.py` exposes 7 path functions all honoring `OPENBOARD_PROFILE_DIR`; `migrate_legacy_paths()` in `migration.py`; `EngineSettings.engines_dir` uses `default_factory=_engines_dir_factory`; `Path.cwd()` absent from `settings.py`; `migrate_legacy_paths()` called at line 671 before `get_settings()` at line 674; all 4 test modules pass |
| TD-13 | All other bugs/tech-debt resolved: `BoardState.board_ref`; downloader SSL/SHA-256/ZIP; `_pending_old_board` removed | VERIFIED | `board_ref` property with verbatim "MUST NOT mutate" docstring at line 39 of `board_state.py`; `SSL_CONTEXT = ssl.create_default_context()` at line 21 of `downloader.py`; `os.path.commonpath` ZIP guard at line 213; `expected_sha256` param at line 121; `_pending_old_board` has 0 hits in `openboard/`; all security and perf tests pass |
| TD-14 | Regression test for every fix (TD-01..TD-13); traceability table exists | VERIFIED | `tests/CONCERNS_TRACEABILITY.md` with 14-row locked table referencing canonical `pinned_attacker_fen` and all tests by exact path+name; 14 `^- TD-` coverage bullets; format assertion test passes |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `openboard/models/move_kind.py` | MoveKind IntFlag with 7 bits | VERIFIED | `class MoveKind(enum.IntFlag)` with QUIET/CAPTURE/CASTLE/EN_PASSANT/PROMOTION/CHECK/CHECKMATE |
| `openboard/models/game.py` | `move_undone` forwarder, enriched `move_made`, `_resolve_move_context`, `MoveContext` NamedTuple | VERIFIED | All present; `player_color` absent; sync `request_computer_move` absent |
| `openboard/models/board_state.py` | `board_ref` property with "MUST NOT mutate" docstring; `old_board` in `make_move` | VERIFIED | `board_ref` at line 39; snapshot `.board` retained; `old_board = self._board.copy()` at line 84 |
| `openboard/controllers/chess_controller.py` | `replay_to_position`; `announce_attacking_pieces` uses `board.attackers()` + `board_ref` | VERIFIED | Both present; `board_ref` adopted in `announce_attacking_pieces` |
| `openboard/views/views.py` | `_build_menu_bar()` seam; zero `wx.ID_ANY` binds; no `\tB` accelerator; `migrate_legacy_paths()` before `get_settings()` | VERIFIED | All confirmed |
| `openboard/engine/engine_adapter.py` | No `_simple` methods; `raise EngineTimeoutError`; `raise EngineProcessError` with "startup failed" | VERIFIED | 796 lines; all typed raise sites present |
| `openboard/config/paths.py` | 7 path functions; `OPENBOARD_PROFILE_DIR` override; `settings_path()` returns `config.json` | VERIFIED | All 7 functions present |
| `openboard/config/migration.py` | `migrate_legacy_paths()`; conditional `_migrate_engines_dir()` | VERIFIED | Present; `paths.engines_dir()` not called before existence check |
| `openboard/config/settings.py` | `EngineSettings.engines_dir` via `_engines_dir_factory`; no `Path.cwd()` | VERIFIED | `default_factory=_engines_dir_factory` at line 46; zero `Path.cwd` |
| `openboard/engine/downloader.py` | `SSL_CONTEXT = ssl.create_default_context()`; `expected_sha256` param; `os.path.commonpath` guard | VERIFIED | All present at lines 21, 121, 213 |
| `openboard/engine/stockfish_manager.py` | "no upstream checksum source" INFO log | VERIFIED | Line 49 |
| `openboard/exceptions.py` | Pruned 5 unused types; `EngineTimeoutError`/`EngineProcessError`/`DownloadError`/`NetworkError` kept | VERIFIED | 0 pruned classes; 4 typed exceptions importable |
| `tests/conftest.py` | `pinned_attacker_fen` fixture with `4r3/8/8/8/8/8/8/4K3 w - - 0 1` | VERIFIED | Present at line 26; single source of truth across all plans |
| `tests/CONCERNS_TRACEABILITY.md` | Locked `\| REQ-ID \| Concern \| Test path \| Test name \|` format; 14 rows | VERIFIED | 14-row table; 14 `^- TD-` bullets; canonical TD-04 references present |
| `tests/test_views_menus.py` | TD-05 behavioral test + guardrail + TD-09 accelerator test | VERIFIED | All 4 tests PASS |
| `tests/test_board_state_terminal.py` | `TestBoardRefProperty` (3 tests including docstring contract) | VERIFIED | All PASS |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `BoardState.make_move` | `Game._on_board_move` | `self.move_made.send(self, move=move, old_board=old_board)` | WIRED | Line 84-86 of `board_state.py` |
| `Game._on_board_move` | subscribers of `Game.move_made` | `self.move_made.send(self, move=move, old_board=old_board, move_kind=move_kind)` | WIRED | Line 128 of `game.py` |
| `Game.new_game` | `Game._connect_board_signals` | method call after `BoardState()` construction | WIRED | Line 152 of `game.py` |
| `views.py:on_show_move_list` | `ChessController.replay_to_position` | `self.controller.replay_to_position(selected_position)` | WIRED | Line 612 of `views.py` |
| `Game.request_computer_move_async` | `Game._resolve_move_context` | `context = self._resolve_move_context()` | WIRED | Line 412 of `game.py` |
| `views.py:main` | `migration.migrate_legacy_paths` | called BEFORE `get_settings()` | WIRED | Lines 670-674 of `views.py`; migration at 671, settings at 674 |
| `EngineSettings` | `paths.engines_dir` | `default_factory=_engines_dir_factory` | WIRED | Line 46 of `settings.py` |
| `downloader.py:download_file` | `ssl.create_default_context()` | `context=SSL_CONTEXT` in all `urlopen()` calls | WIRED | `SSL_CONTEXT` at line 21; used in all 3 `urlopen` calls |
| `downloader.py:extract_zip` | `os.path.commonpath` validation | per-member resolved-path check | WIRED | Line 213 of `downloader.py` |
| `engine_adapter.py:get_best_move` | `EngineTimeoutError` | `except FutureTimeoutError` block raising `EngineTimeoutError` | WIRED | Line 475 of `engine_adapter.py` |
| `engine_adapter.py:_start_engine` | `EngineProcessError` | `except Exception` and `except PermissionError` at startup failure sites | WIRED | Lines 261, 270 of `engine_adapter.py` |

### Data-Flow Trace (Level 4)

Not applicable — this phase delivers bug fixes and structural refactoring (no new data-rendering components). The verification focuses on signal wiring and API correctness rather than UI data flows. The test suite comprehensively covers data flows through signal assertions.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes at 386 count | `uv run python -m pytest -q --tb=short` | 386 passed, 2 warnings (pre-existing coroutine warnings in integration tests unrelated to Phase 1) | PASS |
| Plan 01+02 cohort (17 tests) | targeted pytest run | 17 passed | PASS |
| Plans 03+04+05 cohort (60 tests) | targeted pytest run | 60 passed | PASS |
| ruff check across all openboard/ | `uv run ruff check openboard/` | All checks passed | PASS |
| ty check across all openboard/ | `uv run python -m ty check openboard/` | All checks passed | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| TD-01 | 01-01 | move_undone reconnected after new_game() | SATISFIED | `_connect_board_signals()` + `_on_board_undo` forwarder; regression test passes |
| TD-02 | 01-01 | Game.move_made enriched payload with old_board + MoveKind | SATISFIED | `MoveContext` in `game.py`; broad-subscriber test passes |
| TD-03 | 01-01 | model-routed navigation; _pending_old_board removed | SATISFIED | `replay_to_position` uses `make_move`/`undo_move`; 0 `_pending_old_board` hits |
| TD-04 | 01-03 | attackers() bitboard; pinned attacker fix | SATISFIED | `board.attackers()` in `announce_attacking_pieces`; canonical fixture test passes |
| TD-05 | 01-03 | specific menu IDs; no wx.ID_ANY bind | SATISFIED | 0 `id=wx.ID_ANY` in `views.py`; behavioral test passes |
| TD-06 | 01-02 | _simple API surface deleted | SATISFIED | 0 `_simple` methods; source-tree grep test passes |
| TD-07 | 01-02 | _resolve_move_context helper extracted | SATISFIED | `MoveContext(NamedTuple)` with purity contract; test passes |
| TD-08 | 01-02 | sync request_computer_move removed | SATISFIED | 0 `def request_computer_move\b` in `game.py`; test passes |
| TD-09 | 01-03 | Book Hint \tB accelerator removed | SATISFIED | 0 `Book Hint\tB` in `views.py`; KeyAction still exists |
| TD-10 | 01-02 | player_color backward-compat attr removed | SATISFIED | 0 `self.player_color` in `game.py`; test passes |
| TD-11 | 01-05 | Exception hierarchy pruned; typed raise sites wired | SATISFIED | 5 types pruned; 3 typed raise sites in production code; all tests pass |
| TD-12 | 01-04 | platformdirs paths; migration; startup ordering | SATISFIED | `paths.py`, `migration.py` exist; ordering enforced; all 4 test modules pass |
| TD-13 | 01-03, 01-04 | board_ref; SSL/SHA-256/ZIP; _pending_old_board | SATISFIED | All three slices fully implemented and tested |
| TD-14 | 01-05 | Regression test for every fix | SATISFIED | `CONCERNS_TRACEABILITY.md` with 14-row locked table; format test passes |

**All 14 Phase 1 requirements: SATISFIED**

### Anti-Patterns Found

None found. Grep sweeps confirmed:
- Zero `_pending_old_board` references in `openboard/` (0 hits)
- Zero `id=wx.ID_ANY` in `openboard/views/views.py` EVT_MENU bind sites (0 hits)
- Zero `Book Hint\tB` accelerator strings in `views.py` (0 hits)
- Zero `self.player_color` assignments in `game.py` (0 hits)
- Zero `_simple` method definitions in `engine_adapter.py` (0 hits)
- Zero `Path.cwd()` in `settings.py` (0 hits)
- Zero module-top `settings = get_settings()` in `views.py` (0 hits — the assignment at line 674 is inside `main()`)
- Zero pruned exception class definitions in `exceptions.py` (0 hits)

### Human Verification Required

None. All must-haves are verifiable programmatically. The test suite at 386 passing tests covers the full behavioral surface of Phase 1. No visual appearance, real-time behavior, or external service integration items remain that require human testing for this phase's scope.

### Gaps Summary

No gaps. All 14 TD requirements are satisfied. The phase goal is fully achieved:

- Every documented bug from CONCERNS.md is fixed (TD-01..TD-05, TD-09, TD-13)
- All structural patterns are established correctly:
  - Signal forwarders on `Game` via `_connect_board_signals()` (D-05 canonical)
  - Model-routed navigation via `ChessController.replay_to_position` (D-06)
  - `platformdirs` for persistence with `OPENBOARD_PROFILE_DIR` test isolation (D-09)
  - Specific menu IDs throughout `_build_menu_bar()` (D-08)
  - `move_made(old_board, move_kind)` enriched payload (D-02)
- Test count reached 386 (from pre-phase baseline of ~190), exceeding the expected ~386 target.

---

_Verified: 2026-04-29_
_Verifier: Claude (gsd-verifier)_

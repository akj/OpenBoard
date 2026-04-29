---
phase: 01-tech-debt-cleanup
plan: "01"
subsystem: signals
tags:
  - signals
  - blinker
  - move-kind
  - chess
  - python
  - mvc
dependency_graph:
  requires: []
  provides:
    - Game.move_undone forwarder signal (TD-01)
    - Game.move_made enriched payload with old_board and move_kind (TD-02)
    - ChessController.replay_to_position live-stack navigation (TD-03)
    - MoveKind IntFlag enum (D-01)
    - _connect_board_signals canonical forwarder pattern (D-05)
  affects:
    - openboard/models/board_state.py
    - openboard/models/game.py
    - openboard/controllers/chess_controller.py
    - openboard/views/views.py
    - tests/conftest.py
    - tests/test_game.py
    - tests/test_chess_controller.py
    - tests/test_chess_controller_opening_book.py
tech_stack:
  added:
    - openboard/models/move_kind.py (MoveKind IntFlag enum)
  patterns:
    - D-05 canonical forwarder: _connect_board_signals() called from __init__ and new_game()
    - D-02 enriched payload: BoardState emits old_board snapshot, Game computes MoveKind bits post-push
    - D-06 model-routed navigation: ChessController.replay_to_position replaces views._navigate_to_position
key_files:
  created:
    - openboard/models/move_kind.py
  modified:
    - openboard/models/board_state.py
    - openboard/models/game.py
    - openboard/controllers/chess_controller.py
    - openboard/views/views.py
    - tests/conftest.py
    - tests/test_game.py
    - tests/test_chess_controller.py
    - tests/test_chess_controller_opening_book.py
decisions:
  - D-01: MoveKind IntFlag with QUIET/CAPTURE/CASTLE/EN_PASSANT/PROMOTION/CHECK/CHECKMATE bits
  - D-02: Game.move_made payload extended with old_board and move_kind; old_board option (a) — extended BoardState contract
  - D-03: _pending_old_board removed; old_board flows exclusively through BoardState.move_made signal
  - D-04: Game.move_undone forwarder reconnected by Game._connect_board_signals() called in new_game()
  - D-05: _connect_board_signals helper is canonical for ALL future model-controller signal wiring
  - D-06: replay_to_position uses BoardState.make_move/undo_move exclusively; no view-layer board.push
metrics:
  duration: "765m"
  completed_date: "2026-04-29"
  tasks_completed: 3
  files_modified: 8
  files_created: 1
---

# Phase 01 Plan 01: Signal Contract Foundations Summary

Established canonical signal patterns via MoveKind IntFlag enum, enriched Game.move_made payload with old_board snapshot and move_kind bits, Game.move_undone forwarder reconnected on new_game(), and model-routed ChessController.replay_to_position replacing the views._navigate_to_position model-bypass.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add MoveKind enum + canonical fixtures + RED tests | 4447288 | move_kind.py, conftest.py, test_game.py, test_chess_controller.py |
| 2+3 | Implement GREEN + sweep + model-routed navigation | 98e109d | board_state.py, game.py, chess_controller.py, views.py, test updates |

## Decisions Made

### D-01: MoveKind IntFlag Bit Layout
`MoveKind.QUIET = 0` (zero value, composable with `|`). Bits: CAPTURE=1, CASTLE=2, EN_PASSANT=4, PROMOTION=8, CHECK=16, CHECKMATE=32. Multiple bits may be set: a capture-with-check yields `CAPTURE | CHECK`. Subscribers test with `in`: `MoveKind.CAPTURE in move_kind`.

### D-02: old_board Propagation via Extended BoardState Contract (Option a)
BoardState.make_move() now captures `old_board = self._board.copy()` before the push and passes it as a signal kwarg: `self.move_made.send(self, move=move, old_board=old_board)`. Game._on_board_move receives old_board and computes MoveKind bits from POST-push state (CHECK/CHECKMATE) and PRE-push state (CAPTURE/CASTLE/EN_PASSANT). This is "Option (a)" from RESEARCH.md — it extends the BoardState contract rather than computing in the controller.

### D-03: _pending_old_board Removal (14 sites swept)
The controller-side `_pending_old_board` stash is entirely eliminated. All old_board values now flow exclusively through the BoardState.move_made signal. `_format_move_announcement(move, old_board)` now takes old_board as a required parameter. `announce_last_move()` uses a single O(1) `board.copy(); pop()` instead of the O(n) replay loop.

### D-04: Game.move_undone Forwarder (canonical)
`Game.move_undone = Signal()` added. `_on_board_undo` forwards `BoardState.move_undone` to `Game.move_undone`. `_connect_board_signals()` connects all three forwarders (move_made, move_undone, status_changed) and is called from both `__init__` and `new_game()`.

### D-05: Canonical Forwarder Pattern for v1
The `_connect_board_signals()` helper is now the single place where BoardState signals get wired to Game-level forwarders. Future signals (Phase 3a Clock, Phase 4a SoundService) must use this pattern — add the new signal to the helper and let `new_game()` inherit it automatically.

### D-06: replay_to_position Scope (locked per Codex MEDIUM)
`ChessController.replay_to_position(target_index)` operates on the LIVE `Game.board_state.board.move_stack` ONLY. It does not navigate externally-loaded PGN replay state — that is Phase 2a's concern. PGN navigation and the `_in_replay` buffer are separate concerns.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] quiet_check_fen FEN incorrect**
- **Found during:** Task 2 GREEN phase
- **Issue:** The plan's `quiet_check_fen` FEN `rnbqkbnr/ppp2ppp/8/3pp3/2B1P3/8/PPPP1PPP/RNBQK1NR` does NOT deliver check after Qd1-h5. The queen on h5 does not attack the black king on e8 in that position.
- **Fix:** Replaced with `4k3/8/8/8/8/8/PPPP1PPP/RNBQKBNR w KQ - 0 1` where black king on e8 with no blocking pieces IS checked by Qh5+ via the h5-e8 diagonal.
- **Files modified:** tests/conftest.py
- **Commit:** 98e109d

**2. [Rule 3 - Blocking] Tasks 2 and 3 implemented together**
- **Found during:** Task 2 GREEN phase execution
- **Issue:** After updating `_on_model_move` to call `_format_move_announcement(move, old_board)` (Task 2), the existing controller tests immediately broke because `_format_move_announcement` still had the old single-argument signature with `_pending_old_board` fallback.
- **Fix:** Completed the full `_pending_old_board` sweep (Task 3) immediately rather than committing an intermediate broken state. Both tasks are in a single commit (98e109d).
- **Files modified:** chess_controller.py, views.py, test files

## Cross-Plan Traceability

### canonical TD-04 FEN
The fixture `tests/conftest.py::pinned_attacker_fen` is defined here and returns the exact string `4r3/8/8/8/8/8/8/4K3 w - - 0 1`. Plan 03 (TestAnnounceAttackingPieces) must read this fixture without redefining it.

### Replay scope (locked)
`replay_to_position` docstring explicitly states "SCOPE: operates on `Game.board_state.board.move_stack` only. Does NOT navigate PGN-replay state loaded from outside (Phase 2a's concern)."

### Future signal wiring (D-05)
All new signals in Phase 3a (ClockSignals), Phase 4a (SoundService), and Phase 4b (autosave) MUST use the `_connect_board_signals()` pattern — add the signal to the helper, and `new_game()` reconnection is automatic.

## Known Stubs

None — all signal contracts fully implemented and tested.

## Threat Flags

None — this plan is a pure refactor with no new network endpoints, auth paths, file access patterns, or schema changes.

## Self-Check: PASSED

- [x] openboard/models/move_kind.py exists with class MoveKind(enum.IntFlag)
- [x] tests/conftest.py contains pinned_attacker_fen, pre_scholars_mate_fen, quiet_check_fen
- [x] tests/test_game.py contains TestMoveUndoneForwarder
- [x] tests/test_chess_controller.py contains TestMoveMadePayload, TestReplayToPosition, TestOldBoardProvenance, TestPendingOldBoardRemoved
- [x] All 10 plan cohort tests pass (test_game.py::TestMoveUndoneForwarder, test_chess_controller.py::TestMoveMadePayload, TestReplayToPosition, TestOldBoardProvenance, TestPendingOldBoardRemoved)
- [x] All 96 tests in affected files pass
- [x] Full pytest suite: 282 passed, 3 pre-existing failures (wx import + build validation, unrelated)
- [x] ruff check clean for all touched files
- [x] ty check clean for all core model/controller files
- [x] grep -rn "_pending_old_board" openboard/ tests/ — zero hits in production code
- [x] views.py has no board.push() or board_state.move_made.send() calls
- [x] def replay_to_position exists in chess_controller.py
- [x] Commits exist: 4447288 (RED), 98e109d (GREEN)

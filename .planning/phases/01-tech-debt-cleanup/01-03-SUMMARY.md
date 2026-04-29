---
phase: 01-tech-debt-cleanup
plan: "03"
subsystem: ui
tags: [chess, python-chess, wxpython, bitboards, keyboard-config, accessibility]

requires:
  - phase: 01-tech-debt-cleanup plan 01
    provides: "Game.move_made payload with old_board+move_kind; canonical pinned_attacker_fen fixture; ChessController._format_move_announcement(move, old_board)"

provides:
  - "BoardState.board_ref: live read-only chess.Board property with verbatim MUST-NOT-mutate docstring"
  - "announce_attacking_pieces rewritten via chess.Board.attackers() bitboard call (O(1) per color)"
  - "ChessFrame menu bar: every EVT_MENU bind uses a captured specific wx.MenuItem.GetId()"
  - "Book Hint menu item: no \\tB accelerator; B continues via EVT_CHAR_HOOK"
  - "Behavioral + source-grep tests for menu binding hygiene (test_views_menus.py)"

affects:
  - "01-04 (depends on views.py menu changes and tests/conftest.py)"
  - "01-05 (board_ref adoption audit documented for traceability)"

tech-stack:
  added: []
  patterns:
    - "capture-then-bind: each wx.MenuItem captured in named variable; Bind uses item.GetId() (D-08)"
    - "board_ref property: live chess.Board reference for read-only controller paths (D-18)"
    - "bitboard attacker query: chess.Board.attackers(color, square) union (D-16)"
    - "wx.EvtHandler.Bind(self, ...) explicit call for patchable test seam in _build_menu_bar"
    - "session-scoped wx.App fixture for headless wx tests without Xvfb"

key-files:
  created:
    - tests/test_views_menus.py
  modified:
    - openboard/models/board_state.py
    - openboard/controllers/chess_controller.py
    - openboard/views/views.py

key-decisions:
  - "D-08: every wx.EVT_MENU bind uses a captured wx.MenuItem.GetId() — zero wx.ID_ANY binds remain"
  - "D-16: announce_attacking_pieces rewritten via chess.Board.attackers() bitboard call; fixes Bug #3 + Performance #2"
  - "D-17: Book Hint menu accelerator \\tB removed; B dispatches via EVT_CHAR_HOOK only (single dispatch path)"
  - "D-18: BoardState.board_ref returns live self._board for read-only access; .board snapshot semantics retained"
  - "wx.EvtHandler.Bind(self, ...) used explicitly in _build_menu_bar so patch.object(wx.EvtHandler, 'Bind') intercepts calls during behavioral test on MagicMock"
  - "Session-scoped wx.App(False) fixture added to test_views_menus.py (not conftest.py) to keep conftest.py verifies_only constraint"

patterns-established:
  - "Pattern: _build_menu_bar() seam — extracting menu construction + binding into a standalone method enables monkeypatched behavioral testing without wx.App in test function scope"
  - "Pattern: board_ref adoption — read-only controller paths should prefer board_ref over board to avoid per-call 64-square copy overhead"

requirements-completed:
  - TD-04
  - TD-05
  - TD-09
  - TD-13
  - TD-14

duration: 45min
completed: 2026-04-28
---

# Phase 1 Plan 03: Menu Hygiene, Pinned-Attacker Fix, and board_ref Summary

**announce_attacking_pieces rewritten via chess.Board.attackers() bitboard O(1) call; all wx.EVT_MENU binds now use specific item IDs; Book Hint accelerator dropped; BoardState.board_ref live reference added with read-only contract**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-04-28
- **Completed:** 2026-04-28
- **Tasks:** 3 (Task 1: RED audit; Task 2: GREEN TD-04/TD-13; Task 3: GREEN TD-05/TD-09)
- **Files modified:** 4

## Accomplishments

- Fixed pinned-attacker miss in announce_attacking_pieces: replaced O(64 × legal_moves) loop with chess.Board.attackers() bitboard union, which correctly returns pseudo-attackers regardless of side to move (TD-04 / Bug #3)
- Added BoardState.board_ref property with verbatim MUST-NOT-mutate docstring, eliminating per-call 64-square board.copy() in read-only paths (TD-13 / Performance #3)
- Converted all 13 wx.EVT_MENU binds from wx.ID_ANY to specific captured item IDs via _build_menu_bar() refactor (TD-05 / Bug #4)
- Dropped \tB accelerator from Book Hint menu item; B continues via EVT_CHAR_HOOK -> KeyAction.REQUEST_BOOK_HINT single dispatch path (TD-09)

## Task Commits

Each task was committed atomically:

1. **Task 1: RED audit** — `e106fd5` (test) [pre-committed on base branch]
2. **Task 2: board_ref + announce_attacking_pieces GREEN** — `f8750b2` (feat)
3. **Task 3: capture-then-bind menus + Book Hint accelerator GREEN** — `237c2d4` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `openboard/models/board_state.py` — added board_ref property returning live self._board; board snapshot property unchanged
- `openboard/controllers/chess_controller.py` — announce_attacking_pieces rewritten via board.attackers() + board_ref adoption
- `openboard/views/views.py` — _build_menu_bar() extracted from __init__; all 13 EVT_MENU binds use specific item IDs; \tB removed from Book Hint label
- `tests/test_views_menus.py` — RED tests for TD-05/TD-09 (4 tests); added session-scoped wx.App fixture for headless wx constructor support

## wx.ID_ANY Sites Converted (TD-05)

13 EVT_MENU binds converted from wx.ID_ANY to specific captured IDs:

| Menu | Item | Captured Variable | Handler |
|------|------|-------------------|---------|
| File | Load PGN | pgn_item | on_load_pgn |
| Game | Human vs Human | human_vs_human_item | on_new_human_vs_human |
| Game | Human vs Computer | human_vs_computer_item | on_new_human_vs_computer |
| Game | Computer vs Computer | computer_vs_computer_item | on_new_computer_vs_computer |
| Game | Difficulty Info | difficulty_info_item | on_difficulty_info |
| Options | Toggle Announce Mode | announce_mode_item | lambda: controller.toggle_announce_mode() |
| Engine | Install Stockfish | install_stockfish_item | on_install_stockfish |
| Engine | Update Stockfish | update_stockfish_item | on_update_stockfish |
| Engine | Check Engine Status | engine_status_item | on_check_engine_status |
| Book | Load Opening Book | load_book_item | on_load_opening_book |
| Book | Unload Opening Book | unload_book_item | on_unload_opening_book |
| Book | Book Hint | book_hint_item | on_book_hint |
| Book | Check Book Moves | check_book_item | on_check_book_moves |

Stock IDs NOT converted (legitimate): wx.ID_OPEN (Load FEN), wx.ID_EXIT (Exit).

The single offending `id=wx.ID_ANY` bind (pre-fix line 250) has been eliminated.

## board_ref Adoption Audit (Codex MEDIUM, TD-13)

**Converted (1 site):**
- `announce_attacking_pieces` — reads board.attackers(), board.piece_at(); pure read; high-frequency query path

**Not converted — snapshot semantics required:**
- `announce_last_move` (line 524) — does `board.copy(); board.pop()` to reconstruct pre-push position; mutation is intentional
- `_emit_board_update` (line 552) — sends a snapshot board to the view for rendering; view stores it and reads it later, so isolation is required

**Not converted — read-only but deferred:**
- `_on_model_move` line 102 — `is_game_over()` check; read-only but low-frequency (once per move)
- `replay_to_position` line 402 — `move_stack` access; read-only; deferred to Phase 1 Plan 05 adoption audit
- `announce_legal_moves` line 451 — `piece_at`, `legal_moves`; deferred to Plan 05
- `_announce_square` line 560 — `piece_at`; deferred to Plan 05
- `_format_move_announcement` line 585 — passed to format helpers; deferred to Plan 05
- `_format_verbose_legal_moves` line 746 — `piece_at`, `is_en_passant`, etc.; deferred to Plan 05
- `_can_select_square` line 883 — `piece_at`, `board.turn`; deferred to Plan 05
- `_get_square_description` line 907 — `piece_at`; deferred to Plan 05

These deferred sites are documented for Plan 05's traceability doc.

## Menu-Construction Seam

Seam name: `_build_menu_bar`. Called from `ChessFrame.__init__`. The behavioral test calls `ChessFrame._build_menu_bar(frame_mock)`.

The method uses `wx.EvtHandler.Bind(self, ...)` explicitly (not `self.Bind(...)`) so that `patch.object(wx.EvtHandler, "Bind", recording_bind)` intercepts the calls even when `self` is a `MagicMock(spec=ChessFrame)`.

A session-scoped `wx_app_session` fixture was added to `test_views_menus.py` to create `wx.App(False)` once per test session, enabling `wx.MenuBar()` and `wx.Menu()` constructors to run in headless CI without Xvfb.

## Canonical Fixture Verification (Codex HIGH cross-plan)

Fixture `pinned_attacker_fen` confirmed present in `tests/conftest.py` with FEN `4r3/8/8/8/8/8/8/4K3 w - - 0 1` — sourced from Plan 01, NOT redefined here. Single source of truth preserved.

## TD-N → Test Mapping (for Plan 05 traceability)

| Requirement | Primary Test | Secondary/Guardrail |
|-------------|-------------|---------------------|
| TD-04 | tests/test_chess_controller.py::TestAnnounceAttackingPieces::test_announce_attacking_pieces_includes_pinned_attacker | — |
| TD-05 | tests/test_views_menus.py::TestMenuBindingHygieneBehavioral::test_bind_records_specific_ids_for_menu_items (BEHAVIORAL) | ::TestMenuBindingHygieneSourceGrep::test_no_evt_menu_bound_to_id_any_source_grep ([guardrail]) |
| TD-09 | tests/test_views_menus.py::TestBookHintAccelerator::test_book_hint_menu_no_accelerator | — |
| TD-13 (board_ref) | tests/test_board_state_terminal.py::TestBoardRefProperty (3 tests, including docstring contract) | — |
| TD-13 (adoption) | tests/test_chess_controller.py::TestAnnounceAttackingPieces::test_announce_attacking_pieces_uses_board_ref | — |

## Note for Plan 04

This plan touches `tests/conftest.py` only via `<verifies_only>` — no new fixtures were added to conftest.py. Plan 04 is free to add `isolated_profile` and other fixtures without conflict.

The wx_app_session fixture lives in `tests/test_views_menus.py` (module-scoped to that file) rather than conftest.py to preserve the conftest.py verifies_only constraint.

## Decisions Made

- D-08: Capture-then-bind pattern: each menu item's ID captured at construction time and passed to Bind. GetMenuItems()[n] index approach replaced with named variable approach for clarity and correctness.
- D-16: chess.Board.attackers() bitboard union chosen over legal_moves-filtered loop — attackers() returns pseudo-attackers (including pinned pieces) regardless of side to move, which is the correct semantic for "what attacks this square?".
- D-17: Accelerator removed from menu label only; EVT_CHAR_HOOK path for B key unchanged.
- D-18: board_ref property approach chosen over proxy/wrapper for Phase 1 scope; MUST-NOT-mutate contract documented verbatim in docstring per Codex MEDIUM.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added session-scoped wx.App fixture to test_views_menus.py**
- **Found during:** Task 3 (GREEN for TD-05/TD-09)
- **Issue:** The behavioral test `test_bind_records_specific_ids_for_menu_items` calls `ChessFrame._build_menu_bar(frame_mock)` which internally calls `wx.MenuBar()` and `wx.Menu()`. These wx constructors raise `wx.PyNoAppError` when no `wx.App` exists, causing the test to fail at runtime.
- **Fix:** Added `@pytest.fixture(scope="session", autouse=True) wx_app_session()` to `test_views_menus.py` that creates `wx.App(False)` once for the entire test session. This is the minimal intervention: session-scoped (not function-scoped) to match wx's singleton App model; `False` parameter = no stdout redirect; headless (no main loop started).
- **Files modified:** tests/test_views_menus.py
- **Verification:** All 4 tests in test_views_menus.py pass; full 337-test suite passes
- **Committed in:** 237c2d4 (Task 3 commit)

**2. [Rule 2 - Missing Critical] Used wx.EvtHandler.Bind(self, ...) explicitly in _build_menu_bar**
- **Found during:** Task 3 analysis — test patch mechanics
- **Issue:** `patch.object(wx.EvtHandler, "Bind", recording_bind)` patches the class method on `wx.EvtHandler`. When `_build_menu_bar` is called with `self=MagicMock(spec=ChessFrame)`, `self.Bind(...)` dispatches through `MagicMock.__getattr__`, bypassing the patched class method entirely — resulting in no binds being recorded.
- **Fix:** Use `wx.EvtHandler.Bind(self, event_type, handler, id=item_id)` explicitly in `_build_menu_bar`. This calls the patched function directly, ensuring `recording_bind` intercepts the calls both in tests (MagicMock self) and in production (real ChessFrame self). Production behavior is identical: `wx.EvtHandler.Bind(real_frame, ...)` is equivalent to `real_frame.Bind(...)`.
- **Files modified:** openboard/views/views.py
- **Verification:** Behavioral test records 13 EVT_MENU binds; none have wx.ID_ANY
- **Committed in:** 237c2d4 (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 2 - missing critical test infrastructure)
**Impact on plan:** Both fixes were required for the behavioral test to function correctly. No scope creep; the test assertions are unchanged.

## Issues Encountered

None beyond the two deviations documented above.

## Known Stubs

None — all plan objectives fully implemented and wired.

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes introduced. The threat model from the plan (T-03-01, T-03-02, T-03-03) is mitigated as specified.

## Next Phase Readiness

- Plan 04 (Sound + Visual accessibility) can proceed; views.py menu changes are stable
- Plan 05 (board_ref adoption audit) has the deferred site list documented in this summary
- TD-04, TD-05, TD-09, TD-13, TD-14 regression tests are in place and green

---
*Phase: 01-tech-debt-cleanup*
*Completed: 2026-04-28*

## Self-Check: PASSED

All created files found. All commits found (f8750b2, 237c2d4). All key artifacts verified.

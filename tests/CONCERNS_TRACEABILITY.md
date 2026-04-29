# Phase 1 — CONCERNS Traceability

**Audit date:** 2026-04-29
**Phase:** 01-tech-debt-cleanup
**Total TD requirements:** 14 (TD-01..TD-14)

Every regression test below has a docstring containing the literal `TD-N` token per
CONTEXT.md D-24. This file is verified by
`tests/test_downloader.py::TestConcernsTraceability::test_concerns_traceability_doc_exists_and_lists_all_td`.

## Mapping

Locked format per Codex LOW: `| REQ-ID | Concern | Test path | Test name |`. One row per
TD-XX (14 rows total).

| REQ-ID | Concern | Test path | Test name |
|--------|---------|-----------|-----------|
| TD-01 | Bug #1: move_undone signal lost after new_game() | tests/test_game.py | TestMoveUndoneForwarder::test_move_undone_signal_reconnects_after_new_game |
| TD-02 | D-02 / Pitfall 1: MoveKind from POST-push board state | tests/test_chess_controller.py | TestMoveMadePayload::test_move_made_payload_includes_old_board_and_move_kind_for_capture_with_check |
| TD-03 | Bug #2 + Fragile #3: _navigate_to_position bypass + _pending_old_board state | tests/test_chess_controller.py | TestReplayToPosition::test_replay_to_position_uses_make_move + TestPendingOldBoardRemoved::test_pending_old_board_removed |
| TD-04 | Bug #3 + Performance #2: pinned attackers / O(64×legal_moves) — uses canonical fixture `pinned_attacker_fen` (FEN `4r3/8/8/8/8/8/8/4K3 w - - 0 1`) defined in tests/conftest.py per Plan 01 | tests/test_chess_controller.py | TestAnnounceAttackingPieces::test_announce_attacking_pieces_includes_pinned_attacker |
| TD-05 | Bug #4: wx.ID_ANY menu bind fallback | tests/test_views_menus.py | TestMenuBindingHygieneBehavioral::test_bind_records_specific_ids_for_menu_items (primary) + TestMenuBindingHygieneSourceGrep::test_no_evt_menu_bound_to_id_any_source_grep ([guardrail]) |
| TD-06 | Tech Debt: Dead `_simple` API surface | tests/test_engine_adapter.py | TestSimpleApiRemoved::test_simple_api_removed |
| TD-07 | Tech Debt: Duplicate difficulty-resolution logic | tests/test_game_async.py | TestResolveMoveContextExtracted::test_resolve_move_context_extracted |
| TD-08 | Tech Debt: Sync request_computer_move dead in production | tests/test_game.py | TestSyncRequestComputerMoveRemoved::test_request_computer_move_sync_removed |
| TD-09 | Tech Debt: `B` keyboard shortcut conflict | tests/test_views_menus.py | TestBookHintAccelerator::test_book_hint_menu_no_accelerator |
| TD-10 | Tech Debt: player_color backward-compat attr | tests/test_game.py | TestPlayerColorRemoved::test_player_color_removed |
| TD-11 | Tech Debt: Unused exception types pruned + raise sites wired | tests/test_exceptions.py + tests/test_engine_adapter.py + tests/test_downloader.py + tests/test_stockfish_manager.py | TestPrunedExceptionTypes::* + TestExceptionWiring::test_engine_timeout_error_raised_on_compute_timeout + ::test_engine_process_error_raised_on_startup_failure + TestDownloadFileExceptionWiring::* + TestStockfishManagerExceptionBubbleUp::* |
| TD-12 | Security #4: cwd-relative persistence paths + startup ordering | tests/test_paths.py + tests/test_migration.py + tests/test_settings.py + tests/test_views_startup_ordering.py | TestPathsModule::* + TestLegacyConfigJsonMigration::* + TestLegacyKeyboardConfigJsonMigration::* + TestEnginesDirMigrationConditional::* + TestMigrationIdempotency::* + TestEnginesDirViaPaths::test_engines_dir_resolves_via_paths + TestStartupOrdering::test_import_views_does_not_initialize_settings + ::test_import_views_does_not_trigger_migration |
| TD-13 | Performance #2/#3 + Security #1/#2/#3 + Fragile #3 | tests/test_chess_controller.py + tests/test_board_state_terminal.py + tests/test_downloader_security.py | TestAnnounceAttackingPieces + TestBoardRefProperty::* + TestSSLContext + TestSHA256Verification + TestZipPathTraversalGuard + TestPendingOldBoardRemoved |
| TD-14 | Test discipline final audit | tests/CONCERNS_TRACEABILITY.md (this file) | tests/test_downloader.py::TestConcernsTraceability::test_concerns_traceability_doc_exists_and_lists_all_td |

## TD Coverage Bullet List

Every TD requirement has at least one regression test as required by D-23 / D-24:

- TD-01: tests/test_game.py::TestMoveUndoneForwarder
- TD-02: tests/test_chess_controller.py::TestMoveMadePayload
- TD-03: tests/test_chess_controller.py::TestReplayToPosition + TestPendingOldBoardRemoved
- TD-04: tests/test_chess_controller.py::TestAnnounceAttackingPieces (uses canonical fixture `pinned_attacker_fen`)
- TD-05: tests/test_views_menus.py::TestMenuBindingHygieneBehavioral (primary) + TestMenuBindingHygieneSourceGrep ([guardrail])
- TD-06: tests/test_engine_adapter.py::TestSimpleApiRemoved
- TD-07: tests/test_game_async.py::TestResolveMoveContextExtracted
- TD-08: tests/test_game.py::TestSyncRequestComputerMoveRemoved
- TD-09: tests/test_views_menus.py::TestBookHintAccelerator
- TD-10: tests/test_game.py::TestPlayerColorRemoved
- TD-11: tests/test_exceptions.py::TestPrunedExceptionTypes + TestKeptExceptionTypes; tests/test_engine_adapter.py::TestExceptionWiring; tests/test_downloader.py::TestDownloadFileExceptionWiring; tests/test_stockfish_manager.py::TestStockfishManagerExceptionBubbleUp
- TD-12: tests/test_paths.py + tests/test_migration.py + tests/test_settings.py::TestEnginesDirViaPaths + tests/test_views_startup_ordering.py
- TD-13: tests/test_board_state_terminal.py::TestBoardRefProperty + tests/test_downloader_security.py (3 classes) + (TD-04, TD-03 cross-references)
- TD-14: tests/CONCERNS_TRACEABILITY.md (this file)

## Validation

Per VALIDATION.md row 1-05-05, this file is verified by:

```bash
test -f tests/CONCERNS_TRACEABILITY.md
grep -c "^- TD-" tests/CONCERNS_TRACEABILITY.md   # ≥ 14
```

---

*Audit produced by Plan 05 (D-26 Plan 5 deliverable) on completion of Phase 1.*

---
phase: 1
slug: tech-debt-cleanup
status: signed-off
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-27
signed_off: 2026-04-27
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.1+ + pytest-cov 7.0.0+ + pytest-asyncio 1.3.0+ |
| **Config file** | `pyproject.toml` (no `[tool.pytest.ini_options]` block — uses defaults; tests live in `tests/` per pytest auto-discovery) |
| **Quick run command** | `uv run python -m pytest tests/ -v --tb=short -x` |
| **Full suite command** | `uv run python -m pytest -v --tb=short` |
| **Estimated runtime** | ~30-60 seconds (current baseline) |

---

## Sampling Rate

- **After every task commit:** Run `uv run python -m pytest tests/test_<touched_module>.py -x` (≤10 s)
- **After every plan wave:** Run `uv run python -m pytest -v --tb=short` (full suite; ~30-60 s)
- **Before `/gsd-verify-work`:** Full suite green AND `uv run ruff check .` AND `uv run python -m ty check`
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | TD-01 | — | move_undone fires after Game.new_game() | unit | `uv run python -m pytest tests/test_game.py::test_move_undone_signal_reconnects_after_new_game -x` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | TD-02 | — | Game.move_made payload carries old_board + move_kind IntFlag | unit | `uv run python -m pytest tests/test_chess_controller.py -k "move_made_payload or move_kind" -x` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | TD-02 | — | MoveKind.CHECK computed from POST-push board.is_check() | unit | `uv run python -m pytest tests/test_chess_controller.py -k "move_kind_check_post_push" -x` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 1 | TD-03 | — | replay_to_position uses BoardState.make_move/undo_move | unit | `uv run python -m pytest tests/test_chess_controller.py::test_replay_to_position_uses_make_move -x` | ❌ W0 | ⬜ pending |
| 1-01-05 | 01 | 1 | TD-03 | — | _pending_old_board references absent (meta-test via inspect.getsource) | unit | `uv run python -m pytest tests/test_chess_controller.py::test_pending_old_board_removed -x` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 2 | TD-06 | — | EngineAdapter._simple* methods removed | unit | `uv run python -m pytest tests/test_engine_adapter.py::test_simple_api_removed -x` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 2 | TD-07 | — | Game._resolve_move_context() helper extracted | unit | `uv run python -m pytest tests/test_game_async.py::test_resolve_move_context_extracted -x` | ❌ W0 | ⬜ pending |
| 1-02-03 | 02 | 2 | TD-08 | — | Sync Game.request_computer_move removed; tests use async path | unit | `uv run python -m pytest tests/test_game_async.py -x` | ⚠ Partial | ⬜ pending |
| 1-02-04 | 02 | 2 | TD-10 | — | Game.player_color attribute does not exist | unit | `uv run python -m pytest tests/test_game.py::test_player_color_removed -x` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 2 | TD-04 | — | announce_attacking_pieces names pinned attackers | unit | `uv run python -m pytest tests/test_chess_controller.py::test_announce_attacking_pieces_includes_pinned_attacker -x` | ❌ W0 | ⬜ pending |
| 1-03-02 | 03 | 2 | TD-05 | — | No EVT_MENU bind uses wx.ID_ANY | unit (introspection) | `uv run python -m pytest tests/test_views_menus.py -x` | ❌ W0 (NEW file) | ⬜ pending |
| 1-03-03 | 03 | 2 | TD-09 | — | EVT_CHAR_HOOK B dispatches to request_book_hint AND menu lacks `\tB` accelerator | unit | `uv run python -m pytest tests/test_views_menus.py::test_book_hint_no_accelerator -x` | ❌ W0 | ⬜ pending |
| 1-03-04 | 03 | 2 | TD-13 | — | BoardState.board_ref returns live _board reference | unit | `uv run python -m pytest tests/test_board_state_terminal.py::test_board_ref_returns_live_reference -x` | ❌ W0 | ⬜ pending |
| 1-04-01 | 04 | 3 | TD-12 | — | paths.py helpers honor OPENBOARD_PROFILE_DIR | unit | `uv run python -m pytest tests/test_paths.py -x` | ❌ W0 (NEW file) | ⬜ pending |
| 1-04-02 | 04 | 3 | TD-12 / D-10 | — | One-shot migration is idempotent | unit | `uv run python -m pytest tests/test_migration.py -x` | ❌ W0 (NEW file) | ⬜ pending |
| 1-04-03 | 04 | 3 | TD-12 | — | EngineSettings.engines_dir resolves via paths.engines_dir() | unit | `uv run python -m pytest tests/test_settings.py -k "engines_dir" -x` | ❌ W0 | ⬜ pending |
| 1-04-04 | 04 | 3 | TD-13 / D-21 | T-04-V9 | urlopen calls pass context=ssl.create_default_context() | unit | `uv run python -m pytest tests/test_downloader_security.py::test_download_uses_ssl_context -x` | ❌ W0 (NEW file) | ⬜ pending |
| 1-04-05 | 04 | 3 | TD-13 / D-21 | T-04-V12 | extract_zip rejects path traversal | unit | `uv run python -m pytest tests/test_downloader_security.py::test_extract_zip_rejects_path_traversal -x` | ❌ W0 | ⬜ pending |
| 1-04-06 | 04 | 3 | TD-13 / D-21 | T-04-V6 | download_file raises DownloadError on SHA-256 mismatch when sha provided | unit | `uv run python -m pytest tests/test_downloader_security.py::test_download_sha256_mismatch_raises -x` | ❌ W0 | ⬜ pending |
| 1-04-07 | 04 | 3 | TD-13 / D-21 | T-04-V6 | download_file logs WARNING when expected_sha256 is None | unit | `uv run python -m pytest tests/test_downloader_security.py::test_download_warns_when_no_sha256 -x` | ❌ W0 | ⬜ pending |
| 1-05-01 | 05 | 4 | TD-11 / D-19 | — | EngineTimeoutError raised on engine timeout | unit | `uv run python -m pytest tests/test_engine_adapter.py -k "engine_timeout_error" -x` | ❌ W0 | ⬜ pending |
| 1-05-02 | 05 | 4 | TD-11 / D-19 | — | EngineProcessError raised on engine startup failure | unit | `uv run python -m pytest tests/test_engine_adapter.py -k "engine_process_error" -x` | ❌ W0 | ⬜ pending |
| 1-05-03 | 05 | 4 | TD-11 / D-19 | — | DownloadError / NetworkError raised at download/network boundaries | unit | `uv run python -m pytest tests/test_downloader.py tests/test_stockfish_manager.py -x` | ⚠ Partial | ⬜ pending |
| 1-05-04 | 05 | 4 | TD-11 / D-19 | — | Pruned exception types unimportable | unit | `uv run python -m pytest tests/test_exceptions.py::test_pruned_exception_types_unimportable -x` | ❌ W0 | ⬜ pending |
| 1-05-05 | 05 | 4 | TD-14 | — | tests/CONCERNS_TRACEABILITY.md exists and lists every TD-N → test file → test name | meta-doc | `test -f tests/CONCERNS_TRACEABILITY.md && grep -c "^- TD-" tests/CONCERNS_TRACEABILITY.md` (≥14) | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

The following test files / fixtures need to be created **before** the implementing tasks land (per CONTEXT.md D-23 test-first discipline):

- [ ] `tests/test_paths.py` — covers TD-12 (paths helpers + `OPENBOARD_PROFILE_DIR` override)
- [ ] `tests/test_migration.py` — covers D-10 (one-shot migration helper)
- [ ] `tests/test_views_menus.py` — covers TD-05, TD-09 (menu binding hygiene; introspection-based per RESEARCH.md Open Q1)
- [ ] `tests/test_downloader.py` — covers D-19 (`DownloadError` / `NetworkError` raise paths)
- [ ] `tests/test_downloader_security.py` — covers D-22 (SSL context, SHA-256, ZIP traversal — REQUIRED to be a NEW file per CONTEXT.md D-25)
- [ ] `tests/conftest.py` — add `isolated_profile` fixture for `OPENBOARD_PROFILE_DIR` test isolation; add `pinned_attacker_fen` and `pre_scholars_mate_fen` fixtures
- [ ] `tests/CONCERNS_TRACEABILITY.md` — Plan 5 deliverable; audit artifact, not a test file
- [ ] `pyproject.toml` — add `platformdirs>=4.3.8` to `[project.dependencies]`

**Existing test files extended (not new):**
- `tests/test_game.py` — TD-01, TD-08, TD-10
- `tests/test_chess_controller.py` — TD-02, TD-03, TD-04
- `tests/test_chess_controller_opening_book.py` — `_pending_old_board` removal sweep (D-03), TD-08 sync-test migration
- `tests/test_board_state_terminal.py` — TD-13 board_ref test
- `tests/test_engine_adapter.py` — TD-06 `_simple` removal; D-19 `EngineTimeoutError` / `EngineProcessError`
- `tests/test_game_async.py` — TD-07 helper extracted; TD-08 migrated tests
- `tests/test_settings.py` — TD-12 `engines_dir` resolved via paths
- `tests/test_exceptions.py` — TD-11 prune updates
- `tests/test_game_mode.py` — TD-10 line 199 `player_color` reference must change
- `tests/test_game_opening_book_integration.py` — TD-08 sync-test migration

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Wx menu fires correctly via real keyboard input on each platform after TD-05 fix | TD-05 | Headless `wxPython` testing on macOS / Windows requires platform-specific display servers; CI is currently Linux-only with no `Xvfb` (per RESEARCH.md Open Q1). Introspection-based assertion in `test_views_menus.py` covers binding correctness; manual smoke test confirms real-keystroke behavior. | Launch app on each platform; click File → Load PGN; verify only that menu fires; click Help → About; verify only that menu fires (no double-fire of Load PGN). |
| Migration helper runs cleanly on a real installation that has legacy `cwd`-relative files | TD-12 / D-10 | Migration is one-shot and depends on existing legacy files; CI runners start with a clean profile and have no legacy files to migrate. Idempotency test covers re-runs; manual test confirms first-time migration. | On a system with existing `~/projects/openboard/config.json` and `~/projects/openboard/keyboard_config.json`, launch `uv run openboard` from `~/projects/openboard`; confirm `INFO: Migrated <legacy> → <new>` log lines for each file; confirm files now under `platformdirs.user_config_dir("openboard")`. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** signed off 2026-04-27 (gsd-plan-checker: PASSED dimensions 8a/8b/8c/8d/8e). Plans embed Wave 0 RED tests in each Task 1; existing tasks all carry `<automated>` verify commands; sampling continuity holds across Waves 1-4; no watch-mode flags; feedback latency under the 60s budget per `pytest -x` invocations.

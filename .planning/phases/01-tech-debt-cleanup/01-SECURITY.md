---
phase: 1
slug: tech-debt-cleanup
status: verified
threats_open: 0
asvs_level: 1
created: 2026-04-29
---

# Phase 1 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Phase 1 (tech-debt-cleanup) spans five plans (01-01 through 01-05). All STRIDE
> threats from each plan's `<threat_model>` block were verified by
> `gsd-security-auditor` against implementation and regression tests on
> 2026-04-29. ASVS L1 categories activated: V6, V9, V12, V14 (all in Plan 04).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| user keyboard → wxPython EVT_MENU dispatch | Each menu item bound to its specific `wx.MenuItem.GetId()` (Bug #4 root cause closed). | UI events only — no data sensitivity |
| local filesystem (cwd) → user data dirs (platformdirs) | One-shot migration on first launch via `shutil.move` in `openboard/config/migration.py`. After migration the cwd is no longer trusted. | User config files (`config.json`, keyboard config, autosave, engines/) |
| Network (GitHub releases / arbitrary HTTPS) → local install dir | `openboard/engine/downloader.py` receives bytes over HTTPS (TLS verified), optionally validates SHA-256, validates ZIP archive members against path traversal, writes to `engines_dir()`. | Stockfish binary archive (untrusted) |
| Compressed archive (ZIP) → local filesystem | `extract_zip` is the chokepoint where untrusted filenames could escape `extract_to` via `..` path components. | Archive members |
| `__import__` → settings singleton | Pre-fix the singleton was initialized at module-top in `views.py:31`, which defeated migration. Post-fix the boundary is `main()` only — `_settings` initialization happens *after* `migrate_legacy_paths()`. | Settings object |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-01-01 | Tampering | `Game.move_made` payload extra kwargs (`old_board`, `move_kind`) | accept | blinker subscribers ignore unknown kwargs by contract; locked by `tests/test_chess_controller.py::test_broad_subscriber_signature_compatible` (line 791). | closed |
| T-01-02 | Information Disclosure | `old_board` snapshot leak via signal | accept | Pre-push board state already exposed via `BoardState.board`; passing it as a signal kwarg is no broader than the status quo. No PII or secrets pass through `chess.Board`. | closed |
| T-01-03 | Denial of Service | O(n) replay fallback in `_format_move_announcement` | mitigate | Replay branch deleted; signal always carries `old_board`. `openboard/controllers/chess_controller.py:575-590` has no replay path. Verified by `tests/test_chess_controller.py::TestOldBoardProvenance` (line 852). | closed |
| T-02-01 | Tampering | Removed `_simple` API as legacy attack surface | accept | `_simple` methods deleted (zero hits in `openboard/`); locked by `tests/test_engine_adapter.py::TestSimpleApiRemoved` (line 75). | closed |
| T-02-02 | Repudiation | `_resolve_move_context` centralization | accept | Helper at `openboard/models/game.py:330`, called at `:412`. Side-effect-free; locked by `tests/test_game_async.py::TestResolveMoveContextExtracted` (line 249, including `is_pure` assertion). | closed |
| T-02-03 | Denial of Service | `engine_adapter=None` silent no-op | mitigate | Three explicit `raise EngineError(...)` sites at `openboard/models/game.py:286, 301, 428`. Verified by `tests/test_game_async.py::test_request_computer_move_async_raises_when_no_engine_and_no_book` (line 319). | closed |
| T-03-01 | Spoofing/Tampering | `on_load_pgn` invoked by all menu events (Bug #4) | mitigate | All `EVT_MENU` binds use specific IDs at `openboard/views/views.py:279-300`. Locked by `tests/test_views_menus.py::TestMenuBindingHygieneBehavioral::test_bind_records_specific_ids_for_menu_items` (line 35). | closed |
| T-03-02 | Denial of Service | O(64 × legal_moves) loop in `announce_attacking_pieces` | mitigate | Replaced with `chess.Board.attackers()` bitboard union at `openboard/controllers/chess_controller.py:499-500`. Verified by `test_announce_attacking_pieces_includes_pinned_attacker` (canonical pinned-attacker FEN fixture). | closed |
| T-03-03 | Tampering | `BoardState.board_ref` returns live reference | accept | Verbatim "MUST NOT mutate" docstring at `openboard/models/board_state.py:39-47` documents the contract (push/pop/set_fen explicitly named). Snapshot `.board` API retained for callers that need mutation safety. Locked by `test_board_ref_docstring_contains_readonly_contract`. | closed |
| T-04-01 | Tampering (V9) | MITM on Stockfish download | mitigate | `SSL_CONTEXT = ssl.create_default_context()` at `downloader.py:21`. All three `urlopen()` calls (`:72, :151, :297`) pass `context=SSL_CONTEXT`. Locked by `tests/test_downloader_security.py::TestSSLContext::test_download_uses_ssl_context` (line 15) plus an automated invariant counting urlopen calls vs context-bearing calls. | closed |
| T-04-02 | Tampering (V6) | Tampered binary at rest in transit (no integrity check) | mitigate | `download_file(expected_sha256=...)` raises `DownloadError` and unlinks the partial file on mismatch (`downloader.py:166-180`). When `expected_sha256 is None`, logs DEBUG (Codex MEDIUM revision — not WARN) at `:178`; `StockfishManager.__init__` logs a single startup INFO at `stockfish_manager.py:48-52`. Locked by `test_download_sha256_mismatch_raises`, `test_download_logs_debug_when_no_sha256`, `test_stockfish_manager_logs_single_startup_info_on_no_checksum_source`. | closed |
| T-04-03 | Tampering / EoP (V12) | ZIP slip / path traversal | mitigate | Per-member `os.path.commonpath([str(extract_root), str(target)]) != str(extract_root)` guard at `downloader.py:208-219`; raises `DownloadError`. Locked by `tests/test_downloader_security.py::TestZipPathTraversalGuard::test_extract_zip_rejects_path_traversal`, which asserts the malicious file is **not** created outside `extract_to`. | closed |
| T-04-04 | Tampering (V14) | `config.json` from cwd loaded as user config | mitigate | Settings, keyboard config, autosave, engines all resolve via `paths.py` under `user_config_dir`/`user_data_dir`/`user_state_dir`. `_engines_dir_factory` used at `settings.py:46`. One-shot migration in `migration.py:69-86`. Filename preserved as `config.json` per Codex HIGH at `paths.py:100`. | closed |
| T-04-05 | Denial of Service (V12) | Zip bomb (extreme decompression ratio) | accept | Out of Phase 1 scope per CONTEXT.md. Future hardening could enforce `ZipInfo.file_size` bounds. Single-user desktop, archive source is GitHub Stockfish releases — low practical risk. See Accepted Risks Log. | closed |
| T-04-06 | Test pollution | Shared `_settings` singleton or stale `OPENBOARD_PROFILE_DIR` | mitigate | `isolated_profile` fixture uses `monkeypatch.setenv` (auto-clean) at `tests/conftest.py:71-79`. `_settings` touched only via lazy initialization post-migration; tests construct `EngineSettings()` fresh per test. | closed |
| T-04-07 | Tampering / Repudiation (V14) | Settings singleton initialized at module-top | mitigate | Module-top `settings = get_settings()` removed from `views.py`. `main()` calls `migrate_legacy_paths()` (line 671) BEFORE the first `get_settings()` (line 674). Locked by `tests/test_views_startup_ordering.py` (sentinel-pattern import test). | closed |
| T-04-08 | Tampering (V12) | Eager `paths.engines_dir()` creation interferes with one-shot migration | mitigate | `_migrate_engines_dir()` does NOT call `paths.engines_dir()` — it computes `paths.user_data_dir() / "engines"` manually so the destination is not pre-created (`migration.py:46-66`). Locked by `TestMigrationIdempotency::test_migration_idempotent` and `TestEnginesDirMigrationConditional::test_migration_engines_dir_conditional_when_legacy_absent`. | closed |
| T-05-01 | Repudiation | Bare `RuntimeError` obscures engine timeouts and startup failures | mitigate | `EngineProcessError` raises at `engine_adapter.py:261, 270` carry literal `"Engine startup failed"`. `EngineTimeoutError` at `:475` carries operation/timeout context. Locked by `tests/test_engine_adapter.py::TestExceptionWiring` (line 117), which asserts the literal `"startup failed"` substring (line 173). `tests/CONCERNS_TRACEABILITY.md` (5749 bytes) maps every TD-N requirement to its regression test. | closed |
| T-05-02 | Information Disclosure | Pruned exception types might leak internal state via subclass introspection | accept | Pruned classes have zero references in production code outside `exceptions.py` (grep guard verified empty). Pruning REDUCES attack surface. | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01 | T-01-01 | blinker contract: subscribers ignore unknown kwargs by design. Adding `old_board`/`move_kind` to `move_made` cannot escalate privilege; values derive from python-chess primitives that already pass through the codebase. Locked by `test_broad_subscriber_signature_compatible`. | gsd-security-auditor | 2026-04-29 |
| AR-02 | T-01-02 | Pre-push board state is already exposed via `BoardState.board` and `_format_move_announcement`. No PII or secrets transit `chess.Board` objects. | gsd-security-auditor | 2026-04-29 |
| AR-03 | T-02-01 | The `_simple` methods were thin aliases delegating to existing `start()`/`get_best_move()`. Deletion removes ~85 LOC of unused dispatch but introduces no new pathway. | gsd-security-auditor | 2026-04-29 |
| AR-04 | T-02-02 | Centralization in `_resolve_move_context` IMPROVES auditability — single chokepoint for any future logging or tracing. Purity contract enforced by test. | gsd-security-auditor | 2026-04-29 |
| AR-05 | T-03-03 | `board_ref` returns a live `chess.Board` for performance (Performance #3). Documented contract via verbatim docstring. Single-user desktop, no security boundary. Snapshot `.board` API retained for mutation-safety. Future enhancement: runtime guard via proxy (out of Phase 1 scope). | gsd-security-auditor | 2026-04-29 |
| AR-06 | T-04-05 | Zip bomb hardening (decompression-ratio bounds) is out of Phase 1 scope. Single-user desktop; archive source is GitHub Stockfish releases — low practical risk. Future hardening could enforce `ZipInfo.file_size` bounds. | gsd-security-auditor | 2026-04-29 |
| AR-07 | T-05-02 | Pruned exception types had no callers and no raise sites — pruning REDUCES surface area. Codex MEDIUM grep-verification ensures no production file accidentally re-imports a pruned class. | gsd-security-auditor | 2026-04-29 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-04-29 | 19 | 19 | 0 | gsd-security-auditor (initial audit) |

### 2026-04-29 — Initial audit

- **State at entry:** B (no SECURITY.md; PLAN/SUMMARY artifacts present for all 5 plans).
- **Threats found:** 19 (across 5 plans).
- **Verification mode:** "Verify all open threats" via `gsd-security-auditor`.
- **Result:** `## SECURED` — all 19 threats closed. No `BLOCKERS`, no `WARNINGS`.
- **ASVS L1 satisfied:** V6 (Cryptography — SHA-256), V9 (Communications Security — explicit SSL context), V12 (File and Resource — ZIP traversal guard, conditional engines-dir migration), V14 (Configuration — platformdirs migration + startup ordering).
- **Block-on policy:** `high` — zero high-severity OPEN threats remain.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-04-29

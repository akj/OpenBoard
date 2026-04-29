---
phase: 01-tech-debt-cleanup
plan: "04"
subsystem: config-paths-security
tags:
  - platformdirs
  - security
  - ssl
  - sha256
  - zip-traversal
  - migration
  - persistence
  - python
  - subtrack-a-paths-migration
  - subtrack-b-downloader-hardening
dependency_graph:
  requires:
    - Plan 01-01 (signal contracts, canonical forwarder pattern)
    - Plan 01-03 (views.py menu changes; tests/conftest.py append-only)
  provides:
    - openboard/config/paths.py (platformdirs wrappers + OPENBOARD_PROFILE_DIR override)
    - openboard/config/migration.py (one-shot migrate_legacy_paths() + conditional _migrate_engines_dir())
    - SSL_CONTEXT + SHA-256 + ZIP traversal guard in downloader.py (TD-13/D-21)
    - migrate_legacy_paths() wired in main() BEFORE get_settings() (Codex HIGH startup ordering)
    - EngineSettings.engines_dir via paths.engines_dir() factory (no Path.cwd())
  affects:
    - openboard/config/settings.py
    - openboard/engine/downloader.py
    - openboard/engine/stockfish_manager.py
    - openboard/views/views.py
    - tests/conftest.py
    - tests/test_paths.py
    - tests/test_migration.py
    - tests/test_settings.py
    - tests/test_downloader_security.py
    - tests/test_views_startup_ordering.py
tech_stack:
  added:
    - platformdirs>=4.3.8 (pyproject.toml runtime dependency)
    - openboard/config/paths.py (new module)
    - openboard/config/migration.py (new module)
  patterns:
    - OPENBOARD_PROFILE_DIR env override for test isolation (D-09 / RESEARCH.md Pitfall 6)
    - _migrate_engines_dir() does NOT call paths.engines_dir() — avoids eager mkdir (Codex HIGH / T-04-08)
    - sys.modules save/restore in startup-ordering tests (prevents inter-test module identity contamination)
key_files:
  created:
    - openboard/config/paths.py
    - openboard/config/migration.py
    - tests/test_paths.py
    - tests/test_migration.py
    - tests/test_downloader_security.py
    - tests/test_views_startup_ordering.py
  modified:
    - pyproject.toml
    - openboard/config/settings.py
    - openboard/engine/downloader.py
    - openboard/engine/stockfish_manager.py
    - openboard/views/views.py
    - tests/conftest.py
    - tests/test_settings.py
decisions:
  - "D-09: OPENBOARD_PROFILE_DIR env var overrides all platformdirs paths for test isolation; isolated_profile fixture in conftest.py uses monkeypatch.setenv"
  - "D-10: migrate_legacy_paths() is one-shot and idempotent; _migrate_engines_dir() is conditional (no eager paths.engines_dir() call); cwd copy removed by shutil.move semantics"
  - "D-11: EngineSettings.engines_dir default_factory=_engines_dir_factory; no Path.cwd() in settings.py"
  - "D-21: SSL_CONTEXT = ssl.create_default_context() at module top; all 3 urlopen() calls pass context=SSL_CONTEXT (Codex LOW); download_file raises DownloadError on SHA-256 mismatch; logs DEBUG when no hash (Codex MEDIUM — not WARN); extract_zip uses os.path.commonpath guard (Security #2)"
  - "Codex HIGH startup ordering: module-top settings = get_settings() removed; main() calls migrate_legacy_paths() BEFORE get_settings()"
  - "Codex HIGH filename: settings_path() returns config.json (legacy name preserved; no rename in Phase 1)"
  - "Codex MEDIUM log level: DEBUG per-download when no SHA-256, single INFO at StockfishManager startup"
  - "Test isolation: startup-ordering tests use save/restore snapshot for sys.modules to prevent DownloadError identity mismatch in subsequent tests"
metrics:
  duration: "16m"
  completed_date: "2026-04-29"
  tasks_completed: 4
  files_modified: 11
  files_created: 6
---

# Phase 01 Plan 04: Platformdirs Paths, Legacy Migration, and Downloader Hardening Summary

Introduced platformdirs-based persistent file paths with OPENBOARD_PROFILE_DIR test isolation, one-shot migration of legacy cwd-relative files, startup-ordering fix (migrate before settings init), and SSL/SHA-256/ZIP-traversal hardening for the Stockfish downloader.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | RED tests — platformdirs dep + fixtures + failing tests | a7365e0 | pyproject.toml, conftest.py, test_paths.py, test_migration.py, test_settings.py, test_downloader_security.py, test_views_startup_ordering.py |
| 2 | Subtrack A GREEN — paths.py + migration.py + EngineSettings factory | 8c4b2de | config/paths.py, config/migration.py, config/settings.py, test_settings.py |
| 3 | Startup ordering — migrate_legacy_paths() BEFORE get_settings() | 4181f6b | openboard/views/views.py |
| 4 | Subtrack B GREEN — SSL/SHA-256/ZIP hardening + startup INFO | b4348de | engine/downloader.py, engine/stockfish_manager.py |
| 4.fix | Fix startup-ordering tests: sys.modules isolation | 22c158f | tests/test_views_startup_ordering.py |

## Decisions Made

### D-09: OPENBOARD_PROFILE_DIR Test Isolation
All platformdirs helper functions check `os.environ.get("OPENBOARD_PROFILE_DIR")` first. When set, every path is rooted under that directory with `config/`, `data/`, `state/` subdirectories. The `isolated_profile` pytest fixture uses `monkeypatch.setenv` to set this per-test, ensuring no cross-test pollution. Production runs without the env var use the real platformdirs paths.

### D-10: One-Shot Migration Semantics
`migrate_legacy_paths()` is idempotent — a second run on a fresh install is a silent no-op. The `_migrate_engines_dir()` helper is conditional: it checks `Path.cwd() / "engines"` existence BEFORE computing the destination, and explicitly does NOT call `paths.engines_dir()` (which would eagerly `mkdir` the destination, breaking the one-shot move semantics). The file copy semantics use `shutil.move`, which removes the source — no backup is kept.

### D-11: EngineSettings.engines_dir Factory
Replaced `lambda: Path.cwd() / "engines"` with `default_factory=_engines_dir_factory` (where `_engines_dir_factory` is `paths.engines_dir`). The factory creates the directory on first access. Updated `test_engine_settings_default` to assert against `paths.engines_dir()` instead of `Path.cwd() / "engines"`.

### D-21: Downloader Security Baseline
- SSL: `SSL_CONTEXT = ssl.create_default_context()` at module top; all 3 `urlopen()` calls pass `context=SSL_CONTEXT`.
- SHA-256: `download_file` accepts `expected_sha256: str | None = None`; on mismatch, deletes partial file and raises `DownloadError`. On `None`, logs DEBUG (not WARN per Codex MEDIUM revision).
- ZIP traversal: `extract_zip` uses `os.path.commonpath([str(extract_root), str(target)]) != str(extract_root)` to reject escaping members.
- Startup INFO: `StockfishManager.__init__` logs exactly ONE INFO containing "no upstream checksum source" (Codex MEDIUM operator-visible signal).

### Startup Ordering Fix (Codex HIGH)
Removed `settings = get_settings()` from line 31 of views.py (module-top initialization). All `settings.ui.*` references in `BoardPanel` replaced with `get_settings().ui.*` (lazy per-call). `main()` now calls `migrate_legacy_paths()` as its first significant action, before any code that could trigger `get_settings()`.

### get_settings() Call Site Inventory (Codex HIGH)
| File | Line | Site | Status |
|------|------|------|--------|
| openboard/views/views.py | 31 | `settings = get_settings()` | REMOVED (module-top) |
| openboard/views/views.py | main() | `settings = get_settings()` | KEPT (after migrate_legacy_paths()) |
| openboard/engine/engine_detection.py | 28 | `self.settings = get_settings()` | OK — inside EngineDetector.__init__(), only instantiated inside methods, never at module top |

### download_file Caller Inventory (Codex MEDIUM)
| File | Line | Site | Status |
|------|------|------|--------|
| openboard/engine/downloader.py | 106 | `def download_file(...)` | Definition — updated with expected_sha256 kwarg |
| openboard/engine/downloader.py | 271 | `self.download_file(download_url, download_path, download_progress)` | Internal call — backward-compatible (expected_sha256 defaults to None) |
| tests/test_downloader_security.py | multiple | test calls | Written with new signature |

No other production callers outside downloader.py.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Startup-ordering sentinel test was ineffective due to get_settings() None-guard**
- **Found during:** Task 1 RED phase
- **Issue:** The plan prescribed a sentinel-object approach: set `_settings = sentinel`, import views, assert `_settings is sentinel`. But `get_settings()` only initializes `_settings` if it is `None` — if `_settings` is a non-None sentinel, `get_settings()` returns it unchanged without overwriting. So the sentinel was NEVER replaced even in the pre-fix state, making the test always pass regardless of whether views.py had the module-top call.
- **Fix:** Changed approach to set `_settings = None` before import, then assert `_settings is None` after. If views.py calls `get_settings()` at module top, `_settings` becomes a real Settings instance. Post-fix: stays None.
- **Files modified:** tests/test_views_startup_ordering.py
- **Commit:** a7365e0

**2. [Rule 1 - Bug] openboard.views package has no __init__.py — `import openboard.views` does not execute views.py**
- **Found during:** Task 1 RED phase
- **Issue:** The plan said `importlib.import_module("openboard.views")`. But `openboard/views/` has no `__init__.py`, so importing `openboard.views` imports the package namespace (a namespaced package with `__file__=None`) without executing `views.py`. The module-top `settings = get_settings()` line never ran.
- **Fix:** Changed to `importlib.import_module("openboard.views.views")` to reach the actual `views.py` module.
- **Files modified:** tests/test_views_startup_ordering.py
- **Commit:** a7365e0

**3. [Rule 1 - Bug] sys.modules manipulation in startup-ordering tests caused inter-test DownloadError identity mismatch**
- **Found during:** Post-Task-4 cohort test run (tests ran fine in isolation but 2 failed in cohort)
- **Issue:** `test_views_startup_ordering.py` tests cleared all `openboard.*` modules from `sys.modules` without restoring them. After those tests ran, `openboard.exceptions` was re-imported as a fresh module object when `openboard.engine.downloader` was next used. The `DownloadError` class in the downloader came from the new module; the test had imported `DownloadError` from the original module. `pytest.raises(DownloadError)` failed to catch the exception because the two `DownloadError` classes were not the same object.
- **Fix:** Added `_clear_openboard_modules()` / `_restore_openboard_modules()` with `try/finally` in both startup-ordering tests to save and restore sys.modules.
- **Files modified:** tests/test_views_startup_ordering.py
- **Commit:** 22c158f

**4. [Rule 1 - Bug] test_engine_settings_default asserted old Path.cwd() behavior**
- **Found during:** Task 2 GREEN phase (test failure on settings test)
- **Issue:** The existing `test_engine_settings_default` asserted `engine.engines_dir == Path.cwd() / "engines"`. After switching EngineSettings to use paths.engines_dir(), this assertion failed.
- **Fix:** Updated test to assert `engine.engines_dir == paths.engines_dir()`.
- **Files modified:** tests/test_settings.py
- **Commit:** 8c4b2de

**5. [Rule 1 - Bug] Module-top comment contained "get_settings()" text, breaking startup ordering position check**
- **Found during:** Task 3 verification
- **Issue:** The regex `body.find('get_settings(')` matched the comment "migration MUST run before the first get_settings() call" at position 176, before the actual function call at position 472 — causing the ordering assertion to fail even though the code was correct.
- **Fix:** Rewrote the comment to say "migration MUST run before settings are initialized" (no embedded token).
- **Files modified:** openboard/views/views.py
- **Commit:** 4181f6b

## Cross-Plan Traceability

### For Phase 2b (Settings Extension)
`openboard/config/paths.py` is the single source of truth for all persistent file paths. Phase 2b's settings persistence (JSON read/write) should use `paths.settings_path()` as the canonical file target.

### For Phase 4b (Autosave)
`paths.autosave_path()` returns `user_state_dir() / "autosave.json"`. Phase 4b should read from and write to this path exclusively.

### For Future Signal Wiring (D-05)
No changes to signal wiring in this plan. Existing canonical forwarder pattern from Plan 01 is unaffected.

## Known Stubs

None — all platform path functions are fully implemented, migration is fully wired, downloader security is complete.

## Threat Flags

None — all STRIDE threats (T-04-01 through T-04-08) in the plan's threat model are mitigated with regression tests.

## Self-Check: PASSED

- [x] openboard/config/paths.py exists with 7 public functions
- [x] paths.settings_path() returns config.json (legacy filename preserved): `grep -q '/ "config.json"' openboard/config/paths.py` — FOUND
- [x] openboard/config/migration.py exists with migrate_legacy_paths() and _migrate_engines_dir()
- [x] _migrate_engines_dir() does NOT call paths.engines_dir(): `grep "paths.engines_dir()" openboard/config/migration.py` — NOT FOUND (correct)
- [x] EngineSettings.engines_dir uses _engines_dir_factory: `grep "default_factory=_engines_dir_factory" openboard/config/settings.py` — FOUND
- [x] No Path.cwd() in settings.py: `grep "Path.cwd" openboard/config/settings.py` — NOT FOUND
- [x] No module-top `settings = get_settings()` in views.py — REMOVED
- [x] migrate_legacy_paths() called in main() before get_settings(): mig_pos=350 < get_pos=472
- [x] SSL_CONTEXT = ssl.create_default_context() in downloader.py — FOUND
- [x] All 3 urlopen() calls pass context=SSL_CONTEXT: 3/3 verified
- [x] expected_sha256 param in download_file — FOUND
- [x] os.path.commonpath guard in extract_zip — FOUND
- [x] "no upstream checksum source" INFO in StockfishManager.__init__ — FOUND
- [x] All 21 Plan 04 cohort tests pass
- [x] Full pytest suite: 365 passed, 0 failures
- [x] ruff clean for all new/modified source files
- [x] ty clean for all new/modified source files
- [x] Commits: a7365e0 (RED), 8c4b2de (Subtrack A GREEN), 4181f6b (startup ordering), b4348de (Subtrack B GREEN), 22c158f (test isolation fix)

---
phase: 01-tech-debt-cleanup
plan: 05
subsystem: exceptions + engine-adapter + stockfish-manager + audit-doc
tags:
  - exceptions
  - error-handling
  - audit
  - traceability
  - gate-a-exception-cleanup
  - gate-b-traceability-audit
dependency_graph:
  requires:
    - 01-01-SUMMARY.md
    - 01-02-SUMMARY.md
    - 01-03-SUMMARY.md
    - 01-04-SUMMARY.md
  provides:
    - openboard/exceptions.py pruned hierarchy (10 kept types, 5 removed)
    - EngineTimeoutError raised at future.result() timeout in get_best_move()
    - EngineProcessError raised at _start_engine() startup-failure site
    - NetworkError bubble-up from StockfishManager.install_stockfish()
    - tests/CONCERNS_TRACEABILITY.md: TD-01..TD-14 traceability audit table
  affects:
    - openboard/engine/engine_adapter.py
    - openboard/engine/stockfish_manager.py
    - tests/test_exceptions.py
    - tests/test_engine_adapter.py
    - tests/test_downloader.py
    - tests/test_stockfish_manager.py
    - tests/test_engine_adapter_integration.py
tech_stack:
  added: []
  patterns:
    - "Dedicated except FutureTimeoutError before broad except Exception for typed timeout propagation"
    - "Re-raise pattern: except NetworkError: raise in StockfishManager"
    - "sys.modules manipulation with restore in test teardown to avoid class-identity issues from importlib.reload"
key_files:
  created:
    - tests/test_downloader.py
    - tests/CONCERNS_TRACEABILITY.md
  modified:
    - openboard/exceptions.py
    - openboard/engine/engine_adapter.py
    - openboard/engine/stockfish_manager.py
    - tests/test_exceptions.py
    - tests/test_engine_adapter.py
    - tests/test_stockfish_manager.py
    - tests/test_engine_adapter_integration.py
decisions:
  - "Typed exception propagation through start() outer wrapper: let EngineNotFoundError/EngineProcessError/EngineInitializationError propagate as-is by catching them before the broad Exception catch"
  - "sys.modules restore in TestPrunedExceptionTypes instead of importlib.reload to avoid class-identity drift between test runs"
  - "Integration tests test_engine_start_failure/test_engine_start_timeout updated to expect typed exceptions rather than bare RuntimeError (correct per TD-11 D-19)"
metrics:
  duration: "11 minutes"
  completed_date: "2026-04-29"
  tasks_completed: 4
  files_modified: 7
  files_created: 2
---

# Phase 1 Plan 5: Exception Hierarchy Cleanup + Traceability Audit Summary

**One-liner:** Exception hierarchy pruned (5 removed, 4 wired with typed raise sites) and TD-01..TD-14 traceability table authored in CONCERNS_TRACEABILITY.md.

## What Was Built

### Gate A: Exception Hierarchy Cleanup (TD-11 / D-19 / D-20)

**Pruned from `openboard/exceptions.py` (D-20):**
- `AccessibilityError(UIError)` — no callers, no raise sites
- `DialogError(UIError)` — no callers, no raise sites
- `UIError(OpenBoardError)` — parent of pruned types, no direct callers
- `GameStateError(GameError)` — no callers, no raise sites
- `SettingsError(ConfigurationError)` — no callers; `GameModeError` inherits from `ConfigurationError` directly

**Wired raise sites (D-19, STRICT per Codex MEDIUM):**

1. **`EngineTimeoutError`** in `get_best_move()` — dedicated `except FutureTimeoutError as timeout_exc` BEFORE the broad `except Exception`, raises `EngineTimeoutError("get_best_move", time_ms)`. Strict assertion: `pytest.raises(EngineTimeoutError)` only.

2. **`EngineProcessError`** in `_start_engine()` — replaces bare `RuntimeError` at the `except Exception as startup_exc` and `except PermissionError` sites with `EngineProcessError(f"Engine startup failed: {exc}", stderr=str(exc))`. Message contains literal substring `"Engine startup failed"` (Codex MEDIUM specific message).

3. **`NetworkError` bubble-up** in `StockfishManager.install_stockfish()` — added `except NetworkError: raise` before the broad `except Exception` handler so network failures propagate to callers.

4. **Typed exception propagation through `start()`** — the `start()` outer wrapper now catches `(EngineNotFoundError, EngineProcessError, EngineInitializationError)` and re-raises them as-is, preventing them from being wrapped in bare `RuntimeError`.

**Codex MEDIUM grep verification (Task 3):** `TestPrunedExceptionImportsAbsentFromSource` uses `subprocess.run(["grep", ...])` to verify no production file imports any of the 5 pruned classes. All 5 parametrized cases pass.

### Gate B: Traceability Audit (TD-14 / D-26)

`tests/CONCERNS_TRACEABILITY.md` authored with locked Codex LOW format:
- Header: audit date, phase, total count
- Mapping table: `| REQ-ID | Concern | Test path | Test name |` — 14 rows
- TD-04 row: contains exact fixture name `pinned_attacker_fen`, FEN `4r3/8/8/8/8/8/8/4K3 w - - 0 1`, and test `test_announce_attacking_pieces_includes_pinned_attacker` (Codex MEDIUM cross-plan)
- TD Coverage Bullet List: 14 lines `- TD-NN: ...`
- Validation footer with VALIDATION.md row 1-05-05 bash commands

D-24 docstring discipline: confirmed all TD-01..TD-14 have at least one test docstring referencing the token.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Class identity drift from importlib.reload in TestPrunedExceptionTypes**
- **Found during:** Task 2 (GREEN phase) — TestExceptionWiring failed when run in the same pytest session after TestPrunedExceptionTypes
- **Issue:** `importlib.reload("openboard.exceptions")` created a new class object; `engine_adapter.py` (imported at module level before reload) held the OLD reference. `pytest.raises(EngineTimeoutError)` in `TestExceptionWiring` used the NEW class, causing a mismatch even though the exception was raised correctly.
- **Fix:** Changed `TestPrunedExceptionTypes` to use `sys.modules` manipulation (delete + fresh import + restore original in finally block) instead of `importlib.reload`. This inspects the pruned types without changing the class identity that other modules hold.
- **Files modified:** `tests/test_exceptions.py`
- **Commit:** 55f6aa3

**2. [Rule 1 - Bug] Integration tests expecting bare RuntimeError from typed raise sites**
- **Found during:** Task 2 (GREEN phase) — `test_engine_start_failure` and `test_engine_start_timeout` in `test_engine_adapter_integration.py` expected `RuntimeError` but now correctly received typed exceptions
- **Issue:** Pre-existing integration tests used `pytest.raises(RuntimeError, match="Failed to launch engine")` but the typed exception wire-up in Gate A changes these raise sites to `EngineNotFoundError` and `EngineProcessError`.
- **Fix:** Updated both tests to expect the correct typed exceptions (`EngineNotFoundError` for FileNotFoundError case, `EngineProcessError` for startup timeout case).
- **Files modified:** `tests/test_engine_adapter_integration.py`
- **Commit:** 55f6aa3

## Known Stubs

None. All raise sites are wired with real exception types. The traceability doc is a real audit table, not a placeholder.

## Threat Flags

None. Plan 05 is exception-hierarchy cleanup + audit doc. The new raise sites replace existing bare-RuntimeError raises and do not add new trust boundaries or attack surface.

## TDD Gate Compliance

- RED commit: `f0a89a8` — test(01-05): add failing tests for exception prune + raise-path wiring + traceability audit (RED gate)
- GREEN commit: `55f6aa3` — feat(01-05): Gate A — prune unused exception types + wire EngineTimeout/EngineProcess raises
- GREEN commit: `2fecb16` — feat(01-05): Gate B — create tests/CONCERNS_TRACEABILITY.md

## Self-Check: PASSED

All files found, all commits present, all verification checks pass:
- PRUNED_CLASSES_GONE: openboard/exceptions.py has 0 pruned class definitions
- ENGINE_TIMEOUT_WIRED: `raise EngineTimeoutError` present in engine_adapter.py
- ENGINE_PROCESS_WIRED: `raise EngineProcessError` present in engine_adapter.py
- STARTUP_FAILED_MESSAGE_PRESENT: `Engine startup failed` message in engine_adapter.py
- CONCERNS_DOC_EXISTS: tests/CONCERNS_TRACEABILITY.md exists
- TD_COUNT_OK: ≥14 `^- TD-` lines in traceability doc
- LOCKED_TABLE_FORMAT_OK: `| REQ-ID | Concern | Test path | Test name |` header present
- CANONICAL_TD04_REFERENCED: `pinned_attacker_fen`, FEN, and test name present
- 386 tests pass (0 unexpected failures)
- Plan 05 source files: ruff-clean, ty-clean

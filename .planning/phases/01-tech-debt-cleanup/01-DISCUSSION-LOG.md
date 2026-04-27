# Phase 1: Tech Debt Cleanup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-27
**Phase:** 01-tech-debt-cleanup
**Mode:** discuss (auto)
**Areas discussed:** MoveKind shape, platformdirs migration policy, sync request_computer_move disposition, unused exception types, TD-13 catch-all enumeration, plan granularity, regression test convention, _simple API removal style

---

## MoveKind shape (TD-02)

| Option | Description | Selected |
|--------|-------------|----------|
| `enum.IntFlag` (composable bits) | Members `QUIET=0, CAPTURE, CASTLE, EN_PASSANT, PROMOTION, CHECK, CHECKMATE` compose with bitwise OR. Capture-with-check is a single value `CAPTURE \| CHECK`. SoundService does `if MoveKind.CAPTURE in kind`. | ✓ |
| `enum.StrEnum` exclusive categorical + separate `is_check: bool` payload field | Strict mutually-exclusive category, with `is_check` riding alongside. More explicit but two payload fields where one suffices. | |
| Class with attributes (`MoveKind(category="capture", is_check=True, ...)`) | Most flexible, but adds a class to the model layer for what is fundamentally a small flag set. | |

**Auto-selected:** `enum.IntFlag` (recommended default).
**Rationale:** Captures composability natively. Phase 4a SoundService's design (research/ARCHITECTURE.md §2) already assumes per-bit testing. `is_check` as a sibling field would be redundant once you have `MoveKind.CHECK in kind`.

---

## platformdirs migration policy (TD-12)

| Option | Description | Selected |
|--------|-------------|----------|
| Silent one-shot migration with INFO log on first launch | Detect legacy file at `Path.cwd()`; move to `platformdirs.user_*_dir`; log `INFO: Migrated <legacy> → <new>`. Subsequent launches skip. | ✓ |
| Read-from-old-as-fallback-then-write-new (long-lived backward compat) | Always check both locations on read; write only to new. Simpler-feeling but creates a permanent dual-path. | |
| Print warning + manual instructions; do not auto-migrate | Most conservative; user moves files themselves. | |

**Auto-selected:** Silent one-shot migration with INFO log (recommended default).
**Rationale:** Lowest friction for the existing user (project author has files at `cwd`). One-shot avoids forever-fallback complexity. INFO log preserves an audit trail.

---

## Sync `Game.request_computer_move()` disposition (TD-08)

| Option | Description | Selected |
|--------|-------------|----------|
| Remove entirely; tests migrate to async path with synchronous mock callbacks | Cleanest. Production already uses async-only. Tests use inline callback pattern. | ✓ |
| Mark `_test_only` and keep | Preserves the API for test convenience but signals "do not use in production." | |
| `@deprecated` with one-release window | Standard deprecation, but the method has never been a public stable API. | |

**Auto-selected:** Remove entirely (recommended default).
**Rationale:** Never shipped externally. Tests should reflect production code paths (the async path). Reduces engine-adapter / Game surface area.

---

## Unused exception types (TD-11)

| Option | Description | Selected |
|--------|-------------|----------|
| Wire up obviously-belonging types (EngineTimeoutError, EngineProcessError, DownloadError, NetworkError); prune the rest (AccessibilityError, DialogError, SettingsError, GameStateError, UIError) | Capture the value of typed exceptions where they fit; remove dead types that mislead readers. | ✓ |
| Wire up all | Force every type to find a home. Risks cargo-cult raising. | |
| Prune all | Easiest, but loses the typed-exception expressiveness for engine and download errors. | |

**Auto-selected:** Wire up obviously-belonging, prune the rest (recommended default).
**Rationale:** Engine timeouts and download failures have clear sites currently raising bare `RuntimeError`. The other five types lack obvious wire-up sites and clutter the hierarchy.

---

## TD-13 catch-all enumeration

| Option | Description | Selected |
|--------|-------------|----------|
| 6 in-scope items + 7 deferred | Performance #1, #3; Security #1, #2, #3; eliminate `_pending_old_board` (Fragile #3) — all addressed. Fragile #1, #2, #4; Scaling #1; Deps at Risk #1, #2; Missing Critical #1, #2; Test Gaps #1–4 — deferred. | ✓ |
| Aggressive: include Fragile #1 (EngineAdapter refactor) and Missing Critical #1 (promotion UI) | Maximises tech-debt clearing but inflates Phase 1 scope into Tier 1+ territory. | |
| Conservative: only Performance #1 and Security #1; defer everything else under TD-13 | Leaves visible debt unfixed. | |

**Auto-selected:** 6 in-scope + 7 deferred (recommended default).
**Rationale:** Each in-scope item is small, structural, or directly intersects a TD-* fix already locked in. Each deferred item is either too large for v1 (engine refactor), a separate user-visible capability (promotion UI, persistence), or operational/non-blocking (Linux mirror, accessible-output3 pin).

---

## Plan granularity within Phase 1 (D-26)

| Option | Description | Selected |
|--------|-------------|----------|
| 5 logical plans (signal pattern → engine cleanup → bug fixes → persistence/security → exception hierarchy / test discipline) | Matches `granularity = standard`. Plan 1 sequential; Plans 2–4 parallel after Plan 1; Plan 5 after Plans 1–4. | ✓ |
| One plan per fix (14 plans, atomic commits) | Maximally safe, but slow and high-overhead for items that share files (e.g., several TD-* in `chess_controller.py`). | |
| Single big plan | Fast to write, but loses checkpointing and fails the granularity contract. | |

**Auto-selected:** 5 logical plans (recommended default).
**Rationale:** Each batch shares files and rationale, so a single plan-and-commit per batch produces a coherent diff. Parallel execution after Plan 1 fits `parallelization = true` in config.json.

---

## Regression test convention (TD-14, D-24)

| Option | Description | Selected |
|--------|-------------|----------|
| Existing `tests/test_<module>.py` files with TD-N citations in docstrings | Matches the project's existing convention. Tests live next to the code they cover. | ✓ |
| New `tests/test_concerns_<area>.py` files (one per area) | Keeps regression tests visually separate from feature tests. | |
| Single `tests/test_phase1_regressions.py` file | Easiest to inventory but couples unrelated tests in one file. | |

**Auto-selected:** Existing `tests/test_<module>.py` files (recommended default).
**Rationale:** TESTING.md documents `test_<module_or_feature>.py` as the convention. Each test docstring cites TD-N + CONCERNS.md item, providing inline traceability. Security regressions (a new concern surface) get their own `tests/test_downloader_security.py`.

---

## `_simple` API removal style (TD-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Hard-delete the entire `_simple` family | These are internal aliases never exposed externally. | ✓ |
| Deprecation shim with `DeprecationWarning` for one release | Standard deprecation pattern, but unnecessary for never-public surface. | |

**Auto-selected:** Hard-delete (recommended default).
**Rationale:** CI grep confirms no callers outside `engine_adapter.py` itself. Public API stability does not apply. Cleaner diff.

---

## Claude's Discretion

(See CONTEXT.md §"Claude's Discretion" for the full list — locked here as an audit reference.)

- Exact test file targeting per fix (e.g., whether a TD-04 test goes in `test_chess_controller.py` or a new `test_attackers.py`) — pick by closest existing convention.
- Whether `_resolve_move_context()` is a free function on `Game` or a small dataclass — pick by readability.
- Whether `OPENBOARD_PROFILE_DIR` env override on `paths.py` helpers is implemented now or deferred — implement now (~5 lines, pays for itself in test isolation).
- Specific log levels for migration messages (suggested: `logging.INFO` for migrations performed; `logging.DEBUG` for "no migration needed").
- Whether `MoveKind` lives in `openboard/models/move_kind.py` or alongside `BoardState` in `board_state.py` — pick by import-cycle safety.

## Deferred Ideas

(See CONTEXT.md §"Deferred Ideas" — captured here for cross-reference.)

- Promotion-piece choice UI (CONCERNS.md Missing Critical #1) — own phase or bundle with Phase 3c.
- EngineAdapter overall thread/async refactor (Fragile #1) — v1.x or v2.
- Computer-move announcement double-path (Fragile #2) — reassess after D-02 / D-03 land.
- CvC pause/stop button (Scaling #1) — own phase.
- accessible-output3 vendoring (Deps at Risk #1) — v1.x.
- wxPython Linux mirror migration (Fragile #4 / Deps at Risk #2) — operational/build pass concern.
- View-layer broader test coverage (Test Gaps #1) — opportunistic.
- Async computer-move end-to-end tests with real engine timing (Test Gaps #3) — opportunistic.
- Persistence between sessions (Missing Critical #2) — that is Phase 2a + 4b.

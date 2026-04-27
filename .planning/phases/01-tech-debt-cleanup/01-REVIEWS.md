---
phase: 1
reviewers: [codex]
reviewed_at: 2026-04-27T18:51:12-04:00
plans_reviewed:
  - 01-01-PLAN.md
  - 01-02-PLAN.md
  - 01-03-PLAN.md
  - 01-04-PLAN.md
  - 01-05-PLAN.md
codex_model: gpt-5.1-codex (cli default)
codex_cli_version: 0.124.0
---

# Cross-AI Plan Review — Phase 1: Tech Debt Cleanup

> **Note:** Only one external reviewer (Codex) was invoked, so the
> "Consensus Summary" below echoes Codex's cross-plan assessment rather
> than synthesizing across multiple AI systems. Re-run with additional
> reviewers (`/gsd-review --phase 1 --gemini --claude`) for true consensus.

## Codex Review

# Plan Review

## 01-01-PLAN.md

**Summary**  
This is the strongest plan in the set. It is tightly aligned with the phase’s architectural intent: establish the canonical signal-forwarding pattern, enrich `move_made` once at the model boundary, and eliminate the controller-side `_pending_old_board` workaround. The TDD structure is disciplined, the dependency role is correct, and the plan clearly understands that later phases depend on these contracts. The main risk is not conceptual but implementation detail: a few tests and code-path assumptions appear brittle or slightly inconsistent with the actual chess positions and replay semantics.

**Strengths**
- Clear foundational scope: TD-01/02/03 are correctly grouped as the substrate for later phases.
- Good architectural decision to push `old_board` into signal payloads instead of reconstructing state downstream.
- Correctly treats `Game` forwarders as the canonical subscription surface.
- Explicitly calls out elimination of `_pending_old_board` and the O(n) replay fallback.
- TDD sequencing is strong: RED tests first, then focused GREEN tasks.
- Good awareness of `MoveKind.CHECK` needing post-push evaluation.

**Concerns**
- HIGH: Some chess fixtures/tests look questionable. The pinned-attacker explanation mixes “pinned attacker” semantics with “side to move” and may not actually prove the intended legal-vs-attackers distinction cleanly.
- MEDIUM: `replay_to_position` uses `self.game.board_state.board.move_stack` as both live state and history source; if replay mode semantics differ from live mode, this may not fully cover PGN/replay edge cases.
- MEDIUM: The plan assumes extending `BoardState.move_made` with `old_board` is harmless everywhere because blinker ignores extra kwargs. That is mostly true, but any code directly calling handlers without `**kwargs` tolerance could still break.
- MEDIUM: The meta-test asserting `_pending_old_board` string absence is useful, but source-grep tests can become noisy and brittle during refactors.
- LOW: Task text says Plan 01 should not touch `announce_attacking_pieces`, but some examples intermingle controller announcement logic and payload testing enough that implementers could drift scope.

**Suggestions**
- Replace the TD-04-style pinned-attacker example text in this plan’s context/tests with a cleaner known position that directly demonstrates `legal_moves` failure and `attackers()` correctness.
- Add one explicit regression test ensuring a subscriber with signature `(sender, move=None, **kwargs)` still works after `old_board`/`move_kind` are added.
- Clarify replay semantics: whether `replay_to_position` must work only for current move stack or also for PGN replay state already loaded from elsewhere.
- Prefer a behavioral test over the source-grep `_pending_old_board` test, or keep both but mark the grep test as a guardrail rather than primary evidence.

**Risk Assessment**  
**MEDIUM-LOW**. The design is right and load-bearing. Risk is mostly from test-fixture correctness and a few brittle assertions, not from architecture.

---

## 01-02-PLAN.md

**Summary**  
This plan is directionally correct and appropriately scoped: remove dead `_simple` APIs, collapse onto the async move path, extract shared move-context resolution, and delete `player_color`. It supports the long-term threading model by reducing sync/async drift. The main weakness is that the plan underspecifies how `_resolve_move_context()` interacts with book-hit side effects and engine-optional behavior, and it risks turning test migration into more churn than signal if not carefully constrained.

**Strengths**
- Good cleanup target selection: TD-06/07/08/10 belong together.
- Correct decision to delete, not deprecate, internal dead APIs.
- Strong alignment with the project’s existing async engine architecture.
- Good use of existing async mock-callback patterns instead of inventing new harnesses.
- Keeps the scope mostly isolated from UI and persistence work.

**Concerns**
- MEDIUM: `_resolve_move_context()` may become an awkward helper if it mixes validation, book lookup, difficulty resolution, and FEN capture plus possible side effects.
- MEDIUM: Removing sync `request_computer_move()` is right, but migrating all tests to callback/signal observation may make some tests less direct and harder to reason about.
- MEDIUM: Plan text suggests a `MoveContext` dataclass, but this may be over-structuring for a private helper returning only a couple of values.
- LOW: `test_simple_api_removed` checks attribute absence on the class, but if aliases remain elsewhere or import surfaces still expose them indirectly, coverage is narrow.
- LOW: There is some risk of overlapping file churn in `game.py` with Plan 01 depending on actual merge sequencing, even though the dependency is declared.

**Suggestions**
- Keep `_resolve_move_context()` minimal: validate mode, resolve difficulty, capture FEN, optionally return `book_move`; avoid hiding dispatch/emission behavior inside it.
- Add one explicit test for engine-optional behavior: `_resolve_move_context()` or `request_computer_move_async()` should still fail cleanly when `engine_adapter is None` and no book move exists.
- Consider using a tuple unless the helper clearly needs three or more named fields; a private dataclass may be more ceremony than value.
- Ensure migrated tests assert user-visible outcomes, not only signal emission.

**Risk Assessment**  
**MEDIUM**. The cleanup is sound, but helper design and test migration could become noisier than necessary.

---

## 01-03-PLAN.md

**Summary**  
This plan addresses the right user-visible bugs: attacker correctness, menu binding hygiene, removal of the hard-coded `B` accelerator, and `board_ref` for read-only performance. The plan is practical and mostly well-bounded, but its weakest area is the test strategy for wx menu binding. The source-introspection approach is understandable given CI constraints, but it verifies code shape more than behavior. The `board_ref` addition is useful, but the plan underplays the long-term mutation hazard of exposing the live board object.

**Strengths**
- Good separation from Plan 02 and Plan 04; parallelization logic is reasonable.
- Correct use of `board.attackers()` for both correctness and performance.
- Sensible decision to remove the menu accelerator while preserving keyboard-config dispatch.
- Pragmatic acknowledgment that CI likely cannot run real wx view tests.
- `board_ref` keeps snapshot `.board` semantics intact.

**Concerns**
- MEDIUM: The wx menu tests are largely static source checks. They can miss runtime misbinding even if the text looks correct.
- MEDIUM: `board_ref` exposes a mutable live `chess.Board`; contract-only protection is easy to violate later.
- MEDIUM: The pinned-attacker test description still appears muddled and may not robustly prove the exact bug class.
- LOW: Regex/source tests against `views.py` may become fragile if formatting changes.
- LOW: The plan does not specify where `board_ref` should actually be adopted now versus merely added.

**Suggestions**
- Add at least one non-wx behavioral unit around menu construction if possible via monkeypatching `Bind` rather than only parsing source text.
- Add a test or audit grep of current `.board` call sites to verify some hot paths actually switch to `board_ref`.
- Strengthen the `board_ref` docstring to explicitly say controller/view read-only only, never engine/model mutation.
- Tighten the TD-04 fixture and expected announcement wording to reduce ambiguity.

**Risk Assessment**  
**MEDIUM**. The production fixes are straightforward, but the test strategy is somewhat indirect and `board_ref` creates a maintainability hazard if not tightly policed.

---

## 01-04-PLAN.md

**Summary**  
This is the riskiest plan and the one that most needs tightening. The goals are correct and necessary: move persistence to `platformdirs`, add one-shot migration, and harden downloader behavior around TLS, hashing, and ZIP extraction. But the plan mixes path refactoring, startup-order surgery, dependency addition, and security semantics in one pass, and some details are shaky. The biggest concerns are the migration ordering around the settings singleton, the proposed `settings.json` rename vs legacy `config.json`, and the fact that SHA-256 verification is described as supported even though the normal production path has no upstream checksum source.

**Strengths**
- Correctly identifies `platformdirs` migration as a prerequisite for later autosave/settings work.
- Good recognition of Pitfall 3: migration must happen before settings singleton initialization.
- Security hardening scope is appropriate: explicit SSL context, optional hash verification, ZIP traversal guard.
- Good use of isolated-profile testing for path logic.
- Correctly treats missing upstream checksums as normal-case warning behavior rather than a rare fallback.

**Concerns**
- HIGH: The settings singleton/startup ordering is fragile. If any module import still triggers `get_settings()` before `main()`, migration can silently fail or read stale paths.
- HIGH: The migration changes canonical filename from `config.json` to `settings.json`. That is fine if deliberate, but it is a broader compatibility change than “move files to platformdirs”; it must be uniformly reflected across all readers/writers.
- HIGH: The plan text around migrating the `engines/` directory is underdeveloped. Creating target dirs eagerly via `paths.engines_dir()` complicates one-shot directory moves.
- MEDIUM: Plan 04 now depends on Plan 03, but its original roadmap said parallel after Plan 01. The added dependency suggests hidden coupling or sequencing confusion.
- MEDIUM: `download_file` API change may affect callers/tests beyond the security suite; the plan does not inventory all call sites.
- MEDIUM: Logging a WARNING on every no-checksum download could become noisy if downloads are chunked or repeated often.
- LOW: Explicit `ssl.create_default_context()` is good, but if every `urlopen` already used HTTPS defaults, this is mainly explicitness rather than a functional change.

**Suggestions**
- Split the plan mentally into two subtracks even if kept in one file: `paths/migration/startup-order` and `downloader hardening`, with separate verification gates.
- Before implementation, inventory every settings/config file read/write path and confirm all switch consistently to `settings_path()` or equivalent.
- Do not eagerly create `engines_dir()` inside migration logic before deciding whether a legacy `engines/` directory needs to be moved.
- Add one explicit test covering legacy `keyboard_config.json` migration, not only `config.json`.
- Add one explicit test proving startup ordering: importing `views.py` alone must not initialize settings before migration.
- Consider whether `settings.json` rename is necessary now; if not, keeping the legacy filename in the new location reduces churn.

**Risk Assessment**  
**HIGH**. The goals are right, but migration and startup ordering are easy to get subtly wrong, and the plan currently carries too much hidden coupling.

---

## 01-05-PLAN.md

**Summary**  
This is a reasonable close-out/audit plan, but it is somewhat less crisp than the earlier ones. The pruning targets and raise-site goals are valid, and the traceability document is a good final deliverable. The risk is that this plan mixes real production behavior changes with audit/documentation work, and some exception-wire-up tests are not as strong as the rest of the phase because they rely on mocking internals or tolerate pre-fix behavior too much in Wave 0. The plan does achieve the phase goal of closing TD-11 and TD-14 if executed carefully.

**Strengths**
- Good final-audit role after Plans 01-04.
- Traceability doc is useful and directly tied to TD-14.
- Exception pruning targets are explicit.
- Correctly reuses Plan 04’s downloader exception behavior instead of redefining it.
- Strong emphasis on docstring-level TD traceability.

**Concerns**
- MEDIUM: Combining exception-wire-up changes and the full traceability audit in one plan creates two different success modes; if one slips, the other can mask it.
- MEDIUM: Some tests rely on deep mocking of `EngineAdapter` internals, which may be brittle against refactors.
- MEDIUM: The startup-failure test in Task 1 is intentionally tolerant, which weakens the RED/GREEN discipline compared with the rest of the phase.
- LOW: The traceability doc may become high-maintenance if test names move later.
- LOW: Some pruning guidance assumes exact inheritance relationships in `exceptions.py` that may differ in real code.

**Suggestions**
- Tighten the engine-process error test after implementation so final verification is strict, not tolerant.
- Keep `tests/CONCERNS_TRACEABILITY.md` concise and table-driven; do not let it become another requirements document.
- Add one grep-based verification that no production file imports the pruned exceptions.
- Consider separating “exception hierarchy cleanup” and “traceability audit” into distinct task gates in execution, even if they stay in one plan file.

**Risk Assessment**  
**MEDIUM**. It is a sensible finalization plan, but parts of the testing are less robust than the earlier plans and the plan mixes implementation with audit.

---

# Cross-Plan Assessment

## Strengths
- Overall decomposition is coherent and largely aligned with the phase boundary.
- Plan 01 correctly establishes the core architectural contracts before dependent work.
- Wave sequencing is mostly sensible.
- The plans consistently honor accessibility/correctness priorities rather than treating them as cosmetic.
- Test discipline is unusually strong for planning work.
- Security issues are explicitly called out rather than buried.

## Concerns
- HIGH: Plan 04 is under-specified in the most failure-prone areas: startup import order, filename migration semantics, and engines-dir migration.
- MEDIUM: Several tests, especially in Plans 03 and 05, verify source shape or mocked internals more than end behavior.
- MEDIUM: The chess fixture design for TD-04 is not consistently clean across documents; that bug deserves a simpler canonical test position.
- MEDIUM: There is mild scope creep in using traceability docs, meta-tests, and source-grep assertions in addition to behavioral regressions. Useful, but they should not displace runtime evidence.
- LOW: The stated parallelism shifts slightly from the roadmap because Plan 04 now depends on Plan 03; that should be explained or corrected.

## Suggestions
- Rework Plan 04 before execution. It needs the most review.
- Standardize one canonical attacker fixture for TD-04 across all plans/tests/docs.
- Prefer behavior-first tests; keep source-grep/meta-tests as secondary guardrails.
- Explicitly document final inter-plan dependency graph after Plan 01, including why Plan 04 now depends on Plan 03 if that is truly necessary.
- Add a short “phase exit checklist” above Plan 05 so the audit is not the first place integration is considered.

## Overall Risk Assessment
**MEDIUM** overall.  
The phase architecture is strong and mostly complete, and Plans 01-03 are well-designed. The main execution risk is concentrated in Plan 04, with secondary risk from some brittle/meta-heavy testing in Plans 03 and 05. If Plan 04 is tightened around migration semantics and startup ordering, the full phase drops closer to MEDIUM-LOW.

---

## Consensus Summary

**Single reviewer (Codex)** — the cross-plan assessment from Codex
above is reproduced here for convenience. Treat as one informed
opinion, not consensus.

### Highest-Priority Concerns
1. **HIGH (Plan 04):** Settings singleton/startup ordering is fragile.
   Any module import that triggers `get_settings()` before `main()`
   can cause migration to silently fail or read stale paths.
2. **HIGH (Plan 04):** Renaming the canonical config file from
   `config.json` to `settings.json` is a broader compatibility change
   than "move files to platformdirs" and must be uniformly reflected
   across every reader/writer.
3. **HIGH (Plan 04):** Engines-directory migration is underdeveloped.
   Eagerly creating `paths.engines_dir()` complicates one-shot
   directory moves.
4. **MEDIUM (Plan 04 dependency):** Plan 04 now depends on Plan 03
   (file overlap on `views.py`/`conftest.py`), which deviates from the
   roadmap's parallel-after-Plan-01 sequencing. Justify or correct.
5. **MEDIUM (Plans 01, 03):** TD-04 pinned-attacker fixture wording is
   muddled across CONTEXT.md, RESEARCH.md, Plan 01, and Plan 03. Pick
   one canonical position that cleanly demonstrates the
   `legal_moves` failure vs `attackers()` correctness distinction.
6. **MEDIUM (Plans 03, 05):** Several tests verify source shape
   (regex/grep against `views.py`, attribute absence on classes,
   `_pending_old_board` string absence) or mock internals rather than
   prove end behavior. Useful as guardrails but should not displace
   runtime evidence.

### Suggested Plan Edits Before Execution
- **Plan 04 (highest priority):**
  - Inventory every settings/config read/write call site and confirm
    they switch consistently to `settings_path()`.
  - Add a test asserting `import openboard.views` alone does not
    initialize settings before migration runs.
  - Add a test for legacy `keyboard_config.json` migration (currently
    only `config.json` is exercised).
  - Reconsider the `config.json` → `settings.json` rename — keeping
    the legacy filename in the new platformdirs location reduces churn
    if rename is not intentional.
  - Avoid eagerly creating `engines_dir()` inside migration logic
    before deciding whether a legacy `engines/` directory needs moving.
- **Plan 01:**
  - Add a test asserting subscribers with signature
    `(sender, move=None, **kwargs)` still work after `old_board` /
    `move_kind` are added.
  - Clarify whether `replay_to_position` must work for PGN replay
    state already loaded externally, not only for live `move_stack`.
- **Plan 03:**
  - Replace static source-grep menu tests with monkeypatched-`Bind`
    behavioral tests where possible.
  - Document where `board_ref` is *adopted now* vs merely added; add
    grep-based verification that hot paths actually switch.
- **Plan 05:**
  - Tighten Task 1 startup-failure test after implementation; the
    intentional Wave-0 tolerance weakens RED/GREEN discipline.
  - Separate "exception hierarchy cleanup" and "traceability audit"
    into distinct task gates within the plan file.

### Strengths Worth Preserving
- Plan 01 correctly establishes the canonical signal-forwarding
  pattern and `move_made(old_board, move_kind)` payload before any
  dependent work.
- Wave sequencing is largely sensible; the architectural intent is
  preserved across plans.
- TDD/RED-GREEN discipline is unusually strong for planning artifacts.
- Security issues in Plan 04 (SSL context, SHA-256, ZIP path-traversal)
  are explicit rather than buried.
- Plan 05's traceability doc is a useful TD-14 deliverable.

### Overall Risk: MEDIUM
Phase architecture is strong; Plans 01-03 are well-designed. Risk
concentrates in Plan 04 (migration + startup ordering) with secondary
risk from brittle meta/source-grep tests in Plans 03 and 05.
Tightening Plan 04 around migration semantics drops the phase to
MEDIUM-LOW.

### Divergent Views
N/A — single reviewer.

---

## How to Use This Review

To incorporate Codex's feedback into the plans:

```
/gsd-plan-phase 1 --reviews
```

This will replan Phase 1 with `01-REVIEWS.md` as additional input. The
planner will revise (not rewrite) the existing plans to address the
HIGH/MEDIUM concerns above while preserving the Wave structure.

For broader consensus before replanning, run additional reviewers:

```
/gsd-review --phase 1 --gemini --claude
```

Then re-run `/gsd-plan-phase 1 --reviews`.

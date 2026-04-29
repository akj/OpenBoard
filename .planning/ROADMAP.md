# Roadmap: OpenBoard — v1 Foundation & Polish

**Created:** 2026-04-27
**Granularity:** standard (target 5–8 phases; this milestone has 8, structured as a four-tier dependency graph)
**Coverage:** 58/58 v1 requirements mapped (no orphans)
**Core Value:** Blind and visually-impaired players can play full chess games independently — every state change is reliably announced or felt, with no missing or wrong information.

## Milestone Goal

Deliver a Foundation & Polish milestone that makes OpenBoard demo-able to a blind user with no apologies: every documented bug is fixed, save/load and clock infrastructure exist, sound and visual accessibility are layered in, and keyboard / announcement controls are configurable per event.

## Phase Structure

The milestone is organized as a **four-tier dependency graph**, not a flat sequence. Tier 0 is a strict prerequisite for everything; Tier 1 phases are parallel-safe; Tier 2 phases are independent siblings consuming Tier 1; Tier 3 phases integrate everything below.

```
Tier 0 (sequential)         Tier 1 (parallel)          Tier 2 (parallel)            Tier 3 (parallel)
─────────────────           ───────────────────        ───────────────────          ───────────────────
Phase 1: Tech Debt   ─┬──►  Phase 2a: GameSerializer ─┬─► Phase 3a: Clock     ─┬─► Phase 4a: SoundService
                      │                                │                         │
                      └──►  Phase 2b: Settings ext.   ─┼─► Phase 3b: Verbosity ─┘
                                                       │                         
                                                       └─► Phase 3c: Theme +    ──► Phase 4b: Autosave +
                                                            scale + rebind          PGN clock integration
```

## Phases

- [ ] **Phase 1: Tech Debt Cleanup** — Fix every documented bug and tech-debt item; establish forwarder, model-routed, and platformdirs patterns inherited by every later phase.
- [ ] **Phase 2a: GameSerializer (PGN + FEN)** — Save and load games and positions with full headers, error surfacing, and actionable spoken errors.
- [ ] **Phase 2b: Settings Extension** — Add SoundSettings, ClockSettings, ThemeSettings, VerbositySettings as siblings of existing settings, persisted via JSON in platformdirs.
- [ ] **Phase 3a: Clock Infrastructure** — Sudden-death + Fischer + clocks-off time controls, drift-free monotonic timestamping, ClockPanel, low-time announcements, ClockAwareDialog modal pause.
- [ ] **Phase 3b: Verbosity & AnnounceFilter** — Per-event verbosity tiers across nine categories with three preset profiles and a forced repeat-last command.
- [ ] **Phase 3c: Theme, Scale, and Key Rebinding** — High-contrast theme with WCAG-AA composited highlights, three discrete board scales, and an in-app key-rebinding dialog with reserved-shortcut blocklist.
- [ ] **Phase 4a: SoundService** — Categorised SFX (move/capture/check/castle/game-end/low-time tick) with per-channel mixing, announce-then-SFX ordering, graceful no-device degrade, cross-platform parity.
- [ ] **Phase 4b: Autosave Wiring + PGN Clock Integration** — Atomic autosave on every move with crash recovery, resume prompt, PGN [%clk] round-trip so restored games preserve clock state.

## Phase Details

### Phase 1: Tech Debt Cleanup

**Goal**: Every documented bug from `.planning/codebase/CONCERNS.md` is fixed, and the structural patterns (signal forwarders on `Game`, model-routed navigation, `platformdirs` for persistence, specific menu IDs, `move_made(old_board, move_kind)` payload) that every later phase inherits are established once, correctly.
**Depends on**: Nothing (Tier 0 — sequential prerequisite)
**Requirements**: TD-01, TD-02, TD-03, TD-04, TD-05, TD-06, TD-07, TD-08, TD-09, TD-10, TD-11, TD-12, TD-13, TD-14
**Success Criteria** (what must be TRUE):
  1. After starting a new game and pressing undo, the user hears the undo announcement (TD-01: `move_undone` is reconnected after `Game.new_game()`).
  2. Asking "what attacks this square?" with a pinned attacker on the board correctly names the pinned attacker (TD-04: uses `board.attackers()` not legal-move iteration).
  3. Pressing menu items other than "Load PGN" never inadvertently triggers the PGN load handler (TD-05: bound to a specific menu ID, not `wx.ID_ANY`).
  4. On a fresh install on Windows, macOS, and Linux, settings, keyboard config, autosave, and the engines directory all live under the OS-standard user-data location — and any pre-existing files in `cwd` are migrated automatically on first launch (TD-12: `platformdirs` migration).
  5. Each fix from TD-01..TD-13 has a regression test that fails on the buggy code and passes on the fixed code (TD-14).
**Plans:** 5 plans
- [x] 01-01-PLAN.md — Signal pattern refactor (Wave 1): Game.move_undone forwarder, MoveKind IntFlag payload, model-routed replay_to_position; eliminates _pending_old_board and the O(n) replay fallback (TD-01, TD-02, TD-03, TD-14)
- [x] 01-02-PLAN.md — Engine-adapter cleanup (Wave 2): delete _simple API; extract _resolve_move_context; remove sync request_computer_move; remove player_color (TD-06, TD-07, TD-08, TD-10, TD-14)
- [x] 01-03-PLAN.md — Bug fixes & menu hygiene (Wave 2): board.attackers() rewrite; specific menu IDs; drop \\tB accelerator; BoardState.board_ref property (TD-04, TD-05, TD-09, TD-13 perf slice, TD-14)
- [x] 01-04-PLAN.md — Persistence paths & security hardening (Wave 2): platformdirs migration; SSL context; SHA-256 verification; ZIP path-traversal guard (TD-12, TD-13 security slice, TD-14)
- [x] 01-05-PLAN.md — Exception hierarchy & test-discipline finalisation (Wave 3): prune unused types; wire up EngineTimeoutError/EngineProcessError raises; produce tests/CONCERNS_TRACEABILITY.md (TD-11, TD-14)

### Phase 2a: GameSerializer (PGN + FEN save/load)

**Goal**: Users can save and load full games as PGN, save and load positions as FEN, and receive actionable spoken errors when a file is malformed — without losing any in-progress data and without silently dropping content.
**Depends on**: Phase 1 (consumes platformdirs paths and the `move_made(old_board, move_kind)` payload pattern)
**Requirements**: PER-01, PER-02, PER-03, PER-04, PER-05, PER-09
**Success Criteria** (what must be TRUE):
  1. User saves a finished game to `.pgn`; reopening it in a third-party tool (Lichess upload, ChessBase) shows the full Seven Tag Roster, `Result`, and (when clocks were on) `TimeControl` headers (PER-01).
  2. User loads a multi-game PGN file (Lichess export with 50+ games) and either picks a game from a screen-reader-friendly picker or hears "Game N of M loaded" — never silent truncation (PER-02, PER-03).
  3. User pastes a FEN with the rook returned to its starting square but castling rights set; the load reports the corrected castling rights via spoken announcement and applies the position rather than silently rejecting it (PER-05).
  4. User saves the current position to a FEN string (clipboard or file) and pastes it back into a fresh launch to restore the same position (PER-04).
  5. The autosave file format is JSON validated by pydantic with a `schema_version` field; loading a file with a future schema version raises a recoverable, user-readable error (PER-09).
**Plans**: TBD

### Phase 2b: Settings Extension

**Goal**: The `Settings` singleton gains four new dataclass fields (`SoundSettings`, `ClockSettings`, `ThemeSettings`, `VerbositySettings`) with JSON persistence via platformdirs, a versioned schema, and a module-level `settings_changed` signal — providing the configuration substrate that Phases 3a, 3b, 3c, and 4a all consume.
**Depends on**: Phase 1 (consumes `platformdirs` migration; settings file lands at `user_config_dir / "settings.json"`)
**Requirements**: (none — this is an infrastructural prerequisite phase; user-visible behavior surfaces in Phases 3a, 3b, 3c, and 4a, which reference these settings)
**Success Criteria** (what must be TRUE):
  1. After a user-driven change (e.g. mutating defaults via tests or via an early dialog stub), `settings.json` written under `platformdirs.user_config_dir / "openboard"` contains `sound`, `clock`, `theme`, and `verbosity` blocks alongside the existing `ui` and `engine` blocks, with a top-level `version: 1`.
  2. Launching the app, mutating any new settings field, quitting, and relaunching shows the mutated value still applied — settings round-trip across launches.
  3. Loading a settings file written by an older code revision (missing one of the new blocks) silently fills in defaults; loading one with unknown extra keys logs a warning but does not crash.
  4. A `settings_changed.send(category=...)` named signal fires on every category mutation, and at least one subscriber test asserts the category string matches the field that was changed.
**Plans**: TBD

### Phase 3a: Clock Infrastructure

**Goal**: Users can choose a time control before a game, watch each side's clock decrement drift-free during their turn, hear low-time announcements, read the remaining time on demand, and trust that opening any modal dialog mid-game pauses both clocks.
**Depends on**: Phase 1 (forwarder pattern), Phase 2b (`ClockSettings` provides defaults and low-time threshold)
**Requirements**: CLK-01, CLK-02, CLK-03, CLK-04, CLK-05, CLK-06, CLK-07, CLK-08, CLK-10
**Success Criteria** (what must be TRUE):
  1. User starts a 5+3 game, plays for 60 seconds, and the displayed remaining time matches `5:00 - 60s + 3s × moves_made` to within 100 ms — no drift across long games (CLK-02, CLK-03).
  2. User opens the Settings dialog mid-game, leaves it open for 30 seconds, closes it, and zero clock time has elapsed on either side (CLK-04 — `ClockAwareDialog` enforces pause for every v1 modal).
  3. User presses `c` (rebindable) at any time during their turn and hears their own remaining time first, then the opponent's, formatted naturally ("4 minutes 32 seconds") (CLK-06).
  4. When either side's clock crosses zero, the game ends with a spoken result (`0-1 on time` or `1-0 on time`), no further moves are accepted, and the result is reflected in the game-over announcement (CLK-07, CLK-08).
  5. The `ClockPanel` view renders both clocks; its size and contrast scale with the active theme and board-scale settings (CLK-10).
  6. With `clocks-off` selected (CLK-01), no clock UI is rendered, no clock announcements fire, and no `TimeControl` header is added on PGN export.
**Plans**: TBD
**UI hint**: yes

### Phase 3b: Verbosity & AnnounceFilter

**Goal**: Every announcement in the app routes through a single `_announce(category, text)` helper on `ChessController` that consults `VerbositySettings`, so users can independently configure nine event categories, switch among three preset profiles with one keystroke, and force the last announcement to repeat verbatim.
**Depends on**: Phase 1 (announcement call sites are touched after the navigation/announcement bug fixes), Phase 2b (`VerbositySettings`)
**Requirements**: KEY-07, KEY-08, KEY-09, KEY-10, KEY-11
**Success Criteria** (what must be TRUE):
  1. User opens the verbosity dialog and sees nine rows (move-own, move-opponent, navigation-square, navigation-piece, hint, low-time, status, book, error), each with a single `wx.Choice` dropdown for OFF / TERSE / VERBOSE — operable end-to-end with NVDA, VoiceOver, or Orca using only Tab and arrow keys (KEY-07, KEY-09).
  2. With "navigation-square" set to OFF, the user navigates the board with arrow keys and hears no square names; toggling it back to VERBOSE restores them — without restarting the app (KEY-07).
  3. Pressing the verbosity-rotate keystroke cycles through "Minimal" → "Standard" → "Verbose" preset profiles, announcing the new profile name on each rotation (KEY-08).
  4. Pressing the "repeat last announcement" keystroke twice in a row produces two utterances of the same text (Lichess blind-mode notable failure mode that v1 explicitly addresses) (KEY-11).
  5. Every existing `self.announce.send(...)` call site in `ChessController` has been refactored to route through `self._announce(category, text)`; an audit grep finds zero direct sends outside the helper (KEY-10).
**Plans**: TBD
**UI hint**: yes

### Phase 3c: Theme, Scale, and Key Rebinding

**Goal**: Low-vision users can switch to a high-contrast theme with composited highlights that hold WCAG-AA contrast at any of three board scales; all keyboard users can open an in-app key-rebinding dialog that captures by keycode (not Unicode), refuses to overwrite screen-reader chords, detects conflicts, and reloads on save without a restart.
**Depends on**: Phase 1 (`platformdirs`-resolved `keyboard_config.json`, removal of `&Book Hint\tB` accelerator), Phase 2b (`ThemeSettings`)
**Requirements**: VIS-01, VIS-02, VIS-03, VIS-04, VIS-05, VIS-06, KEY-01, KEY-02, KEY-03, KEY-04, KEY-05, KEY-06
**Success Criteria** (what must be TRUE):
  1. User toggles the high-contrast theme from the View menu (or rebound shortcut); every `(square color × highlight combination × scale factor)` tuple in the active palette passes WCAG AA (≥3:1 graphical-objects threshold), verified by a parametrized unit test matrix (VIS-01, VIS-02).
  2. With the user's king in check on the last-moved-to selected square, the rendered square uses **state precedence** (focus > check > selected > last-move target > last-move origin > legal-move dot) so overlays replace rather than blend; check is also indicated by a non-color cue (border style or pattern) per WCAG 1.4.1 (VIS-03, VIS-04).
  3. User chooses a board size from at least three discrete options (small / medium / large); pieces and borders scale proportionally and persist across launches (VIS-05, VIS-06).
  4. User opens the key-rebinding dialog from Settings, presses `Insert+letter` while attempting to bind a NVDA-reserved chord, and the dialog rejects the binding with a spoken explanation rather than silently overwriting it (KEY-01, KEY-03).
  5. User binds the same chord to two different actions; the dialog announces the conflict and refuses to save until the user resolves it; pressing reset-to-defaults via the keyboard alone restores the shipped bindings and announces confirmation (KEY-04, KEY-05).
  6. After saving, the new bindings take effect immediately without a restart, and round-tripping through `keyboard_config.json` (close dialog, reopen) shows the same chords; tested with German QWERTZ and French AZERTY layouts via captured `wx.KeyCode` + modifier flags (KEY-02, KEY-06).
**Plans**: TBD
**UI hint**: yes

### Phase 4a: SoundService

**Goal**: Distinct sound effects play for own-move, opponent-move, capture, check, castle, and game-end across all three platforms; SFX never mask the screen-reader announcement; per-category mute, master volume, and per-category volume persist across sessions; the sound subsystem fails silently and gracefully when no audio device is present.
**Depends on**: Phase 1 (`Game.move_made(old_board, move_kind)` payload), Phase 2b (`SoundSettings`), Phase 3a (clock signals for low-time tick and flag-fall), Phase 3b (`_announce` helper for ordering — announce first, then `wx.CallLater(150–300ms, ...)` SFX)
**Requirements**: SND-01, SND-02, SND-03, SND-04, SND-05, SND-06, SND-07, SND-08
**Success Criteria** (what must be TRUE):
  1. Five back-to-back captures play five distinct capture sounds without truncation (SND-01: per-category mixer channels; SND-07: pre-loaded `Sound` objects with zero cold-start latency mid-game).
  2. With NVDA running, a capture-with-check move plays the screen-reader announcement first, then the SFX after a configurable 150–300 ms delay; the announcement's first syllable is never masked (SND-04).
  3. User opens sound settings, mutes "own move", sets master volume to 30%, quits and relaunches; settings are restored exactly (SND-02, SND-03).
  4. With low-time tick enabled and remaining time below threshold, a narrow-band tick plays once per second on the moving side's clock; with low-time tick disabled (default), no tick fires (SND-05).
  5. Launching the app on a machine with no audio device available (or in headless CI with `SDL_AUDIODRIVER=dummy`) starts and runs to completion with sound disabled and no traceback (SND-06).
  6. Manual cross-platform smoke test on Windows, macOS, and Linux PyInstaller artifacts confirms identical sound behavior on all three before each release (SND-08); SFX assets ship as 16-bit 44.1 kHz mono OGG Vorbis (SND-07).
**Plans**: TBD

### Phase 4b: Autosave Wiring + PGN Clock Integration

**Goal**: The user's in-progress game auto-saves on every move with a crash-safe atomic write; on next launch, an autosave triggers a resume prompt; restored games preserve both the position and the per-side remaining clock time via PGN `[%clk]` annotations that round-trip on save and load.
**Depends on**: Phase 2a (`GameSerializer` PGN/FEN APIs), Phase 3a (`Clock` state must be queryable for PGN annotation and serialisable for autosave)
**Requirements**: PER-06, PER-07, PER-08, CLK-09
**Success Criteria** (what must be TRUE):
  1. User saves a game in progress, force-kills the process (`SIGKILL` mid-write), relaunches; the resume prompt appears, default focus on Resume, and accepting it restores the position with the same clock state (PER-06, PER-07, CLK-09).
  2. User declines the resume prompt; the autosave is cleared and a new game begins (PER-07, PER-08).
  3. After a game ends naturally (checkmate, stalemate, time-out, user "New Game"), the autosave file is removed; the next launch starts fresh with no resume prompt (PER-08).
  4. User saves a finished game to PGN with clocks-on; opening the file shows `{ [%clk H:MM:SS] }` annotations after every move; loading the file back restores the per-side remaining time displayed in the `ClockPanel` (CLK-09).
  5. Atomic write is verified: an instrumented test that injects `SIGKILL` mid-write, on subsequent load, recovers either the new state or the one-generation `.bak` fallback — never crashes on parse, never silently loses both copies (PER-06).
**Plans**: TBD

## Coverage

All 58 v1 requirements are mapped to exactly one phase. No orphans. No duplicates.

| Tier | Phase | Requirement Count |
|------|-------|-------------------|
| 0 | 1: Tech Debt | 14 (TD-01..TD-14) |
| 1 | 2a: GameSerializer | 6 (PER-01..PER-05, PER-09) |
| 1 | 2b: Settings Extension | 0 (infrastructural) |
| 2 | 3a: Clock Infrastructure | 9 (CLK-01..CLK-08, CLK-10) |
| 2 | 3b: Verbosity & AnnounceFilter | 5 (KEY-07..KEY-11) |
| 2 | 3c: Theme + Scale + Rebinding | 12 (VIS-01..VIS-06, KEY-01..KEY-06) |
| 3 | 4a: SoundService | 8 (SND-01..SND-08) |
| 3 | 4b: Autosave + PGN clock | 4 (PER-06, PER-07, PER-08, CLK-09) |
| | **Total** | **58 / 58** |

## Phase Ordering Rationale

- **Phase 1 (Tier 0) must come first** — every later phase inherits the signal-forwarder, model-routed-navigation, and `platformdirs` patterns established here. Doing this once correctly costs less than retrofitting three times.
- **Phases 2a and 2b (Tier 1) are parallel-safe** — `GameSerializer` and the `Settings` extension share no state and can ship as independent PRs.
- **Phases 3a, 3b, 3c (Tier 2) fan out from Tier 1** — Clock needs `ClockSettings`, verbosity needs `VerbositySettings`, theme/scale/rebinding need `ThemeSettings` plus the Tier 0 keyboard-config-path migration. Three independent flows.
- **Phase 4a (Tier 3) is last because its subscribe-map needs every upstream signal** — `SoundService` consumes the Tier 0 `move_made(old_board, move_kind)` payload, the Tier 2 clock signals, and the Tier 2 `_announce` filter (for ordering). Building it last means the subscribe-map is final on first write.
- **Phase 4b (Tier 3) integrates `GameSerializer` + `Clock`** — autosave includes per-side remaining time via PGN `[%clk]` annotations, so the format is final only when both upstream phases ship. PER-09 (autosave format spec) lands in Phase 2a; PER-06/07/08 (autosave wiring) and CLK-09 (PGN clock round-trip) land here.

## Research Flags

Phases that may benefit from `/gsd-research-phase` deeper research during planning:

- **Phase 4a (SoundService)** — cross-platform manual playback verification on Windows/macOS/Linux PyInstaller artifacts is mandatory; PipeWire cold-start latency, hardened-runtime sandbox refusal, and WASAPI exclusive-mode behaviors need real-device validation, not just CI smoke tests. Spike a small playback test on each platform before locking the SoundService API.
- **Phase 3c (KeyRebindDialog)** — non-US keyboard layout behavior of `EVT_CHAR_HOOK` needs a VM test (German QWERTZ + French AZERTY at minimum) before writing the dialog. NVDA / JAWS / Orca reserved-shortcut blocklist needs empirical verification per current screen-reader version.
- **Phase 3c (high-contrast theme)** — the `(square × highlight × scale)` contrast matrix needs designer iteration with a colorimeter or `scripts/check_theme_contrast.py`; the high-contrast palette is data, not code, but getting all 64+ combinations to ≥ 3:1 may require multiple passes.

Phases with standard patterns (skip research-phase): Phase 1, Phase 2a, Phase 2b, Phase 3a, Phase 3b, Phase 4b.

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Tech Debt Cleanup | 0/5 | Planning complete | - |
| 2a. GameSerializer | 0/0 | Not started | - |
| 2b. Settings Extension | 0/0 | Not started | - |
| 3a. Clock Infrastructure | 0/0 | Not started | - |
| 3b. Verbosity & AnnounceFilter | 0/0 | Not started | - |
| 3c. Theme, Scale, and Key Rebinding | 0/0 | Not started | - |
| 4a. SoundService | 0/0 | Not started | - |
| 4b. Autosave + PGN clock integration | 0/0 | Not started | - |

---
*Roadmap created: 2026-04-27 by `/gsd-new-project` orchestrator*
*Last updated: 2026-04-27*

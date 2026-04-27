# Project Research Summary

**Project:** OpenBoard — v1 Foundation & Polish milestone
**Domain:** Accessible desktop chess GUI (wxPython MVC + blinker signals + asyncio engine), screen-reader-first
**Researched:** 2026-04-27
**Confidence:** HIGH overall (stack, architecture, pitfalls verified against current docs and existing codebase; features and verbosity-tier conventions MEDIUM-HIGH).

## Executive Summary

OpenBoard is a mature, accessibility-first desktop chess GUI in mid-life. The v1 milestone is **strictly additive** — it does not rewrite any subsystem. Research across stack, features, architecture, and pitfalls converges on a tight conclusion: the entire v1 surface (clocks, sound, PGN/FEN, autosave, high-contrast theme, scale, key-rebinding, verbosity tiers) can be delivered with **one new runtime dependency** (`pygame>=2.6.1`, `mixer` subsystem only) and **one new dev/runtime utility** (`platformdirs`). Everything else builds on existing stack pieces (python-chess for PGN/FEN, pydantic for serialization, stdlib `time.monotonic` + `wx.Timer` for the clock, stock wxPython widgets for settings dialogs).

The non-negotiable insight from synthesis is **sequencing**: a small Tier-0 batch of tech-debt fixes from `.planning/codebase/CONCERNS.md` are *structural prerequisites*, not parallel work. The `move_undone` signal-rehook fix establishes the canonical "forward-through-`Game`" pattern that the new `Clock` signals must use; the `_pending_old_board` → `move_made(old_board=...)` refactor is the only way `SoundService` can detect captures/castles without re-creating a peek-into-model anti-pattern; the `wx.ID_ANY` PGN-bind bug must be fixed before any new menu items land or the new menus inherit the same fallback-handler bug; the `platformdirs` migration must precede *all* new persistence (settings, autosave, keyboard config) or each new file lands in `cwd` and inherits the same security/UX defect; and the dead `_simple` API removal narrows the surface that downstream phases must reason about.

The principal risks are cross-platform sound (PipeWire cold-start latency on Linux, hardened-runtime sandboxing on macOS, WASAPI exclusive-mode lockouts on Windows), atomic file writes (macOS `os.fsync` is a partial no-op without `F_FULLFSYNC`), non-US keyboard rebinding (`EVT_CHAR_HOOK` is layout-dependent, dead keys produce no event until composed), NVDA's lack of audio ducking (SFX masking the announcement's first syllable — solved by announce-then-`wx.CallLater`-SFX ordering), and WCAG-AA contrast holding under *composited* highlight overlays (selected + check + last-move stacks, not just isolated states). All five risks have known, documented mitigations folded into the architecture decisions.

## Key Findings

### Recommended Stack

The locked existing stack (Python 3.12+, wxPython 4.2.5, python-chess 1.11.2, blinker 1.9.0, accessible-output3 git-HEAD, pydantic 2.12.5, pytest, ruff, ty, PyInstaller) is preserved. v1 adds **only**:

**Core technologies (additions):**
- **`pygame>=2.6.1` (`pygame.mixer` subsystem only)** — cross-platform SFX layer. Picked because it has wheels for Python 3.12/3.13 on Win/macOS/Linux, supports per-channel mixing (overlapping SFX without truncation), per-clip volume, native WAV/OGG decoding, and a non-blocking `Sound.play()` that won't stall the wx main loop. **Critical:** call `pygame.mixer.pre_init(...)` then `pygame.mixer.init()` early in `main()` — never `pygame.init()`, which would activate display/event subsystems and fight wxPython.
- **`platformdirs`** — replaces `Path.cwd()`-relative resolution for settings, autosave, engines, and keyboard config. Fixes an existing CONCERNS.md security/UX defect while landing the new persistence files in correct OS-standard locations.
- **`python-chess` (already locked)** — covers PGN/FEN end-to-end, including STR headers, `[%clk H:MM:SS]` annotations (we write the token into `node.comment` ourselves; trivial helper), `Board.status()` flag bitmask for actionable FEN errors, and `Board.attackers()` for the corrected attacking-pieces feature.
- **stdlib `time.monotonic()` + `wx.Timer`** — chess clock. No library; a 50-line state machine. `wx.Timer` only triggers redraw/recheck; truth lives in monotonic timestamps so missed/late ticks never introduce drift.
- **JSON via pydantic `model_dump_json` + `os.replace()`** — autosave. Atomic write pattern (`tmp + flush + fsync + replace`); on macOS use `fcntl.F_FULLFSYNC` because `os.fsync` is a partial no-op there.
- **stock wxPython widgets** (`wx.Dialog`, `wx.Notebook`, `wx.Choice`, `wx.Slider`, `wx.CheckBox`, `wx.TextCtrl` w/ `EVT_KEY_DOWN`) — settings UI. **Reject `wx.PropertyGrid`** (Win-only `wx.Accessible` MSAA support; uncertain VoiceOver/Orca behavior). **Reject `wx.Grid`** for verbosity dialog (NVDA reads cells as "row 4 column 2 radio").

**Explicitly rejected alternatives:** `simpleaudio` (archived 2022, no Py 3.12 wheel guarantee, no volume API), `playsound` 1.x (unmaintained, macOS PyObjC drama), `playsound3` (no per-channel mixing for overlapping SFX), `wx.adv.Sound` (WAV-only, no volume API, single-clip-at-a-time, dead Linux backend), `wx.MediaCtrl` (pulls in GStreamer/DirectShow/AVFoundation), `miniaudio`/`just_playback` (Windows compile risk for PyInstaller bundles), `pickle` for autosave (schema brittleness, RCE risk), MP3 assets (use OGG Vorbis or short WAV).

See `.planning/research/STACK.md` for full rationale and version compatibility matrix.

### Expected Features

**Must have (table stakes — v1 isn't credible without these):**
- Clocks: sudden-death + Fischer increment + clocks-off; on-demand readout (`c`-key Lichess-style); low-time threshold callout; clock-pause for *every* modal mid-game.
- Sound layer: distinct SFX for own-move, opponent-move, capture, check, castle, game-end; per-category mute + master volume; settings persist; **announce first, SFX after a short `wx.CallLater` delay** (NVDA has no ducking).
- PGN save/load with full Seven Tag Roster + `Result` + `TimeControl` headers; load any standards-compliant PGN; surface `game.errors` after `read_game`; multi-game files at minimum trigger a picker (or announce "Game 1 of N loaded").
- FEN save/load with **actionable spoken errors** mapped from `Board.status()` flags; tolerant en-passant handling (accept old + new spec); `clean_castling_rights()` correction announced rather than rejected.
- Auto-save in-progress game + resume prompt on next launch + clear on graceful end. Atomic write with `os.replace()` and `.bak` fallback for corruption recovery.
- High-contrast theme (≥1 preset beyond default) with all four piece-on-square pairings ≥ WCAG AA (3:1 graphical) **and the highlight-composite matrix held to spec** (selected + check + last-move stacking).
- Adjustable board scale (≥3 discrete sizes); persists; borders scale proportionally.
- In-app key-rebinding dialog with conflict detection, reset-to-defaults, and reserved-shortcut blocklist (NVDA `Insert+*`, JAWS `Insert+*`, Orca `CapsLock+*`, OS chords `Cmd+Q` / `Alt+F4`).
- Per-event verbosity tiers (≥9 categories, OFF/TERSE/VERBOSE), three preset profiles ("Minimal" / "Standard" / "Verbose"). Filter sits in the controller (single `_announce(category, text)` helper), not the view.

**Should have (differentiators):**
- PGN round-trip preserves `[%clk H:MM:SS]` annotations (most desktop apps lose them).
- Spoken `Board.status()`-derived FEN errors ("FEN looks good but castling rights say white can castle kingside, yet the white king has moved").
- "Repeat last announcement" command that *forces re-utterance* (Lichess blind mode famously fails this).
- Clock ticking SFX under low time (small but pointed differentiator — falls out of clock + sound integration).
- Verbosity-profile rotate keystroke.

**Defer (v1.x or v2+):**
- Bronstein / simple-delay clock formats (only Fischer required for v1).
- Multi-stage TimeControl *playable* (parse + display only in v1).
- Full multi-game PGN library browser → v2.
- Custom sound packs / theme uploads (anti-feature; ship one well-tuned set).
- Hourglass time control (anti-feature; near-zero adoption).
- Voice command input (out of scope by design).
- Chess960 / variant FEN (out of scope; `Board(chess960=True)` only as Shredder-FEN fallback during load).
- Per-user verbosity profiles, in-app announcement-text editor, continuous time-remaining narration (all anti-features).

See `.planning/research/FEATURES.md` for the full prioritization matrix and competitor comparison.

### Architecture Approach

The existing wxPython MVC + blinker-signal architecture is preserved. v1 adds five new components and four new `Settings` dataclass fields, plus signal forwarders on `Game` for clock and richer `move_made` payloads. **No new background threads.** The single-asyncio-loop, single-mixer-thread, single-main-thread model is sufficient.

**Major components (new):**
1. **`Clock` (model)** — pure-Python state machine in `openboard/models/clock.py`. Composed by `Game`. Pure `tick(now_ns)` API for testability (no wx coupling). `wx.Timer` lives in `ChessFrame`; on `EVT_TIMER` the controller calls `clock.tick(time.monotonic_ns())`. Emits `tick`, `low_time`, `flag_fall`, `paused`, `time_control_changed` — but **only via `Game` forwarders** (`Game.clock_tick` etc.). Subscribers never bind to `game.clock.X` directly (this is the fix-pattern from the `move_undone` regression).
2. **`GameSerializer` (model)** — `openboard/models/game_serializer.py`. Owns PGN/FEN export/import and autosave/restore. Autosave is **signal-driven debounced** via `wx.CallLater(500, ...)` on `move_made`/`status_changed` (not periodic `wx.Timer`). Atomic three-step write (`tmp + fsync/F_FULLFSYNC + os.replace`).
3. **`SoundService` (view-layer service, not a wx widget)** — `openboard/views/sound_service.py`. Single subscriber to `Game.move_made` (extended with `old_board` and `MoveKind` enum), `Game.status_changed`, `Game.clock_tick`/`flag_fall`, `Game.computer_thinking`. Owns `pygame.mixer` lifecycle. **Init at startup, not lazily** (cold-device latency happens once at boot, not mid-game). Pre-load all `Sound` objects into memory.
4. **`AnnounceFilter` (controller-internal)** — `_announce(category, text)` helper on `ChessController` that consults `VerbositySettings` and forwards to the existing `announce` signal only if enabled. **Single off-switch per category, single point of truth.**
5. **`KeyRebindDialog` (view)** + `KeyRebinder` helper — `openboard/views/key_rebind_dialog.py`. Reload-on-save semantics: build fresh `GameKeyboardConfig`, validate via pydantic, persist to `platformdirs.user_config_dir / "keyboard_config.json"`, then `frame.replace_keyboard_config(new)` rebuilds the dispatch table.

**`Settings` extension:** add `SoundSettings`, `ClockSettings`, `ThemeSettings`, `VerbositySettings` as siblings of existing `UISettings` / `EngineSettings`. New module-level signal `settings_changed.send(category=...)` for live-reactive surfaces. Persist via `dataclasses.asdict()` to `platformdirs.user_config_dir / "settings.json"` with a `version: 1` field for future migrations.

**Signal extension on `Game`:** `move_made` gains `old_board: chess.Board` and `move_kind: MoveKind` (`QUIET | CAPTURE | CASTLE | EN_PASSANT | PROMOTION | CHECK`). This is a load-bearing refactor — it kills the fragile `_pending_old_board` shared mutable state (CONCERNS.md "Fragile Areas") and lets `SoundService` detect categories without peeking at `controller.game.board_state.board`.

See `.planning/research/ARCHITECTURE.md` for per-capability integration decisions and signal taxonomy.

### Critical Pitfalls

The full risk register is in `.planning/research/PITFALLS.md`. The five highest-priority items, each with the architectural answer:

1. **Move SFX masking screen-reader announcements** — NVDA has no audio ducking (verified, NVDA tracker #17349). **Avoid:** announce first, then schedule SFX with `wx.CallLater(150-300ms, ...)`. Make delay user-configurable. Use narrow-band tones for ticks (wide-spectrum sounds mask speech formants).
2. **Clock drift from per-tick decrement** — `wx.Timer` is documented as "not better than 1 ms nor worse than 1 s." **Avoid:** `wx.Timer` is only a redraw signal. Truth lives in `time.monotonic()` timestamps captured on each move-commit. Compute `remaining` at display time, not by subtracting per tick. **Use `time.monotonic()`, never `time.time()`.**
3. **Auto-save torn writes on crash** — `open(path, "w")` truncates first; tmp-then-rename without fsync is durable on the rename but not the contents (especially on macOS where `os.fsync` is a no-op for some filesystems). **Avoid:** three-step atomic write (`tmp.write` → `flush` + `fsync` / `F_FULLFSYNC` on macOS → `os.replace`). Throttle to ≤1 save / 500 ms via `wx.CallLater` debounce. Keep one-generation `.bak` fallback. Run write off the main thread (serialize on main, write in background).
4. **Rebinding overwrites screen-reader hotkeys / fails on non-US layouts** — NVDA reserves `Insert+*` and `CapsLock+*` system-wide; `EVT_CHAR_HOOK` is documented layout-dependent; dead keys produce no event until composed. **Avoid:** maintain `RESERVED_SHORTCUTS` blocklist; capture by `wx.KeyCode` + modifier flags (layout-stable), not Unicode characters; validate on load; provide reset-to-defaults reachable by keyboard alone; test on a German + French AZERTY VM before shipping.
5. **High-contrast theme passes WCAG AA in isolation but fails composited** — chess UIs stack 3+ overlays per square (selected + check + last-move + cursor). Each pair-test passes; the blended pixel fails. **Avoid:** define a *state precedence* (focus > check > selected > last-move target > last-move origin > legal-move dot) so highlights *replace*, not blend. Add a unit test parametrized over every `(square_color × highlight_combination × scale_factor)` triple asserting ≥ 3:1. Also add a non-color cue for check (border style or pattern) per WCAG 1.4.1.

**Cross-cutting:** Clock must pause for *every* modal dialog (introduce a `ClockAwareDialog` base class; subclass it for every v1 modal). PGN load must check `game.errors` and detect multi-game files. FEN load must validate via `Board.is_valid()` and surface `Board.status()` flags; never construct FEN by hand. Sound init at startup not lazily. Verbosity dialog uses one `wx.Choice` per row, **never `wx.Grid`** (inaccessible).

## Implications for Roadmap

Synthesis across all four research files produces a clear **four-tier phase structure**. Tier 0 is sequential and prerequisite; Tiers 1–3 have intra-tier parallelism but a strict inter-tier order. The roadmapper should preserve this ordering — it is load-bearing, not advisory.

### Phase 1 (Tier 0): Tech-debt prerequisites — must come first

**Rationale:** Every later phase inherits patterns established (or bugs left) here. Doing this once, correctly, saves doing it 3× wrong across Tier 1–3 phases. This is a **structural prerequisite tier**, not a parallel cleanup.

**Delivers:**
- `move_undone` signal-rehook fix via `Game.move_undone` forwarder (CONCERNS.md Bug #1) — **establishes the canonical forwarding pattern that `Clock` signals use in Tier 2.**
- `Game.move_made` signal extended with `old_board: chess.Board` and `MoveKind` enum payload, replacing the fragile `_pending_old_board` shared mutable state (CONCERNS.md "Fragile Areas") — **prerequisite for `SoundService` capture/castle detection in Tier 3.**
- `_navigate_to_position` routed through `BoardState.make_move`/`undo_move` instead of bypassing the model (CONCERNS.md Bug #2) — **establishes "all moves go through the model" precedent that PGN/FEN load must follow.**
- `wx.ID_ANY` PGN-binding bug fixed (CONCERNS.md Bug #4) — **protects every new menu item added in Tier 1–3 (PGN save, FEN save, clock controls, theme toggle, scale slider, settings).**
- `platformdirs` migration for `engines_dir`, `config.json`, `keyboard_config.json` paths (CONCERNS.md Security #4) — **prerequisite for all new persistence (settings, autosave) in Tier 1.**
- `_simple` API surface removal in `EngineAdapter` (CONCERNS.md Tech Debt) — **narrows the surface Tier 2/3 must reason about.**
- `announce_attacking_pieces` rewritten to use `board.attackers()` (CONCERNS.md Bug #3 + Performance #2 — same fix).
- `&Book Hint\tB` accelerator double-bind removed (CONCERNS.md Tech Debt) — **prerequisite for key-rebinding dialog in Tier 2.**

**Avoids:** Pitfalls 2, 3, 7, 8 (re-creating signal-rehook bug class), Pitfall 4 (autosave-in-cwd), Pitfall 5 (rebinding dialog inheriting double-binding bugs).

### Phase 2 (Tier 1): Foundation — parallelizable

Two independent capabilities; can ship in parallel because neither depends on the other and both depend only on Tier 0.

**Phase 2a: `GameSerializer` — PGN + FEN save/load**
- Delivers: `Game.save_pgn`/`load_pgn` thin facades; PGN export with full STR + `Result` + `TimeControl` headers; PGN import with `game.errors` surfacing and multi-game detection; `Game.load_fen_position(fen)` with `Board.status()`-derived spoken error mapping; FEN round-trip test corpus (rook-returned, valid/invalid ep, Shredder-FEN, Cyrillic/Polish headers, malformed PGN).
- Uses: `python-chess` (existing). No new deps.
- Avoids: Pitfalls 7 (PGN edge cases), 8 (FEN edge cases). `[%clk]` annotations added in Tier 3 when clocks land — pre-clock the PGN simply lacks the annotation.

**Phase 2b: `Settings` extension — `SoundSettings`, `ClockSettings`, `ThemeSettings`, `VerbositySettings` + JSON persistence**
- Delivers: four new dataclass fields on `Settings`; `save()`/`load()` with `version: 1`; module-level `settings_changed` signal; defaults that match v1's UX recommendations (sound categories: own-move 50%, capture 60%, check 70%, low-time tick OFF; clock low-time threshold scales as `max(10s, 5% of base)`; verbosity defaults preserve current behavior).
- Uses: pydantic (existing), stdlib JSON, `platformdirs` (Tier 0).
- Avoids: Pitfall 4 (settings landing in `cwd`).

### Phase 3 (Tier 2): Mid tier — consumes Tier 1 foundation

Three independent capabilities. Each consumes one Tier 1 deliverable.

**Phase 3a: `Clock` model + `ClockPanel` view**
- Delivers: `Clock` and `TimeControl` in `openboard/models/clock.py`; `wx.Timer`-driven (100 ms) ticks via `controller.tick_clock(now_ns)`; `Game.clock_tick`/`low_time_warning`/`flag_fall`/`clock_paused`/`time_control_changed` forwarders; `ClockPanel` rendering both clocks; on-demand readout via `c`-key (Lichess-style); `ClockAwareDialog` base class to enforce pause-during-modal across all v1 dialogs; sudden-death + Fischer + clocks-off (Bronstein + simple-delay deferred to v1.x).
- Consumes: `ClockSettings` (Tier 1).
- Avoids: Pitfalls 2 (drift — timestamp-not-tick), 3 (no-pause-during-modal — `ClockAwareDialog`).

**Phase 3b: `AnnounceFilter` — verbosity tiers**
- Delivers: `AnnounceCategory` enum (`MOVE`, `NAV_SQUARE`, `NAV_PIECE`, `HINT`, `LOW_TIME`, `STATUS`, `BOOK`, `ERROR`, plus `AUTOSAVE` defaulting silent); `_announce(category, text)` helper on `ChessController`; mechanical refactor of every existing `self.announce.send(...)` call site to route through the helper; verbosity dialog using one `wx.Choice` per row + explicit `wx.StaticText` labels (NEVER `wx.Grid`); three preset profiles ("Minimal" / "Standard" / "Verbose") with one-key rotate keystroke.
- Consumes: `VerbositySettings` (Tier 1).
- Avoids: Pitfall 9 (inaccessible verbosity dialog — operating it must itself be a verbosity test, NVDA + Orca + VoiceOver mandatory).

**Phase 3c: High-contrast theme + adjustable scale + `KeyRebindDialog`**

Three closely-related view-layer additions that share dialog patterns and contrast/scale testing infrastructure. Can split into two sub-phases if scope demands.

- Delivers: `ThemeManager` resolving `ThemeSettings` → palette + piece glyphs; high-contrast preset with **state-precedence highlight composition** (no alpha blending of overlays); board scale (≥3 discrete sizes, persisted, debounced on slider release); `KeyRebindDialog` with reserved-shortcut blocklist, conflict detection, reset-to-defaults reachable via keyboard, key-capture by `wx.KeyCode` + modifier flags (not Unicode); `KeyRebinder` helper for validate-and-persist-then-swap reload-on-save; **theme-contrast matrix test parametrized over `(square × highlight_combo × scale_factor)`** asserting ≥ 3:1.
- Consumes: `ThemeSettings` (Tier 1) + Tier 0 keyboard-config-path migration.
- Avoids: Pitfalls 5 (rebinding overwrites a11y modifiers, non-US layouts), 6 (composited highlights fail WCAG).

### Phase 4 (Tier 3): Top tier — consumes everything

Two integration capabilities that consume Tier 1 + Tier 2 outputs. Last because their subscriber-maps are final only when all upstream signals exist.

**Phase 4a: `SoundService`**
- Delivers: `pygame.mixer.pre_init` + `init` early in `main()`; `SoundService` subscribed to `Game.move_made` (with `MoveKind`), `Game.status_changed`, `Game.clock_tick` (low-time tick), `Game.flag_fall`, `Game.computer_thinking`; per-category mixer channels (no truncation of overlapping SFX); pre-loaded `Sound` objects (zero cold-start latency mid-game); SFX as 16-bit 44.1 kHz mono OGG Vorbis; **announce-then-`wx.CallLater(150-300ms, ...)`-SFX ordering** with user-configurable delay; graceful degrade on no audio device (`SDL_AUDIODRIVER=dummy` for headless CI); cross-platform smoke test on Win/macOS/Linux PyInstaller artifacts before shipping.
- Consumes: `SoundSettings` (Tier 1), `MoveKind`/`old_board` move signal (Tier 0), `Game.clock_tick`/`flag_fall` (Tier 2), `_announce` filter (Tier 2 — for ordering).
- Avoids: Pitfalls 1 (SFX masking announcements), 10 (cross-platform sound regressions).

**Phase 4b: Autosave wiring**
- Delivers: `GameSerializer.autosave_path()` resolved via `platformdirs.user_state_dir`; signal-driven debounced save via `wx.CallLater(500, ...)` on `move_made` / `status_changed`; three-step atomic write (`tmp + flush + fsync`/`F_FULLFSYNC` on macOS + `os.replace`); one-generation `.bak` fallback; resume-prompt modal at startup (default focus on Resume); clear autosave on graceful end (game-over reached or user "New Game"); autosave **includes clock state** (`[%clk]` annotations + active-side + monotonic offset) so crash recovery preserves remaining time per side; serialize-on-main, write-on-background-thread (avoid UI hitch); SIGKILL-during-write recovery test.
- Consumes: `GameSerializer` (Tier 1) + `Clock` state (Tier 2 — clock ms must round-trip, otherwise crash recovery loses time).
- Avoids: Pitfall 4 (torn-state autosave).

### Phase Ordering Rationale

- **Tier 0 must precede everything.** The `move_undone` forwarding pattern, `move_made(old_board, move_kind)` payload, and `platformdirs` migration are inputs to multiple later phases; landing them once correctly costs less than retrofitting three times. This is the most important sequencing point in the milestone.
- **Tier 1 is parallel-safe.** `GameSerializer` and `Settings` extension share no state and can ship as independent PRs.
- **Tier 2 fans out from Tier 1.** Clock needs `ClockSettings`; verbosity needs `VerbositySettings`; theme/scale/rebinding need `ThemeSettings` + Tier 0 config-path migration. Three independent flows.
- **Tier 3 integrates everything.** `SoundService` subscribes to model + clock signals; autosave needs PGN + clock state. Building these last means their subscribe-maps and serialization formats are final on first write — no rework when Tier 2 lands.

### Research Flags

Phases likely needing deeper research during planning (`/gsd-research-phase`):
- **Phase 4a (SoundService):** cross-platform manual playback verification on Win/macOS/Linux PyInstaller artifacts is mandatory; PipeWire cold-start latency, hardened-runtime sandbox refusal, and WASAPI exclusive-mode behaviors need real-device validation, not just CI smoke tests. Spike a small playback test on each platform before locking the SoundService API.
- **Phase 3c (KeyRebindDialog):** non-US keyboard layout behavior of `EVT_CHAR_HOOK` needs a VM test (German QWERTZ + French AZERTY at minimum) *before* writing the dialog. NVDA / JAWS / Orca reserved-shortcut blocklist needs empirical verification per current screen-reader version.
- **Phase 3c (high-contrast theme):** the (square × highlight × scale) contrast matrix needs designer iteration with a colorimeter or `scripts/check_theme_contrast.py`; the high-contrast palette is data, not code, but getting all 64+ combinations to ≥ 3:1 may require multiple passes.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Tier 0):** every fix has line-numbered references in CONCERNS.md and a documented pattern in ARCHITECTURE.md (`Game` forwarder, model-routed navigation, specific menu IDs, `platformdirs`). No new research needed.
- **Phase 2a (GameSerializer):** `python-chess` PGN/FEN APIs are well-documented and verified in STACK.md; the test corpus is enumerated in PITFALLS.md.
- **Phase 2b (Settings extension):** straightforward dataclass + JSON pattern matching existing `UISettings` / `EngineSettings`.
- **Phase 3a (Clock):** state machine + `wx.Timer` cadence pattern is fully specified in ARCHITECTURE.md §1.
- **Phase 3b (AnnounceFilter):** mechanical refactor of existing call sites; the only design choice (`_announce(category, text)` helper vs. wrapping the `Signal`) is resolved in ARCHITECTURE.md §6.
- **Phase 4b (Autosave):** atomic-write pattern is canonical and verified in STACK.md + PITFALLS.md.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | `pygame.mixer` 2.6.1 verified against pygame docs; alternatives explicitly enumerated and rejected with citations; `python-chess` 1.11.2 PGN/FEN coverage verified via Context7. Only MEDIUM area is the **rebinding UI widget choice** (rooted in accessibility judgment more than benchmarks — but the widgets picked are stock and well-supported). |
| Features | HIGH | Lichess blind-mode commands directly read from official tutorial; PGN/FEN spec details from saremba.de + Wikipedia; WCAG contrast thresholds explicit. Verbosity-tier conventions are MEDIUM (NVDA tier model is documented, but per-event verbosity in chess apps is inferred from screen-reader-application convention rather than direct precedent — this is a design choice not a research gap). |
| Architecture | HIGH | Verified against existing code with line numbers; wxPython `wx.Timer`/`wx.CallAfter`/`wx.CallLater` semantics from Context7 official docs; signal-forwarder pattern is the established fix-pattern from CONCERNS.md Bug #1. |
| Pitfalls | HIGH for stack-specific items, MEDIUM for cross-platform sound and screen-reader interaction (verified with NVDA docs + wxPython docs but real-device a11y testing is the only HIGH bar — folded into Phase 4a research flag). |

**Overall confidence:** HIGH.

### Gaps to Address

- **PipeWire cold-start latency on Linux** — observed 200-400 ms in mailing-list reports, not benchmarked here. Verify on target hardware during Phase 4a; mitigate with startup-time `pygame.mixer.init()` (already in plan).
- **NVDA / JAWS / Orca reserved-shortcut exhaustive list** — only modifier-key cases (`Insert`, `CapsLock`) are explicitly documented; full list is empirical and changes between screen-reader versions. Plan for empirical testing during Phase 3c; the blocklist is data, easily patched in a hotfix.
- **macOS hardened-runtime + sandbox impact on `pygame.mixer`** — needs verification on a notarized .dmg build, not just `uv run`. Add to Phase 4a CI matrix.
- **PyInstaller `pygame` hook bundling** — STACK.md notes PyInstaller has a built-in pygame hook but flags "verify in build CI on first integration." First integration is Phase 4a.
- **Variation-display vs variation-preserve scope split for PGN load** — research enumerated the choice (preserve on save even if not displayed), but the v1 UX decision (do we render variations? if yes, where?) is open. Defer to Phase 2a planning.
- **`platformdirs` migration of `keyboard_config.json`** — existing `keyboard_config.json` files at user `cwd` will not be found after migration. Plan a one-shot migration helper in Phase 1 that moves any existing file to the new location.

## Sources

### Primary (HIGH confidence)
- `/wxwidgets/phoenix` (Context7) — `wx.Timer` periodic-event pattern, `wx.CallAfter` thread marshalling, `wx.CallLater` one-shot debounce, `wx.KeyEvent` non-US layout caveats, `wx.Accessible` Windows-only MSAA scope.
- `/niklasf/python-chess` (Context7) — PGN export/import, `chess.pgn.read_game`, `Game.errors`, `Board.status()`, `Board.attackers()`, `Board(fen, chess960=...)`, polyglot opening book.
- python-chess 1.11.2 docs — https://python-chess.readthedocs.io/en/latest/pgn.html, https://python-chess.readthedocs.io/en/latest/core.html
- pygame 2.6.1 release notes (Python 3.13 wheels, mixer subsystem) — https://github.com/pygame/pygame/releases
- pygame.mixer reference (`pre_init`, `Sound.set_volume`, `Channel.set_volume`, default 512-sample buffer) — https://www.pygame.org/docs/ref/mixer.html
- pygame manylinux wheels + PulseAudio (issue #1351) — https://github.com/pygame/pygame/issues/1351
- pydantic 2.x `model_dump_json` / `model_validate` — https://docs.pydantic.dev/latest/concepts/models/
- Atomic-write `os.replace()` (POSIX `rename(2)` + Windows `MoveFileExW`) — https://docs.python.org/3/library/os.html#os.replace
- PEP 418 `time.monotonic()` semantics — https://peps.python.org/pep-0418/
- WCAG 2.1 contrast (4.5:1 text, 3:1 graphical) — https://webaim.org/articles/contrast/
- Lichess blind-mode tutorial / guide / changelog — https://lichess.org/page/blind-mode-tutorial, https://lichess.org/page/blind-mode-guide
- PGN spec — http://www.saremba.de/chessgml/standards/pgn/pgn-complete.htm; https://en.wikipedia.org/wiki/Portable_Game_Notation
- FEN spec — https://en.wikipedia.org/wiki/Forsyth%E2%80%93Edwards_Notation; https://www.chessprogramming.org/Forsyth-Edwards_Notation
- NVDA 2025.x user guide (Insert/CapsLock modifier keys, audio-ducking limitation) — https://download.nvaccess.org/documentation/userGuide.html; tracker #17349
- `simpleaudio` archived status — https://snyk.io/advisor/python/simpleaudio
- `playsound` unmaintained / macOS PyObjC — https://github.com/TaylorSMarks/playsound/issues/5, /97
- `wx.adv.Sound` limitations (WAV-only, no volume) — https://docs.wxpython.org/wx.adv.Sound.html
- Existing repo: `.planning/codebase/CONCERNS.md` (8 bugs, 6 tech-debt items, fragile-area annotations with line numbers) — HIGH confidence: source-of-truth.
- Existing repo: `.planning/codebase/ARCHITECTURE.md`, `.planning/PROJECT.md`, `openboard/models/board_state.py`, `game.py`, `controllers/chess_controller.py`, `config/settings.py`, `config/keyboard_config.py` — direct code reading.

### Secondary (MEDIUM confidence)
- pygame.mixer as wxPython sound consensus — https://discuss.wxpython.org/t/playing-part-of-a-sound-cross-platform-in-wxpython/28145
- Atomic-write three-step pattern with macOS `F_FULLFSYNC` caveat — https://blog.elijahlopez.ca/posts/data-corruption-atomic-writing/
- `playsound3` non-blocking but no per-channel mixing — https://copyprogramming.com/howto/how-to-play-music-in-python
- `[%clk H:MM:SS]` PGN annotation as de facto standard (Lichess + chess.com) — https://en.wikipedia.org/wiki/Portable_Game_Notation §8.2.5
- Lichess sound categories (Move/Capture/Check/CheckCapture) — forum threads, not formally documented
- Hourglass time control adoption ("uncommon") — Wikipedia, Lichess feature-request threads, cutechess #273
- TTS-vs-SFX collisions / audio ducking — https://accessibleandroid.com/understanding-audio-ducking-on-android-talkback-jieshuo-and-operating-system-challenges/
- pygame-ce community fork — https://github.com/pygame-community/pygame-ce
- `SDL_AUDIODRIVER=dummy` for headless CI — https://discourse.libsdl.org/t/couldnt-open-audio-device-no-available-audio-device/18499

### Tertiary (LOW confidence — flagged for verification during phases)
- PipeWire cold-start latency 200-400 ms — observed in mailing-list reports; verify on target hardware in Phase 4a.
- NVDA / JAWS reserved-shortcut exhaustive list — empirical; verify per current screen-reader version in Phase 3c.
- macOS hardened-runtime + sandbox impact on `pygame.mixer` — verify in Phase 4a notarized .dmg build.

---
*Research completed: 2026-04-27*
*Ready for roadmap: yes*

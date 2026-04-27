# Feature Research

**Domain:** Accessible desktop chess GUI (screen-reader-first, keyboard-only) — v1 Foundation & Polish
**Researched:** 2026-04-27
**Confidence:** MEDIUM-HIGH (Lichess blind mode, FIDE/PGN spec, python-chess API confirmed via primary sources; verbosity-tier conventions inferred from NVDA/VoiceOver patterns and Lichess gaps)

## Scope Note

This research covers the v1 capabilities listed in `PROJECT.md` (Active section): clocks, sounds, PGN/FEN save+load, auto-save, high-contrast theme, board scale, in-app rebinding UI, per-event verbosity. It is **not** an inventory of the existing app — see `.planning/codebase/ARCHITECTURE.md` for that. The point of this document is to feed requirement-writing: for each new capability, what is the minimum a v1 must do to feel credible, what is worth doing extra, and what would be a trap.

---

## Feature Landscape

### Table Stakes (Users Expect These — v1 isn't credible without them)

These are the features without which a blind chess player will close OpenBoard within five minutes and not return. Anchor every requirement to these.

#### Chess clock — core

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Sudden-death format (`X+0`, e.g. `5+0`) | Universal default for every chess clock app since the 1990s. Setting "no time control" is also fine, but if clocks exist, sudden death must work. | S | Single integer per side; tick down at 1s resolution. |
| Fischer increment (`X+Y`, e.g. `3+2`, `15+10`) | Dominant online format on Lichess and chess.com. PGN spec encodes it as `300+5`. | S | Add Y seconds **after** move is completed (Fischer's patent). Differs from delay. |
| Classical multi-stage (`40/X:Y+Z`) — at minimum *parse* and *display* | FIDE classical is `40/5400+30:1800+30`. v1 can refuse to *play* with this but must not crash on PGN load with this header. | S to support display; M to actually run the stages. v1 should display only. | python-chess does not auto-parse `TimeControl`; we implement parser. Multi-stage *play* is M and can defer; multi-stage *display* is S. |
| Per-side clock readout, on demand, to screen reader | Lichess blind mode binds `c` to "check the clock; your time listed first." This is the minimum required clock interaction for a blind user. | S | Format: `Your time, 4 minutes 32 seconds. Opponent, 5 minutes 1 second.` Spell out at low time. |
| On-the-move clock callout (configurable) | After a move lands, briefly state remaining time on the moving side. Must be opt-out — for fast time controls it competes with move announcement. | M | Behind verbosity tier; default OFF for moves, ON for low-time threshold crossings. |
| Low-time threshold announcement (configurable, default 30s and 10s) | Blind players cannot see a flashing red clock. They need an explicit spoken warning. | S | Threshold crossings: announce once when crossed, not continuously. |
| Clocks-off mode (no clock at all) | Casual players, training, position study. Listed in PROJECT.md as a hard requirement. | S | Equivalent to "no time control" — `Game::set_time_control(None)`. Disables all clock UI and announcements. |
| Increment-after-move semantics | If clock format is `X+Y`, every move must add Y seconds before the *opposite* side's clock starts. Not after the move that *exhausts* time. | S | python-chess does not run clocks — this is our state machine. |

#### Move sound layer

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Move SFX (own move vs opponent) | Universal across Lichess, chess.com, ChessBase. Distinguishing own from opponent is essential when audio is the primary feedback channel. | S | Two short sound files; play after the move lands. |
| Capture SFX (distinct from move) | Lichess Standard pack ships `Move.ogg` and `Capture.ogg` as separate events. Captures are categorically different events and a blind player needs to know without parsing the announcement. | S | Triggered by `move.is_capture()` check (python-chess provides). |
| Check SFX | Lichess ships `Check.ogg`. Critical — missing a check is a forfeit-tier mistake. | S | Triggered after move applies if `board.is_check()`. |
| Castle SFX (distinct from move) | Castling is a two-piece event; a single move-thunk understates it. Lichess does not ship a dedicated castle sound, but accessibility-first apps benefit from it because the announcement comes after a brief delay. | S | Triggered by `board.is_castling(move)`. |
| Game-end SFX (win / loss / draw) | Universal. Different sounds per outcome help the player register the result without waiting for the speech queue to drain. | S | Three short clips. |
| Per-category mute toggle | Some users mute sounds they don't want without losing others — e.g. mute "own move" but keep "opponent move." | S | Six settings (move/capture/check/castle/end + master mute). |
| Master volume slider | Standard. | S | Persisted to settings. |
| Settings persistence | Lichess and chess.com both persist sound prefs. Re-toggling on every launch is a deal-breaker. | S | Save in `Settings.audio` block. |
| Coexistence with TTS — sounds must not collide with screen-reader speech | A SFX during an active TTS utterance forces the user to choose which to attend to. Sounds should be **short** (<200ms) and the move SFX must fire **before** the move announcement begins, not during. | M | Sequence: apply move → play SFX → enqueue announcement. No overlap. Audio ducking is OS-level and we should not assume it. |

#### PGN save / load semantics

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Write standard Seven Tag Roster (STR) | PGN archival standard mandates Event, Site, Date, Round, White, Black, Result, in that order. Files missing STR are rejected by some readers. | S | python-chess's `Game.headers` is ordered; setting these explicitly is one-liners. |
| Write `Result` correctly (`1-0` / `0-1` / `1/2-1/2` / `*`) | Universal. `*` means "in progress/unknown." | S | Map from `BoardState.result()`. |
| Write `TimeControl` header when clocks are on | Lichess-saved PGN includes this. Without it, clock metadata is lost. | S | Format per PGN spec: `300+5`, `40/5400+30:1800+30`, etc. |
| Write `[%clk h:mm:ss]` annotations on each move | Lichess writes `{ [%clk 0:04:32] }` after every move. Allows time-aware replay and game review. python-chess provides `node.set_clock(seconds)`. | S | Wraps the existing controller→PGN export path. |
| Load any standards-compliant PGN | python-chess `read_game()` handles 99% of real-world files. | S | Already partially in code per ARCHITECTURE.md. v1 hardens edge cases. |
| Multi-game PGN — load Nth game | Real-world PGN files (Lichess exports, ChessBase databases) routinely contain 100s of games separated by blank lines. v1 must at minimum let the user pick which game to load — even a "Game 1 of 47" prompt suffices. | M | python-chess `read_game()` returns one at a time; loop and present a list. |
| Load with malformed bytes — graceful error | A blind user pasting from a forum may copy zero-width spaces or wrong encoding. We must announce a useful error, not crash. | S | Catch parse exceptions, announce via `controller.announce`. |
| Save with explicit user-chosen filename | Every desktop save dialog. wxPython provides `wx.FileDialog`. | S | Must be screen-reader-friendly (wxPython native dialogs are). |

#### FEN save / load

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Export current position as FEN | One-line text the user can paste into any analysis tool. | S | `BoardState.fen()` already exists. Add to menu/clipboard. |
| Load standard FEN — set up arbitrary position | Setup-from-FEN entry. python-chess `Board(fen=…)` validates. | S | Reset clocks, replay state, announcements; emit `board_updated`. |
| Validate FEN — actionable error message | Malformed FEN is the single most common user-input failure for chess apps. Generic "invalid input" is hostile. | S | python-chess's `Board.status()` returns a flag set; map flags to spoken phrases ("invalid en-passant square", "missing castling rights for moved king"). |
| Strict en-passant handling | The FEN spec changed: old spec records ep square after every double-push, new spec records it only when capture is legal. python-chess defaults to "fully legal" but accepts both. v1 must accept both on load. | S | python-chess: `chess.Board(fen, chess960=False)` — default is permissive. |
| Castling rights vs king position consistency | Most-common bug: FEN claims `KQkq` but the king is on e2. python-chess `clean_castling_rights()` returns the corrected subset; we should *announce* the correction and load anyway, not reject. | S | Fall-back to cleaned rights with announcement. |

#### High-contrast theme

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Toggleable theme — at minimum one extra preset beyond default | The whole point. Just "dark mode" is not enough; it needs to specifically maximize piece-on-square contrast. | S | New `BoardTheme` enum with `Default`, `HighContrast`. |
| All four piece-square pairings ≥ WCAG AA (4.5:1 text-equivalent / 3:1 graphical) | WCAG 2.1 graphical-object minimum is 3:1. Chess has four piece-on-square combinations: white-on-light, white-on-dark, black-on-light, black-on-dark. All four must meet the bar simultaneously, which rules out many "looks high-contrast" palettes that fail one combination. | M | Manual measurement. Black-on-light and white-on-dark are easy; the cross combinations require tuning. |
| Toggleable persistence | Setting must survive restart. | S | `UISettings.theme` enum. |
| Last-move and selection highlights still distinguishable in high-contrast | A dark-mode palette where the last-move highlight blends with the dark square defeats the purpose. | M | Highlight uses border or pattern overlay, not just colour swap. |

#### Adjustable piece / board scale

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Resizable board panel — at least three discrete sizes (S/M/L) or continuous slider | Listed in PROJECT.md. Low-vision users need bigger pieces; some users on small laptops need smaller. | M | wxPython rendering already does this implicitly via window resize, but we need a deliberate piece-size setting that survives resize. |
| Persistence across restart | Setting must persist. | S | `UISettings.board_scale`. |

#### In-app key rebinding UI

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Settings dialog showing all current bindings | Without this, the *only* way to change keys is editing JSON — that's a developer affordance, not a user one. | M | `wx.ListCtrl` or simple table of (action, key). |
| Capture-a-keystroke flow that is screen-reader-friendly | "Press the new key for this action" must be spoken before the capture window opens, and the captured key must be spoken back. Users cannot see "press a key now…" prompts. | M | Modal dialog with focused capture control. `EVT_KEY_DOWN` records the event; on first key press, dialog announces the captured combo and asks confirm. |
| Conflict detection — refuse or warn on duplicate binding | If both "next move" and "rewind" are bound to F5, navigation breaks silently. v1 must at minimum warn. | M | On confirm, scan existing bindings; if duplicate, announce conflict and require resolution. |
| Reset-to-defaults | Universal escape hatch for users who lock themselves out. | S | Restore from `keyboard_config.json` shipped defaults. |
| Modifier-key handling (Ctrl/Shift/Alt + key) | Single-key bindings (Lichess-style) work for primary navigation, but secondary actions (save, load, undo) need modifiers — and on macOS, Cmd vs Ctrl semantics are platform-specific. | M | Capture full `wx.KeyEvent` modifier mask. Persist as platform-neutral string ("ctrl+s" / "cmd+s"). On load, pick the platform variant. |

#### Per-event announcement verbosity tiers

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Per-event-category opt-in/out | The current global brief/verbose toggle is too coarse. Users want, e.g., verbose move announcements but silent attacking-piece callouts. | M | Categories below. Each is a tri-state: OFF / TERSE / VERBOSE. |
| Category list (minimum) | Move (own), move (opponent), check, capture, castle, game-state changes (status), low-time, attacking pieces, hints, replay-step. Nine categories is the v1 floor — fewer feels under-built (NVDA itself has tiers per element type), more is fine. | M | Stored as `dict[Category, Verbosity]` in settings. |
| "Reset to default profile" — preset bundles | Three presets: "Minimal" (only moves and checks), "Standard" (default), "Verbose" (everything). Lets users get back to a known-good state. | S | Three named dicts. |
| Setting persistence | Trivial requirement, but worth restating. | S | `UISettings.verbosity_profile`. |

#### Auto-save / crash recovery

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Continuous auto-save of in-progress game | Industry standard since Office 2007 for any non-trivial state. A game lost to a crash is unforgivable, and listed as required in PROJECT.md. | M | Serialize PGN + clock state + game config to a known path on every move. Atomic write (write-then-rename). |
| Resume prompt on next launch | When a saved game exists, the launch path must offer "Resume your previous game?" *before* the user starts a new one. Silent restore is wrong — the user may have intended to start fresh. | M | Modal at startup, default focus on Resume button (or Yes), accessible via screen reader. |
| Clean-shutdown clears the auto-save | If the user properly resigned/finished the game, no resume prompt next time. Otherwise we'd ask forever. | S | Delete or mark the file on graceful exit. |
| Survive engine crash, not just app crash | The Stockfish process can crash independently; the rest of the app shouldn't lose state with it. | S | Auto-save is independent of engine; engine failure does not invalidate game state. |

---

### Differentiators (Competitive Advantage — what makes OpenBoard stand out for blind/VI users)

These are features that go beyond table stakes. Lichess blind mode is web-only and limited; existing accessible desktop chess (Winboard 4.5) is mature but Windows-only and unmaintained; chess.com is partially accessible but not screen-reader-first. There is real room to differentiate.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Clock ticking audio under low-time threshold | Sighted players see a red clock; blind players need an analogue. A soft tick at 30s remaining, faster tick under 10s, gives time pressure tactility no screen-reader app currently offers. | M | Depends on **clock infrastructure** + **sound layer**. Plays only on the moving side's clock. Off by default; opt-in setting. |
| Repeat-last-move command that *actually* repeats | Lichess blind mode famously *fails* to repeat the same announcement twice ("if the output is exactly the same as the previous output, you will not hear anything"). Fixing this is a small but pointed differentiator. | S | `controller.announce` re-sends with a forced re-utterance flag. |
| Full FEN/PGN round-trip with `%clk` annotations preserved | Most desktop chess UIs lose clock annotations on save/load round-trip. Preserving them lets a blind user review their own time usage. | M | Depends on **PGN save/load**. python-chess supports `set_clock`/`clock`. |
| Verbosity profile presets ("Minimal", "Standard", "Verbose") with one-key toggle | Lichess blind mode has *no* verbosity controls. NVDA-as-an-app comparators have global, not per-event, tiers. A keystroke that rotates among three preset profiles is a UX win. | S | Depends on **verbosity tiers**. Bind to e.g. `Ctrl+V`. |
| Spoken FEN-error messages mapped from `python-chess.Board.status()` | "Bad FEN" is hostile; "FEN looks good but castling rights say white can castle kingside, yet the white king has moved" is helpful. The status flags exist; we just have to translate them. | S | Depends on **FEN load**. Static mapping from `STATUS_*` flags to phrases. |
| Multi-game PGN navigator with screen-reader-readable game list | Most apps that handle multi-game PGN dump them all into a sighted list. A spoken "Game 3 of 47, White: Carlsen, Black: Nakamura, Result: 1-0" lets a blind user pick. v2 deferral risk: full library browser is v2; one-shot game-picker dialog is v1. | M | Depends on **PGN load**. Modal `wx.SingleChoiceDialog` with formatted strings. |
| Auto-save with clock state, not just board state | Most game auto-saves drop transient state. Restoring with the correct remaining time per side preserves the contest. | M | Depends on **clocks** + **auto-save**. Serialize clock seconds in the auto-save blob. |
| Increment vs Bronstein vs simple-delay support | Most online platforms only do Fischer increment. FIDE and OTB tournaments use Bronstein and US delay. Supporting all three is a small additional implementation burden if we already have Fischer, and signals "serious chess app." | M | Single state machine with three modes; UI lists all three. **Note:** PROJECT.md only requires "increments after move," so this is a stretch — keep behind a feature flag if v1 risks slipping. |
| Clock callout cadence (e.g. announce every minute, then every 10s, then every second under 10s) | Walks the line between info and noise. Used by some accessible board-games but not in chess apps. | M | State machine driven by remaining time; cadence configurable. |

---

### Anti-Features (Commonly Requested, Often Problematic)

Things to deliberately *not* build in v1, with reasoning. Documenting these prevents requirement creep and gives us something to point at when scope grows.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Tick-on-every-move sound (not just low time) | "Audio metronome." | Blends with move SFX, increases TTS collision rate, is noise that experienced blind players will mute within minutes. Lichess offers it under "Speech mode" only. | Tick only under low-time threshold (differentiator above). |
| Hourglass / sandglass time control | Mentioned in PROJECT.md milestone-context as a format to research. | Real-world adoption is essentially zero — Wikipedia notes "use of this time control is uncommon." Lichess's own users opened a feature request that has gone nowhere. Spec'ing and testing the always-summing semantic adds effort with near-zero user value. | Document as out-of-scope; revisit if a user requests it. |
| Continuous time-remaining narration | "Just tell me how much time I have, always." | Floods the speech queue and crowds out moves. Verbose users would set every category to VERBOSE and then complain about noise. | On-demand readout (`c` key, Lichess-style) + threshold callouts. |
| Voice-controlled key remapping ("say the action name") | "More accessible than reading a list." | OpenBoard's product line is keyboard-in / TTS-out (PROJECT.md Out of Scope). Voice input means a different audio model and breaks the design. | Keyboard-only capture flow. |
| Full chess.com-style sound packs (NES, Piano, Robot, Pentatonic, Futuristic, Speech) | Lichess and chess.com offer them; users may ask. | Asset licensing, pack-management UI, theme persistence — all costs that don't move the accessibility needle. The Lichess Standard pack is enough. | Ship one well-tuned set. Document as v2 if demand emerges. |
| Custom user-uploaded sound packs | "I want to bring my own sounds." | Filesystem path management, sandboxing, validation, error reporting, screen-reader prompts for file picks. All work, no benefit for the primary user (a blind chess player who wants to play, not theme). | Out of scope for v1. |
| Auto-save to multiple slots / save-game library | "I want to keep multiple games." | This is the v2 saved-game library browser per PROJECT.md. Conflating crash-recovery auto-save with multi-slot save creates UX confusion (which file is "live"?). | One auto-save slot, plus user-named PGN exports via Save As. |
| Silent restore (no resume prompt) | "Just put me back where I was." | If the user crashed mid-blunder, they may want a fresh start. Silent restore makes that harder. Crash-recovery dialogs are universal in desktop apps for exactly this reason. | Resume prompt on launch when an auto-save exists; default focus on "Resume." |
| Per-user verbosity profiles (multiple users on one install) | "My partner and I both use it." | Account/profile UI, screen-reader-friendly user-switching, settings-file scoping. Disproportionate cost. | Single user; settings file is per-OS-user already. |
| Chess960 / variant FEN support in v1 | Shredder-FEN, X-FEN are real edge cases. | python-chess supports them but FEN setup UI must be tested for variants. v1 is standard chess only per PROJECT.md scope. | Out of scope; document as v2+. Validate that *loading* a Chess960 FEN gives a clean error rather than silent misbehaviour. |
| In-app announcement-text editor ("change the words used for capture") | Power users sometimes ask for this. | Localization complexity, accidental ambiguity ("piece moved" vs "moved piece"), and zero accessibility benefit. | Hard-code well-tested phrases; revisit if i18n becomes a milestone. |

---

## Feature Dependencies

```
Auto-save / crash recovery
    ├── requires ──> PGN save (serialization format)
    ├── requires ──> Clock infrastructure (clock state in blob)
    └── requires ──> Game status detection (when to clear)

Clock ticking under low time
    ├── requires ──> Clock infrastructure (low-time threshold)
    └── requires ──> Sound layer (tick SFX file)

Move sounds (capture/check/castle distinction)
    └── requires ──> python-chess move classification (already present)

Per-event verbosity
    └── enhances ──> All announcement-emitting features
                    (move, check, capture, low-time, attackers, hints)

PGN load multi-game
    ├── requires ──> PGN parser (python-chess)
    └── enhances ──> Replay UI (existing)

PGN save with %clk annotations
    ├── requires ──> Clock infrastructure (clock-state-per-move)
    └── requires ──> PGN write path

FEN load / validate
    └── enhances ──> Position-setup workflows (board reset, replay)

In-app key rebinding UI
    ├── requires ──> Existing keyboard_config.json infrastructure
    └── enhances ──> Verbosity / sound toggle binding (rebind any
                    of these to user preference)

High-contrast theme
    ├── conflicts with (mildly) ──> Custom highlight-colour preferences
    │                                (decision: theme owns highlights)
    └── enhances ──> Adjustable board scale (large + high-contrast
                    is the common low-vision config)

Auto-save resume prompt
    └── conflicts with ──> "Open last file on startup" pattern
                          (decision: resume is a one-shot; once
                          accepted/declined, normal flow resumes)
```

### Dependency Notes

- **Auto-save requires PGN serialization first.** PGN is our serialization format for crash-recovery; we cannot have auto-save before PGN-save lands. Ordering implication: PGN save lands before auto-save in the implementation phase.
- **Clock ticking SFX requires both clock infra and sound layer.** Sequencing implication: low-time SFX is a *integration* item that lights up only when both substrate features are merged. Avoid spec'ing it as a separate phase milestone — let it fall out of the integration of clocks + sounds.
- **PGN save with `%clk` annotations requires clock infrastructure.** The per-move clock value has to come from somewhere. Implication: PGN write that omits `%clk` is a v1-day-1 feature; PGN write *with* `%clk` lands after clock infra.
- **Per-event verbosity enhances every announcement feature.** Implication: each new announcement-emitting feature added in v1 must be wired to the verbosity-tier dispatcher, not announce unconditionally. Cheaper to do this once at the controller level than to refactor later.
- **Resume prompt and "open last file" are competing patterns.** Decision: resume-prompt wins for in-progress games. Once accepted or declined, behaviour reverts to normal startup (no PGN auto-loaded).
- **High-contrast theme owns highlight colours.** Otherwise the theme is undermined by a clashing user-set highlight. Decision: theme is a complete bundle (squares + pieces + highlights + last-move + selection). User can pick *which* theme; cannot remix.

---

## MVP Definition

### Launch With (v1)

Per PROJECT.md "Active" requirements. Restated here in the order suggested by the dependency graph.

- [ ] **Tech-debt cleanup** — fixes from `.planning/codebase/CONCERNS.md`. Required first because announcement and signal correctness underpins everything else.
- [ ] **PGN save / load (round-trip with STR headers and Result)** — substrate for auto-save and v2 library.
- [ ] **FEN save / load with actionable error messages** — substrate for v3 puzzle import; also unblocks position-setup workflows.
- [ ] **Clock infrastructure (sudden death + Fischer increment + clocks-off; multi-stage parse-only)** — required for sound-layer ticking and PGN `%clk`.
- [ ] **Sound layer (move/capture/check/castle/end + per-category mute + master volume)** — table stakes for blind audio feedback.
- [ ] **Auto-save / crash recovery with resume prompt** — depends on PGN + clocks; closes the "no apologies" gap from PROJECT.md.
- [ ] **High-contrast theme (one preset beyond default, all four piece-square combinations ≥ WCAG AA)** — opt-in, persistent.
- [ ] **Adjustable board scale** — at least three discrete sizes (S/M/L), persistent.
- [ ] **In-app key rebinding UI (capture flow + conflict detection + reset-to-defaults)** — replaces edit-JSON-and-restart workflow.
- [ ] **Per-event verbosity tiers (≥9 categories, OFF/TERSE/VERBOSE, three preset profiles)** — replaces global brief/verbose toggle.

### Add After Validation (v1.x — small follow-ups, same milestone or hotfix)

- [ ] Bronstein and simple-delay clock formats — only Fischer is required; add when first user requests OTB-style timing.
- [ ] Clock-tick audio under low time — small differentiator; ship in v1 if both substrates land cleanly, defer if either is risky.
- [ ] Multi-game PGN game-picker dialog — required if v1 ships with users who load Lichess exports; can defer if v1 demo is single-game files.
- [ ] Verbosity-profile rotate keystroke — UX nicety on top of verbosity tiers.

### Future Consideration (v2+)

Deferred to later milestones per PROJECT.md "Out of Scope":

- [ ] Saved-game library browser — explicit v2 in PROJECT.md.
- [ ] Full Stockfish analysis (live PV, multi-PV, post-game review) — v2.
- [ ] Chess puzzles, opening-book browser — v3.
- [ ] Lichess online play — v4.
- [ ] Variant chess (Chess960, atomic, etc.) — out of scope; not on roadmap.
- [ ] Custom sound packs / theme uploads — anti-feature in v1; revisit only if user demand emerges.
- [ ] Voice command input — explicitly out of scope by design.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Tech-debt cleanup (CONCERNS.md) | HIGH | M | P1 |
| PGN save/load with STR headers | HIGH | S | P1 |
| FEN save/load with error mapping | HIGH | S | P1 |
| Clock infra (sudden death + Fischer + off) | HIGH | M | P1 |
| Move/capture/check/castle SFX | HIGH | S | P1 |
| Per-category sound mute + volume + persist | HIGH | S | P1 |
| Auto-save + resume prompt | HIGH | M | P1 |
| High-contrast theme (one preset, AA-compliant) | HIGH | M | P1 |
| Adjustable board scale | MEDIUM | M | P1 |
| In-app key rebinding UI | HIGH | M | P1 |
| Per-event verbosity tiers (≥9 categories) | HIGH | M | P1 |
| Multi-game PGN game-picker | MEDIUM | M | P2 |
| `%clk` annotations on PGN save | MEDIUM | S | P2 |
| Clock-tick under low-time | MEDIUM | M | P2 |
| Bronstein / simple-delay formats | LOW | M | P3 |
| Multi-stage TimeControl playable (not just parse) | LOW | M | P3 |
| Verbosity-profile rotate keystroke | LOW | S | P3 |
| Chess960 / variant FEN | LOW | M | P3 (out of scope) |

**Priority key:**
- P1: Required for v1 demo; ships in main v1 release.
- P2: Strong nice-to-have for v1; ship if dependencies land cleanly, otherwise punt to v1.x.
- P3: Out of v1 scope; documented for traceability.

---

## Competitor / Comparator Feature Analysis

| Feature | Lichess Blind Mode | Winboard 4.5 (acc.) | Chess.com (partial a11y) | OpenBoard v1 plan |
|---------|--------------------|---------------------|--------------------------|-------------------|
| Screen-reader move announcement | Yes, last-move-only via `l` key | Yes, configurable | Partial via web a11y | **Per-event verbosity tiers, repeat-last with re-utterance fix** |
| Clock readout on demand | `c` key | Yes | No standard binding | **Same `c`-style binding + threshold callouts** |
| Clock-tick audio | No | No | No (visual only) | **Differentiator: tick under low time** |
| Move/capture/check distinct SFX | Yes (Move/Capture/Check/CheckCapture) | Limited | Yes | **Move/capture/check/castle/end** |
| Custom sound packs | Yes (8 packs) | No | Yes (multiple) | **Single tuned pack; anti-feature** |
| PGN save with `%clk` | Yes | No | Partial | **Yes — round-trip preserved** |
| Multi-game PGN load | Yes | Yes (limited UI) | Yes (database UI) | **Game-picker dialog (P2)** |
| FEN load with validation feedback | Limited | Limited | Limited | **Differentiator: actionable spoken errors** |
| In-app key rebinding | No (web) | Limited | No | **Yes — full capture+conflict UI** |
| Per-event verbosity | No (global only) | Limited | No | **Differentiator: ≥9 categories, three profiles** |
| Auto-save / crash recovery | N/A (server-side) | Yes | N/A (server-side) | **Yes — resume prompt** |
| High-contrast desktop theme | Web themes only | Yes (limited) | Yes | **Yes — WCAG AA on all 4 combos** |
| Hourglass time control | Requested, not shipped | No | No | **Anti-feature** |

Sources for competitor analysis: Lichess blind mode tutorial and changelog ([blind-mode-tutorial](https://lichess.org/page/blind-mode-tutorial), [blind-mode-guide](https://lichess.org/page/blind-mode-guide)); Winboard 4.5 description ([SourceForge](https://sourceforge.net/projects/winboard45forja/)); chess.com accessibility threads ([visually impaired use](https://www.chess.com/forum/view/help-support/visually-impaired-use-of-the-site)).

---

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| PGN spec details (STR, TimeControl, %clk) | HIGH | Confirmed in saremba.de spec (referenced by PGN Wikipedia) and python-chess docs. |
| FEN edge cases (en-passant, castling rights) | HIGH | python-chess docs and FEN Wikipedia confirm both old/new spec semantics and `clean_castling_rights()`. |
| Lichess blind-mode commands | HIGH | Direct read of Lichess blind-mode-guide page. |
| Lichess sound categories | MEDIUM | Forum threads confirm Move/Capture/Check/CheckCapture; not formally documented. |
| WCAG contrast thresholds for graphical objects | HIGH | WCAG 2.1 SC 1.4.11 explicitly: 3:1 for graphical objects, 4.5:1 for normal text. |
| Verbosity-tier conventions | MEDIUM | NVDA punctuation tiers (None/Some/Most/All) are well-documented; per-event verbosity in chess apps is not, so OpenBoard's design is inferred from screen-reader-application convention rather than direct precedent. |
| Auto-save UX expectations | MEDIUM | Office and game industry conventions are well-established; precise UX (silent vs prompt) varies. We chose prompt for screen-reader transparency. |
| Hourglass adoption | HIGH | Multiple sources confirm "uncommon" — Wikipedia, Lichess feature-request threads, cutechess issue. |

---

## Sources

**Primary (HIGH confidence):**
- PGN specification — [saremba.de PGN complete](http://www.saremba.de/chessgml/standards/pgn/pgn-complete.htm)
- PGN format / Seven Tag Roster / TimeControl tag — [Wikipedia: PGN](https://en.wikipedia.org/wiki/Portable_Game_Notation)
- python-chess PGN API (`set_clock`, `read_game`, `Board.status`) — [python-chess PGN docs](https://python-chess.readthedocs.io/en/latest/pgn.html), [core docs](https://python-chess.readthedocs.io/en/stable/core.html)
- FEN spec edge cases — [Wikipedia: FEN](https://en.wikipedia.org/wiki/Forsyth%E2%80%93Edwards_Notation), [Chessprogramming wiki](https://www.chessprogramming.org/Forsyth-Edwards_Notation)
- Lichess blind mode — [tutorial](https://lichess.org/page/blind-mode-tutorial), [guide](https://lichess.org/page/blind-mode-guide), [changelog](https://lichess.org/page/blind-mode-changelog)
- Time-control formats — [Wikipedia: Time control](https://en.wikipedia.org/wiki/Time_control), [Chess.com: Time controls](https://www.chess.com/terms/chess-time-controls)
- WCAG contrast — [WCAG 2025 AA guide](https://www.allaccessible.org/blog/color-contrast-accessibility-wcag-guide-2025)
- NVDA verbosity / punctuation tiers — [NVDA verbosity discussion](https://nvda.groups.io/g/nvda/topic/86632488), [NVDA #46](https://github.com/nvaccess/nvda/issues/46)

**Secondary (MEDIUM confidence):**
- Lichess sound forums — [sound effects](https://lichess.org/forum/lichess-feedback/sound-effects-2), [check sound consistency](https://github.com/lichess-org/lila/issues/8365)
- Hourglass time control adoption — [Lichess hourglass FR](https://lichess.org/forum/lichess-feedback/hourglass-time-control-suggestion), [cutechess #273](https://github.com/cutechess/cutechess/issues/273)
- Audio ducking / TTS-vs-SFX collisions — [Accessible Android: Audio ducking](https://accessibleandroid.com/understanding-audio-ducking-on-android-talkback-jieshuo-and-operating-system-challenges/)
- Accessible chess background — [Lucas Radaelli blindfold-chess](https://www.lucasradaelli.com/en/projects/blindfold-chess/), [Winboard 4.5 accessible](https://blindhelp.net/software/winboard-452), [English Chess Federation: accessible chess](https://www.englishchess.org.uk/accessible-chess/)

**Tertiary (context only):**
- wxPython key-event capture — [wx.KeyEvent docs](https://docs.wxpython.org/wx.KeyEvent.html), [catching key events globally](https://wiki.wxwidgets.org/Catching_key_events_globally)
- Auto-save UX conventions — [Wikipedia: Autosave](https://en.wikipedia.org/wiki/Autosave)

---

*Feature research for: Accessible desktop chess GUI v1*
*Researched: 2026-04-27*

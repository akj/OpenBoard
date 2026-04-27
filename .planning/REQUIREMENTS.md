# Requirements: OpenBoard

**Defined:** 2026-04-27
**Core Value:** Blind and visually-impaired players can play full chess games independently — every state change is reliably announced or felt, with no missing or wrong information.

## v1 Requirements

Requirements for the v1 "Foundation & Polish" milestone. Each maps to roadmap phases.

### Tech Debt (TD)

<!-- Fix every documented item in .planning/codebase/CONCERNS.md. Several are
     structural prerequisites for later v1 capabilities (see SUMMARY.md). -->

- [ ] **TD-01**: `move_undone` signal is reconnected after `Game.new_game()` so undo announcements work in second and later games (CONCERNS.md Bug #1)
- [ ] **TD-02**: `Game.move_made` carries `old_board: chess.Board` and `move_kind: MoveKind` payload, removing the fragile `_pending_old_board` shared state
- [ ] **TD-03**: `_navigate_to_position` routes through `BoardState.make_move`/`undo_move` instead of bypassing the model layer (CONCERNS.md Bug #2)
- [ ] **TD-04**: `announce_attacking_pieces` uses `chess.Board.attackers()` so pinned attackers are reported correctly and the O(64 × legal_moves) iteration is eliminated (CONCERNS.md Bug #3 + Performance #2)
- [ ] **TD-05**: `on_load_pgn` is bound to a specific menu ID (not `wx.ID_ANY`) so it does not fire on unrelated menu events (CONCERNS.md Bug #4)
- [ ] **TD-06**: `_simple` API surface (`start_simple`, `stop_simple`, `get_best_move_simple*`, `_start_engine_simple`) is removed from `EngineAdapter` (CONCERNS.md Tech Debt)
- [ ] **TD-07**: Duplicate difficulty-resolution logic in `Game.request_computer_move` and `Game.request_computer_move_async` is extracted into a shared `_resolve_move_context()` helper (CONCERNS.md Tech Debt)
- [ ] **TD-08**: Synchronous `Game.request_computer_move()` is either removed or marked `_test_only` / `@deprecated`; tests use the async path (CONCERNS.md Tech Debt)
- [ ] **TD-09**: `&Book Hint\tB` menu accelerator is removed; book hint dispatch goes through the keyboard config system only (CONCERNS.md Tech Debt)
- [ ] **TD-10**: `Game.player_color` backward-compatibility attribute is removed (CONCERNS.md Tech Debt)
- [ ] **TD-11**: Unused exception types in `openboard/exceptions.py` are wired up where they logically belong, or pruned (CONCERNS.md Tech Debt)
- [ ] **TD-12**: All persistent files resolve via `platformdirs` (settings, keyboard_config, autosave, engines_dir) — no `Path.cwd()`-relative resolution; one-shot migration moves any existing user file to the new location (CONCERNS.md Security #4)
- [ ] **TD-13**: All other concrete bugs and tech-debt items in `.planning/codebase/CONCERNS.md` not listed above are resolved or explicitly deferred with rationale captured back into CONCERNS.md
- [ ] **TD-14**: A regression test exists for every fix above (TD-01 through TD-13) so the bug class cannot return silently

### Persistence (PER)

- [ ] **PER-01**: User can save the current game as a `.pgn` file with full Seven Tag Roster, `Result`, and `TimeControl` headers
- [ ] **PER-02**: User can load any standards-compliant `.pgn` file; multi-game files surface a picker (or announce "Game N of M loaded")
- [ ] **PER-03**: PGN parser errors from `python-chess` (`game.errors`) are surfaced to the user via spoken announcement (not silently swallowed)
- [ ] **PER-04**: User can save the current position as a FEN string (clipboard or file)
- [ ] **PER-05**: User can paste or type a FEN string to set up a position; `Board.is_valid()` and `Board.status()` flags drive actionable spoken errors (e.g. "castling rights say white can castle kingside but the white king has moved")
- [ ] **PER-06**: User's in-progress game auto-saves on every move and on graceful exit, durably enough to survive a crash (atomic three-step write — tmp + flush + fsync/F_FULLFSYNC + os.replace — with one-generation `.bak` fallback)
- [ ] **PER-07**: On launch, if an autosave exists, user is prompted to resume; default focus is on Resume; declining starts a new game and clears the autosave
- [ ] **PER-08**: Autosave is cleared on graceful end (game-over reached, user starts New Game, user explicitly discards)
- [ ] **PER-09**: Autosave file format is JSON via pydantic with a `schema_version` field for future migrations

### Clocks (CLK)

- [ ] **CLK-01**: User can choose a time control before starting a game: sudden-death (e.g. 5+0), Fischer increment (e.g. 5+3), or clocks-off
- [ ] **CLK-02**: Each side's remaining time decrements during their turn and pauses on the opponent's turn (Fischer increment applied at end of move per FIDE rules)
- [ ] **CLK-03**: Clock truth is `time.monotonic()` timestamps captured at move-commit; `wx.Timer` only triggers UI redraw and threshold checks (no per-tick subtraction → no drift)
- [ ] **CLK-04**: Clock pauses for **every** modal dialog mid-game (a `ClockAwareDialog` base class enforces this for all v1 dialogs)
- [ ] **CLK-05**: Low-time threshold (configurable, default `max(10s, 5% of base)`) triggers a one-shot announcement of remaining time per side
- [ ] **CLK-06**: User can read the current remaining time on demand via a single keystroke (default `c`, rebindable)
- [ ] **CLK-07**: Flag fall (one side's time reaches zero) ends the game with a spoken result; no further moves accepted
- [ ] **CLK-08**: Game-over announcement and result reflect time-based loss (`0-1 on time` / `1-0 on time`)
- [ ] **CLK-09**: Per-move `[%clk H:MM:SS]` annotations are written to PGN on save and parsed on load; loaded clock state restores remaining time per side
- [ ] **CLK-10**: A `ClockPanel` view renders both clocks; size and contrast scale with the user's theme + board scale settings

### Sound (SND)

- [ ] **SND-01**: Distinct sound effect plays for: own move, opponent move, capture, check, castle, game-end (≥6 categories)
- [ ] **SND-02**: Each category has an independent on/off toggle in settings, persisted across sessions
- [ ] **SND-03**: Master volume slider and per-category volume are configurable; sliders are screen-reader-labeled
- [ ] **SND-04**: Sound effects fire **after** the screen-reader announcement (default 200 ms `wx.CallLater` delay; user-configurable 0–500 ms range) so SFX never masks the announcement's first syllable (NVDA has no audio ducking)
- [ ] **SND-05**: Clock ticking SFX is available under the low-time threshold; off by default; uses narrow-band tones to avoid masking speech formants
- [ ] **SND-06**: Sound subsystem fails gracefully when the audio device is unavailable (headless CI, audio driver crash, hardened-runtime refusal); the app continues to function fully
- [ ] **SND-07**: Sound assets ship as 16-bit 44.1 kHz mono OGG Vorbis (or short WAV); pre-loaded into memory at startup so mid-game playback has zero cold-start latency
- [ ] **SND-08**: All sound features work identically on Windows, macOS, and Linux PyInstaller builds (verified by manual smoke test before each release)

### Visual Accessibility (VIS)

- [ ] **VIS-01**: A high-contrast board/piece theme is available alongside the default theme, toggleable from the View menu and rebindable via the keyboard
- [ ] **VIS-02**: Every `(square color × highlight combination × scale factor)` tuple in the high-contrast theme passes WCAG AA (3:1 graphical-objects threshold), verified by an automated unit-test matrix
- [ ] **VIS-03**: Highlight composition uses **state precedence** (focus > check > selected > last-move target > last-move origin > legal-move dot) — overlays replace, never alpha-blend — so composited squares hold contrast
- [ ] **VIS-04**: Check state is conveyed by both color and a non-color cue (border style or pattern) per WCAG 1.4.1
- [ ] **VIS-05**: User can choose from at least three discrete board sizes (small / medium / large); piece glyphs and borders scale proportionally
- [ ] **VIS-06**: Scale and theme settings persist across sessions; live preview applies on confirm (slider debounce on release, not per-pixel)

### Keyboard & Announcements (KEY)

- [ ] **KEY-01**: User can open an in-app key-rebinding dialog from the Settings menu
- [ ] **KEY-02**: Rebinding captures by `wx.KeyCode` + modifier flags (not Unicode characters) so it works on non-US keyboard layouts (German QWERTZ, French AZERTY verified)
- [ ] **KEY-03**: A reserved-shortcut blocklist prevents binding over screen-reader and OS chords (NVDA `Insert+*`, JAWS `Insert+*`, Orca `CapsLock+*`, `Cmd+Q`, `Alt+F4`); attempted bindings are rejected with spoken explanation
- [ ] **KEY-04**: Conflicts with existing bindings are detected and announced; user must resolve before saving
- [ ] **KEY-05**: Reset-to-defaults action is reachable by keyboard alone and announces confirmation
- [ ] **KEY-06**: Saving rebuilds the dispatch table on the running app (reload-on-save) — no restart required
- [ ] **KEY-07**: At least nine announcement categories are independently configurable (move-own, move-opponent, navigation-square, navigation-piece, hint, low-time, status, book, error); each can be set to OFF or VERBOSE
- [ ] **KEY-08**: Three preset verbosity profiles ("Minimal" / "Standard" / "Verbose") apply category settings in one action; one-key rotate keystroke cycles between profiles
- [ ] **KEY-09**: The verbosity dialog uses one `wx.Choice` per row plus explicit `wx.StaticText` labels — never `wx.Grid` or `wx.ListCtrl` (verified accessible with NVDA, VoiceOver, and Orca)
- [ ] **KEY-10**: A new `_announce(category, text)` helper on `ChessController` is the single point through which all announcements flow; verbosity filtering happens here, not at the view layer
- [ ] **KEY-11**: A "repeat last announcement" command forces re-utterance even of identical text (Lichess-blind-mode notable failure mode that v1 explicitly addresses)

## v2 Requirements

Deferred to the v2 "Engine & Analysis" milestone. Tracked but not in the current roadmap.

### Engine Analysis (ANL)

- **ANL-01**: Live engine evaluation (cp/mate score) displayed during gameplay
- **ANL-02**: Top-N engine principal-variation lines available on demand
- **ANL-03**: Multi-PV hint mode (hint feature exposes multiple candidate moves with scores, not just best move)
- **ANL-04**: Post-game review identifies blunders / mistakes / inaccuracies via eval drops (Lichess-style)
- **ANL-05**: UCI option panel exposes skill level, contempt, MultiPV, threads, and hash size; persists per-difficulty
- **ANL-06**: Configurable engine pondering / analysis depth and time per move

### Library Browsing (LIB)

- **LIB-01**: Browse all saved games in a list (sorted by date, opponent, result, opening); open into the board for review
- **LIB-02**: Browse opening-book moves at the current position with frequencies / weights
- **LIB-03**: Search saved games by player name, opening ECO, or result

## v3 Requirements

Deferred to the v3 "Puzzles" milestone.

### Puzzles (PUZ)

- **PUZ-01**: Bundled Lichess puzzle CSV dataset enables offline puzzle practice
- **PUZ-02**: Puzzle session UX with rating-tracking, theme filters (mate-in-N, fork, pin, etc.), and accessibility-first solution feedback
- **PUZ-03**: Live puzzles via Lichess API tied to user account, with rating tracked online
- **PUZ-04**: User can import custom `.pgn` / `.epd` puzzle files and run them as a puzzle session

## v4 Requirements

Deferred to the v4 "Online Play" milestone.

### Online Play (NET)

- **NET-01**: Lichess OAuth flow links user account from within OpenBoard
- **NET-02**: User can seek and accept challenges through the Lichess API
- **NET-03**: User can play live timed games with full clock support, resign, and offer/accept draw
- **NET-04**: Lichess game archive sync — completed games download and append to local PGN library
- **NET-05**: Online-play accessibility — every network event (opponent connected, move arrived, clock state, disconnection) is announced reliably; flaky-network behavior is graceful, not silent

## Out of Scope

Explicitly excluded. Documented to prevent scope creep. (See `.planning/PROJECT.md` § Out of Scope for project-level boundaries.)

| Feature | Reason |
|---------|--------|
| Mobile or web ports | Desktop wxPython only — no React Native, Electron, PWA |
| Peer-to-peer / custom-server multiplayer | Online play (v4) is via Lichess API only |
| Voice command input | Keyboard-in / TTS-out model is preserved by design |
| Proprietary engine integration (Houdini, Komodo) | UCI standard only |
| Adjustable UI font size for menus and dialogs | Rely on OS-level scaling; revisit if a user requests |
| Focus-indicator audit beyond what already exists | Deferred indefinitely |
| Bronstein / simple-delay clock formats | Only Fischer required for v1; revisit in v1.x |
| Multi-stage TimeControl playable (e.g. 40/90+30/60) | v1 parses + displays only; full play deferred |
| Custom sound packs / theme uploads | Anti-feature; ship one well-tuned set |
| Hourglass time control | Anti-feature; near-zero adoption (Wikipedia + Lichess + cutechess all confirm) |
| Chess960 / variant FEN play | Out of scope; `Board(chess960=True)` only as fallback during FEN load |
| Per-user verbosity profiles | One profile per install; revisit if multi-user demand emerges |
| In-app announcement-text editor | Anti-feature; verbosity is OFF/TERSE/VERBOSE per category, not free-form |
| Continuous time-remaining narration | Anti-feature; on-demand readout + low-time alert only |
| OS-native high-contrast palette query (`GetSysColor`, `NSAppearance`) | App-defined static palettes for v1; revisit if cross-platform parity slips |
| MP3 sound assets | Use OGG Vorbis or short WAV |
| `wx.PropertyGrid` / `wx.Grid` / `wx.ListCtrl` for settings UI | Inaccessible on non-Windows screen readers |
| `simpleaudio`, `playsound`, `wx.adv.Sound`, `wx.MediaCtrl`, `miniaudio` | Each rejected with rationale in `.planning/research/STACK.md` |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TD-01 | (TBD) | Pending |
| TD-02 | (TBD) | Pending |
| TD-03 | (TBD) | Pending |
| TD-04 | (TBD) | Pending |
| TD-05 | (TBD) | Pending |
| TD-06 | (TBD) | Pending |
| TD-07 | (TBD) | Pending |
| TD-08 | (TBD) | Pending |
| TD-09 | (TBD) | Pending |
| TD-10 | (TBD) | Pending |
| TD-11 | (TBD) | Pending |
| TD-12 | (TBD) | Pending |
| TD-13 | (TBD) | Pending |
| TD-14 | (TBD) | Pending |
| PER-01 | (TBD) | Pending |
| PER-02 | (TBD) | Pending |
| PER-03 | (TBD) | Pending |
| PER-04 | (TBD) | Pending |
| PER-05 | (TBD) | Pending |
| PER-06 | (TBD) | Pending |
| PER-07 | (TBD) | Pending |
| PER-08 | (TBD) | Pending |
| PER-09 | (TBD) | Pending |
| CLK-01 | (TBD) | Pending |
| CLK-02 | (TBD) | Pending |
| CLK-03 | (TBD) | Pending |
| CLK-04 | (TBD) | Pending |
| CLK-05 | (TBD) | Pending |
| CLK-06 | (TBD) | Pending |
| CLK-07 | (TBD) | Pending |
| CLK-08 | (TBD) | Pending |
| CLK-09 | (TBD) | Pending |
| CLK-10 | (TBD) | Pending |
| SND-01 | (TBD) | Pending |
| SND-02 | (TBD) | Pending |
| SND-03 | (TBD) | Pending |
| SND-04 | (TBD) | Pending |
| SND-05 | (TBD) | Pending |
| SND-06 | (TBD) | Pending |
| SND-07 | (TBD) | Pending |
| SND-08 | (TBD) | Pending |
| VIS-01 | (TBD) | Pending |
| VIS-02 | (TBD) | Pending |
| VIS-03 | (TBD) | Pending |
| VIS-04 | (TBD) | Pending |
| VIS-05 | (TBD) | Pending |
| VIS-06 | (TBD) | Pending |
| KEY-01 | (TBD) | Pending |
| KEY-02 | (TBD) | Pending |
| KEY-03 | (TBD) | Pending |
| KEY-04 | (TBD) | Pending |
| KEY-05 | (TBD) | Pending |
| KEY-06 | (TBD) | Pending |
| KEY-07 | (TBD) | Pending |
| KEY-08 | (TBD) | Pending |
| KEY-09 | (TBD) | Pending |
| KEY-10 | (TBD) | Pending |
| KEY-11 | (TBD) | Pending |

**Coverage:**
- v1 requirements: 58 total
- Mapped to phases: 0 (will be filled by roadmap creation)
- Unmapped: 58 (expected — pre-roadmap)

---
*Requirements defined: 2026-04-27*
*Last updated: 2026-04-27 after initial definition*

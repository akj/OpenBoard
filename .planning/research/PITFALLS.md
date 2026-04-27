# Pitfalls Research

**Domain:** Accessible desktop chess GUI v1 (wxPython + python-chess + accessible_output3 + blinker)
**Researched:** 2026-04-27
**Confidence:** HIGH for stack-specific pitfalls, MEDIUM for cross-platform sound and screen-reader interaction (verified with NVDA docs + wxPython docs + python-chess Context7, but real device testing is the only HIGH bar for a11y)

This document catalogs domain-specific pitfalls for the v1 "Foundation & Polish" milestone. It builds on `.planning/codebase/CONCERNS.md` rather than duplicating it: the eight bugs and six tech-debt items there are inputs to v1, and several pitfalls below explain how to avoid re-creating those classes of bug as new code lands.

---

## Critical Pitfalls

### Pitfall 1: Move SFX masking the screen reader announcement

**What goes wrong:**
A move plays its SFX (capture clang, check ping) at the same instant `accessible_output3` calls into NVDA / JAWS / VoiceOver / Speech Dispatcher to announce the move. The SFX wins acoustic priority for ~150-400 ms and the user misses the first syllable of the announcement ("…f3 takes e5 with check"). For a blind player this is the difference between knowing it was a check and not knowing.

**Why it happens:**
NVDA does not support audio ducking out of the box (confirmed in NVDA 2025.x user guide and tracker issue #17349). `accessible_output3` is a thin wrapper — it queues to the active screen reader's TTS engine but exposes no signal that the engine has finished or even started speaking. Naive implementations call `play_sfx()` and `speak()` back-to-back from the same wx event handler.

**How to avoid:**
- **Order matters:** announce first, then queue the SFX with a deliberate delay (≈150-300 ms) using `wx.CallLater`. The announcement starts streaming immediately; the SFX lands on top of the trailing portion (the part that repeats the move's *destination*, which the user already inferred from board context).
- **Make the delay user-configurable** in the sound settings dialog ("Sound delay after announcement: 0/150/300/500 ms").
- **Per-event SFX can be disabled** independently — keep the categorical on/off (own-move, opponent, capture, check, castle) so a heavy NVDA user can mute everything except check and clock-low.
- **Volume default is conservative.** Move SFX defaults to ~50% volume; the screen reader is the primary signal.
- For the "low time" tick, use a *brief, narrow-band* tone (think metronome click, not a synth pad) — wide-spectrum sounds mask speech formants more aggressively.

**Warning signs:**
- QA with NVDA's Speech Viewer enabled: if the on-screen speech text says "…takes e5+" but the audible announcement starts mid-word, the SFX is masking.
- User report: "I can't tell when it's check from a knight move" (because the +/check suffix in SAN is at the *end* of the announcement and gets clobbered).
- Automated test: capture the order and `wx.CallLater` delay between announce signal emission and SFX dispatch.

**Phase to address:**
Sound layer phase. Cross-cuts the verbosity tiers phase (verbosity dialog must include "SFX delay" alongside per-event SFX toggles).

---

### Pitfall 2: Clock drift from accumulating wx.Timer ticks instead of timestamping

**What goes wrong:**
Engineer implements the clock as `wx.Timer(100ms)` → `remaining_ms -= 100` on every tick. The clock displays correctly for ~30 seconds, then drifts noticeably. By move 40 in a 5+0 game, the displayed clock is 6-12 seconds slower than wall-clock truth. In a 1+0 bullet game the clock can show 30+ remaining when wall-clock says 0 — a flagging dispute.

**Why it happens:**
`wx.Timer` precision is platform-dependent and explicitly documented as "not better than 1 ms nor worse than 1 s" (wxPython docs). Coalesced tick events on Windows (especially under load), thread starvation, and the GIL all conspire to fire the timer late. Subtracting a *constant* per tick assumes the tick fires on schedule — it doesn't.

**How to avoid:**
- **Never subtract per-tick.** Store `move_started_at: float` (a monotonic wall-clock timestamp from `time.monotonic()`) plus `remaining_at_move_start_ms: int`. On every UI redraw, compute `remaining = remaining_at_move_start_ms - (time.monotonic() - move_started_at) * 1000`.
- The `wx.Timer` (e.g. 100 ms) only triggers a *redraw and re-announcement check* — it does not own the time. If a tick is skipped, the next redraw still computes the correct value.
- **Increment is applied on move-commit, not tick:** when a move is pushed to `BoardState`, capture `time.monotonic()` for the now-active side and set their `remaining_at_move_start_ms = previous_remaining + increment_ms`.
- **Use `time.monotonic()` not `time.time()`** — wall clock can jump backwards (NTP, suspend/resume, DST on some systems).

**Warning signs:**
- Test pattern: simulate 1000 tick events with `time.sleep(0.05)` between them and assert that displayed remaining time matches `start - elapsed_wallclock` to within 50 ms. A naive subtract-per-tick implementation will fail this.
- Manual: start a 5+0 game, walk away for 2 minutes, return — clock should show ~3:00, not 3:08.

**Phase to address:**
Clock infrastructure phase. The `Clock` model class is the single authority; `wx.Timer` only drives presentation.

---

### Pitfall 3: Clock fails to pause during modal dialogs and "New Game" flows

**What goes wrong:**
User opens "Load PGN…", "Settings", or the new key-rebinding dialog mid-game. The clock keeps ticking. By the time they close the dialog, they've "spent" 30 seconds of thinking time on a UI navigation task. Worse: in a finished game replay, the clock is still running because a `Game.new_game()` path didn't reset it.

**Why it happens:**
Modal dialogs in wxPython block the main event loop locally but `wx.Timer` keeps firing. Engineers hook timer pause logic into specific dialogs but miss new ones added later. The `move_undone` signal-loss bug in `CONCERNS.md` (Bug #1) is the same class of failure — model state and signal subscriptions go out of sync after a `new_game()`.

**How to avoid:**
- **Centralize pause/resume around `wx.EVT_ACTIVATE_APP` and a single `Clock.set_paused(reason: str)` API.** Reasons stack: pausing for "modal_dialog" while already paused for "game_over" should not double-toggle. Use a set of pause reasons, not a boolean.
- **Auto-pause whenever a `wx.Dialog.ShowModal` is entered.** Subclass a `ClockAwareDialog` for any v1 modal that can run mid-game (key rebinding, sound settings, theme settings, save-as PGN).
- **`Game.new_game()` must reset the clock and signal subscriptions in one place.** Following the same fix pattern as the `move_undone` bug: forward `Clock` signals through `Game` (game.clock_low, game.flag_fall) so subscribers don't bind to a stale `Clock` instance after `new_game()`.
- **Test:** programmatically open every v1 modal mid-game and assert the clock did not advance more than 50 ms during its lifetime.

**Warning signs:**
- QA: open Settings, walk to lunch, return — clock is at 0:00.
- Code smell: any new `wx.Dialog` subclass that doesn't go through the `ClockAwareDialog` base.
- Bug echo: pressing Undo immediately after New Game does the wrong thing → indicates the same signal-rehook hole the `move_undone` bug demonstrated.

**Phase to address:**
Clock infrastructure phase. Verification touches **every** later phase that adds a modal dialog (rebinding UI, sound settings, theme settings).

---

### Pitfall 4: Auto-save writes torn-state files on crash

**What goes wrong:**
Auto-save fires every N seconds (or on every move). It opens `current_game.json` for write, dumps half the JSON, the process is killed (OOM, SIGKILL, power loss, OS update) — and on next launch the user's in-progress game is corrupt JSON. Crash recovery, the *whole point* of auto-save, fails exactly when it matters.

**Why it happens:**
`open(path, "w")` truncates the file before writing. A crash mid-write leaves a partial file. The naive fix — write to `.tmp` then `os.rename` — is *almost* right but skips `fsync`. On modern filesystems with delayed writes (especially btrfs, XFS), the rename is durable but the contents are not — the rename can be applied while the file still has zero bytes.

**How to avoid:**
- **Three-step atomic write, every time:**
  1. Write payload to `current_game.json.tmp` (in the same directory as the target — cross-filesystem rename is not atomic).
  2. `tmp.flush()` then `os.fsync(tmp.fileno())` (or `fcntl.F_FULLFSYNC` on macOS, where `os.fsync` is a no-op for some filesystems).
  3. `os.replace(tmp_path, target_path)` — atomic on POSIX and Windows since Python 3.3.
- **Use `platformdirs.user_data_dir("openboard")` for the save location** — not `Path.cwd()`. The `cwd` issue is already documented in CONCERNS.md (Security #4); auto-save inheriting that bug would be doubly bad.
- **Auto-save is throttled, not per-move.** Coalesce: save at most once per 2 seconds, debounced. A blitz player making 10 moves in 5 seconds should not produce 10 disk syncs (they're slow on HDDs and noisy on SSDs).
- **Auto-save runs off the main thread.** Serialize the game state to an in-memory string on the main thread (cheap), hand it to a background thread for the write+fsync (slow, blocking). Otherwise a save during a redraw causes a visible UI hitch — bad on its own and worse for screen-reader users who rely on consistent timing.
- **On startup, attempt to load `current_game.json`. If it's malformed, fall back to `current_game.json.bak` (a one-generation-old copy made before each save).**

**Warning signs:**
- Test pattern: while auto-save is mid-write, kill the process (`os.kill(pid, SIGKILL)` from a test harness on Linux). Restart the app: it must either load the previous valid state or report a recoverable error — never crash on parse.
- QA: unplug the laptop in the middle of a long capture sequence. Recover.

**Phase to address:**
PGN/FEN persistence + auto-save phase.

---

### Pitfall 5: Key rebinding lets users overwrite the screen reader's own modifier shortcuts

**What goes wrong:**
User opens the key-rebinding dialog and binds "Move forward in PGN" to `NVDA+RightArrow`. NVDA also uses that combination ("read next line"). Now the user has destroyed their primary navigation key inside their own screen reader, system-wide, until they reset OpenBoard or NVDA. The damage is silent — there's no error, just a regression in their non-OpenBoard workflow.

Adjacent failure: dead keys on non-US layouts. A German user tries to bind "show hint" to `=`. On a German keyboard, `=` is `Shift+0`. wxPython's `EVT_CHAR_HOOK` on Linux/X11 may fire only for the character (`=`) without the modifier flags the user actually pressed, or fire only the modifier with no key, depending on layout. The captured binding is unreplayable.

**Why it happens:**
- NVDA reserves `Insert+*` and `CapsLock+*` (the "NVDA modifier"), JAWS reserves `Insert+*`, Orca on Linux reserves `CapsLock+*` or `Insert+*` per user config. These are not application-scoped — they're system hooks.
- `EVT_CHAR_HOOK` on non-US keyboards is documented to be layout-dependent; the wxPython docs explicitly call out that "not all key events may be generated on non-US keyboards" and translation is "keyboard-layout dependent and can only be done properly by the system itself."
- Dead keys (e.g. `^` on French AZERTY waiting for the next key to compose `ê`) generate no event until the second keystroke arrives.

**How to avoid:**
- **Maintain a `RESERVED_SHORTCUTS` blocklist** that includes `Insert+anything`, `CapsLock+anything` (since most VI users remap CapsLock to NVDA modifier), and platform-standard reserved keys (`Cmd+Q`, `Alt+F4`, `F1`-as-help). On rebind capture, if the captured chord is in the blocklist, *refuse* and explain why ("This combination is reserved by NVDA / JAWS — pick another").
- **Capture by `wx.KeyCode` and `wx.GetKeyState` modifier flags, not characters.** The binding stored in `keyboard_config.json` should be `{"keycode": 39, "modifiers": ["ctrl"]}`, not `{"char": "→", "modifiers": ["ctrl"]}` — the keycode is layout-stable.
- **Validate at load time.** When `keyboard_config.json` is read, log and skip bindings with unknown keycodes or empty modifier-only chords (Shift alone, etc.).
- **Provide a "Reset all bindings to default" button** — clearly labeled, focusable from keyboard, with a confirmation dialog. This is the user's escape hatch when they break themselves.
- **Test with a virtual machine running a non-US layout (German + French AZERTY at minimum)** — capture each binding action and replay it to confirm round-trip.
- **Keep the existing `keyboard_config.json` file as the source of truth.** The new UI is a *editor* over that file. Do not introduce a parallel storage in `wx.Config` or registry — it splits the source of truth.

**Warning signs:**
- User report: "NVDA stopped reading after I changed shortcuts in OpenBoard."
- Code smell: rebinding capture using `event.GetUnicodeKey()` (layout-dependent) instead of `event.GetKeyCode()` (raw).
- QA: switch to German keyboard layout, try to rebind every default action; any binding that throws or captures empty chord is a fail.

**Phase to address:**
Key-rebinding UI phase. Hard dependency on wxPython key event semantics — research test on non-US layout *before* writing the dialog, not after.

---

### Pitfall 6: High-contrast theme passes WCAG AA in isolation but fails when highlights overlap

**What goes wrong:**
Designer ships a high-contrast theme with light squares = `#FFFFFF` and dark squares = `#000000` (21:1 — best possible). Selected square gets a yellow border `#FFFF00`. Check highlight gets a red overlay `#FF0000`. Last-move highlight gets a blue overlay `#0000FF`. Each in isolation passes WCAG AA against its base square. But when the player's king is in check on the last-moved-to selected square, three overlays stack and the resulting blended pixel is some muddy purple-orange that no longer has 4.5:1 against either base square — the user can't visually parse the most important state on the board.

**Why it happens:**
WCAG contrast tooling tests two colors at a time. Chess UIs routinely composite three or more state markers on a single square (selected + check + last-move + cursor focus). Alpha blending is invisible to most contrast checkers.

**How to avoid:**
- **Define a state precedence for highlights, not blending.** When two states apply to the same square, the higher-priority one *replaces* the lower's visual treatment, it doesn't composite. Suggested order (highest first): cursor focus > check > selected (origin of move) > last-move target > last-move origin > legal-move dot.
- **Test the matrix.** Write a unit test that iterates every (light/dark square) × (every combination of up to 3 simultaneous states) and asserts the resulting rendered pixel against the *square's* color has at least 3:1 (UI component contrast minimum) or 4.5:1 (text contrast). This is ~64 combinations, automatable.
- **Never rely on color alone (WCAG 1.4.1).** Check should also be announced ("you are in check") — already partially done; ensure the high-contrast theme adds a *non-color* cue (thicker border, stripe pattern) for check, since some users with dyschromatopsia may toggle high-contrast mode and still struggle with red.
- **Adjustable scale must be tested with the high-contrast theme.** A 1-pixel border at 200% scale is a 2-pixel border — fine. At 80% scale (some low-vision users zoom *out* of dense info) it's gone. Borders should scale proportionally, not be a fixed pixel count.

**Warning signs:**
- QA on a colorimeter or with `scripts/check_theme_contrast.py`: any combination falling below 3:1 fails.
- User report: "I can see check, I can see selected, but when both happen I lose track."

**Phase to address:**
High-contrast theme phase. Adjustable-scale phase needs to inherit the same matrix test (the test fixture should parameterize over scale factors).

---

### Pitfall 7: PGN load mishandles variations, NAGs, multi-game files, or non-ASCII headers

**What goes wrong:**
Engineer wires up `chess.pgn.read_game(file)` and assumes that's enough. The first failure surfaces when a user loads a PGN they downloaded from Lichess: it's a multi-game file (every player's history concatenated). The current code reads the first game and silently discards the rest. Or: a study PGN has variations and NAGs (`!`, `?`, `!!`, `$1`); the load works but the move-list dialog only shows the mainline, with no indication that variations were dropped — a teacher exploring a study has lost their material. Or: a Polish player loads a PGN with `[White "Świerc, Ryszard"]`; the file was written as Latin-1 and Python opens it as UTF-8 → `UnicodeDecodeError` aborts the load.

**Why it happens:**
PGN spec is forgiving and python-chess parses forgivingly (errors are collected in `Game.errors` rather than raised by default), which means malformed files *appear* to load successfully even when content was dropped. The library handles variations, NAGs, and comments natively, but the application has to opt in to surface them.

**How to avoid:**
- **Always check `game.errors` after `read_game()`.** If non-empty, surface a dialog: "PGN loaded with N issues. View details?" Log to file unconditionally.
- **Detect multi-game PGNs** by calling `read_game()` in a loop until it returns `None`. If >1 game, present a game-picker dialog. v1 is allowed to ship "we loaded the first game; multi-game library is v2" — but it must *say so*, not silently drop.
- **Encoding fallback chain:** try UTF-8, fall back to Latin-1, fall back to chardet detection. Wrap every file open with `errors="replace"` as a last resort so a single bad byte never crashes a load. Surface a non-fatal warning if fallback was used.
- **Variations in v1 scope:** decision required during planning. The minimum is to *preserve* variations on save (round-trip them through the in-memory `Game` tree even if not displayed). Display can be deferred. Discarding variations silently on load is the bug — discarding them by an explicit, announced "main line only" mode is acceptable.
- **NAGs:** the announcer should know about NAGs when reading a loaded game. `node.nags` is a `set[int]` — map common ones (1=`!`, 2=`?`, 3=`!!`, 4=`??`, 5=`!?`, 6=`?!`) to verbal annotations ("blunder", "good move") in verbose mode.

**Warning signs:**
- Test corpus: include a multi-game Lichess study PGN, a PGN with variations and NAGs (any annotated game), a PGN with Cyrillic / Polish / German header values, and a deliberately malformed PGN. All four must round-trip or fail gracefully with a user-facing error.
- Bug echo: see CONCERNS.md `on_load_pgn` `wx.ID_ANY` binding bug — silent failures in the PGN load path are already a known repo pattern. Be paranoid here.

**Phase to address:**
PGN/FEN persistence phase.

---

### Pitfall 8: FEN edge cases (castling rights when rook returned, ep target subtleties)

**What goes wrong:**
User saves a FEN at a position where the king has not moved but the white kingside rook moved to f1 and back to h1 — castling rights were forfeited the moment the rook first moved. A naive FEN producer that only checks "is the king on e1 and a rook on h1?" emits `KQkq` and the position now claims castling rights it shouldn't have. Loaded back, Stockfish plays `0-0` and the user sees the engine make an "illegal" castle.

Adjacent: en passant. The classic FEN spec says the ep target square is set "after every two-square pawn move", regardless of whether ep is actually capturable. Stockfish and python-chess interpret strictly (you have to legally be able to capture). A FEN written by a different tool (chess.com export) may include an ep target that python-chess thinks is bogus — `Board.is_valid()` returns `False` and the load aborts.

**Why it happens:**
FEN is a string spec. python-chess models the position with full state but the FEN encoding is lossy unless you use the right method (`fen()` vs `epd()` vs `shredder_fen()`). Castling rights and ep target are the two fields where the encoding rules are subtle, and where third-party FENs disagree.

**How to avoid:**
- **Never construct FEN by hand.** Always go through `chess.Board.fen(en_passant="legal")` (default in modern python-chess; Context7 confirms current 1.11.x default behavior). Castling rights are tracked correctly *if* moves were applied through `board.push()` — never via direct piece manipulation that bypasses `Board`'s castling-rights bookkeeping.
- **For loading external FENs, use `Board(fen, chess960=False)` and immediately call `board.is_valid()`.** If invalid, *don't* abort — try `board.is_valid()` again with `Board(fen, chess960=True)` (chess.com sometimes emits Shredder-FEN castling like `HAha`). If both fail, surface the specific reason: "FEN has invalid en passant target square" or "FEN has impossible castling rights."
- **`Board.status()` returns a bitmask of issues** — show specific ones to the user, not a generic "invalid FEN."
- **Round-trip test:** for every position reached during a game, FEN-encode it, decode back, assert `Board.fen() == original.fen()` and `list(board.legal_moves) == list(original.legal_moves)`. Catch decoding regressions early.
- **Setup-from-FEN entry point** (the v1 feature) must validate and offer a side-by-side "you typed X, I parsed it as Y" preview before committing — a single typo in a FEN can spawn an illegal position that a screen-reader user can't visually verify.

**Warning signs:**
- Test fixture must include: position after rook moved+returned, position with valid ep target, position with "spec-correct but not legally capturable" ep target, mid-game position copy-pasted from chess.com (Shredder-FEN), Chess960 starting position.

**Phase to address:**
PGN/FEN persistence phase.

---

### Pitfall 9: Verbosity dialog is itself inaccessible

**What goes wrong:**
A "Per-event announcement verbosity" settings dialog ships with a 2D table: rows are events (move-made, capture, check, castle, promotion, hint, book-hint, time-low, undo, navigation, …), columns are verbosity tiers (silent, brief, normal, verbose). The dialog presents this as a `wx.Grid` because that's the natural visual metaphor. NVDA reads `wx.Grid` cells row-by-row with no useful context: "row 4 column 2 radio". The blind user — the *target user* of this very feature — cannot operate the dialog that controls how the app talks to them.

**Why it happens:**
Engineer optimizes for the visual designer's mental model. `wx.Grid` is one of the worst-supported wxPython widgets for screen readers across platforms. It also fails Tab-order expectations.

**How to avoid:**
- **Use one `wx.Choice` (dropdown) per event row, not a grid.** Dropdowns are universally well-supported by NVDA/JAWS/VoiceOver/Orca, and tab order is linear and predictable.
- **Each control has an explicit `wx.StaticText` label (associated, not just adjacent) so the screen reader announces the event name with the choice.** Use `wx.Window.SetLabel()` and proper accessibility-text rather than relying on visual proximity.
- **Test the dialog with NVDA + Orca + VoiceOver** — *every* settings dialog added in v1, but this one especially. Operating the verbosity dialog is itself a verbosity test.
- **Provide a "Reset to defaults" button** — same accessibility pattern as the rebinding UI.
- **The verbosity model has a shape decision:** flat per-event tier, or hierarchical (categories → events). v1 should ship flat; hierarchical adds a tree widget which is even harder to make accessible.

**Warning signs:**
- QA checklist (mandatory): can the dialog be operated start-to-finish using only Tab, Shift+Tab, Up/Down, Space, and Enter — no mouse, no arrow keys outside of dropdowns?
- Code smell: `wx.Grid`, `wx.ListCtrl` in report mode, or any custom widget for this feature.

**Phase to address:**
Verbosity tiers phase. This pitfall is a hard prerequisite for the feature shipping at all — if the dialog isn't accessible, the feature failed regardless of how good the verbosity model is.

---

### Pitfall 10: Cross-platform sound layer with platform-specific failure modes

**What goes wrong:**
Sound works on the developer's Windows machine. On Linux Mint with PipeWire, there's a 200-400 ms latency on the first SFX after silence (the device wakes up cold) — the user hears the click *after* the announcement finishes, not over its tail. On macOS, the app is sandboxed (when distributed via DMG with a hardened runtime) and the embedded `pygame.mixer` fails silently because it tried to write a temp file outside the sandbox. On Windows with WASAPI exclusive mode held by another app (Discord call), playback simply does nothing.

**Why it happens:**
Cross-platform audio in Python is a stack of partial abstractions. `winsound` is Windows-only and synchronous (blocks the UI). `pygame.mixer` is heavy (initializes a full SDL audio subsystem) and licensed LGPL (already a constraint to track). `simpleaudio` is unmaintained as of 2024 and lacks PipeWire-native support on Linux. `playsound` 1.x is broken; `playsound` 3.x is better but still launches subprocess players. None of them play well with sandbox / hardened-runtime macOS distribution.

**How to avoid:**
- **Pick one library and fall back gracefully.** Recommended order to evaluate during the sound phase:
  1. `pygame.mixer` (most platform coverage, but heavy and LGPL — compatible with this project's MIT but bears mention in NOTICE).
  2. `sounddevice` + `soundfile` (PortAudio binding; cleaner API; works with PipeWire's PulseAudio shim).
  3. Platform-native fallback for the hard cases (e.g. `winsound.PlaySound` async on Windows as last resort).
- **Initialize the audio device at app startup, not on first SFX.** Cold-start latency happens once at boot, not in the middle of gameplay. Pre-load every WAV into memory at startup — do not stream from disk per-event.
- **All SFX are short (<1 s), 16-bit PCM WAV, 44.1 kHz mono.** Anything longer or compressed adds decode latency. Mono is fine for game SFX and halves memory.
- **Play SFX off the main thread.** `pygame.mixer.Sound.play()` is non-blocking but the loading and decode is. Wrap the load in startup; the play call itself is cheap.
- **Failure is silent and logged, never an error popup.** If audio init fails entirely (no device, sandbox refusal), the app continues working; sound settings reflect "audio unavailable."
- **Test matrix in CI:** Linux (Ubuntu 24.04, headless via PulseAudio dummy sink), Windows latest, macOS latest. Each must successfully `import` the audio library; actual playback verification is manual.

**Warning signs:**
- User report on Linux: "first move makes no sound, subsequent ones do." (Cold device start.)
- User report on macOS: "no sounds at all after I installed from the .dmg." (Hardened runtime / sandbox.)
- Code smell: lazy-init pattern (`if self._mixer is None: pygame.mixer.init()` inside `play_sfx`).

**Phase to address:**
Sound layer phase.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems for *this* codebase.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hooking new signals to specific `BoardState` / `Clock` instances directly in controller `__init__` | One line of code, looks symmetric with existing hookups | Recreates the `move_undone` signal-loss bug after `new_game()`; every signal-on-instance breaks when the instance is replaced | **Never** — go through `Game.signal_X` forwarder pattern (see CONCERNS.md Bug #1 for the canonical fix) |
| Adding a new `wx.ID_ANY` menu binding | Fast to write | Recreates `on_load_pgn` fallback-handler bug from CONCERNS.md | **Never** — capture the menu item ID at construction and bind to it |
| Per-tick decrementing in the clock model | Simple, intuitive | Drift makes the clock unreliable; flag falls happen on wrong wall-clock time | **Never** — timestamp on move, compute remaining at display time |
| Using `pygame.mixer.init()` lazily on first SFX | Saves ~50 ms at startup | Cold-device latency exactly when user notices it most (first move) | **Never** — startup is the right place |
| Storing rebindings as Unicode characters instead of keycodes | Reads naturally in JSON | Breaks on non-US layouts, dead keys, layout switches mid-session | Only for *display* in the rebinding UI — storage must be keycode |
| Mixing `time.time()` and `time.monotonic()` in clock code | "It works on my machine" | Wall-clock jumps (NTP, suspend) cause clock to leap forward or backward seconds | **Never** for elapsed-time math; `time.time()` only for display in PGN headers |
| Auto-save on every move | Simple to implement | I/O thrash on blitz, perceptible UI hitch, accelerated SSD wear | Acceptable in v1 if throttled to ≤1 save / 2 seconds and run off-thread |
| Adding a new modal dialog without inheriting `ClockAwareDialog` | Less typing | Clock keeps ticking during dialog → feature regression | **Never** once `ClockAwareDialog` exists |
| Discarding PGN variations on load to "keep it simple" | Smaller move list to render | Silent data loss; user's annotated study is destroyed on save-back | Acceptable only with explicit UI mode "Main line only — variations preserved in file" |
| Using `wx.Grid` for any settings dialog | Visually compact | Inaccessible to screen readers | **Never** for a11y-relevant UI; tabular settings should be one row of `wx.Choice`s per item |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `accessible_output3` | Calling `.speak()` and `.silence()` from background thread | Marshal to main thread via `wx.CallAfter`; the screen reader IPC clients are not thread-safe |
| `accessible_output3` (NVDA backend) | Assuming there's a "speech finished" callback | There isn't — use `wx.CallLater` with empirical delay if you need ordering with SFX |
| python-chess `Board.push()` | Calling `push()` directly on `chess.Board` instead of through `BoardState.make_move()` | Always go through the model layer — see CONCERNS.md Bug #2 (`_navigate_to_position` bypass) |
| python-chess `pgn.read_game()` | Treating no exception as success | Check `game.errors` list; loop until `read_game()` returns `None` to detect multi-game files |
| python-chess `Board(fen)` | Trusting any string the user pastes | Call `board.is_valid()` and surface `board.status()` flags to the user before applying |
| Stockfish (UCI) | Sending UCI commands from main thread synchronously | Already correct in this repo via `EngineAdapter`; do not regress this. CONCERNS.md flags `EngineAdapter` as the most-fragile area in the codebase |
| `wx.Timer` | Subtracting per-tick or assuming uniform tick rate | Timer is only a redraw signal; truth lives in `time.monotonic()` timestamps |
| `wx.CallAfter` | Closing over `self` in a tight engine-callback loop | Lambda captures keep `self` alive; explicitly `weakref` the controller if the call site is unavoidably hot |
| Polyglot opening book | Re-opening the book file per query | Load once at startup, keep handle; the existing `book_handler` already does this — preserve it |
| `platformdirs` (recommended for v1) | Computing paths from `Path.cwd()` | Use `platformdirs.user_data_dir("openboard")` / `user_config_dir` for save files, settings, engine binaries — fixes the existing CONCERNS.md issue while you're in there |

---

## Performance Traps

Patterns that work in development but degrade in real games.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Replaying full move stack to compute "before" board for each announcement | Announcement lag grows with move number | Pass `_pending_old_board` through every code path (see CONCERNS.md Performance #1) | ≥ 50 moves into a game |
| `BoardState.board` returning `_board.copy()` per call | UI hitch on `on_paint` (64 squares × copy) | Add `board_ref` for read-only callers (CONCERNS.md Performance #3) | Any time `on_paint` is the bottleneck — already an issue today |
| `announce_attacking_pieces` iterating legal moves | Blocking the UI thread for 100+ ms in dense middlegames | Use `board.attackers()` bitboard (CONCERNS.md Performance #2 and Bug #3 — same fix) | Any complex middlegame |
| Auto-save serializing the entire game on the main thread | Visible hitch every save interval | Serialize-on-main, write-on-background-thread | Long games (50+ moves) where serialization gets non-trivial |
| Loading SFX from disk per-play | Audible delay on first play of each event type | Pre-load all SFX into memory at startup | First play of each SFX type |
| Clock redraw ticking at 100 ms even when displayed precision is seconds | Wasteful repaint every 100 ms | Tick at 100 ms but repaint only when displayed value changes (or when remaining < 10 s) | Mostly fine, but matters on low-power Linux laptops |
| `wx.Grid` re-rendering full grid on every cell update | Sluggish settings UI | Use simple `wx.Choice`/`wx.RadioBox` per row | Verbosity dialog scaling beyond ~10 events |

---

## Security Mistakes

Domain-specific (chess GUI) plus carryover from CONCERNS.md.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Loading a PGN's `[FEN ""]` header without validating with `Board.is_valid()` | Malformed FEN crashes the load path or puts the engine in an undefined state | Validate every FEN that enters from disk; surface invalid-position errors to the user |
| Trusting comments in user-supplied PGN files | Comments can contain anything; if ever rendered as HTML/markup in a future help dialog → injection | Render comments as plain text; never as HTML; truncate displayed length |
| Auto-save storing absolute paths or user identity in the saved game | Privacy leak when user shares a saved-game file | Save only chess-relevant data (PGN + clock state + settings reference, not absolute paths) |
| Loading a PGN with an enormous number of variations as a DoS vector | Memory blowup or UI freeze | Cap nodes-loaded at a sane bound (e.g. 100k); refuse files exceeding it with explanation |
| Writing the keyboard config back without sanitizing keycodes | A maliciously crafted `keyboard_config.json` could bind every key to an unintended action | Validate keycodes against the `KeyAction` enum on load; reject unknown actions |
| (Inherited) Stockfish download without checksum (CONCERNS.md Security #1) | Compromised binary executed | v1 should fix: verify SHA-256 against the GitHub release manifest |
| (Inherited) ZIP extraction without path traversal check (CONCERNS.md Security #2) | `..` paths escape extraction dir | v1 should fix: validate every member path stays inside the extract dir |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| "Save game" defaults to overwriting `current_game.pgn` without warning | User loses prior saved game | Default filename includes ISO date + opponent + result; "Save As…" is the only path that overwrites silently |
| Sound categories all default to ON at full volume | First launch is jarring; user reaches for the OS volume mixer | Default: own-move ON at 50%, opponent ON at 50%, capture ON at 60%, check ON at 70%, castle ON at 50%, low-time tick OFF (opt-in only) |
| Clock-low threshold hardcoded at 30 seconds | A 60+0 game spends most of its time below 30s; a 90+0 game with a long classical control never warns | Threshold scales: max(10 s, 5% of base time) and is user-overridable |
| "Clocks off" implemented by setting time to infinity | Edge cases (PGN export `[TimeControl "?"]` vs `[TimeControl "-"]` vs absent) all become ambiguous | `Clock` has an explicit `enabled: bool`; PGN export omits `[TimeControl]` / `[WhiteClock]` headers when disabled |
| Theme switch triggers full window recreate | Focus lost; screen reader announces "main window" again, breaking the user's mental position | Theme switch swaps colors in place; preserve focus and screen-reader navigation context |
| Scale slider rebuilds the board panel on every drag tick | Choppy, screen reader announces every intermediate state | Debounce scale changes (apply on slider release, not drag); during drag, only repaint with new scale, do not rewire |
| Rebinding dialog requires a confirmation modal *during* capture | Disorienting for screen-reader users mid-capture | Capture is in-place inline; confirmation is a final "Apply changes" button at dialog level |
| Auto-save success/failure announced verbally on every save | Verbose toggle exists; that doesn't make it the right channel | Auto-save is silent on success, announces only on failure; per-category verbosity must include "auto-save" event with default = silent |
| FEN setup-from-FEN dialog with one big text box and "OK" | User makes a typo, gets generic "invalid FEN", no way to know which field | Multi-field input (board / turn / castling / ep / clocks) OR live-validation with field-level errors |
| Promotion piece chosen by modal blocking the game thread | Loud focus-shift right at the most time-pressed moment | Promotion choice via inline keyboard chord (Q / R / B / N) at the moment the move is keyed; modal is a fallback |

---

## "Looks Done But Isn't" Checklist

- [ ] **Sound:** SFX file embedded in build artifact for *every* platform (PyInstaller spec includes `data` entries for all WAV files; verify on Win/macOS/Linux artifacts)
- [ ] **Sound:** First SFX after app boot has acceptable latency (< 200 ms); not just "it eventually plays"
- [ ] **Sound:** Per-category mute persists across restart (settings actually written, not held only in memory)
- [ ] **Clock:** Verify clock pauses for *every* modal dialog in v1 — not just the ones the engineer remembered
- [ ] **Clock:** PGN written by us round-trips through `chess.pgn.read_game()` and re-encodes to byte-identical PGN headers (`[TimeControl]`, `[WhiteClock]`, `[BlackClock]`)
- [ ] **Clock:** Clock state survives auto-save → kill → reload (the auto-save format must include both clocks' remaining + which side is ticking + monotonic offset for elapsed-since-last-snapshot)
- [ ] **Auto-save:** Crash recovery test: SIGKILL during a write → next launch recovers either the new state or the .bak, never crashes
- [ ] **Auto-save:** Disk-full simulation: errno ENOSPC during fsync → user-facing error, no data loss to existing saved file
- [ ] **PGN load:** Multi-game PGN handled — picker shown or "first game loaded" announced
- [ ] **PGN load:** Variations preserved on load → save round-trip (even if not displayed)
- [ ] **PGN load:** Non-ASCII headers (Cyrillic / Polish / Chinese) round-trip without mojibake
- [ ] **PGN load:** Game.errors list checked and surfaced to user for any non-empty case
- [ ] **FEN:** Round-trip test: every position from a sample game produces identical FEN encoded → decoded → encoded
- [ ] **FEN:** Setup-from-FEN with rook-moved-and-returned position correctly drops castling rights
- [ ] **High-contrast theme:** All highlight combinations (selected + check + last-move + cursor) maintain ≥ 3:1 contrast against base square
- [ ] **High-contrast theme:** Check is conveyed by both color *and* a non-color indicator (border style or pattern)
- [ ] **Scale:** Range tested at 80%, 100%, 150%, 200% — no overlap, no clipping, no border disappearance
- [ ] **Rebinding UI:** All bindings round-trip through JSON file (modify in UI → reopen UI → values match)
- [ ] **Rebinding UI:** NVDA/JAWS reserved chords cannot be assigned (blocked with explanation)
- [ ] **Rebinding UI:** "Reset to defaults" button works and is reachable by keyboard alone
- [ ] **Verbosity dialog:** Operable end-to-end with NVDA, screen on, no mouse
- [ ] **Verbosity dialog:** Verbosity for "auto-save" event defaults to silent
- [ ] **Tech debt:** `move_undone` signal works after `new_game()` (CONCERNS.md Bug #1) — *and a regression test exists*
- [ ] **Tech debt:** `_navigate_to_position` goes through model layer (CONCERNS.md Bug #2)
- [ ] **Tech debt:** `announce_attacking_pieces` uses `board.attackers()` and reports pinned pieces correctly (CONCERNS.md Bug #3)
- [ ] **Tech debt:** Removing `_simple` API surface did not break any external script — `grep -r _simple` outside `engine_adapter.py` returns zero results in main, in tests, in docs, and (manually) in any companion repos
- [ ] **Tech debt:** `on_load_pgn` no longer fires on every `wx.ID_ANY` event (CONCERNS.md Bug #4) — and a test exercises a different menu item to verify

---

## Recovery Strategies

When pitfalls slip through, here's how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Auto-save file corrupt on load | LOW | Fall back to `.bak`, alert user, log the corrupted file path so they can attempt manual recovery |
| Clock drift discovered post-ship | MEDIUM | Hotfix: replace tick-decrement with timestamp model; add the test that should have been there originally; PGN re-export of completed games is unaffected (only display was wrong) |
| Move SFX masking announcements | LOW | Increase default delay; expose delay slider in settings; document the workaround in release notes — the underlying architecture (announce → CallLater → SFX) supports it without a refactor |
| Rebinding bricks user's screen-reader hotkeys | LOW (if the reset button works) / HIGH (if it doesn't) | Document the path to delete `keyboard_config.json` (in `platformdirs.user_config_dir`); reset-button must be reachable without screen reader as an absolute last resort |
| PGN load silently dropped variations | MEDIUM | Re-load the original file (it's untouched on disk); ship a reload + warning; add `game.errors` surfacing |
| FEN load created an "impossible" position | LOW | Reject at load; display `Board.status()` flags; user re-enters |
| High-contrast theme combination unreadable | LOW | Theme is data — patch the JSON theme file in a hotfix release without touching code |
| Sound system fails to init on user's box | LOW | Already handled if the sound layer fails gracefully; user toggles all sounds off and continues |
| `move_undone` regression returns | MEDIUM | The fix-by-forwarding-through-Game pattern means *one* test for the regression (game.new_game then game.undo) plus assertion that all controller subscriptions go through `Game.*` signals, not `BoardState.*` signals directly |
| Clock didn't pause for a new modal | LOW | Inherit from `ClockAwareDialog`; add the test that asserts pause for every dialog the test fixture knows about |

---

## Pitfall-to-Phase Mapping

The roadmap consumer should treat this as the v1 phase risk register.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. SFX masking announcements | Sound layer | Manual NVDA test + automated assertion of announce-then-CallLater ordering |
| 2. Clock drift | Clock infrastructure | Unit test simulating skipped/late ticks against `time.monotonic()` truth |
| 3. Clock not pausing for modals | Clock infrastructure (cross-cuts every later modal phase) | Test fixture iterating every v1 modal asserting < 50 ms clock advance during ShowModal |
| 4. Auto-save torn writes | PGN/FEN persistence + auto-save | SIGKILL-during-write test + recovery from `.bak` test |
| 5. Rebinding overwrites a11y modifiers | Key-rebinding UI | Reserved-shortcut blocklist test + non-US layout VM round-trip test |
| 6. High-contrast highlight overlap | High-contrast theme + scale | Theme-matrix contrast test (parametrized over all state combinations × scale factors) |
| 7. PGN edge cases | PGN/FEN persistence | Test corpus with multi-game, variations, NAGs, non-ASCII headers, malformed |
| 8. FEN edge cases | PGN/FEN persistence | Round-trip test + adversarial test corpus (rook returned, third-party Shredder-FEN) |
| 9. Verbosity dialog inaccessible | Verbosity tiers | Manual NVDA + Orca + VoiceOver operation; no `wx.Grid` allowed |
| 10. Cross-platform sound regressions | Sound layer | CI matrix import smoke test + per-platform manual playback verification before release |
| Re-creating signal-rehook bug class | Cross-cutting tech-debt phase (early) | Regression test for `move_undone` after `new_game` + lint rule (or grep) flagging direct `board_state.X.connect` outside `Game` forwarders |
| Re-creating `wx.ID_ANY` bind bug | Cross-cutting tech-debt phase (early) | Code review check + test exercising a separate menu item to confirm `on_load_pgn` is not called for it |
| `_simple` API removal breaking unknown consumer | Cross-cutting tech-debt phase | Pre-removal: search this repo, public Stockfish-related forks, and project docs; post-removal: keep one release with `DeprecationWarning` shim if any external use is suspected |

**Recommended phase ordering implication:**
The cross-cutting tech-debt phase (CONCERNS.md cleanup) should land **before** clock infrastructure and **before** PGN/FEN persistence, because:
1. The signal-rehook fix pattern (`move_undone` bug) is the canonical pattern for `Clock` signal forwarding through `Game.new_game()`. Establishing it first means the clock phase inherits a known-good pattern.
2. Fixing `_navigate_to_position` to go through the model layer establishes the precedent that PGN-load and FEN-setup must also flow through `Game` / `BoardState`, not directly manipulate the chess.Board.
3. Fixing the `wx.ID_ANY` bind pattern protects every new menu item added in subsequent phases (PGN save, FEN save, clock controls, theme toggle, scale slider, settings).

---

## Sources

**HIGH confidence (Context7 / official docs):**
- python-chess 1.11.2 PGN documentation — variations, NAGs, comments, multi-game, error handling: https://python-chess.readthedocs.io/en/latest/pgn.html and Context7 `/niklasf/python-chess`
- python-chess 1.11.2 Core / FEN — castling, en passant, `Board.is_valid()`, `Board.status()`: https://python-chess.readthedocs.io/en/latest/core.html
- wxPython 4.2.x `wx.Timer` precision documentation: https://docs.wxpython.org/wx.Timer.html
- wxPython 4.2.x `wx.KeyEvent` — non-US layout / dead key behavior: https://docs.wxpython.org/wx.KeyEvent.html
- wxPyWiki `CharacterCodesAndKeyboards`: https://wiki.wxpython.org/CharacterCodesAndKeyboards
- NVDA 2025.x user guide — modifier keys (Insert, CapsLock), audio ducking limitations: https://download.nvaccess.org/documentation/userGuide.html
- Existing repo `.planning/codebase/CONCERNS.md` (8 bugs, 6 tech-debt items, fragile-area annotations)

**MEDIUM confidence (multiple sources agree):**
- Atomic file write pattern (write tmp → fsync → os.replace), with macOS `F_FULLFSYNC` caveat: https://blog.elijahlopez.ca/posts/data-corruption-atomic-writing/, https://dev.to/constanta/crash-safe-json-at-scale-atomic-writes-recovery-without-a-db-3aic, https://github.com/untitaker/python-atomicwrites
- WCAG 2.1 contrast requirements (4.5:1 text / 3:1 UI components): https://webaim.org/articles/contrast/, https://www.section508.gov/create/making-color-usage-accessible/
- Cross-platform Python audio — pygame.mixer / sounddevice / simpleaudio tradeoffs, PipeWire compatibility: https://realpython.com/playing-and-recording-sound-python/, https://github.com/henrikschnor/pasimple

**LOW confidence (single source / inference):**
- Specific cold-start latency numbers for PipeWire (200-400 ms) — observed in mailing-list reports, not benchmarked in this research; verify on target hardware
- NVDA / JAWS reserved-shortcut exhaustive list — only the modifier-key cases are explicitly documented; full list is empirical and changes between screen-reader versions
- Recommendation to use `pygame.mixer` over `sounddevice` for v1 — based on cross-platform coverage breadth; revisit during the sound phase with a small spike on each library

---
*Pitfalls research for: accessible desktop chess GUI v1*
*Researched: 2026-04-27*

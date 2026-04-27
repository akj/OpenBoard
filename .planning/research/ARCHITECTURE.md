# Architecture Research

**Domain:** Accessible desktop chess GUI (wxPython MVC + blinker signals + asyncio engine)
**Researched:** 2026-04-27
**Confidence:** HIGH (verified against existing code and Context7-current wxPython docs)

This is a **subsequent-milestone** integration study, not a greenfield architecture. Existing constraints (`.planning/codebase/ARCHITECTURE.md`) are taken as given. The question this answers is: **for each v1 capability, where does it live, what signals does it emit, and on which thread does it run** — without replicating the anti-patterns flagged in `CONCERNS.md`.

---

## Standard Architecture (recap, target end-state for v1)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         View Layer (wxPython, main thread)               │
│                                                                          │
│  ChessFrame (menus, dialogs, key dispatch, status bar)                   │
│   ├── BoardPanel              (renders board; subscribes board_updated)  │
│   ├── ClockPanel       NEW    (renders both clocks; subscribes tick)     │
│   ├── KeyRebindDialog  NEW    (mutates KeyboardConfig + persists)        │
│   ├── ThemeDialog      NEW    (mutates ThemeSettings)                    │
│   └── SoundService     NEW    (subscribes to model+controller signals;   │
│                                plays SFX on dedicated mixer thread)      │
└─────────────┬────────────────────────────────────────────────────────────┘
              │ blinker signals (subscribe), wx events (bind)
              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    Controller Layer (main thread)                        │
│  ChessController                                                         │
│   - Existing: navigation, selection, replay, announcement formatting     │
│   - NEW: AnnounceFilter (per-event verbosity gate)        wraps announce │
│   - NEW: clock signal forwarding (Game.clock_tick → status_changed?)     │
│   Signals OUT (existing): board_updated, square_focused, selection_      │
│             changed, announce, status_changed, hint_ready,               │
│             computer_thinking                                            │
│   Signals OUT (new): clock_tick, low_time_warning, flag_fall             │
│             (forwarded from Game.clock for view consumption)             │
└─────┬───────────────────────────────────────────────────────────────┬────┘
      │                                                               │
      ▼                                                               ▼
┌──────────────────────────────────┐   ┌──────────────────────────────────┐
│     Model Layer (main thread)    │   │   Engine Layer (asyncio bg thr.) │
│  Game (orchestrator)             │   │   EngineAdapter                  │
│   - NEW: clock: Clock | None     │   │   (unchanged for v1)             │
│   - NEW: serializer: GameSerial. │   │                                  │
│  BoardState (existing, untouched)│   │                                  │
│  Clock                  NEW      │   │                                  │
│   Signals: tick, low_time,       │   │                                  │
│            flag_fall, paused,    │   │                                  │
│            time_control_changed  │   │                                  │
│  GameSerializer         NEW      │   │                                  │
│   - save_pgn / load_pgn          │   │                                  │
│   - save_fen / load_fen          │   │                                  │
│   - autosave / restore_autosave  │   │                                  │
│  OpeningBook (existing)          │   │                                  │
└──────────────────────────────────┘   └──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          Config Layer                                    │
│  Settings (existing)                                                     │
│   ├── UISettings        (existing)                                       │
│   ├── EngineSettings    (existing)                                       │
│   ├── SoundSettings     NEW                                              │
│   ├── ClockSettings     NEW                                              │
│   ├── ThemeSettings     NEW                                              │
│   └── VerbositySettings NEW                                              │
│  Persisted via JSON in user_data_dir (platformdirs) — see security note  │
│                                                                          │
│  GameKeyboardConfig (existing) + KeyRebinder NEW                         │
│   keyboard_config.json moves to user_data_dir on first run               │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities (additions)

| Component | Layer | Owns | File (proposed) |
|-----------|-------|------|-----------------|
| `Clock` | Model | Per-side time, time control, increments, pause/resume; emits `tick`, `low_time`, `flag_fall` | `openboard/models/clock.py` |
| `TimeControl` | Model | Dataclass: base_time_ms, increment_ms, kind (sudden_death / fischer / bronstein) | `openboard/models/clock.py` |
| `GameSerializer` | Model | PGN export (with headers + clock annotations), PGN import (delegates to BoardState), FEN round-trip, autosave/restore | `openboard/models/game_serializer.py` |
| `SoundService` | View (top-level service, but NOT a wx widget) | Maps signals → SFX, owns `pygame.mixer` lifecycle, respects `SoundSettings` | `openboard/views/sound_service.py` |
| `ClockPanel` | View | Renders both clocks, subscribes `tick` via `wx.CallAfter` | `openboard/views/clock_panel.py` |
| `ThemeManager` | View | Resolves `ThemeSettings` → palette + piece glyphs/scale; mutated by ThemeDialog | `openboard/views/theme_manager.py` |
| `AnnounceFilter` | Controller | Wraps `announce.send` with per-event opt-in/out from `VerbositySettings` | `openboard/controllers/announce_filter.py` |
| `KeyRebindDialog` | View | UI for mutating `GameKeyboardConfig` and persisting to disk | `openboard/views/key_rebind_dialog.py` |
| `SoundSettings`, `ClockSettings`, `ThemeSettings`, `VerbositySettings` | Config | Dataclass fields on `Settings` | `openboard/config/settings.py` |

---

## Per-Capability Integration Decisions

The roadmap consumer needs the **decision**, not a buffet. Each subsection below resolves one question.

### 1. Clock Model — Where it Lives & How Ticks Are Emitted

**Decision:** `Clock` is a new model class in `openboard/models/clock.py`. It is composed by `Game` (`game.clock: Clock`). Ticks are driven by a **`wx.Timer` owned by `ChessFrame`**, NOT by `asyncio` and NOT by a Python `threading.Timer`. The frame ticks the clock; the clock decides whether internal state actually changed and emits at most one `tick` signal per wall-clock second of remaining time change.

**Why `wx.Timer` and not asyncio:**
- Asyncio in this codebase is reserved for the engine background thread. Adding a second asyncio context (or coroutines on the main thread) breaks the single-asyncio-loop assumption baked into `WxCallbackExecutor`.
- `wx.Timer` is the canonical wxPython periodic-timer mechanism: `EVT_TIMER` fires on the main thread, no marshalling needed, no thread-safety concerns. (Verified against current wxPython/Phoenix docs via Context7.)
- `threading.Timer` would require `wx.CallAfter` for every tick — pure overhead vs. `wx.Timer`.

**Why "tick the clock" pattern rather than self-ticking clock:**
- The model layer must remain wx-free (`Clock` should be unit-testable without wx). Making `Clock` own its own timer would couple it to wx.
- The frame holds the `wx.Timer`; on each `EVT_TIMER` it calls `controller.tick_clock(monotonic_ns)` which calls `game.clock.tick(monotonic_ns)`.
- `Clock.tick(now_ns)` is pure: it computes elapsed time since last tick using `time.monotonic_ns()` (passed in by caller for testability), decrements the active side's clock, and decides whether to emit signals.

**Cadence and signal frequency:**
- `wx.Timer.Start(100)` — 100 ms tick interval. This is short enough that flag-fall is detected within 100 ms of zero; long enough that wx is not stressed.
- `Clock.tick()` only emits the `tick` signal when the *displayed* time changes (i.e., the integer seconds remaining for the active side rolls over). At 100 ms timer cadence with whole-second display, that's 1 emit/sec, not 10. **This is the answer to "how do we avoid spamming signals every 100 ms."**
- `Clock.tick()` emits `low_time` exactly once when the active side's remaining time crosses the `low_time_threshold_ms` boundary (configured in `ClockSettings`, default 30 s).
- `Clock.tick()` emits `flag_fall` exactly once when remaining time hits zero, then transitions to a stopped/flagged state.

**Lifecycle:**
- `wx.Timer` is created in `ChessFrame.__init__` and bound there. It is `Start()`ed when a game begins and `Stop()`ped at game-over, on pause, on dialog modality (e.g., during PGN load), and at frame close. Forgetting to `Stop()` leaks; this is enforced by tying lifecycle to the existing `_on_status_changed` "game over" path.
- `Clock` is replaced (not reused) on `Game.new_game()` — same pattern as `BoardState`, AND we apply the **fix from the `move_undone` bug** (see Anti-Pattern 1) by having `Game` forward `clock.tick`/`low_time`/`flag_fall` through its own signals. The controller subscribes to `Game.clock_tick`, never to `game.clock.tick` directly.

**Signals emitted:**

| Signal (on `Clock`) | Forwarded as (on `Game`) | Args | Frequency |
|---------------------|--------------------------|------|-----------|
| `tick` | `clock_tick` | `white_ms: int`, `black_ms: int`, `active_color: chess.Color` | ~1 Hz while active |
| `low_time` | `low_time_warning` | `color: chess.Color`, `remaining_ms: int` | Once per crossing |
| `flag_fall` | `flag_fall` | `color: chess.Color` | Once per game |
| `paused` | `clock_paused` | `paused: bool` | On user toggle |
| `time_control_changed` | `time_control_changed` | `time_control: TimeControl \| None` | On config change / clocks-off |

**Threading:**
- All signal emissions are on the wx main thread (because `wx.Timer` fires there).
- View subscribers (ClockPanel, SoundService) need no `wx.CallAfter` for clock signals.

**File placement:**
- `openboard/models/clock.py` — `Clock`, `TimeControl`, `TimeControlKind` enum.
- Tests: `tests/test_clock.py` (pure unit tests using injected `now_ns`, no wx required).

---

### 2. Sound Subsystem — Service vs. Distributed Calls

**Decision:** **Single `SoundService` singleton-style listener** instantiated in `main()` after `Settings` is loaded but before `ChessFrame.Show()`. It subscribes to existing model/controller signals plus the new clock signals. Distributed `play_sound()` calls scattered through controllers are rejected.

**Why a service, not distributed calls:**
- *Decoupling:* the controller has no business knowing what a "capture" sounds like. It already announces "captures pawn"; the sound layer can listen for the same event and play a capture SFX with zero controller code change.
- *Testability:* unit tests for `ChessController` already swallow `announce.send` via signal mocking. Adding `play_sound()` calls inside controller methods would force every controller test to also mock the sound mixer.
- *Single off-switch:* `SoundSettings.enabled = False` instantly mutes every event. Distributed calls would each need to check the setting.
- *Per-category volume:* `SoundSettings.volumes[category]` flows through one place.
- *Future-proof:* v2/v3/v4 features (analysis, puzzles, online) emit signals; the sound service auto-extends by subscribing.

**Library choice: `pygame.mixer`** (verified MEDIUM confidence — pygame.mixer is the consensus non-blocking cross-platform option for wxPython per discuss.wxpython.org and Python audio guides; alternatives are `playsound3` or `simpleaudio`).

| Library | Non-blocking | wxPython-compatible | Channels | Volume per channel | Verdict |
|---------|-------------|---------------------|----------|--------------------|---------|
| `pygame.mixer` | Yes (default) | Yes (used widely) | Yes | Yes | **Choose** |
| `playsound3` | Yes (since 3.0) | Yes | Limited | No per-sound volume control | Acceptable backup |
| `simpleaudio` | Yes | Yes, but unmaintained since 2020 | Limited | No | Reject |
| `winsound` (stdlib) | Partial | Windows-only | No | No | Reject (cross-platform requirement) |

**Threading:**
- `pygame.mixer` plays on its own internal thread; from the main thread we just call `Sound.play()` and return immediately.
- `pygame.mixer.init(buffer=512)` for sub-100 ms latency (per pygame guidance for interactive apps).
- `SoundService.__init__` calls `pygame.mixer.init()` lazily on first sound played, so import-time startup remains fast and tests that don't touch sound don't initialize the mixer.

**Subscription map (one row per signal → SFX):**

| Signal | Sender | Sound Category | File |
|--------|--------|----------------|------|
| `Game.move_made` (own move, by checking `board.turn` flipped to non-human) | `Game` | `move_self` | `assets/sounds/move-self.ogg` |
| `Game.move_made` (opponent move) | `Game` | `move_opponent` | `move-opponent.ogg` |
| `Game.move_made` (capture detected via `old_board.is_capture(move)`) | `Game` | `capture` | `capture.ogg` |
| `Game.move_made` (castling via `old_board.is_castling(move)`) | `Game` | `castle` | `castle.ogg` |
| `Game.status_changed` ("Checkmate" / "Stalemate") | `Game` | `game_end` | `game-end.ogg` |
| `BoardState.status_changed` (in-check) — needs new derived signal or check inside SoundService | derived | `check` | `check.ogg` |
| `Clock.tick` while active side `<= low_time_threshold` | `Game.clock` | `tick_low_time` | `tick.ogg` |
| `Clock.flag_fall` | `Game.clock` | `flag_fall` | `flag-fall.ogg` |
| `Game.computer_thinking(thinking=True)` | `ChessController` | `turn_alert` (optional) | `turn-alert.ogg` |

**Capture/castle detection:** SoundService receives `move_made` with the move and inspects `game.board_state.board` — but **this would replicate the `controller.game.board_state.board` anti-pattern from CONCERNS.md.** Resolution: extend `Game.move_made` to carry `old_board` and a `move_kind` flag (one of `MoveKind.QUIET`, `CAPTURE`, `CASTLE`, `EN_PASSANT`, `PROMOTION`, `CHECK`), so the sound service receives all needed context as signal args. Computing this in `Game._on_board_move` is cheap (`old_board.is_capture(move)`) and removes the need for any subscriber to peek at internal model state. **This is a load-bearing refactor — it also fixes the existing `_pending_old_board` shared-mutable-state fragility (CONCERNS.md "Fragile Areas").**

**File placement:**
- `openboard/views/sound_service.py` — `SoundService` class. Lives in `views/` because it's a UI concern (output to the user), not a model concern, and because `pygame` is a presentation-tier dependency we don't want infecting models.
- `assets/sounds/` — committed sound assets.
- Tests: `tests/test_sound_service.py` with `pygame.mixer` mocked.

---

### 3. PGN / FEN Persistence — Service vs. Methods on `Game` & Auto-Save Trigger

**Decision A (separation):** A new **`GameSerializer` service class** in `openboard/models/game_serializer.py`. `Game` exposes a thin facade (`game.save_pgn(path)`, `game.load_pgn(path)`, etc.) that delegates to `GameSerializer`, but the serialization logic does not live on `Game` itself.

**Why a separate service:**
- `Game` is already a 460-line orchestrator that the codebase audit flagged for duplication (request_computer_move sync vs async). Adding ~150 lines of PGN/FEN/autosave logic worsens that.
- PGN headers (player names, time control, result, date), clock-time annotations (`{ [%clk 1:23:45] }`), and autosave file naming/rotation are independent concerns from move orchestration.
- Easier to unit-test in isolation (no `EngineAdapter`, no `OpeningBook` needed for serialization tests).
- Easier to replace later (e.g., when v2's saved-game library wants a different storage backend, only `GameSerializer` changes).

**Decision B (autosave trigger):** **Signal-driven, debounced.** Subscribe to `Game.move_made` and `Game.status_changed`. On each event, schedule a single-shot `wx.CallLater(500, self._do_autosave)`, cancelling any pending one. This ensures:
- A burst of moves (e.g., PGN replay stepping through 80 plies) coalesces into one save.
- Save fires within ~500 ms of game-state quiescence.
- No periodic `wx.Timer` polling: zero work when nothing changes (matches the codebase's signal-driven philosophy).

**Why not periodic `wx.Timer`:**
- Saves disk every N seconds even when idle — wasteful, especially on laptops.
- Doesn't capture the most recent move at app close — the post-move save does.
- The clock already uses `wx.Timer`; adding a second one for autosave is redundant when signals already cover the trigger.

**Crash recovery:**
- `GameSerializer.autosave_path()` returns `platformdirs.user_state_dir("openboard") / "autosave.pgn"`.
- On `main()` startup, after `Game` is constructed, check for autosave file. If found, prompt (modal: "Resume previous game? Yes / Discard / Cancel") and on Yes, call `game.load_pgn(autosave_path)`. This is wired in `ChessFrame.OnInit`-equivalent path.
- On clean shutdown (game-over reached, or user "New Game"), delete the autosave file.

**FEN entry point:**
- `BoardState.load_fen` already exists. `Game.load_fen_position(fen)` is added to `Game` as a thin wrapper that resets `Clock` and clears any replay state (otherwise loading FEN into a replay-mode game leaves `_in_replay = True` — currently `controller.load_fen` correctly resets `_in_replay`, so the controller-side fix is already in place).
- A "Set Up Position…" dialog (FEN entry box) lives in `views/game_dialogs.py`.

**File placement:**
- `openboard/models/game_serializer.py` — `GameSerializer` class.
- `openboard/views/game_dialogs.py` — add `FenEntryDialog`, `SaveAsDialog` (use `wx.FileDialog` for file picking; only the FEN entry needs a custom dialog).
- Tests: `tests/test_game_serializer.py` covering: PGN headers correctness, clock-time annotation round-trip, autosave path resolution, autosave debounce timing (mock `wx.CallLater`).

**Headers to emit (PGN export):**
- `Event`, `Site`, `Date`, `Round`, `White`, `Black`, `Result`, `TimeControl` (PGN spec format: `40/9000:300` for 40/90+5, `300+5` for 5+5, `-` for clocks-off), and python-chess auto-emits `FEN` if non-standard start position.

---

### 4. Settings Extension — Adding New Sections to the Singleton

**Decision:** Extend `Settings` by adding new dataclass fields (not by replacing the singleton mechanism). Add `SoundSettings`, `ClockSettings`, `ThemeSettings`, `VerbositySettings` as siblings of `UISettings` and `EngineSettings`. Persist the entire `Settings` to JSON in `platformdirs.user_config_dir("openboard") / "settings.json"`.

**The singleton pattern survives untouched:**
```python
@dataclass
class Settings:
    ui: UISettings = field(default_factory=UISettings)
    engine: EngineSettings = field(default_factory=EngineSettings)
    sound: SoundSettings = field(default_factory=SoundSettings)        # NEW
    clock: ClockSettings = field(default_factory=ClockSettings)        # NEW
    theme: ThemeSettings = field(default_factory=ThemeSettings)        # NEW
    verbosity: VerbositySettings = field(default_factory=VerbositySettings)  # NEW
```

`get_settings()` and `set_settings()` are unchanged. The only structural change is **adding load/save methods**:

```python
def save(self, path: Path) -> None: ...
@classmethod
def load(cls, path: Path) -> "Settings": ...
```

**Serialization:** Use `dataclasses.asdict(self)` for write, manual reconstruction for read (because `Path` and platform defaults need re-resolution). This sidesteps adding pydantic to settings (pydantic is already used for `KeyBinding`; using both styles is acceptable per existing conventions, but for `Settings` simple JSON via `asdict` is sufficient).

**Migration on schema change:** Settings file includes a top-level `"version": 1`. On load, missing keys are filled from defaults (so a v1.0 file loaded by v1.1 code adds the new fields silently). Keys present in the file but absent in the dataclass are warned-and-ignored (logger.warning). This is robust enough for v1; full migrations land in v2 if schemas diverge.

**Mutability story:**
- During app run, dialogs (Sound dialog, Clock setup dialog, Theme dialog) read from `get_settings()` and mutate fields directly. On dialog OK, `save()` is called explicitly.
- Live-reactive surfaces (e.g., changing piece scale immediately re-renders the board): the dialog emits a module-level blinker named signal `settings_changed.send(category="theme")` after mutation. Views subscribe and refresh.
- This module-level signal is the **one new exception to the "instance signals only" rule** in the codebase. Justification: settings are themselves a singleton, so an instance-attached signal would require holding the `Settings` instance everywhere. The existing `StockfishManager` already uses module-level named signals — same precedent.

**File placement:**
- `openboard/config/settings.py` (existing) — extend.
- `openboard/config/__init__.py` — export `settings_changed` signal.

**Existing tech-debt fix bundled here:** `EngineSettings.engines_dir` defaults to `Path.cwd() / "engines"` (CONCERNS.md "Security Considerations"). This must be migrated to `platformdirs.user_data_dir("openboard") / "engines"` as part of v1 — same migration also fixes the broader "config resolved from cwd" issue. **Roadmap implication:** put `platformdirs` migration in an early phase because it changes file paths for *engines, settings, autosave, and keyboard config* simultaneously.

---

### 5. In-App Key Rebinding UI — Hot-Reload Pattern

**Decision:** **Reload-on-save**, mediated through a `KeyRebinder` helper. When the dialog is OK'd:

1. `KeyRebindDialog` constructs a new `GameKeyboardConfig` instance from the dialog state.
2. Validates: no duplicate `(key, modifier)` pairs (unless the second binding is `enabled=False`).
3. Persists to `platformdirs.user_config_dir / "keyboard_config.json"`.
4. Calls `chess_frame.replace_keyboard_config(new_config)` which:
   - Stores the new config on `ChessFrame`.
   - Rebuilds `KeyboardCommandHandler` from the new config (existing factory `_create_keyboard_handler()` is reused).
   - No need to unbind `EVT_CHAR_HOOK` because it's bound to the frame, not to specific keys — the dispatch table inside `KeyboardCommandHandler` is what changes.

**Why reload-on-save (not live-mutate the existing instance):**
- `GameKeyboardConfig` is a pydantic dataclass — mutating fields in place can put it in a half-validated state if the user cancels mid-edit. Building a new instance gives transactional semantics.
- The existing `find_binding` lookup is fast (linear scan of <30 bindings); rebuilding the dispatch dict is O(n) and runs once per save, not per key press.
- Round-trip safety: the on-disk JSON file is the source of truth. A successful save means the file matches the live config; a failed save (validation rejected) leaves the live config unchanged.

**Cross-platform key capture:** the dialog uses a "press a key" wx capture pattern — it binds `EVT_KEY_DOWN` on a single `wx.TextCtrl` substitute, reads the `wx.KeyEvent`, and converts to the JSON-format `key` + `modifiers` strings. This keeps platform differences (Cmd vs. Ctrl) in one place inside the dialog's key-capture helper.

**File placement:**
- `openboard/views/key_rebind_dialog.py` — `KeyRebindDialog`.
- `openboard/config/keyboard_config.py` — extend with `KeyRebinder` helper (validation + JSON write). Existing `load_keyboard_config_from_json` already exists; pair it with `save_keyboard_config_to_json`.
- Tests: `tests/test_keyboard_config.py` (extend) — assert validation rejects duplicates, assert round-trip JSON preserves bindings.

**Existing tech-debt fix bundled here:** the `"&Book Hint\tB"` accelerator double-bind from CONCERNS.md must be removed before this dialog ships, otherwise users rebinding "B" will see the menu accelerator survive their rebind.

---

### 6. Verbosity Tiers — Where the Per-Event Filter Sits

**Decision:** **Wrap `announce.send` in a controller-internal `AnnounceFilter`.** Specifically:

- `ChessController.__init__` does `self.announce = AnnounceFilter(Signal(), settings.verbosity)` (wrapping a real Signal in a thin filter).
- Or, more simply: keep `announce` as a plain `Signal`, but route every `self.announce.send(...)` call through `self._announce(category, text)` which checks `verbosity_settings.is_enabled(category)` and only forwards if enabled.

The **second form is preferred** because it keeps the public `announce` signal contract intact (downstream view subscribers don't change), and the filter runs entirely inside the controller.

**Why in the controller, not in the view:**
- The controller is the layer that *categorizes* announcements (it knows whether a given `announce.send` call is a "move announcement" vs. a "navigation announcement" vs. a "hint" vs. a "low-time warning"). Moving the filter to `ChessFrame.on_announce` would force the view to re-derive the category from the announcement string — fragile.
- All `self.announce.send(...)` call sites in `ChessController` already exist; the refactor is mechanical: replace each with `self._announce(category, text)` where `category` is one of a new `AnnounceCategory` enum (`MOVE`, `NAV_SQUARE`, `NAV_PIECE`, `HINT`, `LOW_TIME`, `STATUS`, `BOOK`, `ERROR`).

**Why not in `ChessFrame.on_announce`:**
- View doesn't know category.
- Spreading filter logic across layers couples them.

**Why not a wrapper around the `Signal` class itself:**
- Possible but fragile. Subscribers passing through `signal.connect(...)` see the wrapped signal; tests connecting to the raw signal still see all events. The "route through a method" approach is more honest about what's filtering.

**`VerbositySettings` shape:**
```python
@dataclass
class VerbositySettings:
    """Per-event opt-in/out filters. Each defaults to True (preserves current behavior)."""
    moves: bool = True
    navigation_squares: bool = True
    navigation_pieces: bool = True
    hints: bool = True
    low_time_warnings: bool = True
    status_changes: bool = True
    book_messages: bool = True
    errors: bool = True  # always-on in practice; users can't silence errors via UI
```

The existing global `announce_mode` (`brief` / `verbose`) **stays** — it controls *formatting*, not *whether to emit*. Verbosity tiers control *whether to emit at all*. They are orthogonal.

**File placement:**
- `openboard/controllers/chess_controller.py` — add `AnnounceCategory` enum and `_announce(category, text)` helper. Refactor every existing `self.announce.send(self, text=...)` into `self._announce(AnnounceCategory.X, text)`.
- `openboard/config/settings.py` — add `VerbositySettings` dataclass.

---

## Cross-Cutting: Signal Naming Consistency

The codebase convention (per CONVENTIONS.md and existing code) is:
- Snake-case instance attributes on the owning class.
- Action-as-verb-or-noun-phrase: `move_made`, `hint_ready`, `computer_move_ready`, `board_updated`, `square_focused`, `selection_changed`, `announce`, `status_changed`, `computer_thinking`.

**New signal names follow the same pattern:**

| Owner | Signal | Args |
|-------|--------|------|
| `Clock` | `tick` | `white_ms`, `black_ms`, `active_color` |
| `Clock` | `low_time` | `color`, `remaining_ms` |
| `Clock` | `flag_fall` | `color` |
| `Clock` | `paused` | `paused: bool` |
| `Clock` | `time_control_changed` | `time_control` |
| `Game` (forwarders) | `clock_tick`, `low_time_warning`, `flag_fall`, `clock_paused`, `time_control_changed` | (same) |
| `Game` | `move_made` *(extended)* | `move`, `old_board`, `move_kind: MoveKind` |
| `module-level` | `settings_changed` | `category: str` |

**Anti-pattern guarded against:** controller subscribes to `Game.clock_tick`, **not** `game.clock.tick`. This avoids the same class of bug as the `move_undone` regression (CONCERNS.md "Known Bugs"): `Game.new_game()` replaces the clock, and the forwarding pattern means subscribers don't have stale references.

---

## Threading Boundary Cheat-Sheet

| Concern | Thread | Marshal Required? |
|---------|--------|-------------------|
| User keypress | wx main | — |
| `controller.navigate()` / `select()` / `apply_move()` | wx main | — |
| `BoardState.make_move` → `move_made` signal emit | wx main | — |
| All controller signal subscribers (`_on_model_move`, `_on_status_changed`) | wx main | — |
| `wx.Timer` `EVT_TIMER` for clock tick | wx main | — |
| `Clock.tick()` | wx main | — |
| `Clock.tick`/`low_time`/`flag_fall` signal emit | wx main | — |
| `SoundService.on_move_made` (subscriber) | wx main | — |
| `pygame.mixer.Sound.play()` | wx main (returns immediately; pygame plays on its mixer thread) | — |
| `EngineAdapter.get_best_move_async` callback (engine background thread) | bg → main via `WxCallbackExecutor` | **YES — `wx.CallAfter`** (already in place) |
| Autosave I/O on `wx.CallLater(500, ...)` | wx main | — (synchronous file write; PGN files are <100 KB) |
| Settings JSON write | wx main | — |
| `keyboard_config.json` write on rebind | wx main | — |

**No new background threads are introduced.** This is intentional: the existing single-asyncio-loop, single-mixer-thread, single-main-thread model is sufficient and well-understood. Adding more threads would make `WxCallbackExecutor` insufficient and force broader thread-safety auditing.

---

## Build-Order Implications (for Roadmap Phase Sequencing)

The roadmap consumer needs to know what depends on what. Order from lowest to highest dependency:

**Tier 0 — Tech-debt prerequisites that unblock clean v1 work:**
1. **Fix `move_undone` signal-disconnection bug** (CONCERNS.md). Fix forces forwarding pattern on `Game`, which is the same pattern Clock signals will use. Doing it once, correctly, avoids re-doing it twice.
2. **Replace `_pending_old_board` shared-mutable-state with `move_made(old_board=...)` parameter** (CONCERNS.md "Fragile Areas"). Required before SoundService can detect captures without peeking at `controller.game.board_state.board`.
3. **Fix `_navigate_to_position` model-bypass bug** and `wx.ID_ANY` PGN-binding bug (CONCERNS.md "Known Bugs"). PGN save/load expansion will touch `on_load_pgn`; cleaning up the binding first avoids regressions.
4. **Migrate `engines_dir`, `config.json`, and `keyboard_config.json` to `platformdirs`-resolved paths.** Required before any settings persistence work (SoundSettings, ClockSettings, ThemeSettings) — otherwise these settings land in `cwd` too.

**Tier 1 — Foundational v1 capabilities (no inter-dependencies between them):**
5. **`GameSerializer` — PGN/FEN save/load.** Depends only on Tier 0. No clock dependency yet (PGN export of clock annotations is added when Clock lands; pre-Clock the PGN just lacks `[%clk]` tags).
6. **Settings extension (`SoundSettings`, `ClockSettings`, `ThemeSettings`, `VerbositySettings`) + JSON persistence.** Depends only on Tier 0.

**Tier 2 — Capabilities that consume Tier 1:**
7. **Clock model + ClockPanel.** Needs `ClockSettings` (Tier 1) for time-control defaults and `low_time_threshold_ms`.
8. **Verbosity tiers (`AnnounceFilter`).** Needs `VerbositySettings` (Tier 1).
9. **High-contrast theme + piece scale.** Needs `ThemeSettings` (Tier 1).
10. **Key-rebinding dialog.** Needs Tier 0 keyboard-config-path migration.

**Tier 3 — Capabilities that consume Tier 2:**
11. **Sound service.** Needs *all* its signal sources to exist: move/check signals (already present, refactored in Tier 0), clock signals (Tier 2), and `SoundSettings` (Tier 1). Building it last means its subscribe map is final on first write.
12. **Autosave wiring.** Needs `GameSerializer` (Tier 1) and clock state (Tier 2 — clock ms must round-trip through PGN annotations, otherwise crash recovery loses time).

This ordering means: **Tier 0 must precede everything**, **Tier 1 can run in parallel internally**, **Tier 2 has clock and verbosity as siblings**, and **Tier 3 is the final integration tier**.

---

## Anti-Patterns to Guard Against

### Anti-Pattern 1: Subscribing directly to `game.clock.tick`

**What people do:** `game.clock.tick.connect(handler)` from the controller or view.
**Why it's wrong:** `Game.new_game()` replaces the `Clock` instance. Direct subscriptions retain a reference to the old, discarded clock — same class of bug as the `move_undone` regression. The handler is silently never called again.
**Do this instead:** Subscribe to `Game.clock_tick` (a forwarded `Signal()` on `Game` that re-emits `clock.tick`). `Game.new_game()` re-wires the forwarder when it replaces the clock, transparently to subscribers.

### Anti-Pattern 2: Putting `pygame.mixer` calls inside the controller

**What people do:** Adding `mixer.Sound("capture.ogg").play()` inside `ChessController._on_model_move`.
**Why it's wrong:** Couples controller to a presentation library; breaks unit tests that don't have audio; bypasses the centralized `SoundSettings` toggle.
**Do this instead:** Emit signals only; let `SoundService` (a view-layer subscriber) own all audio.

### Anti-Pattern 3: `wx.Timer` inside the model

**What people do:** Making `Clock` own a `wx.Timer` directly.
**Why it's wrong:** Couples model to wxPython; breaks unit tests that import `Clock` without `wx.App`. Violates "models import engine, no further" rule.
**Do this instead:** `wx.Timer` lives in `ChessFrame` (view); on `EVT_TIMER` it calls `controller.tick_clock()`; controller calls `game.clock.tick(time.monotonic_ns())`. `Clock` is pure-Python, fully unit-testable.

### Anti-Pattern 4: Periodic `wx.Timer` for autosave

**What people do:** `wx.Timer` firing every 30 s to write the PGN.
**Why it's wrong:** Wastes I/O when nothing changed; misses last-second moves at app close; redundant with the existing event-driven model.
**Do this instead:** `wx.CallLater` debounce on `move_made` and `status_changed`. Saves only when state changes, coalesces bursts, captures the latest move.

### Anti-Pattern 5: Per-call `if settings.verbosity.X:` checks scattered through the controller

**What people do:** `if get_settings().verbosity.moves: self.announce.send(self, text=...)` at 20 call sites.
**Why it's wrong:** Logic duplication; missing one site means that one announcement always fires regardless of setting.
**Do this instead:** Single `_announce(category, text)` method that consults `VerbositySettings` once.

### Anti-Pattern 6: Live-mutating `GameKeyboardConfig` from the rebind dialog

**What people do:** Directly editing `chess_frame.keyboard_config.bindings[i].key = ...` from the dialog OK handler.
**Why it's wrong:** Half-validated state if the user cancels; pydantic validation is per-instance, not per-mutation.
**Do this instead:** Build a fresh `GameKeyboardConfig` from the dialog state, validate it (pydantic does this on construction), persist to disk, then atomically swap the frame's config and rebuild the command handler.

### Anti-Pattern 7: Subscribing to clock signals from a thread other than wx main

**What people do:** Future audio worker threads or analysis threads adding their own clock subscriptions.
**Why it's wrong:** blinker's signal dispatch is synchronous in the emitting thread. A subscriber wanting to do work on a different thread must do its own dispatch, and the emitter expects subscribers not to block.
**Do this instead:** Subscribers stay on the main thread (since clock signals are emitted there). If a subscriber needs to do non-trivial work, it submits to a worker — but `pygame.mixer.Sound.play()` is already non-blocking, so this rarely arises in v1.

---

## Integration Points

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|--------------|-------|
| View → Controller | direct call (frame holds controller ref) | unchanged |
| Controller → Model | direct call | unchanged |
| Model → Controller | blinker `Signal` (instance) | extended with `Game.clock_*` forwarders |
| Engine → Model | callback marshalled via `WxCallbackExecutor` | unchanged |
| Settings dialogs → Settings | direct mutation + `settings_changed` named signal | NEW signal |
| `wx.Timer` (view) → Clock (model) | indirect via `controller.tick_clock(now_ns)` | NEW |
| `SoundService` ← signals | subscribe to `Game`, `Clock`-via-`Game`, and `ChessController` signals | NEW |
| `GameSerializer` ↔ disk | synchronous file I/O on main thread | NEW; PGN files small enough for sync I/O |
| `KeyRebindDialog` → keyboard config | reload-on-save via `save_keyboard_config_to_json` then frame swap | NEW |

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| `pygame.mixer` (NEW) | `mixer.init(buffer=512)` lazy, `Sound(path).play()` non-blocking | Ensure `pygame` is installed; `pygame-ce` is a maintained fork if upstream `pygame` causes wheel issues on any platform — both expose the same `mixer` API. |
| `platformdirs` (NEW) | `user_data_dir`, `user_config_dir`, `user_state_dir` for engines, settings, autosave | Already de facto Python standard for user-data path resolution. |
| `python-chess.pgn` (existing, extended use) | `chess.pgn.Game.from_board(board)` for export, `chess.pgn.read_game(stream)` for import | Use the `[%clk H:MM:SS]` move-comment format from the PGN spec for clock annotations. |

---

## Scaling Considerations (within v1 scope)

This is a single-user desktop app, so traditional scaling doesn't apply, but the v1 work has internal scaling concerns:

| Concern | Threshold | Mitigation |
|---------|-----------|------------|
| Signal subscriber count | 5–10 subscribers per signal | Fine; blinker dispatches O(n) which is trivial here. |
| Clock tick frequency | 100 ms timer × ~3600 s/game = 36k ticks/game | `Clock.tick` short-circuits when integer-second display unchanged; only ~1 emit/sec actually fires through subscribers. |
| Autosave file size | <50 KB per game | Synchronous write on main thread is acceptable. Above 1 MB consider async via a worker. |
| `pygame.mixer` channels | 8 default channels | Plenty for chess (rarely more than 2 overlapping sounds). |
| Settings JSON size | <5 KB | Atomic-write (`tmp + rename`) is adequate; no fsync needed. |
| PGN move-list rendering in dialog | 200+ plies | Existing dialog is fine; if v2 saved-game library scales this, paginate. Out of scope for v1. |

---

## Sources

- `/home/akj/projects/openboard/.planning/codebase/ARCHITECTURE.md` — existing MVC + signal architecture, threading model (HIGH confidence: this is the authoritative project doc).
- `/home/akj/projects/openboard/.planning/codebase/CONCERNS.md` — `move_undone` bug, `_pending_old_board` fragility, `_navigate_to_position` bypass, `wx.ID_ANY` bind bug, `engines_dir` cwd-dependency. All bundled into Tier 0 of the build order (HIGH confidence: source code references with line numbers).
- `/home/akj/projects/openboard/openboard/models/board_state.py`, `game.py`, `controllers/chess_controller.py`, `config/settings.py`, `config/keyboard_config.py` — direct code reading (HIGH confidence).
- Context7 `/wxwidgets/phoenix` — `wx.Timer` periodic-event pattern, `wx.CallAfter` thread marshalling, `wx.CallLater` one-shot debounce. (HIGH confidence: official wxPython docs.)
- Context7 `/niklasf/python-chess` — PGN export, headers, polyglot opening book API (HIGH confidence: official python-chess docs).
- [Playing (part of) a sound cross-platform in wxPython? — Discuss wxPython](https://discuss.wxpython.org/t/playing-part-of-a-sound-cross-platform-in-wxpython/28145) — pygame.mixer is the consensus wxPython-compatible non-blocking sound option (MEDIUM confidence: community thread, current).
- [Cross-Platform Sound Solutions: Moving Beyond Python's winsound Module](https://runebook.dev/en/docs/python/library/winsound/winsound.MB_ICONEXCLAMATION) — pygame and simpleaudio are the recommended cross-platform paths (MEDIUM confidence: aggregator).
- [How to Play Music in Python: 2026 Guide](https://copyprogramming.com/howto/how-to-play-music-in-python) — playsound3 3.0 (April 2025) added non-blocking with `block=False`; pygame.mixer remains the more featureful option for SFX with per-sound volume (MEDIUM confidence: dated guide, recent).
- [PGN Specification §8.2.5 (Game Termination markers and `[%clk]` move-comment)](https://en.wikipedia.org/wiki/Portable_Game_Notation) — `[%clk H:MM:SS]` format for move-time annotations is the de facto standard used by lichess and chess.com PGN exports (MEDIUM confidence: spec is informal but widely implemented).

---

*Architecture research for: accessible desktop chess GUI v1 — integration of clock, sound, persistence, theme, key-rebinding, and verbosity-tiers into existing wxPython MVC + blinker codebase.*
*Researched: 2026-04-27*

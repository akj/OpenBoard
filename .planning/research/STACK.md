# Stack Research — v1 Foundation & Polish Additions

**Domain:** Accessible desktop chess GUI (Python + wxPython, additive milestone)
**Researched:** 2026-04-27
**Confidence:** HIGH (sound layer, PGN, clock, persistence) / MEDIUM (rebinding UI)

This document is **strictly additive** to `.planning/codebase/STACK.md`. The locked stack (Python 3.12+, wxPython 4.2.5, python-chess 1.11.2, blinker 1.9.0, accessible-output3 git-HEAD, pydantic 2.12.5, pytest, ruff, ty, PyInstaller) is **not** re-recommended here. Only what to add for the v1 milestone.

## TL;DR

| Concern | Recommendation | Confidence |
|---------|---------------|------------|
| 1. Cross-platform sound | `pygame>=2.6.1` (mixer subsystem only) | HIGH |
| 2. PGN serialization | `python-chess` already covers it — no new dep | HIGH |
| 3. Clock | `time.monotonic()` + `wx.Timer` — no new dep | HIGH |
| 4. Auto-save persistence | JSON via pydantic `model_dump_json` + `os.replace()` atomic write | HIGH |
| 5. Settings UI | Stock wx widgets (`wx.Dialog`, `wx.Notebook`, `wx.Choice`, `wx.Slider`) — no `wx.PropertyGrid` | MEDIUM |

---

## 1. Cross-Platform Sound Playback

### Recommendation: `pygame>=2.6.1` (use only `pygame.mixer`)

**Confidence:** HIGH

```toml
# Add to pyproject.toml
dependencies = [
    "pygame>=2.6.1",
    # ... existing
]
```

**Why pygame.mixer:**

| Criterion | Verdict |
|-----------|---------|
| Cross-platform binary wheels (Win / macOS / Linux, Python 3.12 + 3.13) | Yes — manylinux + macOS universal2 + Windows wheels published for 2.6.1 |
| Per-clip volume (`Sound.set_volume()`) | Yes |
| Per-channel volume + multi-clip mixing (no clip cuts off another) | Yes — `mixer.Channel`, default 8 channels, raisable via `set_num_channels()` |
| Non-blocking (does not stall wxPython MainLoop) | Yes — playback runs on SDL audio thread |
| WAV + OGG support out of the box (no ffmpeg) | Yes |
| Active maintenance | Yes — 2.6.1 released 2024-09-29, ongoing point releases |

**How it integrates with the existing architecture:**

- A new `openboard/audio/sound_manager.py` module owns `pygame.mixer.init()` lifecycle.
- **Critical:** call `pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)` then `pygame.mixer.init()` early in `main()` — *do not* call top-level `pygame.init()` (it would spin up display / event subsystems we don't need and conflict with wxPython's event loop / GTK).
- Wrap `init()` in try/except — degrade gracefully to "sound off" if no audio device (mirrors the engine-optional pattern). On headless Linux CI, `os.environ["SDL_AUDIODRIVER"] = "dummy"` keeps tests green.
- Categories (move / opponent / capture / check / castle / clock-tick / alert) each get a dedicated `mixer.Channel` so a quick double-move doesn't truncate the previous SFX.
- Subscribe to `BoardState.move_made` via blinker. Sound playback is fire-and-forget (`Sound.play()`); no `wx.CallAfter` round-trip needed because pygame writes to its own audio thread.

**Buffer size note:** Default 512-sample buffer at 44.1 kHz ≈ 11.6 ms latency — well within the "feels instant" threshold for game SFX. Don't drop below 256 unless profiling demands it; smaller buffers cause underruns on busy systems.

**Cross-platform pitfalls (and how we avoid them):**

| Platform | Pitfall | Mitigation |
|----------|---------|------------|
| Linux (GTK/wx) | SDL2 + GTK can race on audio device init if both try to grab it; PulseAudio errors `Connection terminated` in containers. | Init `pygame.mixer` *before* `wx.App()`. Set `SDL_AUDIODRIVER=alsa` env override available for users on broken Pulse setups. |
| Linux (wheels) | manylinux pygame wheels do not link PulseAudio directly (issue #1351); they go through SDL2's runtime detection. | Acceptable — SDL2 finds Pulse / Pipewire / ALSA at runtime via dlopen. Document `apt install libsdl2-2.0-0` as transitive dep (already pulled in by `libsdl2-dev` in our existing dev deps). |
| Windows | None significant; SDL2 uses WASAPI. | None needed. |
| macOS | None significant; SDL2 uses CoreAudio. Universal2 wheels handle Apple Silicon + Intel. | None needed. |
| All | `pygame.mixer.init()` raises `pygame.error` if no device. | Catch, log, set `sound_enabled = False`, continue. |
| All | A second `pygame.init()` somewhere would activate display subsystem. | Lint rule / code-review only — never call `pygame.init()` in this project, only `pygame.mixer.init()`. |

**Asset format:** Ship sounds as 16-bit 44.1 kHz mono OGG Vorbis (smaller than WAV, no patent concerns, pygame supports natively). For very short SFX (< 200 ms) WAV is also fine.

### Alternatives Considered (and Rejected)

| Library | Latest version | Why Not |
|---------|----------------|---------|
| **`simpleaudio` 1.0.4** | 2022 (archived) | Maintainer publicly archived the project; no Python 3.12 / 3.13 wheels guaranteed. `simpleaudio-patched` fork exists but adds another unmaintained surface. No volume control API. |
| **`playsound` 1.3.0** | 2021 (unmaintained) | Discontinued. macOS requires `PyObjC` (huge transitive install). Python 3.11+ wheel-build failures documented. No volume control. |
| **`playsound3`** | 2.x (active fork) | Better than playsound, but: still single-clip-at-a-time on most backends, no per-channel mixing for overlapping SFX (move + clock-tick), and no volume control comparable to pygame. |
| **`wx.adv.Sound`** | bundled | WAV-only, no volume control API, async playback gets cut off when a second sound starts, Linux backend (OSS/SDL) is flaky. wxPython docs themselves recommend `wx.MediaCtrl` for anything serious — and that introduces GStreamer / DirectShow / AVFoundation dependencies per platform. Hard pass. |
| **`miniaudio` (irmen/pyminiaudio)** 1.61 | 2024 | Solid library but Windows users without VC++ build tools have to compile from source if no wheel matches their platform/Python combo. Adds risk for our PyInstaller-bundled distribution. Lower-level API (you write the playback loop). |
| **`just_playback`** 0.1.8 | 2023 | miniaudio wrapper with `set_volume()`. Lighter than pygame, but: single-clip-per-instance design (you'd allocate one Playback object per category — works but ugly), tiny user base, last release 2023, no per-channel mix bus. Good fallback if pygame ever breaks but not the primary pick. |
| **`sounddevice` + `soundfile`** | active | PortAudio bindings — designed for streaming / DSP, not file SFX. Threading `.write()` calls before previous finishes can crash (issue #469). You'd have to write a Channel/Sound abstraction yourself. Wrong tool. |
| **`pydub` + `simpleaudio`** | active + archived | pydub adds ffmpeg as runtime dep (huge for installer size) and depends on simpleaudio (archived). Double-no. |
| **`pygame-ce` (Community Edition fork)** | 2.5.x | Active, friendly community. **Not picked** because upstream `pygame` 2.6.1 is current, has wheels for Py 3.12/3.13, and switching to the fork would require a justification users / packagers might question. Revisit if upstream pygame stalls again. |

### What NOT to Do

| Avoid | Why |
|-------|-----|
| Calling `pygame.init()` instead of `pygame.mixer.init()` | Spins up display/event subsystems → fights wxPython MainLoop, causes spurious window grabs on macOS. |
| Loading sound files inside the move handler | Adds I/O latency to every move. Load all `Sound` objects once at app start; cache in `SoundManager`. |
| Pre-decoding via `pydub` and re-encoding | Unneeded; pygame mixer decodes WAV/OGG directly. |
| Running `mixer.music` (streaming) for short SFX | `mixer.music` is for one background track; use `Sound` + `Channel` for SFX. |
| Bundling MP3 | Patent encumbrance varies by jurisdiction; OGG Vorbis is patent-free. (Also pygame's MP3 support has historically been spottier than OGG.) |

---

## 2. PGN Serialization

### Recommendation: `python-chess>=1.11.2` (already locked)

**Confidence:** HIGH (verified against official 1.11.2 docs)

`python-chess` 1.11.2 already provides everything v1 needs end-to-end. **Do not add a PGN library.**

| Capability | API | Status |
|------------|-----|--------|
| Read a PGN game from a file | `chess.pgn.read_game(file_handle)` | Built-in |
| Read multiple games from one file | Loop on `read_game` until it returns `None` | Built-in |
| Write a PGN game to a file | `game.accept(chess.pgn.FileExporter(handle, headers=True, comments=True, variations=True))` | Built-in |
| Standard Seven Tag Roster headers (Event, Site, Date, Round, White, Black, Result) | `game.headers` (a `Headers` mapping) | Built-in |
| Custom headers (TimeControl, FEN, SetUp, etc.) | `game.headers["TimeControl"] = "300+5"` | Built-in |
| Move comments | `node.comment = "..."` | Built-in |
| NAGs (`!`, `?`, `!?`, etc.) | `node.nags: set[int]`; `chess.pgn.NAG_*` constants | Built-in |
| Variations | `node.add_variation(move)`, traversed via visitors | Built-in |
| Build a `Game` from a played `chess.Board` history | `chess.pgn.Game.from_board(board)` | Built-in |
| FEN setup (non-standard start position) | `game.headers["SetUp"] = "1"`, `game.headers["FEN"] = ...` | Built-in |
| Visitor-based parse for streaming / partial reads | `chess.pgn.BaseVisitor` subclass | Built-in |

**Gaps / things to watch:**

- `python-chess` does not produce per-move *clock* annotations (`{[%clk 0:05:00]}`) automatically. If we want PGN files with embedded clock state, we write the `[%clk H:MM:SS]` token into `node.comment` ourselves. Trivial, but worth a helper.
- `chess.pgn.read_game` returns `None` at EOF — *not* an exception. Loop accordingly.
- Encoding: PGN spec is ISO 8859-1 / Latin-1, but most modern files are UTF-8. Open files with `encoding="utf-8-sig", errors="replace"` to handle both.
- For FEN save/load: use `chess.Board().fen()` and `chess.Board(fen=...)` — already in use elsewhere in the codebase (`models/board_state.py`). No new work, no new dep.

**Engine-optional impact:** None. PGN/FEN paths never touch `engine_adapter`.

---

## 3. Clock Implementation

### Recommendation: stdlib `time.monotonic()` + `wx.Timer` — **no new dependency**

**Confidence:** HIGH

**Why no library:**

- A chess clock is a 50-line state machine: per-side `remaining_ms: float`, `is_running: bool`, `side_to_move`, `last_tick_monotonic: float`. Increment on move (Fischer), decrement on tick. There is no library worth pulling in for this.
- `time.monotonic()` is the right primitive: never goes backwards, unaffected by NTP / DST / system clock changes. Documented platform precision is sub-millisecond on all three of our targets (PEP 418).
- `wx.Timer` running on the main thread at 100 ms interval is the right cadence for UI redraw + low-time announcements. We do not compute remaining time *from* tick count — we compute it from `time.monotonic()` deltas, so a missed/late tick does not introduce drift. This pattern matches existing chess-clock implementations.

**Drift sanity-check:**

- `wx.Timer` precision is documented as "not better than 1 ms, not worse than 1 s." That's fine because we only use it to *trigger* recalculation; the authoritative remaining-time is `remaining_at_start_of_turn - (time.monotonic() - turn_started_monotonic)`.
- Worst-case OS scheduler hiccup: 100 ms display lag on the clock. Acceptable for casual / classical time controls; for blitz under 1 minute we tighten the timer to 50 ms.

**Architecture fit:**

- New `openboard/models/clock.py` with a `Clock` dataclass-ish class that emits blinker signals: `tick(remaining_white_ms, remaining_black_ms)`, `flag_fell(side)`, `low_time(side, threshold_seconds)`. Mirrors existing model-layer patterns.
- `ChessController` subscribes to `tick` for status-bar update, to `flag_fell` for end-of-game handling, and to `low_time` for accessibility announcement (`announce.send("30 seconds remaining")`).
- `Clock` does *not* own a `wx.Timer` directly — that would couple model to view. Instead, the controller owns the `wx.Timer` and calls `clock.tick_now()` on each tick, and the `Clock` reads `time.monotonic()` itself. Keeps MVC boundary clean.

**Time-control formats supported in v1 (parsed, not necessarily all UX-exposed):**

- Sudden death: `300` (seconds)
- Fischer increment: `300+5`
- Bronstein delay: `300d3` (optional v1; defer if scope creeps)
- Multi-stage (`40/7200:3600`): defer to v2 unless trivial.

**Cross-platform:** All `stdlib` — identical behaviour on Windows / macOS / Linux. No platform-specific code paths.

---

## 4. Auto-Save Persistence

### Recommendation: JSON via pydantic + atomic file replacement (`os.replace()`)

**Confidence:** HIGH

**Storage format:** JSON, written through pydantic's `model_dump_json()`.

```python
# openboard/persistence/saved_game.py (new module)
class SavedGame(pydantic.BaseModel):
    schema_version: int = 1
    pgn: str                       # full PGN, written via chess.pgn.FileExporter to a string
    current_fen: str               # for fast reload without replaying
    side_to_move: chess.Color
    clock_white_ms: float | None
    clock_black_ms: float | None
    time_control: str | None       # e.g. "300+5"
    game_config: dict              # GameConfig.model_dump()
    saved_at: datetime
```

**Atomic write pattern (crash safety):**

```python
def save(self, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(self.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp, path)   # atomic on POSIX and Windows (Python 3.3+)
```

`os.replace()` is the cross-platform atomic-rename primitive — POSIX `rename(2)` on Linux/macOS, `MoveFileExW` with `MOVEFILE_REPLACE_EXISTING` on Windows. Either the new file is fully there or the old one is untouched; no half-written state on crash.

**Why JSON, not pickle, not sqlite:**

| Option | Verdict | Reasoning |
|--------|---------|-----------|
| **JSON via pydantic** | ✓ Pick | Human-readable (debug autosaves by eyeballing), pydantic gives schema validation on load + free serializers, schema versioning by `schema_version: int` field, existing project already uses pydantic for keyboard config (familiar pattern). |
| **Pickle** | ✗ | Brittle: rename a class, move a module, bump a Python version → unpickle fails. Security risk if a saved file ever travels (untrusted unpickle = RCE). Opaque to debugging. We gain nothing over JSON because all our state is primitives + strings + a PGN. |
| **SQLite** | ✗ for v1 | Overkill for "one in-progress game." Adds DB lifecycle complexity, file locking on Windows, vacuum concerns. Worth revisiting in v2 when the saved-game *library* lands — at that point a single `~/.openboard/saved_games.db` with rows per game is sensible. v1 is one autosave file; one JSON file is correct. |

**Schema evolution:** `schema_version: int = 1`. On load, branch on version:

```python
data = json.loads(text)
if data["schema_version"] == 1:
    return SavedGame.model_validate(data)
elif data["schema_version"] == 0:
    return migrate_v0_to_v1(data)
else:
    raise SaveFileTooNew(...)
```

Cheap insurance; pays off the first time we add a field in v2.

**Auto-save trigger strategy:**

- After every applied move (`BoardState.move_made` signal): save. A move occurs O(1 per second) at most; one JSON write of < 4 KB is trivial.
- On graceful shutdown (`wx.EVT_CLOSE`): final save.
- On crash: last successful per-move save survives, because of `os.replace()`.

**Storage location:** `Path.home() / ".openboard" / "autosave.json"` on Linux/macOS, `%APPDATA%/openboard/autosave.json` on Windows. Use `platformdirs` if we want it done right — **but** `platformdirs` is a new dep, and `Settings` already does platform-aware path resolution by hand. Defer `platformdirs` unless we add a third platform-specific path; for v1, extend the existing `Settings` pattern.

**No new dependency required for persistence** — pydantic and stdlib are sufficient.

---

## 5. Configuration / Settings UI

### Recommendation: stock wxPython widgets — no `wx.PropertyGrid`, no third-party

**Confidence:** MEDIUM (rooted in accessibility judgment more than benchmarks)

For the v1 settings dialogs (key-rebinding UI, sound volume per category, theme/scale, announcement verbosity tiers):

| Need | Widget | Notes |
|------|--------|-------|
| Tabbed settings | `wx.Notebook` or `wx.Listbook` | Standard, screen-reader friendly |
| Key capture | `wx.TextCtrl` w/ `EVT_KEY_DOWN` handler + label | Simple custom control; tag with `SetName()` for screen readers |
| Volume sliders | `wx.Slider` | Native, screen-reader-readable |
| Per-category on/off | `wx.CheckBox` | Native |
| Verbosity tier per event | `wx.Choice` (dropdown) per row | Native |
| Theme picker | `wx.Choice` | Native |
| Piece/board scale | `wx.Slider` or `wx.SpinCtrl` | Native |
| Layout | `wx.BoxSizer` + `wx.GridBagSizer` | Standard |

### Why **not** `wx.PropertyGrid`

`wx.propgrid.PropertyGrid` *is* available (in wxPython Phoenix 4.2.5 it's `wx.propgrid`), and it's powerful for tabular property editing. But:

1. **Accessibility uncertainty.** `wx.Accessible` is documented as Windows-only (MSAA). PropertyGrid's screen-reader behaviour on macOS VoiceOver and Linux Orca is not well documented. For an accessibility-first project, "I'm not sure if NVDA/VoiceOver/Orca read this widget correctly" is a deal-breaker. Stock controls (`wx.Slider`, `wx.CheckBox`, `wx.Choice`, `wx.TextCtrl`) have decades of screen-reader plumbing on every platform.
2. **Custom layout flexibility.** A key-rebinding row needs: action label + current binding + "press a key to rebind" button + reset-to-default button. A grid forces a fixed 2-column shape. A `wx.BoxSizer` does whatever we need.
3. **One dialog, not a kitchen sink.** Our settings surface is small (~10 keybindings, 6 sound categories, ~5 visual options, ~5 announcement tiers). PropertyGrid's value is at scale; ours is small enough that hand-laid sizers are clearer.

### What about other libraries?

| Library | Verdict |
|---------|---------|
| `wx.lib.agw.*` (Advanced Generic Widgets) | Pure-Python wxPython add-ons, bundled with wxPython itself. Components like `HyperTreeList`, `FlatNotebook`, `XLSGrid` exist. **Not needed for v1.** Accessibility characteristics of generic-drawn widgets are weaker than native ones. |
| Any custom theming lib (e.g. `wxPython-themes`, `darkdetect`) | Out of scope. High-contrast theme is a *board rendering* change in `BoardPanel` (palette + piece bitmap swap), not a wx-widget-theming change. No new dep. |
| `darkdetect` | Useful for OS-dark-mode auto-detection. **Defer** — v1 spec is "user-toggleable high-contrast theme," not "follow OS dark mode." Add later if user demand. |

### Key-rebinding capture: implementation note

The "press a key to rebind" pattern is standard wxPython:

1. User clicks a `wx.Button` labeled e.g. "Rebind 'Move Up'."
2. Button enters capture mode: `SetLabel("Press a key…")`, `SetFocus()`, `Bind(wx.EVT_KEY_DOWN, on_capture)`.
3. `on_capture` reads `event.GetKeyCode()` + `event.GetModifiers()`, validates uniqueness, writes through `GameKeyboardConfig`, persists to `keyboard_config.json` (existing pydantic-backed file), exits capture mode.

No new library needed. This is ~80 lines of code in a new `openboard/views/keybinding_dialog.py`.

---

## Installation

```bash
# Add to pyproject.toml dependencies (only one new runtime dep across all of v1)
uv add 'pygame>=2.6.1'
```

That is the **entire** new-runtime-dependency surface for v1. Everything else is stdlib (`time.monotonic`, `os.replace`, `json`) or already-locked (`pydantic`, `python-chess`, `wxPython`, `blinker`, `accessible-output3`).

No new dev dependencies required.

---

## Alternatives Considered

| Recommended | Alternative | When the alternative makes sense |
|-------------|-------------|----------------------------------|
| `pygame` for sound | `just_playback` | Pygame becomes unmaintained or its SDL2 binding breaks. just_playback is smaller and miniaudio-based. |
| `pygame` upstream | `pygame-ce` | Upstream pygame stalls on Python 3.14 / new SDL3. Migration is mostly a rename. |
| stdlib clock | None worth naming | A library here would be net-negative. |
| JSON autosave | SQLite | When v2 lands the saved-game library — multi-row storage justifies a DB file. |
| Stock wx widgets | `wx.PropertyGrid` | A future "advanced engine settings" dialog with 50+ tunables. Not v1. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `simpleaudio` | Archived 2022; no Py 3.12 wheel guarantee | `pygame.mixer` |
| `playsound` | Unmaintained since 2021; macOS PyObjC drama | `pygame.mixer` |
| `wx.adv.Sound` | WAV-only, no volume API, single-sound-at-a-time, Linux backend (OSS) effectively dead | `pygame.mixer` |
| `wx.MediaCtrl` for SFX | Pulls in GStreamer / DirectShow / AVFoundation; massive installer bloat for short SFX | `pygame.mixer` |
| `pydub` | ffmpeg runtime dep; SFX don't need format conversion | `pygame.mixer` reads WAV/OGG natively |
| `playsound3` | Better than playsound but no per-channel mixing for overlapping SFX | `pygame.mixer` |
| `pickle` for autosave | Schema brittleness, RCE risk if file ever travels | pydantic `model_dump_json` |
| MP3 assets | Patent variability + pygame's MP3 backend has historical bugs | OGG Vorbis (or WAV for very short clips) |
| Calling top-level `pygame.init()` | Activates display + event subsystems, fights wxPython | `pygame.mixer.init()` only |
| `time.time()` for the clock | Wall-clock; jumps on NTP/DST | `time.monotonic()` |

## Stack Patterns by Variant

**If the user's Linux machine has no working audio device:**
- `pygame.mixer.init()` raises `pygame.error`. Catch it, log, set `SoundManager.enabled = False`. App continues normally with no sound — same engine-optional pattern.
- Headless CI: set `SDL_AUDIODRIVER=dummy` env var in test fixtures.

**If we need to seek inside a sound (we don't, in v1):**
- pygame mixer cannot seek inside a `Sound`. Would need to switch to `mixer.music` (single stream) or `just_playback`. Out of scope for v1 SFX.

**If sound assets ever exceed ~1 MB each (they shouldn't for SFX):**
- Use `mixer.music.load()` + stream from disk instead of in-memory `Sound`. Not needed for short chess SFX (a few KB each).

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `pygame>=2.6.1` | Python 3.12, 3.13 | Wheels published for both; 2.6.1 added 3.13 support. |
| `pygame>=2.6.1` | wxPython 4.2.5 | Independent libs; only interaction risk is double-`pygame.init()` (we don't call it). |
| `pygame>=2.6.1` | PyInstaller 6.16.0 | PyInstaller has a `pygame` hook bundled; SDL2 dynamic libs are picked up automatically. Verify in build CI on first integration. |
| `python-chess>=1.11.2` | All v1 PGN/FEN needs | No upgrade needed. |
| `pydantic>=2.12.5` | JSON autosave via `model_dump_json()` | No upgrade needed. |

## Cross-Platform Sanity Checklist (apply during v1 implementation)

- [ ] On a fresh Windows install: app starts, plays move sound, autosaves, reloads autosave.
- [ ] On a fresh macOS install: app starts, plays move sound, NSCoreAudio path works, autosave file lives under `~/Library/Application Support/openboard/` *or* `~/.openboard/` (decide and document).
- [ ] On a fresh Ubuntu 24.04 install: app starts, plays move sound through Pulse/Pipewire, autosaves.
- [ ] On a Linux machine with PulseAudio disabled / ALSA-only: app starts, plays sound (or degrades gracefully).
- [ ] On a Linux machine with no audio device at all (CI): app starts, sound disabled, no traceback.
- [ ] PyInstaller-bundled binary on each platform: SDL2 .dll / .dylib / .so is included; sound works from the bundle, not just from `uv run`.

---

## Sources

- python-chess 1.11.2 PGN docs — verified headers/comments/NAGs/variations support — https://python-chess.readthedocs.io/en/latest/pgn.html (HIGH)
- pygame 2.6.1 release (2024-09-29, Python 3.13 support) — https://github.com/pygame/pygame/releases (HIGH)
- pygame.mixer 2.6.1 docs (`pre_init`, `Sound.set_volume`, `Channel.set_volume`, default buffer 512) — https://www.pygame.org/docs/ref/mixer.html (HIGH)
- pygame manylinux wheels and PulseAudio (issue #1351) — https://github.com/pygame/pygame/issues/1351 (HIGH)
- simpleaudio archived status — https://snyk.io/advisor/python/simpleaudio + https://github.com/hamiltron/py-simple-audio (HIGH)
- playsound unmaintained / macOS PyObjC issue — https://github.com/TaylorSMarks/playsound/issues/5, https://github.com/TaylorSMarks/playsound/issues/97 (HIGH)
- playsound3 fork — https://pypi.org/project/playsound3/ (MEDIUM)
- wx.adv.Sound limitations (WAV-only, no volume) — https://docs.wxpython.org/wx.adv.Sound.html (HIGH)
- miniaudio Python bindings, Windows compile caveat — https://github.com/irmen/pyminiaudio (HIGH)
- just_playback API — https://github.com/cheofusi/just_playback (MEDIUM)
- python-sounddevice not designed for SFX file playback (issue #469) — https://github.com/spatialaudio/python-sounddevice/issues/469 (MEDIUM)
- wx.Timer precision (1 ms – 1 s, platform-dependent) — https://docs.wxpython.org/wx.Timer.html (HIGH)
- PEP 418 `time.monotonic()` semantics — https://peps.python.org/pep-0418/ (HIGH)
- Atomic-write pattern with `os.replace()` (Python 3.3+, cross-platform) — https://docs.python.org/3/library/os.html#os.replace + https://iifx.dev/en/articles/460341744/how-to-implement-atomic-file-operations-in-python-for-crash-safe-data-storage (HIGH)
- pydantic 2 `model_dump_json` / `model_validate` — https://docs.pydantic.dev/latest/concepts/models/ (HIGH)
- wx.Accessible Windows-only (MSAA) — https://docs.wxpython.org/wx.Accessible.html (HIGH)
- wx.propgrid.PropertyGrid docs — https://docs.wxpython.org/wx.propgrid.PropertyGrid.html (MEDIUM — feature presence verified, accessibility characteristics inferred)
- pygame-ce fork context — https://github.com/pygame-community/pygame-ce (MEDIUM)
- SDL2 `SDL_AUDIODRIVER=dummy` headless escape hatch — https://discourse.libsdl.org/t/couldnt-open-audio-device-no-available-audio-device/18499 (HIGH)

---

*Stack research for: v1 Foundation & Polish additions to existing accessible chess GUI*
*Researched: 2026-04-27*

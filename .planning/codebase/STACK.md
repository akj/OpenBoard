# Technology Stack

**Analysis Date:** 2026-04-27

## Languages

**Primary:**
- Python 3.12 - All application code (`openboard/`, `tests/`, `.build/`)

**Secondary:**
- JSON - Keyboard configuration (`config/keyboard_config.json`)

## Runtime

**Environment:**
- CPython 3.12.3 (resolved in `.venv/pyvenv.cfg`)
- Requires Python `>=3.12` (declared in `pyproject.toml`)

**Package Manager:**
- uv 0.7.19 (`.venv/pyvenv.cfg` records uv version; CI pins uv `0.8.19`)
- Lockfile: `uv.lock` (present and committed)

## Frameworks

**GUI:**
- wxPython 4.2.5 — cross-platform desktop GUI (`openboard/views/views.py`, `openboard/views/game_dialogs.py`, `openboard/views/engine_dialogs.py`)
  - On Linux: installed from the wxPython extras index `https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-24.04/`
  - On Windows/macOS: installed from PyPI

**Chess Logic:**
- chess 1.11.2 — board representation, move generation, UCI engine protocol, PGN I/O, Polyglot opening book (`openboard/models/`, `openboard/engine/engine_adapter.py`, `openboard/models/opening_book.py`)

**Signal / Event Bus:**
- blinker 1.9.0 — decoupled MVC signals (`openboard/models/game.py`, `openboard/engine/stockfish_manager.py`, `openboard/controllers/chess_controller.py`)

**Data Validation:**
- pydantic 2.12.5 — keyboard configuration dataclasses with validation (`openboard/config/keyboard_config.py`)

**Accessibility:**
- accessible-output3 0.0.0 (git — `https://github.com/SigmaNight/accessible_output3`) — screen reader output (`openboard/views/views.py`)

**Testing:**
- pytest 9.0.1 — test runner (`tests/`)
- pytest-asyncio 1.3.0 — async test support (`tests/test_game_async.py`, `tests/test_engine_adapter.py`)
- pytest-cov 7.0.0 — coverage reporting

**Build/Dev:**
- PyInstaller 6.16.0 — standalone executable packaging (`.build/pyinstaller_spec.py`, `.build/scripts/build.py`)
- ruff 0.15.1 — linting and formatting (CI: `uv run ruff check .` and `uv run ruff format --check .`)
- ty 0.0.11 — type checking (CI: `uv run python -m ty check`)

**Icon Generation (dev-only):**
- cairosvg 2.8.2 — SVG-to-PNG conversion for icon assets (`assets/icons/`)
- Pillow 12.1.0 — image processing for icon generation

## Key Dependencies

**Critical:**
- `chess` 1.11.2 — provides `chess.Board`, `chess.engine` (UCI), `chess.pgn`, `chess.polyglot`; the entire game logic layer depends on it
- `wxPython` 4.2.5 — the entire GUI layer; no alternative rendering path exists
- `accessible-output3` (git HEAD) — screen reader output; sourced from git, not a versioned PyPI release; a breaking upstream commit could silently update it
- `blinker` 1.9.0 — all MVC communication is signal-based; removing it would require major refactor

**Infrastructure:**
- `pydantic` 2.12.5 — keyboard config serialization/deserialization including JSON round-trips
- `pyinstaller` 6.16.0 — produces distributable executables for Windows, macOS, Linux

## Configuration

**Environment:**
- No `.env` file mechanism; the application has no runtime secrets
- `config/keyboard_config.json` — default keyboard bindings loaded at startup
- `openboard/config/settings.py` — `UISettings` and `EngineSettings` dataclasses; platform-specific engine search paths resolved at import time

**Build:**
- `pyproject.toml` — project metadata, runtime deps, dev deps, uv source overrides
- `uv.lock` — fully pinned dependency lockfile
- `.build/pyinstaller_spec.py` — PyInstaller spec generator
- `.build/scripts/build.py` — orchestrates PyInstaller invocation
- `.build/installers/scripts/build_installer.py` — builds DEB, RPM, DMG, Inno Setup installers

## Platform Requirements

**Development:**
- Python 3.12+
- uv (any recent version; CI pins 0.8.19)
- Linux: `libgtk-3-dev`, `libwebkit2gtk-4.1-dev`, `libnotify-dev`, `libsdl2-dev` (for wxPython)
- Linux (tests): additionally `stockfish`, `speech-dispatcher`, `espeak-ng`
- macOS (tests): `stockfish` via Homebrew

**Production / Distribution:**
- Windows: self-contained PyInstaller zip or Inno Setup `.exe`; Stockfish can be auto-downloaded via `StockfishDownloader`
- macOS: `.app` bundle in a DMG
- Linux: DEB (Debian/Ubuntu) or RPM (Fedora/RHEL), with runtime deps `gtk3`, `speech-dispatcher >= 0.8`, `espeak-ng`
- Stockfish is an optional runtime dependency on all platforms (system install or locally managed under `engines/stockfish/`)

---

*Stack analysis: 2026-04-27*

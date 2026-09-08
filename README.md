# OpenBoard

A desktop chess app with keyboard navigation and screen reader support, built with wxPython and python-chess.

## Run from source

Install Python 3.12 or later and [uv](https://docs.astral.sh/uv/), then run:

```sh
git clone https://github.com/akj/OpenBoard.git
cd OpenBoard
uv sync --locked
uv run --no-sync openboard
```

Windows and macOS use wxPython wheels. Linux needs GTK libraries and a display. The project uses the wxPython Ubuntu 24.04 wheel index on Linux. See the [CI workflow](.github/workflows/ci.yml) for the system packages and Xvfb setup.

On Ubuntu 24.04, prepare the environment before `uv sync` so speech announcements can use the system Speech Dispatcher binding:

```sh
sudo apt-get install python3-venv python3-speechd speech-dispatcher espeak-ng libgtk-3-0t64 libnotify4 libsdl2-2.0-0
uv venv --python /usr/bin/python3 --system-site-packages
uv sync --locked
```

Linux portable builds include the Python binding but still need a running Speech Dispatcher service. macOS speech uses VoiceOver or the system synthesizer.

Stockfish is optional for two local players. Use the Engine menu to install it on Windows, or install Stockfish yourself and put it on PATH. Computer games and engine hints need an engine. Opening book hints use a Polyglot `.bin` file loaded from the Opening Book menu.

## Play with the keyboard

| Key | Action |
| --- | --- |
| Arrow keys | Focus an adjacent square |
| Space | Select a piece or move it to the focused square |
| Shift+Space | Deselect the piece |
| Ctrl+Z | Undo |
| H | Request an engine hint |
| B | Request an opening book hint |
| M | Announce legal moves for the selected piece |
| A | Announce attackers of the focused square |
| ] | Repeat the last move |
| Ctrl+L | Open the move list |
| F5 / F6 | Previous / next replay move |

The Game menu starts human versus human, human versus computer, and computer versus computer games. Promotion opens a piece chooser. Replay preserves the imported starting position and the full move list.

On Windows, the board exposes square names, roles, focus, and selection through native accessibility. Move and game announcements use accessible-output3. Other platforms retain spoken navigation. Native API tests do not replace testing the app with a screen reader. See [AUDIT.md](AUDIT.md) for the validation completed during the revival and its limits.

## Configuration and development

Keyboard overrides live in `keyboard_config.json` in the platform's user configuration directory. Engines live in the user data directory, and logs in the user state directory. Set `OPENBOARD_PROFILE_DIR` to use a separate profile. Absent or invalid keyboard files fall back to the defaults in [keyboard_config.py](openboard/config/keyboard_config.py). The loader skips unknown actions with a logged warning and preserves recognized bindings. If every binding has an unknown action, it uses the defaults.

```sh
uv run --no-sync pytest
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync ty check
uv run --no-sync openboard --self-test
```

Tests capture app speech and use temporary profiles. Linux GUI tests run under `xvfb-run -a`. The startup self-test imports the app and makes a legal move without opening a window or speaking.

To build a standalone executable:

```sh
uv run --no-sync python .build/scripts/build.py
```

The build checks startup before and after packaging. CI runs the full test suite on Windows, macOS, and Linux, then builds portable archives and checks their extracted executables. Platform installers require [additional system tools](.build/installers/README.md). The release workflow reuses CI with installer builds enabled and checks the release tag against the package version before publishing. [Renovate configuration](renovate.json) controls dependency updates and lockfile maintenance.

MIT license. See [LICENSE](LICENSE).

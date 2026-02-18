# OpenBoard

An accessible, cross-platform chess GUI built with keyboard-first navigation and screen reader support.

OpenBoard is designed so that blind and visually impaired players can enjoy chess without a mouse. It also works well for sighted players who prefer keyboard controls.

## Features

- **Full keyboard navigation** — move around the board with arrow keys, select and place pieces with Space
- **Screen reader support** — announces moves, legal moves, and board state via accessible-output3
- **Brief and verbose announcement modes** — toggle between concise and detailed move descriptions
- **Play against Stockfish** — four difficulty levels from Beginner to Master
- **Human vs Human and Computer vs Computer** modes
- **Opening book support** — load Polyglot opening books for book move hints
- **PGN and FEN support** — load and save games in standard formats
- **Move replay** — step forward and backward through game history
- **Cross-platform** — runs on Windows, macOS, and Linux

## Installation

### From installers (recommended)

Download the latest installer for your platform from the [Releases](../../releases) page:

- **Windows** — `.exe` installer with Start Menu integration and optional PGN file association
- **macOS** — `.dmg` disk image, drag to Applications
- **Linux** — `.deb` (Debian/Ubuntu) or `.rpm` (Fedora/RHEL) packages

### From source

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/yourusername/openboard.git
cd openboard
uv sync
uv run openboard
```

## Keyboard shortcuts

### Board navigation

| Key | Action |
|-----|--------|
| Arrow keys | Move focus around the board |
| Space | Select piece / place piece on target square |
| Shift+Space | Deselect current piece |
| Ctrl+Z | Undo last move |

### Hints and analysis

| Key | Action |
|-----|--------|
| H | Request engine hint |
| B | Request opening book hint |

### Announcements

| Key | Action |
|-----|--------|
| ] | Announce last move |
| M | Announce legal moves for selected piece |
| A | Announce pieces attacking focused square |
| Ctrl+T | Toggle brief/verbose announcement mode |
| Ctrl+L | Show move list |

### Replay

| Key | Action |
|-----|--------|
| F5 | Previous move |
| F6 | Next move |

## Game modes

Start a new game from the **Game** menu:

- **Human vs Human** (Ctrl+N) — two players on the same board
- **Human vs Computer** (Ctrl+M) — choose your color and difficulty
- **Computer vs Computer** (Ctrl+K) — watch two engines play with independent difficulty settings

### Difficulty levels

| Level | Description |
|-------|-------------|
| Beginner | Good for learning |
| Intermediate | Moderate challenge (default) |
| Advanced | Strong opponent |
| Master | Very strong play |

## Engine setup

OpenBoard uses [Stockfish](https://stockfishchess.org/) for computer play and hints. You can install it directly from the **Engine** menu, or OpenBoard will detect an existing Stockfish installation on your system.

## Contributing

Contributions are welcome. The project uses:

- **ruff** for linting and formatting
- **ty** for type checking
- **pytest** for testing

```bash
uv run ruff check .
uv run ty check
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE) for details.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenBoard is an accessible, cross-platform chess GUI written in Python. It uses wxPython for the GUI and provides keyboard navigation, screen reader support, and UCI engine integration (specifically Stockfish).

## Architecture

The project follows an MVC (Model-View-Controller) pattern:

### Models (`openboard/models/`)
- `board_state.py`: Wraps python-chess Board with signal-based updates for move/status changes
- `game.py`: High-level game orchestrator that manages BoardState and optional EngineAdapter

### Views (`openboard/views/`)
- `views.py`: wxPython-based GUI with BoardPanel for chess board display and ChessFrame for the main window

### Controllers (`openboard/controllers/`)
- `chess_controller.py`: Mediates between Game model and View, handles keyboard navigation, selection, and user commands

### Engine (`openboard/engine/`)
- `engine_adapter.py`: Synchronous wrapper around UCI engines (Stockfish) using python-chess

## Key Dependencies

- `chess`: Python chess library for move validation and board representation
- `wxpython`: GUI framework
- `blinker`: Signal system for event handling between MVC components
- `ruff`: Linting and formatting tool
- `pyright`: Static type checking tool

## Development Commands

### Testing
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_game.py

# Run with verbose output
pytest -v
```

### Running the Application
```bash
# From project root
python -m openboard.views.views

# Or directly run the main script
python openboard/views/views.py
```

## Signal-Based Architecture

The application uses blinker signals extensively for communication between components:

- **BoardState signals**: `move_made`, `move_undone`, `status_changed`
- **Game signals**: Forwards BoardState signals plus `hint_ready` for engine responses
- **ChessController signals**: `board_updated`, `square_focused`, `selection_changed`, `announce`, `status_changed`, `hint_ready`

## Engine Integration

OpenBoard automatically detects and uses Stockfish engines installed on your system. The EngineAdapter class provides a synchronous interface to UCI engines and handles engine lifecycle management.

### Engine Installation

**Linux:**
```bash
# Ubuntu/Debian
sudo apt install stockfish

# Fedora
sudo dnf install stockfish

# Arch Linux
sudo pacman -S stockfish
```

**macOS:**
```bash
brew install stockfish
```

**Windows:**
Download from https://stockfishchess.org/download/ and ensure it's in your PATH.

If no engine is found, the application will run in engine-free mode (manual play only).

## Accessibility Features

- Keyboard-only navigation (arrow keys, space for selection)
- Screen reader announcements
- Configurable verbose/brief announcement modes
- Focus highlighting and square-by-square board navigation

## Testing Strategy

Uses pytest with mock engine adapters for testing game logic without requiring actual engine processes. Tests cover move validation, signal emission, and game state management.

## Changelog

- Removed `accessible_output3` dependency from project dependencies
- Added ruff for linting and formatting, mypy for typechecking
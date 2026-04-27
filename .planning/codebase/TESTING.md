# Testing Patterns

**Analysis Date:** 2026-04-27

## Test Framework

**Runner:** pytest 9.0.1+
- Config: `pyproject.toml` (no `[tool.pytest.ini_options]` section detected — uses defaults)
- Run via `uv run python -m pytest -v --tb=short` (as in CI)

**Assertion Library:** pytest's built-in `assert` (no third-party)

**Async support:** `pytest-asyncio` 1.3.0+ for `@pytest.mark.asyncio` tests in integration suite

**Coverage:** `pytest-cov` 7.0.0+

**Run Commands:**
```bash
uv run python -m pytest -v --tb=short       # Run all tests (CI default)
uv run python -m pytest tests/              # Run all tests locally
uv run python -m pytest tests/test_game.py  # Run single file
# Coverage (local, generates htmlcov/):
uv run python -m pytest --cov=openboard --cov-report=html
```

## Test File Organization

**Location:** All tests in top-level `tests/` directory — not co-located with source.

**Naming:** `test_<module_or_feature>.py`
- `tests/test_game.py` — `openboard/models/game.py`
- `tests/test_chess_controller.py` — `openboard/controllers/chess_controller.py`
- `tests/test_engine_adapter.py` — unit tests (mock-only)
- `tests/test_engine_adapter_integration.py` — integration tests (mock engine, real threading)
- `tests/test_engine_adapter_simple.py` — subset of adapter tests (canonical in `test_engine_adapter.py`)
- `tests/conftest.py` — shared fixtures

**Integration vs unit separation:**
- Files named `test_*_integration.py` contain integration tests requiring real or mock engines
- `test_engine_adapter_integration.py` requires Stockfish installed for some tests (CI installs it)
- `test_build_validation.py` contains build-validation tests requiring a configured PyInstaller environment

## Test Structure

**Preferred:** pytest class with `setup_method`:
```python
class TestChessControllerNavigation:
    """Tests for board navigation commands."""

    def setup_method(self):
        self.game = _make_hvh_game()
        self.controller, self.signals = _make_controller(self.game)
        self.signals["announce"].clear()
        self.signals["square_focused"].clear()

    def test_navigate_up_increments_rank(self):
        self.controller.current_square = chess.A1
        self.controller.navigate("up")
        ...
```

**Also used:** `unittest.TestCase` classes (in `test_stockfish_manager.py`):
```python
class TestStockfishManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = StockfishManager(Path(self.temp_dir))

    def test_manager_initialization(self):
        self.assertIsNotNone(self.manager.downloader)
```

**Standalone functions:** Used freely for simple, independent tests without shared state:
```python
def test_game_apply_move():
    game = Game()
    game.apply_move(chess.E2, chess.E4)
    piece = game.board_state.board.piece_at(chess.E4)
    assert piece is not None and piece.symbol().lower() == "p"
```

## Shared Fixtures (conftest.py)

`tests/conftest.py` centralizes FEN position constants:

```python
@pytest.fixture
def stalemate_fen() -> str:
    """FEN for a stalemate position: black king on a8 stalemated by white queen and king."""
    return "k7/2Q5/2K5/8/8/8/8/8 b - - 0 1"

@pytest.fixture
def insufficient_material_fen() -> str:
    """FEN for a draw by insufficient material: kings only."""
    return "4k3/8/8/8/8/8/8/4K3 w - - 0 1"
```

File-local fixtures in `test_engine_adapter_integration.py`:
```python
@pytest.fixture
def mock_engine_path():
    """Provide a mock engine path."""
    return "/usr/bin/mock-stockfish"

@pytest.fixture
def mock_successful_engine():
    """Create a mock engine that succeeds."""
    return MockEngine(delay=0.05)
```

## Mocking

**Primary approach:** `unittest.mock` — `Mock`, `MagicMock`, `patch`, `patch.object`

```python
from unittest.mock import Mock, patch, MagicMock
```

**`Mock(spec=EngineAdapter)`** — spec-constrained mocks for engine injection:
```python
def _make_mock_engine(move_uci="e7e5"):
    engine = Mock(spec=EngineAdapter)
    engine.get_best_move.return_value = chess.Move.from_uci(move_uci)

    def sync_get_best_move_async(fen, time_ms=1000, depth=None, callback=None):
        if callback:
            callback(chess.Move.from_uci(move_uci))

    engine.get_best_move_async.side_effect = sync_get_best_move_async
    return engine
```

**`@patch` context manager** for patching imports:
```python
with patch("openboard.engine.engine_adapter.EngineDetector") as mock_detector_class:
    mock_detector = MagicMock()
    mock_detector.find_engine.return_value = mock_path
    mock_detector_class.return_value = mock_detector
    ...
```

**`patch.object()`** for patching instance methods:
```python
with patch.object(self.manager.detector, "find_engine", return_value=None):
    status = self.manager.get_status()
```

**Inline fake classes** — used when `Mock` would be too permissive or callback behavior is needed:
```python
class DummyEngineAdapter:
    def __init__(self):
        self.last_fen = None
        self.return_move = chess.Move.from_uci("e2e4")

    def get_best_move(self, fen, time_ms=1000):
        self.last_fen = fen
        return self.return_move
```

**Mock engine class** (integration tests) — full async mock engine simulating `chess.engine.Protocol`:
- Defined in `tests/test_engine_adapter_integration.py` as `MockEngine` and `MockTransport`
- Implements `async configure()`, `async play()`, `async quit()`

## Async Testing

**Strategy:** The async engine boundary is replaced with synchronous shims; `pytest-asyncio` is only used for direct `async def test_*` tests in the integration suite.

Most async game-path tests run **without** `pytest-asyncio`:
```python
# test_game_async.py — sync tests of async paths via synchronous callbacks
def test_request_hint_async_callback_emits_hint_ready_on_success(self):
    game = Game(engine_adapter=self.mock_engine)
    # mock engine calls callback synchronously inline
    game.request_hint_async()
    assert len(hint_moves) == 1
```

Direct `async def test_*` functions use `@pytest.mark.asyncio` and exist only in `tests/test_engine_adapter_integration.py`:
```python
@pytest.mark.asyncio
async def test_create_managed_factory(self, mock_engine_path, mock_successful_engine):
    ...
```

## Signal Testing Pattern

Blinker signals are tested by connecting named handler functions and collecting emitted values into lists. `weak=False` prevents garbage collection of named handlers:

```python
def _make_controller(game, config=None):
    controller = ChessController(game, config=config)
    signals = {"announce": [], "board_updated": [], "hint_ready": []}

    def on_announce(sender, **kw):
        signals["announce"].append(kw.get("text"))

    controller.announce.connect(on_announce, weak=False)
    return controller, signals
```

## Parametrize Pattern

Used for exhaustive branch coverage of modifier/state combinations:
```python
@pytest.mark.parametrize(
    "shift,ctrl,alt,expected",
    [
        (False, False, False, True),   # NONE matches no modifiers
        (True, False, False, False),   # NONE rejects shift
        (False, True, False, False),   # NONE rejects ctrl
        (False, False, True, False),   # NONE rejects alt
    ],
)
def test_none_modifier(self, shift, ctrl, alt, expected):
    binding = KeyBinding(key="65", action=KeyAction.SELECT, modifiers=KeyModifier.NONE)
    assert binding.matches(65, shift=shift, ctrl=ctrl, alt=alt) == expected
```

`@pytest.mark.skipif` used to gate tests on Stockfish availability:
```python
@pytest.mark.skipif(
    ...,
    reason="Stockfish not installed"
)
```

## Exception Testing

```python
# Standard pattern
with pytest.raises(IllegalMoveError):
    bs.make_move(chess.Move.from_uci("e2e5"))

# With message match
with pytest.raises(RuntimeError, match="No Stockfish engine found"):
    EngineAdapter()

# Testing exception attributes directly
error = EngineNotFoundError("Stockfish", ["/usr/bin", "/usr/local/bin"])
assert "Searched in: /usr/bin" in str(error)
assert error.engine_name == "Stockfish"
```

## Test Docstrings

All test functions and classes have docstrings explaining what scenario is covered and any constraints:
```python
def test_request_hint_async_calls_engine_with_fen_and_time_ms(self):
    """Verifies that the async hint path passes the current FEN and time_ms to the engine."""
```

Cross-references in docstrings use `(ref: DL-001)` tags linking to design-decision records (informal, embedded in comments/docstrings throughout).

## Coverage

**Tool:** `pytest-cov` 7.0.0+
**HTML report:** `htmlcov/` (present in repo root, not committed to CI)
**Current overall coverage:** ~56% (visible in `htmlcov/index.html`)

No coverage threshold enforced in CI (`setup-test.yml` runs `pytest -v --tb=short` without `--cov`).

Individual module coverage varies:
- `openboard/exceptions.py` — high coverage (dedicated `test_exceptions.py`)
- `openboard/views/` — 0% coverage (wx GUI components not tested; require display)

## Test Types

**Unit Tests:**
- Scope: Single class/function with all dependencies mocked or replaced by fakes
- Files: `test_game.py`, `test_engine_adapter.py`, `test_settings.py`, `test_exceptions.py`, `test_board_state_terminal.py`, `test_keyboard_config.py`

**Integration Tests (mock engine, real threading):**
- Scope: Multiple cooperating classes; engine replaced by `MockEngine` but real asyncio event loops and threads run
- Files: `test_engine_adapter_integration.py`, `test_chess_controller.py`

**Integration Tests (real Stockfish):**
- Scope: Real engine process communication
- Files: `test_engine_adapter_integration.py` (selected tests), `test_game_opening_book_integration.py`
- Requires: Stockfish binary installed (CI installs via apt/brew/pwsh)

**Build Validation:**
- Scope: PyInstaller artifact checks
- Files: `test_build_validation.py`
- Requires: Configured build environment

## CI Test Execution

Tests run on a 3-OS matrix (ubuntu-latest, windows-latest, macos-latest) with `fail-fast: false`:
- Stockfish installed via `apt-get install stockfish` (Linux), `brew install stockfish` (macOS), direct download (Windows)
- Dependencies installed via `uv sync --frozen`
- Package import smoke test runs after pytest: `python -c "import openboard"`
- Defined in `.github/workflows/setup-test.yml`

---

*Testing analysis: 2026-04-27*

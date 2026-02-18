# OpenBoard Test Suite

## Testing Patterns

All test classes use `setup_method()` for fresh fixtures per test. External dependencies are isolated with `unittest.mock.Mock`. Blinker signals are captured via lambda connections rather than wx events, removing the GUI dependency from unit tests.

## Controller Test Strategy

Controller tests instantiate `ChessController` with a real `Game` and a `Mock(spec=EngineAdapter)`. No wx dependency is required. This keeps controller tests fast and deterministic while exercising the full controller-to-model boundary.

## Fixture Strategy

Shared FEN fixtures (stalemate, insufficient material) and mock factories live in `conftest.py`. Use these fixtures in any test requiring deterministic board positions rather than constructing positions inline.

## Duplicate Test Handling

`test_engine_adapter_simple.py` contains a subset of tests that overlap with `test_engine_adapter.py`. The canonical versions are in `test_engine_adapter.py`. The simple variant is retained for baseline coverage but new engine adapter tests belong in the canonical file.

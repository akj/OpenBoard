# Running tests

Install the locked environment with `uv sync --locked`, then run `uv run --no-sync pytest`.
On Linux, GUI tests need an X display. Use `xvfb-run -a uv run --no-sync pytest` on a headless machine.

The autouse fixtures in `conftest.py` give each test a temporary OpenBoard profile,
reset cached settings, and capture speech output. Tests must not use the real user profile
or contact a screen reader. Tests that need a different profile should use `tmp_path`.

Most model and controller tests run without displaying a window. The menu and board tests
exercise wx controls. Their assertions establish application behavior, not what NVDA,
VoiceOver, or another screen reader actually says. Live speech validation remains a
separate manual check.

For a focused run, pass a file or test name, for example
`uv run --no-sync pytest tests/test_board_state.py`.

CI also builds the executable and runs its `--self-test` startup smoke check. That check
loads bundled modules and makes a chess move without opening the GUI or speaking.

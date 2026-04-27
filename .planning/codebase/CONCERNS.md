# Codebase Concerns

**Analysis Date:** 2026-04-27

---

## Tech Debt

### Duplicate difficulty-resolution logic in Game model

- **Issue:** The difficulty configuration lookup block (matching `GameMode.HUMAN_VS_COMPUTER` / `COMPUTER_VS_COMPUTER`, reading difficulty config, getting FEN) is copy-pasted verbatim between `request_computer_move()` (sync) and `request_computer_move_async()` (async). The two methods differ only in whether they call `get_best_move()` or `get_best_move_async()`.
- **Files:** `openboard/models/game.py:279-363` and `openboard/models/game.py:366-463`
- **Impact:** Any change to difficulty handling, mode logic, or book-fallback behavior must be applied in two places. Both have been updated historically, but divergence is a latent risk.
- **Fix:** Extract the common preamble (mode validation, book lookup, difficulty resolution) into a private `_resolve_move_context()` helper and have both methods call it.

### Dead `_simple` API surface in EngineAdapter

- **Issue:** `EngineAdapter` exposes `start_simple()`, `stop_simple()`, `get_best_move_simple()`, `get_best_move_simple_async()`, and `_start_engine_simple()`. Every one of these is a thin alias that delegates to the non-simple counterpart. None are called from anywhere outside `engine_adapter.py` itself (confirmed by grep). `_start_engine_simple()` is defined but never invoked.
- **Files:** `openboard/engine/engine_adapter.py:799-881`
- **Impact:** ~85 lines of dead code that inflates cognitive load when reading or modifying the class.
- **Fix:** Delete the `_simple` family. Update any docstrings referring to them.

### `request_computer_move()` (synchronous path) is dead in production

- **Issue:** `Game.request_computer_move()` (the blocking, thread-freezing variant) is only called from tests. The view and controller exclusively use `request_computer_move_async()`. The sync method blocks the calling thread waiting on the engine.
- **Files:** `openboard/models/game.py:279`, tests only
- **Impact:** Confusing API surface; the sync path would freeze the GUI if accidentally called on the main thread. Tests using the sync path do not reflect actual production code paths.
- **Fix:** Either remove the sync method or clearly mark it `_test_only` / `@deprecated`. Update tests to use the async path.

### Hard-coded `"B"` keyboard shortcut conflict in view

- **Issue:** The Opening Book menu registers `"&Book Hint\tB"` as a menu accelerator, but the same `B` key is also dispatched as `KeyAction.REQUEST_BOOK_HINT` through the keyboard config system. Both bindings exist simultaneously, creating a double-fire risk.
- **Files:** `openboard/views/views.py:238`, `openboard/config/keyboard_config.py`
- **Impact:** Pressing `B` may trigger the action twice (once via menu accelerator, once via `EVT_CHAR_HOOK`).
- **Fix:** Remove the `\tB` tab-accelerator from the menu item and rely solely on the `EVT_CHAR_HOOK` system.

### `player_color` backward-compatibility attribute on Game

- **Issue:** `Game.new_game()` sets `self.player_color = self.config.human_color` at line 101 purely for "backward compatibility." The attribute is not referenced anywhere else in the codebase.
- **Files:** `openboard/models/game.py:101`
- **Impact:** Dead assignment misleads readers into thinking something consumes `player_color`.
- **Fix:** Remove the assignment (and search for any external consumers before doing so).

### Seven exception types defined but never raised or caught

- **Issue:** `exceptions.py` defines `EngineTimeoutError`, `EngineProcessError`, `DownloadError`, `AccessibilityError`, `DialogError`, `SettingsError`, `UIError`, `GameStateError`, and `NetworkError`. None are raised or caught anywhere outside `test_exceptions.py`.
- **Files:** `openboard/exceptions.py:70-188`
- **Impact:** The exception hierarchy looks complete but is misleading — callers catching `EngineTimeoutError` will never receive one; actual timeouts are wrapped in a bare `RuntimeError`.
- **Fix:** Either wire up these types in the places they logically belong, or prune the unused ones.

---

## Known Bugs

### `move_undone` signal lost after `new_game()`

- **Symptoms:** After calling `Game.new_game()`, pressing undo announces nothing (or fails silently) because `_on_model_undo` is no longer connected to the board.
- **Files:** `openboard/controllers/chess_controller.py:74`, `openboard/models/game.py:84-104`
- **Trigger:** Start a game, play moves, call "New Game" from the menu, then immediately press undo on the new game.
- **Root cause:** `ChessController.__init__` connects to `game.board_state.move_undone` once. `Game.new_game()` replaces `self.board_state` with a fresh `BoardState()` and re-hooks `move_made` and `status_changed` — but does **not** re-hook `move_undone`. The controller's handler is still attached to the old, discarded `BoardState`.
- **Workaround:** None currently.
- **Fix:** Either have `Game.new_game()` also reconnect `move_undone`, or have `Game` expose a forwarded signal (like it does for `move_made`) so the controller subscribes to `Game.move_undone` rather than `game.board_state.move_undone` directly.

### `_navigate_to_position` bypasses the model layer

- **Symptoms:** Navigating to a position in the move list (finished games / replay) calls `board.push(move)` directly on the `chess.Board` then manually fires `board_state.move_made` — bypassing `BoardState.make_move()`, skipping legality validation, and not emitting `status_changed`.
- **Files:** `openboard/views/views.py:673-688`
- **Trigger:** Open the move list dialog in a finished game and select a position.
- **Impact:** Board state can get out of sync with `BoardState._board`; game-over status is not re-evaluated; any future listener on `status_changed` is not notified.
- **Fix:** Move the navigation logic into `ChessController` or `Game`, using `BoardState.undo_move()` and `BoardState.make_move()` consistently.

### `announce_attacking_pieces` reports legal-move targets, not true attackers

- **Symptoms:** A piece that attacks a square but is pinned (its legal moves do not include that square) will not be reported. Conversely, the feature only reports pieces whose legal moves include the square — which is a subset of actual attackers.
- **Files:** `openboard/controllers/chess_controller.py:480-495`
- **Trigger:** Ask "what attacks this square?" when one of the attacking pieces is pinned.
- **Fix:** Use `chess.Board.attackers(color, square)` (the python-chess API) for each color instead of iterating `board.legal_moves`. This also removes the O(64 × legal_moves) iteration.

### `on_load_pgn` menu binding fires on every `wx.ID_ANY` event

- **Issue:** The PGN menu item is appended with `wx.ID_ANY` and immediately bound with `self.Bind(wx.EVT_MENU, self.on_load_pgn, id=wx.ID_ANY)`. Binding to `wx.ID_ANY` matches every menu event that does not have a more specific binding. This means `on_load_pgn` is the fallback handler for all uncaught menu events.
- **Files:** `openboard/views/views.py:207`, `openboard/views/views.py:250`
- **Trigger:** Any unhandled menu item click.
- **Fix:** Capture the menu item's ID at construction time and bind to it specifically:
  ```python
  pgn_item = file_menu.Append(wx.ID_ANY, "Load &PGN...\tCtrl-G")
  self.Bind(wx.EVT_MENU, self.on_load_pgn, id=pgn_item.GetId())
  ```

---

## Security Considerations

### Unauthenticated binary download over HTTPS with no integrity check

- **Risk:** `downloader.py` downloads Stockfish executables from GitHub releases using plain `urllib.request.urlopen`. There is no checksum or signature verification of the downloaded binary before it is extracted and executed.
- **Files:** `openboard/engine/downloader.py:106-149`, `openboard/engine/downloader.py:217-329`
- **Current mitigation:** HTTPS transport only (no certificate pinning). Content is extracted from a ZIP and the executable is placed at a known path.
- **Recommendations:** Verify SHA-256 checksums against the GitHub release's published hash file before extracting. Use `zipfile.ZipFile` with `ZipInfo.file_size` bounds checking to guard against zip-bomb extraction.

### ZIP extraction without path traversal check

- **Risk:** `extract_zip()` calls `zip_file.extractall(extract_to)` without validating member paths. A maliciously crafted ZIP could write files outside `extract_to` via `../` path components.
- **Files:** `openboard/engine/downloader.py:152-172`
- **Current mitigation:** Only ZIP files from GitHub releases are processed currently.
- **Recommendations:** Validate every `ZipInfo.filename` against the extract directory before extraction (check that `Path(extract_to / name).resolve()` starts with `Path(extract_to).resolve()`).

### No SSL context or certificate verification customization

- **Risk:** `urlopen` is used bare; on some Python builds and corporate environments, the default SSL context may not enforce certificate verification strictly. There is no explicit `ssl.create_default_context()` call.
- **Files:** `openboard/engine/downloader.py:62`, `openboard/engine/downloader.py:127`, `openboard/engine/downloader.py:244`
- **Recommendations:** Pass an explicit `ssl.create_default_context()` context to `urlopen` to ensure certificate validation is enforced.

### `engines_dir` and `config.json` resolved from `Path.cwd()`

- **Risk:** Engine install dir (`Path.cwd() / "engines"`) and app config (`open("config.json")` with a relative path) depend on the current working directory at startup. If the application is launched from an unexpected directory (e.g., a shortcut), it writes executables to the wrong location or silently uses default config.
- **Files:** `openboard/config/settings.py:44`, `openboard/engine/downloader.py:40`, `openboard/views/views.py:750`
- **Current mitigation:** Failure falls back to defaults for config; engine installation would simply write to the wrong directory.
- **Recommendations:** Use a platform-standard user data directory (e.g., `platformdirs.user_data_dir("openboard")`) instead of `Path.cwd()`.

---

## Performance Bottlenecks

### O(n) board replay on every move announcement

- **Issue:** `_format_move_announcement()` rebuilds the board from scratch by replaying all previous moves whenever `_pending_old_board` is `None`. `announce_last_move()` also replays the full move stack to build a "before" snapshot.
- **Files:** `openboard/controllers/chess_controller.py:598-606`, `openboard/controllers/chess_controller.py:528-535`
- **Impact:** For long games (50+ moves), this becomes noticeably slow. It fires on every move.
- **Fix:** The correct fix is to always pass `_pending_old_board` through every code path that triggers an announcement, eliminating the fallback replay. The `_pending_old_board` mechanism already exists for this purpose — the fallback path is an escape hatch that has become a crutch.

### O(64 × legal_moves) attacking-pieces computation

- **Issue:** `announce_attacking_pieces()` iterates all 64 squares, then for each non-empty square scans all legal moves to see if any land on the target square.
- **Files:** `openboard/controllers/chess_controller.py:480-495`
- **Impact:** Worst case ~1,700 move-object comparisons for a complex position, called synchronously on the UI thread.
- **Fix:** Replace with `board.attackers(chess.WHITE, square) | board.attackers(chess.BLACK, square)` — a single bitboard operation provided by python-chess.

### Board copy on every `BoardState.board` property access

- **Issue:** `BoardState.board` returns `self._board.copy()` on every call. Many methods call it multiple times in a loop or in rapid succession (e.g., all 64 squares in `on_paint`, navigation handlers).
- **Files:** `openboard/models/board_state.py:31-36`, `openboard/views/views.py:99-158`
- **Impact:** Unnecessary allocation on every paint event and every navigation key.
- **Fix:** Distinguish read-only inspection (caller gets the live reference, must not mutate) from cases where a stable snapshot is needed. Add a `board_ref` property returning the live `_board` for read-only callers and keep `.board` for snapshot use. Or document the contract and have callers request a copy only when they need one.

---

## Fragile Areas

### EngineAdapter thread/async lifecycle

- **Files:** `openboard/engine/engine_adapter.py` (881 lines)
- **Why fragile:** This file has received the most fix commits in the repository: thread-safety fixes, deadlock fixes, async resource leak fixes, race condition fixes, and shutdown sequence fixes — all in rapid succession. The current code has multiple overlapping shutdown paths (`stop()`, `astop()`, `_safe_cleanup()`, `_shutdown_engine_gracefully()`), inconsistent locking of `_active_futures` (added under lock but discarded without lock at line 464), and a `shutdown_monitor` coroutine that polls with `asyncio.sleep(0.1)` rather than using an async event.
- **Safe modification:** Always hold `_state_lock` when reading or writing `_active_futures`, `_engine`, `_loop`, or `_engine_thread`. Add tests that exercise concurrent `stop()` + in-flight `get_best_move_async()` calls.
- **Test coverage:** Integration tests exist but require a live Stockfish process.

### Computer move announcement double-path

- **Files:** `openboard/controllers/chess_controller.py:90-177`
- **Why fragile:** When the computer moves, three signal firings happen in order: `board_state.move_made` → `game.move_made` → `_on_model_move` (which skips announcement because `_computer_thinking` is set) → `computer_move_ready` → `_on_computer_move_ready` (which re-announces). This sequence depends on the order of signal dispatch and a shared boolean flag (`_computer_thinking`). The comment at line 177 acknowledges the fragility. A previous regression where captures were announced incorrectly was fixed specifically because of this path.
- **Safe modification:** Any change to computer move timing or signal ordering must be accompanied by tests that verify the announcement text for captures, en passant, castling, and promotion.
- **Test coverage:** `tests/test_chess_controller.py` has announcement tests, but they do not fully exercise the async computer-move flow.

### `_pending_old_board` shared mutable state

- **Files:** `openboard/controllers/chess_controller.py:64`, `openboard/controllers/chess_controller.py:535`, `openboard/controllers/chess_controller.py:544`, `openboard/controllers/chess_controller.py:163`
- **Why fragile:** `_pending_old_board` is a single instance variable used as a temporary context carrier between a move being made and its announcement. It is set and cleared in multiple places. If any code path raises an exception after setting but before clearing it, the stale board contaminates the next announcement. There is no thread-safety guarantee either — a rapid computer move could set it while the UI thread is reading it.
- **Safe modification:** Replace with a parameter-passing approach — pass the old board explicitly to `_format_move_announcement()` and eliminate the shared state.

### wxPython Linux index pinned to Ubuntu 24.04

- **Files:** `pyproject.toml:38-40`
- **Why fragile:** The wxPython Linux index is hardcoded to `ubuntu-24.04`. Any CI runner upgrade or deployment target running a different Ubuntu LTS (or non-Ubuntu Linux) will fail to resolve wxPython at install time.
- **Safe modification:** Add the `marker` properly to scope the index to only Ubuntu 24.04 environments, or pin to a self-hosted mirror that supports multiple Linux versions.

---

## Scaling Limits

### Computer vs Computer mode: no rate limiting or termination condition UI

- **Current behavior:** In `COMPUTER_VS_COMPUTER` mode, the engine fires move after move until game over. There is no UI control to pause or stop mid-game without closing the application. The `on_computer_thinking` handler in the view is a no-op (`pass`).
- **Files:** `openboard/views/views.py:597-600`, `openboard/controllers/chess_controller.py:113-118`
- **Limit:** A very long game (drawn positions, fifty-move rule) will run indefinitely with no way to interrupt other than closing the window.
- **Scaling path:** Add a "Stop" or "Pause" button wired to `controller._computer_thinking` and engine cancellation.

---

## Dependencies at Risk

### `accessible-output3` pinned to an unversioned git commit

- **Risk:** `pyproject.toml` installs `accessible-output3` directly from `https://github.com/SigmaNight/accessible_output3` with no tag or version pin beyond a lockfile commit hash (`fa8754da`). If the upstream repository is deleted, renamed, force-pushed, or goes private, all builds break.
- **Files:** `pyproject.toml:32`, `uv.lock:12`
- **Impact:** The core screen reader integration dependency has no stable release version and no published PyPI package.
- **Migration plan:** Fork the repository into the project's org, or vendor the wheel. At minimum, confirm the pinned commit hash is archived.

### wxPython Linux extra index URL is a single-distro unofficial mirror

- **Risk:** The wxPython Linux wheel is sourced from `https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-24.04/`, an unofficial mirror maintained by the wxPython project itself. If it goes offline or removes old versions, Linux builds fail completely.
- **Files:** `pyproject.toml:38-40`
- **Migration plan:** Mirror needed wheels to a project-controlled index or cache them in GitHub Actions artifacts.

---

## Missing Critical Features

### No promotion choice UI

- **Problem:** `Game.apply_move()` auto-promotes pawns to queens (`promotion = chess.QUEEN` default at line 133). There is no dialog or key-binding to let the player choose a promotion piece.
- **Files:** `openboard/models/game.py:128-134`
- **Blocks:** Underpromotion (promoting to knight, rook, or bishop) is impossible from the UI.

### No persistence of game state between sessions

- **Problem:** There is no save/load game feature beyond loading a FEN or PGN file. Closing the application always loses the current game.
- **Blocks:** Users cannot resume games across sessions.

---

## Test Coverage Gaps

### No tests for the views layer (GUI)

- **What is not tested:** `ChessFrame`, `BoardPanel`, `on_load_pgn`, `on_new_human_vs_computer`, `on_new_computer_vs_computer`, `_navigate_to_position`, `_format_move_for_speech`, menu binding correctness.
- **Files:** `openboard/views/views.py` (790 lines), `openboard/views/game_dialogs.py` (633 lines), `openboard/views/engine_dialogs.py` (337 lines)
- **Risk:** UI regressions (broken menus, layout issues, wrong signal subscriptions, the `wx.ID_ANY` bind bug) go undetected. The `_navigate_to_position` model-bypass bug described above has no test exposing it.
- **Priority:** High — the view layer contains the most complex wiring (signal subscriptions, keyboard dispatch, menu IDs) and no automated coverage.

### No test for `move_undone` signal after `new_game()`

- **What is not tested:** Calling `game.new_game()` then immediately calling `controller.undo()` to verify the announcement is correct and the undo is handled.
- **Files:** `openboard/controllers/chess_controller.py:74`, `openboard/models/game.py:84`
- **Risk:** The signal disconnection bug described above will not be caught by CI.
- **Priority:** High — this is an already-identified bug.

### Async computer-move announcement not fully tested end-to-end

- **What is not tested:** The announcement text emitted after an async computer move (especially captures and special moves) through the real `get_best_move_async` → callback → `_on_computer_move_ready` path. Existing tests mock the engine or use the synchronous path.
- **Files:** `tests/test_chess_controller.py`, `tests/test_game_async.py`
- **Risk:** The double-announcement path (the known-fragile area) is not covered by integration-level tests.
- **Priority:** Medium.

### No test for `announce_attacking_pieces` correctness

- **What is not tested:** The attacking-pieces feature with pinned pieces, positions where `board.attackers()` would differ from the legal-moves-based implementation.
- **Files:** `openboard/controllers/chess_controller.py:462-511`
- **Risk:** The functional bug (legal moves ≠ true attackers) is invisible to CI.
- **Priority:** Medium.

---

*Concerns audit: 2026-04-27*

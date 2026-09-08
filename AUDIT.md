# Revival audit

I audited the implementation and live dependency state. Historical planning files were not treated as specifications.

## Architecture decision

Keep the model, controller, and wx view separation. The app does not need an MVVM or framework migration to support more chess features. Its biggest problems were competing owners of mutable state and asynchronous work.

[Game](openboard/models/game.py) now owns engine request lifetimes. Each request belongs to one position, and changing that position cancels it. A late callback cannot apply a still-legal move to a new game. Duplicate computer requests cannot apply twice. [EngineAdapter](openboard/engine/engine_adapter.py) owns one UCI process and one worker loop. Both synchronous and asynchronous callers use that same lifecycle. Searches are serialized, bounded, and cancellable.

[ChessController](openboard/controllers/chess_controller.py) owns interaction state, including square focus, selection, and replay position. Controller and installer signals belong to their instances. Two windows no longer receive each other's events. Redundant engine lifecycles, unused factories, compatibility aliases, and duplicate default keyboard configuration were removed.

The boundaries still leave room for future features. Analysis can consume board snapshots with history. A future variation tree would need its own explicit data model, but adding one now would complicate the current linear replay without delivering a requested feature.

## Accessibility and interaction

The painted board originally depended on direct speech and exposed no individual squares to native accessibility clients. [BoardAccessible](openboard/views/board_accessibility.py) now represents all 64 squares using the controller's existing focus and selection. It provides names, roles, bounds, focus, selection, and an activation action. Empty squares use just their coordinates. Windows navigation uses native accessibility events; other platforms retain spoken navigation.

Startup publishes initial state after the frame subscribes. New games clear stale interaction state. Replay preserves a PGN's starting FEN and retains future moves when navigating backward. Promotion uses a chooser and restores board focus after the dialog. Engine startup and installation run on workers so the GUI can respond while they finish.

PGN imports reject unsupported variants before changing the current game or pending work. Undo in a computer game returns control to the human and preserves the computer's opening move until the human has made a move.

I used [Lichess's board rendering](https://github.com/lichess-org/lila/blob/master/ui/lib/src/nvui/render.ts) and [notification code](https://github.com/lichess-org/lila/blob/master/ui/lib/src/nvui/notify.ts) as a reference for separate, inspectable square semantics and event announcements. OpenBoard keeps its native wx interaction model.

[Keyboard configuration](openboard/config/keyboard_config.py) validates key names while loading. A malformed custom binding no longer waits until a key press to raise an error. The frame reads the user profile's override instead of a repository-relative copy that omitted the book-hint shortcut. Logs also respect the profile directory.

## Performance and correctness

[BoardState.load_pgn](openboard/models/board_state.py) parses a complete position before replacing the current board. It emits one update instead of an update and status calculation per imported move. A synthetic 200-ply game took a median 19.76 ms on the original implementation and 2.00 ms after the change, across five runs each on this Windows machine. Move notifications dropped from 200 to one. This measures model import, not rendering or overall app speed.

Move announcement snapshots omit unnecessary move history. Engine snapshots retain it because repetition affects analysis. [OpeningBook](openboard/models/opening_book.py) chooses the largest weight in one pass instead of sorting all entries. Loading an invalid replacement preserves the previous book, and closing an empty book releases its reader.

Automatic draw status now distinguishes fivefold repetition and the seventy-five-move rule from draws that a player must claim. Position validation stops invalid boards reaching the UCI process.

## Dependencies and engine installation

All seven open Renovate branches were integrated into `revive-openboard`, preserving their history. They cover development tools, GitHub Actions, lockfile maintenance, Pillow, platformdirs, Pydantic, and PyInstaller. Shared lockfile conflicts were resolved with uv. CairoSVG's additional update was still pending in Renovate's release checks.

[renovate.json](renovate.json) now looks up wxPython releases on PyPI while retaining uv's Linux wheel source. A custom manager tracks the uv version requirement. Renovate's configuration validator accepts the file. A hosted Renovate run against this changed configuration remains unverified. The Linux wheel server timed out during a later lock refresh; cached metadata allowed an offline refresh and installation on Windows.

[Stockfish 19](https://github.com/official-stockfish/Stockfish/releases/tag/sf_19) changed to universal binaries. The old downloader could not find them. [The repaired downloader](openboard/engine/downloader.py) selects the machine's architecture and verifies the release asset's SHA-256 digest. Downloads and extraction use temporary paths. Failed or truncated downloads preserve existing files. Installation prepares the executable and metadata together before replacing the previous installation, restores it on failure, and retains a recovery copy if restoration also fails. The installer stops a running engine before replacement and restarts it afterward. Local engine status no longer makes a network request.

## Tests and builds

The original updated-dependency baseline had 377 passing tests, seven failures, and two skips. The failures came from source-name bans implemented with an external `grep` command. Other tests asserted that historical planning documents contained particular phrases or tested arithmetic unrelated to engine behavior. Those were removed.

The replacement tests exercise late results, cancellation, actual worker-loop ownership, UCI history transmission, PGN state transitions, real Polyglot data, real ZIP extraction, and native Windows accessibility. Tests use temporary profiles and capture app speech.

CI also exercises an installed Stockfish process. The test sends a search, cancels a second search after the UCI command reaches the engine, searches again, and checks that shutdown closes the process and worker.

The old build validator checked file size and permissions without running the executable. [The new validator](.build/validation/verify_build.py) launches the source or packaged app with `--self-test`, checks a structured result, and enforces a timeout. A packaged run uses a temporary working directory without the source checkout on its import path. This is a startup smoke check, not a complete UI test.

Build fixes include an installable Python package and console entry point, frozen dependency use, Linux Xvfb, current Stockfish assets in CI, correct Windows archive layout, accurate architecture labels, and installer failures that fail the build. Duplicate caches and speculative PyInstaller hooks were removed.

The speech library omitted dependencies it loads when creating its outputs. Linux builds now include the system Speech Dispatcher Python binding. macOS installs appscript for VoiceOver. Platform startup checks import those bindings without creating a speech client. Installer fixes also give DEB files root ownership, use LF for Linux scripts, and remove file associations that the application could not open.

The workflow set now has two files. [CI](.github/workflows/ci.yml) runs lint, type checks, and tests on Windows, macOS, and Linux before packaging. It extracts each portable archive and runs the executable outside the checkout. [Release](.github/workflows/release.yml) verifies the version tag and reuses CI with every platform installer required. Publication happens only after those jobs pass, with checksums for the downloadable files. Manual CI runs can exercise installer creation without publishing.

## Verification limits

The Windows test suite passed with 391 tests and two platform-specific skips. Ruff lint and formatting, ty, and actionlint passed. A real Stockfish 19 download, checksum verification, searches, cancellation, and clean subprocess shutdown passed in an isolated profile. A Windows PyInstaller build passed its startup smoke check outside the checkout. Native Windows IAccessible calls verified the board's accessible objects and exposed callback errors that mock tests missed.

Actual NVDA speech, braille presentation, and complete game interaction still need a screen reader pass. No live NVDA or audio settings were changed. The PR's CI results provide the platform test and packaging evidence. Installer creation does not establish the installed application's full user flow.

For the screen reader pass, check square navigation and selection, normal and capturing moves, promotion and focus return, replay from a nonstandard starting position, hints after undo, and closing during engine startup. Check for duplicate announcements as well as missing ones. Keyboard operation and spoken output need to agree with the native focused square.

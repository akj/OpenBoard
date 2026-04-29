# OpenBoard

## What This Is

OpenBoard is an accessible, cross-platform desktop chess GUI with keyboard-first
navigation and screen-reader support, designed primarily for blind and
visually-impaired players but equally usable for sighted players who prefer
keyboard control. The app already plays chess against Stockfish, supports
PGN replay and opening books, and ships installers for Windows, macOS, and
Linux. This milestone is a **Foundation & Polish** pass that fixes documented
bugs, adds save/load and clock infrastructure, layers in sound and visual
accessibility, and improves keyboard / announcement controls — so the app is
demo-able to a blind user with no apologies before deeper features are added.

## Core Value

Blind and visually-impaired players can play full chess games independently —
every state change is reliably announced or felt, with no missing or wrong
information.

## Requirements

### Validated

<!-- Shipped capabilities inferred from existing code (see .planning/codebase/) -->

- ✓ Keyboard-first board navigation (arrows + space + shortcuts) — existing
- ✓ Screen-reader move announcements via accessible_output3 — existing
- ✓ Brief and verbose announcement modes (global toggle) — existing
- ✓ Play vs Stockfish with four difficulty levels — existing
- ✓ Human vs Human and Computer vs Computer modes — existing
- ✓ Polyglot opening-book move hints — existing
- ✓ PGN load and forward / backward replay — existing
- ✓ Stockfish auto-detection and bundled install / update — existing
- ✓ JSON-driven keyboard configuration — existing
- ✓ Cross-platform builds (Windows .exe, macOS .dmg, Linux .deb / .rpm) — existing
- ✓ Engine-optional startup (app launches and functions without Stockfish) — existing
- ✓ Tech debt cleanup — every bug and tech-debt item from `.planning/codebase/CONCERNS.md` fixed; structural patterns (signal forwarders, model-routed navigation, `platformdirs` persistence, specific menu IDs, `move_made(old_board, move_kind)` payload, typed exception hierarchy) established. *Validated in Phase 1.*

### Active

<!-- v1: Foundation & Polish. Each bullet expands into REQ-IDs in REQUIREMENTS.md. -->
- [ ] PGN save and load (game with headers, time, result; load any standard .pgn)
- [ ] FEN save and load (current position; setup-from-FEN entry point)
- [ ] Auto-save in-progress game so it survives a restart (crash recovery)
- [ ] Clock infrastructure — time-control selection, decrementing clocks per side, low-time threshold, screen-reader callouts of remaining time, clocks-off option
- [ ] Sound layer — move SFX (own / opponent / capture / check / castle), turn alerts, clock ticking under low time, per-category on/off + volume controls, settings persisted
- [ ] High-contrast board / piece theme (toggleable for low-vision users)
- [ ] Adjustable piece / board scale (configurable for low-vision users)
- [ ] In-app key-rebinding settings UI (currently only `keyboard_config.json`)
- [ ] Per-event announcement verbosity tiers (beyond the global brief / verbose toggle)

### Out of Scope

<!-- Explicit boundaries — these will not be added to any future milestone. -->

- Mobile or web ports — desktop wxPython only; no React Native, no Electron, no PWA.
- Peer-to-peer or custom-server multiplayer — online play (v4) is via Lichess API only.
- Voice command input — keyboard-in / TTS-out model is preserved by design.
- Proprietary engine integration — UCI standard only; no Houdini / Komodo / proprietary protocols.
- Adjustable UI font size for menus and dialogs — deferred indefinitely (rely on OS-level scaling).
- Focus-indicator audit beyond what already exists — deferred indefinitely.
- Game-library browser, opening-book browser, full Stockfish analysis (live PV / multi-PV / post-game review), chess puzzles, Lichess online play — **deferred to v2 / v3 / v4**, not out of scope. Tracked in `REQUIREMENTS.md` under v2 Requirements.

## Context

- **Origin:** Existing accessibility-first chess GUI; README, installers, and CI are already in place. This is not a greenfield project.
- **Codebase map:** `.planning/codebase/` was generated 2026-04-27 and contains ARCHITECTURE, STACK, STRUCTURE, CONVENTIONS, INTEGRATIONS, TESTING, and CONCERNS docs. Planning agents should read those before phase work.
- **Known correctness debt:** `CONCERNS.md` lists 8 bugs and 6 tech-debt items. Several are accessibility-correctness bugs (e.g. `move_undone` signal lost after `new_game()`, `_navigate_to_position` bypassing the model layer, `announce_attacking_pieces` reporting legal-move targets instead of true attackers). For a screen-reader user, wrong information is worse than no information — these are ethical priorities, not nice-to-haves.
- **Architecture model:** wxPython MVC with `blinker` signal-based decoupling. Engine runs an asyncio loop on a background thread; results marshal back to the main thread via `wx.CallAfter` (`WxCallbackExecutor`). New work must respect these boundaries.
- **Primary user (right now):** the project author, who dogfoods the app. Secondary users: blind / visually-impaired chess players. v1 is correctness-focused for both.
- **Done feels like:** a blind player can sit down and play a full timed game with sound, correct announcements, save / load, and no apologies — that is the v1 acceptance bar.

## Constraints

- **Tech stack**: Python 3.12+, wxPython, python-chess, blinker, accessible_output3 — preserved. No new GUI toolkits; no rewrites.
- **Engine**: Stockfish remains optional. App must start and function without an engine. All engine-dependent code paths must guard `Game.engine_adapter is None`.
- **Threading model**: One wxPython main thread for UI and signal handling. Engine runs asyncio on one daemon background thread. All engine callbacks marshal back to main thread via `wx.CallAfter`. Do not regress this model.
- **Cross-platform**: All v1 features must work on Windows, macOS, and Linux. Platform-specific shortcuts (e.g. Cmd vs Ctrl) are acceptable, but no feature may be Windows-only or macOS-only.
- **Timeline**: No hard deadline. Quality over speed; ship when v1 is demo-able to a blind user without caveats.
- **Type checker**: `ty` (not pyright). Lint and CI workflows are already configured for it.

## Key Decisions

<!-- Significant choices made during initialization. Add new entries as decisions accrue. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 4-milestone roadmap: Foundation → Engine/Analysis → Puzzles → Online Play | Sequence by dependency, risk, and per-milestone shippable value. Each milestone ships independently. | — Pending |
| v1 prioritizes correctness and foundation over new headline features | Accessibility-first product; existing bugs mislead screen-reader users. Stable substrate unlocks ambitious later milestones. | — Pending |
| Build clock infrastructure in v1, not v4 | Online play (v4) inherits clocks, so spec'ing them now removes a v4 unknown; clocks-off remains a user option. | — Pending |
| PGN / FEN save and load in v1 | Substrate for v2 saved-game library, v3 puzzle import, v4 game-archive sync. Pull forward to avoid three later re-designs. | — Pending |
| Saved-game library browser deferred to v2 | Pulling it forward would inflate v1 with mostly-UI list work; storage format is settled in v1, browser builds on top. | — Pending |
| Lichess as the only online integration target (when v4 lands) | Open API, permissive licensing, alignment with accessibility ethos. Excludes peer-to-peer, custom servers, chess.com proprietary surfaces. | — Pending |
| Type checker is `ty`, not pyright | Switched in commit 682e7f4; CI lint workflow updated to match. | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-29 after Phase 1 completion*

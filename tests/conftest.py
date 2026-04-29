"""Shared pytest fixtures for OpenBoard tests.

Centralizes FEN position constants and mock factories used across multiple
test modules. Adding fixtures here propagates them to all test files without
duplication.
"""

from pathlib import Path

import pytest


@pytest.fixture
def stalemate_fen() -> str:
    """FEN for a stalemate position: black king on a8 stalemated by white queen and king."""
    return "k7/2Q5/2K5/8/8/8/8/8 b - - 0 1"


@pytest.fixture
def insufficient_material_fen() -> str:
    """FEN for a draw by insufficient material: kings only."""
    return "4k3/8/8/8/8/8/8/4K3 w - - 0 1"


@pytest.fixture
def pinned_attacker_fen() -> str:
    """Canonical TD-04 attacker FEN — single source of truth for Plans 01 and 03.

    FEN: `4r3/8/8/8/8/8/8/4K3 w - - 0 1`
    Position: black rook on e8, white king on e1, white to move.

    Demonstrates the legal_moves-vs-attackers() distinction cleanly:
    - chess.Board.attackers(chess.BLACK, chess.E1) returns {chess.E8} (correct).
    - The OLD legal_moves-filtered loop misses the rook because it is white-to-move
      and black's moves are not in legal_moves.
    Used by:
    - Plan 01 (this plan): co-locates the FEN with the fixture for early validation.
    - Plan 03 (TestAnnounceAttackingPieces): the TD-04 regression test reads this fixture.

    Do NOT redefine elsewhere; do NOT change without updating both plans' must_haves.
    """
    return "4r3/8/8/8/8/8/8/4K3 w - - 0 1"


@pytest.fixture
def pre_scholars_mate_fen() -> str:
    """FEN where white-to-move Qxf7# delivers MoveKind.CAPTURE | CHECK | CHECKMATE.

    Setup: r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4
    After Qxf7#: white queen captures pawn on f7, black king on e8 is mated.
    Used by TD-02 capture+check+checkmate test.
    """
    return "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"


@pytest.fixture
def quiet_check_fen() -> str:
    """FEN where white-to-move Qd1-h5 delivers MoveKind.CHECK without CAPTURE.

    Setup: 4k3/8/8/8/8/8/PPPP1PPP/RNBQKBNR w KQ - 0 1
    Black king on e8, white queen on d1. Qh5+ checks the king via the h5-e8 diagonal.
    Used to verify CHECK bit set, CAPTURE bit clear.

    Note: The plan's original FEN (rnbqkbnr/ppp2ppp/8/3pp3/2B1P3/8/PPPP1PPP/RNBQK1NR)
    does NOT deliver check after Qh5. This corrected FEN is used instead.
    """
    return "4k3/8/8/8/8/8/PPPP1PPP/RNBQKBNR w KQ - 0 1"


@pytest.fixture
def isolated_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect platformdirs lookups to an isolated tmp_path via OPENBOARD_PROFILE_DIR.

    Used by every Plan-04 test that touches paths.py, migration.py, or settings.py.
    monkeypatch auto-cleans the env var so tests do not leak across the session.
    (RESEARCH.md Pitfall 6 / D-09)
    """
    monkeypatch.setenv("OPENBOARD_PROFILE_DIR", str(tmp_path))
    return tmp_path

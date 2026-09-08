"""Shared positions and isolation for tests."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def isolated_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Keep settings, engines and autosaves inside a temporary profile."""
    from openboard.config import settings

    monkeypatch.setenv("OPENBOARD_PROFILE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "_settings", None)
    return tmp_path


@pytest.fixture(autouse=True)
def speech_output(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Capture announcements without contacting the user's screen reader."""
    from accessible_output3.outputs import auto

    output = MagicMock()
    monkeypatch.setattr(auto, "Auto", lambda: output)
    return output


@pytest.fixture
def stalemate_fen() -> str:
    """Black has no legal move and is not in check."""
    return "k7/2Q5/2K5/8/8/8/8/8 b - - 0 1"


@pytest.fixture
def insufficient_material_fen() -> str:
    """Only the kings remain."""
    return "4k3/8/8/8/8/8/8/4K3 w - - 0 1"


@pytest.fixture
def pinned_attacker_fen() -> str:
    """The black rook attacks e1 even though white is to move."""
    return "4r3/8/8/8/8/8/8/4K3 w - - 0 1"


@pytest.fixture
def pre_scholars_mate_fen() -> str:
    """White can play Qxf7#, a capture that delivers checkmate."""
    return "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"


@pytest.fixture
def quiet_check_fen() -> str:
    """White can play Qh5+, giving check without a capture."""
    return "4k3/8/8/8/8/8/PPPP1PPP/RNBQKBNR w KQ - 0 1"

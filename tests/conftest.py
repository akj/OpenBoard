"""Shared pytest fixtures for OpenBoard tests.

Centralizes FEN position constants and mock factories used across multiple
test modules. Adding fixtures here propagates them to all test files without
duplication.
"""

import pytest


@pytest.fixture
def stalemate_fen() -> str:
    """FEN for a stalemate position: black king on a8 stalemated by white queen and king."""
    return "k7/2Q5/2K5/8/8/8/8/8 b - - 0 1"


@pytest.fixture
def insufficient_material_fen() -> str:
    """FEN for a draw by insufficient material: kings only."""
    return "4k3/8/8/8/8/8/8/4K3 w - - 0 1"

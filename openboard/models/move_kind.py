"""MoveKind IntFlag for composable move-attribute bits.

Used as a kwarg on Game.move_made signal payloads (D-01 / D-02). Multiple
bits may be set simultaneously: a capture-with-check yields
MoveKind.CAPTURE | MoveKind.CHECK. Subscribers test bits independently:

    if MoveKind.CAPTURE in move_kind: ...
    if MoveKind.CHECK in move_kind: ...
"""

import enum


class MoveKind(enum.IntFlag):
    """Composable bits describing the kind of move just made."""

    QUIET = 0
    CAPTURE = 1 << 0
    CASTLE = 1 << 1
    EN_PASSANT = 1 << 2
    PROMOTION = 1 << 3
    CHECK = 1 << 4
    CHECKMATE = 1 << 5

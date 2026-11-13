# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Frames and units of a board (capability python-api, "Frames and units"; change c0500; ``docs/api.md``,
"Frames and units").

Three frames: ``native`` (an Altium document's records: 1/10 000 mil, Y up, Altium's absolute zero),
``model`` (``Design``, ``check``, ``net``, ``analyze``: nanometres, Y down, the native zero) and ``board``
(the Altium editor and the edit sessions: nanometres from the board origin, Y up). ``board_frame`` gives the
conversions of one board; no conversion uses a float. Nothing is written and no process is started.
"""

from __future__ import annotations

from dataclasses import dataclass

from fenolite.api.board import Board, BoardInput, read_board
from fenolite.api.sides import SideUsageError
from fenolite.core.coords import Point
from fenolite.core.units import format_length, nm_to_u, parse_length, u_to_nm

altium_to_nm = u_to_nm
"""Altium units (1/10 000 mil) in nanometres, ``core.units.u_to_nm``."""
nm_to_altium = nm_to_u
"""Nanometres in Altium units, half to even, ``core.units.nm_to_u``."""


@dataclass(frozen=True, slots=True)
class Frame:
    """The frames of one board: ``origin`` is the board origin in the model frame and ``y_up`` whether the
    board frame's Y points up (an Altium board); ``native`` whether the board has native units."""

    origin: Point
    y_up: bool
    native: bool = False

    def _native(self) -> None:
        if not self.native:
            raise SideUsageError("the board has no native unit to convert", hint="an Altium .PcbDoc has one")

    def from_native(self, x: int, y: int) -> Point:
        """Native units of a record to the model frame (Y negated, no origin subtracted)."""
        self._native()
        return Point(u_to_nm(x), -u_to_nm(y))

    def to_native(self, p: Point) -> tuple[int, int]:
        """A model point to native units, half to even."""
        self._native()
        return nm_to_u(p.x), nm_to_u(-p.y)

    def to_board(self, p: Point) -> Point:
        """A model point in the board frame; the identity when the board frame is the model frame."""
        if not self.y_up:
            return p
        return Point(p.x - self.origin.x, self.origin.y - p.y)

    def from_board(self, p: Point) -> Point:
        """A board-frame point in the model frame."""
        if not self.y_up:
            return p
        return Point(p.x + self.origin.x, self.origin.y - p.y)


def board_frame(board: BoardInput) -> Frame:
    """The ``Frame`` of a ``Board`` or the board at a path: an Altium board's origin
    (``backends.altium.frame.board_origin``) with Y up; (0, 0) and the model frame for any other backend."""
    read = board if isinstance(board, Board) else read_board(board)
    if read.backend != "altium":
        return Frame(Point(0, 0), False)
    from fenolite.backends.altium.frame import board_origin

    return Frame(board_origin(read.design), True, True)


__all__ = ["Frame", "altium_to_nm", "board_frame", "format_length", "nm_to_altium", "parse_length"]

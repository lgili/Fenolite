# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the view commands ``net``, ``region`` and ``neighbors`` share: reading the board with its
board-frame records, lengths with units, and records as JSON (change c0066)."""

from __future__ import annotations

import dataclasses
import difflib
import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from fenolite.backends import registry
from fenolite.backends.base import BoardFrame, BoardPad, PlacedExtent
from fenolite.backends.kicad import frame
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.cli.api import Context
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.core.units import Nm, parse_length
from fenolite.geometry import BBox
from fenolite.model.design import Design

UNIT_HINT = "lengths need a unit: 12mm"


@dataclass(frozen=True, slots=True)
class BoardView:
    """A board read for a view: the design, its board-frame records, the issues of both readings (the
    ``model.*`` findings left out, as ``inspect`` does), the combined evidence and the input."""

    design: Design
    pads: tuple[BoardPad, ...]
    extents: tuple[PlacedExtent, ...]
    issues: tuple[Issue, ...]
    evidence: Evidence
    input: InputRef


def load_board(given: str, ctx: Context) -> BoardView:
    """The board that ``given`` names (a board file, a project file or a project folder)."""
    source = Path(given)
    board = resolve_board(source if source.is_absolute() else ctx.cwd / source)
    backend = registry.for_path(board)
    if backend is None or not isinstance(backend, BoardFrame):
        raise CliError("FEN-2001", f"no backend gives the board frame of {board.name}", where=board.name)
    found: list[Issue] = []
    read = backend.read(board, issues=found)
    design = read.content
    if not isinstance(design, Design) or design.board is None:
        raise CliError("FEN-2001", f"{board.name} is not a board", hint="pass a board file", where=board.name)
    pads = backend.board_pads(design, issues=found)
    extents = backend.placed_extents(design, issues=found)
    return BoardView(
        design=design,
        pads=pads,
        extents=extents,
        issues=tuple(dict.fromkeys(found)),
        evidence=Evidence.combine(read.evidence, frame.EVIDENCE),
        input=InputRef(
            path=board.name,
            sha256=hashlib.sha256(board.read_bytes()).hexdigest(),
            kind="kicad_pcb",
            format_version=None,
        ),
    )


def length(text: str, option: str) -> Nm:
    """A length with its unit, or ``FEN-2001`` naming the option."""
    try:
        return parse_length(text.strip())
    except ValueError as error:
        raise CliError("FEN-2001", f"{option}: {error}", where=option, hint=UNIT_HINT) from None


def closest(name: str, known: Iterable[str]) -> str:
    """A hint that names the three known names closest to ``name``."""
    names = sorted(set(known))
    close = difflib.get_close_matches(name, names, n=3, cutoff=0.4)
    if not close:  # a short name such as a net of two letters: compare without the case
        lowered = {n.lower(): n for n in names}
        close = [
            lowered[m] for m in difflib.get_close_matches(name.lower(), sorted(lowered), n=3, cutoff=0.4)
        ]
    return f"did you mean: {', '.join(close)}" if close else "no name is close to it"


def to_json(value: Any) -> Any:
    """A record, a box or a point as JSON data, with the field names of the records."""
    if isinstance(value, Point):
        return {"x": value.x, "y": value.y}
    if isinstance(value, BBox):
        return {"x0": value.x0, "y0": value.y0, "x1": value.x1, "y1": value.y1}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_json(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (tuple, list)):
        return [to_json(item) for item in cast(Sequence[Any], value)]
    return value


__all__ = ["UNIT_HINT", "BoardView", "closest", "length", "load_board", "to_json"]

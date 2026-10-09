# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Where the blocks of a drawing go, and on which paper (capability manufacturing-exports, "Drawing page
layout"; change c0117; user guide ``docs/drawings.md``).

A page is plotted at 1:1 and the board stays where the board file puts it, so page coordinates are board
coordinates (``H-K-DRAW-PAGE``). A block takes the first free corner beside the sheet's obstacles, the
board box and the blocks placed before it. The functions are pure and deterministic; the caller gives
the obstacles of the drawing sheet as rectangles, so this module needs no drawing-sheet code.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.core.units import Nm
from fenolite.exports.drawing_tables import Block
from fenolite.model.presentation import PAPER_SIZES

Box = tuple[Nm, Nm, Nm, Nm]
"""A rectangle: left, top, right, bottom (y grows downwards, as on the page)."""
AUTO_PAPERS: Mapping[str, tuple[Nm, Nm]] = MappingProxyType(
    {
        "A4": (297_002_200, 210_007_200),
        "A3": (419_989_000, 297_002_200),
        "A2": (594_004_400, 419_989_000),
        "A1": (840_994_000, 594_004_400),
        "A0": (1_188_999_400, 840_994_000),
    }
)
"""The papers ``auto`` tries, smallest first, with the landscape page size KiCad plots for each
(``H-K-PCB-PAPER`` for A4 and A3, ``H-K-DRAW-SHEET`` for A2 to A0): a whole number of mils per side."""
BOARD = "board box"
"""The name ``NoRoom.what`` gives the board box, which no block has."""


@dataclass(frozen=True, slots=True)
class Obstacles:
    """What a drawing sheet takes of a page: ``margin`` is the box content must lie in, ``boxes`` are
    the rectangles content must stay away from."""

    margin: Box
    boxes: tuple[Box, ...] = ()


@dataclass(frozen=True, slots=True)
class Placed:
    """A block on a page: its name, its top-left corner and its size."""

    name: str
    at: tuple[Nm, Nm]
    size: tuple[Nm, Nm]

    @property
    def box(self) -> Box:
        return (self.at[0], self.at[1], self.at[0] + self.size[0], self.at[1] + self.size[1])


@dataclass(frozen=True, slots=True)
class NoRoom:
    """What did not fit a page: the board box or a block (``what``), its box when it has one, and the
    smallest paper of ``AUTO_PAPERS`` that holds everything (``""`` when none does)."""

    what: str
    box: Box | None
    smallest: str


@dataclass(frozen=True, slots=True)
class PageLayout:
    """A page laid out: its paper, orientation and size, the board box, the placed blocks, and
    ``problem`` when the page does not hold its content (the blocks are then not placed)."""

    paper: str
    portrait: bool
    size: tuple[Nm, Nm]
    board_box: Box | None
    placed: tuple[Placed, ...] = ()
    problem: NoRoom | None = None


def join(*boxes: Box | None) -> Box | None:
    """The bounding box of the boxes that are not ``None``."""
    found = [box for box in boxes if box is not None]
    if not found:
        return None
    return (
        min(box[0] for box in found),
        min(box[1] for box in found),
        max(box[2] for box in found),
        max(box[3] for box in found),
    )


def mirror(box: Box, width: Nm) -> Box:
    """``box`` mirrored by x ↦ ``width`` − x, as ``--mirror`` plots it on a page ``width`` wide."""
    return (width - box[2], box[1], width - box[0], box[3])


def inside(box: Box, margin: Box) -> bool:
    return margin[0] <= box[0] and margin[1] <= box[1] and box[2] <= margin[2] and box[3] <= margin[3]


def apart(a: Box, b: Box, gap: Nm) -> bool:
    """Whether ``a`` and ``b`` are at least ``gap`` from each other along x or along y."""
    return a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1]


def page_size(paper: str, portrait: bool = False) -> tuple[Nm, Nm]:
    """Width and height of a page as KiCad plots it, where measured, else the nominal size."""
    if paper in AUTO_PAPERS:
        width, height = AUTO_PAPERS[paper]
    else:
        short, long = PAPER_SIZES[paper]
        width, height = long, short
    return (height, width) if portrait else (width, height)


def place(
    blocks: Sequence[Block],
    *,
    page: tuple[Nm, Nm],
    board_box: Box | None,
    obstacles: Obstacles,
    gap: Nm,
    fixed: Mapping[str, tuple[Nm, Nm]] | None = None,
) -> tuple[tuple[Placed, ...], str]:
    """The blocks placed in their order, and the name of the first thing that found no room (``""``
    when everything is placed; ``BOARD`` when the board box itself does not fit).

    The board box must lie in the margin box, ``gap`` from every obstacle. A block takes the first
    top-left corner, in the order of x then y, among the margin box's left edge and the right edges of
    every obstacle, of the board box and of every placed block plus ``gap``, and the margin box's top
    edge and the bottom edges of the same boxes plus ``gap``, at which it lies in the margin box and is
    at least ``gap`` from all of them. A block named in ``fixed`` takes that corner under the same
    conditions."""
    del page  # the margin box and the obstacles already hold what the page size decides
    margin = obstacles.margin
    taken: list[Box] = list(obstacles.boxes)
    if board_box is not None:
        if not inside(board_box, margin) or not all(apart(board_box, box, gap) for box in taken):
            return (), BOARD
        taken.append(board_box)
    wanted = fixed or {}
    placed: list[Placed] = []
    for block in blocks:
        width, height = block.size

        def free(x: Nm, y: Nm, width: Nm = width, height: Nm = height) -> bool:
            box = (x, y, x + width, y + height)
            return inside(box, margin) and all(apart(box, other, gap) for other in taken)

        corner: tuple[Nm, Nm] | None = None
        if block.name in wanted:
            corner = wanted[block.name] if free(*wanted[block.name]) else None
        else:
            xs = sorted({margin[0], *(box[2] + gap for box in taken)})
            ys = sorted({margin[1], *(box[3] + gap for box in taken)})
            corner = next(((x, y) for x in xs for y in ys if free(x, y)), None)
        if corner is None:
            return tuple(placed), block.name
        found = Placed(block.name, corner, (width, height))
        placed.append(found)
        taken.append(found.box)
    return tuple(placed), ""


def choose_paper(
    blocks: Sequence[Block],
    *,
    paper: str,
    portrait: bool = False,
    board_box: Callable[[Nm], Box | None],
    obstacles: Callable[[Nm, Nm], Obstacles],
    gap: Nm,
    fixed: Mapping[str, tuple[Nm, Nm]] | None = None,
) -> PageLayout:
    """The layout of a page on ``paper``, or with ``auto`` on the first of ``AUTO_PAPERS`` that holds
    the board box and every block. ``board_box(width)`` is the page's board box on a page that wide (a
    mirrored page depends on it) and ``obstacles(width, height)`` what the sheet takes of such a page.
    When nothing fits, ``problem`` names what did not and the smallest paper that holds everything."""

    def attempt(name: str, upright: bool) -> tuple[PageLayout, str, Box | None]:
        size = page_size(name, upright)
        box = board_box(size[0])
        sheet = obstacles(*size)
        placed, missing = place(blocks, page=size, board_box=box, obstacles=sheet, gap=gap, fixed=fixed)
        failed: Box | None = box
        if missing not in ("", BOARD):
            block = next(b for b in blocks if b.name == missing)
            corner = (fixed or {}).get(missing)
            failed = None if corner is None else (*corner, corner[0] + block.width, corner[1] + block.height)
        return PageLayout(name, upright, size, box, placed), missing, failed

    if paper != "auto":
        layout, missing, failed = attempt(paper, portrait)
        if not missing:
            return layout
        smallest = next((name for name in AUTO_PAPERS if not attempt(name, False)[1]), "")
        problem = NoRoom(missing, failed, smallest)
        return PageLayout(paper, portrait, layout.size, layout.board_box, problem=problem)
    first: tuple[PageLayout, str, Box | None] | None = None
    for name in AUTO_PAPERS:
        found = attempt(name, False)
        if not found[1]:
            return found[0]
        first = first or found
    assert first is not None
    layout, missing, failed = first
    problem = NoRoom(missing, failed, "")
    return PageLayout(layout.paper, False, layout.size, layout.board_box, problem=problem)


__all__ = [
    "AUTO_PAPERS",
    "BOARD",
    "Box",
    "NoRoom",
    "Obstacles",
    "PageLayout",
    "Placed",
    "apart",
    "choose_paper",
    "inside",
    "join",
    "mirror",
    "page_size",
    "place",
]

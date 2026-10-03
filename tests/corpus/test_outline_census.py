# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Do the corpus outlines chain into closed rings by exact endpoint equality? (capability
kicad-file-backend, "Edge.Cuts outlines chain exactly"; ``H-G-EDGE-EXACT``; change c0020).

A measurement that answers c0005's open question on a snapping tolerance for ``assemble_rings``: it never
fails on an outcome, and records counts per origin through ``census`` for
``docs/evidence/kicad-board-read.md``.
"""

from __future__ import annotations

import dataclasses

import pytest
from _boardcorpus import READABLE_ITEMS, census_outline, entry, outline_outcome
from _boards import FIXTURE, census
from _corpus import require

from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.board import Graphic


@pytest.mark.needs_corpus
def test_edge_cuts_chain() -> None:
    items = [i for i in READABLE_ITEMS if i.path.is_file() and not i.heavy]
    if not items:
        require(READABLE_ITEMS[0])  # skips, or fails in required-resource mode
    counts = census_outline(entry(i) for i in items)
    census("outline", "native", counts)
    assert sum(c["boards"] for c in counts.values()) == len(items)  # every board was measured


def _square(gap_nm: int) -> tuple[Graphic, ...]:
    """Four edge lines of a 10 mm square, the last end moved ``gap_nm`` away from the first start."""
    corners = [Point(0, 0), Point(10_000_000, 0), Point(10_000_000, 10_000_000), Point(0, 10_000_000)]
    ends = [*corners[1:], Point(gap_nm, 0)]
    return tuple(
        Graphic(id=derived_id("gfx", "outline", str(n)), kind="line", layer="Edge.Cuts", points=(a, b))
        for n, (a, b) in enumerate(zip(corners, ends, strict=True))
    )


def test_gap() -> None:
    design = read_board(FIXTURE.read_text(encoding="utf-8"), file=FIXTURE.name)
    assert design.board is not None

    def with_edges(graphics: tuple[Graphic, ...]) -> dict[str, object]:
        board = dataclasses.replace(design.board, graphics=graphics)  # type: ignore[arg-type]
        return outline_outcome(dataclasses.replace(design, board=board))

    assert with_edges(_square(0)) == {
        "pieces": 4, "circles": 0, "zero_length": 0, "result": "chained", "rings": 1,
    }  # fmt: skip
    open_by_500 = with_edges(_square(500))
    assert open_by_500["result"] == "geometry.open-contour"
    assert (open_by_500["gap_nm"], open_by_500["bucket"]) == (500, "gap-up-to-1um")
    assert with_edges(_square(5_000))["bucket"] == "gap-up-to-10um"
    assert with_edges(_square(50_000))["bucket"] == "gap-larger"
    assert with_edges(())["result"] == "no-pieces"

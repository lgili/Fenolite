# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A board cut-out of a component stays a cut-out of that component (change c0443)."""

import dataclasses
from collections import Counter
from pathlib import Path

from _convert import two_layer

from fenolite.backends.altium import lower
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord
from fenolite.core.coords import Point
from fenolite.model.board import Graphic, Outline
from fenolite.model.design import Design

MM = 1_000_000
KEEPOUT_LAYER = 56
NM = 3
SLOT = (Point(-MM, 2 * MM), Point(MM, 2 * MM), Point(MM, 3 * MM), Point(-MM, 3 * MM))
"""A slot of the first footprint, in its frame, inside the board."""


def _with_cutout() -> Design:
    """The two-layer board whose first footprint cuts a slot out of the board: a closed ``Edge.Cuts``
    outline of the footprint, as KiCad holds a cut-out that belongs to a part."""
    design = two_layer()
    assert design.board is not None
    first, *rest = design.board.footprints
    slot = Graphic(id="gra-slot", kind="polygon", layer="Edge.Cuts", points=SLOT, width=0)
    first = dataclasses.replace(first, graphics=(*first.graphics, slot))
    board = dataclasses.replace(design.board, footprints=(first, *rest))
    return dataclasses.replace(design, board=board)


def _cutouts(document: bytes) -> Counter[tuple[int, int, str]]:
    """The board cut-out regions by layer, second flag byte and owner."""
    found: Counter[tuple[int, int, str]] = Counter()
    for region in read_pcbdoc(document).regions:
        if not isinstance(region, RegionRecord):
            continue
        if dict(region.properties.fields).get("ISBOARDCUTOUT", "").upper() == "TRUE":
            owner = "free" if region.prefix.component is None else "component"
            found[(region.prefix.layer, region.prefix.flags2, owner)] += 1
    return found


def _written(design: Design, edges: Outline | None = None) -> bytes:
    return lower.write_design(design, allow_lossy=True, edges=edges).files[f"{design.header.name}.PcbDoc"]


def test_a_footprint_cutout_is_written_as_a_cutout_of_its_component(tmp_path: Path) -> None:
    """Scenario "A cut-out of a component comes back as one": the slot is one board cut-out region of the
    Keep-Out layer owned by the component, without the keep-out flag; read back, the footprint holds the
    slot on ``Edge.Cuts`` and no rule area, and the board's edge rings hold it."""
    design = _with_cutout()
    document = _written(design)
    assert _cutouts(document) == Counter({(KEEPOUT_LAYER, 0, "component"): 1})
    path = tmp_path / "slot.PcbDoc"
    path.write_bytes(document)
    back = AltiumBackend().read(path).design
    assert back.board is not None
    edges = [g for fp in back.board.footprints for g in fp.graphics if g.layer == "Edge.Cuts"]
    assert len(edges) == 1 and edges[0].kind == "polygon" and not edges[0].filled
    read = sorted((p.x, p.y) for p in edges[0].points)
    # the written unit and the turn of the footprint round each vertex by a few nanometres
    assert len(read) == len(SLOT)
    pairs = zip(read, sorted(SLOT), strict=True)
    assert all(abs(a[0] - b.x) <= NM and abs(a[1] - b.y) <= NM for a, b in pairs)
    assert not [area for fp in back.board.footprints for area in fp.keepouts]
    rings = AltiumBackend().board_edges(back)
    assert rings is not None and len(rings) == 2


def test_the_board_ring_of_a_footprint_cutout_is_not_written_again() -> None:
    """KiCad counts a footprint's edge among the board's edges, so a converted outline holds the slot as a
    cut-out too: it is written once, with its component; another cut-out stays a free one."""
    design = _with_cutout()
    assert design.board is not None
    (slot,) = lower.footprint_cutout_rings(design.board)
    hole = (Point(5 * MM, 5 * MM), Point(6 * MM, 5 * MM), Point(6 * MM, 6 * MM), Point(5 * MM, 6 * MM))
    board = (Point(0, 0), Point(50 * MM, 0), Point(50 * MM, 30 * MM), Point(0, 30 * MM))
    edges = Outline(id="out-slot", points=board, cutouts=(slot, hole))
    assert _cutouts(_written(design, edges)) == Counter(
        {(KEEPOUT_LAYER, 0, "component"): 1, (KEEPOUT_LAYER, 0, "free"): 1}
    )


def test_an_open_footprint_edge_is_no_cutout() -> None:
    line = Graphic(id="gra-edge", kind="line", layer="Edge.Cuts", points=SLOT[:2], width=MM // 10)
    assert "no closed outline" in (lower.footprint_cutout_problem(line) or "")
    square = Graphic(id="gra-square", kind="polygon", layer="Edge.Cuts", points=SLOT)
    assert lower.footprint_cutout_problem(square) is None

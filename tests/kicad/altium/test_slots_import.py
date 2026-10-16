# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Slot pads and board cut-out regions against ``kicad-cli pcb import`` (capability altium-pcb-writer,
"Non-plated holes and slots" and "Board cut-out regions"; change c0168; hypotheses ``H-A-SLOT-PAD`` and
``H-A-CUTOUT-REGION``).

``-k candidates`` is task 1.2's measurement: which region keys KiCad 10.0.6 imports as an ``Edge.Cuts``
cut-out, and whether an arc vertex of the shape-based outline survives, in KiCad's import and in
Fenolite's reader (``docs/formats/altium/pcb-records.md``, "Board cut-outs"). ``pcb import`` exists from
10.0 only. A pass says what KiCad's importer reads; it settles nothing for Altium Designer.
"""

from __future__ import annotations

import _altium_slotcases as cases
import pytest
from _resources import kicad_cli_major

from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord
from fenolite.core.coords import Point

pytestmark = pytest.mark.needs_kicad
MM = cases.MM


def _needs_import() -> None:
    if kicad_cli_major() == 9:
        pytest.skip("no `pcb import` before 10.0")


SQUARE: list[tuple[str, tuple[Point, ...]]] = [
    ("line", (Point(10 * MM, 10 * MM), Point(20 * MM, 10 * MM))),
    ("line", (Point(10 * MM, 20 * MM), Point(10 * MM, 10 * MM))),
    ("line", (Point(20 * MM, 10 * MM), Point(20 * MM, 20 * MM))),
    ("line", (Point(20 * MM, 20 * MM), Point(10 * MM, 20 * MM))),
]


def _near(a: Point, b: Point) -> bool:
    return abs(a.x - b.x) <= cases.TOLERANCE and abs(a.y - b.y) <= cases.TOLERANCE


def _same_edges(
    found: list[tuple[str, tuple[Point, ...]]], wanted: list[tuple[str, tuple[Point, ...]]]
) -> bool:
    return len(found) == len(wanted) and all(
        any(
            kind == k and len(points) == len(p) and all(_near(a, b) for a, b in zip(points, p, strict=True))
            for k, p in wanted
        )
        for kind, points in found
    )


@pytest.mark.parametrize("name", sorted(cases.CANDIDATES))
def test_candidates_imported_as_a_cut_out_or_not(name: str) -> None:
    """``ISBOARDCUTOUT=TRUE`` with ``KIND=0`` gives the ring as ``Edge.Cuts`` lines on every layer tried;
    ``KIND=1`` (a polygon cut-out) gives a rule area and no edge, with or without the key."""
    _needs_import()
    found = cases.imported_candidate(name)
    assert found.design.board is not None
    edges = cases.cut_edges(found.design)
    if name in cases.CUT_OUT:
        assert _same_edges(edges, SQUARE), edges
        assert not found.design.board.keepouts
    else:
        assert edges == []
        assert len(found.design.board.keepouts) == 1
    assert not [g for g in found.design.board.graphics if g.layer != "Edge.Cuts"]


def test_candidates_arc_vertex_kept_by_kicad() -> None:
    """KiCad takes the cut-out from ``ShapeBasedRegions6``: a vertex with the round flag, a centre and a
    radius gives one arc to the next vertex, while ``Regions6`` holds the straight square."""
    _needs_import()
    found = cases.imported_candidate("kind0-keepout-boardcutout", arc=True)
    edges = cases.cut_edges(found.design)
    wanted = [item for item in SQUARE if item[1][0] != Point(20 * MM, 10 * MM)]
    wanted.append(("arc", (Point(20 * MM, 10 * MM), Point(25 * MM, 15 * MM), Point(20 * MM, 20 * MM))))
    assert _same_edges(edges, wanted), edges


def test_candidates_read_by_fenolite() -> None:
    """Fenolite's reader gives the region with its keys and its four vertices from ``Regions6``; it keeps
    the shape-based record as bytes beside it, so an arc vertex does not reach the model (no oracle)."""
    data = cases.candidate_document("kind0-keepout-boardcutout", arc=True)
    doc = read_pcbdoc(data)
    (region,) = doc.regions
    assert isinstance(region, RegionRecord)
    properties = dict(region.properties.fields)
    assert properties["KIND"] == "0" and properties["ISBOARDCUTOUT"] == "TRUE"
    assert len(region.outline) == 4
    assert len(doc.shape_regions) == 1

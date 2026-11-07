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
import _probes
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


def test_pad_slot_pads_imported_as_oval_holes() -> None:
    """``H-A-SLOT-PAD``: the three free slot pads of the fixture are three non-plated oval holes of the
    same centre, width, length and angle in KiCad's import (probe ``altium-slot-pad``)."""
    _needs_import()
    assert _probes.run("altium-slot-pad") == "equal"


def test_region_cut_outs_imported_as_edges() -> None:
    """``H-A-CUTOUT-REGION``, scenario "KiCad imports the region": the three cut-out regions of the
    fixture (the lone milled slot, the merged L and the rounded cut-out) are ``Edge.Cuts`` rings of the
    written vertices within 10 nm (probe ``altium-cutout-region``)."""
    _needs_import()
    assert _probes.run("altium-cutout-region") == "equal"
    found = cases.imported_fixture()
    assert found.code == 0
    assert found.design.board is not None and not found.design.board.keepouts


def test_slot_axes_as_kicad_upgrades_them() -> None:
    """Change c0416: ``fp upgrade`` 10.0.6 of ``slot_library`` and Fenolite's import of it give the same
    ``norm.slot_form`` (width, length, axis in the footprint's frame) for each of the four slots KiCad
    encodes, though KiCad holds pads 2 and 6 the other way round (drill and length swapped, the hole turned
    a quarter). KiCad loses the slots of pads 3 and 4, whose hole rotation is 30°: it reads no drill."""
    if kicad_cli_major() == 9:
        pytest.skip("Altium libraries are read by `fp upgrade` from 10.0 on only")
    import hashlib

    from fenolite.backends.altium.adapter.library import import_footprints
    from fenolite.backends.altium.read.pcblib import read_pcblib
    from fenolite.backends.kicad.mod import read_footprint
    from fenolite.checks.equivalence import norm

    data = cases.slot_library()
    run = cases.runner().run(
        ["fp", "upgrade", "-o", "out.pretty", "slots.PcbLib"], files={"slots.PcbLib": data}
    )
    assert run.ok, run.stdout + run.stderr
    (name,) = [n for n in run.outputs if n.endswith(".kicad_mod")]
    kicad = {pad.number: pad for pad in read_footprint(run.outputs[name].decode()).pads}
    digest = hashlib.sha256(data).hexdigest()
    library = import_footprints(
        read_pcblib(data), name="slots", file="slots.PcbLib", sha256=digest, issues=[]
    )
    ours = {pad.number: pad for pad in library.footprints[0].pads}
    assert [kicad[n].drill for n in ("3", "4")] == [None, None]
    axes: list[int] = []
    for number in ("1", "2", "5", "6"):
        mine, theirs = norm.slot_form(ours[number]), norm.slot_form(kicad[number])
        assert mine is not None and theirs is not None, number
        assert all(abs(x - y) <= cases.TOLERANCE for x, y in zip(mine[:2], theirs[:2], strict=True)), number
        assert mine[2] == theirs[2], number
        axes.append(theirs[2])
    assert axes == [0, 90_000_000, 135_000_000, 120_000_000]
    for number in ("2", "6"):  # held the other way round: the raw fields differ, the slot does not
        stack, read = ours[number].padstack, kicad[number].padstack
        assert stack is not None and read is not None
        assert (ours[number].drill, stack.hole_rotation) != (kicad[number].drill, read.hole_rotation)

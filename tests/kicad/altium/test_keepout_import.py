# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Keep-out tracks and a polygon cut-out against ``kicad-cli pcb import`` (change c0407; ``pcb-records.md``,
"Regions and keep-outs").

The authored document of ``_altium_keepouts`` goes through KiCad 10's importer and through Fenolite's reader
and ``convert.altium_to_kicad.keepouts``; both give six rule areas of the same layers and shapes: a band of
the track's width per keep-out track, and the polygon cut-out's outline. ``pcb import`` exists from 10.0
only. A pass says what KiCad's importer reads; it settles nothing for Altium Designer.
"""

from __future__ import annotations

import hashlib

import _altium_keepouts as keepouts
import _altium_slotcases as cases
import pytest
from _resources import kicad_cli_major

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.convert.altium_to_kicad import Ledger
from fenolite.convert.altium_to_kicad import keepouts as convert_keepouts
from fenolite.core.coords import Point
from fenolite.geometry import area2
from fenolite.model.board import Keepout
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad
SHAPE_TOLERANCE = 10_000
"""KiCad polygonises a round end with fewer vertices than Fenolite: a corner of the box may differ by this
much (nm)."""


def _corner(design: Design) -> Point:
    assert design.board is not None
    edge = [p for g in design.board.graphics if g.layer == "Edge.Cuts" for p in g.points]
    return Point(min(p.x for p in edge), min(p.y for p in edge))


def _shapes(design: Design) -> list[tuple[tuple[str, ...], tuple[int, int, int, int], int]]:
    """Each rule area as (layers, box relative to the board's corner, area in nm²), sorted."""
    assert design.board is not None
    corner = _corner(design)

    def shape(area: Keepout) -> tuple[tuple[str, ...], tuple[int, int, int, int], int]:
        xs = [p.x - corner.x for p in area.outline]
        ys = [p.y - corner.y for p in area.outline]
        return tuple(sorted(area.layers)), (min(xs), min(ys), max(xs), max(ys)), abs(area2(area.outline)) // 2

    return sorted(shape(area) for area in design.board.keepouts)


def test_rule_areas_match_kicad_import() -> None:
    if kicad_cli_major() == 9:
        pytest.skip("no `pcb import` before 10.0")
    data = keepouts.keepout_document()
    kicad = cases.import_document(data, "keepouts.PcbDoc").design
    read = import_board(read_pcbdoc(data), file="keepouts.PcbDoc", sha256=hashlib.sha256(data).hexdigest())
    ours = convert_keepouts(read, Ledger())
    theirs, mine = _shapes(kicad), _shapes(ours)
    assert len(theirs) == len(mine) == 6
    for (layers_k, box_k, area_k), (layers_m, box_m, area_m) in zip(theirs, mine, strict=True):
        assert layers_k == layers_m
        assert all(abs(a - b) <= SHAPE_TOLERANCE for a, b in zip(box_k, box_m, strict=True)), (box_k, box_m)
        assert abs(area_k - area_m) <= area_k // 100, (area_k, area_m)
    # the polygon cut-out keeps out poured copper alone, in KiCad and in Fenolite
    assert kicad.board is not None and ours.board is not None
    pour_only = [
        (k.layers, k.no_tracks, k.no_vias, k.no_pads)
        for k in (*kicad.board.keepouts, *ours.board.keepouts)
        if k.no_copper_pour and not k.no_tracks
    ]
    assert pour_only == [(("F.Cu",), False, False, False)] * 2

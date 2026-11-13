# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Adding a remote zone leaves the other written pours unchanged (change c0496; capability altium-pour, "A
computed pour depends only on its own inputs"; capability design-conversion, "A carried pour is kept per
polygon").

The documents are authored for these tests (``tests/_altium_pour.py``): three polygons of three nets, vias,
pads and a track on two layers, written by Fenolite's own writer, with a fourth polygon of a fourth net added
far from them or over the first one.

Task 1.1 (reproduction). Written twice, without and with the remote polygon, the computed pour of the three
polygons is byte-identical apart from the polygon index: none of the candidate causes of design D2 (record
order, a global sort, via grouping over the whole net, snap rounding over the whole scene) changes them
here. What changed the pours of unrelated nets was the carrier: one polygon without a carried pour made
every polygon fall back to the computed pour (design D1), whose regions are not the source's. One global
input was found in the engine and is fixed: the arc tolerance of the objects and of the board's area was
the smallest of all polygons, so a polygon of a finer ``ARCRESOLUTION`` anywhere changed the chords of the
others; each tolerance now has its own context (``pour.pour_reading``)."""

from __future__ import annotations

import dataclasses
import importlib.util
from collections import defaultdict

import pytest
from _altium_pour import FILENAME, Board, clearance, pad, rect, track, via, zone

from fenolite.backends.altium import pcbdoc
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord, TrackRecord
from fenolite.model.board import Zone

pytestmark = pytest.mark.skipif(importlib.util.find_spec("pyclipper") is None, reason="needs the geo extra")

REMOTE = zone("d", "AUX", rect(33, 2, 39, 28))
"""The fourth polygon, more than 20 mm from the three."""
OVER = zone("d", "AUX", rect(8, 2, 16, 8), priority=5)
"""The fourth polygon over the first one, poured before it."""


def _board(*extra: Zone) -> Board:
    aux = (via("v6", "AUX", 36, 15), via("v7", "AUX", 14, 4)) if extra else ()
    zones = (
        zone("a", "GND", rect(1, 1, 12, 9)),
        zone("b", "VCC", rect(1, 11, 12, 19)),
        zone("c", "SIG", rect(1, 21, 12, 29), layer="B.Cu"),
        *extra,
    )
    vias = (via("v1", "GND", 4, 4), via("v2", "GND", 8, 6), via("v3", "VCC", 5, 15), via("v4", "SIG", 6, 25),
            via("v5", "VCC", 9, 5), *aux)  # fmt: skip
    pads = (pad("p1", "GND", 10, 3, kind="thru", drill=0.5, size=(1.2, 1.2)), pad("p2", "SIG", 3, 27))
    tracks = (track("t1", "VCC", (2, 13), (10, 17)),)
    return Board(zones=zones, vias=vias, pads=pads, tracks=tracks, rules=(clearance(0.2),))


Key = tuple[str, object]


def _regions(data: bytes) -> dict[Key, list[bytes]]:
    """The pour regions of each polygon, plain and shape-based, without the polygon index; a polygon is named
    by its layer and first vertex, which the remote polygon does not change."""
    document = read_pcbdoc(data, file=FILENAME)
    found: dict[Key, list[bytes]] = defaultdict(list)
    for records in (document.regions, document.shape_regions):
        for record in records:
            if isinstance(record, RegionRecord) and record.prefix.polygon is not None:
                polygon = document.polygons[record.prefix.polygon]
                key = (polygon.record.get("LAYER") or "", (polygon.vertices[0].x, polygon.vertices[0].y))
                found[key].append(record.raw[:10] + record.raw[12:])
    return dict(found)


def _zero_length(data: bytes) -> int:
    """The zero-length region edges and pour tracks of a document."""
    document = read_pcbdoc(data, file=FILENAME)
    count = 0
    for record in (*document.regions, *document.shape_regions):
        if isinstance(record, RegionRecord) and record.prefix.polygon is not None:
            for ring in (record.outline, *record.holes):
                points = [(v.x, v.y) for v in ring]
                if record.closing is None and points and points[0] == points[-1]:
                    points.pop()  # a ring may state its closing vertex
                count += sum(1 for a, b in zip(points, (*points[1:], points[0]), strict=True) if a == b)
    for item in document.tracks:
        if isinstance(item, TrackRecord) and item.prefix.polygon is not None:
            count += (item.x1, item.y1) == (item.x2, item.y2)
    return count


def _kept(data: bytes) -> dict[str, pcbdoc.KeptPour]:
    """The pours of a written document, as a conversion to KiCad carries them."""
    document = read_pcbdoc(data, file=FILENAME)
    kept: dict[str, pcbdoc.KeptPour] = {}
    for index, polygon in enumerate(document.polygons):
        plain = document.regions_of(index)
        shapes = [
            r for r in document.shape_regions if isinstance(r, RegionRecord) and r.prefix.polygon == index
        ]
        net = document.nets[polygon.net].name if polygon.net is not None else None
        kept[str(index)] = pcbdoc.KeptPour(
            tuple((v.x, v.y) for v in polygon.vertices),
            net,
            tuple((a.raw, b.raw) for a, b in zip(plain, shapes, strict=True)),
            polygon.record.get("LAYER") or "",
        )
    return kept


def test_a_remote_zone_added() -> None:
    """Scenario "A remote zone added": the computed regions of the three polygons do not change."""
    before, after = _board().write(), _board(REMOTE).write()
    old, new = _regions(before.data), _regions(after.data)
    assert len(old) == 3 and len(new) == 4
    assert all(new[key] == records for key, records in old.items())
    assert _zero_length(before.data) == _zero_length(after.data) == 0


def test_an_overlapping_zone_added() -> None:
    """Scenario "An overlapping zone added": the first polygon may change, the other two must not."""
    before, after = _board().write(), _board(OVER).write()
    old, new = _regions(before.data), _regions(after.data)
    first = next(key for key in old if key[0] == "TOP" and key in new and new[key] != old[key])
    assert all(new[key] == records for key, records in old.items() if key != first)
    assert _zero_length(after.data) == 0


def test_a_zone_added_in_kicad_keeps_the_others() -> None:
    """Scenario "A zone added in KiCad": the three carried polygons keep the source's regions; only the new
    polygon is computed, and no ``altium.pour-changed`` is reported."""
    source = _board().write().data
    spec = dataclasses.replace(_board(REMOTE).spec(), kept_pours=_kept(source))
    written = pcbdoc.write_pcbdoc_result(spec, filename=FILENAME, pour="computed")
    assert written.pour is not None and not written.pour.kept and written.pour.poured == 4
    old, new = _regions(source), _regions(written.data)
    assert all(new[key] == records for key, records in old.items())
    assert len(new) == 4 and pcbdoc.POUR_CHANGED not in {issue.code for issue in written.issues}


def test_an_overlapping_zone_computes_only_its_neighbour() -> None:
    """A new polygon over the first one computes the first one again, with ``altium.pour-changed`` naming
    why; the other two keep the source's regions."""
    source = _board().write().data
    spec = dataclasses.replace(_board(OVER).spec(), kept_pours=_kept(source))
    written = pcbdoc.write_pcbdoc_result(spec, filename=FILENAME, pour="computed")
    old, new = _regions(source), _regions(written.data)
    same = [key for key, records in old.items() if new.get(key) == records]
    assert len(same) == 2
    changed = [issue for issue in written.issues if issue.code == pcbdoc.POUR_CHANGED]
    assert [issue.where for issue in changed] == ["zone/a"] and changed[0].severity == "warning"

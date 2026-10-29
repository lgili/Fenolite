# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rewrite of a read document with a computed pour (change c0215; capability altium-build, "Pour mode
of an Altium build": a rewrite pours every polygon again; capability altium-pcb-writer, "Polygon Connect
Style records": the records that map are written back as they were read).

An authored board is written with ``computed``, read with Fenolite's import, and written again with
``rewrite=True``. Its ``GND`` zone connects ``solid``: the read zones hold the model's default settings, so
a rule that says Direct Connect for ``GND`` in the rewrite is the read record, not a lowering.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib.util

import pytest
from _altium_pour import FILENAME, Board, clearance, pad, via, zone

from fenolite.analysis.fills import unfracture
from fenolite.backends.altium import lower
from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.connectstyle import read_connect_styles
from fenolite.backends.altium.pour import area, read_pour
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.geometry import Polygon
from fenolite.geometry.boolean.clipper import ClipperBackend
from fenolite.model.base import ExtBag
from fenolite.model.board import ZoneSettings
from fenolite.model.design import Design

pytestmark = pytest.mark.skipif(importlib.util.find_spec("pyclipper") is None, reason="needs the geo extra")
BOARD = Board(
    zones=(
        zone("z1", "GND", settings=ZoneSettings(connection="solid")),
        zone("z2", "VIN", layer="B.Cu"),
    ),
    pads=(
        pad("p1", "VIN", 10, 10, kind="thru_hole", shape="circle", size=(1.6, 1.6), drill=0.8),
        pad("p2", "GND", 20, 10, kind="thru_hole", shape="circle", size=(1.6, 1.6), drill=0.8),
    ),
    vias=(via("v1", "GND", 30, 20), via("v2", "VIN", 15, 20)),
    rules=(clearance(0.25),),
)
NAME = "pour"


def _read(data: bytes) -> Design:
    design = import_board(read_pcbdoc(data), file=FILENAME, sha256=hashlib.sha256(data).hexdigest())
    return dataclasses.replace(design, header=dataclasses.replace(design.header, name=NAME))


def _fills(data: bytes) -> dict[tuple[str, str | None], list[Polygon]]:
    """The fills of each zone of a document by (layer, net name), as Fenolite reads them."""
    design = read_pour(data, file=FILENAME).design
    assert design.board is not None
    names = {net.id: net.name for net in design.circuit.nets}
    found: dict[tuple[str, str | None], list[Polygon]] = {}
    for found_zone in design.board.zones:
        pieces = found.setdefault((found_zone.layers[0], names.get(found_zone.net_id or "")), [])
        for fill in found_zone.fills:
            rings = unfracture(fill.polygon)
            assert rings is not None
            pieces.append(Polygon(rings[0], rings[1]))
    return found


def _connect(data: bytes) -> dict[str, str]:
    """The style for through-hole pads of each Polygon Connect Style rule of a document, by rule name."""
    styles = read_connect_styles([record.fields for record in read_pcbdoc(data).rules])
    return {style.name: style.th_pad.style for style in styles if style.th_pad is not None}


def test_a_rewrite_pours_every_polygon_again() -> None:
    """The read document's fills are not carried: the rewrite pours both polygons again, and the fills of
    the second computed write equal those of the first within one unit along their boundary (RT-A2 of the
    fills)."""
    first = BOARD.write().data
    design = _read(first)
    assert design.board is not None and all(z.fills for z in design.board.zones)
    written = lower.write_design(design, allow_lossy=True, rewrite=True, pour="computed")
    assert written.pour_mode == "computed" and written.pour is not None and written.pour.pour is not None
    assert written.pour.pour.poured == 2 and not written.pour.pour.refused
    second = written.files[f"{NAME}.PcbDoc"]
    before, after = _fills(first), _fills(second)
    assert sorted(before, key=str) == sorted(after, key=str)
    clipper = ClipperBackend()
    for key, pieces in before.items():
        assert len(pieces) == len(after[key]), key
        boundary = sum(
            abs(a.x - b.x) + abs(a.y - b.y)
            for piece in pieces
            for ring in piece.rings()
            for a, b in zip(ring, (*ring[1:], ring[0]), strict=True)
        )
        difference = sum(area(p) for p in clipper.xor(pieces, after[key]))
        assert difference <= 3 * boundary, (key, float(difference), boundary)


def test_read_connect_records_are_written_back() -> None:
    """The board keeps one ``polygon_connect`` pair per record, and the rewrite writes the records back:
    the ``GND`` rule stays Direct Connect though the read zone holds the default ``thermal``."""
    first = BOARD.write().data
    assert _connect(first) == {"PolygonConnect_net_GND": "direct", "PolygonConnect_net_VIN": "relief",
                               "PolygonConnect": "relief"}  # fmt: skip
    design = _read(first)
    assert design.board is not None
    pairs = [key for key, _ in design.board.ext["altium"].payload if key == "polygon_connect"]
    assert len(pairs) == 3
    assert all(z.settings == ZoneSettings() for z in design.board.zones)
    written = lower.write_design(design, allow_lossy=True, rewrite=True, pour="computed")
    assert _connect(written.files[f"{NAME}.PcbDoc"]) == _connect(first)
    assert not [i for i in written.issues if i.where.startswith("rule/PolygonConnect")]


def test_a_record_that_does_not_map_lowers_the_zones() -> None:
    """A record whose style Fenolite does not read is reported, and the rules are lowered from the read
    zones: the ``GND`` rule becomes Relief Connect."""
    design = _read(BOARD.write().data)
    assert design.board is not None
    bag = design.board.ext["altium"]
    payload = tuple(
        (key, value.replace("THPAD.CONNECTSTYLE=Direct", "THPAD.CONNECTSTYLE=Sideways"))
        if key == "polygon_connect" and "InNet('GND')" in value
        else (key, value)
        for key, value in bag.payload
    )
    board = dataclasses.replace(design.board, ext={"altium": ExtBag(bag.min_version, payload)})
    written = lower.write_design(
        dataclasses.replace(design, board=board), allow_lossy=True, rewrite=True, pour="computed"
    )
    (problem,) = [i for i in written.issues if i.where.startswith("rule/")]
    assert (problem.code, problem.where) == ("altium.not-lowered", "rule/PolygonConnect_net_GND")
    assert "connect-style" in problem.message
    assert _connect(written.files[f"{NAME}.PcbDoc"])["PolygonConnect_net_GND"] == "relief"


def test_outline_rewrite_writes_no_connect_record() -> None:
    """``outline`` (the mode of ``model_roundtrip``) writes no Polygon Connect Style record, as before."""
    design = _read(BOARD.write().data)
    written = lower.write_design(design, allow_lossy=True, rewrite=True, pour="outline")
    assert _connect(written.files[f"{NAME}.PcbDoc"]) == {}

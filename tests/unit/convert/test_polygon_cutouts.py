# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Polygon cut-outs and netted copper shapes in a conversion to Altium, and copper without a net in
``equivalent`` (capability altium-pcb-writer, "Polygon cut-outs"; capability design-conversion, "Copper
shapes keep their net"; capability design-equivalence, "Copper without a net"; change c0439).

The source is the authored board ``tests/data/kicad/convert/polygon_cutouts.kicad_pcb``: a track and a
filled copper polygon on net ``A``, a rule area that forbids pours alone on F.Cu, one on F.Cu and B.Cu, and
one on B.Cu that forbids tracks too. Fenolite reads what Fenolite wrote; Altium's reading is a kit request.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from fenolite.api.conversion import ConversionResult, convert
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord
from fenolite.checks.equivalence.levels import compare_designs
from fenolite.checks.equivalence.model import Tolerances
from fenolite.model.board import Board, Graphic
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "data" / "kicad" / "convert" / "polygon_cutouts.kicad_pcb"
TOP, BOTTOM, MULTI_LAYER = 1, 32, 74
KEEPOUT_FLAG = 2
TOLERANCES = Tolerances(length_nm=3)


def _converted() -> tuple[ConversionResult, bytes]:
    result = convert(FIXTURE, to="altium")
    (name,) = [key for key in result.conversion.files if key.endswith(".PcbDoc")]
    return result, result.conversion.files[name]


def _regions(data: bytes) -> list[tuple[str, int, int, int | None, str | None]]:
    """``(KIND, layer, second flag byte, net, KEEPOUTRESTRICTIONS)`` of each region, sorted."""
    found: list[tuple[str, int, int, int | None, str | None]] = []
    for item in read_pcbdoc(data).regions:
        if isinstance(item, RegionRecord):
            keys = {key.upper(): value for key, value in item.properties.fields}
            prefix = item.prefix
            found.append(
                (keys["KIND"], prefix.layer, prefix.flags2, prefix.net, keys.get("KEEPOUTRESTRICTIONS"))
            )
    return sorted(found, key=lambda r: (r[0], r[1], r[2], -1 if r[3] is None else r[3], r[4] or ""))


def _read_back(tmp_path: Path, data: bytes) -> Design:
    path = tmp_path / "written.PcbDoc"
    path.write_bytes(data)
    return AltiumBackend().read(path).design


def _board(design: Design) -> Board:
    assert design.board is not None
    return design.board


def test_cutouts_are_kind_one_and_shapes_keep_their_net() -> None:
    """Scenario "The authored cut-out board": one ``KIND=1`` region per pour-only area, on Multi-Layer for
    the area on both copper layers and on Top for the one on ``F.Cu``, with no keep-out flag and no net; the
    area that forbids tracks too stays a keep-out region; the copper polygon holds its net. Nothing is
    unexplained."""
    result, data = _converted()
    assert result.unexplained == ()
    regions = _regions(data)
    assert [r for r in regions if r[0] == "1"] == [
        ("1", TOP, 0, None, None),
        ("1", MULTI_LAYER, 0, None, None),
    ]
    assert [r for r in regions if r[0] == "0" and r[2] == KEEPOUT_FLAG] == [
        ("0", BOTTOM, KEEPOUT_FLAG, None, "6")
    ]
    (shape,) = [r for r in regions if r[0] == "0" and r[2] == 0]
    assert shape[1] == TOP and shape[3] is not None


def test_cutouts_read_back_as_pour_only_rule_areas(tmp_path: Path) -> None:
    """The reading of the written document holds the two cut-outs as the rule areas that forbid pours alone
    they were written from (one on ``F.Cu``, one on both copper layers), and the copper polygon on net
    ``A``."""
    _, data = _converted()
    read = _read_back(tmp_path, data)
    board = _board(read)
    pour_only = sorted(
        k.layers
        for k in board.keepouts
        if k.no_copper_pour and not (k.no_tracks or k.no_vias or k.no_pads or k.no_footprints)
    )
    assert pour_only == [("F.Cu",), ("F.Cu", "B.Cu")]
    names = {net.id: net.name for net in read.circuit.nets}
    (shape,) = [g for g in board.graphics if g.layer == "F.Cu" and g.filled]
    assert shape.net_id is not None and names[shape.net_id] == "A"


def test_equivalent_sees_a_cutout_turned_copper(tmp_path: Path) -> None:
    """Scenario "A cut-out written as copper": the reading with one cut-out replaced by a filled polygon of
    no net on its layer is not equivalent at level 5 (``copper-no-net`` at ``(no net):top``)."""
    _, data = _converted()
    read = _read_back(tmp_path, data)
    board = _board(read)
    cut = next(k for k in board.keepouts if k.layers == ("F.Cu",) and not k.no_tracks)
    copper = Graphic(
        id="gfx_cut", kind="polygon", layer="F.Cu", points=tuple(cut.outline), width=0, filled=True
    )
    turned = dataclasses.replace(
        board, keepouts=tuple(k for k in board.keepouts if k.id != cut.id), graphics=(*board.graphics, copper)
    )
    report = compare_designs(read, dataclasses.replace(read, board=turned), level=5, tolerances=TOLERANCES)
    assert not report.equivalent
    found = [(d.level, d.kind, d.where, bool(d.a), bool(d.b)) for d in report.differences]
    assert found == [(5, "copper-no-net", "(no net):top", False, True)]
    assert compare_designs(read, read, level=5, tolerances=TOLERANCES).equivalent


def test_equivalent_sees_a_shape_that_lost_its_net(tmp_path: Path) -> None:
    """A copper polygon written without its net is copper of no net on one side only: the conversion's
    design against the reading with the polygon's net cleared is not equivalent; the KiCad source, whose
    polygon keeps its net in its KiCad slot, is equivalent to the reading at level 5."""
    result, data = _converted()
    read = _read_back(tmp_path, data)
    board = _board(read)
    graphics = tuple(
        dataclasses.replace(g, net_id=None) if g.layer == "F.Cu" and g.filled else g for g in board.graphics
    )
    netless = dataclasses.replace(read, board=dataclasses.replace(board, graphics=graphics))
    source = result.conversion.design
    lost = compare_designs(source, netless, level=5, tolerances=TOLERANCES, frame="relative")
    assert [(d.kind, d.where) for d in lost.differences] == [("copper-no-net", "(no net):top")]
    kept = compare_designs(source, read, level=5, tolerances=TOLERANCES, frame="relative")
    assert not [d for d in kept.differences if d.kind == "copper-no-net"]

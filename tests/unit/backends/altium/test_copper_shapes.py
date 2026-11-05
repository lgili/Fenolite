# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper shapes of a KiCad board written as Altium copper (capability altium-pcb-writer, "Board graphics
and keep-out records", scenarios "Copper polygon with a net" and "Copper on a plane stays a loss"; change
c0412). The boards are Fenolite's own two-layer sample with shapes added in the test; no tool runs."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _coppershapes import BOTTOM, TOP, shapes_design

from fenolite.backends.altium import lower, pcbrecords
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord, TrackRecord
from fenolite.core.errors import Issue
from fenolite.lens import altium_copper
from fenolite.lens.altium import write_model
from fenolite.model.board import Graphic


def _net_index(names: list[str], name: str) -> int:
    return names.index(name)


def test_copper_shapes_are_written_with_their_nets(tmp_path: Path) -> None:
    design = shapes_design(tmp_path)
    written = write_model(design)
    assert not [i for i in written.issues if i.where in lower.LOSS_KINDS], written.issues
    document = read_pcbdoc(written.files["shapes.PcbDoc"], file="shapes.PcbDoc")
    nets = [net.name or "" for net in document.nets]
    regions = [r for r in document.regions if isinstance(r, RegionRecord)]
    free = [
        r
        for r in regions
        if r.prefix.layer in (TOP, BOTTOM) and r.prefix.polygon is None and r.prefix.flags2 != 2
    ]
    by_layer = {r.prefix.layer: r for r in free}
    assert set(by_layer) == {TOP, BOTTOM}
    top, bottom = by_layer[TOP], by_layer[BOTTOM]
    assert top.prefix.net == _net_index(nets, "VCC") and len(top.outline) == 5
    assert bottom.prefix.net is None and len(bottom.outline) == 4
    assert dict(top.properties.fields)["KIND"] == "0" and dict(top.properties.fields)["V7_LAYER"] == "TOP"
    assert len(document.shape_regions) == len(document.regions)
    gnd = _net_index(nets, "GND")
    width = pcbrecords.to_units(500_000)
    tracks = [t for t in document.tracks if isinstance(t, TrackRecord)]
    lines = [t for t in tracks if t.prefix.layer == TOP and t.prefix.net == gnd and t.width == width]
    assert len(lines) == 1, "the drawn copper line is a track of GND on the top layer"


def test_copper_shapes_read_back_as_copper_of_their_net(tmp_path: Path) -> None:
    design = shapes_design(tmp_path)
    written = write_model(design)
    folder = tmp_path / "out"
    folder.mkdir()
    for name, data in written.files.items():
        (folder / name).write_bytes(data)
    from fenolite.backends.altium.backend import AltiumBackend

    second = AltiumBackend().read(folder / "shapes.PcbDoc").design
    assert second.board is not None
    names = {net.id: net.name for net in second.circuit.nets}
    copper = [g for g in second.board.graphics if g.layer.endswith(".Cu") and g.filled]
    found = [(g.layer, names.get(g.net_id or "", "")) for g in copper]
    # the board's own F.Cu keep-out reads back as a filled F.Cu graphic without a net (import side)
    assert found.count(("F.Cu", "VCC")) == 1 and found.count(("B.Cu", "")) == 1


def test_copper_shape_on_a_plane_stays_a_loss(tmp_path: Path) -> None:
    design = shapes_design(tmp_path)
    assert design.board is not None
    graphic = next(g for g in design.board.graphics if g.layer == "F.Cu" and g.filled)
    planes = frozenset({"F.Cu"})
    problem = lower.copper_shape_problem(graphic, ("F.Cu", "B.Cu"), planes, {})
    assert problem == "F.Cu is an internal plane, which holds no primitive"
    outside = dataclasses.replace(graphic, layer="In1.Cu")
    assert lower.copper_shape_problem(outside, ("F.Cu", "B.Cu"), frozenset(), {}) == (
        "In1.Cu is not a copper layer of the written stack"
    )


def test_unwritable_copper_shape_refuses_a_lossless_write(tmp_path: Path) -> None:
    design = shapes_design(tmp_path)
    assert design.board is not None
    circle = Graphic(
        id="gr-circle",
        kind="circle",
        layer="F.Cu",
        points=(design.board.graphics[0].points[0], design.board.graphics[0].points[0].offset(1_000_000, 0)),
        filled=True,
    )
    board = dataclasses.replace(design.board, graphics=(*design.board.graphics, circle))
    with pytest.raises(lower.LossyWriteError) as refused:
        lower.write_design(dataclasses.replace(design, board=board))
    assert [(i.where, "filled circle" in i.message) for i in refused.value.issues] == [("copper-shape", True)]


def test_build_lens_passes_copper_graphics_with_net_names(tmp_path: Path) -> None:
    design = shapes_design(tmp_path)
    issues: list[Issue] = []
    items = altium_copper.lower_items(
        design.board, ("F.Cu", "B.Cu"), issues, net_names={n.id: n.name for n in design.circuit.nets}
    )
    copper = sorted((g.layer, g.kind, g.net_id) for g in items.graphics if g.layer.endswith(".Cu"))
    assert copper == [("B.Cu", "rect", None), ("F.Cu", "line", "GND"), ("F.Cu", "polygon", "VCC")]
    assert not [i for i in issues if i.where.startswith("copper-shape/")]
    planed = altium_copper.lower_items(design.board, ("F.Cu", "B.Cu"), [], planes=("B.Cu",))
    assert not [g for g in planed.graphics if g.layer == "B.Cu"]


def test_region_record_net_index() -> None:
    plain = pcbrecords.region_record(TOP, [(0, 0), (10, 0), (10, 10)])
    with_net = pcbrecords.region_record(TOP, [(0, 0), (10, 0), (10, 10)], net=3)
    body = with_net[5:]
    assert body[3:5] == (3).to_bytes(2, "little") and plain[5:][3:5] == b"\xff\xff"
    assert plain[:8] != with_net[:8] or plain != with_net

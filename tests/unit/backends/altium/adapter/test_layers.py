# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Layers and stack-up of an imported board (capability altium-import, "Layers and stack-up"; c0043)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import _altium_records as rec

from fenolite.backends.altium.adapter import EVIDENCE, LAYERS, import_board
from fenolite.backends.altium.adapter.ids import Ids
from fenolite.backends.altium.adapter.layers import LayerMap, copper_name, stackup
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.core.errors import Issue
from fenolite.model.base import ExtBag

DATA = Path(__file__).resolve().parents[5] / "tests" / "data" / "altium"


def _pairs(bag: dict[str, ExtBag]) -> dict[str, str]:
    return dict(bag["altium"].payload) if bag else {}


def test_the_closed_table() -> None:
    assert LAYERS[33] == ("F.SilkS", "silkscreen") and LAYERS[34] == ("B.SilkS", "silkscreen")
    assert LAYERS[35][0] == "F.Paste" and LAYERS[36][0] == "B.Paste"
    assert LAYERS[37][0] == "F.Mask" and LAYERS[38][0] == "B.Mask"
    assert LAYERS[56] == ("Altium.KeepOut", "user") and LAYERS[55][0] == "Altium.DrillGuide"
    assert LAYERS[73] == ("Altium.DrillDrawing", "user")
    assert [LAYERS[56 + n] for n in (1, 16)] == [("Mech.1", "mechanical"), ("Mech.16", "mechanical")]
    assert 74 not in LAYERS and not any(i in LAYERS for i in range(1, 33))
    assert [copper_name(i, 4) for i in range(4)] == ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]


def test_two_layer_board_of_the_blink_sample() -> None:
    data = (DATA / "blink" / "blink.PcbDoc").read_bytes()
    design = import_board(read_pcbdoc(data), file="blink.PcbDoc", sha256=hashlib.sha256(data).hexdigest())
    board = design.board
    assert board is not None
    copper = [layer for layer in board.layers if layer.kind == "copper"]
    assert [(layer.name, layer.ordinal) for layer in copper] == [("F.Cu", 0), ("B.Cu", 1)]
    assert [_pairs(layer.ext)["layer_id"] for layer in copper] == ["1", "32"]
    assert all(_pairs(layer.ext)["altium_name"] for layer in copper)
    edge = [layer for layer in board.layers if layer.name == "Edge.Cuts"]
    assert len(edge) == 1 and edge[0].kind == "edge"
    assert board.stackup is not None
    assert [layer.kind for layer in board.stackup.layers] == ["copper", "dielectric", "copper"]
    assert [layer.name for layer in board.stackup.layers if layer.kind == "copper"] == ["F.Cu", "B.Cu"]
    dielectric = board.stackup.layers[1]
    assert dielectric.epsilon_r == "4.800" and dielectric.thickness == 320_040
    assert board.stackup.layers[0].thickness == 35_560
    assert board.layers[0].native_ids == {"altium": "layer:F.Cu"}
    assert board.stackup.native_ids == {"altium": "stackup"}
    assert board.stackup.layers[2].native_ids == {"altium": "stack:2"}


def test_plane_and_mid_layer_by_position() -> None:
    record = rec.board((1, 39, 3, 32), extra={"PLANE1NETNAME": "GND"})
    document = rec.document(record, tracks=[rec.track((0, 0), (1000, 0), layer=3)])
    issues: list[Issue] = []
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA, issues=issues)
    board = design.board
    assert board is not None
    by_name = {layer.name: layer for layer in board.layers}
    assert [layer.name for layer in board.layers][:4] == ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
    assert _pairs(by_name["In1.Cu"].ext) == {"layer_id": "39", "altium_name": "Layer 39", "plane_net": "GND"}
    assert by_name["In1.Cu"].kind == "copper" and _pairs(by_name["In2.Cu"].ext)["layer_id"] == "3"
    assert board.tracks[0].layer == "In2.Cu" and board.zones == ()
    assert [i.code for i in issues if i.severity != "info"] == []


def test_layer_outside_the_chain() -> None:
    document = rec.document(
        tracks=[rec.track((0, 0), (1000, 0), layer=2), rec.track((0, 9), (9, 9), layer=2)]
    )
    issues: list[Issue] = []
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA, issues=issues)
    assert design.board is not None and design.board.tracks == ()
    lines = [g for g in design.board.graphics if g.layer == "Altium.2"]
    assert len(lines) == 2 and all(g.kind == "line" for g in lines)
    warnings = [i for i in issues if i.code == "altium.import.layer-outside-stack"]
    assert len(warnings) == 1 and "layer 2" in warnings[0].message and warnings[0].severity == "warning"
    outside = next(layer for layer in design.board.layers if layer.name == "Altium.2")
    assert (outside.kind, outside.ordinal) == ("user", 102)


def test_other_layers_exist_only_when_used() -> None:
    document = rec.document(
        tracks=[rec.track((0, 0), (1000, 0), layer=33), rec.track((0, 0), (9, 9), layer=69)]
    )
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA)
    assert design.board is not None
    names = [(layer.name, layer.kind, layer.ordinal) for layer in design.board.layers]
    assert names == [
        ("F.Cu", "copper", 0),
        ("B.Cu", "copper", 1),
        ("Edge.Cuts", "edge", 100),
        ("F.SilkS", "silkscreen", 133),
        ("Mech.13", "mechanical", 169),
    ]


def test_a_chain_of_one_layer_is_a_bad_stack() -> None:
    issues: list[Issue] = []
    design = import_board(rec.document(rec.board((1,))), file="a.PcbDoc", sha256=rec.SHA, issues=issues)
    assert design.board is not None
    assert [layer.name for layer in design.board.layers][:2] == ["F.Cu", "B.Cu"]
    found = [i for i in issues if i.code == "altium.import.bad-stack"]
    assert len(found) == 1 and found[0].severity == "error"


def test_stackup_from_the_numbered_layers_and_from_the_physical_list() -> None:
    for physical in (False, True):
        record = rec.board((1, 2, 3, 32), stack=physical)
        layers = LayerMap.from_board(record)
        issues: list[Issue] = []
        found = stackup(record, layers, Ids("altium_pcbdoc", EVIDENCE), None, issues)
        assert found is not None and issues == []
        kinds = [layer.kind for layer in found.layers]
        assert kinds == ["copper", "dielectric", "copper", "dielectric", "copper", "dielectric", "copper"]
        assert [layer.name for layer in found.layers][::2] == ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
        assert {layer.thickness for layer in found.layers[::2]} == {35_560}
        assert {(layer.epsilon_r, layer.material) for layer in found.layers[1::2]} == {("4.800", "FR-4")}


def test_an_unreadable_thickness_leaves_the_stack_layer_out() -> None:
    record = rec.board((1, 32), extra={"LAYER1COPTHICK": "thick"})
    issues: list[Issue] = []
    found = stackup(record, LayerMap.from_board(record), Ids("altium_pcbdoc", EVIDENCE), None, issues)
    assert found is not None and [layer.kind for layer in found.layers] == ["dielectric", "copper"]
    assert [i.code for i in issues] == ["altium.import.bad-length"]

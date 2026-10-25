# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scene of a board (capability board-viewer, "Board scene"): every item of the model is in it, on its
layer, for a KiCad and an Altium board of the test data."""

from __future__ import annotations

import dataclasses
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from fenolite.backends import registry
from fenolite.backends.base import BoardFrame
from fenolite.cli.cmd_view import scene_of
from fenolite.geometry import arc_length
from fenolite.model.design import Design
from fenolite.view.scene import COLORS, DRILL, SCHEMA, ZONE_EDGE, ZONE_OUTLINE, build_scene, summary

ROOT = Path(__file__).resolve().parents[3]
KICAD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
ALTIUM = ROOT / "tests" / "data" / "altium" / "board6" / "board6.PcbDoc"
BODIES = ROOT / "tests" / "data" / "altium" / "body2" / "body2.PcbDoc"


def _scene(path: Path) -> tuple[Design, dict[str, Any]]:
    backend = registry.for_path(path)
    assert backend is not None and isinstance(backend, BoardFrame)
    read = backend.read(path)
    design = read.design
    return design, build_scene(design, backend, name=path.name, data=path.read_bytes(), backend=backend.name)


def _labels(scene: dict[str, Any], prefix: str) -> int:
    return sum(1 for prim in scene["prims"] if str(prim[5]).startswith(prefix))


def test_kicad_counts() -> None:
    """Scenario "Counts of a KiCad board"."""
    design, scene = _scene(KICAD)
    board = design.board
    assert board is not None
    assert scene["schema"] == SCHEMA
    pads = registry.for_path(KICAD)
    assert isinstance(pads, BoardFrame)
    copper_entries = sum(len(pad.copper) for pad in pads.board_pads(design))
    pad_copper = [p for p in scene["prims"] if p[0].endswith(".Cu") and "-" in str(p[5]) and p[4] >= 0]
    assert len(pad_copper) >= copper_entries
    assert _labels(scene, "track ") == len(board.tracks)
    assert _labels(scene, "arc ") == len(board.arcs)
    assert sum(1 for p in scene["prims"] if p[5].startswith("via ") and p[0] == DRILL) == len(board.vias)
    fills = sum(len(z.fills) for z in board.zones)
    assert sum(1 for p in scene["prims"] if p[1] == "p" and p[0].endswith(".Cu") and p[4] < 0) == fills
    colors = {layer["id"]: layer["color"] for layer in scene["layers"]}
    assert colors["F.Cu"] == COLORS["F.Cu"] and colors["B.Cu"] == COLORS["B.Cu"]
    assert scene["meta"]["counts"]["tracks"] == len(board.tracks)
    assert summary(scene)["counts"] == scene["meta"]["counts"]
    json.dumps(scene)  # plain JSON values only


def test_kicad_texts_and_nets() -> None:
    design, scene = _scene(KICAD)
    refs = {comp["ref"] for comp in scene["comps"]}
    assert refs == {c.ref for c in design.circuit.components}
    assert set(scene["nets"]) == {net.name for net in design.circuit.nets}
    shown = {t[10] for t in scene["texts"]}
    assert refs & shown, "the visible reference fields are drawn"
    nets = Counter(scene["nets"][p[3]] for p in scene["prims"] if p[3] >= 0)
    assert nets, "copper carries its net"


def test_altium_derived_mask() -> None:
    """Scenario "An Altium board without mask layers"."""
    _, scene = _scene(ALTIUM)
    layers = {layer["id"] for layer in scene["layers"]}
    assert {"F.Mask", "B.Mask"} <= layers
    assert any("mask and paste openings are derived" in note for note in scene["meta"]["notes"])
    assert scene["meta"]["backend"] == "altium"


def test_altium_unfilled_zones_are_outlines() -> None:
    design, scene = _scene(ALTIUM)
    board = design.board
    assert board is not None
    unfilled = [z for z in board.zones if not z.fills]
    assert len(scene["meta"]["unfilled"]) == len(unfilled)
    assert sum(1 for p in scene["prims"] if p[0] == ZONE_OUTLINE) == len(unfilled)


def test_bodies_follow_their_footprints() -> None:
    design, scene = _scene(BODIES)
    board = design.board
    assert board is not None
    expected = sum(
        1 for fp in board.footprints for b in fp.bodies if not b.projection_unknown and len(b.outline) >= 3
    )
    assert len(scene["bodies"]) == expected > 0
    for body in scene["bodies"]:
        assert body["z1"] > body["z0"] >= 0 and len(body["ring"]) >= 6


def test_no_board() -> None:
    design, _ = _scene(KICAD)
    with pytest.raises(ValueError, match="no board"):
        build_scene(dataclasses.replace(design, board=None), None, name="empty")


def test_net_lengths_and_part_parameters() -> None:
    """Change c0187: each net's pad count and routed length (centre lines of its tracks and arcs), and the
    parameters of each part (KiCad fields; Altium component records)."""
    design, scene = _scene(KICAD)
    names = {net.id: net.name for net in design.circuit.nets}
    board = design.board
    assert board is not None
    expected: Counter[str] = Counter()
    for track in board.tracks:
        name = names.get(track.net_id or "")
        if name:
            expected[name] += round(math.hypot(track.end.x - track.start.x, track.end.y - track.start.y))
    for arc in board.arcs:  # geometry's own tested arc length
        expected[names[arc.net_id or ""]] += arc_length(arc.start, arc.mid, arc.end)
    assert board.arcs and len(scene["netinfo"]) == len(scene["nets"])
    for name, info in zip(scene["nets"], scene["netinfo"], strict=True):
        assert info["length"] == round(expected[name] / 1000)
        assert info["pads"] == sum(1 for pad in scene["pads"] if pad["net"] == name)
    _design, fields = _scene(ROOT / "tests" / "data" / "kicad" / "routing" / "pair_two_headers.kicad_pcb")
    assert "Description" in fields["comps"][0]["params"]
    assert "Reference" not in fields["comps"][0]["params"]  # shown by its own row
    blink = scene_of(ROOT / "tests" / "data" / "altium" / "blink" / "blink.PcbDoc")
    u1 = next(c for c in blink["comps"] if c["ref"] == "U1")
    assert u1["params"]["Library reference"] == "Mini_QFP32_IC" and u1["uid"].endswith("IOEYSXFL")


def test_every_zone_outline_is_on_its_view_layer() -> None:
    """Change c0193: every zone's outline, filled or not, on ``View.ZoneEdge``, which starts hidden."""
    design, scene = _scene(ALTIUM)
    board = design.board
    assert board is not None
    outlined = [z for z in board.zones if len(z.outline) >= 3]
    assert sum(1 for p in scene["prims"] if p[0] == ZONE_EDGE) == len(outlined)
    layer = next(layer for layer in scene["layers"] if layer["id"] == ZONE_EDGE)
    assert layer["visible"] is False and layer["kind"] == "view"

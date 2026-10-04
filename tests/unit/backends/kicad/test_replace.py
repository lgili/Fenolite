# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprints re-placed on a read board (capability kicad-file-backend, "Footprints are re-placed on a read
board"; change c0022)."""

from __future__ import annotations

import dataclasses
from functools import cache
from pathlib import Path

import pytest
from _buildhelp import blink, build, resolver

from fenolite.backends.kicad.embed import PATH_PROPERTY, place_footprint, with_property
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.replace import (
    EVIDENCE,
    FIELD_VALUES,
    PlacementError,
    footprint_ref,
    move_footprint,
)
from fenolite.backends.kicad.roundtrip import rt1
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.core.coords import Point
from fenolite.core.evidence import Level
from fenolite.lens import fields as lens_fields
from fenolite.model.board import FootprintInstance
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

FIXTURE = Path(__file__).resolve().parents[4] / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
MM = 1_000_000


def two_layer() -> Design:
    return read_board(FIXTURE.read_text(encoding="utf-8"), file=FIXTURE.name)


@cache
def built_text() -> str:
    output = build(blink(), 10)
    return output.files["blink.kicad_pcb"].decode("utf-8")


def built() -> Design:
    return read_board(built_text(), file="blink.kicad_pcb")


def by_ref(design: Design) -> dict[str, FootprintInstance]:
    assert design.board is not None
    return {footprint_ref(design, fp): fp for fp in design.board.footprints}


def definitions(design: Design) -> dict[str, FootprintDef]:
    assert design.board is not None
    found = resolver(10)
    return {fp.lib_ref: found.footprint(fp.lib_ref) for fp in design.board.footprints}


def footprint_nodes(text: str) -> tuple[list[Node], list[object]]:
    root = parse(text)
    nodes = [c for c in root.children if isinstance(c, Node) and c.name == "footprint"]
    rest = [c for c in root.children if not (isinstance(c, Node) and c.name == "footprint")]
    return nodes, rest


def test_translate_keeps_every_slot() -> None:
    design = two_layer()
    r1 = by_ref(design)["R1"]
    moved = move_footprint(design, r1.id, at=Point(r1.position.x + 2 * MM, r1.position.y))
    before, after = write_board(design, target=10).text, write_board(moved, target=10).text
    old_nodes, old_rest = footprint_nodes(before)
    new_nodes, new_rest = footprint_nodes(after)
    assert old_rest == new_rest and old_nodes[1:] == new_nodes[1:]
    changed = [(a, b) for a, b in zip(old_nodes[0].children, new_nodes[0].children, strict=True) if a != b]
    assert len(changed) == 1
    was, now = changed[0]
    assert isinstance(was, Node) and isinstance(now, Node) and was.name == now.name == "at"
    assert [a.text for a in was.atoms()] == ["20", "15", "90"]
    assert [a.text for a in now.atoms()] == ["22", "15", "90"]
    assert rt1(after, file=FIXTURE.name).passed
    new = by_ref(moved)["R1"]
    assert dataclasses.replace(new, position=r1.position) == r1


def test_translate_to_the_same_place_changes_nothing() -> None:
    design = two_layer()
    r1 = by_ref(design)["R1"]
    assert move_footprint(design, r1.id, at=r1.position, rotation=r1.rotation, side="top") is design
    assert move_footprint(design, r1.id) is design


def test_order_is_kept() -> None:
    design = two_layer()
    assert design.board is not None
    d1 = by_ref(design)["D1"]
    moved = move_footprint(design, d1.id, at=Point(30 * MM, 20 * MM))
    assert moved.board is not None
    assert [fp.id for fp in moved.board.footprints] == [fp.id for fp in design.board.footprints]
    assert moved.board.footprints[0] == design.board.footprints[0]


def test_rotation_from_the_definition() -> None:
    design = built()
    assert design.board is not None
    known = definitions(design)
    old = by_ref(design)
    moved = move_footprint(design, old["U1"].id, rotation=90_000_000, definitions=known, force=True)
    moved = move_footprint(moved, old["R1"].id, side="bottom", definitions=known)
    new = by_ref(moved)
    components = {c.ref: c for c in design.circuit.components}
    copper = tuple(layer.name for layer in design.board.layers if layer.kind == "copper")
    for ref, rotation, side in (("U1", 90_000_000, "top"), ("R1", 0, "bottom")):
        was, now = old[ref], new[ref]
        extended = with_property(known[was.lib_ref], name=PATH_PROPERTY, value=ref)
        fresh = place_footprint(
            extended,
            component=components[ref],
            at=was.position,
            rotation=rotation,
            side=side,  # type: ignore[arg-type]
            locked=was.locked,
            key=ref,
            copper=copper,
        )
        nets = {p.number: p.net_id for p in was.pads}
        wanted = dataclasses.replace(
            fresh,
            id=was.id,
            native_ids=was.native_ids,
            provenance=was.provenance,
            pads=tuple(dataclasses.replace(p, net_id=nets.get(p.number)) for p in fresh.pads),
        )
        assert now == wanted
        assert (now.position, now.rotation, now.side, now.locked) == (
            was.position,
            rotation,
            side,
            was.locked,
        )
        assert now.native_ids == was.native_ids
        assert [f.name for f in now.fields] == [f.name for f in was.fields]
        assert {p.number: p.net_id for p in now.pads} == nets and any(nets.values())
    assert new["D1"] == old["D1"]
    text = write_board(moved, target=10).text
    assert rt1(text, file="blink.kicad_pcb").passed
    back = by_ref(read_board(text, file="blink.kicad_pcb"))
    assert (back["U1"].rotation, back["R1"].side) == (90_000_000, "bottom")
    assert moved.circuit == design.circuit


def test_rotation_keeps_the_field_placement_and_a_flip_takes_the_definitions() -> None:
    design = built()
    assert design.board is not None
    known = definitions(design)
    r1 = by_ref(design)["R1"]
    reference = next(f for f in r1.fields if f.name == "Reference")
    edited = dataclasses.replace(reference, position=Point(0, -3 * MM), visible=False)
    custom = dataclasses.replace(r1, fields=tuple(edited if f is reference else f for f in r1.fields))
    board = dataclasses.replace(
        design.board, footprints=tuple(custom if fp is r1 else fp for fp in design.board.footprints)
    )
    design = dataclasses.replace(design, board=board)
    turned = by_ref(move_footprint(design, r1.id, rotation=30_000_000, definitions=known))["R1"]
    kept = next(f for f in turned.fields if f.name == "Reference")
    assert (kept.position, kept.visible) == (Point(0, -3 * MM), False)
    flipped = by_ref(move_footprint(design, r1.id, side="bottom", definitions=known))["R1"]
    fresh = next(f for f in flipped.fields if f.name == "Reference")
    assert fresh.visible and fresh.position != Point(0, -3 * MM) and fresh.layer.startswith("B.")


def test_no_definition() -> None:
    design = two_layer()
    r1 = by_ref(design)["R1"]
    with pytest.raises(PlacementError) as caught:
        move_footprint(design, r1.id, rotation=0, definitions={})
    (issue,) = caught.value.issues
    assert (issue.code, issue.severity, issue.where) == ("place.no-definition", "error", "R1")
    with pytest.raises(PlacementError):
        move_footprint(design, r1.id, side="bottom")
    assert by_ref(move_footprint(design, r1.id, at=Point(MM, MM)))["R1"].position == Point(MM, MM)


def test_locked_footprint() -> None:
    design = built()
    u1 = by_ref(design)["U1"]
    assert u1.locked
    with pytest.raises(PlacementError) as caught:
        move_footprint(design, u1.id, at=Point(110 * MM, 110 * MM))
    (issue,) = caught.value.issues
    assert (issue.code, issue.where) == ("place.locked", "U1")
    moved = by_ref(move_footprint(design, u1.id, at=Point(110 * MM, 110 * MM), force=True))["U1"]
    assert moved.position == Point(110 * MM, 110 * MM) and moved.locked


def test_unknown_footprint() -> None:
    with pytest.raises(PlacementError) as caught:
        move_footprint(two_layer(), "fp_missing", at=Point(0, 0))
    assert caught.value.issues[0].code == "place.unknown-ref"


def test_field_values_equal_the_lens() -> None:
    assert FIELD_VALUES == lens_fields.FIELD_VALUES


def test_evidence_names_the_hypothesis() -> None:
    assert EVIDENCE.hypotheses == ("H-K-PLACE-MOVE",) and EVIDENCE.level in (
        Level.INFERRED,
        Level.KICAD_VERIFIED,
    )

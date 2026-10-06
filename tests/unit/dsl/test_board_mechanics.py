# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independently authored mechanical requests and unchanged old defaults (c0096)."""

from dataclasses import replace

import pytest

from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.dsl import BOARD_ORIGIN, Design, DslError, MechanicalIntent, Part, mm, placements, to_model
from fenolite.model import canonical
from fenolite.model.board import Board, FootprintInstance, Hole, Keepout


def test_declared_frame_and_provenance_roundtrip() -> None:
    d = Design("mechanics")
    d.board(mm(23), mm(17))
    hole = d.hole("fix", mm(2), mm(3), mm(1), tolerance="0.1mm", source="authored probe", status="measured")
    keepout = d.keepout(
        "access",
        [(mm(1), mm(1)), (mm(4), mm(1)), (mm(4), mm(5)), (mm(1), mm(5))],
        no_footprints=True,
        layers=("B.Cu",),
        status="estimated",
    )
    part = Part("J1", "Demo:Connector")
    d.add(part)
    anchor = MechanicalIntent(
        "connector", tolerance=30, status="measured", source="probe", evidence=Evidence(Level.INFERRED)
    )
    part.place(mm(7), mm(4), locked=True, anchor=anchor)
    model = to_model(d)
    assert model.board is not None
    assert model.board.holes[0].position == Point(BOARD_ORIGIN.x + 2_000_000, BOARD_ORIGIN.y + 3_000_000)
    assert model.board.keepouts[0].outline[0] == Point(BOARD_ORIGIN.x + 1_000_000, BOARD_ORIGIN.y + 1_000_000)
    assert model.board.holes[0].intent == hole.intent
    assert model.board.keepouts[0].intent == keepout.intent
    assert hole.position == Point(2_000_000, 3_000_000)  # recording does not mutate requests
    assert placements(d)["J1"].anchor == anchor and placements(d)["J1"].locked
    text = canonical.dumps(model.board)
    assert canonical.dumps(canonical.loads(text, Board)) == text
    assert (
        "measured" in text
        and "estimated" in text
        and "UNKNOWN" not in canonical.dumps(Board(id=model.board.id))
    )


def test_duplicate_keys_and_malformed_requests() -> None:
    d = Design("mechanics")
    d.board(mm(9), mm(8))
    d.hole("a", "1mm", "1mm", "1mm")
    with pytest.raises(DslError, match="twice"):
        d.hole("a", "2mm", "2mm", "1mm")
    for kwargs in ({"frame": "component"}, {"tolerance": "-1nm"}, {"status": "verified"}):
        with pytest.raises(DslError):
            d.hole("b", "1mm", "1mm", "1mm", **kwargs)
    with pytest.raises(DslError, match="positive"):
        d.hole("b", "1mm", "1mm", "0nm")
    with pytest.raises(DslError, match="unit"):
        d.hole("b", 1, "1mm", "1mm")
    with pytest.raises(DslError, match="exclusion"):
        d.keepout("a", [("1mm", "1mm"), ("2mm", "1mm"), ("2mm", "2mm")])
    part = Part("J1", "Demo:Connector")
    with pytest.raises(DslError, match="locked=True"):
        part.place("1mm", "1mm", anchor=MechanicalIntent("j"))


def test_optional_model_fields_keep_old_canonical_bytes() -> None:
    hole = Hole(id="probe", position=Point(1, 2), drill=3)
    keepout = Keepout(id="probe", outline=(Point(0, 0), Point(1, 0), Point(0, 1)))
    fp = FootprintInstance(id="probe", component_id="", lib_ref="", position=Point(0, 0))
    for entity in (hole, keepout, fp):
        assert "intent" not in canonical.dumps(entity) and "anchor" not in canonical.dumps(entity)
    assert replace(hole, intent=MechanicalIntent("p")).drill == hole.drill


def test_mechanics_need_board() -> None:
    d = Design("mechanics")
    d.hole("a", "1mm", "1mm", "1mm")
    with pytest.raises(DslError, match="board"):
        to_model(d)


@pytest.mark.parametrize("copper", [2, 4])
def test_default_keepout_covers_board_copper_in_model_and_native_text(copper: int) -> None:
    from fenolite.backends.kicad.layers import created_layers
    from fenolite.backends.kicad.pcb import read_board, write_board

    design = Design("layers")
    design.board("20mm", "20mm", copper=copper)
    design.keepout("area", [("1mm", "1mm"), ("4mm", "1mm"), ("4mm", "4mm")], no_pads=True)
    model = to_model(design)
    expected = ("F.Cu", "B.Cu") if copper == 2 else ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
    assert model.board.keepouts[0].layers == expected
    written = write_board(
        replace(model, board=replace(model.board, layers=created_layers(copper))), target=10
    )
    readback = read_board(written.text)
    assert readback.board.keepouts[0].layers == expected


def test_estimated_intent_status_is_source_independent() -> None:
    intent = MechanicalIntent("estimate", source="authored estimate", status="estimated")
    assert intent.status == "estimated"
    with pytest.raises(ValueError, match="status"):
        MechanicalIntent("invalid", status="image")

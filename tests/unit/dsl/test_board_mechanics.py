# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independently authored mechanical intent and unchanged old defaults (c0096)."""

from dataclasses import replace

import pytest

from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.dsl import Design, DslError, MechanicalIntent, Part, mm, placements, to_model
from fenolite.model import canonical
from fenolite.model.board import Board, FootprintInstance, Hole, Keepout


def test_locked_anchor_is_conversion_metadata() -> None:
    """A locked placement carries its ``MechanicalIntent`` into ``placements``; holes and keep-outs are
    declared with ``hole()`` and ``rule_area()`` (c0102, c0103), which carry no intent."""
    d = Design("mechanics")
    d.board(mm(23), mm(17))
    part = Part("J1", "Demo:Connector")
    d.add(part)
    anchor = MechanicalIntent(
        "connector", tolerance=30, status="measured", source="probe", evidence=Evidence(Level.INFERRED)
    )
    part.place(mm(7), mm(4), locked=True, anchor=anchor)
    assert placements(d)["J1"].anchor == anchor and placements(d)["J1"].locked
    model = to_model(d)
    assert model.board is not None and not model.board.holes
    assert "UNKNOWN" not in canonical.dumps(Board(id=model.board.id))


def test_anchor_needs_a_locked_placement() -> None:
    part = Part("J1", "Demo:Connector")
    with pytest.raises(DslError, match="locked=True"):
        part.place("1mm", "1mm", anchor=MechanicalIntent("j"))
    with pytest.raises(DslError, match="MechanicalIntent"):
        part.place("1mm", "1mm", locked=True, anchor="j")  # type: ignore[arg-type]


def test_neutral_hole_and_keepout_calls_are_not_offered() -> None:
    """The maintainer's decision 2 of 2026-10-07: ``hole()`` of c0102 and ``rule_area()`` of c0103 stand,
    and c0096's DSL ``hole(key, …)`` and ``keepout(key, …)`` go."""
    assert not hasattr(Design, "keepout") and not hasattr(Design, "board_hole")
    assert not hasattr(Design("m"), "keepouts")


def test_optional_model_fields_keep_old_canonical_bytes() -> None:
    hole = Hole(id="probe", position=Point(1, 2), drill=3)
    keepout = Keepout(id="probe", outline=(Point(0, 0), Point(1, 0), Point(0, 1)))
    fp = FootprintInstance(id="probe", component_id="", lib_ref="", position=Point(0, 0))
    for entity in (hole, keepout, fp):
        assert "intent" not in canonical.dumps(entity) and "anchor" not in canonical.dumps(entity)
    assert replace(hole, intent=MechanicalIntent("p")).drill == hole.drill


def test_estimated_intent_status_is_source_independent() -> None:
    intent = MechanicalIntent("estimate", source="authored estimate", status="estimated")
    assert intent.status == "estimated"
    with pytest.raises(ValueError, match="status"):
        MechanicalIntent("invalid", status="image")

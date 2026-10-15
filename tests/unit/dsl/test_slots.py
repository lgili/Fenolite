# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Milled slots in the DSL (capability design-dsl, "Slots in the DSL"; change c0167)."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from fenolite.core.coords import Point
from fenolite.core.stadium import stadium
from fenolite.dsl import Design, DslError, arc_to, mm, nm, shape, to_model
from fenolite.dsl.convert import key_id
from fenolite.dsl.shape import closed_ring

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "data" / "slots" / "design.py"
MM = 1_000_000


def board() -> Design:
    d = Design("slots")
    d.board(mm(40), mm(30))
    return d


def test_a_slot_in_the_model() -> None:
    d = board()
    assert d.slot(mm(15), mm(10), length=mm(12), width=mm(2), rot=30) == "S1"
    model = to_model(d)
    assert model.board is not None and model.board.outline is not None
    outline = model.board.outline
    assert outline.cutouts == ()
    (found,) = outline.slots
    assert found.name == "S1" and found.id == key_id("slot", "S1")
    assert found.center == Point(115 * MM, 110 * MM)
    assert (found.length, found.width, found.rotation) == (12 * MM, 2 * MM, 30_000_000)


def test_refused_slots() -> None:
    d = board()
    with pytest.raises(DslError):
        d.slot(mm(5), mm(5), length=mm(2), width=mm(2))
    with pytest.raises(DslError):
        d.slot(mm(5), mm(5), length=mm(4), width=nm(3))
    d.slot(mm(5), mm(5), length=mm(4), width=mm(1), name="S1")
    with pytest.raises(DslError):
        d.slot(mm(20), mm(5), length=mm(4), width=mm(1), name="S1")
    with pytest.raises(DslError):
        d.slot(mm(20), mm(5), length=mm(4), width=mm(1), name="no spaces")
    with pytest.raises(DslError):
        Design("early").slot(mm(5), mm(5), length=mm(4), width=mm(1))


def test_default_names_skip_taken_ones() -> None:
    d = board()
    d.slot(mm(5), mm(5), length=mm(4), width=mm(1), name="S2")
    assert d.slot(mm(10), mm(5), length=mm(4), width=mm(1)) == "S3"
    assert d.slot(mm(15), mm(5), length=mm(4), width=mm(1)) == "S4"
    assert list(d.slot_specs) == ["S2", "S3", "S4"]


def test_rotation_is_kept_modulo_a_half_turn() -> None:
    d = board()
    d.slot(mm(15), mm(10), length=mm(12), width=mm(2), rot=210)
    assert d.slot_specs["S1"].rotation == 30_000_000


def test_shape_stadium_is_the_ring_of_the_slot() -> None:
    path = shape.stadium(mm(15), mm(10), mm(12), mm(2), rot=30)
    ring = closed_ring(path, "cutout()")
    exact = stadium(Point(115 * MM, 110 * MM), 12 * MM, 2 * MM, 30_000_000)
    assert ring.points == exact.points
    assert ring.arcs == exact.arcs()


def test_shape_stadium_horizontal_equals_shape_slot() -> None:
    assert shape.stadium(mm(15), mm(10), mm(12), mm(2)) == shape.slot(
        (mm(10), mm(10)), (mm(20), mm(10)), mm(2)
    )


def test_shape_stadium_refuses_bad_sizes() -> None:
    with pytest.raises(DslError, match="shape.stadium"):
        shape.stadium(mm(0), mm(0), mm(2), mm(2))
    with pytest.raises(DslError, match="even"):
        shape.stadium(mm(0), mm(0), mm(4), nm(3))


def test_a_design_without_slots_writes_no_key() -> None:
    d = board()
    d.cutout(((mm(5), mm(5)), arc_to((mm(6), mm(4)), (mm(7), mm(5))), (mm(6), mm(7))))
    model = to_model(d)
    assert model.board is not None and model.board.outline is not None
    assert model.board.outline.slots == ()


def test_the_shared_fixture() -> None:
    design = runpy.run_path(str(FIXTURE))["design"]
    assert isinstance(design, Design)
    model = to_model(design)
    assert model.board is not None and model.board.outline is not None
    outline = model.board.outline
    assert [slot.name for slot in outline.slots] == ["S1", "S2", "S3"]
    assert len(outline.cutouts) == 1 and len(outline.arcs) == 4
    assert [c.ref for c in model.circuit.components] == ["H1"]

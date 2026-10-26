# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Milled slots of the board outline in the model (capability design-model, "Board slots"; change c0167)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model import Board, Outline, OutlineArc, OutlineSlot, canonical
from fenolite.model.design import Design
from fenolite.model.outline import outline_items, slot_ring

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "data" / "model"
MM = 1_000_000


def slot(name: str = "S1", rotation: int = 30_000_000) -> OutlineSlot:
    return OutlineSlot(
        id=derived_id("slt", "test", name),
        center=Point(115 * MM, 110 * MM),
        length=12 * MM,
        width=2 * MM,
        rotation=rotation,
        name=name,
    )


def slotted() -> Outline:
    corners = (Point(100 * MM, 100 * MM), Point(140 * MM, 100 * MM), Point(140 * MM, 130 * MM))
    return Outline(
        id=derived_id("out", "test", "outline"),
        points=(*corners, Point(100 * MM, 130 * MM)),
        slots=(slot(),),
    )


def test_a_slot_round_trips(tmp_path: Path) -> None:
    outline = slotted()
    design = dataclasses.replace(
        Design.new("slots", seed=0), board=Board(id=derived_id("brd", "test", "board"), outline=outline)
    )
    canonical.dump_dir(design, tmp_path)
    loaded = canonical.load_dir(tmp_path)
    assert loaded.board is not None and loaded.board.outline == outline
    data = json.loads((tmp_path / "board.json").read_text(encoding="utf-8"))["outline"]["slots"]
    assert data[0]["center"] == {"x": 115 * MM, "y": 110 * MM}
    assert data[0]["rotation"] == 30_000_000 and data[0]["name"] == "S1"


def test_empty_slots_are_omitted() -> None:
    plain = dataclasses.replace(slotted(), slots=())
    text = canonical.dumps(plain)
    assert '"slots"' not in text
    assert canonical.loads(text, Outline) == plain


@pytest.mark.parametrize("name", ["v0.2.0/blink_2layer.board.json", "v0.2.1/blink_2layer.board.json"])
def test_older_documents_keep_their_bytes(name: str) -> None:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    board = canonical.loads(text, Board)
    assert board.outline is None or board.outline.slots == ()
    assert canonical.dumps(board) == text


def test_schema_defines_slots() -> None:
    schema = json.loads((ROOT / "schemas" / "fenolite.model.v0" / "board.json").read_text(encoding="utf-8"))
    fields = schema["$defs"]["OutlineSlot"]["properties"]
    assert {"center", "length", "width", "rotation", "name"} <= set(fields)
    assert "slots" in schema["$defs"]["Outline"]["properties"]


def test_outline_items_name_every_ring() -> None:
    outline = dataclasses.replace(
        slotted(),
        cutouts=((Point(120 * MM, 120 * MM), Point(118 * MM, 120 * MM)),),
        arcs=(OutlineArc(1, 0, Point(119 * MM, 119 * MM)), OutlineArc(1, 1, Point(119 * MM, 121 * MM))),
        slots=(slot("S1", 0), dataclasses.replace(slot("", 0), name="")),
    )
    items = outline_items(outline)
    assert [item.name for item in items] == ["board", "cut-out 1", "slot S1", f"slot {outline.slots[1].id}"]
    assert items[0].mids == (None, None, None, None)
    assert items[1].mids == (Point(119 * MM, 119 * MM), Point(119 * MM, 121 * MM))
    s1 = items[2]
    assert s1.points == (
        Point(110 * MM, 109 * MM),
        Point(120 * MM, 109 * MM),
        Point(120 * MM, 111 * MM),
        Point(110 * MM, 111 * MM),
    )
    assert s1.mids == (None, Point(121 * MM, 110 * MM), None, Point(109 * MM, 110 * MM))
    assert s1.is_slot and not items[1].is_slot


def test_a_slot_of_a_bad_size_has_no_ring() -> None:
    bad = dataclasses.replace(slot(), length=2 * MM)
    with pytest.raises(ValueError):
        slot_ring(bad)
    assert [item.name for item in outline_items(dataclasses.replace(slotted(), slots=(bad,)))] == ["board"]

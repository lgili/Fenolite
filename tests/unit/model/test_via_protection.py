# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Via protection in the board model (capability design-model, "Via protection in the board model";
change c0112): the value object, the two additive fields, the schema and old documents."""

from __future__ import annotations

import dataclasses
import json
import random
from pathlib import Path

import _schema

from fenolite.core.coords import Point
from fenolite.core.ids import new_id
from fenolite.model.board import Board, Via, ViaProtection
from fenolite.model.canonical import dumps, loads
from fenolite.model.design import SCHEMA_VERSION

ROOT = Path(__file__).resolve().parents[3]
OLD_BOARD = ROOT / "tests" / "data" / "model" / "v0.2.1" / "blink_2layer.board.json"
SENTENCE = "0.2.x and 0.3.0 cannot read a `board.json` that carries `protection` or `via_protection`"
FIELDS = (
    "tenting_front", "tenting_back", "covering_front", "covering_back", "plugging_front", "plugging_back",
    "capping", "filling",
)  # fmt: skip
RNG = random.Random(112)


def via(**more: object) -> Via:
    return Via(id=new_id("via", RNG), position=Point(1_000_000, 2_000_000), diameter=600_000, drill=300_000,
               **more)  # type: ignore[arg-type]  # fmt: skip


def test_defaults() -> None:
    made = via()
    assert made.protection == ViaProtection()
    assert tuple(f.name for f in dataclasses.fields(ViaProtection)) == FIELDS
    assert all(getattr(made.protection, name) is None for name in FIELDS)
    assert Board(id=new_id("brd", RNG)).via_protection is None
    assert dataclasses.is_dataclass(ViaProtection) and ViaProtection.__dataclass_params__.frozen  # type: ignore[attr-defined]
    assert not hasattr(ViaProtection(), "id")


def test_default_values_are_not_written() -> None:
    """A via whose protection is ``ViaProtection()`` and a board without a default write the text they
    wrote before the fields existed."""
    board = Board(id=new_id("brd", RNG), vias=(via(), via()))
    text = dumps(board)
    assert '"protection"' not in text and '"via_protection"' not in text
    again = loads(text, Board)
    assert all(v.protection == ViaProtection() for v in again.vias) and again.via_protection is None
    assert dumps(again) == text


def test_values_round_trip() -> None:
    protection = ViaProtection(tenting_front=False, plugging_back=True, filling=True)
    default = ViaProtection(tenting_front=True, tenting_back=False)
    board = Board(id=new_id("brd", RNG), vias=(via(protection=protection),), via_protection=default)
    data = json.loads(dumps(board))
    assert data["via_protection"] == {"tenting_front": True, "tenting_back": False}
    assert data["vias"][0]["protection"] == {"tenting_front": False, "plugging_back": True, "filling": True}
    assert loads(dumps(board), Board) == board
    assert _schema.validate(data, _schema.load("fenolite.model.v0/board.json")) == []


def test_v021_document_loads_and_serialises_to_its_bytes() -> None:
    """The ``board.json`` that release 0.2.1 wrote for ``examples/blink_2layer`` (the fixture of c0101)
    holds neither key, loads with the defaults and dumps to its own bytes; the documents say that the
    other direction does not hold."""
    text = OLD_BOARD.read_bytes().decode("utf-8")
    for key in ("protection", "via_protection"):
        assert f'"{key}"' not in text
    board = loads(text, Board)
    assert board.via_protection is None
    assert all(v.protection == ViaProtection() for v in board.vias)
    assert dumps(board).encode("utf-8") == OLD_BOARD.read_bytes()
    assert SCHEMA_VERSION == "0"
    for name in ("docs/design-model.md", "CHANGELOG.md"):
        assert SENTENCE in " ".join((ROOT / name).read_text(encoding="utf-8").split()), name


def test_not_a_boolean_fails_the_schema() -> None:
    board = Board(id=new_id("brd", RNG), vias=(via(protection=ViaProtection(filling=True)),))
    data = json.loads(dumps(board))
    schema = _schema.load("fenolite.model.v0/board.json")
    assert _schema.validate(data, schema) == []
    data["vias"][0]["protection"]["filling"] = "yes"
    problems = _schema.validate(data, schema)
    assert problems and any("/vias/0/protection/filling" in p for p in problems)


def test_schema_lists_the_fields() -> None:
    schema = _schema.load("fenolite.model.v0/board.json")
    assert "via_protection" in schema["properties"]
    assert "protection" in schema["$defs"]["Via"]["properties"]
    assert tuple(schema["$defs"]["ViaProtection"]["properties"]) == FIELDS

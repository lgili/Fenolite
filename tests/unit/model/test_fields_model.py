# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint fields in the board model (capability design-model, "Footprint fields"; change c0030)."""

from __future__ import annotations

import dataclasses
import importlib.util
import json
import random
from pathlib import Path
from typing import Any, get_args

import _schema
import pytest

from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id, new_id
from fenolite.model import Board, FieldJustifyH, FieldJustifyV, FootprintField, FootprintInstance
from fenolite.model.canonical import dumps, loads

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = "fenolite.model.v0/board.json"


def _field(name: str, **changes: Any) -> FootprintField:
    field = FootprintField(
        id=derived_id("fld", "kicad", f"x:field:{name}"),
        name=name,
        position=Point(0, -1_430_000),
        layer="F.SilkS",
        size=Size(1_000_000, 1_000_000),
    )
    return dataclasses.replace(field, **changes)


def _board(*fields: FootprintField) -> Board:
    rng = random.Random(30)
    footprint = FootprintInstance(
        id=new_id("fp", rng), component_id="", lib_ref="L:F", position=Point(0, 0), fields=fields
    )
    return Board(id=new_id("brd", rng), footprints=(footprint,))


def _document(*fields: FootprintField) -> dict[str, Any]:
    return json.loads(dumps(_board(*fields)))


def test_defaults() -> None:
    field = _field("Reference")
    assert (field.rotation, field.thickness, field.visible, field.mirrored) == (0, None, True, False)
    assert (field.h_justify, field.v_justify) == ("center", "center")
    assert get_args(FieldJustifyH) == ("left", "center", "right")
    assert get_args(FieldJustifyV) == ("top", "center", "bottom")
    assert not hasattr(field, "value") and not hasattr(field, "text")


def test_old_documents_still_load() -> None:
    document = _document()
    assert "fields" not in document["footprints"][0]
    board = loads(json.dumps(document), Board)
    assert all(fp.fields == () for fp in board.footprints)


def test_unknown_justification_rejected_by_the_schema() -> None:
    schema = _schema.load(SCHEMA)
    document = _document(_field("Reference", h_justify="left"))
    assert _schema.validate(document, schema) == []
    document["footprints"][0]["fields"][0]["h_justify"] = "middle"
    problems = _schema.validate(document, schema)
    assert problems and all(p.startswith("/footprints/0/fields/0/h_justify") for p in problems)


def test_float_rejected_in_a_field() -> None:
    schema = _schema.load(SCHEMA)
    document = _document(_field("Reference", position=Point(1, 2)))
    document["footprints"][0]["fields"][0]["position"]["x"] = 1.5
    problems = _schema.validate(document, schema)
    assert problems and all(p.startswith("/footprints/0/fields/0/position/x") for p in problems)


def test_field_order_survives_the_canonical_form() -> None:
    board = _board(_field("Value"), _field("Reference"))
    again = loads(dumps(board), Board)
    assert [f.name for f in again.footprints[0].fields] == ["Value", "Reference"]
    assert again == board and dumps(again) == dumps(board)


def test_every_value_survives_the_canonical_form() -> None:
    field = _field(
        "Value",
        rotation=270_000_000,
        thickness=120_000,
        visible=False,
        h_justify="right",
        v_justify="top",
        mirrored=True,
        layer="B.SilkS",
        size=Size(800_000, 900_000),
        native_ids={"kicad": "00000000-0000-4000-8000-000000000030"},
    )
    assert loads(dumps(_board(field)), Board).footprints[0].fields == (field,)


def test_field_prefix() -> None:
    rng = random.Random(1)
    assert new_id("fld", rng).startswith("fld_")
    assert derived_id("fld", "kicad", "x:field:Reference").startswith("fld_")
    with pytest.raises(ValueError):
        new_id("fldx", rng)


def test_schemas_regenerated() -> None:
    spec = importlib.util.spec_from_file_location("gen_schemas", ROOT / "tools" / "gen_schemas.py")
    assert spec is not None and spec.loader is not None
    text = (ROOT / "schemas" / SCHEMA).read_text(encoding="utf-8")
    for word in ("FootprintField", '"fields"', '"h_justify"', '"v_justify"', '"mirrored"'):
        assert word in text, word

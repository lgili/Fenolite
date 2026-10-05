# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import json
import random

import _schema
import pytest

from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError
from fenolite.core.ids import new_id
from fenolite.core.units import parse_angle
from fenolite.model import (
    Board,
    ComponentBody,
    FootprintInstance,
    Pad,
    Padstack,
    PadstackLayer,
    StackLayer,
    Stackup,
    Zone,
)
from fenolite.model.canonical import dumps, loads
from fenolite.model.library import FootprintDef, Library


def test_ninety_degrees_is_exact() -> None:
    rng = random.Random(1)
    fp = FootprintInstance(
        id=new_id("fp", rng),
        component_id="",
        lib_ref="L:F",
        position=Point(0, 0),
        rotation=parse_angle("90deg"),
    )
    assert fp.rotation == 90_000_000


def test_board_structure() -> None:
    rng = random.Random(2)
    stack = Stackup(
        id=new_id("stk", rng),
        layers=(
            StackLayer(id=new_id("sly", rng), name="F.Cu", kind="copper", thickness=35_000),
            StackLayer(
                id=new_id("sly", rng), name="core", kind="dielectric", thickness=1_510_000, epsilon_r="4.5"
            ),
            StackLayer(id=new_id("sly", rng), name="B.Cu", kind="copper", thickness=35_000),
        ),
    )
    pad = Pad(
        id=new_id("pad", rng),
        number="1",
        shape="roundrect",
        size=Size(900_000, 950_000),
        position=Point(-800_000, 0),
        layers=("F.Cu", "F.Paste", "F.Mask"),
        padstack=Padstack(
            id=new_id("pst", rng), layers=(PadstackLayer("F.Cu", "rect", Size(900_000, 950_000)),)
        ),
    )
    zone = Zone(id=new_id("zon", rng), outline=(Point(0, 0), Point(10, 0), Point(10, 10)), layers=("F.Cu",))
    board = Board(id=new_id("brd", rng), stackup=stack, zones=(zone,))
    assert sum(layer.thickness for layer in stack.layers) == 1_580_000
    assert pad.padstack is not None and board.zones[0].fills == ()


# --- padstack holes and offsets, component bodies (change c0043) ----------------------------------------


def _pad(rng: random.Random, padstack: Padstack | None, drill: int | None = 1_000_000) -> Pad:
    return Pad(
        id=new_id("pad", rng),
        number="1",
        shape="circle",
        size=Size(1_800_000, 1_800_000),
        position=Point(0, 0),
        kind="thru_hole",
        drill=drill,
        layers=("F.Cu", "B.Cu"),
        padstack=padstack,
    )


def _board_with(rng: random.Random, pad: Pad, *bodies: ComponentBody) -> Board:
    fp = FootprintInstance(
        id=new_id("fp", rng), component_id="", lib_ref="L:F", position=Point(0, 0), pads=(pad,), bodies=bodies
    )
    return Board(id=new_id("brd", rng), footprints=(fp,))


def test_padstack_written_before_the_hole_fields_still_loads() -> None:
    rng = random.Random(3)
    layers = (
        PadstackLayer("F.Cu", "rect", Size(900_000, 950_000)),
        PadstackLayer("B.Cu", "circle", Size(900_000, 900_000)),
    )
    board = _board_with(rng, _pad(rng, Padstack(id=new_id("pst", rng), layers=layers)))
    text = dumps(board)
    assert "hole_shape" not in text and "offset" not in text and "bodies" not in text
    stack = loads(text, Board).footprints[0].pads[0].padstack
    assert stack is not None
    assert (stack.hole_shape, stack.hole_length, stack.hole_rotation) == ("round", None, 0)
    assert all(layer.offset == Point(0, 0) for layer in stack.layers)


def test_padstack_slot_hole_without_layer_entries() -> None:
    rng = random.Random(4)
    slot = Padstack(id=new_id("pst", rng), hole_shape="slot", hole_length=2_500_000, hole_rotation=90_000_000)
    board = _board_with(rng, _pad(rng, slot))
    loaded = loads(dumps(board), Board).footprints[0].pads[0].padstack
    assert loaded == slot and loaded is not None and loaded.layers == ()


def test_padstack_layer_offset_round_trip_and_schema() -> None:
    rng = random.Random(5)
    layers = (PadstackLayer("F.Cu", "rect", Size(900_000, 950_000), Point(100_000, -50_000)),)
    board = _board_with(rng, _pad(rng, Padstack(id=new_id("pst", rng), layers=layers)))
    text = dumps(board)
    assert loads(text, Board) == board
    for name in ("board.json", "library.json"):
        schema = json.dumps(_schema.load(f"fenolite.model.v0/{name}"))
        for field in ("hole_shape", "hole_length", "hole_rotation", "offset"):
            assert f'"{field}"' in schema, (name, field)
    assert _schema.validate(json.loads(text), _schema.load("fenolite.model.v0/board.json")) == []


def test_unknown_hole_shape_is_rejected_by_the_schema() -> None:
    rng = random.Random(6)
    board = _board_with(rng, _pad(rng, Padstack(id=new_id("pst", rng), hole_shape="slot", hole_length=2)))
    data = json.loads(dumps(board))
    data["footprints"][0]["pads"][0]["padstack"]["hole_shape"] = "oval"
    problems = _schema.validate(data, _schema.load("fenolite.model.v0/board.json"))
    assert problems and all(p.startswith("/footprints/0/pads/0/padstack") for p in problems)
    with pytest.raises(FormatError) as caught:
        loads(json.dumps(data), Board)
    assert caught.value.locator == "/footprints/0/pads/0/padstack/hole_shape"


def test_body_survives_the_canonical_round_trip() -> None:
    rng = random.Random(7)
    outline = (Point(0, 0), Point(2_000_000, 0), Point(2_000_000, -1_000_000), Point(0, -1_000_000))
    body = ComponentBody(
        id=new_id("bdy", rng), kind="extruded", height=1_016_000, outline=outline, layer="Mech.13"
    )
    board = _board_with(rng, _pad(rng, None), body)
    text = dumps(board)
    loaded = loads(text, Board).footprints[0].bodies
    assert loaded == (body,) and loaded[0].outline == outline
    assert _schema.validate(json.loads(text), _schema.load("fenolite.model.v0/board.json")) == []


def test_bodies_default_to_empty_in_old_documents() -> None:
    rng = random.Random(8)
    board = _board_with(rng, _pad(rng, None))
    assert loads(dumps(board), Board).footprints[0].bodies == ()
    definition = FootprintDef(id=new_id("fpd", rng), name="R")
    library = loads(dumps(Library(name="L", footprints=(definition,))), Library)
    assert library.footprints[0].bodies == ()


def test_unknown_body_kind_is_rejected_by_the_schema() -> None:
    rng = random.Random(9)
    body = ComponentBody(id=new_id("bdy", rng), kind="model", height=10, model="part.step")
    data = json.loads(dumps(_board_with(rng, _pad(rng, None), body)))
    data["footprints"][0]["bodies"][0]["kind"] = "sphere"
    problems = _schema.validate(data, _schema.load("fenolite.model.v0/board.json"))
    assert problems and all(p.startswith("/footprints/0/bodies/0/kind") for p in problems)
    with pytest.raises(FormatError) as caught:
        loads(json.dumps(data), Board)
    assert caught.value.locator == "/footprints/0/bodies/0/kind"

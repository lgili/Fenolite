# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
from __future__ import annotations

import dataclasses
import difflib
import json
import random
from pathlib import Path

import _schema
import pytest
from hypothesis import given, settings
from strategies import designs

from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import new_id
from fenolite.core.provenance import Provenance
from fenolite.model import Board, Component, Design, ExtBag, Track
from fenolite.model.canonical import dump_dir, dumps, load_dir, loads


@settings(max_examples=40, deadline=None)
@given(designs())
def test_idempotence(design: Design) -> None:
    for layer, cls in ((design.circuit, type(design.circuit)), (design.board, Board)):
        text = dumps(layer)
        assert dumps(loads(text, cls)) == text


@settings(max_examples=20, deadline=None)
@given(designs())
def test_order_independence(design: Design) -> None:
    assert design.board is not None
    shuffled = dataclasses.replace(
        design.board,
        tracks=tuple(reversed(design.board.tracks)),
        footprints=tuple(reversed(design.board.footprints)),
    )
    assert dumps(shuffled) == dumps(design.board)


def test_defaults_are_omitted_and_keys_follow_field_order() -> None:
    component = Component(id=new_id("cmp", random.Random(1)), ref="R1", value="10k")
    data = json.loads(dumps(component))
    assert list(data) == ["id", "ref", "value"]
    assert "dnp" not in data and "pins" not in data


def test_ordered_fields_keep_their_order() -> None:
    rng = random.Random(3)
    track = Track(id=new_id("trk", rng), start=Point(5, 0), end=Point(0, 0), width=1, layer="F.Cu")
    assert json.loads(dumps(track))["start"] == {"x": 5, "y": 0}


def test_floats_are_rejected() -> None:
    track = Track(
        id=new_id("trk", random.Random(1)), start=Point(0, 0), end=Point(1, 0), width=1.5, layer="F.Cu"
    )  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="floats"):
        dumps(track)


def test_provenance_and_ext_round_trip() -> None:
    track = Track(
        id=new_id("trk", random.Random(4)),
        start=Point(0, 0),
        end=Point(1, 0),
        width=1,
        layer="F.Cu",
        native_ids={"kicad": "a81c0000-0000-4000-8000-000000000001"},
        provenance=Provenance(
            backend="kicad",
            file="demo.kicad_pcb",
            file_sha256="0" * 64,
            locator="sexpr:/kicad_pcb/segment[3]",
            evidence=Evidence(Level.KICAD_VERIFIED),
        ),
        ext={"kicad": ExtBag(min_version="20241229", payload=(("uuid", "a81c"), ("locked", "yes")))},
    )
    assert loads(dumps(track), Track) == track


def test_directory_layout_and_regeneration(tmp_path: Path) -> None:
    design = Design.new("demo", seed=5)
    written = dump_dir(design, tmp_path / "a")
    assert sorted(p.name for p in written) == sorted(
        ["meta.json", "circuit.json", "board.json", "rules.json", "manufacturing.json", "findings.json"]
    )
    assert json.loads((tmp_path / "a" / "meta.json").read_text())["schema_version"] == "0"
    dump_dir(load_dir(tmp_path / "a"), tmp_path / "b")
    for name in (p.name for p in written):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_proximity_rules_keep_their_order_and_regenerate(tmp_path: Path) -> None:
    """Change c0113: the rules are value objects in the order given, and an empty tuple is left out."""
    from fenolite.model.rules import PadSelection, ProximityRule

    design = Design.new("demo", seed=5)
    assert design.rules is not None
    assert "proximity" not in dumps(design.rules)
    rules = (
        ProximityRule("b", (PadSelection("C2"), PadSelection("C1")), (PadSelection("U1", "7"),), 3_000_000),
        ProximityRule("a", (PadSelection("Y1"),), (PadSelection("U1", "12", 0),), 5_000_000, "warning"),
    )
    design = dataclasses.replace(design, rules=dataclasses.replace(design.rules, proximity=rules))
    dump_dir(design, tmp_path / "a")
    loaded = load_dir(tmp_path / "a")
    assert loaded.rules is not None and loaded.rules.proximity == rules
    dump_dir(loaded, tmp_path / "b")
    assert (tmp_path / "a" / "rules.json").read_bytes() == (tmp_path / "b" / "rules.json").read_bytes()


def test_wrong_type_reports_json_pointer(tmp_path: Path) -> None:
    design = Design.new("demo", seed=6)
    rng = random.Random(6)
    tracks = tuple(
        Track(id=new_id("trk", rng), start=Point(i, 0), end=Point(i, 1), width=100, layer="F.Cu")
        for i in range(5)
    )
    assert design.board is not None
    design = dataclasses.replace(design, board=dataclasses.replace(design.board, tracks=tracks))
    dump_dir(design, tmp_path)
    board = json.loads((tmp_path / "board.json").read_text())
    board["tracks"][3]["width"] = "wide"
    (tmp_path / "board.json").write_text(json.dumps(board))
    with pytest.raises(FormatError) as info:
        load_dir(tmp_path)
    assert info.value.locator == "/tracks/3/width"


def test_unknown_property_is_rejected() -> None:
    with pytest.raises(FormatError) as info:
        loads('{"id": "cmp_00000000-0000-4000-8000-000000000000", "ref": "R1", "colour": "red"}', Component)
    assert info.value.locator == "/colour"


def test_move_one_footprint_changes_only_its_position(tmp_path: Path) -> None:

    design = Design.new("demo", seed=8)
    rng = random.Random(8)
    from fenolite.model import FootprintInstance

    fps = tuple(
        FootprintInstance(
            id=new_id("fp", rng), component_id="", lib_ref="L:F", position=Point(i * 1_000_000, 0)
        )
        for i in range(3)
    )
    assert design.board is not None
    before = dataclasses.replace(design.board, footprints=fps)
    after = before.footprints[1]
    after = dataclasses.replace(after, position=Point(after.position.x + 1_000_000, 0))
    moved = dataclasses.replace(before, footprints=(fps[0], after, fps[2]))
    diff = [
        line
        for line in difflib.unified_diff(
            dumps(before).splitlines(), dumps(moved).splitlines(), lineterm="", n=0
        )
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]
    assert len(diff) == 2, diff
    assert [(line[0], line[1:].strip()) for line in diff] == [("-", '"x": 1000000,'), ("+", '"x": 2000000,')]


def test_float_rejected_by_the_schema() -> None:
    schema = _schema.load("fenolite.model.v0/board.json")
    board = json.loads(dumps(Board(id=new_id("brd", random.Random(1)))))
    board["holes"] = [{"id": new_id("hol", random.Random(2)), "position": {"x": 1.5, "y": 0}, "drill": 1000}]
    assert _schema.validate(board, schema)
    board["holes"][0]["position"]["x"] = 1
    assert _schema.validate(board, schema) == []


@settings(max_examples=20, deadline=None)
@given(designs())
def test_dumped_layers_validate_against_the_schemas(design: Design) -> None:
    for name, layer in (
        ("circuit.json", design.circuit),
        ("board.json", design.board),
        ("meta.json", design.header),
    ):
        errors = _schema.validate(json.loads(dumps(layer)), _schema.load(f"fenolite.model.v0/{name}"))
        assert errors == [], errors

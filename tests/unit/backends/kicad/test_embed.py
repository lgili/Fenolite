# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placed copies of library definitions, top side (capabilities kicad-file-backend "Footprint
embedding" and design-model "Placed copies of library definitions", change c0017)."""

from __future__ import annotations

import dataclasses
import uuid
from pathlib import Path

import pytest

from fenolite.backends.kicad.embed import (
    EVIDENCE,
    PLACE_PREFIX,
    footprint_extent,
    place_footprint,
    placement_uuid,
)
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Atom, Node, parse
from fenolite.backends.kicad.versions import FutureFormatError
from fenolite.core.coords import Point, Size
from fenolite.core.evidence import Level
from fenolite.core.ids import FENOLITE_NS
from fenolite.geometry.shapes import BBox
from fenolite.model.board import FootprintInstance, Pad
from fenolite.model.circuit import Circuit, Component
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

LIBS = Path(__file__).resolve().parents[4] / "tests" / "data" / "libs"
MINI = LIBS / "Mini.pretty"
AT = Point(10_000_000, 10_000_000)


def definition(name: str = "Mini_R_0603") -> FootprintDef:
    return read_footprint(MINI / f"{name}.kicad_mod", library="Mini")


def component(ref: str = "R1", value: str = "1k", n: int = 1) -> Component:
    return Component(id=f"cmp_00000000-0000-4000-8000-{n:012d}", ref=ref, value=value)


def design_with(*placed: tuple[Component, FootprintInstance], seed: int = 1) -> Design:
    design = Design.new("placed", seed=seed)
    assert design.board is not None
    board = dataclasses.replace(
        design.board, layers=created_layers(2), footprints=tuple(fp for _, fp in placed)
    )
    return dataclasses.replace(design, circuit=Circuit(components=tuple(c for c, _ in placed)), board=board)


def ids(instance: FootprintInstance) -> set[str]:
    found = {instance.id, *instance.native_ids.values()}
    for pad in instance.pads:
        found |= {pad.id, *pad.native_ids.values()}
    return found


def test_top_placement_of_the_mini_resistor() -> None:
    r1 = component()
    instance = place_footprint(definition(), component=r1, at=AT, key="R1")
    (fp,) = parse(write_board(design_with((r1, instance)), target=10).text).nodes("footprint")
    assert fp.children[0] == Atom.string("Mini:Mini_R_0603")
    assert fp.find("layer") == parse('(layer "F.Cu")') and fp.find("version") is None
    assert fp.find("generator") is None and fp.find("at") == parse("(at 10 10)")
    values = {p.children[0].value: p.children[1].value for p in fp.nodes("property")}  # type: ignore[union-attr]
    assert values["Reference"] == "R1" and values["Value"] == "1k"
    assert instance.lib_ref == "Mini:Mini_R_0603" and instance.component_id == r1.id
    assert instance.attributes == ("smd",) and all(pad.net_id is None for pad in instance.pads)
    assert instance.side == "top" and instance.position == AT and instance.provenance is None


def test_head_children_in_canonical_position() -> None:
    instance = place_footprint(
        definition(), component=component(), at=AT, rotation=30_000_000, key="R1", locked=True
    )
    (fp,) = parse(write_board(design_with((component(), instance)), target=10).text).nodes("footprint")
    heads = [c.name for c in fp.children if isinstance(c, Node)]
    assert heads[:4] == ["locked", "layer", "uuid", "at"] and fp.find("at") == parse("(at 10 10 30)")
    assert instance.locked is True and instance.rotation == 30_000_000


def test_uuids_from_the_key() -> None:
    first = place_footprint(definition(), component=component(), at=AT, key="R1")
    second = place_footprint(definition(), component=component("R2", n=2), at=AT, key="R2")
    again = place_footprint(definition(), component=component(), at=AT, key="R1")
    assert ids(first).isdisjoint(ids(second)) and ids(again) == ids(first)
    assert first.native_ids["kicad"] == placement_uuid("R1", "/footprint")
    assert placement_uuid("R1", "/footprint/pad[0]") == str(
        uuid.uuid5(FENOLITE_NS, f"{PLACE_PREFIX}:R1:/footprint/pad[0]")
    )
    assert first.pads[0].native_ids["kicad"] == placement_uuid("R1", "/footprint/pad[0]")


def test_same_key_same_ids_whatever_the_seed() -> None:
    copies = []
    for seed in (1, 2):
        design = Design.new("seeded", seed=seed)
        copies.append((design, place_footprint(definition(), component=component(), at=AT, key="R1")))
    (one, a), (two, b) = copies
    assert a == b and one.id != two.id


def test_ids_survive_a_write_and_a_read() -> None:
    r1 = component()
    instance = place_footprint(definition(), component=r1, at=AT, key="R1")
    reread = read_board(write_board(design_with((r1, instance)), target=10).text)
    assert reread.board is not None
    (fp,) = reread.board.footprints
    assert fp.id == instance.id and [p.id for p in fp.pads] == [p.id for p in instance.pads]
    assert fp.native_ids == instance.native_ids


def test_inserting_a_part_shifts_nothing() -> None:
    def placed(keys: tuple[str, ...]) -> dict[str, FootprintInstance]:
        return {k: place_footprint(definition(), component=component(k), at=AT, key=k) for k in keys}

    before, after = placed(("R1", "R3")), placed(("R1", "R2", "R3"))
    assert before["R1"] == after["R1"] and before["R3"] == after["R3"]


def test_definition_unchanged() -> None:
    defn = definition()
    place_footprint(defn, component=component(), at=AT, side="bottom", key="R1")
    assert defn == definition()


def test_future_definition_refused() -> None:
    text = (MINI / "Mini_R_0603.kicad_mod").read_text(encoding="utf-8").replace("20260206", "20990101")
    future = read_footprint(text, library="Mini")
    with pytest.raises(FutureFormatError):
        place_footprint(future, component=component(), at=AT, key="R1")


def test_courtyard_extent() -> None:
    assert footprint_extent(definition()) == BBox(-1_500_000, -750_000, 1_500_000, 750_000)


def test_extent_from_pads_and_empty() -> None:
    defn = definition()
    tall = Size(1_000_001, 2_000_000)
    first = Pad(
        id="pad_00000000-0000-4000-8000-000000000001",
        number="1",
        shape="rect",
        size=tall,
        position=Point(0, 0),
    )
    second = dataclasses.replace(
        first, id="pad_00000000-0000-4000-8000-000000000002", number="2", size=Size(1_000_000, 2_000_000),
        position=Point(5_000_000, 0), rotation=90_000_000,
    )  # fmt: skip
    pads = (first, second)
    no_courtyard = dataclasses.replace(defn, graphics=(), pads=pads)
    assert footprint_extent(no_courtyard) == BBox(-500_001, -1_000_000, 6_000_000, 1_000_000)
    assert footprint_extent(dataclasses.replace(defn, graphics=(), pads=())) == BBox(0, 0, 0, 0)


def test_extent_of_arcs_and_circles() -> None:
    led = definition("Mini_LED_THT_3mm")
    assert footprint_extent(led) == BBox(-1_200_000, -2_000_000, 3_750_000, 2_000_000)


def test_evidence() -> None:
    assert EVIDENCE.level is Level.KICAD_VERIFIED
    assert set(EVIDENCE.hypotheses) == {"H-G-BOTTOM-STORE", "H-G-FLIP", "H-G-PAD-ANGLE-ABS"}

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A pad's zone connection on boards and in footprint files (capability kicad-file-backend, "Pad zone
connection"; change c0031)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _boards import board, created_board, footprint, pad, rt1_problems

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad._fpmap import PAD_FIELDS
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import read_footprint, write_footprint
from fenolite.backends.kicad.pcb import CANONICAL_ORDER, FLOOR_HEADS, read_board, write_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse, tree_equal
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.model.base import Modeled, Opaque
from fenolite.model.board import Pad
from fenolite.model.circuit import Circuit, Component
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef

MINI = (
    Path(__file__).resolve().parents[4] / "tests" / "data" / "libs" / "Mini.pretty" / "Mini_R_0603.kicad_mod"
)
TEN = 20260206
CODES = {0: "none", 1: "thermal", 2: "solid", 3: "thru_hole_only"}


def board_pad(extra: str, version: int = TEN) -> tuple[str, Design, Pad, list[Issue]]:
    issues: list[Issue] = []
    text = board(footprint(1, pads=pad(5, extra=extra)), version=version)
    if version > 20241229:
        text = board(footprint(1, pads=pad(5, extra=extra)), version=version, nets=None).replace(
            '(net 1 "A")', '(net "A")'
        )
    design = read_board(text, issues=issues)
    assert design.board is not None
    return text, design, design.board.footprints[0].pads[0], issues


def connect_slots(entity: Pad) -> list[str]:
    out: list[str] = []
    for slot in slotlib.from_ext(entity.ext["kicad"]):
        if isinstance(slot, Modeled) and slot.field == "zone_connection":
            out.append("Modeled")
        elif isinstance(slot, Opaque) and slot.fragment.startswith("(zone_connect"):
            out.append("Opaque")
    return out


def pad_node(text: str, number: str = "1") -> Node:
    root = parse(text)
    footprints = root.nodes("footprint") if root.name == "kicad_pcb" else (root,)
    return next(p for fp in footprints for p in fp.nodes("pad") if p.atoms()[0].value == number)


def mini(connect: str | None = "(zone_connect 0)") -> str:
    """``Mini_R_0603`` with ``connect`` put into its pad ``"1"`` before the pad's uuid."""
    text = MINI.read_text(encoding="utf-8")
    root = parse(text)
    target = next(p for p in root.nodes("pad") if p.atoms()[0].value == "1")
    if connect is None:
        return text
    children = list(target.children)
    at = next(i for i, c in enumerate(children) if isinstance(c, Node) and c.name == "uuid")
    extra = parse(f"(x {connect})").nodes()
    children[at:at] = extra
    return dumps(
        root.with_children([target.with_children(children) if c is target else c for c in root.children])
    )


def placed(defn: FootprintDef) -> Design:
    r1 = Component(id="cmp_00000000-0000-4000-8000-000000000001", ref="R1", value="1k")
    instance = place_footprint(defn, component=r1, at=Point(10_000_000, 10_000_000), key="R1")
    design = Design.new("placed", seed=1)
    assert design.board is not None
    design_board = dataclasses.replace(design.board, layers=created_layers(2), footprints=(instance,))
    return dataclasses.replace(design, circuit=Circuit(components=(r1,)), board=design_board)


def test_field_map() -> None:
    assert PAD_FIELDS["zone_connect"] == "zone_connection"
    order = CANONICAL_ORDER["pad"]
    assert order.index("net") < order.index("zone_connect") < order.index("uuid")
    assert "zone_connect" in FLOOR_HEADS


@pytest.mark.parametrize(("code", "connection"), sorted(CODES.items()))
def test_codes_on_a_board(code: int, connection: str) -> None:
    text, design, found, issues = board_pad(f" (zone_connect {code})")
    assert found.zone_connection == connection and connect_slots(found) == ["Modeled"]
    assert issues == [] and rt1_problems(text, design) == []
    assert tree_equal(pad_node(write_board(design, target=10).text), pad_node(text))


def test_solid_exposed_pad_on_a_board() -> None:
    text, design, found, _ = board_pad(" (zone_connect 2)")
    assert found.zone_connection == "solid" and connect_slots(found) == ["Modeled"]
    assert tree_equal(pad_node(write_board(design, target=10).text), pad_node(text))


def test_pad_without_the_child() -> None:
    text, design, found, _ = board_pad("")
    assert found.zone_connection is None and connect_slots(found) == []
    assert pad_node(write_board(design, target=10).text).find("zone_connect") is None
    edited = design.replace_entity(dataclasses.replace(found, zone_connection="none"))
    node = pad_node(write_board(edited, target=10).text)
    assert node.find("zone_connect") == parse("(zone_connect 0)")
    heads = [c.name for c in node.nodes()]
    assert heads.index("net") < heads.index("zone_connect") < heads.index("uuid")


def test_unknown_code() -> None:
    text, design, found, issues = board_pad(" (zone_connect 7)", version=20241229)
    assert found.zone_connection is None and connect_slots(found) == ["Opaque"]
    assert [i.code for i in issues] == ["kicad.board.kept-opaque"]
    assert rt1_problems(text, design) == []
    assert tree_equal(pad_node(write_board(design, target=9).text), pad_node(text))
    edited = design.replace_entity(dataclasses.replace(found, zone_connection="solid"))
    with pytest.raises(LossyWriteError) as info:
        write_board(edited, target=9)
    (issue,) = info.value.issues
    assert issue.code == "kicad.board.projection-read-only" and "zone_connection" in issue.message
    assert issue.where.endswith("/zone_connect[0]")


def test_repeated_child_stays_opaque() -> None:
    text, design, found, issues = board_pad(" (zone_connect 2) (zone_connect 0)")
    assert found.zone_connection == "solid" and connect_slots(found) == ["Opaque", "Opaque"]
    assert [i.code for i in issues] == ["kicad.board.kept-opaque"] * 2
    assert rt1_problems(text, design) == []
    assert tree_equal(pad_node(write_board(design, target=10).text), pad_node(text))


def test_model_change_on_a_read_pad() -> None:
    text, design, found, _ = board_pad(" (zone_connect 2)")
    thermal = design.replace_entity(dataclasses.replace(found, zone_connection="thermal"))
    assert pad_node(write_board(thermal, target=10).text).find("zone_connect") == parse("(zone_connect 1)")
    cleared = design.replace_entity(dataclasses.replace(found, zone_connection=None))
    assert pad_node(write_board(cleared, target=10).text).find("zone_connect") is None


def test_created_pad() -> None:
    design = created_board()
    assert design.board is not None
    fp = design.board.footprints[0]
    first = dataclasses.replace(fp.pads[0], zone_connection="thru_hole_only")
    design = design.replace_entity(first)
    node = pad_node(write_board(design, target=9).text)
    heads = [c.name for c in node.nodes()]
    assert node.find("zone_connect") == parse("(zone_connect 3)")
    assert heads.index("net") + 1 == heads.index("zone_connect") == heads.index("uuid") - 1


def test_created_board_writes_a_solid_pad() -> None:
    for target in (9, 10):
        text = write_board(created_board(), target=target).text
        assert pad_node(text, "1").find("zone_connect") == parse("(zone_connect 2)")
        assert pad_node(text, "2").find("zone_connect") is None
        reread = read_board(text)
        assert reread.board is not None
        assert [p.zone_connection for p in reread.board.footprints[0].pads] == ["solid", None]


def test_library_pad_placed() -> None:
    issues: list[Issue] = []
    defn = read_footprint(mini(), library="Mini", issues=issues)
    one = next(p for p in defn.pads if p.number == "1")
    assert one.zone_connection == "none" and connect_slots(one) == ["Modeled"] and issues == []
    design = placed(defn)
    assert design.board is not None
    instance = design.board.footprints[0]
    assert [p.zone_connection for p in instance.pads] == ["none", None]
    text = write_board(design, target=10).text
    assert pad_node(text, "1").find("zone_connect") == parse("(zone_connect 0)")
    assert pad_node(text, "2").find("zone_connect") is None


def test_library_footprint_round_trips() -> None:
    text = mini("(zone_connect 2)")
    defn = read_footprint(text, library="Mini")
    written = write_footprint(defn, target=10)
    assert all(tree_equal(pad_node(written, n), pad_node(text, n)) for n in ("1", "2"))


def test_library_pad_gains_the_child_from_the_model() -> None:
    defn = read_footprint(mini(None), library="Mini")
    pads = tuple(dataclasses.replace(p, zone_connection="solid") if p.number == "1" else p for p in defn.pads)
    written = write_footprint(dataclasses.replace(defn, pads=pads), target=10)
    node = pad_node(written, "1")
    heads = [c.name for c in node.nodes()]
    assert node.find("zone_connect") == parse("(zone_connect 2)")
    assert heads.index("layers") < heads.index("zone_connect") < heads.index("uuid")
    assert pad_node(written, "2").find("zone_connect") is None
    assert read_footprint(written, library="Mini").pads[0].zone_connection == "solid"


def test_unknown_code_in_a_footprint_file() -> None:
    issues: list[Issue] = []
    text = mini("(zone_connect 7)")
    defn = read_footprint(text, library="Mini", issues=issues)
    one = next(p for p in defn.pads if p.number == "1")
    assert one.zone_connection is None and connect_slots(one) == ["Opaque"]
    assert [i.code for i in issues] == ["kicad.lib.kept-opaque"]
    assert tree_equal(pad_node(write_footprint(defn, target=10), "1"), pad_node(text, "1"))
    pads = tuple(dataclasses.replace(p, zone_connection="solid") if p is one else p for p in defn.pads)
    with pytest.raises(LossyWriteError) as info:
        write_footprint(dataclasses.replace(defn, pads=pads), target=10)
    assert any("zone_connection" in i.message for i in info.value.issues)


def test_footprint_level_child_stays_opaque() -> None:
    text = board(footprint(1, attr="(attr smd) (zone_connect 2)", pads=pad(5)))
    design = read_board(text)
    assert design.board is not None
    fp = design.board.footprints[0]
    assert fp.pads[0].zone_connection is None
    fragments = [s.fragment for s in slotlib.from_ext(fp.ext["kicad"]) if isinstance(s, Opaque)]
    assert "(zone_connect 2)" in fragments
    lib = mini(None).replace("\t(attr smd)\n", "\t(attr smd)\n\t(zone_connect 1)\n")
    defn = read_footprint(lib, library="Mini")
    assert all(p.zone_connection is None for p in defn.pads)
    assert "(zone_connect 1)" in [
        s.fragment for s in slotlib.from_ext(defn.ext["kicad"]) if isinstance(s, Opaque)
    ]

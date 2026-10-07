# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A pad's fabrication mark on boards and in footprint files (capability kicad-file-backend, "Assembly
and test pad properties on boards and footprints"; change c0118)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _boards import board, created_board, footprint, rt1_problems, uid

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad._fpmap import FAB_PROPERTY_TOKENS, PAD_CANONICAL, PAD_FIELDS
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import prepare_authored_definition, read_footprint, write_footprint
from fenolite.backends.kicad.pcb import CANONICAL_ORDER, read_board, write_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse, tree_equal
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.coords import Point, Size
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
TOKENS = {
    "bga": "pad_prop_bga",
    "fiducial_global": "pad_prop_fiducial_glob",
    "fiducial_local": "pad_prop_fiducial_loc",
    "test_point": "pad_prop_testpoint",
    "heatsink": "pad_prop_heatsink",
    "castellated": "pad_prop_castellated",
    "mechanical": "pad_prop_mechanical",
    "press_fit": "pad_prop_pressfit",
}


def pad_text(marks: str, *, drill: str = "") -> str:
    """A board pad whose ``marks`` sit between ``size`` (or ``drill``) and ``layers``, as KiCad writes."""
    return (
        f'(pad "1" smd rect (at 0 0) (size 1 1){drill}{marks} (layers "F.Cu" "F.Mask") (net 1 "A")'
        f' (uuid "{uid(5)}"))'
    )


def board_pad(marks: str, version: int = TEN) -> tuple[str, Design, Pad, list[Issue]]:
    issues: list[Issue] = []
    text = board(footprint(1, pads=pad_text(marks)), version=version)
    if version > 20241229:
        text = board(footprint(1, pads=pad_text(marks)), version=version, nets=None).replace(
            '(net 1 "A")', '(net "A")'
        )
    design = read_board(text, issues=issues)
    assert design.board is not None
    return text, design, design.board.footprints[0].pads[0], issues


def mark_slots(entity: Pad) -> list[str]:
    out: list[str] = []
    for slot in slotlib.from_ext(entity.ext["kicad"]):
        if isinstance(slot, Modeled) and slot.field == "fab_property":
            out.append("Modeled")
        elif isinstance(slot, Opaque) and slot.fragment.startswith("(property"):
            out.append("Opaque")
    return out


def pad_node(text: str, number: str = "1") -> Node:
    root = parse(text)
    footprints = root.nodes("footprint") if root.name == "kicad_pcb" else (root,)
    return next(p for fp in footprints for p in fp.nodes("pad") if p.atoms()[0].value == number)


def mini(mark: str | None) -> str:
    """``Mini_R_0603`` with ``mark`` put into its pad ``"1"`` before the pad's layers."""
    text = MINI.read_text(encoding="utf-8")
    if mark is None:
        return text
    root = parse(text)
    target = next(p for p in root.nodes("pad") if p.atoms()[0].value == "1")
    children = list(target.children)
    at = next(i for i, c in enumerate(children) if isinstance(c, Node) and c.name == "layers")
    children[at:at] = parse(f"(x {mark})").nodes()
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


def authored(mark: str | None, *, drill: int | None = None) -> FootprintDef:
    """An authored definition of one pad, without a slot list."""
    layers = ("*.Cu", "*.Mask") if drill is not None else ("F.Cu", "F.Mask")
    pad = Pad(
        id="pad_00000000-0000-4000-8000-000000000001",
        number="1",
        shape="circle",
        size=Size(1_500_000, 1_500_000),
        position=Point(0, 0),
        kind="thru_hole" if drill is not None else "smd",
        drill=drill,
        layers=layers,
        fab_property=mark,  # type: ignore[arg-type]
    )
    return FootprintDef(
        id="fpd_00000000-0000-4000-8000-000000000001",
        library="Local",
        name="TP",
        kind="through_hole" if drill is not None else "smd",
        pads=(pad,),
    )


def test_field_map() -> None:
    assert dict(FAB_PROPERTY_TOKENS) == TOKENS
    assert PAD_FIELDS["property"] == "fab_property"
    order = CANONICAL_ORDER["pad"]
    assert order.index("drill") + 1 == order.index("property") == order.index("layers") - 1
    assert PAD_CANONICAL.index("drill") + 1 == PAD_CANONICAL.index("fab_property")
    assert PAD_CANONICAL.index("fab_property") + 1 == PAD_CANONICAL.index("layers")


@pytest.mark.parametrize(("value", "token"), sorted(TOKENS.items()))
def test_tokens_on_a_board(value: str, token: str) -> None:
    text, design, found, issues = board_pad(f" (property {token})")
    assert found.fab_property == value and mark_slots(found) == ["Modeled"]
    assert issues == [] and rt1_problems(text, design) == []
    assert tree_equal(pad_node(write_board(design, target=10).text), pad_node(text))


def test_a_fiducial_pad_on_a_board() -> None:
    """Scenario "A fiducial pad on a board"."""
    text, design, found, _ = board_pad(" (property pad_prop_fiducial_glob)")
    heads = [c.name for c in pad_node(text).nodes()]
    assert heads.index("size") < heads.index("property") < heads.index("layers")
    assert found.fab_property == "fiducial_global" and mark_slots(found) == ["Modeled"]
    assert tree_equal(pad_node(write_board(design, target=10).text), pad_node(text))


def test_pad_without_the_child() -> None:
    text, design, found, _ = board_pad("")
    assert found.fab_property is None and mark_slots(found) == []
    assert pad_node(write_board(design, target=10).text).find("property") is None
    edited = design.replace_entity(dataclasses.replace(found, fab_property="test_point"))
    node = pad_node(write_board(edited, target=10).text)
    assert node.find("property") == parse("(property pad_prop_testpoint)")
    heads = [c.name for c in node.nodes()]
    assert heads.index("size") < heads.index("property") < heads.index("layers")


def test_model_change_on_a_read_pad() -> None:
    _, design, found, _ = board_pad(" (property pad_prop_bga)")
    heatsink = design.replace_entity(dataclasses.replace(found, fab_property="heatsink"))
    assert pad_node(write_board(heatsink, target=10).text).find("property") == parse(
        "(property pad_prop_heatsink)"
    )
    cleared = design.replace_entity(dataclasses.replace(found, fab_property=None))
    assert pad_node(write_board(cleared, target=10).text).find("property") is None


def test_an_unknown_mark() -> None:
    """Scenario "An unknown mark"; a model value that differs from the child is refused."""
    text, design, found, issues = board_pad(" (property pad_prop_unknown)", version=20241229)
    assert found.fab_property is None and mark_slots(found) == ["Opaque"]
    assert [i.code for i in issues] == ["kicad.board.kept-opaque"]
    assert rt1_problems(text, design) == []
    assert tree_equal(pad_node(write_board(design, target=9).text), pad_node(text))
    edited = design.replace_entity(dataclasses.replace(found, fab_property="test_point"))
    with pytest.raises(LossyWriteError) as info:
        write_board(edited, target=9)
    (issue,) = info.value.issues
    assert issue.code == "kicad.board.projection-read-only" and "fab_property" in issue.message
    assert issue.where.endswith("/property[0]")


def test_repeated_children_stay_opaque() -> None:
    text, design, found, issues = board_pad(" (property pad_prop_bga) (property pad_prop_heatsink)")
    assert found.fab_property == "bga" and mark_slots(found) == ["Opaque", "Opaque"]
    assert [i.code for i in issues] == ["kicad.board.kept-opaque"] * 2
    assert rt1_problems(text, design) == []
    assert tree_equal(pad_node(write_board(design, target=10).text), pad_node(text))
    edited = design.replace_entity(dataclasses.replace(found, fab_property="heatsink"))
    with pytest.raises(LossyWriteError) as info:
        write_board(edited, target=10)
    assert [i.code for i in info.value.issues] == ["kicad.board.projection-read-only"]


def created_with(mark: str, *, drill: int | None) -> Design:
    design = created_board()
    assert design.board is not None
    first = design.board.footprints[0].pads[0]
    changed = dataclasses.replace(
        first,
        fab_property=mark,  # type: ignore[arg-type]
        drill=drill,
        kind="smd" if drill is None else "thru_hole",
        layers=("F.Cu", "F.Mask") if drill is None else ("F.Cu", "B.Cu", "F.Mask", "B.Mask"),
    )
    return design.replace_entity(changed)


def test_a_created_test_point_pad() -> None:
    """Scenario "A created test-point pad": after ``drill`` and before ``layers``, for target 9."""
    design = created_with("test_point", drill=800_000)
    node = pad_node(write_board(design, target=9).text)
    heads = [c.name for c in node.nodes()]
    assert node.find("property") == parse("(property pad_prop_testpoint)")
    assert heads.index("drill") + 1 == heads.index("property") == heads.index("layers") - 1
    reread = read_board(write_board(design, target=9).text)
    assert reread.board is not None
    assert reread.board.footprints[0].pads[0].fab_property == "test_point"


def test_a_created_pad_without_a_drill() -> None:
    node = pad_node(write_board(created_with("fiducial_local", drill=None), target=10).text)
    heads = [c.name for c in node.nodes()]
    assert heads.index("size") + 1 == heads.index("property") == heads.index("layers") - 1


def test_press_fit_for_kicad_9() -> None:
    """Scenario "Press-fit for KiCad 9": modelled content newer than the target is never dropped."""
    design = created_with("press_fit", drill=1_000_000)
    for allow in (False, True):
        with pytest.raises(LossyWriteError) as info:
            write_board(design, target=9, allow_lossy=allow)
        assert info.value.droppable is False
        assert [i.code for i in info.value.issues] == ["kicad.token.too-new"]
        assert "pad-property-pressfit" in info.value.issues[0].hint
    assert "(property pad_prop_pressfit)" in write_board(design, target=10).text


def test_press_fit_in_a_footprint_file_for_kicad_9() -> None:
    defn = authored("press_fit", drill=1_000_000)
    with pytest.raises(LossyWriteError) as info:
        write_footprint(defn, target=9, allow_lossy=True)
    assert info.value.droppable is False
    assert "pad_prop_pressfit" in write_footprint(defn, target=10)


def test_an_authored_pad_gets_a_slot_only_when_marked() -> None:
    marked = prepare_authored_definition(authored("test_point", drill=800_000)).pads[0]
    fields = [s.field for s in slotlib.from_ext(marked.ext["kicad"]) if isinstance(s, Modeled)]
    assert fields.index("drill") + 1 == fields.index("fab_property") == fields.index("layers") - 1
    plain = prepare_authored_definition(authored(None)).pads[0]
    assert mark_slots(plain) == []
    written = write_footprint(authored("test_point", drill=800_000), target=9)
    heads = [c.name for c in pad_node(written).nodes()]
    assert heads.index("drill") + 1 == heads.index("property") == heads.index("layers") - 1
    assert "property pad_prop" not in write_footprint(authored(None), target=9)


def test_an_authored_definition_placed_keeps_its_mark() -> None:
    defn = prepare_authored_definition(authored("test_point"))
    design = placed(defn)
    assert design.board is not None
    assert [p.fab_property for p in design.board.footprints[0].pads] == ["test_point"]
    text = write_board(design, target=10).text
    assert pad_node(text).find("property") == parse("(property pad_prop_testpoint)")
    lib = read_footprint(write_footprint(defn, target=10), library="Local")
    assert lib.pads[0].fab_property == "test_point"


def test_library_pad_placed() -> None:
    issues: list[Issue] = []
    defn = read_footprint(mini("(property pad_prop_heatsink)"), library="Mini", issues=issues)
    one = next(p for p in defn.pads if p.number == "1")
    assert one.fab_property == "heatsink" and mark_slots(one) == ["Modeled"] and issues == []
    design = placed(defn)
    assert design.board is not None
    assert [p.fab_property for p in design.board.footprints[0].pads] == ["heatsink", None]
    text = write_board(design, target=10).text
    assert pad_node(text, "1").find("property") == parse("(property pad_prop_heatsink)")
    assert pad_node(text, "2").find("property") is None


def test_library_footprint_round_trips() -> None:
    text = mini("(property pad_prop_bga)")
    defn = read_footprint(text, library="Mini")
    written = write_footprint(defn, target=10)
    assert all(tree_equal(pad_node(written, n), pad_node(text, n)) for n in ("1", "2"))


def test_library_pad_gains_the_child_from_the_model() -> None:
    defn = read_footprint(mini(None), library="Mini")
    pads = tuple(
        dataclasses.replace(p, fab_property="test_point") if p.number == "1" else p for p in defn.pads
    )
    written = write_footprint(dataclasses.replace(defn, pads=pads), target=10)
    node = pad_node(written, "1")
    heads = [c.name for c in node.nodes()]
    assert node.find("property") == parse("(property pad_prop_testpoint)")
    assert heads.index("size") < heads.index("property") < heads.index("layers")
    assert pad_node(written, "2").find("property") is None
    assert read_footprint(written, library="Mini").pads[0].fab_property == "test_point"


def test_an_unknown_mark_in_a_footprint_file() -> None:
    issues: list[Issue] = []
    text = mini("(property pad_prop_unknown)")
    defn = read_footprint(text, library="Mini", issues=issues)
    one = next(p for p in defn.pads if p.number == "1")
    assert one.fab_property is None and mark_slots(one) == ["Opaque"]
    assert [i.code for i in issues] == ["kicad.lib.kept-opaque"]
    assert tree_equal(pad_node(write_footprint(defn, target=10), "1"), pad_node(text, "1"))
    pads = tuple(dataclasses.replace(p, fab_property="bga") if p is one else p for p in defn.pads)
    with pytest.raises(LossyWriteError) as info:
        write_footprint(dataclasses.replace(defn, pads=pads), target=10)
    assert any("fab_property" in i.message for i in info.value.issues)

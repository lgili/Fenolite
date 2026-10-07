# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Writing the stack-up of a board (capability kicad-file-backend, "Stack-up written to boards",
"Created board header" and "Projected fields on write"; change c0101), for the four copper counts of
``created_layers`` (c0100)."""

from __future__ import annotations

import dataclasses

import pytest
from _boards import (
    FIXTURE,
    STACKUP_FIXTURE,
    bare_board,
    created_board,
    created_stackup,
    four_layer_stackup,
    stack_entry,
    stack_of,
)

from fenolite.backends.kicad import pcb, stackup
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, load, parse, tree_equal
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.model.board import Stackup
from fenolite.model.design import Design

LAYERS2, LAYERS4 = created_layers(2), created_layers(4)


def two_layers(*, masks: bool = True, finish: str = "") -> Stackup:
    mask = (stack_entry("F.Mask", "soldermask", 10_000), stack_entry("B.Mask", "soldermask", 10_000))
    return stack_of(
        *mask[:1] * masks,
        stack_entry("F.Cu", "copper", 35_000),
        stack_entry("dielectric 1", "dielectric", 1_500_000, dielectric_kind="core"),
        stack_entry("B.Cu", "copper", 35_000),
        *mask[1:] * masks,
        finish=finish,
    )


def with_stackup(design: Design, value: Stackup | None) -> Design:
    assert design.board is not None
    return dataclasses.replace(design, board=dataclasses.replace(design.board, stackup=value))


def child(root: Node, head: str) -> Node:
    found = root.find(head)
    assert found is not None
    return found


def row_names(node: Node) -> list[str]:
    return [r.children[0].value for r in node.nodes("layer") if isinstance(r.children[0], Atom)]


# -- completion


def test_complete_adds_the_outer_layers_of_the_table() -> None:
    source = four_layer_stackup(outer=False)
    done = stackup.complete(source, LAYERS4)
    assert stackup.values(done) == stackup.values(four_layer_stackup())
    assert done.id == source.id and done.layers[2:12] == source.layers
    assert all(e.thickness == 0 for e in (*done.layers[:2], *done.layers[12:]))
    assert stackup.complete(done, LAYERS4) is done
    assert len({e.id for e in done.layers}) == 14


def test_complete_places_masks_between_the_others() -> None:
    held = stack_of(
        stack_entry("F.SilkS", "silkscreen", 0, color="White"),
        stack_entry("F.Cu", "copper", 35_000),
        stack_entry("dielectric 1", "dielectric", 1_500_000),
        stack_entry("B.Cu", "copper", 35_000),
        stack_entry("B.SilkS", "silkscreen", 0),
    )
    names = [e.name for e in stackup.complete(held, LAYERS2).layers]
    assert names == [
        "F.SilkS", "F.Paste", "F.Mask", "F.Cu", "dielectric 1", "B.Cu", "B.Mask", "B.Paste", "B.SilkS"
    ]  # fmt: skip


def test_complete_follows_the_table() -> None:
    layers = tuple(la for la in LAYERS2 if not la.name.endswith(".Paste"))
    names = [e.name for e in stackup.complete(two_layers(), layers).layers]
    assert names == ["F.SilkS", "F.Mask", "F.Cu", "dielectric 1", "B.Cu", "B.Mask", "B.SilkS"]


# -- the node


def test_node_rows_sheets_and_tail() -> None:
    node = stackup.stackup_node(four_layer_stackup(outer=False), LAYERS4)
    assert row_names(node) == [
        "F.SilkS", "F.Paste", "F.Mask", "F.Cu", "dielectric 1", "In1.Cu", "dielectric 2", "In2.Cu",
        "dielectric 3", "B.Cu", "B.Mask", "B.Paste", "B.SilkS",
    ]  # fmt: skip
    core = node.nodes("layer")[6]
    assert dumps(core, style="compact") == (
        '(layer "dielectric 2" (type "core") (thickness 1.2) (material "FR4") (epsilon_r 4.5)'
        ' (loss_tangent 0.02) addsublayer (thickness 0.3) (material "Laminate B") (epsilon_r 3.66)'
        " (loss_tangent 0.004))"
    )
    assert dumps(node.nodes("layer")[2], style="compact") == (
        '(layer "F.Mask" (type "Top Solder Mask") (color "Green") (thickness 0.01))'
    )
    assert dumps(node.nodes("layer")[0], style="compact") == '(layer "F.SilkS" (type "Top Silk Screen"))'
    tail = [dumps(c, style="compact") for c in node.children[-2:]]
    assert tail == ['(copper_finish "ENIG")', "(dielectric_constraints yes)"]
    assert tree_equal(node, child(child(load(STACKUP_FIXTURE), "setup"), "stackup"))


def test_node_of_an_empty_finish_and_a_dielectric_without_a_kind() -> None:
    plain = stack_of(
        stack_entry("F.Cu", "copper", 35_000),
        stack_entry("dielectric 1", "dielectric", 1_500_000),
        stack_entry("B.Cu", "copper", 35_000),
    )
    node = stackup.stackup_node(plain, LAYERS2)
    assert dumps(node.nodes("layer")[4], style="compact") == '(layer "dielectric 1" (thickness 1.5))'
    assert [dumps(c, style="compact") for c in node.children[-2:]] == [
        '(copper_finish "None")',
        "(dielectric_constraints no)",
    ]


# -- created boards


def test_created_four_layer_board() -> None:
    design = bare_board(4, four_layer_stackup(outer=False))
    roots = [parse(write_board(design, target=target).text) for target in (9, 10)]
    setups = [child(root, "setup") for root in roots]
    assert tree_equal(setups[0], setups[1])
    assert [c.name for c in setups[0].nodes()] == ["stackup", "pad_to_mask_clearance"]
    node = child(setups[0], "stackup")
    assert (
        len(node.nodes("layer")) == 13
        and row_names(node)[0] == "F.SilkS"
        and row_names(node)[-1] == "B.SilkS"
    )
    assert (
        sum(1 for c in node.nodes("layer")[6].children if isinstance(c, Atom) and c.value == "addsublayer")
        == 1
    )
    for root in roots:
        assert dumps(child(root, "general"), style="compact") == (
            "(general (thickness 2.025) (legacy_teardrops no))"
        )


def test_masks_the_stackup_omits() -> None:
    root = parse(write_board(bare_board(2, two_layers(masks=False)), target=10).text)
    by_name = {r.children[0].value: r for r in child(child(root, "setup"), "stackup").nodes("layer")}  # type: ignore[union-attr]
    for name in ("F.Mask", "B.Mask"):
        assert dumps(child(by_name[name], "thickness"), style="compact") == "(thickness 0)"
    for name in ("F.SilkS", "F.Paste", "B.Paste", "B.SilkS"):
        assert by_name[name].find("thickness") is None
    assert dumps(child(child(root, "general"), "thickness"), style="compact") == "(thickness 1.57)"


def test_created_board_with_a_stackup_keeps_its_head_set() -> None:
    plain = parse(write_board(bare_board(2), target=10).text)
    stacked = parse(write_board(bare_board(2, two_layers()), target=10).text)
    assert [c.name for c in stacked.nodes()] == [c.name for c in plain.nodes()]
    assert [c.name for c in child(stacked, "setup").nodes()] == ["stackup", "pad_to_mask_clearance"]
    assert dumps(child(plain, "setup"), style="compact") == "(setup (pad_to_mask_clearance 0))"
    assert (
        dumps(child(plain, "general"), style="compact") == "(general (thickness 1.6) (legacy_teardrops no))"
    )


def test_created_test_board_writes_the_floor_names() -> None:
    for copper in (2, 4, 6, 8):
        design = created_board(copper)
        assert design.board is not None and design.board.stackup is not None
        assert design.board.stackup.thickness() == 1_600_000
        assert not [i for i in design.validate() if i.severity == "error"]
        text = write_board(design, target=9).text
        for name in ("stackup", "color", "material", "epsilon_r", "loss_tangent", "copper_finish",
                     "dielectric_constraints", "addsublayer"):  # fmt: skip
            assert name in text
        assert stackup.values(read_board(text).board.stackup) == stackup.values(  # type: ignore[union-attr]
            stackup.complete(created_stackup(copper), created_layers(copper))  # type: ignore[arg-type]
        )


# -- read boards


def test_unchanged_stackup_keeps_the_bytes() -> None:
    text = STACKUP_FIXTURE.read_text(encoding="utf-8")
    result = write_board(read_board(text), target=9)
    assert result.text == text and result.issues == ()


def test_stackup_edited_on_a_read_board() -> None:
    design = read_board(STACKUP_FIXTURE)
    assert design.board is not None and design.board.stackup is not None
    entries = list(design.board.stackup.layers)
    assert entries[4].name == "dielectric 1"
    entries[4] = dataclasses.replace(entries[4], thickness=150_000)
    changed = dataclasses.replace(design.board.stackup, layers=tuple(entries))
    result = write_board(with_stackup(design, changed), target=9)
    assert result.issues == ()
    root, source = parse(result.text), load(STACKUP_FIXTURE)
    setup = child(root, "setup")
    assert tree_equal(child(setup, "stackup"), stackup.stackup_node(changed, design.board.layers))
    others = [c for c in setup.children if not (isinstance(c, Node) and c.name == "stackup")]
    assert others == [
        c for c in child(source, "setup").children if not (isinstance(c, Node) and c.name == "stackup")
    ]
    assert (
        dumps(child(root, "general"), style="compact") == "(general (thickness 1.975) (legacy_teardrops no))"
    )
    assert [c for c in root.children if isinstance(c, Node) and c.name not in ("setup", "general")] == [
        c for c in source.children if isinstance(c, Node) and c.name not in ("setup", "general")
    ]


def test_stackup_added_to_a_read_board() -> None:
    design = read_board(FIXTURE)
    result = write_board(with_stackup(design, two_layers()), target=9)
    assert result.issues == ()
    root, source = parse(result.text), load(FIXTURE)
    setup = child(root, "setup")
    assert setup.nodes()[0].name == "stackup"
    assert list(setup.children[1:]) == list(child(source, "setup").children)
    general = child(root, "general")
    assert dumps(child(general, "thickness"), style="compact") == "(thickness 1.59)"
    assert child(general, "legacy_teardrops") == child(child(source, "general"), "legacy_teardrops")
    back = read_board(result.text)
    assert back.board is not None
    assert stackup.values(back.board.stackup) == stackup.values(
        stackup.complete(two_layers(), back.board.layers)
    )
    assert write_board(back, target=9).text == result.text


def test_stackup_removed_from_a_read_board() -> None:
    design = read_board(STACKUP_FIXTURE)
    root = parse(write_board(with_stackup(design, None), target=9).text)
    assert child(root, "setup").find("stackup") is None
    assert child(root, "general") == child(load(STACKUP_FIXTURE), "general")


def test_rewrite_keeps_the_edge_children_and_names_what_is_lost() -> None:
    source = load(STACKUP_FIXTURE)
    setup = child(source, "setup")
    node = child(setup, "stackup")
    rows = [
        parse('(layer "F.Cu" (type "copper") (thickness 0.035 locked) (future 1))')
        if isinstance(c, Node) and c.name == "layer" and c.children[0] == Atom.string("F.Cu")
        else c
        for c in node.children
    ]
    extra = [parse("(edge_connector bevelled)"), parse("(castellated_pads yes)"), parse("(edge_plating yes)")]
    new_setup = setup.with_children(
        node.with_children([*rows, *extra]) if c is node else c for c in setup.children
    )
    text = dumps(source.with_children(new_setup if c is setup else c for c in source.children))
    design = read_board(text)
    assert design.board is not None and design.board.stackup is not None
    assert write_board(design, target=9).issues == ()  # unchanged: kept as written
    changed = dataclasses.replace(design.board.stackup, finish="HAL lead-free")
    result = write_board(with_stackup(design, changed), target=9)
    (issue,) = result.issues
    assert issue.code == "kicad.board.stackup-rewritten" and issue.severity == "info"
    assert "F.Cu: thickness locked" in issue.message and "F.Cu: future" in issue.message
    written = child(child(parse(result.text), "setup"), "stackup")
    assert [dumps(c, style="compact") for c in written.children[-5:]] == [
        '(copper_finish "HAL lead-free")',
        "(dielectric_constraints yes)",
        "(edge_connector bevelled)",
        "(castellated_pads yes)",
        "(edge_plating yes)",
    ]


# -- refusals


def test_copper_entries_that_do_not_fit_the_table() -> None:
    design = bare_board(4, two_layers())
    with pytest.raises(LossyWriteError) as caught:
        write_board(design, target=10, allow_lossy=True)
    assert [i.code for i in caught.value.issues] == ["kicad.board.stackup-invalid"]
    assert caught.value.issues[0].severity == "error"


def test_model_findings_refuse_the_write() -> None:
    bad = dataclasses.replace(two_layers(), layers=two_layers().layers[:2] + two_layers().layers[3:])
    for design in (bare_board(2, bad), with_stackup(read_board(FIXTURE), bad)):
        with pytest.raises(LossyWriteError) as caught:
            write_board(design, target=9, allow_lossy=True)
        assert [i.code for i in caught.value.issues] == ["kicad.board.stackup-invalid"]
        assert "model.stackup-order" in caught.value.issues[0].message


def test_codes_are_registered() -> None:
    for code, severity in stackup.WRITE_ISSUE_CODES.items():
        assert pcb.WRITE_ISSUE_CODES[code] == severity


# -- round trip

ROUNDTRIP = {
    "two layers": (2, two_layers()),
    "two layers without masks, a finish": (2, two_layers(masks=False, finish="HAL lead-free")),
    "four layers, sheets, a colour": (4, four_layer_stackup(outer=False)),
    "four layers, every row": (4, four_layer_stackup()),
    "created test board": (4, created_stackup(4)),
    "six layers": (6, created_stackup(6)),
    "eight layers": (8, created_stackup(8)),
}


@pytest.mark.parametrize("case", sorted(ROUNDTRIP))
@pytest.mark.parametrize("target", [9, 10])
def test_roundtrip_of_written_nodes(case: str, target: int) -> None:
    copper, value = ROUNDTRIP[case]
    text = write_board(bare_board(copper, value), target=target).text  # type: ignore[arg-type]
    back = read_board(text)
    assert back.board is not None
    assert stackup.values(back.board.stackup) == stackup.values(stackup.complete(value, back.board.layers))
    assert write_board(back, target=target).text == text

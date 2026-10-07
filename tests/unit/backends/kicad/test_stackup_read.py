# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reading the stack-up of a board (capability kicad-file-backend, "Stack-up on boards" and "Modelled
board content"; change c0101)."""

from __future__ import annotations

import pytest
from _boards import FIXTURE, STACKUP_FIXTURE, four_layer_stackup

from fenolite.backends.kicad import pcb, stackup
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import opaque_count, read_board, write_board
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, load, parse, tree_equal
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.base import Opaque
from fenolite.model.board import Stackup

LAYERS4 = created_layers(4)
SOURCE = load(STACKUP_FIXTURE)


def setup_of(root: Node = SOURCE) -> Node:
    found = root.find("setup")
    assert found is not None
    return found


def edited(change: object, root: Node = SOURCE) -> Node:
    """The fixture with its ``stackup`` node replaced by ``change(node)``."""
    setup = setup_of(root)
    node = setup.find("stackup")
    assert node is not None and callable(change)
    new_setup = setup.with_children(change(node) if c is node else c for c in setup.children)
    return root.with_children(new_setup if c is setup else c for c in root.children)


def rows(node: Node, keep: object) -> Node:
    assert callable(keep)
    return node.with_children(
        c for c in node.children if not (isinstance(c, Node) and c.name == "layer") or keep(c)
    )


def name_of(row: Node) -> str:
    first = row.children[0]
    assert isinstance(first, Atom)
    return first.value


def with_row(node: Node, name: str, fragment: str) -> Node:
    """``node`` with the row ``name`` replaced by the rows of ``fragment`` (a ``(x …)`` wrapper)."""
    new = parse(f"(x {fragment})").children
    out: list[Node | Atom] = []
    for child in node.children:
        if isinstance(child, Node) and child.name == "layer" and name_of(child) == name:
            out.extend(new)
        else:
            out.append(child)
    return node.with_children(out)


def project(root: Node) -> tuple[Stackup | None, list[Issue]]:
    issues: list[Issue] = []
    return stackup.project_stackup(setup_of(root), LAYERS4, issues=issues), issues


def codes(issues: list[Issue]) -> list[str]:
    return [i.code for i in issues if i.code.startswith("kicad.board.stackup-")]


def test_four_layer_node_projected() -> None:
    issues: list[Issue] = []
    design = read_board(STACKUP_FIXTURE, issues=issues)
    board = design.board
    assert board is not None and board.stackup is not None
    found = board.stackup
    assert [e.name for e in found.layers] == [
        "F.SilkS", "F.Paste", "F.Mask", "F.Cu", "dielectric 1", "In1.Cu", "dielectric 2", "dielectric 2",
        "In2.Cu", "dielectric 3", "B.Cu", "B.Mask", "B.Paste", "B.SilkS",
    ]  # fmt: skip
    sheets = [e for e in found.layers if e.name == "dielectric 2"]
    assert [(e.dielectric_kind, e.thickness, e.material) for e in sheets] == [
        ("core", 1_200_000, "FR4"),
        ("core", 300_000, "Laminate B"),
    ]
    assert found.finish == "ENIG" and found.impedance_controlled and found.thickness() == 2_025_000
    assert found.layers[2].color == "Green" and found.layers[0].thickness == 0
    assert codes(issues) == []
    assert stackup.values(found) == stackup.values(four_layer_stackup())
    assert design.validate() == ()
    # the setup child stays an opaque root slot, counted as the setup of the two-layer fixture is
    slots = pcb.slotlib.from_ext(board.ext["kicad"])
    assert [s for s in slots if isinstance(s, Opaque) and s.fragment.startswith("(setup")]


def test_setup_is_counted_as_without_a_node() -> None:
    """``opaque_count`` counts the ``setup`` with a node as it counts one without (one root slot)."""
    setup = setup_of()
    bare = setup.with_children(c for c in setup.children if not (isinstance(c, Node) and c.name == "stackup"))
    without = SOURCE.with_children(bare if c is setup else c for c in SOURCE.children)
    assert opaque_count(read_board(dumps(without))) == opaque_count(read_board(STACKUP_FIXTURE))


def test_ids_are_derived() -> None:
    found, _ = project(SOURCE)
    assert found is not None
    assert found.id == derived_id("stk", "kicad", "stackup")
    assert [e.id for e in found.layers] == [derived_id("sly", "kicad", f"stack:{k}") for k in range(14)]


def test_node_kicad_ignores_is_not_projected_and_is_kept() -> None:
    outer = ("F.SilkS", "F.Paste", "B.Paste", "B.SilkS")
    root = edited(lambda node: rows(node, lambda row: name_of(row) not in outer))
    issues: list[Issue] = []
    design = read_board(dumps(root), issues=issues)
    assert design.board is not None and design.board.stackup is None
    assert codes(issues) == ["kicad.board.stackup-unused"]
    (issue,) = [i for i in issues if i.code == "kicad.board.stackup-unused"]
    assert issue.severity == "warning" and "F.SilkS" in issue.message and "no thickness" in issue.hint
    written = parse(write_board(design, target=9).text)
    assert tree_equal(setup_of(written), setup_of(root))


OUTER_SUFFIXES = ("SilkS", "Paste", "Mask")
INNER_ROWS = ("In1.Cu", "In2.Cu", "dielectric 2", "dielectric 3")
INCOMPLETE = {
    "physical": lambda node: rows(node, lambda row: name_of(row).split(".")[-1] not in OUTER_SUFFIXES),
    "duplicate": lambda node: node.with_children([node.children[0], *node.children]),
    "type": lambda node: with_row(node, "F.Cu", '(layer "F.Cu" (type "Top Solder Mask") (thickness 0.035))'),
    "fewer": lambda node: rows(node, lambda row: name_of(row) not in INNER_ROWS),
    "more": lambda node: with_row(node, "In2.Cu", '(layer "In2.Cu" (type "copper") (thickness 0.0175))'
                                  ' (layer "dielectric 9" (type "core") (thickness 0.1))'
                                  ' (layer "In3.Cu" (type "copper") (thickness 0.0175))'),
    "names": lambda node: with_row(node, "In1.Cu", '(layer "Mid1" (type "copper") (thickness 0.0175))'),
    "order": lambda node: _swap(node),
    "twodiel": lambda node: with_row(node, "dielectric 3",
                                     '(layer "dielectric 3" (type "prepreg") (thickness 0.1))'
                                     ' (layer "dielectric 4" (type "prepreg") (thickness 0.1))'),
    "nodiel": lambda node: rows(node, lambda row: name_of(row) != "dielectric 1"),
    "foreign": lambda node: with_row(node, "F.Paste", '(layer "Edge.Cuts" (type "Top Solder Paste"))'),
}  # fmt: skip


def _swap(node: Node) -> Node:
    """The rows ``In1.Cu`` and ``In2.Cu`` exchanged."""
    children = list(node.children)
    at = {name_of(c): k for k, c in enumerate(children) if isinstance(c, Node) and c.name == "layer"}
    a, b = at["In1.Cu"], at["In2.Cu"]
    children[a], children[b] = children[b], children[a]
    return node.with_children(children)


@pytest.mark.parametrize("case", sorted(INCOMPLETE))
def test_incomplete_nodes(case: str) -> None:
    found, issues = project(edited(INCOMPLETE[case]))
    assert found is None and codes(issues) == ["kicad.board.stackup-unused"], case


def test_paste_rows_on_a_table_without_paste_layers() -> None:
    """A row named after an outer layer that the table does not hold makes the node incomplete."""
    layers = tuple(la for la in LAYERS4 if not la.name.endswith(".Paste"))
    issues: list[Issue] = []
    assert stackup.project_stackup(setup_of(), layers, issues=issues) is None
    assert codes(issues) == ["kicad.board.stackup-unused"]
    no_paste = edited(lambda node: rows(node, lambda row: not name_of(row).endswith(".Paste")))
    found = stackup.project_stackup(setup_of(no_paste), layers)
    assert found is not None and len(found.layers) == 12


def test_side_order_is_silkscreen_paste_mask_whatever_the_rows() -> None:
    def change(node: Node) -> Node:
        children = list(node.children)
        children[0], children[2] = children[2], children[0]  # F.Mask, F.Paste, F.SilkS
        return node.with_children(children)

    found, issues = project(edited(change))
    assert found is not None and codes(issues) == []
    assert [e.name for e in found.layers[:3]] == ["F.SilkS", "F.Paste", "F.Mask"]


UNMODELLED = {
    "fraction of a nanometre": ("F.Cu", '(layer "F.Cu" (type "copper") (thickness 0.0350001))'),
    "copper without thickness": ("F.Cu", '(layer "F.Cu" (type "copper"))'),
    "mask without thickness": ("B.Mask", '(layer "B.Mask" (type "Bottom Solder Mask"))'),
    "dielectric without thickness": ("dielectric 1", '(layer "dielectric 1" (type "prepreg"))'),
    "exponent": ("dielectric 1", '(layer "dielectric 1" (type "prepreg") (thickness 0.2) (epsilon_r 4.5e0))'),
    "epsilon of zero": ("dielectric 1",
                        '(layer "dielectric 1" (type "prepreg") (thickness 0.2) (epsilon_r 0))'),
    "dielectric above": ("F.Mask", '(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))'
                                   ' (layer "coat" (type "core") (thickness 0.01))'),
    "dielectric below": ("B.Mask", '(layer "coat" (type "core") (thickness 0.01))'
                                   ' (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))'),
}  # fmt: skip


@pytest.mark.parametrize("case", sorted(UNMODELLED))
def test_complete_nodes_the_model_cannot_hold(case: str) -> None:
    name, fragment = UNMODELLED[case]
    found, issues = project(edited(lambda node: with_row(node, name, fragment)))
    assert found is None and codes(issues) == ["kicad.board.stackup-unmodelled"], case
    assert issues[0].severity == "info"


def test_values_kept_as_written() -> None:
    """A loss tangent of 0 (what KiCad writes for a mask), another dielectric type and an empty tail."""
    fragment = (
        '(layer "F.Mask" (type "Top Solder Mask") (color "#FF000080") (thickness 0.01) (material "Epoxy")'
        " (epsilon_r 3.30) (loss_tangent 0))"
    )
    root = edited(lambda node: with_row(node, "F.Mask", fragment))
    root = edited(
        lambda node: with_row(
            node, "dielectric 3", '(layer "dielectric 3" (type "laminate") (thickness 0.2))'
        ),
        root,
    )
    root = edited(lambda node: node.with_children(c for c in node.children if c.name == "layer"), root)  # type: ignore[union-attr]
    found, issues = project(root)
    assert found is not None and codes(issues) == []
    mask = found.layers[2]
    assert (mask.color, mask.material, mask.epsilon_r, mask.loss_tangent) == (
        "#FF000080",
        "Epoxy",
        "3.30",
        "0",
    )
    other = next(e for e in found.layers if e.name == "dielectric 3")
    assert other.dielectric_kind is None and other.ext["kicad"].payload == (("type", "laminate"),)
    assert found.finish == "" and not found.impedance_controlled


def test_finish_none_is_empty() -> None:
    def change(node: Node) -> Node:
        return node.with_children(
            parse('(copper_finish "None")') if isinstance(c, Node) and c.name == "copper_finish" else c
            for c in node.children
        )

    found, _ = project(edited(change))
    assert found is not None and found.finish == ""


def general_thickness(root: Node, text: str) -> Node:
    general = root.find("general")
    assert general is not None
    new = general.with_children(
        parse(f"(thickness {text})") if isinstance(c, Node) and c.name == "thickness" else c
        for c in general.children
    )
    return root.with_children(new if c is general else c for c in root.children)


def test_total_thickness_that_differs_from_the_rows() -> None:
    issues: list[Issue] = []
    design = read_board(dumps(general_thickness(SOURCE, "1.6")), issues=issues)
    assert design.board is not None and design.board.stackup is not None
    assert design.board.stackup.thickness() == 2_025_000
    (issue,) = [i for i in issues if i.code.startswith("kicad.board.stackup-")]
    assert issue.code == "kicad.board.stackup-thickness" and issue.severity == "warning"
    assert "1.6 mm" in issue.message and "2.025 mm" in issue.message
    assert "job file" in issue.message and "IPC-2581" in issue.message


def test_equal_thickness_in_another_spelling_gives_no_warning() -> None:
    issues: list[Issue] = []
    read_board(dumps(general_thickness(SOURCE, "2.0250")), issues=issues)
    assert codes(issues) == []


def test_board_without_a_node() -> None:
    issues: list[Issue] = []
    design = read_board(FIXTURE, issues=issues)
    assert design.board is not None and design.board.stackup is None
    assert codes(issues) == []


def test_codes_are_registered() -> None:
    for code, severity in stackup.READ_ISSUE_CODES.items():
        assert pcb.ISSUE_CODES[code] == severity
    assert set(stackup.TYPES) == {"F.SilkS", "F.Paste", "F.Mask", "B.Mask", "B.Paste", "B.SilkS"}
    assert stackup.TYPES["B.Paste"] == ("Bottom Solder Paste", "solderpaste")

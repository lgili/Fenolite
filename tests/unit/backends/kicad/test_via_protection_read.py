# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reading via protection from boards (capability kicad-file-backend, "Via protection on boards", "Via
protection defaults on boards" and "Modelled board content"; change c0112)."""

from __future__ import annotations

import pytest
from _boards import FIXTURE, board, rt1_problems, uid

from fenolite.backends.kicad import pcb
from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad import via_protection as vp
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Node, parse, parse_fragment
from fenolite.core.errors import Issue
from fenolite.model.base import Modeled, Opaque, Slot
from fenolite.model.board import Via, ViaProtection

V9, V10 = 20241229, 20260206
ALL_NONE = (
    "(tenting (front none) (back none)) (capping none) (covering (front none) (back none))"
    " (plugging (front none) (back none)) (filling none)"
)


def via_text(children: str = "", n: int = 1, *, net: str = "(net 1)") -> str:
    return (
        f'(via (at {n} 1) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") {children} {net} (uuid "{uid(n)}"))'
    )


def ten(children: str = "", version: int = 20260206) -> str:
    """A board of the 10.0 format (nets by name) with one via holding ``children``."""
    return board(via_text(children, net='(net "A")'), version=version, nets=None)


def read(text: str) -> tuple[Via, list[Issue]]:
    issues: list[Issue] = []
    design = read_board(text, issues=issues)
    assert design.board is not None
    return design.board.vias[0], issues


def slots_of(via: Via) -> tuple[Slot, ...]:
    return slotlib.from_ext(via.ext["kicad"])


def heads(via: Via, kind: type) -> list[str]:
    out: list[str] = []
    for slot in slots_of(via):
        if isinstance(slot, kind):
            child = slotlib.opaque_child(slot) if isinstance(slot, Opaque) else None
            out.append(
                slot.field if isinstance(slot, Modeled) else child.name if isinstance(child, Node) else ""
            )
    return out


def fragment(text: str) -> Node:
    found = parse_fragment(text)
    assert isinstance(found, Node)
    return found


def test_module_tables() -> None:
    assert vp.FEATURES == ("tenting", "capping", "covering", "plugging", "filling")
    assert dict(vp.SUPPORT) == {
        "tenting": {9, 10}, "covering": {10}, "plugging": {10}, "capping": {10}, "filling": {10},
    }  # fmt: skip
    assert vp.KICAD_DEFAULT == ViaProtection(True, True, False, False, False, False, False, False)
    assert vp.effective_default(None) == vp.KICAD_DEFAULT
    assert vp.effective_default(ViaProtection(tenting_back=False, filling=True)) == ViaProtection(
        True, False, False, False, False, False, False, True
    )
    own = ViaProtection(tenting_front=False, capping=True)
    assert vp.effective(own, ViaProtection(tenting_back=False)) == ViaProtection(
        False, False, False, False, False, False, True, False
    )
    order = pcb.CANONICAL_ORDER["via"]
    assert order[order.index("locked") + 1 : order.index("net")] == vp.FEATURES  # after c0108's lock
    assert all(pcb.VIA_FIELDS[feature] == feature for feature in vp.FEATURES)


def test_read_in_the_10_form() -> None:
    via, issues = read(ten("(tenting (front no) (back none)) (filling yes)"))
    assert via.protection == ViaProtection(tenting_front=False, filling=True)
    assert {"tenting", "filling"} <= set(heads(via, Modeled))
    assert not [i for i in issues if i.code == pcb.KEPT_CODE]


def test_all_none_children_are_kept() -> None:
    text = ten(ALL_NONE, 20250513)
    issues: list[Issue] = []
    design = read_board(text, issues=issues)
    assert design.board is not None
    via = design.board.vias[0]
    assert via.protection == ViaProtection()
    pairs = dict(via.ext["kicad"].payload)
    assert pairs[vp.NONE_KEY] == "tenting capping covering plugging filling"
    assert not [i for i in issues if i.code == pcb.KEPT_CODE]
    assert not any(isinstance(s, Opaque) for s in slots_of(via))
    assert rt1_problems(text, design) == []


def test_the_9_form_by_major() -> None:
    nine, found9 = read(board(via_text("(tenting front)"), version=V9))
    assert nine.protection == ViaProtection(tenting_front=True, tenting_back=False)
    assert "tenting" in heads(nine, Modeled) and not found9
    tenth, found10 = read(ten("(tenting front)"))
    assert tenth.protection == ViaProtection(tenting_front=True, tenting_back=None)
    assert heads(tenth, Opaque) == ["tenting"]
    assert [i.code for i in found10] == [pcb.KEPT_CODE]


@pytest.mark.parametrize(
    ("child", "expected", "modelled"),
    [
        ("", ViaProtection(), True),
        ("(tenting front back)", ViaProtection(tenting_front=True, tenting_back=True), True),
        ("(tenting back)", ViaProtection(tenting_front=False, tenting_back=True), True),
        ("(tenting none)", ViaProtection(tenting_front=False, tenting_back=False), True),
        ("(tenting)", ViaProtection(tenting_front=False, tenting_back=False), False),
        ("(tenting (front yes) (back no))", ViaProtection(), False),
        ("(capping yes)", ViaProtection(), False),
        ("(tenting top)", ViaProtection(), False),
    ],
)
def test_forms_of_a_9_board(child: str, expected: ViaProtection, modelled: bool) -> None:
    text = board(via_text(child), version=V9)
    via, issues = read(text)
    assert via.protection == expected
    assert (not heads(via, Opaque)) == modelled
    assert bool([i for i in issues if i.code == pcb.KEPT_CODE]) == (not modelled)
    assert rt1_problems(text) == []


@pytest.mark.parametrize(
    ("child", "expected", "modelled"),
    [
        ("(tenting (front yes) (back yes))", ViaProtection(tenting_front=True, tenting_back=True), True),
        ("(capping no) (covering (front no) (back no)) (plugging (front no) (back no)) (filling no)",
         ViaProtection(None, None, False, False, False, False, False, False), True),
        ("(tenting (front no))", ViaProtection(tenting_front=False), False),
        ("(tenting front back)", ViaProtection(tenting_front=True, tenting_back=True), False),
        ("(tenting none)", ViaProtection(), False),
        ("(tenting)", ViaProtection(), False),
        ("(plugging (front yes) (back maybe))", ViaProtection(), False),
        ("(filling yes) (tenting (front no) (back no))",
         ViaProtection(tenting_front=False, tenting_back=False, filling=True), True),
    ],
)  # fmt: skip
def test_forms_of_a_10_board(child: str, expected: ViaProtection, modelled: bool) -> None:
    text = ten(child)
    via, _ = read(text)
    assert via.protection == expected
    assert (not heads(via, Opaque)) == modelled
    assert rt1_problems(text) == []


def test_default_projected_from_a_10_setup() -> None:
    setup = (
        "(setup (pad_to_mask_clearance 0) (tenting (front yes) (back no)) (covering (front no) (back no))"
        " (plugging (front no) (back no)) (capping no) (filling yes))"
    )
    text = ten().replace("(setup (pad_to_mask_clearance 0))", setup)
    design = read_board(text)
    assert design.board is not None
    assert design.board.via_protection == ViaProtection(True, False, False, False, False, False, False, True)
    root = slotlib.from_ext(design.board.ext["kicad"])
    kept = [s for s in root if isinstance(s, Opaque) and s.fragment.startswith("(setup")]
    assert len(kept) == 1
    assert rt1_problems(text, design) == []


def test_default_projected_from_a_9_setup() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    anchor = "(pad_to_mask_clearance 0)"
    assert source.count(anchor) == 1
    design = read_board(source.replace(anchor, anchor + " (tenting front)"))
    assert design.board is not None
    default = design.board.via_protection
    assert default == ViaProtection(tenting_front=True, tenting_back=False)
    got = vp.effective(ViaProtection(), default)
    assert got.tenting_back is False and got.filling is False and got.tenting_front is True
    assert read_board(source).board.via_protection is None  # type: ignore[union-attr]


def test_protected_via_and_board_default_of_the_authored_board() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    text = source.replace("(pad_to_mask_clearance 0)", "(pad_to_mask_clearance 0) (tenting front back)")
    root = parse(text)
    via_node = root.find("via")
    assert via_node is not None
    children = list(via_node.children)
    at = next(k for k, c in enumerate(children) if isinstance(c, Node) and c.name == "layers") + 1
    children.insert(at, fragment("(tenting front)"))
    root = root.with_children(via_node.with_children(children) if c is via_node else c for c in root.children)
    design = read_board(root)
    assert design.board is not None
    assert design.board.vias[0].protection == ViaProtection(tenting_front=True, tenting_back=False)
    assert design.board.via_protection == ViaProtection(tenting_front=True, tenting_back=True)
    slots = slotlib.from_ext(design.board.ext["kicad"])
    assert any(isinstance(s, Opaque) and s.fragment.startswith("(setup") for s in slots)
    assert pcb.opaque_count(design) == pcb.opaque_count(read_board(source))


@pytest.mark.parametrize(
    ("setup", "major", "expected"),
    [
        ("(setup (pad_to_mask_clearance 0))", 10, None),
        ("(setup (tenting none))", 9, ViaProtection(tenting_front=False, tenting_back=False)),
        ("(setup (tenting))", 10, ViaProtection(tenting_front=False, tenting_back=False)),
        ("(setup (tenting back))", 10, ViaProtection(tenting_front=False, tenting_back=True)),
        ("(setup (tenting front back))", 9, ViaProtection(tenting_front=True, tenting_back=True)),
        (
            "(setup (tenting (front no) (back no)))",
            10,
            ViaProtection(tenting_front=False, tenting_back=False),
        ),
        ("(setup (filling yes))", 10, ViaProtection(filling=True)),
        ("(setup (filling yes))", 9, ViaProtection()),
        ("(setup (tenting sideways))", 10, ViaProtection()),
    ],
)
def test_project_setup(setup: str, major: int, expected: ViaProtection | None) -> None:
    assert vp.project_setup(fragment(setup), major=major) == expected
    assert vp.project_setup(None, major=major) is None

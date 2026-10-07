# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Writing via protection to boards (capability kicad-file-backend, "Via protection on boards", "Via
protection defaults on boards", "Created board header" and "Projected fields on write"; change c0112)."""

from __future__ import annotations

import dataclasses

import pytest
from _boards import FIXTURE, STACKUP_FIXTURE, bare_board, board, mm, uid

from fenolite.backends.kicad import pcb
from fenolite.backends.kicad import via_protection as vp
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Node, dumps, load, parse, parse_fragment, tree_equal
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.cli import explain
from fenolite.core.ids import derived_id
from fenolite.model.board import Via, ViaProtection
from fenolite.model.design import Design

V9, V10 = 20241229, 20260206
P = ViaProtection
TEN_DEFAULT = (
    "(tenting (front yes) (back no)) (covering (front no) (back no)) (plugging (front no) (back no))"
    " (capping no) (filling yes)"
)


def created(*protections: ViaProtection, default: ViaProtection | None = None) -> Design:
    """A created two-layer board with one through via per protection, and the board default."""
    design = bare_board(2)
    assert design.board is not None
    vias = tuple(
        Via(id=derived_id("via", "prot", str(k)), position=mm(5 + 2 * k, 20), diameter=800_000,
            drill=400_000, layers=("F.Cu", "B.Cu"), protection=protection)
        for k, protection in enumerate(protections)
    )  # fmt: skip
    return dataclasses.replace(
        design, board=dataclasses.replace(design.board, vias=vias, via_protection=default)
    )


def with_default(design: Design, default: ViaProtection | None) -> Design:
    assert design.board is not None
    return dataclasses.replace(design, board=dataclasses.replace(design.board, via_protection=default))


def with_protection(design: Design, protection: ViaProtection, index: int = 0) -> Design:
    assert design.board is not None
    vias = list(design.board.vias)
    vias[index] = dataclasses.replace(vias[index], protection=protection)
    return dataclasses.replace(design, board=dataclasses.replace(design.board, vias=tuple(vias)))


def child(root: Node, head: str) -> Node:
    found = root.find(head)
    assert found is not None
    return found


def same(text: str, source: Node | str, *, apart: tuple[str, ...] = ("generator", "net")) -> bool:
    """Tree equality of a written board and its source, the ``generator`` child and the net table apart
    (the writer names itself and writes the table of the target)."""

    def rest(root: Node) -> Node:
        return root.with_children(c for c in root.children if not (isinstance(c, Node) and c.name in apart))

    return tree_equal(rest(parse(text)), rest(parse(source) if isinstance(source, str) else source))


def texts(node: Node) -> list[str]:
    return [dumps(c, style="compact") for c in node.children]


def vias_of(text: str) -> list[Node]:
    return list(parse(text).nodes("via"))


def protection_texts(via: Node) -> list[str]:
    return [dumps(c, style="compact") for c in via.nodes() if c.name in vp.FEATURE_FIELDS]


def via_text(children: str = "", *, net: str = "(net 1)") -> str:
    return f'(via (at 1 1) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") {children} {net} (uuid "{uid(1)}"))'


def ten(children: str = "", setup: str = "") -> str:
    text = board(via_text(children, net='(net "A")'), version=V10, nets=None)
    anchor = "(setup (pad_to_mask_clearance 0))"
    return text.replace(anchor, f"(setup (pad_to_mask_clearance 0) {setup})") if setup else text


# --- vias -------------------------------------------------------------------------------------------


def test_written_for_target_10() -> None:
    design = created(P(tenting_front=False, tenting_back=False, capping=True, filling=True))
    result = write_board(design, target=10)
    (via,) = vias_of(result.text)
    assert [c.name for c in via.nodes()] == [
        "at", "size", "drill", "layers", "tenting", "capping", "filling", "uuid",
    ]  # fmt: skip
    assert protection_texts(via) == ["(tenting (front no) (back no))", "(capping yes)", "(filling yes)"]
    again = read_board(result.text)
    assert again.board is not None
    assert again.board.vias[0].protection == design.board.vias[0].protection  # type: ignore[union-attr]
    assert pcb.opaque_count(again) == pcb.opaque_count(read_board(write_board(created(P()), target=10).text))


def test_both_sides_are_written_in_kicads_order() -> None:
    design = created(
        P(tenting_front=True, covering_back=False, plugging_front=True, capping=False, filling=False)
    )
    (via,) = vias_of(write_board(design, target=10).text)
    assert protection_texts(via) == [
        "(tenting (front yes) (back none))",
        "(capping no)",
        "(covering (front none) (back no))",
        "(plugging (front yes) (back none))",
        "(filling no)",
    ]


def test_a_via_without_protection_writes_no_child() -> None:
    for target in (9, 10):
        (via,) = vias_of(write_board(created(P()), target=target).text)
        assert protection_texts(via) == []


def test_written_for_target_9() -> None:
    design = created(P(tenting_front=True), P(tenting_front=False, tenting_back=False), P(capping=False))
    first, second, third = vias_of(write_board(design, target=9).text)
    assert protection_texts(first) == ["(tenting front back)"]  # the back side follows KiCad's default
    assert protection_texts(second) == ["(tenting none)"]
    assert protection_texts(third) == []


@pytest.mark.parametrize(
    ("default", "protection", "expected"),
    [
        (P(tenting_front=False, tenting_back=False), P(tenting_front=True), "(tenting front)"),
        (P(tenting_front=False, tenting_back=False), P(tenting_back=True), "(tenting back)"),
        (P(tenting_back=False), P(tenting_front=False), "(tenting none)"),
        (None, P(tenting_back=False), "(tenting front)"),
        (None, P(tenting_front=True, tenting_back=True), "(tenting front back)"),
    ],
)
def test_target_9_resolves_one_side_from_the_default(
    default: ViaProtection | None, protection: ViaProtection, expected: str
) -> None:
    (via,) = vias_of(write_board(created(protection, default=default), target=9).text)
    assert protection_texts(via) == [expected]
    read = read_board(write_board(created(protection, default=default), target=9).text)
    assert read.board is not None
    got = vp.effective(read.board.vias[0].protection, read.board.via_protection)
    assert got == vp.effective(protection, default)


def test_a_10_feature_is_refused_for_target_9() -> None:
    design = created(P(plugging_front=True))
    assert design.board is not None
    for allow in (False, True):
        with pytest.raises(LossyWriteError) as caught:
            write_board(design, target=9, allow_lossy=allow)
        assert caught.value.droppable is False
        (issue,) = caught.value.issues
        assert issue.code == "kicad.board.via-protection-too-new" and issue.severity == "error"
        assert issue.where == design.board.vias[0].id
        assert "plugging_front" in issue.message and "KiCad 10" in issue.message
        assert "allow-lossy" not in issue.message + issue.hint
    assert write_board(created(P(plugging_front=False, filling=False)), target=9).issues == ()


def test_the_code_is_registered() -> None:
    assert pcb.WRITE_ISSUE_CODES["kicad.board.via-protection-too-new"] == "error"
    entry = explain.entries()["kicad.board.via-protection-too-new"]
    assert "allow-lossy" not in entry["fix"] and "cannot be dropped" in entry["fix"]


# --- the board default --------------------------------------------------------------------------------


def test_created_defaults_on_both_targets() -> None:
    design = created(default=P(tenting_front=False, tenting_back=False))
    ten_setup = child(parse(write_board(design, target=10).text), "setup")
    assert texts(ten_setup) == [
        "(pad_to_mask_clearance 0)",
        "(tenting (front no) (back no))",
        "(covering (front no) (back no))",
        "(plugging (front no) (back no))",
        "(capping no)",
        "(filling no)",
    ]
    nine_setup = child(parse(write_board(design, target=9).text), "setup")
    assert texts(nine_setup) == ["(pad_to_mask_clearance 0)", "(tenting none)"]


def test_created_board_with_a_default_keeps_its_head_set() -> None:
    design = created(default=P(tenting_front=True, tenting_back=False))
    root = parse(write_board(design, target=10).text)
    plain = parse(write_board(created(), target=10).text)
    heads = [c.name for c in root.nodes()]
    assert heads == [c.name for c in plain.nodes()]
    assert heads[:7] == ["version", "generator", "generator_version", "general", "paper", "layers", "setup"]
    assert [c.name for c in child(root, "setup").nodes()] == [
        "pad_to_mask_clearance", "tenting", "covering", "plugging", "capping", "filling",
    ]  # fmt: skip
    assert texts(child(plain, "setup")) == ["(pad_to_mask_clearance 0)"]
    assert texts(child(root, "setup"))[1] == "(tenting (front yes) (back no))"


def test_a_default_is_refused_for_target_9() -> None:
    with pytest.raises(LossyWriteError) as caught:
        write_board(created(default=P(filling=True)), target=9, allow_lossy=True)
    assert caught.value.droppable is False
    (issue,) = caught.value.issues
    assert issue.code == "kicad.board.via-protection-too-new" and issue.where == "setup"
    assert "filling" in issue.message
    assert write_board(created(default=P(filling=True)), target=10).issues == ()


def test_unchanged_boards_keep_their_text() -> None:
    source = STACKUP_FIXTURE.read_text(encoding="utf-8")
    assert write_board(read_board(source), target=9).text == source
    written = parse(write_board(read_board(FIXTURE), target=9).text)
    assert child(written, "setup") == child(load(FIXTURE), "setup")
    assert protection_texts(child(written, "via")) == []
    text = ten("(tenting (front no) (back none)) (filling yes)", TEN_DEFAULT)
    assert same(write_board(read_board(text), target=10).text, parse(text))


def test_a_default_edited_on_a_read_board() -> None:
    text = ten(setup=TEN_DEFAULT)
    design = read_board(text)
    assert design.board is not None and design.board.via_protection is not None
    changed = dataclasses.replace(design.board.via_protection, filling=False)
    result = write_board(with_default(design, changed), target=10)
    assert result.issues == ()
    written, source = child(parse(result.text), "setup"), child(parse(text), "setup")
    assert len(written.children) == len(source.children)
    for new, old in zip(written.children, source.children, strict=True):
        if isinstance(old, Node) and old.name == "filling":
            assert dumps(new, style="compact") == "(filling no)"
        else:
            assert new == old


def test_a_default_added_to_a_read_board() -> None:
    design = read_board(FIXTURE)
    result = write_board(with_default(design, P(tenting_front=False, tenting_back=False)), target=9)
    assert result.issues == ()
    root, source = parse(result.text), load(FIXTURE)
    assert texts(child(root, "setup")) == ["(pad_to_mask_clearance 0)", "(tenting none)"]
    assert same(result.text, write_board(design, target=9).text, apart=("setup",))
    assert len(root.children) == len(source.children)
    again = read_board(result.text)
    assert again.board is not None
    assert again.board.via_protection == P(tenting_front=False, tenting_back=False)


def test_a_default_equal_in_effect_keeps_the_fragment() -> None:
    design = read_board(FIXTURE)
    result = write_board(with_default(design, P(tenting_front=True, tenting_back=True)), target=9)
    assert result.text == write_board(design, target=9).text
    resaved = ten(
        setup="(tenting (front yes) (back yes)) (covering (front no) (back no))"
        " (plugging (front no) (back no)) (capping no) (filling no)"
    )
    read = read_board(resaved)
    assert read.board is not None and read.board.via_protection == vp.KICAD_DEFAULT
    assert same(write_board(with_default(read, None), target=10).text, parse(resaved))


def test_a_default_removed_from_a_read_board() -> None:
    text = ten(setup=TEN_DEFAULT)
    result = write_board(with_default(read_board(text), None), target=10)
    assert texts(child(parse(result.text), "setup")) == ["(pad_to_mask_clearance 0)"]


@pytest.mark.parametrize(
    ("setup", "expected"),
    [
        ("(setup (allow_soldermask_bridges_in_footprints no) (pad_to_mask_clearance 0) (x 1))",
         ["allow_soldermask_bridges_in_footprints", "tenting", "covering", "plugging", "capping", "filling",
          "pad_to_mask_clearance", "x"]),
        ("(setup (stackup) (pad_to_mask_clearance 0) (x 1))",
         ["stackup", "pad_to_mask_clearance", "tenting", "covering", "plugging", "capping", "filling", "x"]),
        ("(setup (x 1))", ["tenting", "covering", "plugging", "capping", "filling", "x"]),
        ("(setup (x 1) (tenting front) (y 2))",
         ["x", "tenting", "covering", "plugging", "capping", "filling", "y"]),
        ("(setup (filling no) (x 1) (tenting (front no) (back no)))",
         ["filling", "x", "tenting", "covering", "plugging", "capping"]),
    ],
)  # fmt: skip
def test_rewrite_setup_places_the_children(setup: str, expected: list[str]) -> None:
    node = parse_fragment(setup)
    assert isinstance(node, Node)
    written = vp.rewrite_setup(node, P(tenting_front=False), major=10)
    assert [c.name for c in written.nodes()] == expected
    assert written.find("tenting") == parse_fragment("(tenting (front no) (back yes))")
    others = [c for c in written.children if isinstance(c, Node) and c.name not in vp.FEATURE_FIELDS]
    assert others == [c for c in node.children if isinstance(c, Node) and c.name not in vp.FEATURE_FIELDS]
    removed = vp.rewrite_setup(node, None, major=10)
    assert [c.name for c in removed.nodes()] == [h for h in expected if h not in vp.FEATURE_FIELDS]
    nine = vp.rewrite_setup(node, P(tenting_front=False), major=9)
    assert [dumps(c, style="compact") for c in nine.nodes() if c.name in vp.FEATURE_FIELDS] == [
        "(tenting back)"
    ]


def test_a_read_board_without_setup_cannot_hold_a_default() -> None:
    text = board(via_text()).replace("(setup (pad_to_mask_clearance 0))", "")
    design = with_default(read_board(text), P(tenting_front=False))
    with pytest.raises(LossyWriteError) as caught:
        write_board(design, target=9)
    assert [i.code for i in caught.value.issues] == ["kicad.board.projection-read-only"]
    assert "via_protection" in caught.value.issues[0].message


def test_stackup_and_default_edited_together() -> None:
    """Two projections of one ``setup``: each rewrites only its own children."""
    design = read_board(STACKUP_FIXTURE)
    assert design.board is not None and design.board.stackup is not None
    stack = dataclasses.replace(design.board.stackup, finish="HAL lead-free")
    default = P(tenting_front=False, tenting_back=True)
    changed = dataclasses.replace(
        design, board=dataclasses.replace(design.board, stackup=stack, via_protection=default)
    )
    result = write_board(changed, target=9)
    written, source = child(parse(result.text), "setup"), child(load(STACKUP_FIXTURE), "setup")
    assert child(written, "tenting") == parse_fragment("(tenting back)")
    assert 'copper_finish "HAL lead-free"' in dumps(child(written, "stackup"), style="compact")
    own = ("stackup", "tenting")
    assert [c for c in written.children if not (isinstance(c, Node) and c.name in own)] == [
        c for c in source.children if not (isinstance(c, Node) and c.name in own)
    ]
    again = read_board(result.text)
    assert again.board is not None and again.board.stackup is not None
    assert again.board.via_protection == default and again.board.stackup.finish == "HAL lead-free"
    only_default = write_board(with_default(design, default), target=9)
    assert child(child(parse(only_default.text), "setup"), "stackup") == child(source, "stackup")


# --- projections of via children ----------------------------------------------------------------------


def test_a_projected_via_child_edited() -> None:
    text = ten("(tenting front)")
    design = read_board(text)
    assert design.board is not None
    assert design.board.vias[0].protection == P(tenting_front=True)
    assert same(write_board(design, target=10).text, parse(text))  # unchanged: kept
    result = write_board(with_protection(design, P(tenting_front=True, tenting_back=False)), target=10)
    assert result.issues == ()
    (via,), (source,) = vias_of(result.text), vias_of(text)
    assert [c.name for c in via.nodes()] == [c.name for c in source.nodes()]
    assert protection_texts(via) == ["(tenting (front yes) (back no))"]
    cleared = write_board(with_protection(design, P()), target=10)
    assert protection_texts(vias_of(cleared.text)[0]) == []


def test_an_unread_child_is_replaced_when_the_model_states_a_value() -> None:
    text = ten("(plugging (front yes) (back maybe))")
    design = read_board(text)
    assert same(write_board(design, target=10).text, parse(text))
    result = write_board(with_protection(design, P(plugging_front=False, plugging_back=False)), target=10)
    assert protection_texts(vias_of(result.text)[0]) == ["(plugging (front no) (back no))"]


@pytest.mark.parametrize(
    ("child_text", "expected"),
    [
        ("(tenting front back)", "(tenting (front yes) (back yes))"),
        ("(tenting front)", "(tenting (front yes) (back no))"),
        ("(tenting back)", "(tenting (front no) (back yes))"),
        ("(tenting none)", "(tenting (front no) (back no))"),
        ("(tenting)", "(tenting (front no) (back no))"),
    ],
)
def test_a_9_board_written_for_target_10_keeps_the_meaning_of_9(child_text: str, expected: str) -> None:
    """KiCad 10 reads a 9.0 child naming one side, or none, its own way; the written 10.0 form says what
    9.0.9 plots (design, Decision 3)."""
    text = board(via_text(child_text), version=V9)
    design = read_board(text)
    assert protection_texts(vias_of(write_board(design, target=9).text)[0]) == [child_text]
    result = write_board(design, target=10)
    (via,) = vias_of(result.text)
    assert protection_texts(via) == [expected]
    again = read_board(result.text)
    assert again.board is not None and design.board is not None
    assert again.board.vias[0].protection == design.board.vias[0].protection


def test_all_none_children_stay_beside_a_set_value() -> None:
    all_none = (
        "(tenting (front none) (back none)) (capping none) (covering (front none) (back none))"
        " (plugging (front none) (back none)) (filling none)"
    )
    text = ten(all_none)
    design = read_board(text)
    assert same(write_board(design, target=10).text, parse(text))
    result = write_board(with_protection(design, P(filling=True)), target=10)
    assert protection_texts(vias_of(result.text)[0]) == [
        "(tenting (front none) (back none))",
        "(capping none)",
        "(covering (front none) (back none))",
        "(plugging (front none) (back none))",
        "(filling yes)",
    ]


def test_a_protection_child_added_to_a_read_via_lands_after_free() -> None:
    """KiCad writes ``locked``, ``free`` and ``zone_layer_connections`` before the protection children
    (probe ``via-prot-order``): a child added to a read via that holds them, kept as opaque slots, follows
    them."""
    text = ten("(locked yes) (free yes) (zone_layer_connections)")
    design = read_board(text)
    assert design.board is not None and design.board.vias[0].locked is True
    assert same(write_board(design, target=10).text, text)
    written = write_board(with_protection(design, P(tenting_front=False, filling=True)), target=10)
    (via,) = vias_of(written.text)
    assert [c.name for c in via.nodes()] == [
        "at", "size", "drill", "layers", "locked", "free", "zone_layer_connections", "tenting", "filling",
        "net", "uuid",
    ]  # fmt: skip
    plain = write_board(with_protection(read_board(ten("(free yes)")), P(capping=True)), target=10)
    assert [c.name for c in vias_of(plain.text)[0].nodes()] == [
        "at", "size", "drill", "layers", "free", "capping", "net", "uuid",
    ]  # fmt: skip
    # a via without those children: right after ``layers``, or after the lock
    bare = write_board(with_protection(read_board(ten("(locked yes)")), P(capping=True)), target=10)
    assert [c.name for c in vias_of(bare.text)[0].nodes()][3:6] == ["layers", "locked", "capping"]

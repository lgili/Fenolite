# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A footprint matched through an alias keeps its board node under the new identity (capability layout-lens,
"Kept and re-placed footprints" and "Board content outside the design is kept"; change c0069). Each test
builds the blink, edits the board by token edit, renames ``R1`` to ``R7`` in the script and builds again."""

from __future__ import annotations

from pathlib import Path

import pytest
from _layout_edit import (
    MM,
    add_group,
    add_to_footprint,
    footprint_node,
    group_members,
    move_property,
    node_uuid,
)
from _preserve_help import board_text, merged
from _project import COPPER_WARN, Project, codes, footprint

from fenolite.backends.kicad.embed import placement_uuid
from fenolite.backends.kicad.sexpr import Node, dumps, first_difference, walk
from fenolite.dsl import Design
from fenolite.lens.preserve import footprint_uuid

GROUP = "00000000-0000-4000-8000-0000000000f1"
LINE = "00000000-0000-4000-8000-0000000000e1"


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def rename(p: Project) -> None:
    p.edit_script('Part("R1"', 'Part("R7"')
    p.edit_script("design.add(u1, r1, d1)", 'design.add(u1, r1, d1)\ndesign.moved("R1", "R7")')


def uuids(node: Node) -> dict[str, str]:
    """Locator → uuid of every node of ``node`` that holds one."""
    return {loc: node_uuid(found) for loc, found in walk(node) if found.find("uuid") is not None}


def alias_messages(env: dict[str, object]) -> list[str]:
    return [i["message"] for i in env["issues"] if i["code"] == "layout.alias-used"]  # type: ignore[union-attr,index]


@pytest.mark.parametrize("target", [9, 10])
def test_rename_through_an_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int) -> None:
    p = Project(tmp_path, monkeypatch, target)
    before = footprint_node(p.board.read_text(encoding="utf-8"), "R1")
    old, _ = footprint(p.read(), "R1")
    rename(p)
    code, env, err = p.build("--confirm")
    assert code == 0, err
    text = p.board.read_text(encoding="utf-8")
    after = footprint_node(text, "R7")
    new, component = footprint(p.read(), "R7")
    assert (new.position, new.rotation, new.side) == (old.position, old.rotation, old.side)  # type: ignore[attr-defined]
    assert node_uuid(after) == footprint_uuid("R7") and component.properties["fenolite.path"] == "R7"  # type: ignore[attr-defined]
    # every uuid of the node moved from R1's to R7's, locator by locator
    was, now = uuids(before), uuids(after)
    assert list(was) == list(now) and len(was) > 5
    for loc, value in now.items():
        local = "/footprint" + loc[len("/footprint") :]
        assert was[loc] != value and value == placement_uuid("R7", local), loc
    preserved = env["result"]["preserved"]  # type: ignore[index]
    assert "R7" in preserved["kept"] and preserved["replaced"] == []  # type: ignore[index]
    (message,) = alias_messages(env)
    assert "R7" in message and "R1" in message and "kept" in message
    # the alias is needed for one build only: without it the footprint matches by uuid
    p.edit_script('design.moved("R1", "R7")', "")
    first = p.files()
    code, env, _ = p.build("--confirm")
    assert code == 0 and p.files() == first
    assert not {"layout.alias-unused", "layout.alias-used", "layout.orphan"} & set(codes(env))


def test_silkscreen_edit_survives_a_rename(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(lambda t: move_property(t, "R1", "Reference", 0, MM))
    (edited,) = [
        n for n in footprint_node(p.board.read_text(encoding="utf-8"), "R1").nodes("property")
        if n.atoms()[0].value == "Reference"
    ]  # fmt: skip
    rename(p)
    code, _, err = p.build("--confirm")
    assert code == 0, err
    fp = footprint_node(p.board.read_text(encoding="utf-8"), "R7")
    index, kept = next(
        (i, n) for i, n in enumerate(fp.nodes("property")) if n.atoms()[0].value == "Reference"
    )
    assert node_uuid(kept) == placement_uuid("R7", f"/footprint/property[{index}]")
    assert node_uuid(kept) != node_uuid(edited)

    def normal(node: Node) -> Node:
        children = [
            c
            for c in node.children
            if not (isinstance(c, Node) and c.name == "uuid") and c is not node.children[1]
        ]
        return node.with_children(children)

    # equal except for the uuid and the value atom, which the writer sets to the new reference
    assert first_difference(normal(kept), normal(edited)) is None
    assert kept.atoms()[1].value == "R7"


def test_item_added_in_kicad_keeps_its_uuid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    line = (
        '(fp_line (start -0.5 -0.9) (end 0.5 -0.9) (stroke (width 0.12) (type solid)) (layer "F.SilkS") '
        f'(uuid "{LINE}"))'
    )
    p.edit_board(lambda t: add_to_footprint(t, "R1", line))
    rename(p)
    code, _, err = p.build("--confirm")
    assert code == 0, err
    fp = footprint_node(p.board.read_text(encoding="utf-8"), "R7")
    assert LINE in {node_uuid(n) for n in fp.nodes("fp_line")}
    assert node_uuid(fp) == footprint_uuid("R7")


def test_alias_with_a_new_footprint_is_re_placed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    old, _ = footprint(p.read(), "R1")
    rename(p)
    p.edit_script('footprint="Mini:Mini_R_0603"', 'footprint="Mini:Mini_LED_THT_3mm"')
    code, env, err = p.build(*COPPER_WARN, "--confirm")
    assert code == 0, err
    new, _ = footprint(p.read(), "R7")
    assert new.lib_ref == "Mini:Mini_LED_THT_3mm" and new.position == old.position  # type: ignore[attr-defined]
    (message,) = alias_messages(env)
    assert "replaced" in message and "layout.footprint-replaced" in codes(env)
    assert env["result"]["preserved"]["replaced"] == ["R7"]  # type: ignore[index]


def test_group_follows_a_renamed_footprint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = Project(tmp_path, monkeypatch)
    p.edit_board(lambda t: add_group(t, GROUP, "R1", "D1"))
    text = p.board.read_text(encoding="utf-8")
    d1 = node_uuid(footprint_node(text, "D1"))
    assert group_members(text, GROUP) == [footprint_uuid("R1"), d1]
    rename(p)
    code, _, err = p.build("--confirm")
    assert code == 0, err
    after = p.board.read_text(encoding="utf-8")
    assert group_members(after, GROUP) == [footprint_uuid("R7"), d1]
    assert after.count('(group "') == 1 and dumps(footprint_node(after, "D1")) == dumps(
        footprint_node(text, "D1")
    )


def test_alias_match_without_an_identity_is_re_placed() -> None:
    """``merge_layout`` keeps an alias match only when it is given the identity map of the part."""
    from _buildhelp import blink

    d: Design = blink()
    part = d.parts.pop("R1")
    part.ref = "R7"
    d.parts["R7"] = part
    d.moved("R1", "R7")
    result, _ = merged(d, board_text())
    assert result.summary["replaced"] == ["R7"]
    (found,) = [i for i in result.issues if i.code == "layout.alias-used"]
    assert "replaced" in found.message

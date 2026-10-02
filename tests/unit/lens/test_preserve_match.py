# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Layout lens module, existing project files and footprint matching (capability layout-lens; change
c0019)."""

from __future__ import annotations

import ast
from pathlib import Path

from _buildhelp import LIBS, blink, build
from _layout_edit import add_items, edit_blink

from fenolite.backends.kicad.embed import place_footprint, placement_uuid
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import to_model
from fenolite.lens import preserve
from fenolite.lens.preserve import ExistingProject, footprint_uuid, match_footprints, read_existing
from fenolite.model.circuit import Component

ROOT = Path(__file__).resolve().parents[3]


def edited_board(target: int = 10) -> str:
    return edit_blink(build(blink(), target).files["blink.kicad_pcb"].decode("utf-8"))


def test_import_edges() -> None:
    tree = ast.parse((ROOT / "src" / "fenolite" / "lens" / "preserve.py").read_text(encoding="utf-8"))
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not any(
        m.startswith(("fenolite.geometry", "fenolite.dsl", "fenolite.lens.build")) for m in modules
    )


def test_uuid_of_a_component_path() -> None:
    assert footprint_uuid("power/R1") == placement_uuid("power/R1", "/footprint")
    defn = read_footprint(LIBS / "Mini_v9.pretty" / "Mini_R_0603.kicad_mod", library="Mini")
    component = Component(id=derived_id("cmp", "test", "r1"), ref="R1", lib_footprint_ref=defn.lib_id)
    placed = place_footprint(defn, component=component, at=Point(0, 0), key="power/R1")
    assert placed.native_ids["kicad"] == footprint_uuid("power/R1")


def test_missing_files(tmp_path: Path) -> None:
    (tmp_path / "blink.kicad_pro").write_text("{}\n", encoding="utf-8")
    assert read_existing(tmp_path, "blink") == ExistingProject(None, "{}\n", None)


def test_not_utf8(tmp_path: Path) -> None:
    import pytest

    from fenolite.core.errors import FormatError

    (tmp_path / "blink.kicad_dru").write_bytes(b"\xff\xfe")
    with pytest.raises(FormatError, match="blink.kicad_dru"):
        read_existing(tmp_path, "blink")


def test_moved_footprint_matched_by_uuid() -> None:
    match = match_footprints(to_model(blink()), read_board(edited_board()))
    assert {p: m.key for p, m in match.matches.items()} == {"D1": "uuid", "R1": "uuid", "U1": "uuid"}
    assert match.orphans == () and match.board_only == () and match.unused_aliases == ()


def _with_uuid(text: str, ref: str, uuid: str) -> str:
    root = parse(text)
    out = []
    for child in root.children:
        if isinstance(child, Node) and child.name == "footprint" and f'"Reference" "{ref}"' in dumps(child):
            child = child.with_children(
                [
                    parse(f'(uuid "{uuid}")') if isinstance(c, Node) and c.name == "uuid" else c
                    for c in child.children
                ]
            )
        out.append(child)
    return dumps(root.with_children(out), style="kicad")


def test_path_property_when_the_uuid_changed() -> None:
    board = read_board(_with_uuid(edited_board(), "D1", "00000000-0000-4000-8000-0000000000d1"))
    match = match_footprints(to_model(blink()), board)
    found = match.matches["D1"]
    assert (
        found.key == "path" and found.footprint.native_ids["kicad"] == "00000000-0000-4000-8000-0000000000d1"
    )


def test_alias_after_a_rename() -> None:
    renamed = blink()
    part = renamed.parts.pop("R1")
    part.ref = "R7"
    renamed.parts["R7"] = part
    renamed.moved("R1", "R7")
    board = read_board(build(blink(), 10).files["blink.kicad_pcb"].decode("utf-8"))
    match = match_footprints(to_model(renamed), board, moves={"R7": "R1"})
    assert match.matches["R7"].key == "alias" and match.orphans == () and match.unused_aliases == ()


def test_unused_alias_reported() -> None:
    board = read_board(build(blink(), 10).files["blink.kicad_pcb"].decode("utf-8"))
    design = to_model(blink())
    match = match_footprints(design, board, moves={"R1": "R0"})
    assert match.unused_aliases == (("R1", "R0"),)
    prepared = preserve.prepare(
        design,
        {},
        ExistingProject(board=build(blink(), 10).files["blink.kicad_pcb"].decode()),
        name="blink",
        moves={"R1": "R0"},
    )
    assert [i.code for i in prepared.issues if i.code in ("layout.alias-unused", "layout.alias-used")] == [
        "layout.alias-unused"
    ]


def test_copied_footprint() -> None:
    text = build(blink(), 10).files["blink.kicad_pcb"].decode("utf-8")
    root = parse(text)
    (r1,) = [
        c
        for c in root.children
        if isinstance(c, Node) and c.name == "footprint" and '"Reference" "R1"' in dumps(c)
    ]
    copy = r1.with_children(
        [
            parse('(uuid "00000000-0000-4000-8000-0000000c0b1e")')
            if isinstance(c, Node) and c.name == "uuid"
            else c
            for c in r1.children
        ]
    )
    board = read_board(add_items(text, dumps(copy, style="compact")))
    match = match_footprints(to_model(blink()), board)
    assert (
        match.matches["R1"].key == "uuid"
        and match.matches["R1"].footprint.native_ids["kicad"] != "00000000-0000-4000-8000-0000000c0b1e"
    )
    assert [fp.native_ids["kicad"] for fp in match.orphans] == ["00000000-0000-4000-8000-0000000c0b1e"]

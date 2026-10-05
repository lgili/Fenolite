# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Sheet tree and components of a project (capability kicad-schematic: "Sheet tree of a project" and
"Components of a project"; change c0060)."""

from __future__ import annotations

import shutil
from pathlib import Path

import _schfix as fx
import pytest

from fenolite.backends.kicad import sch
from fenolite.backends.kicad.sexpr import Node
from fenolite.core.errors import FormatError


def retarget(text: str, old: str, new: str) -> str:
    assert f'"{old}"' in text
    return text.replace(f'"{old}"', f'"{new}"')


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


# -- "Sheet tree of a project"


def test_two_sheet_hierarchy() -> None:
    tree = sch.sheet_files(fx.SCHEMATICS / "hier" / "top.kicad_sch")
    assert tree.files == ("top.kicad_sch", "child.kicad_sch")
    assert dict(tree.references) == {"top.kicad_sch": 0, "child.kicad_sch": 1} and tree.issues == ()


def test_sheet_used_twice() -> None:
    tree = sch.sheet_files(fx.SCHEMATICS / "multi" / "top.kicad_sch")
    assert tree.files == ("top.kicad_sch", "cell.kicad_sch") and tree.references["cell.kicad_sch"] == 2


def test_flat_sheet_is_alone() -> None:
    tree = sch.sheet_files(fx.SCHEMATICS / "flat.kicad_sch")
    assert tree.files == ("flat.kicad_sch",) and dict(tree.references) == {"flat.kicad_sch": 0}


def test_cycle(tmp_path: Path) -> None:
    top = fx.text_of("hier/top.kicad_sch")
    write(tmp_path / "root.kicad_sch", retarget(top, "child.kicad_sch", "a.kicad_sch"))
    write(tmp_path / "a.kicad_sch", retarget(top, "child.kicad_sch", "root.kicad_sch"))
    tree = sch.sheet_files(tmp_path / "root.kicad_sch")
    assert tree.files == ("root.kicad_sch", "a.kicad_sch")
    assert [(i.code, i.severity) for i in tree.issues] == [("kicad.sch.sheet-cycle", "error")]


def test_missing_file(tmp_path: Path) -> None:
    top = fx.text_of("hier/top.kicad_sch")
    write(tmp_path / "root.kicad_sch", retarget(top, "child.kicad_sch", "gone.kicad_sch"))
    tree = sch.sheet_files(tmp_path / "root.kicad_sch")
    assert tree.files == ("root.kicad_sch",)
    assert [(i.code, i.severity) for i in tree.issues] == [("kicad.sch.sheet-missing", "warning")]
    assert "gone.kicad_sch" in tree.issues[0].message


def test_file_outside_the_folder_tree(tmp_path: Path) -> None:
    top = fx.text_of("hier/top.kicad_sch")
    write(tmp_path / "p" / "root.kicad_sch", retarget(top, "child.kicad_sch", "../shared/child.kicad_sch"))
    write(tmp_path / "shared" / "child.kicad_sch", "(not a schematic")
    tree = sch.sheet_files(tmp_path / "p" / "root.kicad_sch")
    assert tree.files == ("root.kicad_sch", "../shared/child.kicad_sch")
    assert [(i.code, i.severity) for i in tree.issues] == [("kicad.sch.sheet-outside", "info")]


def test_sub_folder_and_relative_names(tmp_path: Path) -> None:
    top = fx.text_of("hier/top.kicad_sch")
    write(tmp_path / "root.kicad_sch", retarget(top, "child.kicad_sch", "sub/mid.kicad_sch"))
    write(tmp_path / "sub" / "mid.kicad_sch", retarget(top, "child.kicad_sch", "leaf.kicad_sch"))
    shutil.copy(fx.SCHEMATICS / "hier" / "child.kicad_sch", tmp_path / "sub" / "leaf.kicad_sch")
    tree = sch.sheet_files(tmp_path / "root.kicad_sch")
    assert tree.files == ("root.kicad_sch", "sub/mid.kicad_sch", "sub/leaf.kicad_sch")
    assert tree.references["sub/leaf.kicad_sch"] == 1


def test_unreadable_child_names_the_file(tmp_path: Path) -> None:
    shutil.copy(fx.SCHEMATICS / "hier" / "top.kicad_sch", tmp_path / "top.kicad_sch")
    write(tmp_path / "child.kicad_sch", "(kicad_sch (version 20260306)")
    with pytest.raises(FormatError) as caught:
        sch.sheet_files(tmp_path / "top.kicad_sch")
    assert caught.value.file == "child.kicad_sch"


# -- "Components of a project"


def flat() -> tuple[object, ...]:
    return (sch.read_schematic(fx.SCHEMATICS / "flat.kicad_sch"),)


def test_components_of_the_flat_sheet() -> None:
    found = sch.components(flat(), project="flat")  # type: ignore[arg-type]
    assert [c.ref for c in found] == ["D1", "R1", "R2", "R3", "U1"]
    r1 = next(c for c in found if c.ref == "R1")
    assert (r1.value, r1.footprint) == ("330", "Mini:Mini_R_0603")


def test_units_count_once() -> None:
    sheet = sch.read_schematic(fx.SCHEMATICS / "units.kicad_sch")
    assert sch.components((sheet,), project="units") == (sch.SchComponent("U2", "Mini_DualGate", ""),)


def test_lowest_unit_gives_value_and_footprint() -> None:
    def rename(value: str):  # noqa: ANN202
        def change(kids: fx.Children) -> None:
            for index, child in enumerate(kids):
                if isinstance(child, Node) and child.name == "property" and child.atoms()[0].value == "Value":
                    kids[index] = fx.fragment(f'(property "Value" "{value}" (at 0 0 0))')

        return change

    root = fx.tree_of("units.kicad_sch")
    symbols = [i for i, c in enumerate(root.children) if isinstance(c, Node) and c.name == "symbol"]
    children = list(root.children)
    for index, value in zip(symbols, ("from-unit-1", "from-unit-2", "from-unit-3"), strict=True):
        node = children[index]
        assert isinstance(node, Node)
        children[index] = fx.edit_root(node, rename(value))
    children[symbols[0]], children[symbols[2]] = children[symbols[2]], children[symbols[0]]
    sheet = sch.read_schematic(fx.text(root.with_children(children)))
    assert [s.unit for s in sheet.symbols] == [3, 2, 1]
    assert sch.components((sheet,), project="units")[0].value == "from-unit-1"


def test_symbols_left_off_the_board() -> None:
    found = sch.components(flat(), project="flat", on_board_only=True)  # type: ignore[arg-type]
    assert [c.ref for c in found] == ["D1", "R1", "R2", "U1"]


def test_other_project_has_no_component() -> None:
    assert sch.components(flat(), project="other") == ()  # type: ignore[arg-type]


def test_hierarchy_and_repeated_sheet() -> None:
    for folder, expected in (("hier", ["R1", "R2"]), ("multi", ["R1", "R2"])):
        base = fx.SCHEMATICS / folder
        sheets = [sch.read_schematic(base / name) for name in sch.sheet_files(base / "top.kicad_sch").files]
        assert [c.ref for c in sch.components(sheets, project="top")] == expected


# -- "Components of a hierarchy"


def test_hierarchy_components_of_the_fixtures() -> None:
    flat_root = fx.SCHEMATICS / "flat.kicad_sch"
    assert [c.ref for c in sch.hierarchy_components(flat_root)] == ["D1", "R1", "R2", "R3", "U1"]
    assert [c.ref for c in sch.hierarchy_components(flat_root, on_board_only=True)] == [
        "D1",
        "R1",
        "R2",
        "U1",
    ]
    assert sch.hierarchy_components(flat_root) == sch.components(flat(), project="flat")  # type: ignore[arg-type]
    for folder in ("hier", "multi"):
        found = sch.hierarchy_components(fx.SCHEMATICS / folder / "top.kicad_sch")
        assert [(c.ref, c.footprint) for c in found] == [
            ("R1", "Mini:Mini_R_0603"),
            ("R2", "Mini:Mini_R_0603"),
        ]
    units = sch.hierarchy_components(fx.SCHEMATICS / "units.kicad_sch")
    assert units == (sch.SchComponent("U2", "Mini_DualGate", ""),)


def test_hierarchy_components_follow_the_path_not_the_project(tmp_path: Path) -> None:
    for name in ("top.kicad_sch", "cell.kicad_sch"):
        text = fx.text_of(f"multi/{name}").replace('(project "top"', '(project "another"')
        write(tmp_path / name, text)
    found = sch.hierarchy_components(tmp_path / "top.kicad_sch")
    assert [c.ref for c in found] == ["R1", "R2"]
    sheets = [sch.read_schematic(tmp_path / name) for name in ("top.kicad_sch", "cell.kicad_sch")]
    assert sch.components(sheets, project="top") == ()


def test_hierarchy_components_without_a_use_take_the_property(tmp_path: Path) -> None:
    def drop(kids: fx.Children) -> None:
        kids.pop(next(i for i, c in enumerate(kids) if isinstance(c, Node) and c.name == "instances"))

    root = fx.edit_symbol(fx.tree_of("flat.kicad_sch"), "R1", drop)
    write(tmp_path / "flat.kicad_sch", fx.text(root))
    assert "R1" in [c.ref for c in sch.hierarchy_components(tmp_path / "flat.kicad_sch")]


def test_hierarchy_components_skip_cycles_and_missing_files(tmp_path: Path) -> None:
    top = fx.text_of("hier/top.kicad_sch")
    write(tmp_path / "root.kicad_sch", retarget(top, "child.kicad_sch", "a.kicad_sch"))
    write(tmp_path / "a.kicad_sch", retarget(top, "child.kicad_sch", "root.kicad_sch"))
    assert [c.ref for c in sch.hierarchy_components(tmp_path / "root.kicad_sch")] == ["R1"]
    write(tmp_path / "lone.kicad_sch", retarget(top, "child.kicad_sch", "gone.kicad_sch"))
    assert [c.ref for c in sch.hierarchy_components(tmp_path / "lone.kicad_sch")] == ["R1"]

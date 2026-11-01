# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A drawn schematic extracted from read KiCad sheets (capability drawn-schematic, "Drawn content of read
KiCad sheets" and "Opaque items of read sheets"; change c0276)."""

from __future__ import annotations

from pathlib import Path

import _drawn
import pytest
from _buildhelp import resolver

from fenolite.backends.kicad import drawn as kdrawn
from fenolite.backends.kicad import sch
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.dsl import Design, Part, mm, to_model
from fenolite.lens.build import _resolve  # pyright: ignore[reportPrivateUsage]
from fenolite.model.drawn import DrawnSchematic, DrawnSheet
from fenolite.model.drawn_connect import resolve

DATA = Path(__file__).resolve().parents[3] / "data" / "kicad" / "schematic"
FLAT_REFS = {"R1": "R1", "D1": "D1", "U1": "U1", "R2": "R2", "R3": "R3"}


def _flat() -> tuple[sch.SchematicSheet, DrawnSchematic, tuple[object, ...]]:
    sheet = sch.read_schematic(DATA / "flat.kicad_sch", file="flat.kicad_sch")
    drawn, issues = kdrawn.extract(sheet, {}, components=FLAT_REFS, root_file="flat.kicad_sch")
    return sheet, drawn, issues


def test_hand_drawn_fixture() -> None:
    """Scenario "Hand-drawn fixture": every opaque wire and junction slot gives one item, no slot is lost."""
    _sheet, drawn, issues = _flat()
    root = drawn.sheets[0]
    root_nodes = [
        c
        for c in parse((DATA / "flat.kicad_sch").read_text(encoding="utf-8")).children
        if isinstance(c, Node)
    ]
    assert len(root.wires) == sum(1 for c in root_nodes if c.name == "wire") == 5
    assert len(root.junctions) == sum(1 for c in root_nodes if c.name == "junction") == 1
    assert [s.part for s in root.symbols] == ["R1", "D1", "U1", "R2", "R3"]
    assert [(p.symbol, p.net) for p in root.powers] == [("Mini:Mini_GND", "GND")]
    assert len(root.labels) == sum(1 for c in root_nodes if c.name in ("label", "global_label"))
    assert len(root.no_connects) == sum(1 for c in root_nodes if c.name == "no_connect")
    assert [o.kicad.split()[0] for o in root.opaques] == ["(text"]
    assert issues == ()
    assert root.title_block and root.paper == "A4"


def test_text_kept_and_unknown_symbol_kept() -> None:
    """Scenarios "Text kept" and "Unknown symbol kept"."""
    sheet = sch.read_schematic(DATA / "flat.kicad_sch", file="flat.kicad_sch")
    without = {k: v for k, v in FLAT_REFS.items() if k != "R3"}
    drawn, issues = kdrawn.extract(sheet, {}, components={**without, "X1": "X1"}, root_file="flat.kicad_sch")
    assert [i.code for i in issues] == ["drawn.part-unknown"] and "R3" in issues[0].message
    root = drawn.sheets[0]
    assert [s.part for s in root.symbols] == ["R1", "D1", "U1", "R2"]
    assert [o.kicad.split()[0] for o in root.opaques] == ["(symbol", "(text"]


def test_repeated_sheet_becomes_one_drawn_sheet() -> None:
    top = sch.read_schematic(DATA / "multi" / "top.kicad_sch", file="top.kicad_sch")
    cell = sch.read_schematic(DATA / "multi" / "cell.kicad_sch", file="cell.kicad_sch")
    found = kdrawn.extract_with_pins(top, {"cell.kicad_sch": cell}, components={"R1": "a/R", "R2": "b/R"},
                                     root_file="top.kicad_sch")  # fmt: skip
    drawn = found.drawn
    assert [s.key for s in drawn.sheets] == ["root", "cell"]
    refs = drawn.sheets[0].sheet_refs
    assert [(r.sheet, r.module, r.name) for r in refs] == [("cell", "a", "CellA"), ("cell", "b", "CellB")]
    assert [p.name for p in refs[0].pins] == ["IN"]
    assert [s.part for s in drawn.sheets[1].symbols] == ["R"]
    assert drawn.instances() == (("", "root"), ("a", "cell"), ("b", "cell"))
    netlist = resolve(drawn, found.pins)
    assert {("a/R", "1"), ("b/R", "1")} <= set(netlist.pins)


def _flat_design() -> Design:
    design = Design("flat")
    design.board(mm(40), mm(30))
    for ref, lib, footprint, value in (
        ("R1", "Mini:Mini_R", "Mini:Mini_R_0603", "330"),
        ("D1", "Mini:Mini_LED", "Mini:Mini_LED_THT_3mm", "RED"),
        ("U1", "Mini:Mini_QFP32_IC", "", "Mini_QFP32_IC"),
        ("R2", "Mini:Mini_R", "Mini:Mini_R_0603", "10k"),
        ("R3", "Mini:Mini_R", "Mini:Mini_R_0603", "0"),
    ):
        design.add(Part(ref, lib, footprint=footprint or None, value=value))
    return design


def _lower_and_extract(
    drawn: DrawnSchematic, design: Design, target: int, refs: dict[str, str]
) -> DrawnSchematic:
    model = to_model(design)
    issues: list[object] = []
    parts, _ = _resolve(model, resolver(target, _drawn.FIXTURES / "flat"), issues)  # type: ignore[arg-type]
    symbols = {"Mini:Mini_GND": kdrawn.PowerSymbol(_drawn.library()["Mini:Mini_GND"])}
    lowered = kdrawn.lower_drawn(drawn, model, parts, name=design.name, target=target, power_symbols=symbols)
    assert not [i for i in lowered.issues if i.severity == "error"], lowered.issues
    root_text = sch.write_schematic(lowered.sheet, target=target).text
    root = sch.read_schematic(root_text, file=f"{design.name}.kicad_sch")
    children = {
        p: sch.read_schematic(sch.write_schematic(s, target=target).text, file=p)
        for p, s in lowered.children.items()
    }
    again, _ = kdrawn.extract(root, children, components=refs, root_file=f"{design.name}.kicad_sch")
    return again


@pytest.mark.parametrize("target", [9, 10])
def test_write_and_extract_again_hand_drawn(target: int) -> None:
    """Scenario "Write and extract again", on the hand-drawn KiCad fixture."""
    _sheet, first, _ = _flat()
    assert _lower_and_extract(first, _flat_design(), target, FLAT_REFS) == first


@pytest.mark.parametrize("name", [*_drawn.NAMES, "example"])
@pytest.mark.parametrize("target", [9, 10])
def test_write_and_extract_again_built(name: str, target: int) -> None:
    """Scenario "Write and extract again", on the sheets written for each authored drawn fixture."""
    first, _, _ = _drawn.resolved(_drawn.build(name, target))
    again, _, _ = _drawn.resolved(_drawn.build(name, target, value=first))
    assert again == first


def test_empty_sheet_extracts() -> None:
    sheet = sch.read_schematic(DATA / "units.kicad_sch", file="units.kicad_sch")
    drawn, issues = kdrawn.extract(sheet, {}, components={"U2": "U2"}, root_file="units.kicad_sch")
    assert isinstance(drawn.sheets[0], DrawnSheet) and [s.unit for s in drawn.sheets[0].symbols] == [1, 2, 3]
    assert issues == ()

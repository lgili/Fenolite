# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawing kept in the opaque root slots of a read sheet (capability kicad-schematic, "Drawn content of a
read sheet"; change c0276)."""

from __future__ import annotations

from pathlib import Path

from fenolite.backends.kicad import sch
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.core.coords import Point

DATA = Path(__file__).resolve().parents[3] / "data" / "kicad" / "schematic"


def _children(name: str, head: str) -> list[Node]:
    root = parse((DATA / name).read_text(encoding="utf-8"))
    return [c for c in root.children if isinstance(c, Node) and c.name == head]


def _point(item: Node, head: str) -> Point:
    found = item.find(head)
    assert found is not None
    return Point(found.atoms()[0].to_nm(), found.atoms()[1].to_nm())


def test_junctions_of_a_read_sheet() -> None:
    """Scenario "Junctions of a read sheet"."""
    sheet = sch.read_schematic(DATA / "flat.kicad_sch", file="flat.kicad_sch")
    drawing = sch.opaque_drawing(sheet)
    junctions = _children("flat.kicad_sch", "junction")
    assert [at for at, _ in drawing.junctions] == [_point(j, "at") for j in junctions]
    wires = _children("flat.kicad_sch", "wire")
    assert len(drawing.wires) == len(wires) == 5
    assert drawing.wires == sch.opaque_wires(sheet)
    heads = sorted(f.fragment.split()[0].strip("(") for f in drawing.rest)
    assert heads == ["embedded_fonts", "generator", "generator_version", "text", "version"]
    assert drawing.inexact == ()


def test_buses_and_entries_of_a_read_sheet() -> None:
    sheet = sch.read_schematic(DATA / "bus.kicad_sch", file="bus.kicad_sch")
    drawing = sch.opaque_drawing(sheet)
    assert drawing.buses == ((Point(90_000_000, 50_000_000), Point(90_000_000, 80_000_000)),)
    assert drawing.bus_entries == (
        (Point(90_000_000, 62_540_000), Point(2_540_000, -2_540_000)),
        (Point(90_000_000, 67_620_000), Point(2_540_000, -2_540_000)),
    )


def test_inexact_slot_stays_verbatim() -> None:
    text = (DATA / "flat.kicad_sch").read_text(encoding="utf-8")
    text = text.replace("(junction\n\t\t(at 100 57.15)", "(junction\n\t\t(at 100.0000001 57.15)", 1)
    assert "100.0000001" in text
    drawing = sch.opaque_drawing(sch.read_schematic(text, file="flat.kicad_sch"))
    assert drawing.junctions == () and drawing.inexact == ("junction",)
    assert any(f.fragment.startswith("(junction") for f in drawing.rest)


def test_sheet_pins_and_field_poses() -> None:
    top = sch.read_schematic(DATA / "multi" / "top.kicad_sch", file="top.kicad_sch")
    pins = sch.opaque_sheet_pins(top.sheets[0])
    assert pins == (("IN", "input", Point(100_000_000, 55_080_000), 180_000_000),)
    flat = sch.read_schematic(DATA / "flat.kicad_sch", file="flat.kicad_sch")
    poses = {pose.name: pose for pose in sch.symbol_field_poses(flat.symbols[0])}
    assert poses["Reference"].at == Point(102_540_000, 48_730_000) and not poses["Reference"].hide
    assert poses["Footprint"].hide

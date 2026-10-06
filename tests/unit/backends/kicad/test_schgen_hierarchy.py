# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""One schematic sheet per module (capability kicad-schematic, "Hierarchical sheets of a design" and the
hierarchy parts of "Generated sheet content"; change c0070). Hermetic: no tool runs."""

from __future__ import annotations

import pytest
from _buildhelp import blink, build, codes
from _schbuild import NESTED, built_nested, nested_design

from fenolite.backends.kicad import sch, schgen, schlayout
from fenolite.backends.kicad.pcb import kicad_uuid
from fenolite.backends.kicad.schgen import GeneratedSchematic
from fenolite.backends.kicad.schlayout import SymbolPlacement
from fenolite.core.ids import derived_id
from fenolite.dsl import Design, Module, Net, Part, Power, connect, mm
from fenolite.lens.build import BuildOutput
from fenolite.model.schematic import SchematicSheet, SheetPage, SheetUse

IO, POWER, LDO = "sheets/io.kicad_sch", "sheets/power.kicad_sch", "sheets/power.ldo.kicad_sch"


def generated(output: BuildOutput) -> GeneratedSchematic:
    assert output.schematic is not None, [i.message for i in output.issues if i.severity == "error"]
    return output.schematic


def refs(sheet: SchematicSheet) -> list[str]:
    return [symbol.ref for symbol in sheet.symbols if not symbol.ref.startswith("#")]


def test_two_modules_one_nested() -> None:
    made = generated(built_nested())
    assert list(made.children) == [IO, POWER, LDO], "depth first, in natural order: the page order"
    root, io, power, ldo = made.sheet, made.children[IO], made.children[POWER], made.children[LDO]
    assert (refs(root), refs(io), refs(power), refs(ldo)) == (["U1"], ["R2"], ["R1"], ["C1"])
    assert [(r.name, r.file) for r in root.sheets] == [("io", IO), ("power", POWER)]
    assert [(r.name, r.file) for r in power.sheets] == [("ldo", "power.ldo.kicad_sch")]
    assert not io.sheets and not ldo.sheets
    top = f"/{kicad_uuid(root)}"
    box_io, box_power = root.sheets
    (box_ldo,) = power.sheets
    assert box_io.uses == (SheetUse(NESTED, top, "2"),) and box_power.uses == (SheetUse(NESTED, top, "3"),)
    assert box_ldo.uses == (SheetUse(NESTED, f"{top}/{kicad_uuid(box_power)}", "4"),)
    (c1,) = ldo.symbols
    assert c1.uses[0].path == f"{top}/{kicad_uuid(box_power)}/{kicad_uuid(box_ldo)}"
    assert io.symbols[0].uses[0].path == f"{top}/{kicad_uuid(box_io)}"
    assert root.symbols[0].uses[0].path == top


def test_pages_and_names() -> None:
    made = generated(built_nested())
    assert made.sheet.pages == (SheetPage("/", "1"),)
    assert all(child.pages == () for child in made.children.values()), "a child file lists no page"
    assert [child.name for child in made.children.values()] == ["io", "power", "ldo"]
    assert made.sheet.name == NESTED
    for child in made.children.values():
        assert child.title_block == made.sheet.title_block and child.paper.paper == "A4"


def test_ids_come_from_the_module_paths() -> None:
    made = generated(built_nested())
    assert made.sheet.id == derived_id("sch", "fenolite", NESTED)
    assert made.children[LDO].id == derived_id("sch", "fenolite", f"{NESTED}:power/ldo")
    (box,) = made.children[POWER].sheets
    assert box.id == derived_id("shr", "fenolite", f"{NESTED}:sheet:power/ldo")
    assert len({sheet.id for sheet in (made.sheet, *made.children.values())}) == 4


def test_footprint_paths_name_the_sheets() -> None:
    output = built_nested()
    made = generated(output)
    by_ref = {c.ref: made.paths[c.id] for c in output.design.circuit.components}
    box_io, box_power = made.sheet.sheets
    (box_ldo,) = made.children[POWER].sheets
    symbol = {s.ref: kicad_uuid(s) for sheet in (made.sheet, *made.children.values()) for s in sheet.symbols}
    assert by_ref == {
        "U1": f"/{symbol['U1']}",
        "R1": f"/{kicad_uuid(box_power)}/{symbol['R1']}",
        "C1": f"/{kicad_uuid(box_power)}/{kicad_uuid(box_ldo)}/{symbol['C1']}",
        "R2": f"/{kicad_uuid(box_io)}/{symbol['R2']}",
    }


def test_sheet_references_are_boxes_without_pins_after_the_units() -> None:
    made = generated(built_nested())
    root = made.sheet
    io, power = root.sheets
    assert (io.size.w, io.size.h) == (25_400_000, 12_700_000) == (power.size.w, power.size.h)
    assert io.position.y == power.position.y and io.position.x < power.position.x
    u1 = next(s for s in root.symbols if s.ref == "U1")
    assert io.position.y > u1.position.y, "the references take a row below the units"
    for box in (io, power):
        assert box.position.x % schlayout.ORIGIN_STEP == 0 and box.position.y % schlayout.ORIGIN_STEP == 0
    assert schlayout.sheet_ref_size("io") == 25_400_000
    assert schlayout.sheet_ref_size("a_module_with_a_long_name") == 43_180_000  # 27 × 1.524 mm, rounded up


def test_each_sheet_embeds_its_own_symbols_and_the_root_the_flags() -> None:
    made = generated(built_nested())
    names = {path: [d.name for d in sheet.lib_symbols] for path, sheet in made.children.items()}
    assert names == {IO: ["Mini_R"], POWER: ["Mini_R"], LDO: ["Mini_R"]}
    assert [d.name for d in made.sheet.lib_symbols] == ["Mini_QFP32_IC", "PWR_FLAG"]
    flags = [s.ref for sheet in made.children.values() for s in sheet.symbols if s.ref.startswith("#")]
    assert flags == [] and made.power_flags == 2
    assert sorted(s.ref for s in made.sheet.symbols if s.ref.startswith("#")) == ["#FLG01", "#FLG02"]


def test_no_hierarchical_label_and_no_wire_between_sheets() -> None:
    made = generated(built_nested())
    for sheet in (made.sheet, *made.children.values()):
        assert {label.kind for label in sheet.labels} <= {"global"}
    names = {label.name for sheet in made.children.values() for label in sheet.labels}
    assert names == {"VIN", "GND", "DRV", "power{slash}FB"}, "the nets keep the names of the circuit"


@pytest.mark.parametrize("target", [9, 10])
def test_every_sheet_is_written_and_read_back(target: int) -> None:
    output = built_nested(target)
    made = generated(output)
    assert [p for p in output.files if p.endswith(".kicad_sch")] == [f"{NESTED}.kicad_sch", IO, POWER, LDO]
    for path, sheet in made.children.items():
        text = output.files[path].decode("utf-8")
        assert "(sheet_instances" not in text
        back = sch.read_schematic(text, file=path)
        assert [s.ref for s in back.symbols] == [s.ref for s in sheet.symbols]
        assert [(r.name, r.file, r.uses) for r in back.sheets] == [
            (r.name, r.file, r.uses) for r in sheet.sheets
        ]
    assert build(nested_design(), target).files == output.files, "two builds are byte-identical"


def test_grid_on_request() -> None:
    made = generated(build(nested_design(), schematic_layout="grid"))
    assert made.children == {} and made.satellites == 0
    assert not made.sheet.wires and not made.sheet.sheets
    assert refs(made.sheet) == ["U1", "R2", "R1", "C1"], "in the natural order of the component paths"
    top = f"/{kicad_uuid(made.sheet)}"
    assert {use.path for symbol in made.sheet.symbols for use in symbol.uses} == {top}
    by_ref = {s.ref: s for s in made.sheet.symbols}
    assert set(made.paths.values()) == {f"/{kicad_uuid(by_ref[ref])}" for ref in ("U1", "R1", "R2", "C1")}


def test_design_without_modules_has_one_sheet() -> None:
    made = generated(build(blink()))
    assert made.children == {} and not made.sheet.sheets
    assert refs(made.sheet) == ["D1", "R1", "U1"]


def test_unknown_layout() -> None:
    with pytest.raises(ValueError, match="readable, grid"):
        build(blink(), schematic_layout="pretty")


def collision_design() -> Design:
    """A top-level module ``a.b`` and a module ``b`` inside ``a``: both would be ``sheets/a.b.kicad_sch``."""
    design = Design("clash")
    design.board(mm(40), mm(30))
    first = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")
    second = Part("R2", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")
    dotted, outer, inner = Module("a.b"), Module("a"), Module("b")
    dotted.add(first)
    inner.add(second)
    outer.add(inner)
    design.add(dotted, outer)
    vin, gnd = Net("VIN"), Net("GND")
    connect(vin, first[1], second[1])
    connect(gnd, first[2], second[2])
    design.add(Power(vin, gnd))
    first.place(mm(10), mm(10))
    second.place(mm(20), mm(10))
    return design


def test_file_collision() -> None:
    output = build(collision_design())
    assert output.files == {} and output.schematic is None
    (issue,) = [i for i in output.issues if i.code == "build.sheet-file-collision"]
    assert issue.severity == "error" and "a.b" in issue.message and "a/b" in issue.message
    assert "sheets/a.b.kicad_sch" in issue.message
    assert "build.sheet-file-collision" in schgen.ISSUE_CODES
    assert "build.schematic-netlist-differs" not in codes(output)
    assert build(collision_design(), schematic_layout="grid").files, "one flat sheet has no file to share"


def test_letter_case_collides_too() -> None:
    assert schgen.sheet_file("power/ldo") == "sheets/power.ldo.kicad_sch"
    design = collision_design()
    assert {m for m in ("a.b", "a/b")} <= {schgen.module_of(path) for path in design.parts}


def test_a_placement_belongs_to_the_sheet_of_its_unit() -> None:
    at = SymbolPlacement(50_800_000, 50_800_000)
    output = build(nested_design(), symbol_placements={"power/ldo/C1": at, "nowhere/R9": at})
    made = generated(output)
    (c1,) = made.children[LDO].symbols
    assert (c1.position.x, c1.position.y) == (at.x, at.y)
    unknown = [i for i in output.issues if i.code == "build.symbol-placement-unknown"]
    assert len(unknown) == 1 and "nowhere/R9" in unknown[0].message, "reported once, not once per sheet"

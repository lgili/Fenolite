# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Schematic components and pins (capability altium-import, "Schematic components and pins"; c0043)."""

from __future__ import annotations

from pathlib import Path

import _altium_records as rec
from _altium import example_model

from fenolite.backends.altium.adapter.circuit import import_circuit
from fenolite.backends.altium.adapter.netlist import SheetInput
from fenolite.backends.altium.adapter.parts import part_groups
from fenolite.backends.altium.read.sch import read_schematic
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id

DATA = Path(__file__).resolve().parents[5] / "tests" / "data" / "altium"


def test_components_of_the_kicad_example() -> None:
    data = (DATA / "kicad_example" / "altium_kicad.SchDoc").read_bytes()
    sheet = SheetInput("altium_kicad.SchDoc", rec.SHA, read_schematic(data))
    circuit = import_circuit([sheet])
    model, _symbols = example_model()
    mine = {component.ref: component for component in circuit.components}
    assert sorted(mine) == sorted(c.ref for c in model.circuit.components)
    assert len(mine) == len(circuit.components)
    for want in model.circuit.components:
        got = mine[want.ref]
        # The writer gives a component without a value the value of its symbol.
        assert want.value in ("", got.value), want.ref
        if want.lib_footprint_ref:  # else the writer took the footprint of the symbol
            assert got.lib_footprint_ref.split(":")[-1] == want.lib_footprint_ref.split(":")[-1], want.ref
        assert sorted(p.number for p in got.pins) == sorted(p.number for p in want.pins), want.ref
        assert got.path == want.ref and got.provenance is not None
        assert got.provenance.file == "altium_kicad.SchDoc" and got.provenance.locator.startswith(
            "FileHeader#"
        )
    (dual,) = [g for g in part_groups(sheet.document) if g.ref == "U1"]
    assert len(dual.parts) == 2 and len(mine["U1"].pins) == len({p.designator for p in dual.pins})
    assert dict(mine["U1"].ext["altium"].payload)["part_ids"].count(",") == 1


def test_component_value_properties_and_library_references() -> None:
    sheet = rec.Sheet()
    sheet.component(
        "R1", [("1", 10, 10)], value="=Resistance", library="Lib\\Devices.SchLib", libref="RES",
        footprint="R_0603", uid="AAAAAAAA",
        parameters={"Resistance": "10k", "Tolerance": "1%", "resistance": "x"},
    )  # fmt: skip
    sheet.component("C1", [("1", 20, 10)], value="100n", uid="BBBBBBBB", extra="|COMPONENTKIND=2")
    first, second = import_circuit([sheet.input()]).components
    assert (first.ref, first.value, first.path) == ("R1", "10k", "R1")
    assert first.properties == {"Resistance": "10k", "Tolerance": "1%", "resistance": "x"}
    assert (first.lib_symbol_ref, first.lib_footprint_ref) == ("Devices:RES", "Parts:R_0603")
    assert first.native_ids == {"altium": "cmp:\\AAAAAAAA"}
    assert first.id == derived_id("cmp", "altium", "cmp:\\AAAAAAAA") and first.ext == {}
    assert (second.value, second.lib_symbol_ref, second.lib_footprint_ref) == ("100n", "PART", "")
    assert second.ext["altium"].payload == (("component_kind", "2"),)


def test_component_parts_share_one_designator() -> None:
    sheet = rec.Sheet()
    sheet.component(
        "U1", [("1", 10, 10), ("2", 10, 20, 2), ("8", 10, 30, 0)], part=1, parts=2, uid="PARTAAAA"
    )
    sheet.component(
        "U1", [("1", 50, 10, 1), ("2", 50, 20), ("8", 50, 30, 0)], part=2, parts=2, uid="PARTBBBB"
    )
    sheet.wire((50, 20), (60, 20))
    sheet.label("B", 60, 20)
    circuit = import_circuit([sheet.input()])
    (component,) = circuit.components
    assert [pin.number for pin in component.pins] == ["1", "2", "8"]
    assert component.native_ids == {"altium": "cmp:\\PARTAAAA"}
    assert dict(component.ext["altium"].payload) == {"part_ids": "PARTAAAA,PARTBBBB"}
    assert [(n.name, [m.pin for m in n.members]) for n in circuit.nets] == [("B", ["2"])]


def test_component_without_a_designator_record() -> None:
    issues: list[Issue] = []
    sheet = rec.Sheet()
    sheet.component("", [("1", 10, 10)], designator=False)
    sheet.component("", [("1", 30, 10)], designator=False)
    circuit = import_circuit([sheet.input()], issues=issues)
    assert [c.ref for c in circuit.components] == ["", ""]
    found = [i for i in issues if i.code == "altium.import.no-designator"]
    assert len(found) == 2 and found[0].where == "sheet.SchDoc:FileHeader#1"


def test_pin_table_types_and_names() -> None:
    sheet = rec.Sheet()
    fields = {"1": {"ELECTRICAL": "0", "NAME": "IN"}, "2": {"ELECTRICAL": "7"}, "3": {"ELECTRICAL": "9"}}
    sheet.component("U1", [("1", 10, 10), ("2", 10, 20), ("3", 10, 30)], pin_fields=fields, uid="CCCCCCCC")  # type: ignore[arg-type]
    (component,) = import_circuit([sheet.input()]).components
    assert [(p.number, p.etype) for p in component.pins] == [
        ("1", "input"),
        ("2", "power_in"),
        ("3", "unspecified"),
    ]
    assert component.pins[0].name == "IN" and component.pins[0].ext == {}
    assert component.pins[2].ext["altium"].payload == (("electrical", "9"),)
    assert component.pins[0].native_ids == {"altium": "cmp:\\CCCCCCCC:pin:1"}


def test_pin_of_a_part_that_is_not_placed_is_on_no_net() -> None:
    sheet = rec.Sheet()
    # One placed part of a two-part component: the pin of part 2 lies on the wire but is not drawn.
    sheet.component("U1", [("1", 10, 10), ("5", 30, 10, 2)], part=1, parts=2)
    sheet.component("R1", [("1", 30, 10)])
    sheet.wire((10, 10), (30, 10))
    circuit = import_circuit([sheet.input()])
    refs = {c.id: c.ref for c in circuit.components}
    (net,) = circuit.nets
    assert sorted((refs[m.component_id], m.pin) for m in net.members) == [("R1", "1"), ("U1", "1")]
    assert [p.number for p in circuit.components[0].pins] == ["1", "5"]

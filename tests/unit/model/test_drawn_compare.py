# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A drawing compared with the circuit, and its coverage (capability drawn-schematic, "Drawing compared with
the circuit", "Drawn schematic coverage" and "Repeated sheet values"; change c0276)."""

from __future__ import annotations

import dataclasses
import runpy

import _drawn

from fenolite.core.coords import Point
from fenolite.dsl import Part, connect, to_model
from fenolite.model.drawn import DrawnSchematic, DrawnSheet, DrawnSymbol
from fenolite.model.drawn_connect import UnitInfo, compare, component_path, coverage


def _replace_root(value: DrawnSchematic, **changes: object) -> DrawnSchematic:
    return DrawnSchematic(value.root, (dataclasses.replace(value.sheets[0], **changes), *value.sheets[1:]))  # type: ignore[arg-type]


def test_a_faithful_drawing() -> None:
    """Scenario "A faithful drawing"."""
    assert compare(_drawn.netlist("example"), _drawn.circuit("example")) == ()


def test_a_wire_moved_to_the_wrong_pin() -> None:
    """Scenario "A wire moved to the wrong pin": the end on R1 pin 1 goes to R1 pin 2."""
    value = _drawn.drawn("example")
    wires = list(value.sheets[0].wires)
    index = wires.index(
        (Point(114_300_000, 69_850_000), Point(123_190_000, 69_850_000), Point(123_190_000, 76_200_000))
    )
    wires[index] = (*wires[index][:2], Point(130_810_000, 76_200_000))
    found = compare(
        _drawn.netlist("example", _replace_root(value, wires=tuple(wires))), _drawn.circuit("example")
    )
    assert [i.code for i in found] == ["drawn.netlist-differs"]
    assert found[0].where == "R1-1" and found[0].severity == "error"
    assert "(open)" in found[0].message or "(split)" in found[0].message


def test_name_only() -> None:
    """Scenario "Name only"."""
    value = _drawn.drawn("example")
    labels = tuple(
        dataclasses.replace(label, text="I2C_SDA") if label.text == "SDA" else label
        for label in value.sheets[0].labels
    )
    found = compare(_drawn.netlist("example", _replace_root(value, labels=labels)), _drawn.circuit("example"))
    assert [i.code for i in found] == ["drawn.net-name-differs"]
    assert "SDA" in found[0].message and "I2C_SDA" in found[0].message and found[0].severity == "warning"


def _units(name: str) -> dict[str, UnitInfo]:
    model = to_model(_drawn.design(name))
    nets = {(m.component_id, m.pin) for net in model.circuit.nets for m in net.members}
    library = _drawn.library()
    found: dict[str, UnitInfo] = {}
    for component in model.circuit.components:
        symbol = library[component.lib_symbol_ref]
        on_net = frozenset(
            u
            for u in range(1, symbol.unit_count + 1)
            if any((component.id, p.number) in nets for p in symbol.pins_of(u, 1))
        )
        found[component_path(component)] = UnitInfo(symbol.unit_count, on_net)
    return found


def test_complete_fixtures_have_no_coverage_issue() -> None:
    for name in (*_drawn.NAMES, "example"):
        assert coverage(_drawn.drawn(name), _drawn.circuit(name), _units(name)) == (), name


def test_part_added_in_code_only() -> None:
    """Scenario "Part added in code only"."""
    design = _drawn.design("example")
    r9 = Part("R9", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")
    design.add(r9)
    connect(design.nets["SDA"], r9[1])
    model = to_model(design)
    units = {component_path(c): UnitInfo(1, frozenset({1})) for c in model.circuit.components}
    units["U1"] = UnitInfo(1, frozenset({1}))
    found = coverage(_drawn.drawn("example"), model.circuit, units)
    assert [(i.code, i.where) for i in found] == [("drawn.symbol-missing", "R9")]
    assert "unit 1" in found[0].message


def test_unused_unit() -> None:
    """Scenario "Unused unit": a gate of a multi-unit part with no pin on a net is a warning only."""
    scope = runpy.run_path(str(_drawn.folder("flat") / "design.py"))
    design = scope["design"]
    gate = Part("U2", "Mini:Mini_DualGate", footprint="Mini:Mini_R_0603", value="gates")
    design.add(gate)
    connect(design.nets["SDA"], gate[1])
    model = to_model(design)
    value = _drawn.drawn("flat")
    symbols = (
        *value.sheets[0].symbols,
        DrawnSymbol("U2", 1, Point(0, 0)),
        DrawnSymbol("U2", 3, Point(0, 50_800_000)),
    )
    value = _replace_root(value, symbols=symbols)
    units = {
        "U1": UnitInfo(1, frozenset({1})),
        "R1": UnitInfo(1, frozenset({1})),
        "U2": UnitInfo(3, frozenset({1})),
    }
    found = coverage(value, model.circuit, units)
    assert [(i.code, i.severity) for i in found] == [("drawn.unit-missing", "warning")]
    assert "unit 2" in found[0].message


def test_unknown_and_twice_drawn_parts() -> None:
    value = _drawn.drawn("flat")
    symbols = (*value.sheets[0].symbols, DrawnSymbol("X1", 1, Point(0, 0)), value.sheets[0].symbols[1])
    found = coverage(_replace_root(value, symbols=symbols), _drawn.circuit("flat"), _units("flat"))
    assert sorted(i.code for i in found) == ["drawn.part-unknown", "drawn.part-unknown"]


def test_different_resistor_per_channel() -> None:
    """Scenario "Different resistor per channel"."""
    design = _drawn.design("repeat")
    design.parts["ch1/R1"].value = "22k"  # type: ignore[attr-defined]
    model = to_model(design)
    found = coverage(_drawn.drawn("repeat"), model.circuit, _units("repeat"))
    assert [i.code for i in found] == ["drawn.repeated-value-differs"]
    message = found[0].message
    assert "R1" in message and "ch0" in message and "ch1" in message and "value" in message
    assert found[0].hint


def test_generated_sheet_parts_are_left_to_the_generator() -> None:
    value = _drawn.drawn("hier")
    child = DrawnSheet("child", generated=True)
    found = coverage(
        DrawnSchematic(value.root, (value.sheets[0], child)), _drawn.circuit("hier"), _units("hier")
    )
    assert found == ()

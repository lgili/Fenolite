# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The wired layout of a generated sheet (capability kicad-schematic, "Wired sheet layout", "Power symbols
on a generated sheet", "Net names on a wired sheet" and "Wired layout fallbacks"; change c0406).
Hermetic: the authored designs of ``tests/_wireddesigns.py`` and the seeded designs of
``tests/_gendesigns.py`` are built in memory; no tool runs."""

from __future__ import annotations

from collections import Counter
from functools import cache

import pytest
from _buildhelp import build
from _gendesigns import MODULE_SEED, SEED, designs
from _wireddesigns import DESIGNS, build_authored

from fenolite.backends.kicad import sch, schlayout, schwired, symembed
from fenolite.backends.kicad.sch_netlist import grammar_issues
from fenolite.backends.kicad.schgen import LAYOUTS, GeneratedSchematic
from fenolite.backends.kicad.schreadability import measure_sheets
from fenolite.cli.cmd_build import _catalog_definitions  # pyright: ignore[reportPrivateUsage]
from fenolite.core.coords import Point
from fenolite.dsl import to_model
from fenolite.model.schematic import SchematicSheet

NAMES = tuple(DESIGNS)


@cache
def generated(name: str, layout: str = "wired") -> GeneratedSchematic:
    output = build_authored(DESIGNS[name](), layout)
    assert not [i for i in output.issues if i.severity == "error"], output.issues
    assert output.schematic is not None
    return output.schematic


def sheets(found: GeneratedSchematic) -> list[SchematicSheet]:
    return [found.sheet, *found.children.values()]


# --- net roles ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "role"),
    [
        ("GND", "ground"),
        ("AGND", "ground"),
        ("0V", "ground"),
        ("VSSA", "ground"),
        ("+3V3", "rail"),
        ("+12V", "rail"),
        ("5V", "rail"),
        ("VCC", "rail"),
        ("VDDIO", "rail"),
        ("VBUS", "rail"),
        ("-12V", "negative"),
        ("VEE", "negative"),
        ("VIN_RAW", ""),
        ("PWR_LED", ""),
        ("VSENSE", ""),
        ("GND_SENSE", ""),
        ("SIG_IN", ""),
    ],
)
def test_roles_by_name(name: str, role: str) -> None:
    assert schwired.name_role(name) == role


def test_roles_by_interface_and_pin() -> None:
    assert schwired.net_role("SIG", declared="power") == "rail"
    assert schwired.net_role("SIG", declared="ground") == "ground"
    assert schwired.net_role("VREF", power_pin=True) == "rail"
    assert schwired.net_role("RETURN", declared="power") == "rail"
    assert schwired.net_role("AGND", declared="power") == "ground"
    assert schwired.net_role("SIG") == "signal"


# --- the authored designs -------------------------------------------------------------------------


@pytest.mark.parametrize("name", NAMES)
def test_measures_of_authored_designs(name: str) -> None:
    wired = measure_sheets(sheets(generated(name)))
    readable = measure_sheets(sheets(generated(name, "readable")))
    assert wired.label_count * 2 < readable.label_count, (wired, readable)
    assert wired.wires > readable.wires
    assert wired.power_symbols > 0
    assert (wired.wire_over_pin, wired.wire_over_body, wired.four_way, wired.bare_tees) == (0, 0, 0, 0)
    assert wired.overlaps == 0
    assert wired.crossings <= 3
    assert generated(name).fallbacks == 0


@pytest.mark.parametrize("name", NAMES)
def test_wired_sheets_are_inside_the_grammar(name: str) -> None:
    found = generated(name)
    assert grammar_issues(found.sheet, children=found.children) == ()


@pytest.mark.parametrize("name", NAMES)
def test_route_every_wire_is_straight_on_the_grid(name: str) -> None:
    for sheet in sheets(generated(name)):
        for wire in sheet.wires:
            assert wire.start.x == wire.end.x or wire.start.y == wire.end.y
            for point in (wire.start, wire.end):
                assert point.x % schlayout.GRID == 0 and point.y % schlayout.GRID == 0


@pytest.mark.parametrize("name", NAMES)
def test_route_junctions_join_three_directions(name: str) -> None:
    for sheet in sheets(generated(name)):
        ends = Counter(point for wire in sheet.wires for point in (wire.start, wire.end))
        pins = _pin_points(sheet)
        for junction in sheet.junctions:
            assert ends[junction.position] + (1 if junction.position in pins else 0) >= 3


@pytest.mark.parametrize("name", NAMES)
def test_one_label_per_drawn_group(name: str) -> None:
    for sheet in sheets(generated(name)):
        ids = [label.id for label in sheet.labels]
        assert len(ids) == len(set(ids))
        texts = Counter(label.name for label in sheet.labels if label.kind == "global")
        # a net drawn in one wired group on one sheet carries one global label there
        assert all(count <= 2 for count in texts.values()), texts


def test_supplies_are_power_symbols() -> None:
    sheet = generated("opamp").sheet
    powers = [s for s in sheet.symbols if symembed.is_power_symbol(s.lib_ref)]
    assert {s.value for s in powers} == {"+5V", "GND"}
    assert all(s.ref.startswith("#PWR") and not s.in_bom and not s.on_board for s in powers)
    assert sorted(s.ref for s in powers) == [f"#PWR{n:03d}" for n in range(1, len(powers) + 1)]
    assert not [label for label in sheet.labels if label.name in ("+5V", "GND")]
    lib_ids = [d.lib_id for d in sheet.lib_symbols]
    assert "Fenolite:GND" in lib_ids and "Fenolite:RAIL" in lib_ids
    assert generated("opamp").power_symbols == len(powers)


def test_power_flags_join_by_wire() -> None:
    sheet = generated("opamp").sheet
    flags = [s for s in sheet.symbols if symembed.is_power_flag(s.lib_ref)]
    assert len(flags) == 2  # +5V and GND: no power output drives them
    assert not [label for label in sheet.labels if label.id.endswith("flag:+5V")]
    ends = {point for wire in sheet.wires for point in (wire.start, wire.end)}
    assert all(flag.position in ends for flag in flags)


def test_signal_flows_left_to_right() -> None:
    sheet = generated("opamp").sheet
    at = {s.ref: s.position.x for s in sheet.symbols}
    assert at["J1"] < at["R1"] < at["U1"] < at["R4"] < at["J2"]
    mirrored = {s.ref: s.mirror for s in sheet.symbols}
    assert mirrored["J1"] == "y" and mirrored["J2"] == ""  # both connectors face the amplifier


def test_cluster_feedback_part_lies_over_the_amplifier() -> None:
    sheet = generated("opamp").sheet
    at = {s.ref: s.position for s in sheet.symbols}
    assert at["R2"].y < at["U1"].y
    assert abs(at["R2"].x - at["U1"].x) <= 5 * schlayout.ORIGIN_STEP


def test_cluster_decoupling_capacitor_stands_under_its_supply_pin() -> None:
    sheet = generated("opamp").sheet
    at = {s.ref: s.position for s in sheet.symbols}
    assert at["C2"].y > at["U1"].y
    assert abs(at["C2"].x - at["U1"].x) <= 3 * schlayout.ORIGIN_STEP


def test_labels_and_fields_are_posed() -> None:
    for symbol in generated("controller").sheet.symbols:
        poses = sch.field_poses(symbol)
        if symembed.is_power_symbol(symbol.lib_ref):
            assert poses["Reference"].hide and not poses["Value"].hide
        else:
            assert {"Reference", "Value"} <= set(poses)


def test_module_sheets_are_wired() -> None:
    found = generated("modules")
    assert set(found.children) == {"sheets/amp.kicad_sch", "sheets/psu.kicad_sch"}
    for child in found.children.values():
        assert child.wires or child.symbols
        assert any(symembed.is_power_symbol(s.lib_ref) for s in child.symbols)


def test_two_builds_are_equal() -> None:
    first = build_authored(DESIGNS["controller"]())
    second = build_authored(DESIGNS["controller"]())
    assert first.files == second.files


def test_placements_fall_back_to_readable() -> None:
    design = DESIGNS["switch"]()
    footprints, symbols, _ = _catalog_definitions(to_model(design), {}, {})
    placed = build(
        design,
        10,
        schematic_layout="wired",
        authored_footprints=footprints,
        authored_symbols=symbols,
        symbol_placements={"R1": schlayout.SymbolPlacement(50_800_000, 50_800_000)},
    )
    assert "build.schematic-wired-fallback" in [i.code for i in placed.issues]
    assert placed.schematic is not None
    assert not placed.schematic.sheet.junctions
    assert placed.schematic.power_symbols == 0


@pytest.mark.parametrize(("modules", "seed"), [(False, SEED), (True, MODULE_SEED)])
def test_generated_designs_build_wired(modules: bool, seed: int) -> None:
    """Every seeded design draws wired and passes the build's own netlist guard."""
    for design in designs(seed, modules=modules):
        output = build(design, 10, schematic_layout="wired")
        errors = [i for i in output.issues if i.severity == "error"]
        assert not errors, (design.name, errors)
        assert output.schematic is not None
        assert grammar_issues(output.schematic.sheet, children=output.schematic.children) == ()


def test_wired_is_a_layout() -> None:
    assert LAYOUTS == ("readable", "grid", "wired")


def _pin_points(sheet: SchematicSheet) -> set[Point]:
    known = {d.lib_id: d for d in sheet.lib_symbols}
    found: set[Point] = set()
    for symbol in sheet.symbols:
        definition = known.get(symbol.lib_ref)
        if definition is None:
            continue
        for pin in definition.pins_of(symbol.unit, symbol.body_style):
            turn = (symbol.rotation // 1_000_000) % 360
            found.add(schlayout.pin_point(symbol.position, pin.position, turn, symbol.mirror))
    return found


def test_wire_end_inside_a_wire_is_refused() -> None:
    """Scenario "Wire end inside a wire": the two collinear wires on a T's junction joined into one."""
    from dataclasses import replace

    sheet = generated("opamp").sheet
    for junction in sheet.junctions:
        at = junction.position
        touching = [w for w in sheet.wires if at in (w.start, w.end)]
        for first in touching:
            for second in touching:
                if first is second:
                    continue
                a = first.start if first.end == at else first.end
                b = second.start if second.end == at else second.end
                if (a.x == b.x == at.x) or (a.y == b.y == at.y):
                    joined = replace(first, start=a, end=b)
                    kept = tuple(w for w in sheet.wires if w is not first and w is not second)
                    changed = replace(sheet, wires=(*kept, joined))
                    reasons = [i.message.split(":", 1)[0] for i in grammar_issues(changed)]
                    assert "wire-touch" in reasons
                    return
    pytest.fail("no T with a straight run on the op-amp sheet")

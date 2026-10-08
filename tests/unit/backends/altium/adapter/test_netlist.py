# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The netlist of a set of sheets (capability altium-import, "Net identifier scope", "Net names", "Buses",
"Harnesses" and "Hierarchy as modules"; change c0043)."""

from __future__ import annotations

from collections.abc import Sequence

import _altium_records as rec

from fenolite.backends.altium.adapter.circuit import import_circuit
from fenolite.backends.altium.adapter.netlist import (
    Netlist,
    NetOptions,
    PinKey,
    choose_scope,
    natural,
    netlist,
    resolve,
    sheet_data,
)
from fenolite.backends.altium.read.project import ProjectOptions
from fenolite.core.errors import Issue
from fenolite.model.circuit import Circuit


def run(sheets: Sequence[rec.Sheet], issues: list[Issue] | None = None, **options: object) -> Netlist:
    return netlist([s.input() for s in sheets], options=NetOptions(**options), issues=issues)  # type: ignore[arg-type]


def pins(found: Netlist) -> dict[str, list[tuple[str, str]]]:
    """Net name → its pins as (unique id of the component, designator); ``part`` names the id by the ref."""
    return {
        net.name: [(pin.component.rsplit("\\", 1)[-1], pin.designator) for pin in net.pins]
        for net in found.nets
    }


def part(sheet: rec.Sheet, ref: str, *at: tuple[int, int]) -> None:
    """A component whose unique id is its reference, with pins 1, 2 … at the given points."""
    sheet.component(ref, [(str(n), x, y) for n, (x, y) in enumerate(at, 1)], uid=ref)


def module(file: str, ref: str, port: str = "EN", **port_options: object) -> rec.Sheet:
    """A sheet with one part whose pin 1 is wired to a port."""
    sheet = rec.Sheet(file)
    part(sheet, ref, (10, 10))
    sheet.wire((10, 10), (30, 10))
    sheet.port(port, 30, 10, **port_options)  # type: ignore[arg-type]
    return sheet


def codes(issues: list[Issue]) -> list[str]:
    return [i.code.removeprefix("altium.import.") for i in issues]


# --- scope ----------------------------------------------------------------------------------------------


def test_scope_ports_do_not_join_sideways() -> None:
    top = rec.Sheet("top.SchDoc")
    top.symbol("A", "a.SchDoc", (100, 200), entries=[("EN", 1, 1)])
    top.symbol("B", "b.SchDoc", (300, 200), entries=[("EN", 0, 1)])
    sheets = [top, module("a.SchDoc", "R1"), module("b.SchDoc", "R2")]
    issues: list[Issue] = []
    found = run(sheets, issues)
    assert found.scope == "hierarchical" and codes(issues) == ["scope", "duplicate-net-name"]
    assert issues[0].message == "the net identifier scope is hierarchical"
    assert pins(found) == {"EN": [("R1", "1")], "EN#2": [("R2", "1")]}
    flat = run(sheets, scope="flat")
    assert [sorted(net.pins) for net in flat.nets if net.pins] == [
        [PinKey("cmp:\\TOP00001\\R1", "1"), PinKey("cmp:\\TOP00002\\R2", "1")]
    ]
    # Wired together on the top sheet, the two entries join the modules in the hierarchical scope too.
    top.wire((150, 190), (300, 190))
    joined = run(sheets)
    assert sorted(len(net.pins) for net in joined.nets) == [2]


def test_scope_automatic_without_sheet_entries_is_flat() -> None:
    issues: list[Issue] = []
    found = run([module("a.SchDoc", "R1", "CLK"), module("b.SchDoc", "R2", "CLK")], issues)
    assert found.scope == "flat" and codes(issues) == ["scope"]
    assert pins(found) == {"NetR1_1": [("R1", "1"), ("R2", "1")]}
    named = run([module("a.SchDoc", "R1", "CLK"), module("b.SchDoc", "R2", "CLK")], allow_port_names=True)
    assert list(pins(named)) == ["CLK"]


def test_scope_automatic_without_ports_is_global() -> None:
    def sheet(file: str, ref: str) -> rec.Sheet:
        found = rec.Sheet(file)
        part(found, ref, (10, 10))
        found.wire((10, 10), (30, 10))
        found.label("DATA", 20, 10)
        return found

    found = run([sheet("a.SchDoc", "R1"), sheet("b.SchDoc", "R2")])
    assert found.scope == "global" and pins(found) == {"DATA": [("R1", "1"), ("R2", "1")]}
    local = run([sheet("a.SchDoc", "R1"), sheet("b.SchDoc", "R2")], scope="flat")
    assert pins(local) == {"DATA": [("R1", "1")], "DATA#2": [("R2", "1")]}
    data = [sheet_data(s.input()) for s in (sheet("a.SchDoc", "R1"),)]
    assert choose_scope(data, [0]) == "global"


def test_scope_from_project_options() -> None:
    assert NetOptions.from_project(ProjectOptions(hierarchy_mode=0, net_scope="automatic")) == NetOptions()
    options = NetOptions.from_project(
        ProjectOptions(
            hierarchy_mode=0,
            net_scope="strict-hierarchical",
            allow_port_net_names=True,
            allow_sheet_entry_net_names=False,
            power_port_names_take_priority=True,
            append_sheet_number_to_local_nets=True,
        )  # fmt: skip
    )
    assert options == NetOptions(
        scope="strict_hierarchical", power_port_names_first=True, allow_port_names=True,
        allow_sheet_entry_names=False, append_sheet_numbers=True,
    )  # fmt: skip
    unknown = NetOptions.from_project(ProjectOptions(hierarchy_mode=2, net_scope=None))
    assert unknown.scope == "automatic" and unknown.scope_unknown
    assert not NetOptions.from_project(ProjectOptions()).scope_unknown
    issues: list[Issue] = []
    netlist([module("a.SchDoc", "R1").input()], options=unknown, issues=issues)
    assert codes(issues) == ["scope-unknown", "scope"] and issues[0].severity == "warning"
    issues = []
    netlist([module("a.SchDoc", "R1").input()], options=options, issues=issues)
    assert codes(issues) == ["scope", "option-ignored"] and "strict_hierarchical" in issues[0].message


def test_power_ports_join_over_the_design_but_not_in_the_strict_scope() -> None:
    def sheet(file: str, ref: str) -> rec.Sheet:
        found = rec.Sheet(file)
        part(found, ref, (10, 10))
        found.power("GND", 10, 10)
        return found

    top = rec.Sheet("top.SchDoc")
    top.symbol("A", "a.SchDoc", (100, 200))
    part(top, "R0", (10, 10))
    top.power("gnd", 10, 10)
    sheets = [top, sheet("a.SchDoc", "R1")]
    assert [len(net.pins) for net in run(sheets, scope="hierarchical").nets] == [2]
    assert [len(net.pins) for net in run(sheets, scope="flat").nets] == [2]
    strict = run(sheets, scope="strict_hierarchical")
    assert sorted(len(net.pins) for net in strict.nets) == [1, 1]


def test_power_port_wired_to_a_port_stays_local_in_the_hierarchical_scopes() -> None:
    child = rec.Sheet("a.SchDoc")
    part(child, "R1", (10, 10))
    child.wire((10, 10), (30, 10))
    child.port("VIN", 30, 10)
    child.power("VCC", 10, 10)
    top = rec.Sheet("top.SchDoc")
    top.symbol("A", "a.SchDoc", (100, 200), entries=[("VIN", 0, 1)])
    part(top, "R0", (10, 10))
    top.power("VCC", 10, 10)
    part(top, "R9", (50, 190))
    top.wire((50, 190), (100, 190))
    local = run([top, child])
    assert sorted(sorted(p[0] for p in found) for found in pins(local).values()) == [["R0"], ["R1", "R9"]]
    flat = run([top, child], scope="flat")
    assert sorted(sorted(p[0] for p in found) for found in pins(flat).values()) == [["R0", "R1"], ["R9"]]


def test_port_joins_the_sheet_entry_of_its_name_only() -> None:
    top = rec.Sheet("top.SchDoc")
    top.symbol("A", "a.SchDoc", (100, 200), entries=[("EN", 0, 1), ("OTHER", 0, 2)])
    part(top, "R0", (50, 190), (50, 180))
    top.wire((50, 190), (100, 190))
    top.wire((50, 180), (100, 180))
    found = run([top, module("a.SchDoc", "R1")])
    assert pins(found) == {"EN": [("R0", "1"), ("R1", "1")], "OTHER": [("R0", "2")]}


def test_sheet_missing_keeps_its_entries_as_named_points() -> None:
    issues: list[Issue] = []
    top = rec.Sheet("top.SchDoc")
    top.symbol("PWR", "Sub\\Power.SchDoc", (100, 200), entries=[("VIN", 0, 1)])
    part(top, "R0", (50, 190))
    top.wire((50, 190), (100, 190))
    found = run([top], issues)
    (missing,) = [i for i in issues if i.code == "altium.import.sheet-missing"]
    assert "Power.SchDoc" in missing.message and missing.where == "top.SchDoc:FileHeader#1"
    assert found.scope == "hierarchical" and pins(found) == {"VIN": [("R0", "1")]}


def test_sheet_named_by_two_symbols_is_instantiated_twice() -> None:
    issues: list[Issue] = []
    top = rec.Sheet("top.SchDoc")
    top.symbol("CH1", "ch.SchDoc", (100, 200), uid="SYMBOL01")
    top.symbol("CH2", "CH.schdoc", (300, 200), uid="SYMBOL02")
    resolved = resolve([top.input(), module("ch.SchDoc", "R1").input()], issues=issues)
    assert codes(issues) == ["channels", "scope"] and issues[0].where == "ch.SchDoc"
    assert issues[0].severity == "info"
    assert [(i.sheet, i.uids, i.names) for i in resolved.instances] == [
        (0, (), ()),
        (1, ("SYMBOL01",), ("CH1",)),
        (1, ("SYMBOL02",), ("CH2",)),
    ]
    assert sorted(resolved.component_ids.values()) == ["cmp:\\SYMBOL01\\R1", "cmp:\\SYMBOL02\\R1"]


def test_sheet_symbol_with_a_repeat_statement_and_several_files() -> None:
    issues: list[Issue] = []
    top = rec.Sheet("top.SchDoc")
    top.symbol("Repeat(CH,1,4)", "a.SchDoc; b.SchDoc", (100, 200))
    resolved = resolve(
        [top.input(), module("a.SchDoc", "R1").input(), module("b.SchDoc", "R2").input()], issues=issues
    )
    assert codes(issues) == ["channels", "scope"] and len(resolved.instances) == 9
    assert [i.names for i in resolved.instances[1:3]] == [("CH[1]",), ("CH[2]",)]


def test_sheet_loop_is_an_error_without_descent() -> None:
    issues: list[Issue] = []
    first = rec.Sheet("a.SchDoc")
    first.symbol("B", "b.SchDoc", (100, 200))
    second = rec.Sheet("b.SchDoc")
    second.symbol("A", "a.SchDoc", (100, 200))
    top = rec.Sheet("top.SchDoc")
    top.symbol("A", "a.SchDoc", (100, 200))
    resolved = resolve([top.input(), first.input(), second.input()], issues=issues)
    loops = [i for i in issues if i.code == "altium.import.sheet-loop"]
    assert len(loops) == 1 and loops[0].severity == "error" and loops[0].where.startswith("b.SchDoc:")
    assert [i.sheet for i in resolved.instances] == [0, 1, 2]


def test_off_sheet_connectors_join_under_one_parent() -> None:
    def sheet(file: str, ref: str) -> rec.Sheet:
        found = rec.Sheet(file)
        part(found, ref, (10, 10))
        found.power("LINK", 10, 10, off_sheet=True)
        return found

    found = run([sheet("a.SchDoc", "R1"), sheet("b.SchDoc", "R2")], scope="hierarchical")
    assert pins(found) == {"LINK": [("R1", "1"), ("R2", "1")]}
    top = rec.Sheet("top.SchDoc")
    top.symbol("A", "a.SchDoc", (100, 200))
    part(top, "R0", (10, 10))
    top.power("LINK", 10, 10, off_sheet=True)
    apart = run([top, sheet("a.SchDoc", "R1")], scope="flat")
    assert sorted(len(net.pins) for net in apart.nets) == [1, 1]


def test_sheet_kinds_never_join_by_name() -> None:
    sheet = rec.Sheet()
    part(sheet, "R1", (10, 10), (10, 30), (10, 50))
    sheet.label("X", 10, 10)
    sheet.power("X", 10, 30)
    sheet.port("X", 10, 50)
    found = run([sheet], scope="global", allow_port_names=True)
    assert sorted(len(net.pins) for net in found.nets) == [1, 1, 1]
    assert sorted(net.name for net in found.nets) == ["X", "X#2", "X#3"]


# --- names ----------------------------------------------------------------------------------------------


def named(issues: list[Issue] | None = None, **options: object) -> Netlist:
    sheet = rec.Sheet()
    part(sheet, "R1", (10, 10), (30, 10))
    sheet.wire((10, 10), (30, 10))
    sheet.label("VBUS", 20, 10)
    sheet.power("5V", 10, 10)
    return run([sheet], issues, **options)


def test_name_label_beats_power_port() -> None:
    (net,) = named().nets
    assert (net.name, net.aliases) == ("VBUS", ("5V",))
    (net,) = named(power_port_names_first=True).nets
    assert (net.name, net.aliases) == ("5V", ("VBUS",))


def test_name_of_a_net_without_an_identifier() -> None:
    sheet = rec.Sheet()
    part(sheet, "R10", (0, 0), (10, 10))
    part(sheet, "R2", (30, 10))
    part(sheet, "U1", (0, 5), (0, 6), (20, 10))
    sheet.wire((10, 10), (30, 10))
    (net,) = run([sheet]).nets
    assert net.name == "NetR2_1" and net.aliases == ()
    assert [(pin.component[-3:].lstrip("\\"), pin.designator) for pin in net.pins] == [
        ("R10", "2"),
        ("R2", "1"),
        ("U1", "3"),
    ]
    assert natural("R10") > natural("R2") and natural("A") < natural("B1")


def test_name_same_on_two_nets() -> None:
    issues: list[Issue] = []
    sheet = rec.Sheet()
    part(sheet, "R1", (10, 10), (10, 30))
    sheet.label("GND", 10, 10)
    sheet.power("GND", 10, 30)
    found = run([sheet], issues)
    assert [net.name for net in found.nets] == ["GND", "GND#2"]
    (warning,) = [i for i in issues if i.code == "altium.import.duplicate-net-name"]
    assert warning.where == "GND" and warning.severity == "warning"


def test_name_smallest_text_and_sorted_aliases() -> None:
    sheet = rec.Sheet()
    part(sheet, "R1", (10, 10), (30, 10))
    sheet.wire((10, 10), (30, 10))
    for text, x in (("beta", 12), ("Alpha", 14), ("alpha", 16), ("Gamma", 18)):
        sheet.label(text, x, 10)
    (net,) = run([sheet]).nets
    assert net.name == "Alpha" and net.aliases == ("Gamma", "alpha", "beta")


def test_name_ports_and_sheet_entries_only_with_their_options() -> None:
    top = rec.Sheet("top.SchDoc")
    top.symbol("A", "a.SchDoc", (100, 200), entries=[("EN", 0, 1)])
    part(top, "R0", (50, 190))
    top.wire((50, 190), (100, 190))
    sheets = [top, module("a.SchDoc", "R1")]
    assert list(pins(run(sheets))) == ["EN"]  # the sheet entry names it by default
    assert list(pins(run(sheets, allow_sheet_entry_names=False))) == ["NetR0_1"]
    both = run(sheets, allow_port_names=True)
    assert [(net.name, net.aliases) for net in both.nets] == [("EN", ())]


def test_name_level_of_the_sheet() -> None:
    top = rec.Sheet("top.SchDoc")
    top.symbol("A", "a.SchDoc", (100, 200), entries=[("EN", 0, 1)])
    part(top, "R0", (50, 190))
    top.wire((50, 190), (100, 190))
    top.label("TOP_NAME", 60, 190)
    child = module("a.SchDoc", "R1")
    child.label("LOW_NAME", 20, 10)
    assert [net.name for net in run([top, child]).nets] == ["LOW_NAME"]
    high = run([top, child], higher_level_names_first=True)
    assert [(net.name, net.aliases) for net in high.nets] == [("TOP_NAME", ("EN", "LOW_NAME"))]


def test_name_single_pins_and_dangling_names() -> None:
    sheet = rec.Sheet()
    part(sheet, "R1", (10, 10), (10, 30), (10, 50))
    sheet.label("ONE", 10, 10)
    sheet.wire((10, 30), (30, 30))
    sheet.wire((60, 60), (80, 60))
    sheet.label("LOOSE", 70, 60)
    found = run([sheet])
    assert pins(found) == {"LOOSE": [], "ONE": [("R1", "1")]}
    assert [net.name for net in found.nets] == sorted(net.name for net in found.nets)


# --- buses ----------------------------------------------------------------------------------------------


def bus_sheets() -> tuple[rec.Sheet, rec.Sheet]:
    child = rec.Sheet("mem.SchDoc")
    child.component("U1", [(str(n), 10, 10 + 10 * n) for n in range(4)], uid="U1")
    top = rec.Sheet("top.SchDoc")
    top.component("U2", [(str(n), 10, 10 + 10 * n) for n in range(4)], uid="U2")
    for n in range(4):
        child.wire((10, 10 + 10 * n), (40, 10 + 10 * n))
        child.label(f"D{n}", 20, 10 + 10 * n)
        top.wire((10, 10 + 10 * n), (40, 10 + 10 * n))
        top.label(f"DATA{n}", 20, 10 + 10 * n)
    child.bus((50, 0), (50, 60), (80, 60))
    child.port("D[0..3]", 80, 60)
    top.bus((50, 0), (50, 60), (100, 60))
    top.label("DATA[3..0]", 50, 30)
    top.symbol("MEM", "mem.SchDoc", (100, 70), entries=[("D[0..3]", 0, 1)])
    return top, child


def test_bus_through_a_port() -> None:
    issues: list[Issue] = []
    top, child = bus_sheets()
    found = run([top, child], issues)
    assert found.scope == "hierarchical" and codes(issues) == ["scope"]
    by_pin = {(p[0], p[1]): name for name, group in pins(found).items() for p in group}
    assert by_pin[("U1", "0")] == by_pin[("U2", "3")] and by_pin[("U1", "3")] == by_pin[("U2", "0")]
    assert len(found.nets) == 4 and all(len(net.pins) == 2 for net in found.nets)
    (bus,) = found.buses
    assert (bus.name, bus.label) == ("DATA", "DATA[3..0]") and [i for i, _ in bus.members] == [3, 2, 1, 0]
    circuit = import_circuit([top.input(), child.input()])
    (entity,) = circuit.buses
    names = {net.id: net.name for net in circuit.nets}
    assert entity.name == "DATA" and entity.id.startswith("bus_")
    assert [(m.index, names[m.net_id]) for m in entity.members] == list(bus.members)
    assert entity.ext["altium"].payload == (("label", "DATA[3..0]"),)


def test_bus_members_without_a_net_and_width_mismatch() -> None:
    issues: list[Issue] = []
    sheet = rec.Sheet()
    part(sheet, "R1", (10, 10))
    sheet.wire((10, 10), (40, 10))
    sheet.label("A1", 20, 10)
    sheet.bus((50, 0), (50, 60))
    sheet.label("A[0..2]", 50, 30)
    sheet.label("B[0..1]", 50, 40)
    found = run([sheet], issues)
    (bus,) = found.buses
    assert (bus.name, bus.members) == ("A", ((1, "A1"),))
    assert codes(issues) == ["scope", "bus-width", "bus-member"]
    assert issues[2].message.startswith("2 bus member(s)") and issues[1].severity == "warning"


def test_bus_text_of_another_form_is_an_ordinary_identifier() -> None:
    sheet = rec.Sheet()
    part(sheet, "R1", (10, 10))
    sheet.label("A[0]", 10, 10)
    found = run([sheet])
    assert pins(found) == {"A[0]": [("R1", "1")]} and found.buses == ()


# --- harnesses and modules ------------------------------------------------------------------------------


def test_harness_unwired_entry() -> None:
    issues: list[Issue] = []
    sheet = rec.Sheet()
    part(sheet, "U1", (60, 90))
    sheet.connector("SPI", (100, 100), (50, 40), [("MOSI", 1), ("HOLD", 2)])
    sheet.wire((60, 90), (100, 90))
    found = run([sheet], issues)
    (harness,) = found.harnesses
    assert (harness.type, harness.members) == ("SPI", (("MOSI", "SPI.MOSI"),))
    assert pins(found) == {"SPI.MOSI": [("U1", "1")]}
    (info,) = [i for i in issues if i.code == "altium.import.harness-entry"]
    assert info.message.startswith("1 harness entr")
    circuit = import_circuit([sheet.input()])
    (interface,) = circuit.interfaces
    assert (interface.name, interface.kind, list(interface.members)) == ("SPI", "harness", ["MOSI"])
    assert interface.ext["altium"].payload == (("harness_type", "SPI"),)


def harness_module(file: str, ref: str) -> rec.Sheet:
    sheet = rec.Sheet(file)
    part(sheet, ref, (60, 90), (60, 80))
    sheet.connector("SPI", (100, 100), (50, 40), [("MOSI", 1), ("SCK", 2)])
    sheet.wire((60, 90), (100, 90))
    sheet.wire((60, 80), (100, 80))
    sheet.harness_line((150, 90), (200, 90))
    sheet.port("BUS", 200, 90, harness="SPI")
    return sheet


def test_harness_entries_of_one_name_are_one_net_across_sheets() -> None:
    top = rec.Sheet("top.SchDoc")
    top.symbol("A", "a.SchDoc", (100, 200), entries=[("BUS", 1, 1, "SPI")])
    top.symbol("B", "b.SchDoc", (400, 200), entries=[("BUS", 0, 1, "SPI")])
    top.harness_line((200, 190), (400, 190))
    sheets = [top, harness_module("a.SchDoc", "U1"), harness_module("b.SchDoc", "U2")]
    issues: list[Issue] = []
    found = run(sheets, issues)
    assert codes(issues) == ["scope"]
    assert pins(found) == {
        "BUS.MOSI": [("U1", "1"), ("U2", "1")],
        "BUS.SCK": [("U1", "2"), ("U2", "2")],
    }
    (harness,) = found.harnesses
    assert harness.members == (("MOSI", "BUS.MOSI"), ("SCK", "BUS.SCK"))
    # Without the line between the two sheet entries the modules stay apart.
    apart = rec.Sheet("top.SchDoc")
    apart.symbol("A", "a.SchDoc", (100, 200), entries=[("BUS", 1, 1, "SPI")])
    apart.symbol("B", "b.SchDoc", (400, 200), entries=[("BUS", 0, 1, "SPI")])
    alone = run([apart, sheets[1], sheets[2]])
    assert len(alone.harnesses) == 2 and sorted(len(net.pins) for net in alone.nets) == [1, 1, 1, 1]


def test_harness_nested_entry_is_reported() -> None:
    issues: list[Issue] = []
    sheet = rec.Sheet()
    sheet.connector("OUTER", (100, 100), (50, 40), [("INNER", 1)])
    sheet.harness_line((60, 90), (100, 90))
    run([sheet], issues)
    (nested,) = [i for i in issues if i.code == "altium.import.harness-nested"]
    assert nested.where == "sheet.SchDoc:Additional#1" and nested.severity == "warning"


def circuit_of(sheets: Sequence[rec.Sheet], issues: list[Issue] | None = None) -> Circuit:
    return import_circuit([s.input() for s in sheets], issues=issues)


def test_module_per_sheet_symbol_instance() -> None:
    top = rec.Sheet("top.SchDoc")
    top.symbol("power", "pwr.SchDoc", (100, 200), uid="SYMPOWER")
    part(top, "J1", (10, 10))
    middle = rec.Sheet("pwr.SchDoc")
    middle.symbol("ldo", "ldo.SchDoc", (100, 200), uid="SYMLDO01")
    part(middle, "C2", (10, 10))
    part(middle, "C10", (10, 30))
    leaf = rec.Sheet("ldo.SchDoc")
    part(leaf, "U1", (10, 10))
    circuit = circuit_of([top, middle, leaf])
    outer, inner = circuit.modules
    refs = {c.id: c.ref for c in circuit.components}
    assert (outer.path, outer.parent, [refs[i] for i in outer.component_ids]) == (
        "power",
        None,
        ["C2", "C10"],
    )
    assert (inner.path, inner.parent, [refs[i] for i in inner.component_ids]) == (
        "power/ldo",
        outer.id,
        ["U1"],
    )
    assert outer.native_ids == {"altium": "module:\\SYMPOWER"}
    assert inner.native_ids == {"altium": "module:\\SYMPOWER\\SYMLDO01"}
    assert {c.ref: c.path for c in circuit.components} == {
        "J1": "J1", "C2": "power/C2", "C10": "power/C10", "U1": "power/ldo/U1",
    }  # fmt: skip
    assert outer.provenance is not None and outer.provenance.file == "pwr.SchDoc"
    assert circuit_of([leaf]).modules == ()


def test_module_names_without_a_sheet_name_and_twice() -> None:
    issues: list[Issue] = []
    top = rec.Sheet("top.SchDoc")
    top.symbol("", "Sub\\a.SchDoc", (100, 200), named=False)
    top.symbol("X", "b.SchDoc", (300, 200))
    top.symbol("X", "c.SchDoc", (500, 200))
    sheets = [top, *(module(f"{name}.SchDoc", f"R{n}") for n, name in enumerate("abc"))]
    circuit = circuit_of(sheets, issues)
    assert [m.path for m in circuit.modules] == ["a", "X", "X#2"]
    (twice,) = [i for i in issues if i.code == "altium.import.duplicate-sheet-name"]
    assert twice.where == "top.SchDoc:FileHeader#6"

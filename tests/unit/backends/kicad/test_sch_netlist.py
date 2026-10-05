# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fenolite's own netlist of a generated sheet and its grammar check (capability kicad-schematic, "Own
netlist of a generated sheet" and "Netlist grammar check"; change c0063). Hermetic: no tool runs."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import replace
from functools import cache
from pathlib import Path

import pytest
from _buildhelp import blink, build
from _schbuild import blink_unmarked, built_units, sheet_of

from fenolite.backends.kicad import sch, sch_netlist, schlayout
from fenolite.backends.kicad.netlist import KicadNetlist, NetlistNet, NetNode
from fenolite.backends.kicad.sch_netlist import NetlistUnsupportedError, grammar_issues, own_netlist
from fenolite.core.coords import Point
from fenolite.model.schematic import NetLabel, SchematicSheet, SymbolUse

DATA = Path(__file__).resolve().parents[3] / "data" / "kicad" / "schematic"
WIRE = '(wire (pts (xy 10.16 10.16) (xy 20.32 10.16)) (stroke (width 0) (type default)) (uuid "{}"))'


@cache
def blink_sheet(marks: bool = True) -> SchematicSheet:
    output = build(blink() if marks else blink_unmarked())
    assert output.schematic is not None
    return output.schematic.sheet


@cache
def units_sheet() -> SchematicSheet:
    output = built_units()
    assert output.schematic is not None
    return output.schematic.sheet


def fixture(name: str) -> SchematicSheet:
    return sch.read_schematic((DATA / name).read_text(encoding="utf-8"), file=name)


def net(found: KicadNetlist, name: str) -> NetlistNet:
    return next(n for n in found.nets if n.name == name)


def elements(found: KicadNetlist, name: str) -> list[str]:
    return [node.element for node in net(found, name).nodes]


def reasons(sheet: SchematicSheet) -> list[str]:
    return [issue.message.split(":", 1)[0] for issue in grammar_issues(sheet)]


# -- the own netlist


def test_blink_sheet() -> None:
    found = own_netlist(blink_sheet(), project="blink")
    assert [c.ref for c in found.components] == ["D1", "R1", "U1"]
    assert (found.components[1].value, found.components[1].footprint) == ("330", "Mini:Mini_R_0603")
    named = [n.name for n in found.nets if not n.name.startswith("unconnected-(")]
    assert named == ["GND", "LED_A", "LED_DRV", "VIN"]
    assert elements(found, "GND") == ["D1-1", "U1-10"]
    assert elements(found, "LED_A") == ["D1-2", "R1-2"]
    assert elements(found, "LED_DRV") == ["R1-1", "U1-1"]
    assert elements(found, "VIN") == ["U1-9"]
    open_nets = [n for n in found.nets if n.name.startswith("unconnected-(U1-")]
    assert len(open_nets) == 29 and all(len(n.nodes) == 1 for n in open_nets)
    assert not any(node.ref.startswith("#") for n in found.nets for node in n.nodes)
    assert all(n.netclass == "" for n in found.nets)


def test_properties_are_the_fields_kicad_lists() -> None:
    led = own_netlist(blink_sheet(), project="blink").components[0]
    assert set(led.properties) == {"Footprint", "Datasheet", "Description", "fenolite.path"}
    assert led.properties["fenolite.path"] == "D1"


def test_flag_marks_the_pin_type() -> None:
    marked = own_netlist(blink_sheet(), project="blink")
    assert net(marked, "unconnected-(U1-PA1-Pad2)").nodes == (NetNode("U1", "2", "bidirectional+no_connect"),)
    bare = own_netlist(blink_sheet(False), project="blink")
    assert net(bare, "unconnected-(U1-PA1-Pad2)").nodes == (NetNode("U1", "2", "bidirectional"),)
    assert net(marked, "GND").nodes[1] == NetNode("U1", "10", "power_in")


def test_pad_numbers_of_a_mapped_part() -> None:
    found = own_netlist(units_sheet(), project="units")
    assert "D1-2" in elements(found, "GND")
    assert "D1-1" in elements(found, "mod{slash}LED_A")


def test_stored_names() -> None:
    names = [n.name for n in own_netlist(units_sheet(), project="units").nets]
    assert "mod{slash}LED_A" in names and "mod/LED_A" not in names


def test_units_of_one_part() -> None:
    found = own_netlist(units_sheet(), project="units")
    assert [c.ref for c in found.components] == ["D1", "R1", "U2"]
    assert elements(found, "GND") == ["D1-2", "U2-7"]
    assert elements(found, "VCC") == ["U2-14"]
    assert net(found, "unconnected-(U2-Pad1)").nodes == (NetNode("U2", "1", "input+no_connect"),)


def test_read_back_sheet_gives_the_same_netlist() -> None:
    for output, project in ((build(blink()), "blink"), (built_units(), "units")):
        assert output.schematic is not None
        generated = own_netlist(output.schematic.sheet, project=project)
        assert own_netlist(sheet_of(output), project=project) == generated


def test_another_project_has_no_component() -> None:
    found = own_netlist(blink_sheet(), project="other")
    assert found == KicadNetlist((), ())


def test_reads_no_file_and_no_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("no subprocess and no file is allowed here")

    sheet = blink_sheet()
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr("builtins.open", refuse)
    assert len(own_netlist(sheet, project="blink").nets) == 33


def test_evidence_names_its_hypothesis() -> None:
    assert sch_netlist.EVIDENCE.hypotheses == ("H-K-NETLIST-OWN",)


# -- the grammar check


def test_generated_sheets_are_inside_the_grammar() -> None:
    assert grammar_issues(blink_sheet()) == ()
    assert grammar_issues(blink_sheet(False)) == ()
    assert grammar_issues(units_sheet()) == ()
    assert grammar_issues(sheet_of(build(blink(), 9))) == ()


def test_authored_sheet_with_a_wire() -> None:
    flat = fixture("flat.kicad_sch")
    found = reasons(flat)
    assert "wire" in found and "label-kind" in found
    with pytest.raises(NetlistUnsupportedError) as caught:
        own_netlist(flat, project="flat")
    assert caught.value.issues == grammar_issues(flat)
    assert caught.value.cli_code == "FEN-7001"
    assert "--source kicad" in caught.value.hint


def test_hierarchy_refused() -> None:
    assert "sheet" in reasons(fixture("hier/top.kicad_sch"))


def test_issue_form() -> None:
    (issue,) = (i for i in grammar_issues(fixture("hier/top.kicad_sch")) if i.message.startswith("sheet:"))
    assert (issue.code, issue.severity) == ("kicad.sch.netlist-unsupported", "error")
    assert dict(sch_netlist.ISSUE_CODES) == {"kicad.sch.netlist-unsupported": "error"}
    assert "kicad.sch.netlist-unsupported" not in sch.ISSUE_CODES, "the reader's set stays closed"


def with_wire() -> SchematicSheet:
    output = build(blink())
    text = output.files["blink.kicad_sch"].decode("utf-8")
    wire = WIRE.format("0c0063aa-0000-4000-8000-000000000001")
    assert text.count("(sheet_instances") == 1
    return sch.read_schematic(
        text.replace("(sheet_instances", f"{wire}\n\t(sheet_instances"), file="w.kicad_sch"
    )


def with_local_label() -> SchematicSheet:
    sheet = blink_sheet()
    return replace(sheet, labels=(replace(sheet.labels[0], kind="local", shape=""), *sheet.labels[1:]))


def with_two_uses() -> SchematicSheet:
    sheet = blink_sheet()
    first = sheet.symbols[0]
    twice = replace(first, uses=(*first.uses, SymbolUse("other", "/x", "D9", 1)))
    return replace(sheet, symbols=(twice, *sheet.symbols[1:]))


def without_definition() -> SchematicSheet:
    sheet = blink_sheet()
    return replace(sheet, lib_symbols=tuple(d for d in sheet.lib_symbols if d.name != "Mini_R"))


def with_label_off_pin() -> SchematicSheet:
    sheet = blink_sheet()
    first = sheet.labels[0]
    moved = replace(first, position=Point(first.position.x + schlayout.GRID, first.position.y))
    return replace(sheet, labels=(moved, *sheet.labels[1:]))


def with_two_names() -> SchematicSheet:
    sheet = blink_sheet()
    first = sheet.labels[0]
    other = NetLabel(id="lbl-other", kind="global", name="OTHER", position=first.position, shape="passive")
    return replace(sheet, labels=(*sheet.labels, other))


def with_shared_point() -> SchematicSheet:
    sheet = blink_sheet()
    resistor = next(s for s in sheet.symbols if s.ref == "R1")
    use = replace(resistor.uses[0], ref="R2")
    second = replace(resistor, id="sci-r2", ref="R2", uses=(use,))
    return replace(sheet, symbols=(*sheet.symbols, second))


def with_hidden_power() -> SchematicSheet:
    sheet = blink_sheet()
    definitions = []
    for definition in sheet.lib_symbols:
        if definition.name == "Mini_QFP32_IC":
            pins = tuple(replace(p, hidden=p.etype == "power_in") for p in definition.pins)
            definition = replace(definition, pins=pins)
        definitions.append(definition)
    return replace(sheet, lib_symbols=tuple(definitions))


BUILDERS: dict[str, Callable[[], SchematicSheet]] = {
    "wire": with_wire,
    "label-kind": with_local_label,
    "sheet": with_two_uses,
    "undefined-symbol": without_definition,
    "label-off-pin": with_label_off_pin,
    "two-names": with_two_names,
    "shared-point": with_shared_point,
    "frame": blink_sheet,
    "hidden-power": with_hidden_power,
}


@pytest.mark.parametrize("reason", sch_netlist.REASONS)
def test_each_reason(reason: str, monkeypatch: pytest.MonkeyPatch) -> None:
    if reason == "frame":
        proved = schlayout.PROVED_FRAMES - {(0, "")}
        monkeypatch.setattr(schlayout, "PROVED_FRAMES", proved)
    sheet = BUILDERS[reason]()
    found = reasons(sheet)
    assert found == [reason], found
    with pytest.raises(NetlistUnsupportedError, match=reason):
        own_netlist(sheet, project="blink")


def test_reasons_are_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    emitted: set[str] = set()
    for name in ("flat.kicad_sch", "hier/top.kicad_sch", "bus.kicad_sch", "units.kicad_sch"):
        emitted |= set(reasons(fixture(name)))
    for reason, builder in BUILDERS.items():
        if reason != "frame":
            emitted |= set(reasons(builder()))
    monkeypatch.setattr(schlayout, "PROVED_FRAMES", frozenset())
    emitted |= set(reasons(blink_sheet()))
    assert emitted == set(sch_netlist.REASONS)
    assert set(BUILDERS) == set(sch_netlist.REASONS)


def test_power_symbol_refused() -> None:
    sheet = blink_sheet()
    definitions = tuple(replace(d, power="global") if d.name == "Mini_R" else d for d in sheet.lib_symbols)
    assert reasons(replace(sheet, lib_symbols=definitions)) == ["hidden-power"]
    assert all(d.power for d in sheet.lib_symbols if d.library == "fenolite"), "the flag is a power symbol"


def test_stacked_pins_need_a_label() -> None:
    sheet = blink_sheet()
    definitions = []
    for definition in sheet.lib_symbols:
        if definition.name == "Mini_QFP32_IC":
            by_number = {p.number: p for p in definition.pins}
            pins = tuple(
                replace(p, position=by_number["2"].position) if p.number == "3" else p
                for p in definition.pins
            )
            definition = replace(definition, pins=pins)
        definitions.append(definition)
    assert reasons(replace(sheet, lib_symbols=tuple(definitions))) == ["shared-point"]


def test_stacked_pins_under_one_label_are_one_net() -> None:
    sheet = blink_sheet()
    definitions = []
    for definition in sheet.lib_symbols:
        if definition.name == "Mini_QFP32_IC":
            by_number = {p.number: p for p in definition.pins}
            pins = tuple(
                replace(p, position=by_number["10"].position) if p.number == "2" else p
                for p in definition.pins
            )
            definition = replace(definition, pins=pins)
        definitions.append(definition)
    stacked = replace(sheet, lib_symbols=tuple(definitions))
    assert grammar_issues(stacked) == ()
    assert elements(own_netlist(stacked, project="blink"), "GND") == ["D1-1", "U1-2", "U1-10"]


# -- sch.opaque_heads


def test_opaque_heads() -> None:
    assert sch.opaque_heads(blink_sheet()) == {}
    heads = sch.opaque_heads(fixture("flat.kicad_sch"))
    assert heads["wire"] == 5 and heads["junction"] == 1
    assert sch.opaque_heads(fixture("bus.kicad_sch"))["bus_entry"] == 2
    assert sum(sch.opaque_heads(with_wire()).values()) >= 1

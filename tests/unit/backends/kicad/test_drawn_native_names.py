# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad name identity affects connectivity, while extracted drawing text remains literal (c0276)."""

from __future__ import annotations

from dataclasses import replace

import _drawn
import pytest
from _buildhelp import build

from fenolite.backends.kicad import drawn as kdrawn
from fenolite.dsl import Net, connect
from fenolite.model.drawn import DrawnBusAlias, DrawnLabelKind
from fenolite.model.drawn_connect import resolve


@pytest.mark.parametrize("target", [9, 10])
@pytest.mark.parametrize("kind", ["local", "global"])
def test_native_name_aliases_join_without_rewriting_text(target: int, kind: DrawnLabelKind) -> None:
    code, value = _drawn.slash_aliases(kind)
    made = build(code, target, project_dir=_drawn.folder("flat"), drawn=value, drawn_file="schematic.toml")
    assert made.files and not any(i.severity == "error" for i in made.issues), made.issues
    root, children = _drawn.sheets(made)
    extracted, netlist, issues = kdrawn.resolve_sheets(
        root, children, circuit=made.design.circuit, name=code.name, root_file=_drawn.root_name(made)
    )
    assert not any(i.severity == "error" for i in issues), issues
    joined = netlist.net_of(("R1", "1"))
    assert joined is not None and {("U1", "17"), ("R1", "1")} <= set(joined.members)
    assert [label.text for label in extracted.sheets[0].labels] == ["A/B", "A{slash}B"]
    found = kdrawn.extract_with_pins(root, children, components=kdrawn.refs_to_paths(made.design.circuit),
                                    root_file=_drawn.root_name(made))  # fmt: skip
    literal = resolve(found.drawn, found.pins)
    separate = literal.net_of(("R1", "1"))
    assert separate is not None and {("U1", "17"), ("R1", "1")} - set(separate.members)


@pytest.mark.parametrize("target", [9, 10])
def test_native_name_collision_still_refuses_distinct_code_nets(target: int) -> None:
    code, value = _drawn.slash_aliases("global")
    resistor = code.parts["R1"]
    resistor.connections.pop("1")
    connect(Net("A{slash}B"), resistor[1])
    made = build(code, target, project_dir=_drawn.folder("flat"), drawn=value, drawn_file="schematic.toml")
    assert made.files == {}
    assert any(i.code == "build.schematic-netlist-differs" and i.severity == "error" for i in made.issues)


@pytest.mark.parametrize("target", [9, 10])
def test_native_name_sheet_pin_alias(target: int) -> None:
    value = _drawn.drawn("hier")
    root, child = value.sheets
    ref = root.sheet_refs[0]
    root = replace(root, sheet_refs=(replace(ref, pins=(replace(ref.pins[0], name="IN/A"),)),))
    child = replace(
        child,
        labels=tuple(
            replace(label, text="IN{slash}A") if label.kind == "hierarchical" else label
            for label in child.labels
        ),
    )
    made = _drawn.build("hier", target, replace(value, sheets=(root, child)))
    assert made.files and not any(i.severity == "error" for i in made.issues), made.issues
    native_root, children = _drawn.sheets(made)
    found, nets, issues = kdrawn.resolve_sheets(
        native_root, children, circuit=made.design.circuit, name="hier", root_file=_drawn.root_name(made)
    )
    assert not any(i.severity == "error" for i in issues), issues
    group = nets.net_of(("child/R2", "1"))
    assert group is not None and ("U1", "3") in group.members
    assert found.sheets[0].sheet_refs[0].pins[0].name == "IN/A"
    assert found.sheets[1].labels[0].text == "IN{slash}A"


@pytest.mark.parametrize("target", [9, 10])
def test_native_name_bus_alias_members(target: int) -> None:
    value = _drawn.drawn("bus")
    sheets = []
    for index, sheet in enumerate(value.sheets):
        prefix = "D/A" if index == 0 else "D{slash}A"
        labels = tuple(replace(label, text="BUS/A" if "[" in label.text else prefix + label.text[1:])
                       for label in sheet.labels)  # fmt: skip
        refs = tuple(replace(ref, pins=tuple(replace(pin, name="BUS{slash}A") for pin in ref.pins))
                     for ref in sheet.sheet_refs)  # fmt: skip
        alias = DrawnBusAlias("BUS{slash}A", tuple(prefix + str(k) for k in range(4)))
        sheets.append(replace(sheet, labels=labels, sheet_refs=refs, bus_aliases=(alias,)))
    made = _drawn.build("bus", target, replace(value, sheets=tuple(sheets)))
    assert made.files and not any(i.severity == "error" for i in made.issues), made.issues
    root, children = _drawn.sheets(made)
    found, nets, issues = kdrawn.resolve_sheets(
        root, children, circuit=made.design.circuit, name="bus", root_file=_drawn.root_name(made)
    )
    assert not any(i.severity == "error" for i in issues), issues
    for index in range(4):
        group = nets.net_of((f"child/R{index + 10}", "1"))
        assert group is not None and ("U1", str(index + 17)) in group.members
    assert found.sheets[1].bus_aliases[0].members == tuple("D{slash}A" + str(k) for k in range(4))

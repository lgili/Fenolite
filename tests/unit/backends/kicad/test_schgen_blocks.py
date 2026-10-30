# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Block sheets: hierarchical labels and sheet pins from ports, groups and the shared arrangement
(capability kicad-schematic, "Block sheet pins", "Sheet pin geometry", "Block ports sharing a net", "Block
schematic groups on a KiCad sheet", "Shared arrangement of block sheets", "Sheet pins and hierarchical
labels written", and the block scenarios of "Hierarchical sheets of a design", "Own netlist of a generated
sheet" and "Netlist grammar check"; change c0269). Hermetic: no tool runs."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
from _blockbuild import blocks_example, catalog_build
from _schbuild import built_nested, children_of, root_name, sheet_of

from fenolite.backends.kicad import sch, sch_netlist, schlayout
from fenolite.backends.kicad.schgen import GeneratedSchematic
from fenolite.dsl import I2C, Design, Net, Power, block, connect, mm, schematic_group
from fenolite.lens.build import BuildOutput
from fenolite.model.schematic import SchematicSheet

R = "Fenolite:Resistor"
C = "Fenolite:Capacitor"
FP = "Fenolite:Chip_0603"
CH0, CH1 = "sheets/ch0.kicad_sch", "sheets/ch1.kicad_sch"


def generated(output: BuildOutput) -> GeneratedSchematic:
    assert output.schematic is not None, [i.message for i in output.issues if i.severity == "error"]
    return output.schematic


@pytest.fixture(scope="module")
def example() -> BuildOutput:
    return catalog_build(blocks_example())


def labels(sheet: SchematicSheet, kind: str) -> set[str]:
    return {label.name for label in sheet.labels if label.kind == kind}


def pin_point(made: GeneratedSchematic, sheet: SchematicSheet, ref: str, number: str) -> Any:
    instance = next(s for s in sheet.symbols if s.ref == ref)
    definition = next(d for d in sheet.lib_symbols if d.lib_id == instance.lib_ref)
    pin = next(p for p in definition.pins_of(instance.unit, 1) if p.number == number)
    return schlayout.pin_point(
        instance.position, pin.position, instance.rotation // 1_000_000, instance.mirror
    )


def ref_of(output: BuildOutput, path: str) -> str:
    return next(c.ref for c in output.design.circuit.components if c.properties["fenolite.path"] == path)


def test_block_instance_with_ports(example: BuildOutput) -> None:
    made = generated(example)
    root = made.sheet
    assert [r.name for r in root.sheets] == ["ch0 (channel)", "ch1 (channel)"]
    for ref, file in zip(root.sheets, (CH0, CH1), strict=True):
        assert sorted(pin.name for pin in ref.pins) == ["EN", "GND", "VIN"]
        child = made.children[file]
        assert labels(child, "hierarchical") == {"EN", "GND", "VIN"}
        assert labels(child, "global") == set(), "no global label of a port net on the block's sheet"
        for pin in ref.pins:  # the root labels each sheet pin with the circuit net
            at = [label for label in root.labels if label.position == pin.position]
            assert len(at) == 1 and at[0].kind == "global"
    assert {label.name for label in root.labels if label.position == root.sheets[0].pins[1].position} == {
        "VIN"
    }


def test_port_net_labelled_by_the_port(example: BuildOutput) -> None:
    made = generated(example)
    child = made.children[CH0]
    point = pin_point(made, child, ref_of(example, "ch0/R_EN"), "1")
    (label,) = [label for label in child.labels if label.position == point]
    assert (label.kind, label.name, label.shape) == ("hierarchical", "VIN", "input")
    (ref,) = [r for r in made.sheet.sheets if r.name == "ch0 (channel)"]
    (vin,) = [pin for pin in ref.pins if pin.name == "VIN"]
    assert vin.shape == "input"
    (outer,) = [label for label in made.sheet.labels if label.position == vin.position]
    assert (outer.kind, outer.name) == ("global", "VIN")


def test_nested_block_pins_are_hierarchical_on_the_parent(example: BuildOutput) -> None:
    made = generated(example)
    child = made.children[CH0]
    (led,) = child.sheets
    assert sorted(pin.name for pin in led.pins) == ["GND", "VIN"]
    for pin in led.pins:
        (label,) = [label for label in child.labels if label.position == pin.position]
        assert (label.kind, label.name) == ("hierarchical", pin.name)
    inner = made.children["sheets/ch0.led.kicad_sch"]
    assert labels(inner, "hierarchical") == {"GND", "VIN"}
    assert labels(inner, "global") == {"ch0{slash}led{slash}A"}, "a local net keeps its global label"


def test_sides_and_order(example: BuildOutput) -> None:
    (ref, _) = generated(example).sheet.sheets
    left = [(p.name, p.position) for p in ref.pins if p.position.x == ref.position.x]
    right = [(p.name, p.position) for p in ref.pins if p.position.x == ref.position.x + ref.size.w]
    assert [name for name, _ in left] == ["GND", "VIN"] and [name for name, _ in right] == ["EN"]
    assert left[1][1].y - left[0][1].y == schlayout.ORIGIN_STEP
    assert left[0][1].y == ref.position.y + schlayout.ORIGIN_STEP
    assert all(p.position.x % schlayout.GRID == 0 and p.position.y % schlayout.GRID == 0 for p in ref.pins)
    assert {p.rotation for p in ref.pins if p.name != "EN"} == {180_000_000}


def test_two_instances_one_arrangement(example: BuildOutput) -> None:
    made = generated(example)
    origins = []
    for file, prefix in ((CH0, "ch0/"), (CH1, "ch1/")):
        by_path = {
            next(c for c in example.design.circuit.components if c.ref == s.ref).properties["fenolite.path"][
                len(prefix) :
            ]: s.position
            for s in made.children[file].symbols
        }
        origins.append(by_path)
    assert origins[0] == origins[1]


@block
def sensor(b: Any) -> None:
    bus = b.port("I2C", I2C)
    u = b.part("R1", R, footprint=FP)
    v = b.part("R2", R, footprint=FP)
    connect(bus.sda, u[1])
    connect(bus.scl, v[1])
    gnd = b.port("GND", direction="in")
    connect(gnd, u[2], v[2])


def test_interface_port_members() -> None:
    design = Design("i2c")
    design.board(mm(40), mm(30))
    sen = design.use(sensor, "sen")
    sda, scl, gnd = Net("SDA"), Net("SCL"), Net("GND")
    j = design.part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54")
    connect(sda, j[1], sen.I2C.sda)
    connect(scl, j[2], sen.I2C.scl)
    connect(gnd, sen.GND)
    j2 = design.part("J2", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54")
    connect(gnd, j2[1])
    made = generated(catalog_build(design))
    (ref,) = made.sheet.sheets
    assert sorted(pin.name for pin in ref.pins) == ["GND", "I2C_scl", "I2C_sda"]
    assert labels(made.children["sheets/sen.kicad_sch"], "hierarchical") == {"GND", "I2C_scl", "I2C_sda"}


@block
def pair(b: Any) -> None:
    a = b.port("A")
    bb = b.port("B")
    r = b.part("R", R, footprint=FP)
    c = b.part("C", C, footprint=FP)
    connect(a, r[1])
    connect(bb, c[1])
    connect(b.net("M"), r[2], c[2])


def test_two_ports_joined_outside() -> None:
    design = Design("merged")
    design.board(mm(40), mm(30))
    x = design.use(pair, "x")
    connect(x.A, x.B)
    j = design.part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54")
    net = Net("JOIN")
    connect(net, j[1], x.A)
    output = catalog_build(design)
    made = generated(output)
    (ref,) = made.sheet.sheets
    assert not ref.pins
    child = made.children["sheets/x.kicad_sch"]
    assert labels(child, "hierarchical") == set() and "JOIN" in labels(child, "global")
    (merged,) = [i for i in output.issues if i.code == "build.block-port-merged"]
    assert merged.severity == "info" and "x" in merged.message and "A, B" in merged.message


@block
def rc_filter(b: Any) -> None:
    inp = b.port("IN", direction="in")
    out = b.port("OUT", direction="out")
    gnd = b.port("GND", direction="in")
    r1 = b.part("R", R, footprint=FP, value="10k")
    c1 = b.part("C", C, footprint=FP, value="100n")
    connect(inp, r1[1])
    connect(out, r1[2], c1[1])
    connect(gnd, c1[2])
    b.schematic(schematic_group("chain", c1, r1, anchor=r1))


@block(name="rc_filter")
def rc_plain(b: Any) -> None:
    inp = b.port("IN", direction="in")
    out = b.port("OUT", direction="out")
    gnd = b.port("GND", direction="in")
    r1 = b.part("R", R, footprint=FP, value="10k")
    c1 = b.part("C", C, footprint=FP, value="100n")
    connect(inp, r1[1])
    connect(out, r1[2], c1[1])
    connect(gnd, c1[2])


def filter_design(definition: Any) -> Design:
    design = Design("filt")
    design.board(mm(40), mm(30))
    f1 = design.use(definition, "f1")
    src, dst, gnd = Net("SRC"), Net("DST"), Net("GND")
    connect(src, f1.IN)
    connect(dst, f1.OUT)
    connect(gnd, f1.GND)
    j = design.part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54")
    connect(src, j[1])
    connect(dst, j[2])
    design.add(Power(src, gnd))
    return design


def test_declared_chain() -> None:
    output = catalog_build(filter_design(rc_filter))
    made = generated(output)
    child = made.children["sheets/f1.kicad_sch"]
    at = {s.ref: s.position for s in child.symbols}
    r, c = ref_of(output, "f1/R"), ref_of(output, "f1/C")
    assert at[r].x < at[c].x and at[r].y == at[c].y, "R first, then C, in the first row"


def test_default_group_is_a_module_sheet() -> None:
    plain = generated(catalog_build(filter_design(rc_plain)))
    child = plain.children["sheets/f1.kicad_sch"]
    assert labels(child, "hierarchical") == {"IN", "OUT", "GND"}
    # the same parts in a plain module, with the same label texts, flow to the same origins
    texts = {label.position: label.name for label in child.labels}
    assert texts and all(name in ("IN", "OUT", "GND") for name in texts.values())


def test_plain_modules_unchanged() -> None:
    made = generated(built_nested())
    for sheet in (made.sheet, *made.children.values()):
        assert all(label.kind == "global" for label in sheet.labels)
        assert all(not ref.pins and ref.size.h == schlayout.REF_HEIGHT for ref in sheet.sheets)


def test_block_sheets_netlist_created_and_read_back(example: BuildOutput) -> None:
    made = generated(example)
    created = sch_netlist.own_netlist(made.sheet, project="blocks_demo", children=made.children)
    read = sch_netlist.own_netlist(sheet_of(example), project="blocks_demo", children=children_of(example))
    assert created == read
    nets = {net.name: {(n.ref, n.pin) for n in net.nodes} for net in created.nets}
    for path in ("ch0/R_EN", "ch1/R_EN"):
        assert (ref_of(example, path), "1") in nets["VIN"]
    names = {netname.replace("/", "{slash}") for netname in (n.name for n in example.design.circuit.nets)}
    assert names <= set(nets), "every net under its circuit name"
    assert "build.schematic-netlist-differs" not in {i.code for i in example.issues}, "the guard proved it"


def test_block_sheets_are_inside_the_grammar(example: BuildOutput) -> None:
    made = generated(example)
    assert sch_netlist.grammar_issues(made.sheet, children=made.children) == ()


def test_sheet_pin_without_a_label(example: BuildOutput) -> None:
    made = generated(example)
    child = made.children[CH0]
    stripped = dataclasses.replace(
        child,
        labels=tuple(
            label for label in child.labels if not (label.kind == "hierarchical" and label.name == "EN")
        ),
    )
    children = {**made.children, CH0: stripped}
    issues = sch_netlist.grammar_issues(made.sheet, children=children)
    (found,) = [i for i in issues if i.message.startswith("sheet:")]
    assert "ch0" in found.message and "EN" in found.message


def test_hierarchical_label_on_the_root_refused(example: BuildOutput) -> None:
    made = generated(example)
    label = next(label for label in made.children[CH0].labels if label.kind == "hierarchical")
    root = dataclasses.replace(made.sheet, labels=(*made.sheet.labels, label))
    issues = sch_netlist.grammar_issues(root, children=made.children)
    assert any(i.message.startswith("label-kind:") for i in issues)


@pytest.mark.parametrize("target", [9, 10])
def test_pins_read_back(target: int) -> None:
    output = catalog_build(blocks_example(), target)
    made = generated(output)
    read = sheet_of(output)
    assert root_name(output) == "blocks_demo.kicad_sch"
    for created, found in zip(made.sheet.sheets, read.sheets, strict=True):
        assert sch.opaque_sheet_pins(found) == tuple(
            (pin.name, pin.shape, pin.position, pin.rotation) for pin in created.pins
        )
    text = output.files[CH0].decode("utf-8")
    assert '(hierarchical_label "VIN"' in text and "(shape input)" in text

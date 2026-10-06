# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""2-pin parts snapped beside the IC pins they connect to (capability kicad-schematic, "Readable sheet
layout", and the cluster parts of "Deterministic sheet layout"; change c0070). Hermetic: no tool runs."""

from __future__ import annotations

import _gendesigns
import pytest
from _buildhelp import build, resolver
from _schbuild import snap_design

from fenolite.backends.kicad import sch_netlist, schlayout
from fenolite.backends.kicad.schgen import GeneratedSchematic, unit_box
from fenolite.backends.kicad.schlayout import (
    GRID,
    SNAP_REACH,
    Cluster,
    SymbolPlacement,
    UnitBox,
    layout_units,
    pin_point,
    snap_satellites,
)
from fenolite.core.coords import Point
from fenolite.lens.build import BuildOutput
from fenolite.model.schematic import SchematicSheet

Nets = dict[tuple[str, str], str]


def box(path: str, symbol: str = "Mini:Mini_R", text: int = 3, **labels: str) -> UnitBox:
    texts = {k.lstrip("p"): v for k, v in labels.items()}
    return unit_box(path, resolver(10).symbol(symbol), 1, texts, text)


def ic(**labels: str) -> UnitBox:
    return box("U1", "Mini:Mini_QFP32_IC", **labels)


def one_resistor() -> tuple[list[UnitBox], Nets]:
    units = [ic(p1="SIG", p10="GND"), box("R1", p1="SIG", p2="GND")]
    return units, {("U1", "1"): "SIG", ("U1", "10"): "GND", ("R1", "1"): "SIG", ("R1", "2"): "GND"}


def generated(output: BuildOutput) -> GeneratedSchematic:
    assert output.schematic is not None, [i.message for i in output.issues if i.severity == "error"]
    return output.schematic


def points(sheet: SchematicSheet, ref: str) -> dict[str, Point]:
    symbol = next(s for s in sheet.symbols if s.ref == ref)
    definition = next(d for d in sheet.lib_symbols if f"{d.library}:{d.name}" == symbol.lib_ref)
    return {
        pin.number: pin_point(symbol.position, pin.position, symbol.rotation // 1_000_000, symbol.mirror)
        for pin in definition.pins
    }


# -- snap_satellites


def test_resistor_beside_an_ic_pin() -> None:
    units, nets = one_resistor()
    (cluster,) = snap_satellites(units, nets)
    assert cluster.anchor == "U1" and [key for key, _ in cluster.satellites] == ["R1"]
    (wire,), (label,), ((_, place),) = cluster.wires, cluster.labels, cluster.satellites
    pin = next(p for p in units[0].pins if p.number == "1")
    start = pin_point(Point(0, 0), pin.at)
    assert (wire.anchor_pin, wire.near_pin, wire.start) == ("1", "1", start)
    assert wire.end == Point(start.x - SNAP_REACH, start.y), "5.08 mm along the pin's outward direction"
    near = next(p for p in units[1].pins if p.number == "1")
    assert pin_point(Point(place.x, place.y), near.at, place.rotation, place.mirror) == wire.end
    assert place.mirror == "" and (place.rotation, "") in schlayout.PROVED_FRAMES
    assert place.x % GRID == 0 and place.y % GRID == 0 and place.x < wire.end.x, "the body extends away"
    assert (label.satellite, label.pin, label.at) == ("R1", "1", wire.end)
    assert label.angle == 90, "pin 1 is above the centre line of U1: the label points up, across the wire"
    assert len(cluster.boxes) >= 4


def test_label_points_down_below_the_centre_line() -> None:
    units = [ic(p8="SIG"), box("R1", p1="SIG")]
    nets = {("U1", "8"): "SIG", ("R1", "1"): "SIG"}
    pin = next(p for p in units[0].pins if p.number == "8")
    (cluster,) = snap_satellites(units, nets)
    assert pin.at.y > 0, "pin 8 is above the centre in the library frame, where Y points up"
    assert cluster.labels[0].angle == 90
    low = next(p for p in units[0].pins if p.at.y < 0 and p.at.x == pin.at.x)
    units = [ic(**{f"p{low.number}": "SIG"}), box("R1", p1="SIG")]
    (cluster,) = snap_satellites(units, {("U1", low.number): "SIG", ("R1", "1"): "SIG"})
    assert cluster.labels[0].angle == 270


def test_one_satellite_per_pin() -> None:
    units, nets = one_resistor()
    units.append(box("R2", p1="SIG", p2="VIN"))
    nets |= {("R2", "1"): "SIG", ("R2", "2"): "VIN"}
    (cluster,) = snap_satellites(units, nets)
    assert [key for key, _ in cluster.satellites] == ["R1"], "pin 1 holds R1, and no pin is on VIN"
    assert [w.anchor_pin for w in cluster.wires] == ["1"]


def test_second_satellite_takes_a_free_pin_of_its_other_net() -> None:
    units = [ic(p1="SIG", p13="VIN"), box("R1", p1="SIG", p2="GND"), box("R2", p1="SIG", p2="VIN")]
    nets = {
        ("U1", "1"): "SIG",
        ("U1", "13"): "VIN",
        ("R1", "1"): "SIG",
        ("R1", "2"): "GND",
        ("R2", "1"): "SIG",
        ("R2", "2"): "VIN",
    }
    (cluster,) = snap_satellites(units, nets)
    assert [(w.satellite, w.anchor_pin, w.near_pin) for w in cluster.wires] == [
        ("R1", "1", "1"),
        ("R2", "13", "2"),
    ]


def test_overlap_skips_the_snap() -> None:
    """Resistors on two adjacent pins, 2.54 mm apart: the second would lie on the first."""
    units = [ic(p1="A", p2="B"), box("R1", p1="A"), box("R2", p1="B")]
    nets = {("U1", "1"): "A", ("U1", "2"): "B", ("R1", "1"): "A", ("R2", "1"): "B"}
    (cluster,) = snap_satellites(units, nets)
    assert [key for key, _ in cluster.satellites] == ["R1"], "R2 would lie on R1: it is not snapped"


def test_neighbour_without_a_net_does_not_block() -> None:
    units = [ic(p1="A"), box("R1", p1="A"), box("R2", p1="B")]
    nets = {("U1", "1"): "A", ("R1", "1"): "A", ("R2", "1"): "B"}
    (cluster,) = snap_satellites(units, nets)
    assert [key for key, _ in cluster.satellites] == ["R1"], "R2 is on no net of U1"


def test_what_is_no_satellite() -> None:
    led = box("D1", "Mini:Mini_LED", p1="A")
    assert schlayout.is_satellite(led, {("D1", "1"): "A"}, True)
    assert not schlayout.is_satellite(led, {("D1", "1"): "A"}, False), "one unit of several"
    assert not schlayout.is_satellite(led, {}, True), "on no net"
    assert not schlayout.is_satellite(led, {("D1", "1"): "A", ("D1", "2"): "A"}, True), "both pins on one net"
    assert not schlayout.is_satellite(ic(p1="A"), {("U1", "1"): "A"}, True)
    flag = UnitBox("#flag:A", led.pins, led.body, led.symbol)
    assert not schlayout.is_satellite(flag, {("#flag:A", "1"): "A"}, True)
    gate = unit_box("U2", resolver(10).symbol("Mini:Mini_DualGate"), 3, {"7": "A"})
    assert len(gate.pins) == 2 and not schlayout.is_satellite(gate, {("U2#3", "7"): "A"}, False)
    units = [gate, box("R1", p1="A")]
    assert snap_satellites(units, {("U2#3", "7"): "A", ("R1", "1"): "A"}) == (), "an anchor has three pins"


def test_led_is_snapped_too() -> None:
    units = [ic(p1="A"), box("D1", "Mini:Mini_LED", p2="A")]
    (cluster,) = snap_satellites(units, {("U1", "1"): "A", ("D1", "2"): "A"})
    assert cluster.wires[0].near_pin == "2"
    ((_, place),) = cluster.satellites
    near = next(p for p in units[1].pins if p.number == "2")
    assert pin_point(Point(place.x, place.y), near.at, place.rotation) == cluster.wires[0].end


def test_pure_and_deterministic() -> None:
    units, nets = one_resistor()
    assert snap_satellites(units, nets) == snap_satellites(list(units), dict(nets))
    assert snap_satellites(list(reversed(units)), nets) == snap_satellites(units, nets)


# -- placements


def snapped_place(anchor: SymbolPlacement, cluster: Cluster) -> SymbolPlacement:
    ((_, rel),) = cluster.satellites
    return SymbolPlacement(anchor.x + rel.x, anchor.y + rel.y, rel.rotation, rel.mirror)


def test_placed_satellite_keeps_its_wire_around_a_placed_anchor() -> None:
    units, nets = one_resistor()
    (free,) = snap_satellites(units, nets)
    anchor = SymbolPlacement(101_600_000, 76_200_000)
    there = snapped_place(anchor, free)
    (kept,) = snap_satellites(units, nets, placements={"U1": anchor, "R1": there})
    assert kept == free, "sync writes every unit: the build after it keeps the wire"
    elsewhere = SymbolPlacement(there.x + 2 * GRID, there.y, there.rotation)
    assert snap_satellites(units, nets, placements={"U1": anchor, "R1": elsewhere}) == ()
    turned = SymbolPlacement(there.x, there.y, (there.rotation + 180) % 360)
    assert snap_satellites(units, nets, placements={"U1": anchor, "R1": turned}) == ()


def test_placed_satellite_of_a_flowing_anchor_is_not_snapped() -> None:
    units, nets = one_resistor()
    assert snap_satellites(units, nets, placements={"R1": SymbolPlacement(25_400_000, 25_400_000)}) == ()


def test_placed_anchor_is_snapped_around() -> None:
    units, nets = one_resistor()
    (free,) = snap_satellites(units, nets)
    anchor = SymbolPlacement(101_600_000, 76_200_000)
    (cluster,) = snap_satellites(units, nets, placements={"U1": anchor})
    assert cluster == free
    found = layout_units(units, placements={"U1": anchor}, clusters=(cluster,))
    assert found.origins["U1"] == anchor and found.origins["R1"] == snapped_place(anchor, cluster)
    assert not [i for i in found.issues if i.code in ("build.symbol-overlap", "build.symbol-short")]
    quarter = SymbolPlacement(101_600_000, 76_200_000, 90)
    (turned,) = snap_satellites(units, nets, placements={"U1": quarter})
    assert turned.wires[0].start.x == turned.wires[0].end.x, "pin 1 of a turned U1 leaves it vertically"


def test_cell_of_another_placed_unit_blocks_around_a_placed_anchor() -> None:
    units, nets = one_resistor()
    units.append(UnitBox("U3", units[0].pins, units[0].body, units[0].symbol, 3))
    anchor = SymbolPlacement(101_600_000, 76_200_000)
    (free,) = snap_satellites(units[:2], nets)
    there = snapped_place(anchor, free)
    assert (
        snap_satellites(units, nets, placements={"U1": anchor, "U3": SymbolPlacement(there.x, there.y)}) == ()
    )


# -- clusters in the layout


def test_cluster_takes_the_place_of_its_anchor() -> None:
    units, nets = one_resistor()
    units.append(box("U2", "Mini:Mini_QFP32_IC"))
    (cluster,) = snap_satellites(units, nets)
    found = layout_units(units, clusters=(cluster,))
    u1, r1, u2 = (found.origins[key] for key in ("U1", "R1", "U2"))
    assert (r1.x, r1.y, r1.rotation) == (
        u1.x + cluster.satellites[0][1].x,
        u1.y + cluster.satellites[0][1].y,
        270,
    )
    cell, other = found.cells["U1"], found.cells["U2"]
    inner = found.cells["R1"]
    assert cell[0] <= inner[0] and cell[1] <= inner[1] and cell[2] >= inner[2] and cell[3] >= inner[3]
    assert cell[2] <= other[0] or cell[3] <= other[1], "the next cell starts after the cluster"
    assert u1.x % schlayout.ORIGIN_STEP == 0 and r1.x % GRID == 0 and r1.y % GRID == 0
    plain = layout_units(units)
    assert plain.origins["R1"].x < plain.origins["U1"].x and plain.origins["R1"].rotation == 0
    assert list(found.cells)[0] == "U1", "R1 left the order"


# -- generated sheets


def test_generated_resistor_on_an_ic_pin() -> None:
    made = generated(build(snap_design()))
    sheet = made.sheet
    (wire,) = sheet.wires
    u1, r1 = points(sheet, "U1"), points(sheet, "R1")
    assert (wire.start, wire.end) == (u1["1"], r1["1"]) and r1["1"] == Point(
        u1["1"].x - SNAP_REACH, u1["1"].y
    )
    labels = {(label.name, label.position) for label in sheet.labels}
    assert ("SIG", r1["1"]) in labels and ("GND", r1["2"]) in labels
    assert ("SIG", u1["1"]) not in labels, "the pair has one label"
    assert [label.name for label in sheet.labels].count("SIG") == 1
    assert made.satellites == 1 and r1["2"].x < r1["1"].x and r1["2"].y == r1["1"].y
    assert sch_netlist.grammar_issues(sheet) == ()
    found = sch_netlist.own_netlist(sheet, project="snap")
    (sig,) = [net for net in found.nets if net.name == "SIG"]
    assert [node.element for node in sig.nodes] == ["R1-1", "U1-1"]


def test_generated_second_resistor_flows_with_two_labels() -> None:
    made = generated(build(snap_design(second=True)))
    sheet = made.sheet
    assert made.satellites == len(sheet.wires) and made.satellites in (1, 2)
    r2 = points(sheet, "R2")
    labels = {(label.name, label.position) for label in sheet.labels}
    wired = {end for wire in sheet.wires for end in (wire.start, wire.end)}
    if r2["2"] not in wired:
        assert ("SIG", r2["1"]) in labels and ("VIN", r2["2"]) in labels
    assert sch_netlist.grammar_issues(sheet) == ()


def test_generated_adjacent_pins() -> None:
    made = generated(build(snap_design(adjacent=True)))
    sheet = made.sheet
    r2 = points(sheet, "R2")
    labels = {(label.name, label.position) for label in sheet.labels}
    assert ("SIG2", r2["1"]) in labels and ("GND", r2["2"]) in labels, "R2 flows with its two labels"
    assert all(r2["1"] not in (wire.start, wire.end) for wire in sheet.wires)
    assert sch_netlist.grammar_issues(sheet) == ()


def test_generated_placements_keep_or_drop_the_wire() -> None:
    free = generated(build(snap_design(second=True))).sheet
    place = {
        s.ref: SymbolPlacement(s.position.x, s.position.y, s.rotation // 1_000_000, s.mirror)
        for s in free.symbols
        if not s.ref.startswith("#")
    }
    same = generated(build(snap_design(second=True), symbol_placements=place)).sheet
    assert [(w.start, w.end) for w in same.wires] == [(w.start, w.end) for w in free.wires]
    assert same.labels[: -len(flags(same))] == free.labels[: -len(flags(free))]
    assert parts(same) == parts(free), "sync, then build: every part, wire and label stays"
    moved = dict(place)
    moved["R1"] = SymbolPlacement(place["R1"].x - 4 * GRID, place["R1"].y, place["R1"].rotation)
    sheet = generated(build(snap_design(second=True), symbol_placements=moved)).sheet
    r1 = points(sheet, "R1")
    assert all(r1["1"] not in (wire.start, wire.end) for wire in sheet.wires)
    assert {("SIG", r1["1"]), ("GND", r1["2"])} <= {(label.name, label.position) for label in sheet.labels}
    assert sch_netlist.grammar_issues(sheet) == ()


def flags(sheet: SchematicSheet) -> list[str]:
    return [s.ref for s in sheet.symbols if s.ref.startswith("#")]


def parts(sheet: SchematicSheet) -> list[tuple[str, Point, int]]:
    """The placed parts of a sheet. The power flags are left out: they have no entry in a placements
    file, so they flow on their own once every part is placed (as c0069 leaves them)."""
    return [(s.ref, s.position, s.rotation) for s in sheet.symbols if not s.ref.startswith("#")]


def test_wire_through_a_pin() -> None:
    """The snap wire run on through the near pin to a point beyond it is outside the grammar."""
    import dataclasses

    sheet = generated(build(snap_design())).sheet
    (wire,) = sheet.wires
    beyond = Point(wire.end.x - GRID, wire.end.y)
    longer = dataclasses.replace(sheet, wires=(dataclasses.replace(wire, end=beyond),))
    reasons = [issue.message.split(":", 1)[0] for issue in sch_netlist.grammar_issues(longer)]
    assert {"wire-end", "wire-touch"} <= set(reasons), reasons


def test_grid_layout_has_no_satellite() -> None:
    made = generated(build(snap_design(), schematic_layout="grid"))
    assert made.satellites == 0 and not made.sheet.wires
    assert [label.name for label in made.sheet.labels].count("SIG") == 2


@pytest.mark.parametrize("target", [9, 10])
def test_deterministic(target: int) -> None:
    """The sheets of the 25 generated designs with modules, written twice: byte-identical."""
    satellites = sheets = 0
    for index in range(_gendesigns.COUNT):
        first = build(_gendesigns.design(_gendesigns.MODULE_SEED, index, modules=True), target)
        second = build(_gendesigns.design(_gendesigns.MODULE_SEED, index, modules=True), target)
        assert first.files and first.files == second.files, index
        made = generated(first)
        satellites += made.satellites
        sheets += len(made.children)
        for sheet in (made.sheet, *made.children.values()):
            for symbol in sheet.symbols:
                assert symbol.position.x % GRID == 0 and symbol.position.y % GRID == 0
    assert satellites >= 5 and sheets >= 10, (satellites, sheets)

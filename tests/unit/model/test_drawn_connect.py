# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The connectivity of a drawn schematic (capability drawn-schematic, "Drawn connectivity resolver", "Drawn
connectivity rules", "Drawn bus connectivity" and "Drawn net names"; change c0276)."""

from __future__ import annotations

import ast
import dataclasses
import random
import subprocess
from pathlib import Path

import _drawn
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import fenolite.model.drawn_connect as drawn_connect
from fenolite.core.coords import Point
from fenolite.model.drawn import DrawnJunction, DrawnLabel, DrawnSchematic, DrawnSheet, DrawnSymbol
from fenolite.model.drawn_connect import DrawnNetlist, PinPoint, expand, resolve

P = Point


def _groups(netlist: DrawnNetlist) -> set[frozenset[tuple[str, str]]]:
    return {frozenset(net.members) for net in netlist.nets} | {frozenset({e}) for e in netlist.open}


def _group(netlist: DrawnNetlist, element: tuple[str, str]) -> frozenset[tuple[str, str]]:
    return next(g for g in _groups(netlist) if element in g)


def _sheet(
    *, junction: bool = False
) -> tuple[DrawnSchematic, dict[tuple[str, str, int], tuple[PinPoint, ...]]]:
    """Wire A ends inside wire B (a T); wire C crosses B, with a junction on the crossing when asked."""
    ends = {"A": P(50, -50), "B1": P(0, 0), "B2": P(100, 0), "C1": P(70, -50), "C2": P(70, 50)}
    symbols = tuple(DrawnSymbol(part, 1, at) for part, at in ends.items())
    sheet = DrawnSheet(
        "root",
        symbols=symbols,
        wires=((P(0, 0), P(100, 0)), (P(50, -50), P(50, 0)), (P(70, -50), P(70, 50))),
        junctions=(DrawnJunction(P(70, 0)),) if junction else (),
    )
    pins = {("root", "symbol", k): (PinPoint("1", s.at),) for k, s in enumerate(symbols)}
    return DrawnSchematic("root", (sheet,)), pins


def test_t_joint_and_crossing() -> None:
    """Scenario "T joint and crossing": without a junction, neither a T nor a crossing joins (measured with
    ``kicad-cli`` 9.0.9 and 10.0.6: a wire end inside another wire stays apart)."""
    drawn, pins = _sheet()
    netlist = resolve(drawn, pins)
    assert _group(netlist, ("B1", "1")) == {("B1", "1"), ("B2", "1")}
    assert _group(netlist, ("A", "1")) == {("A", "1")}
    assert _group(netlist, ("C1", "1")) == {("C1", "1"), ("C2", "1")}


def test_junction_on_a_t() -> None:
    drawn, pins = _sheet()
    sheet = dataclasses.replace(drawn.sheets[0], junctions=(DrawnJunction(P(50, 0)),))
    netlist = resolve(DrawnSchematic("root", (sheet,)), pins)
    assert _group(netlist, ("A", "1")) == {("A", "1"), ("B1", "1"), ("B2", "1")}


def test_junction_on_a_crossing() -> None:
    """Scenario "Junction on a crossing"."""
    drawn, pins = _sheet(junction=True)
    sheet = dataclasses.replace(
        drawn.sheets[0], junctions=(*drawn.sheets[0].junctions, DrawnJunction(P(50, 0)))
    )
    netlist = resolve(DrawnSchematic("root", (sheet,)), pins)
    assert _group(netlist, ("A", "1")) == {("A", "1"), ("B1", "1"), ("B2", "1"), ("C1", "1"), ("C2", "1")}
    only_crossing = resolve(drawn, pins)
    assert _group(only_crossing, ("C1", "1")) == {("B1", "1"), ("B2", "1"), ("C1", "1"), ("C2", "1")}


def test_hermetic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Hermetic": no tool, no file, no float."""
    pins = _drawn.pins(_drawn.drawn("full"), "full")

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the resolver runs no tool")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    netlist = resolve(_drawn.drawn("full"), pins)
    assert len(netlist.nets) == 6
    tree = ast.parse(Path(drawn_connect.__file__).read_text(encoding="utf-8"))
    floats = [
        node
        for node in ast.walk(tree)
        if (isinstance(node, ast.Constant) and isinstance(node.value, float))
        or (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float")
    ]
    assert floats == []


def test_hierarchical_pin() -> None:
    """Scenario "Hierarchical pin"."""
    netlist = _drawn.netlist("hier")
    assert _group(netlist, ("U1", "3")) == {("U1", "3"), ("child/R2", "1")}


def test_local_labels_stay_on_their_instance() -> None:
    """Scenario "Local labels stay on their instance"."""
    netlist = _drawn.netlist("repeat")
    assert _group(netlist, ("ch0/R1", "2")) == {("ch0/R1", "2"), ("ch0/R2", "1")}
    assert _group(netlist, ("ch1/R1", "2")) == {("ch1/R1", "2"), ("ch1/R2", "1")}
    # the power symbol is global: one net over both instances
    assert _group(netlist, ("ch0/R1", "1")) == {("ch0/R1", "1"), ("ch1/R1", "1")}


def test_bus_data_through_a_sheet() -> None:
    """Scenario "Data bus through a sheet"."""
    netlist = _drawn.netlist("bus")
    for k in range(4):
        assert _group(netlist, ("U1", str(17 + k))) == {("U1", str(17 + k)), (f"child/R{10 + k}", "1")}
    assert not [i for i in netlist.issues if i.code == "drawn.bus-member-unknown"]


def test_bus_entry_without_a_label() -> None:
    """Scenario "Entry without a label"."""
    value = _drawn.drawn("bus")
    child = value.sheets[1]
    labels = tuple(label for label in child.labels if label.text != "D2")
    value = DrawnSchematic(value.root, (value.sheets[0], dataclasses.replace(child, labels=labels)))
    netlist = _drawn.netlist("bus", value)
    assert _group(netlist, ("child/R12", "1")) == {("child/R12", "1")}
    unknown = [i for i in netlist.issues if i.code == "drawn.bus-member-unknown"]
    assert len(unknown) == 1 and "D2" in unknown[0].message


def test_names_in_a_child_sheet() -> None:
    """Scenario "Names in a child sheet"."""
    netlist = _drawn.netlist("hier")
    names = {net.name for net in netlist.nets}
    assert "/child/FB" in names and "VCC" in names


def test_two_global_labels_on_one_net() -> None:
    """Scenario "Two global labels on one net": the text that sorts first wins."""
    drawn, pins = _sheet()
    sheet = drawn.sheets[0]
    labels = (
        DrawnLabel("global", "VIN", P(0, 0), 0, "input"),
        DrawnLabel("global", "IN_PWR", P(100, 0), 0, "input"),
    )
    netlist = resolve(DrawnSchematic("root", (dataclasses.replace(sheet, labels=labels),)), pins)
    net = next(n for n in netlist.nets if ("B1", "1") in n.members)
    assert net.name == "IN_PWR" and net.labels == ("IN_PWR", "VIN")


def test_local_name_and_unnamed() -> None:
    drawn, pins = _sheet()
    sheet = dataclasses.replace(drawn.sheets[0], labels=(DrawnLabel("local", "N", P(0, 0)),))
    netlist = resolve(DrawnSchematic("root", (sheet,)), pins)
    assert {n.name for n in netlist.nets} == {"/N", ""}


def test_dangling_end_and_unconnected_label() -> None:
    drawn, pins = _sheet()
    sheet = dataclasses.replace(
        drawn.sheets[0],
        wires=(*drawn.sheets[0].wires, (P(200, 0), P(300, 0))),
        labels=(DrawnLabel("local", "LOST", P(500, 500)),),
    )
    netlist = resolve(DrawnSchematic("root", (sheet,)), pins)
    codes = sorted(i.code for i in netlist.issues)
    assert codes == ["drawn.dangling", "drawn.dangling", "drawn.label-unconnected"]


def test_sheet_pins_without_labels() -> None:
    value = _drawn.drawn("hier")
    child = dataclasses.replace(value.sheets[1], labels=value.sheets[1].labels[1:])
    netlist = _drawn.netlist("hier", DrawnSchematic(value.root, (value.sheets[0], child)))
    unmatched = [i for i in netlist.issues if i.code == "drawn.sheet-pin-unmatched"]
    assert len(unmatched) == 1 and "IN" in unmatched[0].message


def test_bus_names() -> None:
    assert expand("D[0..3]", {}) == ("D0", "D1", "D2", "D3")
    assert expand("A[2..0]", {}) == ("A2", "A1", "A0")
    assert expand("{SDA SCL}", {}) == ("SDA", "SCL")
    assert expand("I2C{SDA SCL}", {}) == ("I2C.SDA", "I2C.SCL")
    assert expand("BUS", {"BUS": ("X[0..1]", "Y")}) == ("X0", "X1", "Y")
    assert expand("{BUS Z}", {"BUS": ("Y",)}) == ("Y", "Z")
    assert expand("PLAIN", {}) is None


def _split(drawn: DrawnSchematic, seed: int) -> DrawnSchematic:
    """``drawn`` with the items of each sheet shuffled and each axis-aligned segment split at its middle."""
    rng = random.Random(seed)
    sheets = []
    for sheet in drawn.sheets:
        wires: list[tuple[Point, ...]] = []
        for polyline in sheet.wires:
            for start, end in zip(polyline, polyline[1:], strict=False):
                middle = Point((start.x + end.x) // 2, (start.y + end.y) // 2)
                straight = (start.x == end.x or start.y == end.y) and middle not in (start, end)
                on_grid = (start.x + end.x) % 2 == 0 and (start.y + end.y) % 2 == 0
                if straight and on_grid and rng.random() < 0.5:
                    wires += [(start, middle), (middle, end)]
                else:
                    wires.append((start, end))
        rng.shuffle(wires)
        labels = list(sheet.labels)
        rng.shuffle(labels)
        junctions = list(sheet.junctions)
        rng.shuffle(junctions)
        sheets.append(
            dataclasses.replace(sheet, wires=tuple(wires), labels=tuple(labels), junctions=tuple(junctions))
        )
    return DrawnSchematic(drawn.root, tuple(sheets))


@settings(max_examples=25, deadline=None)
@given(st.sampled_from([*_drawn.NAMES, "example"]), st.integers(0, 10**6))
def test_order_and_splitting_do_not_matter(name: str, seed: int) -> None:
    """Scenario "Order and splitting do not matter"."""
    value = _drawn.drawn(name)
    pins = _drawn.pins(value, name)
    first = resolve(value, pins)
    again = resolve(_split(value, seed), pins)
    assert {(n.name, n.members) for n in first.nets} == {(n.name, n.members) for n in again.nets}
    assert first.open == again.open


def test_a_pin_inside_a_wire_stays_open() -> None:
    """A pin joins a wire at the wire's end only (``H-K-SCH-WIRE-END``, measured on 9.0.9 and 10.0.6); a
    junction on the pin's point joins it."""
    drawn, pins = _sheet()
    sheet = drawn.sheets[0]
    middle = DrawnSymbol("M", 1, P(30, 0))
    pins = {**pins, ("root", "symbol", len(sheet.symbols)): (PinPoint("1", P(30, 0)),)}
    alone = dataclasses.replace(sheet, symbols=(*sheet.symbols, middle))
    assert ("M", "1") in resolve(DrawnSchematic("root", (alone,)), pins).open
    joined = dataclasses.replace(alone, junctions=(DrawnJunction(P(30, 0)),))
    assert _group(resolve(DrawnSchematic("root", (joined,)), pins), ("M", "1")) >= {("M", "1"), ("B1", "1")}


def test_label_on_a_sheet_pin() -> None:
    """A label on a sheet pin's point joins the pin without a wire (the generated block sheets of c0269)."""
    value = _drawn.drawn("hier")
    root = value.sheets[0]
    (start, end), *_ = root.segments()
    labels = (
        *root.labels,
        DrawnLabel("local", "LINK", start),
        DrawnLabel("local", "LINK", end),
    )
    value = DrawnSchematic(
        value.root, (dataclasses.replace(root, wires=(), labels=labels), *value.sheets[1:])
    )
    netlist = _drawn.netlist("hier", value)
    assert _group(netlist, ("U1", "3")) == {("U1", "3"), ("child/R2", "1")}
    assert not [i for i in netlist.issues if i.code == "drawn.label-unconnected"]

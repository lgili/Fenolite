# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The per-pin differences of a drawing with its code, and a bus label that touches nothing (change c0470)."""

from __future__ import annotations

import dataclasses

from fenolite.core.coords import Point
from fenolite.model.circuit import Circuit, Component, Net, Pin, PinRef
from fenolite.model.drawn import DrawnLabel, DrawnSchematic, DrawnSheet, DrawnSymbol
from fenolite.model.drawn_connect import PinPoint, compare, pin_differences, resolve

P = Point
_REFS = ("A", "B", "C")


def _drawing() -> tuple[DrawnSchematic, dict[tuple[str, str, int], tuple[PinPoint, ...]]]:
    """A and B on one wire, C alone."""
    symbols = (DrawnSymbol("A", 1, P(0, 0)), DrawnSymbol("B", 1, P(100, 0)), DrawnSymbol("C", 1, P(0, 500)))
    sheet = DrawnSheet("root", symbols=symbols, wires=((P(0, 0), P(100, 0)),))
    pins = {("root", "symbol", k): (PinPoint("1", s.at),) for k, s in enumerate(symbols)}
    return DrawnSchematic("root", (sheet,)), pins


def _circuit(*members: str) -> Circuit:
    parts = tuple(Component(id=f"c{r}", ref=r, pins=(Pin(id=f"p{r}", number="1"),)) for r in _REFS)
    return Circuit(
        components=parts, nets=(Net(id="n", name="N", members=tuple(PinRef(f"c{r}", "1") for r in members)),)
    )


def test_each_differing_pin_is_named_and_compare_summarises_them() -> None:
    drawn, pins = _drawing()
    netlist = resolve(drawn, pins)
    assert pin_differences(netlist, _circuit("A", "B")) == []
    found = pin_differences(netlist, _circuit("A", "B", "C"))
    assert [i.where for i in found] == ["A-1", "B-1", "C-1"]
    summary = compare(netlist, _circuit("A", "B", "C"))[0]
    assert summary.where == "A-1" and summary.message.endswith(f"{found[0].message} (and 2 more)")


def test_a_bus_label_that_touches_nothing_is_a_bus_of_its_own() -> None:
    """KiCad takes a label for a bus by its text (H-K-DRAWN-BUS): a lone ``CAN{TX RX}`` is no dangling
    label, a lone scalar label still is."""
    drawn, pins = _drawing()
    labels = (DrawnLabel("local", "CAN{TX RX}", P(900, 900)), DrawnLabel("local", "LOST", P(700, 700)))
    sheet = dataclasses.replace(drawn.sheets[0], labels=labels)
    netlist = resolve(DrawnSchematic("root", (sheet,)), pins)
    lost = [i.where for i in netlist.issues if i.code == "drawn.label-unconnected"]
    assert lost == ["root:LOST"]

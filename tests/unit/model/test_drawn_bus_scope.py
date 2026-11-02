# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bus-only contacts do not turn a hierarchical bus label into a scalar (c0320)."""

from __future__ import annotations

from dataclasses import replace

import _bus_scope
import _drawn
import pytest

from fenolite.core.coords import Point
from fenolite.model.drawn import (
    DrawnJunction,
    DrawnLabel,
    DrawnLabelKind,
    DrawnSchematic,
    DrawnSheet,
    DrawnSymbol,
)
from fenolite.model.drawn_connect import PinPoint, expand, resolve


@pytest.mark.parametrize("form", _bus_scope.FORMS)
@pytest.mark.parametrize("contact", _bus_scope.CONTACTS)
def test_hierarchical_bus_label_keeps_its_members_at_bus_contacts(
    form: _bus_scope.Form, contact: _bus_scope.Contact
) -> None:
    drawing = _bus_scope.value(form, contact)
    netlist = resolve(drawing, _drawn.pins(drawing, "bus"))
    for number in range(4):
        net = netlist.net_of(("U1", str(17 + number)))
        assert net is not None and (f"child/R{10 + number}", "1") in net.members
    assert not [issue for issue in netlist.issues if issue.code == "drawn.bus-member-unknown"]


@pytest.mark.parametrize("form", _bus_scope.FORMS)
def test_a_bus_contact_does_not_guess_an_unlabelled_member(form: _bus_scope.Form) -> None:
    drawing = _bus_scope.value(form, "entry")
    child = drawing.sheets[1]
    missing = "CHANNEL.D2" if form in ("group", "overbar") else "D2"
    child = replace(child, labels=tuple(label for label in child.labels if label.text != missing))
    drawing = replace(drawing, sheets=(drawing.sheets[0], child))
    netlist = resolve(drawing, _drawn.pins(drawing, "bus"))
    assert ("child/R12", "1") in netlist.open
    assert any(
        issue.code == "drawn.bus-member-unknown" and missing in issue.message for issue in netlist.issues
    )


def test_overbar_spans_are_literal_member_names() -> None:
    assert expand("~{READY}", {}) is None
    assert expand("CHANNEL.~{READY}", {}) is None
    assert expand("CHANNEL{~{READY} D[1..3]}", {}) == (
        "CHANNEL.~{READY}",
        "CHANNEL.D1",
        "CHANNEL.D2",
        "CHANNEL.D3",
    )


@pytest.mark.parametrize("form", ["vector", "group", "vector-group"])
@pytest.mark.parametrize("reverse", [False, True])
def test_generic_qualified_members_are_not_canonicalised(form: str, reverse: bool) -> None:
    drawing = _bus_scope.renamed(form, reverse=reverse, connected=True)
    netlist = resolve(drawing, _drawn.pins(drawing, "bus"))
    for number in range(4):
        net = netlist.net_of(("U1", str(17 + number)))
        assert net is not None and not any(path.startswith("child/") for path, _pin in net.members)


@pytest.mark.parametrize("kind", ["hierarchical", "global"])
def test_generic_scalar_label_scopes_keep_their_existing_meaning(kind: DrawnLabelKind) -> None:
    drawing = _bus_scope.scalar_labels(kind, equal=True)
    netlist = resolve(drawing, _drawn.pins(drawing, "bus"))
    net = netlist.net_of(("child/R10", "1"))
    assert net is not None and ("child/R11", "1") not in net.members
    assert ("U1", "17") not in net.members


@pytest.mark.parametrize("contact", ["wire", "pin"])
def test_actual_wire_or_pin_contacts_keep_priority_over_a_bus(contact: str) -> None:
    anchor = Point(0, 0)
    pin = Point(10, 0) if contact == "wire" else anchor
    sheet = DrawnSheet(
        "root", symbols=(DrawnSymbol("R1", 1, pin),),
        wires=((anchor, pin),) if contact == "wire" else (),
        buses=((anchor, Point(0, 20)),), junctions=(DrawnJunction(anchor),),
        labels=(DrawnLabel("local", "DATA[0..1]", anchor),),
    )  # fmt: skip
    pins = {("root", "symbol", 0): (PinPoint("1", pin),)}
    netlist = resolve(DrawnSchematic("root", (sheet,)), pins)
    net = netlist.net_of(("R1", "1"))
    assert net is not None and net.labels == ("DATA[0..1]",)
    assert not any(issue.code == "drawn.bus-member-unknown" for issue in netlist.issues)

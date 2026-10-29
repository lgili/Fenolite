# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The governing clearance of a pour (change c0215; capability altium-pour, "Pour engine"; input I2 of
``docs/formats/altium/pcb-pour.md``): the engine's ``Clearances`` resolves what
``checks.clearance.ClearanceResolver`` resolves for an Altium reading, and an unread Clearance record that
could govern leaves the pair undetermined."""

from __future__ import annotations

import importlib.util

import pytest
from _altium_pour import Board, clearance, mm, pad, track, via, zone

from fenolite.backends.altium import pcbdoc
from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.pour import (
    Clearances,
    LayerObjects,
    PourReading,
    rule_subject,
)
from fenolite.checks.clearance import ClearanceResolver
from fenolite.core.units import u_to_nm
from fenolite.model.rules import Rule, Selector

pytestmark = pytest.mark.skipif(importlib.util.find_spec("pyclipper") is None, reason="needs the geo extra")


def _unit(value: int) -> int:
    """``value`` as a written length reads back: rounded to a whole file unit of 2.54 nm."""
    return u_to_nm(rec.to_units(value))


def _board(*rules: Rule) -> Board:
    return Board(
        zones=(zone("z1", "GND"), zone("z2", "VIN", layer="B.Cu")),
        pads=(
            pad("p1", "VIN", 10, 10, shape="circle"),
            pad("p2", "SIG", 20, 10),
            pad("p3", "GND", 30, 10, kind="thru_hole", shape="circle", size=(1.6, 1.6), drill=0.8),
        ),
        tracks=(track("t1", "SIG", (5, 20), (15, 20)),),
        vias=(via("v1", "VIN", 25, 20),),
        rules=rules,
    )


def _pairs(reading: PourReading) -> list[tuple[int | str, int | str | None]]:
    """For every polygon and every object of its layer: the engine's value and the copper check's."""
    from fenolite.backends.altium.pour import polygons_of

    rules = Clearances(reading)
    objects = LayerObjects(reading, 3175)
    resolver = ClearanceResolver(reading.design, rules_over_classes=True, floor_over_rules=False)
    nets = {net.name: net.id for net in reading.design.circuit.nets}
    found: list[tuple[int | str, int | str | None]] = []
    for polygon in polygons_of(reading):
        me = rule_subject(polygon.layer, "zone", polygon.net, objects.netclass.get(polygon.net, "Default"))
        mine = resolver.subject("zone", nets.get(polygon.net or ""), ref=None, layer=polygon.layer)
        for item in objects.by_layer[polygon.layer]:
            if item.kind in ("hole", "keepout"):
                continue
            theirs = resolver.subject(item.kind, nets.get(item.net or ""), ref=item.ref, layer=polygon.layer)
            value = rules.clearance(
                me, rule_subject(polygon.layer, item.kind, item.net, item.netclass, item.ref)
            )
            found.append((value, resolver.resolve(mine, theirs).value))
    return found


def test_values_equal_the_copper_check() -> None:
    """For a board-wide rule, a net rule over it and a rule between two nets, every pair of a polygon and
    an object gets the value the copper check gets."""
    vin = Rule(
        id="r_vin", name="vin", kind="clearance", selector_a=Selector("net", "VIN"), min=mm(0.4), priority=1
    )
    pair = Rule(id="r_pair", name="pair", kind="clearance", selector_a=Selector("net", "GND"),
                selector_b=Selector("net", "SIG"), min=mm(0.35), priority=2)  # fmt: skip
    pairs = _pairs(_board(clearance(0.2), vin, pair).base())
    assert pairs and all(mine == theirs for mine, theirs in pairs), pairs
    assert {mine for mine, _ in pairs} >= {_unit(mm(0.4)), _unit(mm(0.35))}


def test_edge_clearance() -> None:
    """The governing Board Outline Clearance of a polygon (I17); 0 without one."""
    edge = Rule(id="r_edge", name="edge", kind="edge_clearance", selector_a=Selector("all"), min=mm(0.5))
    reading = _board(clearance(0.2), edge).base()
    rules = Clearances(reading)
    assert rules.edge(rule_subject("F.Cu", "zone", "GND", "Default")) == _unit(mm(0.5))
    assert Clearances(_board(clearance(0.2)).base()).edge(rule_subject("F.Cu", "zone", "GND", "Default")) == 0


def test_an_unread_record_before_the_governing_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Clearance record of a polygon query (not in the closed scope grammar) at priority 1 makes every
    pair with that polygon's copper undetermined (``rule-scope``), and no pair of another polygon's;
    behind the governing rule it changes nothing."""
    original = pcbdoc.rule_records

    def with_polygon_rule(priority: int) -> None:
        def records(spec: pcbdoc.PcbDocSpec, filename: str) -> list[bytes]:
            keys = [
                ("GAP", "10mil"),
                ("GENERICCLEARANCE", "10mil"),
                ("IGNOREPADTOPADCLEARANCEINFOOTPRINT", "FALSE"),
                ("OBJECTCLEARANCES", ""),
            ]
            extra = pcbdoc._rule(  # pyright: ignore[reportPrivateUsage]
                0, "Clearance", "polygon", "InPolygon('GND_L01_P000')", priority, keys, filename
            )
            return [*original(spec, filename), extra]

        monkeypatch.setattr(pcbdoc, "rule_records", records)

    gnd, vin = rule_subject("F.Cu", "zone", "GND", "Default"), rule_subject("F.Cu", "pad", "VIN", "Default")
    with_polygon_rule(1)
    rules = Clearances(_board(clearance(0.2)).base())
    assert rules.clearance(gnd, vin, polygons=("GND_L01_P000",)) == "rule-scope"
    assert rules.clearance(gnd, vin, polygons=("VIN_L02_P001",)) == _unit(mm(0.2))  # another polygon
    with_polygon_rule(9)
    rules = Clearances(_board(clearance(0.2)).base())
    assert rules.clearance(gnd, vin, polygons=("GND_L01_P000",)) == _unit(mm(0.2))

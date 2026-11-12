# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The governing clearance of a pour (change c0215; capability altium-pour, "Pour engine"; input I2 of
``docs/formats/altium/pcb-pour.md``): the engine's ``Clearances`` resolves what
``checks.clearance.ClearanceResolver`` resolves for an Altium reading, and an unread Clearance record that
could govern leaves the pair undetermined."""

from __future__ import annotations

import importlib.util
from types import SimpleNamespace

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
    """The governing Board Outline Clearance of a polygon (I17). A document without a Board Outline
    Clearance record keeps the governing Clearance to its board cut-outs (S-2311)."""
    edge = Rule(id="r_edge", name="edge", kind="edge_clearance", selector_a=Selector("all"), min=mm(0.5))
    reading = _board(clearance(0.2), edge).base()
    rules = Clearances(reading)
    assert rules.edge(rule_subject("F.Cu", "zone", "GND", "Default")) == _unit(mm(0.5))
    without = Clearances(_board(clearance(0.2)).base())
    assert without.edge(rule_subject("F.Cu", "zone", "GND", "Default")) == _unit(mm(0.2))


def test_edge_reach_is_the_corner_of_altiums_polygon() -> None:
    """``edge_reach``: the clearance over cos(π/n) for the fewest sides n, a multiple of 8, whose corners
    stand at most 0.5 mil outside the circle, as Altium's repour keeps its pour from the board's edge on the
    public rows (S-2224): 162.35 µm for 150 µm, 305.86 µm for 300 µm, 137.47 µm for 127 µm."""
    from fenolite.backends.altium.pour import EDGE_SAG, edge_reach

    assert edge_reach(0) == 0
    assert abs(edge_reach(150_000) - 162_346) <= 15  # an octagon: 12 359 nm over the circle
    assert abs(edge_reach(299_999) - 305_864) <= 15  # 16 sides: 8 would stand 24 718 nm over it
    assert abs(edge_reach(127_000) - 137_465) <= 15
    for value in (1_000, 154_000, 155_000, 648_000, 649_000, 2_000_000):
        assert 0 < edge_reach(value) - value <= EDGE_SAG, value


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


def test_a_matrix_whose_twins_differ_is_read_for_the_polygon(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Clearance matrix that gives an arc and a track, or a fill and a region, different clearances is
    refused by the import (``matrix-kind``); the pour reads it with each twin as the kind that stands for it
    and takes the polygon's clearance to each of them from its own cell (task 4.3, rows -06 and -08)."""
    from fenolite.backends.altium.pour import fine_kind

    original = pcbdoc.rule_records
    # counts of 0.0001 mil: Arc-Poly 0, Track-Poly 10 mil, Fill-Poly 15 mil, Region-Poly 4 mil
    matrix = ";".join(
        f"ClearanceObj_{kind}-ClearanceObj_Poly:{count}"
        for kind, count in (("Arc", 0), ("Track", 100_000), ("Fill", 150_000), ("Region", 40_000))
    )

    def records(spec: pcbdoc.PcbDocSpec, filename: str) -> list[bytes]:
        keys = [
            ("GAP", "8mil"),
            ("GENERICCLEARANCE", "8mil"),
            ("IGNOREPADTOPADCLEARANCEINFOOTPRINT", "FALSE"),
            ("OBJECTCLEARANCES", matrix),
        ]
        extra = pcbdoc._rule(0, "Clearance", "matrix", "All", 1, keys, filename)  # pyright: ignore[reportPrivateUsage]
        return [*original(spec, filename), extra]

    monkeypatch.setattr(pcbdoc, "rule_records", records)
    reading = _board(clearance(0.2)).base()
    rules = Clearances(reading)
    gnd, sig = rule_subject("F.Cu", "zone", "GND", "Default"), rule_subject("F.Cu", "track", "SIG", "Default")
    polygons = ("GND_L01_P000",)
    mil = 25_400
    assert rules.clearance(gnd, sig, polygons=polygons, fine="Arc") == 0
    assert rules.clearance(gnd, sig, polygons=polygons, fine="Track") == 10 * mil
    assert rules.clearance(gnd, sig, polygons=polygons, fine="Fill") == 15 * mil
    assert rules.clearance(gnd, sig, polygons=polygons, fine="Region") == 4 * mil
    assert rules.largest >= 15 * mil
    objects = LayerObjects(reading, 3175)
    (track_item,) = [item for item in objects.by_layer["F.Cu"] if item.kind == "track"]
    assert fine_kind(track_item) == "Track"


def test_an_edge_matrix_whose_edges_differ_is_read_for_the_pour() -> None:
    """A Board Outline Clearance matrix that gives a polygon one value from the outline and the generic
    value from a cut-out is refused by the import (``matrix-kind``); the pour reads it with the outline's
    value for both edges, as it judges both as the board's edge (row -06)."""
    from fenolite.backends.altium.pour import pour_rule_fields
    from fenolite.backends.altium.read.rules import matrix_problem

    matrix = "ClearanceObj_Poly-ClearanceObj_OutlineEdge:196850"
    assert matrix_problem(matrix, "11.811mil", edges=True)
    fields = (("RULEKIND", "BoardOutlineClearance"), ("GAP", "11.811mil"), ("OBJECTCLEARANCES", matrix))

    record = SimpleNamespace(record=dict(fields), fields=fields)  # what the pour reads of a rule record
    read_fields, extra, fine = pour_rule_fields([record])  # pyright: ignore[reportArgumentType]
    judged = dict(read_fields[0])["OBJECTCLEARANCES"]
    assert extra == {0} and not fine
    assert "ClearanceObj_Poly-ClearanceObj_CutoutEdge:196850" in judged
    assert not matrix_problem(judged, "11.811mil", edges=True)


@pytest.mark.parametrize("layer", ["Keep-Out Layer", "KeepOutLayer"])
def test_the_default_keep_out_clearance_governs_only_keep_outs(
    monkeypatch: pytest.MonkeyPatch, layer: str
) -> None:
    """Altium's default keep-out clearance (a scope of keep-out and cut-out terms against ``All``) at
    priority 1 is refused by the import for its scope; the pour reads it as the clearance between a keep-out
    and any object, so it refuses no other pair (task 5.2, flow B). The layer is named with and without
    spaces, as Altium writes it either way."""
    original = pcbdoc.rule_records
    scope = f"OnLayer('{layer}') or IsKeepOut or IsBoardCutoutRegion"

    def records(spec: pcbdoc.PcbDocSpec, filename: str) -> list[bytes]:
        keys = [
            ("GAP", "10mil"),
            ("GENERICCLEARANCE", "10mil"),
            ("IGNOREPADTOPADCLEARANCEINFOOTPRINT", "FALSE"),
            ("OBJECTCLEARANCES", ""),
        ]
        extra = pcbdoc._rule(0, "Clearance", "keepout", scope, 1, keys, filename)  # pyright: ignore[reportPrivateUsage]
        return [*original(spec, filename), extra]

    monkeypatch.setattr(pcbdoc, "rule_records", records)
    rules = Clearances(_board(clearance(0.2)).base())
    gnd = rule_subject("F.Cu", "zone", "GND", "Default")
    vin = rule_subject("F.Cu", "pad", "VIN", "Default")
    keepout = rule_subject("F.Cu", "keepout", None, "Default")
    assert rules.clearance(gnd, vin, polygons=("GND_L01_P000",)) == _unit(mm(0.2))
    assert rules.clearance(gnd, keepout, polygons=("GND_L01_P000",)) == 10 * 25_400
    _, result = _board(clearance(0.2)).pour()
    assert result.polygons and all(polygon.poured for polygon in result.polygons)

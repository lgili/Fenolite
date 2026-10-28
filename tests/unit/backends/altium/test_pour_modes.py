# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The two pour modes of the PCB writer (change c0215; capability altium-pcb-writer, "Polygon pour modes",
"Polygon Connect Style records" and the self-check of altium-pour, "Refusal of a pour")."""

from __future__ import annotations

import importlib.util

import pytest
from _altium_pour import FILENAME, Board, clearance, pad, track, via, zone

from fenolite.backends.altium import pcbdoc
from fenolite.backends.altium.connectstyle import read_connect_styles
from fenolite.backends.altium.pour import PourResult, read_pour
from fenolite.backends.altium.read.cfb import open_compound
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.geometry.errors import BackendUnavailable
from fenolite.model.board import ZoneSettings

GEO = importlib.util.find_spec("pyclipper") is not None
needs_geo = pytest.mark.skipif(not GEO, reason="a computed pour needs the geo extra")

BOARD = Board(
    zones=(
        zone("z1", "GND"),
        zone("z2", "GND", layer="B.Cu", settings=ZoneSettings(connection="solid")),
        zone("z3", "VIN", layer="B.Cu", priority=1, settings=ZoneSettings(connection="solid")),
    ),
    pads=(pad("p1", "VIN", 10, 10, shape="circle"), pad("p2", "GND", 20, 10)),
    tracks=(track("t1", "VIN", (5, 20), (15, 20)),),
    vias=(via("v1", "GND", 25, 20),),
    rules=(clearance(0.2),),
)


def _streams(data: bytes) -> dict[str, bytes]:
    compound = open_compound(data)
    return {path: compound.read(path) for path in compound.streams()}


def test_outline_mode_keeps_the_bytes() -> None:
    """Scenario "Outline mode keeps the bytes": the mode ``outline`` is the writer of earlier versions."""
    spec = BOARD.spec()
    assert pcbdoc.write_pcbdoc(spec, filename=FILENAME) == pcbdoc.write_pcbdoc(
        spec, filename=FILENAME, pour="outline"
    )
    result = pcbdoc.write_pcbdoc_result(spec, filename=FILENAME)
    assert result.pour is None and not result.issues
    polygons = read_pcbdoc(result.data).polygons
    assert {p.record.get("OPTIMALVOIDROTATION") for p in polygons} == {"TRUE"}
    assert not [r for r in read_pcbdoc(result.data).rules if r.kind_number == 20]


@needs_geo
def test_computed_and_reference_inputs_differ_in_the_pour_only() -> None:
    """Scenario "Computed and reference inputs differ in the pour only"."""
    spec = BOARD.spec()
    computed = pcbdoc.write_pcbdoc_result(spec, filename=FILENAME, pour="computed")
    reference = pcbdoc.write_pcbdoc_result(spec, filename=FILENAME, pour="computed", pour_regions=False)
    assert computed.pour is not None and computed.pour.poured == 3 and not computed.pour.refused
    first, second = _streams(computed.data), _streams(reference.data)
    assert first.keys() == second.keys()
    differ = sorted(path for path in first if first[path] != second[path])
    assert differ == [
        "Regions6/Data",
        "Regions6/Header",
        "ShapeBasedRegions6/Data",
        "ShapeBasedRegions6/Header",
    ]
    polygons = read_pcbdoc(reference.data).polygons
    assert {p.record.get("OPTIMALVOIDROTATION") for p in polygons} == {"FALSE"}


@needs_geo
def test_one_rule_per_net_and_a_default() -> None:
    """Scenario "One rule per net and a default" on an authored board: the rules of kind 20 of the written
    document map back to the styles of their nets, every via setting Direct Connect."""
    data = pcbdoc.write_pcbdoc(BOARD.spec(), filename=FILENAME, pour="computed")
    records = [r for r in read_pcbdoc(data).rules if r.kind_number == 20]
    styles = read_connect_styles([r.fields for r in records])
    assert [(s.name, s.priority) for s in styles] == [
        ("PolygonConnect_net_GND", 1),
        ("PolygonConnect_net_VIN", 2),
        ("PolygonConnect", 3),
    ]
    assert all(s.advanced and not s.reason for s in styles)
    gnd, vin, everything = styles
    assert gnd.th_pad is not None and gnd.th_pad.style == "relief"  # z1, thermal, has the highest priority
    assert vin.th_pad is not None and vin.th_pad.style == "direct"
    assert everything.th_pad is not None and everything.th_pad.style == "relief"
    assert all(s.via is not None and s.via.style == "direct" for s in styles)


@needs_geo
def test_zones_of_one_net_disagree() -> None:
    """Scenario "Zones of one net disagree": the zone of the higher priority gives the net's rule, and the
    other is reported."""
    result = pcbdoc.write_pcbdoc_result(BOARD.spec(), filename=FILENAME, pour="computed")
    assert [(i.code, i.where) for i in result.issues] == [("altium.not-lowered", "zone/z2")]


@needs_geo
def test_the_poured_document_reads_back() -> None:
    """The regions of the computed document read back as the fills of their zones. The VIN polygon of the
    bottom layer touches no VIN object, so its dead copper is removed (I13) and it holds no fill: an empty
    pour is a pour, not a refusal."""
    result = pcbdoc.write_pcbdoc_result(BOARD.spec(), filename=FILENAME, pour="computed")
    reading = read_pour(result.data, file=FILENAME)
    board = reading.design.board
    assert board is not None
    nets = {net.id: net.name for net in reading.design.circuit.nets}
    filled = {(zone.layers[0], nets.get(zone.net_id or "")): len(zone.fills) for zone in board.zones}
    assert filled == {("F.Cu", "GND"): 1, ("B.Cu", "GND"): 1, ("B.Cu", "VIN"): 0}
    assert result.pour is not None and not result.pour.refused


@needs_geo
def test_the_self_check_refuses_a_bad_pour(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "The self-check refuses a bad pour": a test engine that pours the GND polygon over every
    void gives copper on the VIN track; the writer refuses that polygon and writes no region of it."""
    from fenolite.backends.altium import pour as engine

    real = engine.pour_reading

    def careless(reading: engine.PourReading, **options: object) -> PourResult:
        found = real(reading, **options)  # type: ignore[arg-type]
        board = reading.design.board
        assert board is not None
        polygons: list[engine.PolygonPour] = []
        for item in found.polygons:
            if item.poured and item.net == "GND" and item.layer == "F.Cu":
                zone_entity = next(z for z in board.zones if z.id == item.zone_id)
                item = engine.PolygonPour(item.index, item.layer, item.net,
                                          (engine.Polygon(zone_entity.outline),), item.arc_resolution, "",
                                          item.zone_id)  # fmt: skip
            polygons.append(item)
        return PourResult(tuple(polygons))

    monkeypatch.setattr(engine, "pour_reading", careless)
    result = pcbdoc.write_pcbdoc_result(BOARD.spec(), filename=FILENAME, pour="computed")
    assert result.pour is not None
    assert ("copper-check", "z1", "F.Cu") in result.pour.refused
    regions = read_pcbdoc(result.data).regions
    top = next(i for i, p in enumerate(read_pcbdoc(result.data).polygons) if p.layer == "TOP")
    assert not [r for r in regions if getattr(r, "prefix", None) is not None and r.prefix.polygon == top]


def test_computed_without_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """The mode ``computed`` needs the geo extra: without it the writer raises ``BackendUnavailable``."""
    import sys

    monkeypatch.setitem(sys.modules, "pyclipper", None)
    with pytest.raises(BackendUnavailable):
        pcbdoc.write_pcbdoc_result(BOARD.spec(), filename=FILENAME, pour="computed")

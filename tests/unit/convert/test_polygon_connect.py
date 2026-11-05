# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pour settings of an Altium board on its KiCad zones (capability design-conversion, "Polygon connect
styles of an Altium board" and "Governing zone clearance"; change c0409, B5 and B6).

The source is the committed Fenolite sample ``tests/data/altium/board6`` (two GND zones, GND in the class
``PWR``). The Polygon Connect Style records are authored here, in the Simple form of
``docs/formats/altium/pcb-pour.md``, and added to the read board as the ``polygon_connect`` pairs the
import keeps."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from fenolite.backends.kicad.sexpr import parse
from fenolite.convert import convert_project
from fenolite.convert.sources import SourceProject, read_source
from fenolite.model.base import ExtBag

ROOT = Path(__file__).resolve().parents[3]
BOARD6 = ROOT / "tests" / "data" / "altium" / "board6" / "board6.PrjPcb"
HEADER = "NETSCOPE=AnyNet|LAYERKIND=SameLayer|COMMENT=|UNIQUEID=C0409|DEFINEDBYLOGICALDOCUMENT=FALSE"


def _record(name: str, priority: int, scope: str, style: str, spoke: str, gap: str) -> str:
    return (
        f"RULEKIND=PolygonConnect|{HEADER}|SCOPE1EXPRESSION={scope}|SCOPE2EXPRESSION=All|NAME={name}|"
        f"ENABLED=TRUE|PRIORITY={priority}|CONNECTSTYLE={style}|RELIEFCONDUCTORWIDTH={spoke}|RELIEFENTRIES=4|"
        f"POLYGONRELIEFANGLE=90 Angle|AIRGAPWIDTH={gap}"
    )


def _source(records: tuple[str, ...] = (), class_clearance: int | None = None) -> SourceProject:
    source = read_source(BOARD6)
    board = source.design.board
    assert board is not None
    bag = board.ext["altium"]
    pairs = (*bag.payload, *(("polygon_connect", text) for text in records))
    board = dataclasses.replace(board, ext={"altium": ExtBag(bag.min_version, pairs)})
    rules = source.design.rules
    if class_clearance is not None and rules is not None:
        changed = tuple(
            dataclasses.replace(rule, min=class_clearance) if rule.name == "Clearance_PWR" else rule
            for rule in rules.rules
        )
        rules = dataclasses.replace(rules, rules=changed)
    design = dataclasses.replace(source.design, board=board, rules=rules)
    return dataclasses.replace(source, design=design)


def test_connect_styles_reach_zones_and_pads() -> None:
    records = (
        _record("PolygonConnect", 2, "All", "Relief", "0.4mm", "0.3mm"),
        _record("PolygonConnect_D1", 1, "InComponent('D1')", "Direct", "0.4mm", "0.3mm"),
    )
    conversion = convert_project(_source(records), to="kicad", allow_lossy=True)
    board = conversion.design.board
    assert board is not None and len(board.zones) == 2
    for zone in board.zones:
        assert (zone.settings.connection, zone.settings.thermal_gap, zone.settings.thermal_spoke_width) == (
            "thermal",
            300_000,
            400_000,
        )
    refs = {component.id: component.ref for component in conversion.design.circuit.components}
    joined = {
        (refs[fp.component_id], pad.number): pad.zone_connection
        for fp in board.footprints
        for pad in fp.pads
        if pad.zone_connection is not None
    }
    assert joined == {("D1", "1"): "solid"}
    pcb = parse(conversion.files[conversion.read_back].decode())
    zone = pcb.nodes("zone")[0]
    fill = zone.find("fill")
    assert fill is not None
    gap, spoke = fill.find("thermal_gap"), fill.find("thermal_bridge_width")
    assert gap is not None and gap.atoms()[0].value == "0.3"
    assert spoke is not None and spoke.atoms()[0].value == "0.4"
    assert conversion.files[conversion.read_back].decode().count("(zone_connect 2)") == 1


def test_without_records_zones_keep_their_connection() -> None:
    conversion = convert_project(_source(), to="kicad", allow_lossy=True)
    board = conversion.design.board
    assert board is not None
    assert all(zone.settings.connection == "thermal" for zone in board.zones)
    assert all(pad.zone_connection is None for fp in board.footprints for pad in fp.pads)


def test_governing_clearance_of_the_polygon() -> None:
    conversion = convert_project(_source(class_clearance=350_000), to="kicad", allow_lossy=True)
    board = conversion.design.board
    assert board is not None
    assert [zone.settings.clearance for zone in board.zones] == [350_000, 350_000]
    pcb = parse(conversion.files[conversion.read_back].decode())
    poured = [zone for zone in pcb.nodes("zone") if zone.find("net") is not None]
    assert len(poured) == 2
    for zone in poured:
        pads = zone.find("connect_pads")
        assert pads is not None
        clearance = pads.find("clearance")
        assert clearance is not None and clearance.atoms()[0].value == "0.35"


def test_sample_clearance_is_the_rule_not_the_default() -> None:
    conversion = convert_project(_source(), to="kicad", allow_lossy=True)
    board = conversion.design.board
    assert board is not None
    assert [zone.settings.clearance for zone in board.zones] == [200_000, 200_000]

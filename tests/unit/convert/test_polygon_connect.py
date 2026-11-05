# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pour settings of an Altium board on its KiCad zones (capability design-conversion, "Polygon connect
styles of an Altium board" and "Governing zone clearance"; changes c0409 and c0420, B5 and B6).

The source is the committed Fenolite sample ``tests/data/altium/board6`` (two GND zones, GND in the class
``PWR``). The Polygon Connect Style records are authored here, in the Simple form of
``docs/formats/altium/pcb-pour.md``, and added to the read board as the ``polygon_connect`` pairs the
import keeps."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from fenolite.backends.altium.connectstyle import fold_subject
from fenolite.backends.kicad.sexpr import parse
from fenolite.convert import convert_project
from fenolite.convert.altium_to_kicad import Ledger
from fenolite.convert.altium_zones import (
    CLEARANCE_FROM_RULES,
    PAD_DIFFERS,
    board_styles,
    connect_zones,
    governing_clearance,
)
from fenolite.convert.sources import SourceProject, read_source
from fenolite.model.base import ExtBag
from fenolite.model.board import Board
from fenolite.model.rules import Rule, RuleSubject, Selector

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


def _named_record(name: str, priority: int, scope1: str, scope2: str, style: str) -> str:
    return _record(name, priority, scope1, style, "0.4mm", "0.3mm").replace(
        "SCOPE2EXPRESSION=All", f"SCOPE2EXPRESSION={scope2}"
    )


def _connected(records: tuple[str, ...]) -> tuple[Board, Ledger, dict[str, str]]:
    source = _source(records)
    board = source.design.board
    assert board is not None
    refs = {component.id: component.ref for component in source.design.circuit.components}
    ledger = Ledger()
    styles = board_styles(board)
    return connect_zones(board, source.design, styles, refs, ledger), ledger, refs


def test_a_named_polygon_record_governs_that_zone_alone() -> None:
    """Scenario "A named polygon": ``IsNamedPolygon`` names one of the two GND pours (change c0420, B5)."""
    records = (
        _record("PolygonConnect", 2, "All", "Relief", "0.4mm", "0.3mm"),
        _named_record("Top", 1, "All", "IsNamedPolygon('gnd_l01_p000')", "Direct"),
    )
    board, ledger, _ = _connected(records)
    assert {zone.name: zone.settings.connection for zone in board.zones} == {
        "GND_L01_P000": "solid",
        "GND_L06_P001": "thermal",
    }
    assert not ledger.changed.get("zone") and not ledger.changed.get("pad")
    assert all(pad.zone_connection is None for fp in board.footprints for pad in fp.pads)


def test_a_pad_whose_styles_differ_between_zones_keeps_its_setting() -> None:
    """Scenario "Pad styles differ between zones": D1 joins one pour directly and the other by relief, and a
    KiCad pad holds one connection, so the pad keeps its setting with a ``pad`` change (change c0420, B5)."""
    records = (
        _record("PolygonConnect", 2, "All", "Relief", "0.4mm", "0.3mm"),
        _named_record("D1_Bottom", 1, "InComponent('D1')", "IsNamedPolygon('GND_L06_P001')", "Direct"),
    )
    board, ledger, refs = _connected(records)
    assert all(zone.settings.connection == "thermal" for zone in board.zones)
    pads = {(refs[fp.component_id], pad.number): pad for fp in board.footprints for pad in fp.pads}
    assert pads[("D1", "1")].zone_connection is None
    assert ledger.changed["pad"][PAD_DIFFERS] == [pads[("D1", "1")].id]


def test_a_pad_with_one_own_style_for_every_zone_gets_it() -> None:
    records = (
        _record("PolygonConnect", 2, "All", "Relief", "0.4mm", "0.3mm"),
        _named_record("D1_All", 1, "InComponent('D1')", "IsNamedPolygon('GND_L06_P001') or "
                      "IsNamedPolygon('GND_L01_P000')", "Direct"),
    )  # fmt: skip
    board, ledger, refs = _connected(records)
    joined = {
        (refs[fp.component_id], pad.number): pad.zone_connection
        for fp in board.footprints
        for pad in fp.pads
        if pad.zone_connection is not None
    }
    assert joined == {("D1", "1"): "solid"} and not ledger.changed.get("pad")


def _rule(name: str, priority: int, a: Selector, b: Selector | None, value: int) -> Rule:
    return Rule(id=f"rul-{name}", name=name, kind="clearance", selector_a=a, selector_b=b, min=value,
                priority=priority)  # fmt: skip


def test_zone_clearance_is_the_smallest_governing_value() -> None:
    """Scenario "Smallest governing clearance" (change c0420, B6): the zone carries the smallest clearance of
    the rules that govern a pair of its polygon, up to the first against any item; a lower rule, a rule of
    other items and an ignored rule do not count, and without a rule against any item there is none."""
    pwr, pads = Selector("netclass", "PWR"), Selector("item_kind", "pad")
    polygon = fold_subject(RuleSubject("zone", net="GND", netclass="PWR"))
    rules = [
        _rule("hv", 1, Selector("netclass", "HV"), Selector("netclass", "LV"), 100_000),
        _rule("pads", 2, pads, Selector("all"), 250_000),
        _rule("pwr", 3, pwr, Selector("all"), 3_000_000),
        _rule("all", 4, Selector("all"), None, 150_000),
    ]
    assert governing_clearance(rules, polygon) == 250_000
    assert governing_clearance(rules[2:], polygon) == 3_000_000
    ignored = [dataclasses.replace(rules[1], severity="ignore"), *rules[2:]]
    assert governing_clearance(ignored, polygon) == 3_000_000
    assert governing_clearance(rules[:2], polygon) is None  # the pad rule holds against pads alone
    assert governing_clearance([dataclasses.replace(rules[2], severity="ignore")], polygon) is None


def test_board6_zone_takes_the_smaller_pad_clearance() -> None:
    """The board6 polygons with an authored higher-ranked pad x All clearance below the class value."""
    source = _source(class_clearance=350_000)
    rules = source.design.rules
    assert rules is not None
    pads = _rule("pads", 1, Selector("item_kind", "pad"), Selector("all"), 250_000)
    ranked = tuple(dataclasses.replace(r, priority=r.priority + 1) for r in rules.rules)
    design = dataclasses.replace(source.design, rules=dataclasses.replace(rules, rules=(pads, *ranked)))
    conversion = convert_project(dataclasses.replace(source, design=design), to="kicad", allow_lossy=True)
    board = conversion.design.board
    assert board is not None
    assert [zone.settings.clearance for zone in board.zones] == [250_000, 250_000]
    (row,) = [row for row in conversion.report.rows if row.kind == "zone"]
    reasons = {reason.reason: (reason.outcome, reason.count) for reason in row.reasons}
    assert reasons[CLEARANCE_FROM_RULES] == ("changed", 2)  # change c0420: a derived clearance is reported

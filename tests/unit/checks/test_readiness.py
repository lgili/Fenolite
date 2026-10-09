# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The readiness rules of ``fenolite ready`` on authored models (capability verification-loop, "Open nets
check" to "Readiness issue codes"; change c0098; ``H-G-READY-RULES``)."""

from __future__ import annotations

import dataclasses

from fenolite.checks import readiness as ready
from fenolite.checks.readiness import OpenNet
from fenolite.checks.stages import StageResult
from fenolite.cli.explain import all_codes, explain
from fenolite.core.coords import Point
from fenolite.core.evidence import Level
from fenolite.model.board import Board, FootprintInstance, Zone
from fenolite.model.circuit import Circuit, Component, Interface, Net, NetClass, Pin, PinRef
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSet, Selector

SQUARE = (Point(0, 0), Point(1_000_000, 0), Point(1_000_000, 1_000_000), Point(0, 1_000_000))


def _part(
    cid: str, ref: str, *pins: tuple[str, str], value: str = "1k", footprint: str = "Lib:R", dnp: bool = False
) -> Component:
    return Component(
        id=cid,
        ref=ref,
        value=value,
        dnp=dnp,
        lib_footprint_ref=footprint,
        pins=tuple(Pin(id=f"pin_{cid}_{n}", number=n, etype=t) for n, t in pins),  # type: ignore[arg-type]
    )


def _net(nid: str, name: str, *members: tuple[str, str], netclass: str | None = None) -> Net:
    return Net(id=nid, name=name, netclass_id=netclass, members=tuple(PinRef(c, p) for c, p in members))


def _design(
    components: tuple[Component, ...],
    nets: tuple[Net, ...] = (),
    *,
    interfaces: tuple[Interface, ...] = (),
    netclasses: tuple[NetClass, ...] = (),
    rules: tuple[Rule, ...] = (),
    zones: tuple[Zone, ...] = (),
    no_connects: tuple[PinRef, ...] = (),
) -> Design:
    footprints = tuple(
        FootprintInstance(
            id=f"fpi_{c.id}", component_id=c.id, lib_ref=c.lib_footprint_ref, position=Point(0, 0)
        )
        for c in components
        if c.lib_footprint_ref
    )
    circuit = Circuit(
        components=components,
        nets=nets,
        netclasses=netclasses,
        interfaces=interfaces,
        no_connects=no_connects,
    )
    return dataclasses.replace(
        Design.new("ready", seed=0),
        circuit=circuit,
        board=Board(id="brd_1", footprints=footprints, zones=zones),
        rules=RuleSet(id="rls_1", rules=rules) if rules else None,
    )


def _wheres(stage: StageResult, code: str) -> list[str]:
    return [i.where for i in stage.issues if i.code == code]


# -- open nets


def test_open_stage_reports_each_open_net() -> None:
    rows = [OpenNet("A", 2, 1_500_000, "R1-1", "R2-1"), OpenNet("B", 1, 250_000, "C1-2", "track")]
    stage = ready.open_stage(rows, evidence=ready.EVIDENCE)
    assert stage.name == "nets.open" and stage.status == "errors"
    assert _wheres(stage, "ready.net-open") == ["A", "B"]
    assert dict(stage.summary) == {"nets": 2, "connections": 3}
    first = next(i for i in stage.issues if i.where == "A")
    assert "2 open connections" in first.message and "R1-1 and R2-1 (1.500 mm)" in first.message


def test_open_stage_without_open_nets_is_ok() -> None:
    stage = ready.open_stage([], evidence=ready.EVIDENCE)
    assert stage.status == "ok" and dict(stage.summary) == {"nets": 0, "connections": 0}


# -- unconnected pins

U1 = _part(
    "cmp_u1", "U1", ("1", "passive"), ("2", "input"), ("3", "input"), ("4", "no_connect"), ("5", "output")
)
R1 = _part("cmp_r1", "R1", ("1", "passive"), ("2", "passive"))
R9 = _part("cmp_r9", "R9", ("1", "passive"), dnp=True)
PINS = _design(
    (U1, R1, R9),
    (
        _net("net_1", "VCC", ("cmp_u1", "1"), ("cmp_r1", "1")),
        _net("net_2", "X", ("cmp_u1", "5")),
        _net("net_3", "R2", ("cmp_r1", "2"), ("cmp_u1", "1")),
    ),
    no_connects=(PinRef("cmp_u1", "3"),),
)


def test_pins_unconnected_rule() -> None:
    found = [f"{c.ref}-{p.number}" for c, p in ready.unconnected_pins(PINS)]
    assert found == ["U1-2", "U1-5"]
    flagged = [f"{c.ref}-{p.number}" for c, p in ready.unconnected_pins(PINS, flagged={("cmp_u1", "5")})]
    assert flagged == ["U1-2"]


def test_pins_stage() -> None:
    stage = ready.pins_stage(PINS)
    assert stage.name == "pins.unconnected" and stage.status == "errors"
    assert _wheres(stage, "ready.pin-unconnected") == ["U1-2", "U1-5"]
    assert dict(stage.summary) == {"pins": 2}
    assert stage.evidence.level is Level.INFERRED and stage.evidence.hypotheses == ("H-G-READY-RULES",)


# -- power nets

SUPPLY = _part("cmp_u2", "U2", ("1", "power_out"), ("2", "passive"), ("3", "passive"))
LOAD = _part("cmp_r3", "R3", ("1", "passive"), ("2", "passive"), ("3", "passive"), ("4", "passive"))
PWR_CLASS = NetClass(id="ncl_1", name="PWR", track_width=500_000)
NETS = (
    _net("net_v5", "V5", ("cmp_u2", "1"), ("cmp_r3", "1")),
    _net("net_vcc", "VCC", ("cmp_u2", "2"), ("cmp_r3", "2"), netclass="ncl_1"),
    _net("net_gnd", "GND", ("cmp_u2", "3"), ("cmp_r3", "3")),
    _net("net_sig", "SIG", ("cmp_r3", "4"), ("cmp_u1", "1")),
)
"""``V5`` is a power net by its ``power_out`` pin, ``VCC`` and ``GND`` by the interface; ``SIG`` holds only
``passive`` pins."""
POWER = Interface(id="itf_1", name="P", kind="power", members={"hv": "net_vcc", "lv": "net_gnd"})
V5_RULE = Rule(id="rul_1", name="v5", kind="track_width", selector_a=Selector("net", "V5"), min=400_000)
ALL_RULE = Rule(id="rul_2", name="floor", kind="track_width", selector_a=Selector("all"), min=150_000)
GND_ZONE = Zone(id="zon_1", outline=SQUARE, layers=("B.Cu",), net_id="net_gnd")


def _power(*, zone: bool = True) -> Design:
    return _design(
        (SUPPLY, LOAD),
        NETS,
        interfaces=(POWER,),
        netclasses=(PWR_CLASS,),
        rules=(V5_RULE, ALL_RULE),
        zones=(GND_ZONE,) if zone else (),
    )


def test_power_nets_and_their_coverage() -> None:
    design = _power()
    rows = {row.net: row for row in ready.power_nets(design, board=design)}
    assert sorted(rows) == ["GND", "V5", "VCC"]
    assert (rows["GND"].source, rows["GND"].zones) == ("interface", 1)
    assert rows["V5"].source == "pin-type" and rows["VCC"].source == "interface"
    stage = ready.power_stage(design, board=design)
    assert stage.name == "power.nets" and stage.status == "ok" and not stage.issues
    bare = _power(zone=False)
    stage = ready.power_stage(bare, board=bare)
    assert _wheres(stage, "ready.power-net-unsized") == ["GND"] and stage.status == "errors"


def test_power_net_width_from_class_and_rule() -> None:
    design = _power()
    rows = {row.net: row for row in ready.power_nets(design, board=design)}
    assert rows["VCC"].width == "class:PWR"
    assert rows["V5"].width == "rule:v5"
    assert rows["GND"].width is None  # the rule that selects ``all`` is a board minimum, not a declaration


def test_power_net_width_ignores_default_class_and_ignored_rules() -> None:
    default = NetClass(id="ncl_2", name="Default", track_width=300_000)
    ignored = dataclasses.replace(V5_RULE, severity="ignore")
    nets = (dataclasses.replace(NETS[0], netclass_id="ncl_2"), *NETS[1:])
    design = _design((SUPPLY, LOAD), nets, netclasses=(PWR_CLASS, default), rules=(ignored,))
    rows = {row.net: row for row in ready.power_nets(design, board=design)}
    assert rows["V5"].width is None


def test_power_net_zones_come_from_the_board() -> None:
    intent = _power(zone=False)
    board = _power(zone=True)
    rows = {row.net: row for row in ready.power_nets(intent, board=board)}
    assert rows["GND"].zones == 1


# -- part fields


def test_parts_stage() -> None:
    no_value = _part("cmp_a", "R1", ("1", "passive"), value=" ")
    no_footprint = _part("cmp_b", "R2", ("1", "passive"), footprint="")
    dnp = _part("cmp_c", "R3", ("1", "passive"), value="", footprint="", dnp=True)
    stage = ready.parts_stage(_design((no_value, no_footprint, dnp)))
    assert stage.name == "parts.fields" and stage.status == "errors"
    assert _wheres(stage, "ready.part-value-missing") == ["R1"]
    assert _wheres(stage, "check.footprint-unresolved") == ["R2"]
    assert dict(stage.summary) == {"footprint": 1, "value": 1}


# -- skipped checks and codes


def test_skipped_check_holds_its_warning() -> None:
    stage = ready.skipped_check("erc.kicad", "no-kicad")
    assert stage.status == "skipped" and stage.reason == "no-kicad"
    assert [(i.code, i.severity, i.where) for i in stage.issues] == [
        ("ready.check-skipped", "warning", "erc.kicad")
    ]


def test_every_code_is_explained() -> None:
    codes = all_codes()
    for code, severity in ready.READY_ISSUE_CODES.items():
        assert codes[code] == (severity,)
        entry = explain(code)
        assert entry is not None and entry.see == "ready"

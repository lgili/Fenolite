# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Polygon Connect Style records read, resolved and lowered (change c0215;
``docs/formats/altium/pcb-pour.md``, "Polygon Connect Style records"; capability altium-pcb-writer,
"Polygon Connect Style records")."""

from __future__ import annotations

from dataclasses import replace

from fenolite.backends.altium import pcbrecords as rec
from fenolite.backends.altium.connectstyle import (
    Connection,
    ConnectStyle,
    governing_connection,
    lower_zone_styles,
    pad_overrides,
    read_connect_style,
    read_connect_styles,
    style_keys,
    zone_connections,
)
from fenolite.backends.altium.read.proptext import parse_length
from fenolite.core.coords import Point, Size
from fenolite.model.board import Board, FootprintInstance, Pad, Zone, ZoneSettings
from fenolite.model.rules import RuleSubject

HEAD = [
    ("SELECTION", "FALSE"), ("LAYER", "TOP"), ("LOCKED", "FALSE"), ("POLYGONOUTLINE", "FALSE"),
    ("USERROUTED", "TRUE"), ("KEEPOUT", "FALSE"), ("UNIONINDEX", "0"), ("RULEKIND", "PolygonConnect"),
    ("NETSCOPE", "AnyNet"), ("LAYERKIND", "SameLayer"),
]  # fmt: skip


def _record(
    name: str, priority: int, scope1: str, scope2: str, *keys: tuple[str, str]
) -> list[tuple[str, str]]:
    return [
        *HEAD,
        ("SCOPE1EXPRESSION", scope1),
        ("SCOPE2EXPRESSION", scope2),
        ("NAME", name),
        ("ENABLED", "TRUE"),
        ("PRIORITY", str(priority)),
        ("COMMENT", " "),
        ("UNIQUEID", "ABCDEFGH"),
        ("DEFINEDBYLOGICALDOCUMENT", "FALSE"),
        *keys,
    ]


def _simple(style: str = "Relief", width: str = "10mil", entries: str = "4", angle: str = "90 Angle",
            gap: str = "10mil", prefix: str = "") -> list[tuple[str, str]]:  # fmt: skip
    return [
        (prefix + "CONNECTSTYLE", style),
        (prefix + "RELIEFCONDUCTORWIDTH", width),
        (prefix + "RELIEFENTRIES", entries),
        (prefix + "POLYGONRELIEFANGLE", angle),
        (prefix + "AIRGAPWIDTH", gap),
    ]


MIL10 = 254_000


def test_simple_record_sets_every_object() -> None:
    style = read_connect_style(_record("PolygonConnect", 1, "All", "All", *_simple()))
    assert style is not None and not style.reason and not style.advanced
    relief = Connection("relief", MIL10, 4, 0, MIL10)
    assert (style.th_pad, style.smd_pad, style.via) == (relief, relief, relief)


def test_advanced_record_sets_each_object() -> None:
    keys = [
        *_simple("Relief", "11.811mil", "4", "45 Angle", "11.811mil", "THPAD."),
        *_simple("Relief", "7.874mil", "4", "90 Angle", "11.811mil", "SMDPAD."),
        *_simple("Direct", prefix="VIA."),
    ]
    style = read_connect_style(_record("PolygonConnect", 3, "All", "All", *keys))
    assert style is not None and style.advanced and not style.reason
    gap = parse_length("11.811mil")
    assert gap == 299_999  # 11.811 mil, rounded half to even to the nanometre
    assert style.th_pad == Connection("relief", gap, 4, 45_000_000, gap)
    assert style.smd_pad == Connection("relief", parse_length("7.874mil") or 0, 4, 0, gap)
    assert style.via is not None and style.via.style == "direct"


def test_records_that_do_not_read_keep_a_reason() -> None:
    """An unknown style value, an entry count outside 2 and 4, an unknown key and a disabled record."""
    bad_style = read_connect_style(_record("A", 1, "All", "All", *_simple(style="Auto")))
    bad_entries = read_connect_style(_record("B", 1, "All", "All", *_simple(entries="3")))
    extra = read_connect_style(_record("C", 1, "All", "All", *_simple(), ("MINDISTANCE", "1mil")))
    disabled = [(k, "FALSE" if k == "ENABLED" else v) for k, v in _record("D", 1, "All", "All", *_simple())]
    assert bad_style is not None and bad_style.reason == "connect-style"
    assert bad_entries is not None and bad_entries.reason == "connect-value"
    assert extra is not None and extra.reason == "connect-keys"
    assert read_connect_style(disabled) is None
    assert read_connect_style([("RULEKIND", "Clearance")]) is None


def _pad(net: str, kind: str = "pad") -> RuleSubject:
    return RuleSubject(item_kind=kind, net=net, netclass="Default")


def _zone(net: str) -> RuleSubject:
    return RuleSubject(item_kind="zone", net=net, netclass="Default")


def test_the_governing_record_by_priority_and_scope() -> None:
    """The first record by priority whose scopes match the pair in either order governs; an unread scope
    before it refuses; no record that matches refuses."""
    styles = read_connect_styles(
        [
            _record("All", 3, "All", "All", *_simple("Relief")),
            _record("Vias", 2, "All", "IsVia", *_simple("Direct")),
            _record("Vdd", 1, "InNet('vdd')", "All", *_simple("Direct", width="20mil")),
        ]
    )
    assert [s.name for s in styles] == ["Vdd", "Vias", "All"]
    vdd = governing_connection(styles, _pad("VDD"), _zone("VDD"), "th_pad")
    assert isinstance(vdd, Connection) and vdd.style == "direct" and vdd.conductor_width == 2 * MIL10
    via = governing_connection(styles, _pad("GND", "via"), _zone("GND"), "via")
    assert isinstance(via, Connection) and via.style == "direct"
    pad = governing_connection(styles, _pad("GND"), _zone("GND"), "smd_pad")
    assert isinstance(pad, Connection) and pad.style == "relief"
    unread = read_connect_styles([_record("Named", 1, "IsNamedPolygon('X')", "All", *_simple()), *[]])
    assert governing_connection(unread, _pad("GND"), _zone("GND"), "th_pad") == "connect-scope"
    narrow = read_connect_styles([_record("Only", 1, "InNet('VIN')", "All", *_simple())])
    assert governing_connection(narrow, _pad("GND"), _zone("GND"), "th_pad") == "connect-none"


def _zone_entity(ident: str, net: str, priority: int, settings: ZoneSettings) -> Zone:
    square = (Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10))
    return Zone(id=ident, outline=square, layers=("F.Cu",), net_id=net, priority=priority, settings=settings)


def test_zone_connections() -> None:
    """Decision 11: thermal, thru_hole_only, solid and none, vias always direct."""
    settings = ZoneSettings(thermal_gap=300_000, thermal_spoke_width=400_000, clearance=250_000)
    relief = Connection("relief", 400_000, 4, 0, 300_000)
    direct = replace(relief, style="direct")
    apart = Connection("none", 400_000, 4, 0, 250_000)
    assert zone_connections(settings) == (relief, relief, direct)
    assert zone_connections(replace(settings, connection="thru_hole_only")) == (relief, direct, direct)
    assert zone_connections(replace(settings, connection="solid")) == (direct, direct, direct)
    assert zone_connections(replace(settings, connection="none")) == (apart, apart, direct)


def test_rule_per_net_and_a_default() -> None:
    """Scenarios "One rule per net and a default" and "Zones of one net disagree" (the lowering)."""
    thermal = ZoneSettings()
    solid = ZoneSettings(connection="solid")
    zones = (
        _zone_entity("z1", "GND", 1, thermal),
        _zone_entity("z2", "GND", 0, solid),
        _zone_entity("z3", "VIN", 0, solid),
    )
    styles, issues = lower_zone_styles(zones)
    assert [(s.name, s.scope) for s in styles] == [
        ("PolygonConnect_net_GND", "InNet('GND')"),
        ("PolygonConnect_net_VIN", "InNet('VIN')"),
        ("PolygonConnect", "All"),
    ]
    assert styles[0].th_pad.style == "relief" and styles[1].th_pad.style == "direct"
    assert all(s.via.style == "direct" for s in styles)
    assert [(i.code, i.severity, i.where) for i in issues] == [("altium.not-lowered", "info", "zone/z2")]


def test_a_pad_override_is_reported() -> None:
    """Decision 11: a pad's own ``zone_connection`` is not lowered; on a board with a zone it is one
    ``altium.not-lowered`` with ``where`` ``pad/<id>``, and a board without a zone reports none."""
    pads = (
        Pad(id="p1", number="1", shape="rect", size=Size(1_000_000, 1_000_000), position=Point(0, 0),
            zone_connection="solid"),
        Pad(id="p2", number="2", shape="rect", size=Size(1_000_000, 1_000_000), position=Point(2_000_000, 0)),
    )  # fmt: skip
    footprint = FootprintInstance(id="f1", component_id="c1", lib_ref="L:F", position=Point(0, 0), pads=pads)
    board = Board(id="b1", footprints=(footprint,), zones=(_zone_entity("z1", "GND", 0, ZoneSettings()),))
    assert [(i.code, i.severity, i.where) for i in pad_overrides(board)] == [
        ("altium.not-lowered", "info", "pad/p1")
    ]
    assert pad_overrides(replace(board, zones=())) == () and pad_overrides(None) == ()


def _mil(nm: int) -> str:
    return rec.mil_text(rec.to_units(nm))


def test_written_keys_read_back() -> None:
    """The keys of a lowered rule read back to the same settings, the widths within one file unit."""
    styles, _ = lower_zone_styles((_zone_entity("z1", "GND", 0, ZoneSettings()),))
    for lowered in styles:
        record = _record(lowered.name, 1, lowered.scope, "All", *style_keys(lowered, _mil))
        read = read_connect_style(record)
        assert isinstance(read, ConnectStyle) and read.advanced and not read.reason
        for mine, back in (
            (lowered.th_pad, read.th_pad),
            (lowered.smd_pad, read.smd_pad),
            (lowered.via, read.via),
        ):
            assert back is not None and back.style == mine.style and back.conductors == mine.conductors
            assert (
                abs(back.conductor_width - mine.conductor_width) <= 2
                and abs(back.air_gap - mine.air_gap) <= 2
            )
    assert parse_length(_mil(MIL10)) == MIL10

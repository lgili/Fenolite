# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pour settings of an Altium board on its KiCad zones (change c0409, B5 and B6).

- **Connect styles (B5).** The Polygon Connect Style records the board keeps as ``polygon_connect`` pairs
  (``backends/altium/connectstyle``, ``docs/formats/altium/pcb-pour.md``) give each zone the connection,
  thermal gap and spoke width of the record that governs the pads of its net, and a pad whose narrower record
  joins it otherwise its own ``zone_connection``.
- **Clearance (B6).** A zone's clearance is the value of the Altium clearance rule that governs the polygon
  against any item: the first rule, in Altium's order, with one scope matching the polygon and the other
  ``All``.

A zone or pad that no record or rule settles keeps its setting, with a ``zone`` or ``pad`` change in the
report that says why.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING

from fenolite.backends.altium.connectstyle import (
    Connection,
    ConnectKind,
    ConnectStyle,
    ObjectKind,
    connect_fields,
    fold_selector,
    fold_subject,
    governing_connection,
    read_connect_styles,
)
from fenolite.model.board import Board, FootprintInstance, Pad, Zone, ZoneConnection
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleSubject

if TYPE_CHECKING:
    from fenolite.convert.altium_to_kicad import Ledger

ZONE_CONNECTIONS: Mapping[tuple[ConnectKind, ConnectKind], ZoneConnection] = {
    ("relief", "relief"): "thermal",
    ("relief", "direct"): "thru_hole_only",
    ("direct", "direct"): "solid",
    ("none", "none"): "none",
}
"""(through-hole pads, SMD pads) of the governing record → the zone's connection."""
PAD_CONNECTIONS: Mapping[ConnectKind, ZoneConnection] = {
    "relief": "thermal",
    "direct": "solid",
    "none": "none",
}
"""The style of one pad's governing record → the pad's own connection."""
STYLE_UNREAD = "the zone keeps the default pad connection: the Altium connect style is not read ({reason})"
STYLE_MIXED = (
    "the zone joins through-hole pads by {th} and SMD pads by {smd}, which no KiCad zone connection holds; "
    "it takes the through-hole style"
)
PAD_SPOKES = "the pad's own thermal gap and spoke width of a narrower connect style are not written"
NO_CLEARANCE = "no Altium clearance rule governs the polygon against any item: the zone keeps its clearance"


def board_styles(board: Board | None) -> tuple[ConnectStyle, ...]:
    """The Polygon Connect Style records an imported Altium board keeps (its ``polygon_connect`` pairs), the
    governing one first."""
    if board is None:
        return ()
    bag = board.ext.get("altium")
    payload = bag.payload if bag is not None else ()
    return read_connect_styles(
        [connect_fields(str(text)) for key, text in payload if key == "polygon_connect"]
    )


def _nets(design: Design) -> dict[str, tuple[str, str | None]]:
    classes = {netclass.id: netclass.name for netclass in design.circuit.netclasses}
    return {
        net.id: (net.name, classes.get(net.netclass_id) if net.netclass_id is not None else None)
        for net in design.circuit.nets
    }


def _zone_connection(
    zone: Zone, th: Connection, smd: Connection, ledger: Ledger
) -> tuple[ZoneConnection, Connection]:
    found = ZONE_CONNECTIONS.get((th.style, smd.style))
    if found is None:
        ledger.change("zone", zone.id, STYLE_MIXED.format(th=th.style, smd=smd.style))
        found = PAD_CONNECTIONS[th.style]
    return found, th if th.style == "relief" else smd


def _expected(connection: ZoneConnection, kind: ObjectKind) -> ZoneConnection:
    if connection == "thru_hole_only":
        return "thermal" if kind == "th_pad" else "solid"
    return connection


def connect_zones(board: Board, design: Design, styles: Sequence[ConnectStyle], refs: Mapping[str, str],
                  ledger: Ledger) -> Board:  # fmt: skip
    """``board`` with the connection of each zone and pad that ``styles`` govern (B5); ``refs`` maps a
    component id to its designator."""
    if not styles or not board.zones:
        return board
    nets = _nets(design)
    zones: list[Zone] = []
    by_net: dict[str, tuple[RuleSubject, ZoneConnection, Connection]] = {}
    for zone in board.zones:
        name, netclass = nets.get(zone.net_id or "", (None, None))
        if name is None:
            zones.append(zone)
            continue
        polygon = RuleSubject("zone", net=name, netclass=netclass)
        pad = RuleSubject("pad", net=name, netclass=netclass)
        th = governing_connection(styles, pad, polygon, "th_pad")
        smd = governing_connection(styles, pad, polygon, "smd_pad")
        if isinstance(th, str) or isinstance(smd, str):
            ledger.change("zone", zone.id, STYLE_UNREAD.format(reason=th if isinstance(th, str) else smd))
            zones.append(zone)
            continue
        connection, relief = _zone_connection(zone, th, smd, ledger)
        settings = dataclasses.replace(zone.settings, connection=connection)
        if relief.style == "relief":
            settings = dataclasses.replace(
                settings, thermal_gap=relief.air_gap, thermal_spoke_width=relief.conductor_width
            )
        zones.append(dataclasses.replace(zone, settings=settings))
        by_net.setdefault(zone.net_id or "", (polygon, connection, relief))
    footprints: list[FootprintInstance] = []
    for fp in board.footprints:
        pads: list[Pad] = []
        for pad in fp.pads:
            held = by_net.get(pad.net_id or "")
            if held is None or pad.kind in ("np_thru_hole", "connect"):
                pads.append(pad)
                continue
            polygon, connection, relief = held
            kind: ObjectKind = "th_pad" if pad.kind == "thru_hole" else "smd_pad"
            subject = RuleSubject(
                "pad", net=polygon.net, netclass=polygon.netclass, ref=refs.get(fp.component_id)
            )
            own = governing_connection(styles, subject, polygon, kind)
            if isinstance(own, str):
                pads.append(pad)
                continue
            wanted = PAD_CONNECTIONS[own.style]
            if wanted != _expected(connection, kind):
                pad = dataclasses.replace(pad, zone_connection=wanted)
            elif own.style == "relief" and (own.air_gap, own.conductor_width) != (
                relief.air_gap,
                relief.conductor_width,
            ):
                ledger.change("pad", pad.id, PAD_SPOKES)
            pads.append(pad)
        footprints.append(dataclasses.replace(fp, pads=tuple(pads)))
    return dataclasses.replace(board, zones=tuple(zones), footprints=tuple(footprints))


def _governing(rules: Sequence[Rule]) -> list[Rule]:
    """The clearance rules, the governing one first: Altium's priority 1 first, unset (0) last."""
    found = [rule for rule in rules if rule.kind == "clearance" and rule.min is not None and not rule.layers]
    return sorted(found, key=lambda rule: (rule.priority == 0, rule.priority, rule.name, rule.id))


def _against_all(rule: Rule, polygon: RuleSubject) -> bool:
    """Whether ``rule`` holds between the folded ``polygon`` and any item: one scope matches it and the other
    is ``All``."""
    first = fold_selector(rule.selector_a)
    second = None if rule.selector_b is None else fold_selector(rule.selector_b)
    if second is None or second.op == "all":
        return first.matches(polygon)
    return first.op == "all" and second.matches(polygon)


def zone_clearances(board: Board, design: Design, ledger: Ledger) -> Board:
    """``board`` with the clearance of each zone set from the Altium clearance rule that governs its polygon
    against any item (B6)."""
    rules = _governing(design.rules.rules if design.rules is not None else ())
    if not rules or not board.zones:
        return board
    nets = _nets(design)
    zones: list[Zone] = []
    for zone in board.zones:
        name, netclass = nets.get(zone.net_id or "", (None, None))
        polygon = fold_subject(RuleSubject("zone", net=name, netclass=netclass))
        rule = next((rule for rule in rules if _against_all(rule, polygon)), None)
        if rule is None or rule.min is None or rule.severity == "ignore":
            ledger.change("zone", zone.id, NO_CLEARANCE)
            zones.append(zone)
            continue
        settings = dataclasses.replace(zone.settings, clearance=rule.min)
        zones.append(dataclasses.replace(zone, settings=settings))
    return dataclasses.replace(board, zones=tuple(zones))


__all__ = [
    "PAD_CONNECTIONS",
    "ZONE_CONNECTIONS",
    "board_styles",
    "connect_zones",
    "zone_clearances",
]

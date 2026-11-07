# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pour settings of an Altium board on its KiCad zones (change c0409, B5 and B6).

- **Connect styles (B5).** The Polygon Connect Style records the board keeps as ``polygon_connect`` pairs
  (``backends/altium/connectstyle``, ``docs/formats/altium/pcb-pour.md``) give each zone the connection,
  thermal gap and spoke width of the record that governs the pads of its net, and a pad whose narrower record
  joins it otherwise its own ``zone_connection``.
- **Clearance (B6).** A zone's clearance is the smallest value of the Altium clearance rules that govern a
  pair of the polygon and an item: in Altium's order, every rule with a scope matching the polygon, up to
  and with the first whose other scope is ``All`` (change c0420). KiCad lets a matching custom rule decide
  a zone's gap and takes the larger of the zone's clearance and a netclass clearance (pcb-pour.md,
  ``H-K-ZONE-CLEARANCE``), so the converted DRU rules carry every wider value.

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
from fenolite.model.rules import PAD_TYPE_OF, Rule, RuleSubject, Selector

if TYPE_CHECKING:
    from fenolite.backends.altium.read.scope import ScopeDocument
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
PAD_DIFFERS = (
    "the connect styles that govern the pad differ between the zones of its net, and a KiCad pad holds one "
    "connection for every zone: the pad keeps its setting"
)
NO_CLEARANCE = "no Altium clearance rule governs the polygon against any item: the zone keeps its clearance"
CLEARANCE_FROM_RULES = (
    "the zone's clearance is the smallest Altium clearance rule that governs its polygon, not the value the "
    "zone held; the written rules keep every wider clearance (change c0420, B6)"
)


def _placed(selector: Selector | None) -> bool:
    """Whether ``selector`` holds a layer or a room: the conversion judges neither (``board_styles``)."""
    if selector is None:
        return False
    return selector.op in ("layer", "area") or any(_placed(item) for item in selector.items)


def board_styles(board: Board | None, document: ScopeDocument | None = None) -> tuple[ConnectStyle, ...]:
    """The Polygon Connect Style records an imported Altium board keeps (its ``polygon_connect`` pairs), the
    governing one first, their scopes read with the full grammar and the source's ``document`` (change
    c0462, task 4.5). A scope that names a layer or a room is not judged: the zones carry the target's layer
    names and no room, so a pour such a record may govern keeps its setting (``connect-scope``)."""
    if board is None:
        return ()
    bag = board.ext.get("altium")
    payload = bag.payload if bag is not None else ()
    styles = read_connect_styles(
        [connect_fields(str(text)) for key, text in payload if key == "polygon_connect"], document
    )
    return tuple(
        dataclasses.replace(style, scope1=None) if _placed(style.scope1) or _placed(style.scope2) else style
        for style in styles
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


def _pad_connection(
    pad: Pad,
    zones: Sequence[tuple[RuleSubject, ZoneConnection, Connection, str]],
    styles: Sequence[ConnectStyle],
    ref: str | None,
    ledger: Ledger,
) -> Pad:
    """``pad`` with its own ``zone_connection`` when the record that governs it against a zone of its net
    (``zones``: each zone's polygon, connection, relief and name) gives another style than that zone does.
    A KiCad pad holds one connection for every zone, so a pad that needs its own one whose records give
    different styles between the zones keeps its setting, with a ``pad`` change (change c0420, B5)."""
    kind: ObjectKind = "th_pad" if pad.kind == "thru_hole" else "smd_pad"
    owns: list[tuple[Connection, ZoneConnection, Connection]] = []
    for polygon, connection, relief, name in zones:
        subject = RuleSubject(
            "pad", net=polygon.net, netclass=polygon.netclass, ref=ref, pad_type=PAD_TYPE_OF.get(pad.kind),
            hole=pad.drill if pad.kind != "smd" else None,
        )  # fmt: skip
        own = governing_connection(styles, subject, polygon, kind, name)
        if isinstance(own, str):
            return pad
        owns.append((own, connection, relief))
    wanted = {PAD_CONNECTIONS[own.style] for own, _, _ in owns}
    if any(PAD_CONNECTIONS[own.style] != _expected(connection, kind) for own, connection, _ in owns):
        if len(wanted) > 1:
            ledger.change("pad", pad.id, PAD_DIFFERS)
            return pad
        return dataclasses.replace(pad, zone_connection=wanted.pop())
    if any(
        own.style == "relief"
        and (own.air_gap, own.conductor_width) != (relief.air_gap, relief.conductor_width)
        for own, _, relief in owns
    ):
        ledger.change("pad", pad.id, PAD_SPOKES)
    return pad


def connect_zones(board: Board, design: Design, styles: Sequence[ConnectStyle], refs: Mapping[str, str],
                  ledger: Ledger) -> Board:  # fmt: skip
    """``board`` with the connection of each zone and pad that ``styles`` govern (B5); ``refs`` maps a
    component id to its designator."""
    if not styles or not board.zones:
        return board
    nets = _nets(design)
    zones: list[Zone] = []
    by_net: dict[str, list[tuple[RuleSubject, ZoneConnection, Connection, str]]] = {}
    for zone in board.zones:
        name, netclass = nets.get(zone.net_id or "", (None, None))
        if name is None:
            zones.append(zone)
            continue
        polygon = RuleSubject("zone", net=name, netclass=netclass, zone=zone.name)
        through = RuleSubject("pad", net=name, netclass=netclass, pad_type="th")
        surface = RuleSubject("pad", net=name, netclass=netclass, pad_type="smd")
        th = governing_connection(styles, through, polygon, "th_pad", zone.name)
        smd = governing_connection(styles, surface, polygon, "smd_pad", zone.name)
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
        by_net.setdefault(zone.net_id or "", []).append((polygon, connection, relief, zone.name))
    footprints: list[FootprintInstance] = []
    for fp in board.footprints:
        pads: list[Pad] = []
        for pad in fp.pads:
            held = by_net.get(pad.net_id or "")
            if held is None or pad.kind in ("np_thru_hole", "connect"):
                pads.append(pad)
                continue
            pads.append(_pad_connection(pad, held, styles, refs.get(fp.component_id), ledger))
        footprints.append(dataclasses.replace(fp, pads=tuple(pads)))
    return dataclasses.replace(board, zones=tuple(zones), footprints=tuple(footprints))


def _governing(rules: Sequence[Rule]) -> list[Rule]:
    """The clearance rules, the governing one first: Altium's priority 1 first, unset (0) last."""
    found = [rule for rule in rules if rule.kind == "clearance" and rule.min is not None and not rule.layers]
    return sorted(found, key=lambda rule: (rule.priority == 0, rule.priority, rule.name, rule.id))


def _touches(rule: Rule, polygon: RuleSubject) -> bool:
    """Whether ``rule`` can govern a pair of the folded ``polygon`` and an item: one scope matches it."""
    second = None if rule.selector_b is None else fold_selector(rule.selector_b)
    return second is None or second.matches(polygon) or fold_selector(rule.selector_a).matches(polygon)


def governing_clearance(rules: Sequence[Rule], polygon: RuleSubject) -> int | None:
    """The smallest ``min`` of the clearance ``rules`` (governing order) that govern a pair of the folded
    ``polygon``: those up to and with the first that holds against any item. ``None`` when no rule holds
    against any item, or that rule is ignored."""
    smallest: int | None = None
    for rule in rules:
        if not _touches(rule, polygon) or rule.min is None:
            continue
        if _against_all(rule, polygon):
            if rule.severity == "ignore":
                return None
            return rule.min if smallest is None else min(smallest, rule.min)
        if rule.severity != "ignore":
            smallest = rule.min if smallest is None else min(smallest, rule.min)
    return None


def _against_all(rule: Rule, polygon: RuleSubject) -> bool:
    """Whether ``rule`` holds between the folded ``polygon`` and any item: one scope matches it and the other
    is ``All``."""
    first = fold_selector(rule.selector_a)
    second = None if rule.selector_b is None else fold_selector(rule.selector_b)
    if second is None or second.op == "all":
        return first.matches(polygon)
    return first.op == "all" and second.matches(polygon)


def zone_clearances(board: Board, design: Design, ledger: Ledger) -> Board:
    """``board`` with the clearance of each zone set to the smallest Altium clearance that governs a pair of
    its polygon (B6, ``governing_clearance``)."""
    rules = _governing(design.rules.rules if design.rules is not None else ())
    if not rules or not board.zones:
        return board
    nets = _nets(design)
    zones: list[Zone] = []
    for zone in board.zones:
        name, netclass = nets.get(zone.net_id or "", (None, None))
        polygon = fold_subject(RuleSubject("zone", net=name, netclass=netclass))
        clearance = governing_clearance(rules, polygon)
        if clearance is None:
            ledger.change("zone", zone.id, NO_CLEARANCE)
            zones.append(zone)
            continue
        if clearance != zone.settings.clearance:
            ledger.change("zone", zone.id, CLEARANCE_FROM_RULES)
        settings = dataclasses.replace(zone.settings, clearance=clearance)
        zones.append(dataclasses.replace(zone, settings=settings))
    return dataclasses.replace(board, zones=tuple(zones))


__all__ = [
    "CLEARANCE_FROM_RULES",
    "PAD_CONNECTIONS",
    "ZONE_CONNECTIONS",
    "board_styles",
    "connect_zones",
    "governing_clearance",
    "zone_clearances",
]

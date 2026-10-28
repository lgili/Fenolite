# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Polygon Connect Style rules of a PCB document: read, resolved for a pad or a via, and lowered from the
zones of a model (change c0215; ``docs/formats/altium/pcb-pour.md``, inputs I5 to I7 and "Polygon Connect
Style records").

A record maps only in one of the two forms the public documents hold: the Simple form (five keys, one
setting for pads and vias) or the Advanced form (the five keys behind ``THPAD.``, ``SMDPAD.`` and
``VIA.``). Anything else, an Auto mode or a value outside the known ones among it, keeps the record with a
``reason``: a pour that such a record could govern is refused, never guessed (``H-A-POUR-CONNECT``).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal

from fenolite.backends.altium.read.proptext import parse_length
from fenolite.backends.altium.read.scope import parse_scope
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm, Udeg
from fenolite.model.board import Board, Zone, ZoneSettings
from fenolite.model.rules import LEAF_OPS, RuleSubject, Selector

ConnectKind = Literal["relief", "direct", "none"]
ObjectKind = Literal["th_pad", "smd_pad", "via"]

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-POUR-CONNECT", "H-A-POUR-RELIEF"))
"""The record form of a Polygon Connect Style rule and what its settings mean for a pour (change c0215),
until a round of kit group K6 settles them."""
KIND_NUMBER = 20
"""The rule-kind number of Polygon Connect Style in ``Rules6`` (``pcb-copper.md``, "Rules")."""
RULE_KIND = "PolygonConnect"
SETTING_KEYS = ("CONNECTSTYLE", "RELIEFCONDUCTORWIDTH", "RELIEFENTRIES", "POLYGONRELIEFANGLE", "AIRGAPWIDTH")
"""The keys of one setting, in the order the saved records hold them."""
PREFIXES: tuple[tuple[str, ObjectKind], ...] = (("THPAD.", "th_pad"), ("SMDPAD.", "smd_pad"), ("VIA.", "via"))
"""The prefixes of the Advanced form, in order, and the object each one sets."""
STYLES: Mapping[str, ConnectKind] = {"Relief": "relief", "Direct": "direct", "NoConnect": "none"}
"""The values of ``CONNECTSTYLE``. ``Relief`` and ``Direct`` are in the public records; ``NoConnect`` is
Fenolite's reading of the third style, which no public record holds (``H-A-POUR-CONNECT``)."""
ANGLES: Mapping[str, Udeg] = {"90 Angle": 0, "45 Angle": 45_000_000}
"""``POLYGONRELIEFANGLE`` → the direction of the first conductor: 0° for the 90° angle, 45° for the 45°
angle (input I6)."""
ENTRIES = (2, 4)
HEADER = ("RULEKIND", "NETSCOPE", "LAYERKIND", "SCOPE1EXPRESSION", "SCOPE2EXPRESSION", "NAME", "ENABLED",
          "PRIORITY", "COMMENT", "UNIQUEID", "DEFINEDBYLOGICALDOCUMENT")  # fmt: skip

Field = tuple[str, str]
NOT_LOWERED = "altium.not-lowered"


@dataclass(frozen=True, slots=True)
class Connection:
    """How one pad or via of the polygon's net joins the pour: the style, and for a relief its conductors
    (their width, their count, the direction of the first) and the air gap, which No Connect keeps too."""

    style: ConnectKind
    conductor_width: Nm
    conductors: int
    angle: Udeg
    air_gap: Nm


@dataclass(frozen=True, slots=True)
class ConnectStyle:
    """One Polygon Connect Style record: its name, its priority (1 governs), its two scopes (``None`` for
    a scope outside the closed grammar of ``read.scope``), whether it is of the Advanced form, and one
    connection per object kind. ``reason`` is not empty when the record could not be read: a pour it could
    govern is refused with that reason."""

    name: str
    priority: int
    scope1: Selector | None
    scope2: Selector | None
    th_pad: Connection | None
    smd_pad: Connection | None
    via: Connection | None
    advanced: bool = False
    reason: str = ""

    def connection(self, kind: ObjectKind) -> Connection | None:
        return {"th_pad": self.th_pad, "smd_pad": self.smd_pad, "via": self.via}[kind]


def _setting(values: Mapping[str, str], prefix: str) -> tuple[Connection | None, str]:
    style = STYLES.get(values.get(prefix + "CONNECTSTYLE", ""))
    width = parse_length(values.get(prefix + "RELIEFCONDUCTORWIDTH", ""))
    entries = values.get(prefix + "RELIEFENTRIES", "")
    angle = ANGLES.get(values.get(prefix + "POLYGONRELIEFANGLE", ""))
    gap = parse_length(values.get(prefix + "AIRGAPWIDTH", ""))
    if style is None:
        return None, "connect-style"
    if width is None or gap is None or angle is None or not entries.isdigit() or int(entries) not in ENTRIES:
        return None, "connect-value"
    if width <= 0 or gap < 0:
        return None, "connect-value"
    return Connection(style, width, int(entries), angle, gap), ""


def _scope(text: str | None) -> Selector | None:
    found = parse_scope(text or "")
    return found if isinstance(found, Selector) else None


def read_connect_style(fields: Sequence[tuple[str, str | None]]) -> ConnectStyle | None:
    """The record ``fields`` as a ``ConnectStyle``, ``None`` when it is not an enabled Polygon Connect
    Style record."""
    values = {key: value or "" for key, value in fields}
    if values.get("RULEKIND") != RULE_KIND or values.get("ENABLED", "TRUE").upper() != "TRUE":
        return None
    name = values.get("NAME", "")
    priority_text = values.get("PRIORITY", "")
    priority = int(priority_text) if priority_text.isdigit() and int(priority_text) >= 1 else 0
    scope1, scope2 = _scope(values.get("SCOPE1EXPRESSION")), _scope(values.get("SCOPE2EXPRESSION"))
    keys = [key for key, _ in fields]
    own = [key for key in keys[keys.index("RULEKIND") :] if key not in HEADER] if "RULEKIND" in keys else []
    advanced_keys = [prefix + key for prefix, _ in PREFIXES for key in SETTING_KEYS]
    reason = ""
    if priority == 0:
        reason = "connect-priority"
    elif (values.get("NETSCOPE"), values.get("LAYERKIND")) != ("AnyNet", "SameLayer"):
        reason = "connect-header"
    if own == list(SETTING_KEYS):
        one, problem = _setting(values, "")
        return ConnectStyle(name, priority, scope1, scope2, one, one, one, False, reason or problem)
    if own == advanced_keys:
        found: dict[ObjectKind, Connection | None] = {}
        for prefix, kind in PREFIXES:
            setting, problem = _setting(values, prefix)
            found[kind] = setting
            reason = reason or problem
        return ConnectStyle(
            name, priority, scope1, scope2, found["th_pad"], found["smd_pad"], found["via"], True, reason
        )
    return ConnectStyle(name, priority, scope1, scope2, None, None, None, False, reason or "connect-keys")


def read_connect_styles(records: Sequence[Sequence[tuple[str, str | None]]]) -> tuple[ConnectStyle, ...]:
    """The enabled Polygon Connect Style records of ``records`` (the field lists of a document's rules),
    the governing one first: by priority, then by name."""
    found = [style for style in (read_connect_style(fields) for fields in records) if style is not None]
    return tuple(sorted(found, key=lambda style: (style.priority, style.name)))


def _fold(selector: Selector) -> Selector:
    if selector.op in LEAF_OPS and selector.op not in ("area", "diff_pair"):
        return replace(selector, value=selector.value.casefold())
    if selector.items:
        return replace(selector, items=tuple(_fold(item) for item in selector.items))
    return selector


def _fold_subject(subject: RuleSubject) -> RuleSubject:
    def fold(text: str | None) -> str | None:
        return None if text is None else text.casefold()

    return replace(
        subject,
        item_kind=subject.item_kind.casefold(),
        net=fold(subject.net),
        netclass=fold(subject.netclass),
        ref=fold(subject.ref),
        layer=fold(subject.layer),
    )


def governing_connection(
    styles: Sequence[ConnectStyle], item: RuleSubject, polygon: RuleSubject, kind: ObjectKind
) -> Connection | str:
    """The connection of the pad or via ``item`` (of the object kind ``kind``) to the polygon ``polygon``:
    that of the first record of ``styles`` whose two scopes match the pair in either order, names compared
    without case. A string is the reason the pour is refused: a record before the governing one whose
    scope the grammar does not hold (``connect-scope``), a governing record that could not be read (its
    ``reason``), or no record that matches (``connect-none``)."""
    a, b = _fold_subject(item), _fold_subject(polygon)
    for style in styles:
        if style.scope1 is None or style.scope2 is None:
            return "connect-scope"
        first, second = _fold(style.scope1), _fold(style.scope2)
        if not ((first.matches(a) and second.matches(b)) or (first.matches(b) and second.matches(a))):
            continue
        if style.reason:
            return style.reason
        found = style.connection(kind)
        return found if found is not None else "connect-value"
    return "connect-none"


# --- lowering from the zones of a model (Decision 11) ----------------------------------------------------

RELIEF_CONDUCTORS = 4
"""The conductors of a relief lowered from a zone: KiCad's thermal relief has four spokes."""
RELIEF_ANGLE: Udeg = 0
"""The direction of the first conductor of a lowered relief: 0°, the 90° angle (Fenolite's choice; a
zone of the model holds no spoke angle)."""


@dataclass(frozen=True, slots=True)
class LoweredStyle:
    """One Polygon Connect Style rule to write: its name, its first scope (the second is ``All``) and its
    three settings."""

    name: str
    scope: str
    th_pad: Connection
    smd_pad: Connection
    via: Connection


def _settings_key(settings: ZoneSettings) -> tuple[str, Nm, Nm, Nm]:
    found = settings.effective()
    return (found.connection, found.thermal_gap, found.thermal_spoke_width, found.clearance)


def zone_connections(settings: ZoneSettings) -> tuple[Connection, Connection, Connection]:
    """The settings for through-hole pads, SMD pads and vias of a zone's ``settings``: a thermal relief is
    Relief Connect with four conductors at 0°, the spoke width and the thermal gap; ``thru_hole_only``
    relieves through-hole pads only; ``solid`` is Direct Connect; ``none`` is No Connect with the zone's
    clearance as the air gap. Vias are Direct Connect, as a KiCad zone joins them."""
    spoke, gap = settings.thermal_spoke_width, settings.thermal_gap
    relief = Connection("relief", spoke, RELIEF_CONDUCTORS, RELIEF_ANGLE, gap)
    direct = Connection("direct", spoke, RELIEF_CONDUCTORS, RELIEF_ANGLE, gap)
    apart = Connection("none", spoke, RELIEF_CONDUCTORS, RELIEF_ANGLE, settings.clearance)
    match settings.connection:
        case "thermal":
            return relief, relief, direct
        case "thru_hole_only":
            return relief, direct, direct
        case "solid":
            return direct, direct, direct
        case "none":
            return apart, apart, direct


def lower_zone_styles(zones: Sequence[Zone]) -> tuple[tuple[LoweredStyle, ...], tuple[Issue, ...]]:
    """The Polygon Connect Style rules of a computed document (change c0215, Decision 11): one rule scoped
    ``InNet('<net>')`` per net of ``zones`` (whose ``net_id`` holds the net's name), from its zone of
    highest priority (then the lowest id), in net-name order, and one ``All`` rule from ``ZoneSettings()``
    last. Each other zone of a net whose settings differ from that zone's is one ``altium.not-lowered``
    with ``where`` ``zone/<id>``. Zones without a net take no rule of their own."""
    by_net: dict[str, list[Zone]] = {}
    for zone in zones:
        if zone.net_id is not None:
            by_net.setdefault(zone.net_id, []).append(zone)
    styles: list[LoweredStyle] = []
    problems: list[Issue] = []
    for net in sorted(by_net):
        ordered = sorted(by_net[net], key=lambda z: (-z.priority, z.id))
        chosen = ordered[0]
        key = _settings_key(chosen.settings)
        for other in ordered[1:]:
            if _settings_key(other.settings) != key:
                problems.append(
                    Issue(
                        NOT_LOWERED,
                        "info",
                        f"the connection settings of zone {other.id} differ from those of {chosen.id}, which "
                        f"give the Polygon Connect Style rule of the net {net!r}",
                        where=f"zone/{other.id}",
                    )
                )
        th, smd, via = zone_connections(chosen.settings.effective())
        styles.append(LoweredStyle(f"PolygonConnect_net_{net}", f"InNet('{net}')", th, smd, via))
    th, smd, via = zone_connections(ZoneSettings())
    styles.append(LoweredStyle("PolygonConnect", "All", th, smd, via))
    return tuple(styles), tuple(problems)


def connect_fields(text: str) -> tuple[Field, ...]:
    """The keys of a board's ``polygon_connect`` pair (``adapter.rules.connect_texts``) as fields."""
    return tuple((key, value) for key, _, value in (item.partition("=") for item in text.split("|")))


def kept_mapping(records: Sequence[Sequence[Field]]) -> tuple[bool, tuple[tuple[str, str], ...]]:
    """Whether the Polygon Connect Style records of a read document map exactly, and (name, reason) of each
    that does not: an enabled record maps when Fenolite reads its style and both scopes; a disabled one
    governs nothing and maps as it is."""
    problems: list[tuple[str, str]] = []
    for fields in records:
        style = read_connect_style(fields)
        if style is None:
            continue
        reason = style.reason or ("connect-scope" if style.scope1 is None or style.scope2 is None else "")
        if reason:
            problems.append((style.name, reason))
    return not problems, tuple(problems)


def pad_overrides(board: Board | None) -> tuple[Issue, ...]:
    """One ``altium.not-lowered`` (info, ``where`` ``pad/<id>``) per pad with its own ``zone_connection`` on a
    board that holds a zone (Decision 11): the override is not written, and the Polygon Connect Style rule of
    the pad's net governs the pour."""
    if board is None or not board.zones:
        return ()
    return tuple(
        Issue(
            NOT_LOWERED,
            "info",
            f"the zone connection of pad {pad.id} ({pad.zone_connection}) is not written: the Polygon "
            "Connect Style rule of its net governs the pour",
            where=f"pad/{pad.id}",
        )
        for footprint in board.footprints
        for pad in footprint.pads
        if pad.zone_connection is not None
    )


def setting_fields(prefix: str, connection: Connection, mil: Callable[[Nm], str]) -> list[Field]:
    """The five keys of one setting behind ``prefix``; ``mil`` turns nanometres into the mil text of a
    record (``pcbdoc._mil``)."""
    style = next(text for text, kind in STYLES.items() if kind == connection.style)
    angle = next(text for text, value in ANGLES.items() if value == connection.angle)
    return [
        (prefix + "CONNECTSTYLE", style),
        (prefix + "RELIEFCONDUCTORWIDTH", mil(connection.conductor_width)),
        (prefix + "RELIEFENTRIES", str(connection.conductors)),
        (prefix + "POLYGONRELIEFANGLE", angle),
        (prefix + "AIRGAPWIDTH", mil(connection.air_gap)),
    ]


def style_keys(style: LoweredStyle, mil: Callable[[Nm], str]) -> list[Field]:
    """The keys of a lowered rule after the common rule keys: the Advanced form."""
    return [
        *setting_fields("THPAD.", style.th_pad, mil),
        *setting_fields("SMDPAD.", style.smd_pad, mil),
        *setting_fields("VIA.", style.via, mil),
    ]


__all__ = [
    "ANGLES",
    "EVIDENCE",
    "KIND_NUMBER",
    "PREFIXES",
    "RULE_KIND",
    "SETTING_KEYS",
    "STYLES",
    "ConnectKind",
    "ConnectStyle",
    "Connection",
    "LoweredStyle",
    "ObjectKind",
    "governing_connection",
    "connect_fields",
    "kept_mapping",
    "lower_zone_styles",
    "pad_overrides",
    "read_connect_style",
    "read_connect_styles",
    "setting_fields",
    "style_keys",
    "zone_connections",
]

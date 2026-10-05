# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Zone settings of KiCad boards: the codec of the setting children of a ``zone`` and of a pad's
``zone_connect``.

Facts, forms per major and the defaults: ``docs/formats/kicad/board.md``, "Zone settings". The reader
(``pcb``) projects the children ``locked``, ``connect_pads``, ``min_thickness`` and ``fill`` with
``project_settings`` and keeps as written every child that ``emit_settings`` does not reproduce for the
major of the file; the writer emits them for its target. ``merge_zones`` merges the zones of a design
script with those of an existing board for the layout lens. This module imports neither ``pcb`` nor
``_fpmap``: both call it.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from fractions import Fraction
from types import MappingProxyType
from typing import Protocol, get_args

from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node
from fenolite.core.errors import Issue, Severity
from fenolite.core.ids import FENOLITE_NS, derived_id
from fenolite.core.units import format_angle, parse_angle
from fenolite.model.board import (
    FootprintInstance,
    HatchBorder,
    IslandRemoval,
    Zone,
    ZoneConnection,
    ZoneHatch,
    ZoneSettings,
    ZoneSmoothing,
)
from fenolite.model.design import Design

CONNECT_ATOMS: Mapping[ZoneConnection, str | None] = MappingProxyType(
    {"thermal": None, "solid": "yes", "none": "no", "thru_hole_only": "thru_hole_only"}
)
"""The atom of ``connect_pads`` per connection; thermal reliefs write no atom."""
PAD_CONNECT_CODES: Mapping[int, ZoneConnection] = MappingProxyType(
    {0: "none", 1: "thermal", 2: "solid", 3: "thru_hole_only"}
)
"""``(zone_connect N)`` of a pad."""
ISLAND_CODES: Mapping[int, IslandRemoval] = MappingProxyType({0: "always", 1: "never", 2: "below_area"})
"""``(island_removal_mode N)``."""
SETTING_HEADS: tuple[str, ...] = ("locked", "connect_pads", "min_thickness", "fill")
"""The zone children this module models, in the order KiCad writes them."""
MM2 = 10**12
"""Square nanometres in a square millimetre."""
_SMOOTHINGS: frozenset[str] = frozenset(get_args(ZoneSmoothing)) - {"none"}
_BORDERS: frozenset[str] = frozenset(get_args(HatchBorder))
_ATOM_CONNECTIONS: Mapping[str | None, ZoneConnection] = MappingProxyType(
    {atom: connection for connection, atom in CONNECT_ATOMS.items()}
)
_ISLAND_NUMBERS: Mapping[IslandRemoval, int] = MappingProxyType({v: k for k, v in ISLAND_CODES.items()})
_PAD_NUMBERS: Mapping[ZoneConnection, int] = MappingProxyType({v: k for k, v in PAD_CONNECT_CODES.items()})


def _node(head: str, *children: Node | Atom) -> Node:
    return Node(Atom.symbol(head), children)


HATCH_EDGE: Node = _node("hatch", Atom.symbol("edge"), Atom.from_nm(500_000))
"""``(hatch edge 0.5)``: the outline display KiCad gives a new zone (cosmetic, not modelled)."""


@dataclass(frozen=True)
class SettingsRead:
    """What the setting children of one zone say.

    ``reasons`` maps the head of each child that cannot be a modelled slot to the reason (repeated, or an
    atom, child or value outside the model); ``inexact`` names those whose reason is a length or an angle
    that is not a whole number of nanometres or microdegrees. Values that could be read are projected
    all the same; a value that could not keeps its default.
    """

    settings: ZoneSettings
    filled: bool
    locked: bool
    reasons: Mapping[str, str]
    inexact: frozenset[str] = frozenset()


class _Bad(Exception):
    """A value outside the model; ``inexact`` when it is a valid but inexact length or angle."""

    def __init__(self, message: str, *, inexact: bool = False) -> None:
        super().__init__(message)
        self.inexact = inexact


def _single(node: Node) -> Atom:
    atoms = node.atoms()
    if len(atoms) != 1 or node.nodes():
        raise _Bad(f"{node.name!r} takes one value")
    return atoms[0]


def _length(node: Node) -> int:
    atom = _single(node)
    try:
        return atom.to_nm(exact=True)
    except ValueError as error:
        try:
            atom.to_nm(exact=False)
        except ValueError:
            raise _Bad(f"{node.name}: {error}") from None
        raise _Bad(f"{node.name}: {error}", inexact=True) from None


def _angle(node: Node) -> int:
    atom = _single(node)
    if atom.kind != AtomKind.NUMBER:
        raise _Bad(f"{node.name}: {atom.text!r} is not an angle")
    try:
        return parse_angle(atom.text, default_unit="deg")
    except ValueError as error:
        raise _Bad(f"{node.name}: {error}", inexact="not representable" in str(error)) from None


def _integer(node: Node) -> int:
    atom = _single(node)
    try:
        return atom.to_int()
    except ValueError:
        raise _Bad(f"{node.name}: {atom.text!r} is not an integer") from None


def _ratio(node: Node) -> str:
    atom = _single(node)
    if atom.kind != AtomKind.NUMBER:
        raise _Bad(f"{node.name}: {atom.text!r} is not a number")
    return atom.text


def area_from_mm2(text: str) -> int:
    """A decimal number of square millimetres as whole square nanometres; ``ValueError`` when it is not a
    whole number of them."""
    area = Fraction(text) * MM2
    if area.denominator != 1 or area < 0:
        raise ValueError(f"{text} mm² is not a whole, non-negative number of square nanometres")
    return area.numerator


def area_to_mm2(nm2: int) -> str:
    """Square nanometres as the shortest exact decimal of square millimetres (``2500000000000`` → ``2.5``)."""
    whole, rest = divmod(nm2, MM2)
    digits = f"{rest:012d}".rstrip("0")
    return f"{whole}.{digits}" if digits else str(whole)


def _area(node: Node) -> int:
    atom = _single(node)
    if atom.kind != AtomKind.NUMBER:
        raise _Bad(f"{node.name}: {atom.text!r} is not an area")
    try:
        return area_from_mm2(atom.text)
    except (ValueError, ZeroDivisionError) as error:
        raise _Bad(f"{node.name}: {error}") from None


def _symbol(node: Node, allowed: frozenset[str]) -> str:
    atom = _single(node)
    if atom.value not in allowed:
        raise _Bad(f"{node.name}: unknown value {atom.text!r}")
    return atom.value


class _Projection:
    """The values read so far, and why a child cannot be a modelled slot."""

    def __init__(self) -> None:
        self.settings = ZoneSettings()
        self.filled = False
        self.locked = False
        self.reasons: dict[str, str] = {}
        self.inexact: set[str] = set()

    def bad(self, head: str, error: _Bad) -> None:
        self.reasons.setdefault(head, str(error))
        if error.inexact:
            self.inexact.add(head)

    def set(self, **changes: object) -> None:
        self.settings = replace(self.settings, **changes)  # type: ignore[arg-type]

    def hatch(self, **changes: object) -> None:
        self.settings = replace(self.settings, hatch=replace(self.settings.hatch, **changes))  # type: ignore[arg-type]

    # -- one child each

    def locked_child(self, node: Node) -> None:
        values = [a.value for a in node.atoms()]
        if node.nodes() or values not in (["yes"], ["no"]):
            self.bad("locked", _Bad(f"locked: unknown form {' '.join(values) or '(list)'}"))
            return
        self.locked = values == ["yes"]

    def connect_pads(self, node: Node) -> None:
        atoms = [a.value for a in node.atoms()]
        key = atoms[0] if len(atoms) == 1 else None
        if len(atoms) > 1 or key not in _ATOM_CONNECTIONS:
            self.bad("connect_pads", _Bad(f"connect_pads: unknown connection {' '.join(atoms)!r}"))
        else:
            self.set(connection=_ATOM_CONNECTIONS[key])
        seen = False
        for child in node.nodes():
            try:
                if child.name != "clearance" or seen:
                    raise _Bad(f"connect_pads: unexpected child {child.name!r}")
                seen = True
                self.set(clearance=_length(child))
            except _Bad as error:
                self.bad("connect_pads", error)

    def min_thickness(self, node: Node) -> None:
        try:
            self.set(min_thickness=_length(node))
        except _Bad as error:
            self.bad("min_thickness", error)

    def fill(self, node: Node) -> None:
        atoms = [a.value for a in node.atoms()]
        if atoms == ["yes"]:
            self.filled = True
        elif atoms:
            self.bad("fill", _Bad(f"fill: unknown atom {' '.join(atoms)!r}"))
        seen: set[str] = set()
        for child in node.nodes():
            try:
                if child.name in seen:
                    raise _Bad(f"fill: {child.name!r} is repeated")
                seen.add(child.name)
                self.fill_child(child)
            except _Bad as error:
                self.bad("fill", error)

    def fill_child(self, child: Node) -> None:
        head = child.name
        if head == "mode":
            _symbol(child, frozenset({"hatch"}))
            self.set(fill_mode="hatched")
        elif head == "thermal_gap":
            self.set(thermal_gap=_length(child))
        elif head == "thermal_bridge_width":
            self.set(thermal_spoke_width=_length(child))
        elif head == "smoothing":
            self.set(smoothing=_symbol(child, _SMOOTHINGS))
        elif head == "radius":
            self.set(smoothing_radius=_length(child))
        elif head == "island_removal_mode":
            code = _integer(child)
            if code not in ISLAND_CODES:
                raise _Bad(f"island_removal_mode: unknown mode {code}")
            self.set(island_removal=ISLAND_CODES[code])
        elif head == "island_area_min":
            self.set(min_island_area=_area(child))
        elif head == "hatch_thickness":
            self.hatch(thickness=_length(child))
        elif head == "hatch_gap":
            self.hatch(gap=_length(child))
        elif head == "hatch_orientation":
            self.hatch(orientation=_angle(child))
        elif head == "hatch_smoothing_level":
            self.hatch(smoothing_level=_integer(child))
        elif head == "hatch_smoothing_value":
            self.hatch(smoothing_value=_ratio(child))
        elif head == "hatch_border_algorithm":
            self.hatch(border=_symbol(child, _BORDERS))
        elif head == "hatch_min_hole_area":
            self.hatch(min_hole_area=_ratio(child))
        else:
            raise _Bad(f"fill: unknown child {head!r}")


def project_settings(children: Sequence[Node], *, major: int) -> SettingsRead:
    """The settings that the setting children of one zone hold (other children are ignored).

    A head that occurs twice is projected from its first occurrence and gets the reason ``repeated``.
    ``major`` is the major of the file; the forms differ per major only in which children are written
    (``emit_settings``), so the projection itself does not depend on it.
    """
    del major
    found = _Projection()
    seen: set[str] = set()
    for child in children:
        head = child.name
        if head not in SETTING_HEADS:
            continue
        if head in seen:
            found.reasons.setdefault(head, f"{head!r} is repeated")
            continue
        seen.add(head)
        if head == "locked":
            found.locked_child(child)
        elif head == "connect_pads":
            found.connect_pads(child)
        elif head == "min_thickness":
            found.min_thickness(child)
        else:
            found.fill(child)
    return SettingsRead(
        found.settings,
        found.filled,
        found.locked,
        MappingProxyType(dict(found.reasons)),
        frozenset(found.inexact),
    )


def _angle_atom(udeg: int) -> Atom:
    return Atom(format_angle(udeg, "deg")[: -len("deg")], AtomKind.NUMBER)


def _number(text: str) -> Atom:
    return Atom(text, AtomKind.NUMBER)


def emit_settings(settings: ZoneSettings, *, filled: bool, locked: bool, major: int) -> dict[str, Node]:
    """The setting children of a zone in the form that KiCad ``major`` writes: ``connect_pads``,
    ``min_thickness`` and ``fill`` always, ``locked`` only for a locked zone.

    For a major below 10 the island children are written only when islands are not always removed; from
    10 on the mode is always written, and the area only for ``below_area``.
    """
    atom = CONNECT_ATOMS[settings.connection]
    connect: list[Node | Atom] = [] if atom is None else [Atom.symbol(atom)]
    connect.append(_node("clearance", Atom.from_nm(settings.clearance)))
    fill: list[Node | Atom] = [Atom.symbol("yes")] if filled else []
    hatched = settings.fill_mode == "hatched"
    if hatched:
        fill.append(_node("mode", Atom.symbol("hatch")))
    fill.append(_node("thermal_gap", Atom.from_nm(settings.thermal_gap)))
    fill.append(_node("thermal_bridge_width", Atom.from_nm(settings.thermal_spoke_width)))
    if settings.smoothing != "none":
        fill.append(_node("smoothing", Atom.symbol(settings.smoothing)))
        fill.append(_node("radius", Atom.from_nm(settings.smoothing_radius)))
    mode = _node("island_removal_mode", Atom.integer(_ISLAND_NUMBERS[settings.island_removal]))
    area = _node("island_area_min", _number(area_to_mm2(settings.min_island_area)))
    if major >= 10:
        fill.append(mode)
        if settings.island_removal == "below_area":
            fill.append(area)
    elif settings.island_removal != "always":
        fill += [mode, area]
    if hatched:
        hatch: ZoneHatch = settings.hatch
        fill.append(_node("hatch_thickness", Atom.from_nm(hatch.thickness)))
        fill.append(_node("hatch_gap", Atom.from_nm(hatch.gap)))
        fill.append(_node("hatch_orientation", _angle_atom(hatch.orientation)))
        if hatch.smoothing_level > 0:
            fill.append(_node("hatch_smoothing_level", Atom.integer(hatch.smoothing_level)))
            fill.append(_node("hatch_smoothing_value", _number(hatch.smoothing_value)))
        fill.append(_node("hatch_border_algorithm", Atom.symbol(hatch.border)))
        fill.append(_node("hatch_min_hole_area", _number(hatch.min_hole_area)))
    out: dict[str, Node] = {}
    if locked:
        out["locked"] = _node("locked", Atom.symbol("yes"))
    out["connect_pads"] = _node("connect_pads", *connect)
    out["min_thickness"] = _node("min_thickness", Atom.from_nm(settings.min_thickness))
    out["fill"] = _node("fill", *fill)
    return out


def setting_parts(settings: ZoneSettings, *, filled: bool, locked: bool) -> dict[str, tuple[object, ...]]:
    """The model values that each setting child stands for, by head."""
    return {
        "locked": (locked,),
        "connect_pads": (settings.connection, settings.clearance),
        "min_thickness": (settings.min_thickness,),
        "fill": (
            filled,
            settings.fill_mode,
            settings.thermal_gap,
            settings.thermal_spoke_width,
            settings.smoothing,
            settings.smoothing_radius,
            settings.island_removal,
            settings.min_island_area,
            settings.hatch,
        ),
    }


DEFAULT_PARTS: Mapping[str, tuple[object, ...]] = MappingProxyType(
    setting_parts(ZoneSettings(), filled=False, locked=False)
)
"""What the reader gives a zone for each absent setting child."""


def projection_differences(
    child: Node, settings: ZoneSettings, *, filled: bool, locked: bool, major: int
) -> tuple[str, ...]:
    """The model fields (``settings``, ``filled``, ``locked``) whose value differs from what the opaque
    setting child ``child`` holds; empty when the child still stands for the model."""
    head = child.name
    read = project_settings([child], major=major)
    theirs = setting_parts(read.settings, filled=read.filled, locked=read.locked)[head]
    mine = setting_parts(settings, filled=filled, locked=locked)[head]
    if theirs == mine:
        return ()
    if head == "locked":
        return ("locked",)
    if head != "fill":
        return ("settings",)
    out: list[str] = []
    if theirs[1:] != mine[1:]:
        out.append("settings")
    if theirs[0] != mine[0]:
        out.append("filled")
    return tuple(out)


def with_fill_flag(child: Node, filled: bool) -> Node | None:
    """An opaque ``fill`` child with its ``yes`` atom set from the model and its lists as written, or
    ``None`` when its atoms are not the plain form (no atom, or ``yes`` alone)."""
    atoms = [a.value for a in child.atoms()]
    if child.name != "fill" or atoms not in ([], ["yes"]):
        return None
    flag: list[Node | Atom] = [Atom.symbol("yes")] if filled else []
    return child.with_children([*flag, *child.nodes()])


# --- pads -------------------------------------------------------------------------------------------


def read_pad_connect(node: Node) -> ZoneConnection | None:
    """The connection of a pad's ``(zone_connect N)``, or ``None`` when N is not one of 0 to 3."""
    atoms = node.atoms()
    if len(atoms) != 1 or node.nodes() or atoms[0].kind != AtomKind.NUMBER:
        return None
    try:
        return PAD_CONNECT_CODES.get(atoms[0].to_int())
    except ValueError:
        return None


def pad_connect_node(connection: ZoneConnection) -> Node:
    """``(zone_connect N)`` for a pad's connection."""
    return _node("zone_connect", Atom.integer(_PAD_NUMBERS[connection]))


# --- script zones across rebuilds (layout-lens, "Zones declared in the script") -----------------------

MERGE_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "kicad.zone.forced": "warning",
        "kicad.zone.orphan": "warning",
        "kicad.zone.overridden": "info",
    }
)
"""The closed set of codes that ``merge_zones`` reports."""
OVERRIDE_HINT = "lock the zone in the script, edit it in KiCad, or re-run with --discard-layout"
SCRIPT_BACKEND = "dsl"
COMPARED: tuple[str, ...] = ("outline", "layers", "net", "priority", "locked", "settings")
"""What a script zone and its board zone are compared by, in the order the issues name them."""


def _zone_uuid(zone: Zone) -> str:
    """The KiCad uuid the board writer gives ``zone`` (the rule of ``pcb.kicad_uuid``, which this module
    cannot import)."""
    native = zone.native_ids.get("kicad")
    return native if native is not None else str(uuid.uuid5(FENOLITE_NS, f"kicad-out:{zone.id}"))


def script_zone_uuid(name: str) -> str:
    """The KiCad uuid of the zone that a design script declares under ``name``: the writer's uuid of a
    zone with the id ``derived_id("zon", "dsl", "zone:<name>")``. A board zone that carries the uuid of
    its own name was written by a script."""
    return str(uuid.uuid5(FENOLITE_NS, f"kicad-out:{derived_id('zon', SCRIPT_BACKEND, f'zone:{name}')}"))


@dataclass(frozen=True)
class ZoneMerge:
    """The zones of a rebuilt board.

    ``zones`` holds every zone to consider, in order: the board's zones that stay, then the added ones in
    name order. ``decided`` holds the ids of those whose net is already a net of the built design (kept,
    forced and added zones); every other zone is a board zone that the script never declared, and follows
    its net as the caller decides. ``kept``, ``forced``, ``added`` and ``removed`` are zone names.
    """

    zones: tuple[Zone, ...]
    issues: tuple[Issue, ...]
    kept: tuple[str, ...] = ()
    forced: tuple[str, ...] = ()
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    decided: frozenset[str] = frozenset()


def _merge_issue(code: str, message: str, where: str, hint: str = "") -> Issue:
    return Issue(code, MERGE_ISSUE_CODES[code], message, where=where, hint=hint)


def _compared(zone: Zone, nets: Mapping[str, str]) -> dict[str, object]:
    return {
        "outline": zone.outline,
        "layers": zone.layers,
        "net": nets.get(zone.net_id or "", ""),
        "priority": zone.priority,
        "locked": zone.locked,
        "settings": zone.settings.effective(),
    }


def merge_zones(built: Design, board: Design) -> ZoneMerge:
    """Merge the zones that the script declares (``built``) with those of the existing ``board``.

    A board zone matches a built zone by KiCad uuid, never by name. The board zone wins and is kept with
    its slots (``kicad.zone.overridden`` when the script differs), unless the built zone is locked and
    differs: it then replaces the board zone and takes its fills (``kicad.zone.forced``). A built zone
    without a match is added. A board zone without a match that carries the uuid of its own name was
    written for a ``zone()`` call that is gone, and is removed (``kicad.zone.orphan``). Any other board
    zone is returned as it is.
    """
    built_zones = built.board.zones if built.board is not None else ()
    board_zones = board.board.zones if board.board is not None else ()
    built_nets = {n.id: n.name for n in built.circuit.nets}
    built_ids = {name: net_id for net_id, name in built_nets.items()}
    board_nets = {n.id: n.name for n in board.circuit.nets}
    by_uuid = {_zone_uuid(zone): zone for zone in built_zones}
    zones: list[Zone] = []
    issues: list[Issue] = []
    kept: list[str] = []
    forced: list[str] = []
    removed: list[str] = []
    decided: set[str] = set()
    matched: set[str] = set()
    for zone in board_zones:
        native = zone.native_ids.get("kicad", "")
        script = by_uuid.get(native) if native and native not in matched else None
        if script is None:
            if native and zone.name and native == script_zone_uuid(zone.name):
                removed.append(zone.name)
                issues.append(
                    _merge_issue(
                        "kicad.zone.orphan",
                        f"zone {zone.name} (uuid {native}) is no longer declared by the script "
                        "and is removed",
                        zone.name,
                    )
                )
            else:
                zones.append(zone)
            continue
        matched.add(native)
        label = script.name or native
        mine, theirs = _compared(script, built_nets), _compared(zone, board_nets)
        differing = [what for what in COMPARED if mine[what] != theirs[what]]
        if differing and script.locked:
            replacement = replace(script, fills=zone.fills, filled=zone.filled)
            zones.append(replacement)
            decided.add(replacement.id)
            forced.append(label)
            issues.append(
                _merge_issue(
                    "kicad.zone.forced",
                    f"zone {label}: the locked zone() replaces the board's zone, whose "
                    f"{', '.join(differing)} differed",
                    label,
                )
            )
            continue
        # the board's zone stays, on the built design's net of its name (the script's net when that
        # net left the design)
        net_id = built_ids.get(str(theirs["net"]), script.net_id) if theirs["net"] else None
        zones.append(replace(zone, net_id=net_id))
        decided.add(zone.id)
        kept.append(label)
        if differing:
            issues.append(
                _merge_issue(
                    "kicad.zone.overridden",
                    f"zone {label}: the script's {', '.join(differing)} differ from the board's zone, "
                    "which is kept",
                    label,
                    OVERRIDE_HINT,
                )
            )
    new = sorted((z for z in built_zones if _zone_uuid(z) not in matched), key=lambda z: (z.name, z.id))
    zones += new
    decided |= {zone.id for zone in new}
    return ZoneMerge(
        tuple(zones),
        tuple(issues),
        tuple(kept),
        tuple(forced),
        tuple(zone.name for zone in new),
        tuple(removed),
        frozenset(decided),
    )


# --- pad zone connections of a script (design-dsl, "Pad zone connections in a build"; c0068) ---------


class PadZoneRequestLike(Protocol):
    """A request for how zones connect to pads of one part (the DSL's ``PadZoneRequest``), read by
    attribute, so this module never imports the DSL."""

    @property
    def number(self) -> str: ...

    @property
    def index(self) -> int | None: ...

    @property
    def connection(self) -> str: ...

    @property
    def locked(self) -> bool: ...


PAD_ZONE_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "kicad.pad.zone-forced": "warning",
        "kicad.pad.zone-overridden": "info",
        "kicad.pad.zone-unknown-pad": "error",
    }
)
"""The closed set of codes that ``apply_pad_connections`` and ``keep_pad_connections`` report."""
PAD_OVERRIDE_HINT = "lock the request in the script, edit the pad in KiCad, or re-run with --discard-layout"


def _pad_issue(code: str, message: str, where: str, hint: str = "") -> Issue:
    return Issue(code, PAD_ZONE_ISSUE_CODES[code], message, where=where, hint=hint)


def _ordered(requests: Sequence[PadZoneRequestLike]) -> list[PadZoneRequestLike]:
    return sorted(requests, key=lambda r: (r.number, r.index is not None, r.index or 0))


def _named_pads(
    instance: FootprintInstance, request: PadZoneRequestLike, where: str, issues: list[Issue]
) -> list[int]:
    """The positions, among the footprint's pads, of the pads that ``request`` names; none, with one
    ``kicad.pad.zone-unknown-pad``, when the footprint has no such pad."""
    carrying = [n for n, pad in enumerate(instance.pads) if pad.number == request.number]
    found = carrying if request.index is None else carrying[request.index : request.index + 1]
    if not found:
        part = where or instance.lib_ref
        which = "" if request.index is None else f" at index {request.index}"
        has = (
            f"it has {len(carrying)} pad(s) with that number"
            if carrying
            else "it has no pad with that number"
        )
        issues.append(
            _pad_issue(
                "kicad.pad.zone-unknown-pad",
                f"{part}: the zone connection request names pad {request.number!r}{which}, which the "
                f"footprint {instance.lib_ref} does not have: {has}",
                f"{part}:{request.number}",
            )
        )
    return found


def _connection(request: PadZoneRequestLike) -> ZoneConnection:
    if request.connection not in _PAD_NUMBERS:
        raise ValueError(f"unknown zone connection {request.connection!r}")
    return request.connection  # type: ignore[return-value]


def apply_pad_connections(
    instance: FootprintInstance,
    requests: Sequence[PadZoneRequestLike],
    *,
    where: str = "",
    issues: list[Issue] | None = None,
) -> FootprintInstance:
    """``instance``, a built copy of a library footprint, with ``Pad.zone_connection`` of every pad that a
    request names set to the request's value: all pads with the number, or the one at ``index`` among
    them. A pad that no request names keeps the value of the library footprint. ``where`` names the part
    in an issue (the component path). Pure."""
    found = issues if issues is not None else []
    pads = list(instance.pads)
    for request in _ordered(requests):
        connection = _connection(request)
        for position in _named_pads(instance, request, where, found):
            if pads[position].zone_connection != connection:
                pads[position] = replace(pads[position], zone_connection=connection)
    return instance if tuple(pads) == instance.pads else replace(instance, pads=tuple(pads))


def keep_pad_connections(
    kept: FootprintInstance,
    requests: Sequence[PadZoneRequestLike],
    *,
    where: str,
    issues: list[Issue] | None = None,
) -> FootprintInstance:
    """``kept``, a footprint that a rebuild keeps as the board has it, with the zone connection of every
    pad that a request names decided (``layout-lens``, "Pad zone connections across rebuilds"): a locked
    request, then the setting the pad carries on the board, then an unlocked request.

    - A pad that equals the request stays, without an issue.
    - A pad without a setting of its own takes the request's value, locked or not, without an issue.
    - A pad with another setting keeps it under an unlocked request (``kicad.pad.zone-overridden``), and
      takes the request's value under a locked one (``kicad.pad.zone-forced``).

    The ``where`` of those two issues is ``"<where>:<pad number>"``. Pure, and stable: run again on its
    own result with the same requests, it returns an equal footprint, and a locked request reports
    nothing."""
    found = issues if issues is not None else []
    pads = list(kept.pads)
    for request in _ordered(requests):
        connection = _connection(request)
        for position in _named_pads(kept, request, where, found):
            current = pads[position].zone_connection
            if current == connection:
                continue
            if current is None:
                pads[position] = replace(pads[position], zone_connection=connection)
                continue
            pad_where = f"{where}:{request.number}"
            if request.locked:
                pads[position] = replace(pads[position], zone_connection=connection)
                found.append(
                    _pad_issue(
                        "kicad.pad.zone-forced",
                        f"{where}: the locked request set the zone connection of pad {request.number} to "
                        f"{connection}; the board had {current}",
                        pad_where,
                    )
                )
            else:
                found.append(
                    _pad_issue(
                        "kicad.pad.zone-overridden",
                        f"{where}: pad {request.number} keeps the zone connection {current} of the board; "
                        f"the script asks for {connection}",
                        pad_where,
                        PAD_OVERRIDE_HINT,
                    )
                )
    return kept if tuple(pads) == kept.pads else replace(kept, pads=tuple(pads))


__all__ = [
    "CONNECT_ATOMS",
    "DEFAULT_PARTS",
    "HATCH_EDGE",
    "ISLAND_CODES",
    "MERGE_ISSUE_CODES",
    "PAD_CONNECT_CODES",
    "PAD_OVERRIDE_HINT",
    "PAD_ZONE_ISSUE_CODES",
    "SETTING_HEADS",
    "PadZoneRequestLike",
    "SettingsRead",
    "ZoneMerge",
    "apply_pad_connections",
    "area_from_mm2",
    "area_to_mm2",
    "emit_settings",
    "keep_pad_connections",
    "merge_zones",
    "pad_connect_node",
    "project_settings",
    "projection_differences",
    "read_pad_connect",
    "script_zone_uuid",
    "setting_parts",
    "with_fill_flag",
]

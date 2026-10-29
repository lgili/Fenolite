# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Role copper: the power, switch-node, ground and high-voltage copper of a placed board, generated from its
confirmed and declared net roles (change c0243, phase 1 of the router that works from electrical intent;
capability net-roles, "Role copper plan" and the requirements after it; ``docs/roles.md``, "Role copper").

``plan`` turns the roles into a ``RoleCopperPlan``: c0224 records (bands with a ``group``, net barriers,
stitching and via arrays limited to a patch) that ``backends.kicad.generate.resolve_generated`` resolves,
plain locked zones (the ground planes), pour-only rule areas (the provisional corridors of the critical
routes), clearance rules (``role.sw.*``, ``role.hv.*``) and issues. ``run`` judges the board with
``fenolite.roles.judge`` before and after the plan, which the caller applies (``apply``: this package
imports no KiCad backend), and refuses a result that judges worse (``roles.copper-worse``).

Every item has a key ``role.<kind>.<net>[.<layer>|.<n>]``; the ids derive from the keys, so a run replaces
its own items. Locked items of other nets and every ``role.corridor.*`` area are obstacles that the plan
never edits (the interface with c0244 decided by the maintainer on 2026-10-29). The defaults below are
generation parameters, not limits; each names its source (``docs/roles.md``, "Copper defaults").
"""

from __future__ import annotations

import itertools
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Any, ClassVar, cast

from fenolite.analysis.boundary import board_boundary
from fenolite.analysis.current import capacity_ma, layer_thickness
from fenolite.analysis.requirements import Requirements
from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.geometry import BBox, Thick, available_backends, convex_hull, thick_bbox, thick_closer_than
from fenolite.model.board import Keepout, Track, Zone, ZoneSettings
from fenolite.model.circuit import Net, NetClass
from fenolite.model.design import Design
from fenolite.model.rules import NetRole, RoleSet, Rule, Selector
from fenolite.roles import profile
from fenolite.roles.classify import Classified, classify
from fenolite.roles.codes import TOPOLOGICAL, issue
from fenolite.roles.kelvin import pad_name
from fenolite.roles.measure import RoleBoard, glob_escape, high_voltage_nets, power_pads
from fenolite.roles.routes import corridor_name
from fenolite.roles.spine import Edge, Obstacles, Terminal, chain, length, longest, route, slab, tree

KINDS: tuple[str, ...] = ("power", "switch_node", "ground", "high_voltage")
"""The role kinds that get copper."""
CONNECTIONS: tuple[str, ...] = ("solid", "thermal", "thru_hole_only", "none")
GROUND_FILLS: tuple[str, ...] = ("reference", "all")
DEFAULT_CONNECTION: Mapping[str, str] = {
    "power": "solid",
    "switch_node": "solid",
    "high_voltage": "solid",
    "ground": "thru_hole_only",
}
"""Solid where the role's current flows (S-0861, S-0862: a relief raises the joint's thermal resistance and
narrows the path); reliefs on through-hole ground pads only, where soldering is the risk."""
WIDEN_PERMILLE: Mapping[str, int] = {"power": 2000, "high_voltage": 1000, "switch_node": 1000, "ground": 1000}
"""How far a band widens where clearance allows: twice for power (S-0851, "thick"), not at all for a switch
node, whose copper area is a coupling plate (S-0860; ``H-G-ROLE-COPPER-SW``), nor for a high-voltage net
(any net with a distance row), whose keep-out band is a convex envelope of its copper."""
PRIORITY: Mapping[str, int] = {"switch_node": 3, "power": 2, "high_voltage": 2, "ground_band": 2, "ground": 0}
STITCH_PITCH_NM = 5_000_000
"""The pitch of the ground stitching: a Fenolite heuristic (``H-G-ROLE-COPPER-STITCH``); the method of
S-0863 (at most a twentieth of the wavelength at the highest significant frequency) is the user's."""
STITCH_MIN_VIAS = 2
"""At least two vias per joined piece, so no piece hangs on one point (S-0863)."""
DEFAULT_CLEARANCE_NM = 200_000
"""The clearance of a net whose class sets none: KiCad's default class clearance."""
DEFAULT_VIA = (600_000, 300_000)
POUR_GRID_NM = 100_000
"""The grid of the simulated pour that judges the result: a switch node keeps its victims one cell further
away, since a simulated fill may reach half a cell past its zone's outline."""
MAX_LEG_ORDERS_LEGS = 4
"""A hot loop of at most this many legs is routed in every order of its legs, the best kept (all legs
routed, then the shortest): the first leg routed must not take the room of another."""
LANDING_STEPS = 12
"""How many pitches a via landing may move outward from its terminal looking for room."""
LANDING_MARGIN_NM = 10_000
"""The margin of a via landing around its vias (10 µm), so the array fits inside it."""
"""The via of a net whose class sets none (diameter, drill)."""
SAFE = re.compile(r"[^A-Za-z0-9_.-]")
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-ROLE-COPPER-CLEAN", "H-G-ROLE-COPPER-REPAIR"))
"""What the planner claims (``docs/hypotheses.md``)."""
NOT_WORSE: Sequence[str] = ("warning", "error")


def safe(text: str) -> str:
    """``text`` with every character outside ``[A-Za-z0-9_.-]`` as ``_``: a part of a key."""
    return SAFE.sub("_", text)


# --- the request -----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Request:
    """What a run of the role copper is asked for: the DSL record ``design.role_copper(...)`` and the options
    of ``fenolite copper`` both give these attributes (``request_of``)."""

    kinds: tuple[str, ...] = KINDS
    layers: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: {})
    ground_layers: tuple[str, ...] | None = None
    ground_fill: str = "reference"
    connection: Mapping[str, str] = field(default_factory=lambda: {})
    stitch_pitch: int | None = None
    temp_rise: int | None = None
    widen: int | None = None
    corridors: bool = True
    keep: tuple[str, ...] = ()
    regenerate: tuple[str, ...] = ()
    nets: tuple[str, ...] = ()


def request_of(value: object | None) -> Request:
    """A ``Request`` from any object with its attributes (the DSL record), or the defaults for ``None``."""
    if value is None:
        return Request()
    if isinstance(value, Request):
        return value
    found: dict[str, Any] = {}
    for name in Request.__slots__:  # type: ignore[attr-defined]
        if hasattr(value, name):
            item = getattr(value, name)
            found[name] = dict(cast("Mapping[str, Any]", item)) if isinstance(item, Mapping) else item
    return Request(**found)


# --- the records, as c0224's protocols read them ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RoleBand:
    """A band of a role net (``BandLike``) with its ``group`` and pad ``connection``; keyed by its name."""

    call: ClassVar[str] = "band"
    name: str
    net: str
    spine: tuple[Point, ...]
    width: int
    max_width: int
    step: int
    layers: tuple[str, ...]
    clearance: int | None
    priority: int
    group: str
    connection: str
    square_ends: bool = True
    avoid: tuple[tuple[Point, ...], ...] = ()

    @property
    def key(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class RoleBarrier:
    """A keep-out band around the copper of high-voltage nets (``BarrierLike`` with ``nets``)."""

    call: ClassVar[str] = "barrier"
    name: str
    nets: tuple[str, ...]
    setback: int
    layers: tuple[str, ...]
    forbid: tuple[str, ...] = ("tracks", "vias", "pours")
    pieces: bool = True
    netclass: str = ""

    @property
    def key(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class RoleStitch:
    """Ground stitching or a via array at a layer change (``StitchPiecesLike`` with an optional
    ``patch``)."""

    call: ClassVar[str] = "stitch_pieces"
    name: str
    net: str
    pitch: int
    layers: tuple[str, ...]
    min_vias: int
    diameter: int | None
    drill: int | None
    clearance: int | None
    margin: int = 0
    patch: tuple[Point, ...] | None = None
    avoid: tuple[tuple[Point, ...], ...] = ()

    @property
    def key(self) -> str:
        return self.name


RoleRecord = RoleBand | RoleBarrier | RoleStitch


@dataclass(frozen=True, slots=True)
class Corridor:
    """A corridor of a critical route: its group, net, kind (``gate`` or ``kelvin``), layer, outline pieces,
    width, and whether phase 1 wrote it (``provisional``) or found it on the board (``found``)."""

    group: str
    net: str
    kind: str
    layer: str
    pieces: tuple[tuple[Point, ...], ...]
    width: int
    origin: str

    @property
    def key(self) -> str:
        return corridor_name(self.group, self.net)

    def to_json(self) -> dict[str, object]:
        return {
            "group": self.group,
            "net": self.net,
            "kind": self.kind,
            "layer": self.layer,
            "key": self.key,
            "width": self.width,
            "origin": self.origin,
            "polygons": [[[p.x, p.y] for p in piece] for piece in self.pieces],
        }


@dataclass(frozen=True, slots=True)
class NetPlan:
    """What the plan does for one role net: its kind, the method and widths, its layers and zone keys, or why
    it was skipped."""

    net: str
    kind: str
    method: str | None = None
    width: int | None = None
    max_width: int | None = None
    layers: tuple[str, ...] = ()
    zones: tuple[str, ...] = ()
    skipped: str | None = None
    vias: int = 0

    def to_json(self) -> dict[str, object]:
        return {
            "net": self.net,
            "kind": self.kind,
            "method": self.method,
            "width": self.width,
            "max_width": self.max_width,
            "layers": list(self.layers),
            "zones": list(self.zones),
            "skipped": self.skipped,
            "vias": self.vias,
        }


@dataclass(frozen=True, slots=True)
class RoleCopperPlan:
    """The plan of a run (``lens.rolecopper.RoleCopperPlanLike``): the c0224 records, the plain zones and
    rule areas, the model rules, the ids of the role items to remove first, the issues and the summary per
    net and corridor."""

    records: tuple[RoleRecord, ...] = ()
    zones: tuple[Zone, ...] = ()
    keepouts: tuple[Keepout, ...] = ()
    rules: tuple[Rule, ...] = ()
    remove: tuple[str, ...] = ()
    issues: tuple[Issue, ...] = ()
    nets: tuple[NetPlan, ...] = ()
    corridors: tuple[Corridor, ...] = ()
    tracks: tuple[Track, ...] = ()


# --- widths ---------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Width:
    """The required width of a net: the value, the method (``rule-of-thumb`` or ``fit``) and the rise."""

    value: int
    method: str
    temp_rise_mk: int | None = None


def rule_of_thumb(milliamps: int, per_amp_nm: int) -> int:
    """``ceil(milliamps × per_amp_nm / 1000)`` (S-0851)."""
    return -(-milliamps * per_amp_nm // 1000)


def fit_width(milliamps: int, temp_rise_mk: int, thickness: int, *, external: bool) -> int:
    """The smallest integer width whose S-0269 capacity at ``thickness`` and ``temp_rise_mk`` reaches
    ``milliamps``: a bisection over integer nanometres on ``analysis.current.capacity_ma``, which rises with
    the width."""
    low, high = 1, 1
    while capacity_ma(high * thickness, temp_rise_mk, external=external) < milliamps:
        high *= 2
    while low < high:
        middle = (low + high) // 2
        if capacity_ma(middle * thickness, temp_rise_mk, external=external) >= milliamps:
            high = middle
        else:
            low = middle + 1
    return low


def required_width(
    milliamps: int,
    *,
    per_amp_nm: int,
    temp_rise_mk: int | None = None,
    thickness: int | None = None,
    external: bool = True,
    floor: int = 0,
) -> Width:
    """The width a current asks for: by the fit of S-0269 with a rise and a copper thickness, else by the
    rule of thumb; never below ``floor`` (the class width)."""
    if temp_rise_mk is not None and thickness:
        value = fit_width(milliamps, temp_rise_mk, thickness, external=external)
        return Width(max(value, floor), "fit", temp_rise_mk)
    return Width(max(rule_of_thumb(milliamps, per_amp_nm), floor), "rule-of-thumb")


# --- the board as the planner sees it ----------------------------------------------------------------------


@dataclass(slots=True)
class _Ctx:
    design: Design
    pads: tuple[BoardPad, ...]
    roles: RoleSet
    request: Request
    requirements: Requirements | None
    nets: dict[str, Net]
    classes: dict[str, NetClass]
    copper: tuple[str, ...]
    part_classes: Mapping[str, Classified]
    issues: list[Issue] = field(default_factory=lambda: list[Issue]())
    planned: list[tuple[str, str, Thick, int]] = field(default_factory=lambda: [])
    """``(net, layer, shape, gap)`` of the role copper planned so far: obstacles of later nets."""
    hv_reach: list[tuple[str, int]] = field(default_factory=lambda: [])
    """``(net, distance)`` of the high-voltage nets: their copper keeps other nets' spines that far."""
    legs: dict[tuple[str, str], list[Edge]] = field(default_factory=lambda: {})
    """The hot-loop legs routed first, per net and layer."""
    sense: list[str] | None = None
    """The sense-branch tracks (``_sense_branches``), once computed."""
    groups: dict[tuple[str, str], tuple[str, str, int, int, str, int]] = field(default_factory=lambda: {})
    """``(net, layer)`` → ``(group, kind, width, max_width, connection, priority)`` of the bands planned."""
    failed: list[tuple[str, str, str, str]] = field(default_factory=lambda: [])
    """``(net, layer, pad, pad)`` of the hot-loop legs without a free path."""
    bounds: BBox | None = None
    """The box of the board outline: the grid search of a spine stays inside it."""

    def netclass(self, net: str) -> NetClass | None:
        found = self.nets.get(net)
        return self.classes.get(found.netclass_id) if found is not None and found.netclass_id else None

    def clearance(self, net: str) -> int:
        cls = self.netclass(net)
        return cls.clearance if cls is not None and cls.clearance is not None else DEFAULT_CLEARANCE_NM

    def spacing(self, a: str | None, b: str | None) -> int:
        return max(self.clearance(a) if a else 0, self.clearance(b) if b else 0, DEFAULT_CLEARANCE_NM)

    def via(self, net: str) -> tuple[int, int]:
        cls = self.netclass(net)
        if cls is not None and cls.via_diameter and cls.via_drill:
            return cls.via_diameter, cls.via_drill
        return DEFAULT_VIA

    def track_width(self, net: str) -> int:
        cls = self.netclass(net)
        return cls.track_width or 0 if cls is not None else 0

    @property
    def board_outline(self) -> tuple[Point, ...]:
        board = self.design.board
        assert board is not None
        return tuple(board_boundary(board).outer)


def _net_id_names(design: Design) -> dict[str, str]:
    return {net.id: net.name for net in design.circuit.nets}


def _pad_shapes(pad: BoardPad, layer: str) -> list[Thick]:
    found: list[Thick] = []
    for entry in pad.copper:
        if entry.layer != layer:
            continue
        try:
            found.append(Thick(tuple(entry.core), entry.width, entry.filled))
        except ValueError:
            continue
    return found


def _on_layer(pad: BoardPad, layer: str) -> bool:
    return any(entry.layer == layer for entry in pad.copper)


def _is_role_key(name: str) -> bool:
    return name.startswith("role.")


def _obstacles(ctx: _Ctx, net: str, layer: str, *, victims: Sequence[tuple[Thick, int]] = ()) -> Obstacles:
    """What a spine of ``net`` on ``layer`` keeps away from: other nets' pads, tracks, arcs and vias by the
    clearance in force, rule areas on the layer that forbid tracks or pours and every ``role.corridor.*``
    area, the zones of other nets of at least the band's priority, the role copper planned so far, the
    board edge, high-voltage copper by its distance, and the given ``victims``."""
    design = ctx.design
    board = design.board
    assert board is not None
    names = _net_id_names(design)
    items: list[tuple[Thick, int]] = list(victims)
    for pad in ctx.pads:
        if pad.net == net:
            continue
        for shape in _pad_shapes(pad, layer):
            items.append((shape, ctx.spacing(net, pad.net)))
        if pad.hole and pad.drill:
            items.append((Thick(tuple(pad.hole), pad.drill), ctx.spacing(net, pad.net)))
    for track in board.tracks:
        other = names.get(track.net_id or "")
        if other != net and track.layer == layer:
            items.append((Thick((track.start, track.end), track.width), ctx.spacing(net, other)))
    for arc in board.arcs:
        other = names.get(arc.net_id or "")
        if other != net and arc.layer == layer:
            items.append((Thick((arc.start, arc.mid, arc.end), arc.width), ctx.spacing(net, other)))
    for via in board.vias:
        other = names.get(via.net_id or "")
        if other != net:
            items.append((Thick((via.position,), via.diameter), ctx.spacing(net, other)))
    for area in board.keepouts:
        if len(area.outline) < 3 or (area.layers and layer not in area.layers):
            continue
        if area.name.startswith("role.corridor.") or area.no_tracks or area.no_copper_pour:
            items.append((Thick(tuple(area.outline), 0, filled=True), ctx.clearance(net)))
    # the net's own Kelvin copper: its sense branches and the receiver's pads stay apart from its pour
    receivers = {pad for pair in ctx.roles.kelvins for pad in pair.receiver}
    for pad in ctx.pads:
        if pad.net == net and pad_name(pad) in receivers:
            items += [(shape, ctx.clearance(net)) for shape in _pad_shapes(pad, layer)]
    for a, b, width in _own_sense_segments(ctx, net, layer):
        items.append((Thick((a, b), width), ctx.clearance(net)))
    for zone in board.zones:
        other = names.get(zone.net_id or "")
        if other == net or layer not in zone.layers or len(zone.outline) < 3:
            continue
        if zone.priority >= PRIORITY["power"] or zone.locked:
            items.append((Thick(tuple(zone.outline), 0, filled=True), ctx.spacing(net, other)))
    for other, at, shape, gap in ctx.planned:
        if other != net and at == layer:
            items.append((shape, max(gap, ctx.spacing(net, other))))
    for other, distance in ctx.hv_reach:
        if other == net:
            continue
        envelope = _hv_envelope(ctx, other, distance)
        if envelope is not None:
            items.append((envelope, 1))
    outline = ctx.board_outline
    if len(outline) >= 3:
        edge = max(ctx.clearance(net), _edge_clearance(design))
        items.append((Thick((*outline, outline[0]), 0), edge))
    return Obstacles(items)


def _join_loose(ctx: _Ctx, records: list[RoleRecord]) -> list[Track]:
    """Join each loose end of a net that got bands on a layer (the copper the left-out pour joined) to that
    net's planned copper, after every net's tree: a band of the net's width where it is free, else a locked
    track of the loose track's width (``role.join.<net>.<n>``), else ``roles.copper-blocked``."""
    tracks: list[Track] = []
    board = ctx.design.board
    assert board is not None
    for (net, layer), (group, kind, width, _, connection, priority) in sorted(ctx.groups.items()):
        own = [shape for at_net, at, shape, _ in ctx.planned if at_net == net and at == layer]
        spines = [
            record.spine
            for record in records
            if isinstance(record, RoleBand) and record.net == net and record.layers == (layer,)
        ]
        if not own or not spines:
            continue
        joined = {
            point
            for record in records
            if isinstance(record, RoleBand) and record.net == net
            for point in record.spine
        }
        for number, loose in enumerate(_loose_ends(ctx, net, layer)):
            if loose.centre in joined or any(thick_closer_than(Thick((loose.centre,), 2), s, 1) for s in own):
                continue
            target = _nearest_on(spines, loose.centre)
            goal = Terminal(f"{group}@{target.x},{target.y}", target, tuple(own))
            obstacles = _obstacles(ctx, net, layer, victims=_victims_on(ctx, net, kind, layer))
            path = route(
                loose,
                goal,
                width=width,
                step=max(width // 2, 100_000),
                obstacles=obstacles,
                bounds=ctx.bounds,
            )
            if path is not None:
                band = RoleBand(
                    f"{group}.join{number}",
                    net,
                    path,
                    width,
                    width,
                    max(1, width // 2),
                    (layer,),
                    ctx.clearance(net),
                    priority,
                    group,
                    connection,
                )
                records.append(band)
                _plan_shape(ctx, net, layer, path, width)
                continue
            thin = _loose_width(ctx, net, layer, loose.centre)
            path = route(
                loose, goal, width=thin, step=max(thin // 2, 100_000), obstacles=obstacles, bounds=ctx.bounds
            )
            if path is None:
                ctx.issues.append(
                    issue(
                        "roles.copper-blocked",
                        f"no free path for the copper of {net} on {layer} to the end of its track at "
                        f"({_mm(loose.centre.x)}, {_mm(loose.centre.y)}) mm; phase 2 or the user joins it",
                        where=f"{net}@{layer}",
                        hint="route that track to the net's copper",
                    )
                )
                continue
            for index, (a, b) in enumerate(zip(path, path[1:], strict=False)):
                key = f"role.join.{safe(net)}.{safe(layer)}.{number}.{index}"
                tracks.append(
                    Track(
                        id=derived_id("trk", "roles", key),
                        start=a,
                        end=b,
                        width=thin,
                        layer=layer,
                        net_id=ctx.nets[net].id,
                        locked=True,
                    )
                )
            _plan_shape(ctx, net, layer, path, thin)
    return tracks


def _nearest_on(spines: Sequence[Sequence[Point]], point: Point) -> Point:
    """The point of the horizontal and vertical segments of ``spines`` nearest to ``point`` (Manhattan)."""
    best: tuple[int, Point] | None = None
    for spine in spines:
        for a, b in zip(spine, spine[1:], strict=False):
            x = min(max(point.x, min(a.x, b.x)), max(a.x, b.x))
            y = min(max(point.y, min(a.y, b.y)), max(a.y, b.y))
            found = Point(x, y)
            score = (_manhattan(found, point), found)
            if best is None or score < (best[0], best[1]):
                best = score
    assert best is not None
    return best[1]


def _loose_width(ctx: _Ctx, net: str, layer: str, point: Point) -> int:
    board = ctx.design.board
    assert board is not None
    net_id = ctx.nets[net].id
    widths = [
        t.width for t in board.tracks if t.net_id == net_id and t.layer == layer and point in (t.start, t.end)
    ]
    return max(widths, default=ctx.track_width(net) or 250_000)


def _mm(value: int) -> str:
    sign = "-" if value < 0 else ""
    whole, part = divmod(abs(value), 1_000_000)
    text = f"{part:06d}".rstrip("0")
    return f"{sign}{whole}.{text}" if text else f"{sign}{whole}"


def _without_union(ctx: _Ctx, records: Sequence[RoleRecord]) -> list[RoleRecord]:
    """Without the ``geo`` extra the bands of a group cannot be united into one zone: each group keeps its
    longest band (``roles.copper-extra``), and a via array whose patch no kept band covers on each of its
    layers is left out with it."""
    groups: dict[str, list[RoleBand]] = {}
    for record in records:
        if isinstance(record, RoleBand) and record.group:
            groups.setdefault(record.group, []).append(record)
    dropped: set[str] = set()
    for group, bands in sorted(groups.items()):
        if len(bands) < 2:
            continue
        best = max(bands, key=lambda band: (length(band.spine), band.name))
        dropped |= {band.name for band in bands if band is not best}
        ctx.issues.append(
            issue(
                "roles.copper-extra",
                f"uniting the {len(bands)} bands of {group} needs the geo extra, so only its longest band "
                "was generated",
                where=group,
                hint="install the geo extra (pip install fenolite[geo])",
            )
        )
    if not dropped:
        return list(records)
    kept_bands = [r for r in records if isinstance(r, RoleBand) and r.name not in dropped]

    def covered(record: RoleStitch) -> bool:
        if record.patch is None:
            return True
        xs, ys = [p.x for p in record.patch], [p.y for p in record.patch]
        centre = Thick((Point((min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2),), 2)
        return all(
            any(
                layer in band.layers
                and any(
                    thick_closer_than(centre, slab(a, b, band.width), 1)
                    for a, b in zip(band.spine, band.spine[1:], strict=False)
                    if a != b
                )
                for band in kept_bands
            )
            for layer in record.layers
        )

    found: list[RoleRecord] = []
    for record in records:
        if isinstance(record, RoleBand) and record.name in dropped:
            continue
        if isinstance(record, RoleStitch) and not covered(record):
            continue
        found.append(record)
    return found


def _fenced(ctx: _Ctx, records: Sequence[RoleRecord]) -> list[RoleRecord]:
    """Each band with the bases of the other nets' bands on its layer added to the rings it does not widen
    over: a band widens only where the base of no later band will lie, whatever their order. Each via array
    with the bases of the other nets' bands on every layer, grown by their clearance, as rings to avoid."""
    bases: dict[str, list[tuple[str, tuple[Point, ...]]]] = {}
    spaced: list[tuple[str, tuple[Point, ...]]] = []
    for record in records:
        if isinstance(record, RoleBand):
            segments = [(a, b) for a, b in zip(record.spine, record.spine[1:], strict=False) if a != b]
            last = len(segments) - 1
            gap = 2 * (record.clearance or 0)
            for number, (a, b) in enumerate(segments):
                ring = slab(a, b, record.width, start=number > 0, end=number < last).core
                bases.setdefault(record.layers[0], []).append((record.net, tuple(ring)))
                wide = slab(a, b, record.width + gap, start=number > 0, end=number < last).core
                spaced.append((record.net, tuple(wide)))
    fenced: list[RoleRecord] = []
    for record in records:
        if isinstance(record, RoleBand):
            others = tuple(ring for net, ring in bases.get(record.layers[0], ()) if net != record.net)
            record = replace(record, avoid=(*record.avoid, *others))
        elif isinstance(record, RoleStitch):
            # a via goes through every layer: it stays off the base of every other net's band, by the band's
            # clearance, so the fill around it never narrows that band below its width
            others = tuple(ring for net, ring in spaced if net != record.net)
            record = replace(record, avoid=(*record.avoid, *others))
        fenced.append(record)
    return fenced


def _plan_shape(ctx: _Ctx, net: str, layer: str, spine: Sequence[Point], width: int) -> None:
    """Record the base of a band along ``spine`` (its slabs, square at the two ends) as planned copper: an
    obstacle of the later spines of other nets."""
    segments = [(a, b) for a, b in zip(spine, spine[1:], strict=False) if a != b]
    last = len(segments) - 1
    for number, (a, b) in enumerate(segments):
        shape = slab(a, b, width, start=number > 0, end=number < last)
        ctx.planned.append((net, layer, shape, ctx.clearance(net)))


def _hv_envelope(ctx: _Ctx, net: str, distance: int) -> Thick | None:
    """A region that holds the keep-out band of a high-voltage net: the convex hull of its pads' and planned
    copper's boxes on every layer, grown by ``distance`` on each axis (it holds c0224's convex barrier, whose
    discs reach ``distance`` only)."""
    points: list[Point] = []
    for pad in ctx.pads:
        if pad.net == net:
            box = _copper_box(pad)
            if box is not None:
                points += [
                    Point(box.x0, box.y0),
                    Point(box.x1, box.y1),
                    Point(box.x0, box.y1),
                    Point(box.x1, box.y0),
                ]
    for at_net, _, shape, _ in ctx.planned:
        if at_net == net:
            box = thick_bbox(shape)
            points += [
                Point(box.x0, box.y0),
                Point(box.x1, box.y1),
                Point(box.x0, box.y1),
                Point(box.x1, box.y0),
            ]
    if not points:
        return None
    grown = [
        Point(p.x + dx, p.y + dy)
        for p in points
        for dx in (-distance, distance)
        for dy in (-distance, distance)
    ]
    hull = convex_hull(grown)
    if len(hull) < 3:
        return None
    return Thick(tuple(hull), 0, filled=True)


def _edge_clearance(design: Design) -> int:
    rules = design.rules.rules if design.rules is not None else ()
    found = [rule.min for rule in rules if rule.kind == "edge_clearance" and rule.min is not None]
    return max(found, default=0)


# --- terminals ---------------------------------------------------------------------------------------------


def _clusters(ctx: _Ctx, names: Sequence[str], layer: str, width: int) -> list[Terminal]:
    """The pads ``names`` on ``layer`` as terminals: pads of one part closer than two widths form one
    cluster, whose spine point is the copper centre of its first pad (a Kelvin element pad: its outer half,
    so the corridor of its sense branch stays free)."""
    by_name = {pad_name(pad): pad for pad in ctx.pads}
    chosen = [by_name[name] for name in names if name in by_name and _on_layer(by_name[name], layer)]
    groups: list[list[BoardPad]] = []
    for pad in sorted(chosen, key=pad_name):
        for group in groups:
            if group[0].ref == pad.ref and any(
                abs(pad.position.x - other.position.x) + abs(pad.position.y - other.position.y) < 2 * width
                for other in group
            ):
                group.append(pad)
                break
        else:
            groups.append([pad])
    found: list[Terminal] = []
    for group in groups:
        label = "+".join(pad_name(pad) for pad in group)
        centre = _spine_point(ctx, group[0])
        copper = tuple(shape for pad in group for shape in _pad_shapes(pad, layer))
        found.append(Terminal(label, centre, copper))
    return found


def _spine_point(ctx: _Ctx, pad: BoardPad) -> Point:
    """The point a spine reaches on ``pad``: its position, or for a sense pad of a Kelvin pair the middle of
    its outer half (away from the other sense pad)."""
    name = pad_name(pad)
    for pair in ctx.roles.kelvins:
        if name in pair.element:
            other = pair.element[1] if pair.element[0] == name else pair.element[0]
            partner = next((p for p in ctx.pads if pad_name(p) == other), None)
            if partner is None:
                break
            dx, dy = partner.position.x - pad.position.x, partner.position.y - pad.position.y
            box = _copper_box(pad)
            if box is None:
                break
            if abs(dx) >= abs(dy):
                half = (box.x1 - box.x0) // 4
                outer = Point(pad.position.x - (half if dx > 0 else -half), pad.position.y)
            else:
                half = (box.y1 - box.y0) // 4
                outer = Point(pad.position.x, pad.position.y - (half if dy > 0 else -half))
            inner = Point(2 * pad.position.x - outer.x, 2 * pad.position.y - outer.y)
            # the half away from where the sense branch attaches: the outer one unless the branch is there
            ends = _sense_attachments(ctx, pad)
            if ends and min(_manhattan(outer, e) for e in ends) < min(_manhattan(inner, e) for e in ends):
                return inner
            return outer
    return pad.position


def _manhattan(a: Point, b: Point) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


def _sense_attachments(ctx: _Ctx, pad: BoardPad) -> list[Point]:
    """The ends of the sense-branch tracks that lie on ``pad``'s copper."""
    board = ctx.design.board
    assert board is not None
    branches = set(_sense_branches(ctx))
    copper = _pad_copper(pad)
    return [
        point
        for track in board.tracks
        if track.id in branches
        for point in (track.start, track.end)
        if _touches_any(point, copper)
    ]


def _copper_box(pad: BoardPad) -> BBox | None:
    points = [point for entry in pad.copper for point in entry.core]
    if not points:
        return None
    grow = max(entry.width for entry in pad.copper) // 2
    return BBox.of_points(points).inflate(grow)


def _loose_tracks(ctx: _Ctx, net: str) -> set[str]:
    """The ids of the net's tracks that hold one of its loose ends (``_loose_ends``)."""
    board = ctx.design.board
    assert board is not None
    ends = {t.centre for layer in ctx.copper for t in _loose_ends(ctx, net, layer)}
    net_id = ctx.nets[net].id if net in ctx.nets else None
    return {t.id for t in board.tracks if t.net_id == net_id and (t.start in ends or t.end in ends)}


def _loose_ends(ctx: _Ctx, net: str, layer: str) -> list[Terminal]:
    """The ends of the net's tracks on ``layer`` that touch no pad, no via and no other track of the net:
    copper that the left-out pour joined, which the zone must reach again."""
    board = ctx.design.board
    assert board is not None
    net_id = ctx.nets[net].id if net in ctx.nets else None
    tracks = [t for t in board.tracks if t.net_id == net_id]
    vias = [v.position for v in board.vias if v.net_id == net_id]
    ends: dict[Point, int] = {}
    for track in tracks:
        if track.layer != layer:
            continue
        for point in (track.start, track.end):
            ends[point] = ends.get(point, 0) + 1
    others = [t for t in tracks if t.layer != layer]
    found: list[Terminal] = []
    pad_copper = [shape for pad in ctx.pads if pad.net == net for shape in _pad_shapes(pad, layer)]
    for point, count in sorted(ends.items(), key=lambda item: (item[0].y, item[0].x)):
        if count > 1 or point in vias or any(point in (t.start, t.end) for t in others):
            continue
        probe = Thick((point,), 2)
        if any(thick_closer_than(probe, shape, 1) for shape in pad_copper):
            continue
        found.append(Terminal(f"end@{point.x},{point.y}", point, ()))
    # a via of the net that reaches the layer and meets nothing of the net there hung from the pour too
    on_layer = {point for track in tracks if track.layer == layer for point in (track.start, track.end)}
    for via in sorted(board.vias, key=lambda v: (v.position.y, v.position.x)):
        if via.net_id != net_id or via.position in on_layer or not _spans(ctx, via.layers, layer):
            continue
        probe = Thick((via.position,), via.diameter)
        if any(thick_closer_than(probe, shape, 1) for shape in pad_copper):
            continue
        found.append(Terminal(f"via@{via.position.x},{via.position.y}", via.position, (probe,)))
    return found


def _spans(ctx: _Ctx, layers: Sequence[str], layer: str) -> bool:
    """Whether a via between ``layers`` (its two outermost copper layers; none: a through via) reaches
    ``layer``."""
    if not layers or layer not in ctx.copper:
        return True
    ends = [ctx.copper.index(name) for name in layers if name in ctx.copper]
    if not ends:
        return True
    return min(ends) <= ctx.copper.index(layer) <= max(ends)


# --- per net ---------------------------------------------------------------------------------------------


def _user_zone_layers(ctx: _Ctx, net: str) -> set[str]:
    board = ctx.design.board
    assert board is not None
    net_id = ctx.nets[net].id if net in ctx.nets else None
    kept = set(ctx.request.keep)
    return {
        layer
        for zone in board.zones
        if zone.net_id == net_id and (not _is_role_key(zone.name) or zone.name in kept)
        for layer in zone.layers
    }


def _hot_legs(ctx: _Ctx, net: str) -> list[tuple[str, str]]:
    """The pairs of consecutive pads of the hot loops that are both on ``net``."""
    nets = {pad_name(pad): pad.net for pad in ctx.pads}
    legs: list[tuple[str, str]] = []
    for loop in ctx.roles.loops:
        pads = loop.pads
        for a, b in zip(pads, (*pads[1:], pads[0]), strict=True):
            if nets.get(a) == net and nets.get(b) == net:
                legs.append((a, b))
    return legs


def _loop_current(ctx: _Ctx, net: str) -> int | None:
    """The current of the hot-loop legs of a net: its own role's current, else the current of the switch node
    of a hot loop through it (the commutation current), else the largest current of that loop's nets."""
    own = ctx.roles.role_of(net)
    if own is not None and own.milliamps is not None:
        return own.milliamps
    nets = {pad_name(pad): pad.net for pad in ctx.pads}
    found: list[int] = []
    nodes: list[int] = []
    for loop in ctx.roles.loops:
        members = {nets.get(pad) for pad in loop.pads}
        if net in members:
            for role in ctx.roles.nets:
                if role.net in members and role.milliamps is not None:
                    found.append(role.milliamps)
                    if role.kind == "switch_node":
                        nodes.append(role.milliamps)
    return max(nodes, default=None) or max(found, default=None)


def _layers_of(ctx: _Ctx, role: NetRole, names: Sequence[str]) -> tuple[str, ...]:
    """The default layers of a net's copper: those of its SMD pads; both outer layers for a net of
    through-hole pads only."""
    given = ctx.request.layers.get(role.kind)
    if given:
        return tuple(layer for layer in ctx.copper if layer in given)
    by_name = {pad_name(pad): pad for pad in ctx.pads}
    smd = {
        entry.layer
        for name in names
        if (pad := by_name.get(name)) is not None and not pad.hole
        for entry in pad.copper
    }
    if smd:
        return tuple(layer for layer in ctx.copper if layer in smd)
    return tuple(layer for layer in (ctx.copper[0], ctx.copper[-1]) if layer) if ctx.copper else ()


def _through_hole_only(ctx: _Ctx, role: NetRole, names: Sequence[str]) -> bool:
    """Whether the layers of a net's copper are the default of through-hole terminals (``_layers_of``)."""
    if ctx.request.layers.get(role.kind):
        return False
    by_name = {pad_name(pad): pad for pad in ctx.pads}
    return all((pad := by_name.get(name)) is None or bool(pad.hole) for name in names)


def _terminal_pads(ctx: _Ctx, net: str) -> list[str]:
    """The pads a role net's copper joins: its power pads (``measure.power_pads``) and the pads of its hot
    loops, else every pad of the net."""
    board = RoleBoard(ctx.design, ctx.pads, ctx.roles, ctx.part_classes)
    found = set(power_pads(board).get(net, ()))
    for a, b in _hot_legs(ctx, net):
        found |= {a, b}
    if len(found) < 2:
        found = {pad_name(pad) for pad in ctx.pads if pad.net == net}
    return sorted(found)


def _band_records(
    ctx: _Ctx,
    net: str,
    kind: str,
    layer: str,
    edges: Sequence[Edge],
    width: int,
    max_width: int,
    connection: str,
    priority: int,
) -> tuple[list[RoleBand], str]:
    """The band records of a tree's edges on one layer, all of one group; without the ``geo`` extra a tree of
    more than one edge is one chain or its longest edge (``roles.copper-extra``)."""
    group = f"role.{kind}.{safe(net)}.{safe(layer)}"
    step = (max_width - width) // 2 if max_width > width else max(1, width // 2)
    spines: list[tuple[Point, ...]] = [edge.path for edge in edges]
    if len(spines) > 1 and "clipper" not in available_backends():
        joined = chain(edges)
        if joined is None:
            best = longest(edges)
            assert best is not None
            spines = [best.path]
            ctx.issues.append(
                issue(
                    "roles.copper-extra",
                    f"the copper of {net} on {layer} branches; uniting its {len(edges)} bands needs the geo "
                    "extra, so only its longest edge was generated",
                    where=group,
                    hint="install the geo extra (pip install fenolite[geo])",
                )
            )
        else:
            spines = [joined]
    records = [
        RoleBand(
            name=f"{group}.{number}",
            net=net,
            spine=spine,
            width=width,
            max_width=max_width,
            step=step,
            layers=(layer,),
            clearance=ctx.clearance(net),
            priority=priority,
            group=group,
            connection=connection,
            avoid=_own_kelvin_rings(ctx, net, layer),
        )
        for number, spine in enumerate(spines)
    ]
    return records, group


def _own_sense_segments(ctx: _Ctx, net: str, layer: str) -> list[tuple[Point, Point, int]]:
    """The net's own sense-branch tracks on ``layer`` (not one that hangs from the left-out pour), whole: the
    pour keeps away from the part on the sense pad too, so it never meets the branch before the pad:
    ``(start, end, width)``."""
    board = ctx.design.board
    assert board is not None
    net_id = ctx.nets[net].id if net in ctx.nets else None
    sense = set(_sense_branches(ctx)) - _loose_tracks(ctx, net)
    return [
        (track.start, track.end, track.width)
        for track in board.tracks
        if track.id in sense and track.net_id == net_id and track.layer == layer
    ]


def _own_kelvin_rings(ctx: _Ctx, net: str, layer: str) -> tuple[tuple[Point, ...], ...]:
    """The net's own Kelvin copper on ``layer`` as rings a band does not widen over: its sense-branch tracks
    (not one that hangs from the left-out pour) and the receiver's pads."""
    rings: list[tuple[Point, ...]] = []
    for a, b, width in _own_sense_segments(ctx, net, layer):
        ring = _segment_ring(a, b, -(-width // 2))
        if ring is not None:
            rings.append(ring)
    receivers = {pad for pair in ctx.roles.kelvins for pad in pair.receiver}
    for pad in ctx.pads:
        if pad.net == net and pad_name(pad) in receivers and _on_layer(pad, layer):
            box = _copper_box(pad)
            if box is not None:
                rings.append(
                    _rect(
                        Point((box.x0 + box.x1) // 2, (box.y0 + box.y1) // 2),
                        (box.x1 - box.x0) // 2,
                        (box.y1 - box.y0) // 2,
                    )
                )
    return tuple(rings)


def _victim_copper(ctx: _Ctx, node: str, distance: int) -> dict[str, list[tuple[Thick, int]]]:
    """The copper of the victims of the switch node ``node`` per layer, with the switching distance as its
    gap: each net of role ``kelvin``, each sensitive signal, each gate net of a switch that is not on the
    node, and the tracks of the sense branches of the Kelvin pairs (the copper of their nets that reaches
    the receiver's pads)."""
    design = ctx.design
    board = design.board
    assert board is not None
    names = _net_id_names(design)
    whole = victim_nets(ctx.roles, ctx.pads, node, ctx)
    found: dict[str, list[tuple[Thick, int]]] = {}

    def add(layer: str, shape: Thick) -> None:
        found.setdefault(layer, []).append((shape, distance))

    for track in board.tracks:
        if names.get(track.net_id or "") in whole:
            add(track.layer, Thick((track.start, track.end), track.width))
    for pad in ctx.pads:
        if pad.net in whole:
            for entry in pad.copper:
                add(entry.layer, Thick(tuple(entry.core), entry.width, entry.filled))
    for track_id in _sense_branches(ctx):
        track = next((t for t in board.tracks if t.id == track_id), None)
        if track is not None:
            add(track.layer, Thick((track.start, track.end), track.width))
    return found


def victim_nets(roles: RoleSet, pads: Sequence[BoardPad], node: str, ctx: _Ctx | None = None) -> list[str]:
    """The nets of their own that are victims of the switch node ``node``: ``kelvin`` nets, sensitive
    signals, and the gate nets of switches that are not on the node (c0222's victims)."""
    nets = {pad_name(pad): pad.net for pad in pads}
    on_node = {name.rpartition("-")[0] for name, net in nets.items() if net == node}
    found: set[str] = set()
    for role in roles.nets:
        if role.net == node:
            continue
        if role.kind == "kelvin" or (role.kind == "signal" and role.sensitive):
            found.add(role.net)
    for gate in roles.gates:
        switch = gate.gate.rpartition("-")[0]
        net = nets.get(gate.gate)
        if net is not None and net != node and switch not in on_node:
            found.add(net)
    return sorted(found)


def _sense_branches(ctx: _Ctx) -> list[str]:
    """The tracks of the Kelvin pairs' sense branches: on each receiver pad's net, the tracks reached from
    that pad by touching ends without passing another pad of the net. A branch that reaches a pad of its net
    other than the pair's sense pads (a monitor wired to the force pads) is left out: it hangs from the power
    copper by design, and the pour joins it there as before. Computed once per run."""
    if ctx.sense is not None:
        return ctx.sense
    board = ctx.design.board
    assert board is not None
    by_name = {pad_name(pad): pad for pad in ctx.pads}
    found: list[str] = []
    for pair in ctx.roles.kelvins:
        for receiver in pair.receiver:
            pad = by_name.get(receiver)
            if pad is None or pad.net is None or pad.net not in ctx.nets:
                continue
            net_id = ctx.nets[pad.net].id
            tracks = [t for t in board.tracks if t.net_id == net_id]
            starts = _pad_copper(pad)
            others = [
                _pad_copper(other)
                for other in ctx.pads
                if other is not pad and other.net == pad.net and pad_name(other) not in pair.element
            ]
            reached: set[str] = set()
            miswired = False
            frontier = [t for t in tracks if _touches_any(t.start, starts) or _touches_any(t.end, starts)]
            while frontier:
                track = frontier.pop()
                if track.id in reached:
                    continue
                reached.add(track.id)
                for point in (track.start, track.end):
                    if any(_touches_any(point, copper) for copper in others):
                        miswired = True
                        continue
                    frontier += [t for t in tracks if t.id not in reached and point in (t.start, t.end)]
            if not miswired:
                found += sorted(reached)
    ctx.sense = found
    return found


def _pad_copper(pad: BoardPad) -> list[Thick]:
    found: list[Thick] = []
    for entry in pad.copper:
        try:
            found.append(Thick(tuple(entry.core), entry.width, entry.filled))
        except ValueError:
            continue
    return found


def _touches_any(point: Point, shapes: Sequence[Thick]) -> bool:
    probe = Thick((point,), 2)
    return any(thick_closer_than(probe, shape, 1) for shape in shapes)


def _adjacent(ctx: _Ctx, layer: str) -> list[str]:
    if layer not in ctx.copper:
        return []
    index = ctx.copper.index(layer)
    return [ctx.copper[i] for i in (index - 1, index + 1) if 0 <= i < len(ctx.copper)]


def _distance_of(ctx: _Ctx, net: str) -> int | None:
    """The largest distance (clearance or creepage) of the user's ``[[distance]]`` and ``[[step]]`` rows that
    name ``net``, or ``None``."""
    requirements = ctx.requirements
    if requirements is None or net not in ctx.nets:
        return None
    circuit = ctx.design.circuit
    own = ctx.nets[net]
    best: int | None = None
    for row in requirements.distances:
        if not any(row.matches(own, other, circuit) for other in circuit.nets):
            continue
        triple = requirements.values(row)
        if triple is None:
            continue
        values = [value for value in (triple[0], triple[1]) if value is not None]
        if values:
            best = max(best or 0, *values)
    return best


def _net_width(ctx: _Ctx, role: NetRole, layers: Sequence[str]) -> Width:
    """The required width of a role net with a current (decision 2)."""
    milliamps = role.milliamps
    assert milliamps is not None
    per_amp = profile.resolve("width_per_amp_nm", ctx.roles.limits, net=role.net, kind=role.kind)
    rise = ctx.request.temp_rise
    if rise is None:
        rise = profile.resolve("temp_rise_mk", ctx.roles.limits, net=role.net, kind=role.kind).value
    board = ctx.design.board
    assert board is not None
    first = layers[0] if layers else (ctx.copper[0] if ctx.copper else "F.Cu")
    return required_width(
        milliamps,
        per_amp_nm=per_amp.value or 0,
        temp_rise_mk=rise,
        thickness=layer_thickness(board, first, None),
        external=first in (ctx.copper[0], ctx.copper[-1]) if ctx.copper else True,
        floor=ctx.track_width(role.net),
    )


def _victims_on(ctx: _Ctx, net: str, kind: str, layer: str) -> list[tuple[Thick, int]]:
    """The victim copper a switch node's spine keeps the switching distance from on ``layer`` and the
    layers next to it (decision 4); nothing for another kind."""
    if kind != "switch_node":
        return []
    distance = profile.resolve("switching_distance_nm", ctx.roles.limits, net=net, kind="kelvin").value or 0
    victims = _victim_copper(ctx, net, distance + POUR_GRID_NM)
    found = list(victims.get(layer, ()))
    for adjacent in _adjacent(ctx, layer):
        found += victims.get(adjacent, ())
    return found


def _route_legs(ctx: _Ctx, widths: Mapping[str, tuple[str, int]], planes: Sequence[str]) -> None:
    """The legs of every hot loop first (decision 3: the commutation loop closes on one layer, the input
    capacitor's legs first): each pair of consecutive loop pads on one net that gets copper, on a layer both
    pads share (not a ground plane's layer, nor one where the user's zone holds the net), routed at the
    net's width; ``widths`` maps a net to its kind and width. The legs become the first edges of the nets'
    trees and obstacles of every later spine."""
    for loop in ctx.roles.loops:
        pads = loop.pads
        nets = {pad_name(pad): pad.net for pad in ctx.pads}
        legs = [
            (a, b)
            for a, b in zip(pads, (*pads[1:], pads[0]), strict=True)
            if nets.get(a) is not None and nets.get(a) == nets.get(b) and nets.get(a) in widths
        ]
        best: (
            tuple[tuple[int, int], list[Issue], dict[tuple[str, str], list[Edge]], list[Any], list[Any]]
            | None
        )
        best = None
        for order in itertools.permutations(range(len(legs))):
            trial = replace(
                ctx,
                issues=[],
                legs={k: list(v) for k, v in ctx.legs.items()},
                planned=list(ctx.planned),
                failed=list(ctx.failed),
            )
            _route_loop_legs(trial, [legs[i] for i in order], widths, planes)
            routed = sum(len(v) for v in trial.legs.values()) - sum(len(v) for v in ctx.legs.values())
            total = sum(length(edge.path) for v in trial.legs.values() for edge in v)
            score = (-routed, total)
            if best is None or score < best[0]:
                best = (score, trial.issues, trial.legs, trial.planned, trial.failed)
            if len(legs) > MAX_LEG_ORDERS_LEGS:
                break  # a long loop is routed in its own order only
        if best is not None:
            ctx.issues += best[1]
            ctx.legs = best[2]
            ctx.planned = best[3]
            ctx.failed = best[4]


def _route_loop_legs(
    ctx: _Ctx, legs: Sequence[tuple[str, str]], widths: Mapping[str, tuple[str, int]], planes: Sequence[str]
) -> None:
    """Route the ``legs`` of one hot loop in the order given (``_route_legs``)."""
    by_name = {pad_name(pad): pad for pad in ctx.pads}
    if True:
        for a, b in legs:
            first, second = by_name.get(a), by_name.get(b)
            if first is None or second is None or first.net is None or first.net != second.net:
                continue
            net = first.net
            if net not in widths:
                continue
            kind, width = widths[net]
            user = _user_zone_layers(ctx, net)
            shared = [
                layer
                for layer in ctx.copper
                if _on_layer(first, layer)
                and _on_layer(second, layer)
                and layer not in user
                and not (kind == "ground" and layer in planes)
            ]
            if not shared:
                continue
            layer = shared[0]
            names = _terminal_pads(ctx, net)
            terminals = {t.label: t for t in _clusters(ctx, names, layer, width)}
            label_a = next((label for label in terminals if a in label.split("+")), None)
            label_b = next((label for label in terminals if b in label.split("+")), None)
            if label_a is None or label_b is None or label_a == label_b:
                continue
            done = ctx.legs.setdefault((net, layer), [])
            if any({edge.a, edge.b} == {label_a, label_b} for edge in done):
                continue
            obstacles = _obstacles(ctx, net, layer, victims=_victims_on(ctx, net, kind, layer))
            path = route(
                terminals[label_a],
                terminals[label_b],
                width=width,
                step=max(width // 2, 100_000),
                obstacles=obstacles,
                bounds=ctx.bounds,
            )
            if path is None:
                ctx.failed.append((net, layer, a, b))
                ctx.issues.append(
                    issue(
                        "roles.copper-blocked",
                        f"no free path for the hot-loop leg of {net} on {layer} between {label_a} and "
                        f"{label_b}",
                        where=f"{net}@{layer}",
                        hint="move the parts of the hot loop closer, or route the leg by hand",
                    )
                )
                continue
            done.append(Edge(label_a, label_b, path))
            _plan_shape(ctx, net, layer, path, width)


def _plan_net(ctx: _Ctx, role: NetRole, kind: str, records: list[RoleRecord], hv: bool) -> NetPlan:
    """The bands of one power, switch-node or high-voltage net (and its via arrays)."""
    net = role.net
    names = _terminal_pads(ctx, net)
    layers = _layers_of(ctx, role, names)
    if kind == "ground":
        # a ground net with a current carries it on its pads' layers besides its planes
        layers = tuple(layer for layer in layers if layer not in _plane_layers(ctx))
    width = _net_width(ctx, role, layers)
    widen = (
        ctx.request.widen
        if ctx.request.widen is not None and kind != "switch_node"
        else WIDEN_PERMILLE["power" if kind == "ground" else kind]
    )
    if hv:
        widen = (
            1000  # its keep-out band is a convex envelope: widened copper would draw it over its neighbours
        )
    max_width = max(width.value, widen * width.value // 1000)
    # the band is one cell of the simulated pour wider than the current asks, so the judge's raster, which
    # may lose half a cell on each side, still measures the required width
    base, widest = width.value + POUR_GRID_NM, max_width + POUR_GRID_NM
    user = _user_zone_layers(ctx, net)
    if set(layers) & user and _through_hole_only(ctx, role, names):
        # through-hole terminals reach every layer: the user's zone on one of them already joins them
        layers = tuple(layer for layer in layers if layer in user)
    skipped_layers = [layer for layer in layers if layer in user]
    if skipped_layers:
        ctx.issues.append(
            issue(
                "roles.copper-skipped",
                f"{net} already holds a zone of the user on {', '.join(skipped_layers)}: no role copper "
                "there "
                "(user-copper)",
                severity="info",
                where=net,
                hint="remove the zone to get role copper on that layer",
            )
        )
    connection = ctx.request.connection.get(kind, DEFAULT_CONNECTION[kind])  # one setting per net
    priority = PRIORITY["ground_band" if kind == "ground" else kind]
    zones: list[str] = []
    done_layers: list[str] = []
    change = _transition(ctx, names, [layer for layer in layers if layer not in user], base)
    for layer in sorted(set(layers) | {at for at_net, at in ctx.legs if at_net == net}, key=ctx.copper.index):
        if layer in user:
            continue
        obstacles = _obstacles(ctx, net, layer, victims=_victims_on(ctx, net, kind, layer))
        terminals = _clusters(ctx, names, layer, base)
        if change is not None and layer == change[0]:
            # the copper of this layer reaches the transition, where the via array joins the other layer
            terminals.append(Terminal(f"via@{change[3].centre.x},{change[3].centre.y}", change[3].centre, ()))
        if len(terminals) < 2:  # a lone pad: its loose ends are what the copper joins it to
            terminals += _loose_ends(ctx, net, layer)
        given = ctx.legs.get((net, layer), [])
        if len(terminals) < 2 and not given:
            continue
        step = max(base // 2, 100_000)
        built = tree(
            terminals,
            lambda a, b, obstacles=obstacles, step=step: route(
                a, b, width=base, step=step, obstacles=obstacles, bounds=ctx.bounds
            ),
            given=given,
        )
        for a, b in built.blocked:
            ctx.issues.append(
                issue(
                    "roles.copper-blocked",
                    f"no free path for the copper of {net} on {layer} between {a} and {b}; phase 2 or the "
                    "user "
                    "joins them",
                    where=f"{net}@{layer}",
                    hint="move the parts or the copper between them, or route that connection",
                )
            )
        if not built.edges:
            continue
        bands, group = _band_records(ctx, net, kind, layer, built.edges, base, widest, connection, priority)
        ctx.groups[(net, layer)] = (group, kind, base, widest, connection, priority)
        records += bands
        zones.append(group)
        done_layers.append(layer)
        for band in bands:
            _plan_shape(ctx, net, layer, band.spine, band.width)
    vias = 0
    if change is not None and role.milliamps is not None:
        a, b, _, q = change
        vias = _landing(
            ctx, net, role.milliamps, (a, b), (q,), kind, base, connection, records,
            bands_on=(a, b), key=f"role.via.{safe(net)}",
        )  # fmt: skip
        if vias:
            for layer in (a, b):
                group = f"role.{kind}.{safe(net)}.{safe(layer)}"
                ctx.groups.setdefault((net, layer), (group, kind, base, widest, connection, priority))
                if group not in zones:
                    zones.append(group)
                if layer not in done_layers:
                    done_layers.append(layer)
    return NetPlan(
        net,
        kind,
        width.method,
        width.value,
        max_width,
        tuple(layer for layer in ctx.copper if layer in done_layers),
        tuple(zones),
        None if zones else ("user-copper" if skipped_layers else "no-terminals"),
        vias,
    )


def _transition(
    ctx: _Ctx, names: Sequence[str], layers: Sequence[str], width: int
) -> tuple[str, str, Terminal, Terminal] | None:
    """Where a net's copper changes layer (decision 6): with SMD terminals on two of ``layers``, the nearest
    pair ``(a, b, p, q)``, ``p`` on layer ``a`` and ``q`` on layer ``b``; the via array lands beside ``q``."""
    smd: dict[str, list[Terminal]] = {}
    for layer in layers:
        found = [
            t
            for t in _clusters(ctx, names, layer, width)
            if not any(_is_th(ctx, n) for n in t.label.split("+"))
        ]
        if found:
            smd[layer] = found
    if len(smd) < 2:
        return None
    a, b = sorted(smd, key=ctx.copper.index)[:2]
    pairs = sorted(
        (abs(p.centre.x - q.centre.x) + abs(p.centre.y - q.centre.y), p.label, q.label, p, q)
        for p in smd[a]
        for q in smd[b]
    )
    _, _, _, p, q = pairs[0]
    return a, b, p, q


def _landing(
    ctx: _Ctx,
    net: str,
    milliamps: int,
    layers: tuple[str, str],
    anchors: Sequence[Terminal],
    kind: str,
    width: int,
    connection: str,
    records: list[RoleRecord],
    *,
    bands_on: Sequence[str],
    key: str,
) -> int:
    """A via array between ``layers`` for ``milliamps``: a square landing reached by a band from an
    ``anchors`` terminal (on each layer of ``bands_on``), beyond the hot loop's pads grown by ``width``, its
    vias limited to the square. The first free direction from the first anchor that has one wins; else
    ``roles.copper-blocked``. Returns the via count asked, or 0."""
    per_via = profile.resolve("milliamps_per_via", ctx.roles.limits, net=net).value or 0
    if per_via <= 0:
        return 0
    count = -(-milliamps // per_via)
    diameter, drill = ctx.via(net)
    clearance = ctx.clearance(net)
    pitch = diameter + clearance
    cols = math.isqrt(count - 1) + 1 if count > 1 else 1
    rows = -(-count // cols)
    along = (cols - 1) * pitch + diameter + 2 * LANDING_MARGIN_NM
    across = max((rows - 1) * pitch + diameter + 2 * LANDING_MARGIN_NM, width)
    hot = {pad for leg in _hot_legs(ctx, net) for pad in leg}
    by_name = {pad_name(pad): pad for pad in ctx.pads}
    avoid = tuple(
        _square(pad.position, _copper_extent(pad) + width) for pad in ctx.pads if pad_name(pad) in hot
    )
    centre = _loop_centre(ctx, net)
    board = ctx.design.board
    assert board is not None
    net_id = ctx.nets[net].id if net in ctx.nets else None
    own = Obstacles(
        [
            (shape, clearance)
            for pad in ctx.pads
            if pad.net == net
            for layer in layers
            for shape in _pad_shapes(pad, layer)
        ]
        + [(Thick((via.position,), via.diameter), clearance) for via in board.vias if via.net_id == net_id]
    )
    walls = {layer: _obstacles(ctx, net, layer) for layer in {*layers, *bands_on}}
    for anchor in anchors:
        first = by_name.get(anchor.label.split("+")[0])
        reach = (_copper_extent(first) if first is not None else 0) + width + along // 2 + clearance
        # from the pad's own position: the copper analyses join a pad to the pour that covers its centre
        origin = first.position if first is not None else anchor.centre
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        if centre is not None:
            directions.sort(key=lambda d: (d[0] * (centre.x - origin.x) + d[1] * (centre.y - origin.y), d))
        tries = [(dx, dy, reach + k * pitch) for k in range(LANDING_STEPS) for dx, dy in directions]
        for dx, dy, distance in tries:
            at = Point(origin.x + dx * distance, origin.y + dy * distance)
            half_x, half_y = (along // 2, across // 2) if dx else (across // 2, along // 2)
            square = _rect(at, half_x, half_y)
            if any(walls[layer].hits(Thick(square, 0, filled=True)) for layer in layers):
                continue
            if own.hits(Thick(square, 0, filled=True)):
                continue  # the vias stay off the net's own pads and vias
            stem = (origin, at)
            if any(walls[layer].hits(slab(origin, at, width, start=False)) for layer in bands_on):
                continue
            for layer in bands_on:
                group = f"role.{kind}.{safe(net)}.{safe(layer)}"
                records.append(
                    RoleBand(
                        f"{group}.landing",
                        net,
                        (origin, at),
                        width,
                        width,
                        max(1, width // 2),
                        (layer,),
                        clearance,
                        PRIORITY.get(kind, 2),
                        group,
                        connection,
                    )
                )
                end = Point(at.x - dx * (along // 2), at.y - dy * (along // 2))
                far = Point(at.x + dx * (along // 2), at.y + dy * (along // 2))
                records.append(
                    RoleBand(
                        f"{group}.landing.pad",
                        net,
                        (end, far),
                        across,
                        across,
                        max(1, across // 2),
                        (layer,),
                        clearance,
                        PRIORITY.get(kind, 2),
                        group,
                        connection,
                        square_ends=True,
                    )
                )
                ctx.planned.append((net, layer, Thick(square, 0, filled=True), clearance))
                _plan_shape(ctx, net, layer, stem, width)
            records.append(
                RoleStitch(
                    key,
                    net,
                    pitch,
                    tuple(layers),
                    count,
                    diameter,
                    drill,
                    clearance,
                    patch=_rect(at, half_x, half_y),
                    avoid=avoid,
                )
            )
            return count
    ctx.issues.append(
        issue(
            "roles.copper-blocked",
            f"no free place for the {count} vias of {net} between {layers[0]} and {layers[1]}",
            where=f"{net}@{layers[0]}+{layers[1]}",
            hint="free room near the transition, or route the layer change by hand",
        )
    )
    return 0


def _loop_centre(ctx: _Ctx, net: str) -> Point | None:
    """The centre of the pads of the hot loops through ``net``, or ``None``."""
    nets = {pad_name(pad): pad for pad in ctx.pads}
    points = [
        nets[pad].position
        for loop in ctx.roles.loops
        if any(nets.get(p) is not None and nets[p].net == net for p in loop.pads)
        for pad in loop.pads
        if pad in nets
    ]
    if not points:
        return None
    return Point(sum(p.x for p in points) // len(points), sum(p.y for p in points) // len(points))


def _is_th(ctx: _Ctx, name: str) -> bool:
    pad = next((p for p in ctx.pads if pad_name(p) == name), None)
    return bool(pad is not None and pad.hole)


def _copper_extent(pad: BoardPad) -> int:
    box = _copper_box(pad)
    if box is None:
        return 0
    return max(box.x1 - box.x0, box.y1 - box.y0) // 2


def _rect(at: Point, half_x: int, half_y: int) -> tuple[Point, ...]:
    return (
        Point(at.x - half_x, at.y - half_y),
        Point(at.x + half_x, at.y - half_y),
        Point(at.x + half_x, at.y + half_y),
        Point(at.x - half_x, at.y + half_y),
    )


def _square(at: Point, half: int) -> tuple[Point, ...]:
    return (
        Point(at.x - half, at.y - half),
        Point(at.x + half, at.y - half),
        Point(at.x + half, at.y + half),
        Point(at.x - half, at.y + half),
    )


# --- ground ----------------------------------------------------------------------------------------------


def _ground_layers(ctx: _Ctx) -> tuple[str, ...]:
    given = ctx.request.ground_layers
    if given:
        return tuple(layer for layer in ctx.copper if layer in given)
    if len(ctx.copper) >= 4:
        return (ctx.copper[1],)
    return (ctx.copper[-1],) if ctx.copper else ()


def _inset(ring: Sequence[Point], by: int) -> tuple[Point, ...]:
    """The board's rectangle-like outline inset by ``by``: each vertex moved toward the centre of its box
    (exact for an axis-parallel rectangle; for another outline, the convex hull of the moved vertices)."""
    box = BBox.of_points(ring)
    cx, cy = (box.x0 + box.x1) // 2, (box.y0 + box.y1) // 2
    moved = [
        Point(
            p.x + (by if p.x < cx else -by if p.x > cx else 0),
            p.y + (by if p.y < cy else -by if p.y > cy else 0),
        )
        for p in ring
    ]
    if len(ring) == 4:
        return tuple(moved)
    return tuple(convex_hull(moved))


def _plane_layers(ctx: _Ctx) -> list[str]:
    """The layers of the ground planes: the ground layers, and the outer ones with ``ground_fill="all"``."""
    layers = list(_ground_layers(ctx))
    if ctx.request.ground_fill == "all" and ctx.copper:
        layers += [layer for layer in (ctx.copper[0], ctx.copper[-1]) if layer not in layers]
    return [layer for layer in ctx.copper if layer in layers]


def _plan_ground(
    ctx: _Ctx, roles: Sequence[NetRole], records: list[RoleRecord], zones: list[Zone]
) -> list[NetPlan]:
    """One locked zone over the board on each ground layer for the first ground net (by pad count, then
    name), stitching between its zones on different layers, and the bands of its hot-loop legs on the
    pads' layer where no plane of the net lies."""
    found: list[NetPlan] = []
    if not roles:
        return found
    outline = ctx.board_outline
    edge = max(_edge_clearance(ctx.design), 0)
    counts = {role.net: sum(1 for pad in ctx.pads if pad.net == role.net) for role in roles}
    ordered = sorted(roles, key=lambda role: (-counts[role.net], role.net))
    layers = _plane_layers(ctx)
    connection = ctx.request.connection.get("ground", DEFAULT_CONNECTION["ground"])
    for number, role in enumerate(ordered):
        net = role.net
        if number > 0:
            ctx.issues.append(
                issue(
                    "roles.copper-skipped",
                    f"the ground planes go to {ordered[0].net}; {net} gets no plane (shared-layer)",
                    severity="info",
                    where=net,
                )
            )
            found.append(NetPlan(net, "ground", skipped="shared-layer"))
            continue
        user = _user_zone_layers(ctx, net)
        if user and ctx.request.ground_layers is None:
            # the user drew this ground's copper: the default planes would add to it, so only explicit
            # ``ground_layers`` add planes to a ground of the user's
            ctx.issues.append(
                issue(
                    "roles.copper-skipped",
                    f"{net} already holds zones of the user on {', '.join(sorted(user))}: no ground plane "
                    "(user-copper)",
                    severity="info",
                    where=net,
                    hint="pass ground_layers to add planes beside the user's zones",
                )
            )
            found.append(NetPlan(net, "ground", skipped="user-copper"))
            continue
        made: list[str] = []
        planes: list[str] = []
        for layer in layers:
            if layer in user:
                ctx.issues.append(
                    issue(
                        "roles.copper-skipped",
                        f"{net} already holds a zone of the user on {layer}: no ground plane there "
                        "(user-copper)",
                        severity="info",
                        where=net,
                    )
                )
                continue
            if len(outline) < 3:
                continue
            key = f"role.ground.{safe(net)}.{safe(layer)}"
            clearance = ctx.clearance(net)
            zones.append(
                Zone(
                    id=derived_id("zon", "dsl", f"zone:{key}"),
                    outline=_inset(outline, max(edge, clearance)),
                    name=key,
                    layers=(layer,),
                    net_id=ctx.nets[net].id,
                    priority=PRIORITY["ground"],
                    settings=ZoneSettings(clearance=clearance, connection=connection),  # type: ignore[arg-type]
                    locked=True,
                )
            )
            made.append(key)
            planes.append(layer)
        # the hot loop's legs of the ground net, routed first (``_route_legs``), on a layer without its plane
        current = _loop_current(ctx, net)
        legs = _hot_legs(ctx, net)
        band_layers: list[str] = []
        if legs and current is not None and role.milliamps is None:  # with a current: ``_plan_net`` made them
            per_amp = profile.resolve("width_per_amp_nm", ctx.roles.limits, net=net, kind="ground").value or 0
            width = max(rule_of_thumb(current, per_amp), ctx.track_width(net)) + POUR_GRID_NM
            for (leg_net, layer), given in sorted(ctx.legs.items()):
                if leg_net != net or not given or layer in planes:
                    continue
                bands, group = _band_records(
                    ctx, net, "ground", layer, given, width, 2 * width, connection, PRIORITY["ground_band"]
                )
                records += bands
                made.append(group)
                band_layers.append(layer)
                for band in bands:
                    _plan_shape(ctx, net, layer, band.spine, band.width)
        if band_layers and planes and current is not None:
            names = sorted({pad for leg in legs for pad in leg})
            width = POUR_GRID_NM + max(
                rule_of_thumb(
                    current,
                    profile.resolve("width_per_amp_nm", ctx.roles.limits, net=net, kind="ground").value or 0,
                ),
                ctx.track_width(net),
            )
            for layer in band_layers:
                anchors = _clusters(ctx, names, layer, width)
                _landing(
                    ctx,
                    net,
                    current,
                    (layer, planes[0]),
                    anchors,
                    "ground",
                    width,
                    connection,
                    records,
                    bands_on=(layer,),
                    key=f"role.via.{safe(net)}.{safe(layer)}",
                )
        # a leg without a free path on its pads' layer closes through the plane: a via array at each of its
        # pads (S-0860 wants the loop on one layer; this is the next best, and the blocked leg is reported)
        if planes and current is not None:
            for leg_net, layer, a, b in ctx.failed:
                if leg_net != net or layer in planes:
                    continue
                width = POUR_GRID_NM + max(
                    rule_of_thumb(
                        current,
                        profile.resolve("width_per_amp_nm", ctx.roles.limits, net=net, kind="ground").value
                        or 0,
                    ),
                    ctx.track_width(net),
                )
                landed = 0
                for pad in (a, b):
                    anchors = _clusters(ctx, [pad], layer, width)
                    if _landing(
                        ctx,
                        net,
                        current,
                        (layer, planes[0]),
                        anchors,
                        "ground",
                        width,
                        connection,
                        records,
                        bands_on=(layer,),
                        key=f"role.via.{safe(net)}.{safe(pad)}",
                    ):
                        made.append(f"role.ground.{safe(net)}.{safe(layer)}")
                        landed += 1
                if landed == 2:  # the leg closes through the plane: no copper is missing
                    ctx.issues = [
                        found
                        for found in ctx.issues
                        if not (
                            found.code == "roles.copper-blocked"
                            and found.where == f"{net}@{layer}"
                            and a in found.message
                            and b in found.message
                        )
                    ]
        board = ctx.design.board
        assert board is not None
        net_id = ctx.nets[net].id
        held = {layer for zone in board.zones if zone.net_id == net_id for layer in zone.layers}
        all_layers = [layer for layer in ctx.copper if layer in held | set(planes)]
        if planes and len(all_layers) >= 2:
            diameter, drill = ctx.via(net)
            records.append(
                RoleStitch(
                    name=f"role.stitch.{safe(net)}",
                    net=net,
                    pitch=ctx.request.stitch_pitch or STITCH_PITCH_NM,
                    layers=tuple(all_layers),
                    min_vias=STITCH_MIN_VIAS,
                    diameter=diameter,
                    drill=drill,
                    # a stitching via is judged against every copper by one clearance: the largest in force
                    clearance=max(
                        [
                            ctx.clearance(net),
                            *(cls.clearance for cls in ctx.classes.values() if cls.clearance),
                        ]
                    ),
                )
            )
        found.append(
            NetPlan(
                net,
                "ground",
                None,
                None,
                None,
                tuple(planes + band_layers),
                tuple(made),
                None if made else "user-copper",
            )
        )
    return found


# --- high voltage ----------------------------------------------------------------------------------------


def _hv_rule(ctx: _Ctx, net: str, distance: int) -> Rule:
    """The clearance of the bus to every other copper: one selector, the bus (a clearance holds between
    different nets only), which both KiCad and Altium write (scope 1 the net, scope 2 all)."""
    name = f"role.hv.{safe(net)}"
    return Rule(
        id=derived_id("rul", "roles", name),
        name=name,
        kind="clearance",
        selector_a=Selector("net", glob_escape(net)),
        min=distance,
    )


def _sw_rules(net: str, victims: Sequence[str], distance: int) -> list[Rule]:
    """``role.sw.<net>`` to its one victim, or ``role.sw.<net>.<victim>`` to each of several: a rule between
    two nets, which both KiCad and Altium write (Altium takes no union of nets in a scope)."""
    found: list[Rule] = []
    for victim in victims:
        name = f"role.sw.{safe(net)}" if len(victims) == 1 else f"role.sw.{safe(net)}.{safe(victim)}"
        found.append(
            Rule(
                id=derived_id("rul", "roles", name),
                name=name,
                kind="clearance",
                selector_a=Selector("net", glob_escape(net)),
                selector_b=Selector("net", glob_escape(victim)),
                min=distance,
            )
        )
    return found


# --- corridors -------------------------------------------------------------------------------------------


def _corridor_width(ctx: _Ctx, net: str) -> int:
    """``2 × class width + pair gap + 2 × clearance`` (a Fenolite heuristic after S-0852 and S-0853)."""
    cls = ctx.netclass(net)
    width = cls.track_width if cls is not None and cls.track_width else 250_000
    clearance = ctx.clearance(net)
    gap = cls.diff_pair_gap if cls is not None and cls.diff_pair_gap else clearance
    return 2 * width + gap + 2 * clearance


def _segment_ring(a: Point, b: Point, half: int) -> tuple[Point, ...] | None:
    """The rectangle around the segment ``ab`` reaching ``half`` on each side (its ends flat), rounded to
    nanometres."""
    dx, dy = b.x - a.x, b.y - a.y
    size = math.isqrt(dx * dx + dy * dy)
    if size == 0:
        return None
    nx, ny = -dy * half // size, dx * half // size
    return (
        Point(a.x + nx, a.y + ny),
        Point(b.x + nx, b.y + ny),
        Point(b.x - nx, b.y - ny),
        Point(a.x - nx, a.y - ny),
    )


def _corridor_nets(ctx: _Ctx) -> list[tuple[str, str, str, list[str]]]:
    """``(group, net, kind, pads)`` for each net of each gate loop and Kelvin pair, the pads in route
    order."""
    nets = {pad_name(pad): pad.net for pad in ctx.pads}
    copper_roles = {role.net for role in ctx.roles.nets if role.kind in KINDS}
    found: list[tuple[str, str, str, list[str]]] = []
    for gate in ctx.roles.gates:
        out = [gate.drive, *gate.resistor, gate.gate]
        back = [gate.source, gate.ret]
        for pads in (out, back):
            by_net: dict[str, list[str]] = {}
            for pad in pads:
                net = nets.get(pad)
                if net is not None:
                    by_net.setdefault(net, []).append(pad)
            for net, members in sorted(by_net.items()):
                # a return through the switch node or a power ground joins that copper by design
                if len(members) >= 2 and net not in copper_roles:
                    found.append((gate.name, net, "gate", members))
    for pair in ctx.roles.kelvins:
        for element, receiver in zip(pair.element, pair.receiver, strict=True):
            net = nets.get(element)
            if net is not None and nets.get(receiver) == net:
                found.append((pair.name, net, "kelvin", [element, receiver]))
    return found


def _plan_corridors(ctx: _Ctx, keepouts: list[Keepout]) -> list[Corridor]:
    """The provisional corridor of each critical net that has no ``role.corridor.<group>.<net>`` area yet:
    along the net's own tracks on the outer layer of its pads where they join the pads, else the straight
    segments between the pads (a Kelvin end on the inner half of its sense pad). A corridor over another
    net's pad or a locked item of another net is left out (``roles.corridor-blocked``)."""
    board = ctx.design.board
    assert board is not None
    names = _net_id_names(ctx.design)
    held = {area.name for area in board.keepouts if area.name.startswith("role.corridor.")}
    by_name = {pad_name(pad): pad for pad in ctx.pads}
    found: list[Corridor] = []
    for group, net, kind, pads in _corridor_nets(ctx):
        records = [by_name[p] for p in pads if p in by_name]
        if len(records) < 2:
            continue
        outer = [
            layer for layer in (ctx.copper[0], ctx.copper[-1]) if all(_on_layer(r, layer) for r in records)
        ]
        if not outer:
            outer = [
                layer
                for layer in (ctx.copper[0], ctx.copper[-1])
                if any(_on_layer(r, layer) for r in records)
            ]
        if not outer:
            continue
        layer = outer[0]
        corridor_key = corridor_name(group, net)
        width = _corridor_width(ctx, net)
        half = width // 2
        if any(name == corridor_key or name.startswith(corridor_key + ".") for name in held):
            found.append(Corridor(group, net, kind, layer, (), width, "found"))
            continue
        net_id = ctx.nets[net].id if net in ctx.nets else None
        own = [t for t in board.tracks if t.net_id == net_id and t.layer == layer]
        if kind == "kelvin":
            own = [t for t in own if t.id in set(_sense_branches(ctx))]
            if {t.id for t in own} & _loose_tracks(ctx, net):
                continue  # the branch hangs from the net's power copper: no isolated route to keep free
        segments: list[tuple[Point, Point]]
        if own:
            segments = [(t.start, t.end) for t in own]
        else:
            points = [
                _kelvin_point(ctx, by_name[p]) if kind == "kelvin" else by_name[p].position for p in pads
            ]
            segments = list(zip(points, points[1:], strict=False))
        boxes = [box for record in records if (box := _copper_box(record)) is not None]
        segments = [cut for a, b in segments if (cut := _outside(a, b, boxes)) is not None]
        pieces = [ring for a, b in segments if (ring := _segment_ring(a, b, half)) is not None]
        if not pieces:
            continue
        mates = {other_net for g, other_net, _, _ in _corridor_nets(ctx) if g == group}
        blocking = _blocking(ctx, pieces, layer, mates, names)
        if blocking:
            ctx.issues.append(
                issue(
                    "roles.corridor-blocked",
                    f"the corridor of {net} in {group} on {layer} would cover {blocking}; it is not written",
                    where=corridor_key,
                    hint="phase 2 routes around that copper, or move it",
                )
            )
            continue
        for number, ring in enumerate(pieces):
            name = corridor_key if number == 0 else f"{corridor_key}.{number}"
            keepouts.append(
                Keepout(
                    id=derived_id("kpo", "dsl", f"area:{name}"),
                    outline=ring,
                    layers=(layer,),
                    no_copper_pour=True,
                    name=name,
                )
            )
        found.append(Corridor(group, net, kind, layer, tuple(pieces), width, "provisional"))
    return found


def _outside(a: Point, b: Point, boxes: Sequence[BBox]) -> tuple[Point, Point] | None:
    """The segment ``ab`` with each end that lies in one of ``boxes`` (the corridor's own pads) moved along
    it to where it leaves that box, so a corridor starts at the pad's edge; ``None`` when nothing is left."""

    def inside(point: Point, box: BBox) -> bool:
        return box.x0 <= point.x <= box.x1 and box.y0 <= point.y <= box.y1

    def leave(start: Point, end: Point) -> Point | None:
        for box in boxes:
            if not inside(start, box):
                continue
            dx, dy = end.x - start.x, end.y - start.y
            limits: list[Fraction] = []
            if dx:
                limits.append(Fraction((box.x1 if dx > 0 else box.x0) - start.x, dx))
            if dy:
                limits.append(Fraction((box.y1 if dy > 0 else box.y0) - start.y, dy))
            share = min(limits, default=Fraction(1))
            if share >= 1:
                return None
            return Point(start.x + round(share * dx), start.y + round(share * dy))
        return start

    first = leave(a, b)
    last = leave(b, a)
    if first is None or last is None or first == last:
        return None
    return first, last


def _kelvin_point(ctx: _Ctx, pad: BoardPad) -> Point:
    """The middle of the inner half of a sense pad (toward the other sense pad), else its position."""
    name = pad_name(pad)
    for pair in ctx.roles.kelvins:
        if name in pair.element:
            outer = _spine_point(ctx, pad)
            return Point(2 * pad.position.x - outer.x, 2 * pad.position.y - outer.y)
    return pad.position


def _blocking(
    ctx: _Ctx, pieces: Sequence[tuple[Point, ...]], layer: str, mates: set[str], names: Mapping[str, str]
) -> str:
    """The first pad of a net outside ``mates``, or locked item of such a net, that a piece covers."""
    board = ctx.design.board
    assert board is not None
    shapes = [Thick(piece, 0, filled=True) for piece in pieces]
    for pad in sorted(ctx.pads, key=pad_name):
        if pad.net in mates or pad.net is None:
            continue
        for copper in _pad_shapes(pad, layer):
            if any(thick_closer_than(shape, copper, 1) for shape in shapes):
                return f"pad {pad_name(pad)} of {pad.net}"
    for track in board.tracks:
        other = names.get(track.net_id or "")
        if track.locked and other not in mates and track.layer == layer:
            if any(thick_closer_than(s, Thick((track.start, track.end), track.width), 1) for s in shapes):
                return f"locked track {track.id} of {other}"
    for zone in board.zones:
        other = names.get(zone.net_id or "")
        if _is_role_key(zone.name) or other in mates or layer not in zone.layers or len(zone.outline) < 3:
            continue
        if any(thick_closer_than(s, Thick(tuple(zone.outline), 0, filled=True), 1) for s in shapes):
            return (
                f"the zone {zone.name or zone.id} of {other}"  # a no-pour corridor would cut the user's pour
            )
    return ""


# --- the plan --------------------------------------------------------------------------------------------


def plan(
    design: Design,
    pads: Sequence[BoardPad],
    roles: RoleSet,
    request: object | None = None,
    *,
    requirements: Requirements | None = None,
    classes: Mapping[str, Classified] | None = None,
) -> RoleCopperPlan:
    """The role copper of the placed board ``design`` (pads in the board frame) for the resolved ``roles``,
    in the order of decision 11: provisional corridors, high-voltage rules, the bands of the switch nodes,
    then of the power and high-voltage nets, net barriers, ground zones, ground stitching and via arrays.
    Only ``confirmed`` and ``declared`` roles get copper."""
    asked = request_of(request)
    board = design.board
    if board is None:
        return RoleCopperPlan()
    copper = tuple(la.name for la in sorted(board.layers, key=lambda la: la.ordinal) if la.kind == "copper")
    ctx = _Ctx(
        design=design,
        pads=tuple(pads),
        roles=roles,
        request=asked,
        requirements=requirements,
        nets={net.name: net for net in design.circuit.nets},
        classes={cls.id: cls for cls in design.circuit.netclasses},
        copper=copper,
        part_classes=classes if classes is not None else _classes(design, pads, roles),
    )
    records: list[RoleRecord] = []
    zones: list[Zone] = []
    keepouts: list[Keepout] = []
    rules: list[Rule] = []
    plans: list[NetPlan] = []
    corridors = _plan_corridors(ctx, keepouts) if asked.corridors else []
    if keepouts:
        ctx.design = _with_keepouts(design, keepouts)
    hv = set(high_voltage_nets(RoleBoard(design, ctx.pads, roles, {})))
    chosen: list[NetRole] = []
    for role in roles.nets:
        kind = "high_voltage" if role.kind == "high_voltage" else role.kind
        if kind not in KINDS or kind not in asked.kinds:
            continue
        if asked.nets and not any(_glob(role.net, pattern) for pattern in asked.nets):
            continue
        if role.source == "inferred":
            ctx.issues.append(
                issue(
                    "roles.copper-skipped",
                    f"the {role.kind} role of {role.net} is inferred and not confirmed: no copper "
                    "(unconfirmed)",
                    severity="info",
                    where=role.net,
                    hint="confirm it with fenolite roles PATH --accept, or declare it in the script",
                )
            )
            plans.append(NetPlan(role.net, role.kind, skipped="unconfirmed"))
            continue
        chosen.append(role)
    # high-voltage rules first, so the reach of each bus keeps the other nets' spines away
    distances: dict[str, int] = {}
    hv_rules: dict[str, Rule] = {}
    for role in chosen:
        if role.net not in hv:
            continue
        distance = _distance_of(ctx, role.net)
        if distance is None:
            ctx.issues.append(
                issue(
                    "roles.limit-missing",
                    f"the high-voltage net {role.net} has no distance requirement: no role copper is "
                    "generated "
                    "for it",
                    where=role.net,
                    hint="add [[distance]] rows (or a [[step]] table) for its working voltage (S-0854)",
                )
            )
            continue
        distances[role.net] = distance
        hv_rules[role.net] = _hv_rule(ctx, role.net, distance)
        ctx.hv_reach.append((role.net, distance))
    order = {"switch_node": 0, "power": 1, "high_voltage": 1}
    ctx.bounds = BBox.of_points(ctx.board_outline) if len(ctx.board_outline) >= 3 else None
    widths: dict[str, tuple[str, int]] = {}
    for role in chosen:
        if (
            role.kind in order
            and role.milliamps is not None
            and (role.net not in hv or role.net in distances)
        ):
            names = _terminal_pads(ctx, role.net)
            widths[role.net] = (
                role.kind,
                _net_width(ctx, role, _layers_of(ctx, role, names)).value + POUR_GRID_NM,
            )
        elif role.kind == "ground" and "ground" in asked.kinds:
            current = _loop_current(ctx, role.net)
            per_amp = (
                profile.resolve("width_per_amp_nm", roles.limits, net=role.net, kind="ground").value or 0
            )
            if current is not None:
                widths[role.net] = (
                    "ground",
                    max(rule_of_thumb(current, per_amp), ctx.track_width(role.net)) + POUR_GRID_NM,
                )

    def handle(role: NetRole) -> None:
        kind = "high_voltage" if role.kind == "high_voltage" else role.kind
        if role.net in hv and role.net not in distances:
            plans.append(NetPlan(role.net, role.kind, skipped="limit-missing"))
            return
        if role.milliamps is None:
            ctx.issues.append(
                issue(
                    "roles.copper-skipped",
                    f"the {role.kind} role of {role.net} has no current: no copper (current-missing); "
                    "Fenolite "
                    "assumes none",
                    severity="warning",
                    where=role.net,
                    hint="give it with design.net_role(..., current=...), --current or a [[current]] row",
                )
            )
            plans.append(NetPlan(role.net, role.kind, skipped="current-missing"))
            return
        made = _plan_net(ctx, role, kind, records, role.net in hv)
        plans.append(made)
        if role.kind == "switch_node":
            victims = victim_nets(roles, ctx.pads, role.net, ctx)
            distance = profile.resolve(
                "switching_distance_nm", roles.limits, net=role.net, kind="kelvin"
            ).value
            if victims and distance:
                rules.extend(_sw_rules(role.net, sorted(victims), distance))

    planes = _plane_layers(ctx)
    ordered = sorted(
        (r for r in chosen if r.kind in order or (r.kind == "ground" and r.milliamps is not None)),
        key=lambda r: (order.get(r.kind, 2), r.net),
    )
    # the high-voltage nets first, whole, so their keep-out envelope is known to every other spine; then the
    # hot-loop legs of the other nets; then the rest of their trees
    _route_legs(ctx, {net: found for net, found in widths.items() if net in distances}, planes)
    for role in ordered:
        if role.net in distances:
            handle(role)
    _route_legs(ctx, {net: found for net, found in widths.items() if net not in distances}, planes)
    for role in ordered:
        if role.net not in distances:
            handle(role)
    # the rule and the barrier of a bus go with its role copper: a bus that the user drew (``user-copper``)
    # keeps the user's rules, and its reach still keeps the other nets' spines away
    generated_nets = {found.net for found in plans if found.zones}
    for net, distance in sorted(distances.items()):
        if net not in generated_nets:
            continue
        rules.append(hv_rules[net])
        layers = tuple(ctx.copper)
        records.append(RoleBarrier(name=f"role.hv.{safe(net)}", nets=(net,), setback=distance, layers=layers))
    ctx.issues += _placement_faults(ctx)
    if "ground" in asked.kinds:
        grounds = [role for role in chosen if role.kind == "ground"]
        plans += _plan_ground(ctx, grounds, records, zones)
    tracks = _join_loose(ctx, records)
    records = _fenced(ctx, records)
    if "clipper" not in available_backends():
        records = _without_union(ctx, records)
    if asked.keep:
        # a kept role item (``keep``, or edited by the user) is not generated again
        keeps = set(asked.keep)

        def generated(key: str) -> bool:
            return key not in keeps and not any(key.startswith(name + ".") for name in keeps)

        records = [r for r in records if generated(getattr(r, "group", "") or r.key)]
        zones = [z for z in zones if generated(z.name)]
        keepouts = [k for k in keepouts if generated(k.name)]
    # a provisional corridor keeps the run's own pours out: on a layer where the run pours nothing, it would
    # only cut the user's pours, so it is not written
    poured = {layer for r in records if isinstance(r, RoleBand) for layer in r.layers}
    poured |= {layer for zone in zones for layer in zone.layers}
    idle = {c.key for c in corridors if c.origin == "provisional" and c.layer not in poured}
    if idle:
        corridors = [c for c in corridors if c.key not in idle]
        keepouts = [
            k for k in keepouts if not any(k.name == key or k.name.startswith(key + ".") for key in idle)
        ]
    merged: dict[str, NetPlan] = {}
    for found in plans:
        held = merged.get(found.net)
        if held is None:
            merged[found.net] = found
            continue
        layers = tuple(layer for layer in ctx.copper if layer in {*held.layers, *found.layers})
        merged[found.net] = replace(
            held,
            method=held.method or found.method,
            width=held.width or found.width,
            max_width=held.max_width or found.max_width,
            layers=layers,
            zones=tuple(dict.fromkeys((*held.zones, *found.zones))),
            skipped=None if (held.zones or found.zones) else held.skipped or found.skipped,
            vias=held.vias + found.vias,
        )
    plans = sorted(merged.values(), key=lambda found: found.net)
    return RoleCopperPlan(
        records=tuple(records),
        zones=tuple(zones),
        keepouts=tuple(keepouts),
        rules=tuple(rules),
        issues=tuple(ctx.issues),
        nets=tuple(plans),
        corridors=tuple(corridors),
        tracks=tuple(tracks),
    )


def _classes(design: Design, pads: Sequence[BoardPad], roles: RoleSet) -> Mapping[str, Classified]:
    counts: dict[str, int] = {}
    for record in pads:
        counts[record.ref] = counts.get(record.ref, 0) + 1
    return classify(design.circuit, user=roles.classes, pad_counts=counts)


def _placement_faults(ctx: _Ctx) -> list[Issue]:
    """``roles.copper-placement`` for each hot loop whose placement bound (the area of the polygon of its
    pads' positions, c0222) is already over the user's ``loop_max``: no copper can meet the limit, and phase
    1 does not move parts (decision 4)."""
    from fenolite.geometry import area2

    nets = {pad_name(pad): pad for pad in ctx.pads}
    found: list[Issue] = []
    for loop in ctx.roles.loops:
        points = [nets[pad].position for pad in loop.pads if pad in nets]
        if len(points) != len(loop.pads):
            continue
        node = next(
            (
                nets[pad].net
                for pad in loop.pads
                if (role := ctx.roles.role_of(nets[pad].net or "")) is not None and role.kind == "switch_node"
            ),
            None,
        )
        largest = profile.resolve("loop_max", ctx.roles.limits, net=node, kind="switch_node")
        bound = abs(area2(points)) // 2
        if largest.value is not None and bound > largest.value:
            found.append(
                issue(
                    "roles.copper-placement",
                    f"the placement bound of the hot loop {loop.name} is {_mm2(bound)} mm², over the "
                    f"{_mm2(largest.value)} mm² of {largest.text()}: no copper can meet it; the copper is "
                    "drawn",
                    where=loop.name,
                    hint="place the input capacitor across the switches",
                )
            )
    return found


def _mm2(value: int) -> str:
    whole, part = divmod(value, profile.MM2)
    text = f"{part * 100 // profile.MM2:02d}".rstrip("0")
    return f"{whole}.{text}" if text else f"{whole}"


def _glob(name: str, pattern: str) -> bool:
    import fnmatch

    return fnmatch.fnmatchcase(name, pattern)


def _with_keepouts(design: Design, keepouts: Sequence[Keepout]) -> Design:
    board = design.board
    assert board is not None
    return replace(design, board=replace(board, keepouts=(*board.keepouts, *keepouts)))


# --- the simulated pour as fills -------------------------------------------------------------------------


def cell_rings(cells: set[tuple[int, int]], grid: int) -> list[tuple[Point, ...]]:
    """The boundary rings of a set of raster cells (cell ``(i, j)`` spans ``[i·grid, (i+1)·grid]`` on each
    axis): each edge between a cell and a non-cell, chained with the cell on its right, a corner where two
    cells touch only diagonally kept apart; collinear points dropped. Outer rings and holes turn opposite
    ways."""
    edges: dict[tuple[int, int], list[tuple[int, int]]] = {}

    def add(a: tuple[int, int], b: tuple[int, int]) -> None:
        edges.setdefault(a, []).append(b)

    for i, j in cells:
        if (i, j - 1) not in cells:
            add((i + 1, j), (i, j))
        if (i + 1, j) not in cells:
            add((i + 1, j + 1), (i + 1, j))
        if (i, j + 1) not in cells:
            add((i, j + 1), (i + 1, j + 1))
        if (i - 1, j) not in cells:
            add((i, j), (i, j + 1))
    rings: list[tuple[Point, ...]] = []
    while edges:
        start = min(edges)
        ring = [start]
        previous: tuple[int, int] | None = None
        current = start
        while True:
            options = edges[current]
            if len(options) == 1 or previous is None:
                chosen = options[0]
            else:
                dx, dy = current[0] - previous[0], current[1] - previous[1]
                # at a diagonal touch, turn so the two cells stay apart: the turn toward the cell side
                back = (current[0] + dy, current[1] - dx)
                chosen = back if back in options else options[0]
            options.remove(chosen)
            if not options:
                del edges[current]
            previous, current = current, chosen
            if current == start:
                break
            ring.append(current)
        points = [Point(x * grid, y * grid) for x, y in ring]
        simplified: list[Point] = []
        size = len(points)
        for index, point in enumerate(points):
            a, c = points[index - 1], points[(index + 1) % size]
            if (a.x == point.x == c.x) or (a.y == point.y == c.y):
                continue
            simplified.append(point)
        if len(simplified) >= 4:
            rings.append(tuple(simplified))
    return rings


def with_simulated_fills(design: Design, pads: Sequence[BoardPad]) -> Design:
    """``design`` with the simulated pour (``analysis.pour``) stored as the fills of each zone layer that has
    none: the cells of each kept island traced into rings, holes joined by keyholes. The judge then reads
    the role copper as it reads a saved fill (decision 10: the result is judged on the simulated pour)."""
    from fenolite.analysis.pour import DEFAULT_GRID_NM, pour_copper
    from fenolite.geometry import area2, keyhole_ring, point_in_ring
    from fenolite.model.board import ZoneFill

    board = design.board
    if board is None:
        return design
    pour = pour_copper(design, pads=pads, boundary=board_boundary(board), grid=DEFAULT_GRID_NM)
    simulated = {(z.zone_id, z.layer) for z in pour.zones if z.state == "simulated"}
    if not simulated:
        return design
    names = {zone.id: zone for zone in board.zones}
    wheres = {z.where: z.zone_id for z in pour.zones}
    fills: dict[str, list[ZoneFill]] = {}
    for island in pour.islands:
        rings = cell_rings(set(island.cells), pour.grid)
        outers = [ring for ring in rings if area2(ring) < 0]
        holes = [ring for ring in rings if area2(ring) > 0]
        owner = next((wheres.get(where, where) for where in island.zones), None)
        if owner is None or owner not in names or (owner, island.layer) not in simulated:
            continue
        for outer in outers:
            inner = [hole for hole in holes if point_in_ring(hole[0], outer).name != "OUTSIDE"]
            ring = keyhole_ring(outer, inner).ring if inner else outer
            fills.setdefault(owner, []).append(ZoneFill(island.layer, tuple(ring)))
    zones = tuple(
        replace(zone, fills=(*zone.fills, *fills[zone.id]), filled=True) if zone.id in fills else zone
        for zone in board.zones
    )
    return replace(design, board=replace(board, zones=zones))


# --- a run: plan, apply, judge -----------------------------------------------------------------------------


Apply = Callable[[Design, RoleCopperPlan], tuple[Design, list[Issue]]]
"""What applies a plan to a design (``lens.rolecopper.apply_plan``): the design after, and the issues of the
resolution."""
GENERATE_TO_ROLES: Mapping[str, str] = {
    "kicad.generate.band-narrow": "roles.copper-narrow",
    "kicad.generate.crossing": "roles.copper-blocked",
    "kicad.generate.off-board": "roles.copper-blocked",
}


@dataclass(frozen=True, slots=True)
class Outcome:
    """A run's result: the design after (the input when refused), the plan, every issue, and the summary of
    ``result`` (``nets``, ``vias``, ``corridors``, ``rules``, ``kept``, ``before``, ``after``,
    ``cleared``)."""

    design: Design
    plan: RoleCopperPlan
    issues: tuple[Issue, ...]
    summary: Mapping[str, object]
    evidence: Evidence = EVIDENCE

    @property
    def refused(self) -> bool:
        return any(found.severity == "error" for found in self.issues)


def _translated(found: Issue) -> Issue:
    """A ``kicad.generate.*`` issue of a role record as the role code it stands for."""
    if not found.where.startswith("role.") and not found.where.startswith("band.role."):
        return found
    code = GENERATE_TO_ROLES.get(found.code)
    if code is None:
        return found
    return issue(code, found.message, where=found.where, hint=found.hint)


def _worse(before: Sequence[Issue], after: Sequence[Issue]) -> tuple[list[Issue], list[Issue]]:
    """The findings of warning or above of ``after`` that ``before`` lacks (by code and subject), and those of
    ``before`` that ``after`` lacks (cleared). The topological findings (``codes.TOPOLOGICAL``: where a
    Kelvin branch or a gate return attaches) belong to the routes of the user and of phase 2, which phase 1
    keeps as they are: they are reported, never counted as worse."""

    def keys(found: Sequence[Issue]) -> dict[tuple[str, str], Issue]:
        return {
            (i.code, i.where): i
            for i in found
            if i.severity in NOT_WORSE and i.code.startswith("roles.") and i.code not in TOPOLOGICAL
        }

    old, new = keys(before), keys(after)
    return [new[k] for k in sorted(new) if k not in old], [old[k] for k in sorted(old) if k not in new]


def run(
    design: Design,
    pads: Sequence[BoardPad],
    request: object | None,
    apply: Apply,
    *,
    stored: RoleSet | None = None,
    declared: RoleSet | None = None,
    requirements: Requirements | None = None,
    circuit: Any = None,
    keep_ids: Sequence[str] = (),
) -> Outcome:
    """Resolve the roles of ``design``, judge it, plan its role copper, apply the plan with ``apply`` and
    judge the result on the simulated pour. A finding of warning or above on the result that the input
    lacked is ``roles.copper-worse`` (error): the outcome is then refused and keeps the input design."""
    from fenolite.roles.judge import run as judge_run
    from fenolite.roles.measure import Inputs

    inputs = Inputs(requirements=requirements, temp_rise_mk=request_of(request).temp_rise)
    if declared is None and design.rules is not None and design.rules.roles is not None:
        from fenolite.roles.judge import split_roles

        declared, own = split_roles(design.rules.roles)
        stored = stored if stored is not None else own
    before = judge_run(
        with_simulated_fills(design, pads),
        pads,
        circuit=circuit,
        stored=stored,
        declared=declared,
        inputs=inputs,
    )
    roles = before.resolved.roles
    made = plan(design, pads, roles, request, requirements=requirements, classes=before.resolved.classes)
    after_design, resolved = apply(design, made)
    issues: list[Issue] = [*made.issues, *(_translated(found) for found in resolved)]
    after = judge_run(
        with_simulated_fills(after_design, pads),
        pads,
        circuit=circuit,
        stored=stored,
        declared=declared,
        inputs=inputs,
    )
    worse, cleared = _worse(before.issues, after.issues)
    for found in worse:
        issues.append(
            issue(
                "roles.copper-worse",
                f"the role copper adds {found.code} on {found.where}: {found.message}",
                where=found.where,
                hint="nothing is written; move the parts or give the planner other layers or widths",
            )
        )
    summary: dict[str, object] = {
        "nets": [found.to_json() for found in made.nets],
        "vias": sum(found.vias for found in made.nets),
        "corridors": [found.to_json() for found in made.corridors],
        "rules": [rule.name for rule in made.rules],
        "records": len(made.records),
        "before": _findings(before.issues),
        "after": _findings(after.issues),
        "cleared": _findings(cleared),
    }
    outcome_design = after_design if not worse else design
    return Outcome(
        outcome_design,
        made,
        tuple(dict.fromkeys(issues)),
        summary,
        Evidence.combine(EVIDENCE, after.evidence),
    )


def _findings(found: Sequence[Issue]) -> list[dict[str, str]]:
    return [
        {"code": i.code, "severity": i.severity, "where": i.where}
        for i in found
        if i.code.startswith("roles.") and i.severity in NOT_WORSE
    ]


__all__ = [
    "CONNECTIONS",
    "DEFAULT_CONNECTION",
    "EVIDENCE",
    "GROUND_FILLS",
    "KINDS",
    "STITCH_MIN_VIAS",
    "STITCH_PITCH_NM",
    "WIDEN_PERMILLE",
    "Corridor",
    "NetPlan",
    "Outcome",
    "Request",
    "RoleBand",
    "RoleBarrier",
    "RoleCopperPlan",
    "RoleStitch",
    "Width",
    "fit_width",
    "plan",
    "request_of",
    "required_width",
    "rule_of_thumb",
    "run",
    "safe",
    "victim_nets",
]

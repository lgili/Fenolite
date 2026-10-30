# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The subjects of the proposals of phase 4 (change c0280; capability net-roles, "Leftover opens of role
copper are proposed"; ``docs/roles.md``, "Proposals after the critical routes").

``subjects`` reads a board after phases 1 and 2 and gives each open connection one subject, of the first kind
that fits, in this order:

- ``fanout``: a pad in an island that holds no via and no through-hole pad, with a zone of its net on another
  copper layer within ``reach`` of it (``fanout:<net>:<REF-N>``);
- ``join``: two islands of a net, one of which holds role copper (a zone named ``role.*``, locked copper, or a
  zone of a stated role net), or a net that phase 1 reported ``roles.copper-blocked``
  (``join:<net>:<a>~<b>``); its ends are the nearest attach points, pad and track ends of one island and,
  for an island with a zone, the nearest point of the zone's copper that a track of the net's width reaches
  with the zone clearance to spare;
- ``role-net``: an open connection of a ``power``, ``switch_node``, ``ground`` or ``high_voltage`` net that
  phase 1 sized no copper for, being inferred and unconfirmed or without a stated current
  (``role-net:<net>:<a>~<b>``);
- ``connection``: any other open connection (``connection:<net>:<a>~<b>``);

and each critical group that phase 2 left ``unrouted`` or ``refused`` one ``group`` subject
(``group:<name>``). The open connections and islands are those of ``analysis.connectivity`` on the pour of
``analysis.pour`` (a saved fill, else the simulated pour), so the count is KiCad's (task 0.1). The subjects
are this package's own types; ``fenolite route --propose`` turns them into routing-protocol subjects. Nothing
here writes copper.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from math import isqrt

from fenolite.analysis.boundary import board_boundary
from fenolite.analysis.connectivity import (
    LinkEnd,
    NetIsland,
    OpenConnection,
    connectivity,
    net_islands,
)
from fenolite.analysis.pour import DEFAULT_GRID_NM, Cell, PourCopper, pour_copper
from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.geometry import Location, dist2_point_segment, point_in_ring
from fenolite.model.board import Zone
from fenolite.model.design import Design
from fenolite.model.rules import RoleSet

KINDS = ("fanout", "join", "role-net", "group", "connection")
"""The subject kinds, in the order proposals are sorted."""
FANOUT_REACH = 2_000_000
"""How far a zone of the pad's net may lie from the pad for a ``fanout`` subject (decision 2)."""
ROLE_NET_KINDS = frozenset({"power", "switch_node", "ground", "high_voltage"})
"""The role kinds whose inferred nets are ``role-net`` subjects and whose zones are role copper."""
ATTACH_REACH = 20_000_000
"""How far from an anchor the nearest point of a zone's copper is looked for."""


@dataclass(frozen=True, slots=True)
class Attach:
    """One end of a subject: ``pad``, ``track-end`` or ``zone``, its net, the point copper must reach, its
    copper layers and its name (``REF-N``, ``trk@x,y``, ``via@x,y``, the zone's name or ``zone@<layer>``)."""

    kind: str
    net: str
    at: Point
    layers: tuple[str, ...]
    name: str


@dataclass(frozen=True, slots=True)
class OpenGroup:
    """A critical group that phase 2 left open: its name, its status (``unrouted`` or ``refused``), its
    reason, and the key, net and ends of each open role route, in route order."""

    name: str
    status: str
    reason: str
    routes: tuple[tuple[str, str, Attach, Attach], ...]


@dataclass(frozen=True, slots=True)
class Subject:
    """One subject: its key, kind and net, its two ends, the c0244 group and route keys of a ``group``
    subject, the length of its open connection, ``hot`` for a net of a hot loop, ``inferred`` the role kind
    of a ``role-net`` subject's net, and ``reason`` for a subject that cannot have a candidate (``pads``)."""

    key: str
    kind: str
    net: str
    a: Attach
    b: Attach
    group: str = ""
    routes: tuple[str, ...] = ()
    length: int = 0
    hot: bool = False
    inferred: str = ""
    reason: str = ""

    @property
    def proposal(self) -> str:
        """``p-`` and 16 hex digits of the SHA-256 of the canonical JSON of the key and the ends' positions:
        it changes when an end moves."""
        data = [self.key, [self.a.at.x, self.a.at.y], [self.b.at.x, self.b.at.y]]
        text = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return "p-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class SubjectPlan:
    """The subjects sorted by kind then key, the number of open connections of the board, and the board's
    fill state (``saved`` when every zone layer is its saved fill, else ``simulated``)."""

    subjects: tuple[Subject, ...] = ()
    open: int = 0
    fill: str = "saved"


# --- the copper of zones ------------------------------------------------------------------------------------


class ZoneCopper:
    """The copper of the zones of a board as the pour gives it: the saved fill of a zone layer, else its
    simulated pour (cells of ``pour.grid``), else its outline. ``covers`` says whether a disc lies in it."""

    def __init__(self, design: Design, pour: PourCopper) -> None:
        board = design.board
        self.grid = pour.grid
        names = {net.id: net.name for net in design.circuit.nets}
        self.cells: dict[tuple[str, str], set[Cell]] = {}
        for island in pour.islands:
            self.cells.setdefault((island.net, island.layer), set()).update(island.cells)
        self.rings: dict[tuple[str, str], list[tuple[Point, ...]]] = {}
        states = {(z.zone_id, z.layer): z.state for z in pour.zones}
        for zone in board.zones if board is not None else ():
            net = names.get(zone.net_id or "")
            if net is None:
                continue
            for fill in zone.fills:
                if states.get((zone.id, fill.layer)) == "saved_fill" and len(fill.polygon) >= 3:
                    self.rings.setdefault((net, fill.layer), []).append(fill.polygon)
            for layer in zone.layers:
                if states.get((zone.id, layer)) == "outline" and len(zone.outline) >= 3:
                    self.rings.setdefault((net, layer), []).append(zone.outline)
        self.simulated = any(z.state != "saved_fill" for z in pour.zones)

    def inside(self, net: str, layer: str, point: Point) -> bool:
        cells = self.cells.get((net, layer))
        if cells is not None and (point.x // self.grid, point.y // self.grid) in cells:
            return True
        return any(
            point_in_ring(point, ring) is not Location.OUTSIDE for ring in self.rings.get((net, layer), ())
        )

    def covers(self, net: str, layer: str, at: Point, radius: int) -> bool:
        """Whether the disc of ``radius`` around ``at`` lies in the zone copper of ``net`` on ``layer``: its
        centre and eight points of its rim, the rim taken one cell wider on a simulated pour."""
        if not self.inside(net, layer, at):
            return False
        reach = radius + (self.grid if (net, layer) in self.cells else 0)
        diagonal = isqrt(reach * reach // 2) + 1
        for dx, dy in ((reach, 0), (-reach, 0), (0, reach), (0, -reach)):
            if not self.inside(net, layer, Point(at.x + dx, at.y + dy)):
                return False
        for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            if not self.inside(net, layer, Point(at.x + sx * diagonal, at.y + sy * diagonal)):
                return False
        return True

    def has(self, net: str, layer: str) -> bool:
        return bool(self.cells.get((net, layer)) or self.rings.get((net, layer)))

    def _box(self, net: str, layer: str) -> tuple[int, int, int, int] | None:
        xs: list[int] = []
        ys: list[int] = []
        cells = self.cells.get((net, layer), set())
        if cells:
            xs += [min(c[0] for c in cells) * self.grid, (max(c[0] for c in cells) + 1) * self.grid]
            ys += [min(c[1] for c in cells) * self.grid, (max(c[1] for c in cells) + 1) * self.grid]
        for ring in self.rings.get((net, layer), ()):
            xs += [p.x for p in ring]
            ys += [p.y for p in ring]
        if not xs:
            return None
        return min(xs), min(ys), max(xs), max(ys)

    def nearest(self, net: str, layer: str, toward: Point, radius: int, limit: int) -> Point | None:
        """The point of the grid of cell centres nearest to ``toward``, within ``limit``, whose disc of
        ``radius`` the zone copper of ``net`` on ``layer`` covers; ties to the smaller ``(x, y)``."""
        box = self._box(net, layer)
        if box is None:
            return None
        step = self.grid
        half = step // 2
        x0 = max(box[0], toward.x - limit) // step
        x1 = min(box[2], toward.x + limit) // step
        y0 = max(box[1], toward.y - limit) // step
        y1 = min(box[3], toward.y + limit) // step
        if x0 > x1 or y0 > y1:
            return None
        best: tuple[int, int, int] | None = None
        for i in range(x0, x1 + 1):
            for j in range(y0, y1 + 1):
                point = Point(i * step + half, j * step + half)
                d2 = (point.x - toward.x) ** 2 + (point.y - toward.y) ** 2
                if d2 > limit * limit or (best is not None and (d2, point.x, point.y) >= best):
                    continue
                if self.covers(net, layer, point, radius):
                    best = (d2, point.x, point.y)
        return None if best is None else Point(best[1], best[2])


# --- subjects -----------------------------------------------------------------------------------------------


def _name(end: LinkEnd) -> str:
    if end.kind == "pad":
        return end.where
    prefix = "via" if end.kind == "via" else "trk"
    return f"{prefix}@{end.position.x},{end.position.y}"


def _attach(net: str, end: LinkEnd, island: NetIsland | None = None) -> Attach:
    """The attach point of an anchor; a track or via end on a pad's position of its island is that pad."""
    if end.kind != "pad" and island is not None:
        end = next((own for own in island.ends if own.kind == "pad" and own.position == end.position), end)
    kind = "pad" if end.kind == "pad" else "track-end"
    layers = tuple(layer for layer in end.layers if layer.endswith(".Cu"))
    return Attach(kind, net, end.position, layers, _name(end))


def _pair_key(kind: str, net: str, a: Attach, b: Attach) -> str:
    first, second = sorted((a.name, b.name))
    return f"{kind}:{net}:{first}~{second}"


def _island(islands: Sequence[NetIsland], end: LinkEnd) -> NetIsland | None:
    return next((island for island in islands if island.holds(end)), None)


@dataclass
class _Context:
    design: Design
    records: Mapping[str, BoardPad]
    roles: RoleSet | None
    copper: ZoneCopper
    widths: Mapping[str, int]
    reach: int
    blocked: frozenset[str]
    zones: dict[str, Zone] = field(default_factory=lambda: {})
    locked: frozenset[str] = frozenset()
    role_nets: frozenset[str] = frozenset()
    inferred: dict[str, str] = field(default_factory=lambda: {})
    hot: frozenset[str] = frozenset()


def _context(
    design: Design,
    pads: Sequence[BoardPad],
    roles: RoleSet | None,
    copper: ZoneCopper,
    widths: Mapping[str, int],
    reach: int,
    blocked: Collection[str],
) -> _Context:
    board = design.board
    records = {f"{p.ref}-{p.number}": p for p in pads if p.ref}
    held = _Context(design, records, roles, copper, widths, reach, frozenset(blocked))
    if board is not None:
        held.zones = {zone.id: zone for zone in board.zones}
        held.locked = frozenset(item.id for item in (*board.tracks, *board.arcs, *board.vias) if item.locked)
    if roles is not None:
        held.role_nets = frozenset(
            role.net for role in roles.nets if role.kind in ROLE_NET_KINDS and role.source != "inferred"
        )
        held.inferred = {
            role.net: role.kind
            for role in roles.nets
            if role.kind in ROLE_NET_KINDS and (role.source == "inferred" or role.milliamps is None)
        }
        hot_pads = {pad for loop in roles.loops for pad in loop.pads}
        held.hot = frozenset(
            record.net for name, record in records.items() if name in hot_pads and record.net is not None
        )
    return held


def _role_copper(island: NetIsland, net: str, ctx: _Context) -> bool:
    for zone_id in island.zones:
        zone = ctx.zones.get(zone_id)
        if zone is not None and (zone.name.startswith("role.") or net in ctx.role_nets):
            return True
    return any(entity in ctx.locked for _kind, entity in island.items)


def _drilled(island: NetIsland, ctx: _Context) -> bool:
    if any(kind == "via" for kind, _ in island.items):
        return True
    for name in island.pads:
        record = ctx.records.get(name)
        if record is not None and (record.drill is not None or record.hole):
            return True
    return False


def _zone_near(net: str, pad: BoardPad, ctx: _Context) -> tuple[Zone, str] | None:
    """The zone of ``net`` on a copper layer the pad is not on whose outline lies within reach of the pad,
    the nearest first, then by name; with that layer."""
    names = {n.id: n.name for n in ctx.design.circuit.nets}
    own = {layer for layer in pad.layers if layer.endswith(".Cu")}
    best: tuple[Fraction, str, str, Zone] | None = None
    for zone in ctx.zones.values():
        outline = zone.outline
        if names.get(zone.net_id or "") != net or len(outline) < 3:
            continue
        d2 = Fraction(0)
        if point_in_ring(pad.position, outline) is Location.OUTSIDE:
            edges = zip(outline, (*outline[1:], outline[0]), strict=True)
            d2 = min(dist2_point_segment(pad.position, a, b) for a, b in edges)
        if d2 > ctx.reach * ctx.reach:
            continue
        for layer in zone.layers:
            if layer in own or not layer.endswith(".Cu"):
                continue
            key = (d2, zone.name, layer, zone)
            if best is None or key[:3] < best[:3]:
                best = key
    return None if best is None else (best[3], best[2])


def _zone_attach(net: str, zone: Zone, layer: str, at: Point) -> Attach:
    name = zone.name or f"zone@{layer}"
    return Attach("zone", net, at, (layer,), name)


def _zone_targets(
    net: str, island: NetIsland, toward: LinkEnd, limit: int, ctx: _Context
) -> list[tuple[int, Attach]]:
    """For each zone layer of ``island``, the nearest point of its copper to ``toward`` that a track of the
    net's width reaches with the zone clearance to spare, as ``(squared distance, attach)``."""
    found: list[tuple[int, Attach]] = []
    width = ctx.widths.get(net, 0)
    for zone_id in sorted(island.zones):
        zone = ctx.zones.get(zone_id)
        if zone is None:
            continue
        clearance = zone.settings.clearance
        for layer in zone.layers:
            if not ctx.copper.has(net, layer):
                continue
            point = ctx.copper.nearest(net, layer, toward.position, (width + 1) // 2 + clearance, limit)
            if point is None:
                continue
            d2 = (point.x - toward.position.x) ** 2 + (point.y - toward.position.y) ** 2
            found.append((d2, _zone_attach(net, zone, layer, point)))
    return found


def _join_ends(
    net: str, conn: OpenConnection, first: NetIsland, second: NetIsland, ctx: _Context
) -> tuple[Attach, Attach]:
    """The nearest pair of attach points of two islands: the connection's anchors, or an anchor of one island
    and the copper of a zone of the other."""
    best: tuple[int, tuple[str, str], Attach, Attach] = (
        conn.length * conn.length,
        (_name(conn.a), _name(conn.b)),
        _attach(net, conn.a, first),
        _attach(net, conn.b, second),
    )
    limit = min(conn.length, ATTACH_REACH)
    for own, other in ((first, second), (second, first)):
        if not other.zones:
            continue
        for end in own.ends:
            for d2, target in _zone_targets(net, other, end, limit, ctx):
                start = _attach(net, end, own)
                rank = (start.name, target.name)
                if (d2, rank) < best[:2]:
                    best = (d2, rank, start, target)
    return best[2], best[3]


def subjects(
    design: Design,
    pads: Sequence[BoardPad],
    *,
    roles: RoleSet | None = None,
    groups: Sequence[OpenGroup] = (),
    widths: Mapping[str, int] | None = None,
    pour: PourCopper | None = None,
    blocked: Collection[str] = (),
    reach: int = FANOUT_REACH,
) -> SubjectPlan:
    """The subjects of the board ``design`` after phases 1 and 2 (see the module). ``roles`` are the roles in
    force (inferred ones with ``source`` ``inferred``); ``groups`` the critical groups phase 2 left open;
    ``widths`` the track width of each net; ``pour`` the board's pour when the caller has it; ``blocked`` the
    nets of phase 1's ``roles.copper-blocked`` edges."""
    board = design.board
    if board is None:
        return SubjectPlan()
    if pour is None:
        pour = pour_copper(design, pads=pads, boundary=board_boundary(board), grid=DEFAULT_GRID_NM)
    copper = ZoneCopper(design, pour)
    ctx = _context(design, pads, roles, copper, widths or {}, reach, blocked)
    report = connectivity(design, pads=pads, pour=pour)
    islands = net_islands(design, pads=pads, nets=report.open_nets(), pour=pour)
    found: list[Subject] = []
    fanned: set[str] = set()
    for row in report.nets:
        net = row.name
        held = islands.get(net, ())
        for conn in row.open:
            first, second = _island(held, conn.a), _island(held, conn.b)
            subject = _fanout(net, conn, first, second, ctx, fanned)
            if subject is None and first is not None and second is not None:
                if net in ctx.blocked or _role_copper(first, net, ctx) or _role_copper(second, net, ctx):
                    a, b = _join_ends(net, conn, first, second, ctx)
                    subject = Subject(
                        _pair_key("join", net, a, b),
                        "join",
                        net,
                        a,
                        b,
                        length=conn.length,
                        hot=net in ctx.hot,
                    )
            if subject is None:
                a, b = _attach(net, conn.a, first), _attach(net, conn.b, second)
                kind = "role-net" if net in ctx.inferred else "connection"
                subject = Subject(
                    _pair_key(kind, net, a, b),
                    kind,
                    net,
                    a,
                    b,
                    length=conn.length,
                    hot=net in ctx.hot,
                    inferred=ctx.inferred.get(net, ""),
                )
            found.append(subject)
    for group in groups:
        if group.status not in ("unrouted", "refused") or not group.routes:
            continue
        _key, net, a, b = group.routes[0]
        found.append(
            Subject(
                f"group:{group.name}",
                "group",
                net,
                a,
                b,
                group=group.name,
                routes=tuple(route[0] for route in group.routes),
                reason="pads" if group.reason == "pads" else "",
            )
        )
    order = {kind: index for index, kind in enumerate(KINDS)}
    unique: dict[str, Subject] = {}
    for subject in sorted(found, key=lambda s: (order[s.kind], s.key)):
        unique.setdefault(subject.key, subject)
    return SubjectPlan(tuple(unique.values()), report.total, "simulated" if copper.simulated else "saved")


def _fanout(
    net: str,
    conn: OpenConnection,
    first: NetIsland | None,
    second: NetIsland | None,
    ctx: _Context,
    fanned: set[str],
) -> Subject | None:
    """The ``fanout`` subject of ``conn`` when one of its ends is a pad of an island without via or
    through-hole pad with a zone of its net on another layer within reach."""
    for end, island in ((conn.a, first), (conn.b, second)):
        if end.kind != "pad" or island is None or end.where in fanned or _drilled(island, ctx):
            continue
        record = ctx.records.get(end.where)
        if record is None:
            continue
        near = _zone_near(net, record, ctx)
        if near is None:
            continue
        zone, layer = near
        fanned.add(end.where)
        a = _attach(net, end)
        target = ctx.copper.nearest(net, layer, end.position, 0, ctx.reach) or end.position
        b = _zone_attach(net, zone, layer, target)
        return Subject(
            f"fanout:{net}:{end.where}", "fanout", net, a, b, length=conn.length, hot=net in ctx.hot
        )
    return None


__all__ = [
    "ATTACH_REACH",
    "FANOUT_REACH",
    "KINDS",
    "ROLE_NET_KINDS",
    "Attach",
    "OpenGroup",
    "Subject",
    "SubjectPlan",
    "ZoneCopper",
    "subjects",
]

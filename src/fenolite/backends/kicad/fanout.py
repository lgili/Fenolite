# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Plane fan-out: one short track and one through via per SMD pad of a net that has a plane (capability
routing, "Plane fan-out"; change c0107; ``docs/routing.md``, "Plane fan-out").

A router does not bring an SMD pad to a plane on a layer of type ``power`` (measured with Freerouting
2.4.1, ``H-G-DSN-PLANE``), so ``fenolite route`` makes those joints before the router runs. ``plan_fanout``
is the engine: a pure function of the design, its board-frame pads and the rules the caller gives it. It
reads no file and no environment variable and changes none of its arguments.

For each SMD pad of a plane net, in board footprint order then pad order:

- a pad that is already joined is skipped: a via of its net overlaps its copper, or a chain of its net's
  tracks and arcs on its layer leads from its copper to a via of the net or to a through-hole pad of the net;
- the eight directions at multiples of 45 degrees are tried in the order of their angle to the outward
  direction (from the footprint's position to the pad's), and along each direction nine distances, a
  quarter of the via diameter apart, from the first at which the via keeps the neck from its own pad;
- the first candidate that passes every test gives the track and the via; without one the pad stays open
  and ``kicad.fanout.failed`` names what blocked its first candidate.

Every test is exact: lengths are integer nanometres, distances are compared as squares (``geometry.thick``).
Zone fills are not obstacles, because they are refilled after routing. The fan-out is ``KICAD-VERIFIED``: the
probes ``route-fanout-t9`` and ``route-fanout-t10`` of ``H-K-FANOUT`` are ``equal`` on both KiCad majors.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from types import MappingProxyType

from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.layers import expand_layers
from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import content_hash, derived_id
from fenolite.core.units import Nm, round_half_even_div
from fenolite.geometry import (
    DEFAULT_TOL,
    BBox,
    GeometryError,
    Location,
    SpatialIndex,
    Thick,
    dist2_point_segment,
    point_in_ring,
    rotate_point,
    thick_bbox,
    thick_closer_than,
    thick_touch,
)
from fenolite.geometry import Arc as GeometryArc
from fenolite.model.board import Track, Via
from fenolite.model.design import Design
from fenolite.model.rules import RuleSubject

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-FANOUT",))
"""Raised when the probes ``route-fanout-t9`` and ``route-fanout-t10`` are recorded."""
FANOUT_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType({"kicad.fanout.failed": "warning"})
"""The closed table of the fan-out's codes."""
DIRECTIONS: tuple[tuple[int, int], ...] = (
    (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1),
)  # fmt: skip
"""The eight directions ``k · 45°`` from +X of the model frame, by ``k``."""
STEPS = 9
"""The distances tried along a direction: the first at which the via keeps its neck, and eight more."""
GRID = 1_000
"""Via centres and the step lie on whole micrometres, so the Specctra file writes them without rounding."""
DEFAULT_CLASS = "Default"
_REACH_LIMIT = 400
"""Steps after which the search for the first distance of a direction stops (a pad wider than 100 steps)."""

Clearance = Callable[[RuleSubject, RuleSubject], Nm]
"""The clearance in force between two rule subjects, in nanometres (0: none)."""


@dataclass(frozen=True, slots=True)
class FanoutSizes:
    """What the fan-out of one net is made with: the track width, the via's diameter and drill, and the
    neck, the least gap between the via's copper and its own pad's copper (nanometres)."""

    width: Nm
    via_diameter: Nm
    via_drill: Nm
    neck: Nm

    def __post_init__(self) -> None:
        for name in ("width", "via_diameter", "via_drill"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"fan-out {name} must be a positive integer of nanometres, got {value!r}")
        if type(self.neck) is not int or self.neck < 0:
            raise ValueError(f"the fan-out neck must be an integer of 0 or more, got {self.neck!r}")
        if self.via_drill >= self.via_diameter:
            raise ValueError("the fan-out via drill must be smaller than the via diameter")


@dataclass(frozen=True, slots=True)
class FanoutPlan:
    """What ``plan_fanout`` returns: the copper it makes, the SMD pads it considered (``REF-NUMBER``, in
    board order), those it skipped as joined, those it left open, and one issue per pad left open."""

    tracks: tuple[Track, ...] = ()
    vias: tuple[Via, ...] = ()
    pads: tuple[str, ...] = ()
    joined: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    issues: tuple[Issue, ...] = ()


@dataclass(frozen=True, slots=True)
class _Item:
    """One thing a fan-out via or track is tested against: a shape, the layer it is on (``None``: every
    copper layer), its net, what it is and how a message names it."""

    shape: Thick
    layer: str | None
    net: str | None
    kind: str
    label: str
    ref: str | None = None
    pad: str | None = None
    drill: Thick | None = None
    drilled: bool = False
    box: BBox = field(default_factory=lambda: BBox(0, 0, 0, 0), compare=False)


def plane_nets(design: Design, plane_layers: Sequence[str]) -> tuple[str, ...]:
    """The names of the nets that have a zone on a layer of ``plane_layers``, sorted."""
    board = design.board
    if board is None or not plane_layers:
        return ()
    names = {net.id: net.name for net in design.circuit.nets}
    wanted = set(plane_layers)
    found = {
        names[zone.net_id]
        for zone in board.zones
        if zone.net_id in names and ("*.Cu" in zone.layers or wanted & set(zone.layers))
    }
    return tuple(sorted(found))


def _holds(shape: Thick, point: Point) -> bool:
    """Whether ``point`` lies in ``shape``, boundary included; exact."""
    core, width = shape.core, shape.width
    if len(core) == 1:
        dx, dy = point.x - core[0].x, point.y - core[0].y
        return 4 * (dx * dx + dy * dy) <= width * width
    if shape.filled:
        if point_in_ring(point, core) is not Location.OUTSIDE:
            return True
        edges = zip(core, (*core[1:], core[0]), strict=True)
    else:
        edges = zip(core, core[1:], strict=False)
    return any(4 * dist2_point_segment(point, a, b) <= width * width for a, b in edges)


def _item(shape: Thick, **fields: object) -> _Item:
    return _Item(shape, box=thick_bbox(shape), **fields)  # type: ignore[arg-type]


def _direction_order(outward: tuple[int, int]) -> tuple[int, ...]:
    """The indices of ``DIRECTIONS`` in the order of their angle to ``outward``, equal angles by index.

    The cosine of the angle to direction ``d`` is ``(o · d) / (|o| · |d|)``; ``|o|`` is common, so the
    directions are compared by the sign of ``o · d`` and by ``(o · d)² / |d|²``, exactly."""
    ox, oy = outward

    def key(k: int) -> tuple[Fraction, int]:
        dx, dy = DIRECTIONS[k]
        dot = ox * dx + oy * dy
        value = Fraction(dot * dot, dx * dx + dy * dy)
        return (-value if dot > 0 else value, k)

    return tuple(sorted(range(len(DIRECTIONS)), key=key))


def _centre(origin: Point, direction: tuple[int, int], distance: int) -> Point:
    """The point ``distance`` from ``origin`` along ``direction``, on whole micrometres."""
    dx, dy = direction
    along = distance if 0 in (dx, dy) else math.isqrt(distance * distance // 2)
    x = round_half_even_div(origin.x + dx * along, GRID) * GRID
    y = round_half_even_div(origin.y + dy * along, GRID) * GRID
    return Point(x, y)


class _Search:
    """The state of one ``plan_fanout`` call: what exists, and what the fan-out has made so far."""

    def __init__(
        self,
        design: Design,
        pads: Sequence[BoardPad],
        plane_layers: Sequence[str],
        outline: Sequence[Sequence[Point]],
        edge_clearance: Nm,
        clearance: Clearance,
    ) -> None:
        board = design.board
        assert board is not None
        self.design = design
        self.clearance = clearance
        self.edge_clearance = max(0, edge_clearance)
        ordered = sorted(board.layers, key=lambda layer: layer.ordinal)
        self.copper = tuple(layer.name for layer in ordered if layer.kind == "copper")
        self.net_names = {net.id: net.name for net in design.circuit.nets}
        classes = {cls.id: cls.name for cls in design.circuit.netclasses}
        self.class_of = {
            net.name: classes.get(net.netclass_id or "", DEFAULT_CLASS) for net in design.circuit.nets
        }
        self.rings = tuple(tuple(ring) for ring in outline if len(ring) >= 3)
        self.edges = tuple(Thick((*ring, ring[0]), 0) for ring in self.rings)
        self.no_vias = tuple(
            Thick(tuple(area.outline), 0, filled=True)
            for area in board.keepouts
            if area.no_vias
            and len(area.outline) >= 3
            and (not area.layers or set(expand_layers(area.layers, self.copper)) & set(self.copper))
        )
        self.no_tracks = tuple(
            (
                frozenset(expand_layers(area.layers, self.copper)) if area.layers else frozenset(self.copper),
                Thick(tuple(area.outline), 0, filled=True),
            )
            for area in board.keepouts
            if area.no_tracks and len(area.outline) >= 3
        )
        planes = set(plane_layers)
        self.zones: dict[str, list[tuple[Point, ...]]] = {}
        for zone in board.zones:
            name = self.net_names.get(zone.net_id or "")
            on_plane = "*.Cu" in zone.layers or planes & set(zone.layers)
            if name is not None and on_plane and len(zone.outline) >= 3:
                self.zones.setdefault(name, []).append(tuple(zone.outline))
        rules = design.rules.rules if design.rules is not None else ()
        pitches = [
            rule.min
            for rule in rules
            if rule.kind == "hole_to_hole"
            and rule.severity != "ignore"
            and rule.min is not None
            and rule.selector_a.op == "all"
            and rule.selector_b is None
            and not rule.layers
        ]
        self.hole_to_hole = max(pitches, default=0)
        self.items: list[_Item] = []
        self.pad_items: dict[str, list[_Item]] = {}
        for pad in pads:
            where = f"{pad.ref}-{pad.number}"
            drilled = bool(pad.hole) and pad.drill is not None
            hole = Thick(tuple(pad.hole), pad.drill) if drilled and pad.drill else None
            for entry in pad.copper:
                if entry.layer not in self.copper:
                    continue
                try:
                    shape = Thick(entry.core, entry.width, entry.filled)
                except (GeometryError, ValueError):
                    continue
                made = _item(
                    shape, layer=entry.layer, net=pad.net, kind="pad", label=f"the pad {where}",
                    ref=pad.ref, pad=pad.pad_id, drilled=drilled,
                )  # fmt: skip
                self.items.append(made)
                self.pad_items.setdefault(pad.pad_id, []).append(made)
            if hole is not None:
                self.items.append(
                    _item(
                        hole,
                        layer=None,
                        net=pad.net,
                        kind="hole",
                        label=f"the hole of {where}",
                        ref=pad.ref,
                        pad=pad.pad_id,
                        drill=hole,
                        drilled=True,
                    )  # fmt: skip
                )
        for mechanical in board.holes:
            shape = Thick((mechanical.position,), mechanical.drill)
            self.items.append(
                _item(shape, layer=None, net=None, kind="hole", label="a board hole", drill=shape)
            )
        for track in board.tracks:
            self.add_track(track.start, track.end, track.width, track.layer, track.net_id, new=False)
        for arc in board.arcs:
            try:
                core = tuple(GeometryArc(arc.start, arc.mid, arc.end).polygonize(DEFAULT_TOL))
            except (GeometryError, ValueError):
                core = (arc.start, arc.mid, arc.end)
            net = self.net_names.get(arc.net_id or "")
            label = f"an arc of {net}" if net else "an arc on no net"
            # the chord approximation is widened by its error bound, so the test stays conservative
            shape = Thick(core, arc.width + 2 * DEFAULT_TOL + 2)
            self.items.append(_item(shape, layer=arc.layer, net=net, kind="track", label=label))
        for via in board.vias:
            self.add_via(via.position, via.diameter, via.drill, via.net_id, new=False)
        self.index = SpatialIndex[_Item].build((item.box, item) for item in self.items)
        self.made: list[_Item] = []
        self._gaps: dict[tuple[str, str, str, str | None, str | None, str | None], int] = {}
        self._max_gaps: dict[str, int] = {}

    # --- what exists ----------------------------------------------------------------------------

    def add_track(
        self, start: Point, end: Point, width: int, layer: str, net_id: str | None, *, new: bool
    ) -> None:
        net = self.net_names.get(net_id or "")
        label = f"a track of {net}" if net else "a track on no net"
        made = _item(Thick((start, end), width), layer=layer, net=net, kind="track", label=label)
        (self.made if new else self.items).append(made)

    def add_via(self, at: Point, diameter: int, drill: int, net_id: str | None, *, new: bool) -> None:
        net = self.net_names.get(net_id or "")
        label = f"a via of {net}" if net else "a via on no net"
        hole = Thick((at,), drill) if drill > 0 else None
        made = _item(Thick((at,), diameter), layer=None, net=net, kind="via", label=label, drill=hole)
        (self.made if new else self.items).append(made)

    def near(self, box: BBox) -> list[_Item]:
        """The items whose box meets ``box``: the board's, then what the fan-out has made, in order."""
        found = list(self.index.query(box))
        x0, y0, x1, y1 = box.as_tuple()
        for item in self.made:
            ix0, iy0, ix1, iy1 = item.box.as_tuple()
            if ix0 <= x1 and x0 <= ix1 and iy0 <= y1 and y0 <= iy1:
                found.append(item)
        return found

    def subject(self, item: _Item, layer: str) -> RuleSubject:
        netclass = self.class_of.get(item.net, DEFAULT_CLASS) if item.net is not None else DEFAULT_CLASS
        kind = "pad" if item.kind == "hole" else item.kind
        return RuleSubject(kind, net=item.net, netclass=netclass, ref=item.ref, layer=layer)

    def gap(self, kind: str, net: str, item: _Item, layer: str | None) -> int:
        """The clearance in force between new copper of ``net`` and ``item``: on the item's layer, on
        ``layer``, or the largest over the copper layers for two things that cross every layer."""
        on = item.layer or layer
        key = (kind, net, item.kind, item.net, item.ref, on)
        found = self._gaps.get(key)
        if found is None:
            netclass = self.class_of.get(net, DEFAULT_CLASS)
            found = max(
                max(
                    0,
                    self.clearance(
                        RuleSubject(kind, net=net, netclass=netclass, layer=name), self.subject(item, name)
                    ),
                )
                for name in ((on,) if on is not None else self.copper)
            )
            self._gaps[key] = found
        return found

    def max_gap(self, net: str) -> int:
        """The largest clearance new copper of ``net`` keeps from anything on the board: how far around a
        candidate the search looks."""
        found = self._max_gaps.get(net)
        if found is None:
            others = [item for item in self.items if item.net != net]
            found = max(
                (
                    max(self.gap("via", net, item, None), self.gap("track", net, item, None))
                    for item in others
                ),
                default=0,
            )
            self._max_gaps[net] = found
        return found

    # --- joined pads ----------------------------------------------------------------------------

    def joined(self, pad: BoardPad, layer: str) -> bool:
        """Whether ``pad`` already reaches its plane: a via of its net overlaps its copper, or a chain of
        its net's tracks and arcs on ``layer`` leads from its copper to a via or a drilled pad of the net."""
        own = [item for item in self.pad_items.get(pad.pad_id, ()) if item.layer == layer]
        everything = [*self.items, *self.made]
        of_net = [item for item in everything if item.net == pad.net]
        vias = [item for item in of_net if item.kind == "via"]
        if any(thick_touch(via.shape, shape.shape) for via in vias for shape in own):
            return True
        wires = [item for item in of_net if item.kind == "track" and item.layer == layer]
        pads = [item for item in of_net if item.kind == "pad" and item.layer == layer]
        seen: set[int] = set()
        reached = {pad.pad_id}
        frontier = [i for i, wire in enumerate(wires) if self._ends_in(wire, own)]
        while frontier:
            index = frontier.pop()
            if index in seen:
                continue
            seen.add(index)
            for end in (wires[index].shape.core[0], wires[index].shape.core[-1]):
                if any(_holds(via.shape, end) for via in vias):
                    return True
                for other in pads:
                    if other.pad in reached or not _holds(other.shape, end):
                        continue
                    if other.drilled:
                        return True
                    reached.add(other.pad or "")
                    shapes = [item for item in pads if item.pad == other.pad]
                    frontier += [i for i, wire in enumerate(wires) if self._ends_in(wire, shapes)]
                frontier += [
                    i
                    for i, wire in enumerate(wires)
                    if i not in seen and end in (wire.shape.core[0], wire.shape.core[-1])
                ]
        return False

    @staticmethod
    def _ends_in(wire: _Item, shapes: Sequence[_Item]) -> bool:
        ends = (wire.shape.core[0], wire.shape.core[-1])
        return any(_holds(shape.shape, end) for shape in shapes for end in ends)

    # --- one candidate --------------------------------------------------------------------------

    def blocked(self, pad: BoardPad, layer: str, net: str, sizes: FanoutSizes, centre: Point) -> str | None:
        """What blocks the via at ``centre`` and its track from ``pad``, or ``None``."""
        diameter = sizes.via_diameter
        via = Thick((centre,), diameter)
        drill = Thick((centre,), sizes.via_drill)
        track = Thick((pad.position, centre), sizes.width) if centre != pad.position else None
        # the board: its edge, its cut-outs, the plane, the keep-outs
        if self.rings:
            if point_in_ring(centre, self.rings[0]) is not Location.INSIDE:
                return "the board edge"
            if any(point_in_ring(centre, ring) is not Location.OUTSIDE for ring in self.rings[1:]):
                return "a cut-out of the board"
            if any(thick_closer_than(via, edge, self.edge_clearance) for edge in self.edges):
                return "the board edge"
        if not self._on_plane(net, centre, diameter):
            return f"the outline of the zone of {net} (the via would not lie inside it)"
        if any(thick_touch(via, area) for area in self.no_vias):
            return "a keep-out that forbids vias"
        if track is not None and any(layer in on and thick_touch(track, area) for on, area in self.no_tracks):
            return "a keep-out that forbids tracks"
        # copper and holes
        reach = diameter + max(self.max_gap(net), self.hole_to_hole)
        low_x, high_x = min(pad.position.x, centre.x), max(pad.position.x, centre.x)
        low_y, high_y = min(pad.position.y, centre.y), max(pad.position.y, centre.y)
        box = BBox(low_x - reach, low_y - reach, high_x + reach, high_y + reach)
        for item in self.near(box):
            own = item.net == net
            if item.drill is not None and thick_closer_than(drill, item.drill, self.hole_to_hole):
                return f"{item.label} (hole to hole)"
            if own:
                if item.kind == "via" and thick_touch(via, item.shape):
                    return item.label
                if item.kind in ("pad", "hole") and item.pad != pad.pad_id and thick_touch(via, item.shape):
                    return item.label
                continue
            if item.kind == "via" and thick_touch(via, item.shape):
                return item.label
            if thick_closer_than(via, item.shape, self.gap("via", net, item, None)):
                return item.label
            if (
                track is not None
                and item.layer in (None, layer)
                and thick_closer_than(track, item.shape, self.gap("track", net, item, layer))
            ):
                return item.label
        return None

    def _on_plane(self, net: str, centre: Point, diameter: int) -> bool:
        """Whether ``centre`` lies inside the outline of a zone of ``net`` on a plane layer by at least half
        the via's diameter."""
        for ring in self.zones.get(net, ()):
            if point_in_ring(centre, ring) is not Location.INSIDE:
                continue
            edges = zip(ring, (*ring[1:], ring[0]), strict=True)
            if all(4 * dist2_point_segment(centre, a, b) >= diameter * diameter for a, b in edges):
                return True
        return False

    def first_distance(
        self, pad: BoardPad, layer: str, sizes: FanoutSizes, direction: tuple[int, int]
    ) -> int:
        """The number of steps to the first distance at which the via keeps the neck from its pad."""
        own = [item.shape for item in self.pad_items.get(pad.pad_id, ()) if item.layer == layer]
        step = step_of(sizes)
        for count in range(1, _REACH_LIMIT + 1):
            via = Thick((_centre(pad.position, direction, count * step),), sizes.via_diameter)
            if not any(
                thick_touch(via, shape) if sizes.neck == 0 else thick_closer_than(via, shape, sizes.neck)
                for shape in own
            ):
                return count
        return _REACH_LIMIT


def step_of(sizes: FanoutSizes) -> int:
    """The step along a direction: a quarter of the via diameter, rounded up to a whole micrometre."""
    return -(-sizes.via_diameter // (4 * GRID)) * GRID


def _outward(design: Design, pad: BoardPad) -> tuple[int, int]:
    """From the footprint's position to the pad's, or the pad's +X turned by its board rotation."""
    board = design.board
    assert board is not None
    origin = next((fp.position for fp in board.footprints if fp.id == pad.footprint_id), pad.position)
    dx, dy = pad.position.x - origin.x, pad.position.y - origin.y
    if (dx, dy) != (0, 0):
        return dx, dy
    turned = rotate_point(Point(1_000_000, 0), pad.rotation)
    return turned.x, turned.y


def plan_fanout(
    design: Design,
    pads: Sequence[BoardPad],
    *,
    nets: Mapping[str, FanoutSizes],
    plane_layers: Sequence[str],
    outline: Sequence[Sequence[Point]],
    edge_clearance: Nm,
    clearance: Clearance,
) -> FanoutPlan:
    """One track and one through via for each SMD pad of the plane nets ``nets`` (net name → sizes).

    ``pads`` are the board-frame pads of ``BoardFrame.board_pads``; ``plane_layers`` the plane layers of
    the board; ``outline`` the rings of the board outline, the board first; ``edge_clearance`` the
    copper-to-edge clearance; ``clearance(a, b)`` the clearance in force between two rule subjects. The
    result is the same for equal arguments, item ids included.
    """
    board = design.board
    if board is None or not nets:
        return FanoutPlan()
    search = _Search(design, pads, plane_layers, outline, edge_clearance, clearance)
    if len(search.copper) < 2:
        return FanoutPlan()
    order = {fp.id: index for index, fp in enumerate(board.footprints)}
    by_footprint: dict[str, list[BoardPad]] = {}
    for pad in pads:
        by_footprint.setdefault(pad.footprint_id, []).append(pad)
    net_ids = {net.name: net.id for net in design.circuit.nets}
    top, bottom = search.copper[0], search.copper[-1]
    tracks: list[Track] = []
    vias: list[Via] = []
    considered: list[str] = []
    joined: list[str] = []
    failed: list[str] = []
    issues: list[Issue] = []
    for footprint_id in sorted(by_footprint, key=lambda found: order.get(found, len(order))):
        for pad in by_footprint[footprint_id]:
            if pad.net is None or pad.net not in nets or pad.net not in net_ids:
                continue
            if pad.drill is not None or pad.hole:
                continue
            layer = next((entry.layer for entry in pad.copper if entry.layer in search.copper), None)
            if layer is None:
                continue
            where = f"{pad.ref}-{pad.number}"
            considered.append(where)
            if search.joined(pad, layer):
                joined.append(where)
                continue
            sizes = nets[pad.net]
            step = step_of(sizes)
            found: Point | None = None
            first_block: str | None = None
            for k in _direction_order(_outward(design, pad)):
                direction = DIRECTIONS[k]
                start = search.first_distance(pad, layer, sizes, direction)
                for count in range(start, start + STEPS):
                    centre = _centre(pad.position, direction, count * step)
                    why = search.blocked(pad, layer, pad.net, sizes, centre)
                    if why is None:
                        found = centre
                        break
                    first_block = first_block or why
                if found is not None:
                    break
            if found is None:
                failed.append(where)
                issues.append(
                    Issue(
                        "kicad.fanout.failed",
                        FANOUT_ISSUE_CODES["kicad.fanout.failed"],
                        f"the pad {where} of {pad.net} gets no fan-out via: its first candidate is "
                        f"blocked by {first_block}, and no other of the {len(DIRECTIONS) * STEPS} fits",
                        where=where,
                        hint="move the part, free room beside the pad, or join the pad in the script",
                    )
                )
                continue
            net_id = net_ids[pad.net]
            geometry = (pad.position.x, pad.position.y, found.x, found.y, sizes.width, layer)
            tracks.append(
                Track(
                    id=derived_id("trk", "routing", content_hash(pad.net, geometry)),
                    start=pad.position,
                    end=found,
                    width=sizes.width,
                    layer=layer,
                    net_id=net_id,
                )
            )
            span = (top, bottom)
            via_geometry = (found.x, found.y, sizes.via_diameter, sizes.via_drill, span, "through")
            vias.append(
                Via(
                    id=derived_id("via", "routing", content_hash(pad.net, via_geometry)),
                    position=found,
                    diameter=sizes.via_diameter,
                    drill=sizes.via_drill,
                    layers=span,
                    net_id=net_id,
                )
            )
            search.add_track(pad.position, found, sizes.width, layer, net_id, new=True)
            search.add_via(found, sizes.via_diameter, sizes.via_drill, net_id, new=True)
    return FanoutPlan(
        tuple(tracks), tuple(vias), tuple(considered), tuple(joined), tuple(failed), tuple(issues)
    )


__all__ = [
    "DIRECTIONS",
    "EVIDENCE",
    "FANOUT_ISSUE_CODES",
    "STEPS",
    "Clearance",
    "FanoutPlan",
    "FanoutSizes",
    "plane_nets",
    "plan_fanout",
    "step_of",
]

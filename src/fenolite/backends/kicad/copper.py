# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Manual copper of a KiCad design: uuids, intent resolution and the merge with existing copper
(capability manual-copper; user guide ``docs/copper.md``; facts: ``docs/formats/kicad/frame.md``).

Script copper is derived output: its source is the intents, and every build regenerates it from the
effective placements. Its marker is a version-8 uuid (RFC 9562, S-0110) whose first 48 bits spell
``fenoli``, so a rebuild can tell it from copper drawn in KiCad without any registry.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
import uuid
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Protocol, cast, runtime_checkable

from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.frame import board_pads
from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm
from fenolite.geometry import (
    DEFAULT_TOL,
    BBox,
    GeometryError,
    Location,
    Polygon,
    SpatialIndex,
    ceil_sqrt,
    dist2_point_segment,
    point_in_ring,
    round_point,
)
from fenolite.geometry import Arc as GeoArc
from fenolite.model.board import Arc, Track, Via
from fenolite.model.circuit import Net, NetClass
from fenolite.model.design import Design

COPPER_MARKER = 0x66656E6F6C69
"""The 48-bit ``custom_a`` field of every copper uuid: the ASCII bytes of ``fenoli``."""
_VERSION = 8
_VARIANT = 0b10
_HASH_BITS = 74
_CANONICAL = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def copper_uuid(key: str, locator: str) -> str:
    """The KiCad uuid of the script copper item ``locator`` of the intent ``key``: version 8, the Fenolite
    marker in ``custom_a``, and the first 74 bits of the SHA-256 of ``kicad-copper:<key>:<locator>`` in
    ``custom_b`` and ``custom_c``. ``uuid.UUID`` refuses ``version=8`` before Python 3.14 (S-0111), so the
    bits are set on the integer."""
    digest = hashlib.sha256(f"kicad-copper:{key}:{locator}".encode()).digest()
    bits = int.from_bytes(digest, "big") >> (256 - _HASH_BITS)
    custom_b, custom_c = bits >> 62, bits & ((1 << 62) - 1)
    value = (COPPER_MARKER << 80) | (_VERSION << 76) | (custom_b << 64) | (_VARIANT << 62) | custom_c
    return str(uuid.UUID(int=value))


def is_copper_uuid(text: str) -> bool:
    """Whether ``text`` is a canonical uuid with the copper marker, version 8 and the RFC variant."""
    if not _CANONICAL.fullmatch(text):
        return False
    value = int(text.replace("-", ""), 16)
    return (
        value >> 80 == COPPER_MARKER and (value >> 76) & 0xF == _VERSION and (value >> 62) & 0b11 == _VARIANT
    )


# --- intents as the resolver reads them -----------------------------------------------------------


@runtime_checkable
class PadEndLike(Protocol):
    """A pad of a component, by number; ``index`` picks one of the pads sharing the number."""

    @property
    def component(self) -> str: ...
    @property
    def number(self) -> str: ...
    @property
    def index(self) -> int | None: ...


@runtime_checkable
class ViaStepLike(Protocol):
    """A through via inside a track path, after which the track runs on ``layer``."""

    @property
    def at(self) -> Point: ...
    @property
    def layer(self) -> str: ...
    @property
    def diameter(self) -> Nm | None: ...
    @property
    def drill(self) -> Nm | None: ...


class TrackIntentLike(Protocol):
    @property
    def key(self) -> str: ...
    @property
    def path(self) -> Sequence[PadEndLike | Point | ViaStepLike]: ...
    @property
    def layer(self) -> str: ...
    @property
    def width(self) -> Nm | None: ...
    @property
    def net(self) -> str | None: ...


class ViaIntentLike(Protocol):
    @property
    def key(self) -> str: ...
    @property
    def at(self) -> Point: ...
    @property
    def net(self) -> str | None: ...
    @property
    def diameter(self) -> Nm | None: ...
    @property
    def drill(self) -> Nm | None: ...


class StitchIntentLike(Protocol):
    @property
    def key(self) -> str: ...
    @property
    def net(self) -> str | None: ...
    @property
    def pitch(self) -> Nm: ...
    @property
    def along(self) -> Sequence[Point]: ...
    @property
    def region(self) -> Sequence[Point]: ...
    @property
    def origin(self) -> Point: ...
    @property
    def diameter(self) -> Nm | None: ...
    @property
    def drill(self) -> Nm | None: ...
    @property
    def clearance(self) -> Nm | None: ...
    @property
    def margin(self) -> Nm: ...


CopperIntentLike = TrackIntentLike | ViaIntentLike | StitchIntentLike

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-FRAME-UUID", "H-G-FRAME-ROUTE"))
"""``INFERRED``: the two rows cover the routed blink, not every design."""
COPPER_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "kicad.copper.bad-intent": "error",
        "kicad.copper.pad-not-found": "error",
        "kicad.copper.layer-mismatch": "error",
        "kicad.copper.bad-layer": "error",
        "kicad.copper.net-conflict": "error",
        "kicad.copper.unknown-net": "error",
        "kicad.copper.no-net": "error",
        "kicad.copper.size-missing": "error",
        "kicad.copper.bad-size": "error",
        "kicad.copper.stale": "warning",
        "kicad.copper.end-unplaced": "warning",
        "kicad.copper.stitch-empty": "warning",
        "kicad.copper.regenerated": "info",
        "kicad.copper.duplicate": "info",
        "kicad.copper.stitch-skipped": "info",
    }
)


def _issue(code: str, message: str, where: str) -> Issue:
    return Issue(code, COPPER_ISSUE_CODES[code], message, where=where)


class _Refused(Exception):
    """An intent that creates nothing: the issue says why."""

    def __init__(self, code: str, message: str, key: str) -> None:
        self.issue = _issue(code, message, key)
        super().__init__(message)


def _at(point: Point) -> str:
    return f"({_format(point.x)}, {_format(point.y)}) mm"


def _format(value: int) -> str:
    sign = "-" if value < 0 else ""
    whole, part = divmod(abs(value), 1_000_000)
    text = f"{part:06d}".rstrip("0")
    return f"{sign}{whole}.{text}" if text else f"{sign}{whole}"


# --- the design as the resolver sees it -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Board:
    design: Design
    pads: tuple[BoardPad, ...]
    copper_layers: tuple[str, ...]
    nets: Mapping[str, Net]
    net_names: Mapping[str, str]
    classes: Mapping[str, NetClass]
    unplaced: frozenset[str]

    def matches(self, component: str, key: str) -> list[BoardPad]:
        found = [pad for pad in self.pads if pad.path and pad.path == component]
        if not found:
            found = [pad for pad in self.pads if pad.ref == component]
        if not found:
            raise _Refused(
                "kicad.copper.pad-not-found", f"{key}: no footprint of {component!r} on the board", key
            )
        return found

    def netclass(self, net: Net) -> NetClass | None:
        return self.classes.get(net.netclass_id) if net.netclass_id is not None else None


def _board(design: Design, unplaced: Collection[str]) -> _Board:
    layers = design.board.layers if design.board is not None else ()
    copper = tuple(la.name for la in sorted(layers, key=lambda la: la.ordinal) if la.kind == "copper")
    return _Board(
        design=design,
        pads=board_pads(design),
        copper_layers=copper,
        nets={net.name: net for net in design.circuit.nets},
        net_names={net.id: net.name for net in design.circuit.nets},
        classes={cls.id: cls for cls in design.circuit.netclasses},
        unplaced=frozenset(unplaced),
    )


def _named_net(board: _Board, name: str | None, key: str) -> Net | None:
    if name is None:
        return None
    net = board.nets.get(name)
    if net is None:
        raise _Refused("kicad.copper.unknown-net", f"{key}: {name!r} is not a net of the design", key)
    return net


def _positive(value: int, what: str, key: str) -> int:
    if value <= 0:
        raise _Refused("kicad.copper.bad-size", f"{key}: the {what} {value} nm is not positive", key)
    return value


def _via_sizes(
    given: tuple[Nm | None, Nm | None], cls: NetClass | None, net: Net, key: str
) -> tuple[int, int]:
    diameter = given[0] if given[0] is not None else (cls.via_diameter if cls is not None else None)
    drill = given[1] if given[1] is not None else (cls.via_drill if cls is not None else None)
    if diameter is None or drill is None:
        missing = "diameter" if diameter is None else "drill"
        raise _Refused(
            "kicad.copper.size-missing",
            f"{key}: no via {missing} is given and the class of {net.name} sets none",
            key,
        )
    _positive(diameter, "via diameter", key)
    _positive(drill, "via drill", key)
    if drill >= diameter:
        raise _Refused(
            "kicad.copper.bad-size",
            f"{key}: the drill {drill} nm is not smaller than the diameter {diameter} nm",
            key,
        )
    return diameter, drill


def _track(key: str, locator: str, start: Point, end: Point, width: int, layer: str, net: Net) -> Track:
    native = copper_uuid(key, locator)
    return Track(
        id=derived_id("trk", "kicad", native),
        native_ids={"kicad": native},
        start=start,
        end=end,
        width=width,
        layer=layer,
        net_id=net.id,
    )


def _via(key: str, locator: str, at: Point, sizes: tuple[int, int], board: _Board, net: Net) -> Via:
    native = copper_uuid(key, locator)
    return Via(
        id=derived_id("via", "kicad", native),
        native_ids={"kicad": native},
        position=at,
        diameter=sizes[0],
        drill=sizes[1],
        layers=(board.copper_layers[0], board.copper_layers[-1]),
        net_id=net.id,
    )


# --- tracks ---------------------------------------------------------------------------------------


def _dist2(a: Point, b: Point) -> int:
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2


def _is_pad_end(element: object) -> bool:
    return not isinstance(element, Point) and hasattr(element, "component")


def _copper_layer(board: _Board, layer: str, key: str) -> None:
    if layer not in board.copper_layers:
        raise _Refused(
            "kicad.copper.bad-layer",
            f"{key}: {layer!r} is not a copper layer of the board ({', '.join(board.copper_layers)})",
            key,
        )


def _candidates(board: _Board, end: PadEndLike, layer: str, key: str) -> list[BoardPad]:
    """The pads a pad end may mean, with copper on ``layer``."""
    number = str(end.number)
    matched = board.matches(end.component, key)
    names = (
        {end.component} | {pad.path for pad in matched if pad.path} | {pad.ref for pad in matched if pad.ref}
    )
    staged = sorted(names & board.unplaced)
    if staged:
        raise _Refused(
            "kicad.copper.end-unplaced",
            f"{key}: {end.component} is not placed yet (it sits in the staging row), so no copper is created",
            key,
        )
    numbered = [pad for pad in matched if pad.number == number]
    if not numbered:
        known = ", ".join(dict.fromkeys(pad.number for pad in matched if pad.number))
        raise _Refused(
            "kicad.copper.pad-not-found", f"{key}: {end.component} has no pad {number!r} (pads: {known})", key
        )
    if end.index is not None:
        if not 0 <= end.index < len(numbered):
            raise _Refused(
                "kicad.copper.pad-not-found",
                f"{key}: {end.component} has {len(numbered)} pad(s) numbered {number!r}; index "
                f"{end.index} is beyond them",
                key,
            )
        numbered = [numbered[end.index]]
    found = [pad for pad in numbered if any(entry.layer == layer for entry in pad.copper)]
    if not found:
        raise _Refused(
            "kicad.copper.layer-mismatch",
            f"{key}: pad {number!r} of {end.component} has no copper on {layer}",
            key,
        )
    return found


def _choose(options: Sequence[Sequence[BoardPad] | Point]) -> list[Point | BoardPad]:
    """One pad per pad end, in path order: the first end by the nearest pair or the nearest candidate to the
    second element, every other end by the candidate nearest to the element before it."""
    chosen: list[Point | BoardPad] = []

    def point_of(item: Point | BoardPad) -> Point:
        return item if isinstance(item, Point) else item.position

    for index, option in enumerate(options):
        if isinstance(option, Point):
            chosen.append(option)
            continue
        if len(option) == 1:
            chosen.append(option[0])
            continue
        if index > 0:
            before = point_of(chosen[index - 1])
            chosen.append(min(option, key=lambda pad: _dist2(pad.position, before)))
            continue
        second = options[1]
        if isinstance(second, Point):
            target = second
            chosen.append(min(option, key=lambda pad: _dist2(pad.position, target)))
        else:
            pairs = [
                (_dist2(a.position, b.position), i, j)
                for i, a in enumerate(option)
                for j, b in enumerate(second)
            ]
            chosen.append(option[min(pairs)[1]])
    return chosen


def _resolve_track(board: _Board, intent: TrackIntentLike) -> tuple[list[Track], list[Via]]:
    key, path = intent.key, list(intent.path)
    if len(path) < 2:
        raise _Refused("kicad.copper.bad-intent", f"{key}: a track path needs at least two elements", key)
    if not isinstance(path[0], Point) and not _is_pad_end(path[0]):
        raise _Refused("kicad.copper.bad-intent", f"{key}: a track path cannot start with a via step", key)
    _copper_layer(board, intent.layer, key)
    layers: list[str] = []  # the layer of the segment that leaves each element
    current = intent.layer
    for element in path:
        if not isinstance(element, Point) and not _is_pad_end(element):
            step = cast(ViaStepLike, element)
            _copper_layer(board, step.layer, key)
            if step.layer == current:
                raise _Refused(
                    "kicad.copper.bad-layer", f"{key}: the via step at {_at(step.at)} stays on {current}", key
                )
            current = step.layer
        layers.append(current)
    options: list[Sequence[BoardPad] | Point] = []
    for index, element in enumerate(path):
        if isinstance(element, Point):
            options.append(element)
        elif _is_pad_end(element):
            options.append(_candidates(board, cast(PadEndLike, element), layers[index], key))
        else:
            options.append(cast(ViaStepLike, element).at)
    chosen = _choose(options)
    ends = [(cast(PadEndLike, path[i]), pad) for i, pad in enumerate(chosen) if isinstance(pad, BoardPad)]
    named = _named_net(board, intent.net, key)
    net = _track_net(board, ends, named, key)
    cls = board.netclass(net)
    width = intent.width if intent.width is not None else (cls.track_width if cls is not None else None)
    if width is None:
        raise _Refused(
            "kicad.copper.size-missing",
            f"{key}: no width is given and the class of {net.name} sets no track width",
            key,
        )
    _positive(width, "track width", key)
    sizes = {
        index: _via_sizes((cast(ViaStepLike, e).diameter, cast(ViaStepLike, e).drill), cls, net, key)
        for index, e in enumerate(path)
        if not isinstance(e, Point) and not _is_pad_end(e)
    }
    points = [item if isinstance(item, Point) else item.position for item in chosen]
    tracks: list[Track] = []
    vias: list[Via] = []
    for index, point in enumerate(points):
        if index in sizes:
            vias.append(_via(key, f"via[{index}]", point, sizes[index], board, net))
        if index + 1 < len(points) and point != points[index + 1]:
            tracks.append(_track(key, f"seg[{index}]", point, points[index + 1], width, layers[index], net))
    return tracks, vias


def _track_net(
    board: _Board, ends: Sequence[tuple[PadEndLike, BoardPad]], named: Net | None, key: str
) -> Net:
    labels = [f"{end.component}.{pad.number}" for end, pad in ends]
    without = [label for label, (_, pad) in zip(labels, ends, strict=True) if pad.net is None]
    if without:
        raise _Refused(
            "kicad.copper.net-conflict",
            f"{key}: pad {', '.join(without)} is on no net, so the track would join it",
            key,
        )
    found = dict.fromkeys(pad.net for _, pad in ends if pad.net is not None)
    if len(found) > 1:
        shown = ", ".join(f"{label} on {pad.net}" for label, (_, pad) in zip(labels, ends, strict=True))
        raise _Refused("kicad.copper.net-conflict", f"{key}: the track would join two nets ({shown})", key)
    if not found:
        if named is None:
            raise _Refused("kicad.copper.no-net", f"{key}: a track without a pad end must name its net", key)
        return named
    name = next(iter(found))
    if named is not None and named.name != name:
        raise _Refused(
            "kicad.copper.net-conflict",
            f"{key}: the net {named.name} is named, but the pads ({', '.join(labels)}) are on {name}",
            key,
        )
    return board.nets[name]


def _required_net(board: _Board, name: str | None, key: str, what: str) -> Net:
    net = _named_net(board, name, key)
    if net is None:
        raise _Refused("kicad.copper.no-net", f"{key}: a {what} must name its net", key)
    return net


def _resolve_via(board: _Board, intent: ViaIntentLike) -> Via:
    net = _required_net(board, intent.net, intent.key, "via")
    sizes = _via_sizes((intent.diameter, intent.drill), board.netclass(net), net, intent.key)
    return _via(intent.key, "via", intent.at, sizes, board, net)


# --- stitching ------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Obstacle:
    """Copper or a hole the stitching keeps clear of: a core with a width, and the net it is on."""

    core: tuple[Point, ...]
    width: int
    filled: bool
    net: str | None
    via: bool = False

    def bbox(self) -> BBox:
        box = BBox.of_points(self.core)
        return box.inflate(-(-self.width // 2))


def _core_dist2(point: Point, obstacle: _Obstacle) -> Fraction:
    """The exact squared distance from ``point`` to the core of ``obstacle`` (0 inside a filled ring)."""
    core = obstacle.core
    if len(core) == 1:
        return Fraction(_dist2(point, core[0]))
    if obstacle.filled:
        if point_in_ring(point, core) is not Location.OUTSIDE:
            return Fraction(0)
        edges = zip(core, core[1:] + core[:1], strict=True)
    else:
        edges = zip(core, core[1:], strict=False)
    return min(dist2_point_segment(point, a, b) for a, b in edges)


def _closer(point: Point, diameter: int, obstacle: _Obstacle, gap: int, *, touching: bool = False) -> bool:
    """Whether the disc at ``point`` comes closer than ``gap`` to ``obstacle`` (or reaches it, ``touching``).

    ``dist < gap + d/2 + w/2`` is compared as ``4·dist² < (2·gap + d + w)²``, with integers and ``Fraction``.
    """
    limit = (2 * gap + diameter + obstacle.width) ** 2
    distance = 4 * _core_dist2(point, obstacle)
    return distance <= limit if touching else distance < limit


def _obstacles(
    board: _Board, tracks: Iterable[Track], arcs: Iterable[Arc], vias: Iterable[Via]
) -> list[_Obstacle]:
    found: list[_Obstacle] = []
    for pad in board.pads:
        found += [_Obstacle(entry.core, entry.width, entry.filled, None) for entry in pad.copper]
        if pad.hole and pad.drill is not None:
            found.append(_Obstacle(pad.hole, pad.drill, False, None))
    for track in tracks:
        net = board.net_names.get(track.net_id) if track.net_id is not None else None
        found.append(_Obstacle((track.start, track.end), track.width, False, net))
    for arc in arcs:
        net = board.net_names.get(arc.net_id) if arc.net_id is not None else None
        try:
            core = GeoArc(arc.start, arc.mid, arc.end).polygonize(DEFAULT_TOL)
        except GeometryError:
            core = (arc.start, arc.mid, arc.end)
        found.append(_Obstacle(tuple(core), arc.width + 2 * DEFAULT_TOL + 2, False, net))
    for via in vias:
        net = board.net_names.get(via.net_id) if via.net_id is not None else None
        found.append(_Obstacle((via.position,), via.diameter, False, net, via=True))
    return found


def _along(points: Sequence[Point], pitch: int) -> list[tuple[str, Point]]:
    """The division points of a polyline: each segment in the fewest equal parts no longer than ``pitch``."""
    found: list[Point] = []
    for a, b in zip(points, points[1:], strict=False):
        parts = max(1, ceil_sqrt(Fraction(_dist2(a, b), pitch * pitch)))
        for k in range(parts + 1):
            point = round_point(
                a.x + Fraction((b.x - a.x) * k, parts), a.y + Fraction((b.y - a.y) * k, parts)
            )
            if not found or found[-1] != point:
                found.append(point)
    return [(f"via[{k}]", point) for k, point in enumerate(found)]


def _region(ring: Sequence[Point], origin: Point, pitch: int, reach: int) -> list[tuple[str, Point]]:
    """The grid points ``origin + (i, j)·pitch`` inside ``ring`` at least ``reach / 2`` from every edge
    (``reach`` is the via diameter plus twice the margin), in order of ``j`` then ``i``."""
    xs, ys = [p.x for p in ring], [p.y for p in ring]
    closed = (*ring[1:], ring[0])
    edges = list(zip(ring, closed, strict=True))
    found: list[tuple[str, Point]] = []
    for j in range(-((origin.y - min(ys)) // pitch), (max(ys) - origin.y) // pitch + 1):
        for i in range(-((origin.x - min(xs)) // pitch), (max(xs) - origin.x) // pitch + 1):
            point = Point(origin.x + i * pitch, origin.y + j * pitch)
            if point_in_ring(point, ring) is not Location.INSIDE:
                continue
            if all(4 * dist2_point_segment(point, a, b) >= reach * reach for a, b in edges):
                found.append((f"via[{i},{j}]", point))
    return found


def _resolve_stitch(
    board: _Board, intent: StitchIntentLike, obstacles: Sequence[_Obstacle], issues: list[Issue]
) -> list[Via]:
    key = intent.key
    along, region = tuple(intent.along), tuple(intent.region)
    if bool(along) == bool(region):
        raise _Refused(
            "kicad.copper.bad-intent", f"{key}: a stitch takes exactly one of along and region", key
        )
    if intent.pitch <= 0 or intent.margin < 0:
        raise _Refused(
            "kicad.copper.bad-intent", f"{key}: the pitch must be positive and the margin not negative", key
        )
    if along and len(along) < 2:
        raise _Refused("kicad.copper.bad-intent", f"{key}: along needs at least two points", key)
    if region:
        try:
            simple = len(region) >= 3 and Polygon(region).is_simple()
        except (GeometryError, ValueError):
            simple = False
        if not simple:
            raise _Refused(
                "kicad.copper.bad-intent",
                f"{key}: region must be a simple ring of at least three points",
                key,
            )
    net = _required_net(board, intent.net, key, "stitch")
    cls = board.netclass(net)
    diameter, drill = _via_sizes((intent.diameter, intent.drill), cls, net, key)
    clearance = (
        intent.clearance if intent.clearance is not None else (cls.clearance if cls is not None else None)
    )
    if clearance is None:
        raise _Refused(
            "kicad.copper.size-missing",
            f"{key}: no clearance is given and the class of {net.name} sets none",
            key,
        )
    if clearance < 0:
        raise _Refused("kicad.copper.bad-size", f"{key}: the clearance {clearance} nm is negative", key)
    if along:
        candidates = _along(along, intent.pitch)
    else:
        candidates = _region(region, intent.origin, intent.pitch, diameter + 2 * intent.margin)
    index = SpatialIndex[_Obstacle].build((obstacle.bbox(), obstacle) for obstacle in obstacles)
    reach = clearance + -(-diameter // 2)
    kept: list[Via] = []
    cells: dict[tuple[int, int], list[Point]] = {}
    dropped = 0
    for locator, point in candidates:
        box = BBox(point.x - reach, point.y - reach, point.x + reach, point.y + reach)
        blocked = False
        for obstacle in index.query(box):
            own = obstacle.net == net.name
            if own and not obstacle.via:
                continue  # own-net tracks and arcs may be touched
            if _closer(point, diameter, obstacle, 0 if own else clearance, touching=own):
                blocked = True
                break
        cell = (point.x // diameter, point.y // diameter)
        if not blocked:
            near = (cells.get((cell[0] + dx, cell[1] + dy), ()) for dx in (-1, 0, 1) for dy in (-1, 0, 1))
            blocked = any(_dist2(point, other) <= diameter * diameter for group in near for other in group)
        if blocked:
            dropped += 1
            continue
        cells.setdefault(cell, []).append(point)
        kept.append(_via(key, locator, point, (diameter, drill), board, net))
    if dropped:
        issues.append(
            _issue(
                "kicad.copper.stitch-skipped",
                f"{key}: {dropped} stitch candidate(s) dropped to keep {_format(clearance)} mm from other "
                "copper",
                key,
            )
        )
    if not kept:
        issues.append(_issue("kicad.copper.stitch-empty", f"{key}: the stitch keeps no via", key))
    return kept


# --- the merge with existing copper ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CopperMerge:
    """What stays of the existing copper beside the script copper of a build: the ids of the items kept,
    the issues, and how many items were regenerated with a change, stale, or duplicates."""

    kept: frozenset[str]
    issues: tuple[Issue, ...] = ()
    regenerated: int = 0
    stale: int = 0
    duplicates: int = 0


def _fields(item: Track | Arc | Via, names: Mapping[str, str]) -> tuple[object, ...]:
    """The modelled fields of a copper item, with its net by name."""
    net = names.get(item.net_id) if item.net_id is not None else None
    if isinstance(item, Via):
        return ("via", item.position, item.diameter, item.drill, tuple(item.layers), item.via_type, net)
    if isinstance(item, Arc):
        return ("arc", item.start, item.mid, item.end, item.width, item.layer, net)
    return ("track", item.start, item.end, item.width, item.layer, net)


def _shape_key(item: Track | Arc | Via, names: Mapping[str, str]) -> tuple[object, ...]:
    """What makes two items the same copper: a track's ends as an unordered pair."""
    fields = _fields(item, names)
    if isinstance(item, Track):
        first, second = sorted((item.start, item.end))
        return ("track", first, second, *fields[3:])
    return fields


def _describe(item: Track | Arc | Via, names: Mapping[str, str]) -> str:
    net = names.get(item.net_id, "no net") if item.net_id is not None else "no net"
    if isinstance(item, Via):
        return f"via on {'-'.join(item.layers)} at {_at(item.position)} on {net}"
    kind = "arc" if isinstance(item, Arc) else "track"
    return f"{kind} on {item.layer} from {_at(item.start)} on {net}"


def _net_names(design: Design) -> dict[str, str]:
    return {net.id: net.name for net in design.circuit.nets}


def merge_copper(existing: Design, built: Design) -> CopperMerge:
    """Which tracks, arcs and vias of ``existing`` stay beside the script copper of ``built``.

    Existing script copper is dropped: regenerated when ``built`` holds its uuid, stale otherwise. Existing
    copper without a copper uuid that equals a script item is a duplicate. Everything else is kept.
    """
    old, new = existing.board, built.board
    if old is None:
        return CopperMerge(frozenset())
    old_names, new_names = _net_names(existing), _net_names(built)
    script: dict[str, Track | Via] = {}
    for item in (*new.tracks, *new.vias) if new is not None else ():
        native = item.native_ids.get("kicad", "")
        if is_copper_uuid(native):
            script[native] = item
    shapes = {_shape_key(item, new_names) for item in script.values()}
    kept: set[str] = set()
    issues: list[Issue] = []
    regenerated = stale = duplicates = 0
    items: tuple[Track | Arc | Via, ...] = (*old.tracks, *old.arcs, *old.vias)
    for item in items:
        native = item.native_ids.get("kicad", "")
        if is_copper_uuid(native):
            twin = script.get(native)
            if twin is None:
                stale += 1
                issues.append(
                    _issue(
                        "kicad.copper.stale",
                        f"script copper {native} has no intent any more and is removed: "
                        f"{_describe(item, old_names)}",
                        native,
                    )
                )
            elif _fields(item, old_names) != _fields(twin, new_names):
                regenerated += 1
                issues.append(
                    _issue(
                        "kicad.copper.regenerated",
                        f"script copper {native} was edited in KiCad or its pads moved; it is regenerated: "
                        f"{_describe(twin, new_names)}",
                        native,
                    )
                )
        elif _shape_key(item, old_names) in shapes:
            duplicates += 1
            issues.append(
                _issue(
                    "kicad.copper.duplicate",
                    f"{_describe(item, old_names)} equals script copper and is removed",
                    native or item.id,
                )
            )
        else:
            kept.add(item.id)
    return CopperMerge(frozenset(kept), tuple(issues), regenerated, stale, duplicates)


# --- resolution -----------------------------------------------------------------------------------


def resolve_copper(
    design: Design,
    intents: Sequence[CopperIntentLike],
    *,
    unplaced: Collection[str] = (),
    issues: list[Issue] | None = None,
) -> Design:
    """``design`` with the copper of ``intents``: the tracks, arcs and vias that ``merge_copper`` keeps, in
    their order, followed by the created tracks and vias in intent order. An intent with an error creates
    nothing; ``unplaced`` names the components the build staged. Nothing is read or written."""
    found: list[Issue] = []
    if design.board is None:
        if issues is not None and intents:
            issues.append(_issue("kicad.copper.bad-intent", "the design has no board to draw copper on", ""))
        return design
    board = _board(design, unplaced)
    user = [
        [item for item in group if not is_copper_uuid(item.native_ids.get("kicad", ""))]
        for group in (design.board.tracks, design.board.arcs, design.board.vias)
    ]
    tracks: list[Track] = []
    vias: list[Via] = []
    seen: set[str] = set()
    for intent in intents:
        key = intent.key
        try:
            if key in seen:
                raise _Refused("kicad.copper.bad-intent", f"{key}: the key is used by an earlier intent", key)
            seen.add(key)
            if hasattr(intent, "path"):
                new_tracks, new_vias = _resolve_track(board, cast(TrackIntentLike, intent))
                tracks += new_tracks
                vias += new_vias
            elif hasattr(intent, "pitch"):
                obstacles = _obstacles(
                    board,
                    (*cast("list[Track]", user[0]), *tracks),
                    cast("list[Arc]", user[1]),
                    (*cast("list[Via]", user[2]), *vias),
                )
                vias += _resolve_stitch(board, cast(StitchIntentLike, intent), obstacles, found)
            else:
                vias.append(_resolve_via(board, cast(ViaIntentLike, intent)))
        except _Refused as refused:
            found.append(refused.issue)
    built = dataclasses.replace(
        design, board=dataclasses.replace(design.board, tracks=tuple(tracks), arcs=(), vias=tuple(vias))
    )
    merge = merge_copper(design, built)
    found += merge.issues
    old = design.board
    result = dataclasses.replace(
        design,
        board=dataclasses.replace(
            old,
            tracks=(*(t for t in old.tracks if t.id in merge.kept), *tracks),
            arcs=tuple(a for a in old.arcs if a.id in merge.kept),
            vias=(*(v for v in old.vias if v.id in merge.kept), *vias),
        ),
    )
    if issues is not None:
        issues.extend(found)
    return result


__all__ = [
    "COPPER_ISSUE_CODES",
    "COPPER_MARKER",
    "EVIDENCE",
    "CopperIntentLike",
    "CopperMerge",
    "PadEndLike",
    "StitchIntentLike",
    "TrackIntentLike",
    "ViaIntentLike",
    "ViaStepLike",
    "copper_uuid",
    "is_copper_uuid",
    "merge_copper",
    "resolve_copper",
]

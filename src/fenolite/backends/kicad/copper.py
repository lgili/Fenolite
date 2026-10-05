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
from fenolite.backends.kicad.layers import expand_layers
from fenolite.backends.kicad.outline import BoardOutline, board_outline
from fenolite.backends.kicad.rulemap import rule_order
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
from fenolite.model.board import Arc, Keepout, Track, Via, ViaType
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
    """A via inside a track path, after which the track runs on ``layer``. Its ``kind`` (``through``,
    ``blind``, ``buried`` or ``micro``) is read by attribute when the step has one: a step without it is a
    through via, as the steps of earlier scripts are."""

    @property
    def at(self) -> Point: ...
    @property
    def layer(self) -> str: ...
    @property
    def diameter(self) -> Nm | None: ...
    @property
    def drill(self) -> Nm | None: ...


@runtime_checkable
class ArcStepLike(Protocol):
    """An arc inside a track path: from the point of the element before it through ``mid`` to ``end``."""

    @property
    def mid(self) -> Point: ...
    @property
    def end(self) -> Point: ...


class TrackIntentLike(Protocol):
    @property
    def key(self) -> str: ...
    @property
    def path(self) -> Sequence[PadEndLike | Point | ViaStepLike | ArcStepLike]: ...
    @property
    def layer(self) -> str: ...
    @property
    def width(self) -> Nm | None: ...
    @property
    def net(self) -> str | None: ...


class ViaIntentLike(Protocol):
    """One via. Its ``kind`` and ``layers`` are read by attribute when the intent has them: an intent
    without ``kind`` is a through via, and one without ``layers`` names none."""

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
VIA_KINDS = ("through", "blind", "buried", "micro")
"""The kinds of a via step and of a single via (``Via.via_type``)."""
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


def _arc(key: str, locator: str, points: tuple[Point, Point, Point], width: int, layer: str, net: Net) -> Arc:
    native = copper_uuid(key, locator)
    return Arc(
        id=derived_id("arc", "kicad", native),
        native_ids={"kicad": native},
        start=points[0],
        mid=points[1],
        end=points[2],
        width=width,
        layer=layer,
        net_id=net.id,
    )


def _via(
    key: str,
    locator: str,
    at: Point,
    sizes: tuple[int, int],
    board: _Board,
    net: Net,
    kind: str = "through",
    layers: tuple[str, str] | None = None,
) -> Via:
    """A via of ``kind``; ``layers`` is its span in stack order, the whole board for a through via."""
    native = copper_uuid(key, locator)
    return Via(
        id=derived_id("via", "kicad", native),
        native_ids={"kicad": native},
        position=at,
        diameter=sizes[0],
        drill=sizes[1],
        layers=layers if layers is not None else (board.copper_layers[0], board.copper_layers[-1]),
        net_id=net.id,
        via_type=cast(ViaType, kind),
    )


def _via_kind(item: object, key: str) -> str:
    """The kind of a via step or a via intent: ``through`` when it has none."""
    kind = getattr(item, "kind", "through")
    if kind not in VIA_KINDS:
        raise _Refused(
            "kicad.copper.bad-intent",
            f"{key}: the via kind {kind!r} is not one of {', '.join(VIA_KINDS)}",
            key,
        )
    return cast(str, kind)


def _via_span(board: _Board, kind: str, a: str, b: str, key: str) -> tuple[str, str] | None:
    """The two layers of a via that is not a through via, in stack order, after checking that they fit
    its kind; ``None`` for a through via, which spans the board.

    ``blind``: exactly one of the two is the first or the last copper layer. ``buried``: neither is.
    ``micro``: exactly one is, and the two are next to each other in the stack. Whether a target can hold
    the kind is the board writer's rule."""
    if kind == "through":
        return None
    stack = board.copper_layers
    first, second = sorted((stack.index(a), stack.index(b)))
    outer = sum(1 for index in (first, second) if index in (0, len(stack) - 1))
    fits = {
        "blind": outer == 1,
        "buried": outer == 0,
        "micro": outer == 1 and second - first == 1,
    }[kind]
    if first == second or not fits:
        rule = {
            "blind": "one of the two must be an outer layer and the other an inner one",
            "buried": "both must be inner layers",
            "micro": "one must be an outer layer and the other the layer next to it",
        }[kind]
        raise _Refused(
            "kicad.copper.bad-layer",
            f"{key}: the layers {a} and {b} do not fit a {kind} via on a board with the copper layers "
            f"{', '.join(stack)}: {rule}",
            key,
        )
    return stack[first], stack[second]


# --- tracks ---------------------------------------------------------------------------------------


def _dist2(a: Point, b: Point) -> int:
    return (a.x - b.x) ** 2 + (a.y - b.y) ** 2


def _is_pad_end(element: object) -> bool:
    return not isinstance(element, Point) and hasattr(element, "component")


def _is_arc_step(element: object) -> bool:
    return not isinstance(element, Point) and not _is_pad_end(element) and hasattr(element, "mid")


def _is_via_step(element: object) -> bool:
    return not isinstance(element, Point) and not _is_pad_end(element) and not _is_arc_step(element)


def _on_one_line(a: Point, b: Point, c: Point) -> bool:
    """Whether three points lie on one line, decided exactly with integers."""
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x) == 0


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


def _resolve_track(board: _Board, intent: TrackIntentLike) -> tuple[list[Track], list[Arc], list[Via]]:
    key, path = intent.key, list(intent.path)
    if len(path) < 2:
        raise _Refused("kicad.copper.bad-intent", f"{key}: a track path needs at least two elements", key)
    if not isinstance(path[0], Point) and not _is_pad_end(path[0]):
        what = "an arc step" if _is_arc_step(path[0]) else "a via step"
        raise _Refused("kicad.copper.bad-intent", f"{key}: a track path cannot start with {what}", key)
    _copper_layer(board, intent.layer, key)
    layers: list[str] = []  # the layer of the segment that leaves each element
    spans: dict[int, tuple[str, tuple[str, str] | None]] = {}  # the kind and the layers of each via step
    current = intent.layer
    for index, element in enumerate(path):
        if _is_via_step(element):
            step = cast(ViaStepLike, element)
            kind = _via_kind(step, key)
            _copper_layer(board, step.layer, key)
            if step.layer == current:
                raise _Refused(
                    "kicad.copper.bad-layer", f"{key}: the via step at {_at(step.at)} stays on {current}", key
                )
            spans[index] = (kind, _via_span(board, kind, current, step.layer, key))
            current = step.layer
        layers.append(current)
    options: list[Sequence[BoardPad] | Point] = []
    for index, element in enumerate(path):
        if isinstance(element, Point):
            options.append(element)
        elif _is_pad_end(element):
            options.append(_candidates(board, cast(PadEndLike, element), layers[index], key))
        elif _is_arc_step(element):
            options.append(cast(ArcStepLike, element).end)
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
        if _is_via_step(e)
    }
    points = [item if isinstance(item, Point) else item.position for item in chosen]
    tracks: list[Track] = []
    arcs: list[Arc] = []
    vias: list[Via] = []
    for index, point in enumerate(points):
        if index in sizes:
            kind, span = spans[index]
            vias.append(_via(key, f"via[{index}]", point, sizes[index], board, net, kind, span))
        if index + 1 == len(points):
            break
        after = path[index + 1]
        if _is_arc_step(after):
            mid, end = cast(ArcStepLike, after).mid, points[index + 1]
            if len({point, mid, end}) < 3 or _on_one_line(point, mid, end):
                raise _Refused(
                    "kicad.copper.bad-intent",
                    f"{key}: the arc step at path[{index + 1}] does not make an arc: its three points "
                    f"{_at(point)}, {_at(mid)} and {_at(end)} must be distinct and not on one line",
                    key,
                )
            arcs.append(_arc(key, f"arc[{index + 1}]", (point, mid, end), width, layers[index], net))
        elif point != points[index + 1]:
            tracks.append(_track(key, f"seg[{index}]", point, points[index + 1], width, layers[index], net))
    return tracks, arcs, vias


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
    key = intent.key
    net = _required_net(board, intent.net, key, "via")
    kind = _via_kind(intent, key)
    named: object = getattr(intent, "layers", None)
    span: tuple[str, str] | None = None
    if kind == "through":
        if named is not None:
            raise _Refused(
                "kicad.copper.bad-layer",
                f"{key}: a through via spans the whole board, so it takes no layers",
                key,
            )
    else:
        pair = tuple(cast("Sequence[object]", named)) if isinstance(named, (tuple, list)) else ()
        if len(pair) != 2 or not all(isinstance(name, str) for name in pair) or pair[0] == pair[1]:
            raise _Refused(
                "kicad.copper.bad-layer",
                f"{key}: a {kind} via names its two different copper layers in layers, not {named!r}",
                key,
            )
        first, second = cast("tuple[str, str]", pair)
        _copper_layer(board, first, key)
        _copper_layer(board, second, key)
        span = _via_span(board, kind, first, second, key)
    sizes = _via_sizes((intent.diameter, intent.drill), board.netclass(net), net, key)
    return _via(key, "via", intent.at, sizes, board, net, kind, span)


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


@dataclass(frozen=True, slots=True)
class _Barriers:
    """Where a stitch via may not go besides other copper: the rule areas that forbid vias, and the rings
    of the board outline with the edge clearance in force (change c0074; ``H-K-STITCH-AVOID``)."""

    keepouts: tuple[_Obstacle, ...] = ()
    edges: tuple[_Obstacle, ...] = ()
    edge_clearance: int = 0
    rings: tuple[tuple[Point, ...], ...] = ()
    """The board ring, then its cut-outs, as ``board_outline`` gives them."""

    def blocks(self, point: Point, diameter: int) -> bool:
        """Whether the via disc at ``point`` meets a keep-out, comes closer to the board edge than the
        edge clearance, or lies off the board: outside its ring or inside a cut-out."""
        if any(_closer(point, diameter, area, 0, touching=True) for area in self.keepouts):
            return True
        if any(_closer(point, diameter, ring, self.edge_clearance) for ring in self.edges):
            return True
        if not self.rings:
            return False
        if point_in_ring(point, self.rings[0]) is Location.OUTSIDE:
            return True
        return any(point_in_ring(point, hole) is Location.INSIDE for hole in self.rings[1:])


def edge_clearance_in_force(design: Design, floor: Nm = 0) -> Nm:
    """The copper-to-edge clearance a stitch via keeps: the ``min`` of the governing board-wide
    ``edge_clearance`` rule, the last of them in ``rulemap.rule_order``, else ``floor``, the project's
    ``min_copper_edge_clearance``."""
    rules = design.rules.rules if design.rules is not None else ()
    wide = [
        rule
        for rule in rule_order(rules)
        if rule.kind == "edge_clearance" and rule.selector_a.op == "all" and rule.min is not None
    ]
    limit = wide[-1].min if wide else floor
    return max(0, limit if limit is not None else 0)


def _barriers(
    board: _Board, keepouts: Iterable[Keepout], outline: BoardOutline, edge_clearance: int
) -> _Barriers:
    """The keep-outs that forbid vias on a copper layer (a through via crosses every copper layer), and
    each ring of a closed outline as a closed polyline. Without a closed outline the edge is not checked."""
    copper = board.copper_layers
    areas = tuple(
        _Obstacle(tuple(area.outline), 0, True, None)
        for area in keepouts
        if area.no_vias and len(area.outline) >= 3 and set(expand_layers(area.layers, copper)) & set(copper)
    )
    rings = tuple(_Obstacle((*ring, ring[0]), 0, False, None) for ring in outline.rings)
    return _Barriers(areas, rings, edge_clearance, outline.rings)


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
    board: _Board,
    intent: StitchIntentLike,
    obstacles: Sequence[_Obstacle],
    issues: list[Issue],
    barriers: _Barriers | None = None,
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
        blocked = blocked or (barriers is not None and barriers.blocks(point, diameter))
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
                "copper, out of the rule areas that forbid vias and off the board edge",
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
    """What makes two items the same copper: the ends of a track or an arc as an unordered pair (an arc
    with the same mid point)."""
    fields = _fields(item, names)
    if isinstance(item, Track):
        first, second = sorted((item.start, item.end))
        return ("track", first, second, *fields[3:])
    if isinstance(item, Arc):
        first, second = sorted((item.start, item.end))
        return ("arc", first, item.mid, second, *fields[4:])
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
    script: dict[str, Track | Arc | Via] = {}
    for item in (*new.tracks, *new.arcs, *new.vias) if new is not None else ():
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
    keepouts: Sequence[Keepout] = (),
    outline: BoardOutline | None = None,
    edge_floor: Nm = 0,
) -> Design:
    """``design`` with the copper of ``intents``: the tracks, arcs and vias that ``merge_copper`` keeps, in
    their order, followed by the created tracks, arcs and vias in intent order. An intent with an error
    creates nothing; ``unplaced`` names the components the build staged. Nothing is read or written.

    Stitch vias also stay out of the rule areas that forbid vias, those of the design and the ``keepouts``
    given besides (a rebuild passes those of the existing board), and off the board edge: ``outline`` is
    the outline to keep clear of (default: ``board_outline(design)``), and ``edge_floor`` the project's
    ``min_copper_edge_clearance``, used when no board-wide ``edge_clearance`` rule governs."""
    found: list[Issue] = []
    if design.board is None:
        if issues is not None and intents:
            issues.append(_issue("kicad.copper.bad-intent", "the design has no board to draw copper on", ""))
        return design
    board = _board(design, unplaced)
    barriers = _barriers(
        board,
        (*design.board.keepouts, *keepouts),
        outline if outline is not None else board_outline(design),
        edge_clearance_in_force(design, edge_floor),
    )
    user = [
        [item for item in group if not is_copper_uuid(item.native_ids.get("kicad", ""))]
        for group in (design.board.tracks, design.board.arcs, design.board.vias)
    ]
    tracks: list[Track] = []
    arcs: list[Arc] = []
    vias: list[Via] = []
    seen: set[str] = set()
    for intent in intents:
        key = intent.key
        try:
            if key in seen:
                raise _Refused("kicad.copper.bad-intent", f"{key}: the key is used by an earlier intent", key)
            seen.add(key)
            if hasattr(intent, "path"):
                new_tracks, new_arcs, new_vias = _resolve_track(board, cast(TrackIntentLike, intent))
                tracks += new_tracks
                arcs += new_arcs
                vias += new_vias
            elif hasattr(intent, "pitch"):
                obstacles = _obstacles(
                    board,
                    (*cast("list[Track]", user[0]), *tracks),
                    (*cast("list[Arc]", user[1]), *arcs),
                    (*cast("list[Via]", user[2]), *vias),
                )
                vias += _resolve_stitch(board, cast(StitchIntentLike, intent), obstacles, found, barriers)
            else:
                vias.append(_resolve_via(board, cast(ViaIntentLike, intent)))
        except _Refused as refused:
            found.append(refused.issue)
    built = dataclasses.replace(
        design,
        board=dataclasses.replace(design.board, tracks=tuple(tracks), arcs=tuple(arcs), vias=tuple(vias)),
    )
    merge = merge_copper(design, built)
    found += merge.issues
    old = design.board
    result = dataclasses.replace(
        design,
        board=dataclasses.replace(
            old,
            tracks=(*(t for t in old.tracks if t.id in merge.kept), *tracks),
            arcs=(*(a for a in old.arcs if a.id in merge.kept), *arcs),
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
    "VIA_KINDS",
    "ArcStepLike",
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

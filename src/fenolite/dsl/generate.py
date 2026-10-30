# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generated copper of the DSL: power bands, keep-out rings, class barriers, body keep-outs, fan-out to a
zone and stitching of zone pieces (``docs/copper.md``, "Generated copper"; capability design-dsl,
"Generated copper calls").

A script cannot know where a pad ends up nor compute with polygons (``dsl`` imports no geometry), so each
call checks its arguments and records plain data; the KiCad build resolves the records after placement and
script copper (``fenolite.backends.kicad.generate``) into ordinary zones, rule areas, tracks and vias. Every
record has the key ``<call>.<name>``, from which the names and ids of what it generates derive.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, cast

from fenolite.core.coords import Point
from fenolite.core.units import Nm
from fenolite.dsl.errors import DslError
from fenolite.dsl.items import AREA_NAME, FORBID
from fenolite.dsl.part import Net, Part
from fenolite.dsl.units import as_nm

if TYPE_CHECKING:
    from fenolite.dsl.design import Design

KEEPOUT_FORBID: tuple[str, ...] = ("tracks", "vias", "pours")
"""What a generated keep-out forbids unless the call says otherwise."""
SIDES: tuple[str, ...] = ("top", "bottom")
"""The sides a fan-out takes its pads from."""
FULL_TURN = 360_000_000
"""A full turn in microdegrees: the number of sides of a ring divides it."""
MIN_SIDES = 8


@dataclass(frozen=True, slots=True)
class BandIntent:
    """A power band of ``net`` along ``spine`` (board-frame points, horizontal and vertical segments):
    ``width`` wide, each side widened in levels of ``step`` up to ``max_width / 2`` where it keeps
    ``clearance`` (``None``: the net's class clearance) from other nets' copper."""

    call: ClassVar[str] = "band"
    name: str
    net: str
    spine: tuple[Point, ...]
    width: Nm
    max_width: Nm
    step: Nm
    layers: tuple[str, ...]
    clearance: Nm | None = None
    priority: int = 0

    @property
    def key(self) -> str:
        return f"{self.call}.{self.name}"


@dataclass(frozen=True, slots=True)
class RingIntent:
    """Keep-out rings of ``sides`` sides around each hole of the part ``component`` (a component path)."""

    call: ClassVar[str] = "keepout_ring"
    name: str
    component: str
    setback: Nm
    layers: tuple[str, ...]
    forbid: tuple[str, ...] = KEEPOUT_FORBID
    sides: int = 32

    @property
    def key(self) -> str:
        return f"{self.call}.{self.name}"


@dataclass(frozen=True, slots=True)
class BarrierIntent:
    """The band ``setback`` wide around the copper of the net class ``netclass``, as rule areas."""

    call: ClassVar[str] = "barrier"
    name: str
    netclass: str
    setback: Nm
    layers: tuple[str, ...]
    forbid: tuple[str, ...] = KEEPOUT_FORBID
    pieces: bool = False

    @property
    def key(self) -> str:
        return f"{self.call}.{self.name}"


@dataclass(frozen=True, slots=True)
class BodyKeepoutIntent:
    """A keep-out over the plan view of the part ``component``, grown by ``setback``."""

    call: ClassVar[str] = "body_keepout"
    name: str
    component: str
    setback: Nm
    layers: tuple[str, ...]
    forbid: tuple[str, ...] = KEEPOUT_FORBID

    @property
    def key(self) -> str:
        return f"{self.call}.{self.name}"


@dataclass(frozen=True, slots=True)
class FanoutZoneIntent:
    """A track and a through via from each SMD pad of ``net`` on ``side`` (of the parts ``refs``, component
    paths, when not empty) to the zone of ``net`` on another layer."""

    call: ClassVar[str] = "fanout_zone"
    name: str
    net: str
    side: str = "top"
    refs: tuple[str, ...] = ()
    width: Nm | None = None
    diameter: Nm | None = None
    drill: Nm | None = None
    clearance: Nm | None = None

    @property
    def key(self) -> str:
        return f"{self.call}.{self.name}"


@dataclass(frozen=True, slots=True)
class StitchPiecesIntent:
    """Through vias of ``net`` on a grid of ``pitch`` in each overlap of two zones of ``net`` on different
    layers of ``layers``, at least ``min_vias`` per overlap."""

    call: ClassVar[str] = "stitch_pieces"
    name: str
    net: str
    pitch: Nm
    layers: tuple[str, ...]
    min_vias: int = 2
    diameter: Nm | None = None
    drill: Nm | None = None
    clearance: Nm | None = None
    margin: Nm = 0

    @property
    def key(self) -> str:
        return f"{self.call}.{self.name}"


GeneratedIntent = (
    BandIntent | RingIntent | BarrierIntent | BodyKeepoutIntent | FanoutZoneIntent | StitchPiecesIntent
)
CALLS: tuple[str, ...] = ("keepout_ring", "body_keepout", "barrier", "band", "fanout_zone", "stitch_pieces")
"""The calls in the order the build resolves them: keep-outs first, so vias avoid them, then bands, so
stitches find them."""


@dataclass(frozen=True, slots=True)
class Recorded:
    """What a call records: its intent, and the nets and parts it names, checked against the design when
    ``generated`` reads it."""

    intent: GeneratedIntent
    nets: tuple[Net, ...] = ()
    parts: tuple[Part, ...] = ()


# --- argument checks --------------------------------------------------------------------------------


def _name(design: Design, call: str, name: object, default: str) -> str:
    chosen = default if name is None else name
    if not isinstance(chosen, str) or not AREA_NAME.fullmatch(chosen):
        raise DslError(
            f"{call}(): the name {chosen!r} must match {AREA_NAME.pattern}"
            + ("; pass name=" if name is None else "")
        )
    if f"{call}.{chosen}" in design.generated:
        raise DslError(f"{call}(): the name {chosen!r} is already used; pass another name=")
    return chosen


def _length(value: object, what: str, *, positive: bool = True) -> Nm:
    length = as_nm(value, name=what)
    if positive and length <= 0:
        raise DslError(f"{what} must be above 0")
    if not positive and length < 0:
        raise DslError(f"{what} must not be negative")
    return length


def _optional(value: object, what: str, *, positive: bool = True) -> Nm | None:
    return None if value is None else _length(value, what, positive=positive)


def _net(value: object, what: str) -> Net:
    if not isinstance(value, Net):
        raise DslError(f"{what}: net must be a Net, not {value!r}")
    return value


def _part(value: object, what: str) -> Part:
    if not isinstance(value, Part):
        raise DslError(f"{what}: give a Part (a hole() or any part of the design), not {value!r}")
    return value


def _forbid(value: object, what: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence) or not value:
        raise DslError(f"{what}: forbid must be a non-empty tuple of {', '.join(FORBID)}, not {value!r}")
    kinds: list[str] = []
    for kind in cast("Sequence[object]", value):
        if not isinstance(kind, str) or kind not in FORBID:
            raise DslError(f"{what}: forbid: {kind!r} is not one of {', '.join(FORBID)}")
        if kind in kinds:
            raise DslError(f"{what}: forbid: {kind!r} is listed twice")
        kinds.append(kind)
    return tuple(kinds)


def _whole(value: object, what: str, least: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < least:
        raise DslError(f"{what} must be an int of at least {least}, not {value!r}")
    return value


def _spine(value: object, what: str) -> tuple[Point, ...]:
    from fenolite.dsl.convert import BOARD_ORIGIN

    if isinstance(value, str) or not isinstance(value, Sequence) or len(cast("Sequence[object]", value)) < 2:
        raise DslError(f"{what}: the spine is a sequence of at least two (x, y) points")
    points: list[Point] = []
    for index, pair in enumerate(cast("Sequence[object]", value)):
        xy = cast("Sequence[object]", pair) if isinstance(pair, (tuple, list)) else ()
        if len(xy) != 2:
            raise DslError(f"{what}: spine[{index}] must be an (x, y) pair of lengths, not {pair!r}")
        points.append(
            Point(
                BOARD_ORIGIN.x + as_nm(xy[0], name=f"{what}: spine[{index}].x"),
                BOARD_ORIGIN.y + as_nm(xy[1], name=f"{what}: spine[{index}].y"),
            )
        )
    previous: tuple[int, int] | None = None
    for index, (a, b) in enumerate(zip(points, points[1:], strict=False)):
        dx, dy = b.x - a.x, b.y - a.y
        if (dx == 0) == (dy == 0):
            raise DslError(
                f"{what}: spine segment {index} must be horizontal or vertical and not empty "
                f"(from {a.x - BOARD_ORIGIN.x} nm, {a.y - BOARD_ORIGIN.y} nm)"
            )
        direction = ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))
        if previous is not None and direction == (-previous[0], -previous[1]):
            raise DslError(f"{what}: spine segment {index} turns back on segment {index - 1}")
        previous = direction
    return tuple(points)


def _record(design: Design, record: Recorded) -> None:
    for net in record.nets:
        design.register_net(net)
    design.generated[record.intent.key] = record


# --- the calls, as ``Design`` forwards them ------------------------------------------------------------


def record_band(
    design: Design,
    net: object,
    spine: object,
    *,
    width: object,
    layers: tuple[str, ...],
    max_width: object,
    step: object,
    clearance: object,
    priority: object,
    name: object,
) -> None:
    chosen = _net(net, "band()")
    label = _name(design, "band", name, chosen.name)
    what = f"band {label}"
    points = _spine(spine, what)
    wide = _length(width, f"{what}: width")
    widest = wide if max_width is None else _length(max_width, f"{what}: max_width")
    if widest < wide:
        raise DslError(f"{what}: max_width must be at least width")
    room = widest // 2 - wide // 2
    if step is None:
        level = room if room > 0 else max(1, wide // 2)
    else:
        level = _length(step, f"{what}: step")
    if room and level > room:
        raise DslError(f"{what}: step must be at most (max_width - width) / 2")
    for index, (a, b) in enumerate(zip(points, points[1:], strict=False)):
        if abs(b.x - a.x) + abs(b.y - a.y) < widest:
            raise DslError(f"{what}: spine segment {index} is shorter than max_width ({widest} nm)")
    _record(
        design,
        Recorded(
            BandIntent(
                label,
                chosen.name,
                points,
                wide,
                widest,
                level,
                layers,
                _optional(clearance, f"{what}: clearance", positive=False),
                _whole(priority, f"{what}: priority", 0),
            ),
            nets=(chosen,),
        ),
    )


def record_ring(
    design: Design,
    part: object,
    *,
    setback: object,
    layers: tuple[str, ...],
    forbid: object,
    sides: object,
    name: object,
) -> None:
    target = _part(part, "keepout_ring()")
    label = _name(design, "keepout_ring", name, target.label)
    what = f"keepout_ring {label}"
    count = _whole(sides, f"{what}: sides", MIN_SIDES)
    if FULL_TURN % count:
        raise DslError(f"{what}: sides must divide 360000000 (a whole number of microdegrees per side)")
    intent = RingIntent(
        label, target.path, _length(setback, f"{what}: setback", positive=False), layers,
        _forbid(forbid, what), count,
    )  # fmt: skip
    _record(design, Recorded(intent, parts=(target,)))


def record_barrier(
    design: Design,
    netclass: object,
    *,
    setback: object,
    layers: tuple[str, ...],
    forbid: object,
    pieces: object,
    name: object,
) -> None:
    if not isinstance(netclass, str) or not netclass:
        raise DslError(f"barrier(): netclass must be the name of a net class, not {netclass!r}")
    label = _name(design, "barrier", name, netclass)
    what = f"barrier {label}"
    if not isinstance(pieces, bool):
        raise DslError(f"{what}: pieces must be a bool, not {pieces!r}")
    intent = BarrierIntent(
        label, netclass, _length(setback, f"{what}: setback"), layers, _forbid(forbid, what), pieces
    )
    _record(design, Recorded(intent))


def record_body(
    design: Design,
    part: object,
    *,
    setback: object,
    layers: tuple[str, ...],
    forbid: object,
    name: object,
) -> None:
    target = _part(part, "body_keepout()")
    label = _name(design, "body_keepout", name, target.label)
    what = f"body_keepout {label}"
    back = _length(setback, f"{what}: setback", positive=False)
    intent = BodyKeepoutIntent(label, target.path, back, layers, _forbid(forbid, what))
    _record(design, Recorded(intent, parts=(target,)))


def record_fanout(
    design: Design,
    net: object,
    *,
    side: object,
    refs: object,
    width: object,
    diameter: object,
    drill: object,
    clearance: object,
    name: object,
) -> None:
    chosen = _net(net, "fanout_zone()")
    label = _name(design, "fanout_zone", name, chosen.name)
    what = f"fanout_zone {label}"
    if side not in SIDES:
        raise DslError(f"{what}: side must be one of {', '.join(SIDES)}, not {side!r}")
    parts: tuple[Part, ...] = ()
    if refs is not None:
        if isinstance(refs, (str, Part)) or not isinstance(refs, Sequence) or not refs:
            raise DslError(f"{what}: refs must be a non-empty sequence of parts, not {refs!r}")
        parts = tuple(_part(ref, what) for ref in cast("Sequence[object]", refs))
    sizes = {
        key: _optional(value, f"{what}: {key}")
        for key, value in (("width", width), ("diameter", diameter), ("drill", drill))
    }
    if sizes["diameter"] is not None and sizes["drill"] is not None and sizes["drill"] >= sizes["diameter"]:
        raise DslError(f"{what}: drill must be smaller than diameter")
    intent = FanoutZoneIntent(
        label,
        chosen.name,
        cast(str, side),
        tuple(part.path for part in parts),
        sizes["width"],
        sizes["diameter"],
        sizes["drill"],
        _optional(clearance, f"{what}: clearance", positive=False),
    )
    _record(design, Recorded(intent, nets=(chosen,), parts=parts))


def record_stitch_pieces(
    design: Design,
    net: object,
    *,
    pitch: object,
    layers: tuple[str, ...],
    min_vias: object,
    diameter: object,
    drill: object,
    clearance: object,
    margin: object,
    name: object,
) -> None:
    chosen = _net(net, "stitch_pieces()")
    label = _name(design, "stitch_pieces", name, chosen.name)
    what = f"stitch_pieces {label}"
    if len(layers) < 2:
        raise DslError(f"{what}: layers must name at least two copper layers")
    hole = _optional(drill, f"{what}: drill")
    size = _optional(diameter, f"{what}: diameter")
    if size is not None and hole is not None and hole >= size:
        raise DslError(f"{what}: drill must be smaller than diameter")
    intent = StitchPiecesIntent(
        label,
        chosen.name,
        _length(pitch, f"{what}: pitch"),
        layers,
        _whole(min_vias, f"{what}: min_vias", 1),
        size,
        hole,
        _optional(clearance, f"{what}: clearance", positive=False),
        0 if margin is None else _length(margin, f"{what}: margin", positive=False),
    )
    _record(design, Recorded(intent, nets=(chosen,)))


# --- what the build reads ---------------------------------------------------------------------------


def generated(design: Design) -> tuple[GeneratedIntent, ...]:
    """The generated-copper records of ``design`` as plain data, in key order: nets by name, parts by
    component path, points in the written board frame. A net or a part that is not in the design raises
    ``DslError``."""
    found: list[GeneratedIntent] = []
    for key in sorted(design.generated):
        record = design.generated[key]
        for net in record.nets:
            if design.nets.get(net.name) is not net:
                raise DslError(f"{key}: net {net.name} is not in the design")
        for part in record.parts:
            if design.parts.get(part.path) is not part:
                raise DslError(f"{key}: part {part.ref} is not in the design")
        found.append(record.intent)
    return tuple(found)


__all__ = [
    "CALLS",
    "KEEPOUT_FORBID",
    "SIDES",
    "BandIntent",
    "BarrierIntent",
    "BodyKeepoutIntent",
    "FanoutZoneIntent",
    "GeneratedIntent",
    "Recorded",
    "RingIntent",
    "StitchPiecesIntent",
    "generated",
]

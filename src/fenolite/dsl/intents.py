# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper intents of the DSL: tracks, arcs, vias and stitches declared by pad references, board points and
anchors in a part's frame (``docs/dsl.md``, "Copper"; capability design-dsl, "Copper intents in the DSL"
and "Copper anchors in the DSL").

A script cannot know where a pad ends up: the build decides each placement after the script ran, and a
footprint moved in KiCad keeps its place. So the script records what to join, as plain data, and the build
resolves it after placement (``fenolite.backends.kicad.copper``). Nothing here is a model object.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from fenolite.core.coords import Point
from fenolite.core.units import Nm
from fenolite.dsl.errors import DslError
from fenolite.dsl.part import Net, Part
from fenolite.dsl.units import as_nm
from fenolite.model.board import ViaProtection

if TYPE_CHECKING:
    from fenolite.dsl.design import Design

KEY = re.compile(r"^[A-Za-z0-9_.+-]+(/[A-Za-z0-9_.+-]+)*$")
"""A copper key: it names the intent stably, and every uuid of its copper derives from it."""
VIA_KINDS = ("through", "blind", "buried", "micro")
"""The kinds of a via (``Via.via_type`` of the model)."""


@dataclass(frozen=True, slots=True)
class PadRef:
    """The pads of a part with one number, as a script names them; ``index`` picks one of several."""

    part: Part
    number: str
    index: int | None = None

    def at(self, dx: object = None, dy: object = None) -> AnchorRef:
        """The point ``(dx, dy)`` from the position of these pads, in the frame of the part's footprint as
        its library draws it (X to the right, Y down); a length left out is 0. The build resolves it after
        placement, so the point follows the part. It is a point only: it joins no pad."""
        return anchor_ref(self.part, self.number, self.index, dx, dy)


@dataclass(frozen=True, slots=True)
class AnchorRef:
    """A point in the frame of a part's footprint, as a script names it: ``offset`` (nanometres, X to the
    right, Y down, as the library draws the footprint) from the footprint's origin, or from the position
    of the pads ``number`` and ``index`` name. ``part.at(…)`` and ``part.pad(…).at(…)`` make one."""

    part: Part
    number: str | None
    index: int | None
    offset: Point

    @property
    def component(self) -> str:
        """The component path of the part, as the build names it."""
        return self.part.path


@dataclass(frozen=True, slots=True)
class PadEnd:
    """A pad end as the build reads it: the component path, the pad number and the optional index."""

    component: str
    number: str
    index: int | None = None


@dataclass(frozen=True, slots=True)
class Anchor:
    """An anchor as the build reads it: the component path, the pad number as text or ``None`` for the
    footprint's origin, the index, and the offset in the footprint's library frame (not shifted by
    ``BOARD_ORIGIN``: it is not a board point until the build resolves it after placement)."""

    component: str
    number: str | None
    index: int | None
    offset: Point


Spot = Point | Anchor | AnchorRef
"""Where script copper takes a point: a board point, or an anchor (an ``AnchorRef`` as a script records
it, an ``Anchor`` in what ``copper()`` returns)."""


@dataclass(frozen=True, slots=True)
class ViaStep:
    """A via of ``kind`` inside a track path at ``at`` (a board-frame point or an anchor), after which the
    track runs on ``layer``. New fields come last and have defaults, so a step built without them is a
    through via."""

    at: Spot
    layer: str
    diameter: Nm | None = None
    drill: Nm | None = None
    kind: str = "through"
    protection: ViaProtection = ViaProtection()


@dataclass(frozen=True, slots=True)
class ArcStep:
    """An arc inside a track path: from the point of the element before it through ``mid`` to ``end``
    (board-frame points or anchors), the three-point form of the model and of KiCad's file. The path
    continues from ``end``."""

    mid: Spot
    end: Spot


PathElement = PadEnd | Point | Anchor | ViaStep | ArcStep


@dataclass(frozen=True, slots=True)
class TrackIntent:
    key: str
    path: tuple[PathElement, ...]
    layer: str = "F.Cu"
    width: Nm | None = None
    net: str | None = None
    locked: bool = False


@dataclass(frozen=True, slots=True)
class ViaIntent:
    """One via; ``layers`` are the two copper layers of a via that is not a through via."""

    key: str
    at: Point | Anchor
    net: str
    diameter: Nm | None = None
    drill: Nm | None = None
    kind: str = "through"
    layers: tuple[str, str] | None = None
    protection: ViaProtection = ViaProtection()
    locked: bool = False


@dataclass(frozen=True, slots=True)
class StitchIntent:
    """Stitching vias; ``region`` is a ring of points, or a ``PadEnd``: the copper of that pad."""

    key: str
    net: str
    pitch: Nm
    along: tuple[Point | Anchor, ...] = ()
    region: tuple[Point | Anchor, ...] | PadEnd = ()
    origin: Point | Anchor = Point(0, 0)
    diameter: Nm | None = None
    drill: Nm | None = None
    clearance: Nm | None = None
    margin: Nm = 0
    protection: ViaProtection = ViaProtection()
    locked: bool = False


CopperIntent = TrackIntent | ViaIntent | StitchIntent


# --- what a script records ------------------------------------------------------------------------


_Recorded = PadRef | Point | AnchorRef | ViaStep | ArcStep


@dataclass(frozen=True, slots=True)
class _Track:
    key: str
    path: tuple[_Recorded, ...]
    layer: str
    width: Nm | None
    net: Net | None
    locked: bool = False


@dataclass(frozen=True, slots=True)
class _Via:
    key: str
    at: Point | AnchorRef
    net: Net
    diameter: Nm | None
    drill: Nm | None
    kind: str = "through"
    layers: tuple[str, str] | None = None
    protection: ViaProtection = ViaProtection()
    locked: bool = False


@dataclass(frozen=True, slots=True)
class _Stitch:
    key: str
    net: Net
    pitch: Nm
    along: tuple[Point | AnchorRef, ...]
    region: tuple[Point | AnchorRef, ...] | PadRef
    origin: Point | AnchorRef
    diameter: Nm | None
    drill: Nm | None
    clearance: Nm | None
    margin: Nm
    protection: ViaProtection = ViaProtection()
    locked: bool = False


Recorded = _Track | _Via | _Stitch


def _origin() -> Point:
    from fenolite.dsl.convert import BOARD_ORIGIN

    return BOARD_ORIGIN


def _point(value: object, what: str) -> Point:
    """An ``(x, y)`` pair of lengths in the frame of ``place()``, as a board-frame point."""
    pair = cast("Sequence[object]", value) if isinstance(value, (tuple, list)) else ()
    if len(pair) != 2:
        raise DslError(f"{what}: a point is an (x, y) pair of lengths, not {value!r}")
    origin = _origin()
    return Point(origin.x + as_nm(pair[0], name=f"{what}.x"), origin.y + as_nm(pair[1], name=f"{what}.y"))


def anchor_ref(part: Part, number: str | None, index: int | None, dx: object, dy: object) -> AnchorRef:
    """The anchor ``(dx, dy)`` from the origin of the footprint of ``part``, or from its pads ``number``."""
    what = f"part {part.ref}: at()" if number is None else f"part {part.ref}: pad({number!r}).at()"
    offset = Point(
        0 if dx is None else as_nm(dx, name=f"{what}: dx"), 0 if dy is None else as_nm(dy, name=f"{what}: dy")
    )
    return AnchorRef(part, number, index, offset)


def _spot(value: object, what: str) -> Point | AnchorRef:
    """A point of script copper: an anchor, or an ``(x, y)`` pair in the frame of ``place()``."""
    if isinstance(value, AnchorRef):
        return value
    if isinstance(value, PadRef):
        raise DslError(
            f"{what}: part.pad(…) joins a pad and is not a point; write part.pad(…).at() for the point "
            "at the pad"
        )
    return _point(value, what)


def _one_point(x: object, y: object, what: str) -> Point | AnchorRef:
    """The point of ``via_step`` and ``Design.via``: two lengths, or one argument that is an anchor or an
    ``(x, y)`` pair."""
    if y is not None:
        if isinstance(x, (AnchorRef, PadRef, tuple, list)):
            raise DslError(f"{what}: give the point as one argument or as two lengths, not as both")
        return _point((x, y), what)
    if isinstance(x, (AnchorRef, PadRef, tuple, list)):
        return _spot(cast(object, x), what)
    raise DslError(
        f"{what}: the point is two lengths, an (x, y) pair or an anchor (part.at(…), part.pad(…).at(…)), "
        f"not {x!r} alone"
    )


def _size(value: object, what: str) -> Nm | None:
    if value is None:
        return None
    size = as_nm(value, name=what)
    if size <= 0:
        raise DslError(f"{what} must be positive")
    return size


def _layer(value: object, what: str) -> str:
    if not isinstance(value, str) or not value:
        raise DslError(f"{what} must be a copper layer name such as 'F.Cu', not {value!r}")
    return value


def _net(value: object, what: str, *, required: bool) -> Net | None:
    if value is None and not required:
        return None
    if not isinstance(value, Net):
        raise DslError(f"{what}: net must be a Net, not {value!r}")
    return value


def check_key(design: Design, key: object) -> str:
    if not isinstance(key, str) or not KEY.fullmatch(key):
        raise DslError(f"copper key {key!r} must match {KEY.pattern}")
    if key in design.copper_intents:
        raise DslError(f"copper key {key!r} is already used")
    return key


def pad_ref(part: Part, number: object, index: object) -> PadRef:
    if isinstance(number, bool) or not isinstance(number, (str, int)) or str(number) == "":
        raise DslError(f"part {part.ref}: a pad number is a non-empty str or an int, not {number!r}")
    if index is not None and (isinstance(index, bool) or not isinstance(index, int) or index < 0):
        raise DslError(f"part {part.ref}: a pad index is a non-negative int or None, not {index!r}")
    return PadRef(part, str(number), index)


def _kind(value: object, what: str) -> str:
    if value not in VIA_KINDS:
        raise DslError(f"{what}: kind must be one of {', '.join(VIA_KINDS)}, not {value!r}")
    return cast(str, value)


_SIDED = {True: (True, True), False: (False, False), "front": (True, False), "back": (False, True),
          None: (None, None)}  # fmt: skip


def _sided(value: object, name: str) -> tuple[bool | None, bool | None]:
    if not (value is None or isinstance(value, (bool, str))) or value not in _SIDED:
        raise DslError(f"protect(): {name} must be True, False, 'front', 'back' or None, not {value!r}")
    return _SIDED[value]  # type: ignore[index]


def _whole(value: object, name: str) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise DslError(f"protect(): {name} must be True, False or None, not {value!r}")
    return value


def protect(
    *,
    tenting: object = None,
    covering: object = None,
    plugging: object = None,
    capping: object = None,
    filling: object = None,
) -> ViaProtection:
    """How a via is protected (``docs/dsl.md``, "Via protection"). ``tenting``, ``covering`` and
    ``plugging`` take ``True`` (both sides), ``False`` (neither side), ``"front"`` or ``"back"`` (that side
    only) or ``None`` (both sides follow the board default); ``capping`` and ``filling`` take ``True``,
    ``False`` or ``None``. Pass the result as ``protection=`` to ``Design.via``, ``via_step`` or
    ``Design.stitch``, or to ``Design.via_protection`` as the board default."""
    return ViaProtection(
        *_sided(tenting, "tenting"), *_sided(covering, "covering"), *_sided(plugging, "plugging"),
        _whole(capping, "capping"), _whole(filling, "filling"),
    )  # fmt: skip


def _protection(value: object, what: str) -> ViaProtection:
    """``protection=`` of a via call: ``None`` records ``ViaProtection()``."""
    if value is None:
        return ViaProtection()
    if not isinstance(value, ViaProtection):
        raise DslError(f"{what}: protection must be None or the value of protect(), not {value!r}")
    return value


def via_step(
    x: object,
    y: object = None,
    *,
    to: str,
    diameter: object = None,
    drill: object = None,
    kind: str = "through",
    protection: object = None,
) -> ViaStep:
    """A via of ``kind`` (``through``, ``blind``, ``buried`` or ``micro``) at ``(x, y)`` in the frame of
    ``place()``, or at the one point given first: an ``(x, y)`` pair or an anchor (``part.at(…)``,
    ``part.pad(…).at(…)``); the track continues on the layer ``to``. ``protection`` is the value of
    ``protect()``."""
    return ViaStep(
        _one_point(x, y, "via_step"), _layer(to, "via_step: to"), _size(diameter, "via_step: diameter"),
        _size(drill, "via_step: drill"), _kind(kind, "via_step"), _protection(protection, "via_step"),
    )  # fmt: skip


def arc_to(mid: object, end: object) -> ArcStep:
    """An arc from the point of the path element before it through ``mid`` to ``end``, each an ``(x, y)``
    pair of lengths in the frame of ``place()`` or an anchor; the path continues from ``end``."""
    step = ArcStep(_spot(mid, "arc_to: mid"), _spot(end, "arc_to: end"))
    if step.mid == step.end:
        raise DslError("arc_to: mid and end are the same point")
    return step


def _place(element: _Recorded) -> Spot:
    """The point of a path element that is not a pad reference: the ``end`` of an arc step."""
    assert not isinstance(element, PadRef)
    if isinstance(element, ViaStep):
        return element.at
    return element.end if isinstance(element, ArcStep) else element


def _same_place(a: _Recorded, b: _Recorded) -> bool:
    if isinstance(a, PadRef) or isinstance(b, PadRef):
        return a == b
    return _place(a) == _place(b)


def _locked(value: object, what: str) -> bool:
    """``locked`` of a copper intent: a ``bool``, nothing else."""
    if not isinstance(value, bool):
        raise DslError(f"{what}: locked must be True or False, not {value!r}")
    return value


def record_track(
    design: Design,
    key: object,
    path: Sequence[object],
    layer: object,
    width: object,
    net: object,
    locked: object = False,
) -> None:
    name = check_key(design, key)
    what = f"track {name}"
    if len(path) < 2:
        raise DslError(f"{what}: a path needs at least two elements")
    elements: list[_Recorded] = []
    for index, element in enumerate(path):
        if isinstance(element, (PadRef, AnchorRef, ViaStep, ArcStep)):
            elements.append(element)
        elif isinstance(element, (tuple, list)):
            elements.append(_point(cast(object, element), f"{what}: path[{index}]"))
        else:
            raise DslError(
                f"{what}: path[{index}] must be part.pad(…), an anchor (part.at(…), part.pad(…).at(…)), "
                f"via_step(…), arc_to(…) or an (x, y) pair, not {element!r}"
            )
    if isinstance(elements[0], ViaStep):
        raise DslError(f"{what}: a path cannot start with a via step")
    if isinstance(elements[0], ArcStep):
        raise DslError(
            f"{what}: a path cannot start with an arc step: an arc starts at the element before it"
        )
    for index, (a, b) in enumerate(zip(elements, elements[1:], strict=False)):
        if _same_place(a, b):
            raise DslError(f"{what}: path[{index}] and path[{index + 1}] are at the same point")
    design.copper_intents[name] = _Track(
        name,
        tuple(elements),
        _layer(layer, f"{what}: layer"),
        _size(width, f"{what}: width"),
        _net(net, what, required=False),
        _locked(locked, what),
    )


def _via_layers(value: object, kind: str, what: str) -> tuple[str, str] | None:
    """``layers`` of a single via: none for a through via, two different layer names for another kind."""
    if kind == "through":
        if value is not None:
            raise DslError(f"{what}: layers cannot be given for a through via, which spans the whole board")
        return None
    pair = cast("Sequence[object]", value) if isinstance(value, (tuple, list)) else ()
    names = [name for name in pair if isinstance(name, str) and name]
    if len(pair) != 2 or len(names) != 2 or names[0] == names[1]:
        raise DslError(
            f"{what}: layers must name the two different copper layers of a {kind} via, such as "
            f"('F.Cu', 'In1.Cu'), not {value!r}"
        )
    return names[0], names[1]


def record_via(
    design: Design,
    key: object,
    x: object,
    y: object,
    net: object,
    diameter: object,
    drill: object,
    kind: object = "through",
    layers: object = None,
    locked: object = False,
    protection: object = None,
) -> None:
    name = check_key(design, key)
    what = f"via {name}"
    chosen = _net(net, what, required=True)
    assert chosen is not None
    via_kind = _kind(kind, what)
    design.copper_intents[name] = _Via(
        name,
        _one_point(x, y, what),
        chosen,
        _size(diameter, f"{what}: diameter"),
        _size(drill, f"{what}: drill"),
        via_kind,
        _via_layers(layers, via_kind, what),
        _protection(protection, what),
        _locked(locked, what),
    )


def record_stitch(
    design: Design,
    key: object,
    *,
    net: object,
    pitch: object,
    along: Sequence[object],
    region: object,
    origin: object,
    diameter: object,
    drill: object,
    clearance: object,
    margin: object,
    locked: object = False,
    protection: object = None,
) -> None:
    name = check_key(design, key)
    what = f"stitch {name}"
    chosen = _net(net, what, required=True)
    assert chosen is not None
    step = _size(pitch, f"{what}: pitch")
    if step is None:
        raise DslError(f"{what}: pitch is required")
    line = tuple(_spot(p, f"{what}: along[{i}]") for i, p in enumerate(along))
    ring: tuple[Point | AnchorRef, ...] | PadRef
    if isinstance(region, PadRef):
        ring = region  # the copper of that pad: not a ring, so the three-point rule does not apply
        if origin is not None and not isinstance(origin, (AnchorRef, PadRef)):
            raise DslError(
                f"{what}: a pad region lays its grid from the pad; leave origin out or give an anchor "
                "(part.at(…), part.pad(…).at(…)), not a board point"
            )
    elif isinstance(region, Sequence) and not isinstance(region, str):
        points = cast("Sequence[object]", region)
        ring = tuple(_spot(p, f"{what}: region[{i}]") for i, p in enumerate(points))
    else:
        raise DslError(f"{what}: region is a sequence of points or part.pad(…), not {region!r}")
    if bool(line) == bool(ring):
        raise DslError(f"{what}: give exactly one of along and region")
    if line and len(line) < 2:
        raise DslError(f"{what}: along needs at least two points")
    if not isinstance(ring, PadRef) and ring and len(ring) < 3:
        raise DslError(f"{what}: region needs at least three points")
    gap = 0 if margin is None else as_nm(margin, name=f"{what}: margin")
    if gap < 0:
        raise DslError(f"{what}: margin must not be negative")
    free = None if clearance is None else as_nm(clearance, name=f"{what}: clearance")
    if free is not None and free < 0:
        raise DslError(f"{what}: clearance must not be negative")
    design.copper_intents[name] = _Stitch(
        name,
        chosen,
        step,
        line,
        ring,
        _origin() if origin is None else _spot(origin, f"{what}: origin"),
        _size(diameter, f"{what}: diameter"),
        _size(drill, f"{what}: drill"),
        free,
        gap,
        _protection(protection, what),
        _locked(locked, what),
    )


def _net_name(design: Design, net: Net, key: str) -> str:
    if design.nets.get(net.name) is not net:
        raise DslError(f"copper {key}: net {net.name} is not in the design")
    return net.name


def _in_design(design: Design, part: Part, key: str) -> str:
    if design.parts.get(part.path) is not part:
        raise DslError(f"copper {key}: part {part.ref} is not in the design")
    return part.path


def _plain(design: Design, spot: Spot, key: str) -> Point | Anchor:
    """A point as it is, an anchor with the component path of its part."""
    if isinstance(spot, AnchorRef):
        return Anchor(_in_design(design, spot.part, key), spot.number, spot.index, spot.offset)
    return spot


def _pad_end(design: Design, ref: PadRef, key: str) -> PadEnd:
    return PadEnd(_in_design(design, ref.part, key), ref.number, ref.index)


def _end(design: Design, element: _Recorded, key: str) -> PathElement:
    if isinstance(element, PadRef):
        return _pad_end(design, element, key)
    if isinstance(element, ViaStep):
        at = _plain(design, element.at, key)
        return element if at is element.at else dataclasses.replace(element, at=at)
    if isinstance(element, ArcStep):
        mid, end = _plain(design, element.mid, key), _plain(design, element.end, key)
        return element if mid is element.mid and end is element.end else ArcStep(mid, end)
    return _plain(design, element, key)


def copper(design: Design) -> tuple[CopperIntent, ...]:
    """The copper intents of ``design`` as plain data, in key order: pad references become component
    paths, nets their names, every point is in the written board frame, and every anchor is an ``Anchor``
    whose offset stays in its footprint's frame."""
    found: list[CopperIntent] = []
    for key in sorted(design.copper_intents):
        item = design.copper_intents[key]
        if isinstance(item, _Track):
            net = None if item.net is None else _net_name(design, item.net, key)
            path = tuple(_end(design, element, key) for element in item.path)
            found.append(TrackIntent(key, path, item.layer, item.width, net, item.locked))
        elif isinstance(item, _Via):
            net_name = _net_name(design, item.net, key)
            at = _plain(design, item.at, key)
            found.append(
                ViaIntent(
                    key, at, net_name, item.diameter, item.drill, item.kind, item.layers,
                    item.protection, item.locked,
                )
            )  # fmt: skip
        else:
            found.append(
                StitchIntent(
                    key,
                    _net_name(design, item.net, key),
                    item.pitch,
                    tuple(_plain(design, p, key) for p in item.along),
                    _pad_end(design, item.region, key)
                    if isinstance(item.region, PadRef)
                    else tuple(_plain(design, p, key) for p in item.region),
                    _plain(design, item.origin, key),
                    item.diameter,
                    item.drill,
                    item.clearance,
                    item.margin,
                    item.protection,
                    item.locked,
                )
            )
    return tuple(found)


__all__ = [
    "KEY",
    "VIA_KINDS",
    "Anchor",
    "AnchorRef",
    "ArcStep",
    "CopperIntent",
    "PadEnd",
    "PadRef",
    "Recorded",
    "StitchIntent",
    "TrackIntent",
    "ViaIntent",
    "ViaStep",
    "arc_to",
    "copper",
    "protect",
    "via_step",
]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The operations of a PCB edit session and the items they name (capability altium-edit, "Edit session on
an Altium document", "Asserted edits", "Records cloned from the document", "Index upkeep"; change c0241,
design Decision 5).

An item is named by kind, geometry and net (a component by designator), in nanometres from the board's
origin, Y up, as ``fenolite inspect`` and the kit's ``expected.md`` show it; it must match exactly one
record. Each operation states the old value of each field it changes. A failed match or a different old
value raises ``Refused`` with ``altium.edit.assertion``; a new record with no record of its kind and layer to
copy from raises it with ``altium.edit.no-template``. Every function edits a ``State`` and declares what it
removed and added; the index upkeep is in the same function as the edit that needs it.

The facts behind each function are the rows ``H-A-EDIT-*`` of ``docs/hypotheses.md``, all ``INFERRED``; what
the 2026-11-04 agent run of phase A observed is in ``docs/formats/altium/pcb-document.md``, "Edit
observations". Where that run shows Altium doing otherwise (it inserts a placed component first and renumbers
every component index, J13), the session does the smaller change (it appends) and phase B decides.
"""

# evidence: see edit.session

from __future__ import annotations

import math
import re
import secrets
import string
import struct
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from fractions import Fraction

from fenolite.backends.altium.docboard import angle_text, name_codes
from fenolite.backends.altium.edit import records as rec
from fenolite.backends.altium.edit.state import PRIMITIVE_STORAGES, SHAPE_BASED, WIDE, State
from fenolite.backends.altium.libboard import long_id
from fenolite.backends.altium.pcbrecords import (
    FLIP_PAIRS,
    LAYER_NAMES,
    layer_text,
    mil_text,
    to_units,
    v7_layer,
)
from fenolite.backends.altium.read.pcbprims import (
    ARC,
    FILL,
    PAD,
    REGION,
    TEXT,
    TRACK,
    VIA,
    ArcRecord,
    FillRecord,
    PadRecord,
    Primitive,
    RawPrimitive,
    RegionRecord,
    TextRecord,
    TrackRecord,
    ViaRecord,
    primitive_type,
)
from fenolite.backends.altium.read.pcbprops import PropertyRecord, parse_mil

TOLERANCE = 2
"""Two coordinates within this many units (1/10 000 mil, 2.54 nm each) are the same: a point given in
nanometres is rounded to a unit, and the document may hold the next unit."""
REACH = 787
"""0.002 mm in units: an item is the nearest record within this distance of what it states (change c0452,
Decision 2), so a point rounded to the micrometre, as ``fenolite inspect`` shows it, names its record."""
ID_LETTERS = string.ascii_uppercase
ID_LENGTH = 8
"""The form of a pad's ``UNIQUEID`` in every document read: eight upper-case letters (``H-A-EDIT-IDS``)."""
COMPONENT_STORAGES = ("Pads6", "Tracks6", "Arcs6", "Texts6", "Fills6", "Regions6", "ShapeBasedRegions6",
                      "Vias6", "ComponentBodies6", "ShapeBasedComponentBodies6")  # fmt: skip
KIND_NAMES = {
    TRACK: "track",
    VIA: "via",
    ARC: "arc",
    PAD: "pad",
    TEXT: "text",
    REGION: "region",
    FILL: "fill",
}

Point = tuple[int, int]
"""A point in nanometres from the board's origin, Y up."""


class Refused(Exception):
    """An operation that cannot be made as stated: ``code`` is ``altium.edit.assertion`` or
    ``altium.edit.no-template``."""

    def __init__(self, code: str, message: str, where: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.where = where


def _assert(condition: bool, message: str, where: str = "") -> None:
    if not condition:
        raise Refused("altium.edit.assertion", message, where)


# --- items -------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Track:
    """A track by its two ends (either order) and its net (``None``: no net); ``layer`` and ``width``
    (nanometres) narrow it."""

    start: Point
    end: Point
    net: str | None
    layer: str | None = None
    width: int | None = None


@dataclass(frozen=True, slots=True)
class Arc:
    """A free arc by its centre, its radius (nanometres) and its net; ``layer`` and ``width`` narrow it."""

    centre: Point
    radius: int
    net: str | None
    layer: str | None = None
    width: int | None = None


@dataclass(frozen=True, slots=True)
class Fill:
    """A free fill by two opposite corners of its rectangle (either pair) and its layer."""

    corner: Point
    opposite: Point
    layer: str
    net: str | None = None


@dataclass(frozen=True, slots=True)
class Via:
    at: Point
    net: str | None


@dataclass(frozen=True, slots=True)
class Component:
    designator: str


@dataclass(frozen=True, slots=True)
class Polygon:
    name: str


@dataclass(frozen=True, slots=True)
class Text:
    """A free text by the string it shows; ``layer`` keeps the texts on that layer, ``at`` the nearest one
    whose anchor lies within ``REACH`` of it (change c0497)."""

    text: str
    layer: str | None = None
    at: Point | None = None


@dataclass(frozen=True, slots=True)
class Designator:
    """The designator text of the component ``ref`` (change c0497)."""

    ref: str


@dataclass(frozen=True, slots=True)
class Comment:
    """The comment text of the component ``ref`` (change c0497)."""

    ref: str


@dataclass(frozen=True, slots=True)
class Vias:
    """Every via of ``net`` (``None``: every via) whose hole and diameter (nm), when given, match within
    ``TOLERANCE``: the selector of a bulk edit (change c0497)."""

    net: str | None = None
    hole: int | None = None
    diameter: int | None = None


@dataclass(frozen=True, slots=True)
class Region:
    """A free region by its layer and the lower-left corner of its outline's box."""

    layer: str
    corner: Point


Item = Track | Arc | Fill | Via | Component | Polygon | Text | Region | Designator | Comment


def describe(item: Item) -> str:
    def mm(p: Point) -> str:
        return f"({p[0] / 1e6:g}, {p[1] / 1e6:g}) mm"

    if isinstance(item, Track):
        return f"the track {mm(item.start)}–{mm(item.end)} on {item.net or 'no net'}"
    if isinstance(item, Arc):
        radius = f"{item.radius / 1e6:g} mm"
        return f"the arc of centre {mm(item.centre)} and radius {radius} on {item.net or 'no net'}"
    if isinstance(item, Fill):
        return f"the fill {mm(item.corner)}–{mm(item.opposite)} on {item.layer}"
    if isinstance(item, Via):
        return f"the via at {mm(item.at)} on {item.net or 'no net'}"
    if isinstance(item, Component):
        return f"the component {item.designator}"
    if isinstance(item, Polygon):
        return f"the polygon {item.name}"
    if isinstance(item, Text):
        return f"the text {item.text!r}" + (f" on {item.layer}" if item.layer else "")
    if isinstance(item, Designator):
        return f"the designator of {item.ref}"
    if isinstance(item, Comment):
        return f"the comment of {item.ref}"
    return f"the region on {item.layer} at {mm(item.corner)}"


# --- the document as an operation sees it ------------------------------------------------------------


class View:
    """The typed view of a ``State`` that operations select from: the origin, the nets and the components."""

    def __init__(self, state: State) -> None:
        self.state = state
        board = state.properties("Board6")[0]
        ox, oy = parse_mil(board.get("ORIGINX")), parse_mil(board.get("ORIGINY"))
        self.origin = (int(ox or 0), int(oy or 0))
        self.nets = [record.text("NAME") for record in state.properties("Nets6")]
        self.components = state.properties("Components6")

    def units(self, point: Point) -> tuple[int, int]:
        return to_units(point[0]) + self.origin[0], to_units(point[1]) + self.origin[1]

    def net_index(self, name: str | None) -> int:
        if name is None:
            return rec.NO_INDEX
        _assert(name in self.nets, f"the document holds no net {name!r}")
        return self.nets.index(name)

    def net_name(self, index: int | None) -> str | None:
        if index is None or index == rec.NO_INDEX or not 0 <= index < len(self.nets):
            return None
        return self.nets[index]

    def layer_id(self, name: str) -> int:
        for layer, text in LAYER_NAMES.items():
            if text.lower() == name.lower():
                return layer
        raise Refused("altium.edit.assertion", f"no layer is named {name!r}")

    def component(self, designator: str) -> int:
        found = [i for i, c in enumerate(self.components) if c.get("SOURCEDESIGNATOR") == designator]
        _assert(len(found) == 1, f"{len(found)} components are named {designator!r}, not one", "Components6")
        return found[0]

    def find(self, item: Item) -> tuple[str, int]:
        """The storage and position of the one record ``item`` names."""
        if isinstance(item, Component):
            return "Components6", self.component(item.designator)
        if isinstance(item, Polygon):
            found = [
                i for i, p in enumerate(self.state.properties("Polygons6")) if _polygon_name(p) == item.name
            ]
            _assert(len(found) == 1, f"{len(found)} polygons are named {item.name!r}, not one", "Polygons6")
            return "Polygons6", found[0]
        if isinstance(item, Designator | Comment):
            return "Texts6", self.component_text(item)
        storage, distance = self._distance(item)
        held = [(d, i) for i, p in enumerate(self.state.typed(storage)) if (d := distance(p)) is not None]
        if isinstance(item, Text) and not any(d <= REACH for d, _ in held):
            layer = None if item.layer is None else self.layer_id(item.layer)
            free = [
                repr(self.shown(p)) for p in self.state.typed("Texts6")
                if isinstance(p, TextRecord) and p.prefix.component is None
                and (layer is None or p.prefix.layer == layer)
            ]  # fmt: skip
            where = f" on {item.layer}" if item.layer else ""
            raise Refused(
                "altium.edit.assertion",
                f"0 records match {describe(item)}, not one; the free texts{where}: "
                + (", ".join(free[:5]) or "none"),
                "Texts6/Data",
            )
        return storage, _nearest(held, f"{describe(item)}", f"{storage}/Data")

    def shown(self, p: TextRecord) -> str:
        wide = self.state.wide()
        return wide[p.wide_index][1] if p.wide_index is not None and p.wide_index in wide else p.short_text

    def component_text(self, item: Designator | Comment) -> int:
        """The position in ``Texts6`` of the one long text of the component whose designator or comment
        byte is set (change c0497, D2)."""
        index = self.component(item.ref)
        owned = [
            (i, self.state.typed("Texts6")[i])
            for i in component_primitives(self.state, index).get("Texts6", [])
        ]
        texts = [(i, p) for i, p in owned if isinstance(p, TextRecord)]
        if any(p.is_designator is None for _, p in texts):
            raise Refused("altium.edit.no-template", f"a text of {item.ref} is of the short form, which does "
                          "not say whether it is the designator or the comment", "Texts6/Data")  # fmt: skip
        found = [i for i, p in texts if (p.is_designator if isinstance(item, Designator) else p.is_comment)]
        _assert(
            len(found) == 1, f"{item.ref} holds {len(found)} such texts, not one: {describe(item)}", "Texts6"
        )
        return found[0]

    def _distance(self, item: Item) -> tuple[str, Callable[[Primitive], float | None]]:
        """The storage of ``item`` and the distance of a record from what ``item`` states, in units, or
        ``None`` for a record of another kind, net, layer, width or text."""
        if isinstance(item, Track):
            a, b = self.units(item.start), self.units(item.end)
            layer = None if item.layer is None else self.layer_id(item.layer)
            net, width = self.net_index(item.net), _width(item.width)

            def track(p: Primitive) -> float | None:
                if not isinstance(p, TrackRecord) or _net(p.prefix.net) != net:
                    return None
                if (layer is not None and p.prefix.layer != layer) or not _same(p.width, width):
                    return None
                ends = ((p.x1, p.y1), (p.x2, p.y2))
                return min(max(_gap(ends[0], a), _gap(ends[1], b)), max(_gap(ends[0], b), _gap(ends[1], a)))

            return "Tracks6", track
        if isinstance(item, Arc):
            centre, radius = self.units(item.centre), to_units(item.radius)
            layer = None if item.layer is None else self.layer_id(item.layer)
            net, width = self.net_index(item.net), _width(item.width)

            def arc(p: Primitive) -> float | None:
                if not isinstance(p, ArcRecord) or not _free(p) or _net(p.prefix.net) != net:
                    return None
                if (layer is not None and p.prefix.layer != layer) or not _same(p.width, width):
                    return None
                return max(_gap((p.cx, p.cy), centre), abs(p.radius - radius))

            return "Arcs6", arc
        if isinstance(item, Fill):
            box = _corners(self.units(item.corner), self.units(item.opposite))
            layer, net = self.layer_id(item.layer), self.net_index(item.net)

            def fill(p: Primitive) -> float | None:
                if not isinstance(p, FillRecord) or not _free(p) or p.prefix.layer != layer:
                    return None
                if _net(p.prefix.net) != net:
                    return None
                held = _corners((p.x1, p.y1), (p.x2, p.y2))
                return max(abs(u - v) for u, v in zip(held, box, strict=True))

            return "Fills6", fill
        if isinstance(item, Via):
            at, net = self.units(item.at), self.net_index(item.net)
            return (
                "Vias6",
                lambda p: (
                    _gap((p.x, p.y), at) if isinstance(p, ViaRecord) and _net(p.prefix.net) == net else None
                ),
            )
        if isinstance(item, Text):
            wide = {index: text for index, (_, text) in self.state.wide().items()}
            layer = None if item.layer is None else self.layer_id(item.layer)
            at = None if item.at is None else self.units(item.at)

            def text(p: Primitive) -> float | None:
                if not isinstance(p, TextRecord) or p.prefix.component is not None:
                    return None
                if layer is not None and p.prefix.layer != layer:
                    return None
                shown = wide.get(p.wide_index, p.short_text) if p.wide_index is not None else p.short_text
                if shown != item.text:
                    return None
                return 0 if at is None else _gap((p.x, p.y), at)

            return "Texts6", text
        if isinstance(item, Region):
            layer, corner = self.layer_id(item.layer), self.units(item.corner)
            return "Regions6", lambda p: _free_region(p, layer, corner)
        raise TypeError(f"{type(item).__name__} is not an item")


def _nearest(held: list[tuple[float, int]], what: str, where: str) -> int:
    """The position of the nearest record within ``REACH``; a second one within ``TOLERANCE`` of its
    distance, or none, refuses (change c0452, Decision 2)."""
    near = sorted((d, i) for d, i in held if d <= REACH)
    _assert(bool(near), f"0 records match {what}, not one", where)
    ties = [i for d, i in near if d - near[0][0] <= TOLERANCE]
    _assert(len(ties) == 1, f"{len(ties)} records match {what}, not one", where)
    return ties[0]


def _polygon_name(record: PropertyRecord) -> str:
    from fenolite.backends.altium.read.pcb import decode_name

    return decode_name(record.text("NAME"))


def _net(index: int | None) -> int:
    return rec.NO_INDEX if index is None else index


def _gap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _width(width: int | None) -> int | None:
    return None if width is None else to_units(width)


def _same(held: int, stated: int | None) -> bool:
    return stated is None or abs(held - stated) <= TOLERANCE


def _free(p: ArcRecord | FillRecord) -> bool:
    return p.prefix.polygon is None and p.prefix.component is None


def _corners(a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int, int, int]:
    return min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])


def _free_region(p: Primitive, layer: int, corner: tuple[int, int]) -> float | None:
    if not isinstance(p, RegionRecord) or p.prefix.polygon is not None or p.prefix.component is not None:
        return None
    if p.prefix.layer != layer or not p.outline:
        return None
    return _gap((min(v.x for v in p.outline), min(v.y for v in p.outline)), corner)


def _twins(state: State, raw: bytes) -> list[int]:
    """The record of ``ShapeBasedRegions6`` that stands for the region ``raw`` of ``Regions6`` (phase A,
    J14: both change together): of those with the same layer, polygon, component and property text, the
    one whose box is nearest within ``REACH`` (change c0452, Decision 2); none when no record is. Read before
    ``raw`` changes."""
    found = [p for p in state.typed("Regions6") if p.raw == raw]
    _assert(bool(found), "the region is not held by Regions6", "Regions6/Data")
    region = found[0]
    assert isinstance(region, RegionRecord)
    box = _box(region)
    held: list[tuple[float, int]] = []
    if not state.has("ShapeBasedRegions6"):
        return []
    for position, other in enumerate(state.typed("ShapeBasedRegions6")):
        if (
            isinstance(other, RegionRecord)
            and other.prefix.layer == region.prefix.layer
            and other.prefix.polygon == region.prefix.polygon
            and other.prefix.component == region.prefix.component
            and other.properties.fields == region.properties.fields
        ):
            distance = max(abs(u - v) for u, v in zip(_box(other), box, strict=True))
            if distance <= REACH:
                held.append((distance, position))
    return [min(held)[1]] if held else []


def _box(region: RegionRecord) -> tuple[float, float, float, float]:
    xs = [float(v.x) for v in region.outline]
    ys = [float(v.y) for v in region.outline]
    return min(xs), min(ys), max(xs), max(ys)


# --- unique ids --------------------------------------------------------------------------------------


def held_ids(state: State) -> set[str]:
    """Every unique id the document holds, upper-case."""
    out: set[str] = set()
    for storage in ("UniqueIDPrimitiveInformation", "Components6", "Polygons6", "Rules6", "Classes6"):
        if state.has(storage):
            out |= {(r.get("UNIQUEID") or "").upper() for r in state.properties(storage)}
    return out - {""}


def new_id(taken: set[str]) -> str:
    """Eight upper-case letters from ``secrets``, unique in ``taken``, which it joins."""
    while True:
        value = "".join(secrets.choice(ID_LETTERS) for _ in range(ID_LENGTH))
        if value not in taken:
            taken.add(value)
            return value


# --- shared edits ------------------------------------------------------------------------------------


def _expect(name: str, held: object, stated: object, where: str) -> None:
    _assert(held == stated, f"{name} is {held}, not the stated {stated}", where)


def _length_text(units: int) -> str:
    return f"{units * 127 / 50 / 1e6:.4f}".rstrip("0").rstrip(".") + " mm"


def check_expect(view: View, storage: str, position: int, expect: Mapping[str, object]) -> None:
    """The stated old values of a track, an arc, a fill or a via: ``width``, ``diameter`` (nm), ``rotation``
    (degrees), ``layer`` (a name)."""
    item = view.state.typed(storage)[position]
    where = f"{storage}/Data#{position}"
    for key, value in expect.items():
        if key == "layer" and not isinstance(item, RawPrimitive):
            _expect("the layer", LAYER_NAMES.get(item.prefix.layer), value, where)
        elif key == "width" and isinstance(item, TrackRecord | ArcRecord):
            stated = to_units(int(value))  # type: ignore[arg-type]
            _assert(
                abs(item.width - stated) <= TOLERANCE,
                f"the width is {_length_text(item.width)}, not the stated {_length_text(stated)}",
                where,
            )
        elif key == "rotation" and isinstance(item, FillRecord):
            _assert(
                math.isclose(item.rotation % 360, float(value) % 360, abs_tol=1e-6),  # type: ignore[arg-type]
                f"the rotation is {item.rotation:g}°, not the stated {value}°",
                where,
            )
        elif key == "diameter" and isinstance(item, ViaRecord):
            stated = to_units(int(value))  # type: ignore[arg-type]
            _assert(
                abs(item.diameter - stated) <= TOLERANCE,
                f"the diameter is {_length_text(item.diameter)}, not the stated {_length_text(stated)}",
                where,
            )
        else:
            raise Refused("altium.edit.assertion", f"{key!r} is not a field of {storage} that can be stated")


def component_primitives(state: State, index: int) -> dict[str, list[int]]:
    """The positions of the primitives of component ``index`` in each storage that holds them."""
    out: dict[str, list[int]] = {}
    for storage in COMPONENT_STORAGES:
        if not state.has(storage):
            continue
        found = [i for i, raw in enumerate(state.get(storage)) if rec.prefix_of(raw)[3] == index]
        if found:
            out[storage] = found
    return out


def _turned(keys: Mapping[str, str], key: str, turn: float) -> dict[str, str]:
    """``{key: its angle turned by turn}``, empty when the body holds no such angle."""
    try:
        return {key: f"{(float(keys[key]) + turn) % 360:.3f}"} if key in keys else {}
    except ValueError:
        return {}


FLIPPED_TEXTURE_ROTATION = " 3.60000000000000E+0002"
"""``TEXTUREROTATION`` of a body with the value 0 after Altium's own flip to the bottom (S-2123)."""
BOTTOM_BODY_ANGLE = "0.000"
"""``MODEL.3D.ROTZ`` and ``MODEL.2D.ROTATION`` of a body after Altium's own flip to the bottom, whatever they
were on top; Altium's save writes them so on any bottom body (S-2124)."""


def _texture_zero(text: str | None) -> bool:
    try:
        return text is not None and float(text) == 0
    except ValueError:
        return False


def _body_model_keys(raw: bytes, move: rec.Transform, turn: float, flipped: bool = False) -> bytes:
    """A body with its ``MODEL.2D.X``/``Y`` moved and ``MODEL.3D.ROTZ`` turned, where it holds them. With
    ``flipped`` (a flip), ``BODYPROJECTION`` changes side. On the way down ``MODEL.3D.ROTZ`` and
    ``MODEL.2D.ROTATION`` take 0, as Altium's own flip writes them for any top value and its save does on any
    bottom body (S-2124, change c0453 task 3.3), and ``TEXTUREROTATION`` 0 takes Altium's 360 (S-2123); any
    other texture rotation is kept, as Altium keeps 90 (S-2124). On the way up the angles and the texture
    rotation are kept, as Altium keeps 0, 0 and 360 (S-2124; ``pcb-document.md``, "Frame of a bottom
    part")."""
    keys = rec.region_keys(raw)
    x, y = parse_mil(keys.get("MODEL.2D.X")), parse_mil(keys.get("MODEL.2D.Y"))
    changes: dict[str, str] = {}
    if x is not None and y is not None:
        nx, ny = move(float(x), float(y))
        changes["MODEL.2D.X"], changes["MODEL.2D.Y"] = mil_text(round(nx)), mil_text(round(ny))
    if turn:
        changes |= _turned(keys, "MODEL.3D.ROTZ", turn)
    if flipped and "BODYPROJECTION" in keys:
        down = keys["BODYPROJECTION"].strip() != "1"
        changes["BODYPROJECTION"] = "1" if down else "0"
        if down:
            changes |= {
                key: BOTTOM_BODY_ANGLE for key in ("MODEL.3D.ROTZ", "MODEL.2D.ROTATION") if key in keys
            }
        if down and _texture_zero(keys.get("TEXTUREROTATION")):
            changes["TEXTUREROTATION"] = FLIPPED_TEXTURE_ROTATION
    return rec.set_region_keys(raw, changes) if changes else raw


def move_primitives(
    state: State, index: int, move: rec.Transform, *, turn: float = 0.0, mirror: bool = False,
    layers: Mapping[int, int] | None = None, flipped: bool = False,
) -> None:  # fmt: skip
    """Every primitive of component ``index`` moved by ``move``, turned by ``turn``, mirrored, and put on
    the other layer of its pair in ``layers``, which maps long layer ids (``flip_layers``). ``flipped``: the
    move is a flip, and the bodies change side (``_body_model_keys``)."""
    for storage, positions in component_primitives(state, index).items():
        for position in positions:
            raw = state.get(storage)[position]
            new = rec.transform(raw, move, turn=turn, mirror=mirror, shape_based=storage in SHAPE_BASED)
            if storage.endswith("ComponentBodies6"):
                new = _body_model_keys(new, move, turn, flipped)
            if layers:
                held = layer_of(new)
                if held is not None and held in layers:
                    new = relayer_long(new, layers[held], strict=False)
            if new[0] == PAD and mirror:
                new = _swap_pad_sides(new)
            state.replace(storage, position, new)


def _swap_pad_sides(raw: bytes) -> bytes:
    """A pad with its top and bottom sizes and shapes exchanged (a flipped pad of a top-bottom stack)."""
    top = rec.unpack(raw, 21, "<2i")
    bottom = rec.unpack(raw, 37, "<2i")
    shapes = rec.unpack(raw, 49, "<3B")
    raw = rec.patch(raw, 21, "<2i", *bottom)
    raw = rec.patch(raw, 37, "<2i", *top)
    return rec.patch(raw, 49, "<3B", shapes[2], shapes[1], shapes[0])


def rotation_text(degrees: float) -> str:
    """A ``ROTATION`` value in the form saved files hold: `` 9.00000000000000E+0001``."""
    if degrees == 0:
        return " 0.00000000000000E+0000"
    exponent = math.floor(math.log10(abs(degrees)))
    mantissa = degrees / 10**exponent
    sign = "-" if exponent < 0 else "+"
    return f"{'-' if mantissa < 0 else ' '}{abs(mantissa):.14f}E{sign}{abs(exponent):04d}"


def _component_xy(record: PropertyRecord) -> tuple[Fraction, Fraction]:
    x, y = parse_mil(record.get("X")), parse_mil(record.get("Y"))
    _assert(x is not None and y is not None, "the component record holds no X and Y")
    assert x is not None and y is not None
    return x, y


# --- operations --------------------------------------------------------------------------------------


def delete(state: State, item: Item) -> None:
    view = View(state)
    storage, position = view.find(item)
    if isinstance(item, Component):
        _delete_component(state, position)
    elif isinstance(item, Polygon):
        _delete_polygon(state, position)
    elif isinstance(item, Region):
        twins = _twins(state, state.get(storage)[position])
        state.remove(storage, {position})
        if twins:
            state.remove("ShapeBasedRegions6", {twins[0]})
    elif isinstance(item, Text):
        text = state.typed(storage)[position]
        state.remove(storage, {position})
        if isinstance(text, TextRecord) and text.wide_index is not None:
            _drop_wide(state, {text.wide_index})
    else:
        state.remove(storage, {position})


def _drop_wide(state: State, indices: set[int]) -> None:
    held = state.wide()
    state.remove(WIDE, {held[i][0] for i in indices if i in held})


def _delete_component(state: State, index: int) -> None:
    """The component, its primitives, their wide strings and unique-id entries go; every component index
    above it and every pad position after a removed pad is renumbered (``H-A-EDIT-DELETE``)."""
    owned = component_primitives(state, index)
    removed_pads = set(owned.get("Pads6", []))
    texts = [state.typed("Texts6")[i] for i in owned.get("Texts6", [])]
    wide = {t.wide_index for t in texts if isinstance(t, TextRecord) and t.wide_index is not None}
    for storage, positions in owned.items():
        state.remove(storage, set(positions))
    _drop_wide(state, wide)
    state.remove("Components6", {index})
    for storage in COMPONENT_STORAGES:
        if not state.has(storage):
            continue
        for position, raw in enumerate(state.get(storage)):
            owner = rec.prefix_of(raw)[3]
            if owner != rec.NO_INDEX and owner > index:
                state.replace(storage, position, rec.set_prefix(raw, component=owner - 1))
    _renumber_pad_entries(state, removed_pads)


def _renumber_pad_entries(state: State, removed: set[int]) -> None:
    """The entries of ``UniqueIDPrimitiveInformation`` of removed pads go; each later pad's entry gets its
    new position."""
    if not removed or not state.has("UniqueIDPrimitiveInformation"):
        return
    entries = state.properties("UniqueIDPrimitiveInformation")
    drop: set[int] = set()
    for position, entry in enumerate(entries):
        index = entry.get("PRIMITIVEINDEX") or ""
        if (entry.get("PRIMITIVEOBJECTID") or "").upper() != "PAD" or not index.isdigit():
            continue
        pad = int(index)
        if pad in removed:
            drop.add(position)
            continue
        shift = sum(1 for r in removed if r < pad)
        if shift:
            raw = rec.set_property(entry.raw, {"PRIMITIVEINDEX": str(pad - shift)})
            state.replace("UniqueIDPrimitiveInformation", position, raw)
    state.remove("UniqueIDPrimitiveInformation", drop)


def _delete_polygon(state: State, index: int) -> None:
    """The polygon and its poured primitives go; every polygon index above it is renumbered, and the pour
    indices of the others are numbered from 0 in their order (``H-A-EDIT-DELETE``,
    ``H-A-INTEG-POURINDEX``)."""
    for storage in PRIMITIVE_STORAGES:
        if not state.has(storage) or storage.endswith("ComponentBodies6"):
            continue
        poured = {i for i, raw in enumerate(state.get(storage)) if rec.prefix_of(raw)[2] == index}
        state.remove(storage, poured)
        for position, raw in enumerate(state.get(storage)):
            polygon = rec.prefix_of(raw)[2]
            if polygon not in (rec.NO_INDEX, 0xFFFE) and polygon > index:
                state.replace(storage, position, rec.set_prefix(raw, polygon=polygon - 1))
    state.remove("Polygons6", {index})
    polygons = state.properties("Polygons6")
    order = sorted(range(len(polygons)), key=lambda i: int(polygons[i].get("POURINDEX") or 0))
    for number, position in enumerate(order):
        if (polygons[position].get("POURINDEX") or "") != str(number):
            state.replace(
                "Polygons6", position, rec.set_property(polygons[position].raw, {"POURINDEX": str(number)})
            )


def move(state: State, item: Item, dx: int, dy: int, expect: Mapping[str, object]) -> None:
    view = View(state)
    storage, position = view.find(item)
    du, dv = to_units(dx), to_units(dy)
    if isinstance(item, Component):
        record = view.components[position]
        x, y = _component_xy(record)
        for key, value in expect.items():
            _assert(key in ("x", "y"), f"{key!r} cannot be stated for a component move")
            held = (x - view.origin[0]) if key == "x" else (y - view.origin[1])
            _assert(abs(held - to_units(int(value))) <= TOLERANCE,  # type: ignore[arg-type]
                    f"the component's {key} is {_length_text(int(held))}", "Components6")  # fmt: skip
        new = rec.set_property(record.raw, {"X": mil_text(int(x) + du), "Y": mil_text(int(y) + dv)})
        state.replace("Components6", position, new)
        move_primitives(state, position, rec.shift(du, dv))
        return
    if isinstance(item, Polygon):
        _assert(not expect, "no old value can be stated for a polygon move")
        _move_polygon(state, position, du, dv)
        return
    check_expect(view, storage, position, expect)
    raw = state.get(storage)[position]
    twins = _twins(state, raw) if isinstance(item, Region) else []
    state.replace(storage, position, rec.transform(raw, rec.shift(du, dv)))
    for twin in twins:
        other = state.get("ShapeBasedRegions6")[twin]
        state.replace("ShapeBasedRegions6", twin, rec.transform(other, rec.shift(du, dv), shape_based=True))


OUTLINE_KEY = re.compile(r"(KIND|VX|VY|CX|CY|SA|EA|R)(\d+)")
"""The keys of a polygon's outline in ``Polygons6``, eight per vertex (``docboard._outline``)."""


def _outline(record: PropertyRecord) -> list[tuple[int, int, str]]:
    """The vertices of a polygon's outline in document units with their ``KIND``, the repeated last
    vertex included."""
    out: list[tuple[int, int, str]] = []
    while (x := parse_mil(record.get(f"VX{len(out)}"))) is not None:
        y = parse_mil(record.get(f"VY{len(out)}"))
        _assert(y is not None, f"the polygon's vertex {len(out)} holds no VY", "Polygons6")
        assert y is not None
        out.append((round(x), round(y), record.get(f"KIND{len(out)}") or "0"))
    return out


def _poured(state: State, index: int) -> dict[str, set[int]]:
    """The positions of the primitives poured by polygon ``index``, per storage."""
    out: dict[str, set[int]] = {}
    for storage in PRIMITIVE_STORAGES:
        if state.has(storage) and not storage.endswith("ComponentBodies6"):
            found = {i for i, raw in enumerate(state.get(storage)) if rec.prefix_of(raw)[2] == index}
            if found:
                out[storage] = found
    return out


def _move_polygon(state: State, index: int, du: int, dv: int) -> None:
    """Every vertex of the outline and the centre of every arc vertex moved, and every poured primitive
    with them (change c0452, Decision 4)."""
    record = state.properties("Polygons6")[index]
    changes: dict[str, str] = {}
    for number, (x, y, kind) in enumerate(_outline(record)):
        changes[f"VX{number}"], changes[f"VY{number}"] = mil_text(x + du), mil_text(y + dv)
        cx, cy = parse_mil(record.get(f"CX{number}")), parse_mil(record.get(f"CY{number}"))
        if kind != "0" and cx is not None and cy is not None:
            changes[f"CX{number}"], changes[f"CY{number}"] = (
                mil_text(round(cx) + du),
                mil_text(round(cy) + dv),
            )
    state.replace("Polygons6", index, rec.set_property(record.raw, changes))
    for storage, positions in _poured(state, index).items():
        for position in positions:
            raw = state.get(storage)[position]
            moved = rec.transform(raw, rec.shift(du, dv), shape_based=storage in SHAPE_BASED)
            state.replace(storage, position, moved)


def set_outline(state: State, item: Polygon, outline: list[Point], old: list[Point]) -> None:
    """The polygon ``item`` with the outline ``outline`` of line vertices in the place of its old one,
    which ``old`` states vertex by vertex, and without its poured primitives (change c0452, Decision 4)."""
    view = View(state)
    _, index = view.find(item)
    record = state.properties("Polygons6")[index]
    held = _outline(record)[:-1]
    where = f"Polygons6/Data#{index}"
    _assert(len(held) == len(old), f"{item.name} has {len(held)} vertices, not the stated {len(old)}", where)
    for number, ((x, y, _), point) in enumerate(zip(held, old, strict=True)):
        _assert(
            _gap((x, y), view.units(point)) <= REACH,
            f"vertex {number} of {item.name} is not the stated one",
            where,
        )
    state.replace("Polygons6", index, _with_outline(record.raw, [view.units(p) for p in outline]))
    for storage, positions in _poured(state, index).items():
        state.remove(storage, positions)


def _with_outline(raw: bytes, vertices: list[tuple[int, int]]) -> bytes:
    _assert(len(vertices) >= 3, "an outline needs three vertices")
    zero = angle_text(0)
    fields: list[tuple[str, str]] = []
    for number, (x, y) in enumerate((*vertices, vertices[0])):
        fields += [(f"KIND{number}", "0"), (f"VX{number}", mil_text(x)), (f"VY{number}", mil_text(y)),
                   (f"CX{number}", "0mil"), (f"CY{number}", "0mil"), (f"SA{number}", zero),
                   (f"EA{number}", zero), (f"R{number}", "0mil")]  # fmt: skip
    return rec.replace_run(raw, lambda key: OUTLINE_KEY.fullmatch(key) is not None, fields)


def rotate(state: State, item: Component, degrees: float, old_rotation: float) -> None:
    view = View(state)
    index = view.component(item.designator)
    record = view.components[index]
    held = float((record.get("ROTATION") or "0").strip())
    _assert(
        math.isclose(held % 360, old_rotation % 360, abs_tol=1e-6),
        f"the rotation of {item.designator} is {held:g}°, not the stated {old_rotation:g}°",
        "Components6",
    )
    x, y = _component_xy(record)
    new = (held + degrees) % 360
    state.replace("Components6", index, rec.set_property(record.raw, {"ROTATION": rotation_text(new)}))
    move_primitives(state, index, rec.quarter_turn(float(x), float(y), degrees), turn=degrees)


def flip(state: State, item: Component, old_side: str) -> None:
    view = View(state)
    index = view.component(item.designator)
    record = view.components[index]
    side = (record.get("LAYER") or "").upper()
    _expect(f"the side of {item.designator}", side, old_side.upper(), "Components6")
    x, _y = _component_xy(record)
    held = float((record.get("ROTATION") or "0").strip())
    # The mirror in X about the origin is Altium's frame of the other side, the footprint mirrored in Y and
    # turned by 180 - R (change c0453, ``pcb-document.md``, "Frame of a bottom part").
    rotation = (180.0 - held) % 360
    changes = {"LAYER": "BOTTOM" if side == "TOP" else "TOP", "ROTATION": rotation_text(rotation)}
    state.replace("Components6", index, rec.set_property(record.raw, changes))
    mirror = rec.mirror_x(float(x))
    move_primitives(state, index, mirror, mirror=True, layers=flip_layers(state), flipped=True)


MECHPAIR_KEY = re.compile(r"MECHPAIR(\d+)L([12])")
MECHANICAL_NAME = re.compile(r"MECHANICAL(\d+)")


def mechanical_pairs(state: State) -> tuple[tuple[int, int], ...]:
    """The mechanical layer pairs the board declares, by layer number: each ``MECHPAIR<i>L1`` and
    ``MECHPAIR<i>L2`` of ``Board6`` that names ``MECHANICAL<n>`` (``pcb-document.md``, "Mechanical layer
    pairs"). A board without those keys pairs no mechanical layer."""
    named: dict[str, dict[str, int]] = {}
    for key, value in state.properties("Board6")[0].fields:
        found, layer = MECHPAIR_KEY.fullmatch(key.upper()), MECHANICAL_NAME.fullmatch(value.strip().upper())
        if found is not None and layer is not None:
            named.setdefault(found.group(1), {})[found.group(2)] = int(layer.group(1))
    return tuple(
        (pair["1"], pair["2"])
        for _, pair in sorted(named.items(), key=lambda item: int(item[0]))
        if "1" in pair and "2" in pair and pair["1"] != pair["2"]
    )


def flip_layers(state: State) -> dict[int, int]:
    """The other-side layer of each layer a flip moves, by long layer id: the top and bottom copper, overlay
    and the rest of ``FLIP_PAIRS`` that is not mechanical, Multi-Layer onto itself, and the mechanical pairs
    the board declares (``mechanical_pairs``). A mechanical layer of no declared pair stays where it is, as
    Altium Designer's own flip leaves it (S-1892, case J9)."""
    layers = {
        long_id(a): long_id(b) for a, b in FLIP_PAIRS.items() if not MECHANICAL_FIRST <= a <= MECHANICAL_LAST
    }
    for a, b in mechanical_pairs(state):
        layers[MECHANICAL_LONG + a] = MECHANICAL_LONG + b
        layers[MECHANICAL_LONG + b] = MECHANICAL_LONG + a
    return layers


def set_property(state: State, item: Item, key: str, value: object, old: object) -> None:
    view = View(state)
    storage, position = view.find(item)
    where = f"{storage}/Data#{position}"
    if isinstance(item, Component) and key.lower() == "comment":
        owned = component_primitives(state, position).get("Texts6", [])
        comments = [
            t for i in owned if isinstance(t := state.typed("Texts6")[i], TextRecord) and t.is_comment
        ]
        _assert(len(comments) == 1, f"{item.designator} holds {len(comments)} comment texts, not one", where)
        _set_wide(state, comments[0], str(value), str(old), short=False)
        return
    if isinstance(item, Text) and key.lower() == "text":
        text = state.typed(storage)[position]
        assert isinstance(text, TextRecord)
        _set_wide(state, text, str(value), str(old), short=True, position=position)
        return
    if isinstance(item, Component | Polygon):
        record = (view.components if storage == "Components6" else state.properties(storage))[position]
        held = record.get(key)
        _assert(held is not None, f"the record holds no key {key!r}", where)
        _expect(key, held, str(old), where)
        state.replace(storage, position, rec.set_property(record.raw, {key: str(value)}))
        return
    fields: dict[tuple[type, str], int] = {(Track, "width"): 29, (Arc, "width"): 41, (Via, "diameter"): 21}
    offset = fields.get((type(item), key))
    _assert(offset is not None, f"{key!r} is not a property a session sets on {describe(item)}", where)
    assert offset is not None
    check_expect(view, storage, position, {key: old})
    raw = state.get(storage)[position]
    state.replace(storage, position, rec.patch(raw, offset, "<i", to_units(int(value))))  # type: ignore[arg-type]


def _set_wide(
    state: State, text: TextRecord, value: str, old: str, *, short: bool, position: int = -1
) -> None:
    held = state.wide()
    index = text.wide_index
    _assert(index is not None and index in held, "the text has no wide-string entry", "WideStrings6")
    assert index is not None
    entry, shown = held[index]
    _expect("the text", shown, old, f"WideStrings6/Data#{entry}")
    state.replace(WIDE, entry, rec.wide_entry(index, value))
    if short and position >= 0:
        state.replace("Texts6", position, rec.set_text_string(text.raw, value))


def _template(state: State, storage: str, kind: int, layer: int) -> bytes:
    for raw in state.get(storage):
        if raw[0] == kind and rec.prefix_of(raw)[0] == layer:
            return raw
    raise Refused(
        "altium.edit.no-template",
        f"the document holds no {KIND_NAMES.get(kind, str(kind))} on {LAYER_NAMES.get(layer, layer)} to copy",
        f"{storage}/Data",
    )


def clone(state: State, item: Item, changes: Mapping[str, object]) -> None:
    """A new track, via or free text: a copy of ``item``, or, when ``layer`` changes, of a record of the
    same kind on that layer, with ``item``'s geometry and the stated changes (``H-A-EDIT-CLONE``)."""
    view = View(state)
    storage, position = view.find(item)
    _assert(isinstance(item, Track | Via | Text), f"{describe(item)} is not cloned by a session")
    source = state.typed(storage)[position]
    assert not isinstance(source, RawPrimitive)
    allowed = {
        Track: {"start", "end", "net", "layer", "width"},
        Via: {"at", "net"},
        Text: {"at", "text", "layer"},
    }
    unknown = set(changes) - allowed[type(item)]  # pyright: ignore[reportArgumentType]
    _assert(not unknown, f"{', '.join(sorted(unknown))} cannot be changed by a clone of {describe(item)}")
    layer = view.layer_id(str(changes["layer"])) if "layer" in changes else source.prefix.layer
    raw = source.raw
    if layer != source.prefix.layer:
        template = _template(state, storage, primitive_type(source), layer)
        raw = _carry(template, source)
    raw = rec.set_prefix(raw, layer=layer, polygon=rec.NO_INDEX, component=rec.NO_INDEX)
    if "net" in changes:
        raw = rec.set_prefix(raw, net=view.net_index(changes["net"]))  # type: ignore[arg-type]
    if isinstance(source, TrackRecord):
        start = view.units(changes["start"]) if "start" in changes else (source.x1, source.y1)  # type: ignore[arg-type]
        end = view.units(changes["end"]) if "end" in changes else (source.x2, source.y2)  # type: ignore[arg-type]
        raw = rec.patch(raw, 13, "<4i", *start, *end)
        width = to_units(int(changes["width"])) if "width" in changes else source.width  # type: ignore[arg-type]
        raw = rec.patch(raw, 29, "<i", width)
    elif isinstance(source, ViaRecord) and "at" in changes:
        raw = rec.patch(raw, 13, "<2i", *view.units(changes["at"]))  # type: ignore[arg-type]
    elif isinstance(source, TextRecord):
        if "at" in changes:
            raw = rec.patch(raw, 13, "<2i", *view.units(changes["at"]))  # type: ignore[arg-type]
        shown = str(changes.get("text", item.text if isinstance(item, Text) else source.text))
        if source.wide_index is not None:
            index = max(state.wide(), default=-1) + 1
            state.append(WIDE, rec.wide_entry(index, shown))
            raw = rec.set_wide_index(raw, index)
        raw = rec.set_text_string(raw, shown)
    state.append(storage, raw)


KEEPOUT_FLAG = 2
"""The second flag byte of a keep-out (``pcb-records.md``, "Regions and keep-outs"): no template of a new
record is one."""


def _shape_template(state: State, storage: str, kind: int, layer: int) -> bytes:
    """The first record of ``kind`` on ``layer`` that is no keep-out and, for a region, a free region of
    ``KIND=0`` that is no board cut-out: the template of a new shape (change c0452, Decision 5)."""
    for raw in state.get(storage) if state.has(storage) else []:
        if raw[0] != kind or rec.prefix_of(raw)[0] != layer or rec.split(raw)[1][0][2] == KEEPOUT_FLAG:
            continue
        if kind == REGION:
            keys = rec.region_keys(raw)
            free = rec.prefix_of(raw)[2:] == (rec.NO_INDEX, rec.NO_INDEX)
            if not free or keys.get("KIND", "0") != "0" or keys.get("ISBOARDCUTOUT") == "TRUE":
                continue
        return raw
    raise Refused(
        "altium.edit.no-template",
        f"the document holds no {KIND_NAMES.get(kind, str(kind))} on {LAYER_NAMES.get(layer, layer)} to copy",
        f"{storage}/Data",
    )


def _new_shape(raw: bytes, layer: int, net: int) -> bytes:
    return rec.set_prefix(raw, layer=layer, net=net, polygon=rec.NO_INDEX, component=rec.NO_INDEX)


def add_arc(
    state: State, centre: Point, radius: int, angles: tuple[float, float], *, width: int, layer: str,
    net: str | None,
) -> None:  # fmt: skip
    """A free arc cloned from an arc on ``layer``: centre, radius, start and end angles (degrees,
    anticlockwise from the start) and width; no sub-polygon."""
    view = View(state)
    at, number = view.units(centre), view.layer_id(layer)
    _assert(radius > 0 and width > 0, "an arc needs a radius and a width above zero")
    raw = _new_shape(_shape_template(state, "Arcs6", ARC, number), number, view.net_index(net))
    raw = rec.patch(raw, 13, "<3i", *at, to_units(radius))
    raw = rec.patch(raw, 25, "<2d", angles[0] % 360.0, angles[1] % 360.0)
    raw = rec.patch(raw, 41, "<i", to_units(width))
    if len(rec.split(raw)[1][0]) >= 47:
        raw = rec.patch(raw, 45, "<H", 0)
    state.append("Arcs6", raw)


def add_fill(
    state: State, corner: Point, opposite: Point, *, layer: str, net: str | None, rotation: float
) -> None:
    """A free fill cloned from a fill on ``layer``: its two corners, lower-left first, and its rotation;
    the template's bytes after the rotation are kept (no row records what they hold)."""
    view = View(state)
    number = view.layer_id(layer)
    box = _corners(view.units(corner), view.units(opposite))
    _assert(box[0] < box[2] and box[1] < box[3], "a fill needs a width and a height above zero")
    raw = _new_shape(_shape_template(state, "Fills6", FILL, number), number, view.net_index(net))
    raw = rec.patch(raw, 13, "<4i", *box)
    raw = rec.patch(raw, 29, "<d", rotation % 360.0)
    state.append("Fills6", raw)


def add_region(state: State, outline: list[Point], *, layer: str, net: str | None) -> None:
    """A free region cloned from a free region on ``layer`` with the outline ``outline`` and no hole, in
    ``Regions6`` and, when the template has a twin, in ``ShapeBasedRegions6``."""
    view = View(state)
    number = view.layer_id(layer)
    _assert(len(outline) >= 3, "a region needs three vertices")
    vertices = [view.units(p) for p in outline]
    template = _shape_template(state, "Regions6", REGION, number)
    twins = _twins(state, template)
    index = view.net_index(net)
    state.append(
        "Regions6", _new_shape(rec.region_outline(template, vertices, shape_based=False), number, index)
    )
    for twin in twins:
        other = state.get("ShapeBasedRegions6")[twin]
        shaped = rec.region_outline(other, vertices, shape_based=True)
        state.append("ShapeBasedRegions6", _new_shape(shaped, number, index))


def add_polygon(state: State, name: str, outline: list[Point], *, layer: str, net: str) -> None:
    """A polygon cloned from the first record of ``Polygons6``, with no pour (change c0452, Decision 4)."""
    view = View(state)
    number = view.layer_id(layer)
    _assert(1 <= number <= 32, f"a polygon lies on a signal layer, not on {layer}")
    polygons = state.properties("Polygons6") if state.has("Polygons6") else []
    if not polygons:
        raise Refused("altium.edit.no-template", "the document holds no polygon to copy", "Polygons6/Data")
    _assert(name not in [_polygon_name(p) for p in polygons], f"the document holds a polygon {name!r}")
    template = polygons[0]
    pour = max((int(p.get("POURINDEX") or 0) for p in polygons), default=-1) + 1
    changes = {"NAME": name_codes(name), "LAYER": v7_layer(number), "NET": str(view.net_index(net)),
               "POURINDEX": str(pour)}  # fmt: skip
    if template.get("UNIQUEID") is not None:
        changes["UNIQUEID"] = new_id(held_ids(state))
    raw = rec.set_property(template.raw, changes)
    state.append("Polygons6", _with_outline(raw, [view.units(p) for p in outline]))


def _carry(template: bytes, source: Primitive) -> bytes:
    """The template's record with the source's geometry fields (its form, tail and length are the
    template's)."""
    if isinstance(source, TrackRecord):
        return rec.patch(template, 13, "<5i", source.x1, source.y1, source.x2, source.y2, source.width)
    if isinstance(source, ViaRecord):
        return rec.patch(template, 13, "<4i", source.x, source.y, source.diameter, source.hole)
    if isinstance(source, TextRecord):
        return rec.patch(template, 13, "<3i", source.x, source.y, source.height)
    return template


def relayer(raw: bytes, layer: int, *, strict: bool = True) -> bytes:
    """``raw`` on ``layer``: its layer byte, a region's or body's ``V7_LAYER``, and the long layer id of a
    saved long track, arc, fill, pad or text, which Altium shows the primitive on (S-1588, case J23: a track
    whose layer byte alone was changed stayed on its old layer; S-1890, case J9: a flipped component's
    designator and comment whose layer byte alone was changed stayed on Top Overlay). A form whose long
    layer id no row records (``rec.long_layer_offset``) raises ``RecordError`` when ``strict``, else keeps
    its other bytes."""
    moved = rec.set_prefix(raw, layer=layer)
    if moved[0] in (REGION, rec.BODY):
        moved = rec.set_region_keys(moved, {"V7_LAYER": v7_layer(layer)})
    try:
        offset = rec.long_layer_offset(moved)
    except rec.RecordError:
        if strict:
            raise
        return moved
    return moved if offset is None else rec.patch(moved, offset, "<I", long_id(layer))


MECHANICAL_FIRST, MECHANICAL_LAST = 57, 72
"""The layer bytes of Mechanical 1 to 16; Mechanical 17 to 32 hold 72 and only their long layer id."""
MECHANICAL_LONG = long_id(MECHANICAL_FIRST) - 1
"""The long layer id of Mechanical ``n`` is this plus ``n`` (``pcb-library.md``, "Long layer ids")."""


def _byte_of(long: int) -> int | None:
    """The layer byte of the long layer id ``long``: Mechanical 17 to 32 take 72 (S-1654)."""
    if MECHANICAL_LONG < long <= MECHANICAL_LONG + 32:
        return min(MECHANICAL_FIRST - 1 + long - MECHANICAL_LONG, MECHANICAL_LAST)
    return _BYTES.get(long)


def _long_ids() -> dict[int, int]:
    found: dict[int, int] = {}
    for layer in range(1, 83):
        try:
            found[long_id(layer)] = layer
        except ValueError:
            continue
    return found


_BYTES = _long_ids()


def layer_of(raw: bytes) -> int | None:
    """The long layer id of the layer ``raw`` lies on: the id its form holds, else that of its layer byte;
    ``None`` for a byte without a long id or a form no row records."""
    try:
        offset = rec.long_layer_offset(raw)
    except rec.RecordError:
        offset = None
    if offset is not None:
        (value,) = rec.unpack(raw, offset, "<I")
        assert isinstance(value, int)
        return value
    try:
        return long_id(rec.prefix_of(raw)[0])
    except ValueError:
        return None


def relayer_long(raw: bytes, long: int, *, strict: bool = True) -> bytes:
    """``raw`` on the layer of the long layer id ``long``: ``relayer`` onto its layer byte, then, for
    Mechanical 17 to 32, the long id and a region's or body's ``V7_LAYER`` of that layer itself. A form
    that holds neither cannot name Mechanical 17 to 32: ``RecordError`` when ``strict``, else ``raw``
    unchanged."""
    layer = _byte_of(long)
    if layer is None:
        raise rec.RecordError(f"the long layer id {long:#x} has no layer byte")
    moved = relayer(raw, layer, strict=strict)
    if long == long_id(layer):
        return moved
    if moved[0] in (REGION, rec.BODY):
        moved = rec.set_region_keys(moved, {"V7_LAYER": f"MECHANICAL{long - MECHANICAL_LONG}"})
    try:
        offset = rec.long_layer_offset(moved)
    except rec.RecordError:
        offset = None
    if offset is not None:
        return rec.patch(moved, offset, "<I", long)
    if moved[0] in (REGION, rec.BODY):
        return moved
    if strict:
        raise rec.RecordError(
            f"a type {raw[0]} record of this form cannot lie on Mechanical {long - MECHANICAL_LONG}"
        )
    return raw


def on_layer(raw: bytes, layer: int) -> bool:
    """Whether ``raw`` lies on ``layer``: by its long layer id when its form holds one, else by its layer
    byte. A saved long track, arc or fill on Mechanical 17 to 32 holds the layer byte of Mechanical 16 (72),
    and only its long layer id names its layer (``pcb-records.md``, S-1654)."""
    try:
        offset = rec.long_layer_offset(raw)
    except rec.RecordError:
        offset = None
    if offset is None:
        return rec.prefix_of(raw)[0] == layer
    return rec.unpack(raw, offset, "<I") == (long_id(layer),)


def remap_layer(state: State, old: str, new: str) -> None:
    """Every primitive on the layer ``old`` (``on_layer``) moves to ``new``: its layer byte, a region's or
    body's ``V7_LAYER`` and a long track's, arc's, fill's or text's long layer id together (``relayer``,
    ``H-A-EDIT-LAYER``). Copper layers are not remapped: a polygon's pour and the pads' stacks would need a
    change of their own."""
    view = View(state)
    a, b = view.layer_id(old), view.layer_id(new)
    _assert(
        a > 32 and b > 32 and b not in (74, 56),
        f"{old} and {new}: only layers that are not copper are remapped",
    )
    count = 0
    for storage in PRIMITIVE_STORAGES:
        if not state.has(storage):
            continue
        for position, raw in enumerate(state.get(storage)):
            if not on_layer(raw, a):
                continue
            try:
                moved = relayer(raw, b)
            except rec.RecordError as error:
                raise Refused("altium.edit.assertion", str(error), f"{storage}#{position}") from error
            state.replace(storage, position, moved)
            count += 1
    _assert(count > 0, f"no primitive lies on {old}")


PAIRED_RULE_KEYS: Mapping[str, str] = {"GAP": "GENERICCLEARANCE", "GENERICCLEARANCE": "GAP"}
"""Keys that a saved rule holds equal and that change together: a Clearance's or Board Outline Clearance's
``GAP`` and ``GENERICCLEARANCE`` (``pcb-copper.md``, "Rules"; ``rule-file.md``). Altium Designer shows the
gap from ``GENERICCLEARANCE`` and saves ``GAP`` back from it (S-1588, case J23)."""


def _same_value(held: str, old: str) -> bool:
    return held == old or (parse_mil(held) is not None and parse_mil(held) == parse_mil(old))


def set_rule(state: State, name: str, key: str, value: str, old: str) -> None:
    """The key ``key`` of the rule ``name`` set from ``old`` to ``value`` (``H-A-EDIT-RULE``), with its paired
    key of ``PAIRED_RULE_KEYS`` when the rule holds it, which must hold ``old`` too."""
    rules = state.properties("Rules6")
    found = [i for i, r in enumerate(rules) if r.get("NAME") == name]
    _assert(len(found) == 1, f"{len(found)} rules are named {name!r}, not one", "Rules6")
    record = rules[found[0]]
    where = f"Rules6/Data#{found[0]}"
    held = record.get(key)
    if held is None:
        raise Refused("altium.edit.assertion", f"the rule {name!r} holds no key {key!r}", where)
    _assert(_same_value(held, old), f"{key} of {name!r} is {held}, not the stated {old}", where)
    changes = {key: value}
    paired = PAIRED_RULE_KEYS.get(key)
    if paired is not None and (other := record.get(paired)) is not None:
        _assert(_same_value(other, old), f"{paired} of {name!r} is {other}, not {key}'s {old}", where)
        changes[paired] = value
    state.replace("Rules6", found[0], rec.set_property(record.raw, changes, lead=2))


def add_component(
    state: State, source: State, designator: str, *, new_designator: str | None, at: Point | None,
    nets: Mapping[str, str],
) -> None:  # fmt: skip
    """The component ``designator`` of ``source`` with its primitives, appended (``H-A-EDIT-ADD``): one
    record of ``Components6`` with a new ``UNIQUEID``, its primitives with the new component index, one new
    ``UniqueIDPrimitiveInformation`` entry per pad, and a new wide-string entry per text. A pad named in
    ``nets`` takes that net; the others have none. Each record must have the form of the records of its
    kind and layer that the document holds (``altium.edit.no-template`` otherwise)."""
    here, there = View(state), View(source)
    index = there.component(designator)
    name = new_designator or designator
    _assert(not [c for c in here.components if c.get("SOURCEDESIGNATOR") == name],
            f"the document holds a component {name!r} already", "Components6")  # fmt: skip
    record = there.components[index]
    x, y = _component_xy(record)
    dx, dy = (0, 0)
    if at is not None:
        target = here.units(at)
        dx, dy = target[0] - int(x), target[1] - int(y)
    taken = held_ids(state)
    new_index = len(here.components)
    changes = {"UNIQUEID": new_id(taken), "SOURCEDESIGNATOR": name, "X": mil_text(int(x) + dx),
               "Y": mil_text(int(y) + dy)}  # fmt: skip
    owned = component_primitives(source, index)
    for pad in owned.get("Pads6", []):
        found = source.typed("Pads6")[pad]
        if isinstance(found, PadRecord) and found.name in nets:
            here.net_index(nets[found.name])
    for storage, positions in owned.items():
        for position in positions:
            _same_form(state, storage, source.get(storage)[position])
    _copy_models(
        state, source, [source.get("ComponentBodies6")[p] for p in owned.get("ComponentBodies6", [])]
    )
    state.append("Components6", rec.set_property(record.raw, changes))
    wide = source.wide()
    next_wide = max(state.wide(), default=-1) + 1
    for storage, positions in owned.items():
        for position in positions:
            raw = rec.set_prefix(source.get(storage)[position], component=new_index)
            raw = rec.transform(raw, rec.shift(dx, dy), shape_based=storage in SHAPE_BASED)
            item = source.typed(storage)[position]
            if storage == "Pads6" and isinstance(item, PadRecord):
                net = here.net_index(nets[item.name]) if item.name in nets else rec.NO_INDEX
                raw = rec.set_prefix(raw, net=net)
                pad = state.append("Pads6", raw)
                _add_pad_entry(state, source, position, pad, taken)
                continue
            if storage == "Texts6" and isinstance(item, TextRecord) and item.wide_index is not None:
                shown = name if item.is_designator else wide.get(item.wide_index, (0, item.text))[1]
                state.append(WIDE, rec.wide_entry(next_wide, shown))
                raw = rec.set_text_string(rec.set_wide_index(raw, next_wide), shown)
                next_wide += 1
            elif rec.prefix_of(raw)[1] != rec.NO_INDEX:
                raw = rec.set_prefix(raw, net=rec.NO_INDEX)
            state.append(storage, raw)


OUTLINE_STORAGES = frozenset(
    {"Regions6", "ShapeBasedRegions6", "ComponentBodies6", "ShapeBasedComponentBodies6"}
)
"""The storages whose first subrecord is the 18-byte head, the property text and the outline
(``pcb-bodies.md``, "Record"): its length tells nothing of the form (change c0499, D5)."""


def _outline_form(sub: bytes, storage: str) -> bytes | None:
    """The form of a region or body subrecord: the head bytes that are constants of the form (9 to 12, and for
    a body 1 to 6 and 13 to 17) and the vertex size, or ``None`` when its text length or its vertices do not
    fit the subrecord. A region's flags, net and hole count are values, not form."""
    if len(sub) < 26:
        return None
    (length,) = struct.unpack_from("<I", sub, 18)
    at = 22 + length
    if at + 4 > len(sub):
        return None
    (count,) = struct.unpack_from("<I", sub, at)
    size = 37 if storage in SHAPE_BASED else 16
    rest = len(sub) - at - 4
    body = storage.endswith("ComponentBodies6")
    fits = rest in (count * size, (count + 1) * size) if body else rest >= count * size
    if not fits:
        return None
    head = sub[1:7] + sub[9:18] if body else sub[9:13]
    return head + bytes((size,))


def _same_form(state: State, storage: str, raw: bytes) -> None:
    layer = rec.prefix_of(raw)[0]
    if storage in OUTLINE_STORAGES:
        forms = {
            _outline_form(rec.split(r)[1][0], storage)
            for r in state.get(storage)
            if r[0] == raw[0] and rec.prefix_of(r)[0] == layer
        } - {None}
        found = _outline_form(rec.split(raw)[1][0], storage)
        if found is not None and (not forms or found in forms):
            return
        raise Refused(
            "altium.edit.no-template",
            f"the {KIND_NAMES.get(raw[0], storage)} records on {LAYER_NAMES.get(layer, layer)} "
            "of the document are of another form than the source's",
            f"{storage}/Data",
        )
    lengths = {
        len(rec.split(r)[1][0]) for r in state.get(storage) if r[0] == raw[0] and rec.prefix_of(r)[0] == layer
    }
    if lengths and len(rec.split(raw)[1][0]) not in lengths:
        raise Refused(
            "altium.edit.no-template",
            f"the {KIND_NAMES.get(raw[0], storage)} records on {LAYER_NAMES.get(layer, layer)} "
            "of the document are of another form than the source's",
            f"{storage}/Data",
        )


def _model_entries(state: State) -> list[tuple[str, bytes]]:
    """The records of ``Models/Data`` as ``(ID upper-case, the record with its 32-bit length)``, in order;
    record ``n`` names the stream ``Models/<n>`` (``pcb-bodies.md``, "Embedded models and their
    placement")."""
    data = state.streams.get(f"{state.name('Models')}/Data", b"")
    out: list[tuple[str, bytes]] = []
    at = 0
    while at + 4 <= len(data):
        (size,) = struct.unpack_from("<I", data, at)
        raw = data[at : at + 4 + size]
        if len(raw) < 4 + size:
            break
        out.append((rec.keys_of(raw[4:].rstrip(b"\0")).get("ID", "").upper(), raw))
        at += 4 + size
    return out


def _copy_models(state: State, source: State, bodies: list[bytes]) -> None:
    """Append to ``Models`` the entry and stream of each model that a body of ``bodies`` names
    (``MODEL.MODELTYPE=1``) and the document lacks; a model the document holds (same ``ID``) is shared
    (change c0499, D5)."""
    wanted: list[str] = []
    for raw in bodies:
        keys = rec.region_keys(raw)
        ident = keys.get("MODELID", "").upper()
        if keys.get("MODEL.MODELTYPE", "").strip() == "1" and ident and ident not in wanted:
            wanted.append(ident)
    held = [ident for ident, _ in _model_entries(state)]
    missing = [ident for ident in wanted if ident not in held]
    if not missing:
        return
    _assert(state.has("Models"), "the document has no Models storage for the model of a body", "Models")
    entries = {ident: (n, raw) for n, (ident, raw) in enumerate(_model_entries(source))}
    name, kept = state.name("Models"), source.name("Models")
    data = state.streams[f"{name}/Data"]
    count = len(held)
    for ident in missing:
        _assert(
            ident in entries, f"the source's Models storage lacks the model {ident} a body names", "Models"
        )
        n, raw = entries[ident]
        stream = source.streams.get(f"{kept}/{n}")
        _assert(stream is not None, f"the source lacks the stream Models/{n} of the model {ident}", "Models")
        data += raw
        state.streams[f"{name}/{count}"] = stream  # type: ignore[assignment]
        count += 1
    state.streams[f"{name}/Data"] = data
    state.streams[f"{name}/Header"] = struct.pack("<I", count)
    state.touched.add(name)


def _add_pad_entry(state: State, source: State, old_pad: int, new_pad: int, taken: set[str]) -> None:
    if not source.has("UniqueIDPrimitiveInformation"):
        return
    for entry in source.properties("UniqueIDPrimitiveInformation"):
        if (entry.get("PRIMITIVEOBJECTID") or "").upper() == "PAD" and entry.get("PRIMITIVEINDEX") == str(
            old_pad
        ):
            changes = {"PRIMITIVEINDEX": str(new_pad), "UNIQUEID": new_id(taken)}
            state.append("UniqueIDPrimitiveInformation", rec.set_property(entry.raw, changes))
            return


# --- board edits (change c0497) ----------------------------------------------------------------------

AUTOPOSITION = {"designator": "NAMEAUTOPOSITION", "comment": "COMMENTAUTOPOSITION"}
"""The ``Components6`` keys of a text's position mode (``pcb-records.md``, "Edit session board fields",
S-2325): a text moved or turned by a session is written with its key left out, the mode of a text placed by
hand (``H-A-EDIT-TEXT``)."""
TEXT_BOX_AT = 124
"""The width of a text's box in a long text record (``pcb-records.md``, "Text", S-0816); 0 when not stored."""


def _manual(state: State, view: View, item: Designator | Comment) -> None:
    index = view.component(item.ref)
    record = view.components[index]
    key = AUTOPOSITION["designator" if isinstance(item, Designator) else "comment"]
    if record.get(key) is not None:
        state.replace("Components6", index, rec.replace_run(record.raw, lambda name: name == key, []))


def move_text(
    state: State, item: Designator | Comment, dx: int, dy: int, expect: Mapping[str, object]
) -> None:
    """The anchor of a component's text shifted; its position-mode key left out (design D2)."""
    _assert(not expect, "no old value can be stated for a text move")
    view = View(state)
    _, position = view.find(item)
    raw = state.get("Texts6")[position]
    x, y = rec.unpack(raw, 13, "<2i")
    state.replace("Texts6", position, rec.patch(raw, 13, "<2i", int(x) + to_units(dx), int(y) + to_units(dy)))  # type: ignore[call-overload]
    _manual(state, view, item)


def _text_box(text: TextRecord, shown: str) -> tuple[int, int]:
    body = rec.split(text.raw)[1][0]
    stored = rec.unpack(text.raw, TEXT_BOX_AT, "<i")[0] if len(body) >= TEXT_BOX_AT + 4 else 0
    width = stored if isinstance(stored, int) and stored > 0 else len(shown) * text.height
    return width, text.height


def _turned_vector(x: float, y: float, degrees: float) -> tuple[float, float]:
    return rec.quarter_turn(0.0, 0.0, degrees)(x, y)


def rotate_text(
    state: State, item: Designator | Comment, degrees: float, old_rotation: float, about: str
) -> None:
    """The text turned by ``degrees`` about its box centre (``about="centre"``) or its anchor: the anchor of
    the turned box is written, its bottom-left corner, its bottom-right one when the text is mirrored
    (design D2)."""
    _assert(about in ("centre", "anchor"), f"a text turns about its centre or its anchor, not {about!r}")
    view = View(state)
    _, position = view.find(item)
    text = state.typed("Texts6")[position]
    assert isinstance(text, TextRecord)
    where = f"Texts6/Data#{position}"
    _assert(math.isclose(text.rotation % 360, old_rotation % 360, abs_tol=1e-6),
            f"the rotation is {text.rotation:g}°, not the stated {old_rotation:g}°", where)  # fmt: skip
    new = (text.rotation + degrees) % 360
    anchor: tuple[float, float] = (text.x, text.y)
    if about == "centre":
        _assert(text.font_type != 1, 'turn a TrueType text about its anchor with about="anchor"', where)
        width, height = _text_box(text, view.shown(text))
        half = ((-width if text.mirrored else width) / 2, height / 2)
        old_half, new_half = _turned_vector(*half, text.rotation), _turned_vector(*half, new)
        anchor = (text.x + old_half[0] - new_half[0], text.y + old_half[1] - new_half[1])
    raw = rec.patch(text.raw, 13, "<2i", round(anchor[0]), round(anchor[1]))
    state.replace("Texts6", position, rec.patch(raw, 27, "<d", new))
    _manual(state, view, item)


VIA_FORM = 246
"""The shortest via subrecord that holds the back solder-mask expansion at 242."""
TENT_TOP, TENT_BOTTOM = 0x20, 0x40
"""Bits 5 and 6 of a via's first flags byte (``pcb-copper.md``, "Via", ``H-A-PCB-CU-VIATENT``)."""


def via_positions(view: View, selector: Via | Vias) -> list[int]:
    if isinstance(selector, Via):
        return [view.find(selector)[1]]
    net = None if selector.net is None else view.net_index(selector.net)
    hole, diameter = _width(selector.hole), _width(selector.diameter)
    return [
        i for i, p in enumerate(view.state.typed("Vias6"))
        if isinstance(p, ViaRecord) and (net is None or _net(p.prefix.net) == net)
        and _same(p.hole, hole) and _same(p.diameter, diameter)
    ]  # fmt: skip


def set_via_mask(
    state: State, selector: Via | Vias, *, tented_top: bool, tented_bottom: bool, expansion: int | None,
    count: int,
) -> None:  # fmt: skip
    """Bits 5 and 6 of each selected via's first flags byte, the manual mask cache state 2 at 66 when a side
    is tented or ``expansion`` (nm) is given, and the expansion at 54 and 242 (design D5)."""
    view = View(state)
    positions = via_positions(view, selector)
    what = describe(selector) if isinstance(selector, Via) else f"Vias(net={selector.net!r})"
    _assert(
        len(positions) == count, f"{what} takes {len(positions)} vias, not the stated {count}", "Vias6/Data"
    )
    for position in positions:
        raw = state.get("Vias6")[position]
        body = rec.split(raw)[1][0]
        if len(body) < VIA_FORM:
            raise Refused("altium.edit.no-template", f"the via {position} is shorter than {VIA_FORM} bytes "
                          "and holds no back solder-mask expansion", f"Vias6/Data#{position}")  # fmt: skip
        flags = body[1] & ~(TENT_TOP | TENT_BOTTOM)
        flags |= (TENT_TOP if tented_top else 0) | (TENT_BOTTOM if tented_bottom else 0)
        raw = rec.patch(raw, 1, "<B", flags)
        if tented_top or tented_bottom or expansion is not None:
            raw = rec.patch(raw, 66, "<B", 2)
        if expansion is not None:
            raw = rec.patch(rec.patch(raw, 54, "<i", to_units(expansion)), 242, "<i", to_units(expansion))
        state.replace("Vias6", position, raw)


def set_region_outline(state: State, item: Region, outline: list[Point], old: list[Point]) -> None:
    """The free region ``item`` with the ring ``outline`` (line vertices) in ``Regions6`` and its twin, its
    keys, flags, layer and net kept (design D7)."""
    view = View(state)
    storage, position = view.find(item)
    region = state.typed(storage)[position]
    assert isinstance(region, RegionRecord)
    where = f"{storage}/Data#{position}"
    held = [(round(v.x), round(v.y)) for v in region.outline]
    _assert(len(held) == len(old), f"the region has {len(held)} vertices, not the stated {len(old)}", where)
    for number, (point, stated) in enumerate(zip(held, old, strict=True)):
        _assert(
            _gap(point, view.units(stated)) <= REACH,
            f"vertex {number} of the region is not the stated one",
            where,
        )
    _assert(len(outline) >= 3, "an outline needs three vertices")
    vertices = [view.units(p) for p in outline]
    twins = _twins(state, region.raw)
    state.replace(storage, position, rec.region_outline(region.raw, vertices, shape_based=False))
    for twin in twins:
        other = state.get("ShapeBasedRegions6")[twin]
        state.replace("ShapeBasedRegions6", twin, rec.region_outline(other, vertices, shape_based=True))


def _inside(ring: list[tuple[int, int]], outline: list[tuple[int, int]]) -> bool:
    from fenolite.geometry.predicates import Location
    from fenolite.geometry.rings import ring_locations, rings_cross
    from fenolite.geometry.vector import Point as GeoPoint

    a = [GeoPoint(x, y) for x, y in ring]
    b = [GeoPoint(x, y) for x, y in outline]
    return not rings_cross(a, b) and ring_locations(a, b) == {Location.INSIDE}


def add_board_cutout(state: State, ring: list[Point], *, notch: bool) -> None:
    """A board cut-out of ``ring`` (nm, no closing vertex): a free region with ``KIND=0`` and
    ``ISBOARDCUTOUT=TRUE`` and its twin, cloned from a cut-out of the document or in the writer's form; with
    ``notch``, a ring across the outline cut out of ``Board6`` and ``BoardRegions`` instead (design D3)."""
    from fenolite.backends.altium.edit import drawing
    from fenolite.backends.altium.pcbrecords import cutout_region

    view = View(state)
    _assert(len(ring) >= 3, "a cut-out needs three vertices")
    vertices = [view.units(p) for p in ring]
    outline = drawing.outline_vertices(state)
    inside = _inside(vertices, drawing.polygonised(outline)[0])
    if not notch:
        _assert(
            inside,
            "the cut-out crosses the board outline; give notch=True to cut it out of the outline",
            "Board6",
        )
        _add_cutout_region(state, vertices, cutout_region)
        return
    _assert(not inside, "the notch lies inside the board outline; add it without notch=True", "Board6")
    try:
        kept, chorded = drawing.outline_less(outline, vertices)
    except ValueError as error:
        raise Refused("altium.edit.assertion", f"the notch: {error}", "Board6") from error
    record = state.properties("Board6")[0]
    state.replace("Board6", 0, _with_board_outline(record.raw, kept))
    if state.has("BoardRegions") and state.get("BoardRegions"):
        raw = state.get("BoardRegions")[0]
        state.replace("BoardRegions", 0, rec.region_outline(raw, chorded, shape_based=False))


def _with_board_outline(raw: bytes, vertices: list[tuple[int, int, dict[str, str] | None]]) -> bytes:
    zero = angle_text(0)
    fields: list[tuple[str, str]] = []
    for number, (x, y, arc) in enumerate((*vertices, (*vertices[0][:2], None))):
        keys = arc or {"KIND": "0", "CX": "0mil", "CY": "0mil", "SA": zero, "EA": zero, "R": "0mil"}
        fields += [(f"KIND{number}", keys["KIND"]), (f"VX{number}", mil_text(x)),
                   (f"VY{number}", mil_text(y)),
                   (f"CX{number}", keys["CX"]), (f"CY{number}", keys["CY"]), (f"SA{number}", keys["SA"]),
                   (f"EA{number}", keys["EA"]), (f"R{number}", keys["R"])]  # fmt: skip
    return rec.replace_run(raw, lambda key: OUTLINE_KEY.fullmatch(key) is not None, fields)


def _cutout_template(state: State) -> bytes | None:
    for raw in state.get("Regions6") if state.has("Regions6") else []:
        keys = rec.region_keys(raw)
        free = rec.prefix_of(raw)[2:] == (rec.NO_INDEX, rec.NO_INDEX)
        if free and keys.get("ISBOARDCUTOUT") == "TRUE" and keys.get("KIND", "0") == "0":
            return raw
    return None


def _add_cutout_region(state: State, vertices: list[tuple[int, int]], form: Callable[..., bytes]) -> None:
    template = _cutout_template(state)
    if template is None:
        state.append("Regions6", form(vertices))
        if state.has("ShapeBasedRegions6"):
            state.append("ShapeBasedRegions6", form(vertices, shape_based=True))
        return
    twins = _twins(state, template)
    state.append("Regions6", rec.region_outline(template, vertices, shape_based=False))
    for twin in twins:
        other = state.get("ShapeBasedRegions6")[twin]
        state.append("ShapeBasedRegions6", rec.region_outline(other, vertices, shape_based=True))


def add_polygon_cutout(state: State, ring: list[Point], *, layer: str) -> list[str]:
    """A free region with ``KIND=1`` on a copper layer or Multi-Layer; the pour of each polygon on that
    layer whose outline meets the ring is removed. The names of those polygons (design D4)."""
    from fenolite.backends.altium.pcbrecords import region_record
    from fenolite.geometry.polygon import Polygon as GeoPolygon
    from fenolite.geometry.polygon import polygons_intersect
    from fenolite.geometry.vector import Point as GeoPoint

    view = View(state)
    number = view.layer_id(layer)
    _assert(
        1 <= number <= 32 or number == 74,
        f"a polygon cut-out lies on a copper layer or Multi-Layer, not {layer}",
    )
    _assert(len(ring) >= 3, "a cut-out needs three vertices")
    vertices = [view.units(p) for p in ring]
    free = [raw for raw in state.get("Regions6") if rec.prefix_of(raw)[2:] == (rec.NO_INDEX, rec.NO_INDEX)]
    template = next((raw for raw in free if rec.region_keys(raw).get("KIND") == "1"), None)

    def written(points: list[tuple[int, int]], shape_based: bool = False) -> bytes:
        return region_record(number, points, shape_based=shape_based, polygon_cutout=True)

    if template is None:
        _add_cutout_region(state, vertices, written)
    else:
        twins = _twins(state, template)
        state.append("Regions6", relayer(rec.region_outline(template, vertices, shape_based=False), number))
        for twin in twins:
            other = state.get("ShapeBasedRegions6")[twin]
            state.append(
                "ShapeBasedRegions6", relayer(rec.region_outline(other, vertices, shape_based=True), number)
            )
    cut = GeoPolygon(tuple(GeoPoint(x, y) for x, y in vertices))
    stale: list[str] = []
    for index, polygon in enumerate(state.properties("Polygons6") if state.has("Polygons6") else []):
        if number != 74 and (polygon.get("LAYER") or "").upper() != layer_text(number):
            continue
        outline = [(x, y) for x, y, _ in _outline(polygon)[:-1]]
        if len(outline) >= 3 and polygons_intersect(
            GeoPolygon(tuple(GeoPoint(x, y) for x, y in outline)), cut
        ):
            for storage, positions in _poured(state, index).items():
                state.remove(storage, positions)
            stale.append(_polygon_name(polygon))
    return stale


def draw_board_shape(state: State, layer: str, *, width: int, old_count: int | None) -> int:
    """The free tracks and arcs of the mechanical ``layer`` replaced by the edges of the board shape; their
    old number must be ``old_count`` when given. The number removed (design D6)."""
    from fenolite.backends.altium.edit import drawing

    view = View(state)
    number = view.layer_id(layer)
    _assert(drawing.mechanical(number), f"the board shape is drawn on a mechanical layer, not on {layer}")
    _assert(width > 0, "a drawing needs a width above zero")
    old = drawing.drawn_edges(state, number)
    held = f"{layer} holds {len(old)} free tracks and arcs, not the stated {old_count}"
    _assert(old_count is None or len(old) == old_count, held, "Tracks6/Data")
    templates = {
        kind: _drawing_template(state, storage, kind, number)
        for storage, kind in (("Tracks6", TRACK), ("Arcs6", ARC))
    }
    for storage in ("Tracks6", "Arcs6"):
        state.remove(storage, {position for s, position, _ in old if s == storage})
    for edge in drawing.board_shape(state):
        if edge.centre is None:
            raw = templates[TRACK]
            if raw is None:
                raise Refused(
                    "altium.edit.no-template",
                    "the document holds no track on a mechanical layer to copy",
                    "Tracks6/Data",
                )
            raw = rec.patch(raw, 13, "<5i", *map(round, (*edge.a, *edge.b)), to_units(width))
            state.append("Tracks6", raw)
        else:
            raw = templates[ARC]
            if raw is None:
                raise Refused(
                    "altium.edit.no-template",
                    "the document holds no arc on a mechanical layer to copy",
                    "Arcs6/Data",
                )
            raw = rec.patch(raw, 13, "<3i", *map(round, (*edge.centre, edge.radius)))
            raw = rec.patch(rec.patch(raw, 25, "<2d", edge.start, edge.end), 41, "<i", to_units(width))
            state.append("Arcs6", raw)

    def drawn(after: State) -> None:
        found = drawing.compare(after, number)
        _assert(
            not found,
            f"{layer} differs from the board shape after the redraw: {found[0].message if found else ''}",
        )

    state.post.append(drawn)
    return len(old)


def _drawing_template(state: State, storage: str, kind: int, layer: int) -> bytes | None:
    """A free record of ``kind`` on ``layer``, else on any mechanical layer moved to ``layer``."""
    from fenolite.backends.altium.edit import drawing

    raws = state.get(storage) if state.has(storage) else []
    free = [raw for raw in raws if raw[0] == kind and rec.prefix_of(raw)[2:] == (rec.NO_INDEX, rec.NO_INDEX)]
    for raw in free:
        if on_layer(raw, layer):
            return rec.set_prefix(raw, net=rec.NO_INDEX)
    for raw in free:
        if drawing.mechanical(rec.prefix_of(raw)[0]):
            return relayer(rec.set_prefix(raw, net=rec.NO_INDEX), layer)
    return None


__all__ = [
    "Arc",
    "Comment",
    "Component",
    "Designator",
    "Fill",
    "Item",
    "Point",
    "Polygon",
    "REACH",
    "Refused",
    "Region",
    "Text",
    "Track",
    "Via",
    "Vias",
    "View",
    "add_arc",
    "add_board_cutout",
    "add_component",
    "add_fill",
    "add_polygon",
    "add_polygon_cutout",
    "add_region",
    "clone",
    "delete",
    "describe",
    "draw_board_shape",
    "flip",
    "held_ids",
    "move",
    "move_text",
    "new_id",
    "remap_layer",
    "rotate",
    "rotate_text",
    "rotation_text",
    "set_outline",
    "set_property",
    "set_region_outline",
    "set_rule",
    "set_via_mask",
]

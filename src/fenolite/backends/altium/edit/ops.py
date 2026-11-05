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
import secrets
import string
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from fractions import Fraction

from fenolite.backends.altium.edit import records as rec
from fenolite.backends.altium.edit.state import PRIMITIVE_STORAGES, SHAPE_BASED, WIDE, State
from fenolite.backends.altium.libboard import long_id
from fenolite.backends.altium.pcbrecords import (
    FLIP_PAIRS,
    LAYER_NAMES,
    mil_text,
    to_units,
    v7_layer,
)
from fenolite.backends.altium.read.pcbprims import (
    ARC,
    PAD,
    REGION,
    TEXT,
    TRACK,
    VIA,
    ArcRecord,
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
ID_LETTERS = string.ascii_uppercase
ID_LENGTH = 8
"""The form of a pad's ``UNIQUEID`` in every document read: eight upper-case letters (``H-A-EDIT-IDS``)."""
COMPONENT_STORAGES = ("Pads6", "Tracks6", "Arcs6", "Texts6", "Fills6", "Regions6", "ShapeBasedRegions6",
                      "Vias6", "ComponentBodies6", "ShapeBasedComponentBodies6")  # fmt: skip
KIND_NAMES = {TRACK: "track", VIA: "via", ARC: "arc", PAD: "pad", TEXT: "text", REGION: "region"}

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
    """A track by its two ends (either order) and its net (``None``: no net); ``layer`` narrows it."""

    start: Point
    end: Point
    net: str | None
    layer: str | None = None


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
    """A free text by the string it shows."""

    text: str


@dataclass(frozen=True, slots=True)
class Region:
    """A free region by its layer and the lower-left corner of its outline's box."""

    layer: str
    corner: Point


Item = Track | Via | Component | Polygon | Text | Region


def describe(item: Item) -> str:
    def mm(p: Point) -> str:
        return f"({p[0] / 1e6:g}, {p[1] / 1e6:g}) mm"

    if isinstance(item, Track):
        return f"the track {mm(item.start)}–{mm(item.end)} on {item.net or 'no net'}"
    if isinstance(item, Via):
        return f"the via at {mm(item.at)} on {item.net or 'no net'}"
    if isinstance(item, Component):
        return f"the component {item.designator}"
    if isinstance(item, Polygon):
        return f"the polygon {item.name}"
    if isinstance(item, Text):
        return f"the text {item.text!r}"
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
        storage, test = self._test(item)
        found = [i for i, p in enumerate(self.state.typed(storage)) if test(p)]
        _assert(len(found) == 1, f"{len(found)} records match {describe(item)}, not one", f"{storage}/Data")
        return storage, found[0]

    def _test(self, item: Item) -> tuple[str, Callable[[Primitive], bool]]:
        if isinstance(item, Track):
            a, b = self.units(item.start), self.units(item.end)
            layer = None if item.layer is None else self.layer_id(item.layer)
            net = self.net_index(item.net)

            def track(p: Primitive) -> bool:
                if not isinstance(p, TrackRecord) or _net(p.prefix.net) != net:
                    return False
                if layer is not None and p.prefix.layer != layer:
                    return False
                ends = ((p.x1, p.y1), (p.x2, p.y2))
                return (_near(ends[0], a) and _near(ends[1], b)) or (_near(ends[0], b) and _near(ends[1], a))

            return "Tracks6", track
        if isinstance(item, Via):
            at, net = self.units(item.at), self.net_index(item.net)
            return (
                "Vias6",
                lambda p: isinstance(p, ViaRecord) and _net(p.prefix.net) == net and _near((p.x, p.y), at),
            )
        if isinstance(item, Text):
            wide = {index: text for index, (_, text) in self.state.wide().items()}

            def text(p: Primitive) -> bool:
                if not isinstance(p, TextRecord) or p.prefix.component is not None:
                    return False
                shown = wide.get(p.wide_index, p.short_text) if p.wide_index is not None else p.short_text
                return shown == item.text

            return "Texts6", text
        if isinstance(item, Region):
            layer, corner = self.layer_id(item.layer), self.units(item.corner)
            return "Regions6", lambda p: _free_region(p, layer, corner)
        raise TypeError(f"{type(item).__name__} is not an item")


def _polygon_name(record: PropertyRecord) -> str:
    from fenolite.backends.altium.read.pcb import decode_name

    return decode_name(record.text("NAME"))


def _net(index: int | None) -> int:
    return rec.NO_INDEX if index is None else index


def _near(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return abs(a[0] - b[0]) <= TOLERANCE and abs(a[1] - b[1]) <= TOLERANCE


def _free_region(p: Primitive, layer: int, corner: tuple[int, int]) -> bool:
    if not isinstance(p, RegionRecord) or p.prefix.polygon is not None or p.prefix.component is not None:
        return False
    if p.prefix.layer != layer or not p.outline:
        return False
    return _near((min(v.x for v in p.outline), min(v.y for v in p.outline)), corner)


def _twins(state: State, raw: bytes, shape_based_storage: str = "ShapeBasedRegions6") -> list[int]:
    """The records of ``ShapeBasedRegions6`` that stand for the free region ``raw`` of ``Regions6``: the
    same layer, the same property text and the same box (phase A, J14: both change together)."""
    found = state.typed("Regions6")
    (region,) = [p for p in found if p.raw == raw]
    assert isinstance(region, RegionRecord)
    box = _box(region)
    out: list[int] = []
    for position, other in enumerate(state.typed(shape_based_storage)):
        if (
            isinstance(other, RegionRecord)
            and other.prefix.layer == region.prefix.layer
            and other.prefix.polygon == region.prefix.polygon
            and other.prefix.component == region.prefix.component
            and other.properties.fields == region.properties.fields
            and _box(other) == box
        ):
            out.append(position)
    return out


def _box(region: RegionRecord) -> tuple[int, int, int, int]:
    xs = [round(v.x) for v in region.outline]
    ys = [round(v.y) for v in region.outline]
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
    """The stated old values of a track or a via: ``width``, ``diameter`` (nm), ``layer`` (a name)."""
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


def _body_model_keys(raw: bytes, move: rec.Transform, turn: float) -> bytes:
    """A body with its ``MODEL.2D.X``/``Y`` moved and ``MODEL.3D.ROTZ`` turned, where it holds them."""
    keys = rec.region_keys(raw)
    x, y = parse_mil(keys.get("MODEL.2D.X")), parse_mil(keys.get("MODEL.2D.Y"))
    changes: dict[str, str] = {}
    if x is not None and y is not None:
        nx, ny = move(float(x), float(y))
        changes["MODEL.2D.X"], changes["MODEL.2D.Y"] = mil_text(round(nx)), mil_text(round(ny))
    if turn and "MODEL.3D.ROTZ" in keys:
        try:
            changes["MODEL.3D.ROTZ"] = f"{(float(keys['MODEL.3D.ROTZ']) + turn) % 360:.3f}"
        except ValueError:
            pass
    return rec.set_region_keys(raw, changes) if changes else raw


def move_primitives(
    state: State, index: int, move: rec.Transform, *, turn: float = 0.0, mirror: bool = False,
    layers: Mapping[int, int] | None = None,
) -> None:  # fmt: skip
    """Every primitive of component ``index`` moved by ``move``, turned by ``turn``, mirrored, and put on
    the other layer of its pair in ``layers``."""
    for storage, positions in component_primitives(state, index).items():
        for position in positions:
            raw = state.get(storage)[position]
            new = rec.transform(raw, move, turn=turn, mirror=mirror, shape_based=storage in SHAPE_BASED)
            if storage.endswith("ComponentBodies6"):
                new = _body_model_keys(new, move, turn)
            if layers:
                layer = rec.prefix_of(new)[0]
                if layer in layers:
                    new = relayer(new, layers[layer], strict=False)
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
    _assert(not isinstance(item, Polygon), "a polygon is not moved by a session")
    check_expect(view, storage, position, expect)
    raw = state.get(storage)[position]
    state.replace(storage, position, rec.transform(raw, rec.shift(du, dv)))
    if isinstance(item, Region):
        for twin in _twins(state, raw):
            other = state.get("ShapeBasedRegions6")[twin]
            state.replace(
                "ShapeBasedRegions6", twin, rec.transform(other, rec.shift(du, dv), shape_based=True)
            )


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
    changes = {"LAYER": "BOTTOM" if side == "TOP" else "TOP", "ROTATION": rotation_text((-held) % 360)}
    state.replace("Components6", index, rec.set_property(record.raw, changes))
    move_primitives(state, index, rec.mirror_x(float(x)), mirror=True, layers=FLIP_PAIRS)


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
    fields = {"width": (TRACK, 29), "diameter": (VIA, 21)}
    _assert(key in fields, f"{key!r} is not a property a session sets on {describe(item)}", where)
    check_expect(view, storage, position, {key: old})
    raw = state.get(storage)[position]
    state.replace(storage, position, rec.patch(raw, fields[key][1], "<i", to_units(int(value))))  # type: ignore[arg-type]


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
    saved long track, arc or fill, which Altium shows the primitive on (S-1588, case J23: a track whose
    layer byte alone was changed stayed on its old layer). A form whose long layer id no row records
    (``rec.long_layer_offset``) raises ``RecordError`` when ``strict``, else keeps its other bytes."""
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
    body's ``V7_LAYER`` and a long track's, arc's or fill's long layer id together (``relayer``,
    ``H-A-EDIT-LAYER``). Copper layers are not remapped: a polygon's pour and the pads' stacks would need a
    change of their own. A text keeps any layer field other than its layer byte: no row records one."""
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


def _same_form(state: State, storage: str, raw: bytes) -> None:
    layer = rec.prefix_of(raw)[0]
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


__all__ = [
    "Component",
    "Item",
    "Point",
    "Polygon",
    "Refused",
    "Region",
    "Text",
    "Track",
    "Via",
    "View",
    "add_component",
    "clone",
    "delete",
    "describe",
    "flip",
    "held_ids",
    "move",
    "new_id",
    "remap_layer",
    "rotate",
    "rotation_text",
    "set_property",
    "set_rule",
]

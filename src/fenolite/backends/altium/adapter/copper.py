# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Free primitives of a PCB document as board objects (capability altium-import, "Tracks, arcs and vias",
"Zones from polygons" and "Outline, graphics and texts"; ``docs/formats/altium/import.md``; changes c0043,
c0122 and c0124).

A free primitive carries no component index. On a copper layer of the chain a track is a ``Track``, an arc
an ``Arc`` and a via a ``Via``; a polygon is a ``Zone`` whose regions are its fills, each one ring that
holds the region's outline and its holes (``geometry.keyhole_ring``). Everything else that is drawn
becomes a ``Graphic`` or a ``Text``. What gives no entity is counted in the census.

An internal plane is the exception among the copper layers of the chain: it is stored in negative, so a free
primitive on it cuts the plane and is no copper. It gives no entity and is counted as ``plane-cuts``
(``_plane_cut``; capability altium-import, "Objects on an internal plane").
"""

# evidence: see import_evidence

from __future__ import annotations

import re
from collections.abc import Sequence
from fractions import Fraction

from fenolite.backends.altium.adapter import units
from fenolite.backends.altium.adapter.codes import issue
from fenolite.backends.altium.adapter.context import Context
from fenolite.backends.altium.adapter.ids import Exact, bag
from fenolite.backends.altium.adapter.layers import EDGE, MULTI
from fenolite.backends.altium.read.pcb import SPLIT_PLANE_POLYGON, PcbDocument, PolygonRecord
from fenolite.backends.altium.read.pcbprims import (
    ArcRecord,
    FillRecord,
    Primitive,
    RawPrimitive,
    RegionRecord,
    RegionVertex,
    TrackRecord,
    via_pad_removed,
)
from fenolite.backends.altium.read.pcbstack import OutlineVertex
from fenolite.core.coords import Point, Size
from fenolite.geometry.polygon import keyhole_ring
from fenolite.geometry.transform import FULL_TURN, QUARTER_TURN, rotate_point
from fenolite.model.board import Arc, Graphic, GraphicKind, Text, Track, Via, ViaType, Zone, ZoneFill

POLYGON_TYPE = "polygon"
_LAYER_TEXT = re.compile(r"(TOP|BOTTOM|MID|PLANE)(\d*)", re.IGNORECASE)


def layer_of_text(text: str | None) -> int | None:
    """The copper layer id of a ``LAYER`` text of a property record: ``TOP`` 1, ``MID<n>`` n + 1,
    ``BOTTOM`` 32, ``PLANE<n>`` n + 38; ``None`` for any other text."""
    match = _LAYER_TEXT.fullmatch(text or "")
    if match is None:
        return None
    word, number = match.group(1).upper(), match.group(2)
    if word in ("TOP", "BOTTOM"):
        return None if number else (1 if word == "TOP" else 32)
    if not number:
        return None
    value = int(number)
    if word == "MID":
        return value + 1 if 1 <= value <= 30 else None
    return value + 38 if 1 <= value <= 16 else None


def _xy(point: Point) -> list[int]:
    return [point.x, point.y]


def _free(item: Primitive, components: int) -> bool:
    """Whether ``item`` belongs to no component: no index, or an index that names no record."""
    return (
        isinstance(item, RawPrimitive) or item.prefix.component is None or item.prefix.component >= components
    )


def _poured(item: TrackRecord | ArcRecord) -> bool:
    return item.prefix.polygon is not None


def _plane_cut(ctx: Context, kind: str, layer_id: int) -> bool:
    """Whether a free primitive of record kind ``kind`` on ``layer_id`` lies on an internal plane; it is
    then counted, in the census and on its layer, and the caller makes no entity of it."""
    if not ctx.layers.is_plane(layer_id):
        return False
    ctx.layers.cut(layer_id)
    ctx.census.skip(kind, "plane-cuts")
    return True


def _graphic(
    ctx: Context,
    kind: GraphicKind,
    layer: str,
    points: Sequence[Point],
    *,
    width: int,
    filled: bool,
    locator: str,
    pairs: list[tuple[str, str]],
) -> Graphic:
    ident = ctx.ids.content("gfx", "gfx", kind, layer, [_xy(p) for p in points], width, filled, sorted(pairs))
    return Graphic(
        id=ident,
        provenance=ctx.provenance(locator),
        ext=bag(pairs),
        kind=kind,
        layer=layer,
        points=tuple(points),
        width=width,
        filled=filled,
    )


def _bad(ctx: Context, kind: str, what: str, locator: str) -> None:
    ctx.issues.append(issue("altium.import.bad-geometry", f"{what}; the record is not mapped", locator))
    ctx.census.skip(kind, "bad-geometry")


def _net_pair(ctx: Context, index: int | None) -> list[tuple[str, str]]:
    name = ctx.net_name(index)
    return [("net", name)] if name is not None else []


# --- tracks, arcs, vias ---------------------------------------------------------------------------------


def tracks(doc: PcbDocument, ctx: Context) -> tuple[list[Track], list[Graphic]]:
    """The free tracks: ``Track`` on a copper layer of the chain, a ``line`` graphic elsewhere, nothing
    on an internal plane."""
    found: list[Track] = []
    graphics: list[Graphic] = []
    for index, item in enumerate(doc.tracks):
        locator = f"Tracks6/Data#{index}"
        if isinstance(item, RawPrimitive):
            ctx.census.skip("tracks", "raw-primitives")
            continue
        if not _free(item, len(doc.components)):
            ctx.census.skip("tracks", "footprint-graphics")
            continue
        if _poured(item):
            ctx.census.skip("tracks", "pour-primitives")
            continue
        if _plane_cut(ctx, "tracks", item.prefix.layer):
            continue
        exact = Exact(ctx.census)
        start = exact.point("start", item.x1, item.y1)
        end = exact.point("end", item.x2, item.y2)
        width = exact.length("width", item.width)
        layer_id = item.prefix.layer
        if ctx.layers.is_copper(layer_id):
            if item.width <= 0:
                _bad(ctx, "tracks", "a track needs a width above 0", locator)
                continue
            layer = ctx.layers.name(layer_id)
            net_id = ctx.net(item.prefix.net)
            found.append(
                Track(
                    id=ctx.ids.content("trk", "tracks", _xy(start), _xy(end), width, layer, net_id or ""),
                    provenance=ctx.provenance(locator),
                    ext=bag(exact.pairs()),
                    start=start,
                    end=end,
                    width=width,
                    layer=layer,
                    net_id=net_id,
                )
            )
        else:
            layer = ctx.layers.name(layer_id)
            graphics.append(
                _graphic(
                    ctx,
                    "line",
                    layer,
                    (start, end),
                    width=max(width, 0),
                    filled=False,
                    locator=locator,
                    pairs=exact.pairs(),
                )  # fmt: skip
            )
        ctx.census.map("tracks")
    return found, graphics


ARC_KEY = "arc"
"""The bag key of an arc that an arc record gave (change c0127): the record's own centre, radius and
angles, which the three points of the model do not give back in every case."""


def arc_pair(item: ArcRecord) -> str:
    """The value of the pair ``arc``: ``<centre x>,<centre y>,<radius>,<start angle>,<end angle>``, the
    three integers of the record in units of 1/10 000 mil in the document's frame and its two angles as
    ``float.hex()`` of the stored doubles."""
    angles = f"{float(item.start_angle).hex()},{float(item.end_angle).hex()}"
    return f"{item.cx},{item.cy},{item.radius},{angles}"


def arcs(doc: PcbDocument, ctx: Context) -> tuple[list[Arc], list[Graphic]]:
    """The free arcs: ``Arc`` on a copper layer of the chain (a full circle is a ``circle`` graphic with
    its net in the bag), an ``arc`` or ``circle`` graphic elsewhere, nothing on an internal plane. An
    ``Arc`` and an ``arc`` graphic keep their record in the pair ``arc`` (``arc_pair``)."""
    found: list[Arc] = []
    graphics: list[Graphic] = []
    for index, item in enumerate(doc.arcs):
        locator = f"Arcs6/Data#{index}"
        if isinstance(item, RawPrimitive):
            ctx.census.skip("arcs", "raw-primitives")
            continue
        if not _free(item, len(doc.components)):
            ctx.census.skip("arcs", "footprint-graphics")
            continue
        if _poured(item):
            ctx.census.skip("arcs", "pour-primitives")
            continue
        if _plane_cut(ctx, "arcs", item.prefix.layer):
            continue
        if item.radius <= 0:
            _bad(ctx, "arcs", "an arc needs a radius above 0", locator)
            continue
        exact = Exact(ctx.census)
        exact.length("centre.x", item.cx)
        exact.length("centre.y", item.cy)
        exact.length("radius", item.radius)
        width = exact.length("width", item.width)
        start_angle = exact.angle("start_angle", item.start_angle)
        end_angle = exact.angle("end_angle", item.end_angle)
        full = units.sweep(start_angle, end_angle) == FULL_TURN
        layer_id = item.prefix.layer
        copper = ctx.layers.is_copper(layer_id)
        if copper and item.width <= 0:
            _bad(ctx, "arcs", "an arc on copper needs a width above 0", locator)
            continue
        layer = ctx.layers.name(layer_id)
        pairs = exact.pairs()
        if full:
            centre, edge = units.circle_points(item.cx, item.cy, item.radius)
            if copper:
                pairs += _net_pair(ctx, item.prefix.net)
            graphics.append(
                _graphic(
                    ctx,
                    "circle",
                    layer,
                    (centre, edge),
                    width=max(width, 0),
                    filled=False,
                    locator=locator,
                    pairs=pairs,
                )  # fmt: skip
            )
        else:
            start, mid, end = units.arc_points(item.cx, item.cy, item.radius, start_angle, end_angle)
            pairs.append((ARC_KEY, arc_pair(item)))
            if copper:
                net_id = ctx.net(item.prefix.net)
                found.append(
                    Arc(
                        id=ctx.ids.content(
                            "arc", "arcs", _xy(start), _xy(mid), _xy(end), width, layer, net_id or ""
                        ),
                        provenance=ctx.provenance(locator),
                        ext=bag(pairs),
                        start=start,
                        mid=mid,
                        end=end,
                        width=width,
                        layer=layer,
                        net_id=net_id,
                    )
                )
            else:
                graphics.append(
                    _graphic(
                        ctx,
                        "arc",
                        layer,
                        (start, mid, end),
                        width=max(width, 0),
                        filled=False,
                        locator=locator,
                        pairs=pairs,
                    )  # fmt: skip
                )
        ctx.census.map("arcs")
    return found, graphics


PAD_REMOVED_KEY = "pad_removed"
"""The bag key of a via whose record names layers without a pad shape: their Altium layer ids, in
ascending order, separated by commas (change c0132; ``read.pcbprims.via_pad_removed``)."""


def vias(doc: PcbDocument, ctx: Context) -> list[Via]:
    """Every via with its span: ``through`` between the outer layers, ``blind`` with one outer layer,
    ``buried`` otherwise. A start or end layer outside the chain gives the outer layers and a warning.
    A via whose record names layers without a pad shape holds them in the pair ``pad_removed``; its
    diameter and its id are those of the record without them."""
    found: list[Via] = []
    chain = ctx.layers.chain
    outer = {chain[0], chain[-1]}
    for index, item in enumerate(doc.vias):
        locator = f"Vias6/Data#{index}"
        if isinstance(item, RawPrimitive):
            ctx.census.skip("vias", "raw-primitives")
            continue
        if item.diameter <= 0 or item.hole <= 0:
            _bad(ctx, "vias", "a via needs a diameter and a hole above 0", locator)
            continue
        exact = Exact(ctx.census)
        position = exact.point("position", item.x, item.y)
        diameter = exact.length("diameter", item.diameter)
        drill = exact.length("drill", item.hole)
        pairs = exact.pairs()
        ends = (item.start_layer, item.end_layer)
        if all(ctx.layers.is_copper(layer) for layer in ends):
            ordered = sorted(ends, key=chain.index)
            names = (ctx.layers.name(ordered[0]), ctx.layers.name(ordered[1]))
            count = len(outer & set(ends))
            via_type: ViaType = "through" if set(ends) == outer else ("blind" if count == 1 else "buried")
        else:
            ctx.issues.append(
                issue(
                    "altium.import.via-span",
                    f"the via spans the layers {ends[0]} to {ends[1]}, which are not both in the copper "
                    "chain; it is read as a through via",
                    locator,
                )
            )
            names = (ctx.layers.name(chain[0]), ctx.layers.name(chain[-1]))
            via_type = "through"
            pairs.append(("via_layers", f"{ends[0]},{ends[1]}"))
        removed = via_pad_removed(item)
        if removed:  # the model holds one diameter: the layers without a pad shape are said here alone
            pairs.append((PAD_REMOVED_KEY, ",".join(str(layer) for layer in removed)))
        net_id = ctx.net(item.prefix.net)
        found.append(
            Via(
                id=ctx.ids.content("via", "vias", _xy(position), diameter, drill, list(names), net_id or ""),
                provenance=ctx.provenance(locator),
                ext=bag(pairs),
                position=position,
                diameter=diameter,
                drill=drill,
                layers=names,
                net_id=net_id,
                via_type=via_type,
            )
        )
        ctx.census.map("vias")
    return found


def definition_graphics(primitives: Sequence[Primitive], ctx: Context, storage: str) -> list[Graphic]:
    """The tracks, arcs, fills and regions of a library footprint as graphics on the neutral layers, in
    primitive order; pads, bodies and texts are left to the caller. ``storage`` names the footprint's
    storage in the locators."""
    found: list[Graphic] = []
    for index, item in enumerate(primitives):
        locator = f"{storage}/Data#{index}"
        exact = Exact(ctx.census)
        if isinstance(item, TrackRecord):
            start = exact.point("start", item.x1, item.y1)
            end = exact.point("end", item.x2, item.y2)
            width = max(exact.length("width", item.width), 0)
            layer = ctx.layers.name(item.prefix.layer)
            found.append(
                _graphic(
                    ctx,
                    "line",
                    layer,
                    (start, end),
                    width=width,
                    filled=False,
                    locator=locator,
                    pairs=exact.pairs(),
                )  # fmt: skip
            )
            ctx.census.map("tracks")
        elif isinstance(item, ArcRecord):
            if item.radius <= 0:
                _bad(ctx, "arcs", "an arc needs a radius above 0", locator)
                continue
            width = max(exact.length("width", item.width), 0)
            start_angle = exact.angle("start_angle", item.start_angle)
            end_angle = exact.angle("end_angle", item.end_angle)
            layer = ctx.layers.name(item.prefix.layer)
            if units.sweep(start_angle, end_angle) == FULL_TURN:
                points: tuple[Point, ...] = units.circle_points(item.cx, item.cy, item.radius)
                kind: GraphicKind = "circle"
            else:
                points = units.arc_points(item.cx, item.cy, item.radius, start_angle, end_angle)
                kind = "arc"
            found.append(
                _graphic(
                    ctx, kind, layer, points, width=width, filled=False, locator=locator, pairs=exact.pairs()
                )  # fmt: skip
            )
            ctx.census.map("arcs")
        elif isinstance(item, FillRecord):
            kind, points = _fill_points(item, exact)
            layer = ctx.layers.name(item.prefix.layer)
            found.append(
                _graphic(ctx, kind, layer, points, width=0, filled=True, locator=locator, pairs=exact.pairs())
            )
            ctx.census.map("fills")
        elif isinstance(item, RegionRecord):
            points = region_points(item.outline)
            if item.holes:
                ctx.census.note("region-holes", len(item.holes))
            if len(points) < 3:
                _bad(ctx, "regions", "a region needs at least three vertices", locator)
                continue
            layer = ctx.layers.name(item.prefix.layer)
            found.append(
                _graphic(ctx, "polygon", layer, points, width=0, filled=True, locator=locator, pairs=[])
            )
            ctx.census.map("regions")
    return found


# --- zones ----------------------------------------------------------------------------------------------


def _vertex_point(vertex: RegionVertex) -> Point:
    """A region vertex (doubles or integers, in units) as a model point, rounded half to even."""
    x = units.round_half_even(Fraction(vertex.x) * units.NM_PER_UNIT)
    y = units.round_half_even(Fraction(vertex.y) * units.NM_PER_UNIT)
    return Point(x, -y)


def region_points(vertices: Sequence[RegionVertex]) -> tuple[Point, ...]:
    """The model points of a region outline, without a repeated last vertex and without repeated
    neighbours."""
    points: list[Point] = []
    for vertex in vertices:
        try:
            point = _vertex_point(vertex)
        except (ValueError, OverflowError):  # a double that is not finite
            continue
        if not points or points[-1] != point:
            points.append(point)
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    return tuple(points)


def _outline_points(vertices: Sequence[OutlineVertex], exact: Exact, field: str) -> tuple[Point, ...]:
    points: list[Point] = []
    for k, vertex in enumerate(vertices):
        x, x_exact = units.units_length(vertex.x)
        y, y_exact = units.units_length(vertex.y)
        if not x_exact:
            exact.inexact(f"{field}.{k}.x", str(vertex.x))
        if not y_exact:
            exact.inexact(f"{field}.{k}.y", str(vertex.y))
        points.append(Point(x, -y))
    if len(points) > 1 and points[0] == points[-1]:
        points.pop()
    return tuple(points)


def _bad_vertex_text(record: PolygonRecord) -> bool:
    """Whether a vertex coordinate of the polygon is not a length text."""
    for k in range(len(record.vertices)):
        for key in (f"VX{k}", f"VY{k}"):
            text = record.record.get(key)
            if text is not None and units.text_length(text) is None:
                return True
    return False


def zones(doc: PcbDocument, ctx: Context) -> tuple[list[Zone], set[int]]:
    """One ``Zone`` per polygon of type ``Polygon`` on a copper layer of the chain, with the regions that
    carry its index as fills; also the indexes of the polygons that became zones. A fill is the keyhole
    ring of its region: the outline without the holes. A hole that the ring does not hold is counted as
    ``region-holes``, and the holes outside their outline are reported once."""
    mapped: dict[int, tuple[PolygonRecord, str, int]] = {}
    for index, record in enumerate(doc.polygons):
        locator = f"Polygons6/Data#{index}"
        layer_id = layer_of_text(record.layer)
        if (record.polygon_type or "").lower() != POLYGON_TYPE or layer_id is None:
            ctx.census.skip("polygons", "polygons")
            continue
        if not ctx.layers.is_copper(layer_id):
            ctx.census.skip("polygons", "polygons")
            continue
        if _bad_vertex_text(record):
            ctx.issues.append(
                issue("altium.import.bad-length", "a vertex of the polygon is not a length in mil", locator)
            )
            ctx.census.skip("polygons", "polygons")
            continue
        mapped[index] = (record, locator, layer_id)
    highest = max((record.pour_index or 0 for record, _, _ in mapped.values()), default=0)
    found: list[Zone] = []
    arcs_seen = 0
    holes_outside = regions_outside = 0
    for index, (record, locator, layer_id) in mapped.items():
        exact = Exact(ctx.census)
        layer = ctx.layers.name(layer_id)
        if any(vertex.kind != 0 for vertex in record.vertices):
            outline: tuple[Point, ...] = ()
            arcs_seen += 1
        else:
            outline = _outline_points(record.vertices, exact, "outline")
        fills: list[ZoneFill] = []
        for region in doc.regions_of(index):
            if not ctx.layers.is_copper(region.prefix.layer):
                continue
            points = region_points(region.outline)
            if len(points) < 3:
                ctx.census.note("region-holes", len(region.holes))
                continue
            merged = keyhole_ring(points, [region_points(hole) for hole in region.holes])
            fills.append(ZoneFill(ctx.layers.name(region.prefix.layer), merged.ring))
            ctx.census.note("region-holes", len(region.holes) - merged.merged)
            if merged.outside:
                holes_outside += merged.outside
                regions_outside += 1
        pairs = exact.pairs()
        if record.pour_index is not None:
            pairs.append(("pour_index", str(record.pour_index)))
        if record.hatch_style:
            pairs.append(("hatch_style", record.hatch_style))
        net_id = ctx.net(record.net)
        unique = record.record.get("UNIQUEID")
        if unique:
            ident, native = ctx.ids.native("zon", f"zone:{unique}")
        else:
            ident = ctx.ids.content(
                "zon", "zones", [_xy(p) for p in outline], record.name, layer, net_id or "", index
            )
            native = {}
        found.append(
            Zone(
                id=ident,
                native_ids=native,
                provenance=ctx.provenance(locator),
                ext=bag(pairs),
                outline=outline,
                name=record.name,
                layers=(layer,),
                net_id=net_id,
                priority=highest - (record.pour_index or 0),
                fills=tuple(fills),
                filled=bool(fills),
            )
        )
        ctx.census.map("polygons")
    if arcs_seen:
        ctx.issues.append(
            issue(
                "altium.import.zone-arc",
                f"{arcs_seen} zone(s) have an outline with an arc vertex; their outline is kept by the "
                "reader's record and is empty in the model",
                "Polygons6/Data",
            )
        )
    if holes_outside:
        ctx.issues.append(
            issue(
                "altium.import.zone-hole-outside",
                f"{holes_outside} hole(s) of {regions_outside} poured region(s) lie outside the region's "
                "outline; they are dropped and the fill is solid there",
                "Regions6/Data",
            )
        )
    return found, set(mapped)


# --- shapes, texts, outline -----------------------------------------------------------------------------


def _fill_points(item: FillRecord, exact: Exact) -> tuple[GraphicKind, tuple[Point, ...]]:
    a = exact.point("corner1", item.x1, item.y1)
    b = exact.point("corner2", item.x2, item.y2)
    rotation = exact.angle("rotation", item.rotation)
    if rotation == 0 or rotation == FULL_TURN // 2:
        return "rect", (a, b)
    # Twice the centre keeps the rotation about the centre in integers.
    cx2, cy2 = a.x + b.x, a.y + b.y
    corners = (a, Point(b.x, a.y), b, Point(a.x, b.y))
    turned: list[Point] = []
    for corner in corners:
        moved = rotate_point(Point(2 * corner.x - cx2, 2 * corner.y - cy2), rotation)
        turned.append(
            Point(
                units.round_half_even(Fraction(moved.x + cx2, 2)),
                units.round_half_even(Fraction(moved.y + cy2, 2)),
            )
        )
    if rotation % QUARTER_TURN == 0:
        return "rect", (turned[0], turned[2])
    return "polygon", tuple(turned)


def shapes(doc: PcbDocument, ctx: Context, fill_regions: set[int]) -> list[Graphic]:
    """The free fills and regions as filled graphics; one on a copper layer carries its net name in the
    pair ``net`` and is counted by ``altium.import.copper-shape``. ``fill_regions`` are the polygon indexes
    that became zones: their regions are fills, not graphics. The holes of a region that is a graphic are
    not in the model and are counted as ``region-holes``. A free fill or region on an internal plane is no
    shape of copper: it gives nothing."""
    found: list[Graphic] = []
    copper_shapes = 0
    for index, item in enumerate(doc.fills):
        locator = f"Fills6/Data#{index}"
        if isinstance(item, RawPrimitive):
            ctx.census.skip("fills", "raw-primitives")
            continue
        if not _free(item, len(doc.components)):
            ctx.census.skip("fills", "footprint-graphics")
            continue
        if _plane_cut(ctx, "fills", item.prefix.layer):
            continue
        exact = Exact(ctx.census)
        kind, points = _fill_points(item, exact)
        layer = ctx.layers.name(item.prefix.layer)
        pairs = exact.pairs()
        if ctx.layers.is_copper(item.prefix.layer):
            pairs += _net_pair(ctx, item.prefix.net)
            copper_shapes += 1
        found.append(_graphic(ctx, kind, layer, points, width=0, filled=True, locator=locator, pairs=pairs))
        ctx.census.map("fills")
    for index, item in enumerate(doc.regions):
        locator = f"Regions6/Data#{index}"
        if isinstance(item, RawPrimitive):
            ctx.census.skip("regions", "raw-primitives")
            continue
        polygon = item.prefix.polygon
        if not (polygon in fill_regions and ctx.layers.is_copper(item.prefix.layer)):
            ctx.census.note("region-holes", len(item.holes))  # the holes of a fill are counted by ``zones``
        if not _free(item, len(doc.components)):
            ctx.census.skip("regions", "footprint-graphics")
            continue
        if polygon is not None:
            if polygon in fill_regions and ctx.layers.is_copper(item.prefix.layer):
                ctx.census.map("regions")
            else:
                ctx.census.skip(
                    "regions", "pour-primitives" if polygon != SPLIT_PLANE_POLYGON else "polygons"
                )
            continue
        if _plane_cut(ctx, "regions", item.prefix.layer):
            continue
        points = region_points(item.outline)
        if len(points) < 3:
            _bad(ctx, "regions", "a region needs at least three vertices", locator)
            continue
        layer = ctx.layers.name(item.prefix.layer)
        pairs: list[tuple[str, str]] = []
        if ctx.layers.is_copper(item.prefix.layer):
            pairs += _net_pair(ctx, item.prefix.net)
            copper_shapes += 1
        found.append(
            _graphic(ctx, "polygon", layer, points, width=0, filled=True, locator=locator, pairs=pairs)
        )
        ctx.census.map("regions")
    ctx.census.skip("shape_regions", "shape-based-regions", len(doc.shape_regions))
    if copper_shapes:
        ctx.issues.append(
            issue(
                "altium.import.copper-shape",
                f"{copper_shapes} fill(s) and region(s) on copper are graphics with their net in the bag; "
                "the model has no copper shape with a net",
                "Fills6/Data",
            )
        )
    return found


def texts(doc: PcbDocument, ctx: Context) -> list[Text]:
    """The free texts; the text is the wide string when the record names one (the reader resolved it).
    A free text on an internal plane gives nothing."""
    found: list[Text] = []
    for index, item in enumerate(doc.texts):
        locator = f"Texts6/Data#{index}"
        if isinstance(item, RawPrimitive):
            ctx.census.skip("texts", "raw-primitives")
            continue
        if not _free(item, len(doc.components)):
            ctx.census.skip("texts", "footprint-graphics")
            continue
        if _plane_cut(ctx, "texts", item.prefix.layer):
            continue
        exact = Exact(ctx.census)
        position = exact.point("position", item.x, item.y)
        height = exact.length("size", item.height)
        thickness = exact.length("thickness", item.stroke_width)
        rotation = exact.angle("rotation", item.rotation)
        layer = ctx.layers.name(item.prefix.layer if item.prefix.layer != MULTI else ctx.layers.chain[0])
        found.append(
            Text(
                id=ctx.ids.content(
                    "txt", "texts", item.text, _xy(position), layer, height, thickness, rotation
                ),
                provenance=ctx.provenance(locator),
                ext=bag(exact.pairs()),
                text=item.text,
                position=position,
                layer=layer,
                size=Size(height, height),
                thickness=max(thickness, 0),
                rotation=rotation,
            )
        )
        ctx.census.map("texts")
    return found


def _nearer(point: Point, a: Point, b: Point) -> bool:
    """Whether ``point`` is nearer to ``a`` than to ``b``."""
    da = (point.x - a.x) ** 2 + (point.y - a.y) ** 2
    db = (point.x - b.x) ** 2 + (point.y - b.y) ** 2
    return da <= db


def outline(vertices: Sequence[OutlineVertex], ctx: Context, locator: str = "Board6/Data#0") -> list[Graphic]:
    """The board outline as graphics on ``Edge.Cuts`` with width 0: one per segment, a ``line`` for a line
    vertex and an ``arc`` for an arc vertex; a segment of zero length is dropped."""
    found: list[Graphic] = []
    count = len(vertices)
    if count < 2:
        return found
    corners: list[Point] = []
    inexact: list[list[str]] = []
    for vertex in vertices:
        x, x_exact = units.units_length(vertex.x)
        y, y_exact = units.units_length(vertex.y)
        notes: list[str] = []
        if not x_exact:
            notes.append(f"x={vertex.x}")
        if not y_exact:
            notes.append(f"y={vertex.y}")
        ctx.census.inexact_lengths += len(notes)
        corners.append(Point(x, -y))
        inexact.append(notes)
    for k, vertex in enumerate(vertices):
        a, b = corners[k], corners[(k + 1) % count]
        where = f"{locator}:V{k}"
        if a == b:
            continue
        notes = [f"start.{n}" for n in inexact[k]] + [f"end.{n}" for n in inexact[(k + 1) % count]]
        pairs = [("u", ",".join(notes))] if notes else []
        if vertex.kind == 0 or vertex.radius <= 0:
            found.append(
                _graphic(ctx, "line", EDGE, (a, b), width=0, filled=False, locator=where, pairs=pairs)
            )
            continue
        start_angle, _ = units.angle(vertex.start_angle)
        end_angle, _ = units.angle(vertex.end_angle)
        start, mid, end = units.arc_points(vertex.cx, vertex.cy, vertex.radius, start_angle, end_angle)
        if not _nearer(start, a, b):
            start, end = end, start
        found.append(
            _graphic(ctx, "arc", EDGE, (start, mid, end), width=0, filled=False, locator=where, pairs=pairs)
        )
    return found


__all__ = [
    "arcs",
    "definition_graphics",
    "layer_of_text",
    "outline",
    "region_points",
    "shapes",
    "texts",
    "tracks",
    "vias",
    "zones",
]

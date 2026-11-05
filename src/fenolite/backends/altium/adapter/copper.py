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

Change c0407: a primitive on copper whose second flag byte is 2 is a keep-out, not copper. A track or an arc
gives a rule area of the band its width covers (``geometry.bands``), a fill or a region a rule area of its
outline, each on its layer alone (``Context.keepouts``). A region of ``KIND=1`` is a polygon cut-out: a rule
area that forbids poured copper, on its copper layer, or on every copper layer from the Keep-Out or the
Multi-Layer layer. Both are what KiCad 10.0.6's ``pcb import`` makes of them (``pcb-records.md``, "Regions
and keep-outs"). A primitive of a component is in the board's frame there, not in its footprint.
"""

# evidence: see import_evidence

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from fenolite.backends.altium.adapter import units
from fenolite.backends.altium.adapter.codes import issue
from fenolite.backends.altium.adapter.context import Context
from fenolite.backends.altium.adapter.ids import Exact, bag
from fenolite.backends.altium.adapter.layers import EDGE, MULTI
from fenolite.backends.altium.adapter.pads import WILDCARD_ALL
from fenolite.backends.altium.read.pcb import SPLIT_PLANE_POLYGON, PcbDocument, PolygonRecord
from fenolite.backends.altium.read.pcbprims import (
    ArcRecord,
    FillRecord,
    Primitive,
    RawPrimitive,
    RegionRecord,
    RegionVertex,
    TextRecord,
    TrackRecord,
    via_pad_removed,
)
from fenolite.backends.altium.read.pcbstack import OutlineVertex
from fenolite.core.coords import Point, Size
from fenolite.geometry.bands import arc_band, segment_band
from fenolite.geometry.errors import GeometryError
from fenolite.geometry.polygon import keyhole_ring
from fenolite.geometry.transform import FULL_TURN, QUARTER_TURN, Transform, rotate_point
from fenolite.model.board import (
    Arc,
    FootprintField,
    Graphic,
    GraphicKind,
    Keepout,
    Text,
    Track,
    Via,
    ViaProtection,
    ViaType,
    Zone,
    ZoneFill,
)

POLYGON_TYPE = "polygon"
KEEPOUT_FLAG = 2
"""The second flag byte of a keep-out primitive (``pcb-records.md``, "Regions and keep-outs")."""
EVERY_RESTRICTION = 0x1F
"""The restrictions of a keep-out that holds no value: KiCad takes 31, every restriction (``pcb-records.md``,
"Regions and keep-outs"); the 36-byte track holds none."""
RESTRICTION_KEYS = ("KEEPOUTRESTRICTIONS", "KEEPOUTRESTRIC")
"""The keys of a keep-out region's restrictions: Altium's own first, then the one KiCad's importer reads."""
POLYGON_CUTOUT_KIND = "1"
"""``KIND`` of a polygon cut-out region (``pcb-pour.md``, I20; ``pcb-records.md``, "Regions and
keep-outs")."""
ALL_COPPER_LAYERS = frozenset({56, 74})
"""The Keep-Out and the Multi-Layer layer: a polygon cut-out there keeps pours off every copper layer."""
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


# --- keep-outs and polygon cut-outs (change c0407) -------------------------------------------------------


def is_keepout(item: Primitive) -> bool:
    """Whether ``item`` is a keep-out: its second flag byte is 2."""
    return not isinstance(item, RawPrimitive) and item.prefix.flags2 == KEEPOUT_FLAG


def is_polygon_cutout(item: RegionRecord) -> bool:
    """Whether a region is a polygon cut-out: ``KIND=1``."""
    keys = {key.upper(): value for key, value in item.properties.fields}
    return keys.get("KIND", "0").strip() == POLYGON_CUTOUT_KIND


def _restrictions(item: RegionRecord) -> int:
    """The restrictions value of a keep-out region (``RESTRICTION_KEYS``), else ``EVERY_RESTRICTION``."""
    keys = {key.upper(): value for key, value in item.properties.fields}
    for key in RESTRICTION_KEYS:
        text = keys.get(key, "").strip()
        if text.isdigit() and int(text) <= EVERY_RESTRICTION:
            return int(text)
    return EVERY_RESTRICTION


RESTRICTION_BYTE: Mapping[type, int] = {TrackRecord: 45, ArcRecord: 56, FillRecord: 46}
"""The offset in the subrecord of the restrictions byte of a keep-out track, arc or fill of the long form:
the byte after its 32-bit long layer id, which tracks hold at 41, arcs at 52 and fills at 42 (census of the
public PCB documents; ``pcb-records.md``, "Regions and keep-outs")."""


def record_restrictions(item: TrackRecord | ArcRecord | FillRecord) -> int:
    """The restrictions value of a keep-out track, arc or fill: the byte of ``RESTRICTION_BYTE`` when its
    subrecord holds it, else ``EVERY_RESTRICTION`` (a short form, as KiCad 10.0.6 imports a 36-byte keep-out
    track). A value of 0 restricts nothing: Altium lets a kind whose restriction is cleared through (S-1711),
    and KiCad's import of such a fill forbids nothing."""
    offset = RESTRICTION_BYTE[type(item)]
    body = item.raw[5:]  # the type byte and the subrecord's length come first
    if len(body) > offset and body[offset] <= EVERY_RESTRICTION:
        return body[offset]
    return EVERY_RESTRICTION


def _keepout(
    ctx: Context,
    layers: Sequence[str],
    outline: Sequence[Point],
    restrictions: int,
    locator: str,
    section: str,
    into: list[Keepout] | None = None,
    frame: Transform | None = None,
) -> None:
    """One rule area in ``into`` (``ctx.keepouts`` by default); the bits of ``restrictions`` as the
    writer's ``KEEPOUT_BITS``: 1 vias, 2 tracks, 4 poured copper, 8 and 16 together pads. ``frame`` maps
    each point into a footprint's pad frame (change c0411)."""
    if frame is not None:
        outline = tuple(frame.apply(p) for p in outline)
    (ctx.keepouts if into is None else into).append(
        Keepout(
            id=ctx.ids.content("kpo", section, list(layers), [_xy(p) for p in outline], restrictions),
            provenance=ctx.provenance(locator),
            outline=tuple(outline),
            layers=tuple(layers),
            no_vias=bool(restrictions & 0x01),
            no_tracks=bool(restrictions & 0x02),
            no_copper_pour=bool(restrictions & 0x04),
            no_pads=restrictions & 0x18 == 0x18,
        )
    )


def _corners(kind: GraphicKind, points: Sequence[Point]) -> tuple[Point, ...]:
    """The four corners of a ``rect`` (two opposite corners), else ``points``."""
    if kind != "rect":
        return tuple(points)
    a, b = points
    return (a, Point(b.x, a.y), b, Point(a.x, b.y))


def _halves(centre: Point, edge: Point) -> tuple[tuple[Point, Point, Point], ...]:
    """A circle as two half arcs, from ``edge`` round to its opposite point and back."""
    dx, dy = edge.x - centre.x, edge.y - centre.y
    far = Point(centre.x - dx, centre.y - dy)
    return (
        (edge, Point(centre.x - dy, centre.y + dx), far),
        (far, Point(centre.x + dy, centre.y - dx), edge),
    )


def _stroke_keepout(
    ctx: Context,
    census: str,
    kind: GraphicKind,
    layer: str,
    points: Sequence[Point],
    width: int,
    locator: str,
    section: str = "kpo",
    into: list[Keepout] | None = None,
    frame: Transform | None = None,
    *,
    restrictions: int = EVERY_RESTRICTION,
) -> None:
    """A keep-out track (``line``), arc or circle on copper as the rule areas of the band its ``width``
    covers, one per stroke (two for a circle), with ``restrictions`` (``record_restrictions`` of its
    record). A stroke that covers no area is bad geometry. ``into`` and ``frame`` as ``_keepout``."""
    try:
        if kind == "line":
            rings = [segment_band(points[0], points[1], width)]
        elif kind == "arc":
            rings = [arc_band(points[0], points[1], points[2], width)]
        else:
            rings = [arc_band(*half, width) for half in _halves(points[0], points[1])]
    except GeometryError as error:
        _bad(ctx, census, f"a keep-out {kind} covers no area ({error})", locator)
        return
    for ring in rings:
        _keepout(ctx, (layer,), ring, restrictions, locator, section, into, frame)
    ctx.census.map(census)


def _region_keepout(
    ctx: Context,
    item: RegionRecord,
    points: Sequence[Point],
    locator: str,
    section: str = "kpo",
    into: list[Keepout] | None = None,
    frame: Transform | None = None,
    *,
    definition: bool = False,
    owned: bool = False,
) -> bool:
    """A polygon cut-out (anywhere ``KiCad`` takes one) or a keep-out region on copper as its rule area in
    ``into`` (``ctx.keepouts`` by default); whether it was one. ``points`` are in the frame of the
    document, and ``frame`` maps them as ``_keepout`` does. A cut-out on every copper layer is on the
    board's copper layers, or on ``*.Cu`` in a ``definition``, as a Multi-Layer pad (change c0411). A
    keep-out region of the Keep-Out layer ``owned`` by a footprint is its rule area on every copper layer,
    with its restrictions: the writers write such an area so (change c0411)."""
    layer_id = item.prefix.layer
    copper = ctx.layers.is_copper(layer_id)
    if is_polygon_cutout(item) and (copper or layer_id in ALL_COPPER_LAYERS):
        everywhere = (WILDCARD_ALL,) if definition else ctx.layers.copper_names
        layers = (ctx.layers.name(layer_id),) if copper else everywhere
        _keepout(ctx, layers, points, 0x04, locator, section, into, frame)
    elif is_keepout(item) and copper:
        name = ctx.layers.name(layer_id)
        _keepout(ctx, (name,), points, _restrictions(item), locator, section, into, frame)
    elif owned and is_keepout(item) and layer_id == KEEPOUT_LAYER_ID:
        everywhere = (WILDCARD_ALL,) if definition else ctx.layers.copper_names
        _keepout(ctx, everywhere, points, _restrictions(item), locator, section, into, frame)
    else:
        return False
    ctx.census.map("regions")
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
    section: str = "gfx",
    net_id: str | None = None,
) -> Graphic:
    ident = ctx.ids.content(
        "gfx", section, kind, layer, [_xy(p) for p in points], width, filled, sorted(pairs)
    )
    return Graphic(
        id=ident,
        provenance=ctx.provenance(locator),
        ext=bag(pairs),
        kind=kind,
        layer=layer,
        points=tuple(points),
        width=width,
        filled=filled,
        net_id=net_id,
    )


def _bad(ctx: Context, kind: str, what: str, locator: str) -> None:
    ctx.issues.append(issue("altium.import.bad-geometry", f"{what}; the record is not mapped", locator))
    ctx.census.skip(kind, "bad-geometry")


def _net_pair(ctx: Context, index: int | None) -> list[tuple[str, str]]:
    name = ctx.net_name(index)
    return [("net", name)] if name is not None else []


# --- tracks, arcs, vias ---------------------------------------------------------------------------------


def tracks(doc: PcbDocument, ctx: Context, owned: Collection[int] = ()) -> tuple[list[Track], list[Graphic]]:
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
            if item.prefix.component not in owned:  # else an item of its footprint (``footprint_items``)
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
        if ctx.layers.is_copper(layer_id) and is_keepout(item):
            # a keep-out track on copper keeps out the band of its width (change c0407)
            _stroke_keepout(
                ctx,
                "tracks",
                "line",
                ctx.layers.name(layer_id),
                (start, end),
                width,
                locator,
                restrictions=record_restrictions(item),
            )
            continue
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
                    locked=item.prefix.locked,
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


def arcs(doc: PcbDocument, ctx: Context, owned: Collection[int] = ()) -> tuple[list[Arc], list[Graphic]]:
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
            if item.prefix.component not in owned:  # else an item of its footprint (``footprint_items``)
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
        if copper and is_keepout(item):
            # a keep-out arc on copper keeps out the band of its width (change c0407)
            if full:
                stroke: tuple[Point, ...] = units.circle_points(item.cx, item.cy, item.radius)
            else:
                stroke = units.arc_points(item.cx, item.cy, item.radius, start_angle, end_angle)
            kind: GraphicKind = "circle" if full else "arc"
            _stroke_keepout(
                ctx, "arcs", kind, layer, stroke, width, locator, restrictions=record_restrictions(item)
            )
            continue
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
                        locked=item.prefix.locked,
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
    diameter and its id are those of the record without them. The two tenting flags of the record become
    ``Via.protection`` (``tenting_front`` from the top flag, ``tenting_back`` from the bottom flag, both
    explicit; ``H-A-PCB-CU-VIATENT``); the solder-mask expansion of the via is not read."""
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
                locked=item.prefix.locked,
                # both sides explicit: an Altium via carries its own flags and follows no board default,
                # and a ``None`` would be read by the KiCad backend as "tented" (change c0112)
                protection=ViaProtection(tenting_front=item.tented_top, tenting_back=item.tented_bottom),
            )
        )
        ctx.census.map("vias")
    return found


_CENSUS_KINDS: dict[type, str] = {
    TrackRecord: "tracks",
    ArcRecord: "arcs",
    FillRecord: "fills",
    RegionRecord: "regions",
}


KEEPOUT_LAYER_ID = 56
"""The Keep-Out layer (``LayerMap``: ``Altium.KeepOut``)."""


def keepout_layer_restrictions(item: Primitive) -> int | None:
    """The restrictions value of a keep-out (second flag byte 2) on the Keep-Out layer: the byte after the
    long layer id of a track, arc or fill, or ``KEEPOUTRESTRICTIONS`` of a region (``pcb-records.md``,
    "Regions and keep-outs"); ``None`` for any other primitive (change c0420, N2 and N3). A conversion reads
    it from the source record, so the rule area forbids only what the keep-out forbids (S-1711)."""
    if isinstance(item, RawPrimitive) or item.prefix.layer != KEEPOUT_LAYER_ID or not is_keepout(item):
        return None
    if isinstance(item, RegionRecord):
        return _restrictions(item)
    if isinstance(item, (TrackRecord, ArcRecord, FillRecord)):
        return record_restrictions(item)
    return None


def library_keepout(item: Primitive, ctx: Context) -> bool:
    """Whether a primitive of a library footprint is a rule area of the footprint (changes c0410, c0411): a
    keep-out track, arc, fill or region on copper, a keep-out region of the Keep-Out layer, or a polygon
    cut-out on copper, the Keep-Out or the Multi-Layer layer. Such a primitive gives no graphic. Any other
    drawing of the Keep-Out layer stays a graphic of ``Altium.KeepOut``, as on a board: ``convert`` makes
    its rule area."""
    if isinstance(item, RawPrimitive) or type(item) not in _CENSUS_KINDS:
        return False
    layer_id = item.prefix.layer
    copper = ctx.layers.is_copper(layer_id)
    cutout = (
        isinstance(item, RegionRecord)
        and is_polygon_cutout(item)
        and (copper or layer_id in ALL_COPPER_LAYERS)
    )
    region = isinstance(item, RegionRecord) and layer_id == KEEPOUT_LAYER_ID
    return cutout or ((copper or region) and is_keepout(item))


def _library_keepout(item: Primitive, ctx: Context, locator: str, section: str, into: list[Keepout]) -> None:
    """The rule areas of a keep-out or a polygon cut-out of a library footprint (``library_keepout``), in
    the footprint's frame, in ``into`` (change c0411); each record as on a board (change c0407)."""
    if not isinstance(item, (TrackRecord, ArcRecord, FillRecord, RegionRecord)):
        return  # ``library_keepout`` holds no other kind
    exact = Exact(ctx.census)
    layer = ctx.layers.name(item.prefix.layer)
    if isinstance(item, TrackRecord):
        start = exact.point("start", item.x1, item.y1)
        end = exact.point("end", item.x2, item.y2)
        width = max(exact.length("width", item.width), 0)
        _stroke_keepout(
            ctx,
            "tracks",
            "line",
            layer,
            (start, end),
            width,
            locator,
            section,
            into,
            restrictions=record_restrictions(item),
        )
    elif isinstance(item, ArcRecord):
        if item.radius <= 0:
            _bad(ctx, "arcs", "an arc needs a radius above 0", locator)
            return
        width = max(exact.length("width", item.width), 0)
        start_angle = exact.angle("start_angle", item.start_angle)
        end_angle = exact.angle("end_angle", item.end_angle)
        full = units.sweep(start_angle, end_angle) == FULL_TURN
        if full:
            stroke: tuple[Point, ...] = units.circle_points(item.cx, item.cy, item.radius)
        else:
            stroke = units.arc_points(item.cx, item.cy, item.radius, start_angle, end_angle)
        kind: GraphicKind = "circle" if full else "arc"
        _stroke_keepout(
            ctx,
            "arcs",
            kind,
            layer,
            stroke,
            width,
            locator,
            section,
            into,
            restrictions=record_restrictions(item),
        )
    elif isinstance(item, FillRecord):
        fill_kind, points = _fill_points(item, exact)
        corners = _corners(fill_kind, points)
        _keepout(ctx, (layer,), corners, record_restrictions(item), locator, section, into)
        ctx.census.map("fills")
    else:
        points = region_points(item.outline)
        if len(points) < 3:
            _bad(ctx, "regions", "a region needs at least three vertices", locator)
            return
        _region_keepout(ctx, item, points, locator, section, into, definition=True, owned=True)


def definition_graphics(
    primitives: Sequence[Primitive], ctx: Context, storage: str, keepouts: list[Keepout] | None = None
) -> list[Graphic]:
    """The tracks, arcs, fills and regions of a library footprint as graphics on the neutral layers, in
    primitive order; pads, bodies and texts are left to the caller. ``storage`` names the footprint's
    storage in the locators. A keep-out on copper or a polygon cut-out (``library_keepout``) gives no
    graphic but a rule area of the footprint in ``keepouts`` (change c0411)."""
    found: list[Graphic] = []
    areas: list[Keepout] = [] if keepouts is None else keepouts
    for index, item in enumerate(primitives):
        locator = f"{storage}/Data#{index}"
        if library_keepout(item, ctx):
            _library_keepout(item, ctx, locator, f"lib:{storage}", areas)
            continue
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


# --- the items of a component (change c0126) ------------------------------------------------------------

REFERENCE_FIELD = "Reference"
VALUE_FIELD = "Value"


@dataclass(frozen=True, slots=True)
class Owned:
    """The primitives of one component that are no pad, each with its record index: the tracks, arcs,
    fills, regions and texts that carry the component's index."""

    tracks: tuple[tuple[int, TrackRecord], ...] = ()
    arcs: tuple[tuple[int, ArcRecord], ...] = ()
    fills: tuple[tuple[int, FillRecord], ...] = ()
    regions: tuple[tuple[int, RegionRecord], ...] = ()
    texts: tuple[tuple[int, TextRecord], ...] = ()


def owned_primitives(doc: PcbDocument) -> dict[int, Owned]:
    """Component index → the primitives that carry it, for the indexes that name a component record."""
    count = len(doc.components)
    found: dict[int, dict[str, list[tuple[int, Any]]]] = {}
    kinds: tuple[tuple[str, Sequence[Primitive]], ...] = (
        ("tracks", doc.tracks),
        ("arcs", doc.arcs),
        ("fills", doc.fills),
        ("regions", doc.regions),
        ("texts", doc.texts),
    )
    for name, items in kinds:
        for index, item in enumerate(items):
            if isinstance(item, RawPrimitive) or _free(item, count):
                continue
            owner = item.prefix.component
            assert owner is not None
            found.setdefault(owner, {}).setdefault(name, []).append((index, item))
    return {
        owner: Owned(**{name: tuple(held) for name, held in parts.items()}) for owner, parts in found.items()
    }


@dataclass(frozen=True, slots=True)
class FootprintItems:
    """What ``footprint_items`` gives one footprint: its graphics (tracks, arcs, fills, regions, in that
    order and, within each, in record order), the fields ``Reference`` and ``Value`` it has a text for,
    and its other texts."""

    graphics: tuple[Graphic, ...] = ()
    fields: tuple[FootprintField, ...] = ()
    texts: tuple[Text, ...] = ()
    keepouts: tuple[Keepout, ...] = ()
    """The component's keep-outs on copper and polygon cut-outs, as rule areas in the pad frame (c0411)."""


def _is_rect(corners: Sequence[Point]) -> bool:
    a, b, c, d = corners
    return (a.y == b.y and b.x == c.x and c.y == d.y and d.x == a.x) or (
        a.x == b.x and b.y == c.y and c.x == d.x and d.y == a.y
    )


def footprint_items(
    owned: Owned,
    ctx: Context,
    frame: Transform,
    rotation: int,
    *,
    native: str,
    name_on: bool = True,
    comment_on: bool = True,
) -> FootprintItems:
    """The primitives of one component as the graphics, the fields and the texts of its footprint
    (capability altium-import, "Graphics, fields and texts of a component"; ``import.md``, "Primitives of a
    component"). ``frame`` is the inverse of the footprint's placement, the transform of its pads, so
    every point is footprint-local and a bottom footprint holds mirrored coordinates; ``rotation`` is the
    footprint's angle, which a text's angle is taken relative to. ``native`` names the footprint in the
    section of the content ids. The mapping of a record is that of ``definition_graphics``; an arc keeps
    its record in the pair ``arc``, and a graphic on a copper layer its net name in the pair ``net``. The
    first designator text and the first comment text give the fields ``Reference`` and ``Value``, shown
    as ``name_on`` and ``comment_on`` say; every other text is a ``Text``. A primitive on an internal
    plane gives no item and stays counted as ``footprint-graphics``."""
    section = f"fp:{native}"
    graphics: list[Graphic] = []
    keepouts: list[Keepout] = []

    def on_plane(kind: str, layer_id: int) -> bool:
        """A primitive of a component on an internal plane is no item of its footprint: a line there is a
        cut in the plane, not a drawing (change c0124). It stays counted as ``footprint-graphics``."""
        if not ctx.layers.is_plane(layer_id):
            return False
        ctx.census.skip(kind, "footprint-graphics")
        return True

    def add(
        kind: GraphicKind,
        layer_id: int,
        net: int | None,
        points: Sequence[Point],
        width: int,
        filled: bool,
        locator: str,
        pairs: list[tuple[str, str]],
    ) -> None:
        if ctx.layers.is_copper(layer_id):
            pairs = pairs + _net_pair(ctx, net)
        local = tuple(frame.apply(point) for point in points)
        graphics.append(
            _graphic(
                ctx,
                kind,
                ctx.layers.name(layer_id),
                local,
                width=width,
                filled=filled,
                locator=locator,
                pairs=pairs,
                section=section,
            )
        )

    for index, item in owned.tracks:
        if on_plane("tracks", item.prefix.layer):
            continue
        exact = Exact(ctx.census)
        start = exact.point("start", item.x1, item.y1)
        end = exact.point("end", item.x2, item.y2)
        width = max(exact.length("width", item.width), 0)
        if ctx.layers.is_copper(item.prefix.layer) and is_keepout(item):
            # a keep-out of a component on copper is a rule area of its footprint (changes c0407, c0411)
            layer = ctx.layers.name(item.prefix.layer)
            locator = f"Tracks6/Data#{index}"
            _stroke_keepout(
                ctx,
                "tracks",
                "line",
                layer,
                (start, end),
                width,
                locator,
                section,
                keepouts,
                frame,
                restrictions=record_restrictions(item),
            )
            continue
        add(
            "line",
            item.prefix.layer,
            item.prefix.net,
            (start, end),
            width,
            False,
            f"Tracks6/Data#{index}",
            exact.pairs(),
        )
        ctx.census.map("tracks")
    for index, item in owned.arcs:
        locator = f"Arcs6/Data#{index}"
        if on_plane("arcs", item.prefix.layer):
            continue
        if item.radius <= 0:
            _bad(ctx, "arcs", "an arc needs a radius above 0", locator)
            continue
        exact = Exact(ctx.census)
        exact.length("centre.x", item.cx)
        exact.length("centre.y", item.cy)
        exact.length("radius", item.radius)
        width = max(exact.length("width", item.width), 0)
        start_angle = exact.angle("start_angle", item.start_angle)
        end_angle = exact.angle("end_angle", item.end_angle)
        pairs = exact.pairs()
        full = units.sweep(start_angle, end_angle) == FULL_TURN
        if ctx.layers.is_copper(item.prefix.layer) and is_keepout(item):
            # a keep-out of a component on copper is a rule area of its footprint (changes c0407, c0411)
            if full:
                stroke: tuple[Point, ...] = units.circle_points(item.cx, item.cy, item.radius)
            else:
                stroke = units.arc_points(item.cx, item.cy, item.radius, start_angle, end_angle)
            layer = ctx.layers.name(item.prefix.layer)
            kind: GraphicKind = "circle" if full else "arc"
            _stroke_keepout(
                ctx,
                "arcs",
                kind,
                layer,
                stroke,
                width,
                locator,
                section,
                keepouts,
                frame,
                restrictions=record_restrictions(item),
            )
            continue
        if full:
            points: tuple[Point, ...] = units.circle_points(item.cx, item.cy, item.radius)
            add("circle", item.prefix.layer, item.prefix.net, points, width, False, locator, pairs)
        else:
            points = units.arc_points(item.cx, item.cy, item.radius, start_angle, end_angle)
            pairs.append((ARC_KEY, arc_pair(item)))
            add("arc", item.prefix.layer, item.prefix.net, points, width, False, locator, pairs)
        ctx.census.map("arcs")
    for index, item in owned.fills:
        if on_plane("fills", item.prefix.layer):
            continue
        exact = Exact(ctx.census)
        kind, points = _fill_points(item, exact)
        points = _corners(kind, points)
        if ctx.layers.is_copper(item.prefix.layer) and is_keepout(item):
            # a keep-out of a component on copper is a rule area of its footprint (changes c0407, c0411)
            layer = ctx.layers.name(item.prefix.layer)
            locator = f"Fills6/Data#{index}"
            _keepout(ctx, (layer,), points, record_restrictions(item), locator, section, keepouts, frame)
            ctx.census.map("fills")
            continue
        corners = tuple(frame.apply(point) for point in points)
        # a fill that lies square in the document may be turned in the footprint's frame, and the reverse
        shape: tuple[GraphicKind, tuple[Point, ...]] = (
            ("rect", (corners[0], corners[2])) if _is_rect(corners) else ("polygon", corners)
        )
        pairs = exact.pairs()
        if ctx.layers.is_copper(item.prefix.layer):
            pairs += _net_pair(ctx, item.prefix.net)
        graphics.append(
            _graphic(
                ctx,
                shape[0],
                ctx.layers.name(item.prefix.layer),
                shape[1],
                width=0,
                filled=True,
                locator=f"Fills6/Data#{index}",
                pairs=pairs,
                section=section,
            )
        )
        ctx.census.map("fills")
    for index, item in owned.regions:
        locator = f"Regions6/Data#{index}"
        if on_plane("regions", item.prefix.layer):
            continue
        points = region_points(item.outline)
        if len(points) < 3:
            _bad(ctx, "regions", "a region needs at least three vertices", locator)
            continue
        if _region_keepout(ctx, item, points, locator, section, keepouts, frame, owned=True):
            continue  # a polygon cut-out or a keep-out region of a component on copper (c0407, c0411)
        local = tuple(frame.apply(point) for point in points)
        # A region of four vertices that is a rectangle square to the footprint is the filled ``rect`` that
        # a fill of the same corners gives: the writer writes a filled rectangle as a region, and the two
        # are one shape in the model.
        shape = ("rect", (local[0], local[2])) if len(local) == 4 and _is_rect(local) else ("polygon", local)
        pairs = _net_pair(ctx, item.prefix.net) if ctx.layers.is_copper(item.prefix.layer) else []
        graphics.append(
            _graphic(
                ctx,
                shape[0],
                ctx.layers.name(item.prefix.layer),
                shape[1],
                width=0,
                filled=True,
                locator=locator,
                pairs=pairs,
                section=section,
            )
        )
        ctx.census.map("regions")

    fields: dict[str, FootprintField] = {}
    texts: list[Text] = []
    for index, item in owned.texts:
        locator = f"Texts6/Data#{index}"
        if on_plane("texts", item.prefix.layer):
            continue
        exact = Exact(ctx.census)
        position = frame.apply(exact.point("position", item.x, item.y))
        height = exact.length("size", item.height)
        thickness = max(exact.length("thickness", item.stroke_width), 0)
        angle = (exact.angle("rotation", item.rotation) - rotation) % FULL_TURN
        layer = ctx.layers.name(item.prefix.layer if item.prefix.layer != MULTI else ctx.layers.chain[0])
        name = REFERENCE_FIELD if item.is_designator else VALUE_FIELD if item.is_comment else ""
        if name and name not in fields:
            shown = name_on if name == REFERENCE_FIELD else comment_on
            fields[name] = FootprintField(
                id=ctx.ids.content("fld", section, name, _xy(position), layer, height, thickness, angle),
                provenance=ctx.provenance(locator),
                ext=bag(exact.pairs()),
                name=name,
                position=position,
                layer=layer,
                size=Size(height, height),
                rotation=angle,
                thickness=thickness,
                visible=shown,
                mirrored=bool(item.mirrored),
            )
        else:
            texts.append(
                Text(
                    id=ctx.ids.content(
                        "txt", section, item.text, _xy(position), layer, height, thickness, angle
                    ),
                    provenance=ctx.provenance(locator),
                    ext=bag(exact.pairs()),
                    text=item.text,
                    position=position,
                    layer=layer,
                    size=Size(height, height),
                    thickness=thickness,
                    rotation=angle,
                )
            )
        ctx.census.map("texts")
    ordered = tuple(fields[name] for name in (REFERENCE_FIELD, VALUE_FIELD) if name in fields)
    return FootprintItems(tuple(graphics), ordered, tuple(texts), tuple(keepouts))


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
        if style := record.record.get("POUROVERSTYLE"):
            pairs.append(("pour_over", style))
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


def is_board_cutout(item: RegionRecord) -> bool:
    """Whether a free region is a board cut-out: ``KIND=0`` (or no ``KIND``) with ``ISBOARDCUTOUT=TRUE``
    (``pcb-records.md``, "Board cut-outs"; change c0168). ``KIND=1``, a polygon cut-out, is not one."""
    keys = {key.upper(): value for key, value in item.properties.fields}
    return keys.get("ISBOARDCUTOUT", "").upper() == "TRUE" and keys.get("KIND", "0") == "0"


def shapes(
    doc: PcbDocument, ctx: Context, fill_regions: set[int], owned: Collection[int] = ()
) -> list[Graphic]:
    """The free fills and regions as filled graphics; one on a copper layer is copper of its net
    (``net_id``, change c0376; the name also in the pair ``net``) and is counted by
    ``altium.import.copper-shape``. ``fill_regions`` are the polygon indexes
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
            if item.prefix.component not in owned:  # else an item of its footprint (``footprint_items``)
                ctx.census.skip("fills", "footprint-graphics")
            continue
        if _plane_cut(ctx, "fills", item.prefix.layer):
            continue
        exact = Exact(ctx.census)
        kind, points = _fill_points(item, exact)
        layer = ctx.layers.name(item.prefix.layer)
        if ctx.layers.is_copper(item.prefix.layer) and is_keepout(item):
            # a keep-out fill on copper is a rule area of its outline (change c0407)
            _keepout(ctx, (layer,), _corners(kind, points), record_restrictions(item), locator, "kpo")
            ctx.census.map("fills")
            continue
        pairs = exact.pairs()
        net_id: str | None = None
        if ctx.layers.is_copper(item.prefix.layer):
            pairs += _net_pair(ctx, item.prefix.net)
            net_id = ctx.net(item.prefix.net)  # the copper of its net (change c0376)
            copper_shapes += 1
        found.append(
            _graphic(
                ctx, kind, layer, points, width=0, filled=True, locator=locator, pairs=pairs, net_id=net_id
            )
        )
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
            if item.prefix.component not in owned:  # else an item of its footprint (``footprint_items``)
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
        if is_board_cutout(item):
            # a board cut-out is an edge of the board (change c0168): a ring of Edge.Cuts, width 0
            found.append(
                _graphic(ctx, "polygon", EDGE, points, width=0, filled=False, locator=locator, pairs=[])
            )
            ctx.census.map("regions")
            continue
        if _region_keepout(ctx, item, points, locator):
            continue  # a polygon cut-out or a keep-out region on copper is no copper (change c0407)
        layer = ctx.layers.name(item.prefix.layer)
        pairs: list[tuple[str, str]] = []
        region_net: str | None = None
        if ctx.layers.is_copper(item.prefix.layer):
            pairs += _net_pair(ctx, item.prefix.net)
            region_net = ctx.net(item.prefix.net)  # the copper of its net (change c0376)
            copper_shapes += 1
        found.append(
            _graphic(
                ctx,
                "polygon",
                layer,
                points,
                width=0,
                filled=True,
                locator=locator,
                pairs=pairs,
                net_id=region_net,
            )  # fmt: skip
        )
        ctx.census.map("regions")
    ctx.census.skip("shape_regions", "shape-based-regions", len(doc.shape_regions))
    if copper_shapes:
        ctx.issues.append(
            issue(
                "altium.import.copper-shape",
                f"{copper_shapes} fill(s) and region(s) on copper are copper graphics of their net (the net "
                "also in the bag), not zones",
                "Fills6/Data",
            )
        )
    return found


def texts(doc: PcbDocument, ctx: Context, owned: Collection[int] = ()) -> list[Text]:
    """The free texts; the text is the wide string when the record names one (the reader resolved it).
    A free text on an internal plane gives nothing."""
    found: list[Text] = []
    for index, item in enumerate(doc.texts):
        locator = f"Texts6/Data#{index}"
        if isinstance(item, RawPrimitive):
            ctx.census.skip("texts", "raw-primitives")
            continue
        if not _free(item, len(doc.components)):
            if item.prefix.component not in owned:  # else an item of its footprint (``footprint_items``)
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


OUTLINE_VERTEX_NM = 10_000
"""How far, in nanometres, the ends of an outline arc computed from its centre, radius and angles may lie
from the two vertices it joins for the vertices to be its ends (change c0378): the arc of vertex k runs from
vertex k to vertex k+1, and a vertex may lie micrometres off the circle (``pcb-document.md``). The distance
is KiCad's own join distance of edge ends (``backends.kicad.outline.CHAIN_GAP``)."""


def _within(point: Point, other: Point, distance: int) -> bool:
    return (point.x - other.x) ** 2 + (point.y - other.y) ** 2 <= distance * distance


def outline(vertices: Sequence[OutlineVertex], ctx: Context, locator: str = "Board6/Data#0") -> list[Graphic]:
    """The board outline as graphics on ``Edge.Cuts`` with width 0: one per segment, a ``line`` for a line
    vertex and an ``arc`` for an arc vertex; a segment of zero length is dropped. An arc runs from its vertex
    to the next: its ends are the two vertices when its computed ends lie within ``OUTLINE_VERTEX_NM`` of
    them, its middle comes from its centre, radius and angles."""
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
        if _within(start, a, OUTLINE_VERTEX_NM) and _within(end, b, OUTLINE_VERTEX_NM):
            start, end = a, b
        found.append(
            _graphic(ctx, "arc", EDGE, (start, mid, end), width=0, filled=False, locator=where, pairs=pairs)
        )
    return found


__all__ = [
    "KEEPOUT_LAYER_ID",
    "arcs",
    "definition_graphics",
    "keepout_layer_restrictions",
    "layer_of_text",
    "outline",
    "region_points",
    "shapes",
    "texts",
    "tracks",
    "vias",
    "zones",
]

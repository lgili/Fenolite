# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The poured copper of the polygons of a PCB document, computed from the document as Fenolite's reader
reads it (change c0215; capability altium-pour; ``docs/formats/altium/pcb-pour.md``).

``pour_reading`` takes a ``PourReading`` (the records of a document, its import, the pads of the import in
the board frame and the rings of its edge) and gives, per polygon of type ``Polygon``, the pieces of its
copper in the frame of the import (nanometres, Y down), or the reason it is refused. Only what the
document holds enters a pour: its polygon records, its rules, its objects and its board shape. Each input
is a row of "Pour inputs" of ``pcb-pour.md`` (``INPUTS``); an input the engine cannot evaluate refuses the
polygon (``REASONS``), and so does every later polygon of its layer that depends on it.

The geometry is the ``clipper`` backend of the ``geo`` extra, made when ``pour_reading`` runs. Every void
of a clearance lies outside the true curve: offsets use the arc tolerance ``tol`` (a quarter of the
polygon's ``ARCRESOLUTION``) and grow by ``tol + 1`` nm more, so no chord of a void comes nearer to an
object than its clearance (input I14).

Package layering keeps this module from ``checks``: the governing clearance is resolved here from the
neutral rules of the import as ``checks.clearance.ClearanceResolver`` resolves them for an Altium reading
(``rules_over_classes``, no board minimum, no zone clearance), and a test keeps the two equal.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Final, Literal

from fenolite.backends.altium.connectstyle import (
    Connection,
    ConnectStyle,
    ObjectKind,
    governing_connection,
    read_connect_styles,
)
from fenolite.backends.altium.read.pcb import PcbDocument, read_pcbdoc
from fenolite.backends.altium.read.pcbprims import RegionRecord
from fenolite.backends.altium.read.proptext import parse_length
from fenolite.backends.base import BoardPad, EdgeRing
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.geometry import Arc as GeoArc
from fenolite.geometry import Polygon
from fenolite.geometry.boolean.clipper import ClipperBackend
from fenolite.geometry.errors import BackendUnavailable, GeometryError
from fenolite.geometry.polygon import area2, convex_hull
from fenolite.geometry.predicates import floor_sqrt
from fenolite.geometry.shapes import BBox
from fenolite.geometry.transform import rotate_point
from fenolite.model.board import Board, Zone
from fenolite.model.design import Design
from fenolite.model.rules import LEAF_OPS, Rule, RuleSubject, Selector

PourMode = Literal["outline", "computed"]
POUR_MODES: tuple[PourMode, ...] = ("outline", "computed")

INPUTS: Mapping[str, str] = {
    "I1": "the polygon record",
    "I2": "the governing Clearance to an object of another net",
    "I3": "a polygon-specific Clearance rule",
    "I4": "a void at the exact value of its rule",
    "I5": "the governing Polygon Connect Style",
    "I6": "the shape of a relief",
    "I7": "Direct Connect and No Connect",
    "I8": "objects of the polygon's own net, by POUROVERSTYLE",
    "I9": "the pour order on a layer",
    "I10": "the removal of necks",
    "I11": "the order of the steps",
    "I12": "the removal of islands",
    "I13": "the removal of dead copper",
    "I14": "curves as straight edges",
    "I15": "optimal void rotation",
    "I16": "keep-outs",
    "I17": "the board shape and its clearance",
    "I18": "pads and vias as the copper check shapes them",
    "I19": "holes without copper",
    "I20": "copper the engine does not shape",
    "I21": "the pour engine of Altium Designer",
}
"""The inputs a pour uses, each a row of ``pcb-pour.md``, "Pour inputs" (a unit test compares the two)."""

REASONS: Mapping[str, str] = {
    "hatched": "the polygon is not solid (HATCHSTYLE)",
    "shelved": "the polygon is shelved",
    "outline-arc": "the polygon's outline holds an arc vertex",
    "outline": "the polygon's outline is not a simple ring of three points or more",
    "plane-layer": "the polygon lies on an internal plane",
    "no-board": "the document holds no closed board outline",
    "no-clearance": "no Clearance rule governs the polygon and an object",
    "rule-unmapped": "a Clearance record that Fenolite does not read could govern the polygon",
    "rule-scope": "a Clearance rule with a scope Fenolite does not read could govern the polygon",
    "connect-scope": "a Polygon Connect Style rule with a scope Fenolite does not read could govern a pad",
    "connect-style": "a Polygon Connect Style that Fenolite does not read governs a pad",
    "connect-value": "a Polygon Connect Style value that Fenolite does not read governs a pad",
    "connect-keys": "a Polygon Connect Style record of a form that Fenolite does not read governs a pad",
    "connect-header": "a Polygon Connect Style record of another net or layer kind governs a pad",
    "connect-priority": "a Polygon Connect Style record without a priority governs a pad",
    "connect-none": "no Polygon Connect Style rule governs a pad of the polygon's net",
    "pour-over": "the polygon's POUROVERSTYLE is not 0, 1 or 2",
    "threshold": "a threshold of the polygon is not a length or an area that Fenolite reads",
    "unshaped-copper": "copper the engine does not shape (a text, a graphic) lies within the polygon's reach",
    "unshaped-pad": "a pad whose copper the import does not shape lies within the polygon's reach",
    "polygon-cutout": "a polygon cut-out lies within the polygon's reach",
    "depends-on-refused": "an earlier polygon of the layer within this one's reach is refused",
    "copper-check": "the copper check finds a short or a clearance below the rule on the computed pour",
}
"""Why a polygon keeps its outline only (``altium.zone-unpoured``), a closed list."""

HYPOTHESES: tuple[str, ...] = (
    "H-A-POUR-OPEN",
    "H-A-POUR-REGION",
    "H-A-POUR-CLEARANCE",
    "H-A-POUR-CONNECT",
    "H-A-POUR-RELIEF",
    "H-A-POUR-OVER",
    "H-A-POUR-ORDER",
    "H-A-POUR-NECK",
    "H-A-POUR-STEPS",
    "H-A-POUR-ISLAND",
    "H-A-POUR-DEAD",
    "H-A-POUR-ARC",
    "H-A-POUR-VOIDROT",
    "H-A-POUR-KEEPOUT",
    "H-A-POUR-EDGE",
    "H-A-POUR-VIAPAD",
)
EVIDENCE: Final = Evidence(Level.INFERRED, hypotheses=HYPOTHESES)
"""Every computed pour is ``INFERRED`` until a K6 round of the kit settles its rows (Decision 10)."""

SQUARE_NM_PER_UNIT = Fraction(127, 50) ** 2
"""``AREATHRESHOLD`` is in square file units (input I12)."""
TOUCH_NM = 10
"""How near a piece must come to an object of its net to touch it (I13): a conductor ends on the pad's
copper, and Clipper rounds its vertices to the nanometre."""
POUR_OVER_STYLES: Mapping[str, Literal["none", "all", "polygons"]] = {
    "0": "none",
    "1": "all",
    "2": "polygons",
}
"""``POUROVERSTYLE`` → what of the polygon's own net the pour covers (I8; ``H-A-POUR-OVER``)."""
DEFAULT_CLASS = "Default"
ACUTE_COS, ACUTE_SCALE = 8_727, 1_000_000
"""``cos(89.5°)`` as a fraction: a convex corner whose cosine is above it, sharper than 89.5°, is cut by the
neck removal (``_Geometry.chord_cut``; I10); 90° itself, with its rounding, stays."""
KEEPOUT_FLAG = 2
"""The second flag byte of a keep-out primitive (``pcb-records.md``, "Regions and keep-outs")."""
KEEPOUT_LAYER = 56
"""The Keep-Out layer: a keep-out there keeps every copper layer."""
KEEPOUT_COPPER = 0x04
"""The restriction bit of copper (polygon pours) in ``KEEPOUTRESTRICTIONS`` (``pcbdoc.KEEPOUT_BITS``)."""
RULE_KINDS: Mapping[str, str] = {
    "track": "track",
    "arc": "track",
    "via": "via",
    "pad": "pad",
    "hole": "pad",
    "zone": "zone",
    "keepout": "keepout",
}
"""The item kind a rule sees for each object (``checks.clearance.ITEM_KINDS``; a hole is its pad's)."""


@dataclass(frozen=True, slots=True)
class PourReading:
    """A PCB document as the engine pours it: its records, its import, the pads of the import in the board
    frame (``frame.board_pads``) and the rings of its edge (``frame.board_edges``)."""

    document: PcbDocument
    design: Design
    pads: tuple[BoardPad, ...]
    edges: tuple[EdgeRing, ...] | None


def read_pour(data: bytes, *, file: str = "pour.PcbDoc") -> PourReading:
    """The ``PourReading`` of the document ``data``."""
    from fenolite.backends.altium import frame
    from fenolite.backends.altium.adapter.board import import_board

    document = read_pcbdoc(data, file=file)
    design = import_board(document, file=file, sha256=hashlib.sha256(data).hexdigest())
    return PourReading(document, design, frame.board_pads(design), frame.board_edges(design))


@dataclass(frozen=True, slots=True)
class PolygonPour:
    """The pour of the polygon at position ``index`` of ``Polygons6``: its layer and net, its pieces in the
    frame of the import (normal form, sorted), its ``ARCRESOLUTION`` in nanometres, and the reason it is
    refused (empty when it is poured; a refused polygon has no piece)."""

    index: int
    layer: str
    net: str | None
    pieces: tuple[Polygon, ...]
    arc_resolution: Nm
    reason: str = ""
    zone_id: str = ""

    @property
    def poured(self) -> bool:
        return not self.reason


@dataclass(frozen=True, slots=True)
class PourResult:
    """One ``PolygonPour`` per polygon of type ``Polygon`` on a copper layer, in record order."""

    polygons: tuple[PolygonPour, ...]
    evidence: Evidence = EVIDENCE

    def of(self, index: int) -> PolygonPour | None:
        return next((pour for pour in self.polygons if pour.index == index), None)


# --- the polygons -------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PourPolygon:
    index: int
    zone: Zone
    layer: str
    net: str | None
    pour_index: int
    remove_dead: bool
    islands: Fraction | None
    neck: Nm
    arc_resolution: Nm
    pour_over: Literal["none", "all", "polygons"]
    reason: str = ""
    name: str = ""

    @property
    def tol(self) -> int:
        """The arc tolerance of the offsets: a quarter of ``ARCRESOLUTION``, at least 50 nm."""
        return max(self.arc_resolution // 4, 50)

    @property
    def box(self) -> BBox:
        return BBox.of_points(self.zone.outline) if self.zone.outline else BBox(0, 0, 0, 0)


def polygons_of(reading: PourReading) -> list[PourPolygon]:
    board = reading.design.board
    if board is None:
        return []
    names = {net.id: net.name for net in reading.design.circuit.nets}
    found: list[PourPolygon] = []
    for zone in board.zones:
        locator = zone.provenance.locator if zone.provenance is not None else ""
        if not locator.startswith("Polygons6/Data#"):
            continue
        index = int(locator.rsplit("#", 1)[1])
        polygon = reading.document.polygons[index]
        get = polygon.record.get
        reason = ""
        if (get("HATCHSTYLE") or "Solid") != "Solid":
            reason = "hatched"
        elif (get("SHELVED") or "FALSE").upper() == "TRUE":
            reason = "shelved"
        elif not zone.outline:
            reason = "outline-arc"
        elif (get("LAYER") or "").upper().startswith("PLANE"):
            reason = "plane-layer"
        arc = parse_length(get("ARCRESOLUTION") or "")
        necks = (get("REMOVENECKS") or "").upper() == "TRUE"
        neck = parse_length(get("NECKWIDTHTHRESHOLD") or "") if necks else 0
        style = POUR_OVER_STYLES.get(get("POUROVERSTYLE") or "")
        islands: Fraction | None = None
        if (get("REMOVEISLANDSBYAREA") or "").upper() == "TRUE":
            try:
                islands = Fraction(get("AREATHRESHOLD") or "") * SQUARE_NM_PER_UNIT
            except (ValueError, ZeroDivisionError):
                reason = reason or "threshold"
        if not reason and (arc is None or arc <= 0 or neck is None or neck < 0):
            reason = "threshold"
        if not reason and style is None:
            reason = "pour-over"
        found.append(
            PourPolygon(
                index=index,
                zone=zone,
                layer=zone.layers[0],
                net=names.get(zone.net_id) if zone.net_id is not None else None,
                pour_index=polygon.pour_index or 0,
                remove_dead=(get("REMOVEDEAD") or "").upper() == "TRUE",
                islands=islands,
                neck=neck or 0,
                arc_resolution=max(arc or 1, 1),
                pour_over=style or "all",
                reason=reason,
                name=polygon.name,
            )
        )
    return sorted(found, key=lambda p: p.index)


# --- objects on a layer -------------------------------------------------------------------------------------

_Core = tuple[tuple[Point, ...], int, bool]
"""A copper shape as the copper check holds it: a core, a width and whether the core is a filled ring."""
ObjectType = Literal["track", "arc", "via", "pad", "hole", "keepout"]


@dataclass(frozen=True, slots=True)
class PourObject:
    kind: ObjectType
    net: str | None
    netclass: str
    ref: str | None
    shape: _Core
    box: BBox
    entity_id: str
    connect: ObjectKind | None = None
    """For a pad or a via: the object kind of its Polygon Connect Style setting."""
    center: Point | None = None
    rotation: int = 0


def _box(core: Sequence[Point], width: int) -> BBox:
    return BBox.of_points(core).inflate((width + 1) // 2)


def _span(names: Sequence[str], layers: Sequence[str], through: bool) -> tuple[str, ...]:
    if through or len(layers) != 2 or layers[0] not in names or layers[1] not in names:
        return tuple(names)
    first, last = sorted((names.index(layers[0]), names.index(layers[1])))
    return tuple(names[first : last + 1])


def _slot_core(position: Point, length: Nm, drill: Nm, rotation: int) -> tuple[Point, ...]:
    half = (length - drill) // 2
    a = rotate_point(Point(-half, 0), rotation)
    b = rotate_point(Point(half, 0), rotation)
    return (Point(position.x + a.x, position.y + a.y), Point(position.x + b.x, position.y + b.y))


class LayerObjects:
    """The objects of the board per copper layer (I18, I19, I16), and per layer the boxes of what the
    engine does not shape (I20)."""

    def __init__(self, reading: PourReading, tol: int) -> None:
        from fenolite.backends.altium.backend import removed_pad_vias

        design = removed_pad_vias(reading.design)
        board = design.board
        assert board is not None
        self.board: Board = board
        self.copper = tuple(layer.name for layer in board.layers if layer.kind == "copper")
        circuit = design.circuit
        classes = {c.id: c.name for c in circuit.netclasses}
        self.netclass: dict[str | None, str] = {None: DEFAULT_CLASS}
        names: dict[str, str] = {}
        for net in circuit.nets:
            names[net.id] = net.name
            self.netclass[net.name] = classes.get(net.netclass_id or "", DEFAULT_CLASS)
        self.by_layer: dict[str, list[PourObject]] = {name: [] for name in self.copper}
        self.unshaped: dict[str, list[tuple[BBox, str]]] = {name: [] for name in self.copper}
        self.keepout_regions: set[str] = set()
        """The locators of the records that are shaped here although the import makes graphics of them: the
        keep-out regions (``_keepout_regions``) and the copper of ``_copper_records``."""
        self.layer_names: dict[int, str] = {}
        """Altium layer id → the name of the copper layer of the import."""
        for layer in board.layers:
            pairs = dict(layer.ext["altium"].payload) if "altium" in layer.ext else {}
            ident = pairs.get("layer_id", "")
            if layer.kind == "copper" and ident.isdecimal():
                self.layer_names[int(ident)] = layer.name
        self._names = names
        self._tracks(board, tol)
        self._vias(board)
        self._pads(reading.pads)
        self._holes_and_keepouts(board)
        self._keepout_regions(reading)
        self._copper_records(reading, tol)
        self._unshaped(board)
        for items in self.by_layer.values():
            items.sort(key=lambda o: (o.kind, o.entity_id, o.box.as_tuple()))

    def _net(self, net_id: str | None) -> str | None:
        return self._names.get(net_id) if net_id is not None else None

    def _add(self, layer: str, item: PourObject) -> None:
        if layer in self.by_layer:
            self.by_layer[layer].append(item)

    def _object(
        self,
        kind: ObjectType,
        net: str | None,
        shape: _Core,
        ident: str,
        *,
        ref: str | None = None,
        connect: ObjectKind | None = None,
        center: Point | None = None,
        rotation: int = 0,
    ) -> PourObject:
        core, width, _ = shape
        netclass = self.netclass.get(net, DEFAULT_CLASS)
        return PourObject(
            kind, net, netclass, ref, shape, _box(core, width), ident, connect, center, rotation
        )

    def _tracks(self, board: Board, tol: int) -> None:
        for track in board.tracks:
            shape = ((track.start, track.end), track.width, False)
            self._add(track.layer, self._object("track", self._net(track.net_id), shape, track.id))
        sag = max(tol // 2, 1)
        for arc in board.arcs:
            try:
                core = GeoArc(arc.start, arc.mid, arc.end).polygonize(sag)
            except (GeometryError, ValueError):
                if arc.layer in self.unshaped:
                    self.unshaped[arc.layer].append((_box((arc.start, arc.mid, arc.end), arc.width), arc.id))
                continue
            # the chords of the polygonised centre line lie inside the arc: widen by their sag on each side
            shape = (core, arc.width + 2 * sag, False)
            self._add(arc.layer, self._object("arc", self._net(arc.net_id), shape, arc.id))

    def _vias(self, board: Board) -> None:
        for via in board.vias:
            net = self._net(via.net_id)
            shape = ((via.position,), via.diameter, False)
            # a via without a pad shape on a layer is its hole there (c0132, ``removed_pad_vias``): a polygon
            # keeps its clearance to the hole and does not join it (``H-A-IMP-VIA-PADLESS``)
            hole = via.diameter == via.drill
            for layer in _span(self.copper, via.layers, via.via_type == "through"):
                if hole:
                    self._add(layer, self._object("hole", net, shape, via.id))
                else:
                    self._add(
                        layer, self._object("via", net, shape, via.id, connect="via", center=via.position)
                    )

    def _pads(self, pads: Sequence[BoardPad]) -> None:
        kinds: dict[str, ObjectKind] = {"thru_hole": "th_pad", "smd": "smd_pad"}
        for pad in pads:
            kind = kinds.get(pad.kind)
            ref = pad.ref or None
            on = {entry.layer for entry in pad.copper}
            for entry in pad.copper:
                shape = (entry.core, entry.width, entry.filled)
                item = self._object(
                    "pad", pad.net, shape, pad.pad_id, ref=ref, connect=kind, center=pad.position,
                    rotation=pad.rotation,
                )  # fmt: skip
                self._add(entry.layer, item)
            if pad.hole and pad.drill and pad.kind != "smd":
                net = pad.net if pad.kind == "thru_hole" else None
                for layer in self.copper:
                    if layer not in on:
                        shape = (pad.hole, pad.drill, False)
                        self._add(layer, self._object("hole", net, shape, pad.pad_id, ref=ref))
            elif not pad.copper and pad.kind != "np_thru_hole":
                for layer in pad.layers:
                    if layer in self.unshaped:
                        self.unshaped[layer].append((BBox.of_points((pad.position,)).inflate(1), "pad"))

    def _holes_and_keepouts(self, board: Board) -> None:
        for hole in board.holes:
            core = (
                (hole.position,)
                if hole.length is None
                else _slot_core(hole.position, hole.length, hole.drill, hole.rotation)
            )
            for layer in self.copper:
                self._add(layer, self._object("hole", None, (core, hole.drill, False), hole.id))
        for keepout in board.keepouts:
            if not keepout.no_copper_pour or len(keepout.outline) < 3:
                continue
            for layer in keepout.layers or self.copper:
                self._add(layer, self._object("keepout", None, (tuple(keepout.outline), 0, True), keepout.id))

    def _keepout_regions(self, reading: PourReading) -> None:
        """The keep-out regions of the document's records (I16): a region whose second flag byte is 2 and
        whose ``KEEPOUTRESTRICTIONS`` hold the copper bit (``0x04``), on a copper layer or on the Keep-Out
        layer, which keeps every copper layer. The import makes a filled graphic of such a region; those
        graphics are shaped here and are no unshaped copper."""
        from fenolite.backends.altium.adapter.units import pcb_point

        names = self.layer_names
        for index, region in enumerate(reading.document.regions):
            if isinstance(region, RegionRecord) and region.properties.get("KIND") == "1":
                self.keepout_regions.add(f"Regions6/Data#{index}")  # a polygon cut-out: ``polygon-cutout``
                continue
            if not isinstance(region, RegionRecord) or region.prefix.flags2 != KEEPOUT_FLAG:
                continue
            self.keepout_regions.add(f"Regions6/Data#{index}")
            restrictions = region.properties.get("KEEPOUTRESTRICTIONS") or "0"
            if not restrictions.isdecimal() or not int(restrictions) & KEEPOUT_COPPER:
                continue
            layers = (
                self.copper if region.prefix.layer == KEEPOUT_LAYER else (names.get(region.prefix.layer),)
            )
            points = tuple(pcb_point(round(v.x), round(v.y)) for v in region.outline)
            if len(points) < 3:
                continue
            for layer in layers:
                if layer is not None:
                    shape = (points, 0, True)
                    self._add(layer, self._object("keepout", None, shape, f"keepout:{index}"))

    def _copper_records(self, reading: PourReading, tol: int) -> None:
        """The copper that the import keeps as graphics, shaped from its records with the net of their
        prefix (I18): the tracks and arcs of components, every fill, and the free copper regions (``KIND=0``,
        no keep-out, no board cut-out, no polygon). A region is its outline: its holes are left filled, so
        its void is never too small."""
        from fenolite.backends.altium.adapter import units
        from fenolite.backends.altium.adapter.copper import is_board_cutout
        from fenolite.backends.altium.read.pcbprims import ArcRecord, FillRecord, TrackRecord
        from fenolite.core.trig import FULL_TURN

        document = reading.document
        sag = max(tol // 2, 1)

        def net(index: int | None) -> str | None:
            return document.net_name(index)

        def owned(
            storage: str, index: int, layer_id: int, kind: ObjectType, shape: _Core, net_index: int | None
        ) -> None:
            layer = self.layer_names.get(layer_id)
            if layer is None:
                return
            self.keepout_regions.add(f"{storage}/Data#{index}")
            self._add(layer, self._object(kind, net(net_index), shape, f"{storage}:{index}"))

        for index, item in enumerate(document.tracks):
            if (
                isinstance(item, TrackRecord)
                and item.prefix.component is not None
                and item.prefix.polygon is None
            ):
                core = (units.pcb_point(item.x1, item.y1), units.pcb_point(item.x2, item.y2))
                shape = (core, units.pcb_length(item.width), False)
                owned("Tracks6", index, item.prefix.layer, "track", shape, item.prefix.net)
        for index, item in enumerate(document.arcs):
            if (
                not isinstance(item, ArcRecord)
                or item.prefix.component is None
                or item.prefix.polygon is not None
            ):
                continue
            start, _ = units.angle(item.start_angle)
            end, _ = units.angle(item.end_angle)
            try:
                if units.sweep(start, end) == FULL_TURN:
                    first = units.arc_points(item.cx, item.cy, item.radius, 0, FULL_TURN // 2)
                    second = units.arc_points(item.cx, item.cy, item.radius, FULL_TURN // 2, 0)
                    core = (*GeoArc(*first).polygonize(sag), *GeoArc(*second).polygonize(sag)[1:])
                else:
                    core = GeoArc(*units.arc_points(item.cx, item.cy, item.radius, start, end)).polygonize(
                        sag
                    )
            except (GeometryError, ValueError):
                continue
            width = units.pcb_length(item.width) + 2 * sag
            owned("Arcs6", index, item.prefix.layer, "arc", (core, width, False), item.prefix.net)
        for index, item in enumerate(document.fills):
            if not isinstance(item, FillRecord) or item.prefix.polygon is not None:
                continue
            a, b = units.pcb_point(item.x1, item.y1), units.pcb_point(item.x2, item.y2)
            rotation, _ = units.angle(item.rotation)
            corners = (a, Point(b.x, a.y), b, Point(a.x, b.y))
            if rotation not in (0, FULL_TURN // 2):
                cx2, cy2 = a.x + b.x, a.y + b.y
                corners = tuple(
                    Point((m.x + cx2) // 2, (m.y + cy2) // 2)
                    for m in (rotate_point(Point(2 * c.x - cx2, 2 * c.y - cy2), rotation) for c in corners)
                )
            try:
                Polygon(corners)
            except GeometryError:
                continue
            owned("Fills6", index, item.prefix.layer, "track", (corners, 0, True), item.prefix.net)
        for index, region in enumerate(document.regions):
            if not isinstance(region, RegionRecord) or region.prefix.polygon is not None:
                continue
            if region.prefix.flags2 == KEEPOUT_FLAG or is_board_cutout(region):
                continue
            if (region.properties.get("KIND") or "0") != "0":
                continue
            points: list[Point] = []
            for vertex in region.outline:
                point = units.pcb_point(round(vertex.x), round(vertex.y))
                if not points or points[-1] != point:
                    points.append(point)
            while len(points) > 1 and points[0] == points[-1]:
                points.pop()
            try:
                Polygon(tuple(points))
            except GeometryError:
                continue
            owned(
                "Regions6", index, region.prefix.layer, "track", (tuple(points), 0, True), region.prefix.net
            )

    def _unshaped(self, board: Board) -> None:
        texts = [*board.texts, *(t for fp in board.footprints for t in fp.texts)]
        for text in texts:
            if text.layer in self.unshaped:
                reach = 4 * max(text.size.w, text.size.h) + 1
                self.unshaped[text.layer].append((BBox.of_points((text.position,)).inflate(reach), "text"))
        graphics = [*board.graphics, *(g for fp in board.footprints for g in fp.graphics)]
        for graphic in graphics:
            locator = graphic.provenance.locator if graphic.provenance is not None else ""
            if locator in self.keepout_regions:
                continue
            if graphic.layer in self.unshaped and graphic.points:
                self.unshaped[graphic.layer].append((_box(graphic.points, graphic.width), "graphic"))


# --- rules --------------------------------------------------------------------------------------------------


def _fold(selector: Selector) -> Selector:
    if selector.op in LEAF_OPS and selector.op not in ("area", "diff_pair"):
        return replace(selector, value=selector.value.casefold())
    if selector.items:
        return replace(selector, items=tuple(_fold(item) for item in selector.items))
    return selector


def _fold_subject(subject: RuleSubject) -> RuleSubject:
    def fold(text: str | None) -> str | None:
        return None if text is None else text.casefold()

    return replace(
        subject,
        item_kind=subject.item_kind.casefold(),
        net=fold(subject.net),
        netclass=fold(subject.netclass),
        ref=fold(subject.ref),
        layer=fold(subject.layer),
    )


def _precedence(rules: Sequence[Rule]) -> list[Rule]:
    """The rules, the governing one first: the reverse of ``checks.clearance.rule_precedence``."""
    ordered = sorted(rules, key=lambda r: (r.priority != 0, -r.priority, r.name, r.id))
    return list(reversed(ordered))


@dataclass(frozen=True, slots=True)
class _Candidate:
    rule: Rule
    first: Selector
    second: Selector | None
    layers: frozenset[str]

    def matches(self, a: RuleSubject, b: RuleSubject) -> bool:
        if self.layers and a.layer not in self.layers:
            return False
        if self.second is None:
            return self.first.matches(a) or self.first.matches(b)
        return (self.first.matches(a) and self.second.matches(b)) or (
            self.first.matches(b) and self.second.matches(a)
        )

    def matches_one(self, a: RuleSubject) -> bool:
        if self.layers and a.layer not in self.layers:
            return False
        return self.first.matches(a)


_POLYGON_QUERY = re.compile(r"\s*(?:InPolygon|InPoly|IsNamedPolygon)\s*\(\s*'([^']*)'\s*\)\s*", re.IGNORECASE)


def _polygon_only(first: str | None, second: str | None) -> str | None:
    """The name of the one polygon that a record scoped ``InPolygon('<name>')`` (or ``InPoly``,
    ``IsNamedPolygon``) on one side and a scope of the closed grammar on the other can govern (input I3);
    ``None`` for any other pair of scopes, which may govern every polygon."""
    from fenolite.backends.altium.read.scope import parse_scope

    for one, other in ((first or "", second or ""), (second or "", first or "")):
        match = _POLYGON_QUERY.fullmatch(one)
        if match is not None and isinstance(parse_scope(other), Selector):
            return match.group(1)
    return None


class Clearances:
    """The governing Clearance between a polygon and an object of a reading (I2), and the governing Board
    Outline Clearance of a polygon (I17), resolved from the neutral rules of the import as the copper check
    resolves them for an Altium reading. A Clearance record that the import does not map and that comes
    before the governing rule (or any such record when no rule governs) leaves the pair undetermined."""

    def __init__(self, reading: PourReading) -> None:
        from fenolite.backends.altium.adapter.layers import copper_layers_of
        from fenolite.backends.altium.read.rules import NOT_APPLYING, map_rules

        design = reading.design
        rules = design.rules.rules if design.rules is not None else ()

        def candidates(kind: str) -> list[_Candidate]:
            return [
                _Candidate(
                    rule,
                    _fold(rule.selector_a),
                    None if rule.selector_b is None else _fold(rule.selector_b),
                    frozenset(layer.casefold() for layer in rule.layers),
                )
                for rule in _precedence([r for r in rules if r.kind == kind and r.min is not None])
            ]

        self._clearance = candidates("clearance")
        self._edge = candidates("edge_clearance")
        self.largest: Nm = max((c.rule.min or 0 for c in self._clearance), default=0)
        """The largest clearance a rule of the reading gives."""
        board = design.board
        layers = copper_layers_of(board.layers) if board is not None else None
        mapping = map_rules(
            [record.fields for record in reading.document.rules], origin="pour", layers=layers
        )
        records = reading.document.rules
        self._unmapped: list[tuple[int, str, str | None]] = []
        """(priority, reason, the one polygon it can govern or ``None`` for any) of each unread record."""
        for record in mapping.unmapped:
            if record.kind != "Clearance" or record.reason in NOT_APPLYING:
                continue
            found = records[record.index] if 0 <= record.index < len(records) else None
            priority = found.priority if found is not None else None
            only = (
                _polygon_only(found.record.get("SCOPE1EXPRESSION"), found.record.get("SCOPE2EXPRESSION"))
                if (found is not None)
                else None
            )
            self._unmapped.append((priority or 0, record.reason, only))
        self._memo: dict[tuple[RuleSubject, RuleSubject, tuple[str, ...]], Nm | str] = {}

    def _before(self, rule: Rule | None, polygons: tuple[str, ...]) -> str:
        """The refusal when an unread Clearance record that can govern a pair with the copper of one of the
        polygons named ``polygons`` comes before ``rule`` (any of them for ``None``)."""
        names = {name.casefold() for name in polygons}
        for priority, reason, only in self._unmapped:
            if only is not None and only.casefold() not in names:
                continue
            if rule is None or priority == 0 or priority <= rule.priority:
                return "rule-scope" if reason == "scope" else "rule-unmapped"
        return ""

    def clearance(self, a: RuleSubject, b: RuleSubject, *, polygons: tuple[str, ...] = ()) -> Nm | str:
        """The governing clearance between ``a`` and ``b`` on ``a.layer``, or the reason it is unknown;
        ``polygons`` are the names of the polygons whose copper the pair holds (input I3)."""
        key = (a, b, polygons)
        found = self._memo.get(key)
        if found is None:
            fa, fb = _fold_subject(a), _fold_subject(b)
            rule = next((c.rule for c in self._clearance if c.matches(fa, fb)), None)
            reason = self._before(rule, polygons)
            if reason:
                found = reason
            elif rule is None or rule.severity == "ignore" or rule.min is None:
                found = "no-clearance"
            else:
                found = rule.min
            self._memo[key] = found
            self._memo[(b, a, polygons)] = found
        return found

    def edge(self, a: RuleSubject) -> Nm:
        """The governing Board Outline Clearance of ``a``, 0 when none governs."""
        fa = _fold_subject(a)
        rule = next((c.rule for c in self._edge if c.matches_one(fa)), None)
        if rule is None or rule.severity == "ignore" or rule.min is None:
            return 0
        return rule.min


# --- geometry -----------------------------------------------------------------------------------------------


DISC_STEPS = (8, 16, 32, 64, 128, 256, 512, 1280, 2560)
"""The vertex counts of a ``disc``: each divides a full turn of 360 000 000 µdeg."""


def disc(center: Point, radius: int, tol: int) -> Polygon:
    """A regular polygon around the circle of ``radius`` about ``center`` whose every edge lies outside the
    circle and at most ``tol`` from it (the last count of ``DISC_STEPS`` past ``tol``): its vertices on the
    circle of ``radius / cos(π/n)``, rounded away from the centre. Integer arithmetic only, through the
    fixed-point table of ``core.trig``, so the polygon is the same on every platform."""
    from fenolite.core.trig import FULL_TURN, ONE, cos_sin_fixed

    if radius <= 0:
        raise ValueError(f"a disc needs a radius of at least 1 nm, got {radius}")
    steps = DISC_STEPS[-1]
    outer = radius
    for count in DISC_STEPS:
        cos, _ = cos_sin_fixed(FULL_TURN // (2 * count))
        outer = -(-radius * ONE // cos) + 2  # radius / cos(π/n), up, with 2 nm for the rounding below
        if (outer * (ONE - cos) + ONE - 1) // ONE <= tol:
            steps = count
            break
    points: list[Point] = []
    for k in range(steps):
        cos, sin = cos_sin_fixed(k * (FULL_TURN // steps))
        dx, dy = outer * cos, outer * sin
        x = -(-dx // ONE) if dx > 0 else dx // ONE
        y = -(-dy // ONE) if dy > 0 else dy // ONE
        points.append(Point(center.x + x, center.y + y))
    return Polygon(tuple(points))


class _Geometry:
    def __init__(self, backend: ClipperBackend) -> None:
        self.backend = backend

    def offset(self, polys: Sequence[Polygon], delta: int, tol: int) -> tuple[Polygon, ...]:
        """``polys`` offset by ``delta`` with round joins whose chords lie within ``tol / 2`` of their arcs:
        Clipper's last chord of a join can span up to twice its step, so its arc tolerance is ``tol / 8``."""
        if not polys:
            return ()
        return self.backend.offset(polys, delta, join="round", tol=max(tol // 8, 10))

    def grow(self, shape: _Core, by: int, tol: int) -> tuple[Polygon, ...]:
        """The points within ``width / 2 + by`` of the core, every curve kept outside the true one: a point
        core is a ``disc``; an open polyline or a ring is offset by ``tol + 1`` more than its reach."""
        core, width, filled = shape
        reach = (width + 1) // 2 + by
        if filled:
            ring = Polygon(core)
            if reach <= 0:
                return (ring,)
            if width == 0:
                # a sharp ring (a rectangular pad, a fill, a region): its void keeps square corners, as the
                # saved pours of the public corpus show (I2; ``H-A-POUR-CLEARANCE``), a superset of the round
                # one; a miter of a corner sharper than 60° is squared off at twice the reach
                return self.backend.offset(
                    (ring,), reach + 1, join="miter", tol=max(tol // 8, 10), miter_limit=2
                )
            return self.offset((ring,), reach + tol + 1, tol)
        if reach <= 0:
            return ()
        if len(set(core)) == 1:
            return (disc(core[0], reach, tol),)
        return self.backend.stroke([core], reach + tol + 1, tol=max(tol // 8, 10))

    def open(self, polys: Sequence[Polygon], width: int, tol: int) -> tuple[Polygon, ...]:
        """The neck removal of I10 (``H-A-POUR-NECK``), as the saved pours of the public corpus show it: the
        copper that a round opening by a disc of diameter ``width`` removes, piece by piece. A piece at a
        convex corner sharper than 89.5° goes with its convex hull, so the tip is cut by the chord between
        the ends of the opening's arc (the saved pours hold no convex corner below 75° and only 16 between
        75° and 89.9° among 2853); the sliver the opening takes off a corner of 89.5° or more (within half
        the width of it) comes back, so the corner stays sharp; every other piece is a neck and stays
        removed. The result is cut back to
        ``polys``: nothing grows."""
        half = width // 2
        if half <= 0 or not polys:
            return tuple(polys)
        eroded = self.offset(polys, -half, tol)
        rounded = self.meet(self.offset(eroded, half, tol), polys) if eroded else ()
        removed = self.minus(polys, rounded)
        if not removed:
            return tuple(polys)
        corners = _convex_corners(polys, half)
        cut: list[Polygon] = []  # the necks and the hulls of the tips; Clipper's difference unites them
        for piece in removed:
            found = [(v, corners[v]) for v in piece.outer if v in corners]
            tips = [(v, reach) for v, reach in found if reach]
            for apex, reach in tips:
                # the tip only: the part of the piece within the reach of the opening's arc at this corner
                local = self.meet((piece,), (disc(apex, reach * 3 // 2 + half, tol),))
                points = [q for poly in local for q in poly.outer]
                hull = convex_hull(points) if points else ()
                if len(hull) >= 3:
                    cut.append(Polygon(hull))
            box = piece.bbox()
            if found and not tips and max(box.width, box.height) <= half + tol:
                continue  # the sliver the round opening takes off a corner of 89.5° or more stays
            cut.append(piece)
        return _without_debris(self.minus(polys, cut), tol) if cut else tuple(polys)

    def union(self, polys: Sequence[Polygon]) -> tuple[Polygon, ...]:
        return self.backend.union(polys) if polys else ()

    def minus(self, a: Sequence[Polygon], b: Sequence[Polygon]) -> tuple[Polygon, ...]:
        if not a:
            return ()
        return self.backend.difference(a, b) if b else tuple(a)

    def meet(self, a: Sequence[Polygon], b: Sequence[Polygon]) -> tuple[Polygon, ...]:
        if not a or not b:
            return ()
        return self.backend.intersection(a, b)


def _without_debris(polys: Sequence[Polygon], tol: int) -> tuple[Polygon, ...]:
    """``polys`` without the pieces and the holes smaller than ``tol²``: a difference whose clip shares edges
    with its subject leaves hairline slivers of Clipper's rounding along them. Removing a sliver of copper is
    always safe; filling a hairline hole joins copper that was already one piece."""
    floor = tol * tol
    kept: list[Polygon] = []
    for poly in polys:
        if area(poly) < floor:
            continue
        holes = tuple(hole for hole in poly.holes if abs(area2(hole)) >= 2 * floor)
        kept.append(poly if len(holes) == len(poly.holes) else Polygon(poly.outer, holes))
    return tuple(kept)


def _convex_corners(polys: Sequence[Polygon], radius: int) -> dict[Point, int]:
    """The convex corners of the copper ``polys`` (on the left of each ring in normal form), each with the
    distance from the corner to where a circle of ``radius`` inscribed in it touches its edges,
    ``radius / tan(α/2)``, for a corner sharper than 89.5° (``ACUTE_COS``), else 0."""
    found: dict[Point, int] = {}
    for poly in polys:
        for ring in poly.rings():
            count = len(ring)
            for i in range(count):
                apex, before, after = ring[i], ring[i - 1], ring[(i + 1) % count]
                v1 = (before.x - apex.x, before.y - apex.y)
                v2 = (after.x - apex.x, after.y - apex.y)
                cross = v1[0] * v2[1] - v1[1] * v2[0]
                if cross >= 0:
                    continue
                dot = v1[0] * v2[0] + v1[1] * v2[1]
                l1 = floor_sqrt(v1[0] * v1[0] + v1[1] * v1[1])
                l2 = floor_sqrt(v2[0] * v2[0] + v2[1] * v2[1])
                acute = dot * ACUTE_SCALE > ACUTE_COS * l1 * l2
                found[apex] = -(-radius * (l1 * l2 + dot) // -cross) if acute else 0
    return found


def area(poly: Polygon) -> Fraction:
    """The area of ``poly`` less its holes, in square nanometres."""
    return Fraction(abs(area2(poly.outer)) - sum(abs(area2(hole)) for hole in poly.holes), 2)


def _board_area(reading: PourReading, geometry: _Geometry, tol: int) -> tuple[Polygon, ...] | None:
    """The board shape of I17: the edge's first ring less the others; arcs as chords, a cut-out grown by
    ``tol`` so that no pour enters it."""
    edges = reading.edges
    if not edges:
        return None
    rings: list[tuple[Point, ...]] = []
    for ring in edges:
        points: list[Point] = []
        for i, start in enumerate(ring.points):
            mid = ring.mids[i]
            if mid is None:
                points.append(start)
            else:
                end = ring.points[(i + 1) % len(ring.points)]
                points.extend(GeoArc(start, mid, end).polygonize(max(tol, 1))[:-1])
        rings.append(tuple(points))
    try:
        outer = Polygon(rings[0])
    except GeometryError:
        return None
    holes: list[Polygon] = []
    for ring in rings[1:]:
        try:
            holes.extend(geometry.offset((Polygon(ring),), tol + 1, tol))
        except GeometryError:
            continue
    return geometry.minus((outer,), holes)


def rule_subject(
    layer: str, kind: str, net: str | None, netclass: str, ref: str | None = None
) -> RuleSubject:
    return RuleSubject(item_kind=RULE_KINDS[kind], net=net, netclass=netclass, ref=ref, layer=layer)


def _bar(center: Point, angle: int, length: int, width: int) -> Polygon:
    """The rectangle of a relief conductor from ``center`` along ``angle``, ``length`` long, ``width``
    wide."""
    half = (width + 1) // 2
    corners = (Point(0, -half), Point(length, -half), Point(length, half), Point(0, half))
    turned = (rotate_point(corner, angle) for corner in corners)
    return Polygon(tuple(Point(center.x + p.x, center.y + p.y) for p in turned))


@dataclass(slots=True)
class _Layer:
    poured: list[tuple[PourPolygon, tuple[Polygon, ...]]] = field(default_factory=lambda: [])
    refused: list[PourPolygon] = field(default_factory=lambda: [])


@dataclass(frozen=True, slots=True)
class _Context:
    geometry: _Geometry
    objects: LayerObjects
    rules: Clearances
    styles: tuple[ConnectStyle, ...]
    cutouts: Mapping[str, tuple[BBox, ...]]
    board: tuple[Polygon, ...]
    reach: Nm
    """How far beyond a polygon's outline an object can shape its pour: the largest clearance, air gap
    and conductor width of the reading."""


def pour_reading(
    reading: PourReading,
    *,
    backend: ClipperBackend | None = None,
    refuse: Mapping[int, str] | None = None,
) -> PourResult:
    """The pour of every polygon of ``reading`` (capability altium-pour, "Pour engine"). ``refuse`` maps a
    polygon index to a reason that refuses it before it is poured (the self-check of the writer)."""
    polygons = polygons_of(reading)
    if not polygons:
        return PourResult(())
    geometry = _Geometry(backend if backend is not None else ClipperBackend())
    forced = dict(refuse or {})
    tol = min(p.tol for p in polygons)
    objects = LayerObjects(reading, tol)
    rules = Clearances(reading)
    styles = read_connect_styles([record.fields for record in reading.document.rules])
    board = _board_area(reading, geometry, tol)
    widest = max(
        (
            c.air_gap + c.conductor_width
            for s in styles
            for c in (s.th_pad, s.smd_pad, s.via)
            if c is not None
        ),
        default=0,
    )
    context = _Context(
        geometry,
        objects,
        rules,
        styles,
        _polygon_cutouts(reading),
        board or (),
        rules.largest + widest + tol + 1,
    )
    layers: dict[str, _Layer] = {}
    out: dict[int, PolygonPour] = {}
    for polygon in sorted(polygons, key=lambda p: (p.pour_index, p.index)):
        state = layers.setdefault(polygon.layer, _Layer())
        reason = polygon.reason or forced.get(polygon.index, "")
        if not reason and board is None:
            reason = "no-board"
        if not reason:
            reason = _depends(polygon, state, context)
        pieces: tuple[Polygon, ...] = ()
        if not reason:
            pieces, reason = _pour(polygon, state, context)
        if reason:
            pieces = ()
            state.refused.append(polygon)
        else:
            state.poured.append((polygon, pieces))
        out[polygon.index] = PolygonPour(
            polygon.index,
            polygon.layer,
            polygon.net,
            _sorted(pieces),
            polygon.arc_resolution,
            reason,
            polygon.zone.id,
        )
    return PourResult(tuple(out[index] for index in sorted(out)))


def _sorted(pieces: Sequence[Polygon]) -> tuple[Polygon, ...]:
    """The pieces by their lowest point in the file's frame (the largest Y here), then the leftmost."""

    def key(poly: Polygon) -> tuple[int, int]:
        low = max(poly.outer, key=lambda p: (p.y, -p.x))
        return (-low.y, low.x)

    return tuple(sorted(pieces, key=key))


def _depends(polygon: PourPolygon, state: _Layer, context: _Context) -> str:
    """``depends-on-refused`` when an earlier refused polygon of the layer lies within this one's reach."""
    reach = polygon.box.inflate(context.reach)
    for other in state.refused:
        if other.zone.outline and other.box.intersects(reach):
            return "depends-on-refused"
    return ""


def _polygon_cutouts(reading: PourReading) -> Mapping[str, tuple[BBox, ...]]:
    """The boxes of the polygon cut-outs (regions of ``KIND=1``) per copper layer of the import."""
    from fenolite.backends.altium.adapter.units import pcb_point

    board = reading.design.board
    layer_names: dict[int, str] = {}
    if board is not None:
        for layer in board.layers:
            pairs = dict(layer.ext["altium"].payload) if "altium" in layer.ext else {}
            ident = pairs.get("layer_id", "")
            if ident.isdecimal():
                layer_names[int(ident)] = layer.name
    found: dict[str, list[BBox]] = {}
    for region in reading.document.regions:
        if not isinstance(region, RegionRecord) or region.properties.get("KIND") != "1":
            continue
        name = layer_names.get(region.prefix.layer)
        points = [pcb_point(round(v.x), round(v.y)) for v in region.outline]
        if name is not None and points:
            found.setdefault(name, []).append(BBox.of_points(points))
    return {name: tuple(boxes) for name, boxes in found.items()}


def _pour(polygon: PourPolygon, state: _Layer, context: _Context) -> tuple[tuple[Polygon, ...], str]:
    """The pieces of one polygon, or the reason it is refused (I1 to I21, in the order of I11)."""
    geometry, objects, rules = context.geometry, context.objects, context.rules
    layer, net, tol = polygon.layer, polygon.net, polygon.tol
    me = rule_subject(layer, "zone", net, objects.netclass.get(net, DEFAULT_CLASS))
    reach = polygon.box.inflate(context.reach + polygon.neck)
    for box, _what in objects.unshaped.get(layer, []):
        if box.intersects(reach):
            return (), "unshaped-pad" if _what == "pad" else "unshaped-copper"
    if any(box.intersects(reach) for box in context.cutouts.get(layer, ())):
        return (), "polygon-cutout"
    try:
        area_now = geometry.meet((Polygon(polygon.zone.outline),), context.board)
    except GeometryError:
        return (), "outline"
    edge = rules.edge(me)
    if edge > 0:
        inner = geometry.offset(context.board, -(edge + tol + 1), tol)
        area_now = geometry.meet(area_now, inner)
    voids: list[Polygon] = []
    joins: list[tuple[PourObject, Connection]] = []
    same: list[PourObject] = []
    for item in objects.by_layer.get(layer, []):
        if not item.box.intersects(reach):
            continue
        subject = rule_subject(layer, item.kind, item.net, item.netclass, item.ref)
        own = net is not None and item.net == net
        if own and item.kind in ("via", "pad") and item.connect is not None:
            found = governing_connection(context.styles, subject, me, item.connect)
            if isinstance(found, str):
                return (), found
            joins.append((item, found))
            same.append(item)
            continue
        if own and item.kind in ("track", "arc"):
            same.append(item)
            if polygon.pour_over == "all":
                continue
        value = rules.clearance(me, subject, polygons=(polygon.name,))
        if isinstance(value, str):
            return (), value
        voids.extend(geometry.grow(item.shape, value, tol))
    for other, pieces in state.poured:
        if not pieces or not other.box.intersects(reach):
            continue
        if net is not None and other.net == net and polygon.pour_over != "none":
            continue
        them = rule_subject(layer, "zone", other.net, objects.netclass.get(other.net, DEFAULT_CLASS))
        value = rules.clearance(me, them, polygons=(polygon.name, other.name))
        if isinstance(value, str):
            return (), value
        voids.extend(geometry.offset(pieces, value + tol + 1, tol))
    forbidden = geometry.union(voids)
    gaps = [
        g
        for item, join in joins
        if join.style in ("relief", "none")
        for g in geometry.grow(item.shape, join.air_gap, tol)
    ]
    copper = geometry.minus(area_now, geometry.union([*forbidden, *gaps]))
    if polygon.neck > 0 and copper:
        # the result is cut back to the copper it was made from: the chords of Clipper's offsets would grow
        # it by their sag, and no void may lose its clearance
        copper = geometry.open(copper, polygon.neck, tol)
    conductors = _conductors(joins, copper, forbidden, area_now, geometry, tol)
    if conductors:
        copper = geometry.union([*copper, *conductors])
    pieces = list(copper)
    if polygon.islands is not None:
        pieces = [piece for piece in pieces if area(piece) >= polygon.islands]
    if polygon.remove_dead:
        if net is None:
            return (), ""
        touch = [g for item in same for g in geometry.grow(item.shape, TOUCH_NM, tol)]
        for other, others in state.poured:
            if other.net == net and polygon.pour_over != "none":
                touch.extend(others)
        pieces = [piece for piece in pieces if geometry.meet((piece,), touch)]
    return tuple(pieces), ""


def _conductors(
    joins: Sequence[tuple[PourObject, Connection]],
    copper: Sequence[Polygon],
    forbidden: Sequence[Polygon],
    area_now: Sequence[Polygon],
    geometry: _Geometry,
    tol: int,
) -> list[Polygon]:
    """The relief conductors of I6: bars of the conductor width from each pad's or via's centre, turned with
    a pad, within the pad grown by the air gap and the conductor width; a bar that would enter another
    net's clearance, leave the polygon or reach no copper is left out."""
    found: list[Polygon] = []
    for item, join in joins:
        if join.style != "relief" or item.center is None:
            continue
        core, width, _ = item.shape
        radius = max(max(abs(p.x - item.center.x), abs(p.y - item.center.y)) for p in core) * 2 + width
        length = radius + join.air_gap + join.conductor_width
        step = 360_000_000 // join.conductors
        turn = item.rotation if item.kind == "pad" else 0
        ring = geometry.grow(item.shape, join.air_gap + join.conductor_width, tol)
        for k in range(join.conductors):
            bar = _bar(item.center, join.angle + turn + k * step, length, join.conductor_width)
            spoke = geometry.meet(geometry.meet((bar,), ring), area_now)
            if not spoke or geometry.meet(spoke, forbidden) or not geometry.meet(spoke, copper):
                continue
            found.extend(spoke)
    return found


def _clean(points: Sequence[Point]) -> tuple[Point, ...]:
    out: list[Point] = []
    for point in points:
        if not out or out[-1] != point:
            out.append(point)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return tuple(out)


def check_pour(reading: PourReading, result: PourResult) -> tuple[int, ...]:
    """The self-check of a computed pour (capability altium-pour, "Refusal of a pour"): the indices of the
    poured polygons of ``result`` whose copper, as ``reading`` (the written document read back) holds it,
    touches an object of another net or comes nearer to it than the governing clearance, judged with the
    exact predicates of the copper check (``geometry.thick``) on the fills of the import."""
    from fenolite.geometry.thick import Thick, thick_closer_than

    polygons = {p.index: p for p in polygons_of(reading)}
    if not polygons:
        return ()
    tol = min(p.tol for p in polygons.values())
    objects = LayerObjects(reading, tol)
    rules = Clearances(reading)
    fills: dict[str, list[tuple[int, str | None, Thick, BBox]]] = {}
    for pour in result.polygons:
        polygon = polygons.get(pour.index)
        if not pour.poured or polygon is None:
            continue
        for fill in polygon.zone.fills:
            ring = _clean(fill.polygon)
            try:
                shape = Thick(ring, 0, filled=True)
            except (GeometryError, ValueError):
                continue
            fills.setdefault(polygon.layer, []).append((pour.index, pour.net, shape, BBox.of_points(ring)))
    failed: set[int] = set()
    for layer, found in fills.items():
        for index, net, shape, box in found:
            if index in failed:
                continue
            name = polygons[index].name
            me = rule_subject(layer, "zone", net, objects.netclass.get(net, DEFAULT_CLASS))
            near = box.inflate(rules.largest + 1)
            for item in objects.by_layer.get(layer, []):
                if (net is not None and item.net == net) or not item.box.intersects(near):
                    continue
                subject = rule_subject(layer, item.kind, item.net, item.netclass, item.ref)
                value = rules.clearance(me, subject, polygons=(name,))
                if isinstance(value, str):
                    continue
                core, width, filled = item.shape
                if thick_closer_than(shape, Thick(core, width, filled), value):
                    failed.add(index)
                    break
            if index in failed:
                continue
            for other, other_net, other_shape, other_box in found:
                if other == index or (net is not None and other_net == net) or not other_box.intersects(near):
                    continue
                them = rule_subject(layer, "zone", other_net, objects.netclass.get(other_net, DEFAULT_CLASS))
                value = rules.clearance(me, them, polygons=(name, polygons[other].name))
                if not isinstance(value, str) and thick_closer_than(shape, other_shape, value):
                    failed.add(max(index, other))
    return tuple(sorted(failed))


__all__ = [
    "BackendUnavailable",
    "EVIDENCE",
    "HYPOTHESES",
    "INPUTS",
    "POUR_MODES",
    "REASONS",
    "Clearances",
    "PolygonPour",
    "PourMode",
    "PourReading",
    "PourResult",
    "LayerObjects",
    "PourObject",
    "PourPolygon",
    "area",
    "check_pour",
    "DISC_STEPS",
    "disc",
    "polygons_of",
    "rule_subject",
    "pour_reading",
    "read_pour",
]

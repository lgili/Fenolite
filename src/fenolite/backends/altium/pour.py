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

from fenolite.backends.altium.adapter.arcring import once, record_outline  # change c0463: shared
from fenolite.backends.altium.adapter.layers import MULTI
from fenolite.backends.altium.adapter.pads import SHAPE_OCTAGON
from fenolite.backends.altium.connectstyle import (
    Connection,
    ConnectStyle,
    ObjectKind,
    governing_connection,
    read_connect_styles,
)
from fenolite.backends.altium.hatch import HATCH_NORMALS, first_part, grid_segments
from fenolite.backends.altium.read.pcb import PcbDocument, RuleRecord, read_pcbdoc
from fenolite.backends.altium.read.pcbprims import ArcRecord, RegionRecord, TrackRecord
from fenolite.backends.altium.read.proptext import parse_length
from fenolite.backends.altium.read.scope import ScopeDocument
from fenolite.backends.base import BoardPad, EdgeRing
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.geometry import Arc as GeoArc
from fenolite.geometry import Polygon
from fenolite.geometry.boolean.clipper import ClipperBackend
from fenolite.geometry.errors import BackendUnavailable, GeometryError
from fenolite.geometry.index import SpatialIndex
from fenolite.geometry.polygon import area2, convex_hull
from fenolite.geometry.predicates import floor_sqrt
from fenolite.geometry.shapes import BBox
from fenolite.geometry.transform import rotate_point
from fenolite.model.board import Board, Zone, rule_areas
from fenolite.model.design import Design
from fenolite.model.rules import CASED_LEAVES, LEAF_OPS, PAD_TYPE_OF, Rule, RuleSubject, Selector

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
    "hatched": "the polygon's hatch is not one Fenolite pours (HATCHSTYLE None or unknown, or its GRIDSIZE "
    "and TRACKWIDTH not two lengths with the width below the grid)",
    "shelved": "the polygon is shelved",
    "outline-arc": "an arc of the polygon's outline has no radius or does not join its two vertices",
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
    "polygon-cutout": "a polygon cut-out within the polygon's reach could not be taken out of its area",
    "depends-on-refused": "an earlier polygon of the layer within this one's reach is refused",
    "copper-check": "the copper check finds a short or a clearance below the rule on the computed pour",
    "neck-bound": "the exact cut of the neck removal exceeds its resource bound",
}
"""Why a polygon keeps its outline only (``altium.zone-unpoured``), a closed list."""
EXACT: Final = frozenset({"shelved", "plane-layer"})
"""The reasons that are Altium's own outcome, not a refusal (change c0463, D4): Altium shows a shelved
polygon with no copper, and an internal plane is no polygon pour (``pcb-copper.md``). A census counts them
under ``exact``, and no later polygon depends on them."""

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
    "H-A-POUR-HATCH",
)
EVIDENCE: Final = Evidence(Level.INFERRED, hypotheses=HYPOTHESES)
"""Every computed pour is ``INFERRED`` until a K6 round of the kit settles its rows (Decision 10)."""

SQUARE_NM_PER_UNIT = Fraction(127, 50) ** 2
"""``AREATHRESHOLD`` is in square file units (input I12)."""
UNIT_SLACK_NM = 2
"""What a written vertex may move toward an object when the document rounds it to its unit (1/10 000 mil =
2.54 nm, half of it on each axis: at most 1.8 nm), rounded up (change c0243): a void with square corners
grows by this much more, so the copper read back from the document keeps its clearance."""
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


PourTrack = tuple[Point, Point, Nm]
"""A track of a hatched pour: its two ends in the frame of the import and its width."""


@dataclass(frozen=True, slots=True)
class PolygonPour:
    """The pour of the polygon at position ``index`` of ``Polygons6``: its layer and net, its pieces in the
    frame of the import (normal form, sorted), its ``ARCRESOLUTION`` in nanometres, and the reason it is
    refused (empty when it is poured; a refused polygon has no piece). A hatched polygon (change c0463) also
    has its ``tracks``, which the document holds instead of regions; its pieces are their copper."""

    index: int
    layer: str
    net: str | None
    pieces: tuple[Polygon, ...]
    arc_resolution: Nm
    reason: str = ""
    zone_id: str = ""
    tracks: tuple[PourTrack, ...] = ()

    @property
    def poured(self) -> bool:
        return not self.reason

    @property
    def exact(self) -> bool:
        """Whether the polygon pours no copper because Altium pours none either (``EXACT``)."""
        return self.reason in EXACT


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
    outline: tuple[Point, ...] = ()
    """The ring the polygon pours: the zone's outline, or the record's outline with its arcs as chords."""
    hatch: tuple[str, Nm, Nm] | None = None
    """``(HATCHSTYLE, GRIDSIZE, TRACKWIDTH)`` of a hatched polygon, the lengths in nanometres (c0463)."""

    @property
    def tol(self) -> int:
        """The arc tolerance of the offsets: a quarter of ``ARCRESOLUTION``, at least 50 nm."""
        return max(self.arc_resolution // 4, 50)

    @property
    def box(self) -> BBox:
        return BBox.of_points(self.outline) if self.outline else BBox(0, 0, 0, 0)


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
        arc = parse_length(get("ARCRESOLUTION") or "")
        outline = once(zone.outline)
        if not outline and arc is not None and arc > 0:  # the import keeps no outline with an arc vertex
            outline = record_outline(polygon.vertices, arc)
        read = _hatch(get("HATCHSTYLE") or "Solid", get("GRIDSIZE"), get("TRACKWIDTH"))
        hatch = None if isinstance(read, str) else read
        if isinstance(read, str):
            reason = read
        elif (get("SHELVED") or "FALSE").upper() == "TRUE":
            reason = "shelved"
        elif not outline:
            reason = "outline-arc" if arc is not None and arc > 0 else "threshold"
        elif (get("LAYER") or "").upper().startswith("PLANE"):
            reason = "plane-layer"
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
                outline=outline,
                hatch=hatch,
            )
        )
    return sorted(found, key=lambda p: p.index)


def _hatch(style: str, grid: str | None, width: str | None) -> tuple[str, Nm, Nm] | str | None:
    """The hatch of a polygon record (``H-A-POUR-HATCH``): ``None`` when it is solid, the reason
    ``hatched`` when Fenolite does not pour it (``None`` style: an outline only; an unknown style; no grid
    or width; a width that fills the grid)."""
    if style == "Solid":
        return None
    pitch = parse_length(grid or "")
    track = parse_length(width or "")
    if style not in HATCH_NORMALS or pitch is None or track is None or not 2 <= track < pitch:
        return "hatched"
    return (style, pitch, track)


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
    pad_type: str | None = None
    """For a pad or the hole of a pad: ``smd``, ``th`` or ``npth`` (``model.rules.PAD_TYPES``)."""
    hole: Nm | None = None
    """The diameter of the object's hole: of a via, of a pad with a hole, of a free hole (change c0462)."""
    concentric_drill: Nm | None = None
    """The drill diameter of a round plated hole centered on its circular copper pad."""


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
        self.octagonal_smd = {
            pad.id: pad.size
            for footprint in board.footprints
            for pad in footprint.pads
            if pad.kind == "smd"
            and pad.layers == ("F.Cu",)
            and pad.padstack is None
            and "altium" in pad.ext
            and ("shape", str(SHAPE_OCTAGON)) in pad.ext["altium"].payload
        }
        """Native simple top-layer octagons, kept as opaque custom pads by the neutral model (S-2314)."""
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
        self._holes_and_keepouts(board, _cutout_locators(reading))
        self._keepout_regions(reading)
        self._copper_records(reading, tol)
        self._unshaped(board)
        for items in self.by_layer.values():
            items.sort(key=lambda o: (o.kind, o.entity_id, o.box.as_tuple()))

    def octagonal_void(self, polygon: PourPolygon, item: PourObject, clearance: Nm) -> Polygon | None:
        """The S-2314 void for a foreign pad in a solid pour, or ``None`` for other obstacles."""
        size = self.octagonal_smd.get(item.entity_id)
        at = item.center
        if (
            size is None
            or at is None
            or polygon.hatch is not None
            or (polygon.net is not None and polygon.net == item.net)
        ):
            return None
        w, h = size.w + 2 * clearance, size.h + 2 * clearance
        x, y = (w + 1) // 2, (h + 1) // 2
        cut = (min(w, h) + 2) // 4
        corners = (
            Point(-x + cut, -y), Point(x - cut, -y), Point(x, -y + cut), Point(x, y - cut),
            Point(x - cut, y), Point(-x + cut, y), Point(-x, y - cut), Point(-x, -y + cut),
        )  # fmt: skip
        turned = (rotate_point(p, item.rotation) for p in corners)
        return Polygon(once(tuple(Point(at.x + p.x, at.y + p.y) for p in turned)))

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
        pad_type: str | None = None,
        hole: Nm | None = None,
    ) -> PourObject:
        core, width, _ = shape
        netclass = self.netclass.get(net, DEFAULT_CLASS)
        return PourObject(
            kind,
            net,
            netclass,
            ref,
            shape,
            _box(core, width),
            ident,
            connect,
            center,
            rotation,
            pad_type,
            hole,
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
            # of another net keeps its clearance to the hole (``H-A-IMP-VIA-PADLESS``); a polygon of its net
            # joins it as a via (``connect``; S-2227, row -02)
            hole = via.diameter == via.drill
            for layer in _span(self.copper, via.layers, via.via_type == "through"):
                if hole:
                    item = self._object(
                        "hole", net, shape, via.id, connect="via", center=via.position, hole=via.drill
                    )
                    self._add(layer, item)
                else:
                    item = self._object(
                        "via", net, shape, via.id, connect="via", center=via.position, hole=via.drill
                    )
                    self._add(layer, item)

    def _pads(self, pads: Sequence[BoardPad]) -> None:
        kinds: dict[str, ObjectKind] = {"thru_hole": "th_pad", "smd": "smd_pad"}
        for pad in pads:
            kind = kinds.get(pad.kind)
            pad_type = PAD_TYPE_OF.get(pad.kind)
            drill = pad.drill if pad.hole and pad.drill and pad.kind != "smd" else None
            ref = pad.ref or None
            on = {entry.layer for entry in pad.copper}
            for entry in pad.copper:
                shape = (entry.core, entry.width, entry.filled)
                item = self._object(
                    "pad", pad.net, shape, pad.pad_id, ref=ref, connect=kind, center=pad.position,
                    rotation=pad.rotation, pad_type=pad_type, hole=drill,
                )  # fmt: skip
                if drill is not None and pad_type == "th" and pad.hole == entry.core == (pad.position,):
                    item = replace(
                        item, concentric_drill=drill, box=_box(entry.core, max(entry.width, drill))
                    )
                self._add(entry.layer, item)
            if pad.hole and pad.drill and pad.kind != "smd":
                net = pad.net if pad.kind == "thru_hole" else None
                for layer in self.copper:
                    if layer not in on:
                        shape = (pad.hole, pad.drill, False)
                        item = self._object(
                            "hole", net, shape, pad.pad_id, ref=ref, pad_type=pad_type, hole=pad.drill
                        )
                        self._add(layer, item)
            elif not pad.copper and pad.kind != "np_thru_hole":
                for layer in pad.layers:
                    if layer in self.unshaped:
                        self.unshaped[layer].append((BBox.of_points((pad.position,)).inflate(1), "pad"))

    def _holes_and_keepouts(self, board: Board, cutouts: frozenset[str]) -> None:
        for hole in board.holes:
            core = (
                (hole.position,)
                if hole.length is None
                else _slot_core(hole.position, hole.length, hole.drill, hole.rotation)
            )
            for layer in self.copper:
                item = self._object(
                    "hole", None, (core, hole.drill, False), hole.id, pad_type="npth", hole=hole.drill
                )
                self._add(layer, item)
        for keepout in rule_areas(board):
            if not keepout.no_copper_pour or len(keepout.outline) < 3:
                continue
            if keepout.provenance is not None and keepout.provenance.locator in cutouts:
                continue  # a polygon cut-out leaves the area (``_polygon_cutouts``), with no clearance
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
        prefix (I18): the tracks and arcs of components, fills, and free copper regions (``KIND=0``,
        no keep-out, no board cut-out, no polygon). Keep-out primitives use their rule areas (I16). A region
        is its outline: its holes are left filled, so its void is never too small. A free stroke on the
        Keep-Out layer that restricts poured copper is a keep-out on every copper layer (S-2311)."""
        from fenolite.backends.altium.adapter import units
        from fenolite.backends.altium.adapter.copper import (
            RESTRICTION_BYTE,
            is_board_cutout,
            is_keepout,
            keepout_layer_restrictions,
        )
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

        def stroke_kind(item: TrackRecord | ArcRecord) -> ObjectType | None:
            if item.prefix.polygon is not None:
                return None
            if item.prefix.component is None:
                restrictions = keepout_layer_restrictions(item)
                if restrictions is not None:
                    return "keepout" if restrictions & KEEPOUT_COPPER else None
                # Altium upgrades legacy Keep-Out strokes with no restriction byte to all bits (S-2311).
                if item.prefix.layer == KEEPOUT_LAYER and len(item.raw) - 5 <= RESTRICTION_BYTE[type(item)]:
                    return "keepout"
                return None
            if is_keepout(item):
                return None
            return "track" if isinstance(item, TrackRecord) else "arc"

        def stroke(
            storage: str, index: int, item: TrackRecord | ArcRecord, kind: ObjectType, shape: _Core
        ) -> None:
            if kind == "keepout":
                obstacle = self._object(kind, None, shape, f"{storage}:{index}")
                for layer in self.copper:
                    self._add(layer, obstacle)
            else:
                owned(storage, index, item.prefix.layer, kind, shape, item.prefix.net)

        for index, item in enumerate(document.tracks):
            if not isinstance(item, TrackRecord) or (kind := stroke_kind(item)) is None:
                continue
            core = (units.pcb_point(item.x1, item.y1), units.pcb_point(item.x2, item.y2))
            shape = (core, units.pcb_length(item.width), False)
            stroke("Tracks6", index, item, kind, shape)
        for index, item in enumerate(document.arcs):
            if not isinstance(item, ArcRecord) or (kind := stroke_kind(item)) is None:
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
            stroke("Arcs6", index, item, kind, (core, width, False))
        for index, item in enumerate(document.fills):
            if not isinstance(item, FillRecord) or item.prefix.polygon is not None or is_keepout(item):
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
    if selector.op in LEAF_OPS and selector.op not in CASED_LEAVES:
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


PAD_PAIR_KEY = "IGNOREPADTOPADCLEARANCEINFOOTPRINT"
PAD_PAIR_KINDS = frozenset({"Clearance", "BoardOutlineClearance"})
"""A record of these kinds with ``IGNOREPADTOPADCLEARANCEINFOOTPRINT=TRUE`` leaves out the pairs of two pads
of one footprint. The import does not map it (``keys``, ``rule-file.md``): no neutral selector says that.
The pour never judges two pads, only a polygon's copper against an object, so for the pour the record says
what it says with ``FALSE`` and is read so (change c0463, task 4.3; row ``-02``)."""


def _pads_judged(fields: Sequence[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    """``fields`` with ``IGNOREPADTOPADCLEARANCEINFOOTPRINT=FALSE`` (``PAD_PAIR_KINDS``)."""
    return tuple((key, "FALSE" if key == PAD_PAIR_KEY else value) for key, value in fields)


TWIN_FORMS: Mapping[str, str] = {"Arc": "Track", "Region": "Fill"}
"""The object kinds of a Clearance matrix that one neutral kind holds (``read.rules.TWIN_KINDS``) → the kind
that stands for both. The import refuses a matrix whose twins differ (``matrix-kind``); the pour asks only
the polygon's row, so it reads the matrix with each twin as the kind that stands for it and takes the
polygon's clearance to an arc, a track, a fill or a region from its own cell (change c0463, task 4.3,
rows ``-06`` and ``-08``). The Hole cell also has no neutral rule (S-2312)."""
FINE_KINDS = ("Arc", "Track", "Fill", "Region", "Hole")
"""The object kinds whose cell with ``Poly`` the pour reads separately from the neutral rule."""
_MATRIX_ENTRY = re.compile(r"ClearanceObj_([A-Za-z]+)-ClearanceObj_([A-Za-z]+):(\d+)")


def _twins_judged(
    fields: Sequence[tuple[str, str]],
) -> tuple[tuple[tuple[str, str], ...], dict[str, Nm]] | None:
    """``fields`` with the matrix of ``TWIN_FORMS`` and the clearance of ``Poly`` to each of ``FINE_KINDS``,
    or ``None`` when the record holds no matrix that this reads."""
    from fenolite.backends.altium.read.rules import MATRIX_UNIT
    from fenolite.core.units import round_half_even_div

    values = dict(fields)
    text = (values.get("OBJECTCLEARANCES") or "").strip()
    gap = parse_length(values.get("GAP") or "")
    if not text or gap is None:
        return None
    listed: dict[tuple[str, ...], int] = {}
    for part in text.split(";"):
        match = _MATRIX_ENTRY.fullmatch(part.strip())
        pair = None if match is None else tuple(sorted((match.group(1), match.group(2))))
        if match is None or pair is None or pair in listed:
            return None
        listed[pair] = int(match.group(3))

    def form(pair: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(TWIN_FORMS.get(kind, kind) for kind in pair))

    def poly(kind: str) -> Nm:
        count = listed.get(tuple(sorted((kind, "Poly"))))
        return gap if count is None else round_half_even_div(count * MATRIX_UNIT[0], MATRIX_UNIT[1])

    kinds = sorted({kind for pair in listed for kind in pair} | set(TWIN_FORMS) | set(TWIN_FORMS.values()))
    entries: list[str] = []
    for position, first in enumerate(kinds):
        for second in kinds[position:]:
            count = listed.get(form((first, second)))
            if count is not None:
                entries.append(f"ClearanceObj_{first}-ClearanceObj_{second}:{count}")
    judged = tuple((key, ";".join(entries) if key == "OBJECTCLEARANCES" else value) for key, value in fields)
    return judged, {kind: poly(kind) for kind in FINE_KINDS}


def _edges_judged(fields: Sequence[tuple[str, str]]) -> tuple[tuple[str, str], ...] | None:
    """``fields`` of a Board Outline Clearance record with each object's ``CutoutEdge`` cell set to its
    ``OutlineEdge`` cell, or ``None`` when the record holds no matrix that this reads. The import refuses a
    matrix whose two edges differ (``matrix-kind``), since its edge check judges both as the board's edge;
    so does the pour (I17), which keeps the outline's value from both (row ``-06``: the Poly cell of the
    outline is 0.5 mm, its cut-out cell the generic value)."""
    values = dict(fields)
    text = (values.get("OBJECTCLEARANCES") or "").strip()
    if not text:
        return None
    outline: dict[str, str] = {}
    kept: list[str] = []
    for part in text.split(";"):
        match = _MATRIX_ENTRY.fullmatch(part.strip())
        if match is None:
            return None
        first, second, count = match.group(1), match.group(2), match.group(3)
        if first in ("OutlineEdge", "CutoutEdge"):
            first, second = second, first
        if second == "OutlineEdge":
            outline[first] = count
        if second != "CutoutEdge":
            kept.append(f"ClearanceObj_{first}-ClearanceObj_{second}:{count}")
    kept.extend(f"ClearanceObj_{name}-ClearanceObj_CutoutEdge:{count}" for name, count in outline.items())
    return tuple((key, ";".join(kept) if key == "OBJECTCLEARANCES" else value) for key, value in fields)


def pour_rule_fields(
    records: Sequence[RuleRecord],
) -> tuple[list[tuple[tuple[str, str], ...]], frozenset[int], dict[int, dict[str, Nm]]]:
    """The fields of the rule ``records`` as the pour reads them (change c0463, task 4.3), the indexes of the
    records the import does not read and the pour reads, and, by index, the additional polygon cells
    of each Clearance matrix."""
    from fenolite.backends.altium.read.rules import matrix_problem

    footprint_pads = frozenset(
        index
        for index, record in enumerate(records)
        if (record.record.get("RULEKIND") or "") in PAD_PAIR_KINDS
        and (record.record.get(PAD_PAIR_KEY) or "").upper() == "TRUE"
    )
    fields = [
        _pads_judged(record.fields) if i in footprint_pads else tuple(record.fields)
        for i, record in enumerate(records)
    ]
    fine: dict[int, dict[str, Nm]] = {}
    read: set[int] = set(footprint_pads)
    for i, record in enumerate(records):
        kind = record.record.get("RULEKIND") or ""
        if kind == "BoardOutlineClearance":
            matrix, gap = record.record.get("OBJECTCLEARANCES"), record.record.get("GAP")
            if not matrix_problem(matrix or "", gap, edges=True):
                continue
            edges = _edges_judged(fields[i])
            if edges is not None and not matrix_problem(
                dict(edges).get("OBJECTCLEARANCES") or "", gap, edges=True
            ):
                fields[i] = edges
                read.add(i)
            continue
        if kind != "Clearance":
            continue
        matrix, gap = record.record.get("OBJECTCLEARANCES") or "", record.record.get("GAP")
        if not matrix:
            continue
        problem = matrix_problem(matrix, gap)
        # A Hole cell, including the default GAP when only the THPad cell changes, has no neutral rule.
        if not problem and not any(kind in matrix for kind in ("ClearanceObj_Hole", "ClearanceObj_THPad")):
            continue
        judged = _twins_judged(fields[i])
        if judged is None:
            continue
        if not problem:
            fine[i] = {"Hole": judged[1]["Hole"]}
        elif not matrix_problem(dict(judged[0]).get("OBJECTCLEARANCES") or "", gap):
            fields[i], fine[i] = judged
            read.add(i)
    return fields, frozenset(read), fine


def fine_kind(item: PourObject) -> str | None:
    """The object kind of the matrix that ``item`` is when it is one of ``FINE_KINDS``."""
    storage = item.entity_id.split(":", 1)[0]
    if storage == "Fills6":
        return "Fill"
    if storage == "Regions6":
        return "Region"
    return {"arc": "Arc", "track": "Track"}.get(item.kind)


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


KEEPOUT_TERMS = re.compile(
    r"\(*\s*(?:IsKeepOut|IsBoardCutoutRegion|OnLayer\(\s*'Keep[- ]?Out(?:[- ]?Layer)?'\s*\))\s*\)*",
    re.IGNORECASE,
)
"""A term of Altium's keep-out scope: a keep-out object, a board cut-out, or the Keep-Out layer."""


def _keepout_only(scope: str | None) -> bool:
    """Whether ``scope`` is one keep-out term or an ``or`` of them (``KEEPOUT_TERMS``)."""
    terms = re.split(r"\s+or\s+", (scope or "").strip(), flags=re.IGNORECASE)
    return bool(scope and scope.strip()) and all(KEEPOUT_TERMS.fullmatch(term) for term in terms)


def _keepout_rule(record: RuleRecord) -> Rule | None:
    """The rule the pour reads from a Clearance record the import refuses for its scope when one scope is
    only keep-out terms and the other is ``All`` (Altium's default keep-out clearance, change c0463 task
    5.2): the clearance between a keep-out object and any object. A board cut-out is the board's edge to the
    pour (I17), which the record does not move; a keep-out on the Keep-Out layer is a keep-out object. A
    record with an object matrix is not read."""
    fields = record.record
    first, second = fields.get("SCOPE1EXPRESSION"), fields.get("SCOPE2EXPRESSION")
    if not any(_keepout_only(one) and (other or "").strip().casefold() == "all"
               for one, other in ((first, second), (second, first))):  # fmt: skip
        return None
    if (fields.get("OBJECTCLEARANCES") or "").strip():
        return None
    gap = parse_length(fields.get("GAP") or "")
    if gap is None:
        return None
    name = fields.get("NAME") or "keep-out clearance"
    return Rule(
        id=f"pour-keepout-{record.priority or 0}-{name}", name=name, kind="clearance",
        selector_a=Selector("item_kind", "keepout"), min=gap, priority=record.priority or 0,
    )  # fmt: skip


class Clearances:
    """The governing Clearance between a polygon and an object of a reading (I2), and the governing Board
    Outline Clearance of a polygon (I17), resolved from the neutral rules of the import as the copper check
    resolves them for an Altium reading. A Clearance record that the import does not map and that comes
    before the governing rule (or any such record when no rule governs) leaves the pair undetermined."""

    def __init__(self, reading: PourReading) -> None:
        from fenolite.backends.altium.adapter.layers import copper_layers_of
        from fenolite.backends.altium.read.rules import NOT_APPLYING, map_rules
        from fenolite.backends.altium.read.scopedoc import scope_document

        design = reading.design
        board = design.board
        layers = copper_layers_of(board.layers) if board is not None else None
        records = reading.document.rules
        fields, extra, fine = pour_rule_fields(records)
        mapping = map_rules(
            fields,
            origin="pour",
            layers=layers,
            document=scope_document(reading.document, layers),
        )
        imported = design.rules.rules if design.rules is not None else ()
        added = [
            (rule, i)
            for rule, i in zip(mapping.ruleset.rules, mapping.rule_records, strict=True)
            if i in extra
        ]
        rules = (*imported, *(rule for rule, _ in added))
        holes = {f"Rules6/Data#{i}": {"Hole": cells["Hole"]} for i, cells in fine.items()}
        self._fine = {
            rule.id: holes[rule.provenance.locator]
            for rule in imported
            if rule.provenance is not None and rule.provenance.locator in holes
        }
        self._fine.update({rule.id: fine[i] for rule, i in added if i in fine})
        """The additional polygon clearance cells for each rule, keyed by its model id."""

        keepout: list[Rule] = []
        read_scopes: set[int] = set()
        for record in mapping.unmapped:
            found = records[record.index] if 0 <= record.index < len(records) else None
            if record.kind == "Clearance" and record.reason == "scope" and found is not None:
                rule = _keepout_rule(found)
                if rule is not None:
                    keepout.append(rule)
                    read_scopes.add(record.index)
        rules = (*rules, *keepout)

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
        self.has_outline_clearance = any(
            (record.record.get("RULEKIND") or "") == "BoardOutlineClearance"
            for record in reading.document.rules
        )
        """Whether the document holds a Board Outline Clearance record, read or not (S-2224)."""
        self.largest: Nm = max(
            (
                *(c.rule.min or 0 for c in self._clearance),
                *(v for cells in self._fine.values() for v in cells.values()),
            ),
            default=0,
        )
        """The largest clearance a rule of the reading gives."""
        self._unmapped: list[tuple[int, str, str | None]] = []
        """(priority, reason, the one polygon it can govern or ``None`` for any) of each unread record."""
        for record in mapping.unmapped:
            if record.kind != "Clearance" or record.reason in NOT_APPLYING or record.index in read_scopes:
                continue
            found = records[record.index] if 0 <= record.index < len(records) else None
            priority = found.priority if found is not None else None
            only = (
                _polygon_only(found.record.get("SCOPE1EXPRESSION"), found.record.get("SCOPE2EXPRESSION"))
                if (found is not None)
                else None
            )
            self._unmapped.append((priority or 0, record.reason, only))
        self._memo: dict[tuple[RuleSubject, RuleSubject, tuple[str, ...], str | None], Nm | str] = {}

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

    def clearance(
        self, a: RuleSubject, b: RuleSubject, *, polygons: tuple[str, ...] = (), fine: str | None = None
    ) -> Nm | str:
        """The governing clearance between ``a`` and ``b`` on ``a.layer``, or the reason it is unknown;
        ``polygons`` are the names of the polygons whose copper the pair holds (input I3), ``fine`` the kind
        of ``FINE_KINDS`` that ``b`` is, for a polygon ``a``."""
        key = (a, b, polygons, fine)
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
                found = self._fine.get(rule.id, {}).get(fine or "", rule.min)
            self._memo[key] = found
            self._memo[(b, a, polygons, fine)] = found
        return found

    def obstacle(
        self, polygon: RuleSubject, subject: RuleSubject, item: PourObject, *, name: str
    ) -> tuple[_Core, Nm] | str:
        """The physical foreign-net shape and its governing gap, shared by the pour and writer self-check."""
        value = self.clearance(polygon, subject, polygons=(name,), fine=fine_kind(item))
        if isinstance(value, str):
            return value
        core, width, _ = item.shape
        drill = item.concentric_drill
        if drill is None:
            return item.shape, value
        hole_gap = self.clearance(polygon, subject, polygons=(name,), fine="Hole")
        if isinstance(hole_gap, str):
            return hole_gap
        # With no annular ring only Hole applies. Otherwise the two concentric voids union (S-2312).
        if drill >= width or (drill + 1) // 2 + hole_gap > (width + 1) // 2 + value:
            return (core, drill, False), hole_gap
        return item.shape, value

    def edge(self, a: RuleSubject) -> Nm | str:
        """The governing Board Outline Clearance of ``a``, 0 when none governs. Without that rule type,
        look up the ordinary Clearance to a board cut-out, an object of no net on ``a``'s layer (S-2311).
        The outer board edge has no constraint in that case."""
        if not self.has_outline_clearance:
            edge = RuleSubject(item_kind="board", layer=a.layer)
            found = self.clearance(a, edge, polygons=(a.zone,) if a.zone else ())
            return 0 if found == "no-clearance" else found
        fa = _fold_subject(a)
        rule = next((c.rule for c in self._edge if c.matches_one(fa)), None)
        if rule is None or rule.severity == "ignore" or rule.min is None:
            return 0
        return rule.min


# --- geometry -----------------------------------------------------------------------------------------------


DISC_STEPS = (8, 16, 32, 64, 128, 256, 512, 1280, 2560)
"""The vertex counts of a ``disc``: each divides a full turn of 360 000 000 µdeg."""


EDGE_SAG: Final = 12_700
"""How far, at most, a corner of the polygon by which Altium grows the board's edge stands outside the circle
of the clearance (nm; ``edge_reach``). S-2224 places it between 12 359 and 24 718 nm; 0.5 mil is taken."""


def edge_reach(clearance: Nm) -> Nm:
    """How far the pour keeps from a straight edge of the board for the governing ``clearance`` (I17;
    ``H-A-POUR-EDGE``): ``clearance / cos(π/n)``, rounded up, for the fewest sides n, a multiple of 8, whose
    corners stand at most ``EDGE_SAG`` outside the circle (Altium's voids around round objects are such
    polygons too, with the polygon's ``ARCRESOLUTION`` as their bound: 48 and 104 sides on row -04).
    Altium's repour of the public rows keeps its pour 162.35 µm from every straight edge of rows -04 and -07
    for a rule of 150 µm (n = 8) and 305.86 µm on row -05 for 300 µm (n = 16). At the row -03 board cut-out
    the governing Clearance of 127 µm (n = 8) leaves 137.47 µm. Its chords along an arc of the edge touch
    the circle that far from it (S-2224, S-2227, S-2311): the edge grown by a
    regular polygon around the circle of the clearance, a corner along each axis. An edge along another
    direction may hold the pour nearer than this, never farther."""
    from fenolite.core.trig import FULL_TURN, ONE, cos_sin_fixed

    if clearance <= 0:
        return 0
    sides = 8
    while True:
        cos, _ = cos_sin_fixed(FULL_TURN // (2 * sides))
        reach = -(-clearance * ONE // cos)
        if reach - clearance <= EDGE_SAG or sides >= 1024:
            return reach
        sides += 8


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

    def grow(self, shape: _Core, by: int, tol: int, *, round_corners: bool = False) -> tuple[Polygon, ...]:
        """The points within ``width / 2 + by`` of the core, every curve kept outside the true one: a point
        core is a ``disc``; an open polyline or a ring is offset by ``tol + 1`` more than its reach."""
        core, width, filled = shape
        reach = (width + 1) // 2 + by
        if filled:
            ring = Polygon(core)
            if reach <= 0:
                return (ring,)
            if width == 0 and not round_corners:
                # a sharp ring (a rectangular pad, a fill, a region): its void keeps square corners, as the
                # saved pours of the public corpus show (I2; ``H-A-POUR-CLEARANCE``), a superset of the round
                # one; a miter of a corner sharper than 60° is squared off at twice the reach
                return self.backend.offset(
                    (ring,), reach + 1 + UNIT_SLACK_NM, join="miter", tol=max(tol // 8, 10), miter_limit=2
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
        convex corner sharper than 89.5° has a chord at the tangent distance along its angle bisector
        when both sides reach the chord and its tip belongs to one copper component (S-2322).
        Other acute corners use the local opening hull. The sliver the opening takes off a corner of
        89.5° or more (within half the width of it) comes back, so the corner stays sharp. Every other
        piece is a neck and stays removed. Copper that grows back from two parts of the eroded copper
        is parted where the two meet (``_pinches``). The result is cut back to ``polys``: nothing grows."""
        half = width // 2
        if half <= 0 or not polys:
            return tuple(polys)
        eroded = self.offset(polys, -half, tol)
        rounded = self.meet(self.offset(eroded, half, tol), polys) if eroded else ()
        removed = self.minus(polys, rounded)
        if not removed:
            return tuple(polys)
        corners = _convex_corners(polys, half)
        rings_at_vertex = {
            point: index
            for index, ring in enumerate(ring for poly in polys for ring in poly.rings())
            for point in ring
        }
        cut: list[Polygon] = []
        supported: set[Point] = set()
        for piece in removed:
            found = [(v, corners[v][0]) for v in piece.outer if v in corners]
            tips = [(v, reach) for v, reach in found if reach]
            box = piece.bbox()
            whole = box.width + box.height + tol + 1  # a disc this wide about a vertex holds the whole piece
            for apex, reach in tips:
                if apex in supported:
                    continue
                _, before, after, owner = corners[apex]
                chord = _acute_chord(apex, before, after, reach)
                if chord is not None and not self.minus((chord,), (owner,)):
                    cut.append(chord)
                    supported.add(apex)
                    continue
                # the tip only: the part of the piece within the reach of the opening's arc at this corner (a
                # spike of almost no angle reaches farther than the piece: row -06)
                local = self.meet((piece,), (disc(apex, min(reach * 3 // 2 + half, whole), tol),))
                points = [q for poly in local for q in poly.outer]
                hull = convex_hull(points) if points else ()
                if len(hull) >= 3:
                    cut.append(Polygon(hull))
            if found and not tips:
                apex = found[0][0]
                extent = max(box.width, box.height)
                limit = half + tol
                if extent <= limit or (
                    len(found) == 1
                    and extent <= 2 * limit
                    and all((p.x - apex.x) ** 2 + (p.y - apex.y) ** 2 <= limit**2 for p in piece.outer)
                ):
                    continue  # preserve the nonacute corner even if its box is wider after rotation
            if (
                not found
                and not piece.holes
                and half <= min(box.width, box.height)
                and max(box.width, box.height) <= 2 * width
            ):
                boundaries = {rings_at_vertex[p] for p in piece.outer if p in rings_at_vertex}
                if len(boundaries) == 2:
                    # Altium cuts a short neck between two clearance rims with chords (kit P3).
                    hull = convex_hull(piece.outer)
                    if len(hull) >= 3:
                        piece = Polygon(hull)
            cut.append(piece)
        cut.extend(self._pinches(eroded, half, tol))
        return _certified_neck_cut(polys, cut, tol) if cut else tuple(polys)

    def _pinches(self, eroded: Sequence[Polygon], half: int, tol: int) -> tuple[Polygon, ...]:
        """Where the copper grown back by ``half`` from two parts of the eroded copper ``eroded`` meets, grown
        by ``tol``: the opening parts a neck narrower than its width into two parts, and their discs, grown
        back, join them again at a pinch. Altium's repour of row -04 keeps them apart: a lobe of 0.11 mm²
        joined to the rest only through such a pinch is an island there (S-2227)."""
        boxes = [piece.bbox().inflate(half + tol) for piece in eroded]
        grown: dict[int, tuple[Polygon, ...]] = {}
        found: list[Polygon] = []
        for i in range(len(eroded)):
            for j in range(i + 1, len(eroded)):
                if not boxes[i].intersects(boxes[j]):
                    continue
                for k in (i, j):
                    if k not in grown:
                        grown[k] = self.offset((eroded[k],), half, tol)
                found.extend(self.meet(grown[i], grown[j]))
        return self.offset(found, tol, tol) if found else ()

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


def _certified_neck_cut(subject: Sequence[Polygon], cut: Sequence[Polygon], tol: int) -> tuple[Polygon, ...]:
    """The final cut of the opening (c0332): ``subject`` minus ``cut`` selected exactly, realized on integers
    within half a nanometre per axis of the exact boundary (``geometry.boolean._exact_cut``), then the
    existing debris policy. Integer arithmetic only, so the result is the same on every platform; a
    resource bound refuses with ``GeometryError`` and no floating fallback."""
    from fenolite.geometry.boolean._exact_cut import exact_difference
    from fenolite.geometry.boolean._exact_noding import Budget

    budget = Budget()
    try:
        result = exact_difference(subject, cut, budget)
    except GeometryError as error:
        if error.message != "exact geometry index-comparison budget exceeded":
            raise
        # A denser cell can exhaust its index cap before reaching its edge cap. Keep the same
        # operation budget and let finer cells divide the index work on one retry.
        result = exact_difference(subject, cut, budget, strip_edges=max(1, budget.limits.input_edges // 4))
    return _without_debris(result.polygons, tol)


def _resource_bound(error: GeometryError) -> bool:
    """Whether ``error`` is a work or storage bound of the exact geometry (``ResourceLimit``, or the bounds
    that raise a plain ``GeometryError`` saying so), which counts work and so is the same on every machine."""
    from fenolite.geometry.boolean._exact_noding import ResourceLimit

    return isinstance(error, ResourceLimit) or error.message.endswith("budget exceeded")


def _convex_corners(polys: Sequence[Polygon], radius: int) -> dict[Point, tuple[int, Point, Point, Polygon]]:
    """The convex corners of the copper with their neighbours, component and tangent distance
    ``radius / tan(α/2)`` for a corner sharper than 89.5° (``ACUTE_COS``), else 0."""
    found: dict[Point, tuple[int, Point, Point, Polygon]] = {}
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
                reach = -(-radius * (l1 * l2 + dot) // -cross) if acute else 0
                found[apex] = reach, before, after, poly
    return found


def _acute_chord(apex: Point, before: Point, after: Point, reach: int) -> Polygon | None:
    """The triangular tip cut at ``reach`` along the bisector, when the chord fits both straight sides."""
    scale = 1024
    ax, ay = before.x - apex.x, before.y - apex.y
    bx, by = after.x - apex.x, after.y - apex.y
    length_a = floor_sqrt((ax * ax + ay * ay) * scale**2)
    length_b = floor_sqrt((bx * bx + by * by) * scale**2)
    lengths = length_a * length_b
    dot = (ax * bx + ay * by) * scale**2
    # The length along each side is reach / cos(α/2), with cos²(α/2) = (1 + cos(α)) / 2.
    span = floor_sqrt(2 * reach**2 * lengths * scale**2 // (lengths + dot))
    if span > min(length_a, length_b):
        return None
    points = (
        apex,
        Point(apex.x + round(Fraction(ax * span, length_a)), apex.y + round(Fraction(ay * span, length_a))),
        Point(apex.x + round(Fraction(bx * span, length_b)), apex.y + round(Fraction(by * span, length_b))),
    )
    return Polygon(points) if area2(points) else None


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


def _board_cutouts(reading: PourReading) -> tuple[Polygon, ...]:
    """True board cut-outs, including cut-outs that the import merged into the outer ring as notches."""
    from fenolite.backends.altium.adapter.copper import is_board_cutout, region_points

    found: list[Polygon] = []
    for region in reading.document.regions:
        if not isinstance(region, RegionRecord) or not is_board_cutout(region):
            continue
        try:
            found.append(Polygon(region_points(region.outline)))
        except GeometryError:
            continue
    return tuple(found)


def connect_document(reading: PourReading) -> ScopeDocument:
    """The ``ScopeDocument`` of ``reading``, with which its Polygon Connect Style scopes are read (change
    c0462, task 4.5): the names of its nets, classes, components and polygons, and its copper layers."""
    from fenolite.backends.altium.adapter.layers import copper_layers_of
    from fenolite.backends.altium.read.scopedoc import scope_document

    board = reading.design.board
    return scope_document(reading.document, copper_layers_of(board.layers) if board is not None else None)


def rule_subject(
    layer: str,
    kind: str,
    net: str | None,
    netclass: str,
    ref: str | None = None,
    *,
    zone: str | None = None,
    pad_type: str | None = None,
    hole: Nm | None = None,
) -> RuleSubject:
    """The subject of an object of the pour: ``zone`` the name of a polygon's copper, ``pad_type`` and
    ``hole`` of a pad, a pad's hole, a via or a free hole (change c0462)."""
    return RuleSubject(
        item_kind=RULE_KINDS[kind], net=net, netclass=netclass, ref=ref, layer=layer, zone=zone,
        hole=hole, pad_type=pad_type,
    )  # fmt: skip


def object_subject(layer: str, item: PourObject) -> RuleSubject:
    """The subject of the pour object ``item`` on ``layer``."""
    return rule_subject(
        layer, item.kind, item.net, item.netclass, item.ref, pad_type=item.pad_type, hole=item.hole
    )


def _bar(center: Point, angle: int, length: int, width: int) -> Polygon:
    """The rectangle of a relief conductor from ``center`` along ``angle``, ``length`` long, ``width``
    wide."""
    half = (width + 1) // 2
    corners = (Point(0, -half), Point(length, -half), Point(length, half), Point(0, half))
    turned = (rotate_point(corner, angle) for corner in corners)
    return Polygon(tuple(Point(center.x + p.x, center.y + p.y) for p in turned))


def _projected_width(polygon: Polygon, normal: Point) -> int:
    """The span of the polygon's outer ring along a non-unit normal."""
    positions = [point.x * normal.x + point.y * normal.y for point in polygon.outer]
    return max(positions) - min(positions)


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
    cutouts: Mapping[str, tuple[tuple[BBox, Polygon], ...]]
    board: tuple[Polygon, ...]
    board_cutouts: tuple[Polygon, ...]
    reach: Nm
    """How far beyond a polygon's outline an object can shape its pour: the largest clearance, air gap
    and conductor width of the reading."""


def pour_reading(
    reading: PourReading,
    *,
    backend: ClipperBackend | None = None,
    refuse: Mapping[int, str] | None = None,
    fixed: Mapping[int, tuple[Polygon, ...]] | None = None,
) -> PourResult:
    """The pour of every polygon of ``reading`` (capability altium-pour, "Pour engine"). ``refuse`` maps a
    polygon index to a reason that refuses it before it is poured (the self-check of the writer). ``fixed``
    maps a polygon index to copper that is taken as that polygon's pour, not computed (a carried pour,
    change c0496)."""
    polygons = polygons_of(reading)
    if not polygons:
        return PourResult(())
    geometry = _Geometry(backend if backend is not None else ClipperBackend())
    forced = dict(refuse or {})
    rules = Clearances(reading)
    styles = read_connect_styles(  # change c0462: the full grammar, with the document's names
        [record.fields for record in reading.document.rules], connect_document(reading)
    )
    widest = max(
        (
            c.air_gap + c.conductor_width
            for s in styles
            for c in (s.th_pad, s.smd_pad, s.via)
            if c is not None
        ),
        default=0,
    )
    contexts: dict[int, tuple[_Context, bool]] = {}

    def context_of(tol: int) -> tuple[_Context, bool]:
        """The context of a polygon of arc tolerance ``tol``, and whether the board has an area. Each
        tolerance has its own (change c0496): a polygon's pour reads no other polygon's ``ARCRESOLUTION``."""
        if tol not in contexts:
            board = _board_area(reading, geometry, tol)
            contexts[tol] = (
                _Context(
                    geometry,
                    LayerObjects(reading, tol),
                    rules,
                    styles,
                    _polygon_cutouts(reading),
                    board or (),
                    () if rules.has_outline_clearance else _board_cutouts(reading),
                    rules.largest + widest + tol + 1,
                ),
                board is not None,
            )
        return contexts[tol]

    layers: dict[str, _Layer] = {}
    out: dict[int, PolygonPour] = {}
    for polygon in sorted(polygons, key=lambda p: (p.pour_index, p.index)):
        state = layers.setdefault(polygon.layer, _Layer())
        context, has_board = context_of(polygon.tol)
        reason = polygon.reason or forced.get(polygon.index, "")
        if not reason and not has_board:
            reason = "no-board"
        if not reason:
            reason = _depends(polygon, state, context)
        pieces: tuple[Polygon, ...] = ()
        tracks: tuple[PourTrack, ...] = ()
        if fixed is not None and polygon.index in fixed:
            pieces, reason = fixed[polygon.index], ""
        elif not reason:
            pieces, tracks, reason = _pour(polygon, state, context)
        if reason:
            pieces, tracks = (), ()
            if reason not in EXACT:  # no copper in Altium either: nothing of a neighbour depends on it
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
            tracks,
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
        if other.outline and other.box.intersects(reach):
            return "depends-on-refused"
    return ""


def _cutout_locators(reading: PourReading) -> frozenset[str]:
    """The locators (``Regions6/Data#<n>``) of the polygon cut-outs, regions of ``KIND=1``. The import makes a
    pour-only rule area of each; Altium's pour stops at the cut-out's edge with no clearance (S-2227, row
    ``-02``), so the pour takes the cut-out out of its area and keeps no clearance to that rule area."""
    return frozenset(
        f"Regions6/Data#{index}"
        for index, region in enumerate(reading.document.regions)
        if isinstance(region, RegionRecord) and region.properties.get("KIND") == "1"
    )


def _polygon_cutouts(reading: PourReading) -> Mapping[str, tuple[tuple[BBox, Polygon], ...]]:
    """The box and ring of each polygon cut-out (region of ``KIND=1``) per copper layer of the import, on
    Multi-Layer for every copper layer (change c0439 writes a pour-only rule area of every copper layer
    there)."""
    from fenolite.backends.altium.adapter.units import pcb_point

    board = reading.design.board
    layer_names: dict[int, str] = {}
    copper: list[str] = []
    if board is not None:
        for layer in board.layers:
            pairs = dict(layer.ext["altium"].payload) if "altium" in layer.ext else {}
            ident = pairs.get("layer_id", "")
            if ident.isdecimal():
                layer_names[int(ident)] = layer.name
            if layer.kind == "copper":
                copper.append(layer.name)
    found: dict[str, list[tuple[BBox, Polygon]]] = {}
    for region in reading.document.regions:
        if not isinstance(region, RegionRecord) or region.properties.get("KIND") != "1":
            continue
        points: list[Point] = []
        for v in region.outline:  # a record may repeat a vertex: the ring keeps it once
            point = pcb_point(round(v.x), round(v.y))
            if not points or point != points[-1]:
                points.append(point)
        while len(points) > 1 and points[-1] == points[0]:
            points.pop()
        if len(points) < 3:
            continue
        try:
            ring = Polygon(tuple(points))
        except GeometryError:  # a cut-out with no area cuts nothing
            continue
        names = copper if region.prefix.layer == MULTI else [layer_names.get(region.prefix.layer)]
        for name in names:
            if name is not None:
                found.setdefault(name, []).append((BBox.of_points(points), ring))
    return {name: tuple(items) for name, items in found.items()}


def _pour(
    polygon: PourPolygon, state: _Layer, context: _Context
) -> tuple[tuple[Polygon, ...], tuple[PourTrack, ...], str]:
    """The pieces of one polygon and, when it is hatched, its tracks, or the reason it is refused (I1 to
    I21, in the order of I11). A hatch's tracks are centred on the edges of the area a solid pour would
    fill with every clearance, air gap and the board's clearance grown by half the track width ``h``
    (``H-A-POUR-HATCH``, S-2223), so the hatch's copper keeps the same distances as a solid pour's."""
    geometry, objects, rules = context.geometry, context.objects, context.rules
    layer, net, tol = polygon.layer, polygon.net, polygon.tol
    h = polygon.hatch[2] // 2 if polygon.hatch is not None else 0
    me = rule_subject(layer, "zone", net, objects.netclass.get(net, DEFAULT_CLASS), zone=polygon.name)
    reach = polygon.box.inflate(context.reach + polygon.neck + h)  # a hatch's copper reaches h beyond
    for box, _what in objects.unshaped.get(layer, []):
        if box.intersects(reach):
            return (), (), "unshaped-pad" if _what == "pad" else "unshaped-copper"
    try:
        outline = (Polygon(polygon.outline),)
        area_now = (
            geometry.meet(outline, context.board) if rules.has_outline_clearance else geometry.union(outline)
        )
    except GeometryError:
        return (), (), "outline"
    cut = [ring for box, ring in context.cutouts.get(layer, ()) if box.intersects(reach)]
    if cut:  # no polygon pours its copper in a polygon cut-out (pcb-records.md, "Regions and keep-outs")
        try:
            area_now = geometry.minus(area_now, geometry.union(cut))
        except GeometryError:
            return (), (), "polygon-cutout"
    if rules.has_outline_clearance or context.board_cutouts:
        edge = rules.edge(me)
        if isinstance(edge, str):
            return (), (), edge
        margin = edge_reach(edge) + h
        if rules.has_outline_clearance and margin > 0:
            inner = geometry.offset(context.board, -margin, tol)
            area_now = geometry.meet(area_now, inner)
        elif context.board_cutouts:
            void = geometry.offset(context.board_cutouts, margin, tol) if margin else context.board_cutouts
            area_now = geometry.minus(area_now, void)
    voids: list[Polygon] = []
    joins: list[tuple[PourObject, Connection]] = []
    same: list[PourObject] = []
    for item in objects.by_layer.get(layer, []):
        if not item.box.intersects(reach):
            continue
        subject = object_subject(layer, item)
        own = net is not None and item.net == net
        if own and item.kind == "hole" and item.connect == "via":
            item = replace(item, kind="via")  # a via without a pad here: Altium joins it as a via (S-2227)
            subject = object_subject(layer, item)
        if own and item.kind in ("via", "pad") and item.connect is not None:
            found = governing_connection(context.styles, subject, me, item.connect, polygon.name)
            if isinstance(found, str):
                return (), (), found
            if item.concentric_drill is not None and item.concentric_drill > item.shape[1]:
                # Altium's relief air gap starts at the larger of the drilled extent and copper (S-2312).
                item = replace(item, shape=(item.shape[0], item.concentric_drill, False))
            joins.append((item, found))
            same.append(item)
            continue
        if own and item.kind in ("track", "arc"):
            same.append(item)
            if polygon.pour_over == "all":
                continue
        obstacle = rules.obstacle(me, subject, item, name=polygon.name)
        if isinstance(obstacle, str):
            return (), (), obstacle
        shape, value = obstacle
        # A region vertex rounds to the native file unit and back to nanometres.
        octagon = objects.octagonal_void(polygon, item, value + UNIT_SLACK_NM + 1)
        if octagon is not None:
            voids.append(octagon)
        else:
            # Native positive-clearance keep-out regions round their corners (S-2300, kit P8).
            voids.extend(geometry.grow(shape, value + h, tol, round_corners=item.kind == "keepout"))
    for other, pieces in state.poured:
        if not pieces or not other.box.intersects(reach):
            continue
        if net is not None and other.net == net and polygon.pour_over != "none":
            continue
        them = rule_subject(
            layer, "zone", other.net, objects.netclass.get(other.net, DEFAULT_CLASS), zone=other.name
        )
        value = rules.clearance(me, them, polygons=(polygon.name, other.name))
        if isinstance(value, str):
            return (), (), value
        voids.extend(geometry.offset(pieces, value + h + tol + 1, tol))
    forbidden = geometry.union(voids)
    gaps = {
        item: geometry.grow(item.shape, join.air_gap + h, tol)
        for item, join in joins
        if join.style in ("relief", "none")
    }
    copper = geometry.minus(
        area_now, geometry.union([*forbidden, *(g for pieces in gaps.values() for g in pieces)])
    )
    tracks: tuple[PourTrack, ...] = ()
    if polygon.hatch is not None:
        copper, tracks = _hatched(polygon.hatch, copper, joins, forbidden, area_now, geometry, tol)
    elif polygon.neck > 0 and copper:
        # the result is cut back to the copper it was made from: the chords of Clipper's offsets would grow
        # it by their sag, and no void may lose its clearance
        try:
            copper = geometry.open(copper, polygon.neck, tol)
        except GeometryError as error:
            if not _resource_bound(error):
                raise  # any other refusal of the exact cut reaches the build (c0332)
            return (), (), "neck-bound"  # the exact cut's resource bound (``_certified_neck_cut``; row -08)
    if polygon.hatch is None:
        if polygon.islands is not None:
            # A sub-threshold receiver is removed before a spoke can attach it (S-2321).
            copper = tuple(piece for piece in copper if area(piece) >= polygon.islands)
        conductors = _conductors(joins, gaps, copper, forbidden, area_now, geometry, tol)
        if conductors:
            copper = geometry.union([*copper, *conductors])
    pieces = list(copper)
    if polygon.islands is not None:
        pieces = [piece for piece in pieces if area(piece) >= polygon.islands]
    if polygon.remove_dead:
        if net is None:
            return (), (), ""
        touch = [g for item in same for g in geometry.grow(item.shape, TOUCH_NM, tol)]
        for other, others in state.poured:
            if other.net == net and polygon.pour_over != "none":
                touch.extend(others)
        if len(pieces) > 1 and len(touch) > 1:
            contacts = SpatialIndex[Polygon].build((contact.bbox(), contact) for contact in touch)
            pieces = [piece for piece in pieces if geometry.meet((piece,), contacts.query(piece.bbox()))]
        else:
            pieces = [piece for piece in pieces if geometry.meet((piece,), touch)]
    if tracks and len(pieces) < len(copper):  # a removed piece takes its tracks with it
        tracks = tuple(t for t in tracks if _on(pieces, t))
    return tuple(pieces), tracks, ""


def _on(pieces: Sequence[Polygon], track: PourTrack) -> bool:
    """Whether the middle of ``track`` lies on ``pieces``."""
    from fenolite.geometry.polygon import Location

    a, b, _ = track
    middle = Point((a.x + b.x) // 2, (a.y + b.y) // 2)
    return any(piece.locate(middle) != Location.OUTSIDE for piece in pieces)


def _hatched(
    hatch: tuple[str, Nm, Nm],
    area: Sequence[Polygon],
    joins: Sequence[tuple[PourObject, Connection]],
    forbidden: Sequence[Polygon],
    area_now: Sequence[Polygon],
    geometry: _Geometry,
    tol: int,
) -> tuple[tuple[Polygon, ...], tuple[PourTrack, ...]]:
    """The copper and the tracks of a hatch (``H-A-POUR-HATCH``; S-2223) over ``area``, the solid pour's
    area with every distance grown by half the width ``h``: a track of the width along every edge of
    ``area`` (round ends, so their copper is ``area`` grown by ``h`` less ``area`` shrunk by ``h``), the
    parts of the grid lines inside ``area`` (``hatch.grid_segments``), and for each relief a conductor of
    its width from the pad's centre to the edge of its air gap, along each direction of ``_conductors``. A
    conductor that would come within a clearance of another net (``forbidden`` shrunk by ``h``), leave the
    polygon or reach no copper is left out. The neck removal does not apply (no record shows it)."""
    style, grid, width = hatch
    h = width // 2
    area = _without_debris(area, tol)
    if not area:
        return (), ()
    tracks: list[PourTrack] = []
    for piece in area:
        for ring in piece.rings():
            for a, b in zip(ring, (*ring[1:], ring[0]), strict=True):
                tracks.append((a, b, width))
    lines = grid_segments(area, style, grid)
    tracks.extend((a, b, width) for a, b in lines)
    copper: list[Polygon] = [
        *geometry.minus(geometry.offset(area, h, tol), geometry.offset(area, -h, tol)),
    ]
    if lines:
        copper.extend(geometry.backend.stroke([(a, b) for a, b in lines], h, tol=max(tol // 8, 10)))
    band = geometry.union(copper)
    clear: tuple[Polygon, ...] | None = None
    for item, join in joins:
        if join.style != "relief" or item.center is None:
            continue
        if clear is None:
            clear = geometry.offset(forbidden, -h, tol) if forbidden else ()
        core, shape_width, _ = item.shape
        radius = max(max(abs(p.x - item.center.x), abs(p.y - item.center.y)) for p in core) * 2 + shape_width
        length = radius + join.air_gap + join.conductor_width
        step = 360_000_000 // join.conductors
        turn = item.rotation if item.kind == "pad" else 0
        within = geometry.union([*area_now, *_pad(item, geometry, tol)])
        gap = geometry.meet(geometry.grow(item.shape, join.air_gap, tol), within)
        half = max(join.conductor_width // 2, 1)
        for k in range(join.conductors):
            tip = rotate_point(Point(length, 0), join.angle + turn + k * step)
            part = first_part(gap, item.center, Point(item.center.x + tip.x, item.center.y + tip.y))
            if part is None:
                continue
            spoke = geometry.backend.stroke([part], half, tol=max(tol // 8, 10))
            if geometry.meet(spoke, clear) or not geometry.meet(spoke, band):
                continue
            tracks.append((part[0], part[1], join.conductor_width))
            copper.extend(spoke)
    return geometry.union(copper), tuple(tracks)


def _conductors(
    joins: Sequence[tuple[PourObject, Connection]],
    gaps: Mapping[PourObject, tuple[Polygon, ...]],
    copper: Sequence[Polygon],
    forbidden: Sequence[Polygon],
    area_now: Sequence[Polygon],
    geometry: _Geometry,
    tol: int,
) -> list[Polygon]:
    """The relief conductors of I6: bars of the conductor width from each pad's or via's centre, turned with
    a pad, within the pad grown by the air gap and the conductor width, and within the polygon or the pad
    itself (S-2224 row -07). A through-hole copper capsule in 45° mode starts at the copper endpoint
    facing each spoke (S-2308). A bar that would enter another net's clearance, leave both or reach no
    copper is left out. A 90° SMD relief avoids a facing SMD relief pad's air gap (S-2309). A bar whose
    extension alone meets that gap can still join a full-width receiver, clipped at the peer gap (S-2317)."""
    if not any(join.style == "relief" for _, join in joins):
        return []
    blocked = geometry.backend.prepare_intersection(forbidden)
    receivers = geometry.backend.prepare_intersection(copper)
    smd_gaps = [
        (item, item.box.inflate(join.air_gap + tol + UNIT_SLACK_NM), gaps[item])
        for item, join in joins
        if item.pad_type == "smd" and join.style == "relief"
    ]
    found: list[Polygon] = []
    for item, join in joins:
        if join.style != "relief" or item.center is None:
            continue
        core, width, filled = item.shape
        radius = max(max(abs(p.x - item.center.x), abs(p.y - item.center.y)) for p in core) * 2 + width
        length = radius + join.air_gap + join.conductor_width
        step = 360_000_000 // join.conductors
        turn = item.rotation if item.kind == "pad" else 0
        ring = geometry.grow(item.shape, join.air_gap + join.conductor_width, tol)
        within = geometry.union([*area_now, *_pad(item, geometry, tol)])
        neighbors: list[tuple[Point, tuple[Polygon, ...]]] = []
        if item.pad_type == "smd" and join.angle == 0 and join.conductors == 4:
            reach = item.box.inflate(join.air_gap + join.conductor_width + tol + UNIT_SLACK_NM)
            neighbors = [
                (peer.center, pieces)
                for peer, box, pieces in smd_gaps
                if peer is not item and peer.center is not None and box.intersects(reach)
            ]
        for k in range(join.conductors):
            angle = join.angle + turn + k * step
            origin = item.center
            if item.pad_type == "th" and join.angle == 45_000_000 and len(core) == 2 and not filled:
                # Select the end of the copper capsule that faces the spoke (S-2308).
                start, end = core
                direction = rotate_point(Point(length, 0), angle)
                advance = (end.x - start.x) * direction.x + (end.y - start.y) * direction.y
                if advance:
                    origin = end if advance > 0 else start
            bar = _bar(origin, angle, length, join.conductor_width)
            spoke = geometry.meet(geometry.meet((bar,), ring), within)
            if not spoke:
                continue
            box = BBox.of_points([point for piece in spoke for point in piece.outer])
            if geometry.backend.intersection_prepared(spoke, blocked.query(box), box):
                continue
            receiver = geometry.backend.intersection_prepared(spoke, receivers.query(box), box)
            if not receiver:
                continue
            if neighbors:
                direction = rotate_point(Point(length, 0), angle)
                peer_gaps = [
                    gap
                    for center, pieces in neighbors
                    if (center.x - origin.x) * direction.x + (center.y - origin.y) * direction.y > 0
                    for gap in pieces
                ]
                if geometry.meet(spoke, peer_gaps):
                    span = geometry.meet(spoke, gaps[item])
                    if geometry.meet(span, peer_gaps):
                        continue
                    normal = rotate_point(Point(0, length), angle)
                    width = _projected_width(bar, normal)
                    if all(_projected_width(part, normal) < width for part in receiver):
                        continue
                    spoke = tuple(
                        part
                        for part in geometry.minus(spoke, peer_gaps)
                        if geometry.meet((part,), span) and geometry.meet((part,), receiver)
                    )
            found.extend(spoke)
    return found


def poured_tracks(
    document: PcbDocument, index: int, tol: int = 50
) -> tuple[tuple[tuple[Point, ...], Nm], ...]:
    """The tracks and arcs of ``document`` that carry the polygon index ``index``, the copper of a hatched
    pour (S-2223), each as its centre line in the frame of the import and its width: a track as its two
    ends, an arc as a chain of points on it with every chord within ``tol`` of the arc."""
    from fenolite.backends.altium.adapter.units import angle, arc_points, circle_points, pcb_length, pcb_point
    from fenolite.geometry.shapes import Circle

    found: list[tuple[tuple[Point, ...], Nm]] = []
    for track in document.tracks:
        if isinstance(track, TrackRecord) and track.prefix.polygon == index:
            a, b = pcb_point(track.x1, track.y1), pcb_point(track.x2, track.y2)
            found.append(((a, b), pcb_length(track.width)))
    for arc in document.arcs:
        if not isinstance(arc, ArcRecord) or arc.prefix.polygon != index or arc.radius <= 0:
            continue
        start, end = angle(arc.start_angle)[0], angle(arc.end_angle)[0]
        if (end - start) % 360_000_000 == 0:
            centre, _ = circle_points(arc.cx, arc.cy, arc.radius)
            ring = Circle.from_radius(centre, pcb_length(arc.radius)).polygonize(tol)
            found.append(((*ring, ring[0]), pcb_length(arc.width)))
            continue
        first, middle, last = arc_points(arc.cx, arc.cy, arc.radius, start, end)
        found.append((GeoArc(first, middle, last).polygonize(tol), pcb_length(arc.width)))
    return tuple(found)


def _pad(item: PourObject, geometry: _Geometry, tol: int) -> tuple[Polygon, ...]:
    """The copper of the pad or via ``item`` itself, its shape grown by nothing."""
    core, width, filled = item.shape
    if filled:
        return (Polygon(core),)
    return geometry.grow(item.shape, 0, tol) if width > 0 else ()


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
    exact predicates of the copper check (``geometry.thick``) on the fills of the import, and on the tracks
    and arcs of a hatched polygon (``poured_tracks``), which the import does not read as fills. For a
    simple octagonal SMD pad in a solid pour, test the fill against its native clearance void (S-2314)."""
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
        for core, width in poured_tracks(reading.document, pour.index) if polygon.hatch is not None else ():
            try:
                shape = Thick(core, width, filled=False)
            except (GeometryError, ValueError):
                continue
            box = BBox.of_points(core).inflate((width + 1) // 2)
            fills.setdefault(polygon.layer, []).append((pour.index, pour.net, shape, box))
    failed: set[int] = set()
    geometry: _Geometry | None = None
    for layer, found in fills.items():
        for index, net, shape, box in found:
            if index in failed:
                continue
            polygon = polygons[index]
            name = polygon.name
            me = rule_subject(layer, "zone", net, objects.netclass.get(net, DEFAULT_CLASS), zone=name)
            near = box.inflate(rules.largest + 1)
            for item in objects.by_layer.get(layer, []):
                if (net is not None and item.net == net) or not item.box.intersects(near):
                    continue
                subject = object_subject(layer, item)
                obstacle = rules.obstacle(me, subject, item, name=name)
                if isinstance(obstacle, str):
                    continue
                (core, width, filled), value = obstacle
                octagon = objects.octagonal_void(polygon, item, value)
                if octagon is None:
                    violates = thick_closer_than(shape, Thick(core, width, filled), value)
                else:
                    if geometry is None:
                        geometry = _Geometry(ClipperBackend())
                    try:
                        violates = bool(geometry.meet((Polygon(shape.core),), (octagon,)))
                    except GeometryError:
                        violates = True
                if violates:
                    failed.add(index)
                    break
            if index in failed:
                continue
            for other, other_net, other_shape, other_box in found:
                if other == index or (net is not None and other_net == net) or not other_box.intersects(near):
                    continue
                them = rule_subject(
                    layer, "zone", other_net, objects.netclass.get(other_net, DEFAULT_CLASS),
                    zone=polygons[other].name,
                )  # fmt: skip
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
    "poured_tracks",
    "PourTrack",
    "rule_subject",
    "pour_reading",
    "read_pour",
]

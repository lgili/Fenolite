# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad lowering of a board imported from Altium (capability design-conversion, "Layers of a
converted Altium board", "Keep-out outlines of a converted Altium board" and "Slots of a converted Altium
board"; change c0161).

The Altium import names its layers in a neutral form (``docs/formats/altium/import.md``, "Layers"):
``F.Cu``, ``In<k>.Cu`` and ``B.Cu`` for the copper chain, the KiCad names for silkscreen, paste and mask,
``Edge.Cuts``, ``Mech.<n>``, ``Altium.KeepOut``, ``Altium.DrillGuide``, ``Altium.DrillDrawing`` and
``Altium.<id>``. ``lower_board`` gives the board a KiCad layer table (``layers.board_rows`` and
``layers.user_rows``) and moves every item onto a row of it, or out of the board with a reason:

- copper: an even count keeps its names; an odd count gets one empty inner layer before ``B.Cu`` (and a
  copy of the last dielectric and copper sheet in the stack-up), counted ``changed`` under ``stackup``;
- ``Mech.<n>`` goes to ``User.<n>`` while ``n`` is at most the target's ``USER_LAYERS`` (the inverse of
  c0160's ``KICAD_MECHANICAL``), the Altium layer's name as the user name; above, its items are lost;
- each closed outline of the drawings on ``Altium.KeepOut`` (a polygon, a rectangle, a circle, or lines
  and arcs that join into a ring) becomes a rule area on every copper layer that keeps out tracks, vias
  and copper pour (S-0742, ``H-A-IMP-KEEPOUT-LAYER``); an open line is lost;
- the drill layers and the layers outside the stack lose their items.

It also turns each slot from the import's frame (the footprint's, ``adapter/pads.py``) into the pad's
frame that the KiCad writers take, names each footprint ``<project>:<name>``, and renames a net whose
stored form another net already holds. Nothing is written here.
"""

from __future__ import annotations

import dataclasses
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from fenolite.backends.kicad.layers import (
    CREATED_ROWS,
    MAX_COPPER,
    USER_LAYERS,
    Row,
    board_rows,
    layers_of_rows,
    user_rows,
)
from fenolite.backends.kicad.pcb import stored_net_name
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.geometry.shapes import Arc as ArcShape
from fenolite.geometry.shapes import Circle
from fenolite.geometry.transform import FULL_TURN, Transform
from fenolite.model.board import Arc as ArcItem
from fenolite.model.board import (
    Board,
    Dimension,
    FootprintField,
    FootprintInstance,
    Graphic,
    Keepout,
    Layer,
    Pad,
    Padstack,
    StackLayer,
    Text,
    Track,
    Via,
    Zone,
)
from fenolite.model.circuit import Circuit, Net
from fenolite.model.design import Design

KEEPOUT = "Altium.KeepOut"
MECH = re.compile(r"Mech\.([1-9]\d*)")
HALF_TURN = 180_000_000
QUARTER_TURN = 90_000_000
ARC_TOLERANCE = 5_000
"""The largest distance (5 µm) between a keep-out arc or circle and the segments that stand for it."""
JOIN_TOLERANCE = 25_400
"""How far apart (1 mil, on each axis) two ends of keep-out drawings may lie and still join into an
outline: a public document draws its keep-out ring with ends 3 nm to 10 µm apart (``-01``, 2026-10-09)."""
NON_COPPER = frozenset(row[1] for row in CREATED_ROWS if not row[1].endswith(".Cu"))
"""The non-copper names of KiCad's table that the import may use as they are."""

REASON_OUTSIDE = "a layer outside the stack"
REASON_DRILL = "a drill drawing or drill guide: KiCad draws its drill map from the holes"
REASON_MECH = "a mechanical layer beyond the user layers of the target"
REASON_KEEPOUT_OPEN = "a keep-out line that encloses no area"
REASON_KEEPOUT_AREA = "a keep-out outline is a rule area on every copper layer"
REASON_KEEPOUT_TEXT = "a text on the keep-out layer"
REASON_KEEPOUT_ARC = "a keep-out outline is written as segments: arcs within 5 µm, ends joined within 1 mil"
REASON_KEEPOUT_FOOTPRINT = "a keep-out outline of a footprint is a rule area of the board"
REASON_KEEPOUT_ITEM = "a copper item on the keep-out layer"
REASON_ODD = "an odd count of signal layers gets one empty inner layer before B.Cu"
REASON_SLOT = "a slot turned against a pad of this shape"
REASON_PADSTACK = "per-layer copper shapes are written as the pad's outer shape on every layer"
REASON_NET = "two nets of one stored name: the second is renamed"
REASON_FIELD = "a field on a layer KiCad cannot hold is placed on the fabrication layer of its side"
REASON_NAME = "a footprint name with characters a KiCad name cannot hold is written with _"

Items = dict[str, dict[str, list[str]]]
"""Kind → reason → the ids of the items (``convert.report.Items``)."""


@dataclass
class Lowered:
    """The lowered design, and the items it changed and lost, per kind and reason."""

    design: Design
    changed: Items = field(default_factory=lambda: defaultdict(lambda: defaultdict(list)))
    lost: Items = field(default_factory=lambda: defaultdict(lambda: defaultdict(list)))
    user_names: dict[str, str] = field(default_factory=lambda: {})
    """Each user layer the board holds and the Altium layer it comes from."""

    def change(self, kind: str, reason: str, ident: str) -> None:
        self.changed[kind][reason].append(ident)

    def lose(self, kind: str, reason: str, ident: str) -> None:
        self.lost[kind][reason].append(ident)

    def items(self, which: Items) -> dict[str, dict[str, tuple[str, ...]]]:
        return {kind: {r: tuple(ids) for r, ids in reasons.items() if ids} for kind, reasons in which.items()}


@dataclass(frozen=True)
class LayerMap:
    """The KiCad table of a board and where each imported layer name goes: ``renamed`` maps a name to
    its KiCad name, ``lost`` a name to the reason its items are lost; ``Altium.KeepOut`` is in neither."""

    rows: tuple[Row, ...]
    renamed: Mapping[str, str]
    lost: Mapping[str, str]
    added: tuple[str, ...] = ()
    """The empty inner copper layer of an odd count, if any."""


def _altium_name(layer: Layer) -> str | None:
    bag = layer.ext.get("altium")
    return None if bag is None else dict(bag.payload).get("altium_name")


def layer_map(board: Board, *, target: int) -> LayerMap:
    """The KiCad layer table of ``board`` for ``target`` and the map of its layer names. Raises
    ``ValueError`` for more than ``MAX_COPPER`` copper layers."""
    copper = [layer for layer in sorted(board.layers, key=lambda x: x.ordinal) if layer.kind == "copper"]
    count = len(copper)
    if count > MAX_COPPER:
        raise ValueError(f"the board has {count} copper layers; a KiCad board holds at most {MAX_COPPER}")
    even = max(count + count % 2, 2)
    rows = list(board_rows(even))
    renamed: dict[str, str] = {layer.name: layer.name for layer in copper}
    added = (f"In{even - 2}.Cu",) if count % 2 else ()
    lost: dict[str, str] = {}
    most = USER_LAYERS[target]
    users: dict[int, str | None] = {}
    for layer in board.layers:
        name = layer.name
        if layer.kind == "copper":
            continue
        match = MECH.fullmatch(name)
        if name in NON_COPPER:
            renamed[name] = name
        elif match is not None:
            number = int(match.group(1))
            if number <= most:
                renamed[name] = f"User.{number}"
                users[number] = _altium_name(layer)
            else:
                lost[name] = REASON_MECH
        elif name == KEEPOUT:
            continue
        elif name in ("Altium.DrillDrawing", "Altium.DrillGuide"):
            lost[name] = REASON_DRILL
        else:
            lost[name] = REASON_OUTSIDE
    if users:
        names = [users.get(n) for n in range(1, max(users) + 1)]
        rows += user_rows(max(users), target=target, names=names)
    return LayerMap(tuple(rows), renamed, lost, added)


def _odd_stackup(board: Board, added: str) -> Board:
    """``board`` whose stack-up holds a copy of its last dielectric and inner copper sheet before ``B.Cu``,
    named ``added``; a board without a stack-up is returned as it is."""
    stackup = board.stackup
    if stackup is None:
        return board
    entries = list(stackup.layers)
    index = next((i for i, e in enumerate(entries) if e.kind == "copper" and e.name == "B.Cu"), None)
    if index is None or index == 0:
        return board
    before = entries[index - 1]
    dielectric = dataclasses.replace(before, id=derived_id("sly", "fenolite", f"{before.id}:odd"))
    sheet: StackLayer = dataclasses.replace(
        entries[index], id=derived_id("sly", "fenolite", f"{stackup.id}:{added}"), name=added
    )
    entries[index:index] = [sheet, dielectric]
    return dataclasses.replace(board, stackup=dataclasses.replace(stackup, layers=tuple(entries)))


# --- keep-out outlines ------------------------------------------------------------------------------


def _segments(graphic: Graphic) -> tuple[list[Point], bool] | None:
    """The points of an open drawing (a line or an arc) and whether arcs were approximated; ``None`` for
    a closed one."""
    if graphic.kind == "line":
        return list(graphic.points), False
    if graphic.kind == "arc":
        start, mid, end = graphic.points[0], graphic.points[1], graphic.points[2]
        return list(ArcShape(start, mid, end).polygonize(ARC_TOLERANCE)), True
    return None


def _closed(graphic: Graphic) -> tuple[tuple[Point, ...], bool] | None:
    """The ring of a closed drawing and whether a curve was approximated; ``None`` for an open one."""
    points = list(graphic.points)
    if graphic.kind == "polygon" and len(points) >= 3:
        return tuple(points), False
    if graphic.kind == "rect":
        a, b = points[0], points[1]
        return (a, Point(b.x, a.y), b, Point(a.x, b.y)), False
    if graphic.kind == "circle":
        centre, end = points[0], points[1]
        return tuple(Circle.from_kicad(centre, end).polygonize(ARC_TOLERANCE)), True
    return None


def keepout_rings(
    graphics: Sequence[Graphic],
) -> tuple[list[tuple[tuple[Point, ...], list[str], bool]], list[str]]:
    """The closed outlines among ``graphics`` (all on the keep-out layer, in the board frame) and the ids
    of the open drawings left over. Each outline is ``(ring, ids, approximated)``. Lines and arcs join
    where their ends are equal to the nanometre; a chain whose every end meets exactly one other is a
    ring."""
    rings: list[tuple[tuple[Point, ...], list[str], bool]] = []
    pieces: list[tuple[str, list[Point], bool]] = []
    for graphic in graphics:
        closed = _closed(graphic)
        if closed is not None:
            rings.append((closed[0], [graphic.id], closed[1]))
            continue
        found = _segments(graphic)
        if found is not None and len(found[0]) >= 2:
            pieces.append((graphic.id, found[0], found[1]))
    representatives: list[Point] = []

    def snap(point: Point) -> Point:
        for known in representatives:
            if abs(known.x - point.x) <= JOIN_TOLERANCE and abs(known.y - point.y) <= JOIN_TOLERANCE:
                return known
        representatives.append(point)
        return point

    snapped: list[tuple[str, list[Point], bool]] = []
    for ident, points, curved in pieces:
        first, last = snap(points[0]), snap(points[-1])
        moved = first != points[0] or last != points[-1]
        snapped.append((ident, [first, *points[1:-1], last], curved or moved))
    pieces = snapped
    ends: dict[Point, list[int]] = defaultdict(list)
    for index, (_, points, _) in enumerate(pieces):
        ends[points[0]].append(index)
        ends[points[-1]].append(index)
    used: set[int] = set()
    left: list[str] = []
    for start in range(len(pieces)):
        if start in used:
            continue
        chain = [start]
        used.add(start)
        ident, points, curved = pieces[start]
        ring = list(points)
        ids, approximated = [ident], curved
        closed = False
        while True:
            tail = ring[-1]
            if tail == ring[0] and len(chain) > 0 and len(ring) > 2:
                closed = True
                break
            nxt = [i for i in ends[tail] if i not in used]
            if len(ends[tail]) != 2 or len(nxt) != 1:
                break
            i = nxt[0]
            used.add(i)
            chain.append(i)
            other_id, other, other_curved = pieces[i]
            other = other if other[0] == tail else list(reversed(other))
            ring += other[1:]
            ids.append(other_id)
            approximated = approximated or other_curved
        if closed and len(set(ring)) >= 3:
            rings.append((tuple(ring[:-1]), ids, approximated))
        else:
            left += ids
    return rings, left


# --- the board --------------------------------------------------------------------------------------


_NAME_CHARS = re.compile(r"[\\/:]")


def footprint_name(lib_ref: str) -> str:
    """The name of a footprint in a KiCad library from the import's ``lib_ref`` (``<library>:<name>`` or
    ``<name>``): the part after the first colon, with each character a KiCad name or a file name cannot
    hold written ``_``."""
    _, colon, name = lib_ref.partition(":")
    name = name if colon else lib_ref
    return _NAME_CHARS.sub("_", name)


def _flip_side(name: str, bottom: bool) -> str:
    return ("B." if bottom else "F.") + name.split(".", 1)[1]


class _Board:
    """One lowering in progress."""

    def __init__(self, design: Design, project: str, target: int) -> None:
        assert design.board is not None
        self.design = design
        self.board = design.board
        self.project = project
        self.target = target
        self.map = layer_map(self.board, target=target)
        self.result = Lowered(design)

    def name(self, layer: str) -> str | None:
        return self.map.renamed.get(layer)

    def lost_reason(self, layer: str) -> str:
        return self.map.lost.get(layer, REASON_OUTSIDE)

    def layered(self, items: Iterable[Graphic | Text], kind: str) -> list[Graphic | Text]:
        kept: list[Graphic | Text] = []
        for item in items:
            name = self.name(item.layer)
            if name is None:
                reason = REASON_KEEPOUT_TEXT if item.layer == KEEPOUT else self.lost_reason(item.layer)
                self.result.lose(kind, reason, item.id)
                continue
            kept.append(item if name == item.layer else dataclasses.replace(item, layer=name))
        return kept

    def footprint(self, fp: FootprintInstance, keepouts: list[Graphic]) -> FootprintInstance:
        bottom = fp.side == "bottom"
        pads: list[Pad] = []
        for pad in fp.pads:
            lowered = self.pad(pad)
            if lowered is not None:
                pads.append(lowered)
        fields: list[FootprintField] = []
        for item in fp.fields:
            name = self.name(item.layer)
            if name is None:
                name = _flip_side("F.Fab", bottom)
                self.result.change("footprint-text", REASON_FIELD, item.id)
            fields.append(item if name == item.layer else dataclasses.replace(item, layer=name))
        graphics: list[Graphic] = []
        to_board = Transform.placement(fp.position, fp.rotation)
        for graphic in fp.graphics:
            if graphic.layer == KEEPOUT:
                points = tuple(to_board.apply(p) for p in graphic.points)
                keepouts.append(dataclasses.replace(graphic, points=points))
                continue
            graphics += [
                g for g in self.layered((graphic,), self.graphic_kind(graphic)) if isinstance(g, Graphic)
            ]
        texts = [t for t in self.layered(fp.texts, "footprint-text") if isinstance(t, Text)]
        name = footprint_name(fp.lib_ref)
        if name != (fp.lib_ref.partition(":")[2] or fp.lib_ref):
            self.result.change("footprint", REASON_NAME, fp.id)
        lib_ref = f"{self.project}:{name}" if name else ""
        return dataclasses.replace(
            fp,
            lib_ref=lib_ref,
            pads=tuple(pads),
            fields=tuple(fields),
            graphics=tuple(graphics),
            texts=tuple(texts),
        )

    @staticmethod
    def graphic_kind(graphic: Graphic) -> str:
        return "footprint-copper" if graphic.layer.endswith(".Cu") else "footprint-graphic"

    def pad(self, pad: Pad) -> Pad | None:
        layers = tuple(n for n in (self.name(x) for x in pad.layers) if n is not None)
        if layers != tuple(pad.layers):
            pad = dataclasses.replace(pad, layers=layers)
        stack = pad.padstack
        if stack is None:
            return pad
        if stack.layers:
            # the board writer writes one shape per created pad: a stack of one shape is that shape, and
            # another is written with the pad's own shape (its outer layers') on every layer
            uniform = all(
                e.shape == pad.shape and e.size == pad.size and e.offset == Point(0, 0) for e in stack.layers
            )
            if not uniform:
                self.result.change("pad", REASON_PADSTACK, pad.id)
            stack = dataclasses.replace(stack, layers=())
        if stack.hole_shape != "slot":
            return dataclasses.replace(pad, padstack=None if stack.hole_shape == "round" else stack)
        # the import gives the slot's axis in the footprint's frame; the KiCad writers take the pad's
        relative = (stack.hole_rotation - pad.rotation) % FULL_TURN
        stack = dataclasses.replace(stack, hole_rotation=relative)
        if relative % QUARTER_TURN and not _round(pad, stack):
            self.result.lose("pad", REASON_SLOT, pad.id)
            return None
        return dataclasses.replace(pad, padstack=stack)

    def lower(self) -> Lowered:
        board = self.board
        result = self.result
        keepouts: list[Graphic] = [g for g in board.graphics if g.layer == KEEPOUT]
        graphics = [g for g in board.graphics if g.layer != KEEPOUT]
        footprints = [self.footprint(fp, keepouts) for fp in board.footprints]
        footprint_keepouts = {g.id for fp in board.footprints for g in fp.graphics if g.layer == KEEPOUT}
        tracks: list[Track] = []
        for track in board.tracks:
            name = self.name(track.layer)
            if name is None:
                reason = REASON_KEEPOUT_ITEM if track.layer == KEEPOUT else self.lost_reason(track.layer)
                result.lose("track", reason, track.id)
            else:
                tracks.append(track)
        arcs: list[ArcItem] = []
        for arc in board.arcs:
            name = self.name(arc.layer)
            if name is None:
                reason = REASON_KEEPOUT_ITEM if arc.layer == KEEPOUT else self.lost_reason(arc.layer)
                result.lose("arc", reason, arc.id)
            else:
                arcs.append(arc)
        zones: list[Zone] = []
        for zone in board.zones:
            layers = tuple(n for n in (self.name(x) for x in zone.layers) if n is not None)
            if not layers:
                result.lose(
                    "zone", self.lost_reason(zone.layers[0]) if zone.layers else REASON_OUTSIDE, zone.id
                )
                continue
            fills = tuple(
                dataclasses.replace(f, layer=self.name(f.layer) or f.layer)
                for f in zone.fills
                if self.name(f.layer)
            )
            zones.append(dataclasses.replace(zone, layers=layers, fills=fills))
        areas = list(board.keepouts)
        copper = [row[1] for row in self.map.rows if row[1].endswith(".Cu")]
        rings, left = keepout_rings(keepouts)
        for ring, ids, approximated in rings:
            ident = derived_id("kpo", "fenolite", "keepout:" + ":".join(ids))
            areas.append(
                Keepout(
                    id=ident,
                    outline=ring,
                    layers=tuple(copper),
                    no_tracks=True,
                    no_vias=True,
                    no_copper_pour=True,
                )
            )
            for graphic_id in ids:
                kind = "footprint-graphic" if graphic_id in footprint_keepouts else "graphic"
                reason = REASON_KEEPOUT_FOOTPRINT if kind == "footprint-graphic" else REASON_KEEPOUT_AREA
                result.change(kind, reason, graphic_id)
            if approximated:
                result.change("keep-out", REASON_KEEPOUT_ARC, ident)
        for graphic_id in left:
            kind = "footprint-graphic" if graphic_id in footprint_keepouts else "graphic"
            result.lose(kind, REASON_KEEPOUT_OPEN, graphic_id)
        lowered_areas: list[Keepout] = []
        for area in areas:
            layers = tuple(n for n in (self.name(x) for x in area.layers) if n is not None)
            if not layers:
                result.lose("keep-out", REASON_OUTSIDE, area.id)
                continue
            lowered_areas.append(
                area if layers == tuple(area.layers) else dataclasses.replace(area, layers=layers)
            )
        vias: list[Via] = []
        for via in board.vias:
            layers = tuple(n for n in (self.name(x) for x in via.layers) if n is not None)
            if len(layers) != len(via.layers):
                result.lose("via", REASON_OUTSIDE, via.id)
                continue
            vias.append(via)
        texts = [t for t in self.layered(board.texts, "text") if isinstance(t, Text)]
        root_graphics = [g for g in self.layered(graphics, "graphic") if isinstance(g, Graphic)]
        dimensions: list[Dimension] = []
        for dimension in board.dimensions:
            name = self.name(dimension.layer)
            if name is None:
                result.lose("dimension", self.lost_reason(dimension.layer), dimension.id)
            else:
                dimensions.append(
                    dimension if name == dimension.layer else dataclasses.replace(dimension, layer=name)
                )
        made = dataclasses.replace(
            board,
            layers=layers_of_rows(self.map.rows),
            footprints=tuple(footprints),
            tracks=tuple(tracks),
            arcs=tuple(arcs),
            vias=tuple(vias),
            zones=tuple(zones),
            keepouts=tuple(lowered_areas),
            graphics=tuple(root_graphics),
            texts=tuple(texts),
            dimensions=tuple(dimensions),
        )
        if self.map.added:
            made = _odd_stackup(made, self.map.added[0])
            ident = board.stackup.id if board.stackup is not None else board.id
            result.change("stackup", REASON_ODD, ident)
        circuit = self.nets(self.design)
        result.design = dataclasses.replace(self.design, circuit=circuit, board=made)
        result.user_names = {
            f"User.{m.group(1)}": layer.name
            for layer in board.layers
            if (m := MECH.fullmatch(layer.name)) is not None and layer.name in self.map.renamed
        }
        return result

    def nets(self, design: Design) -> Circuit:
        seen: set[str] = set()
        nets: list[Net] = []
        for net in design.circuit.nets:
            stored = stored_net_name(net)
            if stored in seen or not net.name:
                base = net.name or "Net"
                n = 2
                while stored_net_name(dataclasses.replace(net, name=f"{base}_{n}")) in seen:
                    n += 1
                net = dataclasses.replace(net, name=f"{base}_{n}")
                stored = stored_net_name(net)
                self.result.change("net", REASON_NET, net.id)
            seen.add(stored)
            nets.append(net)
        return dataclasses.replace(design.circuit, nets=tuple(nets))


def _round(pad: Pad, stack: Padstack) -> bool:
    """Whether ``pad`` has round copper on every layer: a circle, or an oval of equal sides."""
    if stack.layers:
        return all(
            entry.shape == "circle" or (entry.shape == "oval" and entry.size.w == entry.size.h)
            for entry in stack.layers
        )
    return pad.shape == "circle" or (pad.shape == "oval" and pad.size.w == pad.size.h)


def lower_board(design: Design, *, project: str, target: int) -> Lowered:
    """The design of an Altium import with a KiCad layer table and every item on a row of it, for
    ``target``; what moved or went, per kind and reason. A design without a board is returned as it is."""
    if design.board is None:
        return Lowered(design)
    return _Board(design, project, target).lower()


__all__ = [
    "ARC_TOLERANCE",
    "KEEPOUT",
    "LayerMap",
    "Lowered",
    "footprint_name",
    "keepout_rings",
    "layer_map",
    "lower_board",
]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper of each net as pieces, and the test that an edit keeps the connected groups of a net
(capability copper-tidy, "Prune dangling copper" and "Chamfer joints").

A piece is one copper item with its thick shapes per copper layer, built as ``analysis.copper`` builds
them for the copper check: a track is its segment, an arc the polyline of its polygonisation, a via a
disc on every layer of its span, a pad the entries of its board-frame record, a zone fill a filled ring.
Two pieces are joined when shapes of both on one layer touch (``geometry.touch_groups``), as in
``analysis.connectivity``. This package may not import ``analysis``, so the shapes are built here.

Zone outlines are kept apart: a fill may be stale or missing, so a track end or a via inside the outline
of a zone of its own net counts as joined there (``joined_at``), while the groups count stored fills
only.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import partial

from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.geometry import Arc as GeoArc
from fenolite.geometry import BBox, GeometryError, Thick, thick_bbox, thick_touch, touch_groups
from fenolite.model.board import Arc, Board, Track, Via
from fenolite.model.design import Design

ARC_TOL_NM = 1_000
"""The chord error of a polygonised arc, as in ``analysis.copper``."""
_WILDCARDS = ("*", "&")


@dataclass(frozen=True, slots=True)
class Piece:
    """One copper item of a net: its kind (``track``, ``arc``, ``via``, ``pad``, ``fill`` or ``zone`` for
    an outline), its id (a fill: ``<zone id>#<index>``) and its shapes as ``(layer, shape)``."""

    kind: str
    ident: str
    shapes: tuple[tuple[str, Thick], ...]


@dataclass(frozen=True, slots=True)
class NetPieces:
    """The pieces per net id, the zone outlines per net id, and the net ids with an item that could not
    be shaped (a tidy step leaves such a net alone)."""

    pieces: Mapping[str, tuple[Piece, ...]] = field(default_factory=lambda: {})
    outlines: Mapping[str, tuple[Piece, ...]] = field(default_factory=lambda: {})
    unsupported: frozenset[str] = frozenset()


def copper_layers(board: Board) -> tuple[str, ...]:
    """The copper layers of the board, in table order."""
    return tuple(layer.name for layer in board.layers if layer.kind == "copper")


def expand_layers(layers: Iterable[str], copper: Sequence[str]) -> tuple[str, ...]:
    """The copper layers that ``layers`` name, wildcards (``*.Cu``, ``F&B.Cu``) expanded, in table
    order."""
    named: set[str] = set()
    for name in layers:
        if name in copper:
            named.add(name)
        elif any(mark in name for mark in _WILDCARDS) and name.endswith(".Cu"):
            pattern = name.replace("F&B", "[FB]")
            named.update(layer for layer in copper if fnmatch.fnmatchcase(layer, pattern))
    return tuple(layer for layer in copper if layer in named)


def via_span(via: Via, copper: tuple[str, ...]) -> tuple[str, ...]:
    """The copper layers a via has copper on: every layer for a through via, else those between its two
    layers."""
    layers = via.layers
    if via.via_type == "through" or len(layers) != 2 or layers[0] not in copper or layers[1] not in copper:
        return copper
    first, last = sorted((copper.index(layers[0]), copper.index(layers[1])))
    return copper[first : last + 1]


def track_piece(track: Track) -> Piece:
    """The piece of a track; ``GeometryError`` or ``ValueError`` when it cannot be shaped."""
    return Piece("track", track.id, ((track.layer, Thick((track.start, track.end), track.width)),))


def arc_piece(arc: Arc) -> Piece:
    shape = Thick(GeoArc(arc.start, arc.mid, arc.end).polygonize(ARC_TOL_NM), arc.width)
    return Piece("arc", arc.id, ((arc.layer, shape),))


def via_piece(via: Via, copper: tuple[str, ...]) -> Piece:
    shape = Thick((via.position,), via.diameter)
    return Piece("via", via.id, tuple((layer, shape) for layer in via_span(via, copper)))


def pad_piece(record: BoardPad) -> Piece:
    """The piece of a board-frame pad record: its copper entries."""
    shapes = tuple((entry.layer, Thick(entry.core, entry.width, entry.filled)) for entry in record.copper)
    return Piece("pad", record.pad_id, shapes)


def _fill_piece(ident: str, layer: str, polygon: Sequence[Point]) -> Piece:
    return Piece("fill", ident, ((layer, Thick(ring(polygon), 0, filled=True)),))


def ring(points: Sequence[Point]) -> tuple[Point, ...]:
    """``points`` as a ring: repeated neighbours and a closing repeat of the first point left out."""
    out: list[Point] = []
    for point in points:
        if not out or out[-1] != point:
            out.append(point)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return tuple(out)


def net_pieces(design: Design, pads: Sequence[BoardPad]) -> NetPieces:
    """The pieces of every net of ``design.board``; copper without a net is left out."""
    board = design.board
    if board is None:
        return NetPieces()
    copper = copper_layers(board)
    found: dict[str, list[Piece]] = {}
    outlines: dict[str, list[Piece]] = {}
    unsupported: set[str] = set()

    def add(net_id: str | None, make: Callable[[], Piece]) -> None:
        if net_id is None:
            return
        try:
            piece = make()
        except (GeometryError, ValueError):
            unsupported.add(net_id)
            return
        found.setdefault(net_id, []).append(piece)

    for track in board.tracks:
        add(track.net_id, partial(track_piece, track))
    for arc in board.arcs:
        add(arc.net_id, partial(arc_piece, arc))
    for via in board.vias:
        add(via.net_id, partial(via_piece, via, copper))
    for record in pads:
        if record.kind == "np_thru_hole" or record.net_id is None:
            continue
        if not record.copper:
            if expand_layers(record.layers, copper):
                unsupported.add(record.net_id)
            continue
        add(record.net_id, partial(pad_piece, record))
    for zone in board.zones:
        if zone.net_id is None:
            continue
        for index, fill in enumerate(zone.fills):
            add(zone.net_id, partial(_fill_piece, f"{zone.id}#{index}", fill.layer, fill.polygon))
        try:
            area = Thick(ring(zone.outline), 0, filled=True)
        except (GeometryError, ValueError):
            unsupported.add(zone.net_id)
            continue
        layers = expand_layers(zone.layers, copper)
        outlines.setdefault(zone.net_id, []).append(
            Piece("zone", zone.id, tuple((layer, area) for layer in layers))
        )
    return NetPieces(
        {net: tuple(held) for net, held in found.items()},
        {net: tuple(held) for net, held in outlines.items()},
        frozenset(unsupported),
    )


def _meets(a: BBox, b: BBox) -> bool:
    return a.x0 <= b.x1 and b.x0 <= a.x1 and a.y0 <= b.y1 and b.y0 <= a.y1


def joined_at(
    shape: Thick, layer: str, own: str, pieces: Iterable[Piece], outlines: Iterable[Piece] = ()
) -> bool:
    """Whether ``shape`` on ``layer`` touches a piece other than ``own``, or a zone outline."""
    box = thick_bbox(shape)
    for piece in (*pieces, *outlines):
        if piece.ident == own:
            continue
        for at, other in piece.shapes:
            if at == layer and _meets(box, thick_bbox(other)) and thick_touch(shape, other):
                return True
    return False


def groups(pieces: Sequence[Piece]) -> dict[str, int]:
    """The group of every piece by id: the index of the first piece of its group."""
    roots = touch_groups([piece.shapes for piece in pieces])
    return {piece.ident: root for piece, root in zip(pieces, roots, strict=True)}


def keeps_groups(before: Sequence[Piece], after: Sequence[Piece], *, removed: Collection[str] = ()) -> bool:
    """Whether ``after`` keeps the groups of ``before``.

    The pieces in both must be grouped alike: two of them are in one group after exactly when they were
    before. A piece only in ``after`` must be in a group that holds a piece of both, so an edit makes no
    new island. ``removed`` names pieces whose removal is allowed; any other piece of ``before`` must be
    in ``after``."""
    old, new = groups(before), groups(after)
    if any(ident not in new and ident not in removed for ident in old):
        return False
    forward: dict[int, int] = {}
    backward: dict[int, int] = {}
    for ident, root in old.items():
        if ident not in new:
            continue
        other = new[ident]
        if forward.setdefault(root, other) != other or backward.setdefault(other, root) != root:
            return False
    return all(root in backward for ident, root in new.items() if ident not in old)


__all__ = [
    "ARC_TOL_NM",
    "NetPieces",
    "Piece",
    "arc_piece",
    "copper_layers",
    "expand_layers",
    "groups",
    "joined_at",
    "keeps_groups",
    "net_pieces",
    "pad_piece",
    "ring",
    "track_piece",
    "via_piece",
    "via_span",
]

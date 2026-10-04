# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper of a board as thick shapes per net (capability board-analyses, "Copper of a net as thick
shapes").

The shapes are those that the capability copper-check defines in "Copper items and their shapes": a track
is its segment, an arc the polyline of its polygonisation with a band, a via a disc on every layer of its
span, a pad the entries of its board-frame record, and a zone fill a filled ring. ``checks.copper`` builds
the same shapes for ``fenolite check``; this package may not import ``checks``, so they are built here and
a test keeps the two builders equal.
"""

from __future__ import annotations

import fnmatch
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.geometry import Arc as GeoArc
from fenolite.geometry import GeometryError, Thick
from fenolite.model.base import Entity
from fenolite.model.board import Board
from fenolite.model.design import Design

ARC_TOL_NM = 1_000
"""The chord error of a polygonised arc; its band is ``ARC_TOL_NM + 1`` nm."""
_WILDCARDS = ("*", "&")


@dataclass(frozen=True, slots=True)
class CopperShape:
    """One thick shape of a copper item on a layer. ``where`` is ``REF-PIN`` for a pad, else the entity's
    locator or id; ``band`` bounds the approximation of the shape (an arc), else 0."""

    shape: Thick
    layer: str
    kind: str
    where: str
    entity_id: str
    band: int = 0


@dataclass(frozen=True, slots=True)
class NetCopper:
    """The shapes per net name, what could not be shaped per kind, and the two outer copper layers (the
    first is the top face)."""

    by_net: Mapping[str, tuple[CopperShape, ...]] = field(default_factory=lambda: {})
    unsupported: Mapping[str, int] = field(default_factory=lambda: {})
    outer: tuple[str, str] | None = None
    layers: tuple[str, ...] = ()


def _where(entity: Entity) -> str:
    provenance = entity.provenance
    return provenance.locator if provenance is not None and provenance.locator else entity.id


def _names_copper(layers: Sequence[str], copper: Sequence[str]) -> bool:
    known = set(copper)
    for name in layers:
        if name in known:
            return True
        if any(mark in name for mark in _WILDCARDS) and name.endswith(".Cu"):
            pattern = name.replace("F&B", "[FB]")
            if not copper or any(fnmatch.fnmatchcase(layer, pattern) for layer in copper):
                return True
    return False


def _clean_ring(points: Sequence[Point]) -> tuple[Point, ...]:
    out: list[Point] = []
    for point in points:
        if not out or out[-1] != point:
            out.append(point)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return tuple(out)


def _span(copper: tuple[str, ...], layers: Sequence[str], through: bool) -> tuple[str, ...]:
    if not copper:
        return tuple(dict.fromkeys(layers))
    if through or len(layers) != 2 or layers[0] not in copper or layers[1] not in copper:
        return copper
    first, last = sorted((copper.index(layers[0]), copper.index(layers[1])))
    return copper[first : last + 1]


def copper_layers(board: Board) -> tuple[str, ...]:
    """The copper layers of the board, in table order."""
    return tuple(layer.name for layer in board.layers if layer.kind == "copper")


def net_copper(design: Design, *, pads: Sequence[BoardPad] | None, arc_tol: int = ARC_TOL_NM) -> NetCopper:
    """The copper of the board per net. Copper without a net is left out. With ``pads`` ``None``, every
    pad that carries copper is counted as unsupported."""
    board = design.board
    if board is None:
        return NetCopper()
    names = {net.id: net.name for net in design.circuit.nets}
    copper = copper_layers(board)
    found: dict[str, list[CopperShape]] = {}
    unsupported: Counter[str] = Counter()

    def add(net_id: str | None, shape: CopperShape) -> None:
        if net_id is not None:
            found.setdefault(names.get(net_id, net_id), []).append(shape)

    for track in board.tracks:
        try:
            shape = Thick((track.start, track.end), track.width)
        except (GeometryError, ValueError):
            unsupported["track"] += 1
            continue
        add(track.net_id, CopperShape(shape, track.layer, "track", _where(track), track.id))
    for arc in board.arcs:
        try:
            shape = Thick(GeoArc(arc.start, arc.mid, arc.end).polygonize(arc_tol), arc.width)
        except (GeometryError, ValueError):
            unsupported["arc"] += 1
            continue
        add(arc.net_id, CopperShape(shape, arc.layer, "arc", _where(arc), arc.id, arc_tol + 1))
    for via in board.vias:
        try:
            shape = Thick((via.position,), via.diameter)
        except (GeometryError, ValueError):
            unsupported["via"] += 1
            continue
        for layer in _span(copper, via.layers, via.via_type == "through"):
            add(via.net_id, CopperShape(shape, layer, "via", _where(via), via.id))
    if pads is None:
        for footprint in board.footprints:
            for pad in footprint.pads:
                if pad.kind != "np_thru_hole" and _names_copper(pad.layers, copper):
                    unsupported["pad"] += 1
    else:
        for record in pads:
            if record.kind == "np_thru_hole":
                continue
            if not record.copper:
                if _names_copper(record.layers, copper):
                    unsupported["pad"] += 1
                continue
            try:
                shapes = [
                    (entry.layer, Thick(entry.core, entry.width, entry.filled)) for entry in record.copper
                ]
            except (GeometryError, ValueError):
                unsupported["pad"] += 1
                continue
            holder = record.ref or record.footprint_id
            where = f"{holder}-{record.number}" if record.number else holder
            for layer, shape in shapes:
                add(record.net_id, CopperShape(shape, layer, "pad", where, record.pad_id))
    for zone in board.zones:
        for fill in zone.fills:
            try:
                shape = Thick(_clean_ring(fill.polygon), 0, filled=True)
            except (GeometryError, ValueError):
                unsupported["fill"] += 1
                continue
            add(zone.net_id, CopperShape(shape, fill.layer, "fill", _where(zone), zone.id))
    outer = (copper[0], copper[-1]) if copper else None
    by_net = {name: tuple(shapes) for name, shapes in sorted(found.items())}
    return NetCopper(by_net, dict(sorted(unsupported.items())), outer, copper)


__all__ = ["ARC_TOL_NM", "CopperShape", "NetCopper", "copper_layers", "net_copper"]

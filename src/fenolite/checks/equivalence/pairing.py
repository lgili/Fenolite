# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pairing of one design held in two representations (change c0421; ``docs/equivalence.md``, "Pairing
across representations").

Each rule pairs items only when the two forms describe the same thing exactly, and leaves anything else to
the levels as before:

- ``layer_aliases``: a layer of one side pairs with a layer of the other side whose user name is its name
  (a KiCad ``User.<n>`` named after an Altium ``Mech.<k>``);
- ``used_layers``: the layers an item of a board is on, so a non-copper layer that one side declares and
  nothing uses is not a difference;
- ``mounting_holes``: a board-only footprint with no reference and one NPTH pad is a board hole when the
  other side holds that hole;
- ``keepout_rings``: the areas a drawing of a keep-out layer keeps out (its outline, or the band of its
  stroke), as rule areas hold them;
- ``edge_rings``: the closed rings that the ``Edge.Cuts`` drawings of a board form.

Pure: integers only, no backend.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence

from fenolite.checks.equivalence import norm
from fenolite.checks.equivalence.model import Tolerances
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.geometry import GeometryError, Transform
from fenolite.geometry.bands import arc_band, segment_band
from fenolite.model.board import Board, FootprintInstance, Graphic, Hole, Layer
from fenolite.model.design import Design

USER_NAME = "user_name"
"""The key of an ext bag that holds the name a layer is shown by (the KiCad reader keeps it)."""
EDGE_LAYER = "Edge.Cuts"
BOARD_ONLY = "board_only"
NPTH = "np_thru_hole"
TURN = 360_000_000


# --- layers ----------------------------------------------------------------------------------------


def user_names(layer: Layer) -> tuple[str, ...]:
    """The user names an ext bag of ``layer`` gives it, in bag order."""
    return tuple(
        str(value) for bag in layer.ext.values() for key, value in bag.payload if key == USER_NAME and value
    )


def layer_aliases(board_a: Board, board_b: Board) -> dict[str, str]:
    """Side ``b``'s name of each layer that pairs by user name with a layer of side ``a``, mapped to side
    ``a``'s name. A layer pairs only when its own name is missing on the other side and the user name names
    exactly one such layer there; each layer pairs once."""
    names_a = {layer.name for layer in board_a.layers}
    names_b = {layer.name for layer in board_b.layers}
    only_a = {layer.name: layer for layer in board_a.layers if layer.name not in names_b}
    only_b = {layer.name: layer for layer in board_b.layers if layer.name not in names_a}
    found: dict[str, str] = {}
    taken_a: set[str] = set()
    for name_b, layer_b in sorted(only_b.items()):
        hits = [alias for alias in user_names(layer_b) if alias in only_a and alias not in taken_a]
        if len(set(hits)) == 1:
            found[name_b] = hits[0]
            taken_a.add(hits[0])
    for name_a, layer_a in sorted(only_a.items()):
        if name_a in taken_a:
            continue
        hits = [alias for alias in user_names(layer_a) if alias in only_b and alias not in found]
        if len(set(hits)) == 1:
            found[hits[0]] = name_a
            taken_a.add(name_a)
    return found


def used_layers(board: Board, *, pad_masks: bool = True) -> set[str]:
    """The layers that an item of ``board`` is on: graphics, texts, zones, rule areas, tracks, arcs, vias,
    and the pads, fields, graphics, texts and rule areas of its footprints. Without ``pad_masks`` a pad
    counts only on its copper layers: one backend lists a pad's mask and paste layers, another derives
    them."""
    used: set[str] = set()
    used.update(graphic.layer for graphic in board.graphics)
    used.update(text.layer for text in board.texts)
    used.update(dimension.layer for dimension in board.dimensions)
    for zone in board.zones:
        used.update(zone.layers)
    for keepout in board.keepouts:
        used.update(keepout.layers)
    used.update(track.layer for track in board.tracks)
    used.update(arc.layer for arc in board.arcs)
    for via in board.vias:
        used.update(via.layers)
    for footprint in board.footprints:
        for pad in footprint.pads:
            used.update(layer for layer in pad.layers if pad_masks or layer.endswith(".Cu"))
        used.update(field.layer for field in footprint.fields)
        used.update(graphic.layer for graphic in footprint.graphics)
        used.update(text.layer for text in footprint.texts)
        for keepout in footprint.keepouts:
            used.update(keepout.layers)
    return used


# --- mounting holes --------------------------------------------------------------------------------


def _hole_footprint(design: Design, footprint: FootprintInstance) -> bool:
    refs = {component.id: component.ref for component in design.circuit.components}
    return (
        BOARD_ONLY in footprint.attributes
        and not refs.get(footprint.component_id, "")
        and len(footprint.pads) == 1
        and footprint.pads[0].kind == NPTH
        and footprint.pads[0].drill is not None
    )


def _hole_of(footprint: FootprintInstance) -> Hole:
    pad = footprint.pads[0]
    centre = Transform.placement(footprint.position, footprint.rotation).apply(pad.position)
    form = norm.slot_form(pad)
    drill = norm.drill_width(pad)
    assert drill is not None
    if form is None:
        return Hole(id=derived_id("hol", "c0421", footprint.id), position=centre, drill=drill)
    width, length, axis = form
    return Hole(
        id=derived_id("hol", "c0421", footprint.id),
        position=centre,
        drill=width,
        length=length,
        rotation=(axis + footprint.rotation) % norm.HALF_TURN,
    )


def _holes_equal(one: Hole, other: Hole, tolerances: Tolerances) -> bool:
    return (
        not one.plated
        and not other.plated
        and norm.points_equal(one.position, other.position, tolerances)
        and norm.lengths_equal(one.drill, other.drill, tolerances)
        and (one.length is None) == (other.length is None)
        and (one.length is None or norm.lengths_equal(one.length, other.length or 0, tolerances))
        and (
            one.length is None or norm.angles_equal(one.rotation, other.rotation, tolerances, norm.HALF_TURN)
        )
    )


def _as_holes(design: Design, other: Design, tolerances: Tolerances) -> Design:
    """``design`` with each hole footprint that a free hole of ``other`` matches turned into that hole."""
    board, held = design.board, other.board
    if board is None or held is None:
        return design
    waiting = [hole for hole in held.holes if not hole.plated]
    taken = [False] * len(waiting)
    gone: set[str] = set()
    holes: list[Hole] = []
    for footprint in board.footprints:
        if not _hole_footprint(design, footprint):
            continue
        hole = _hole_of(footprint)
        index = next(
            (k for k, h in enumerate(waiting) if not taken[k] and _holes_equal(hole, h, tolerances)), None
        )
        if index is None:
            continue
        taken[index] = True
        gone.add(footprint.id)
        holes.append(hole)
    if not gone:
        return design
    components = {fp.component_id for fp in board.footprints if fp.id in gone}
    kept = tuple(fp for fp in board.footprints if fp.id not in gone)
    still = {fp.component_id for fp in kept}
    circuit = dataclasses.replace(
        design.circuit,
        components=tuple(c for c in design.circuit.components if c.id not in components or c.id in still),
    )
    new_board = dataclasses.replace(board, footprints=kept, holes=(*board.holes, *holes))
    return dataclasses.replace(design, circuit=circuit, board=new_board)


def mounting_holes(a: Design, b: Design, tolerances: Tolerances) -> tuple[Design, Design]:
    """``a`` and ``b`` with each board-only footprint that holds no reference and exactly one NPTH pad taken
    as a board hole, when the other side holds a free unplated hole at the pad's board position with its
    drill (and slot length and axis). An unpaired footprint stays a footprint."""
    return _as_holes(a, b, tolerances), _as_holes(b, a, tolerances)


# --- keep-out drawings -----------------------------------------------------------------------------


def keepout_rings(graphic: Graphic) -> list[tuple[Point, ...]] | None:
    """The rings a drawing of a keep-out layer keeps out: a filled polygon or rectangle, or one of width 0,
    its outline; a line, an arc, a circle and each side of a stroked outline the band of its width, one ring
    per stroke (``geometry.bands``, change c0407). ``None`` for a drawing that covers no area or of another
    kind."""
    points = tuple(graphic.points)
    try:
        if graphic.kind == "rect" and len(points) == 2:
            a, b = points
            points = (a, Point(b.x, a.y), b, Point(a.x, b.y))
        if graphic.kind in ("polygon", "rect"):
            ring = points[:-1] if len(points) > 1 and points[0] == points[-1] else points
            if len(ring) < 3:
                return None
            if graphic.filled or graphic.width <= 0:
                return [ring]
            return [segment_band(p, ring[(i + 1) % len(ring)], graphic.width) for i, p in enumerate(ring)]
        if graphic.kind == "line" and len(points) == 2:
            return [segment_band(points[0], points[1], graphic.width)]
        if graphic.kind == "arc" and len(points) == 3:
            return [arc_band(points[0], points[1], points[2], graphic.width)]
        if graphic.kind == "circle" and len(points) == 2:
            centre, edge = points
            dx, dy = edge.x - centre.x, edge.y - centre.y
            far = Point(centre.x - dx, centre.y - dy)
            return [
                arc_band(edge, Point(centre.x - dy, centre.y + dx), far, graphic.width),
                arc_band(far, Point(centre.x + dy, centre.y - dx), edge, graphic.width),
            ]
    except (GeometryError, ValueError, ZeroDivisionError):
        return None
    return None


def split_keepout_drawings(
    graphics: Sequence[Graphic], layers: Collection[str]
) -> tuple[list[Graphic], list[tuple[Graphic, tuple[Point, ...]]]]:
    """The graphics that stay graphics, and each ring of a drawing on one of ``layers`` with its drawing; a
    drawing on such a layer that covers no area stays a graphic."""
    kept: list[Graphic] = []
    rings: list[tuple[Graphic, tuple[Point, ...]]] = []
    for graphic in graphics:
        found = keepout_rings(graphic) if graphic.layer in layers else None
        if found is None:
            kept.append(graphic)
        else:
            rings += [(graphic, ring) for ring in found]
    return kept, rings


# --- Edge.Cuts rings -------------------------------------------------------------------------------

Edge = tuple[Point, Point | None, Point]
"""An edge of a chain: its start, its arc mid (``None`` for a line) and its end."""


def _edges(graphic: Graphic) -> list[Edge] | None:
    pts = graphic.points
    if graphic.kind == "line" and len(pts) == 2 and pts[0] != pts[1]:
        return [(pts[0], None, pts[1])]
    if graphic.kind == "arc" and len(pts) == 3 and pts[0] != pts[2]:
        return [(pts[0], pts[1], pts[2])]
    return None


def edge_rings(
    graphics: Sequence[Graphic],
) -> tuple[list[tuple[tuple[Point, ...], dict[int, Point]]], list[Graphic]]:
    """The closed rings that the ``Edge.Cuts`` lines and arcs of ``graphics`` form end to end (exact points,
    each point joining exactly two edges), as vertices with the arc mid of each edge, plus each
    ``Edge.Cuts`` polygon or rectangle; and every other graphic. A line or arc of an open chain, or at a
    point that more than two edges share, stays a graphic."""
    rest: list[Graphic] = []
    strokes: list[tuple[Graphic, Edge]] = []
    rings: list[tuple[tuple[Point, ...], dict[int, Point]]] = []
    for graphic in graphics:
        if graphic.layer != EDGE_LAYER:
            rest.append(graphic)
            continue
        if graphic.kind in ("polygon", "rect") and not graphic.filled:
            pts = graphic.points
            if graphic.kind == "rect" and len(pts) == 2:
                a, b = pts
                pts = (a, Point(b.x, a.y), b, Point(a.x, b.y))
            ring = pts[:-1] if len(pts) > 1 and pts[0] == pts[-1] else pts
            if len(ring) >= 3:
                rings.append((tuple(ring), {}))
                continue
        edges = _edges(graphic)
        if edges is None:
            rest.append(graphic)
        else:
            strokes += [(graphic, edge) for edge in edges]
    at: dict[Point, list[int]] = defaultdict(list)
    for index, (_, (start, _, end)) in enumerate(strokes):
        at[start].append(index)
        at[end].append(index)
    used = [False] * len(strokes)
    for first in range(len(strokes)):
        if used[first]:
            continue
        chain = _chain(first, strokes, at, used)
        if chain is None:
            continue
        points: list[Point] = []
        mids: dict[int, Point] = {}
        for k, (start, mid, _) in enumerate(chain):
            points.append(start)
            if mid is not None:
                mids[k] = mid
        rings.append((tuple(points), mids))
    rest += [graphic for k, (graphic, _) in enumerate(strokes) if not used[k]]
    return rings, rest


def _chain(
    first: int, strokes: Sequence[tuple[Graphic, Edge]], at: Mapping[Point, list[int]], used: list[bool]
) -> list[Edge] | None:
    """The closed chain through stroke ``first``, oriented edge by edge, marking its strokes used; ``None``
    (nothing marked) when the chain is open or meets a point of more than two edges."""
    start, mid, end = strokes[first][1]
    chain: list[Edge] = [(start, mid, end)]
    seen = {first}
    here = end
    while here != start:
        joined = at.get(here, [])
        if len(joined) != 2:
            return None
        nxt = next((k for k in joined if k not in seen), None)
        if nxt is None:
            return None
        a, m, b = strokes[nxt][1]
        if a == here:
            chain.append((a, m, b))
            here = b
        else:
            chain.append((b, m, a))
            here = a
        seen.add(nxt)
    if len(at.get(start, [])) != 2:
        return None
    for k in seen:
        used[k] = True
    return chain


__all__ = [
    "edge_rings",
    "keepout_rings",
    "layer_aliases",
    "mounting_holes",
    "split_keepout_drawings",
    "used_layers",
    "user_names",
]

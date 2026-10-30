# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper of the zones for the practice checks: which copper each zone layer stands for, and the simulated
pour of a zone whose fill is missing or stale (change c0204; capability board-analyses, "Copper states of
the practice checks"; user guide ``docs/analyses.md``, "Practice checks").

Each zone layer of a zone with a net has one of three states:

- ``saved_fill``: the fill polygons stored in the file, used as they are;
- ``simulated``: the file holds no fill on that layer, or the stored fill is stale: it puts copper where the
  outlines in force forbid it (outside its zone outline, outside the board or in a cut-out, inside a keep-out
  that forbids pours on the layer) or on copper of another net. The pour is then simulated;
- ``outline``: the pour should be simulated but its raster would exceed ``MAX_CELLS``; the zone outline itself
  is taken as the copper, an upper bound, and the row says so.

The simulated pour is a raster of square cells of side ``grid`` aligned on the board origin; a cell is copper
when its centre is. Zones are poured in priority order (highest first, then file order). A cell of a zone is
copper when its centre lies inside the zone outline, inside the board and outside its cut-outs, at least the
clearance away from the board edge, outside every keep-out that forbids pours on the layer, at least the
clearance plus half the width away from copper of another net, and at least the clearance plus one cell away
from a cell of an earlier zone of another net. The clearance is the largest of the zone's own clearance and
of the class clearances of the two nets. The cells of the zones of one net on one layer are then joined by
their sides into islands; an island that holds no cell covered by a pad, a track, an arc or a via of the net
is dropped, as dead copper. Thermal spokes, the minimum width and holes without copper are not simulated: a
simulated pour joins its pads solidly.

The raster says where the copper is to within one cell. Everything is integer arithmetic.
"""

from __future__ import annotations

import fnmatch
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction

from fenolite.analysis.boundary import BoardBoundary
from fenolite.analysis.copper import (
    ARC_TOL_NM,
    CopperShape,
    NetCopper,
    copper_layers,
    loose_copper,
    net_copper,
)
from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.geometry import GeometryError, Thick
from fenolite.model.board import Zone
from fenolite.model.design import Design

DEFAULT_GRID_NM = 100_000
"""The side of a raster cell when the caller gives none: 0.1 mm."""
MAX_CELLS = 4_000_000
"""The largest raster of one zone layer; a larger one takes the zone outline as its copper."""
STATES = ("saved_fill", "simulated", "outline")
NON_FILL = ("pad", "track", "arc", "via")

Cell = tuple[int, int]
_Seg = tuple[Point, Point]


@dataclass(frozen=True, slots=True)
class ZoneLayer:
    """The copper of one zone on one layer: ``state`` (one of ``STATES``), ``reason`` (``""`` for a saved
    fill, ``no-fill``, ``stale: …`` or ``too-large``), the cells of the simulated pour that were kept and the
    number of islands that were dropped."""

    zone_id: str
    where: str
    net: str
    layer: str
    priority: int
    state: str
    reason: str = ""
    cells: int = 0
    dropped: int = 0


@dataclass(frozen=True, slots=True)
class Island:
    """A kept island of a simulated pour: its net, its layer, its cells, the zones it comes from, and the
    copper items of the net that cover one of its cells, as ``(kind, entity_id, where)``."""

    net: str
    layer: str
    cells: frozenset[Cell]
    zones: tuple[str, ...]
    joins: frozenset[tuple[str, str, str]]


@dataclass(frozen=True, slots=True)
class PourCopper:
    """The copper of the board for the practice checks: ``copper`` holds the shapes per net, the fills of
    every zone layer that is not ``saved_fill`` removed and the outline of every ``outline`` zone layer
    added; ``islands`` the kept islands of the simulated pours; ``zones`` the state of each zone layer."""

    grid: int
    copper: NetCopper
    zones: tuple[ZoneLayer, ...] = ()
    islands: tuple[Island, ...] = ()
    loose: tuple[CopperShape, ...] = field(default=())

    def state_of(self, zone_id: str, layer: str) -> str | None:
        return next((z.state for z in self.zones if z.zone_id == zone_id and z.layer == layer), None)

    def states_of(self, net: str) -> tuple[str, ...]:
        """The states of the zone layers of ``net``, sorted and without repeats."""
        return tuple(sorted({z.state for z in self.zones if z.net == net}))


# --- raster primitives ----------------------------------------------------------------------------------


def centre(index: int, grid: int) -> int:
    return index * grid + grid // 2


def _first(value: Fraction | int, grid: int) -> int:
    """The first cell index whose centre is at or after ``value``."""
    return math.ceil(Fraction(value - grid // 2, grid))


def _last(value: Fraction | int, grid: int) -> int:
    """The last cell index whose centre is at or before ``value``."""
    return math.floor(Fraction(value - grid // 2, grid))


def row_spans(ring: Sequence[Point], y: int) -> list[tuple[Fraction, Fraction]]:
    """The intervals of the horizontal line at ``y`` inside ``ring`` under the non-zero rule."""
    crossings: list[tuple[Fraction, int]] = []
    count = len(ring)
    for k in range(count):
        a, b = ring[k], ring[(k + 1) % count]
        if a.y <= y < b.y:
            direction = 1
        elif b.y <= y < a.y:
            direction = -1
        else:
            continue
        crossings.append((a.x + Fraction((y - a.y) * (b.x - a.x), b.y - a.y), direction))
    crossings.sort()
    spans: list[tuple[Fraction, Fraction]] = []
    winding = 0
    start = Fraction(0)
    for x, direction in crossings:
        before = winding
        winding += direction
        if before == 0 and winding != 0:
            start = x
        elif before != 0 and winding == 0:
            spans.append((start, x))
    return spans


def ring_cells(ring: Sequence[Point], grid: int) -> set[Cell]:
    """The cells whose centre lies inside ``ring`` (non-zero rule)."""
    if len(ring) < 3:
        return set()
    ys = [p.y for p in ring]
    found: set[Cell] = set()
    for j in range(_first(min(ys), grid), _last(max(ys), grid) + 1):
        for lo, hi in row_spans(ring, centre(j, grid)):
            found.update((i, j) for i in range(_first(lo, grid), _last(hi, grid) + 1))
    return found


def _near(px: int, py: int, a: Point, b: Point, d2: int, strict: bool) -> bool:
    """Whether ``(px, py)`` lies within ``D/2`` of the segment ``a–b``, ``d2`` being ``D²``: closer than it
    with ``strict``, else at most."""
    dx, dy = b.x - a.x, b.y - a.y
    ex, ey = px - a.x, py - a.y
    l2 = dx * dx + dy * dy
    t = ex * dx + ey * dy
    if l2 == 0 or t <= 0:
        value, limit = 4 * (ex * ex + ey * ey), d2
    elif t >= l2:
        fx, fy = px - b.x, py - b.y
        value, limit = 4 * (fx * fx + fy * fy), d2
    else:
        cross = dx * ey - dy * ex
        value, limit = 4 * cross * cross, d2 * l2
    return value < limit if strict else value <= limit


def band_cells(segments: Iterable[_Seg], diameter: int, grid: int, *, strict: bool) -> set[Cell]:
    """The cells whose centre lies within ``diameter / 2`` of a segment (closer than it with ``strict``)."""
    found: set[Cell] = set()
    d2 = diameter * diameter
    half = (diameter + 1) // 2
    for a, b in segments:
        i0, i1 = _first(min(a.x, b.x) - half, grid), _last(max(a.x, b.x) + half, grid)
        j0, j1 = _first(min(a.y, b.y) - half, grid), _last(max(a.y, b.y) + half, grid)
        for j in range(j0, j1 + 1):
            y = centre(j, grid)
            for i in range(i0, i1 + 1):
                if (i, j) not in found and _near(centre(i, grid), y, a, b, d2, strict):
                    found.add((i, j))
    return found


def segments_of(core: Sequence[Point], closed: bool) -> list[_Seg]:
    if len(core) == 1:
        return [(core[0], core[0])]
    pairs = list(zip(core, core[1:], strict=False))
    if closed:
        pairs.append((core[-1], core[0]))
    return pairs


def shape_cells(shape: Thick, grid: int, *, grow: int = 0, strict: bool = False) -> set[Cell]:
    """The cells whose centre lies in ``shape`` grown by ``grow`` (closer than that with ``strict``)."""
    diameter = shape.width + 2 * grow
    found: set[Cell] = ring_cells(shape.core, grid) if shape.filled else set()
    if diameter > 0 or not shape.filled:
        found |= band_cells(segments_of(shape.core, shape.filled), diameter, grid, strict=strict)
    return found


def window_cells(shape: Thick, grid: int, window: tuple[int, int, int, int]) -> set[Cell]:
    """The cells of ``shape_cells(shape, grid)`` whose centre lies in the box ``window`` (``x0, y0, x1, y1``),
    found without rasterising the rest of the shape (change c0213)."""
    x0, y0, x1, y1 = window
    i0, i1, j0, j1 = _first(x0, grid), _last(x1, grid), _first(y0, grid), _last(y1, grid)
    found: set[Cell] = set()
    if shape.filled and len(shape.core) >= 3:
        for j in range(j0, j1 + 1):
            for lo, hi in row_spans(shape.core, centre(j, grid)):
                found.update((i, j) for i in range(max(i0, _first(lo, grid)), min(i1, _last(hi, grid)) + 1))
    if shape.width > 0 or not shape.filled:
        d2 = shape.width * shape.width
        half = (shape.width + 1) // 2
        for a, b in segments_of(shape.core, shape.filled):
            low_j, high_j = _first(min(a.y, b.y) - half, grid), _last(max(a.y, b.y) + half, grid)
            low_i, high_i = _first(min(a.x, b.x) - half, grid), _last(max(a.x, b.x) + half, grid)
            for j in range(max(j0, low_j), min(j1, high_j) + 1):
                y = centre(j, grid)
                for i in range(max(i0, low_i), min(i1, high_i) + 1):
                    if (i, j) not in found and _near(centre(i, grid), y, a, b, d2, False):
                        found.add((i, j))
    return found


def covers(shape: Thick, point: Point) -> bool:
    """Whether ``point`` lies in the closed region of ``shape``."""
    if shape.filled:
        spans = row_spans(shape.core, point.y)
        if any(lo <= point.x <= hi for lo, hi in spans):
            return True
    d2 = shape.width * shape.width
    return any(_near(point.x, point.y, a, b, d2, False) for a, b in segments_of(shape.core, shape.filled))


def islands_of(cells: set[Cell]) -> list[set[Cell]]:
    """The sets of cells joined by their sides, in the order of their smallest cell."""
    left = set(cells)
    found: list[set[Cell]] = []
    for start in sorted(cells):
        if start not in left:
            continue
        left.discard(start)
        island = {start}
        stack = [start]
        while stack:
            i, j = stack.pop()
            for near in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if near in left:
                    left.discard(near)
                    island.add(near)
                    stack.append(near)
        found.append(island)
    return found


# --- zone states ----------------------------------------------------------------------------------------


def layer_matches(names: Sequence[str], layer: str) -> bool:
    """Whether a layer list of a zone or a keep-out names ``layer`` (``*.Cu`` and ``F&B.Cu`` included)."""
    for name in names:
        pattern = name.replace("F&B", "[FB]").replace("&", "*")
        if name == layer or fnmatch.fnmatchcase(layer, pattern):
            return True
    return False


def _where(zone: Zone) -> str:
    provenance = zone.provenance
    return provenance.locator if provenance is not None and provenance.locator else zone.id


def _clearances(design: Design) -> dict[str, int]:
    classes = {cls.id: cls for cls in design.circuit.netclasses}
    found: dict[str, int] = {}
    for net in design.circuit.nets:
        cls = classes.get(net.netclass_id or "")
        if cls is not None and cls.clearance is not None:
            found[net.name] = cls.clearance
    return found


def _cell_count(ring: Sequence[Point], grid: int) -> int:
    xs, ys = [p.x for p in ring], [p.y for p in ring]
    return max(0, (max(xs) - min(xs)) // grid + 1) * max(0, (max(ys) - min(ys)) // grid + 1)


def _forbidden(
    design: Design, boundary: BoardBoundary | None, layer: str, grid: int
) -> tuple[set[Cell] | None, set[Cell], list[tuple[str, set[Cell]]]]:
    """The cells inside the board (``None`` without an outline), inside a cut-out, and inside each keep-out
    that forbids pours on ``layer``."""
    board = design.board
    assert board is not None
    inside = ring_cells(boundary.outer, grid) if boundary is not None and boundary.outer else None
    cut: set[Cell] = set()
    for ring in boundary.cutouts if boundary is not None else ():
        cut |= ring_cells(ring, grid)
    keepouts: list[tuple[str, set[Cell]]] = []
    for keepout in board.keepouts:
        if keepout.no_copper_pour and len(keepout.outline) >= 3 and layer_matches(keepout.layers, layer):
            keepouts.append((keepout.name or keepout.id, ring_cells(keepout.outline, grid)))
    return inside, cut, keepouts


def _stale(
    zone: Zone,
    layer: str,
    grid: int,
    forbidden: tuple[set[Cell] | None, set[Cell], list[tuple[str, set[Cell]]]],
    others: Sequence[CopperShape],
) -> str:
    """Why the stored fill of a zone layer is stale, or ``""``."""
    cells: set[Cell] = set()
    for fill in zone.fills:
        if fill.layer == layer and len(fill.polygon) >= 3:
            if _cell_count(fill.polygon, grid) > MAX_CELLS:
                return ""
            cells |= ring_cells(fill.polygon, grid)
    if not cells:
        return ""
    if cells - ring_cells(zone.outline, grid):
        return "stale: fill outside its zone outline"
    inside, cut, keepouts = forbidden
    if inside is not None and cells - inside:
        return "stale: fill outside the board"
    if cells & cut:
        return "stale: fill in a board cut-out"
    for name, held in keepouts:
        if cells & held:
            return f"stale: fill inside the keep-out {name}"
    for shape in others:
        if shape.layer == layer and shape.kind in NON_FILL and cells & shape_cells(shape.shape, grid):
            return f"stale: fill over copper of another net ({shape.where})"
    return ""


def _offsets(reach: int, grid: int) -> list[Cell]:
    """The cell offsets whose centres lie closer than ``reach`` to the centre of a cell."""
    steps = reach // grid + 1
    return [
        (di, dj)
        for di in range(-steps, steps + 1)
        for dj in range(-steps, steps + 1)
        if (di * grid) ** 2 + (dj * grid) ** 2 < reach * reach
    ]


def _edge(cells: set[Cell]) -> list[Cell]:
    return [
        (i, j)
        for i, j in cells
        if (i + 1, j) not in cells
        or (i - 1, j) not in cells
        or (i, j + 1) not in cells
        or (i, j - 1) not in cells
    ]


def pour_copper(
    design: Design,
    *,
    pads: Sequence[BoardPad] | None,
    boundary: BoardBoundary | None,
    grid: int = DEFAULT_GRID_NM,
    arc_tol: int = ARC_TOL_NM,
) -> PourCopper:
    """The copper of ``design.board`` with every zone layer in its state, and the simulated pours."""
    if grid <= 0:
        raise ValueError(f"the grid of the simulated pour must be above 0, got {grid}")
    board = design.board
    copper = net_copper(design, pads=pads, arc_tol=arc_tol)
    loose = loose_copper(design, pads=pads, arc_tol=arc_tol)
    if board is None:
        return PourCopper(grid, copper, loose=loose)
    names = {net.id: net.name for net in design.circuit.nets}
    classes = _clearances(design)
    layers = copper_layers(board)
    order = sorted(
        (
            (zone, index)
            for index, zone in enumerate(board.zones)
            if zone.net_id is not None and len(zone.outline) >= 3
        ),
        key=lambda pair: (-pair[0].priority, pair[1]),
    )
    forbidden_by_layer: dict[str, tuple[set[Cell] | None, set[Cell], list[tuple[str, set[Cell]]]]] = {}

    def forbidden(layer: str) -> tuple[set[Cell] | None, set[Cell], list[tuple[str, set[Cell]]]]:
        if layer not in forbidden_by_layer:
            forbidden_by_layer[layer] = _forbidden(design, boundary, layer, grid)
        return forbidden_by_layer[layer]

    states: list[ZoneLayer] = []
    poured: list[tuple[str, str, str, int, set[Cell]]] = []  # zone id, net, layer, rank, cells
    for rank, (zone, _) in enumerate(order):
        net = names.get(zone.net_id or "", zone.net_id or "")
        others = [(name, s) for name, held in copper.by_net.items() if name != net for s in held]
        others += [("", s) for s in loose]
        for layer in layers:
            if not layer_matches(zone.layers, layer):
                continue
            where = _where(zone)
            has_fill = any(fill.layer == layer for fill in zone.fills)
            reason = (
                "no-fill"
                if not has_fill
                else _stale(zone, layer, grid, forbidden(layer), [s for _, s in others])
            )
            if not reason:
                states.append(ZoneLayer(zone.id, where, net, layer, zone.priority, "saved_fill"))
                continue
            if _cell_count(zone.outline, grid) > MAX_CELLS:
                states.append(ZoneLayer(zone.id, where, net, layer, zone.priority, "outline", "too-large"))
                continue
            clearance = max(zone.settings.clearance, classes.get(net, 0))
            cells = ring_cells(zone.outline, grid)
            inside, cut, keepouts = forbidden(layer)
            if inside is not None:
                cells &= inside
                if boundary is not None:
                    edges = segments_of(boundary.outer, True)
                    for ring in boundary.cutouts:
                        edges += segments_of(ring, True)
                    cells -= band_cells(edges, 2 * clearance, grid, strict=True)
            cells -= cut
            for _, held in keepouts:
                cells -= held
            for other, shape in others:
                if shape.layer != layer or not cells:
                    continue
                if shape.kind == "fill" and not _earlier_fill(shape, rank, order, states, layer):
                    continue
                reach = max(clearance, classes.get(other, 0))
                cells -= shape_cells(shape.shape, grid, grow=reach, strict=True)
            for _, other_net, other_layer, _, held in poured:
                if other_layer != layer or other_net == net or not cells:
                    continue
                offsets = _offsets(max(clearance, classes.get(other_net, 0)) + grid, grid)
                cells -= {(i + di, j + dj) for i, j in _edge(held) for di, dj in offsets} | held
            poured.append((zone.id, net, layer, rank, cells))
            states.append(ZoneLayer(zone.id, where, net, layer, zone.priority, "simulated", reason))
    by_net = _replace_fills(copper, board.zones, states, names)
    islands, kept, dropped = _islands(poured, by_net, grid)
    final = tuple(
        ZoneLayer(
            z.zone_id,
            z.where,
            z.net,
            z.layer,
            z.priority,
            z.state,
            z.reason,
            kept.get((z.zone_id, z.layer), 0),
            dropped.get((z.zone_id, z.layer), 0),
        )
        for z in states
    )
    wheres = {z.zone_id: z.where for z in final}
    named = tuple(
        Island(i.net, i.layer, i.cells, tuple(sorted({wheres.get(z, z) for z in i.zones})), i.joins)
        for i in islands
    )
    shaped = NetCopper(by_net, copper.unsupported, copper.outer, copper.layers)
    return PourCopper(grid, shaped, final, named, loose)


def rejoin(
    pour: PourCopper, design: Design, *, pads: Sequence[BoardPad] | None, arc_tol: int = ARC_TOL_NM
) -> PourCopper:
    """The copper of ``design`` on the simulated cells of ``pour`` (change c0280): the items of ``design``
    shaped again, the zone layers in their states of ``pour``, and each kept island joined to the items of its
    net that cover one of its cells. ``design`` is the board of ``pour`` with items added; the result equals
    ``pour_copper`` of ``design`` when no added item comes within the clearance of a zone of another net and
    none lands only on an island that ``pour`` dropped, which the caller tests."""
    board = design.board
    copper = net_copper(design, pads=pads, arc_tol=arc_tol)
    loose = loose_copper(design, pads=pads, arc_tol=arc_tol)
    if board is None:
        return PourCopper(pour.grid, copper, loose=loose)
    names = {net.id: net.name for net in design.circuit.nets}
    by_net = _replace_fills(copper, board.zones, pour.zones, names)
    islands: list[Island] = []
    for island in pour.islands:
        joins: set[tuple[str, str, str]] = set()
        for shape in by_net.get(island.net, ()):
            if shape.layer == island.layer and shape.kind in NON_FILL:
                if not island.cells.isdisjoint(shape_cells(shape.shape, pour.grid)):
                    joins.add((shape.kind, shape.entity_id, shape.where))
        islands.append(Island(island.net, island.layer, island.cells, island.zones, frozenset(joins)))
    shaped = NetCopper(by_net, copper.unsupported, copper.outer, copper.layers)
    return PourCopper(pour.grid, shaped, pour.zones, tuple(islands), loose)


def _earlier_fill(
    shape: CopperShape, rank: int, order: Sequence[tuple[Zone, int]], states: Sequence[ZoneLayer], layer: str
) -> bool:
    """Whether a fill of another net counts against the zone of ``rank``: its zone is poured earlier and its
    stored fill stands on the layer."""
    for other_rank, (zone, _) in enumerate(order):
        if zone.id == shape.entity_id:
            standing = any(
                z.zone_id == zone.id and z.layer == layer and z.state == "saved_fill" for z in states
            )
            return other_rank < rank and standing
    return False


def _replace_fills(
    copper: NetCopper, zones: Sequence[Zone], states: Sequence[ZoneLayer], names: Mapping[str, str]
) -> dict[str, tuple[CopperShape, ...]]:
    """The shapes per net: the fills of a zone layer that is not ``saved_fill`` removed, the outline of an
    ``outline`` zone layer added."""
    standing = {(z.zone_id, z.layer) for z in states if z.state == "saved_fill"}
    stated = {(z.zone_id, z.layer) for z in states}
    by_net: dict[str, list[CopperShape]] = {}
    for net, shapes in copper.by_net.items():
        by_net[net] = [
            s
            for s in shapes
            if s.kind != "fill" or (s.entity_id, s.layer) in standing or (s.entity_id, s.layer) not in stated
        ]
    by_id = {zone.id: zone for zone in zones}
    for state in states:
        if state.state != "outline":
            continue
        zone = by_id[state.zone_id]
        try:
            shape = Thick(tuple(zone.outline), 0, filled=True)
        except (GeometryError, ValueError):
            continue
        net = names.get(zone.net_id or "", zone.net_id or "")
        by_net.setdefault(net, []).append(CopperShape(shape, state.layer, "fill", state.where, zone.id))
    return {net: tuple(shapes) for net, shapes in sorted(by_net.items())}


def _islands(
    poured: Sequence[tuple[str, str, str, int, set[Cell]]],
    by_net: Mapping[str, Sequence[CopperShape]],
    grid: int,
) -> tuple[list[Island], dict[tuple[str, str], int], dict[tuple[str, str], int]]:
    """The kept islands per net and layer, with the kept cells and the dropped islands per zone layer."""
    merged: dict[tuple[str, str], dict[Cell, str]] = defaultdict(dict)
    for zone_id, net, layer, _, cells in poured:
        owner = merged[net, layer]
        for cell in cells:
            owner.setdefault(cell, zone_id)
    islands: list[Island] = []
    kept: dict[tuple[str, str], int] = defaultdict(int)
    dropped: dict[tuple[str, str], int] = defaultdict(int)
    for (net, layer), owner in sorted(merged.items()):
        index: dict[Cell, int] = {}
        found = islands_of(set(owner))
        for number, island in enumerate(found):
            for cell in island:
                index[cell] = number
        joins: dict[int, set[tuple[str, str, str]]] = defaultdict(set)
        for shape in by_net.get(net, ()):
            if shape.layer != layer or shape.kind not in NON_FILL:
                continue
            for cell in shape_cells(shape.shape, grid):
                number = index.get(cell)
                if number is not None:
                    joins[number].add((shape.kind, shape.entity_id, shape.where))
        for number, island in enumerate(found):
            zones = sorted({owner[cell] for cell in island})
            if joins.get(number):
                islands.append(Island(net, layer, frozenset(island), tuple(zones), frozenset(joins[number])))
                for cell in island:
                    kept[owner[cell], layer] += 1
            else:
                for zone_id in zones:
                    dropped[zone_id, layer] += 1
    return islands, dict(kept), dict(dropped)


__all__ = [
    "DEFAULT_GRID_NM",
    "MAX_CELLS",
    "NON_FILL",
    "STATES",
    "Cell",
    "Island",
    "PourCopper",
    "ZoneLayer",
    "band_cells",
    "centre",
    "covers",
    "islands_of",
    "layer_matches",
    "pour_copper",
    "rejoin",
    "ring_cells",
    "row_spans",
    "segments_of",
    "shape_cells",
    "window_cells",
]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Level 8 of a design comparison: what a person sees (capability fidelity-proof, "Rendered layer masks";
capability design-equivalence, "Level 8 compares rendered presentation"; change c0278).

Both sides are drawn by the viewer's own scene builders (``view.scene`` for a board, the schematic scene of
a sheet), so every primitive is drawn as the viewer draws it. ``render_masks`` rasterises each layer of a
board scene, or a whole schematic scene, onto a grid shared by both sides: the grid's origin and size are
the union of both sides' bounds, so a pixel of one side lies on the pixel of the other. A mask is a
run-length image: per row, the half-open column intervals that are inked. A pixel is inked when its centre
lies in a primitive: polygons are filled even-odd at the pixel centres with exact rational edge crossings,
strokes are capsules (segments with round ends), discs and rings are exact, arcs are flattened by the
geometry kernel with half a pixel of chord error, and a text is the box of its glyphs. Zones are drawn by
their outline only (``board_scene`` leaves the fills out): a fill depends on the filler and its version.

``compare_masks`` counts the pixels inked on one side with no inked pixel within one pixel of it on the
other (a one-pixel tolerance for rounding), and locates the largest connected region of such pixels.
``compare_scenes`` gives the findings of level 8 as plain values (``view`` imports no ``checks``; the command
turns them into the level's differences): ``render-missing`` for a layer one side alone
draws, ``render-pixels`` for a layer whose differing pixels exceed ``pixel_ppm`` of its inked pixels, and
the first changes ``view.compare.compare`` names between the two scenes, so the user sees which primitive
moved. Rendering is ``INFERRED``: one renderer draws both sides (``H-K-FID-PLOT-AGREE``).
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from math import isqrt
from typing import Any

from fenolite.backends.base import BoardFrame
from fenolite.core.coords import Point
from fenolite.geometry import Arc as GeoArc
from fenolite.geometry import GeometryError
from fenolite.geometry.transform import rotate_point
from fenolite.model.design import Design
from fenolite.view import compare as visual
from fenolite.view.scene import build_scene

DEFAULT_PIXEL_PPM = 1000
"""The share of differing pixels a layer may hold, in parts per million of its inked pixels: the 0.1 % of
the viewer's screenshot tests."""
BOARD_PITCH_NM = 50_000
SHEET_PITCH_NM = 127_000
"""The default pixel pitches of a board layer and of a schematic sheet."""
SHEET_LAYER = "sheet"
"""The one layer of a schematic scene."""
LEFT_OUT = frozenset({"View.Checks", "View.Keepouts"})
"""View layers that show findings or overlays, not the design."""
UM = 1000
"""Nanometres per micrometre: scenes hold micrometres."""
CHANGE_LIMIT = 3


@dataclass(frozen=True, slots=True)
class Finding:
    """One difference of level 8: its kind (``render-missing`` or ``render-pixels``), where it is, its field
    and the two values."""

    kind: str
    where: str
    field: str
    a: str
    b: str


@dataclass(frozen=True, slots=True)
class SceneComparison:
    """Level 8 over two sets of scenes: the findings in ``(where, kind)`` order, the count of layers and
    sheets compared, and the level's summary (with the first changes the visual diff names per scene)."""

    findings: tuple[Finding, ...]
    compared: int
    summary: Mapping[str, object]


Interval = tuple[Fraction, Fraction]
Run = tuple[int, int]


# --- shapes ----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Polygon:
    """Rings filled even-odd, in nanometres."""

    rings: tuple[tuple[Point, ...], ...]


@dataclass(frozen=True, slots=True)
class Capsule:
    """The points within ``radius`` of the segment ``a``-``b``: a stroke with round ends, or a disc."""

    a: Point
    b: Point
    radius: int


@dataclass(frozen=True, slots=True)
class Annulus:
    """The points between two radii of a centre: a stroked circle."""

    centre: Point
    inner: int
    outer: int


Shape = Polygon | Capsule | Annulus


def _p(x: object, y: object) -> Point:
    return Point(int(x) * UM, int(y) * UM)  # type: ignore[call-overload]


def _pairs(flat: Sequence[object]) -> list[Point]:
    return [_p(flat[k], flat[k + 1]) for k in range(0, len(flat) - 1, 2)]


def _polyline(points: Sequence[Point], width: int) -> list[Shape]:
    radius = max(width // 2, 1)
    if len(points) == 1:
        return [Capsule(points[0], points[0], radius)]
    return [Capsule(a, b, radius) for a, b in zip(points, points[1:], strict=False)]


def _arc_points(start: Point, mid: Point, end: Point, tol: int) -> list[Point]:
    try:
        return list(GeoArc(start, mid, end).polygonize(max(tol, 1)))
    except GeometryError:
        return [start, end]


def _quarter_text_box(
    x: int, y: int, height: int, width: int, rotation: object, h: str, v: str, chars: int
) -> Polygon:
    """The box of a text's glyphs: ``chars`` glyphs of ``width`` by ``height`` at ``(x, y)`` (nm), turned by
    ``rotation`` degrees (an exact decimal read as a fraction, not a float) about its anchor."""
    total = width * max(chars, 1)
    x0 = {"left": 0, "right": -total}.get(h, -total // 2)
    y0 = {"top": 0, "bottom": -height}.get(v, -height // 2)
    udeg = int(Fraction(str(rotation)) * 1_000_000) if rotation else 0
    corners = (Point(x0, y0), Point(x0 + total, y0), Point(x0 + total, y0 + height), Point(x0, y0 + height))
    turned = [rotate_point(Point(c.x, -c.y), udeg) for c in corners]  # counter-clockwise on a Y-down page
    return Polygon((tuple(Point(x + c.x, y - c.y) for c in turned),))


def board_shapes(scene: Mapping[str, Any], pitch_nm: int) -> dict[str, list[Shape]]:
    """The shapes of each layer of a board scene (``view.scene``), in nanometres."""
    out: dict[str, list[Shape]] = {}
    for prim in scene.get("prims", []):
        layer, kind, data = str(prim[0]), str(prim[1]), prim[2]
        if layer in LEFT_OUT:
            continue
        held = out.setdefault(layer, [])
        if kind == "s":
            held += _polyline(_pairs(data[:4]), int(data[4]) * UM)
        elif kind == "a":
            pts = _pairs(data[:6])
            held += _polyline(_arc_points(pts[0], pts[1], pts[2], pitch_nm // 2), int(data[6]) * UM)
        elif kind == "c":
            centre = _p(data[0], data[1])
            held.append(Capsule(centre, centre, int(data[2]) * UM))
        elif kind == "l":
            held += _polyline(_pairs(data[1:]), int(data[0]) * UM)
        elif kind == "p":
            held.append(Polygon(tuple(tuple(_pairs(ring)) for ring in data if len(ring) >= 6)))
        elif kind == "o":
            for ring in data:
                pts = _pairs(ring)
                held += _polyline([*pts, pts[0]] if pts else pts, pitch_nm)
    for text in scene.get("texts", []):
        layer = str(text[0])
        if layer in LEFT_OUT:
            continue
        x, y, height, width, rotation, h, v, value = (
            int(text[1]) * UM, int(text[2]) * UM, int(text[3]) * UM, int(text[4]) * UM, text[6], str(text[7]),
            str(text[8]), str(text[10]),
        )  # fmt: skip
        out.setdefault(layer, []).append(_quarter_text_box(x, y, height, width, rotation, h, v, len(value)))
    return {layer: shapes for layer, shapes in out.items() if shapes}


def sheet_shapes(scene: Mapping[str, Any], pitch_nm: int) -> dict[str, list[Shape]]:
    """The shapes of a schematic scene (``view.kicad_schematic``), all on ``SHEET_LAYER``, in nanometres."""
    shapes: list[Shape] = []
    for prim in scene.get("prims", []):
        kind = prim.get("k")
        width = int(prim.get("w") or 0) * UM or pitch_nm
        if kind == "l":
            shapes += _polyline(_pairs(prim["p"]), width)
        elif kind == "g":
            pts = _pairs(prim["p"])
            if prim.get("f") and len(pts) >= 3:
                shapes.append(Polygon((tuple(pts),)))
            shapes += _polyline([*pts, pts[0]] if pts else pts, width)
        elif kind == "e":
            centre, radius = _p(prim["x"], prim["y"]), int(prim["rx"]) * UM
            if prim.get("f"):
                shapes.append(Capsule(centre, centre, radius + width // 2))
            else:
                shapes.append(Annulus(centre, max(radius - width // 2, 0), radius + width // 2))
        elif kind == "t":
            size = int(prim.get("sz") or 0) * UM
            glyph = int(prim.get("gw") or 0) * UM
            rotation = 90 * int(prim.get("rot") or 0)
            value = str(prim.get("s", ""))
            longest = max((len(line) for line in value.split("\n")), default=0)
            shapes.append(
                _quarter_text_box(
                    int(prim["x"]) * UM,
                    int(prim["y"]) * UM,
                    size,
                    glyph,
                    rotation,
                    str(prim.get("h", "center")),
                    str(prim.get("v", "center")),
                    longest,
                )
            )
    return {SHEET_LAYER: shapes} if shapes else {}


def shapes_of(scene: Mapping[str, Any], pitch_nm: int) -> dict[str, list[Shape]]:
    """The shapes of a board scene by layer, or of a schematic scene on ``SHEET_LAYER``."""
    return (
        sheet_shapes(scene, pitch_nm) if scene.get("kind") == "schematic" else board_shapes(scene, pitch_nm)
    )


def _box(shape: Shape) -> tuple[int, int, int, int]:
    if isinstance(shape, Polygon):
        xs = [p.x for ring in shape.rings for p in ring]
        ys = [p.y for ring in shape.rings for p in ring]
        return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 0, 0)
    if isinstance(shape, Capsule):
        r = shape.radius
        return (min(shape.a.x, shape.b.x) - r, min(shape.a.y, shape.b.y) - r, max(shape.a.x, shape.b.x) + r,
                max(shape.a.y, shape.b.y) + r)  # fmt: skip
    c, r = shape.centre, shape.outer
    return (c.x - r, c.y - r, c.x + r, c.y + r)


# --- the grid --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Grid:
    """A pixel grid: the origin (the top-left corner of pixel ``(0, 0)``), the pitch and the size in
    pixels, all integers of nanometres."""

    origin: Point
    pitch: int
    columns: int
    rows: int


def grid_for(scenes: Iterable[Mapping[str, Any]], pitch_nm: int) -> Grid:
    """One grid over the union of the bounds of ``scenes``, with a margin of one pixel."""
    boxes = [_box(s) for scene in scenes for shapes in shapes_of(scene, pitch_nm).values() for s in shapes]
    if not boxes:
        return Grid(Point(0, 0), pitch_nm, 1, 1)
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    ox = (x0 // pitch_nm - 1) * pitch_nm
    oy = (y0 // pitch_nm - 1) * pitch_nm
    return Grid(Point(ox, oy), pitch_nm, -(-(x1 - ox) // pitch_nm) + 1, -(-(y1 - oy) // pitch_nm) + 1)


# --- rasterising -----------------------------------------------------------------------------------


def _row_intervals(shape: Shape, y: Fraction) -> list[Interval]:
    """The parts of the horizontal line at ``y`` that ``shape`` covers, as closed intervals of x."""
    if isinstance(shape, Polygon):
        crossings: list[Fraction] = []
        for ring in shape.rings:
            n = len(ring)
            for k in range(n):
                a, b = ring[k], ring[(k + 1) % n]
                if (a.y <= y) != (b.y <= y):
                    crossings.append(a.x + (y - a.y) * (b.x - a.x) / Fraction(b.y - a.y))
        crossings.sort()
        return [(crossings[k], crossings[k + 1]) for k in range(0, len(crossings) - 1, 2)]
    if isinstance(shape, Annulus):
        c = shape.centre
        dy = y - c.y
        outer = _half_chord(shape.outer, dy)
        if outer is None:
            return []
        inner = _half_chord(shape.inner, dy) if shape.inner > 0 else None
        if inner is None:
            return [(c.x - outer, c.x + outer)]
        return [(c.x - outer, c.x - inner), (c.x + inner, c.x + outer)]
    return _capsule_row(shape, y)


def _half_chord(radius: int, dy: Fraction) -> Fraction | None:
    """Half the chord of a circle of ``radius`` at the distance ``dy`` from its centre; ``None`` beyond it.
    The root is taken on the integer square, which is exact to a nanometre."""
    left = radius * radius - dy * dy
    if left < 0:
        return None
    return Fraction(isqrt(math.floor(left)))


def _capsule_row(shape: Capsule, y: Fraction) -> list[Interval]:
    a, b, r = shape.a, shape.b, shape.radius
    found: list[Interval] = []
    for end in (a, b):
        half = _half_chord(r, y - end.y)
        if half is not None:
            found.append((end.x - half, end.x + half))
    dx, dy = b.x - a.x, b.y - a.y
    length2 = dx * dx + dy * dy
    if length2:
        reach = isqrt(r * r * length2)  # |cross| ≤ r·|ab|, the root on integers
        low, high = Fraction(-(10**30)), Fraction(10**30)
        ok = True
        # 0 ≤ (x − ax)·dx + (y − ay)·dy ≤ |ab|²
        base = (y - a.y) * dy
        if dx:
            bound1, bound2 = (-base) / dx + a.x, (length2 - base) / dx + a.x
            low, high = max(low, min(bound1, bound2)), min(high, max(bound1, bound2))
        elif not 0 <= base <= length2:
            ok = False
        # −reach ≤ dx·(y − ay) − dy·(x − ax) ≤ reach
        cross = dx * (y - a.y)
        if dy:
            bound1, bound2 = (cross - reach) / Fraction(dy) + a.x, (cross + reach) / Fraction(dy) + a.x
            low, high = max(low, min(bound1, bound2)), min(high, max(bound1, bound2))
        elif abs(cross) > reach:
            ok = False
        if ok and low <= high:
            found.append((low, high))
    if not found:
        return []
    return [(min(i[0] for i in found), max(i[1] for i in found))]  # a capsule is convex


def _columns(interval: Interval, grid: Grid) -> Run | None:
    """The pixels whose centres lie in ``interval``, as a half-open run of columns, clipped to the grid."""
    low, high = interval
    first = math.ceil((low - grid.origin.x) / grid.pitch - Fraction(1, 2))
    last = math.floor((high - grid.origin.x) / grid.pitch - Fraction(1, 2))
    first, last = max(first, 0), min(last, grid.columns - 1)
    return (first, last + 1) if first <= last else None


def _union(runs: Iterable[Run]) -> tuple[Run, ...]:
    out: list[list[int]] = []
    for start, end in sorted(runs):
        if out and start <= out[-1][1]:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return tuple((s, e) for s, e in out)


@dataclass(frozen=True, slots=True)
class Mask:
    """A run-length image on a grid: per row, the inked half-open column runs, in order."""

    grid: Grid
    rows: tuple[tuple[Run, ...], ...]

    @property
    def inked(self) -> int:
        return sum(end - start for row in self.rows for start, end in row)


def rasterise(shapes: Sequence[Shape], grid: Grid) -> Mask:
    """The mask of ``shapes`` on ``grid``: a pixel is inked when its centre lies in a shape."""
    rows: list[list[Run]] = [[] for _ in range(grid.rows)]
    for shape in shapes:
        _, y0, _, y1 = _box(shape)
        first = max(math.ceil(Fraction(y0 - grid.origin.y, grid.pitch) - Fraction(1, 2)), 0)
        last = min(math.floor(Fraction(y1 - grid.origin.y, grid.pitch) - Fraction(1, 2)), grid.rows - 1)
        for row in range(first, last + 1):
            y = grid.origin.y + Fraction((2 * row + 1) * grid.pitch, 2)
            for interval in _row_intervals(shape, y):
                run = _columns(interval, grid)
                if run is not None:
                    rows[row].append(run)
    return Mask(grid, tuple(_union(row) for row in rows))


def render_masks(
    scene: Mapping[str, Any], *, pitch_nm: int, origin: Point, size: tuple[int, int]
) -> dict[str, Mask]:
    """The mask of each layer of a board scene, or of the one layer of a schematic scene, on the grid of
    ``origin``, ``pitch_nm`` and ``size`` (columns, rows)."""
    grid = Grid(origin, pitch_nm, size[0], size[1])
    return {layer: rasterise(shapes, grid) for layer, shapes in sorted(shapes_of(scene, pitch_nm).items())}


# --- comparing -------------------------------------------------------------------------------------


def _dilated(mask: Mask) -> list[tuple[Run, ...]]:
    rows = mask.rows
    out: list[tuple[Run, ...]] = []
    for k in range(len(rows)):
        near = [(s - 1, e + 1) for j in (k - 1, k, k + 1) if 0 <= j < len(rows) for s, e in rows[j]]
        out.append(_union(near))
    return out


def _minus(row: Sequence[Run], other: Sequence[Run]) -> list[Run]:
    out: list[Run] = []
    for start, end in row:
        cursor = start
        for s, e in other:
            if e <= cursor or s >= end:
                continue
            if s > cursor:
                out.append((cursor, s))
            cursor = max(cursor, e)
        if cursor < end:
            out.append((cursor, end))
    return out


@dataclass(frozen=True, slots=True)
class MaskDiff:
    """The comparison of two masks of one grid: the differing pixels of each side (inked there with no
    inked pixel within one pixel on the other side), the inked pixels of both together, the box of the
    largest connected differing region in nanometres (``None`` without one), and whether the differing
    pixels exceed the tolerance."""

    only_a: int
    only_b: int
    inked: int
    box: tuple[int, int, int, int] | None
    exceeds: bool

    @property
    def differing(self) -> int:
        return self.only_a + self.only_b


def _largest(runs: Sequence[tuple[int, Run]], grid: Grid) -> tuple[int, int, int, int] | None:
    """The box of the largest 8-connected region of the runs ``(row, run)``."""
    if not runs:
        return None
    parent = list(range(len(runs)))

    def find(k: int) -> int:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    by_row: dict[int, list[int]] = {}
    for index, (row, _) in enumerate(runs):
        by_row.setdefault(row, []).append(index)
    for index, (row, (start, end)) in enumerate(runs):
        for other in by_row.get(row - 1, []):
            s, e = runs[other][1]
            if s <= end and start <= e:  # touching diagonally counts
                parent[find(index)] = find(other)
    sizes: dict[int, int] = {}
    boxes: dict[int, list[int]] = {}
    for index, (row, (start, end)) in enumerate(runs):
        root = find(index)
        sizes[root] = sizes.get(root, 0) + end - start
        box = boxes.setdefault(root, [start, row, end, row + 1])
        box[0], box[1], box[2], box[3] = (
            min(box[0], start),
            min(box[1], row),
            max(box[2], end),
            max(box[3], row + 1),
        )
    best = max(sizes, key=lambda root: (sizes[root], -boxes[root][1], -boxes[root][0]))
    c0, r0, c1, r1 = boxes[best]
    o, p = grid.origin, grid.pitch
    return (o.x + c0 * p, o.y + r0 * p, o.x + c1 * p, o.y + r1 * p)


def compare_masks(a: Mask, b: Mask, *, pixel_ppm: int = DEFAULT_PIXEL_PPM) -> MaskDiff:
    """Compare two masks of one grid within one pixel; ``exceeds`` when the differing pixels times a million
    exceed ``pixel_ppm`` times the inked pixels."""
    if a.grid != b.grid:
        raise ValueError("compare masks of one grid")
    near_a, near_b = _dilated(a), _dilated(b)
    runs: list[tuple[int, Run]] = []
    only_a = only_b = 0
    inked = 0
    for k in range(a.grid.rows):
        left = _minus(a.rows[k], near_b[k])
        right = _minus(b.rows[k], near_a[k])
        only_a += sum(e - s for s, e in left)
        only_b += sum(e - s for s, e in right)
        runs += [(k, run) for run in _union([*left, *right])]
        inked += sum(e - s for s, e in _union([*a.rows[k], *b.rows[k]]))
    differing = only_a + only_b
    exceeds = differing > 0 and differing * 1_000_000 > pixel_ppm * max(inked, 1)
    return MaskDiff(only_a, only_b, inked, _largest(runs, a.grid), exceeds)


def board_scene(design: Design, frame: BoardFrame | None, *, name: str, backend: str) -> dict[str, Any]:
    """The viewer's scene of ``design``'s board with its zones drawn by outline only (no fill)."""
    board = design.board
    if board is None:
        raise ValueError(f"{name}: the design holds no board")
    bare = tuple(dataclasses.replace(zone, fills=(), filled=False) for zone in board.zones)
    plain = dataclasses.replace(design, board=dataclasses.replace(board, zones=bare))
    return build_scene(plain, frame, name=name, backend=backend)


def _changes(a: Mapping[str, Any], b: Mapping[str, Any]) -> list[str]:
    """The first changes the visual diff names from side ``a`` to side ``b``."""
    one = {**a, "meta": {**dict(a.get("meta") or {}), "backend": "same"}}
    other = {**b, "meta": {**dict(b.get("meta") or {}), "backend": "same"}}
    try:
        diff = visual.compare(other, one)
    except (ValueError, KeyError):
        return []
    return [str(change["text"]) for change in diff["changes"][:CHANGE_LIMIT]]


def compare_scenes(
    scenes_a: Mapping[str, Mapping[str, Any]],
    scenes_b: Mapping[str, Mapping[str, Any]],
    *,
    pixel_ppm: int = DEFAULT_PIXEL_PPM,
    board_pitch_nm: int = BOARD_PITCH_NM,
    sheet_pitch_nm: int = SHEET_PITCH_NM,
) -> SceneComparison:
    """Level 8 over two sets of scenes, by name: a board scene is compared layer by layer (``where`` the
    layer, or ``<board>/<layer>`` when there are several), a schematic scene as one picture (``where`` its
    sheet path). A scene or a layer that one side alone draws gives ``render-missing``."""
    differences: list[Finding] = []
    layers = sheets = 0
    changes: dict[str, list[str]] = {}
    boards = sum(1 for scene in scenes_a.values() if scene.get("kind") != "schematic")
    for name in sorted(set(scenes_a) | set(scenes_b)):
        one, other = scenes_a.get(name), scenes_b.get(name)
        if one is None or other is None:
            differences.append(
                Finding("render-missing", name, "layer", name if one else "", name if other else "")
            )
            continue
        sheet = one.get("kind") == "schematic"
        pitch = sheet_pitch_nm if sheet else board_pitch_nm
        grid = grid_for((one, other), pitch)
        size = (grid.columns, grid.rows)
        masks_a = render_masks(one, pitch_nm=pitch, origin=grid.origin, size=size)
        masks_b = render_masks(other, pitch_nm=pitch, origin=grid.origin, size=size)
        found_changes = False
        for layer in sorted(set(masks_a) | set(masks_b)):
            where = name if sheet else (layer if boards == 1 else f"{name}/{layer}")
            if layer not in masks_a or layer not in masks_b:
                differences.append(
                    Finding(
                        "render-missing",
                        where,
                        "layer",
                        layer if layer in masks_a else "",
                        layer if layer in masks_b else "",
                    )  # fmt: skip
                )
                continue
            if sheet:
                sheets += 1
            else:
                layers += 1
            diff = compare_masks(masks_a[layer], masks_b[layer], pixel_ppm=pixel_ppm)
            if diff.exceeds and diff.box is not None:
                x0, y0, x1, y1 = diff.box
                differences.append(
                    Finding(
                        "render-pixels",
                        f"{where}:{x0},{y0}-{x1},{y1}",
                        "pixels",
                        f"{diff.only_a}/{diff.inked}",
                        f"{diff.only_b}/{diff.inked}",
                    )  # fmt: skip
                )
                found_changes = True
        if found_changes:
            changes[name] = _changes(one, other)
    ordered = tuple(sorted(differences, key=lambda d: (d.where, d.kind, d.field, d.a, d.b)))
    summary: dict[str, object] = {
        "layers": layers,
        "sheets": sheets,
        "pixel_ppm": pixel_ppm,
        "pitch_nm": {"board": board_pitch_nm, "sheet": sheet_pitch_nm},
        "changes": changes,
    }
    return SceneComparison(ordered, layers + sheets, summary)


__all__ = [
    "BOARD_PITCH_NM",
    "DEFAULT_PIXEL_PPM",
    "SHEET_PITCH_NM",
    "Finding",
    "Grid",
    "Mask",
    "MaskDiff",
    "SceneComparison",
    "board_scene",
    "compare_masks",
    "compare_scenes",
    "grid_for",
    "rasterise",
    "render_masks",
    "shapes_of",
]

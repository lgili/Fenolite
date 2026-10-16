# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Where every part of a panel lies (capability board-panels, "Panel layout" and "Panel separations";
change c0173, design Decisions 2 to 4).

``layout(panel, board)`` is pure and integer. The board's box is the box of its outline; each copy is that
box moved by an integer translation after a quarter turn, so nothing is rounded. Panel coordinates have
their origin at the panel's top-left corner, Y down.

- **Copies** sit in rows and columns inside the rails: a V-scored edge set has no gap (the boards touch), a
  tabbed one the array's gap; between rails and copies the ``rails`` set decides, and the gap of a rail on
  the top or bottom is ``gap_y``, on the left or right ``gap_x``.
- **Tabs.** Along each tabbed edge of length ``L``, ``n = max(1, ⌈L / pitch⌉)`` tabs at ``(i + ½)·L/n``,
  each ``width`` wide across the gap. A tab between two copies has a row of holes at each copy's edge, a
  tab to a rail one row at the copy's edge and none on the rail's side; the holes are ``drill + hole_gap``
  apart, tangent to the copy's edge outside it, or reaching ``inset`` into it.
- **Score lines.** One straight line per V-scored boundary, from panel edge to panel edge.
- **Rings.** The panel's material is the rails, the copies and the tabs. ``outline`` is the boundary of
  that material: ring 0 is the outer ring and the others are the routed gaps enclosed by it (KiCad's
  ``Edge.Cuts``). ``routes`` are the boundaries of the routed regions inside the panel's rectangle (the
  route tool path of an Altium panel). Every ring is rectilinear and found on the grid of the rectangles'
  coordinates, exactly.
- **Fiducials and tooling holes** are the script's, or placed on the rails by ``fiducials()`` and
  ``tooling_holes()``: three fiducials in an L near the corners, their centres ``limits.fiducial_edge``
  from the panel's long edges, and four tooling holes at the corners of the rails.

This release panels boards whose outline is one rectangle (``panel.board-outline`` otherwise): a V-score
needs straight edges, and the routed gaps are found from the copies' boxes.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal

from fenolite.backends.kicad.outline import edge_outline
from fenolite.core.coords import Point, Size
from fenolite.core.errors import Issue
from fenolite.core.trig import QUARTER_TURN
from fenolite.core.units import Nm, Udeg, format_length
from fenolite.geometry.transform import rotate_point
from fenolite.model.design import Design
from fenolite.model.panel import BETWEEN, Method, Panel, PanelFiducial, PanelHole
from fenolite.panel import ids
from fenolite.panel.limits import resolved

MM = 1_000_000
Axis = Literal["x", "y"]
X: Axis = "x"
Y: Axis = "y"
"""``x``: a line of constant X (vertical); ``y``: a line of constant Y (horizontal)."""
FIDUCIAL_ALONG = 10 * MM
"""How far from the panel's side the placed fiducials lie along a rail (a Fenolite choice, clear of the
tooling holes)."""
TOOLING_ALONG = 5 * MM
"""How far from the panel's side the placed tooling holes lie along a rail (a Fenolite choice)."""


def _mm(value: int) -> str:
    return format_length(value)


@dataclass(frozen=True, slots=True)
class Rect:
    """An axis-aligned rectangle ``[x0, x1] × [y0, y1]``."""

    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0

    def corners(self) -> tuple[Point, ...]:
        return (
            Point(self.x0, self.y0),
            Point(self.x1, self.y0),
            Point(self.x1, self.y1),
            Point(self.x0, self.y1),
        )

    def contains(self, other: Rect) -> bool:
        return self.x0 <= other.x0 and self.y0 <= other.y0 and other.x1 <= self.x1 and other.y1 <= self.y1


@dataclass(frozen=True, slots=True)
class BoardShape:
    """What a layout needs of the board: the box of its outline (board frame), whether that outline is the
    box, its cut-outs and slots, and its thickness (``None`` when the board states none)."""

    box: Rect
    rectangular: bool
    inner_rings: int = 0
    thickness: Nm | None = None


def board_shape(design: Design) -> BoardShape | None:
    """The shape of ``design``'s board: from ``Board.outline`` when it has one (a design read from Altium or
    built from a script), else from its edges (``edge_outline``). ``None`` without a closed outline."""
    board = design.board
    if board is None:
        return None
    outline = board.outline if board.outline is not None and board.outline.points else edge_outline(design)
    if outline is None or len(outline.points) < 2:
        return None
    xs = [p.x for p in outline.points]
    ys = [p.y for p in outline.points]
    box = Rect(min(xs), min(ys), max(xs), max(ys))
    ring0_arcs = [arc for arc in outline.arcs if arc.ring == 0]
    corners = set(box.corners())
    rectangular = not ring0_arcs and len(outline.points) == 4 and set(outline.points) == corners
    thickness = board.stackup.thickness() if board.stackup is not None and board.stackup.layers else None
    inner = len(outline.cutouts) + len(outline.slots)
    return BoardShape(box, rectangular, inner, thickness or None)


@dataclass(frozen=True, slots=True)
class PanelCopy:
    """Copy ``k`` at ``row`` and ``col``: the board turned by ``rotation`` and moved so that the box of its
    outline has its top-left corner at ``origin``; ``rect`` is that box in the panel."""

    id: str
    row: int
    col: int
    k: int
    origin: Point
    rotation: Udeg
    rect: Rect
    board_min: Point
    """The top-left corner of the turned board box, in the turned board frame."""

    def place(self, p: Point) -> Point:
        """The panel point of the board point ``p`` (exact for a quarter turn)."""
        q = rotate_point(p, self.rotation)
        return Point(q.x - self.board_min.x + self.origin.x, q.y - self.board_min.y + self.origin.y)

    def unplace(self, q: Point) -> Point:
        """The board point of the panel point ``q``."""
        p = Point(q.x - self.origin.x + self.board_min.x, q.y - self.origin.y + self.board_min.y)
        return rotate_point(p, -self.rotation)


@dataclass(frozen=True, slots=True)
class Tab:
    """A tab across a routed gap: ``rect`` in the panel, its ``holes`` (centres) and their ``drill``.
    ``edge`` names the boundary (``x<c>.<r>`` between columns ``c`` and ``c + 1`` in row ``r``, ``y<r>.<c>``
    between rows, ``top.<c>``, ``bottom.<c>``, ``left.<r>``, ``right.<r>`` to a rail); ``copies`` are the
    numbers ``k`` of the copies it holds; ``axis`` is the direction of the gap's length."""

    id: str
    edge: str
    k: int
    rect: Rect
    axis: Axis
    holes: tuple[Point, ...]
    drill: Nm
    copies: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ScoreLine:
    """A V-score line: of constant X (``axis`` ``x``) or Y at ``at``, from ``start`` to ``end`` along the
    other axis. ``boundary`` names it as a tab's ``edge`` does, without the row or column."""

    id: str
    axis: Axis
    at: int
    start: int
    end: int
    boundary: str

    def points(self) -> tuple[Point, Point]:
        if self.axis == "x":
            return Point(self.at, self.start), Point(self.at, self.end)
        return Point(self.start, self.at), Point(self.end, self.at)


@dataclass(frozen=True, slots=True)
class PlacedFiducial:
    id: str
    ref: str
    at: Point
    side: Literal["top", "bottom"]
    copper: Nm
    mask: Nm


@dataclass(frozen=True, slots=True)
class PlacedHole:
    id: str
    ref: str
    at: Point
    drill: Nm


@dataclass(frozen=True, slots=True)
class PanelLayout:
    """The laid-out panel. ``unused`` is what an asked ``fit`` size leaves (0 × 0 for a grid); ``issues``
    are the structural errors (``panel.board-outline``, ``panel.no-fit``) and placement warnings found while
    laying out."""

    rows: int
    cols: int
    rotation: Udeg
    size: Size
    unused: Size
    board: Rect
    copies: tuple[PanelCopy, ...] = ()
    rails: tuple[Rect, ...] = ()
    gaps: dict[str, Nm] = field(default_factory=lambda: {})
    tabs: tuple[Tab, ...] = ()
    score_lines: tuple[ScoreLine, ...] = ()
    outline: tuple[tuple[Point, ...], ...] = ()
    routes: tuple[tuple[Point, ...], ...] = ()
    fiducials: tuple[PlacedFiducial, ...] = ()
    tooling_holes: tuple[PlacedHole, ...] = ()
    methods: dict[str, Method] = field(default_factory=lambda: {})
    issues: tuple[Issue, ...] = ()

    @property
    def frame(self) -> Rect:
        return Rect(0, 0, self.size.w, self.size.h)

    @property
    def frame_ring(self) -> tuple[Point, ...]:
        """Ring 0 of ``outline``: the outer ring of the panel's material."""
        return self.outline[0] if self.outline else ()

    @property
    def gap_rings(self) -> tuple[tuple[Point, ...], ...]:
        """The inner rings of ``outline``: the routed gaps that the material encloses."""
        return self.outline[1:]


def _issue(
    code: str, severity: Literal["error", "warning", "info"], message: str, where: str = "", hint: str = ""
) -> Issue:
    return Issue(code, severity, message, where=where, hint=hint)


# --- the counts ----------------------------------------------------------------------------------------


def _turned(box: Rect, rotation: Udeg) -> tuple[int, int]:
    return (box.height, box.width) if (rotation // QUARTER_TURN) % 2 else (box.width, box.height)


@dataclass(frozen=True, slots=True)
class _Spacing:
    gx: int
    gy: int
    left: int
    right: int
    top: int
    bottom: int
    """The rail gaps: a tabbed rail that exists is ``gap_x`` (left, right) or ``gap_y`` (top, bottom) from
    the copies; a V-scored one, or a missing rail, 0."""


def _spacing(panel: Panel) -> _Spacing:
    array, frame = panel.array, panel.frame
    gx = 0 if panel.method("columns") == "vscore" else array.gap_x
    gy = 0 if panel.method("rows") == "vscore" else array.gap_y
    tabbed_rails = panel.method("rails") == "tabs"

    def rail(width: int, gap: int) -> int:
        return gap if tabbed_rails and width > 0 else 0

    return _Spacing(
        gx,
        gy,
        rail(frame.left, array.gap_x),
        rail(frame.right, array.gap_x),
        rail(frame.top, array.gap_y),
        rail(frame.bottom, array.gap_y),
    )


def fit_counts(panel: Panel, box: Rect, rotation: Udeg, width: Nm, height: Nm) -> tuple[int, int]:
    """``(rows, cols)`` that ``width × height`` holds at ``rotation``: ``cols = ⌊(U + g) / (b + g)⌋`` with
    ``U`` the width inside the rails and their gaps, ``b`` the turned box's width and ``g`` the gap between
    columns; rows likewise (capability design-dsl, "Panel fit rule")."""
    s = _spacing(panel)
    frame = panel.frame
    bw, bh = _turned(box, rotation)
    usable_w = width - frame.left - frame.right - s.left - s.right
    usable_h = height - frame.top - frame.bottom - s.top - s.bottom
    cols = max(0, (usable_w + s.gx) // (bw + s.gx)) if usable_w > 0 else 0
    rows = max(0, (usable_h + s.gy) // (bh + s.gy)) if usable_h > 0 else 0
    return rows, cols


# --- rings on the grid of the rectangles ----------------------------------------------------------------


def _loops(mask: set[tuple[int, int]], xs: list[int], ys: list[int]) -> list[tuple[Point, ...]]:
    """The boundary loops of the cells in ``mask`` (cell ``(i, j)`` spans ``xs[i]..xs[i+1]`` ×
    ``ys[j]..ys[j+1]``), each traced with the cells on one side, collinear vertices dropped, starting at
    its least vertex."""
    edges: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for i, j in mask:
        if (i, j - 1) not in mask:
            edges[(i, j)].append((i + 1, j))
        if (i + 1, j) not in mask:
            edges[(i + 1, j)].append((i + 1, j + 1))
        if (i, j + 1) not in mask:
            edges[(i + 1, j + 1)].append((i, j + 1))
        if (i - 1, j) not in mask:
            edges[(i, j + 1)].append((i, j))
    for ends in edges.values():
        ends.sort()
    loops: list[tuple[Point, ...]] = []
    while edges:
        start = min(edges)
        path = [start]
        at = start
        while True:
            ends = edges[at]
            nxt = ends.pop(0)
            if not ends:
                del edges[at]
            if nxt == start:
                break
            path.append(nxt)
            at = nxt
        points = [Point(xs[i], ys[j]) for i, j in path]
        kept: list[Point] = []
        n = len(points)
        for k, p in enumerate(points):
            a, b = points[k - 1], points[(k + 1) % n]
            if (a.x == p.x == b.x) or (a.y == p.y == b.y):
                continue
            kept.append(p)
        low = kept.index(min(kept, key=lambda p: (p.x, p.y)))
        loops.append(tuple(kept[low:] + kept[:low]))
    return loops


def _area2(ring: tuple[Point, ...]) -> int:
    return sum(a.x * b.y - b.x * a.y for a, b in zip(ring, ring[1:] + ring[:1], strict=True))


def rings(
    frame: Rect, material: list[Rect]
) -> tuple[tuple[tuple[Point, ...], ...], tuple[tuple[Point, ...], ...]]:
    """``(outline, routes)``: the boundary rings of the union of ``material`` (the largest first, then the
    others in the order of their least vertex) and the boundary rings of what of ``frame`` it leaves."""
    xs = sorted({frame.x0, frame.x1, *(r.x0 for r in material), *(r.x1 for r in material)})
    ys = sorted({frame.y0, frame.y1, *(r.y0 for r in material), *(r.y1 for r in material)})
    xi = {x: i for i, x in enumerate(xs)}
    yi = {y: j for j, y in enumerate(ys)}
    covered: set[tuple[int, int]] = set()
    for rect in material:
        for i in range(xi[rect.x0], xi[rect.x1]):
            for j in range(yi[rect.y0], yi[rect.y1]):
                covered.add((i, j))
    inside = {(i, j) for i in range(xi[frame.x0], xi[frame.x1]) for j in range(yi[frame.y0], yi[frame.y1])}
    outline = _loops(covered, xs, ys)
    outline.sort(key=lambda ring: (-abs(_area2(ring)), min(ring)))
    routes = sorted(_loops(inside - covered, xs, ys), key=min)
    return tuple(outline), tuple(routes)


# --- the layout ------------------------------------------------------------------------------------------


def _ceil_div(a: int, b: int) -> int:
    return -(-a // b)


def _hole_row(center: int, holes: int, pitch: int) -> list[int]:
    """The positions of ``holes`` holes ``pitch`` apart, centred on ``center``."""
    return [center + (2 * j - (holes - 1)) * pitch // 2 for j in range(holes)]


def layout(panel: Panel, board: Design | BoardShape) -> PanelLayout:  # noqa: C901, PLR0912, PLR0915
    """The layout of ``panel`` over ``board`` (a design, or its ``board_shape``)."""
    shape = board if isinstance(board, BoardShape) else board_shape(board)
    limits = resolved(panel.limits)
    if shape is None or not shape.rectangular:
        reason = (
            "the board has no closed outline"
            if shape is None
            else "the board's outline is not one rectangle; this release panels rectangular boards"
        )
        empty = Rect(0, 0, 0, 0) if shape is None else shape.box
        return PanelLayout(
            0,
            0,
            0,
            Size(0, 0),
            Size(0, 0),
            empty,
            issues=(
                _issue(
                    "panel.board-outline",
                    "error",
                    reason,
                    where="board",
                    hint="give the board a closed rectangular outline on Edge.Cuts",
                ),
            ),
        )
    box = shape.box
    issues: list[Issue] = []
    rotation = panel.array.rotation
    rows, cols = panel.array.rows, panel.array.cols
    unused_target: tuple[int, int] | None = None
    if panel.fit is not None:
        fit = panel.fit
        rows, cols = fit_counts(panel, box, rotation, fit.width, fit.height)
        if fit.auto_rotate:
            options = [(0, *fit_counts(panel, box, 0, fit.width, fit.height))]
            options.append((QUARTER_TURN, *fit_counts(panel, box, QUARTER_TURN, fit.width, fit.height)))
            best = max(options, key=lambda o: (o[1] * o[2], -o[0]))
            rotation, rows, cols = best
        unused_target = (fit.width, fit.height)
        if rows * cols == 0:
            return PanelLayout(
                0,
                0,
                rotation,
                Size(0, 0),
                Size(fit.width, fit.height),
                box,
                issues=(
                    _issue(
                        "panel.no-fit",
                        "error",
                        f"no copy of the {_mm(box.width)} × {_mm(box.height)} board fits in "
                        f"{_mm(fit.width)} × {_mm(fit.height)} with these rails and gaps",
                        where="fit",
                        hint="ask for a larger size, or narrower rails or gaps",
                    ),
                ),
            )
    s = _spacing(panel)
    frame = panel.frame
    bw, bh = _turned(box, rotation)
    x_start = frame.left + s.left
    y_start = frame.top + s.top
    width = x_start + cols * bw + (cols - 1) * s.gx + s.right + frame.right
    height = y_start + rows * bh + (rows - 1) * s.gy + s.bottom + frame.bottom
    turned = (rotate_point(Point(box.x0, box.y0), rotation), rotate_point(Point(box.x1, box.y1), rotation))
    board_min = Point(min(p.x for p in turned), min(p.y for p in turned))
    copies: list[PanelCopy] = []
    for row in range(1, rows + 1):
        for col in range(1, cols + 1):
            x0 = x_start + (col - 1) * (bw + s.gx)
            y0 = y_start + (row - 1) * (bh + s.gy)
            rect = Rect(x0, y0, x0 + bw, y0 + bh)
            k = (row - 1) * cols + col
            copies.append(
                PanelCopy(ids.copy_id(row, col), row, col, k, Point(x0, y0), rotation, rect, board_min)
            )
    by_cell = {(c.row, c.col): c for c in copies}
    rails: list[Rect] = []
    if frame.top:
        rails.append(Rect(0, 0, width, frame.top))
    if frame.bottom:
        rails.append(Rect(0, height - frame.bottom, width, height))
    if frame.left:
        rails.append(Rect(0, 0, frame.left, height))
    if frame.right:
        rails.append(Rect(width - frame.right, 0, width, height))
    spec = panel.tabs
    pitch = spec.drill + spec.hole_gap
    half = spec.drill // 2
    tabs: list[Tab] = []

    def add_tabs(
        edge: str,
        span: tuple[int, int],
        across: tuple[int, int],
        axis: Axis,
        sides: tuple[int | None, int | None],
        held: tuple[int, ...],
    ) -> None:
        """Tabs along the gap ``across[0]..across[1]`` (perpendicular to ``axis``... the gap's length runs
        along ``axis`` over ``span``); ``sides`` are the copy edges at either end of the gap that get holes
        (``None``: a rail)."""
        length = span[1] - span[0]
        n = max(1, _ceil_div(length, spec.pitch))
        for i in range(n):
            centre = span[0] + (2 * i + 1) * length // (2 * n)
            lo, hi = centre - spec.width // 2, centre - spec.width // 2 + spec.width
            holes: list[Point] = []
            for side, sign in zip(sides, (1, -1), strict=True):
                if side is None or not spec.holes:
                    continue
                at = side + sign * (half - spec.inset)
                for along in _hole_row(centre, spec.holes, pitch):
                    holes.append(Point(at, along) if axis == "y" else Point(along, at))
            rect = Rect(across[0], lo, across[1], hi) if axis == "y" else Rect(lo, across[0], hi, across[1])
            tabs.append(Tab(ids.tab_id(edge, i + 1), edge, i + 1, rect, axis, tuple(holes), spec.drill, held))

    methods: dict[str, Method] = {between: panel.method(between) for between in BETWEEN}
    if methods["columns"] == "tabs":
        for col in range(1, cols):
            for row in range(1, rows + 1):
                a, b = by_cell[(row, col)], by_cell[(row, col + 1)]
                add_tabs(
                    f"x{col}.{row}",
                    (a.rect.y0, a.rect.y1),
                    (a.rect.x1, b.rect.x0),
                    "y",
                    (a.rect.x1, b.rect.x0),
                    (a.k, b.k),
                )
    if methods["rows"] == "tabs":
        for row in range(1, rows):
            for col in range(1, cols + 1):
                a, b = by_cell[(row, col)], by_cell[(row + 1, col)]
                add_tabs(
                    f"y{row}.{col}",
                    (a.rect.x0, a.rect.x1),
                    (a.rect.y1, b.rect.y0),
                    "x",
                    (a.rect.y1, b.rect.y0),
                    (a.k, b.k),
                )
    if methods["rails"] == "tabs":
        for col in range(1, cols + 1):
            if frame.top:
                c = by_cell[(1, col)]
                add_tabs(
                    f"top.{col}",
                    (c.rect.x0, c.rect.x1),
                    (frame.top, c.rect.y0),
                    "x",
                    (None, c.rect.y0),
                    (c.k,),
                )
            if frame.bottom:
                c = by_cell[(rows, col)]
                add_tabs(
                    f"bottom.{col}",
                    (c.rect.x0, c.rect.x1),
                    (c.rect.y1, height - frame.bottom),
                    "x",
                    (c.rect.y1, None),
                    (c.k,),
                )
        for row in range(1, rows + 1):
            if frame.left:
                c = by_cell[(row, 1)]
                add_tabs(
                    f"left.{row}",
                    (c.rect.y0, c.rect.y1),
                    (frame.left, c.rect.x0),
                    "y",
                    (None, c.rect.x0),
                    (c.k,),
                )
            if frame.right:
                c = by_cell[(row, cols)]
                add_tabs(
                    f"right.{row}",
                    (c.rect.y0, c.rect.y1),
                    (c.rect.x1, width - frame.right),
                    "y",
                    (c.rect.x1, None),
                    (c.k,),
                )
    lines: list[tuple[Axis, int, str]] = []
    if methods["columns"] == "vscore":
        for col in range(1, cols):
            lines.append((X, by_cell[(1, col)].rect.x1, f"x{col}"))
    if methods["rows"] == "vscore":
        for row in range(1, rows):
            lines.append((Y, by_cell[(row, 1)].rect.y1, f"y{row}"))
    if methods["rails"] == "vscore":
        if frame.top:
            lines.append((Y, frame.top, "top"))
        if frame.bottom:
            lines.append((Y, height - frame.bottom, "bottom"))
        if frame.left:
            lines.append((X, frame.left, "left"))
        if frame.right:
            lines.append((X, width - frame.right, "right"))
    lines.sort(key=lambda line: (line[0], line[1]))
    counters = {"x": 0, "y": 0}
    scores: list[ScoreLine] = []
    for axis, at, boundary in lines:
        counters[axis] += 1
        end = height if axis == "x" else width
        scores.append(ScoreLine(ids.vscore_id(axis, counters[axis]), axis, at, 0, end, boundary))
    frame_rect = Rect(0, 0, width, height)
    material = [*rails, *(c.rect for c in copies), *(t.rect for t in tabs)]
    outline, routes = rings(frame_rect, material)
    fiducials = _fiducials(panel, width, height, limits.fiducial_edge, issues)
    holes = _tooling(panel, width, height, issues)
    unused = (
        Size(0, 0) if unused_target is None else Size(unused_target[0] - width, unused_target[1] - height)
    )
    return PanelLayout(
        rows=rows,
        cols=cols,
        rotation=rotation,
        size=Size(width, height),
        unused=unused,
        board=box,
        copies=tuple(copies),
        rails=tuple(rails),
        gaps={
            "columns": s.gx,
            "rows": s.gy,
            "top": s.top,
            "bottom": s.bottom,
            "left": s.left,
            "right": s.right,
        },
        tabs=tuple(tabs),
        score_lines=tuple(scores),
        outline=outline,
        routes=routes,
        fiducials=fiducials,
        tooling_holes=holes,
        methods=methods,
        issues=tuple(issues),
    )


def _fiducials(
    panel: Panel, width: int, height: int, edge: int, issues: list[Issue]
) -> tuple[PlacedFiducial, ...]:
    placed = [
        PlacedFiducial(ids.fiducial_id(f.ref), f.ref, f.at, f.side, f.copper, f.mask) for f in panel.fiducials
    ]
    auto = panel.fiducial_set
    if auto is None:
        return tuple(placed)
    frame = panel.frame
    n = len(placed)
    for side in auto.sides:
        spots = _rail_spots(
            frame.top,
            frame.bottom,
            frame.left,
            frame.right,
            width,
            height,
            edge,
            auto.mask,
            FIDUCIAL_ALONG,
            three=True,
        )
        if spots is None:
            issues.append(
                _issue(
                    "panel.fiducial-place",
                    "warning",
                    "fiducials() places fiducials on rails, and the panel has no pair of rails wide enough",
                    where="fiducials",
                    hint="add rails(top=…, bottom=…) or place fiducial(ref, x, y)",
                )
            )
            break
        for spot in spots:
            n += 1
            ref = f"PFID{n}"
            placed.append(PlacedFiducial(ids.fiducial_id(ref), ref, spot, side, auto.copper, auto.mask))
    return tuple(placed)


def _rail_spots(
    top: int,
    bottom: int,
    left: int,
    right: int,
    width: int,
    height: int,
    edge: int,
    size: int,
    along: int,
    *,
    three: bool,
) -> tuple[Point, ...] | None:
    """Corner spots on a pair of rails: on the top and bottom rails when both exist, else on the left and
    right ones; the centre ``edge`` from the panel's edge (at least the rail's middle, at most the rail's
    width less half of ``size``) and ``along`` from the panel's sides. Three in an L, or four."""
    if top and bottom:
        across_top = min(max(edge, top // 2), top - size // 2)
        across_bottom = min(max(edge, bottom // 2), bottom - size // 2)
        spots = [
            Point(along, across_top),
            Point(width - along, across_top),
            Point(along, height - across_bottom),
            Point(width - along, height - across_bottom),
        ]
    elif left and right:
        across_left = min(max(edge, left // 2), left - size // 2)
        across_right = min(max(edge, right // 2), right - size // 2)
        spots = [
            Point(across_left, along),
            Point(across_left, height - along),
            Point(width - across_right, along),
            Point(width - across_right, height - along),
        ]
    else:
        return None
    return tuple(spots[:3] if three else spots)


def _tooling(panel: Panel, width: int, height: int, issues: list[Issue]) -> tuple[PlacedHole, ...]:
    placed = [PlacedHole(ids.tooling_id(h.ref), h.ref, h.at, h.drill) for h in panel.tooling_holes]
    auto = panel.tooling_set
    if auto is None:
        return tuple(placed)
    frame = panel.frame
    spots = _rail_spots(
        frame.top,
        frame.bottom,
        frame.left,
        frame.right,
        width,
        height,
        0,
        auto.drill,
        TOOLING_ALONG,
        three=False,
    )
    if spots is None:
        issues.append(
            _issue(
                "panel.tooling-place",
                "warning",
                "tooling_holes() places holes on rails, and the panel has no pair of rails",
                where="tooling_holes",
                hint="add rails(top=…, bottom=…) or place tooling_hole(ref, x, y)",
            )
        )
        return tuple(placed)
    n = len(placed)
    for spot in spots:
        n += 1
        ref = f"PTH{n}"
        placed.append(PlacedHole(ids.tooling_id(ref), ref, spot, auto.drill))
    return tuple(placed)


def fiducial_of(item: PanelFiducial) -> PlacedFiducial:
    return PlacedFiducial(ids.fiducial_id(item.ref), item.ref, item.at, item.side, item.copper, item.mask)


def hole_of(item: PanelHole) -> PlacedHole:
    return PlacedHole(ids.tooling_id(item.ref), item.ref, item.at, item.drill)


__all__ = [
    "BoardShape",
    "PanelCopy",
    "PanelLayout",
    "PlacedFiducial",
    "PlacedHole",
    "Rect",
    "ScoreLine",
    "Tab",
    "board_shape",
    "fit_counts",
    "layout",
    "rings",
]

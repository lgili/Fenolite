# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The spine trees of the role copper (change c0243, decision 3; capability net-roles, "Power and
switch-node copper"; ``docs/roles.md``, "Role copper").

A net's terminals (pad clusters, and the loose ends of its tracks) are joined by a rectilinear tree: Prim's
order by Manhattan distance, pad labels breaking ties, the edges of a hot loop placed first. Each edge is
the cheapest free path of horizontal and vertical segments among a straight run, the two L shapes and the
Z shapes whose middle line lies on a grid of ``step``: its length plus a penalty per turn. A path is free
when each segment, at the band's base width, keeps every obstacle's gap (``thick_closer_than``, exact on
integers). An edge without a free path is reported as blocked, never forced. Nothing here imports a
backend; every length is an integer of nanometres.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from fenolite.core.coords import Point
from fenolite.geometry import BBox, SpatialIndex, Thick, thick_bbox, thick_closer_than

MIN_STEP_NM = 100_000
"""The finest grid of the middle line of a Z path: 0.1 mm."""
REACH_STEPS = 12
"""How far a Z path's middle line may lie outside the box of its two ends, in steps."""


@dataclass(frozen=True, slots=True)
class Terminal:
    """One end of an edge: its label (the pad names of a cluster, or ``end@x,y`` for a loose end), the point
    the spine starts from, and the copper of the net there on the layer (where an end may be snapped)."""

    label: str
    centre: Point
    copper: tuple[Thick, ...] = ()

    def holds(self, point: Point) -> bool:
        """Whether ``point`` lies on the terminal's copper (its centre always does)."""
        if point == self.centre:
            return True
        probe = Thick((point,), 2)
        return any(thick_closer_than(probe, shape, 1) for shape in self.copper)


class Obstacles:
    """Shapes that a spine keeps away from, each with its own gap (the clearance, or the switching distance
    for the copper of a victim of a switch node)."""

    def __init__(self, items: Sequence[tuple[Thick, int]]) -> None:
        self.items = list(items)
        self._index = SpatialIndex[int].build(
            (thick_bbox(shape).inflate(gap), number) for number, (shape, gap) in enumerate(self.items)
        )

    def hits(self, shape: Thick) -> bool:
        """Whether ``shape`` comes nearer to an obstacle than its gap."""
        box: BBox = thick_bbox(shape)
        for number in self._index.query(box):
            other, gap = self.items[number]
            if thick_closer_than(shape, other, gap):
                return True
        return False


def _segments(points: Sequence[Point]) -> list[tuple[Point, Point]]:
    return [(a, b) for a, b in zip(points, points[1:], strict=False) if a != b]


def _clean(points: Sequence[Point]) -> tuple[Point, ...]:
    """``points`` without repeats and without points in the middle of a straight run."""
    out: list[Point] = []
    for point in points:
        if out and out[-1] == point:
            continue
        if len(out) >= 2:
            a, b = out[-2], out[-1]
            if (a.x == b.x == point.x) or (a.y == b.y == point.y):
                out[-1] = point
                continue
        out.append(point)
    return tuple(out)


def length(points: Sequence[Point]) -> int:
    """The Manhattan length of a rectilinear path."""
    return sum(abs(b.x - a.x) + abs(b.y - a.y) for a, b in _segments(points))


def _valid(points: Sequence[Point], least: int) -> bool:
    """Horizontal and vertical segments, no turn back, inner segments at least ``least`` long."""
    segments = _segments(points)
    if not segments:
        return False
    previous: tuple[int, int] | None = None
    for number, (a, b) in enumerate(segments):
        dx, dy = b.x - a.x, b.y - a.y
        if dx and dy:
            return False
        direction = ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))
        if previous is not None and direction == (-previous[0], -previous[1]):
            return False
        inner = 0 < number < len(segments) - 1
        if inner and abs(dx) + abs(dy) < least:
            return False
        previous = direction
    return True


def candidates(a: Terminal, b: Terminal, *, step: int, least: int) -> list[tuple[Point, ...]]:
    """The rectilinear paths from ``a`` to ``b`` that a spine may take, in no order: a straight run (the
    ends snapped onto the other terminal's copper when they are nearly aligned), two L shapes and the Z
    shapes on the grid of ``step``."""
    p, q = a.centre, b.centre
    found: list[tuple[Point, ...]] = []
    if p.x == q.x or p.y == q.y:
        found.append((p, q))
    # a nearly aligned end may be snapped onto the other terminal's copper, as long as the band, ``least``
    # wide, still covers that terminal's centre (the anchor the copper analyses join pads by)
    for snapped_end in (Point(p.x, q.y), Point(q.x, p.y)):
        if snapped_end != q and 2 * _manhattan(snapped_end, q) < least and b.holds(snapped_end):
            found.append((p, snapped_end))
    for snapped_start in (Point(q.x, p.y), Point(p.x, q.y)):
        if snapped_start != p and 2 * _manhattan(snapped_start, p) < least and a.holds(snapped_start):
            found.append((snapped_start, q))
    found.append((p, Point(q.x, p.y), q))
    found.append((p, Point(p.x, q.y), q))
    grid = max(step, MIN_STEP_NM)
    reach = REACH_STEPS * grid
    for horizontal in (True, False):
        low = min(p.x, q.x) if horizontal else min(p.y, q.y)
        high = max(p.x, q.x) if horizontal else max(p.y, q.y)
        first = -(-(low - reach) // grid) * grid
        for middle in range(first, high + reach + 1, grid):
            if horizontal:
                found.append((p, Point(middle, p.y), Point(middle, q.y), q))
            else:
                found.append((p, Point(p.x, middle), Point(q.x, middle), q))
    paths = {_clean(path) for path in found}
    return sorted(path for path in paths if len(path) >= 2 and _valid(path, least))


def route(
    a: Terminal,
    b: Terminal,
    *,
    width: int,
    step: int,
    obstacles: Obstacles,
    turn: int | None = None,
    bounds: BBox | None = None,
) -> tuple[Point, ...] | None:
    """The cheapest free path from ``a`` to ``b`` at ``width``, or ``None``: among the straight, L and Z
    paths, its Manhattan length plus ``turn`` (default two widths) per turn, ties by the points; when none is
    free, the grid search of ``search`` within ``bounds``."""
    penalty = 2 * width if turn is None else turn
    ranked = sorted(
        candidates(a, b, step=step, least=width),
        key=lambda path: (length(path) + penalty * (len(path) - 2), path),
    )
    for path in ranked:
        if free_path(path, width, obstacles):
            longer = extend(path, width, obstacles, (a, b))
            if ends_hold(longer, width):
                return longer
    found = search(a, b, width=width, step=step, obstacles=obstacles, turn=penalty, bounds=bounds)
    if found is None or not free_path(found, width, obstacles):
        return None
    longer = extend(found, width, obstacles, (a, b))
    return longer if ends_hold(longer, width) else None


def ends_hold(path: Sequence[Point], width: int) -> bool:
    """Whether a path of several segments has end segments of at least half the width: a shorter one would
    end inside the corner of the band, whose outline would then cross itself."""
    segments = _segments(path)
    if len(segments) < 2:
        return True
    half = -(-width // 2)
    return all(abs(e.x - s.x) + abs(e.y - s.y) > half for s, e in (segments[0], segments[-1]))


def free_path(path: Sequence[Point], width: int, obstacles: Obstacles) -> bool:
    """Whether the band's base along ``path`` keeps every obstacle's gap: each segment's slab, reaching past
    a joint but not past the path's two ends (a terminal's centre, where the band may stop square)."""
    segments = _segments(path)
    last = len(segments) - 1
    return not any(
        obstacles.hits(slab(s, e, width, start=number > 0, end=number < last))
        for number, (s, e) in enumerate(segments)
    )


def extend(
    path: Sequence[Point], width: int, obstacles: Obstacles, ends: Sequence[Terminal] = ()
) -> tuple[Point, ...]:
    """``path`` lengthened past each end by as much as half the width as the slab stays free, and no further
    than the end terminal's copper reaches (``ends``: the terminals at the path's start and end): the square
    ends of the bands of a tree then overlap where they meet at a terminal, and a band ending on a small pad
    covers it whole where there is room, without taking the room beyond the pad."""
    points = list(path)
    half = -(-width // 2)
    for number, (first, second) in enumerate(((0, 1), (-1, -2))):
        a, b = points[first], points[second]
        dx, dy = a.x - b.x, a.y - b.y
        size = abs(dx) + abs(dy)
        if not size:
            continue
        cap = half
        if number < len(ends) and ends[number].copper:
            boxes = [thick_bbox(shape) for shape in ends[number].copper]
            far = max(
                (box.x1 - a.x if dx > 0 else a.x - box.x0)
                if dx
                else (box.y1 - a.y if dy > 0 else a.y - box.y0)
                for box in boxes
            )
            cap = max(0, min(half, far + half // 2))
        # the longest extension up to the cap that stays free (a bisection over nanometres)
        low, high = 0, cap
        while low < high:
            middle = (low + high + 1) // 2
            longer = Point(a.x + dx * middle // size, a.y + dy * middle // size)
            if obstacles.hits(slab(b, longer, width, start=False, end=False)):
                high = middle - 1
            else:
                low = middle
        points[first] = Point(a.x + dx * low // size, a.y + dy * low // size)
    return tuple(points)


SEARCH_MARGIN_NM = 12_000_000
"""How far the grid search of a spine may stray outside the box of its two ends."""


def search(
    a: Terminal,
    b: Terminal,
    *,
    width: int,
    step: int,
    obstacles: Obstacles,
    turn: int,
    bounds: BBox | None = None,
) -> tuple[Point, ...] | None:
    """The cheapest rectilinear path from ``a`` to ``b`` on a grid of ``step`` (plus the lines through both
    ends), or ``None``: Dijkstra's search over the nodes whose square of side ``width`` keeps every
    obstacle's gap (adjacent free nodes, never farther apart than ``width``, cover the band's base between
    them), with ``turn`` added per turn and no turn before a run of ``width`` except at the ends, so the
    path stays a band's spine. Ties go to the smaller point, so the result does not depend on dict order."""
    import heapq

    p, q = a.centre, b.centre
    grid = max(min(step, width), MIN_STEP_NM)
    box = BBox(min(p.x, q.x), min(p.y, q.y), max(p.x, q.x), max(p.y, q.y)).inflate(SEARCH_MARGIN_NM)
    if bounds is not None:
        box = BBox(
            max(box.x0, bounds.x0), max(box.y0, bounds.y0), min(box.x1, bounds.x1), min(box.y1, bounds.y1)
        )
    xs = sorted(
        {p.x + k * grid for k in range(-((p.x - box.x0) // grid), (box.x1 - p.x) // grid + 1)} | {q.x}
    )
    ys = sorted(
        {p.y + k * grid for k in range(-((p.y - box.y0) // grid), (box.y1 - p.y) // grid + 1)} | {q.y}
    )
    half = -(-width // 2)
    # the lines that just clear each obstacle (its box grown by its gap and half the width) find the narrow
    # channels a uniform grid steps over
    lines_x: set[int] = set()
    lines_y: set[int] = set()
    for shape, gap in obstacles.items:
        edge = thick_bbox(shape)
        reach = gap + half + 1
        lines_x |= {edge.x0 - reach, edge.x1 + reach}
        lines_y |= {edge.y0 - reach, edge.y1 + reach}
    xs = sorted(set(xs) | {x for x in lines_x if box.x0 <= x <= box.x1})
    ys = sorted(set(ys) | {y for y in lines_y if box.y0 <= y <= box.y1})
    xi, yi = {x: i for i, x in enumerate(xs)}, {y: j for j, y in enumerate(ys)}
    if p.x not in xi or p.y not in yi or q.x not in xi or q.y not in yi:
        return None
    free: dict[tuple[int, int], bool] = {}

    def is_free(node: tuple[int, int]) -> bool:
        found = free.get(node)
        if found is None:
            x, y = xs[node[0]], ys[node[1]]
            ring = (
                Point(x - half, y - half),
                Point(x + half, y - half),
                Point(x + half, y + half),
                Point(x - half, y + half),
            )
            found = not obstacles.hits(Thick(ring, 0, filled=True))
            free[node] = found
        return found

    start, goal = (xi[p.x], yi[p.y]), (xi[q.x], yi[q.y])
    # the band stops square at a terminal: its two end nodes are judged by the path's slabs afterwards
    free[start] = free[goal] = True
    # state: node, direction (0 none, 1..4), the run so far capped at ``width``
    begin = (start, 0, width)
    best: dict[tuple[tuple[int, int], int, int], int] = {begin: 0}
    before: dict[tuple[tuple[int, int], int, int], tuple[tuple[int, int], int, int]] = {}
    queue: list[tuple[int, tuple[int, int], int, int]] = [(0, start, 0, width)]
    moves = ((1, (1, 0)), (2, (-1, 0)), (3, (0, 1)), (4, (0, -1)))
    reached: tuple[tuple[int, int], int, int] | None = None
    while queue:
        cost, node, direction, run = heapq.heappop(queue)
        state = (node, direction, run)
        if cost > best.get(state, cost):
            continue
        if node == goal:
            reached = state
            break
        for number, (dx, dy) in moves:
            if direction and number != direction and ((number - 1) // 2 == (direction - 1) // 2):
                continue  # no turning back
            turning = direction != 0 and number != direction
            if turning and run < width:
                continue
            nxt = (node[0] + dx, node[1] + dy)
            if not (0 <= nxt[0] < len(xs) and 0 <= nxt[1] < len(ys)) or not is_free(nxt):
                continue
            span = abs(xs[nxt[0]] - xs[node[0]]) + abs(ys[nxt[1]] - ys[node[1]])
            # the first run is an end segment: it may turn at once; after a turn a run must reach ``width``
            grown = width if direction == 0 else min(width, (0 if turning else run) + span)
            new = (nxt, number, grown)
            total = cost + span + (turn if turning else 0)
            if total < best.get(new, total + 1):
                best[new] = total
                before[new] = state
                heapq.heappush(queue, (total, nxt, number, grown))
    if reached is None:
        return None
    nodes = [reached[0]]
    state = reached
    while state in before:
        state = before[state]
        nodes.append(state[0])
    points = [Point(xs[i], ys[j]) for i, j in reversed(nodes)]
    return _clean(points)


def slab(a: Point, b: Point, width: int, *, start: bool = True, end: bool = True) -> Thick:
    """The rectangle a band's base covers along the horizontal or vertical segment ``ab``: ``width`` wide,
    reaching ``width / 2`` past ``a`` (``start``) and past ``b`` (``end``), where a band's corner may lie."""
    half = -(-width // 2)
    dx = (b.x > a.x) - (b.x < a.x)
    dy = (b.y > a.y) - (b.y < a.y)
    lead, tail = (half if start else 0), (half if end else 0)
    p = Point(a.x - dx * lead, a.y - dy * lead)
    q = Point(b.x + dx * tail, b.y + dy * tail)
    x0, x1 = min(p.x, q.x), max(p.x, q.x)
    y0, y1 = min(p.y, q.y), max(p.y, q.y)
    if dx:
        y0, y1 = a.y - half, a.y + half
    else:
        x0, x1 = a.x - half, a.x + half
    return Thick((Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1)), 0, filled=True)


@dataclass(frozen=True, slots=True)
class Edge:
    """A routed edge of a tree: the labels of its two terminals and its path."""

    a: str
    b: str
    path: tuple[Point, ...]


@dataclass(frozen=True, slots=True)
class Tree:
    """The edges of a spine tree in the order they were placed, and the terminal pairs that found no free
    path (each out-of-tree terminal once, with its nearest tree terminal)."""

    edges: tuple[Edge, ...] = ()
    blocked: tuple[tuple[str, str], ...] = ()


def _manhattan(a: Point, b: Point) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


def tree(
    terminals: Sequence[Terminal],
    route_edge: Callable[[Terminal, Terminal], tuple[Point, ...] | None],
    *,
    first: Sequence[tuple[str, str]] = (),
    given: Sequence[Edge] = (),
) -> Tree:
    """The spine tree over ``terminals``: the edges ``first`` (pairs of labels, a hot loop's legs) in their
    order, then Prim's order by Manhattan distance with the labels breaking ties. ``route_edge`` gives the
    path of an edge or ``None``; a terminal that no tree terminal reaches is blocked."""
    by_label = {terminal.label: terminal for terminal in terminals}
    edges: list[Edge] = list(given)
    joined: set[str] = {label for edge in given for label in (edge.a, edge.b) if label in by_label}
    blocked: list[tuple[str, str]] = []
    for label_a, label_b in first:
        if label_a not in by_label or label_b not in by_label or label_a == label_b:
            continue
        if {label_a, label_b} <= joined:
            continue
        path = route_edge(by_label[label_a], by_label[label_b])
        if path is None:
            blocked.append((label_a, label_b))
            continue
        edges.append(Edge(label_a, label_b, path))
        joined |= {label_a, label_b}
    if not joined and terminals:
        joined.add(sorted(by_label)[0])
    while True:
        outside = sorted(label for label in by_label if label not in joined)
        if not outside:
            break
        pairs = sorted(
            (_manhattan(by_label[inner].centre, by_label[outer].centre), outer, inner)
            for outer in outside
            for inner in sorted(joined)
        )
        placed = False
        failed: dict[str, str] = {}
        for _, outer, inner in pairs:
            if outer in failed and outer in joined:
                continue
            path = route_edge(by_label[inner], by_label[outer])
            if path is None:
                failed.setdefault(outer, inner)
                continue
            edges.append(Edge(inner, outer, path))
            joined.add(outer)
            placed = True
            break
        if not placed:
            for outer in outside:
                blocked.append((failed.get(outer, sorted(joined)[0]), outer))
                joined.add(outer)  # reported once; not joined by copper
            break
    return Tree(tuple(edges), tuple(blocked))


def chain(edges: Sequence[Edge]) -> tuple[Point, ...] | None:
    """The one spine of a tree that is a single chain whose joined paths stay a valid band spine (no turn
    back), else ``None``."""
    if not edges:
        return None
    if len(edges) == 1:
        return edges[0].path
    degree: dict[str, int] = {}
    for edge in edges:
        degree[edge.a] = degree.get(edge.a, 0) + 1
        degree[edge.b] = degree.get(edge.b, 0) + 1
    if max(degree.values()) > 2:
        return None
    ends = sorted(label for label, count in degree.items() if count == 1)
    if len(ends) != 2:
        return None
    left = list(edges)
    current = ends[0]
    points: list[Point] = []
    while left:
        edge = next((e for e in left if current in (e.a, e.b)), None)
        if edge is None:
            return None
        left.remove(edge)
        path = list(edge.path) if edge.a == current else list(reversed(edge.path))
        if points and points[-1] != path[0]:
            return None
        points += path if not points else path[1:]
        current = edge.b if edge.a == current else edge.a
    joined = _clean(points)
    return joined if _valid(joined, 0) else None


def longest(edges: Sequence[Edge]) -> Edge | None:
    """The longest edge, by Manhattan length and then by its labels."""
    return max(edges, key=lambda edge: (length(edge.path), edge.a, edge.b), default=None)


__all__ = [
    "Edge",
    "ends_hold",
    "Obstacles",
    "Terminal",
    "Tree",
    "candidates",
    "chain",
    "length",
    "longest",
    "route",
    "slab",
    "tree",
]

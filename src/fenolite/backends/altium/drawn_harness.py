# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A KiCad bus group that crosses a sheet, written as an Altium signal harness (change c0470, task 5.4).

KiCad carries a bus group such as ``UART{TX, RX}`` through a hierarchical label and its sheet pin; on each
sheet a label ``UART.TX`` names a member. Altium joins the members of a port or sheet entry only through a
harness (``docs/formats/altium/connectivity.md``, "Buses and harnesses"). The writer gives the port or
sheet entry the name ``UART`` and a harness type, and draws beside it a block of the generated layout
(``layout.harness_block``): a signal harness line, a connector with one entry per member, and per entry a
wire whose net label ``UART.TX`` joins the member's wires on that sheet by name. The block is placed in
free space: none of its points or lines meets an item of the sheet. The sheet carrier lists the block's
items, and the reader drops them on the way back to KiCad.
"""

# evidence: see drawn

from __future__ import annotations

import heapq
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from fenolite.backends.altium.layout import CONNECTOR_MIN_WIDTH, ENTRY_PITCH, HarnessBlock, text_width
from fenolite.backends.altium.project import unique_id

MIL = 10_000
"""File units per mil."""
STUB = 300
"""The length of a member's wire, in mil."""
STEP = 100
"""The margin around a block, in mil."""
GRID = 50
"""The grid of the search for a harness line, in mil: KiCad's default grid."""
FINE_GRID = 10
"""The grid of a second search, in mil, when the search on ``GRID`` finds no block: Altium's snap grid
(change c0470)."""
BEND = 4
"""The cost of a bend of a harness line, in grid steps."""

Pt = tuple[int, int]
Seg = tuple[Pt, Pt]
Rect = tuple[int, int, int, int]


def harness_type(entries: Sequence[str]) -> str:
    """The harness type of a bus group of ``entries``: one name per set of entries, in their order."""
    return "KiCadBus_" + unique_id("\n".join(entries))


@dataclass(frozen=True, slots=True)
class GroupEnd:
    """The harness of a bus group on one sheet: the KiCad buses that join its ports or sheet entries
    (``network``, written as signal harness lines) and the points a block's line may start from (the
    buses' vertices and the ends' points), in mil from the top-left corner; the group's name and entries,
    its harness type and the locator of its first end. KiCad joins the groups on one bus by member name,
    so a harness has one name per group it joins."""

    starts: tuple[Pt, ...]
    network: tuple[tuple[Pt, ...], ...]
    names: tuple[str, ...]
    entries: tuple[str, ...]
    kind: str
    where: str
    through: bool = False
    """No member of the group joins anything on this sheet: the harness lines join its sheet entries and
    ports alone, and no block is drawn (change c0470)."""


@dataclass(slots=True)
class Occupancy:
    """The electrical points, lines and areas of a sheet's records, in file units from the top-left."""

    points: set[Pt] = field(default_factory=lambda: set[Pt]())
    segments: list[Seg] = field(default_factory=lambda: list[Seg]())
    buses: list[Seg] = field(default_factory=lambda: list[Seg]())
    rects: list[Rect] = field(default_factory=lambda: list[Rect]())


def _value(record: Mapping[str, str], key: str) -> int:
    return int(record.get(key, "0")) * 100_000 + int(record.get(f"{key}_FRAC", "0"))


def occupancy(records: Iterable[Sequence[tuple[str, str]]], height: int) -> Occupancy:
    """What a block must not meet: the ends and lines of wires, buses, harness lines, bus entries, pins and
    ports, the points of net labels, power ports, junctions and no-ERC marks, and the areas of sheet
    symbols and harness connectors. ``height`` is the sheet's height in file units."""
    found = Occupancy()

    def at(fields: Mapping[str, str], name: str = "LOCATION") -> Pt:
        return _value(fields, f"{name}.X"), height - _value(fields, f"{name}.Y")

    for record in records:
        fields = dict(record)
        kind = fields.get("RECORD", "")
        if kind in ("26", "27", "218"):
            count = int(fields.get("LOCATIONCOUNT", "0"))
            points = [
                (_value(fields, f"X{i}"), height - _value(fields, f"Y{i}")) for i in range(1, count + 1)
            ]
            pairs = list(zip(points, points[1:], strict=False))
            if kind == "26":  # a bus joins nothing (H-A-IMP-BUS): only the block's area keeps off it
                found.buses += pairs
                continue
            found.points.update(points)
            found.segments += pairs
        elif kind == "37":
            a, b = at(fields), at(fields, "CORNER")
            found.points.update((a, b))
            found.segments.append((a, b))
        elif kind == "2":
            a = at(fields)
            length = _value(fields, "PINLENGTH")
            turn = int(fields.get("PINCONGLOMERATE", "0")) & 3
            dx, dy = ((length, 0), (0, -length), (-length, 0), (0, length))[turn]
            b = (a[0] + dx, a[1] + dy)
            found.points.update((a, b))
            found.segments.append((a, b))
        elif kind == "18":
            a = at(fields)
            width = _value(fields, "WIDTH")
            # a port reaches from its location rightwards, or upwards when it stands (``STYLE`` 4 to 7)
            vertical = fields.get("STYLE", "0") in ("4", "5", "6", "7")
            other = (a[0], a[1] - width) if vertical else (a[0] + width, a[1])
            found.points.update((a, other))
            found.segments.append((a, other))
        elif kind in ("15", "215"):
            x, y = at(fields)
            found.rects.append((x, y, x + _value(fields, "XSIZE"), y + _value(fields, "YSIZE")))
        elif kind in ("17", "22", "25", "29") and "LOCATION.X" in fields:
            found.points.add(at(fields))
    return found


def _cross(o: Pt, a: Pt, b: Pt) -> int:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def on_segment(p: Pt, a: Pt, b: Pt) -> bool:
    """Whether ``p`` lies on the segment ``ab``, ends included."""
    return _on(p, a, b)


def _on(p: Pt, a: Pt, b: Pt) -> bool:
    return (
        _cross(a, b, p) == 0
        and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
    )


def _meets(a: Pt, b: Pt, c: Pt, d: Pt) -> bool:
    """Whether the segments ``ab`` and ``cd`` share a point."""
    d1, d2, d3, d4 = _cross(c, d, a), _cross(c, d, b), _cross(a, b, c), _cross(a, b, d)
    if ((d1 > 0 > d2) or (d1 < 0 < d2)) and ((d3 > 0 > d4) or (d3 < 0 < d4)):
        return True
    return _on(a, c, d) or _on(b, c, d) or _on(c, a, b) or _on(d, a, b)


def _inside(p: Pt, rect: Rect) -> bool:
    return rect[0] <= p[0] <= rect[2] and rect[1] <= p[1] <= rect[3]


def _hits_rect(a: Pt, b: Pt, rect: Rect) -> bool:
    if _inside(a, rect) or _inside(b, rect):
        return True
    x0, y0, x1, y1 = rect
    corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    return any(_meets(a, b, corners[i], corners[(i + 1) % 4]) for i in range(4))


def _overlap(a: Rect, b: Rect) -> bool:
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


@dataclass(frozen=True, slots=True)
class Placed:
    """A block in mil from the top-left: the connector block, the harness lines before its own (each of
    two points) and per entry its wire and the text of its net label at the wire's far end."""

    block: HarnessBlock
    lines: tuple[tuple[Pt, Pt], ...]
    stubs: tuple[tuple[Pt, Pt, str], ...]


class _Grid:
    """The free nodes and steps of the ``GRID`` lattice of a sheet ``width`` × ``height`` mil: a node is
    free when it lies on no point, line or area of ``occupied``, a step when no point lies inside it. A
    node inside a straight line of ``occupied`` may be crossed at a right angle: Altium joins no crossing
    lines without a junction (``connectivity.md``)."""

    def __init__(
        self, occupied: Occupancy, width: int, height: int, reserved: Iterable[Pt] = (), grid: int = GRID
    ) -> None:
        self.grid = grid
        self.columns, self.rows = width // grid, height // grid
        size = grid * MIL
        self.points: dict[Pt, list[Pt]] = {}
        for point in occupied.points:
            self.points.setdefault((point[0] // size, point[1] // size), []).append(point)
        self.blocked: set[Pt] = set()
        self.blocked_steps: set[tuple[Pt, Pt]] = set()
        self.crossing: dict[Pt, int] = {}
        """Per node inside one straight line, the axis a line may cross it along: 0 across a vertical
        line, 1 across a horizontal one."""
        for px, py in occupied.points:
            rx, ry = px % size, py % size
            if rx == 0 and ry == 0:
                self.blocked.add((px // size, py // size))
            elif rx == 0:
                a, b = (px // size, py // size), (px // size, py // size + 1)
                self.blocked_steps.update(((a, b), (b, a)))
            elif ry == 0:
                a, b = (px // size, py // size), (px // size + 1, py // size)
                self.blocked_steps.update(((a, b), (b, a)))
        for a, b in occupied.segments:
            self._block_segment(a, b, size)
        for x0, y0, x1, y1 in occupied.rects:
            for i in range(-(-x0 // size), x1 // size + 1):
                for j in range(-(-y0 // size), y1 // size + 1):
                    self.blocked.add((i, j))
        self.blocked.update(reserved)

    def _block_segment(self, a: Pt, b: Pt, size: int) -> None:
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        for i in range(-(-x0 // size), x1 // size + 1):
            for j in range(-(-y0 // size), y1 // size + 1):
                node = (i, j)
                if not _on((i * size, j * size), a, b):
                    continue
                axis = 0 if a[0] == b[0] else 1 if a[1] == b[1] else -1
                inner = (i * size, j * size) not in (a, b)
                if axis < 0 or not inner or self.crossing.get(node, axis) != axis:
                    self.blocked.add(node)
                else:
                    self.crossing[node] = axis

    def free(self, node: Pt, axis: int) -> bool:
        """Whether a line moving along ``axis`` (0 across, 1 up or down) may pass ``node``."""
        if not (0 < node[0] < self.columns and 0 < node[1] < self.rows) or node in self.blocked:
            return False
        return self.crossing.get(node, axis) == axis

    def clear(self, a: Pt, b: Pt) -> bool:
        """Whether no occupied point lies on the step from node ``a`` to node ``b``, ends excluded."""
        return (a, b) not in self.blocked_steps


_STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _trace(prev: Mapping[tuple[Pt, int], tuple[Pt, int]], node: Pt, direction: int) -> list[Pt]:
    path = [node]
    cur = (node, direction)
    while cur in prev:
        pnode, pdir = prev[cur]
        path.append(pnode)
        if pdir < 0:
            break
        cur = (pnode, pdir)
    path.reverse()
    return path


def _paths(
    grid: _Grid, starts: Iterable[Pt]
) -> Iterable[tuple[Pt, Pt, Mapping[tuple[Pt, int], tuple[Pt, int]], int]]:
    """The cheapest path of grid nodes from one of ``starts`` to each free node they reach, nearest first;
    a bend costs ``BEND`` steps. Yields ``(previous_node, node, prev_map, direction)`` so ``_trace`` builds
    the full path only when a candidate box is clear."""
    best: dict[tuple[Pt, int], int] = {}
    prev: dict[tuple[Pt, int], tuple[Pt, int]] = {}
    queue: list[tuple[int, int, Pt, int]] = []
    order = 0
    sources = set(starts)
    for start in sorted(sources):
        for direction, (dx, dy) in enumerate(_STEPS):
            node = (start[0] + dx, start[1] + dy)
            if node not in sources and grid.free(node, direction // 2) and grid.clear(start, node):
                key = (node, direction)
                best[key] = 1
                prev[key] = (start, -1)
                heapq.heappush(queue, (1, order, node, direction))
                order += 1
    seen: set[Pt] = set()
    while queue:
        cost, _, node, direction = heapq.heappop(queue)
        if best.get((node, direction), cost + 1) < cost:
            continue
        if node not in seen and node not in grid.crossing:
            seen.add(node)
            yield prev[(node, direction)][0], node, prev, direction
        for turn, (dx, dy) in enumerate(_STEPS):
            if node in grid.crossing and turn != direction:
                continue  # a crossing goes straight on
            following = (node[0] + dx, node[1] + dy)
            if following in sources:
                continue
            if not grid.free(following, turn // 2) or not grid.clear(node, following):
                continue
            step = cost + 1 + (BEND if turn != direction else 0)
            key = (following, turn)
            if best.get(key, step + 1) > step:
                best[key] = step
                prev[key] = (node, direction)
                heapq.heappush(queue, (step, order, following, turn))
                order += 1


def _runs(path: Sequence[Pt], grid: int = GRID) -> list[tuple[Pt, Pt]]:
    """The straight runs of a path of nodes, in mil."""
    points = [(x * grid, y * grid) for x, y in path]
    corners = [points[0]]
    for before, here, after in zip(points, points[1:], points[2:], strict=False):
        if (here[0] - before[0], here[1] - before[1]) != (after[0] - here[0], after[1] - here[1]):
            corners.append(here)
    corners.append(points[-1])
    return list(zip(corners, corners[1:], strict=False))


def place(end: GroupEnd, occupied: Occupancy, width: int, height: int, grid: int = GRID) -> Placed | None:
    """The nearest block of ``end`` in free space on a sheet ``width`` × ``height`` mil, or ``None``: a
    harness line on the ``GRID`` from one of the end's starts that touches nothing of ``occupied`` (file
    units) but its start, ending on the connection point of a connector whose block (connector, member
    wires and labels, with a margin) holds nothing. The placed block is added to ``occupied``. ``grid`` is
    the lattice in mil; ``GRID`` by default."""
    starts = [(x // grid, y // grid) for x, y in end.starts if x % grid == 0 and y % grid == 0]
    if not starts:
        return None
    count = len(end.entries)
    position = ENTRY_PITCH * ((count + 1) // 2)
    longest = max((end.kind, *end.entries), key=len)
    wide = max(CONNECTOR_MIN_WIDTH, text_width(longest))
    label = max(text_width(f"{name}.{entry}") for name in end.names for entry in end.entries)
    tall = ENTRY_PITCH * (count + 1)
    lattice = _Grid(occupied, width, height, grid=grid)
    size = grid * MIL
    for (px, py), (qx, qy), prev, direction in _paths(lattice, starts):
        if py != qy:
            continue  # the line reaches the connector across its edge
        facing = 1 if qx > px else -1
        x, y = qx * grid, qy * grid
        top = y - position
        if facing > 0:
            left = x
            area = (x, top - STEP, x + wide + STUB + label + STEP, top + tall + STEP)
        else:
            left = x - wide
            area = (left - STUB - STEP, top - STEP, max(x, left - STUB + label + STEP), top + tall + STEP)
        if area[0] <= 0 or area[1] <= 0 or area[2] >= width or area[3] >= height:
            continue
        box = (area[0] * MIL, area[1] * MIL, area[2] * MIL, area[3] * MIL)
        if any(_overlap(box, rect) for rect in occupied.rects):
            continue
        if any(_inside(point, box) for point in occupied.points):
            continue
        if any(_hits_rect(c, d, box) for c, d in (*occupied.segments, *occupied.buses)):
            continue
        path = _trace(prev, (qx, qy), direction)
        if any(_inside((i * size, j * size), box) for i, j in path[:-1]):
            continue
        runs = _runs(path, grid)
        edge = left + wide if facing > 0 else left
        reach = STUB if facing > 0 else -STUB
        stubs = tuple(
            ((edge, top + ENTRY_PITCH * k), (edge + reach, top + ENTRY_PITCH * k), entry)
            for k, entry in enumerate(end.entries, start=1)
        )
        block = HarnessBlock(
            end.kind,
            tuple((entry, None) for entry in end.entries),
            left,
            top,
            wide,
            tall,
            position,
            runs[-1],
            (),
            facing < 0,
        )
        occupied.rects.append(box)
        for p, q in runs:
            occupied.segments.append(((p[0] * MIL, p[1] * MIL), (q[0] * MIL, q[1] * MIL)))
            occupied.points.update(((p[0] * MIL, p[1] * MIL), (q[0] * MIL, q[1] * MIL)))
        return Placed(block, tuple(runs[:-1]), stubs)
    return None


def place_all(
    ends: Sequence[GroupEnd], records: Sequence[Sequence[tuple[str, str]]], height: int, size: tuple[int, int]
) -> list[Placed] | GroupEnd:
    """The block of each of ``ends`` on a sheet of ``records`` (``height`` in file units, ``size`` in
    mil), in the order of ``ends``; or the end that finds no free space. An end's own network is a bus
    to it, which its line may touch; another end's network is a line it may not touch. An end that fails
    moves to the front and the blocks are placed again: at most twice per end."""
    order = list(ends)
    failed: GroupEnd = order[0]

    def units(point: Pt) -> Pt:
        return point[0] * MIL, point[1] * MIL

    def segments(end: GroupEnd) -> list[Seg]:
        return [(units(a), units(b)) for line in end.network for a, b in zip(line, line[1:], strict=False)]

    for _ in range(2 * len(order)):
        base = occupancy(records, height)
        found: dict[int, Placed] = {}
        for end in order:
            occupied = Occupancy(
                set(base.points), list(base.segments), [*base.buses, *segments(end)], list(base.rects)
            )
            for other in ends:
                if other is not end:
                    occupied.segments += segments(other)
                    occupied.points.update(units(p) for line in other.network for p in line)
                    occupied.points.update(units(p) for p in other.starts)
            on_grid = any(x % GRID == 0 and y % GRID == 0 for x, y in end.starts)
            placed = place(end, occupied, size[0], size[1]) if on_grid else None
            if placed is None and not on_grid:
                # an end off KiCad's grid, as an Altium sheet entry may lie: Altium's grid (change c0470)
                placed = place(end, occupied, size[0], size[1], FINE_GRID)
            if placed is None:
                failed = end
                break
            found[id(end)] = placed
            base.rects.append(occupied.rects[-1])
            runs = occupied.segments[len(occupied.segments) - len(placed.lines) - 1 :]
            base.segments += runs
            base.points.update(point for run in runs for point in run)
        else:
            return [found[id(end)] for end in ends]
        if failed is order[0]:
            break
        order.remove(failed)
        order.insert(0, failed)
    return failed


__all__ = [
    "FINE_GRID",
    "GroupEnd",
    "Occupancy",
    "Placed",
    "harness_type",
    "occupancy",
    "on_segment",
    "place",
    "place_all",
]

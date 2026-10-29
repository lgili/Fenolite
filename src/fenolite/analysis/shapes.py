# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pour-shape checks of ``fenolite analyze``: necks, tips and slivers of pours, the area of declared
loops and the copper of the two pads of two-pad parts (change c0213; capability board-analyses, "Neck kind",
"Tips and slivers", "Loop kind" and "Balance kind"; user guide ``docs/analyses.md``, "Pour shapes").

The copper is the raster of ``analysis.pour``: the cells of the stored fills of the ``saved_fill`` zone
layers and the kept islands of the ``simulated`` ones. An ``outline`` zone layer is an upper bound, not
copper, and is skipped and counted. The width of a cell is the shortest run of copper cells through it along
the two axes (``n·g``) and the two diagonals (``n·g·√2``, rounded down); a cell is wide when its width
reaches the width of the row, thin otherwise. A run measures a band crossed within 22.5° of its direction,
so a width is high by at most 8 % plus one cell. Everything is integer arithmetic.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import isqrt

from fenolite.analysis.codes import issue
from fenolite.analysis.copper import CopperShape
from fenolite.analysis.pour import MAX_CELLS, Cell, PourCopper, centre, islands_of, ring_cells, window_cells
from fenolite.analysis.practice import PracticeReport, copper_path
from fenolite.analysis.requirements import NeckReq, Requirements
from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry import Thick, thick_bbox
from fenolite.model.design import Design

NECK_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-PRACTICE-POUR", "H-G-SHAPE-NECK"))
LOOP_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-PRACTICE-DECOUPLING", "H-G-SHAPE-LOOP"))
BALANCE_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-PRACTICE-POUR", "H-G-SHAPE-BALANCE"))
SHAPES = ("neck", "tip", "sliver")
_DIRECTIONS = ((1, 0), (0, 1), (1, 1), (1, -1))
_SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))
_AROUND = (*_SIDES, (1, 1), (1, -1), (-1, 1), (-1, -1))


def _level(pour: PourCopper, pads: Sequence[BoardPad] | None, evidence: Evidence) -> Evidence:
    unsure = bool(pour.copper.unsupported) or pads is None
    return Evidence(Level.UNVERIFIED, hypotheses=evidence.hypotheses) if unsure else evidence


def _pad_name(record: BoardPad) -> str:
    holder = record.ref or record.footprint_id
    return f"{holder}-{record.number}" if record.number else holder


def _near(cell: Cell, steps: Iterable[Cell]) -> list[Cell]:
    return [(cell[0] + di, cell[1] + dj) for di, dj in steps]


def _point(cell: Cell, grid: int) -> Point:
    return Point(centre(cell[0], grid), centre(cell[1], grid))


# --- the copper of the pours ----------------------------------------------------------------------------


def pour_cells(pour: PourCopper) -> tuple[dict[tuple[str, str], set[Cell]], int]:
    """The cells of the zone copper per net and layer, and the number of zone layers skipped: ``outline``
    ones, and stored fills whose raster would exceed ``MAX_CELLS``."""
    grid = pour.grid
    found: dict[tuple[str, str], set[Cell]] = defaultdict(set)
    skipped = 0
    for zone in pour.zones:
        if zone.state == "outline":
            skipped += 1
            continue
        if zone.state != "saved_fill":
            continue
        for shape in pour.copper.by_net.get(zone.net, ()):
            if shape.kind != "fill" or shape.entity_id != zone.zone_id or shape.layer != zone.layer:
                continue
            box = thick_bbox(shape.shape)
            if ((box.x1 - box.x0) // grid + 1) * ((box.y1 - box.y0) // grid + 1) > MAX_CELLS:
                skipped += 1
                continue
            found[zone.net, zone.layer] |= ring_cells(shape.shape.core, grid)
    for island in pour.islands:
        found[island.net, island.layer] |= island.cells
    return dict(found), skipped


def cell_widths(cells: set[Cell], grid: int) -> dict[Cell, int]:
    """The width of each cell: its shortest run of cells along the two axes and the two diagonals, in
    nanometres."""
    widths: dict[Cell, int] = {}
    for di, dj in _DIRECTIONS:
        diagonal = di != 0 and dj != 0
        for cell in cells:
            i, j = cell
            if (i - di, j - dj) in cells:
                continue
            run = [cell]
            while (i + len(run) * di, j + len(run) * dj) in cells:
                run.append((i + len(run) * di, j + len(run) * dj))
            count = len(run)
            length = isqrt(2 * count * count * grid * grid) if diagonal else count * grid
            for member in run:
                if length < widths.get(member, length + 1):
                    widths[member] = length
    return widths


def _island8(cells: set[Cell]) -> int:
    """The number of sets of ``cells`` joined by a side or a corner."""
    left = set(cells)
    count = 0
    while left:
        stack = [left.pop()]
        count += 1
        while stack:
            for near in _near(stack.pop(), _AROUND):
                if near in left:
                    left.discard(near)
                    stack.append(near)
    return count


# --- necks, tips and slivers ----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NeckRow:
    """A place where the pour of a net narrows below the width of its ``[[neck]]`` row: ``shape`` is
    ``neck`` (between two wider parts), ``tip`` (a thin end ``extent`` long) or ``sliver`` (a whole island);
    ``at`` the centre of a cell of it, ``width`` its width (for a tip and a sliver, its widest cell);
    ``copper`` the states of the net's zone layers."""

    net: str
    layer: str
    shape: str
    at: Point
    width: int
    limit: int
    requirement: str
    extent: int | None = None
    copper: tuple[str, ...] = ()


def find_shapes(cells: set[Cell], grid: int, width: int) -> list[tuple[str, Cell, int, int | None]]:
    """The necks, tips and slivers of ``cells`` for the width ``width``: ``(shape, cell, width, extent)``."""
    widths = cell_widths(cells, grid)
    found: list[tuple[str, Cell, int, int | None]] = []
    for island in islands_of(cells):
        wide = {cell for cell in island if widths[cell] >= width}
        if not wide:
            first = min(island, key=lambda c: (-widths[c], c))
            found.append(("sliver", first, widths[first], None))
            continue
        found += _necks(island, widths, width)
        thin = island - wide
        for part in islands_of(thin):
            contact = {near for cell in part for near in _near(cell, _AROUND) if near in wide}
            if _island8(contact) != 1:
                continue
            steps = {cell: 1 for cell in part if any(near in contact for near in _near(cell, _AROUND))}
            queue = sorted(steps)
            for cell in queue:
                for near in _near(cell, _AROUND):
                    if near in part and near not in steps:
                        steps[near] = steps[cell] + 1
                        queue.append(near)
            far = max(part, key=lambda c: (steps.get(c, 0), (-c[0], -c[1])))
            extent = steps.get(far, 0) * grid
            if extent >= width:
                found.append(("tip", far, max(widths[cell] for cell in part), extent))
    return found


def _necks(
    island: set[Cell], widths: Mapping[Cell, int], width: int
) -> list[tuple[str, Cell, int, int | None]]:
    """The cells that join two sets holding wide cells, the cells added widest first (ties in cell order)."""
    parent: dict[Cell, Cell] = {}
    wide: dict[Cell, bool] = {}

    def find(cell: Cell) -> Cell:
        while parent[cell] != cell:
            parent[cell] = parent[parent[cell]]
            cell = parent[cell]
        return cell

    found: list[tuple[str, Cell, int, int | None]] = []
    for cell in sorted(island, key=lambda c: (-widths[c], c)):
        parent[cell] = cell
        roots = sorted({find(near) for near in _near(cell, _SIDES) if near in parent})
        held = widths[cell] >= width
        if not held and sum(1 for root in roots if wide[root]) >= 2:
            found.append(("neck", cell, widths[cell], None))
        wide[cell] = held or any(wide[root] for root in roots)
        for root in roots:
            parent[root] = cell
    return found


def analyze_necks(design: Design, *, pour: PourCopper, requirements: Requirements | None) -> PracticeReport:
    """The kind ``necks``: for each net with a zone that a ``[[neck]]`` row selects (the matching row with
    the largest width governs), every neck, tip and sliver of its pour below that width, each one
    ``analysis.neck-narrow`` (error)."""
    rules = requirements.necks if requirements is not None else ()
    issues: list[Issue] = []
    if not rules:
        issues.append(
            issue(
                "analysis.input-missing",
                "no [[neck]] row in the requirements: no width to measure the pours against",
                where="neck",
                hint="add a [[neck]] row with select and min_width_nm",
            )
        )
        return PracticeReport((), tuple(issues), _level(pour, (), NECK_EVIDENCE), {"nets": 0})
    nets = {net.name: net for net in design.circuit.nets}
    zoned = sorted({z.net for z in pour.zones})
    governing: dict[str, NeckReq] = {}
    for rule in rules:
        matched = [name for name in zoned if name in nets and rule.select.matches(nets[name], design.circuit)]
        if not matched:
            issues.append(
                issue(
                    "analysis.requirement-unmatched",
                    f"the [[neck]] row of {rule.select.text()} matches no net with a zone",
                    where=rule.select.text(),
                )
            )
        for name in matched:
            if name not in governing or rule.min_width_nm > governing[name].min_width_nm:
                governing[name] = rule
    cells, skipped = pour_cells(pour)
    rows: list[NeckRow] = []
    for (net, layer), held in sorted(cells.items()):
        rule = governing.get(net)
        if rule is None or not held:
            continue
        states = pour.states_of(net)
        for shape, cell, width, extent in find_shapes(held, pour.grid, rule.min_width_nm):
            at = _point(cell, pour.grid)
            rows.append(
                NeckRow(net, layer, shape, at, width, rule.min_width_nm, rule.select.text(), extent, states)
            )
            issues.append(
                issue(
                    "analysis.neck-narrow",
                    f"a {shape} of the pour of {net} on {layer} at ({at.x}, {at.y}) nm is {width} nm wide, "
                    f"below the {rule.min_width_nm} nm of the [[neck]] row of {rule.select.text()}",
                    where=f"{net}@{layer}",
                    hint="widen the pour there, move the cut-out or keep-out that narrows it, or remove a "
                    "tip or sliver that carries nothing",
                )
            )
    summary = {
        "nets": len(governing),
        **{f"{shape}s": sum(1 for row in rows if row.shape == shape) for shape in SHAPES},
        "skipped": skipped,
    }
    return PracticeReport(tuple(rows), tuple(issues), _level(pour, (), NECK_EVIDENCE), summary)


# --- loops ----------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LoopLeg:
    """A leg of a loop between two of its pads: ``copper`` along the shortest path along copper, or
    ``straight`` (through a part, or across a gap that no copper of one net closes)."""

    start: str
    end: str
    kind: str
    length: int


@dataclass(frozen=True, slots=True)
class LoopRow:
    """A ``[[loop]]`` row measured: the area of the closed path through its pads (``None`` when a pad is
    missing), its legs, the row's largest area, and the area on the baseline board and the change."""

    name: str
    pads: tuple[str, ...]
    area_nm2: int | None
    legs: tuple[LoopLeg, ...] = ()
    limit: int | None = None
    baseline_nm2: int | None = None
    change_nm2: int | None = None


def _straight(a: Point, b: Point) -> int:
    d2 = (a.x - b.x) ** 2 + (a.y - b.y) ** 2
    return (isqrt(4 * d2) + 1) // 2


def loop_areas(
    design: Design, *, pads: Sequence[BoardPad] | None, pour: PourCopper, requirements: Requirements | None
) -> tuple[list[LoopRow], list[Issue]]:
    """The rows of the ``[[loop]]`` rows, without a baseline, and the issues of the pads that are missing."""
    rows: list[LoopRow] = []
    issues: list[Issue] = []
    records = {_pad_name(record): record for record in pads or ()}
    for rule in requirements.loops if requirements is not None else ():
        missing = [name for name in rule.pads if name not in records]
        if missing:
            issues.append(
                issue(
                    "analysis.requirement-unmatched",
                    f"the [[loop]] row {rule.name} names {', '.join(missing)}, which no pad holds",
                    where=rule.name,
                )
            )
            rows.append(LoopRow(rule.name, rule.pads, None, limit=rule.max_area_nm2))
            continue
        legs: list[LoopLeg] = []
        ring: list[Point] = []
        count = len(rule.pads)
        for k in range(count):
            a, b = records[rule.pads[k]], records[rule.pads[(k + 1) % count]]
            found = None
            if a.net is not None and a.net == b.net:
                found = copper_path(design, pour, pads or (), a.net, a.position, b.position)
            if found is None:
                points, length, kind = (a.position, b.position), _straight(a.position, b.position), "straight"
            else:
                (points, length), kind = found, "copper"
            legs.append(LoopLeg(rule.pads[k], rule.pads[(k + 1) % count], kind, length))
            ring += [point for point in points if not ring or point != ring[-1]]
        twice = sum(ring[k].x * ring[(k + 1) % len(ring)].y - ring[(k + 1) % len(ring)].x * ring[k].y
                    for k in range(len(ring)))  # fmt: skip
        rows.append(LoopRow(rule.name, rule.pads, abs(twice) // 2, tuple(legs), rule.max_area_nm2))
    return rows, issues


def analyze_loops(
    design: Design,
    *,
    pads: Sequence[BoardPad] | None,
    pour: PourCopper,
    requirements: Requirements | None,
    baseline: Mapping[str, int | None] | None = None,
) -> PracticeReport:
    """The kind ``loops``: the area of each ``[[loop]]`` row, judged against its ``max_area_nm2``
    (``analysis.loop-area``, error); ``baseline`` maps a loop's name to its area on another board."""
    if not (requirements.loops if requirements is not None else ()):
        found = issue(
            "analysis.input-missing",
            "no [[loop]] row in the requirements: no loop to measure",
            where="loop",
            hint="add a [[loop]] row with name and pads",
        )
        return PracticeReport((), (found,), _level(pour, pads, LOOP_EVIDENCE), {"loops": 0})
    measured, issues = loop_areas(design, pads=pads, pour=pour, requirements=requirements)
    rows: list[LoopRow] = []
    for row in measured:
        before = baseline.get(row.name) if baseline is not None else None
        change = None if before is None or row.area_nm2 is None else row.area_nm2 - before
        rows.append(LoopRow(row.name, row.pads, row.area_nm2, row.legs, row.limit, before, change))
        if row.limit is not None and row.area_nm2 is not None and row.area_nm2 > row.limit:
            issues.append(
                issue(
                    "analysis.loop-area",
                    f"the loop {row.name} through {', '.join(row.pads)} encloses {row.area_nm2} nm², above "
                    f"the {row.limit} nm² of its [[loop]] row",
                    where=row.name,
                    hint="place the loop's parts closer, and route the return under the forward path",
                )
            )
    summary = {"loops": len(rows), "above": sum(1 for i in issues if i.code == "analysis.loop-area")}
    return PracticeReport(tuple(rows), tuple(issues), _level(pour, pads, LOOP_EVIDENCE), summary)


# --- balance --------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BalanceRow:
    """A two-pad SMD part: the copper of each pad's net joined to the pad near it, in square nanometres,
    and the ratio of the larger to the smaller in permille (``None`` when one is 0)."""

    part: str
    pads: tuple[str, str]
    layer: str
    copper_nm2: tuple[int, int]
    ratio_permille: int | None
    copper: tuple[str, ...] = ()


def _pad_area(record: BoardPad, layer: str, pour: PourCopper, shapes: Sequence[CopperShape]) -> int:
    grid = pour.grid
    boxes = [thick_bbox(Thick(e.core, e.width, e.filled)) for e in record.copper if e.layer == layer]
    x0, y0 = min(b.x0 for b in boxes), min(b.y0 for b in boxes)
    x1, y1 = max(b.x1 for b in boxes), max(b.y1 for b in boxes)
    grow = max(x1 - x0, y1 - y0)
    window = (x0 - grow, y0 - grow, x1 + grow, y1 + grow)
    own: set[Cell] = set()
    copper: set[Cell] = set()
    for shape in shapes:
        if shape.layer != layer:
            continue
        held = window_cells(shape.shape, grid, window)
        if shape.kind == "pad" and shape.entity_id == record.pad_id:
            own |= held
        copper |= held
    lo_i, lo_j = -((grid // 2 - window[0]) // grid), -((grid // 2 - window[1]) // grid)
    hi_i, hi_j = (window[2] - grid // 2) // grid, (window[3] - grid // 2) // grid
    for island in pour.islands:
        if island.net == record.net and island.layer == layer:
            copper |= {(i, j) for i, j in island.cells if lo_i <= i <= hi_i and lo_j <= j <= hi_j}
    reached = set(own)
    stack = sorted(own)
    while stack:
        for near in _near(stack.pop(), _SIDES):
            if near in copper and near not in reached:
                reached.add(near)
                stack.append(near)
    return len(reached - own) * grid * grid


def analyze_balance(design: Design, *, pads: Sequence[BoardPad] | None, pour: PourCopper) -> PracticeReport:
    """The kind ``balance``: one row per part with exactly two SMD pads on one layer. Nothing is judged."""
    by_part: dict[str, list[BoardPad]] = defaultdict(list)
    for record in pads or ():
        by_part[record.footprint_id].append(record)
    rows: list[BalanceRow] = []
    for held in by_part.values():
        if len(held) != 2 or any(record.kind != "smd" for record in held):
            continue
        layers = [{entry.layer for entry in record.copper} for record in held]
        if len(layers[0]) != 1 or layers[0] != layers[1]:
            continue
        (layer,) = layers[0]
        first, second = sorted(held, key=_pad_name)
        areas = tuple(
            _pad_area(record, layer, pour, pour.copper.by_net.get(record.net or "", ()))
            if record.net is not None
            else 0
            for record in (first, second)
        )
        small, large = min(areas), max(areas)
        ratio = large * 1000 // small if small else None
        states = tuple(sorted({s for r in (first, second) for s in pour.states_of(r.net or "")}))
        part = first.ref or first.footprint_id
        rows.append(
            BalanceRow(
                part, (_pad_name(first), _pad_name(second)), layer, (areas[0], areas[1]), ratio, states
            )
        )
    rows.sort(key=lambda row: row.part)
    summary = {"parts": len(rows), "one_sided": sum(1 for row in rows if row.ratio_permille is None)}
    return PracticeReport(tuple(rows), (), _level(pour, pads, BALANCE_EVIDENCE), summary)


__all__ = [
    "BALANCE_EVIDENCE",
    "LOOP_EVIDENCE",
    "NECK_EVIDENCE",
    "SHAPES",
    "BalanceRow",
    "LoopLeg",
    "LoopRow",
    "NeckRow",
    "analyze_balance",
    "analyze_loops",
    "analyze_necks",
    "cell_widths",
    "find_shapes",
    "loop_areas",
    "pour_cells",
]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Power paths: the copper a current crosses between two sets of pads, its capacity and its resistance
(capability board-analyses, "Power path current" and "Power path voltage drop"; ``docs/analyses.md``,
"Power paths").

A path names the pads where the current enters and those where it leaves. Its network
(``analysis.network``) keeps the copper on some path between the two sets; the rest carries no direct
current and is not judged. Each active element gets the capacity of the published fit of
``analysis.current`` at its cross-section: a part of a track or arc at its width, a via group as the sum
of its barrels, a fill at its narrowest section (``analysis.section``). An element fails only where the
topology says the whole current flows through it; elsewhere a capacity below the whole current is
undecided, because Fenolite computes no share of the current.

With a resistivity given by the user the resistance is an interval. A part of a track or arc is a
uniform conductor ``ρ·L/(w·t)``; a via group is its barrels in parallel, ``ρ·h/ΣA``; a fill between two
ports lies between ``R_s·ℓ²/A`` and ``R_s·A/w²`` with ``R_s = ρ/t``, ``ℓ`` the shortest path in the fill
between the two port hulls, ``w`` their narrowest section and ``A`` the fill's area outside the hulls
(Fenolite's own derivation, ``H-G-AN-POUR``, from two facts: a solution minimises the Dirichlet
energy, S-0682, and one metric bounds an extremal length from below, S-0681; neither source states the
bounds of a conductor).
The low end is the network at its low values with every fill of more than two ports shorted; the high
end is the network at its high values, or the best single chain. Units: resistivity in picoohm-metres,
lengths in nanometres, resistance in microohms (``1000·ρ·L/(w·t)``), drop in millivolts. Every value is
an integer or a ``Fraction``; each low end is rounded down and each high end up.

Nothing is assumed: resistivity, thickness, plating, rise and depths come from the user or the stack-up.
The capacities and the resistance are estimates (``INFERRED``), not a simulation: ports are ideal
contacts, the vias of a group share the current equally, and no heat spreads from a neck.
"""

from __future__ import annotations

import heapq
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction
from itertools import combinations
from math import ceil, floor

from fenolite.analysis.boundary import BoardBoundary
from fenolite.analysis.codes import issue
from fenolite.analysis.copper import ARC_TOL_NM, copper_layers
from fenolite.analysis.current import SOURCE_OF_FIT, barrel_area_nm2, capacity_ma, in_range, layer_thickness
from fenolite.analysis.deadline import Deadline, passed
from fenolite.analysis.fills import FillRegion, area_outside
from fenolite.analysis.insulation import layer_depths
from fenolite.analysis.network import Element, PathNetwork, RegionUse, path_network
from fenolite.analysis.report import EVIDENCE as ANALYSIS_EVIDENCE
from fenolite.analysis.report import LOWERING, Measure, mm, sorted_issues
from fenolite.analysis.requirements import Requirements
from fenolite.analysis.section import Port, Section, narrowest_section, port_hull
from fenolite.analysis.surface import Terminal, surface_distance
from fenolite.backends.base import BoardPad
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.geometry import Thick, thick_gap_floor, thick_touch
from fenolite.model.design import Design
from fenolite.model.findings import Findings

EVIDENCE = Evidence(
    Level.INFERRED, hypotheses=("H-G-AN-NECKFIT", "H-G-AN-NETWORK", "H-G-AN-POUR", "H-G-AN-SECTION")
)
"""``INFERRED`` until an independent tool computes the same quantities: the grid cut, the
finite-difference solution of the tests and the KiCad probes do not raise it."""
PATH_LIMIT = 400
"""A fill with more boundary points than this gets the plan gap of its two port hulls as ``ℓ`` instead of
the shortest path inside it: the path search visits every pair of boundary points. The gap is never
longer than the path, so the low end of the resistance stays a lower bound."""
PathPads = tuple[Sequence[str], Sequence[str]]
_Bounds = tuple[Fraction, Fraction | None]


@dataclass(frozen=True, slots=True)
class Interval:
    """``low ≤ value ≤ high`` in whole units; ``high`` is ``None`` when no upper bound is known."""

    low: int
    high: int | None


@dataclass(frozen=True, slots=True)
class PathElement:
    """One active element of a path: ``kind`` is ``track``, ``arc``, ``via-group`` or ``fill``; ``layer``
    its layer, or the two layers of a via group joined by ``/``. ``area_nm2`` is its cross-section, for a
    fill its narrowest ``section`` (between the two ``ports``) times the copper thickness. A value whose
    input is missing is ``None``. ``hull_free`` is false when the section is only an upper bound."""

    kind: str
    where: str
    layer: str
    series: bool
    area_nm2: int | None = None
    section: Measure | None = None
    ports: tuple[str, ...] = ()
    capacity_ma: int | None = None
    in_range: bool | None = None
    resistance_uohm: Interval | None = None
    hull_free: bool = True


@dataclass(frozen=True, slots=True)
class PathRow:
    """One power path. ``milliamps`` and ``drop_mv`` are ``None`` for a path that is only measured;
    ``resistance_uohm`` is ``None`` without a resistivity. ``complete`` is false when a deadline left a
    fill of the path with its coarse bounds (change c0503): its intervals are sound but wider."""

    net: str
    start: tuple[str, ...]
    end: tuple[str, ...]
    milliamps: int | None
    temp_rise_mk: int | None
    elements: tuple[PathElement, ...] = ()
    resistance_uohm: Interval | None = None
    drop_mv: Interval | None = None
    complete: bool = True


@dataclass(frozen=True, slots=True)
class PowerReport:
    """Rows sorted by net, start and end; issues by code, ``where`` and message."""

    rows: tuple[PathRow, ...] = ()
    issues: tuple[Issue, ...] = ()
    summary: Mapping[str, object] = field(default_factory=lambda: {})
    evidence: Evidence = field(default_factory=lambda: Evidence.combine(ANALYSIS_EVIDENCE, EVIDENCE))

    def findings(self) -> Findings:
        """The issues as a findings layer, for a caller that attaches them to ``Design.findings``."""
        return Findings(issues=self.issues)


# --- a fill between two ports ---------------------------------------------------------------------


def _between_hulls(region: FillRegion, a: Port, b: Port, arc_tol: int) -> int:
    """A lower bound of the shortest path inside the fill between the two port hulls: the surface search
    on the fill as a one-face board, else the gap of the hulls in plan view."""
    hull_a = Thick(port_hull(a, arc_tol=arc_tol), 0, filled=True)
    hull_b = Thick(port_hull(b, arc_tol=arc_tol), 0, filled=True)
    if thick_touch(hull_a, hull_b):
        return 0
    gap = thick_gap_floor(hull_a, hull_b)
    if len(region.outer) + sum(len(hole) for hole in region.holes) > PATH_LIMIT:
        return gap
    face = BoardBoundary(region.outer, region.holes, None, 0, "model")
    path = surface_distance([Terminal(hull_a, "top")], [Terminal(hull_b, "top")], face)
    return gap if path is None else max(gap, path.length - path.band)


def _bounds(
    region: FillRegion, a: Port, b: Port, sheet: Fraction, arc_tol: int, section: Section | None = None
) -> _Bounds:
    """The exact bounds, in microohms, of the resistance of the fill between two ports."""
    hulls = (port_hull(a, arc_tol=arc_tol), port_hull(b, arc_tol=arc_tol))
    if len(hulls[0]) < 3 or len(hulls[1]) < 3:
        return Fraction(0), None
    if section is None:
        section = narrowest_section(region, a, b, arc_tol=arc_tol)
    area = area_outside(region, hulls)
    length = max(0, _between_hulls(region, a, b, arc_tol) - a.band - b.band)
    low = sheet * length * length / area if area > 0 else Fraction(0)
    width = section.measure.low
    high = sheet * area / (width * width) if width > 0 and section.hull_free and area > 0 else None
    return low, high


def _coarse_bounds(
    region: FillRegion, a: Port, b: Port, sheet: Fraction, arc_tol: int, section: Section | None
) -> _Bounds:
    """The bounds of stage 0 and 1 (design D2 of change c0503): ``ℓ₀``, the gap of the two port hulls, is
    at most the path inside the fill, and ``A₀``, the whole area of the fill, at least the area outside the
    hulls, so ``R_s·ℓ₀²/A₀`` is at most the exact low end and ``R_s·A₀/w²`` at least the exact high end.
    Without ``section`` (stage 0) the high end is ``None``."""
    hulls = (port_hull(a, arc_tol=arc_tol), port_hull(b, arc_tol=arc_tol))
    if len(hulls[0]) < 3 or len(hulls[1]) < 3:
        return Fraction(0), None
    hull_a, hull_b = Thick(hulls[0], 0, filled=True), Thick(hulls[1], 0, filled=True)
    gap = 0 if thick_touch(hull_a, hull_b) else thick_gap_floor(hull_a, hull_b)
    length = max(0, gap - a.band - b.band)
    area = Fraction(region.area2, 2)
    low = sheet * length * length / area if area > 0 else Fraction(0)
    if section is None:
        return low, None
    width = section.measure.low
    high = sheet * area / (width * width) if width > 0 and section.hull_free and area > 0 else None
    return low, high


def stage_bounds(
    region: FillRegion, a: Port, b: Port, *, sheet_uohm: Fraction | int, stage: int, arc_tol: int = ARC_TOL_NM
) -> Interval:
    """The interval of ``region_bounds`` at ``stage`` 0, 1 or 2 of design D2 of change c0503; stage 2 is
    ``region_bounds`` itself, and each stage's interval contains the next one's."""
    sheet = Fraction(sheet_uohm)
    if stage >= 2:
        low, high = _bounds(region, a, b, sheet, arc_tol)
    else:
        section = narrowest_section(region, a, b, arc_tol=arc_tol) if stage == 1 else None
        low, high = _coarse_bounds(region, a, b, sheet, arc_tol, section)
    return Interval(floor(low), None if high is None else ceil(high))


def region_bounds(
    region: FillRegion, a: Port, b: Port, *, sheet_uohm: Fraction | int, arc_tol: int = ARC_TOL_NM
) -> Interval:
    """The interval of the resistance of ``region`` between two ports for a sheet resistance of
    ``sheet_uohm`` microohms per square: ``R_s·ℓ²/A`` rounded down and ``R_s·A/w²`` rounded up
    (``H-G-AN-POUR``). ``high`` is ``None`` when the section is 0 or only a bound."""
    low, high = _bounds(region, a, b, Fraction(sheet_uohm), arc_tol)
    return Interval(floor(low), None if high is None else ceil(high))


# --- the network as resistors ---------------------------------------------------------------------

_Edge = tuple[int, int, Fraction]


def _solve(edges: Sequence[_Edge], sources: Sequence[int], sinks: Sequence[int]) -> Fraction | None:
    """The exact resistance between two sets of nodes of a network of resistors: nodes joined by a
    resistance of 0 are merged, then every other node is removed by the star-mesh transformation, the
    node of fewest neighbours first. ``None`` when the two sets are not joined."""
    parent: dict[int, int] = {}

    def find(node: int) -> int:
        root = node
        while parent.setdefault(root, root) != root:
            root = parent[root]
        while parent[node] != root:
            parent[node], node = root, parent[node]
        return root

    for node in sources[1:]:
        parent[find(node)] = find(sources[0])
    for node in sinks[1:]:
        parent[find(node)] = find(sinks[0])
    for first, second, value in edges:
        if value == 0:
            parent[find(first)] = find(second)
    source, sink = find(sources[0]), find(sinks[0])
    if source == sink:
        return Fraction(0)
    conductance: dict[int, dict[int, Fraction]] = {source: {}, sink: {}}
    for first, second, value in edges:
        a, b = find(first), find(second)
        if a == b:
            continue
        conductance.setdefault(a, {})[b] = conductance.setdefault(a, {}).get(b, Fraction(0)) + 1 / value
        conductance.setdefault(b, {})[a] = conductance.setdefault(b, {}).get(a, Fraction(0)) + 1 / value
    while len(conductance) > 2:
        node = min(
            (n for n in conductance if n not in (source, sink)), key=lambda n: (len(conductance[n]), n)
        )
        links = conductance.pop(node)
        total = sum(links.values(), Fraction(0))
        for other in links:
            del conductance[other][node]
        for (a, g_a), (b, g_b) in combinations(sorted(links.items()), 2):
            extra = g_a * g_b / total
            conductance[a][b] = conductance[a].get(b, Fraction(0)) + extra
            conductance[b][a] = conductance[b].get(a, Fraction(0)) + extra
    joined = conductance[source].get(sink)
    return None if not joined else 1 / joined


def _chain(edges: Sequence[_Edge], sources: Sequence[int], sinks: Sequence[int]) -> Fraction | None:
    """The smallest sum of resistances over the chains from a source to a sink."""
    links: dict[int, list[tuple[int, Fraction]]] = {}
    for first, second, value in edges:
        links.setdefault(first, []).append((second, value))
        links.setdefault(second, []).append((first, value))
    goal = set(sinks)
    best: dict[int, Fraction] = dict.fromkeys(sources, Fraction(0))
    heap: list[tuple[Fraction, int]] = [(Fraction(0), node) for node in sources]
    heapq.heapify(heap)
    while heap:
        here, node = heapq.heappop(heap)
        if node in goal:
            return here
        if here > best.get(node, here):
            continue
        for other, value in links.get(node, ()):
            total = here + value
            if other not in best or total < best[other]:
                best[other] = total
                heapq.heappush(heap, (total, other))
    return None


# --- one path -------------------------------------------------------------------------------------


@dataclass(slots=True)
class _Inputs:
    design: Design
    pads: Sequence[BoardPad] | None
    copper_thickness: Mapping[str, Nm] | None
    via_plating: Nm | None
    resistivity: int | None
    arc_tol: int
    missing: Counter[str]
    issues: list[Issue]


@dataclass(slots=True)
class _Region:
    """An active fill of a path and the stage its bounds reached (design D2 of change c0503): 0 with the
    coarse ``ℓ₀`` and ``A₀``, 1 with the narrowest sections too, 2 with the exact ``ℓ`` and ``A``."""

    use: RegionUse
    element: Element
    thickness: Nm | None
    external: bool
    stage: int = -1
    made: PathElement | None = None
    bounds: dict[tuple[int, int], _Bounds] = field(default_factory=lambda: {})
    sections: dict[tuple[int, int], Section] | None = None
    best: tuple[Section, int, int] | None = None
    missing: Counter[str] = field(default_factory=lambda: Counter[str]())

    def width(self) -> Fraction | None:
        """The widest interval of its pairs of ports; ``None`` when one has no high end."""
        widths = [high - low for low, high in self.bounds.values() if high is not None]
        if len(widths) < len(self.bounds) or not widths:
            return None
        return max(widths)


def _sections(region: _Region, arc_tol: int) -> None:
    use = region.use
    active = use.active_ports
    best: tuple[Section, int, int] | None = None
    sections: dict[tuple[int, int], Section] = {}
    for i, j in combinations(active, 2):
        limit = None if best is None or len(active) == 2 else best[0].measure.low + 1
        found = narrowest_section(use.region, use.ports[i], use.ports[j], arc_tol=arc_tol, limit=limit)
        if found.measure.bounded:
            continue
        sections[(i, j)] = found
        if best is None or found.measure.low < best[0].measure.low:
            best = (found, i, j)
    region.sections, region.best = sections, best


def _refine(region: _Region, stage: int, rise: int | None, given: _Inputs) -> None:
    """Bring ``region`` to ``stage``: its element and the bounds of its resistance between each two active
    ports."""
    use = region.use
    if stage >= 1 and region.sections is None:
        _sections(region, given.arc_tol)
    sheet = None
    if given.resistivity is not None and region.thickness is not None:
        sheet = Fraction(1000 * given.resistivity, region.thickness)
    if sheet is None and stage >= 1:
        stage = 2  # nothing more to compute: no resistance without a sheet resistance
    sections = region.sections or {}
    bounds: dict[tuple[int, int], _Bounds] = {}
    if sheet is not None:
        for i, j in combinations(use.active_ports, 2):
            a, b = use.ports[i], use.ports[j]
            if stage >= 2:
                bounds[(i, j)] = _bounds(use.region, a, b, sheet, given.arc_tol, sections.get((i, j)))
            else:
                section = sections.get((i, j)) if stage == 1 else None
                bounds[(i, j)] = _coarse_bounds(use.region, a, b, sheet, given.arc_tol, section)
    region.stage, region.bounds = stage, bounds
    region.missing = Counter()
    element = region.element
    if region.best is None:
        region.made = PathElement("fill", element.where, element.layer, element.series)
        return
    section, i, j = region.best
    area = capacity = within = None
    if region.thickness is None:
        region.missing["copper thickness"] += 1
    else:
        area = section.measure.low * region.thickness
        if rise is None:
            region.missing["temperature rise"] += 1
        elif area > 0:
            capacity = capacity_ma(area, rise, external=region.external)
            within = in_range(section.measure.low, rise, capacity, external=region.external)
    resistance = None
    if len(use.active_ports) == 2 and (i, j) in bounds:
        low, high = bounds[(i, j)]
        resistance = Interval(floor(low), None if high is None else ceil(high))
    region.made = PathElement(
        "fill",
        element.where,
        element.layer,
        element.series,
        area,
        section.measure,
        (use.ports[i].where, use.ports[j].where),
        capacity,
        within,
        resistance,
        section.hull_free,
    )


@dataclass(slots=True)
class _Request:
    start: tuple[str, ...]
    end: tuple[str, ...]
    milliamps: int | None
    rise: int | None
    drop: int | None
    network: PathNetwork | None = None
    regions: dict[int, _Region] = field(default_factory=lambda: {})


def _prepare(given: _Inputs, request: _Request) -> None:
    """The network of a path and its active fills, none of them computed yet."""
    design = given.design
    network = path_network(
        design, pads=given.pads, start=request.start, end=request.end, arc_tol=given.arc_tol
    )
    given.issues += network.issues
    request.network = network
    board = design.board
    if board is None:
        return
    layers = copper_layers(board)
    outer = {layers[0], layers[-1]} if layers else set[str]()
    uses = iter(network.regions)
    for index, element in enumerate(network.elements):
        use = next(uses) if element.kind == "fill" else None
        if use is None or not element.active:
            continue
        thickness = layer_thickness(board, element.layer, given.copper_thickness)
        request.regions[index] = _Region(use, element, thickness, element.layer in outer)


def _row(given: _Inputs, request: _Request) -> PathRow:
    """The row of a prepared path from its fills at the stage they reached."""
    start, end, milliamps, rise, drop = (
        request.start, request.end, request.milliamps, request.rise, request.drop
    )  # fmt: skip
    design = given.design
    network = request.network
    assert network is not None
    complete = all(region.stage >= 2 for region in request.regions.values())
    board = design.board
    names = "/".join((",".join(start), ",".join(end)))
    if board is None or not network.elements:
        return PathRow(network.net, tuple(start), tuple(end), milliamps, rise, complete=complete)
    layers = copper_layers(board)
    outer = {layers[0], layers[-1]} if layers else set[str]()
    vias = {via.id: via for via in board.vias}
    depths = layer_depths(board) if given.resistivity is not None else None
    rho = given.resistivity
    made: list[PathElement] = []
    low_edges: list[_Edge] = []
    high_edges: list[_Edge] = []  # every edge of the network at its high value, when all have one
    chain_edges: list[_Edge] = []  # the edges with a high value, a fill by each pair of its ports
    whole = True  # every active element has a high value and no fill has more than two active ports
    groups = iter(network.groups)
    uses = iter(network.regions)
    for index, element in enumerate(network.elements):
        group = next(groups) if element.kind == "via-group" else None
        use = next(uses) if element.kind == "fill" else None
        if not element.active:
            continue
        low: Fraction | None = None
        high: Fraction | None = None
        if element.kind in ("track", "arc"):
            thickness = layer_thickness(board, element.layer, given.copper_thickness)
            width = element.width or 0
            area = capacity = within = None
            if thickness is None or width <= 0:
                given.missing["copper thickness"] += 1
            else:
                area = width * thickness
                if rise is None:
                    given.missing["temperature rise"] += 1
                else:
                    external = element.layer in outer
                    capacity = capacity_ma(area, rise, external=external)
                    within = in_range(width, rise, capacity, external=external)
                if rho is not None and element.length_nm is not None:
                    low = Fraction(1000 * rho * element.length_nm, area)
                    high = Fraction(1000 * rho * (element.length_nm + element.length_band), area)
            resistance = None if low is None or high is None else Interval(floor(low), ceil(high))
            made.append(
                PathElement(
                    element.kind, element.where, element.layer, element.series, area, None, (), capacity,
                    within, resistance,
                )
            )  # fmt: skip
            ends = element.ends
        elif group is not None:
            area = capacity = within = None
            drills = [vias[via_id].drill for via_id in group.vias if via_id in vias]
            if given.via_plating is None or not drills or min(drills) <= 0:
                given.missing["via plating"] += 1
            else:
                areas = [barrel_area_nm2(drill, given.via_plating) for drill in drills]
                area = sum(areas)
                if rise is None:
                    given.missing["temperature rise"] += 1
                else:
                    each = [capacity_ma(one, rise, external=True) for one in areas]
                    capacity = sum(each)
                    within = all(in_range(None, rise, one, external=True) for one in each)
                if rho is not None and len(element.ends) == 2:
                    first, last = group.layers[0], group.layers[-1]
                    if depths is None or first not in depths or last not in depths:
                        given.missing["stack-up"] += 1
                    else:
                        middles = [Fraction(depths[name][0] + depths[name][1], 2) for name in (first, last)]
                        low = high = 1000 * rho * abs(middles[1] - middles[0]) / area
            resistance = None if low is None or high is None else Interval(floor(low), ceil(high))
            made.append(
                PathElement(
                    "via-group", element.where, element.layer, element.series, area, None, (), capacity,
                    within, resistance,
                )
            )  # fmt: skip
            ends = element.ends
        else:
            assert use is not None
            region = request.regions[index]
            assert region.made is not None
            given.missing.update(region.missing)
            bounds = region.bounds
            made.append(region.made)
            active = use.active_ports
            nodes = [use.nodes[index] for index in active]
            if len(active) > 2 or not bounds:
                whole = whole and len(active) <= 2 and bool(bounds)
                low_edges += [(nodes[0], node, Fraction(0)) for node in nodes[1:]]
            for (i, j), (pair_low, pair_high) in bounds.items():
                if len(active) == 2:
                    low_edges.append((use.nodes[i], use.nodes[j], pair_low))
                    if pair_high is None:
                        whole = False
                    else:
                        high_edges.append((use.nodes[i], use.nodes[j], pair_high))
                if pair_high is not None:
                    chain_edges.append((use.nodes[i], use.nodes[j], pair_high))
            continue
        # a part of a track or arc, or a via group: one resistor between its joints
        nodes = list(dict.fromkeys(ends))
        if len(nodes) < 2:
            continue
        if low is None or high is None or len(nodes) > 2:
            whole = False
            low_edges += [(nodes[0], node, Fraction(0)) for node in nodes[1:]]
        else:
            low_edges.append((nodes[0], nodes[1], low))
            high_edges.append((nodes[0], nodes[1], high))
            chain_edges.append((nodes[0], nodes[1], high))
    made.sort(key=lambda item: (item.layer, item.kind, item.where))

    resistance_row: Interval | None = None
    drop_row: Interval | None = None
    if rho is not None and any(element.active for element in network.elements):
        low_value = _solve(low_edges, network.start_nodes, network.end_nodes)
        high_value = _solve(high_edges, network.start_nodes, network.end_nodes) if whole else None
        if high_value is None:
            high_value = _chain(chain_edges, network.start_nodes, network.end_nodes)
        resistance_row = Interval(
            floor(low_value) if low_value is not None else 0, None if high_value is None else ceil(high_value)
        )
        if milliamps is not None:
            high_drop = resistance_row.high
            drop_row = Interval(
                milliamps * resistance_row.low // 1_000_000,
                None if high_drop is None else -(-milliamps * high_drop // 1_000_000),
            )
    if milliamps is not None:
        given.issues += _judge(made, network, names, milliamps, rise)
        if drop is not None and drop_row is not None:
            if drop_row.low > drop:
                given.issues.append(
                    issue(
                        "analysis.drop-above",
                        f"power path {names} on net {network.net} drops at least {drop_row.low} mV at "
                        f"{milliamps} mA; {drop} mV is the largest drop required",
                        where=names,
                    )
                )
            elif drop_row.high is None or drop < drop_row.high:
                upper = "no upper bound is known" if drop_row.high is None else f"at most {drop_row.high} mV"
                given.issues.append(
                    issue(
                        "analysis.drop-undecided",
                        f"power path {names} on net {network.net} drops at least {drop_row.low} mV at "
                        f"{milliamps} mA and {upper}; {drop} mV is required: the interval does not decide",
                        where=names,
                    )
                )
    outside = sum(1 for element in made if element.in_range is False)
    if outside:
        given.issues.append(
            issue(
                "analysis.fit-out-of-range",
                f"{outside} element(s) of power path {names} lie outside the range the source states for the "
                "fit (width, temperature rise or current); their capacity is an extrapolation",
                where=names,
            )
        )
    return PathRow(
        network.net,
        tuple(start),
        tuple(end),
        milliamps,
        rise,
        tuple(made),
        resistance_row,
        drop_row,
        complete,
    )


def _judge(
    elements: Sequence[PathElement], network: PathNetwork, names: str, milliamps: int, rise: int | None
) -> list[Issue]:
    """An element below the current fails when it carries the whole current, and is undecided otherwise."""
    two_ports = {use.region.where: len(use.active_ports) == 2 for use in network.regions}
    found: list[Issue] = []
    for element in elements:
        if element.capacity_ma is None or element.capacity_ma >= milliamps:
            continue
        text = (
            f"{element.kind} {element.where} of power path {names} on {element.layer} carries "
            f"{element.capacity_ma} mA at a rise of {rise} mK by the fit, below the {milliamps} mA required"
        )
        if element.section is not None and len(element.section.points) >= 2:
            first, last = element.section.points[0], element.section.points[-1]
            text += (
                f"; its narrowest section, {mm(element.section.low)} mm, runs from "
                f"({mm(first.x)}, {mm(first.y)}) mm to ({mm(last.x)}, {mm(last.y)}) mm"
            )
        fill = element.kind == "fill"
        carries_all = element.series and (
            not fill or (two_ports.get(element.where, False) and element.hull_free)
        )
        if carries_all:
            found.append(issue("analysis.path-exceeded", text, where=element.where))
        elif fill and not element.hull_free:
            why = "; its section is only an upper bound, because a hole lies inside the hull of a port"
            found.append(issue("analysis.path-undecided", text + why, where=element.where))
        else:
            why = "; its share of the current is not computed, so the measure does not decide"
            found.append(issue("analysis.path-undecided", text + why, where=element.where))
    return found


def _staged(given: _Inputs, requests: Sequence[_Request], deadline: Deadline) -> None:
    """Every fill at stage 0, then at stage 1 while time remains, then at stage 2: first the fills of the
    rows whose judgment stage 1 leaves undecided, the widest interval first, then by ``where``."""
    regions = [(request, region) for request in requests for region in request.regions.values()]
    for request, region in regions:
        _refine(region, 0, request.rise, given)
    for request, region in regions:
        if passed(deadline):
            return
        _refine(region, 1, request.rise, given)
    undecided: set[int] = set()
    for number, request in enumerate(requests):
        scratch = replace(given, missing=Counter(), issues=[])
        _row(scratch, request)
        if any(found.code.endswith("-undecided") for found in scratch.issues):
            undecided.add(number)
    order = sorted(
        (
            (number not in undecided, width is None, -(width or 0), region.element.where, number, k)
            for number, request in enumerate(requests)
            for k, region in request.regions.items()
            if region.stage < 2
            for width in (region.width(),)
        ),
        key=lambda item: item[:4] + (item[4], item[5]),
    )
    for _, _, _, _, number, k in order:
        if passed(deadline):
            return
        request = requests[number]
        _refine(request.regions[k], 2, request.rise, given)


def _cut(requests: Sequence[_Request]) -> Issue | None:
    """The ``analysis.deadline`` warning naming the rows and the fills left below stage 2."""
    coarse = [
        (request, region) for request in requests for region in request.regions.values() if region.stage < 2
    ]
    if not coarse:
        return None
    rows = sorted({"/".join((",".join(request.start), ",".join(request.end))) for request, _ in coarse})
    names = sorted({f"{region.element.where} (stage {region.stage})" for _, region in coarse})
    return issue(
        "analysis.deadline",
        f"the deadline passed before the power paths {', '.join(rows)} were refined: the fills "
        f"{', '.join(names)} keep their coarse bounds, which are sound but wider",
        where="power",
        hint="run again with a longer --deadline, or --deadline 0 for none",
    )


def analyze_power(
    design: Design,
    *,
    pads: Sequence[BoardPad] | None,
    paths: Sequence[PathPads] = (),
    requirements: Requirements | None = None,
    temp_rise_mk: int | None = None,
    copper_thickness: Mapping[str, Nm] | None = None,
    via_plating: Nm | None = None,
    resistivity_pohm_m: int | None = None,
    arc_tol: int = ARC_TOL_NM,
    deadline: Deadline | None = None,
) -> PowerReport:
    """One row per power path: each pair of ``paths``, measured only, and each ``[[path]]`` row of
    ``requirements``, measured and judged against its current and its largest drop. With ``deadline``
    (change c0503) the fills are bounded coarse first and refined while time remains; a row left with a
    coarse fill has ``complete`` false and the report one ``analysis.deadline`` warning."""
    given = _Inputs(design, pads, copper_thickness, via_plating, resistivity_pohm_m, arc_tol, Counter(), [])
    requests = [_Request(tuple(start), tuple(end), None, temp_rise_mk, None) for start, end in paths]
    wants_drop = False
    for row in requirements.paths if requirements is not None else ():
        wants_drop = wants_drop or row.drop_mv is not None
        requests.append(_Request(row.start, row.end, row.milliamps, row.temp_rise_mk, row.drop_mv))
    for request in requests:
        _prepare(given, request)
    if deadline is None:
        for request in requests:
            for region in request.regions.values():
                _refine(region, 2, request.rise, given)
    else:
        _staged(given, requests, deadline)
    rows = [_row(given, request) for request in requests]
    cut = _cut(requests)
    if cut:
        given.issues.append(cut)
    rows.sort(key=lambda row: (row.net, row.start, row.end, row.milliamps or 0))
    issues = list(dict.fromkeys(given.issues))
    for name, count in sorted(given.missing.items()):
        issues.append(
            issue(
                "analysis.input-missing",
                f"{name} not given: {count} element(s) of the power paths have no "
                + ("resistance" if name == "stack-up" else "capacity")
                + (
                    " and no resistance"
                    if name == "copper thickness" and resistivity_pohm_m is not None
                    else ""
                ),
                where=name,
                hint="Fenolite assumes no value; give it as an option or in the stack-up of the board",
            )
        )
    if resistivity_pohm_m is None and wants_drop:
        issues.append(
            issue(
                "analysis.input-missing",
                "resistivity not given: no path has a resistance, and no voltage drop is judged",
                where="resistivity",
                hint="Fenolite assumes no resistivity; give the one of your copper at your temperature",
            )
        )
    ordered = sorted_issues(issues)
    combined = Evidence.combine(ANALYSIS_EVIDENCE, EVIDENCE)
    if any(found.code in (*LOWERING, "analysis.path-unmatched") for found in ordered):
        combined = Evidence(Level.UNVERIFIED, hypotheses=combined.hypotheses)
    summary: dict[str, object] = {
        "paths": len(rows),
        "elements": sum(len(row.elements) for row in rows),
        "missing": dict(sorted(given.missing.items())),
        "fit": SOURCE_OF_FIT,
    }
    return PowerReport(tuple(rows), ordered, summary, combined)


__all__ = [
    "EVIDENCE",
    "PATH_LIMIT",
    "Interval",
    "PathElement",
    "PathRow",
    "PowerReport",
    "analyze_power",
    "region_bounds",
    "stage_bounds",
]

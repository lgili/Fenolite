# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The share of a power path's current in each of its tracks, arcs, fills and vias, from a resistive solve
on a raster of the copper (change c0213; capability board-analyses, "Current split"; user guide
``docs/analyses.md``, "Power paths").

The cells of the net's copper on every layer (the raster of ``analysis.pour``, with every zone layer in its
copper state) are the nodes of a network of resistors. The cells of each pad and each via on a layer form one
node, an ideal contact as a joint of the power network is; contacts that share or touch cells are one node,
and a through-hole pad's layers too. Two neighbour cells are joined by the conductance ``t/ρ`` of a square of
copper of the layer's thickness, doubled between a contact and a free cell, because the contact's edge lies at
the face of its cell, half a step from the free cell's centre. The layers of a via are joined pairwise down
its span by ``A/(ρ·h)``: ``A`` the barrel's area for the plating given, ``h`` the depth between the middles of
the two layers in the stack-up. The resistivity cancels from the shares.

The start pads are held at ``SCALE`` and the end pads at 0; the other potentials are found by successive
over-relaxation in integers until none moves by more than ``TOLERANCE`` in a pass, or ``iterations`` passes.
A via carries the flow through its barrel; a track, an arc or a fill carries the net inflow into the cells it
alone covers, and its share is that current over the path's. With a resistivity the path's resistance is
``ρ·SCALE/I``, compared with the interval that ``analysis.power`` gives on the same board. ``power`` counts a
track from the centre of its pads, while the solve holds each pad at one potential, so on a path of tracks
the solve may lie below the interval by the copper inside the pads. It is an estimate on a raster, not a
field simulation: the copper is placed to within one cell.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from operator import mul

from fenolite.analysis.codes import issue
from fenolite.analysis.copper import copper_layers
from fenolite.analysis.current import barrel_area_nm2, layer_thickness
from fenolite.analysis.insulation import layer_depths
from fenolite.analysis.pour import MAX_CELLS, Cell, PourCopper, shape_cells
from fenolite.analysis.power import Interval, PowerReport
from fenolite.analysis.practice import fill_names
from fenolite.backends.base import BoardPad
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-AN-NETWORK", "H-G-POWER-SPLIT"))
SCALE = 1 << 40
"""The potential of the start pads; the end pads are at 0."""
TOLERANCE = SCALE >> 24
"""The relaxation stops when no potential moves by more than this in a pass: about 6·10⁻⁸ of ``SCALE``."""
_SIDES = ((1, 0), (0, 1))
_Key = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SplitElement:
    """One element of a solved path: ``kind`` is ``track``, ``arc``, ``fill``, ``island`` or ``via``;
    ``layer`` its layer, or the layers of a via joined by ``/``. ``share_permille`` is ``None`` when no cell
    is the element's alone (all of it lies on other copper)."""

    kind: str
    where: str
    layer: str
    share_permille: int | None
    milliamps: int | None = None


@dataclass(frozen=True, slots=True)
class SplitRow:
    """A power path solved on the raster: the elements that carry its current, its resistance (with a
    resistivity), the interval of ``power`` and whether the resistance lies in it."""

    net: str
    start: tuple[str, ...]
    end: tuple[str, ...]
    milliamps: int | None
    elements: tuple[SplitElement, ...] = ()
    resistance_uohm: int | None = None
    bounds: Interval | None = None
    within: bool | None = None
    nodes: int = 0
    iterations: int = 0
    converged: bool = True


@dataclass(frozen=True, slots=True)
class SplitReport:
    rows: tuple[SplitRow, ...] = ()
    issues: tuple[Issue, ...] = ()
    evidence: Evidence = EVIDENCE
    summary: Mapping[str, object] = field(default_factory=lambda: {})


def _pad_name(record: BoardPad) -> str:
    holder = record.ref or record.footprint_id
    return f"{holder}-{record.number}" if record.number else holder


class _Union:
    def __init__(self) -> None:
        self.parent: dict[_Key, _Key] = {}

    def find(self, key: _Key) -> _Key:
        root = key
        while self.parent.setdefault(root, root) != root:
            root = self.parent[root]
        while self.parent[key] != root:
            self.parent[key], key = root, self.parent[key]
        return root

    def union(self, first: _Key, second: _Key) -> None:
        a, b = self.find(first), self.find(second)
        if a != b:
            self.parent[max(a, b)] = min(a, b)


@dataclass(slots=True)
class _Network:
    nodes: list[_Key]
    edges: dict[tuple[int, int], int]
    owner: dict[int, _Key]
    start: set[int]
    end: set[int]
    elements: dict[_Key, tuple[str, str, str]]
    extent: int


def _network(
    design: Design,
    pour: PourCopper,
    pads: Sequence[BoardPad],
    net: str,
    start: Sequence[str],
    end: Sequence[str],
    thickness: Mapping[str, Nm],
    barrel: Mapping[str, Fraction],
    middles: Mapping[str, Fraction],
) -> _Network | None:
    """The resistor network of ``net``; ``None`` when a pad of the path holds no copper of the net."""
    grid = pour.grid
    shapes = pour.copper.by_net.get(net, ())
    names = fill_names(shapes)
    cells: dict[str, dict[Cell, list[_Key]]] = defaultdict(lambda: defaultdict(list))
    elements: dict[_Key, tuple[str, str, str]] = {}
    via_where: dict[str, str] = {}
    for number, shape in enumerate(shapes):
        found = shape_cells(shape.shape, grid)
        if shape.kind in ("pad", "via"):
            if not found:  # a contact smaller than a cell keeps the cell that holds its centre
                point = shape.shape.core[0]
                found = {(point.x // grid, point.y // grid)}
            key: _Key = (
                ("pad", shape.entity_id) if shape.kind == "pad" else ("via", shape.entity_id, shape.layer)
            )
            if shape.kind == "via":
                via_where[shape.entity_id] = shape.where
        elif shape.kind == "fill":
            key = ("fill", names[number], shape.layer)
            elements[key] = ("fill", names[number], shape.layer)
        else:
            key = (shape.kind, shape.entity_id)
            elements[key] = (shape.kind, shape.where, shape.layer)
        for cell in found:
            cells[shape.layer][cell].append(key)
    for number, island in enumerate(pour.islands):
        if island.net != net:
            continue
        key = ("island", str(number))
        elements[key] = ("island", f"{'+'.join(island.zones)}#island{number}", island.layer)
        for cell in island.cells:
            cells[island.layer][cell].append(key)
    contacts = _Union()
    for held in cells.values():
        for cell, keys in held.items():
            own = [k for k in keys if k[0] in ("pad", "via")]
            for key in own[1:]:
                contacts.union(own[0], key)
            for di, dj in _SIDES:
                near = held.get((cell[0] + di, cell[1] + dj), [])
                other = [k for k in near if k[0] in ("pad", "via")]
                if own and other:
                    contacts.union(own[0], other[0])
    index: dict[_Key, int] = {}
    nodes: list[_Key] = []

    def node(key: _Key) -> int:
        if key not in index:
            index[key] = len(nodes)
            nodes.append(key)
        return index[key]

    owner: dict[int, _Key] = {}
    members: dict[_Key, set[_Key]] = defaultdict(set)
    edges: dict[tuple[int, int], int] = defaultdict(int)
    where: dict[tuple[str, Cell], tuple[int, bool]] = {}
    for layer in sorted(cells):
        for cell in sorted(cells[layer]):
            keys = cells[layer][cell]
            own = [k for k in keys if k[0] in ("pad", "via")]
            if own:
                root = contacts.find(own[0])
                where[layer, cell] = (node(("contact", *root)), True)
                for key in own:
                    members[root].add(key[:2])
            else:
                number = node(("cell", layer, str(cell[0]), str(cell[1])))
                where[layer, cell] = (number, False)
                distinct = set(keys)
                if len(distinct) == 1:
                    owner[number] = keys[0]
    for root, held in members.items():
        if len(held) == 1 and next(iter(held))[0] == "via":
            owner[index[("contact", *root)]] = next(iter(held))
    for (layer, cell), (number, contact) in where.items():
        weight = 1000 * thickness[layer]
        for di, dj in _SIDES:
            near = where.get((layer, (cell[0] + di, cell[1] + dj)))
            if near is None or near[0] == number:
                continue
            pair = (min(number, near[0]), max(number, near[0]))
            edges[pair] += 2 * weight if contact != near[1] else weight
    order = (
        {name: k for k, name in enumerate(copper_layers(design.board))} if design.board is not None else {}
    )
    for via_id, area in barrel.items():
        spans = sorted(
            (order.get(layer, 0), layer) for layer in cells if ("via", via_id, layer) in contacts.parent
        )
        for (_, upper), (_, lower) in zip(spans, spans[1:], strict=False):
            a = index[("contact", *contacts.find(("via", via_id, upper)))]
            b = index[("contact", *contacts.find(("via", via_id, lower)))]
            if a != b:
                edges[min(a, b), max(a, b)] += round(1000 * area / abs(middles[upper] - middles[lower]))
        if spans:
            elements["via", via_id] = (
                "via",
                via_where.get(via_id, via_id),
                "/".join(layer for _, layer in spans),
            )
    by_pad = {_pad_name(record): record for record in pads}
    ends: list[set[int]] = []
    for names_of in (start, end):
        found_nodes: set[int] = set()
        for name in names_of:
            record = by_pad.get(name)
            if record is None or ("pad", record.pad_id) not in contacts.parent:
                return None
            found_nodes.add(index[("contact", *contacts.find(("pad", record.pad_id)))])
        ends.append(found_nodes)
    extent = max(
        (
            max(i for i, _ in held)
            - min(i for i, _ in held)
            + max(j for _, j in held)
            - min(j for _, j in held)
        )
        for held in cells.values()
    )
    return _Network(nodes, dict(edges), owner, ends[0], ends[1], elements, extent)


def _solve(network: _Network, iterations: int) -> tuple[list[int], int, bool]:
    """The potentials by successive over-relaxation in integers, with ``ω = 2 − 3/n`` for a raster ``n``
    cells across (the sum of its two spans); the passes run and whether no potential moved by more than
    ``TOLERANCE`` in the last one."""
    count = len(network.nodes)
    neighbours: list[list[int]] = [[] for _ in range(count)]
    weights: list[list[int]] = [[] for _ in range(count)]
    for (a, b), weight in network.edges.items():
        neighbours[a].append(b)
        weights[a].append(weight)
        neighbours[b].append(a)
        weights[b].append(weight)
    potential = [SCALE // 2] * count
    for number in network.start:
        potential[number] = SCALE
    for number in network.end:
        potential[number] = 0
    fixed = network.start | network.end
    free = [
        (n, neighbours[n], weights[n], 2 * sum(weights[n]))
        for n in range(count)
        if n not in fixed and weights[n]
    ]
    size = max(network.extent, 1)
    over, under = (2 * size - 3, size) if size > 3 else (1, 1)
    read = potential.__getitem__
    for done in range(1, iterations + 1):
        moved = 0
        for n, near, weight, twice in free:
            step = (2 * sum(map(mul, weight, map(read, near))) + twice // 2) // twice - potential[n]
            if step:
                move = step * over // under or step
                potential[n] += move
                if abs(move) > moved:
                    moved = abs(move)
        if moved <= TOLERANCE:
            return potential, done, True
    return potential, iterations, False


def _carried(network: _Network, flows: Sequence[tuple[int, int, int]]) -> dict[_Key, int]:
    """The current each element carries. A via carries the largest flow through its barrel. A track, an arc
    or a fill carries, in each piece of the cells it alone covers, the sum of the net flows into that piece
    from each node around it, cells shared with other elements joined into one node (so a current that
    passes through a contact or a joint counts once), and the largest over its pieces."""
    parent: dict[int, int] = {}

    def find(node: int) -> int:
        while parent.setdefault(node, node) != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def shared(node: int) -> bool:
        return node not in network.owner and network.nodes[node][0] == "cell"

    barrels: dict[_Key, int] = {}
    for a, b, flow in flows:
        first, second = network.owner.get(a), network.owner.get(b)
        if first is not None and first == second:
            if first[0] == "via":
                barrels[first] = max(barrels.get(first, 0), abs(flow))
            else:
                parent[find(max(a, b))] = find(min(a, b))
        elif shared(a) and shared(b):
            parent[find(max(a, b))] = find(min(a, b))
    inflow: dict[tuple[int, int], int] = defaultdict(int)
    for a, b, flow in flows:
        first, second = network.owner.get(a), network.owner.get(b)
        if first == second:
            continue
        if first is not None and first[0] != "via":
            inflow[find(a), find(b)] -= flow
        if second is not None and second[0] != "via":
            inflow[find(b), find(a)] += flow
    pieces: dict[int, int] = defaultdict(int)
    for (piece, _), net in inflow.items():
        pieces[piece] += max(net, 0)
    carried: dict[_Key, int] = dict(barrels)
    for node, key in network.owner.items():
        if key[0] != "via":
            carried[key] = max(carried.get(key, 0), pieces.get(find(node), 0))
    return carried


def analyze_split(
    design: Design,
    *,
    pads: Sequence[BoardPad] | None,
    pour: PourCopper,
    power: PowerReport,
    copper_thickness: Mapping[str, Nm] | None = None,
    via_plating: Nm | None = None,
    resistivity_pohm_m: int | None = None,
    iterations: int | None = None,
) -> SplitReport:
    """Each row of ``power`` solved on the raster of ``pour``: the share of each element and, with a
    resistivity, the resistance against ``power``'s interval. ``iterations`` bounds the relaxation (default:
    50 per cell of the raster's extent, plus 1000)."""
    board = design.board
    missing: Counter[str] = Counter()
    rows: list[SplitRow] = []
    issues: list[Issue] = []
    unsolved = 0
    for row in power.rows:
        shapes = pour.copper.by_net.get(row.net, ())
        if board is None or pads is None or not shapes:
            unsolved += 1
            continue
        layers = sorted(
            {shape.layer for shape in shapes} | {i.layer for i in pour.islands if i.net == row.net}
        )
        thickness = {layer: layer_thickness(board, layer, copper_thickness) for layer in layers}
        gaps = [layer for layer, value in thickness.items() if value is None]
        if gaps:
            missing["copper thickness"] += 1
            unsolved += 1
            continue
        via_ids = sorted({shape.entity_id for shape in shapes if shape.kind == "via"})
        barrel: dict[str, Fraction] = {}
        middles: dict[str, Fraction] = {}
        if via_ids:
            depths = layer_depths(board)
            if via_plating is None:
                missing["via plating"] += 1
                unsolved += 1
                continue
            if depths is None or any(layer not in depths for layer in layers):
                missing["stack-up"] += 1
                unsolved += 1
                continue
            middles = {layer: Fraction(top + bottom, 2) for layer, (top, bottom) in depths.items()}
            vias = {via.id: via for via in board.vias}
            for via_id in via_ids:
                barrel[via_id] = Fraction(barrel_area_nm2(vias[via_id].drill, via_plating))
        if sum(len(shape_cells(s.shape, pour.grid)) for s in shapes if s.kind == "fill") > MAX_CELLS:
            unsolved += 1
            continue
        known = {layer: value for layer, value in thickness.items() if value is not None}
        network = _network(design, pour, pads, row.net, row.start, row.end, known, barrel, middles)
        if network is None:
            unsolved += 1
            continue
        rows.append(
            _split_row(
                row.net,
                row.start,
                row.end,
                row.milliamps,
                row.resistance_uohm,
                network,
                resistivity_pohm_m,
                iterations,
            )
        )
    for name, count in sorted(missing.items()):
        issues.append(
            issue(
                "analysis.input-missing",
                f"{name} not given: {count} power path(s) are not split",
                where=name,
                hint="Fenolite assumes no value; give it as an option or in the stack-up of the board",
            )
        )
    evidence = EVIDENCE
    if pads is None or pour.copper.unsupported or any(not row.converged for row in rows):
        evidence = Evidence(Level.UNVERIFIED, hypotheses=EVIDENCE.hypotheses)
    summary = {"paths": len(rows), "unsolved": unsolved, "grid": pour.grid}
    return SplitReport(tuple(rows), tuple(issues), evidence, summary)


def _split_row(
    net: str,
    start: tuple[str, ...],
    end: tuple[str, ...],
    milliamps: int | None,
    bounds: Interval | None,
    network: _Network,
    resistivity: int | None,
    iterations: int | None,
) -> SplitRow:
    if network.start & network.end:
        return SplitRow(
            net,
            start,
            end,
            milliamps,
            (),
            0 if resistivity is not None else None,
            bounds,
            None,
            len(network.nodes),
        )
    limit = iterations if iterations is not None else 50 * network.extent + 1000
    potential, done, converged = _solve(network, limit)
    into = out = 0
    flows: list[tuple[int, int, int]] = []
    for (a, b), weight in network.edges.items():
        flow = weight * (potential[a] - potential[b])
        flows.append((a, b, flow))
        if (a in network.start) != (b in network.start):
            into += flow if a in network.start else -flow
        if (a in network.end) != (b in network.end):
            out += -flow if a in network.end else flow
    current = Fraction(into + out, 2)
    elements: list[SplitElement] = []
    carried = _carried(network, flows)
    for key, (kind, where, layer) in network.elements.items():
        through = carried.get(key)
        share = amps = None
        if through is not None and current > 0:
            share = round(1000 * through / current)
            amps = None if milliamps is None else round(milliamps * through / current)
        elements.append(SplitElement(kind, where, layer, share, amps))
    elements.sort(key=lambda e: (e.layer, e.kind, e.where))
    resistance = within = None
    if resistivity is not None and current > 0:
        resistance = round(Fraction(1_000_000 * resistivity * SCALE) / current)
        if bounds is not None:
            within = bounds.low <= resistance and (bounds.high is None or resistance <= bounds.high)
    return SplitRow(
        net,
        start,
        end,
        milliamps,
        tuple(elements),
        resistance,
        bounds,
        within,
        len(network.nodes),
        done,
        converged,
    )


__all__ = ["EVIDENCE", "SCALE", "SplitElement", "SplitReport", "SplitRow", "analyze_split"]

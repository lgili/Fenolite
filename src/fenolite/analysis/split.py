# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The share of a power path's current in each of its tracks, arcs, fills and vias, from a resistive solve
on a mesh of the copper (change c0213; capability board-analyses, "Current split"; user guide
``docs/analyses.md``, "Power paths").

The cells of the net's copper on every layer (the raster of ``analysis.pour``, with every zone layer in its
copper state, merged into the leaves of the adaptive mesh of ``analysis.mesh``, change c0503) are the nodes of
a network of resistors, solved coarse to fine on the meshes of ``8h`` to ``h``. The cells of each pad and each
via on a layer form one node, an ideal contact as a joint of the power network is; contacts that share or
touch cells are one node, and a through-hole pad's layers too. Two neighbour cells are joined by the
conductance ``t/ρ`` of a square of copper of the layer's thickness, doubled between a contact and a free cell,
because the contact's edge lies at the face of its cell, half a step from the free cell's centre. The layers
of a via are joined pairwise down its span by ``A/(ρ·h)``: ``A`` the barrel's area for the plating given,
``h`` the depth between the middles of the two layers in the stack-up. The resistivity cancels from the
shares.

The start pads are held at ``SCALE`` and the end pads at 0; the other potentials are found by conjugate
gradients in integers, preconditioned by a V-cycle of aggregation multigrid, until no node's relaxation step
exceeds ``TOLERANCE``, or ``iterations`` passes.
A via carries the flow through its barrel; a track, an arc or a fill carries the net inflow into the cells it
alone covers, and its share is that current over the path's. With a resistivity the path's resistance is
``ρ·SCALE/I``, compared with the interval that ``analysis.power`` gives on the same board. ``power`` counts a
track from the centre of its pads, while the solve holds each pad at one potential, so on a path of tracks
the solve may lie below the interval by the copper inside the pads. It is an estimate on a raster, not a
field simulation: the copper is placed to within one cell.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction
from functools import partial
from operator import mul

from fenolite.analysis.codes import issue
from fenolite.analysis.copper import copper_layers
from fenolite.analysis.current import barrel_area_nm2, layer_thickness
from fenolite.analysis.deadline import Deadline, passed
from fenolite.analysis.insulation import layer_depths
from fenolite.analysis.mesh import (
    SCALE_K,
    LayerMesh,
    Leaf,
    Spans,
    cell_spans,
    contact_free,
    hanging,
    mesh_edges,
    mesh_layers,
    ring_spans,
    weight,
)
from fenolite.analysis.pour import MAX_CELLS, PourCopper, shape_cells
from fenolite.analysis.power import Interval, PathRow, PowerReport
from fenolite.analysis.practice import fill_names
from fenolite.backends.base import BoardPad
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.geometry import area2
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-AN-NETWORK", "H-G-POWER-SPLIT"))
SCALE = 1 << 40
"""The potential of the start pads; the end pads are at 0."""
LEVELS = 3
"""The coarsest level of the cascade: cells of ``8·h`` (change c0503, design D4)."""
TOLERANCE = SCALE >> 24
"""The solve stops when no node's relaxation step ``rᵢ/dᵢ`` exceeds this: about 6·10⁻⁸ of ``SCALE``."""
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
    """A power path solved on the mesh: the elements that carry its current, its resistance (with a
    resistivity), the interval of ``power`` and whether the resistance lies in it. ``cell_nm`` is the cell
    size of the finest level solved, ``nodes`` and ``iterations`` its nodes and passes; ``complete`` is
    false when a deadline stopped the cascade above the pour grid (change c0503)."""

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
    cell_nm: int = 0
    complete: bool = True


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
    meshes: dict[str, LayerMesh]
    where: dict[tuple[str, Leaf], int]
    contacts: dict[_Key, int]
    cell: int


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
    level: int = 0,
) -> _Network | None:
    """The resistor network of ``net`` on the mesh of cell size ``pour.grid·2^level``; ``None`` when a pad of
    the path holds no copper of the net."""
    grid = pour.grid << level
    shapes = pour.copper.by_net.get(net, ())
    names = fill_names(shapes)
    items: dict[str, list[tuple[_Key, Spans]]] = defaultdict(list)
    elements: dict[_Key, tuple[str, str, str]] = {}
    via_where: dict[str, str] = {}
    for number, shape in enumerate(shapes):
        if shape.kind == "fill":
            spans = ring_spans(shape.shape.core, grid)
        else:
            found = shape_cells(shape.shape, grid)
            if shape.kind in ("pad", "via") and not found:  # a contact smaller than a cell keeps its centre's
                point = shape.shape.core[0]
                found = {(point.x // grid, point.y // grid)}
            spans = cell_spans(found)
        if shape.kind in ("pad", "via"):
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
        if spans:
            items[shape.layer].append((key, spans))
    for number, island in enumerate(pour.islands):
        if island.net != net:
            continue
        key = ("island", str(number))
        elements[key] = ("island", f"{'+'.join(island.zones)}#island{number}", island.layer)
        items[island.layer].append((key, cell_spans({(i >> level, j >> level) for i, j in island.cells})))
    meshes = mesh_layers(items)
    contacts = _Union()
    pairs: dict[str, list[tuple[Leaf, Leaf, int, int, int]]] = {}
    for layer, mesh in meshes.items():
        for _, label in mesh.leaves.values():
            own = [k for k in label if k[0] in ("pad", "via")]
            for key in own:
                contacts.find(key)
            for key in own[1:]:
                contacts.union(own[0], key)
        pairs[layer] = mesh_edges(mesh)
        for a, b, _, _, _ in pairs[layer]:
            first, second = mesh.leaves[a][1], mesh.leaves[b][1]
            if not contact_free(first) and not contact_free(second):
                one = next(k for k in first if k[0] in ("pad", "via"))
                contacts.union(one, next(k for k in second if k[0] in ("pad", "via")))
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
    where: dict[tuple[str, Leaf], int] = {}
    for layer, mesh in meshes.items():
        for leaf in sorted(mesh.leaves):
            label = mesh.leaves[leaf][1]
            own = [k for k in label if k[0] in ("pad", "via")]
            if own:
                root = contacts.find(own[0])
                where[layer, leaf] = node(("contact", *root))
                for key in own:
                    members[root].add(key[:2])
            else:
                number = node(("cell", layer, str(leaf[0]), str(leaf[1])))
                where[layer, leaf] = number
                if len(label) == 1:
                    owner[number] = label[0]
    for root, held in members.items():
        if len(held) == 1 and next(iter(held))[0] == "via":
            owner[index[("contact", *root)]] = next(iter(held))
    for layer, found in pairs.items():
        mesh = meshes[layer]
        conductance = 1000 * thickness[layer]
        for a, b, size_a, size_b, shared in found:
            first, second = where[layer, a], where[layer, b]
            if first == second:
                continue
            free_a, free_b = contact_free(mesh.leaves[a][1]), contact_free(mesh.leaves[b][1])
            pair = (min(first, second), max(first, second))
            edges[pair] += weight(size_a, size_b, shared, not free_a, not free_b, conductance)
        for pair, value in hanging(mesh, conductance):
            first, second = where[layer, pair[0]], where[layer, pair[1]]
            edges[min(first, second), max(first, second)] -= value
    order = (
        {name: k for k, name in enumerate(copper_layers(design.board))} if design.board is not None else {}
    )
    for via_id, area in barrel.items():
        spans_of = sorted(
            (order.get(layer, 0), layer) for layer in meshes if ("via", via_id, layer) in contacts.parent
        )
        for (_, upper), (_, lower) in zip(spans_of, spans_of[1:], strict=False):
            a = index[("contact", *contacts.find(("via", via_id, upper)))]
            b = index[("contact", *contacts.find(("via", via_id, lower)))]
            if a != b:
                edges[min(a, b), max(a, b)] += round(
                    SCALE_K * 1000 * area / abs(middles[upper] - middles[lower])
                )
        if spans_of:
            elements["via", via_id] = (
                "via",
                via_where.get(via_id, via_id),
                "/".join(layer for _, layer in spans_of),
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
    keyed = {key: index[("contact", *contacts.find(key))] for key in contacts.parent}
    network = _Network(nodes, dict(edges), owner, ends[0], ends[1], elements, 0, meshes, where, keyed, grid)
    network.extent = _hops(network)
    return network


def _hops(network: _Network) -> int:
    """The most links between a start node and any node: the span of the network that bounds the passes
    of a level by default."""
    links: list[list[int]] = [[] for _ in network.nodes]
    for a, b in network.edges:
        links[a].append(b)
        links[b].append(a)
    seen = dict.fromkeys(network.start, 0)
    queue = deque(network.start)
    while queue:
        here = queue.popleft()
        for other in links[here]:
            if other not in seen:
                seen[other] = seen[here] + 1
                queue.append(other)
    return max(seen.values(), default=0)


def _guess(fine: _Network, coarse: _Network | None, potential: Sequence[int] | None) -> list[int]:
    """The starting potentials of ``fine``: each node takes the potential of the coarse node that holds the
    centre of its leaf, or of a coarse cell next to it (a contact: of the same contact), else
    ``SCALE / 2``."""
    guess = [SCALE // 2] * len(fine.nodes)
    if coarse is None or potential is None:
        return guess
    ratio = coarse.cell // fine.cell
    for key, number in fine.contacts.items():
        other = coarse.contacts.get(key)
        if other is not None:
            guess[number] = potential[other]
    for (layer, leaf), number in fine.where.items():
        if fine.nodes[number][0] != "cell":
            continue
        mesh = coarse.meshes.get(layer)
        size = fine.meshes[layer].leaves[leaf][0]
        if mesh is None:
            continue
        i, j = (2 * leaf[0] + size) // (2 * ratio), (2 * leaf[1] + size) // (2 * ratio)
        # a leaf along an edge may lie outside the coarse copper: the nearest coarse cell around it then
        for di, dj in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            held = mesh.locate(i + di, j + dj)
            if held is not None:
                guess[number] = potential[coarse.where[layer, held]]
                break
    return guess


_Level = tuple[list[list[int]], list[list[int]], list[int], list[int]]
"""One level of the solver's hierarchy: neighbours, weights, diagonal, and each node's aggregate one level
coarser (empty on the coarsest)."""
COARSEST = 32
"""The hierarchy stops at this many nodes, or when a level no longer shrinks by a fifth."""


def _matched(neighbours: list[list[int]], weights: list[list[int]], group: list[int]) -> list[int]:
    """Pairs each group with its most strongly joined unpaired neighbour group (heaviest positive link, the
    lowest number on a tie), in order of the groups: the pairwise aggregation of a coarser level."""
    count = max(group, default=-1) + 1
    links: list[dict[int, int]] = [{} for _ in range(count)]
    for node, near in enumerate(neighbours):
        own = group[node]
        for other, value in zip(near, weights[node], strict=True):
            mate = group[other]
            if mate != own:
                links[own][mate] = links[own].get(mate, 0) + value
    pair = [-1] * count
    made = 0
    for own in range(count):
        if pair[own] >= 0:
            continue
        best, held = -1, 0
        for mate, value in sorted(links[own].items()):
            if pair[mate] < 0 and value > held:
                best, held = mate, value
        pair[own] = made
        if best >= 0:
            pair[best] = made
        made += 1
    return [pair[g] for g in group]


def _hierarchy(neighbours: list[list[int]], weights: list[list[int]], diagonal: list[int]) -> list[_Level]:
    """The levels of an aggregation multigrid over the free nodes: each coarser level joins the nodes of
    two pairwise matchings (about four nodes) into one, with the Galerkin weights ``PᵀAP`` summed in
    integers (Fenolite's own preconditioner, change c0503)."""
    levels: list[_Level] = []
    while True:
        count = len(diagonal)
        if count <= COARSEST:
            levels.append((neighbours, weights, diagonal, []))
            return levels
        group = _matched(neighbours, weights, list(range(count)))
        group = _matched(neighbours, weights, group)
        size = max(group) + 1
        if 5 * size > 4 * count:
            levels.append((neighbours, weights, diagonal, []))
            return levels
        levels.append((neighbours, weights, diagonal, group))
        coarse_diagonal = [0] * size
        joined: list[dict[int, int]] = [{} for _ in range(size)]
        for node in range(count):
            own = group[node]
            coarse_diagonal[own] += diagonal[node]
            for other, value in zip(neighbours[node], weights[node], strict=True):
                mate = group[other]
                if mate == own:
                    coarse_diagonal[own] -= value
                else:
                    joined[own][mate] = joined[own].get(mate, 0) + value
        neighbours = [sorted(held) for held in joined]
        weights = [[held[k] for k in near] for held, near in zip(joined, neighbours, strict=True)]
        diagonal = coarse_diagonal


def _sweep(level: _Level, z: list[int], r: Sequence[int], order: Sequence[int]) -> None:
    """One Gauss-Seidel sweep of ``A z = r`` in ``order``, rounded to whole units."""
    neighbours, weights, diagonal, _ = level
    read = z.__getitem__
    for n in order:
        d = diagonal[n]
        if d > 0:
            z[n] = (2 * (r[n] + sum(map(mul, weights[n], map(read, neighbours[n])))) + d) // (2 * d)


def _cycle(levels: Sequence[_Level], depth: int, r: Sequence[int]) -> list[int]:
    """The V-cycle of the hierarchy from ``depth`` on ``r``: a forward sweep, the coarse correction, a
    backward sweep (many sweeps on the coarsest), so the preconditioner is symmetric."""
    level = levels[depth]
    neighbours, weights, diagonal, group = level
    count = len(diagonal)
    forward, backward = range(count), range(count - 1, -1, -1)
    z = [0] * count
    if not group:
        for _ in range(min(4 * count, 64)):
            _sweep(level, z, r, forward)
            _sweep(level, z, r, backward)
        return z
    _sweep(level, z, r, forward)
    read = z.__getitem__
    coarse = [0] * len(levels[depth + 1][2])
    for n in range(count):
        coarse[group[n]] += r[n] - diagonal[n] * z[n] + sum(map(mul, weights[n], map(read, neighbours[n])))
    correction = _cycle(levels, depth + 1, coarse)
    for n in range(count):
        z[n] += correction[group[n]]
    _sweep(level, z, r, backward)
    return z


def _rounded(value: int, top: int, bottom: int) -> int:
    """``value·top/bottom`` rounded to the nearest whole number, ``bottom`` above 0."""
    return (2 * value * top + bottom) // (2 * bottom)


def _solve(
    network: _Network, iterations: int, guess: list[int], deadline: Deadline | None = None
) -> tuple[list[int], int, bool, bool]:
    """The potentials from ``guess`` by conjugate gradients in integers, preconditioned by a V-cycle of
    aggregation multigrid (change c0503, task 4.1): the passes run, whether no free node's relaxation step
    ``rᵢ/dᵢ`` exceeds ``TOLERANCE`` (the stop of the former relaxation, which moved each node by about that
    much), and whether ``deadline`` cut the solve (checked every pass). ``α`` and ``β`` are exact ratios of
    integers; each update is rounded to a whole unit of potential, ``2⁻⁴⁰`` of ``SCALE``. ``β`` is the
    flexible form ``z·(r − r₀)/(r₀·z₀)``, which keeps the rounded preconditioner safe."""
    count = len(network.nodes)
    adjacent: list[list[tuple[int, int]]] = [[] for _ in range(count)]
    for (a, b), value in network.edges.items():
        adjacent[a].append((b, value))
        adjacent[b].append((a, value))
    potential = guess
    for number in network.start:
        potential[number] = SCALE
    for number in network.end:
        potential[number] = 0
    fixed = network.start | network.end
    free = [n for n in range(count) if n not in fixed and adjacent[n]]
    slot = {n: k for k, n in enumerate(free)}
    neighbours: list[list[int]] = []
    weights: list[list[int]] = []
    diagonal: list[int] = []
    residual: list[int] = []
    for n in free:
        near = [(slot[m], value) for m, value in adjacent[n] if m in slot]
        neighbours.append([m for m, _ in near])
        weights.append([value for _, value in near])
        diagonal.append(sum(value for _, value in adjacent[n]))
        residual.append(sum(value * (potential[m] - potential[n]) for m, value in adjacent[n]))
    if not free:
        return potential, 0, True, False
    levels = _hierarchy(neighbours, weights, diagonal)
    x = [potential[n] for n in free]

    def apply(vector: Sequence[int]) -> list[int]:
        read = vector.__getitem__
        return [
            d * v - sum(map(mul, w, map(read, near)))
            for d, v, w, near in zip(diagonal, vector, weights, neighbours, strict=True)
        ]

    def settled(r: Sequence[int]) -> bool:
        return all(abs(value) <= TOLERANCE * d for value, d in zip(r, diagonal, strict=True))

    done, converged, cut = 0, settled(residual), False
    z = _cycle(levels, 0, residual)
    p = list(z)
    rz: int = sum(map(mul, residual, z))
    while not converged and done < iterations:
        if passed(deadline):
            cut = True
            break
        q = apply(p)
        pq: int = sum(map(mul, p, q))
        if pq <= 0 or rz <= 0:
            break
        alpha = (rz, pq)
        x = [xi + _rounded(pi, *alpha) for xi, pi in zip(x, p, strict=True)]
        before = residual
        residual = [ri - _rounded(qi, *alpha) for ri, qi in zip(residual, q, strict=True)]
        done += 1
        converged = settled(residual)
        if converged:
            break
        z = _cycle(levels, 0, residual)
        new_rz: int = sum(map(mul, residual, z))
        top: int = new_rz - sum(map(mul, before, z))
        p = [zi + _rounded(pi, top, rz) for zi, pi in zip(z, p, strict=True)]
        rz = new_rz
    for n, value in zip(free, x, strict=True):
        potential[n] = value
    return potential, done, converged, cut


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
    deadline: Deadline | None = None,
) -> SplitReport:
    """Each row of ``power`` solved on the mesh of its copper, coarse to fine (change c0503): the share of
    each element and, with a resistivity, the resistance against ``power``'s interval. ``iterations``
    bounds the passes of each level (default: 50 per link of the level's span, plus 1000). With
    ``deadline`` a row keeps its finest finished level and has ``complete`` false when that is not the
    finest; the report then holds one ``analysis.deadline`` warning."""
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
        # the cells the fills cover, by their area: the mesh never rasterises them
        area = sum(abs(area2(s.shape.core)) for s in shapes if s.kind == "fill") // 2
        if area > MAX_CELLS * pour.grid * pour.grid:
            unsolved += 1
            continue
        known = {layer: value for layer, value in thickness.items() if value is not None}

        made = _split_row(
            row,
            partial(_network, design, pour, pads, row.net, row.start, row.end, known, barrel, middles),
            resistivity_pohm_m,
            iterations,
            deadline,
        )
        if made is None:
            unsolved += 1
            continue
        rows.append(made)
    for name, count in sorted(missing.items()):
        issues.append(
            issue(
                "analysis.input-missing",
                f"{name} not given: {count} power path(s) are not split",
                where=name,
                hint="Fenolite assumes no value; give it as an option or in the stack-up of the board",
            )
        )
    cut = [row for row in rows if not row.complete]
    if cut:
        names = ", ".join(
            f"{'/'.join((','.join(row.start), ','.join(row.end)))} at {row.cell_nm} nm" if row.cell_nm else
            f"{'/'.join((','.join(row.start), ','.join(row.end)))} with no level"
            for row in cut
        )  # fmt: skip
        issues.append(
            issue(
                "analysis.deadline",
                f"the deadline passed before the split of the power paths {names} reached the grid of "
                f"{pour.grid} nm: each keeps its finest finished level",
                where="split",
                hint="run again with a longer --deadline, or --deadline 0 for none",
            )
        )
    evidence = EVIDENCE
    if pads is None or pour.copper.unsupported or any(not row.converged for row in rows):
        evidence = Evidence(Level.UNVERIFIED, hypotheses=EVIDENCE.hypotheses)
    summary = {"paths": len(rows), "unsolved": unsolved, "grid": pour.grid}
    return SplitReport(tuple(rows), tuple(issues), evidence, summary)


def _split_row(
    row: PathRow,
    build: Callable[[int], _Network | None],
    resistivity: int | None,
    iterations: int | None,
    deadline: Deadline | None,
) -> SplitRow | None:
    """The finest level of the cascade that finished: each level from ``LEVELS`` down to 0 whose cells
    still separate the start and end contacts, started from the level before it."""
    network = build(0)
    if network is None:
        return None
    if network.start & network.end:
        return SplitRow(
            row.net, row.start, row.end, row.milliamps, (), 0 if resistivity is not None else None,
            row.resistance_uohm, None, len(network.nodes), cell_nm=network.cell,
        )  # fmt: skip
    best: SplitRow | None = None
    previous: tuple[_Network, list[int]] | None = None
    for level in range(LEVELS, -1, -1):
        mesh = network if level == 0 else build(level)
        if mesh is None or mesh.start & mesh.end or not mesh.start or not mesh.end:
            continue
        if passed(deadline):
            break
        guess = _guess(mesh, *(previous if previous is not None else (None, None)))
        limit = iterations if iterations is not None else 50 * mesh.extent + 1000
        potential, done, converged, cut = _solve(mesh, limit, guess, deadline)
        if cut:
            break
        previous = (mesh, potential)
        best = _result(row, mesh, potential, done, converged, resistivity, complete=level == 0)
    if best is None:
        return SplitRow(
            row.net, row.start, row.end, row.milliamps, bounds=row.resistance_uohm, complete=False
        )
    return best


def _result(
    row: PathRow,
    network: _Network,
    potential: Sequence[int],
    done: int,
    converged: bool,
    resistivity: int | None,
    *,
    complete: bool,
) -> SplitRow:
    milliamps, bounds = row.milliamps, row.resistance_uohm
    into = out = 0
    flows: list[tuple[int, int, int]] = []
    for (a, b), value in network.edges.items():
        flow = value * (potential[a] - potential[b])
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
        resistance = round(Fraction(1_000_000 * resistivity * SCALE * SCALE_K) / current)
        if bounds is not None:
            within = bounds.low <= resistance and (bounds.high is None or resistance <= bounds.high)
    return SplitRow(
        row.net,
        row.start,
        row.end,
        milliamps,
        tuple(elements),
        resistance,
        bounds,
        within,
        len(network.nodes),
        done,
        converged,
        network.cell,
        complete,
    )


__all__ = ["EVIDENCE", "LEVELS", "SCALE", "SplitElement", "SplitReport", "SplitRow", "analyze_split"]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An adaptive mesh of a net's copper for the current split (change c0503, design D4; capability
board-analyses, "Current split"; ``docs/analyses.md``, "Power paths").

The copper of each layer is first described as runs of cells per row of the raster of cell size ``h``
(the cells whose centre lies in a shape, the rule of ``analysis.pour``), each run labelled with the items
that cover it. A quadtree over the box of the runs keeps a square as one leaf when every cell in it carries
the same label, and splits it in four otherwise, down to single cells: leaves are large inside plain copper
and of size ``h`` only along copper edges, holes, pads and vias. Leaves that share a side are balanced to
differ by at most one level. Every raster cell's centre lies in exactly one leaf, so the mesh holds the
same copper as the raster, in far fewer nodes.

Two leaves of sizes ``a`` and ``b`` that share a side of length ``s`` are joined by the two-point flux
``(t/ρ)·s/d`` with ``d = (a + b)/2``, the distance between their centres across the side; a leaf next to a
contact by ``(t/ρ)·s/(a/2)``, as the contact's edge lies at the face. Weights are kept in integers times
``SCALE_K``. The discretisation is Fenolite's own (``INFERRED``, ``H-G-POWER-SPLIT``).
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections import Counter, defaultdict, deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

from fenolite.core.coords import Point

Cell = tuple[int, int]
Key = tuple[str, ...]
Label = tuple[Key, ...]
Spans = dict[int, list[tuple[int, int]]]
"""Per row ``j``, the inclusive runs ``(i0, i1)`` of cells."""
SCALE_K = 3
"""The weights of the mesh are ``SCALE_K`` times the conductance in units of ``t/ρ``: with leaves balanced
2:1 every two-point flux is then a whole number."""
CONTACTS = ("pad", "via")
MAX_LEAF = 8
"""The largest leaf, in cells: larger leaves add little speed and cost accuracy where the field bends
(change c0503, task 3.3: 16 cells left the dumbbell bench 2.2 % from the finite-difference oracle, 8 cells
1.8 %)."""


def _first(value: Fraction | int, grid: int) -> int:
    return math.ceil(Fraction(value - grid // 2, grid))


def _last(value: Fraction | int, grid: int) -> int:
    return math.floor(Fraction(value - grid // 2, grid))


def ring_spans(ring: Sequence[Point], grid: int) -> Spans:
    """The cells whose centre lies inside ``ring`` (non-zero rule), as runs per row: the cells of
    ``pour.ring_cells``, found edge by edge instead of row by row over every edge."""
    crossings: dict[int, list[tuple[Fraction, int]]] = defaultdict(list)
    count = len(ring)
    if count < 3:
        return {}
    for k in range(count):
        a, b = ring[k], ring[(k + 1) % count]
        if a.y == b.y:
            continue
        direction = 1 if a.y < b.y else -1
        low, high = (a.y, b.y) if a.y < b.y else (b.y, a.y)
        for j in range(_first(low, grid), _last(high - 1, grid) + 1):
            y = j * grid + grid // 2
            crossings[j].append((a.x + Fraction((y - a.y) * (b.x - a.x), b.y - a.y), direction))
    found: Spans = {}
    for j, row in crossings.items():
        row.sort()
        winding = 0
        start = Fraction(0)
        runs: list[tuple[int, int]] = []
        for x, direction in row:
            before = winding
            winding += direction
            if before == 0 and winding != 0:
                start = x
            elif before != 0 and winding == 0:
                i0, i1 = _first(start, grid), _last(x, grid)
                if i0 <= i1:
                    runs.append((i0, i1))
        if runs:
            found[j] = runs
    return found


def cell_spans(cells: Iterable[Cell]) -> Spans:
    """``cells`` as runs per row."""
    rows: dict[int, list[int]] = defaultdict(list)
    for i, j in cells:
        rows[j].append(i)
    found: Spans = {}
    for j, held in rows.items():
        held.sort()
        runs: list[tuple[int, int]] = []
        for i in held:
            if runs and i <= runs[-1][1] + 1:
                runs[-1] = (runs[-1][0], max(runs[-1][1], i))
            else:
                runs.append((i, i))
        found[j] = runs
    return found


_Row = tuple[list[int], list[int], list[Label]]


def _label_rows(items: Sequence[tuple[Key, Spans]]) -> dict[int, _Row]:
    """Per row, the runs of cells with the same non-empty label (the sorted keys that cover them)."""
    events: dict[int, list[tuple[int, int, Key]]] = defaultdict(list)
    for key, spans in items:
        for j, runs in spans.items():
            for i0, i1 in runs:
                events[j].append((i0, 1, key))
                events[j].append((i1 + 1, -1, key))
    interned: dict[Label, Label] = {}
    rows: dict[int, _Row] = {}
    for j, row in events.items():
        row.sort()
        held: Counter[Key] = Counter()
        starts: list[int] = []
        ends: list[int] = []
        labels: list[Label] = []
        k = 0
        while k < len(row):
            at = row[k][0]
            while k < len(row) and row[k][0] == at:
                held[row[k][2]] += row[k][1]
                k += 1
            label = tuple(sorted(key for key, n in held.items() if n > 0))
            if not label or k == len(row):
                continue
            end = row[k][0] - 1
            label = interned.setdefault(label, label)
            if labels and labels[-1] == label and ends[-1] == at - 1:
                ends[-1] = end
            else:
                starts.append(at)
                ends.append(end)
                labels.append(label)
        if starts:
            rows[j] = (starts, ends, labels)
    return rows


def _uniform(rows: Mapping[int, _Row], i0: int, j0: int, size: int) -> Label | None:
    """The label of every cell of the square, ``()`` when it holds no copper, ``None`` when it is mixed."""
    first: Label | None = None
    last = i0 + size - 1
    for j in range(j0, j0 + size):
        row = rows.get(j)
        label: Label = ()
        if row is not None:
            starts, ends, labels = row
            k = bisect_right(starts, i0) - 1
            if k >= 0 and ends[k] >= i0:
                if ends[k] < last:
                    return None
                label = labels[k]
            elif k + 1 < len(starts) and starts[k + 1] <= last:
                return None
        if first is None:
            first = label
        elif label != first:
            return None
    return first


Leaf = tuple[int, int]
"""The lower corner ``(i0, j0)`` of a leaf, in cells."""


@dataclass(slots=True)
class LayerMesh:
    """The leaves of one layer: lower corner to ``(size, label)``, sizes in cells."""

    leaves: dict[Leaf, tuple[int, Label]]
    origin: Cell
    sizes: tuple[int, ...]

    def locate(self, i: int, j: int) -> Leaf | None:
        """The leaf that holds the cell ``(i, j)``, ``None`` outside the copper."""
        ox, oy = self.origin
        for size in self.sizes:
            key = (ox + (i - ox) // size * size, oy + (j - oy) // size * size)
            found = self.leaves.get(key)
            if found is not None and found[0] == size:
                return key
        return None

    def side(self, leaf: Leaf, size: int, direction: tuple[int, int]) -> list[tuple[Leaf, int]]:
        """The leaves across one side of ``leaf`` with the length of side they share, in cells."""
        i0, j0 = leaf
        dx, dy = direction
        found: list[tuple[Leaf, int]] = []
        step = 0
        while step < size:
            i = i0 + size if dx > 0 else i0 - 1 if dx < 0 else i0 + step
            j = j0 + size if dy > 0 else j0 - 1 if dy < 0 else j0 + step
            near = self.locate(i, j)
            if near is None:
                step += 1
                continue
            other = self.leaves[near][0]
            along = near[1] if dx else near[0]
            shared = min(along + other, (j0 if dx else i0) + size) - (j if dx else i)
            found.append((near, shared))
            step += shared
        return found


_SIDES = ((1, 0), (0, 1), (-1, 0), (0, -1))


def layer_mesh(rows: Mapping[int, _Row], origin: Cell, top: int) -> LayerMesh:
    """The balanced quadtree of the labelled runs ``rows`` in the square of ``top`` cells at ``origin``."""
    leaves: dict[Leaf, tuple[int, Label]] = {}
    stack = [(origin[0], origin[1], top)]
    while stack:
        i0, j0, size = stack.pop()
        label = _uniform(rows, i0, j0, size) if size <= MAX_LEAF else None
        if label is None:
            half = size // 2
            stack += [
                (i0, j0, half),
                (i0 + half, j0, half),
                (i0, j0 + half, half),
                (i0 + half, j0 + half, half),
            ]
        elif label:
            leaves[i0, j0] = (size, label)
    sizes = tuple(1 << k for k in range(top.bit_length() - 1, -1, -1))
    mesh = LayerMesh(leaves, origin, sizes)
    work = deque(sorted(leaves))
    while work:
        leaf = work.popleft()
        held = leaves.get(leaf)
        if held is None or held[0] < 4:
            continue
        size, label = held
        near = [found for direction in _SIDES for found, _ in mesh.side(leaf, size, direction)]
        if all(leaves[found][0] * 2 >= size for found in near):
            continue
        half = size // 2
        del leaves[leaf]
        children = [(leaf[0], leaf[1]), (leaf[0] + half, leaf[1]), (leaf[0], leaf[1] + half)]
        children.append((leaf[0] + half, leaf[1] + half))
        for child in children:
            leaves[child] = (half, label)
        work.extend(children)
        work.extend(found for found in near if leaves.get(found, (0,))[0] > half)
    return mesh


def mesh_layers(items: Mapping[str, Sequence[tuple[Key, Spans]]]) -> dict[str, LayerMesh]:
    """The mesh of each layer of ``items`` (keys with their runs), over one square that holds them all."""
    rows = {layer: _label_rows(held) for layer, held in items.items()}
    bounds = [
        (
            min(starts[0] for starts, _, _ in held.values()),
            min(held),
            max(ends[-1] for _, ends, _ in held.values()),
            max(held),
        )
        for held in rows.values()
        if held
    ]
    if not bounds:
        return {}
    i0, j0 = min(b[0] for b in bounds), min(b[1] for b in bounds)
    span = max(max(b[2] for b in bounds) - i0, max(b[3] for b in bounds) - j0) + 1
    top = 1 << max(0, (span - 1).bit_length())
    return {layer: layer_mesh(held, (i0, j0), top) for layer, held in sorted(rows.items())}


def contact_free(label: Label) -> bool:
    return not any(key[0] in CONTACTS for key in label)


def mesh_edges(mesh: LayerMesh) -> list[tuple[Leaf, Leaf, int, int, int]]:
    """Each pair of leaves that share a side: ``(a, b, size of a, size of b, shared length)``, once."""
    found: list[tuple[Leaf, Leaf, int, int, int]] = []
    for leaf in sorted(mesh.leaves):
        size = mesh.leaves[leaf][0]
        for direction in _SIDES[:2]:
            for near, shared in mesh.side(leaf, size, direction):
                found.append((leaf, near, size, mesh.leaves[near][0], shared))
    return found


def weight(a: int, b: int, shared: int, contact_a: bool, contact_b: bool, conductance: int) -> int:
    """The weight, ``SCALE_K`` times ``conductance·s/d``, of the side shared by two leaves of sizes ``a``
    and ``b``; a contact's edge lies at the face of the free leaf."""
    if contact_a and not contact_b:
        return round(Fraction(SCALE_K * conductance * shared * 2, b))
    if contact_b and not contact_a:
        return round(Fraction(SCALE_K * conductance * shared * 2, a))
    return round(Fraction(SCALE_K * conductance * shared * 2, a + b))


def hanging(mesh: LayerMesh, conductance: int) -> list[tuple[tuple[Leaf, Leaf], int]]:
    """The corrections of the two-point flux at each side of a leaf ``B`` of size ``2s`` that two free leaves
    ``S1`` and ``S2`` of size ``s`` share: their links to ``B`` carry, besides the flux across the side, a
    current along it, as a conductance ``g1·g2/(g1 + g2)`` from ``S1`` to ``S2`` through ``B``. That much is
    taken off the link ``S1–S2``, so that a potential linear in ``x`` and ``y`` solves the mesh exactly, as
    it solves the raster (Fenolite's own correction, ``INFERRED``)."""
    found: list[tuple[tuple[Leaf, Leaf], int]] = []
    for leaf in sorted(mesh.leaves):
        size, label = mesh.leaves[leaf]
        if size < 2 or not contact_free(label):
            continue
        for direction in _SIDES:
            near = mesh.side(leaf, size, direction)
            if len(near) != 2 or any(mesh.leaves[other][0] * 2 != size for other, _ in near):
                continue
            if not all(contact_free(mesh.leaves[other][1]) for other, _ in near):
                continue
            g1, g2 = (weight(size, size // 2, shared, False, False, conductance) for _, shared in near)
            found.append(((near[0][0], near[1][0]), round(Fraction(g1 * g2, g1 + g2))))
    return found


__all__ = [
    "hanging",
    "SCALE_K",
    "LayerMesh",
    "Spans",
    "cell_spans",
    "contact_free",
    "layer_mesh",
    "mesh_edges",
    "mesh_layers",
    "ring_spans",
    "weight",
]

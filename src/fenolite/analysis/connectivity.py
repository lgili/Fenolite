# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The open connections of each net of a board (capability board-analyses, "Open connections of a net";
user guide ``docs/analyses.md``, "Open connections").

The copper of a net (``net_copper``: the shapes of the copper check) is joined where it touches on one
copper layer, by ``geometry.touch_groups``, the union that ``checks.equivalence.routing.pieces`` uses too.
The shapes of one via, and of one pad, are one item across their layers; every fill polygon is an item of
its own. An island counts when it holds a pad, a track, an arc or a via; islands of fills alone are counted
apart and join nothing. The open connections of a net are the minimum spanning tree over its counted
islands, each edge between the nearest anchors of two islands: a pad's position, the two ends of a track or
an arc, a via's position.

Everything is integer arithmetic, and the report does not depend on the order of the board's items. The
count per net is what KiCad's DRC reports as unconnected items (``H-K-CONN-PARITY``); the two ends of a
connection are Fenolite's rule, not KiCad's.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from math import isqrt

from fenolite.analysis.codes import issue
from fenolite.analysis.copper import CopperShape, net_copper
from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry import Thick, touch_groups
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-CONN-PARITY",))
"""The level of the register row ``H-K-CONN-PARITY``: the counts per net against KiCad's unconnected
items, on the bench and on the corpus. A report that left an item out is ``UNVERIFIED``."""
COUNTED = ("pad", "track", "arc", "via")
"""The kinds that make an island count; a fill does not."""
_SEP = "\x00"


@dataclass(frozen=True, slots=True)
class LinkEnd:
    """One end of an open connection: the anchor of a copper item. ``where`` is ``REF-PIN`` for a pad and
    the item's locator otherwise; ``layers`` are the copper layers the item is on."""

    kind: str
    where: str
    position: Point
    layers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OpenConnection:
    """A connection that copper does not make: the nearest anchors of two islands, ``a`` the smaller end,
    and their straight distance in nanometres, rounded to the nearest integer."""

    a: LinkEnd
    b: LinkEnd
    length: int


@dataclass(frozen=True, slots=True)
class NetConnectivity:
    """The islands of one net. ``pads`` holds, per counted island, its pads as sorted ``REF-PIN`` texts
    (an island without a pad gives ``()``), the islands sorted; ``islands`` is their number,
    ``fill_islands`` the number of islands of fills alone, ``open`` the ``islands − 1`` open connections
    and ``unsupported`` the number of items of the net that could not be shaped."""

    name: str
    pads: tuple[tuple[str, ...], ...]
    islands: int
    fill_islands: int = 0
    open: tuple[OpenConnection, ...] = ()
    unsupported: int = 0


@dataclass(frozen=True, slots=True)
class ConnectivityReport:
    """One row per net that has a counted island, sorted by name; the issues; the evidence."""

    nets: tuple[NetConnectivity, ...] = ()
    issues: tuple[Issue, ...] = ()
    evidence: Evidence = EVIDENCE

    def open_nets(self) -> tuple[str, ...]:
        """The names of the nets that have at least one open connection, sorted."""
        return tuple(net.name for net in self.nets if net.open)

    def net(self, name: str) -> NetConnectivity | None:
        """The row of the net ``name``, or ``None``."""
        return next((net for net in self.nets if net.name == name), None)

    @property
    def total(self) -> int:
        """The number of open connections of the report."""
        return sum(len(net.open) for net in self.nets)


@dataclass(slots=True)
class _Item:
    kind: str
    where: str
    shapes: list[tuple[str, Thick]]
    anchors: tuple[Point, ...] = ()


_Anchors = dict[tuple[str, str], tuple[Point, ...]]
_Island = tuple[tuple[str, ...], list[LinkEnd]]


def _end_key(end: LinkEnd) -> tuple[str, Point, str, tuple[str, ...]]:
    return (end.where, end.position, end.kind, end.layers)


def _round_sqrt(n: int) -> int:
    return (isqrt(4 * n) + 1) // 2


def _pad_where(record: BoardPad) -> str:
    holder = record.ref or record.footprint_id
    return f"{holder}-{record.number}" if record.number else holder


def _anchors(design: Design, pads: Sequence[BoardPad] | None) -> _Anchors:
    """The anchors per kind and entity id; a pad's id is followed by its ``where`` text."""
    found: _Anchors = {}
    board = design.board
    if board is None:
        return found
    for track in board.tracks:
        found["track", track.id] = (track.start, track.end)
    for arc in board.arcs:
        found["arc", arc.id] = (arc.start, arc.end)
    for via in board.vias:
        found["via", via.id] = (via.position,)
    for record in pads or ():
        found["pad", f"{record.pad_id}{_SEP}{_pad_where(record)}"] = (record.position,)
    return found


def _items(shapes: Sequence[CopperShape], anchors: _Anchors) -> list[_Item]:
    """The items of one net: the shapes of a pad, a via, a track or an arc joined by entity; one item per
    fill polygon. The order is that of a sort, so the board's order does not show."""
    grouped: dict[tuple[str, str, str], _Item] = {}
    fills: list[_Item] = []
    for shape in shapes:
        if shape.kind == "fill":
            fills.append(_Item("fill", shape.where, [(shape.layer, shape.shape)]))
            continue
        key = (shape.kind, shape.entity_id, shape.where)
        item = grouped.get(key)
        if item is None:
            ident = f"{shape.entity_id}{_SEP}{shape.where}" if shape.kind == "pad" else shape.entity_id
            item = grouped[key] = _Item(shape.kind, shape.where, [], anchors.get((shape.kind, ident), ()))
        item.shapes.append((shape.layer, shape.shape))
    return [grouped[key] for key in sorted(grouped)] + fills


def _ends(item: _Item) -> list[LinkEnd]:
    layers = tuple(dict.fromkeys(layer for layer, _ in item.shapes))
    return [LinkEnd(item.kind, item.where, at, layers) for at in dict.fromkeys(item.anchors)]


def _nearest(one: Sequence[LinkEnd], other: Sequence[LinkEnd]) -> tuple[int, LinkEnd, LinkEnd] | None:
    """The nearest pair of anchors of two islands: the squared distance and the two ends, the smaller
    first. Ties go to the smaller pair of ``where`` texts, then of positions."""
    best: tuple[int, tuple[object, ...], LinkEnd, LinkEnd] | None = None
    for first in one:
        for second in other:
            d2 = (first.position.x - second.position.x) ** 2 + (first.position.y - second.position.y) ** 2
            if best is not None and d2 > best[0]:
                continue
            a, b = sorted((first, second), key=_end_key)
            rank = (a.where, b.where, a.position, b.position, a.kind, b.kind, a.layers, b.layers)
            if best is None or (d2, rank) < (best[0], best[1]):
                best = (d2, rank, a, b)
    return None if best is None else (best[0], best[2], best[3])


def _spanning(islands: Sequence[Sequence[LinkEnd]]) -> tuple[OpenConnection, ...]:
    """Kruskal's tree over the islands, by the edge of the nearest anchors of each pair."""
    edges: list[tuple[int, tuple[object, ...], int, int, LinkEnd, LinkEnd]] = []
    for i, one in enumerate(islands):
        for j in range(i + 1, len(islands)):
            found = _nearest(one, islands[j])
            if found is not None:
                d2, a, b = found
                rank = (a.where, b.where, a.position, b.position, a.kind, b.kind, a.layers, b.layers)
                edges.append((d2, rank, i, j, a, b))
    edges.sort(key=lambda edge: (edge[0], edge[1]))
    parent = list(range(len(islands)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    tree: list[OpenConnection] = []
    for d2, _, i, j, a, b in edges:
        root_a, root_b = find(i), find(j)
        if root_a != root_b:
            parent[max(root_a, root_b)] = min(root_a, root_b)
            tree.append(OpenConnection(a, b, _round_sqrt(d2)))
    return tuple(tree)


def _islands(shapes: Sequence[CopperShape], anchors: _Anchors) -> tuple[list[_Island], int]:
    """The counted islands of one net (their pads and their ends, sorted) and the number of islands of
    fills alone."""
    items = _items(shapes, anchors)
    groups: dict[int, list[_Item]] = defaultdict(list)
    for item, root in zip(items, touch_groups([item.shapes for item in items]), strict=True):
        groups[root].append(item)
    counted: list[_Island] = []
    fill_islands = 0
    for members in groups.values():
        if not any(item.kind in COUNTED for item in members):
            fill_islands += 1
            continue
        pads = tuple(sorted(item.where for item in members if item.kind == "pad"))
        ends = sorted((end for item in members for end in _ends(item)), key=_end_key)
        counted.append((pads, ends))
    counted.sort(key=lambda island: (island[0], [_end_key(end) for end in island[1]]))
    return counted, fill_islands


def _unsupported(
    design: Design, pads: Sequence[BoardPad] | None, shaped: Collection[tuple[str, str]]
) -> Counter[str]:
    """The number of items per net name that ``net_copper`` could not shape."""
    board = design.board
    counts: Counter[str] = Counter()
    if board is None:
        return counts
    names = {net.id: net.name for net in design.circuit.nets}

    def miss(net_id: str | None) -> None:
        if net_id is not None:
            counts[names.get(net_id, net_id)] += 1

    for kind, held in (("track", board.tracks), ("arc", board.arcs), ("via", board.vias)):
        for entity in held:
            if (kind, entity.id) not in shaped:
                miss(entity.net_id)
    if pads is None:
        for footprint in board.footprints:
            for pad in footprint.pads:
                if pad.kind != "np_thru_hole" and any(layer.endswith(".Cu") for layer in pad.layers):
                    miss(pad.net_id)
    else:
        for record in pads:
            if record.kind == "np_thru_hole" or ("pad", record.pad_id) in shaped:
                continue
            if record.copper or any(layer.endswith(".Cu") for layer in record.layers):
                miss(record.net_id)
    return counts


def connectivity(
    design: Design, *, pads: Sequence[BoardPad] | None, nets: Collection[str] | None = None
) -> ConnectivityReport:
    """The islands and the open connections of each net of ``design.board``. ``pads`` are the board-frame
    pad records (``None`` when the caller has none: every pad is then unsupported); ``nets`` limits the
    report to the nets of those names."""
    copper = net_copper(design, pads=pads)
    anchors = _anchors(design, pads)
    wanted = None if nets is None else set(nets)
    missing: Counter[str] = Counter()
    if copper.unsupported:
        shaped = {(shape.kind, shape.entity_id) for held in copper.by_net.values() for shape in held}
        missing = _unsupported(design, pads, shaped)
    rows: list[NetConnectivity] = []
    for name, shapes in copper.by_net.items():
        if wanted is not None and name not in wanted:
            continue
        counted, fill_islands = _islands(shapes, anchors)
        if not counted:
            continue
        rows.append(
            NetConnectivity(
                name=name,
                pads=tuple(island[0] for island in counted),
                islands=len(counted),
                fill_islands=fill_islands,
                open=_spanning([island[1] for island in counted]),
                unsupported=missing.get(name, 0),
            )
        )
    issues = tuple(
        issue(
            "analysis.item-unsupported",
            f"{count} {kind} item(s) could not be shaped and take no part in the open connections",
            where=kind,
            hint="the nets of these items may show more open connections than the board has",
        )
        for kind, count in sorted(copper.unsupported.items())
    )
    evidence = Evidence(Level.UNVERIFIED, hypotheses=EVIDENCE.hypotheses) if issues else EVIDENCE
    return ConnectivityReport(tuple(sorted(rows, key=lambda row: row.name)), issues, evidence)


__all__ = [
    "COUNTED",
    "EVIDENCE",
    "ConnectivityReport",
    "LinkEnd",
    "NetConnectivity",
    "OpenConnection",
    "connectivity",
]

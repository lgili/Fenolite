# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net lengths: the total as a tool counts it, and the pin-to-pin lengths along the copper (capability
board-analyses, "Net length report", "Pin-to-pin length", "Pair skew in the length report"; user guide
``docs/analyses.md``, "Length").

The total of a net is a fact of the tool the board is judged by, so it comes from ``LengthFacts``
(``backends.base``); without facts it is the routed length alone. A path is found here: the copper of a net
becomes a graph of item ends, vias and pads, and the shortest path from a start pad to every other pad is
searched on integer weights (``H-G-NETLEN-PATH``).

Joins. An item end joins a track, an arc, a via or a pad of its net when it lies within that item's copper
on a shared copper layer; inside the body of a track or an arc it splits that item at the nearest point of
its centre line. A pad or a via whose copper touches the body of an item that has no end inside it joins
that item at the point of the centre line nearest to its position. A via inside a pad joins the pad. Tracks
and arcs that only cross are not joined.
"""

from __future__ import annotations

import heapq
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from fnmatch import fnmatchcase

from fenolite.analysis.codes import issue
from fenolite.analysis.copper import ARC_TOL_NM, copper_layers
from fenolite.analysis.report import LOWERING, mm, sorted_issues
from fenolite.backends.base import BoardPad, LengthFacts
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.geometry import Arc as GeoArc
from fenolite.geometry import (
    BBox,
    GeometryError,
    SpatialIndex,
    Thick,
    arc_length,
    arc_length_to,
    segment_length,
    segment_length_to,
    thick_bbox,
    thick_touch,
)
from fenolite.model.board import Arc, Board, Track, Via
from fenolite.model.design import Design
from fenolite.model.findings import Findings

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-NETLEN-PATH",))
"""No tool prints a pin-to-pin length, so the paths stay ``INFERRED``."""


@dataclass(frozen=True, slots=True)
class PathRow:
    """The shortest path along the copper from the start pad of a net to the pad ``end`` (``REF-PIN``):
    its length with the die lengths of both pads, the vias it changes layer through and the copper layers
    it runs on, in order. ``length`` is ``None`` when the copper does not join the two pads."""

    end: str
    length: Nm | None
    vias: int = 0
    layers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LengthRow:
    """The length of one net: the parts and the total of the facts, the start pad, the path to every other
    pad, and the length of the copper that lies on no path."""

    net: str
    routed: Nm
    vias: Nm
    die: Nm
    total: Nm
    via_count: int
    start: str | None = None
    paths: tuple[PathRow, ...] = ()
    off_path: Nm = 0


@dataclass(frozen=True, slots=True)
class PairRow:
    """The skew of a differential pair: ``skew`` is ``total_p − total_n``, so a negative skew means that
    ``p`` is the shorter net; ``path_skew`` is the same difference of the two pin-to-pin lengths when each
    net has exactly two pads and both paths exist."""

    name: str
    p: str
    n: str
    total_p: Nm
    total_n: Nm
    skew: Nm
    path_skew: Nm | None = None


@dataclass(frozen=True, slots=True)
class LengthReport:
    """Rows sorted by net name, pair rows by name, issues by code, ``where`` and message."""

    rows: tuple[LengthRow, ...] = ()
    pairs: tuple[PairRow, ...] = ()
    issues: tuple[Issue, ...] = ()
    summary: Mapping[str, object] = field(default_factory=lambda: {})
    evidence: Evidence = EVIDENCE

    def findings(self) -> Findings:
        """The issues as a findings layer, for a caller that attaches them to ``Design.findings``."""
        return Findings(issues=self.issues)


# --- the copper of one net --------------------------------------------------------------------------

_Node = tuple[str, int, object]
"""``("p", pad index, None)``, ``("v", via index, layer)`` or ``("i", item index, position)``."""
_Tag = tuple[str, int, int, int]
"""What an edge runs along: ``("i", item index, from, to)``, ``("v", via index, 0, 0)`` or ``("", …)``."""
_JOIN: _Tag = ("", 0, 0, 0)


def _point(point: Point) -> Thick:
    return Thick((point, point), 0)


@dataclass(frozen=True, slots=True)
class _Item:
    """A track or an arc: its entity, its copper and its centre-line length."""

    entity: Track | Arc
    layer: str
    shape: Thick
    box: BBox
    length: int

    def ends(self) -> tuple[tuple[int, Point], tuple[int, Point]]:
        return (0, self.entity.start), (self.length, self.entity.end)

    def position(self, at: Point) -> int:
        """The length from the start to the point of the centre line nearest to ``at``."""
        entity = self.entity
        if isinstance(entity, Arc):
            return min(arc_length_to(entity.start, entity.mid, entity.end, at), self.length)
        return min(segment_length_to(entity.start, entity.end, at), self.length)


def _item(entity: Track | Arc) -> _Item | None:
    width = max(entity.width, 0)
    try:
        if isinstance(entity, Arc):
            try:
                core = GeoArc(entity.start, entity.mid, entity.end).polygonize(ARC_TOL_NM)
            except GeometryError:
                core = (entity.start, entity.end)
            shape = Thick(core, width) if len(set(core)) > 1 else _point(entity.start)
            length = arc_length(entity.start, entity.mid, entity.end)
        else:
            shape = Thick((entity.start, entity.end), width)
            length = segment_length(entity.start, entity.end)
    except (GeometryError, ValueError):
        return None
    return _Item(entity, entity.layer, shape, thick_bbox(shape), length)


def _span(copper: Sequence[str], via: Via) -> tuple[str, ...]:
    ends = [copper.index(name) for name in via.layers if name in copper]
    if via.via_type == "through" or len(ends) < 2:
        return tuple(copper)
    return tuple(copper[min(ends) : max(ends) + 1])


def pad_name(pad: BoardPad) -> str:
    """``REF-PIN``."""
    return f"{pad.ref}-{pad.number}"


@dataclass(slots=True)
class _Net:
    """The graph of one net: zero-weight joins, item parts and layer changes through vias."""

    items: list[_Item]
    vias: list[Via]
    pads: list[BoardPad]
    copper: tuple[str, ...]
    depths: Mapping[str, Nm]
    cuts: list[set[int]] = field(default_factory=lambda: [])
    joins: list[tuple[_Node, _Node]] = field(default_factory=lambda: [])
    edges: dict[_Node, list[tuple[_Node, int, _Tag]]] = field(default_factory=lambda: {})
    unknown: int = 0

    def join(self, a: _Node, b: _Node) -> None:
        self.joins.append((a, b))

    def _edge(self, a: _Node, b: _Node, weight: int, tag: _Tag) -> None:
        self.edges.setdefault(a, []).append((b, weight, tag))
        self.edges.setdefault(b, []).append((a, weight, tag))

    def build(self) -> None:
        items, vias, pads = self.items, self.vias, self.pads
        self.cuts = [{0, item.length} for item in items]
        by_layer: dict[str, list[int]] = {}
        for index, item in enumerate(items):
            by_layer.setdefault(item.layer, []).append(index)
        trees: dict[str, SpatialIndex[int]] = {
            layer: SpatialIndex[int].build((items[i].box, i) for i in indices)
            for layer, indices in by_layer.items()
        }
        discs: list[Thick | None] = []
        for via in vias:
            try:
                discs.append(
                    Thick((via.position,), via.diameter) if via.diameter > 0 else _point(via.position)
                )
            except (GeometryError, ValueError):
                discs.append(None)
        spans = [_span(self.copper, via) for via in vias]
        pad_shapes: list[list[tuple[str, Thick]]] = []
        for pad in pads:
            shapes: list[tuple[str, Thick]] = []
            for entry in pad.copper:
                try:
                    shapes.append((entry.layer, Thick(entry.core, entry.width, entry.filled)))
                except (GeometryError, ValueError):
                    continue
            pad_shapes.append(shapes)
        ended: set[tuple[str, int, int]] = (
            set()
        )  # (junction kind, junction index, item index): an end is inside
        # 1. item ends
        for index, item in enumerate(items):
            for position, at in item.ends():
                probe = _point(at)
                node: _Node = ("i", index, position)
                for v, disc in enumerate(discs):
                    if disc is not None and item.layer in spans[v] and thick_touch(probe, disc):
                        self.join(node, ("v", v, item.layer))
                        ended.add(("v", v, index))
                for p, shapes in enumerate(pad_shapes):
                    if any(layer == item.layer and thick_touch(probe, shape) for layer, shape in shapes):
                        self.join(node, ("p", p, None))
                        ended.add(("p", p, index))
                tree = trees[item.layer]
                for other in tree.query(BBox(at.x, at.y, at.x, at.y)):
                    if other != index and thick_touch(probe, items[other].shape):
                        cut = items[other].position(at)
                        self.cuts[other].add(cut)
                        self.join(node, ("i", other, cut))
        # 2. pads and vias on the body of an item that has no end inside them
        for p, shapes in enumerate(pad_shapes):
            for layer, shape in shapes:
                tree = trees.get(layer)
                if tree is None:
                    continue
                for index in tree.query(thick_bbox(shape)):
                    if ("p", p, index) not in ended and thick_touch(shape, items[index].shape):
                        cut = items[index].position(pads[p].position)
                        self.cuts[index].add(cut)
                        self.join(("p", p, None), ("i", index, cut))
        for v, disc in enumerate(discs):
            if disc is None:
                continue
            for layer in spans[v]:
                tree = trees.get(layer)
                if tree is not None:
                    for index in tree.query(thick_bbox(disc)):
                        if ("v", v, index) not in ended and thick_touch(disc, items[index].shape):
                            cut = items[index].position(vias[v].position)
                            self.cuts[index].add(cut)
                            self.join(("v", v, layer), ("i", index, cut))
                # 3. a via inside a pad
                for p, shapes in enumerate(pad_shapes):
                    if any(name == layer and thick_touch(disc, shape) for name, shape in shapes):
                        self.join(("p", p, None), ("v", v, layer))
        # the edges
        for a, b in self.joins:
            self._edge(a, b, 0, _JOIN)
        for index, cuts in enumerate(self.cuts):
            ordered = sorted(cuts)
            for low, high in zip(ordered, ordered[1:], strict=False):
                self._edge(("i", index, low), ("i", index, high), high - low, ("i", index, low, high))
        for v, span in enumerate(spans):
            for upper, lower in zip(span, span[1:], strict=False):
                known = upper in self.depths and lower in self.depths
                weight = abs(self.depths[upper] - self.depths[lower]) if known else 0
                self._edge(("v", v, upper), ("v", v, lower), weight, ("v", v, 0, 0))

    def _tag_id(self, tag: _Tag) -> str | None:
        if tag[0] == "i":
            return self.items[tag[1]].entity.id
        return self.vias[tag[1]].id if tag[0] == "v" else None

    def _ids(self, node: _Node, came: Mapping[_Node, tuple[_Node, _Tag]], last: _Tag = _JOIN) -> list[str]:
        """The sorted ids of the tracks, arcs and vias on the path to ``node``, and of ``last``."""
        found = {self._tag_id(last)}
        while node in came:
            node, tag = came[node]
            found.add(self._tag_id(tag))
        return sorted(name for name in found if name is not None)

    def search(self, start: _Node) -> tuple[dict[_Node, int], dict[_Node, tuple[_Node, _Tag]]]:
        """Dijkstra on integer weights; of two paths of equal length, the one whose sorted item ids come
        first is kept."""
        dist: dict[_Node, int] = {start: 0}
        came: dict[_Node, tuple[_Node, _Tag]] = {}
        done: set[_Node] = set()
        order = 0
        heap: list[tuple[int, int, _Node]] = [(0, order, start)]
        while heap:
            reached, _, node = heapq.heappop(heap)
            if node in done or reached != dist[node]:
                continue
            done.add(node)
            for other, weight, tag in self.edges.get(node, ()):
                if other in done:
                    continue
                length = reached + weight
                known = dist.get(other)
                if known is not None and length > known:
                    continue
                if known is not None and length == known:
                    if came.get(other, (None,))[0] == node:
                        continue
                    if self._ids(node, came, tag) >= self._ids(other, came):
                        continue
                dist[other] = length
                came[other] = (node, tag)
                order += 1
                heapq.heappush(heap, (length, order, other))
        return dist, came


def _trace(
    net: _Net, node: _Node, came: Mapping[_Node, tuple[_Node, _Tag]]
) -> tuple[int, tuple[str, ...], set[tuple[int, int, int]]]:
    """The vias a path changes layer through, the layers it runs on from the start, and its item parts."""
    vias: set[int] = set()
    layers: list[str] = []
    parts: set[tuple[int, int, int]] = set()
    while node in came:
        node, tag = came[node]
        if tag[0] == "v":
            vias.add(tag[1])
        elif tag[0] == "i":
            parts.add((tag[1], tag[2], tag[3]))
            layer = net.items[tag[1]].layer
            if not layers or layers[-1] != layer:
                layers.append(layer)
    return len(vias), tuple(reversed(layers)), parts


# --- the report -------------------------------------------------------------------------------------


def _pad_order(pad: BoardPad) -> tuple[str, str, str]:
    return pad.ref, pad.number, pad.pad_id


def _start(pads: Sequence[BoardPad], starts: Collection[str]) -> int | None:
    """The index of the start pad among pads sorted by ``(ref, number)``: the first whose ``ref`` or
    ``REF-PIN`` is in ``starts``, else the first."""
    if not pads:
        return None
    for index, pad in enumerate(pads):
        if pad.ref in starts or pad_name(pad) in starts:
            return index
    return 0


def _measure_net(
    name: str,
    board: Board,
    net_id: str,
    pads: Sequence[BoardPad],
    facts: LengthFacts | None,
    starts: Collection[str],
    issues: list[Issue],
) -> tuple[LengthRow, int]:
    """The row of one net, and the count of its vias whose height is unknown."""
    copper = copper_layers(board)
    on_copper = set(copper)
    linear: list[Track | Arc] = [
        *(t for t in board.tracks if t.net_id == net_id and t.layer in on_copper),
        *(a for a in board.arcs if a.net_id == net_id and a.layer in on_copper),
    ]
    vias = [via for via in board.vias if via.net_id == net_id]
    own = sorted((pad for pad in pads if pad.net_id == net_id), key=_pad_order)
    routed = sum(
        arc_length(e.start, e.mid, e.end) if isinstance(e, Arc) else segment_length(e.start, e.end)
        for e in linear
    )
    length = facts.nets.get(name) if facts is not None else None
    counted = facts is not None and length is not None and facts.count_vias
    depths: Mapping[str, Nm] = facts.depths if facts is not None and counted else {}
    unknown = 0
    if (
        facts is None
        or length is None
        or (facts.count_vias and any(layer not in facts.depths for layer in copper))
    ):
        unknown = len(vias)
    die: Mapping[str, Nm] = facts.die if facts is not None else {}
    items = [made for made in map(_item, linear) if made is not None]
    if len(items) != len(linear):
        issues.append(
            issue(
                "analysis.item-unsupported",
                f"net {name}: {len(linear) - len(items)} track(s) or arc(s) have a shape the paths cannot "
                "use; they count in the routed length only",
                where=name,
            )
        )
    graph = _Net(items, vias, own, copper, depths)
    graph.build()
    start = _start(own, starts)
    paths: list[tuple[str, str, PathRow]] = []
    used: set[tuple[int, int, int]] = set()
    opened: list[str] = []
    if start is not None:
        dist, came = graph.search(("p", start, None))
        for index, pad in enumerate(own):
            if index == start:
                continue
            node: _Node = ("p", index, None)
            if node not in dist:
                opened.append(pad_name(pad))
                paths.append((pad_name(pad), pad.pad_id, PathRow(pad_name(pad), None)))
                continue
            count, layers, parts = _trace(graph, node, came)
            used |= parts
            total = dist[node] + die.get(own[start].pad_id, 0) + die.get(pad.pad_id, 0)
            paths.append((pad_name(pad), pad.pad_id, PathRow(pad_name(pad), total, count, layers)))
    off_path = 0
    if start is not None:
        for index, cuts in enumerate(graph.cuts):
            ordered = sorted(cuts)
            for low, high in zip(ordered, ordered[1:], strict=False):
                if (index, low, high) not in used:
                    off_path += high - low
    if opened:
        issues.append(
            issue(
                "analysis.length-open",
                f"net {name}: the copper does not join {pad_name(own[start or 0])} to "
                + ", ".join(sorted(opened)),
                where=name,
                hint="route the open connection, or pass --from to measure from another pad",
            )
        )
    if off_path > 0:
        issues.append(
            issue(
                "analysis.length-stub",
                f"net {name}: {mm(off_path)} mm of copper lies on no path from {pad_name(own[start or 0])}; "
                "the total counts it",
                where=name,
            )
        )
    row = LengthRow(
        net=name,
        routed=length.routed if length is not None else routed,
        vias=length.vias if length is not None else 0,
        die=length.die if length is not None else 0,
        total=length.total if length is not None else routed,
        via_count=length.via_count if length is not None else len(vias),
        start=pad_name(own[start]) if start is not None else None,
        paths=tuple(path for _, _, path in sorted(paths, key=lambda found: found[:2])),
        off_path=off_path,
    )
    return row, unknown


def measure_lengths(
    design: Design,
    *,
    pads: Sequence[BoardPad] | None,
    facts: LengthFacts | None = None,
    nets: Sequence[str] = (),
    starts: Collection[str] = (),
) -> LengthReport:
    """The length of each net of ``design`` whose name matches a glob of ``nets`` and that has a pad, a
    track, an arc or a via on the board.

    ``pads`` are the pads in the board frame (``None``: no pad, so no path). With ``facts``, the parts and
    the total of a net are the facts'; without, the total is the routed length and one
    ``analysis.input-missing`` warning counts the vias whose height is unknown. ``starts`` holds the
    ``REF`` or ``REF-PIN`` texts that choose a start pad. Pure: equal inputs give equal reports."""
    board = design.board
    issues: list[Issue] = []
    rows: list[LengthRow] = []
    unknown = 0
    known = list(pads or ())
    if board is not None and nets:
        present = {
            item.net_id for item in (*board.tracks, *board.arcs, *board.vias) if item.net_id is not None
        } | {pad.net_id for pad in known if pad.net_id is not None}
        chosen = sorted(
            (
                net
                for net in design.circuit.nets
                if net.id in present and any(fnmatchcase(net.name, g) for g in nets)
            ),
            key=lambda net: net.name,
        )
        for net in chosen:
            row, missing = _measure_net(net.name, board, net.id, known, facts, starts, issues)
            rows.append(row)
            unknown += missing
    if not rows:
        issues.append(
            issue(
                "analysis.input-missing",
                "net selection: no net with copper or a pad matches "
                + (", ".join(repr(g) for g in nets) if nets else "an empty selection"),
                hint="pass --net GLOB with the name of a net of the board",
            )
        )
    elif facts is None or unknown:
        issues.append(
            issue(
                "analysis.input-missing",
                f"length facts: the height of {unknown} via(s) is unknown, so the totals and the paths count "
                "no via height" + ("" if facts is not None else " and no die length"),
                hint="measure a KiCad board, whose backend gives the length facts",
            )
        )
    ordered = sorted_issues(issues)
    combined = Evidence.combine(EVIDENCE, *((facts.evidence,) if facts is not None else ()))
    if any(found.code in LOWERING for found in ordered):
        combined = Evidence(Level.UNVERIFIED, hypotheses=combined.hypotheses)
    summary: dict[str, object] = {
        "nets": len(rows),
        "major": facts.major if facts is not None else None,
        "stackup": facts.stackup if facts is not None else None,
        "count_vias": facts.count_vias if facts is not None else None,
    }
    return LengthReport(tuple(rows), (), ordered, summary, combined)


__all__ = ["EVIDENCE", "LengthReport", "LengthRow", "PairRow", "PathRow", "measure_lengths", "pad_name"]

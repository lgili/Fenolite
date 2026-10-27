# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Ground ties, sense nets and isolation islands (capability board-analyses, "Ground ties" and "Sense
nets and isolation islands"; user guide ``docs/analyses.md``, "Ground ties").

A tie is proved by removing exactly its own copper and looking at what is left. The copper graph of the
tie's nets has one node per pad, track, arc and via (their shapes on every layer) and one per filled
polygon of a zone; two nodes are joined when shapes of theirs on one layer touch (``thick_touch``, the
predicate of ``touch_groups``). The tie's nodes are named by id: a part's pads (``--tie REF``), or tracks,
arcs, vias and zones by model id, KiCad uuid or locator (``--tie-item``). Nothing is removed because it
lies near a tie or inside its box. A test that removes copper by area removes the copper of the other
side too, and so tests another board.

The neighbours of a tie are the nodes that touch it. After the removal, the groups are the connected
parts of the graph that hold a neighbour; the tie splits the net when there are two or more. When there
is one, another path joins the two sides, and the shortest one (in nodes) is given: the sides of a part
are its pads by net, and the sides of copper items are the free ends of their chain. The domains of
``--domains`` name pads by ``REF-PIN`` patterns: a group after a split that holds pads of both domains has
an extra joint.

The isolation islands read no copper: the nets of the circuit are joined by every part but the barrier
parts, as a part joins the nets of its pins. Everything is integer arithmetic, and the report does not
depend on the order of the board's items.
"""

from __future__ import annotations

import fnmatch
from collections import defaultdict, deque
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from fenolite.analysis.codes import issue
from fenolite.analysis.copper import ARC_TOL_NM, CopperShape, net_copper
from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry import SpatialIndex, Thick, thick_bbox, thick_touch
from fenolite.model.base import Entity
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-TIES",))
"""Graph reasoning on the board's own copper, proved on authored benches; no tool confirms it."""
_POINT = 2
"""The width of the disc that stands for an end point of a tie (1 nm around the point)."""


@dataclass(frozen=True, slots=True)
class Tie:
    """A tie to prove: ``part`` names a part by its reference, else ``items`` names copper items."""

    name: str
    part: str | None = None
    items: tuple[str, ...] = ()

    @classmethod
    def of_part(cls, ref: str) -> Tie:
        return cls(ref, part=ref)

    @classmethod
    def of_items(cls, ids: Sequence[str]) -> Tie:
        return cls(",".join(ids), items=tuple(ids))


@dataclass(frozen=True, slots=True)
class TieItem:
    """A node of the copper graph: ``kind`` (pad, track, arc, via or fill), the model id of its entity
    (a pad's id, a zone's id for a fill), ``where`` (``REF-PIN`` for a pad, else the locator) and its net;
    ``layer`` is the layer of a fill polygon, else empty."""

    kind: str
    id: str
    where: str
    net: str
    layer: str = ""


@dataclass(frozen=True, slots=True)
class TieRow:
    """The proof of one tie. ``removed`` are the nodes taken out, ``groups`` the pads of each group that
    holds a neighbour of the tie (sorted ``REF-PIN`` texts, the groups sorted), ``split`` whether there are
    two or more, ``path`` the shortest other path between the sides when there is one group, ``extra`` the
    pads of a domain found with the other domain, and ``zones`` whether the zones of the nets were
    ``filled``, ``unfilled`` (a zone without a fill: its copper is missing) or ``none``."""

    tie: str
    nets: tuple[str, ...]
    removed: tuple[TieItem, ...]
    groups: tuple[tuple[str, ...], ...]
    split: bool
    path: tuple[TieItem, ...] = ()
    extra: tuple[str, ...] = ()
    zones: str = "none"


@dataclass(frozen=True, slots=True)
class SenseRow:
    """One sense net: its copper nodes and the other-net nodes its copper touches."""

    net: str
    items: int
    shared: tuple[TieItem, ...] = ()


@dataclass(frozen=True, slots=True)
class Island:
    """Nets joined through parts that are not barriers, sorted, and the barrier parts with a pin on them."""

    nets: tuple[str, ...]
    barriers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TieReport:
    rows: tuple[TieRow, ...] = ()
    sense: tuple[SenseRow, ...] = ()
    issues: tuple[Issue, ...] = ()
    evidence: Evidence = EVIDENCE
    summary: Mapping[str, int] = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class IslandReport:
    islands: tuple[Island, ...] = ()
    issues: tuple[Issue, ...] = ()
    evidence: Evidence = EVIDENCE


@dataclass(slots=True)
class _Node:
    item: TieItem
    shapes: list[tuple[str, Thick]]
    anchors: tuple[Point, ...] = ()
    pad: BoardPad | None = None


class _Graph:
    """The nodes of some nets and their touches."""

    def __init__(self, nodes: list[_Node]) -> None:
        self.nodes = nodes
        self.edges: list[set[int]] = [set() for _ in nodes]
        keyed: dict[str, list[tuple[int, Thick]]] = defaultdict(list)
        for index, node in enumerate(nodes):
            for layer, shape in node.shapes:
                keyed[layer].append((index, shape))
        for shapes in keyed.values():
            tree = SpatialIndex[int].build((thick_bbox(shape), index) for index, shape in shapes)
            for p, q in tree.pairs():
                (first, one), (second, other) = shapes[p], shapes[q]
                if first != second and second not in self.edges[first] and thick_touch(one, other):
                    self.edges[first].add(second)
                    self.edges[second].add(first)

    def parts(self, removed: Collection[int]) -> list[int]:
        """The connected part of every node without ``removed``, as its smallest index (-1 when removed)."""
        part = [-1] * len(self.nodes)
        for start in range(len(self.nodes)):
            if start in removed or part[start] >= 0:
                continue
            part[start] = start
            todo = [start]
            while todo:
                for nxt in self.edges[todo.pop()]:
                    if nxt not in removed and part[nxt] < 0:
                        part[nxt] = start
                        todo.append(nxt)
        return part

    def path(self, starts: Iterable[int], goals: Collection[int], removed: Collection[int]) -> list[int]:
        """The shortest path in nodes from a start to a goal without ``removed``; ties go to the smaller
        indices, as the nodes are visited in order."""
        before: dict[int, int] = {}
        queue: deque[int] = deque()
        for start in sorted(starts):
            if start not in removed and start not in before:
                before[start] = start
                queue.append(start)
        while queue:
            at = queue.popleft()
            if at in goals:
                out = [at]
                while before[out[-1]] != out[-1]:
                    out.append(before[out[-1]])
                return out[::-1]
            for nxt in sorted(self.edges[at]):
                if nxt not in removed and nxt not in before:
                    before[nxt] = at
                    queue.append(nxt)
        return []


def _where(entity: Entity) -> str:
    provenance = entity.provenance
    return provenance.locator if provenance is not None and provenance.locator else entity.id


def _nodes(
    by_net: Mapping[str, Sequence[CopperShape]], design: Design, pads: Sequence[BoardPad]
) -> list[_Node]:
    """The nodes of the nets of ``by_net``: the shapes of a pad, a via, a track or an arc joined by entity,
    one node per fill polygon; sorted, so the board's order does not show."""
    board = design.board
    assert board is not None
    anchors: dict[str, tuple[Point, ...]] = {}
    for track in board.tracks:
        anchors[track.id] = (track.start, track.end)
    for arc in board.arcs:
        anchors[arc.id] = (arc.start, arc.end)
    for via in board.vias:
        anchors[via.id] = (via.position,)
    records = {record.pad_id: record for record in pads}
    grouped: dict[tuple[str, str, str, str], _Node] = {}
    fills: list[_Node] = []
    for net, shapes in by_net.items():
        for shape in shapes:
            if shape.kind == "fill":
                item = TieItem("fill", shape.entity_id, shape.where, net, shape.layer)
                fills.append(_Node(item, [(shape.layer, shape.shape)]))
                continue
            key = (shape.kind, shape.where, shape.entity_id, net)
            node = grouped.get(key)
            if node is None:
                record = records.get(shape.entity_id) if shape.kind == "pad" else None
                at = (record.position,) if record is not None else anchors.get(shape.entity_id, ())
                node = grouped[key] = _Node(
                    TieItem(shape.kind, shape.entity_id, shape.where, net), [], at, record
                )
            node.shapes.append((shape.layer, shape.shape))
    fills.sort(key=lambda node: (node.item.id, node.item.layer, node.shapes[0][1].core))
    return [grouped[key] for key in sorted(grouped)] + fills


def _names(design: Design) -> dict[str, set[str]]:
    """The names a user may give a track, an arc, a via or a zone: its model id, its native ids and its
    locator, per model id."""
    board = design.board
    assert board is not None
    found: dict[str, set[str]] = {}
    for entity in (*board.tracks, *board.arcs, *board.vias, *board.zones):
        found[entity.id] = {entity.id, _where(entity), *entity.native_ids.values()}
    return found


def _touches(node: _Node, point: Point, layers: Collection[str]) -> bool:
    disc = Thick((point,), _POINT)
    return any(layer in layers and thick_touch(shape, disc) for layer, shape in node.shapes)


def _sides(graph: _Graph, tie: Tie, removed: Collection[int], neighbours: Collection[int]) -> list[set[int]]:
    """The neighbours on each side of the tie, the sides sorted: a part's sides are its pads by net; the
    sides of copper items are the free ends of their chain (an end that touches no other tie item)."""
    nodes = graph.nodes
    sides: dict[object, set[int]] = defaultdict(set)
    if tie.part is not None:
        for index in removed:
            for nxt in graph.edges[index]:
                if nxt in neighbours:
                    sides[nodes[index].item.net].add(nxt)
        return [sides[key] for key in sorted(sides, key=str)]
    for index in removed:
        node = nodes[index]
        layers = {layer for layer, _ in node.shapes}
        for point in node.anchors:
            if any(_touches(nodes[other], point, layers) for other in removed if other != index):
                continue
            for nxt in graph.edges[index]:
                if nxt in neighbours and _touches(nodes[nxt], point, layers):
                    sides[point.x, point.y].add(nxt)
    claimed: dict[int, int] = defaultdict(int)
    for members in sides.values():
        for member in members:
            claimed[member] += 1
    out = [{m for m in sides[key] if claimed[m] == 1} for key in sorted(sides, key=str)]
    return [members for members in out if members]


def _domain(pad: str, domains: Mapping[str, Sequence[str]]) -> str | None:
    for name, globs in domains.items():
        if any(fnmatch.fnmatchcase(pad, glob) for glob in globs):
            return name
    return None


def _zones(design: Design, nets: Collection[str]) -> str:
    board = design.board
    assert board is not None
    names = {net.id: net.name for net in design.circuit.nets}
    held = [zone for zone in board.zones if zone.net_id is not None and names.get(zone.net_id) in nets]
    if not held:
        return "none"
    return "filled" if all(zone.fills for zone in held) else "unfilled"


def _labels(graph: _Graph, indices: Iterable[int]) -> str:
    return " → ".join(graph.nodes[index].item.where for index in indices)


def _prove(
    design: Design,
    by_net: Mapping[str, Sequence[CopperShape]],
    pads: Sequence[BoardPad],
    tie: Tie,
    domains: Mapping[str, Sequence[str]] | None,
    names: Mapping[str, set[str]],
) -> tuple[TieRow | None, list[Issue]]:
    if tie.part is not None:
        tie_ids = {record.pad_id for record in pads if record.ref == tie.part}
        nets = {record.net for record in pads if record.ref == tie.part and record.net}
    else:
        wanted = set(tie.items)
        tie_ids = {ident for ident, known in names.items() if known & wanted}
        found: set[str] = {name for ident in tie_ids for name in names[ident]}
        missing = sorted(wanted - found)
        if missing:
            message = f"the tie item(s) {', '.join(missing)} are not on the board"
            return None, [issue("analysis.tie-unmatched", message, where=tie.name)]
        nets = {net for net, shapes in by_net.items() if any(shape.entity_id in tie_ids for shape in shapes)}
    if not tie_ids:
        message = f"the part {tie.part} is not on the board, or has no pad"
        return None, [issue("analysis.tie-unmatched", message, where=tie.name)]
    graph = _Graph(_nodes({net: by_net[net] for net in sorted(nets) if net in by_net}, design, pads))
    removed = {index for index, node in enumerate(graph.nodes) if node.item.id in tie_ids}
    neighbours = {nxt for index in removed for nxt in graph.edges[index] if nxt not in removed}
    part = graph.parts(removed)
    roots = sorted({part[index] for index in neighbours})
    members: dict[int, list[int]] = defaultdict(list)
    for index, root in enumerate(part):
        if root in roots:
            members[root].append(index)

    def pads_of(indices: Iterable[int]) -> tuple[str, ...]:
        return tuple(
            sorted({graph.nodes[i].item.where for i in indices if graph.nodes[i].item.kind == "pad"})
        )

    groups = sorted(pads_of(members[root]) for root in roots)
    issues: list[Issue] = []
    path: list[int] = []
    extra: list[str] = []
    zones = _zones(design, nets)
    if zones == "unfilled":
        issues.append(
            issue(
                "analysis.input-missing",
                "a zone of the tie's nets holds no fill, so its copper is not in the graph",
                where=tie.name,
                hint="fill the zones first: fenolite fill",
            )
        )
    if len(neighbours) < 2:
        issues.append(
            issue(
                "analysis.tie-dangling",
                f"the tie {tie.name} touches {len(neighbours)} copper item(s), so it joins nothing",
                where=tie.name,
            )
        )
    elif len(roots) == 1:
        sides = _sides(graph, tie, removed, neighbours)
        if len(sides) >= 2:
            goals = {index for side in sides[1:] for index in side}
            path = graph.path(sides[0], goals, removed)
        shown = f": {_labels(graph, path)}" if path else ""
        issues.append(
            issue(
                "analysis.tie-parallel",
                f"removing the tie {tie.name} splits nothing: another path joins its sides{shown}",
                where=tie.name,
                hint="a second tie, a via or a pour joins the two areas: remove it, or name it in the tie",
            )
        )
    elif domains:
        for root in roots:
            group = members[root]
            held: dict[str, list[int]] = defaultdict(list)
            for index in group:
                item = graph.nodes[index].item
                name = _domain(item.where, domains) if item.kind == "pad" else None
                if name is not None:
                    held[name].append(index)
            if len(held) < 2:
                continue
            order = list(domains)
            intruder = min(held, key=lambda name: (len(held[name]), -order.index(name)))
            others = {i for name, found in held.items() if name != intruder for i in found}
            strays = sorted({graph.nodes[i].item.where for i in held[intruder]})
            extra += strays
            joint = graph.path(held[intruder], others, removed)
            issues.append(
                issue(
                    "analysis.tie-extra",
                    f"after removing the tie {tie.name}, pad(s) {', '.join(strays)} of domain {intruder} "
                    f"are still joined to the other domain: {_labels(graph, joint)}",
                    where=strays[0],
                    hint="a second joint between the domains; the tie is not the only connection",
                )
            )
    row = TieRow(
        tie=tie.name,
        nets=tuple(sorted(nets)),
        removed=tuple(graph.nodes[index].item for index in sorted(removed)),
        groups=tuple(groups),
        split=len(roots) >= 2,
        path=tuple(graph.nodes[index].item for index in path),
        extra=tuple(sorted(extra)),
        zones=zones,
    )
    return row, issues


def _tie_groups(design: Design) -> dict[str, dict[str, int]]:
    """Per footprint id, the index of the net-tie group of each pad number that is in one."""
    board = design.board
    assert board is not None
    groups: dict[str, dict[str, int]] = {}
    for footprint in board.footprints:
        found: dict[str, int] = {}
        for index, group in enumerate(footprint.net_ties):
            for number in group:
                found.setdefault(number, index)
        if found:
            groups[footprint.id] = found
    return groups


def _sense(
    design: Design, by_net: Mapping[str, Sequence[CopperShape]], pads: Sequence[BoardPad], nets: Sequence[str]
) -> tuple[list[SenseRow], list[Issue]]:
    graph = _Graph(_nodes(by_net, design, pads))
    ties = _tie_groups(design)

    def joined_on_purpose(a: _Node, b: _Node) -> bool:
        if a.pad is None or b.pad is None or a.pad.footprint_id != b.pad.footprint_id:
            return False
        groups = ties.get(a.pad.footprint_id, {})
        first, second = groups.get(a.pad.number), groups.get(b.pad.number)
        return first is not None and first == second

    rows: list[SenseRow] = []
    issues: list[Issue] = []
    for net in nets:
        own = [index for index, node in enumerate(graph.nodes) if node.item.net == net]
        if not own:
            message = f"the sense net {net} has no copper on the board"
            issues.append(issue("analysis.tie-unmatched", message, where=net))
            continue
        shared: list[TieItem] = []
        for index in own:
            node = graph.nodes[index]
            for other in sorted(graph.edges[index]):
                peer = graph.nodes[other]
                if peer.item.net == net or joined_on_purpose(node, peer):
                    continue
                shared.append(peer.item)
                issues.append(
                    issue(
                        "analysis.sense-shared",
                        f"copper of the sense net {net} ({node.item.kind} {node.item.where}) touches "
                        f"copper of {peer.item.net} ({peer.item.kind} {peer.item.where})",
                        where=node.item.where,
                        hint="a sense net meets its element only at its pads, through a net-tie part",
                    )
                )
        rows.append(SenseRow(net, len(own), tuple(dict.fromkeys(shared))))
    return rows, issues


def analyze_ties(
    design: Design,
    *,
    pads: Sequence[BoardPad] | None,
    ties: Sequence[Tie] = (),
    domains: Mapping[str, Sequence[str]] | None = None,
    sense: Sequence[str] = (),
    arc_tol: int = ARC_TOL_NM,
) -> TieReport:
    """The proof of each tie of ``ties`` and the check of each net of ``sense`` on ``design.board``.
    ``pads`` are the board-frame pad records; without them no pad takes part and the level is
    ``UNVERIFIED``. ``domains`` maps two domain names to ``REF-PIN`` patterns."""
    if design.board is None:
        return TieReport()
    records = tuple(pads or ())
    copper = net_copper(design, pads=pads, arc_tol=arc_tol)
    names = _names(design)
    rows: list[TieRow] = []
    issues: list[Issue] = []
    for tie in ties:
        row, found = _prove(design, copper.by_net, records, tie, domains, names)
        issues += found
        if row is not None:
            rows.append(row)
    sense_rows, found = _sense(design, copper.by_net, records, sense) if sense else ([], [])
    issues += found
    issues += [
        issue(
            "analysis.item-unsupported",
            f"{count} {kind} item(s) could not be shaped and take no part in the graph",
            where=kind,
        )
        for kind, count in sorted(copper.unsupported.items())
    ]
    level = Level.UNVERIFIED if copper.unsupported or pads is None else EVIDENCE.level
    summary = {
        "ties": len(rows),
        "split": sum(row.split for row in rows),
        "sense": len(sense_rows),
        "shared": sum(len(row.shared) for row in sense_rows),
    }
    return TieReport(
        tuple(rows),
        tuple(sense_rows),
        tuple(issues),
        Evidence(level, hypotheses=EVIDENCE.hypotheses),
        summary,
    )


def isolation_islands(design: Design, *, barriers: Sequence[str]) -> IslandReport:
    """The islands of the nets of ``design.circuit`` once the parts named by ``barriers`` are removed: each
    other part joins the nets of its pins. Nets without a pin are left out. It reads no copper."""
    circuit = design.circuit
    refs = {component.id: component.ref for component in circuit.components}
    known = set(refs.values())
    issues = [
        issue("analysis.tie-unmatched", f"the barrier part {ref} is not in the design", where=ref)
        for ref in sorted(set(barriers) - known)
    ]
    wanted = set(barriers)
    nets_of: dict[str, set[str]] = defaultdict(set)
    named = [net for net in circuit.nets if net.members]
    for net in named:
        for member in net.members:
            nets_of[member.component_id].add(net.name)
    parent = {net.name: net.name for net in named}

    def find(name: str) -> str:
        while parent[name] != name:
            parent[name] = parent[parent[name]]
            name = parent[name]
        return name

    for component_id, held in nets_of.items():
        if refs.get(component_id) in wanted:
            continue
        first, *rest = sorted(held)
        for name in rest:
            a, b = find(first), find(name)
            if a != b:
                parent[max(a, b)] = min(a, b)
    islands: dict[str, list[str]] = defaultdict(list)
    for name in parent:
        islands[find(name)].append(name)
    out: list[Island] = []
    for members in islands.values():
        inside = set(members)
        bounds = sorted(
            {refs[cid] for cid, held in nets_of.items() if refs.get(cid) in wanted and held & inside}
        )
        out.append(Island(tuple(sorted(members)), tuple(bounds)))
    return IslandReport(tuple(sorted(out, key=lambda island: island.nets)), tuple(issues))


__all__ = [
    "EVIDENCE",
    "Island",
    "IslandReport",
    "SenseRow",
    "Tie",
    "TieItem",
    "TieReport",
    "TieRow",
    "analyze_ties",
    "isolation_islands",
]

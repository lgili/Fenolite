# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Allowances: the rules of kinds ``short`` and ``antenna`` that let ``check`` accept a short or a stub
(change c0465, designs D2 and D3).

An allowance is a rule, not a waiver: it is matched by the selectors of the items, through the precedence
of every rule (``checks.clearance.rule_precedence``, the later rule governs), and it never goes stale.
``governing`` gives the rule in force; ``stub`` measures the open-ended run of copper a dangling item ends,
on the design's own copper (``checks.padpath.CopperGraph``), without a tool. No code is shared with
``checks.waivers``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from fenolite.backends.base import BoardPad, DrcViolation
from fenolite.checks.clearance import ClearanceResolver, CopperKind, rule_precedence, selector_matches
from fenolite.checks.padpath import CopperGraph, Step
from fenolite.core.errors import Issue, Severity
from fenolite.geometry import Location, point_in_ring
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleKind, RuleSubject

ALLOWED_SEVERITY = {"ignore": "info", "warning": "warning", "error": "error"}
"""A governing ``short`` rule's severity → the severity of the short it governs."""
UNRESOLVED_CODE = "check.allowance-unresolved"
"""The info of a stage entry an allowance could have judged but whose item is not on the design."""
_RUN = ("track", "arc")


def allowance_rules(design: Design, allowances: Sequence[Rule] | None = None) -> tuple[Rule, ...]:
    """``allowances``, or with ``None`` the rules of kinds ``short`` and ``antenna`` of ``design``."""
    if allowances is not None:
        return tuple(allowances)
    rules = design.rules.rules if design.rules is not None else ()
    return tuple(r for r in rules if r.kind in ("short", "antenna"))


def _on_layers(rule: Rule, subject: RuleSubject) -> bool:
    if not rule.layers:
        return True
    return subject.layer is not None and subject.layer.casefold() in {x.casefold() for x in rule.layers}


def governing(
    rules: Sequence[Rule], kind: RuleKind, a: RuleSubject, b: RuleSubject | None = None
) -> Rule | None:
    """The rule of ``kind`` in force for the item ``a`` (``antenna``) or the pair ``a``, ``b`` in either order
    (``short``): the last that matches in ``rule_precedence`` order, or ``None``."""
    found: Rule | None = None
    for rule in rule_precedence([r for r in rules if r.kind == kind]):
        if not _on_layers(rule, a):
            continue
        if b is None:
            matched = selector_matches(rule.selector_a, a)
        else:
            second = rule.selector_b
            assert second is not None  # Rule checks it for a short rule
            matched = (selector_matches(rule.selector_a, a) and selector_matches(second, b)) or (
                selector_matches(rule.selector_a, b) and selector_matches(second, a)
            )
        if matched:
            found = rule
    return found


def allowed_suffix(rule: Rule) -> str:
    """What the message of a short a rule allowed or relaxed ends with."""
    return f" (allowed by rule {rule.name})"


def stub_suffix(length: int, rule: Rule) -> str:
    """What the message of a stub within an ``antenna`` rule's ``max`` ends with, lengths in mm."""
    assert rule.max is not None
    return f" (stub {_mm(length)} within {_mm(rule.max)} of rule {rule.name})"


def _mm(nm: int) -> str:
    whole, rest = divmod(nm, 1_000_000)
    return f"{whole}.{rest:06d}".rstrip("0").rstrip(".") + "mm"


@dataclass(frozen=True, slots=True)
class Stub:
    """The open-ended run a dangling item belongs to: its ``length`` along the centre line, the ids of its
    tracks and arcs, the number of its open ends, and the piece at its first open end (``end_id``, a track
    or an arc; empty for a via that joins nothing) with that piece's ``net_id`` and ``layer``."""

    item_id: str
    length: int
    pieces: tuple[str, ...]
    open_ends: int
    end_id: str
    net_id: str | None
    layer: str


class _Nodes:
    """The vertices of a ``CopperGraph`` gathered into nodes: the layer vertices of one via are one node."""

    def __init__(self, graph: CopperGraph) -> None:
        self.graph = graph
        parent: dict[str, str] = {vertex: vertex for vertex in graph.adj}

        def root(vertex: str) -> str:
            while parent[vertex] != vertex:
                parent[vertex] = parent[parent[vertex]]
                vertex = parent[vertex]
            return vertex

        for vertex, neighbours in graph.adj.items():
            for other, step in neighbours:
                if step.kind == "via":
                    a, b = root(vertex), root(other)
                    if a != b:
                        parent[max(a, b)] = min(a, b)
        self.of = {vertex: root(vertex) for vertex in graph.adj}
        self.members: dict[str, list[str]] = {}
        for vertex in sorted(graph.adj):
            self.members.setdefault(self.of[vertex], []).append(vertex)
        self._zones = self._zone_vertices()

    def _zone_vertices(self) -> frozenset[str]:
        board = self.graph.design.board
        if board is None:
            return frozenset()
        inside: set[str] = set()
        for key, (net, layer, point) in self.graph.positions.items():
            for zone in board.zones:
                if zone.net_id != net:
                    continue
                for fill in zone.fills:
                    if fill.layer == layer and point_in_ring(point, fill.polygon) != Location.OUTSIDE:
                        inside.add(key)
        return frozenset(inside)

    def edges(self, node: str) -> list[tuple[str, str, Step]]:
        """The tracks and arcs at ``node``: ``(vertex, other vertex, step)``, in a stable order."""
        found: list[tuple[str, str, Step]] = []
        for vertex in self.members.get(node, ()):
            for other, step in self.graph.adj[vertex]:
                if step.kind in _RUN:
                    found.append((vertex, other, step))
        return found

    def joins_other(self, node: str) -> bool:
        """Whether ``node`` meets copper outside a run: a pad, or a zone of its net."""
        for vertex in self.members.get(node, ()):
            if vertex in self._zones:
                return True
            if any(step.kind == "pad" for _, step in self.graph.adj[vertex]):
                return True
        return False


def _edge_key(vertex: str, other: str, step: Step) -> tuple[str, str, str]:
    a, b = sorted((vertex, other))
    return (a, b, step.id)


def _chain(nodes: _Nodes, start: tuple[str, str, Step]) -> tuple[list[tuple[str, str, Step]], list[str]]:
    """The maximal run through ``start``: every edge reached through nodes of two edges that join nothing
    else, and the nodes where it ends."""
    seen = {_edge_key(*start)}
    edges = [start]
    ends: list[str] = []
    pending = [nodes.of[start[0]], nodes.of[start[1]]]
    while pending:
        node = pending.pop()
        at = nodes.edges(node)
        if len(at) != 2 or nodes.joins_other(node):
            ends.append(node)
            continue
        for edge in at:
            key = _edge_key(*edge)
            if key in seen:
                continue
            seen.add(key)
            edges.append(edge)
            far = nodes.of[edge[1]] if nodes.of[edge[0]] == node else nodes.of[edge[0]]
            pending.append(far)
    return edges, ends


def _open(nodes: _Nodes, node: str) -> bool:
    return len(nodes.edges(node)) == 1 and not nodes.joins_other(node)


def _stub_of(nodes: _Nodes, item_id: str, start: tuple[str, str, Step], extra_open: str | None) -> Stub | str:
    edges, ends = _chain(nodes, start)
    opened = sorted({node for node in ends if _open(nodes, node) or node == extra_open})
    if not opened:
        return "not-dangling"
    end_node = opened[0]
    at_end = sorted(
        (edge for edge in edges if end_node in (nodes.of[edge[0]], nodes.of[edge[1]])), key=lambda e: e[2].id
    )
    end = at_end[0][2] if at_end else edges[0][2]
    net = nodes.graph.positions.get(at_end[0][0] if at_end else edges[0][0], (None, "", None))[0]
    return Stub(
        item_id,
        sum(edge[2].length_nm for edge in edges),
        tuple(sorted({edge[2].id for edge in edges})),
        len(opened),
        end.id,
        net,
        end.layer,
    )


def stub(
    design: Design, item_id: str, *, pads: Sequence[BoardPad] | None = None, graph: CopperGraph | None = None
) -> Stub | str:
    """The stub that the track, arc or via ``item_id`` ends, or why there is none: ``no-item`` (no such copper
    item with a net on a copper layer) or ``not-dangling`` (its run meets other copper at every end).

    The run is followed from the item through every node of two pieces that meets nothing else; it stops at
    a pad, a zone of its net, or a junction of three or more pieces. A via is one node across its layers; a
    via that ends a run and joins nothing else is an open end. A track whose two ends are both open is one
    stub of its whole length."""
    graph = CopperGraph(design, pads=pads) if graph is None else graph
    nodes = _Nodes(graph)
    board = design.board
    via = next((v for v in board.vias if v.id == item_id), None) if board is not None else None
    if via is not None:
        vertices = [
            key
            for key, (net, _, point) in graph.positions.items()
            if net == via.net_id and point == via.position
        ]
        own = {nodes.of[vertex] for vertex in vertices if any(s.id == via.id for _, s in graph.adj[vertex])}
        if len(own) != 1:
            return "no-item"
        (node,) = own
        at = nodes.edges(node)
        if nodes.joins_other(node) or len(at) > 1:
            return "not-dangling"
        if not at:
            return Stub(item_id, 0, (), 1, "", via.net_id, "")
        return _stub_of(nodes, item_id, at[0], node)
    for vertex in sorted(graph.adj):
        for other, step in graph.adj[vertex]:
            if step.id == item_id and step.kind in _RUN:
                return _stub_of(nodes, item_id, (vertex, other, step), None)
    return "no-item"


def stubs(design: Design, item_ids: Sequence[str]) -> dict[str, Stub | str]:
    """``stub`` of each of ``item_ids`` on one graph of ``design``."""
    graph = CopperGraph(design)
    return {item: stub(design, item, graph=graph) for item in dict.fromkeys(item_ids)}


def stub_subject(design: Design, found: Stub, resolver: ClearanceResolver | None = None) -> RuleSubject:
    """The subject an ``antenna`` rule is matched against: the piece at the stub's open end (for a via that
    joins nothing, the via). Rule areas are not resolved here, so an ``area`` leaf matches no stub."""
    resolver = ClearanceResolver(design) if resolver is None else resolver
    return resolver.subject("via" if not found.end_id else "track", found.net_id, ref=None, layer=found.layer)


SHORT_TYPE = "shorting_items"
DANGLING_TYPES = ("track_dangling", "via_dangling")
"""The DRC entry types an allowance judges (KiCad's names; design D4 of change c0465)."""


@dataclass(frozen=True, slots=True)
class _Item:
    kind: CopperKind
    net_id: str | None
    ref: str | None
    layer: str | None
    entity_id: str


def _native_items(design: Design, oracle: str) -> dict[str, list[_Item]]:
    """``native id → the copper items that carry it`` on the board of ``design``, for ``oracle``."""
    board = design.board
    found: dict[str, list[_Item]] = {}
    if board is None:
        return found

    def add(native: str | None, item: _Item) -> None:
        if native:
            found.setdefault(native.lower(), []).append(item)

    for track in board.tracks:
        add(track.native_ids.get(oracle), _Item("track", track.net_id, None, track.layer, track.id))
    for arc in board.arcs:
        add(arc.native_ids.get(oracle), _Item("arc", arc.net_id, None, arc.layer, arc.id))
    for via in board.vias:
        add(via.native_ids.get(oracle), _Item("via", via.net_id, None, None, via.id))
    for zone in board.zones:
        add(zone.native_ids.get(oracle), _Item("zone", zone.net_id, None, None, zone.id))
    refs = {c.id: c.ref for c in design.circuit.components}
    for footprint in board.footprints:
        ref = refs.get(footprint.component_id)
        for pad in footprint.pads:
            add(pad.native_ids.get(oracle), _Item("pad", pad.net_id, ref, None, pad.id))
    return found


def _with_severity(found: Issue, severity: str, suffix: str) -> Issue:
    rank = {"info": 0, "warning": 1, "error": 2}
    kept = found.severity if rank[found.severity] < rank[severity] else severity
    return dataclasses.replace(found, severity=cast(Severity, kept), message=found.message + suffix)


def judge_entries(
    entries: Sequence[tuple[Issue, tuple[str, ...], DrcViolation]],
    *,
    design: Design | None,
    oracle: str,
    rules: Sequence[Rule],
) -> tuple[list[tuple[Issue, tuple[str, ...], DrcViolation]], dict[str, int], list[Issue]]:
    """The DRC ``entries`` judged against the ``short`` and ``antenna`` ``rules`` (design D4 of change c0465),
    the count per code of the entries an allowance accepted, and one info ``check.allowance-unresolved`` per
    entry whose items do not resolve on ``design`` to one copper item each.

    A ``shorting_items`` entry whose governing ``short`` rule has severity ``ignore`` takes severity ``info``
    and ends with `` (allowed by rule <name>)``; ``warning`` lowers an error to a warning. A
    ``track_dangling`` or ``via_dangling`` entry whose stub is at most the governing ``antenna`` rule's
    ``max`` takes ``info`` and ends with `` (stub <length> within <max> of rule <name>)``. Entries of other
    types, and every entry when no rule of the kind is given, are returned unchanged."""
    shorts = [r for r in rules if r.kind == "short"]
    antennae = [r for r in rules if r.kind == "antenna"]
    if design is None or (not shorts and not antennae):
        return list(entries), {}, []
    natives = _native_items(design, oracle)
    resolver = ClearanceResolver(design)
    allowed: dict[str, int] = {}
    unresolved: list[Issue] = []

    def resolved(violation: DrcViolation) -> list[_Item] | None:
        items: list[_Item] = []
        for entry in violation.items:
            found = natives.get(entry.uuid.lower(), [])
            if len(found) != 1:
                return None
            items.append(found[0])
        return items

    def unresolved_issue(made: Issue, why: str) -> None:
        unresolved.append(
            Issue(
                UNRESOLVED_CODE,
                "info",
                f"{made.code} at {made.where or 'no item'}: {why}; no allowance was applied",
                where=made.code,
            )
        )

    targets = [
        items[0].entity_id
        for _, _, violation in entries
        if antennae
        and violation.type in DANGLING_TYPES
        and (items := resolved(violation)) is not None
        and len(items) == 1
    ]
    measured = stubs(design, targets) if targets else {}
    judged: list[tuple[Issue, tuple[str, ...], DrcViolation]] = []
    for made, names, violation in entries:
        if violation.type == SHORT_TYPE and shorts:
            items = resolved(violation)
            if items is None or len(items) != 2:
                unresolved_issue(made, "its items are not two copper items of the design")
                judged.append((made, names, violation))
                continue
            layer = next((item.layer for item in items if item.layer is not None), None)
            a, b = (
                resolver.subject(item.kind, item.net_id, ref=item.ref, layer=layer or "") for item in items
            )
            rule = governing(shorts, "short", a, b)
            if rule is not None and rule.severity != "error":
                made = _with_severity(made, ALLOWED_SEVERITY[rule.severity], allowed_suffix(rule))
                if rule.severity == "ignore":
                    allowed[made.code] = allowed.get(made.code, 0) + 1
        elif violation.type in DANGLING_TYPES and antennae:
            items = resolved(violation)
            found = measured.get(items[0].entity_id) if items is not None and len(items) == 1 else None
            if not isinstance(found, Stub):
                unresolved_issue(
                    made, "its item has no stub on the design" if items else "its item is not on the design"
                )
                judged.append((made, names, violation))
                continue
            rule = governing(antennae, "antenna", stub_subject(design, found, resolver))
            if rule is not None and rule.max is not None and found.length <= rule.max:
                made = _with_severity(made, "info", stub_suffix(found.length, rule))
                allowed[made.code] = allowed.get(made.code, 0) + 1
        judged.append((made, names, violation))
    return judged, dict(sorted(allowed.items())), unresolved


__all__ = [
    "ALLOWED_SEVERITY",
    "DANGLING_TYPES",
    "SHORT_TYPE",
    "UNRESOLVED_CODE",
    "Stub",
    "allowance_rules",
    "allowed_suffix",
    "governing",
    "judge_entries",
    "stub",
    "stub_subject",
    "stubs",
    "stub_suffix",
]

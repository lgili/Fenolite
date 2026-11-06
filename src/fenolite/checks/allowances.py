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

from collections.abc import Sequence
from dataclasses import dataclass

from fenolite.backends.base import BoardPad
from fenolite.checks.clearance import ClearanceResolver, rule_precedence, selector_matches
from fenolite.checks.padpath import CopperGraph, Step
from fenolite.geometry import Location, point_in_ring
from fenolite.model.design import Design
from fenolite.model.rules import Rule, RuleKind, RuleSubject

ALLOWED_SEVERITY = {"ignore": "info", "warning": "warning", "error": "error"}
"""A governing ``short`` rule's severity → the severity of the short it governs."""
UNRESOLVED_CODE = "check.allowance-unresolved"
"""The info of a stage entry an allowance could have judged but whose item is not on the design."""
_RUN = ("track", "arc")


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


def stub_subject(design: Design, found: Stub) -> RuleSubject:
    """The subject an ``antenna`` rule is matched against: the piece at the stub's open end (for a via that
    joins nothing, the via). Rule areas are not resolved here, so an ``area`` leaf matches no stub."""
    return ClearanceResolver(design).subject(
        "via" if not found.end_id else "track", found.net_id, ref=None, layer=found.layer
    )


__all__ = [
    "ALLOWED_SEVERITY",
    "UNRESOLVED_CODE",
    "Stub",
    "allowed_suffix",
    "governing",
    "stub",
    "stub_subject",
    "stub_suffix",
]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Tool-free judgement of ordered signal topologies using the user's timing and loss inputs."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, replace

from fenolite.backends.base import BoardFrame
from fenolite.checks.codes import issue
from fenolite.checks.padpath import CopperGraph, Path, Step
from fenolite.checks.stages import StageResult, ran, skipped
from fenolite.checks.subjects import for_issues
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design
from fenolite.model.rules import RuleSet, Topology, TopologyEdge

STAGE = "topology.rules"
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-TOPO-DELAY",))
NO_READ_EVIDENCE = Evidence()


def tree_path(topology: Topology, a: str, b: str) -> tuple[TopologyEdge, ...]:
    """The unique sequence of edges between two nodes in the declared tree."""
    queue: deque[tuple[str, tuple[TopologyEdge, ...]]] = deque([(a, ())])
    seen = {a}
    while queue:
        current, path = queue.popleft()
        if current == b:
            return path
        for edge in topology.edges:
            other = edge.b if edge.a == current else edge.a if edge.b == current else ""
            if other and other not in seen:
                seen.add(other)
                queue.append((other, (*path, edge)))
    raise ValueError("ends do not belong to one topology tree")


@dataclass(frozen=True, slots=True)
class Measurement:
    """Strict lower/upper integer sums and their explicit input receipt."""

    status: str
    low_fs: int = 0
    high_fs: int = 0
    high_mdb: int = 0
    inputs: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


def measure_path(
    topology: Topology, a: str, b: str, graph: CopperGraph, rules: RuleSet, *, loss: bool = False
) -> Measurement:
    if topology.missing_bridges:
        return Measurement("bridge-missing")
    steps: list[Step] = []
    pads = {a, b}
    bridge_fs = bridge_mdb = 0
    for edge in tree_path(topology, a, b):
        pads.update((edge.a, edge.b))
        if edge.kind == "bridge":
            bridge_fs += edge.delay_fs
            bridge_mdb += edge.loss_mdb
            continue
        path = graph.shortest(edge.a, edge.b)
        if path.status != "ok":
            return Measurement(path.status)
        steps.extend(path.steps)
        pads.update(path.pads)
    inputs: set[str] = set()
    missing: set[str] = set()
    low = high = bridge_mdb if loss else bridge_fs
    seen_vias: set[str] = set()
    # Rejoin portions of the same stored track/arc before rounding, so an incidental graph junction
    # does not add a femtosecond of rounding error to a whole source segment.
    portions: list[Step] = []
    for step in steps:
        if portions and portions[-1].id == step.id and step.kind in ("track", "arc"):
            portions[-1] = replace(step, length_nm=portions[-1].length_nm + step.length_nm)
        else:
            portions.append(step)
    for step in portions:
        if step.kind == "via":
            if step.id in seen_vias:
                continue
            seen_vias.add(step.id)
            if loss:
                row = next((row for row in rules.losses if not row.layer), None)
                value = row.via_mdb if row else None
            else:
                row = next((row for row in rules.propagation if not row.layer), None)
                value = row.via_fs if row else None
            if value is None:
                missing.add("via loss" if loss else "via propagation")
            else:
                low += value
                high += value
                inputs.add(f"via={value} {'mdb' if loss else 'fs'}")
        elif step.kind in ("track", "arc"):
            if loss:
                layer_loss = next((row for row in rules.losses if row.layer == step.layer), None)
                value = layer_loss.per_mm_mdb if layer_loss else None
            else:
                propagation = next((row for row in rules.propagation if row.layer == step.layer), None)
                value = propagation.per_mm_fs if propagation else None
            if value is None:
                missing.add(f"{step.layer} {'loss' if loss else 'propagation'}")
            else:
                product = step.length_nm * value
                low += product // 1_000_000
                high += (product + 999_999) // 1_000_000
                inputs.add(f"{step.layer}={value} {'mdb' if loss else 'fs'}/mm")
    if loss:
        frequencies = {
            row.at_hz for row in rules.losses if row.layer in {step.layer for step in portions} and row.at_hz
        }
        if len(frequencies) > 1:
            missing.add("one common loss frequency")
        inputs.update(f"frequency={value} Hz" for value in frequencies)
    elif graph.design.board is not None:
        refs = {part.id: part.ref for part in graph.design.circuit.components}
        for footprint in graph.design.board.footprints:
            for pad in footprint.pads:
                if f"{refs.get(footprint.component_id, '')}-{pad.number}" not in pads:
                    continue
                if any("(die_delay" in payload for bag in pad.ext.values() for _, payload in bag.payload):
                    missing.add("native pad die_delay units (unprobed)")
                low += pad.die_delay_fs
                high += pad.die_delay_fs
                if pad.die_delay_fs:
                    inputs.add(
                        f"{refs.get(footprint.component_id, '')}-{pad.number} die={pad.die_delay_fs} fs"
                    )
    if any(edge.kind == "bridge" for edge in tree_path(topology, a, b)):
        inputs.add(f"bridges={bridge_mdb if loss else bridge_fs} {'mdb' if loss else 'fs'}")
    return Measurement(
        "input-missing" if missing else "ok",
        low if not loss else 0,
        high if not loss else 0,
        high if loss else 0,
        tuple(sorted(inputs)),
        tuple(sorted(missing)),
    )


def _unjudged(topology: Topology, measurement: Measurement, ends: tuple[str, ...]) -> Issue | None:
    where = ", ".join((topology.name, *ends))
    if measurement.status == "input-missing":
        return issue(
            "topology.input-missing",
            f"topology {topology.name}: missing {', '.join(measurement.missing)}; constraint not judged",
            where=where,
            hint="state design.propagation() or design.loss() for every layer and via on this path",
        )
    if measurement.status == "path-through-zone":
        return issue(
            "topology.path-through-zone",
            f"topology {topology.name}: {' to '.join(ends)} connects through zone copper; "
            "constraint not judged",
            where=where,
            hint="route a continuous track path to measure its centre-line length",
        )
    if measurement.status == "unrouted":
        return issue(
            "topology.unrouted",
            f"topology {topology.name}: no routed pad path for {' to '.join(ends)}; constraint not judged",
            where=where,
            hint="route the constrained pins and check again",
        )
    return None


def _paths(topology: Topology, graph: CopperGraph) -> tuple[tuple[TopologyEdge, Path], ...]:
    return tuple((edge, graph.shortest(edge.a, edge.b)) for edge in topology.edges if edge.kind == "net")


def _descendants(topology: Topology, root: str) -> set[str]:
    found: set[str] = set()
    queue = [root]
    while queue:
        current = queue.pop()
        for edge in topology.edges:
            if edge.a == current:
                found.add(edge.b)
                queue.append(edge.b)
    return found


def _has_loop(paths: tuple[tuple[TopologyEdge, Path], ...], graph: CopperGraph) -> bool:
    nets = {edge.net for edge, _ in paths}
    parent = {key: key for key in graph.adj}

    def root(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for a, neighbours in graph.adj.items():
        for b, step in neighbours:
            if step.kind in ("pad", "via"):
                parent[root(a)] = root(b)
    seen: set[tuple[str, str]] = set()
    for a, neighbours in graph.adj.items():
        position = graph.positions.get(a)
        if position is None or graph.net_names.get(position[0]) not in nets:
            continue
        for b, step in neighbours:
            if step.kind not in ("track", "arc"):
                continue
            key = (min(a, b), max(a, b))
            if key in seen:
                continue
            seen.add(key)
            ra, rb = root(a), root(b)
            if ra == rb:
                return True
            parent[ra] = rb
    return False


def _stubs(paths: tuple[tuple[TopologyEdge, Path], ...], graph: CopperGraph) -> tuple[int, ...]:
    occupied = {vertex for _, path in paths for vertex in path.vertices}
    # A pad touching the measured path belongs to it; zero-length pad fan-outs are not stubs.
    occupied |= {
        other for vertex in tuple(occupied) for other, step in graph.adj[vertex] if step.kind == "pad"
    }
    found: list[int] = []
    for vertex in sorted(occupied):
        for other, step in graph.adj[vertex]:
            if other in occupied or step.kind == "zone":
                continue
            stack = [(other, vertex, step.length_nm, frozenset({vertex, other}))]
            while stack:
                current, previous, length, seen = stack.pop()
                neighbours = [
                    (value, edge)
                    for value, edge in graph.adj[current]
                    if value != previous
                    and value not in seen
                    and value not in occupied
                    and edge.kind != "zone"
                ]
                if not neighbours:
                    if length:
                        found.append(length)
                    continue
                for value, edge in neighbours:
                    stack.append((value, current, length + edge.length_nm, seen | {value}))
    return tuple(sorted(found))


def topology_stage(
    design: Design | None,
    *,
    model: Design | None = None,
    frame: BoardFrame | None = None,
    evidence: Evidence = NO_READ_EVIDENCE,
) -> StageResult:
    """Judge cached topology intent on the current board geometry, with no external tool."""
    if design is None:
        return skipped(STAGE, "read-refused")
    rules = model.rules if model is not None else design.rules
    if rules is None or not rules.topologies:
        return skipped(STAGE, "no-topology")
    checked = replace(design, rules=rules)
    pads = frame.board_pads(checked) if frame is not None else None
    graph = CopperGraph(checked, pads=pads)
    issues = list(build_issues(checked))
    counts: Counter[str] = Counter()
    judged = not_judged = 0
    by_name = {topology.name: topology for topology in rules.topologies}
    for topology in rules.topologies:
        for constraint in topology.constraints:
            counts[constraint.kind] += 1
            ends = constraint.ends
            if constraint.kind in ("delay", "loss"):
                measured = measure_path(
                    topology, ends[0], ends[1], graph, rules, loss=constraint.kind == "loss"
                )
                if measured.status != "ok":
                    found = _unjudged(topology, measured, ends)
                    if found is not None:
                        issues.append(found)
                    not_judged += 1
                    continue
                judged += 1
                receipt = "; ".join(measured.inputs)
                if constraint.kind == "delay":
                    if constraint.min_fs is not None and measured.low_fs < constraint.min_fs:
                        actual, limit, side = measured.low_fs, constraint.min_fs, "below minimum"
                    elif constraint.max_fs is not None and measured.high_fs > constraint.max_fs:
                        actual, limit, side = measured.high_fs, constraint.max_fs, "above maximum"
                    else:
                        continue
                    issues.append(
                        issue(
                            "topology.delay-out-of-range",
                            f"topology {topology.name}: delay {actual} fs {side} {limit} fs ({receipt})",
                            severity=constraint.severity,
                            where=", ".join((topology.name, *ends)),
                            hint="change the routing or the stated delay budget and propagation inputs",
                        )
                    )
                elif constraint.max_mdb is not None and measured.high_mdb > constraint.max_mdb:
                    issues.append(
                        issue(
                            "topology.loss-over-budget",
                            f"topology {topology.name}: loss {measured.high_mdb} mdb "
                            f"above maximum {constraint.max_mdb} mdb ({receipt})",
                            severity=constraint.severity,
                            where=", ".join((topology.name, *ends)),
                            hint="change the routing or the stated loss inputs and budget",
                        )
                    )
            elif constraint.kind == "skew":
                values = [measure_path(topology, topology.nodes[0], end, graph, rules) for end in ends]
                if any(value.status != "ok" for value in values):
                    for value in values:
                        if value.status != "ok" and (found := _unjudged(topology, value, ends)) is not None:
                            issues.append(found)
                    not_judged += 1
                    continue
                judged += 1
                longest = max(value.high_fs for value in values)
                for end, value in zip(ends, values, strict=True):
                    skew = value.high_fs - longest
                    if constraint.max_fs is not None and abs(skew) > constraint.max_fs:
                        issues.append(
                            issue(
                                "topology.skew-out-of-range",
                                f"topology {topology.name}: {end} skew {skew} fs "
                                f"beyond maximum {constraint.max_fs} fs ({'; '.join(value.inputs)})",
                                severity=constraint.severity,
                                where=f"{topology.name}, {end}",
                                hint="match the delays from the root or change the stated skew budget",
                            )
                        )
            else:
                paths = _paths(topology, graph)
                unavailable = next(((edge, path) for edge, path in paths if path.status != "ok"), None)
                if topology.missing_bridges or unavailable is not None:
                    if unavailable is not None:
                        edge, path = unavailable
                        found = _unjudged(topology, Measurement(path.status), (edge.a, edge.b))
                        if found is not None:
                            issues.append(found)
                    not_judged += 1
                    continue
                judged += 1
                if constraint.kind == "order":
                    # A shortest edge path must not reach a later descendant before its declared end.
                    wrong = next(
                        (
                            (edge, pin)
                            for edge, path in paths
                            for pin in topology.nodes
                            if pin in _descendants(topology, edge.b) and pin in path.pads
                        ),
                        None,
                    )
                    if wrong is not None or _has_loop(paths, graph):
                        detail = (
                            f"{wrong[1]} is reached before {wrong[0].b}"
                            if wrong
                            else "copper contains a loop"
                        )
                        issues.append(
                            issue(
                                "topology.order",
                                f"topology {topology.name}: {detail}",
                                severity=constraint.severity,
                                where=topology.name,
                                hint="route the pads in the declared chain order without copper loops",
                            )
                        )
                else:
                    for length in _stubs(paths, graph):
                        if constraint.max_nm is not None and length > constraint.max_nm:
                            issues.append(
                                issue(
                                    "topology.stub-too-long",
                                    f"topology {topology.name}: stub {length} nm "
                                    f"above maximum {constraint.max_nm} nm",
                                    severity=constraint.severity,
                                    where=topology.name,
                                    hint="shorten the unlisted copper branch or change the stub budget",
                                )
                            )
    for constraint in rules.protocol_skews:
        counts["skew"] += 1
        trees = [by_name[name] for name in constraint.topologies]
        values = [measure_path(tree, tree.nodes[0], tree.nodes[-1], graph, rules) for tree in trees]
        if any(value.status != "ok" for value in values):
            not_judged += 1
            for tree, value in zip(trees, values, strict=True):
                if value.status != "ok" and (found := _unjudged(tree, value, tree.nodes)) is not None:
                    issues.append(found)
            continue
        judged += 1
        skew = max(value.high_fs for value in values) - min(value.high_fs for value in values)
        if skew > constraint.max_fs:
            receipt = "; ".join(sorted({item for value in values for item in value.inputs}))
            issues.append(
                issue(
                    "topology.skew-out-of-range",
                    f"interface {constraint.interface}: member skew {skew} fs "
                    f"above maximum {constraint.max_fs} fs ({receipt})",
                    severity=constraint.severity,
                    where=", ".join(constraint.topologies),
                    hint="match the routed pair delays or change the stated protocol budget",
                )
            )
    issues = list(dict.fromkeys(issues))
    level = Evidence.combine(EVIDENCE, evidence)
    if any(found.code == "topology.input-missing" for found in issues):
        level = Evidence(Level.UNVERIFIED, hypotheses=level.hypotheses)
    result = ran(
        STAGE,
        issues,
        level,
        {
            "topologies": len(rules.topologies),
            "constraints": dict(sorted(counts.items())),
            "judged": judged,
            "not_judged": not_judged,
        },
    )
    subjects = for_issues(checked, result.issues)
    if model is not None:
        intent = for_issues(model, result.issues)
        subjects = tuple(
            tuple(
                sorted(
                    set(current) | {subject for subject in cached if subject.kind == "pin"},
                    key=lambda subject: (subject.kind, subject.name, subject.id),
                )
            )
            for current, cached in zip(subjects, intent, strict=True)
        )
    return replace(result, subjects=subjects)


__all__ = ["EVIDENCE", "Measurement", "STAGE", "build_issues", "measure_path", "topology_stage", "tree_path"]


def build_issues(design: Design) -> tuple[Issue, ...]:
    """Missing series bridges are build findings rather than guessed electrical connections."""
    return tuple(
        issue(
            "topology.bridge-missing",
            f"topology {topology.name}: series part {ref} has no bridge",
            where=f"{topology.name}, {ref}",
            hint="declare design.bridge(part, a, b), or a bridge in the device record",
        )
        for topology in (() if design.rules is None else design.rules.topologies)
        for ref in topology.missing_bridges
    )

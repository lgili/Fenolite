# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bounded, deterministic translation proposals with explicit unplaced reasons (c0096)."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, replace

from fenolite.backends.base import BoardFrame, BoardPad, DesignRules
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.geometry import BBox, ceil_sqrt
from fenolite.model import canonical
from fenolite.model.design import Design
from fenolite.placement.constrained_legality import (
    PlacementChecker,
    PlacementCopperFinding,
    PlacementLegality,
    check_constraints,
)
from fenolite.placement.constraints import PlacementConstraints, PlacementObjective

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-CONSTRAINED-PLACE",))
DEFAULT_CONSTRAINTS = PlacementConstraints()


@dataclass(frozen=True)
class Unplaced:
    footprint_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ObjectiveMeasure:
    key: str
    first_pad: str
    second_pad: str
    squared_distance_nm: int | None
    distance_nm: int | None
    contribution_nm: int | None
    max_distance_nm: int | None
    status: str
    reason: str = ""


@dataclass(frozen=True)
class PlacementAssessment:
    """State of supplied placement checks, without electrical readiness or qualification."""

    state: str
    missing_inputs: tuple[str, ...]
    findings: tuple[str, ...]
    evidence: Evidence = EVIDENCE


@dataclass(frozen=True)
class PlacementProposal:
    design: Design
    positions: tuple[tuple[str, Point], ...]
    unplaced: tuple[Unplaced, ...]
    objectives: tuple[ObjectiveMeasure, ...]
    legality: PlacementLegality
    assessment: PlacementAssessment
    intrinsic: tuple[PlacementCopperFinding, ...]
    constraints: PlacementConstraints
    selected: tuple[str, ...]
    candidate_counts: tuple[tuple[str, int], ...]
    source_sha256: str
    request_sha256: str
    evidence: Evidence = EVIDENCE


def measure_objectives(
    pads: Sequence[BoardPad], objectives: Sequence[PlacementObjective]
) -> tuple[ObjectiveMeasure, ...]:
    by_id = {pad.pad_id: pad for pad in pads}
    rows: list[ObjectiveMeasure] = []
    for objective in sorted(objectives, key=lambda row: row.key):
        first, second = by_id.get(objective.first_pad), by_id.get(objective.second_pad)
        reason = "missing pad identity" if first is None or second is None else ""
        if first is not None and second is not None and objective.require_connected:
            if first.net_id is None or first.net_id != second.net_id:
                reason = "pads do not share an assigned net"
        if reason:
            rows.append(
                ObjectiveMeasure(
                    objective.key,
                    objective.first_pad,
                    objective.second_pad,
                    None,
                    None,
                    None,
                    objective.max_distance,
                    "unknown",
                    reason,
                )
            )
            continue
        assert first is not None and second is not None
        squared = (first.position.x - second.position.x) ** 2 + (first.position.y - second.position.y) ** 2
        distance = ceil_sqrt(squared)
        status = (
            "unmet" if objective.max_distance is not None and squared > objective.max_distance**2 else "met"
        )
        rows.append(
            ObjectiveMeasure(
                objective.key,
                objective.first_pad,
                objective.second_pad,
                squared,
                distance,
                distance * objective.weight,
                objective.max_distance,
                status,
            )
        )
    return tuple(rows)


def _set_position(design: Design, footprint_id: str, at: Point) -> Design:
    assert design.board is not None
    return replace(
        design,
        board=replace(
            design.board,
            footprints=tuple(
                replace(fp, position=at) if fp.id == footprint_id else fp for fp in design.board.footprints
            ),
        ),
    )


def _subset(design: Design, footprint_ids: set[str]) -> Design:
    assert design.board is not None
    return replace(
        design,
        board=replace(
            design.board, footprints=tuple(fp for fp in design.board.footprints if fp.id in footprint_ids)
        ),
    )


def propose_placement(
    design: Design,
    frame: BoardFrame,
    selected: Sequence[str],
    *,
    constraints: PlacementConstraints = DEFAULT_CONSTRAINTS,
    objectives: Sequence[PlacementObjective] = (),
    rules: DesignRules | None = None,
    checker: PlacementChecker | None = None,
) -> PlacementProposal:
    """Greedy translations with bounded candidate enumeration; no topology or orientation changes."""
    if len(set(selected)) != len(selected):
        raise ValueError("selected footprint ids must be distinct")
    if len({o.key for o in objectives}) != len(objectives):
        raise ValueError("objective keys must be distinct")
    if design.board is None:
        raise ValueError("placement needs a board")
    source_sha = hashlib.sha256(canonical.dumps(design).encode()).hexdigest()
    ordered = tuple(sorted(selected))
    requested = {
        "selected": ordered,
        "constraints": constraints,
        "objectives": tuple(objectives),
        "rules": rules,
    }
    request_sha = hashlib.sha256(canonical.dumps(requested).encode()).hexdigest()
    by_id = {fp.id: fp for fp in design.board.footprints}
    unknown = set(ordered) - set(by_id)
    if unknown:
        raise ValueError("unknown selected footprints: " + ", ".join(sorted(unknown)))
    for group in constraints.regions:
        if set(group.footprint_ids) - set(by_id):
            raise ValueError(f"region {group.key}: unknown footprint ids")
    fixed = {fp.id for fp in by_id.values() if fp.locked}
    fixed.update(r.footprint_id for r in constraints.reservations if r.fixed)
    taken = (set(by_id) - set(ordered)) | fixed
    working = design
    positions: list[tuple[str, Point]] = []
    unplaced: list[Unplaced] = []
    counts: list[tuple[str, int]] = []
    extents = {e.footprint_id: e for e in frame.placed_extents(design)}
    outline = design.board.outline
    for identity in ordered:
        if identity in fixed:
            counts.append((identity, 0))
            continue
        extent = extents.get(identity)
        if extent is None or not (extent.front or extent.back) or extent.source == "none":
            unplaced.append(Unplaced(identity, ("missing_extent",)))
            counts.append((identity, 0))
            continue
        if outline is None or not outline.points:
            unplaced.append(Unplaced(identity, ("missing_outline",)))
            counts.append((identity, 0))
            continue
        region = BBox.of_points(outline.points)
        points = tuple(p for ring in (*extent.front, *extent.back) for p in ring)
        box = BBox.of_points(points)
        at = by_id[identity].position
        x0 = region.x0 + constraints.edge_clearance - (box.x0 - at.x)
        y0 = region.y0 + constraints.edge_clearance - (box.y0 - at.y)
        x1 = region.x1 - constraints.edge_clearance - (box.x1 - at.x)
        y1 = region.y1 - constraints.edge_clearance - (box.y1 - at.y)
        # Restrict the search lattice before spending the finite candidate budget.
        # Polygon containment is still checked below; these are necessary box bounds.
        for group in constraints.regions:
            if identity in group.footprint_ids:
                bounds = BBox.of_points(group.outline)
                x0 = max(x0, bounds.x0 - (box.x0 - at.x))
                y0 = max(y0, bounds.y0 - (box.y0 - at.y))
                x1 = min(x1, bounds.x1 - (box.x1 - at.x))
                y1 = min(y1, bounds.y1 - (box.y1 - at.y))
        nx, ny = max(0, (x1 - x0) // constraints.pitch + 1), max(0, (y1 - y0) // constraints.pitch + 1)
        best: tuple[tuple[int, int, int, int], Point] | None = None
        reasons: set[str] = set()
        tried = 0
        for index in range(min(nx * ny, constraints.max_candidates)):
            y, x = divmod(index, nx)
            candidate = Point(x0 + x * constraints.pitch, y0 + y * constraints.pitch)
            proposed = _set_position(working, identity, candidate)
            active = _subset(proposed, taken | {identity})
            checked = check_constraints(active, frame, constraints, rules=rules, checker=checker)
            tried += 1
            projection_gaps = tuple(
                m
                for m in checked.missing_inputs
                if m.startswith(
                    (
                        "extent:",
                        "frame:",
                        "copper:copper.item-unsupported",
                        "copper:checker-unavailable",
                        "rules:",
                    )
                )
                and not m.endswith(":conservative")
            )
            if checked.hard or projection_gaps:
                reasons.update(checked.hard)
                reasons.update(projection_gaps)
                continue
            measured = measure_objectives(frame.board_pads(active), objectives)
            score = (
                sum(m.status == "unmet" for m in measured),
                sum(m.contribution_nm or 0 for m in measured),
                candidate.y,
                candidate.x,
            )
            if best is None or score < best[0]:
                best = (score, candidate)
            if not objectives:
                break
        counts.append((identity, tried))
        if best is None:
            why = (
                "search_budget_exhausted" if nx * ny > constraints.max_candidates else "no_feasible_candidate"
            )
            unplaced.append(Unplaced(identity, (why, *sorted(reasons))))
            continue
        working = _set_position(working, identity, best[1])
        positions.append((identity, best[1]))
        taken.add(identity)
    active = _subset(working, taken)
    legality = check_constraints(active, frame, constraints, rules=rules, checker=checker)
    # Retain intrinsic package findings of unplaced parts as well: placement cannot repair their geometry.
    all_copper = check_constraints(working, frame, constraints, rules=rules, checker=checker).copper
    intrinsic = tuple(f for f in all_copper.findings if f.relation == "intrinsic")
    kept = tuple(f for f in legality.copper.findings if f.relation != "intrinsic") + intrinsic
    measured = measure_objectives(frame.board_pads(active), objectives)
    missing = tuple(sorted(set((*legality.missing_inputs, *legality.mechanical.missing_inputs))))
    findings = tuple(
        sorted(
            set(
                (
                    *legality.hard,
                    *(f"{f.code}:{f.where}" for f in kept),
                    *(f"unplaced:{u.footprint_id}" for u in unplaced),
                    *(f"objective:{m.key}:{m.status}" for m in measured if m.status != "met"),
                )
            )
        )
    )
    state = "findings" if findings else "incomplete" if missing else "checked"
    assessment = PlacementAssessment(state, missing, findings)
    return PlacementProposal(
        working,
        tuple(positions),
        tuple(unplaced),
        measured,
        legality,
        assessment,
        intrinsic,
        constraints,
        ordered,
        tuple(counts),
        source_sha,
        request_sha,
    )


__all__ = [
    "PlacementAssessment",
    "Unplaced",
    "ObjectiveMeasure",
    "PlacementProposal",
    "measure_objectives",
    "propose_placement",
]

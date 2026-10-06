# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Hard placement checks with the shared copper and mounted-volume contracts (c0096)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from itertools import combinations
from typing import Protocol

from fenolite.backends.base import BoardFrame, DesignRules
from fenolite.core.coords import Point
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence
from fenolite.geometry.thick import Thick, thick_closer_than, thick_touch
from fenolite.model.design import Design
from fenolite.placement.constraints import MechanicalReview, PlacementConstraints, review_mechanics
from fenolite.placement.legality import check, ring_inside, rings_overlap


@dataclass(frozen=True)
class PlacementCopperFinding:
    code: str
    severity: Severity
    layer: str
    at: Point
    items: tuple[object, ...]
    gap: int
    clearance: int | None
    source: str
    message: str
    relation: str
    where: str

    def to_issue(self) -> Issue:
        return Issue(self.code, self.severity, self.message, self.where)


@dataclass(frozen=True)
class CopperInspection:
    findings: tuple[PlacementCopperFinding, ...] = ()
    issues: tuple[Issue, ...] = ()
    summary: Mapping[str, object] = field(default_factory=lambda: {})
    evidence: Evidence = Evidence()


@dataclass(frozen=True)
class MechanicalFinding:
    code: str
    first: str
    second: str
    status: str
    reason: str


@dataclass(frozen=True)
class MechanicalInspection:
    projections: tuple[object, ...] = ()
    findings: tuple[MechanicalFinding, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    evidence: Evidence = Evidence()


@dataclass(frozen=True)
class PlacementLegality:
    hard: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    copper: CopperInspection
    mechanical: MechanicalInspection
    reservations: MechanicalReview

    @property
    def intrinsic(self) -> tuple[PlacementCopperFinding, ...]:
        return tuple(f for f in self.copper.findings if f.relation == "intrinsic")


class PlacementChecker(Protocol):
    def __call__(
        self,
        design: Design,
        frame: BoardFrame,
        constraints: PlacementConstraints,
        *,
        rules: DesignRules | None = None,
    ) -> PlacementLegality: ...


def check_geometry(
    design: Design, frame: BoardFrame, constraints: PlacementConstraints, *, rules: DesignRules | None = None
) -> PlacementLegality:
    """Judge supplied hard geometry; retain every intrinsic finding and all projection gaps."""
    board = design.board
    frame_issues: list[Issue] = []
    pads = frame.board_pads(design, issues=frame_issues)
    extents = frame.placed_extents(design, issues=frame_issues)
    names = {fp.id: fp.id for fp in board.footprints} if board is not None else {}
    rings = (board.outline.points, *board.outline.cutouts) if board is not None and board.outline else ()
    hard = [
        f"{i.code}:{i.where}"
        for i in check(extents, rings, edge_clearance=constraints.edge_clearance, names=names)
        if i.severity in ("error", "warning")
    ]
    missing = [f"frame:{i.code}:{i.where}" for i in frame_issues if i.severity != "info"]
    for extent in extents:
        if extent.source == "none" or not (extent.front or extent.back):
            missing.append(f"extent:{extent.footprint_id}")
        elif not extent.exact:
            missing.append(f"extent:{extent.footprint_id}:conservative")
        for group in constraints.regions:
            if extent.footprint_id in group.footprint_ids and any(
                not ring_inside(ring, group.outline) for ring in (*extent.front, *extent.back)
            ):
                hard.append(f"region:{group.key}:{extent.footprint_id}")
    if not rings:
        missing.append("board_outline")
    elif board is not None and board.outline is not None:
        for extent in extents:
            if any(
                rings_overlap(ring, cutout)
                for ring in (*extent.front, *extent.back)
                for cutout in board.outline.cutouts
            ):
                hard.append(f"cutout:{extent.footprint_id}")
    for first, second in combinations(extents, 2):
        if first.footprint_id == second.footprint_id:
            continue
        for face in ("front", "back"):
            if constraints.gap and any(
                thick_closer_than(Thick(a, 0, True), Thick(b, 0, True), constraints.gap)
                for a in getattr(first, face)
                for b in getattr(second, face)
            ):
                hard.append(f"gap:{first.footprint_id}:{second.footprint_id}:{face}")
    if board is not None:
        for keepout in board.keepouts:
            area = Thick(keepout.outline, 0, True)
            if keepout.no_footprints:
                for extent in extents:
                    for face, layer in (("front", "F.Cu"), ("back", "B.Cu")):
                        if layer in keepout.layers and any(
                            rings_overlap(ring, keepout.outline, touching_overlaps=True)
                            for ring in getattr(extent, face)
                        ):
                            hard.append(f"keepout:{keepout.id}:{extent.footprint_id}:{face}")
            if keepout.no_pads:
                for pad in pads:
                    if any(
                        (entry.layer in keepout.layers)
                        and thick_touch(area, Thick(entry.core, entry.width, entry.filled))
                        for entry in pad.copper
                    ):
                        hard.append(f"keepout:{keepout.id}:{pad.pad_id}:pad")
        drills = [(p.pad_id, p.footprint_id, Thick(p.hole, p.drill)) for p in pads if p.hole and p.drill]
        drills += [(h.id, "", Thick((h.position,), h.drill)) for h in board.holes]
        for (first_id, first_fp, first), (second_id, second_fp, second) in combinations(drills, 2):
            if first_fp and first_fp == second_fp:
                continue
            if thick_touch(first, second):
                hard.append(f"drill:{first_id}:{second_id}")
        # An opposite-face drill can damage surface copper even without a courtyard on that face.
        for drill_id, footprint_id, drill in drills:
            for pad in pads:
                if pad.pad_id == drill_id or (footprint_id and pad.footprint_id == footprint_id):
                    continue
                if any(thick_touch(drill, Thick(e.core, e.width, e.filled)) for e in pad.copper):
                    hard.append(f"drill-copper:{drill_id}:{pad.pad_id}")
    reservation_review = review_mechanics(design, pads, constraints.reservations)
    hard.extend("duplicate-drill:" + ",".join(ids) for ids in reservation_review.duplicate_drills)
    missing.extend(reservation_review.missing_inputs)
    missing.extend(("copper:checker-unavailable", "mechanical:checker-unavailable"))
    return PlacementLegality(
        tuple(sorted(set(hard))),
        tuple(sorted(set(missing))),
        CopperInspection(),
        MechanicalInspection(missing_inputs=("mechanical:checker-unavailable",)),
        reservation_review,
    )


def check_constraints(
    design: Design,
    frame: BoardFrame,
    constraints: PlacementConstraints,
    *,
    rules: DesignRules | None = None,
    checker: PlacementChecker | None = None,
) -> PlacementLegality:
    """Use an injected checker; absent copper/mechanical checking remains explicitly incomplete."""
    if checker is not None:
        return checker(design, frame, constraints, rules=rules)
    return check_geometry(design, frame, constraints, rules=rules)


__all__ = [
    "PlacementLegality",
    "PlacementChecker",
    "PlacementCopperFinding",
    "CopperInspection",
    "MechanicalFinding",
    "MechanicalInspection",
    "check_geometry",
    "check_constraints",
]

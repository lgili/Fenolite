# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""CLI orchestration of neutral placement checks; the placement kernel imports no checker (c0096). The
copper relation is c0097's ``CopperFinding.relation`` and the mechanical provider is c0099's typed
``fenolite.analysis.body_volumes`` (task R5)."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Collection
from dataclasses import replace
from functools import reduce
from typing import NamedTuple, TypeVar

from fenolite.analysis.body_volumes import BodyVolume, VolumeConstraints, body_volume, check_body_volumes
from fenolite.backends.base import BoardFrame, DesignRules
from fenolite.checks.clearance import ClearanceResolver
from fenolite.checks.copper import check_copper
from fenolite.geometry.errors import GeometryError
from fenolite.geometry.index import SpatialIndex
from fenolite.geometry.shapes import BBox
from fenolite.geometry.thick import Thick, thick_bbox
from fenolite.model.board import placed_keepout
from fenolite.model.design import Design
from fenolite.placement.constrained_legality import (
    CopperInspection,
    MechanicalFinding,
    MechanicalInspection,
    PlacementCopperFinding,
    PlacementLegality,
    check_geometry,
)
from fenolite.placement.constraints import MechanicalVolume, PlacementConstraints


def _volume(volume: MechanicalVolume) -> BodyVolume:
    """A supplied request volume as the body-volume check takes it: the same fields, unchanged."""
    return BodyVolume(volume.name, volume.outline, volume.z_min, volume.z_max, volume.status)


def _mechanical(design: Design, constraints: PlacementConstraints) -> MechanicalInspection:
    """The c0099 body-volume check on the supplied volumes and reservations; its unknowns and missing
    inputs are kept, never read as a mechanical success."""
    supplied = constraints.volumes
    reservations = tuple(v for row in constraints.reservations for v in row.volumes)
    volumes = VolumeConstraints(
        board_thickness=supplied.board_thickness,
        allowed_penetrations=tuple(_volume(v) for v in supplied.allowed_penetrations),
        obstacles=tuple(_volume(v) for v in (*supplied.obstacles, *reservations)),
        missing_assembly=supplied.missing_assembly,
    )
    report = check_body_volumes(design, volumes)
    return MechanicalInspection(
        tuple(report.projections),
        tuple(MechanicalFinding(f.code, f.first, f.second, f.status, f.reason) for f in report.findings),
        tuple(report.missing_inputs),
        report.evidence,
    )


def check_placement_constraints(
    design: Design,
    frame: BoardFrame,
    constraints: PlacementConstraints,
    *,
    rules: DesignRules | None = None,
) -> PlacementLegality:
    """Combine existing geometry/copper verdicts and the mechanical provider without exemptions."""
    basic = check_geometry(design, frame, constraints, rules=rules)
    pads = frame.board_pads(design)
    report = check_copper(
        design,
        pads=pads,
        min_clearance=rules.min_clearance if rules else None,
        rules_over_classes=rules.rules_over_classes if rules else True,
        floor_over_rules=rules.floor_over_rules if rules else False,
        tolerance=rules.clearance_tolerance if rules else 0,
        tolerance_source=rules.tolerance_source if rules else "",
    )
    findings = [
        PlacementCopperFinding(
            found.code,
            found.severity,
            found.layer,
            found.at,
            found.items,
            found.gap,
            found.clearance,
            found.source,
            found.message,
            found.relation,
            found.where,
        )
        for found in report.findings
    ]
    copper = CopperInspection(tuple(findings), report.issues, report.summary, report.evidence)
    hard = [*basic.hard, *(f"copper:{f.code}:{f.where}" for f in findings if f.relation != "intrinsic")]
    missing = [
        x
        for x in basic.missing_inputs
        if x not in ("copper:checker-unavailable", "mechanical:checker-unavailable")
    ]
    missing.extend(
        f"copper:{i.code}"
        for i in report.issues
        if i.code in ("copper.item-unsupported", "copper.clearance-unset", "copper.rules-incomplete")
    )
    if rules is not None:
        missing.extend(f"rules:{name}" for name, _ in rules.unread)
        if rules.opaque_clearance_rules:
            missing.append("rules:opaque_clearance")
    mechanical = _mechanical(design, constraints)
    hard.extend(f"{f.code}:{f.first}:{f.second}" for f in mechanical.findings if f.status != "unknown")
    missing.extend(mechanical.missing_inputs)
    missing.extend(f"{f.code}:{f.reason}" for f in mechanical.findings if f.status == "unknown")
    return replace(
        basic,
        hard=tuple(sorted(set(hard))),
        missing_inputs=tuple(sorted(set(missing))),
        copper=copper,
        mechanical=mechanical,
    )


T = TypeVar("T")


class _Tally(NamedTuple):
    hard: Counter[str]
    missing: Counter[str]
    copper: Counter[PlacementCopperFinding]
    mechanical: Counter[MechanicalFinding]
    mechanical_missing: Counter[str]


def _footprint_boxes(design: Design, frame: BoardFrame) -> dict[str, BBox]:
    """Footprint id → a box holding its pad copper, drills, placed extents, rule areas and body outlines."""
    assert design.board is not None
    boxes: dict[str, list[BBox]] = defaultdict(list)
    for pad in frame.board_pads(design):
        try:
            shapes = [Thick(e.core, e.width, e.filled) for e in pad.copper]
            if pad.hole and pad.drill:
                shapes.append(Thick(pad.hole, pad.drill))
        except (GeometryError, ValueError):
            continue  # the copper check leaves out a pad it cannot shape
        boxes[pad.footprint_id].extend(thick_bbox(shape) for shape in shapes)
    for extent in frame.placed_extents(design):
        boxes[extent.footprint_id].extend(BBox.of_points(ring) for ring in (*extent.front, *extent.back))
    for fp in design.board.footprints:
        boxes[fp.id].extend(
            BBox.of_points(placed_keepout(fp, area).outline) for area in fp.keepouts if area.outline
        )
        for body in fp.bodies:
            volume = body_volume(body, fp, board_thickness=0).volume
            if volume is not None:
                boxes[fp.id].append(BBox.of_points(volume.outline))
    return {ident: reduce(BBox.union, rows) for ident, rows in boxes.items() if rows}


def _tally(legality: PlacementLegality) -> _Tally:
    """The verdicts an evaluation reads, each as a multiset."""
    return _Tally(
        Counter(legality.hard),
        Counter(legality.missing_inputs),
        Counter(legality.copper.findings),
        Counter(legality.mechanical.findings),
        Counter(legality.mechanical.missing_inputs),
    )


def _added(base: Counter[T], before: Counter[T], after: Counter[T]) -> Counter[T] | None:
    """``base`` with what ``after`` adds to ``before``; ``None`` when ``after`` lacks some of ``before``."""
    return None if before - after else base + (after - before)


class MovedPartsCheck:
    """``check_placement_constraints`` of boards made of ``fixed`` and some placed footprints, judging again
    only what lies near the placed ones (change c0487, follow-up 2026-11-17).

    ``fixed`` is checked once. A board is then cut to its placed footprints and the footprints, tracks and
    vias of ``fixed`` whose boxes lie within reach of them (the largest clearance, hole clearance and gap);
    everything else of the board is kept whole. The cut board is checked without and with the placed
    footprints, and the verdicts are those of ``fixed`` plus what the placed footprints add. When they take
    any verdict away (a group such as a duplicate drill changes), or a placed footprint holds a rule area
    (which changes the rules of the copper inside it), the whole board is checked instead.

    The ``hard``, ``missing_inputs``, copper findings and mechanical findings and missing inputs are those of
    the whole board's check (the copper findings sorted as the copper check sorts them); the copper issues
    and summary are left empty and ``reservations`` is the cut board's."""

    def __init__(
        self,
        fixed: Design,
        frame: BoardFrame,
        constraints: PlacementConstraints,
        *,
        rules: DesignRules | None = None,
    ) -> None:
        board = fixed.board
        assert board is not None
        self.frame, self.constraints, self.rules = frame, constraints, rules
        self.base = check_placement_constraints(fixed, frame, constraints, rules=rules)
        self._base = _tally(self.base)
        resolver = ClearanceResolver(
            fixed,
            min_clearance=rules.min_clearance if rules else None,
            rules_over_classes=rules.rules_over_classes if rules else True,
            floor_over_rules=rules.floor_over_rules if rules else False,
        )
        self.reach = max(resolver.max_value, resolver.max_hole, constraints.gap) + 1
        boxes = _footprint_boxes(fixed, frame)
        self._footprints = SpatialIndex[str].build((box, ident) for ident, box in boxes.items())
        self._tracks = SpatialIndex[int].build(
            (thick_bbox(Thick((t.start, t.end), t.width)), n) for n, t in enumerate(board.tracks)
        )
        self._vias = SpatialIndex[int].build(
            (thick_bbox(Thick((v.position,), v.diameter)), n) for n, v in enumerate(board.vias)
        )
        self.windows = 0
        """The evaluations judged on a cut board; the others checked the whole board."""

    def full(self, design: Design) -> PlacementLegality:
        return check_placement_constraints(design, self.frame, self.constraints, rules=self.rules)

    def __call__(self, design: Design, placed: Collection[str]) -> PlacementLegality:
        """The check of ``design``: the footprints of ``fixed`` with the same values and order, and the
        footprints ``placed``; every other part of its board as in ``fixed``."""
        board = design.board
        assert board is not None
        moved = tuple(fp for fp in board.footprints if fp.id in placed)
        if not moved:
            return self.base
        if any(fp.keepouts for fp in moved):
            return self.full(design)
        own = _footprint_boxes(replace(design, board=replace(board, footprints=moved)), self.frame)
        window = reduce(BBox.union, own.values()).inflate(self.reach) if own else None
        near: set[str] = set(self._footprints.query(window)) if window else set()
        tracks: set[int] = set(self._tracks.query(window)) if window else set()
        vias: set[int] = set(self._vias.query(window)) if window else set()
        cut = replace(
            board,
            footprints=tuple(fp for fp in board.footprints if fp.id in near),
            tracks=tuple(t for n, t in enumerate(board.tracks) if n in tracks),
            vias=tuple(v for n, v in enumerate(board.vias) if n in vias),
        )
        without = _tally(self.full(replace(design, board=cut)))
        found = self.full(
            replace(
                design,
                board=replace(
                    cut, footprints=tuple(fp for fp in board.footprints if fp.id in near or fp.id in placed)
                ),
            )
        )
        with_moved = _tally(found)
        merged = (
            _added(self._base.hard, without.hard, with_moved.hard),
            _added(self._base.missing, without.missing, with_moved.missing),
            _added(self._base.copper, without.copper, with_moved.copper),
            _added(self._base.mechanical, without.mechanical, with_moved.mechanical),
            _added(self._base.mechanical_missing, without.mechanical_missing, with_moved.mechanical_missing),
        )
        hard, missing, copper, mechanical, mechanical_missing = merged
        if (
            hard is None
            or missing is None
            or copper is None
            or mechanical is None
            or mechanical_missing is None
        ):
            return self.full(design)
        self.windows += 1
        findings = sorted(copper.elements(), key=lambda f: (f.code, f.where, f.message))
        return replace(
            found,
            hard=tuple(sorted(hard)),
            missing_inputs=tuple(sorted(missing)),
            copper=CopperInspection(tuple(findings), evidence=found.copper.evidence),
            mechanical=MechanicalInspection(
                (),
                tuple(mechanical.elements()),
                tuple(mechanical_missing.elements()),
                found.mechanical.evidence,
            ),
        )


__all__ = ["MovedPartsCheck", "check_placement_constraints"]

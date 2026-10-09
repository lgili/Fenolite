# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""CLI orchestration of neutral placement checks; the placement kernel imports no checker (c0096). The
copper relation is c0097's ``CopperFinding.relation`` and the mechanical provider is c0099's typed
``fenolite.analysis.body_volumes`` (task R5)."""

from __future__ import annotations

from dataclasses import replace

from fenolite.analysis.body_volumes import BodyVolume, VolumeConstraints, check_body_volumes
from fenolite.backends.base import BoardFrame, DesignRules
from fenolite.checks.copper import check_copper
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


__all__ = ["check_placement_constraints"]

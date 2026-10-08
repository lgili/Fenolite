# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The CLI checker uses c0099's typed body-volume provider on supplied inputs, keeps its unknowns, and takes
the copper relation of c0097's findings (c0096, task R5)."""

from types import SimpleNamespace

import pytest

from fenolite.analysis.body_volumes import BodyVolume, VolumeConstraints
from fenolite.backends.kicad import frame
from fenolite.checks.copper import check_copper
from fenolite.cli import placement_checks
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.placement.constraints import (
    MechanicalConstraints,
    MechanicalReservation,
    MechanicalVolume,
    PlacementConstraints,
)

from ._constrained_fixture import board, part


def test_integrated_provider_never_reports_mechanical_success() -> None:
    """A part without a body is a missing input of the real provider, never a clear verdict."""
    inputs = PlacementConstraints(volumes=MechanicalConstraints(missing_assembly=("supplied:fixture",)))
    design = board(part("A", 10, 10))
    report = placement_checks.check_placement_constraints(design, frame, inputs)
    assert "copper:checker-unavailable" not in report.missing_inputs
    assert "mechanical:checker-unavailable" not in report.missing_inputs
    assert "supplied:fixture" in report.missing_inputs
    assert "board_thickness" in report.missing_inputs
    assert any(name.startswith("body:") for name in report.missing_inputs)
    assert report.mechanical.evidence.level == Level.INFERRED


def test_provider_gets_exact_typed_inputs_and_preserves_known_and_unknown_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = []
    findings = (
        SimpleNamespace(
            code="body.intersection", first="A", second="fixture", status="exact", reason="overlap"
        ),
        SimpleNamespace(code="body.unknown", first="B", second="", status="unknown", reason="projection"),
    )
    evidence = Evidence(Level.INFERRED)

    def inspect(design, volumes):
        captured.append((design, volumes))
        return SimpleNamespace(
            projections=("retained projection",),
            findings=findings,
            missing_inputs=("supplied:fixture",),
            evidence=evidence,
        )

    monkeypatch.setattr(placement_checks, "check_body_volumes", inspect)
    ring = (Point(1, 1), Point(3, 1), Point(3, 3), Point(1, 3))
    obstacle = MechanicalVolume("fixture", ring, 0, 8)
    access = MechanicalVolume("access", ring, -2, 4)
    inputs = PlacementConstraints(
        volumes=MechanicalConstraints(2, (access,), (obstacle,), ("supplied:fixture",)),
        reservations=(MechanicalReservation("reserved", "A", "p_A", (access,)),),
    )
    design = board(part("A", 10, 10, drill=2))
    report = placement_checks.check_placement_constraints(design, frame, inputs)
    typed_obstacle = BodyVolume("fixture", ring, 0, 8)
    typed_access = BodyVolume("access", ring, -2, 4)
    assert captured == [
        (
            design,
            VolumeConstraints(2, (typed_access,), (typed_obstacle, typed_access), ("supplied:fixture",)),
        )
    ]
    assert "body.intersection:A:fixture" in report.hard
    assert "body.unknown:projection" in report.missing_inputs
    assert "body.unknown:B:" not in report.hard
    assert "mechanical:checker-unavailable" not in report.missing_inputs
    assert report.mechanical.evidence == evidence
    assert report.mechanical.projections == ("retained projection",)
    assert len(report.mechanical.findings) == 2


def test_copper_relation_is_the_finding_relation() -> None:
    """Every placement copper finding carries the relation c0097 gives the same finding."""
    design = board(part("A", 10, 10, two_pads=True), part("B", 20, 10, two_pads=True))
    report = placement_checks.check_placement_constraints(design, frame, PlacementConstraints())
    direct = check_copper(design, pads=frame.board_pads(design))
    assert [f.relation for f in report.copper.findings] == [f.relation for f in direct.findings]
    assert {f.relation for f in report.copper.findings} >= {"intrinsic", "inter_component"}

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Optional mechanical provider orchestration uses supplied inputs and retains unknowns."""

from types import SimpleNamespace

import pytest

from fenolite.backends.kicad import frame
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


def test_missing_provider_never_reports_mechanical_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def absent(name):
        raise ModuleNotFoundError(name=name)

    monkeypatch.setattr(placement_checks.importlib, "import_module", absent)
    inputs = PlacementConstraints(volumes=MechanicalConstraints(missing_assembly=("supplied:fixture",)))
    report = placement_checks.check_placement_constraints(board(part("A", 10, 10)), frame, inputs)
    assert "copper:checker-unavailable" not in report.missing_inputs
    assert "mechanical:checker-unavailable" in report.missing_inputs
    assert "supplied:fixture" in report.missing_inputs
    assert not report.mechanical.projections


def test_provider_gets_exact_inputs_and_preserves_known_and_unknown_findings(
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

    provider = SimpleNamespace(VolumeConstraints=MechanicalConstraints, check_body_volumes=inspect)
    monkeypatch.setattr(placement_checks.importlib, "import_module", lambda name: provider)
    ring = (Point(1, 1), Point(3, 1), Point(3, 3), Point(1, 3))
    obstacle = MechanicalVolume("fixture", ring, 0, 8)
    access = MechanicalVolume("access", ring, -2, 4)
    inputs = PlacementConstraints(
        volumes=MechanicalConstraints(2, (access,), (obstacle,), ("supplied:fixture",)),
        reservations=(MechanicalReservation("reserved", "A", "p_A", (access,)),),
    )
    design = board(part("A", 10, 10, drill=2))
    report = placement_checks.check_placement_constraints(design, frame, inputs)
    assert captured == [
        (design, MechanicalConstraints(2, (access,), (obstacle, access), ("supplied:fixture",)))
    ]
    assert "body.intersection:A:fixture" in report.hard
    assert "body.unknown:projection" in report.missing_inputs
    assert "body.unknown:B:" not in report.hard
    assert "mechanical:checker-unavailable" not in report.missing_inputs
    assert report.mechanical.evidence == evidence
    assert report.mechanical.projections == ("retained projection",)
    assert len(report.mechanical.findings) == 2


def test_missing_nested_dependency_is_not_misreported_as_absent_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(name):
        raise ModuleNotFoundError(name="provider_nested_dependency")

    monkeypatch.setattr(placement_checks.importlib, "import_module", broken)
    with pytest.raises(ModuleNotFoundError) as caught:
        placement_checks.check_placement_constraints(board(part("A", 10, 10)), frame, PlacementConstraints())
    assert caught.value.name == "provider_nested_dependency"

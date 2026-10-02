# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Neutral result types of ``fenolite.backends.base`` (capability backend-protocol)."""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest
from _boards import created_board

from fenolite.backends import base, registry
from fenolite.backends.base import (
    DrcItem,
    DrcOutcome,
    DrcReport,
    DrcViolation,
    ProjectSet,
    RoundTrip,
    SkippedFile,
    WriteResult,
)
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pcb import write_board
from fenolite.core.coords import Point


def test_write_result_is_immutable() -> None:
    result = WriteResult(text="(kicad_pcb)\n")
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.text = ""  # type: ignore[misc]
    assert result.issues == ()


def test_capability_default_target_among_targets() -> None:
    for backend in registry.all_backends():
        report = backend.capabilities()
        if report.write_kinds:
            assert report.default_target in report.targets, backend.name


def test_capability_write_advertised_and_implemented() -> None:
    backend = KicadBackend()
    operations = backend.capabilities().operations
    assert {"write", "lower", "validate"} <= set(operations)
    design = created_board()
    assert backend.write(design) == write_board(design, target=10)
    assert callable(backend.lower) and callable(backend.validate)
    assert backend.write(design, target=9, allow_lossy=True) == write_board(design, target=9)


def violation(kind: str) -> DrcViolation:
    item = DrcItem(uuid="u", description="d", position=Point(1, 2))
    return DrcViolation(type=kind, description=kind, severity="error", items=(item,))


def test_violations_by_type() -> None:
    clearance, mismatch = violation("clearance"), violation("lib_footprint_mismatch")
    report = DrcReport(
        source="b", date="d", kicad_version="10.0.6", coordinate_units="mm",
        violations=(clearance, mismatch, clearance), unconnected_items=(violation("unconnected_items"),),
    )  # fmt: skip
    assert report.of_type("lib_footprint_mismatch") == (mismatch,)
    assert report.of_type("clearance") == (clearance, clearance) and report.of_type("other") == ()


def test_integer_positions_only() -> None:
    with pytest.raises(TypeError):
        DrcItem(uuid="u", description="d", position=Point(1.5, 0))  # type: ignore[arg-type]


def test_drc_types_are_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        violation("x").type = "y"  # type: ignore[misc]


def test_board_outside_the_files() -> None:
    with pytest.raises(ValueError, match="a.kicad_pcb"):
        ProjectSet(root=Path("p"), board="a.kicad_pcb", files={})


@pytest.mark.parametrize("name", ["/abs.kicad_pcb", "../up.kicad_pcb", "a\\b.kicad_pcb", "a//b", ""])
def test_project_names_are_relative_posix(name: str) -> None:
    with pytest.raises(ValueError, match="relative POSIX"):
        ProjectSet(root=Path("p"), board="b.kicad_pcb", files={"b.kicad_pcb": Path("b"), name: Path("x")})


def test_project_set_is_immutable() -> None:
    project = ProjectSet(root=Path("p"), board="b.kicad_pcb", files={"b.kicad_pcb": Path("p/b.kicad_pcb")},
                         skipped=(SkippedFile("x.pretty", "missing"),))  # fmt: skip
    with pytest.raises(dataclasses.FrozenInstanceError):
        project.board = "c.kicad_pcb"  # type: ignore[misc]
    assert project.has_project is False and project.has_rules is False


def test_inconsistent_round_trip_refused() -> None:
    with pytest.raises(ValueError, match="passed"):
        RoundTrip(
            level="RT1", passed=True, tree_equal=False, model_equal=True, opaque_equal=True, opaque_count=0
        )
    with pytest.raises(ValueError):
        RoundTrip(
            level="RT1", passed=False, tree_equal=True, model_equal=True, opaque_equal=True, opaque_count=0
        )
    ok = RoundTrip(
        level="RT1", passed=True, tree_equal=True, model_equal=True, opaque_equal=True, opaque_count=3
    )
    assert ok.difference == ""


def test_outcome_is_immutable() -> None:
    outcome = DrcOutcome(report=None, tool_version="10.0.6", canary="not-applicable")
    with pytest.raises(dataclasses.FrozenInstanceError):
        outcome.canary = "fired"  # type: ignore[misc]
    assert outcome.outcome == "exit" and outcome.returncode == 0 and outcome.tool_writes == ()


def test_base_imports_no_backend() -> None:
    tree = ast.parse(Path(base.__file__).read_text(encoding="utf-8"))
    names = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    names |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not {n for n in names if n.startswith("fenolite.backends.")}

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Neutral result types of ``fenolite.backends.base`` (capability backend-protocol)."""

from __future__ import annotations

import dataclasses

import pytest
from _boards import created_board

from fenolite.backends import registry
from fenolite.backends.base import DrcItem, DrcReport, DrcViolation, WriteResult
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
    assert "write" in operations and "lower" in operations and "validate" not in operations
    design = created_board()
    assert backend.write(design) == write_board(design, target=10)
    assert callable(backend.lower)
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

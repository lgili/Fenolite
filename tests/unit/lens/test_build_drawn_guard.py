# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The guard of a build with a drawn schematic (capability design-dsl, "Drawn schematic build guard"; change
c0276)."""

from __future__ import annotations

import dataclasses
import subprocess

import _drawn
import pytest

from fenolite.backends.kicad import drawn as kdrawn
from fenolite.backends.kicad.schgen import GeneratedSchematic
from fenolite.core.coords import Point
from fenolite.lens import build as build_mod
from fenolite.model.schematic import Wire


def test_lowering_defect_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Lowering defect caught": a wire end moved onto another pin by a faulty lowering."""
    real = kdrawn.lower_drawn

    def faulty(*args: object, **kwargs: object) -> GeneratedSchematic:
        lowered = real(*args, **kwargs)  # type: ignore[arg-type]
        wires = list(lowered.sheet.wires)
        # the last segment of the SDA wire ends on R1 pin 1 at (123.19, 76.2); stop it short of the pin
        index = next(i for i, w in enumerate(wires) if w.end == Point(123_190_000, 76_200_000))
        wires[index] = Wire(id=wires[index].id, start=wires[index].start, end=Point(123_190_000, 72_390_000))
        return dataclasses.replace(lowered, sheet=dataclasses.replace(lowered.sheet, wires=tuple(wires)))

    monkeypatch.setattr(kdrawn, "lower_drawn", faulty)
    output = _drawn.build("example")
    assert output.files == {}
    differs = [i for i in output.issues if i.code == "build.schematic-netlist-differs"]
    assert len(differs) == 1 and differs[0].where == "R1-1" and differs[0].severity == "error"


def test_hermetic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Hermetic"."""

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the build runs no tool")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    output = _drawn.build("example")
    assert output.files and not [i for i in output.issues if i.severity == "error"]


def test_the_generated_guard_does_not_run(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the guard of generated sheets runs for generated sheets only")

    monkeypatch.setattr(build_mod, "schematic_netlist_issue", refuse)
    for name in _drawn.NAMES:
        output = _drawn.build(name)
        assert output.files, name

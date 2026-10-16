# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Slots and cut-outs in the round trips of an Altium document (capability altium-verification, "Slots and
cut-outs in the round trips"; change c0168)."""

from __future__ import annotations

import dataclasses
import tempfile
from pathlib import Path
from typing import cast

import _altium_slotcases as cases
import pytest

from fenolite.backends.altium import pcbdoc
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.roundtrip import RT_A2_SCOPE, rt_a0, rt_a1
from fenolite.backends.base import ProjectRead, ReadResult
from fenolite.checks.rta2 import rta2_stage
from fenolite.checks.stages import StageResult
from fenolite.core.coords import Point
from fenolite.model.design import Design

BACKEND = AltiumBackend()


def _read(data: bytes) -> ReadResult:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "slots.PcbDoc"
        path.write_bytes(data)
        return BACKEND.read(path)


def _rta2(model: Design, result: ReadResult, reading: Design) -> StageResult:
    """RT-A2 as ``checks.documents`` runs it: the reading in the model's frame, the cut-outs compared."""
    moved = BACKEND.in_model_frame(model, reading)
    read = ProjectRead(None, dataclasses.replace(result, content=moved))
    return rta2_stage(model, read, RT_A2_SCOPE, cutouts=BACKEND.cutout_differences(model, moved))


def _design(result: ReadResult) -> Design:
    assert isinstance(result.content, Design)
    return result.content


def test_fixture_passes_rt_a0_to_rt_a2(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Fixture passes RT-A0 to RT-A2": the written fixture with the gate on passes the three
    levels, holes and cut-out rings compared; a cut-out moved by 2 µm in the read model gives one RT-A2
    finding naming it."""
    pytest.importorskip("pyclipper")
    monkeypatch.setattr(pcbdoc, "CUTOUT_REGIONS", True)
    output = cases.fixture_build(gate=True)
    data = output.files["slots.PcbDoc"]
    for verdict in (rt_a0(data, kind="altium_pcbdoc"), rt_a1(data, kind="altium_pcbdoc")):
        assert verdict.judged and verdict.passed, verdict.difference
    result = _read(data)
    reading = _design(result)
    model = output.design
    assert model.board is not None and len(model.board.holes) == 4
    stage = _rta2(model, result, reading)
    assert stage.summary["holds"] is True, stage.issues
    compared = stage.summary["compared"]
    assert {"cutout", "hole"} <= set(cast(dict[str, list[str]], compared)["pcb"])
    # one cut-out moved by 2 µm in the read model
    board = reading.board
    assert board is not None
    graphics = list(board.graphics)
    (index,) = [i for i, g in enumerate(graphics) if g.kind == "polygon" and len(g.points) == 130]
    shifted = graphics[index]
    graphics[index] = dataclasses.replace(
        shifted, points=tuple(Point(p.x + 2_000, p.y) for p in shifted.points)
    )
    moved = dataclasses.replace(reading, board=dataclasses.replace(board, graphics=tuple(graphics)))
    stage = _rta2(model, result, moved)
    assert stage.summary["differences"] == 1
    (finding,) = stage.issues
    assert finding.where.startswith("pcb:/cutout/") and finding.code == "check.rta2-failed"


def test_a_moved_hole_is_one_finding() -> None:
    """With the gate off nothing of the cut-outs is compared, and a hole of the reading 1 µm off gives a
    finding of the kind ``hole``."""
    output = cases.fixture_build(gate=False)
    result = _read(output.files["slots.PcbDoc"])
    reading = _design(result)
    model = output.design
    assert _rta2(model, result, reading).summary["holds"] is True
    board = reading.board
    assert board is not None
    first, *rest = board.holes
    holes = (dataclasses.replace(first, position=Point(first.position.x + 1_000, first.position.y)), *rest)
    off = dataclasses.replace(reading, board=dataclasses.replace(board, holes=holes))
    stage = _rta2(model, result, off)
    assert stage.issues and {i.where.split("/")[1] for i in stage.issues} == {"hole"}

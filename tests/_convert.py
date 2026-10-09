# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Designs and sources of the conversion tests (change c0159)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

import fenolite.convert as convert_package
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.convert.sources import KICAD, SourceProject
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[1]
TWO_LAYER = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
BLINK_T9 = ROOT / "tests" / "data" / "acceptance" / "blink_2layer_t9"
BLINK_T10 = ROOT / "tests" / "data" / "acceptance" / "blink_2layer_t10"


def two_layer() -> Design:
    return KicadBackend().read(TWO_LAYER).design


def with_pads(design: Design, *changes: dict[str, object]) -> tuple[Design, list[str], str]:
    """``design`` with its first pads, footprint after footprint, changed by ``changes`` (one mapping of
    field values per pad), the ids of those pads, and the reference of the first one's footprint."""
    board = design.board
    assert board is not None
    left = list(changes)
    ids: list[str] = []
    footprints = []
    for footprint in board.footprints:
        pads = []
        for pad in footprint.pads:
            if left:
                pad = dataclasses.replace(pad, **left.pop(0))  # type: ignore[arg-type]
                ids.append(pad.id)
            pads.append(pad)
        footprints.append(dataclasses.replace(footprint, pads=tuple(pads)))
    board = dataclasses.replace(board, footprints=tuple(footprints))
    first = board.footprints[0].component_id
    ref = next(c.ref for c in design.circuit.components if c.id == first)
    return dataclasses.replace(design, board=board), ids, ref


def source_of(design: Design, path: Path = TWO_LAYER) -> SourceProject:
    """A KiCad source that holds ``design``, as if it had been read from ``path``."""
    return SourceProject(
        given=path, path=path, root=path.parent, backend=KICAD, kind="kicad_pcb", design=design, major=10
    )


def read_as(monkeypatch: pytest.MonkeyPatch, design: Design) -> None:
    """Make ``convert_project`` read ``design`` whatever path it is given."""
    monkeypatch.setattr(convert_package, "read_source", lambda path: source_of(design, Path(path)))

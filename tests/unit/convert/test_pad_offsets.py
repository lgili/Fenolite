# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored copper offsets survive conversion without changing source slots."""

from dataclasses import replace
from pathlib import Path

import pytest
from _convert import source_of, two_layer

from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.kicad import pcb, slots
from fenolite.convert import convert_project, pads
from fenolite.core.coords import Point
from fenolite.geometry.transform import rotate_point
from fenolite.model.base import Opaque
from fenolite.model.library import Library


@pytest.mark.parametrize("rotation", [0, 90_000_000, 180_000_000, 270_000_000])
@pytest.mark.parametrize("bottom", [False, True])
def test_offset_board_and_derived_library(tmp_path: Path, rotation: int, bottom: bool) -> None:
    design = two_layer()
    assert design.board is not None
    footprint = design.board.footprints[0]
    pad = footprint.pads[0]
    bag = slots.to_ext((*slots.from_ext(pad.ext["kicad"]), Opaque("(drill 0.6 (offset 0.12 -0.23))")))
    pad = replace(
        pad,
        kind="thru_hole",
        drill=600_000,
        rotation=rotation,
        layers=("F.Cu", "B.Cu", "F.Mask", "B.Mask"),
        ext={"kicad": bag},
    )
    footprint = replace(footprint, side="bottom" if bottom else "top", pads=(pad, *footprint.pads[1:]))
    design = replace(
        design,
        board=replace(
            design.board,
            footprints=(footprint, *design.board.footprints[1:]),
        ),
    )
    before = pcb.write_board(design).text
    projected = pads.project(design)
    assert projected.board is not None
    stack = projected.board.footprints[0].pads[0].padstack
    assert stack is not None
    expected = rotate_point(Point(120_000, -230_000), rotation)
    assert {layer.offset for layer in stack.layers} == {expected}
    conversion = convert_project(source_of(design), to="altium", allow_lossy=True)
    assert pcb.write_board(design).text == before
    assert design.board.footprints[0].pads[0].padstack is None
    for name, data in conversion.files.items():
        (tmp_path / name).write_bytes(data)
    backend = AltiumBackend()
    target = backend.read(tmp_path / conversion.read_back).design
    board = target.board
    assert board is not None
    ref = next(c.ref for c in design.circuit.components if c.id == footprint.component_id)
    component = next(c for c in target.circuit.components if c.ref == ref)
    target_footprint = next(fp for fp in board.footprints if fp.component_id == component.id)
    found = next(p for p in target_footprint.pads if p.number == pad.number)
    assert found.padstack is not None
    assert all(
        abs(layer.offset.x - expected.x) <= 2 and abs(layer.offset.y - expected.y) <= 2
        for layer in found.padstack.layers
    )
    library = backend.read(tmp_path / "two_layer.PcbLib").content
    assert isinstance(library, Library)
    pattern = target_footprint.lib_ref.rpartition(":")[2]
    library_footprint = next(fp for fp in library.footprints if fp.name == pattern)
    library_pad = next(p for p in library_footprint.pads if p.number == pad.number)
    assert library_pad.padstack is not None
    library_expected = Point(expected.x, -expected.y) if bottom else expected
    assert all(
        abs(layer.offset.x - library_expected.x) <= 2 and abs(layer.offset.y - library_expected.y) <= 2
        for layer in library_pad.padstack.layers
    ), (library_expected, library_pad.padstack.layers)

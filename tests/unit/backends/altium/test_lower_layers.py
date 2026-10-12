# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Mechanical layers of KiCad drawings and copper texts (change c0160, task 3.1)."""

from __future__ import annotations

import dataclasses

import pytest
from _convert import two_layer

from fenolite.backends.altium import lower, pcbdoc
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.core.coords import Point, Size
from fenolite.model.board import Graphic, Text


@pytest.mark.parametrize("layer,ident", tuple(lower.KICAD_MECHANICAL.items()))
def test_mapped_drawings_and_copper_texts(layer: str, ident: int) -> None:
    design = two_layer()
    assert design.board is not None
    graphic = Graphic(
        id="gra-map", kind="line", layer=layer, points=(Point(0, 0), Point(1000000, 0)), width=100000
    )
    texts = tuple(
        Text(
            id=f"txt-{n}",
            text="copper",
            position=Point(0, 0),
            layer=name,
            size=Size(1000000, 1000000),
            thickness=100000,
        )
        for n, name in enumerate(("F.Cu", "B.Cu"))
    )
    board = dataclasses.replace(design.board, graphics=(graphic,), texts=texts)
    inputs = lower.from_design(dataclasses.replace(design, board=board), issues=[])
    assert inputs.pcb is not None
    assert not {"graphic", "text"} & set(inputs.lost)
    document = read_pcbdoc(pcbdoc.write_pcbdoc(inputs.pcb))
    assert any(item.prefix.layer == ident for item in document.tracks)
    assert {item.prefix.layer for item in document.texts if item.text == "copper"} == {1, 32}
    assert dict(document.board.fields)[f"LAYER{ident}NAME"] == layer
    assert dict(document.board.fields)[f"LAYER{ident}MECHENABLED"] == "TRUE"


@pytest.mark.parametrize("layer", ("User.9", "Margin"))
def test_unmapped_layers_remain_reported(layer: str) -> None:
    design = two_layer()
    assert design.board is not None
    graphic = Graphic(
        id="gra-unknown", kind="line", layer=layer, points=(Point(0, 0), Point(1000000, 0)), width=100000
    )
    board = dataclasses.replace(design.board, graphics=(graphic,))
    inputs = lower.from_design(dataclasses.replace(design, board=board), issues=[])
    assert inputs.lost["graphic"] == {
        f"the layer {layer} has no layer in the document for a graphic": (graphic.id,)
    }

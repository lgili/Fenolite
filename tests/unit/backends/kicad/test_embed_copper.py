# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``place_footprint``'s ``copper`` keyword (capability kicad-file-backend, MODIFIED "Footprint embedding";
change c0011)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import parse
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.coords import Point
from fenolite.model.circuit import Circuit, Component
from fenolite.model.design import Design

LED = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "data"
    / "libs"
    / "Mini_v9.pretty"
    / "Mini_LED_THT_3mm.kicad_mod"
)
FOUR = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def four_layer(**kwargs: object) -> tuple[Design, object]:
    d1 = Component(id="cmp_00000000-0000-4000-8000-000000000001", ref="D1", value="LED")
    placed = place_footprint(
        read_footprint(LED, library="Mini"),
        component=d1,
        at=Point(10_000_000, 10_000_000),
        key="D1",
        **kwargs,
    )  # type: ignore[arg-type]
    base = Design.new("four", seed=0)
    assert base.board is not None
    board = dataclasses.replace(base.board, layers=created_layers(4), footprints=(placed,))
    return dataclasses.replace(base, circuit=Circuit(components=(d1,)), board=board), placed


def test_wildcard_pads_on_a_four_layer_board() -> None:
    design, placed = four_layer(copper=FOUR)
    pad = next(p for p in placed.pads if p.number == "1")  # type: ignore[attr-defined]
    assert pad.layers == (*FOUR, "F.Mask", "B.Mask")
    text = write_board(design, target=10).text
    back = next(p for p in read_board(text).board.footprints[0].pads if p.number == "1")  # type: ignore[union-attr]
    assert back.layers == (*FOUR, "F.Mask", "B.Mask")
    (fp,) = parse(text).nodes("footprint")
    first = next(p for p in fp.nodes("pad") if p.atoms()[0].value == "1")
    assert [a.value for a in first.find("layers").atoms()] == ["*.Cu", "*.Mask"]  # type: ignore[union-attr]


def test_default_copper_on_a_four_layer_board_is_refused() -> None:
    design, _ = four_layer()
    with pytest.raises(LossyWriteError) as caught:
        write_board(design, target=10)
    assert caught.value.droppable is False
    assert caught.value.issues and {i.code for i in caught.value.issues} == {
        "kicad.board.projection-read-only"
    }

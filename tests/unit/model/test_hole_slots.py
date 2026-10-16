# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Slotted board holes in the model (capability design-model, "Slotted board holes"; change c0168)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model import Board, canonical
from fenolite.model.board import Hole
from fenolite.model.design import Design

MM = 1_000_000


def _design(*holes: Hole) -> Design:
    board = Board(id=derived_id("brd", "test", "board"), holes=holes)
    return dataclasses.replace(Design.new("holes", seed=0), board=board)


def round_hole() -> Hole:
    return Hole(id=derived_id("hol", "test", "H1"), position=Point(52 * MM, 32 * MM), drill=3_200_000)


def slotted_hole() -> Hole:
    return Hole(
        id=derived_id("hol", "test", "H2"),
        position=Point(20 * MM, 30 * MM),
        drill=2 * MM,
        length=12 * MM,
        rotation=90_000_000,
    )


def test_a_slotted_hole_round_trips(tmp_path: Path) -> None:
    design = _design(round_hole(), slotted_hole())
    canonical.dump_dir(design, tmp_path)
    loaded = canonical.load_dir(tmp_path)
    assert loaded.board is not None
    assert sorted(loaded.board.holes, key=lambda h: h.id) == sorted(
        (round_hole(), slotted_hole()), key=lambda h: h.id
    )
    data = json.loads((tmp_path / "board.json").read_text(encoding="utf-8"))["holes"]
    (slot,) = [item for item in data if "length" in item]
    assert slot["length"] == 12 * MM and slot["rotation"] == 90_000_000


def test_a_round_hole_keeps_its_bytes() -> None:
    text = canonical.dumps(round_hole())
    assert '"length"' not in text and '"rotation"' not in text
    assert text == canonical.dumps(
        Hole(id=derived_id("hol", "test", "H1"), position=Point(52 * MM, 32 * MM), drill=3_200_000)
    )


@pytest.mark.parametrize("length", [2 * MM, 1 * MM])
def test_a_slot_not_longer_than_its_drill_is_refused(length: int) -> None:
    with pytest.raises(ValueError, match="longer than its drill"):
        Hole(id=derived_id("hol", "test", "H3"), position=Point(0, 0), drill=2 * MM, length=length)

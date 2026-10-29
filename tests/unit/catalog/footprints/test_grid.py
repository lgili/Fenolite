# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``grid`` family (change c0260, scenario "Depopulated centre")."""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction
from typing import Any

import pytest

from fenolite.catalog.footprints import generate
from fenolite.catalog.footprints.grid import row_name
from fenolite.catalog.footprints.lands import LandTable
from fenolite.catalog.footprints.record import Package

Record = Callable[..., Package]


def _ten(raw: dict[str, Any]) -> None:
    raw.update(name="BGA_Test", rows=10, columns=10, depopulated={"center": "4x4"})
    raw["body"] = {"length": "5.0mm..5.2mm", "width": "5.0mm..5.2mm", "height": "1mm max"}


def test_depopulated_centre(record: Record) -> None:
    fp = generate(record("bga12", _ten)).footprint
    assert fp is not None
    names = [p.number for p in fp.pads]
    assert len(names) == 84 and "E5" not in names
    rows = sorted({name.rstrip("0123456789") for name in names}, key=lambda r: (len(r), r))
    assert rows == list("ABCDEFGHJK")
    a1 = next(p for p in fp.pads if p.number == "A1")
    assert a1.position.x == min(p.position.x for p in fp.pads) and a1.position.y == min(
        p.position.y for p in fp.pads
    )
    assert all(p.shape == "circle" and p.size.w == 250_000 for p in fp.pads)


def test_row_letters() -> None:
    assert [row_name(i) for i in (0, 7, 8, 19, 20, 21)] == ["A", "H", "J", "Y", "AA", "AB"]
    assert not {row_name(i) for i in range(40)} & {"I", "O", "Q", "S", "X", "Z"}


@pytest.mark.parametrize(
    "depopulated",
    [["Z9"], {"center": "3x4"}],
)
def test_depopulation_outside_the_grid(record: Record, depopulated: object) -> None:
    def edit(raw: dict[str, Any]) -> None:
        _ten(raw)
        raw["depopulated"] = depopulated

    result = generate(record("bga12", edit))
    assert result.footprint is None and [i.code for i in result.issues] == ["package.dimensions-inconsistent"]


def test_named_depopulation(record: Record) -> None:
    fp = generate(record("bga12", lambda raw: raw.update(depopulated=["B2", "B3"]))).footprint
    assert fp is not None and len(fp.pads) == 10 and "B2" not in {p.number for p in fp.pads}


def test_ball_ratio(record: Record) -> None:
    def calculated(raw: dict[str, Any]) -> None:
        raw.pop("land")

    table = LandTable(version=1, ball_ratio={"nsmd": Fraction(4, 5)})
    result = generate(record("bga12", calculated), table=table)
    assert result.footprint is not None and result.land.pad_diameter == 240_000  # 0.30 mm × 4/5
    missing = generate(record("bga12", calculated))
    assert missing.footprint is None and [i.code for i in missing.issues] == ["package.no-goals"]

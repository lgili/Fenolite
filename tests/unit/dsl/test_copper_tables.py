# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper tables in the DSL (capability design-dsl, "Copper tables in the DSL" and "Copper table checks";
change c0275)."""

from __future__ import annotations

import pytest

from fenolite.core.coords import Point
from fenolite.dsl import Design, DslError, Net, copper, mm, protect
from fenolite.dsl.intents import ArcTableIntent, TrackTableIntent, ViaTableIntent


def _design() -> tuple[Design, Net]:
    d = Design("tables")
    d.board(mm(50), mm(30))
    return d, Net("GND")


def test_table_of_two_segments() -> None:
    d, gnd = _design()
    d.track_table(
        "GND/F.Cu/1",
        net=gnd,
        layer="F.Cu",
        width=mm("0.25"),
        rows_nm=((0, 0, 5_000_000, 0), (5_000_000, 0, 5_000_000, 5_000_000)),
    )
    (intent,) = copper(d)
    assert isinstance(intent, TrackTableIntent)
    assert intent.net == "GND" and intent.layer == "F.Cu" and intent.width == 250_000
    assert intent.rows == (
        (100_000_000, 100_000_000, 105_000_000, 100_000_000),
        (105_000_000, 100_000_000, 105_000_000, 105_000_000),
    )
    assert "GND" in d.nets


def test_arc_and_via_tables() -> None:
    d, gnd = _design()
    d.arc_table(
        "GND/F.Cu/2",
        net=gnd,
        layer="B.Cu",
        width=mm("0.2"),
        rows_nm=((0, 0, 1_000_000, 1_000_000, 2_000_000, 0),),
    )
    d.via_table(
        "GND/via/1",
        net=gnd,
        diameter=mm("0.6"),
        drill=mm("0.3"),
        rows_nm=((1_000_000, 2_000_000),),
        protection=protect(tenting=True),
        locked=True,
    )
    arc, via = copper(d)
    assert isinstance(arc, ArcTableIntent) and arc.rows[0][2:4] == (101_000_000, 101_000_000)
    assert isinstance(via, ViaTableIntent) and via.rows == ((101_000_000, 102_000_000),)
    assert via.locked and via.protection.tenting_front is True and via.layers is None


@pytest.mark.parametrize(
    ("rows", "words"),
    [
        (((0, 0, 0, 0),), ("T/1", "row 0", "zero length")),
        (((0, 0, 1.5, 0),), ("T/1", "row 0", "not an int")),
        (((0, 0, True, 0),), ("T/1", "row 0", "not an int")),
        (((0, 0, 1),), ("T/1", "row 0", "3 values")),
        ((), ("T/1", "rows_nm")),
    ],
)
def test_refused_rows(rows: object, words: tuple[str, ...]) -> None:
    d, gnd = _design()
    with pytest.raises(DslError) as raised:
        d.track_table("T/1", net=gnd, layer="F.Cu", width=mm("0.25"), rows_nm=rows)
    for word in words:
        assert word in str(raised.value)
    assert not d.copper_intents


def test_other_refusals() -> None:
    d, gnd = _design()
    with pytest.raises(DslError, match="row 0 does not make an arc"):
        d.arc_table("A/1", net=gnd, layer="F.Cu", width=mm("0.2"), rows_nm=((0, 0, 1, 1, 2, 2),))
    with pytest.raises(DslError, match="In1.Cu"):
        d.track_table("T/1", net=gnd, layer="In1.Cu", width=mm("0.2"), rows_nm=((0, 0, 1, 0),))
    with pytest.raises(DslError, match="width"):
        d.track_table("T/1", net=gnd, layer="F.Cu", width=0.2, rows_nm=((0, 0, 1, 0),))
    with pytest.raises(DslError, match="drill"):
        d.via_table("V/1", net=gnd, diameter=mm("0.3"), drill=mm("0.3"), rows_nm=((0, 0),))
    d.via("V/1", mm(1), mm(1), net=gnd, diameter=mm("0.6"), drill=mm("0.3"))
    with pytest.raises(DslError, match="already used"):
        d.via_table("V/1", net=gnd, diameter=mm("0.6"), drill=mm("0.3"), rows_nm=((0, 0),))
    with pytest.raises(DslError, match="net must be a Net"):
        d.track_table("T/2", net="GND", layer="F.Cu", width=mm("0.2"), rows_nm=((0, 0, 1, 0),))  # type: ignore[arg-type]


def test_board_frame_points() -> None:
    d, gnd = _design()
    d.via_table("V/1", net=gnd, diameter=mm("0.6"), drill=mm("0.3"), rows_nm=((-1_000_000, 0),))
    (via,) = copper(d)
    assert isinstance(via, ViaTableIntent)
    assert Point(*via.rows[0]) == Point(99_000_000, 100_000_000)

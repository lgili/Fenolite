# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The capacity fit and the capacity of tracks, arcs and vias (capability board-analyses; change c0047)."""

from __future__ import annotations

import dataclasses
import math
import random

import pytest
from _analysis import MM, at
from _coppercheck import Copper

from fenolite.analysis.current import (
    FIT_EXP_AREA,
    FIT_EXP_RISE,
    FIT_K_EXTERNAL,
    FIT_K_INTERNAL,
    MIL_NM,
    analyze_current,
    barrel_area_nm2,
    capacity_ma,
    in_range,
)
from fenolite.model.design import Design

THICK = {"*": 35_000}


def test_fit_one_millimetre_track() -> None:
    area = 1_000_000 * 35_000
    assert capacity_ma(area, 10_000, external=True) == 2391
    assert capacity_ma(area, 10_000, external=False) == 1195


def test_fit_independent_computation() -> None:
    """The same fit computed here with ``math``: every pair differs by at most 1 mA."""
    rng = random.Random(47)
    for _ in range(400):
        area = round(10 ** rng.uniform(9, 13))
        rise = rng.randint(1_000, 100_000)
        for external in (True, False):
            k = float(FIT_K_EXTERNAL if external else FIT_K_INTERNAL)
            mils2 = area / (MIL_NM * MIL_NM)
            amperes = (
                k
                * math.exp(float(FIT_EXP_RISE) * math.log(rise / 1000))
                * math.exp(float(FIT_EXP_AREA) * math.log(mils2))
            )
            assert abs(capacity_ma(area, rise, external=external) - amperes * 1000) <= 1, (area, rise)


@pytest.mark.parametrize(("area", "rise"), [(0, 10_000), (10**9, 0), (-1, 10_000), (10**9, -5)])
def test_fit_invalid_input(area: int, rise: int) -> None:
    with pytest.raises(ValueError, match="above 0"):
        capacity_ma(area, rise, external=True)


def test_fit_refuses_floats() -> None:
    with pytest.raises(ValueError, match="int"):
        capacity_ma(1e9, 10_000, external=True)  # type: ignore[arg-type]


def test_range() -> None:
    assert in_range(1_000_000, 10_000, 2391, external=True)
    assert not in_range(12_000_000, 10_000, 14_490, external=True)
    assert not in_range(1_000_000, 100_001, 2391, external=True)
    assert not in_range(1_000_000, 10_000, 17_501, external=False)
    assert in_range(None, 10_000, 1902, external=True)


def one_track(width: float = 0.25, layer: str = "F.Cu", layers: int = 2) -> Design:
    made = Copper(layers=4 if layers == 4 else 2)
    made.track("VBUS", at(0, 0), at(10, 0), width=round(width * MM), layer=layer, locator="/track")
    return made.build()


def test_track_quarter_millimetre() -> None:
    report = analyze_current(one_track(), temp_rise_mk=20_000, copper_thickness=THICK)
    (row,) = report.rows
    assert (row.kind, row.external, row.area_nm2, row.capacity_ma) == ("track", True, 8_750_000_000, 1187)
    assert (row.net, row.layer, row.where, row.at) == ("VBUS", "F.Cu", "/track", at(0, 0))
    assert report.summary["nets"] == {"VBUS": {"capacity_ma": 1187, "where": "/track"}}
    assert report.summary["fit"] == "S-0269" and report.issues == ()


def test_inner_layer_halves_the_constant() -> None:
    made = Copper(layers=4)
    made.track("N", at(0, 0), at(10, 0), width=MM, layer="F.Cu")
    made.track("N", at(0, 5), at(10, 5), width=MM, layer="In1.Cu")
    made.track("N", at(0, 9), at(10, 9), width=MM, layer="B.Cu")
    report = analyze_current(made.build(), temp_rise_mk=10_000, copper_thickness=THICK)
    found = {row.layer: (row.capacity_ma, row.external) for row in report.rows}
    assert found == {"F.Cu": (2391, True), "In1.Cu": (1195, False), "B.Cu": (2391, True)}


def test_thickness_per_layer_and_from_the_stackup() -> None:
    made = Copper(layers=4)
    made.track("N", at(0, 0), at(10, 0), width=MM, layer="F.Cu")
    made.track("N", at(0, 5), at(10, 5), width=MM, layer="In1.Cu")
    design = made.build()
    report = analyze_current(design, temp_rise_mk=10_000, copper_thickness={"*": 35_000, "In1.Cu": 17_500})
    assert {row.layer: row.thickness for row in report.rows} == {"F.Cu": 35_000, "In1.Cu": 17_500}
    only = analyze_current(design, temp_rise_mk=10_000, copper_thickness={"F.Cu": 35_000})
    assert [row.layer for row in only.rows] == ["F.Cu"] and only.summary["skipped"] == 1


def test_nothing_assumed() -> None:
    made = Copper()
    for y in range(3):
        made.track("N", at(0, y), at(10, y))
    report = analyze_current(made.build(), temp_rise_mk=10_000)
    assert report.rows == () and report.summary["skipped"] == 3
    (found,) = report.issues
    assert found.code == "analysis.input-missing" and found.severity == "warning"
    assert "copper thickness" in found.message and "3 item(s)" in found.message
    assert report.evidence.level.value == "UNVERIFIED"


def test_no_temperature_rise_is_not_assumed() -> None:
    report = analyze_current(one_track(), copper_thickness=THICK)
    (found,) = report.issues
    assert report.rows == () and "temperature rise" in found.message


def test_wide_track_flagged() -> None:
    report = analyze_current(one_track(12), temp_rise_mk=10_000, copper_thickness=THICK)
    (row,) = report.rows
    assert row.capacity_ma == 14_490 and row.in_range is False
    (found,) = report.issues
    assert found.code == "analysis.fit-out-of-range" and "1 item(s)" in found.message


def via_board(count: int = 1) -> Design:
    made = Copper()
    for index in range(count):
        via = made.via("N", at(5 * index, 0))
        made.vias[-1] = dataclasses.replace(via, drill=300_000)
    return made.build()


def test_via_barrel() -> None:
    assert barrel_area_nm2(300_000, 25_000) == 25_525_440_310
    report = analyze_current(via_board(), temp_rise_mk=10_000, via_plating=25_000)
    (row,) = report.rows
    assert (row.kind, row.area_nm2, row.capacity_ma) == ("via", 25_525_440_310, 1902)
    assert (row.layer, row.width, row.thickness, row.external) == ("F.Cu/B.Cu", None, 25_000, True)


def test_via_plating_not_given() -> None:
    report = analyze_current(via_board(2), temp_rise_mk=10_000)
    (found,) = report.issues
    assert report.rows == () and found.code == "analysis.input-missing"
    assert "via plating" in found.message and "2 item(s)" in found.message


def test_via_barrel_invalid() -> None:
    with pytest.raises(ValueError, match="above 0"):
        barrel_area_nm2(0, 25_000)


def test_arcs_are_rows_and_rows_are_sorted() -> None:
    made = Copper()
    made.track("B", at(0, 0), at(10, 0))
    made.arc("A", at(0, 5), at(5, 7), at(10, 5))
    report = analyze_current(made.build(), temp_rise_mk=10_000, copper_thickness=THICK)
    assert [(row.net, row.kind) for row in report.rows] == [("A", "arc"), ("B", "track")]

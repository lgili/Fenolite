# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Power paths: capacities, judging, resistance and drop (capability board-analyses, "Power path current"
and "Power path voltage drop"). Every current, rise, thickness and resistivity here is illustrative."""

from __future__ import annotations

import time
from fractions import Fraction
from math import ceil, floor

import pytest
from _analysis import box
from _power import (
    DUMBBELL,
    SPLIT4,
    SPLIT4_HOLE,
    branch,
    dumbbell,
    fdm_resistance,
    neck_board,
    strip,
    two_strips,
    via_array,
)

from fenolite.analysis import PowerReport, analyze_current, analyze_power, load_requirements, power
from fenolite.analysis.current import barrel_area_nm2
from fenolite.analysis.power import EVIDENCE, Interval, PathElement, region_bounds
from fenolite.analysis.requirements import SCHEMA
from fenolite.analysis.section import Port
from fenolite.core.evidence import Level
from fenolite.geometry import Thick

HEAD = f'schema = "{SCHEMA}"\n'
RHO = 20_000
"""An illustrative resistivity in picoohm-metres; Fenolite ships none."""


def path(milliamps: int, rise_mk: int, drop: int | None = None, to: str = "U1-1") -> str:
    text = f'[[path]]\nfrom = ["J1-1"]\nto = ["{to}"]\nmilliamps = {milliamps}\ntemp_rise_mk = {rise_mk}\n'
    return HEAD + text + (f"drop_mv = {drop}\n" if drop is not None else "")


def codes(report: PowerReport) -> list[str]:
    return [found.code for found in report.issues]


def only(report: PowerReport, kind: str) -> list[PathElement]:
    (row,) = report.rows
    return [element for element in row.elements if element.kind == kind]


def test_the_branch_is_not_judged() -> None:
    """Scenario "The branch is not judged"."""
    design, pads = branch()
    report = analyze_power(
        design, pads=pads, requirements=load_requirements(path(2000, 20_000)), copper_thickness={"*": 35_000}
    )
    (row,) = report.rows
    assert (row.net, row.start, row.end, row.milliamps, row.temp_rise_mk) == (
        "VBUS",
        ("J1-1",),
        ("U1-1",),
        2000,
        20_000,
    )
    assert [(e.where, e.capacity_ma, e.series, e.in_range) for e in row.elements] == [
        ("/main[0]", 3244, True, True),
        ("/main[1]", 3244, True, True),
    ]
    assert not report.issues and report.evidence.level is Level.INFERRED
    assert row.resistance_uohm is None and row.drop_mv is None
    current = HEAD + '[[current]]\nselect = { net = "VBUS" }\nmilliamps = 2000\ntemp_rise_mk = 20000\n'
    whole = analyze_current(design, copper_thickness={"*": 35_000}, requirements=load_requirements(current))
    (found,) = whole.issues
    assert found.code == "analysis.current-exceeded" and found.where == "/side" and "1187 mA" in found.message
    # a path through the branch judges the branch
    side = analyze_power(
        design,
        pads=pads,
        requirements=load_requirements(path(2000, 20_000, to="C1-1")),
        copper_thickness={"*": 35_000},
    )
    assert codes(side) == ["analysis.path-exceeded"] and side.issues[0].where == "/side"


def test_a_via_group_in_series() -> None:
    """Scenario "A via group in series"."""
    required = load_requirements(path(8000, 10_000))
    design, pads = via_array(4)
    report = analyze_power(
        design, pads=pads, requirements=required, via_plating=25_000, copper_thickness={"*": 35_000}
    )
    (group,) = only(report, "via-group")
    assert group.capacity_ma == 7608 and group.series and group.layer == "F.Cu/B.Cu"
    exceeded = [found for found in report.issues if found.code == "analysis.path-exceeded"]
    assert [found.where for found in exceeded] == [group.where]
    assert "7608 mA" in exceeded[0].message and "8000 mA" in exceeded[0].message
    design, pads = via_array(5)
    more = analyze_power(
        design, pads=pads, requirements=required, via_plating=25_000, copper_thickness={"*": 35_000}
    )
    assert only(more, "via-group")[0].capacity_ma == 9510
    assert "analysis.path-exceeded" not in codes(more)
    # without a plating the group has no capacity, and the reply says what is missing
    bare = analyze_power(design, pads=pads, requirements=required, copper_thickness={"*": 35_000})
    assert only(bare, "via-group")[0].capacity_ma is None
    missing = [found for found in bare.issues if found.code == "analysis.input-missing"]
    assert [found.where for found in missing] == ["via plating"] and bare.evidence.level is Level.UNVERIFIED


def test_a_neck_in_series() -> None:
    """Scenario "A neck in series" (``H-G-AN-NECKFIT``: the arithmetic only)."""
    design, pads = neck_board(DUMBBELL)
    report = analyze_power(
        design, pads=pads, requirements=load_requirements(path(5000, 10_000)), copper_thickness={"*": 35_000}
    )
    (fill,) = only(report, "fill")
    assert fill.section is not None and fill.section.low == 2_000_000 and fill.capacity_ma == 3953
    assert (
        fill.area_nm2 == 2_000_000 * 35_000
        and fill.ports == ("J1-1", "U1-1")
        and fill.series
        and fill.hull_free
    )
    (found,) = report.issues
    assert found.code == "analysis.path-exceeded" and found.where == "/pour#0"
    for part in ("/pour#0", "3953 mA", "5000 mA", "(10, 4) mm", "(10, 6) mm", "F.Cu"):
        assert part in found.message, (part, found.message)
    met = analyze_power(
        design, pads=pads, requirements=load_requirements(path(3953, 10_000)), copper_thickness={"*": 35_000}
    )
    assert not met.issues


def test_parallel_layers_are_undecided() -> None:
    """Scenario "Parallel layers are undecided"."""
    design, pads = two_strips()
    report = analyze_power(
        design,
        pads=pads,
        requirements=load_requirements(path(12_000, 10_000)),
        copper_thickness={"*": 50_000},
    )
    fills = only(report, "fill")
    assert [(e.section.low if e.section else None, e.capacity_ma, e.series) for e in fills] == [
        (5_000_000, 9948, False),
        (5_000_000, 9948, False),
    ]
    assert codes(report) == ["analysis.path-undecided"] * 2
    assert all("share of the current is not computed" in found.message for found in report.issues)


def test_a_path_that_is_only_measured_and_one_that_matches_no_pad() -> None:
    design, pads = branch()
    report = analyze_power(
        design,
        pads=pads,
        paths=((("J1-1",), ("U1-1",)), (("J1-1",), ("U9-1",))),
        copper_thickness={"*": 35_000},
        temp_rise_mk=20_000,
    )
    unknown, measured = report.rows
    assert unknown.net == "" and not unknown.elements
    assert measured.milliamps is None and [e.capacity_ma for e in measured.elements] == [3244, 3244]
    assert codes(report) == ["analysis.path-unmatched"] and report.evidence.level is Level.UNVERIFIED
    assert report.summary == {"paths": 2, "elements": 2, "missing": {}, "fit": "S-0269"}
    assert report.findings().issues == report.issues
    # without a rise no element has a capacity
    bare = analyze_power(design, pads=pads, paths=((("J1-1",), ("U1-1",)),), copper_thickness={"*": 35_000})
    assert [e.capacity_ma for e in bare.rows[0].elements] == [None, None]
    assert [(f.code, f.where) for f in bare.issues] == [("analysis.input-missing", "temperature rise")]
    assert "2 element(s)" in bare.issues[0].message


def test_power_evidence_and_determinism() -> None:
    assert EVIDENCE.level is Level.INFERRED
    assert EVIDENCE.hypotheses == ("H-G-AN-NECKFIT", "H-G-AN-NETWORK", "H-G-AN-POUR", "H-G-AN-SECTION")
    design, pads = via_array()
    required = load_requirements(path(8000, 10_000))
    thick = {"*": 35_000}
    first = analyze_power(
        design, pads=pads, copper_thickness=thick, requirements=required, via_plating=25_000
    )
    second = analyze_power(
        design, pads=pads, copper_thickness=thick, requirements=required, via_plating=25_000
    )
    assert first == second
    assert set(first.evidence.hypotheses) >= {"H-G-AN-FIT", "H-G-AN-SECTION"}
    assert Interval(1, None).high is None


# --- resistance and drop ----------------------------------------------------------------------------


def test_a_strip_between_two_plates() -> None:
    """Scenario "A strip between two plates": both bounds are ``R_s · 18 mm / 5 mm`` with ``R_s`` 400 µΩ."""
    design, pads = strip()
    report = analyze_power(
        design,
        pads=pads,
        requirements=load_requirements(path(10_000, 20_000)),
        copper_thickness={"*": 50_000},
        resistivity_pohm_m=RHO,
    )
    (row,) = report.rows
    assert row.resistance_uohm == Interval(1440, 1440) and row.drop_mv == Interval(14, 15)
    (fill,) = row.elements
    assert fill.resistance_uohm == Interval(1440, 1440) and not report.issues


def test_two_strips_in_parallel() -> None:
    """Scenario "Two strips in parallel"."""
    design, pads = two_strips()
    report = analyze_power(
        design,
        pads=pads,
        paths=((("J1-1",), ("U1-1",)),),
        copper_thickness={"*": 50_000},
        resistivity_pohm_m=RHO,
    )
    (row,) = report.rows
    assert row.resistance_uohm == Interval(720, 720) and row.drop_mv is None


def test_drop_judged() -> None:
    """Scenario "Drop judged"."""
    design, pads = strip()
    found: list[list[str]] = []
    for drop in (10, 14, 15):
        report = analyze_power(
            design,
            pads=pads,
            requirements=load_requirements(path(10_000, 20_000, drop)),
            copper_thickness={"*": 50_000},
            resistivity_pohm_m=RHO,
        )
        found.append(codes(report))
    assert found == [["analysis.drop-above"], ["analysis.drop-undecided"], []]


def test_resistivity_not_given() -> None:
    """Scenario "Resistivity not given"."""
    design, pads = strip()
    report = analyze_power(
        design,
        pads=pads,
        requirements=load_requirements(path(10_000, 20_000, 15)),
        copper_thickness={"*": 50_000},
    )
    (row,) = report.rows
    assert row.resistance_uohm is None and row.drop_mv is None
    assert [(f.code, f.where) for f in report.issues] == [("analysis.input-missing", "resistivity")]
    assert report.evidence.level is Level.UNVERIFIED


def test_track_resistance_and_a_strip_without_thickness() -> None:
    design, pads = branch()
    report = analyze_power(
        design,
        pads=pads,
        paths=((("J1-1",), ("U1-1",)),),
        copper_thickness={"*": 50_000},
        resistivity_pohm_m=RHO,
    )
    (row,) = report.rows
    # 1000 · ρ · L / (w · t) = 1000 · 20 000 · 10 mm / (1 mm · 50 µm) = 4000 µΩ per part
    assert [e.resistance_uohm for e in row.elements] == [Interval(4000, 4000), Interval(4000, 4000)]
    assert row.resistance_uohm == Interval(8000, 8000)
    bare = analyze_power(design, pads=pads, paths=((("J1-1",), ("U1-1",)),), resistivity_pohm_m=RHO)
    assert bare.rows[0].resistance_uohm == Interval(0, None)
    assert [f.where for f in bare.issues] == ["copper thickness"]


def test_barrel_resistance_from_the_depths(monkeypatch: pytest.MonkeyPatch) -> None:
    """The seam of change c0101: a via group is ``ρ·h/ΣA`` with ``h`` between the middles of its layers."""
    design, pads = via_array(4)
    kwargs = {"copper_thickness": {"*": 35_000}, "via_plating": 25_000, "resistivity_pohm_m": RHO}
    without = analyze_power(design, pads=pads, paths=((("J1-1",), ("U1-1",)),), **kwargs)  # type: ignore[arg-type]
    (group,) = only(without, "via-group")
    assert group.resistance_uohm is None and without.rows[0].resistance_uohm is not None
    assert without.rows[0].resistance_uohm.high is None
    assert "stack-up" in [f.where for f in without.issues]
    depths = {"F.Cu": (0, 35_000), "B.Cu": (1_565_000, 1_600_000)}
    monkeypatch.setattr(power, "layer_depths", lambda board: depths)
    report = analyze_power(design, pads=pads, paths=((("J1-1",), ("U1-1",)),), **kwargs)  # type: ignore[arg-type]
    (group,) = only(report, "via-group")
    area = 4 * barrel_area_nm2(300_000, 25_000)
    exact = Fraction(1000 * RHO * 1_565_000, area)
    assert group.resistance_uohm == Interval(floor(exact), ceil(exact)) and group.area_nm2 == area
    assert "stack-up" not in [f.where for f in report.issues]
    total = report.rows[0].resistance_uohm
    assert total is not None and total.high is not None and total.low >= floor(exact)


def test_region_bounds_of_a_neck() -> None:
    left = Port("A", (Thick(box(4, 4, 6, 6), 0, filled=True),))
    right = Port("B", (Thick(box(17, 4, 19, 6), 0, filled=True),))
    found = region_bounds(dumbbell(), left, right, sheet_uohm=400)
    # ℓ = 11 mm, A = 206 − 8 = 198 mm², w = 2 mm: 400 · 121 / 198 and 400 · 198 / 4
    assert found == Interval(244, 19_800)
    assert region_bounds(dumbbell(), left, left, sheet_uohm=400) == Interval(0, None)


def test_fdm_agreement_of_regions_and_of_a_path() -> None:
    """Scenario "Agreement with a finite-difference solution" (``H-G-AN-POUR``, ``H-G-AN-NETWORK``): each
    grid resistance lies inside the interval widened by 2 %. The widths are printed (``-rA``)."""
    sheet = 400  # µΩ per square: the illustrative resistivity over 50 µm of copper
    pads = ((4.0, 4.0, 6.0, 6.0), (17.0, 4.0, 19.0, 6.0))
    ends = ((0.0, 0.0, 1.0, 5.0), (19.0, 0.0, 20.0, 5.0))

    def neck(width: float) -> list[tuple[float, float, float, float]]:
        return [(0, 0, 10, 10), (10, 5 - width / 2, 13, 5 + width / 2), (13, 0, 23, 10)]

    strip_squares = fdm_resistance([(0, 0, 20, 5)], [], *ends)
    cases = [
        ("strip", strip(), sheet * strip_squares),
        ("dumbbell", neck_board(DUMBBELL), sheet * fdm_resistance(neck(2), [], *pads)),
        (
            "split4",
            neck_board(SPLIT4, (SPLIT4_HOLE,)),
            sheet * fdm_resistance(neck(4), [(10.7, 4.2, 12.3, 5.8)], *pads),
        ),
        ("two_strips", two_strips(), sheet * strip_squares / 2),
    ]
    for name, (design, board_pads), grid in cases:
        began = time.perf_counter()
        report = analyze_power(
            design,
            pads=board_pads,
            paths=((("J1-1",), ("U1-1",)),),
            copper_thickness={"*": 50_000},
            resistivity_pohm_m=RHO,
        )
        seconds = time.perf_counter() - began
        found = report.rows[0].resistance_uohm
        assert found is not None and found.high is not None, name
        assert found.low * 0.98 <= grid <= found.high * 1.02, (name, found, grid)
        print(f"{name}: interval {found.low}..{found.high} µΩ, grid {grid:.1f} µΩ, {seconds * 1000:.0f} ms")

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Findings against the user's requirements and the closed code table (capability board-analyses,
"Findings and issue codes"; change c0047)."""

from __future__ import annotations

import pytest
from _analysis import at, discs, edge_board, slot_board
from _coppercheck import Copper

from fenolite.analysis import analyze_current, analyze_distances, load_requirements
from fenolite.analysis.codes import ISSUE_CODES, issue
from fenolite.analysis.report import DistanceRow
from fenolite.analysis.requirements import SCHEMA
from fenolite.core.evidence import Level

HEAD = f'schema = "{SCHEMA}"\n'


def distance(**values: int) -> str:
    body = "".join(f"{key} = {value}\n" for key, value in values.items())
    return HEAD + '[[distance]]\na = { net = "A" }\nb = { net = "B" }\n' + body


def codes(report: object) -> list[str]:
    return [found.code for found in report.issues]  # type: ignore[attr-defined]


POWER_CODES = {
    "analysis.path-unmatched": "warning",
    "analysis.path-open": "warning",
    "analysis.path-exceeded": "error",
    "analysis.path-undecided": "warning",
    "analysis.drop-above": "error",
    "analysis.drop-undecided": "warning",
    "analysis.insulation-below": "error",
    "analysis.insulation-undecided": "warning",
    "analysis.creepage-over": "info",
}
"""The nine codes of change c0115 ("Power and insulation codes")."""


def test_table_of_ten_codes() -> None:
    """The ten codes of c0047; c0115 adds nine beside them."""
    first = [code for code in ISSUE_CODES if code not in POWER_CODES]
    assert len(first) == 10 and all(code.startswith("analysis.") for code in ISSUE_CODES)
    errors = sorted(code for code in first if ISSUE_CODES[code] == ("error",))
    assert errors == [
        "analysis.clearance-below",
        "analysis.creepage-below",
        "analysis.current-exceeded",
        "analysis.embedded-below",
    ]


def test_power_codes_in_the_table() -> None:
    """Scenario "Codes in the table"."""
    assert len(ISSUE_CODES) == 19
    for code, severity in POWER_CODES.items():
        assert ISSUE_CODES[code] == (severity,), code
    with pytest.raises(ValueError, match="no severity"):
        issue("analysis.creepage-over", "x", severity="warning")
    assert issue("analysis.creepage-over", "x").severity == "info"


def test_unknown_code_refused() -> None:
    with pytest.raises(ValueError, match="not an analysis issue code"):
        issue("analysis.unknown", "x")
    with pytest.raises(ValueError, match="no severity"):
        issue("analysis.input-missing", "x", severity="error")
    assert issue("analysis.input-missing", "x", where="w").severity == "warning"


def test_current_exceeded() -> None:
    made = Copper()
    made.track("VBUS", at(0, 0), at(10, 0), locator="/track")
    text = HEAD + '[[current]]\nselect = { net = "VBUS" }\nmilliamps = 2000\ntemp_rise_mk = 20000\n'
    report = analyze_current(
        made.build(), copper_thickness={"*": 35_000}, requirements=load_requirements(text)
    )
    (found,) = report.issues
    assert (found.code, found.severity, found.where) == ("analysis.current-exceeded", "error", "/track")
    for part in ("1187 mA", "2000 mA", "F.Cu"):
        assert part in found.message, part
    met = HEAD + '[[current]]\nselect = { net = "VBUS" }\nmilliamps = 1187\ntemp_rise_mk = 20000\n'
    assert (
        analyze_current(
            made.build(), copper_thickness={"*": 35_000}, requirements=load_requirements(met)
        ).issues
        == ()
    )


def test_current_row_gives_the_rise_and_unmatched_rows_warn() -> None:
    made = Copper()
    made.track("VBUS", at(0, 0), at(10, 0))
    text = HEAD + (
        '[[current]]\nselect = { net = "VBUS" }\nmilliamps = 100\ntemp_rise_mk = 20000\n'
        '[[current]]\nselect = { net = "NOPE" }\nmilliamps = 100\ntemp_rise_mk = 20000\n'
    )
    report = analyze_current(
        made.build(),
        temp_rise_mk=10_000,
        copper_thickness={"*": 35_000},
        requirements=load_requirements(text),
    )
    assert report.rows[0].temp_rise_mk == 20_000  # type: ignore[union-attr]
    (found,) = report.issues
    assert found.code == "analysis.requirement-unmatched" and found.where == "current[1]"


def test_creepage_below_clearance_met() -> None:
    design, boundary = slot_board()
    requirements = load_requirements(distance(clearance_nm=8_000_000, creepage_nm=12_000_000))
    report = analyze_distances(design, pads=None, boundary=boundary, requirements=requirements)
    # since c0115 a judged creepage that passes a groove without a groove width also warns
    found, missing = report.issues
    assert (found.code, found.severity) == ("analysis.creepage-below", "error")
    assert "11 mm" in found.message and "12 mm" in found.message and "F.Cu" in found.message
    assert (missing.code, missing.where) == ("analysis.input-missing", "groove width")
    # with a groove width that the slot is not below, the slot counts and nothing is missing
    given = analyze_distances(
        design, pads=None, boundary=boundary, requirements=requirements, groove=2_000_000
    )
    assert codes(given) == ["analysis.creepage-below"]


def test_clearance_below_and_undecided() -> None:
    design, boundary = slot_board()
    below = load_requirements(distance(clearance_nm=9_500_000))
    assert codes(analyze_distances(design, pads=None, boundary=boundary, requirements=below)) == [
        "analysis.clearance-below"
    ]
    undecided = load_requirements(distance(clearance_nm=9_000_001))
    report = analyze_distances(design, pads=None, boundary=boundary, requirements=undecided)
    (found,) = report.issues
    assert (found.code, found.severity) == ("analysis.clearance-undecided", "warning")
    assert "does not decide" in found.message


def test_limit_bounds_the_creepage_and_passes() -> None:
    design, boundary = slot_board()
    report = analyze_distances(
        design, pads=None, boundary=boundary, requirements=load_requirements(distance(creepage_nm=10_000_000))
    )
    (row,) = report.rows
    assert isinstance(row, DistanceRow) and row.creepage is not None
    assert (row.creepage.bounded, row.creepage.low, row.creepage.high) == (True, 10_000_000, None)
    assert report.issues == ()


def test_embedded_below() -> None:
    made = Copper(layers=4)
    made.track("A", at(0, 0), at(10, 0), layer="In1.Cu")
    made.track("B", at(0, 1), at(10, 1), layer="In1.Cu")
    report = analyze_distances(
        made.build(),
        pads=None,
        boundary=None,
        requirements=load_requirements(distance(embedded_nm=1_000_000)),
    )
    (found,) = report.issues
    assert (
        found.code == "analysis.embedded-below" and "In1.Cu" in found.message and "0.75 mm" in found.message
    )


def test_measured_only() -> None:
    design, boundary = slot_board()
    report = analyze_distances(design, pads=None, boundary=boundary, pairs=(("A", "B"),))
    (row,) = report.rows
    assert isinstance(row, DistanceRow) and row.clearance is not None and row.creepage is not None
    assert report.issues == () and report.evidence.level is Level.INFERRED
    assert report.summary["faces_alone"] == 1


def test_unmatched_distance_rows_and_steps() -> None:
    text = HEAD + (
        '[[distance]]\na = { net = "A" }\nb = { net = "NOPE" }\ncreepage_nm = 1\n'
        '[[distance]]\na = { net = "A" }\nb = { net = "B" }\nmillivolts = 400000\n'
        "[[step]]\nup_to_mv = 300000\ncreepage_nm = 3000000\n"
    )
    report = analyze_distances(
        discs().build(), pads=None, boundary=None, requirements=load_requirements(text)
    )
    assert [(found.code, found.where) for found in report.issues] == [
        ("analysis.requirement-unmatched", "distance[0]"),
        ("analysis.requirement-unmatched", "distance[1]"),
    ]
    assert len(report.rows) == 1


def test_creepage_across_the_edge_is_judged() -> None:
    design, boundary = edge_board()
    report = analyze_distances(
        design,
        pads=None,
        boundary=boundary,
        requirements=load_requirements(distance(clearance_nm=5_100_001, creepage_nm=6_000_000)),
    )
    assert codes(report) == ["analysis.clearance-undecided", "analysis.creepage-below"]

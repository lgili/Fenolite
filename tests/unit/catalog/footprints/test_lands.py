# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The worst-case land calculator and the constants (change c0260, requirements "Worst-case land calculation",
"Pad gap is kept", "Fenolite-authored land constants")."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import fields, replace
from fractions import Fraction
from pathlib import Path
from typing import Any

from fenolite.catalog.footprints import generate
from fenolite.catalog.footprints.lands import (
    LAND_CLASSES,
    LANDS,
    Goals,
    LandTable,
    RowLand,
    back_solve,
    ceil_to,
    corner_ratio,
    drill_for,
    facing_rows,
    floor_to,
    lead_diagonal,
)
from fenolite.catalog.footprints.record import Package
from fenolite.core.quantities import LengthRange, parse_length_range

Record = Callable[..., Package]
TEST_TABLE = LandTable(
    version=1,
    goals={
        "gullwing": Goals(300_000, 100_000, 50_000),
        "gullwing-fine": Goals(300_000, 100_000, 50_000),
        "chip": Goals(300_000, 0, 50_000),
        "nolead": Goals(300_000, 0, 50_000),
    },
)
LANDS_PAGE = Path(__file__).resolve().parents[4] / "docs" / "formats" / "library" / "lands.md"


def _calculated(raw: dict[str, Any]) -> None:
    raw.pop("land")


def test_calculated_soic_land(record: Record) -> None:
    result = generate(record("soic8", _calculated), table=TEST_TABLE)
    land = result.land
    assert (land.z, land.g, land.x) == (6_800_000, 3_060_000, 610_000)
    assert land.source == "calculated" and land.evidence == "INFERRED" and land.table == 1
    fp = result.footprint
    assert fp is not None
    xs = sorted({abs(pad.position.x) for pad in fp.pads})
    assert xs == [4_930_000 // 2]
    assert {(pad.size.w, pad.size.h) for pad in fp.pads} == {(1_870_000, 610_000)}
    assert fp.description.endswith("land: calculated lands/1 nominal (INFERRED)")


def test_arithmetic_is_exact_and_on_the_grid() -> None:
    goals = Goals(300_000, 100_000, 50_000)
    land = facing_rows(
        ("span", parse_length_range("5.80mm..6.19mm")),
        ("lead.length", parse_length_range("0.41mm..1.27mm")),
        ("lead.width", parse_length_range("0.31mm..0.51mm")),
        goals,
        10_000,
    )
    assert land == RowLand(6_790_000, 3_060_000, 610_000)  # Z 6.79 is already on the grid
    assert (land.length, land.spacing) == (1_865_000, 4_925_000)
    odd = facing_rows(
        ("span", LengthRange(5_800_001, None, 6_190_001)),
        ("lead.length", LengthRange.exact(1_270_000)),
        ("lead.width", LengthRange.exact(510_001)),
        goals,
        10_000,
    )
    assert odd == RowLand(6_800_000, 3_060_000, 620_000)  # Z and X up, G down
    assert (ceil_to(1, 10), floor_to(-1, 10), ceil_to(-11, 10)) == (10, -10, -10)


def test_missing_bound(record: Record) -> None:
    def no_min(raw: dict[str, Any]) -> None:
        raw.pop("land")
        raw["span"] = "6.20mm max"

    result = generate(record("soic8", no_min), table=TEST_TABLE)
    assert result.footprint is None
    assert [i.code for i in result.issues] == ["package.missing-bound"]
    assert "min of span" in result.issues[0].message and result.issues[0].where.endswith(":span")


def test_fine_pitch_is_clipped(record: Record) -> None:
    def fine(raw: dict[str, Any]) -> None:
        raw.pop("land")
        raw.update(name="SSOP8", pitch="0.5mm", lead={"length": "0.40mm..1.27mm", "width": "0.20mm..0.30mm"})

    table = replace(TEST_TABLE, goals={"gullwing-fine": Goals(300_000, 100_000, 50_000)})
    result = generate(record("soic8", fine), table=table)
    fp = result.footprint
    assert fp is not None
    assert {pad.size.h for pad in fp.pads} == {500_000 - table.pad_gap}
    clipped = [i for i in result.issues if i.code == "package.pads-clipped"]
    assert len(clipped) == 1 and "side goal" in clipped[0].message and clipped[0].severity == "warning"


def test_land_impossible(record: Record) -> None:
    def tight(raw: dict[str, Any]) -> None:
        raw.pop("land")
        raw.update(span="4.10mm..4.20mm", lead={"length": "0.40mm..2.10mm", "width": "0.33mm..0.51mm"})

    result = generate(record("soic8", tight), table=TEST_TABLE)
    assert result.footprint is None and [i.code for i in result.issues] == ["package.land-impossible"]


def test_uncalibrated_class(record: Record) -> None:
    result = generate(record("soic8", _calculated), table=LandTable(version=1))
    assert result.footprint is None and [i.code for i in result.issues] == ["package.no-goals"]


def test_back_solve_inverts_the_calculator() -> None:
    span, lead, width = (
        LengthRange(5_800_000, None, 6_200_000),
        LengthRange(400_000, None, 1_270_000),
        LengthRange(330_000, None, 510_000),
    )
    goals = Goals(300_000, 100_000, 50_000)
    land = facing_rows(("s", span), ("l", lead), ("w", width), goals, 10_000)
    assert back_solve(span, lead, width, land) == goals


def test_through_hole_helpers() -> None:
    assert lead_diagonal(560_000, 380_000) == 676_757
    assert lead_diagonal(600_000, None) == 600_000
    assert lead_diagonal(300_000, 400_000) == 500_000  # an exact root is not raised
    table = LandTable(version=1, hole_clearance=230_000, annular_ring=350_000)
    assert drill_for(560_000, 380_000, table) == 910_000
    assert drill_for(560_000, 380_000, LandTable(version=1)) is None
    assert (
        corner_ratio(300_000) == 200_000 and corner_ratio(1_000_000) == 100_000 and corner_ratio(0) == 200_000
    )


def test_released_table_shape() -> None:
    table = LANDS[1]
    assert table.version == 1 and set(table.goals) <= set(LAND_CLASSES)
    assert (table.pad_gap, table.grid, table.courtyard) == (200_000, 10_000, 500_000)
    assert table.paste_window == Fraction(4, 5)
    for cls, goals in table.goals.items():
        assert len(table.calibration[cls]) >= 3, cls
        assert all(value % table.grid == 0 for value in (goals.toe, goals.heel, goals.side)), cls


def _published_rows() -> dict[str, str]:
    """``constant`` → its row of the published table in ``lands.md``."""
    rows: dict[str, str] = {}
    for line in LANDS_PAGE.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\| `([a-z_.-]+)` \|", line)
        if match:
            rows[match.group(1)] = line
    return rows


def _mm(nm: int) -> str:
    sign = "-" if nm < 0 else ""
    whole, frac = divmod(abs(nm), 1_000_000)
    text = f"{whole}.{frac:06d}".rstrip("0").rstrip(".")
    return f"{sign}{text} mm"


def test_published_table_equals_the_code() -> None:
    rows = _published_rows()
    table = LANDS[1]
    expected: dict[str, str] = {}
    for cls, goals in table.goals.items():
        expected[f"{cls}.toe"] = _mm(goals.toe)
        expected[f"{cls}.heel"] = _mm(goals.heel)
        expected[f"{cls}.side"] = _mm(goals.side)
    for name in ("pad_gap", "grid", "courtyard", "hole_clearance", "annular_ring", "paste_cell"):
        value = getattr(table, name)
        assert isinstance(value, int)
        expected[name] = _mm(value)
    expected["paste_window"] = "4/5"
    for kind, ratio in table.ball_ratio.items():
        expected[f"ball_ratio.{kind}"] = f"{ratio.numerator}/{ratio.denominator}"
    for name, value in expected.items():
        row = rows.get(name)
        assert row is not None, f"lands.md has no row for {name}"
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert cells[1] == value, (name, cells[1], value)
        assert cells[2] == "`INFERRED`" and cells[3], name
    published_classes = {name.split(".")[0] for name in rows if name.endswith(".toe")}
    assert published_classes == set(table.goals)
    page = LANDS_PAGE.read_text(encoding="utf-8")
    assert "IPC-7351" in page and "no IPC" in page.replace("No IPC", "no IPC")
    assert {f.name for f in fields(LandTable)} >= {"pad_gap", "hole_clearance", "ball_ratio"}


CALIBRATION = Path(__file__).resolve().parents[3] / "data" / "packages" / "calibration"


def test_calibration_set_within_tolerance() -> None:
    """``H-G-LAND-CALC``: the calculator with ``lands/1`` against the 27 cited manufacturer lands."""
    from fenolite.catalog.footprints import read_package

    worst = 0
    for path in sorted(CALIBRATION.glob("*.toml")):
        result = generate(read_package(path.read_text(encoding="utf-8"), file=path.name))
        assert result.footprint is not None, path.name
        assert result.land.deltas, path.name
        worst = max(worst, *(abs(value) for value in result.land.deltas.values()))
    assert worst <= 450_000

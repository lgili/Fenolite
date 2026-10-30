# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A ``connector`` series expanded per position count (change c0260, scenario "Result of a connector series"
at the API level)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fenolite.catalog.footprints import generate, positions_of, series_name
from fenolite.catalog.footprints.record import Package

Record = Callable[..., Package]


def test_result_of_a_connector_series(record: Record) -> None:
    series = record("connector_xh", lambda raw: raw.update(positions="2..4"))
    counts = positions_of(series)
    assert counts == (2, 3, 4)
    results = [generate(series, positions=n) for n in counts]
    assert [r.name for r in results] == ["CONN2_XH_P2.5", "CONN3_XH_P2.5", "CONN4_XH_P2.5"]
    ids = [r.footprint.id for r in results if r.footprint is not None]
    assert len(set(ids)) == 3
    for n, result in zip(counts, results, strict=True):
        fp = result.footprint
        assert fp is not None and len(fp.pads) == n
        fab = [g for g in fp.graphics if g.layer == "F.Fab"]
        xs = [p.x for g in fab for p in g.points]
        assert max(xs) - min(xs) == 2_500_000 * n + 2_400_000  # body = per position + extra


def test_series_land_and_offset(record: Record) -> None:
    result = generate(record("connector_xh"), positions=3)
    fp = result.footprint
    assert fp is not None
    assert {p.drill for p in fp.pads} == {900_000} and {p.size.h for p in fp.pads} == {900_000 + 700_000}
    assert result.land.source == "manufacturer" and "drill" in result.land.deltas
    fab_ys = [p.y for g in fp.graphics if g.layer == "F.Fab" for p in g.points]
    assert (max(fab_ys) + min(fab_ys)) // 2 == 525_000


def test_mechanical_holes(record: Record) -> None:
    def pegs(raw: dict[str, Any]) -> None:
        raw["mechanical"] = [{"kind": "hole", "drill": "1.1mm", "beyond": "1.5mm", "y": "1.0mm"}]

    fp = generate(record("connector_xh", pegs), positions=3).footprint
    assert fp is not None
    holes = [p for p in fp.pads if p.kind == "np_thru_hole"]
    assert [(h.position.x, h.position.y, h.number) for h in holes] == [
        (-4_000_000, 1_000_000, ""),
        (4_000_000, 1_000_000, ""),
    ]


def test_series_name_pattern(record: Record) -> None:
    series = record("connector_xh")
    assert series_name(series, 12) == "CONN12_XH_P2.5"

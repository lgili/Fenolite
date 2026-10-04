# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The parity benches without ``kicad-cli`` (capability kicad-oracle, "Copper verdict parity canaries",
scenario "Missing canary fails"; change c0029). Hermetic: the Fenolite half of every row, and the verdict
helper on authored reports."""

from __future__ import annotations

import _copperparity as cp
import pytest

from fenolite.backends.base import DrcItem, DrcReport, DrcViolation
from fenolite.backends.kicad import lowering
from fenolite.core.coords import Point


def report(*violations: DrcViolation) -> DrcReport:
    return DrcReport("bench.kicad_pcb", "", "10.0.6", "mm", violations=violations)


def violation(kind: str, *uuids: str) -> DrcViolation:
    return DrcViolation(kind, "", "error", tuple(DrcItem(u, "", Point(0, 0)) for u in uuids))


def canary(bench: cp.ParityBench) -> DrcViolation:
    return violation("clearance", *bench.bench.uuids("canary_a"), *bench.bench.uuids("canary_b"))


@pytest.mark.parametrize("source", cp.SOURCES)
def test_missing_canary_fails(source: str) -> None:
    bench = cp.parity_bench(source, 10)
    row = bench.rows[0]
    (a, *_), (b, *_) = bench.uuids(row)
    for found in (None, report(), report(violation("clearance", a, b))):
        with pytest.raises(pytest.fail.Exception, match="rules file not loaded"):
            cp.kicad_verdict(found, bench, row)


def test_verdict_helper() -> None:
    bench = cp.parity_bench("rule", 10)
    row = bench.rows[0]
    (a, *_), (b, *_) = bench.uuids(row)
    fired = canary(bench)
    assert cp.kicad_verdict(report(fired), bench, row) == "clean"
    assert cp.kicad_verdict(report(fired, violation("clearance", b, a)), bench, row) == "clearance"
    both = report(fired, violation("clearance", a, b), violation("shorting_items", a, b))
    assert cp.kicad_verdict(both, bench, row) == "short"
    assert cp.kicad_verdict(report(fired, violation("clearance", a, "other")), bench, row) == "clean"
    assert cp.kicad_verdict(report(fired, violation("track_dangling", a, b)), bench, row) == "clean"


@pytest.mark.parametrize("target", [9, 10])
@pytest.mark.parametrize("source", cp.SOURCES)
def test_fenolite_half_of_the_parity_rows(source: str, target: int) -> None:
    """A gap below ``c`` is a clearance finding, a gap of ``c`` or more is clean: for every pair kind,
    under each clearance source, on both targets."""
    bench = cp.parity_bench(source, target)
    c = cp.CLEARANCE[source]
    kinds = (*cp.KINDS, cp.FILL, "boundary-1um", "boundary-1nm")
    rows = [row for row in bench.rows if row.group in kinds]
    assert len(rows) >= 20
    for row in rows:
        expected = "clearance" if row.gap < c else "clean"
        assert cp.fenolite_verdict(source, target, row) == expected, row
    report, _ = cp.fenolite_report(source, target)
    sources = {
        finding.source.split(":")[0] for finding in report.findings if finding.code == "copper.clearance"
    }
    assert {"rule": "rule", "class": "class", "floor": "floor"}[source] in sources


def test_rule_bench_holds_the_zone_rows_for_target_10_only() -> None:
    groups10 = {row.group for row in cp.parity_bench("rule", 10).rows}
    groups9 = {row.group for row in cp.parity_bench("rule", 9).rows}
    assert {cp.FILL, "zone-overlap"} <= groups10 and not {cp.FILL, "zone-overlap"} & groups9
    assert "(clearance 0)" in cp.parity_bench("rule", 10).files[cp.BOARD]
    (row,) = [row for row in cp.parity_bench("rule", 10).rows if row.group == "zone-overlap"]
    assert cp.fenolite_verdict("rule", 10, row) in ("short", "overlap")


def test_fenolite_half_of_the_resolution_rows() -> None:
    """With the switches that c0026's tables ship with: a rule governs below the classes and below the
    board minimum, the larger class governs without a rule, an ``ignore`` rule silences its pair, and a
    rule on item kind ``track`` governs an arc."""
    expected = {
        "rule-below-class": ["clean", "clearance"],
        "rule-above-class": ["clearance", "clean"],
        "two-classes": ["clearance", "clean", "clean"],
        "ignore": ["clean", "clearance"],
        "arc-kind": ["clearance", "clean"],
        "floor-above-rule": ["clean", "clearance"],
    }
    assert set(expected) == set(cp.RESOLVE)
    for case, verdicts in expected.items():
        source = "floor" if case == "floor-above-rule" else "class"
        rows = [row for row in cp.parity_bench(source, 10).rows if row.group == case]
        assert [cp.fenolite_verdict(source, 10, row) for row in rows] == verdicts, case


def test_resolution_rows_follow_the_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Were KiCad to keep the classes above a rule, or the minimum above a rule, the verdicts of the rows
    that tell the two readings apart would change with the tables."""
    monkeypatch.setattr(lowering, "RULES_OVER_CLASSES", frozenset[int]())
    monkeypatch.setattr(lowering, "FLOOR_OVER_RULES", {"min_clearance": frozenset({10})})
    cp.fenolite_report.cache_clear()
    try:
        below = [row for row in cp.parity_bench("class", 10).rows if row.group == "rule-below-class"]
        assert [cp.fenolite_verdict("class", 10, row) for row in below] == ["clearance", "clearance"]
        floor = [row for row in cp.parity_bench("floor", 10).rows if row.group == "floor-above-rule"]
        assert [cp.fenolite_verdict("floor", 10, row) for row in floor] == ["clearance", "clearance"]
    finally:
        cp.fenolite_report.cache_clear()

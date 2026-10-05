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


# --- the zone's own clearance (change c0068, "Zone clearance parity canaries") ---------------------


@pytest.mark.parametrize("target", [9, 10])
@pytest.mark.parametrize("case", cp.ZONE_CASES)
def test_zone_clearance_fenolite_half(case: str, target: int) -> None:
    """Scenario "Hermetic rows": a clearance finding on every row below ``c``, with the source its case
    names, and none on the others."""
    spec = cp.ZONE_CASES[case]
    bench = cp.parity_bench(spec.bench, target)
    rows = [row for row in bench.rows if row.group == cp.zone_group(case)]
    assert len(rows) == 3 * len(spec.kinds)
    report, uuid_of = cp.fenolite_report(spec.bench, target)
    for row in rows:
        expected = "clearance" if row.gap < spec.c else "clean"
        assert cp.fenolite_verdict(spec.bench, target, row) == expected, row
    wanted = {uuid for row in rows for side in bench.uuids(row) for uuid in side}
    found = [
        finding
        for finding in report.findings
        if finding.code == "copper.clearance" and {uuid_of.get(i.entity_id) for i in finding.items} <= wanted
    ]
    # one zone per row below ``c``; the two pads of the fill–pad row give a finding each
    zones = {uuid for row in rows for uuid in bench.uuids(row)[0]}
    named = {uuid_of.get(i.entity_id) for finding in found for i in finding.items} & zones
    assert len(named) == len(spec.kinds) and len(found) >= len(named)
    assert {finding.source.split(":")[0] for finding in found} == {spec.source}
    assert {finding.clearance for finding in found} == {spec.c}


def test_zone_clearance_benches_take_the_value_from_the_model() -> None:
    """Each zone takes its clearance from ``ZoneSettings.clearance``: no token edit sets it."""
    for source in cp.ZONE_SOURCES:
        bench = cp.parity_bench(source, 10)
        board = bench.bench.design.board
        assert board is not None
        written = {zone.settings.clearance for zone in board.zones}
        expected = {case.zone for case in cp.ZONE_CASES.values() if case.bench == source}
        assert written - {500_000} <= expected <= written | {500_000}
        for value in expected:
            assert f"(clearance {value / 1e6:g})" in bench.files[cp.BOARD]
    assert '"min_clearance": 0.4' in cp.parity_bench("zone-floor", 10).files[cp.PROJECT]


@pytest.mark.parametrize("target", [9, 10])
def test_zone_clearance_two_fills_are_reported_with_the_class_value(target: int) -> None:
    """The documented difference: KiCad's DRC judges no pair of fills; ``check_copper`` reports this pair,
    0.1 mm apart, with the class value of 0.3 mm and not with a zone's 0.5 mm."""
    bench = cp.parity_bench("zone", target)
    (row,) = [row for row in bench.rows if row.group == cp.FILL_FILL]
    assert cp.fenolite_verdict("zone", target, row) == "clearance"
    report, uuid_of = cp.fenolite_report("zone", target)
    pair = {uuid for side in bench.uuids(row) for uuid in side}
    (found,) = [f for f in report.findings if {uuid_of.get(i.entity_id) for i in f.items} == pair]
    assert (found.clearance, found.source, found.gap) == (300_000, "class:FF", cp.FILL_FILL_GAP)


@pytest.mark.parametrize("source", cp.ZONE_SOURCES)
def test_zone_clearance_missing_canary_fails(source: str) -> None:
    bench = cp.parity_bench(source, 10)
    with pytest.raises(pytest.fail.Exception, match="rules file not loaded"):
        cp.kicad_verdict(report(), bench, bench.rows[0])

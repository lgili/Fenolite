# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Zone-fill comparison and unsupported-oracle behaviour with no external tool."""

from __future__ import annotations

import dataclasses

from fakes import FakeFillOracle, FakeValidator, project, validation

from fenolite.backends.base import FillOutcome, ZoneFills
from fenolite.checks.fill import fill_stage
from fenolite.checks.stages import run_checks
from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.model.board import Zone, ZoneFill
from fenolite.model.design import Design

VERIFIED = Evidence(Level.KICAD_VERIFIED, oracle="fake 10.0")
RING = (Point(0, 0), Point(1_000_000, 0), Point(1_000_000, 1_000_000))
GOOD = ZoneFill("B.Cu", RING)
OTHER = ZoneFill("B.Cu", (Point(0, 0), Point(2_000_000, 0), Point(2_000_000, 1_000_000)))


def design(*zones: Zone) -> Design:
    made = Design.new("fill", seed=0)
    assert made.board is not None
    return dataclasses.replace(made, board=dataclasses.replace(made.board, zones=zones))


def zone(name: str, *fills: ZoneFill) -> Zone:
    return Zone(id=f"zon_{name}", outline=RING, name=name, layers=("B.Cu",), net_id="GND", fills=fills)


def test_current_fill_counts_one_zone() -> None:
    original = design(zone("ground", GOOD))
    oracle = FakeFillOracle(FillOutcome((ZoneFills("zon_ground", (GOOD,), True),), "10.0", evidence=VERIFIED))
    stage = fill_stage(oracle, project(), original)
    assert stage.status == "ok" and stage.issues == ()
    assert stage.summary == {"tool_version": "10.0", "zones": 1, "current": 1, "unfilled": 0, "stale": 0}
    assert oracle.calls == [project()]


def test_unfilled_and_stale_are_warnings() -> None:
    original = design(zone("empty"), zone("old", OTHER))
    oracle = FakeFillOracle(
        FillOutcome(
            (ZoneFills("zon_empty", (GOOD,), True), ZoneFills("zon_old", (GOOD,), True)),
            "10.0",
            evidence=VERIFIED,
        )
    )
    stage = fill_stage(oracle, project(), original)
    assert [(i.code, i.severity) for i in stage.issues] == [
        ("zone.fill-stale", "warning"),
        ("zone.unfilled", "warning"),
    ]
    assert stage.status == "ok" and stage.evidence.level is Level.UNVERIFIED
    assert (stage.summary["unfilled"], stage.summary["stale"]) == (1, 1)


def test_unsupported_oracle_skips_without_lowering_envelope() -> None:
    original = design(zone("ground"))
    oracle = FakeFillOracle(FillOutcome(None, "9.0.9", supported=False))
    report = run_checks(
        project=project(),
        stages=("zone.fill", "roundtrip"),
        model=None,
        built=False,
        validator=FakeValidator(validation(original)),
        oracle=None,
        fill_oracle=oracle,
    )
    fill, roundtrip = report.stages
    assert (fill.status, fill.reason) == ("skipped", "oracle-unsupported")
    assert [i.code for i in report.issues] == ["zone.fill-unchecked"]
    assert report.evidence == roundtrip.evidence and len(oracle.calls) == 1


def test_failed_refill_is_retryable_on_timeout() -> None:
    original = design(zone("ground"))
    oracle = FakeFillOracle(FillOutcome(None, "10.0", outcome="timeout", returncode=None))
    stage = fill_stage(oracle, project(), original)
    assert stage.status == "errors" and stage.issues[0].code == "check.oracle-failed"
    assert stage.issues[0].retryable


def test_unstable_refill_is_unchecked() -> None:
    original = design(zone("ground", GOOD))
    oracle = FakeFillOracle(
        FillOutcome((ZoneFills("zon_ground", (OTHER,), True),), "10.0", evidence=VERIFIED, stable=False)
    )
    stage = fill_stage(oracle, project(), original)
    assert (stage.status, stage.reason) == ("skipped", "oracle-unstable")
    assert [issue.code for issue in stage.issues] == ["zone.fill-unchecked"]

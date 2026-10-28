# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Steps K6.2 to K6.11 of the kit on simulated runs (change c0215; capability altium-verification, "Kit
group K6 for computed pours"). Fenolite's own pour stands in for Altium's repour (``_simulate``), so every
verdict here is synthetic and settles nothing."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _simulate import simulate, simulated_judge

from fenolite.backends.altium import pour as engine
from fenolite.backends.altium.pour import PourReading, PourResult, polygons_of
from fenolite.cli._kit import SAMPLES_DIR, build_sample
from fenolite.core.coords import Point
from fenolite.geometry import Polygon
from fenolite.geometry.boolean.clipper import ClipperBackend
from fenolite.verify.kit.results import KitVerdict, verify_results
from fenolite.verify.kit.steps import PROBE_ROWS

POUR_ROWS = (
    *PROBE_ROWS,
    "H-A-POUR-KIT",
    "H-A-POUR-OPEN",
    "H-A-POUR-REGION",
    "H-A-POUR-SCRIPT",
    "H-A-POUR-ENGINE",
)
MM = 1_000_000


def _verdict(kit: Path) -> KitVerdict:
    return verify_results(kit, judge=simulated_judge)


def _step(verdict: KitVerdict, ident: str):  # noqa: ANN202
    return next(step for step in verdict.steps if step.id == ident)


def _rows(verdict: KitVerdict) -> dict[str, str]:
    return {row.id: row.outcome for row in verdict.hypotheses}


def test_a_simulated_run_of_the_pour_steps_passes(kit: Path) -> None:
    """Scenario "A simulated run of the pour steps passes"."""
    simulate(kit)
    verdict = _verdict(kit)
    assert verdict.synthetic
    group = [step for step in verdict.steps if step.id.startswith("K6.") and step.id != "K6.1"]
    assert [step.id for step in group] == [f"K6.{n}" for n in range(2, 12)]
    assert all(step.outcome == "pass" for step in group), [(s.id, s.reasons) for s in group if s.reasons]
    rows = _rows(verdict)
    assert all(rows[ident] == "pass" for ident in POUR_ROWS), {i: rows[i] for i in POUR_ROWS}


def test_a_repour_that_did_not_run(kit: Path) -> None:
    """Scenario "A repour that did not run": the reference input saved again without regions."""
    simulate(kit, replace={"pour/rebuilt.PcbDoc": (kit / "pour" / "reference" / "pour.PcbDoc").read_bytes()})
    verdict = _verdict(kit)
    step = _step(verdict, "K6.2")
    assert step.outcome == "fail"
    assert any(
        reason.startswith("repoured: the repour did not run") and "P0" in reason for reason in step.reasons
    )
    assert _rows(verdict)["H-A-POUR-KIT"] == "fail"


def _neck_kept(monkeypatch: pytest.MonkeyPatch) -> bytes:
    """``computed/pour.PcbDoc`` with the 4.5 mil neck of probe P3 kept: a bar across the gap between the
    ends of the tracks ``p3a`` and ``p3b``, joined to the pour."""
    real = engine.pour_reading

    def keeping(reading: PourReading, **options: object) -> PourResult:
        found = real(reading, **options)  # type: ignore[arg-type]
        names = {p.index: p.name for p in polygons_of(reading)}
        rings = reading.edges or ()
        x0 = min(p.x for ring in rings for p in ring.points)
        y0 = min(p.y for ring in rings for p in ring.points)

        def at(x: float, y: float) -> Point:
            return Point(x0 + round(x * MM), y0 + round(y * MM))

        bar = Polygon((at(15.94, 28.9), at(16.06, 28.9), at(16.06, 29.9), at(15.94, 29.9)))
        return PourResult(
            tuple(
                dataclasses.replace(p, pieces=ClipperBackend().union([*p.pieces, bar]))
                if p.poured and names.get(p.index) == "P3"
                else p
                for p in found.polygons
            ),
            found.evidence,
        )

    with monkeypatch.context() as patch:
        patch.setattr(engine, "pour_reading", keeping)
        patch.setattr(engine, "check_pour", lambda *_: ())
        return build_sample(SAMPLES_DIR / "pour" / "design.py").files["computed/pour.PcbDoc"]


def test_a_neck_removed_differently(kit: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A neck removed differently": the saved board of K6.2 keeps the 4.5 mil neck of P3."""
    simulate(kit, replace={"pour/rebuilt.PcbDoc": _neck_kept(monkeypatch)})
    verdict = _verdict(kit)
    step = _step(verdict, "K6.2")
    assert step.outcome == "fail"
    assert any(reason.startswith("pour-match: probe P3 (P3): M2") for reason in step.reasons), step.reasons
    assert all(reason.startswith("pour-match: probe P3 ") for reason in step.reasons), step.reasons
    rows = _rows(verdict)
    assert (rows["H-A-POUR-KIT"], rows["H-A-POUR-NECK"], rows["H-A-POUR-STEPS"]) == ("fail", "fail", "fail")
    assert rows["H-A-POUR-CLEARANCE"] == "pass" and rows["H-A-POUR-OVER"] == "pass"

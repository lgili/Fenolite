# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The canary check every rules test runs (capability kicad-oracle, "Rules proofs carry a canary",
scenario "Canary absent"; change c0018). Hermetic: no kicad-cli is needed."""

from __future__ import annotations

import _rulebench as rb
import pytest

from fenolite.backends.base import DrcItem, DrcReport, DrcViolation
from fenolite.core.coords import Point


def report(*violations: DrcViolation) -> DrcReport:
    return DrcReport("bench.kicad_pcb", "", "10.0.6", "mm", violations=violations)


def clearance(a: str, b: str) -> DrcViolation:
    return DrcViolation("clearance", "", "error", (DrcItem(a, "", Point(0, 0)), DrcItem(b, "", Point(0, 0))))


def test_canary_absent_fails() -> None:
    bench = rb.builder().build()
    (a,), (b,) = bench.uuids("canary_a"), bench.uuids("canary_b")
    for found in (
        report(),
        report(DrcViolation("track_dangling", "", "warning", (DrcItem(a, "", Point(0, 0)),))),
    ):
        with pytest.raises(pytest.fail.Exception, match="rules file not loaded"):
            rb.require_canary(found, bench)
    with pytest.raises(pytest.fail.Exception, match="rules file not loaded"):
        rb.require_canary(None, bench)
    assert not rb.canary_fired(report(clearance(a, "other")), bench)
    assert rb.require_canary(report(clearance(b, a)), bench) is not None


def test_canary_rule_comes_first() -> None:
    text = rb.with_canary('(version 1)\n(rule "x" (constraint clearance (min 1mm)))\n')
    assert text.index("(rule canary") < text.index('(rule "x"')
    with pytest.raises(ValueError):
        rb.with_canary("(rule x)\n")


def test_canary_pair_geometry() -> None:
    bench = rb.builder()
    bench.pair("p", "N1", "N2")
    tracks = {t.net_id: t for t in bench.build().design.board.tracks}  # type: ignore[union-attr]
    nets = {n.name: n.id for n in bench.nets.values()}
    a, b = tracks[nets["CANARY_A"]], tracks[nets["CANARY_B"]]
    assert b.start.y - a.start.y == 1_000_000 and a.width == 250_000
    nearest = min(t.start.y for t in tracks.values() if t.net_id not in (a.net_id, b.net_id))
    assert nearest - b.start.y >= 10_000_000

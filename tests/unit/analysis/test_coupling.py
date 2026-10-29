# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The coupling screen of change c0204 (capability board-analyses, "Coupling screen"), on the authored bench
``coupling()`` of ``tests/_practicebench.py``."""

from __future__ import annotations

from fractions import Fraction
from math import floor

from _practicebench import coupling

from fenolite.analysis.coupling import NOTE, CouplingReport, analyze_coupling
from fenolite.backends.kicad.frame import board_pads
from fenolite.core.evidence import Level

MM = 1_000_000
H = 1_600_000


def screen(thickness: int | None = H) -> CouplingReport:
    design = coupling()
    return analyze_coupling(
        design,
        pads=board_pads(design),
        aggressors=("PHASE_*", "LED"),
        victims=("ISENSE",),
        board_thickness=thickness,
    )


def expected(length: int, gap: int) -> int:
    return floor(Fraction(length * H * H, H * H + gap * gap))


def test_a_sense_net_beside_a_phase_track() -> None:
    """Scenario "A sense net beside a phase track": the 10 mm at 0.5 mm rank above the 30 mm at 3 mm."""
    report = screen()
    first, second, third = report.rows
    assert (first.aggressor, first.victim, first.parallel, first.gap) == (
        "PHASE_U",
        "ISENSE",
        10 * MM,
        MM // 2,
    )
    assert first.score == expected(10 * MM, MM // 2) == 9_110_320
    assert (second.aggressor, second.parallel, second.gap) == ("LED", 30 * MM, 3 * MM)
    assert second.score == expected(30 * MM, 3 * MM)
    assert report.summary["note"] == NOTE and "not a voltage" in NOTE
    assert report.evidence.level is Level.INFERRED and report.issues == ()
    assert (third.aggressor, third.parallel, third.score) == ("PHASE_V", 0, 0)


def test_coupling_broadside_on_the_neighbouring_layer() -> None:
    rows = {row.aggressor: row for row in screen().rows}
    assert rows["PHASE_V"].broadside == 5 * MM and rows["PHASE_U"].broadside == 0


def test_coupling_victim_reference_share() -> None:
    (victim,) = screen().victims
    assert (victim.net, victim.length, victim.referenced_permille) == ("ISENSE", 40 * MM, 0)


def test_coupling_without_a_height_scores_nothing() -> None:
    report = screen(thickness=None)
    assert all(row.score is None for row in report.rows if row.aggressor != "PHASE_V")
    assert [i.code for i in report.issues] == ["analysis.input-missing"]
    assert report.heights == {"F.Cu": None, "B.Cu": None}


def test_coupling_unmatched_names() -> None:
    design = coupling()
    report = analyze_coupling(design, pads=board_pads(design), aggressors=("NOPE",), victims=("ISENSE",))
    assert report.rows == () and "analysis.input-missing" in [i.code for i in report.issues]

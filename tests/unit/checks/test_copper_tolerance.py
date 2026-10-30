# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The clearance tolerance of the tool (capability copper-check, "Clearance tolerance of the tool"; change
c0281, issue 3 of the board library's conversion report): KiCad's DRC reports a clearance only below the
value minus 500 nm (``H-K-COPPER-EPSILON``), and the build's copper guard follows it."""

from __future__ import annotations

import pytest
from _coppercheck import Copper, mm

from fenolite.backends.kicad.copperrules import KICAD_DRC_EPSILON_NM
from fenolite.backends.kicad.triad import write_triad
from fenolite.checks.copper import check_copper
from fenolite.cli.cmd_build import copper_guard
from fenolite.core.coords import Point

CLASS = "Signal"


def bench(edge_gap: int) -> Copper:
    made = Copper()
    made.netclass(CLASS, mm(0.2))
    made.net("A", CLASS)
    made.net("B", CLASS)
    made.track("A", Point(0, 0), Point(mm(10), 0), width=250_000)
    made.track("B", Point(0, 250_000 + edge_gap), Point(mm(10), 250_000 + edge_gap), width=250_000)
    return made


def guarded(edge_gap: int) -> list[str]:
    texts = write_triad(bench(edge_gap).build(), name="bench", target=10)
    files = {name: text.encode("utf-8") for name, text in texts.items()}
    issues, result = copper_guard(files, name="bench", mode="refuse", target=10)
    assert result["ran"] is True
    return [issue.code for issue in issues if issue.code == "copper.clearance"]


def test_kicads_tolerance() -> None:
    """Scenario "KiCad's tolerance"."""
    assert KICAD_DRC_EPSILON_NM == 500
    assert guarded(mm(0.2) - 500) == []
    assert guarded(mm(0.2) - 501) == ["copper.clearance"]
    for gap in (mm(0.2) - 500, mm(0.2) - 501):
        (found,) = check_copper(bench(gap).build(), pads=None).findings
        assert found.code == "copper.clearance"


def test_tolerance_on_the_function() -> None:
    assert check_copper(bench(mm(0.2) - 500).build(), pads=None, tolerance=500).findings == ()
    report = check_copper(bench(mm(0.2) - 501).build(), pads=None, tolerance=500)
    assert [f.code for f in report.findings] == ["copper.clearance"] and report.summary["tolerance"] == 500
    with pytest.raises(ValueError, match="tolerance"):
        check_copper(bench(mm(0.2)).build(), pads=None, tolerance=-1)

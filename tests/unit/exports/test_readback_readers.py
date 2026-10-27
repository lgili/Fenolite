# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The read-back readers on authored texts in the form ``kicad-cli`` writes (change c0203; the facts in
``docs/formats/kicad/gerber.md`` and ``docs/formats/kicad/drill.md``)."""

from __future__ import annotations

import pytest

from fenolite.core.coords import Point
from fenolite.exports.readback import Hole, Unsupported, check_drill, contours, read_drill, read_gerber

HEAD = "%TF.FileFunction,Profile,NP*%\n%FSLAX46Y46*%\n%MOMM*%\n%LPD*%\nG01*\n%ADD10C,0.100000*%\nD10*\n"
MM = 1_000_000


def test_a_closed_rectangle_and_a_stadium() -> None:
    text = HEAD + (
        "X0Y0D02*\nX60000000Y0D01*\nX60000000Y0D02*\nX60000000Y-40000000D01*\n"
        "X60000000Y-40000000D02*\nX0Y-40000000D01*\nX0Y-40000000D02*\nX0Y0D01*\n"
        "X13000000Y-31000000D02*\nX17000000Y-31000000D01*\nX17000000Y-33000000D02*\nX13000000Y-33000000D01*\n"
        "X17000000Y-31000000D02*\nG75*\nG02*\nX17000000Y-33000000I0J-1000000D01*\nG01*\n"
        "X13000000Y-33000000D02*\nG75*\nG02*\nX13000000Y-31000000I0J1000000D01*\nG01*\nM02*\n"
    )
    gerber = read_gerber(text)
    assert gerber.function == "Profile,NP" and gerber.operations == 8
    found = contours(gerber.pieces)
    assert found == [((0, -40 * MM, 60 * MM, 0), True), ((12 * MM, -33 * MM, 18 * MM, -31 * MM), True)]


def test_an_open_contour() -> None:
    gerber = read_gerber(HEAD + "X0Y0D02*\nX10000000Y0D01*\nM02*\n")
    assert contours(gerber.pieces) == [((0, 0, 10 * MM, 0), False)]


@pytest.mark.parametrize(
    "text",
    [
        "%FSLAX36Y36*%\n%MOMM*%\n",
        "%FSLAX46Y46*%\n%MOIN*%\n",
        "%FSLAX46Y46*%\n%MOMM*%\n%SRX2Y2I1J1*%\n",
        "%FSLAX46Y46*%\n%MOMM*%\nX1Y1D04*\n",
        "X1Y1D01*\n",
    ],
)
def test_gerber_outside_the_subset(text: str) -> None:
    with pytest.raises(Unsupported):
        read_gerber(text)


DRILL = """M48
; #@! TF.FileFunction,NonPlated,1,2,NPTH
FMAT,2
METRIC
T1C1.000
%
G90
G05
T1
X29.0Y-10.0G85X31.0Y-10.0
X5.0Y-5.0
M30
"""


def test_drill_hits_and_slots() -> None:
    drill = read_drill(DRILL)
    assert drill.plated is False and drill.hits == [(Point(5 * MM, -5 * MM), MM)]
    assert drill.slots == [(Point(29 * MM, -10 * MM), Point(31 * MM, -10 * MM), MM)]
    holes = [
        Hole(Point(29 * MM, 10 * MM), Point(31 * MM, 10 * MM), MM, False, "H1"),
        Hole(Point(5 * MM, 5 * MM), Point(5 * MM, 5 * MM), MM, False, "H2"),
    ]
    assert check_drill({"a.drl": drill}, holes) == []
    plated = [Hole(Point(5 * MM, 5 * MM), Point(5 * MM, 5 * MM), MM, True, "H2"), holes[0]]
    issues = check_drill({"a.drl": drill}, plated)
    assert [i.where for i in issues] == ["a.drl", "H2"]


@pytest.mark.parametrize(
    "change", [("METRIC", "INCH"), ("X5.0Y-5.0", "X50Y-50"), ("T1C1.000", "T1F00S00C1.000")]
)
def test_drill_outside_the_subset(change: tuple[str, str]) -> None:
    with pytest.raises(Unsupported):
        read_drill(DRILL.replace(*change))

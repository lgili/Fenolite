# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``analysis.returns`` (change c0202; capability board-analyses, "Return paths"), on the authored bench of
``tests/_returnbench.py``."""

from __future__ import annotations

from _returnbench import EDGE, GAP, bench

from fenolite.analysis.returns import ReturnReport, ReturnRow, analyze_returns
from fenolite.backends.kicad.frame import board_pads
from fenolite.core.evidence import Level

MM = 1_000_000


def run(*, reference: tuple[str, ...] = (), via_distance: int | None = None) -> ReturnReport:
    design = bench()
    return analyze_returns(
        design, pads=board_pads(design), nets=("SIG*",), reference=reference, via_distance=via_distance
    )


def rows(**options: object) -> dict[str, ReturnRow]:
    return {row.net: row for row in run(**options).rows}  # type: ignore[arg-type]


def test_a_track_across_a_gap() -> None:
    """Scenario "A track across a split plane": one split span as wide as the gap, one warning."""
    report = run()
    sig1 = rows()["SIG1"]
    (span,) = sig1.spans
    assert span.kind == "split" and GAP <= span.length <= GAP + 2 and span.layer == "F.Cu"
    assert (span.start.x, span.end.x) in [(28 * MM, 32 * MM), (28 * MM - 1, 32 * MM), (28 * MM, 32 * MM + 1)]
    assert sig1.length == 40 * MM and sig1.unreferenced == span.length
    codes = [i.code for i in report.issues]
    assert codes == ["analysis.return-split"] and report.evidence.level is Level.INFERRED


def test_a_track_off_the_plane_is_an_edge() -> None:
    (span,) = rows()["SIG2"].spans
    assert span.kind == "edge" and EDGE <= span.length <= EDGE + 2


def test_a_track_over_the_plane() -> None:
    sig3 = rows()["SIG3"]
    assert sig3.spans == () and sig3.unreferenced == 0 and sig3.length == 10 * MM


def test_vias() -> None:
    (via,) = rows()["SIG4"].vias
    assert via.distance == MM and via.nearest is not None
    near = run(via_distance=2 * MM)
    assert "analysis.return-via" not in [i.code for i in near.issues]
    far = run(via_distance=MM // 2)
    assert [i.code for i in far.issues].count("analysis.return-via") == 1


def test_reference_nets_can_be_named() -> None:
    """Naming a reference net with no fill leaves every track unreferenced, as edge spans."""
    sig3 = rows(reference=("VREF",))["SIG3"]
    assert sig3.unreferenced == sig3.length and sig3.spans[0].kind == "edge"


def test_no_match() -> None:
    design = bench()
    report = analyze_returns(design, pads=board_pads(design), nets=("NOPE",))
    assert report.rows == () and [i.code for i in report.issues] == ["analysis.input-missing"]

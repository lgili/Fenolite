# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pairing of Fenolite's findings with a tool's own DRC rows (change c0498, task 4.2; ``checks.native``,
design D3). Every finding and row is authored here."""

from __future__ import annotations

from fenolite.backends.altium.rulemap import NATIVE_CODES
from fenolite.backends.base import NativeFinding
from fenolite.checks.codes import issue
from fenolite.checks.native import compare
from fenolite.core.coords import Point

OURS = [
    issue("copper.clearance", "track of A is 0.1 mm from track of B at (1, -2) mm", where="T#1, T#2"),
    issue("copper.edge-clearance", "pad R1-1 is near the edge at (5, -5) mm", where="R1-1, cutout 1"),
    issue("silk.clearance", "txt is 0.01mm from trk at (9, -9) mm", where="Texts6/Data#1, Tracks6/Data#4"),
    issue("copper.short", "a short at (3, -3) mm", where="T#7, T#8"),
]


def run(ours=OURS, rows=()):  # noqa: ANN001, ANN201
    return compare(ours, rows, NATIVE_CODES, source="stored", file="board.PcbDoc")


def test_items_pair_and_order_does_not_matter() -> None:
    rows = [
        NativeFinding("Clearance", "Clearance", ("T#1", "T#2"), None, ""),
        NativeFinding("BoardOutlineClearance", "Edge", ("R1-1", "edge"), None, ""),
        NativeFinding("SilkToSilkClearance", "Silk", ("Texts6/Data#1", "Tracks6/Data#4"), None, ""),
        NativeFinding("Height", "Height", ("C1",), None, ""),
        NativeFinding("Clearance", "Clearance", ("T#5", "T#6"), None, "", waived=True),
    ]
    warnings, summary = run(rows=rows)
    assert summary["matched"] == 3 and summary["unjudged"] == {"Height": 1} and summary["waived"] == 1
    assert summary["fenolite_only"] == [{"code": "copper.short", "where": "T#7, T#8"}]
    assert summary["native_only"] == [] and summary["stale"] == 0
    assert summary["by_kind"]["ShortCircuit"] == {"matched": 0, "fenolite_only": 1, "native_only": 0}
    assert [w.code for w in warnings] == ["check.fenolite-only"] and warnings[0].severity == "warning"
    again = run(list(reversed(OURS)), list(reversed(rows)))
    assert again == (warnings, summary)


def test_a_report_row_pairs_by_place() -> None:
    """A row without items pairs with a finding of its kind within 0.1 mm of the place its message gives."""
    near = NativeFinding("Clearance", "Clearance Constraint", (), Point(1_050_000, -2_000_000), "Violation")
    far = NativeFinding("Clearance", "Clearance Constraint", (), Point(1_200_000, -2_000_000), "Violation")
    assert run(rows=[near])[1]["matched"] == 1
    warnings, summary = run(rows=[far])
    assert summary["matched"] == 0 and summary["by_kind"]["Clearance"]["native_only"] == 1
    assert "check.native-only" in [w.code for w in warnings]


def test_stale_rows_are_said_once() -> None:
    rows = [NativeFinding("Clearance", "C", ("T#1", "T#99"), None, "", stale=True)] * 2
    warnings, summary = run(rows=rows)
    assert summary["stale"] == 2 and [w.code for w in warnings].count("check.native-stale") == 1

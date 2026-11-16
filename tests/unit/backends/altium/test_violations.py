# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Altium's own DRC results read back (change c0498, task 4.1; ``read.violations``): the violations an
authored PCB document stores in the recorded layout, and an authored ``.drc`` text report."""

from __future__ import annotations

from pathlib import Path

import pytest
from _violations import BLINK, storage, violation, with_storages

from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.violations import (
    UNKNOWN,
    holds_violations,
    report_violations,
    stored_violations,
)
from fenolite.core.coords import Point
from fenolite.model.design import Design

MIL = 25_400


@pytest.fixture(scope="module")
def design() -> Design:
    return AltiumBackend().read(BLINK).design


def refs(design: Design) -> dict[str, str]:
    """``Pads6/Data#n`` → ``REF-PIN`` as the copper check names a pad."""
    names = {c.id: c.ref for c in design.circuit.components}
    assert design.board is not None
    return {
        p.provenance.locator: f"{names[fp.component_id]}-{p.number}"
        for fp in design.board.footprints
        for p in fp.pads
        if p.provenance is not None
    }


def test_stored_violations_name_items_rules_and_places(tmp_path: Path, design: Design) -> None:
    """A violation names its rule by position, its pads as ``REF-PIN`` and its place in the model frame."""
    path = with_storages(
        tmp_path / "board.PcbDoc",
        storage(
            "TClearanceViolation", [violation(1, ("Pad", 0), ("Pad", 2), "1000mil", "2000mil", "Clearance")]
        ),
        storage(
            "TBoardOutlineClearanceViolation", [violation(1, ("Track", 3), ("Board", 0), "10mil", "5mil")]
        ),
    )
    assert holds_violations(path) and not holds_violations(BLINK)
    read = stored_violations(path, design)
    assert read.issues == () and read.source == "stored" and read.evidence.level.value == "CORPUS-VERIFIED"
    clearance, edge = read.findings
    pads = refs(design)
    assert clearance.kind == "Clearance" and clearance.rule == "Clearance"
    assert clearance.primitives == tuple(sorted((pads["Pads6/Data#0"], pads["Pads6/Data#2"])))
    assert clearance.at == Point(1000 * MIL, -2000 * MIL) and clearance.message == "Clearance"
    assert edge.kind == "Clearance"  # RULEINDEX 1 names a Clearance rule: the rule's RULEKIND wins
    assert edge.primitives == ("Tracks6/Data#3", "edge") and not edge.waived and not edge.stale


def test_waived_stale_and_unknown(tmp_path: Path, design: Design) -> None:
    waived = {"RULEINDEX": "1", "PRIM1KIND": "Pad", "PRIM1INDEX": "0", "PRIM2KIND": "Pad", "PRIM2INDEX": "2"}
    path = with_storages(
        tmp_path / "board.PcbDoc",
        storage(
            "TClearanceViolation",
            [
                violation(1, ("Pad", 0), ("Pad", 2), "0mil", "0mil"),
                violation(1, ("Track", 999), ("Pad", 2), "0mil", "0mil"),
                violation(1, ("Widget", 1), ("Pad", 2), "0mil", "0mil"),
            ],
        ),
        storage("WaivedViolations", [waived]),
    )
    read = stored_violations(path, design)
    assert [(f.waived, f.stale) for f in read.findings] == [(True, False), (False, True)]
    (unknown,) = read.issues
    assert unknown.code == UNKNOWN and unknown.where == "TClearanceViolation/Data#2"


def test_a_header_count_that_differs_is_said(tmp_path: Path, design: Design) -> None:
    path = with_storages(
        tmp_path / "board.PcbDoc",
        storage("TWidthViolation", [violation(3, ("Track", 1), ("Track", 1), "0mil", "0mil")], count=2),
    )
    read = stored_violations(path, design)
    assert len(read.findings) == 1 and [i.code for i in read.issues] == [UNKNOWN]


REPORT = """Protel Design System Design Rule Check
PCB File : board.PcbDoc

Processing Rule : Clearance Constraint (Gap=10mil) (All),(All)
   Violation between Clearance Constraint: (8mil < 10mil) Between Pad U1-1(1000mil,2000mil) on Top Layer And Track (1000mil,2010mil)(1200mil,2010mil) on Top Layer
Rule Violations :1

Processing Rule : Fancy Constraint (All)
   Violation between Fancy Constraint: Track (0mm,1.5mm)(1mm,1.5mm) on Top Layer
Rule Violations :1

Violations Detected : 2
"""  # noqa: E501


def test_report_lines(tmp_path: Path, design: Design) -> None:
    """Authored lines of the recorded form (``H-A-DRC-TXT``, INFERRED): the kind from the constraint name,
    the place from the first coordinate pair; a kind no table names is said."""
    report = tmp_path / "Design Rule Check - board.drc"
    report.write_text(REPORT, encoding="utf-8")
    read = report_violations(report, design)
    assert read.source == "report" and read.evidence.level.value == "INFERRED"
    clearance, other = read.findings
    assert (clearance.kind, clearance.primitives, clearance.at) == (
        "Clearance",
        (),
        Point(1000 * MIL, -2000 * MIL),
    )
    assert clearance.rule.startswith("Clearance Constraint") and clearance.message.startswith("Violation")
    assert other.kind == "unknown" and other.at == Point(0, -1_500_000)
    assert [i.code for i in read.issues] == [UNKNOWN]

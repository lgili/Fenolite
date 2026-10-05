# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every evidence a backend declares agrees with the hypothesis register (capability
verification-evidence, "Declared levels agree with the register"; change c0067).

The rule is ``fenolite.verify.report_problems``, the one the capability report passes
(``tests/unit/test_capability_evidence.py``): every named id has a row, no named row is refuted, and the
declared level is not above any row it names. Lowest wins; a weaker declaration is accepted.
"""

from __future__ import annotations

from pathlib import Path

from fenolite.backends import matrix
from fenolite.core.evidence import Evidence, Level
from fenolite.verify import load_register, report_problems

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "docs" / "hypotheses.md"
FIX = (
    "To fix it: lower the declared level to the weakest row it names, or name the rows that support it; "
    "a refuted row supports nothing, so name its successor. Never edit a row of docs/hypotheses.md to make "
    "this pass: a row changes only when its test settles it."
)


def live_problems() -> list[str]:
    """One line per declared constant or matrix cell that the register does not support."""
    rows = load_register(REGISTER)
    found: list[str] = []
    for package in matrix.packages():
        for claim in matrix.module_claims(package):
            for name, evidence in claim.constants:
                found += [f"{package}.{claim.module}.{name}: {p}" for p in report_problems(evidence, rows)]
    for row in matrix.rows():
        for operation, cell in row.cells():
            found += [
                f"matrix row {row.backend}/{row.kind}, {operation}: {p}" for p in report_problems(cell, rows)
            ]
    return found


def test_live_declarations_agree_with_the_register() -> None:
    found = live_problems()
    assert not found, "\n".join([*found, "", FIX])


def test_live_check_covers_every_package_and_every_cell() -> None:
    constants = [
        evidence
        for package in matrix.packages()
        for claim in matrix.module_claims(package)
        for _, evidence in claim.constants
    ]
    assert len(constants) >= 40 and len(matrix.rows()) >= 15
    assert any(evidence.hypotheses for evidence in constants)
    registered = {row.id for row in load_register(REGISTER)}
    named = {ident for row in matrix.rows() for ident in row.verified_by()}
    assert named and named <= registered, sorted(named - registered)


def test_declaration_stronger_than_its_row() -> None:
    rows = load_register(REGISTER)
    by_id = {row.id: row for row in rows}
    assert by_id["H-K-LIB-READ"].level is Level.INFERRED
    problems = report_problems(Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-LIB-READ",)), rows)
    assert len(problems) == 1
    assert all(word in problems[0] for word in ("H-K-LIB-READ", "KICAD-VERIFIED", "INFERRED"))


def test_weaker_declaration_is_accepted() -> None:
    rows = load_register(REGISTER)
    by_id = {row.id: row for row in rows}
    assert by_id["H-K-PCB-WRITE"].level is Level.KICAD_VERIFIED
    assert report_problems(Evidence(Level.INFERRED, hypotheses=("H-K-PCB-WRITE",)), rows) == []


def test_refuted_row_supports_no_declaration() -> None:
    rows = load_register(REGISTER)
    refuted = next(row for row in rows if row.id == "H-A-RD-SCH-TEXT")
    assert refuted.refuted
    problems = report_problems(Evidence(Level.INFERRED, hypotheses=(refuted.id,)), rows)
    assert len(problems) == 1 and "refuted" in problems[0]

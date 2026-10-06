# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A backend's capability evidence agrees with its operations and with the hypothesis register
(capability backend-protocol, "Capability reports"; change c0052).

``fenolite.verify.report_problems`` (moved there by change c0067) returns one message per problem: a named
hypothesis with no row, a refuted row, or a report level that is stronger than a row it names. A weaker
level is allowed: a row states what its test covered, and the report states what holds for an arbitrary
file.
"""

from __future__ import annotations

from pathlib import Path

from fenolite.backends import registry
from fenolite.backends.kicad import backend as kicad_backend
from fenolite.backends.kicad import pcb
from fenolite.core.evidence import Evidence, Level
from fenolite.verify import report_problems
from fenolite.verify.hypotheses import HypothesisRow, load_register

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "docs" / "hypotheses.md"


def _row(ident: str, level: Level, result: str = "confirmed") -> HypothesisRow:
    return HypothesisRow(
        ident, "kicad", "statement", level, level.value, "test", "criterion", result, "2026-10-04"
    )


ROWS = (_row("H-K-PCB-READ", Level.CORPUS_VERIFIED), _row("H-K-PCB-WRITE", Level.KICAD_VERIFIED))


def test_report_stronger_than_the_register() -> None:
    evidence = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-PCB-READ", "H-K-PCB-WRITE"))
    problems = report_problems(evidence, ROWS)
    assert len(problems) == 1
    assert all(word in problems[0] for word in ("H-K-PCB-READ", "KICAD-VERIFIED", "CORPUS-VERIFIED"))


def test_report_at_or_below_the_register_is_accepted() -> None:
    for level in (Level.CORPUS_VERIFIED, Level.INFERRED, Level.UNVERIFIED):
        assert report_problems(Evidence(level, hypotheses=("H-K-PCB-READ", "H-K-PCB-WRITE")), ROWS) == []


def test_unregistered_hypothesis() -> None:
    problems = report_problems(Evidence(Level.INFERRED, hypotheses=("H-K-PCB-READ",)), ROWS[1:])
    assert len(problems) == 1 and "H-K-PCB-READ" in problems[0] and "not registered" in problems[0]


def test_refuted_hypothesis() -> None:
    rows = (_row("H-K-PCB-READ", Level.KICAD_VERIFIED, "refuted; superseded by H-K-PCB-WRITE"),)
    problems = report_problems(Evidence(Level.INFERRED, hypotheses=("H-K-PCB-READ",)), rows)
    assert len(problems) == 1 and "H-K-PCB-READ" in problems[0] and "refuted" in problems[0]


def test_kicad_report_follows_its_operations() -> None:
    report = registry.get("kicad").capabilities()
    assert report.evidence == Evidence.combine(pcb.EVIDENCE, pcb.WRITE_EVIDENCE)
    assert report.evidence.hypotheses == ("H-K-PCB-READ", "H-K-PCB-WRITE")
    source = Path(kicad_backend.__file__).read_text(encoding="utf-8")
    assert "Level." not in source, "the report's level is computed from pcb.EVIDENCE and pcb.WRITE_EVIDENCE"


def test_live_reports_agree_with_the_register() -> None:
    rows = load_register(REGISTER)
    backends = registry.all_backends()
    assert backends
    for backend in backends:
        evidence = backend.capabilities().evidence
        assert evidence.hypotheses, f"{backend.name}: the report names no hypothesis"
        assert report_problems(evidence, rows) == [], backend.name

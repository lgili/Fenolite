# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A fake ``Validator`` and a fake ``Oracle`` for ``checks`` tests: no backend module is imported."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fenolite.backends.base import (
    DrcItem,
    DrcOutcome,
    DrcReport,
    DrcViolation,
    ProjectSet,
    ReadResult,
    RoundTrip,
    SkippedFile,
    Validation,
)
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design

READ_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-PCB-READ",))
VERIFIED = Evidence(Level.KICAD_VERIFIED, oracle="fake 1.0", hypotheses=("H-FAKE-DRC",))


def roundtrip(passed: bool = True, difference: str = "") -> RoundTrip:
    return RoundTrip("RT1", passed, True, passed, True, opaque_count=2, difference=difference)


def validation(
    design: Design | None = None, *, passed: bool = True, difference: str = "", issues: tuple[Issue, ...] = ()
) -> Validation:
    read = ReadResult(design if design is not None else Design.new("fake", seed=0), issues, READ_EVIDENCE)
    return Validation(read, roundtrip(passed, difference))


@dataclass
class FakeValidator:
    result: Validation | None = None
    error: FormatError | None = None
    name: str = "fake"
    calls: list[Path] = field(default_factory=lambda: [])

    def validate(self, path: Path, *, issues: list[Issue] | None = None) -> Validation:
        self.calls.append(path)
        if self.error is not None:
            raise self.error
        return self.result if self.result is not None else validation()


def report(*violations: DrcViolation, unconnected: tuple[DrcViolation, ...] = ()) -> DrcReport:
    return DrcReport("board.kicad_pcb", "", "1.0", "mm", violations=violations, unconnected_items=unconnected)


def violation(kind: str = "clearance", severity: str = "error", uid: str = "u1") -> DrcViolation:
    return DrcViolation(kind, kind, severity, (DrcItem(uid, "item", Point(0, 0)),))


def outcome(
    canary: str = "fired",
    reason: str = "",
    *,
    drc: DrcReport | None = None,
    missing: bool = False,
    timeout: bool = False,
    evidence: Evidence = VERIFIED,
) -> DrcOutcome:
    found = None if missing or timeout else (drc if drc is not None else report())
    return DrcOutcome(
        report=found,
        tool_version="1.0",
        canary=canary,  # type: ignore[arg-type]
        canary_reason=reason,
        canary_removed=1 if canary == "fired" else 0,
        tool_writes=("z.kicad_prl", "a.kicad_prl"),
        outcome="timeout" if timeout else "exit",
        returncode=None if timeout else (3 if missing else 0),
        message="no board" if missing else "",
        evidence=evidence if found is not None else Evidence(),
    )


@dataclass
class FakeOracle:
    result: DrcOutcome = field(default_factory=outcome)
    name: str = "fake"
    calls: list[ProjectSet] = field(default_factory=lambda: [])

    def version(self) -> str:
        return "1.0"

    def drc(self, project: ProjectSet) -> DrcOutcome:
        self.calls.append(project)
        return self.result


def project(
    *, has_project: bool = True, has_rules: bool = True, skipped: tuple[SkippedFile, ...] = ()
) -> ProjectSet:
    files = {"board.kicad_pcb": Path("p/board.kicad_pcb")}
    return ProjectSet(Path("p"), "board.kicad_pcb", files, skipped, has_project, has_rules)


__all__ = ["FakeOracle", "FakeValidator", "outcome", "project", "report", "validation", "violation"]

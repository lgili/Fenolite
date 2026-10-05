# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A fake ``Validator``, a fake ``Oracle`` and a fake ``DocumentValidator`` for ``checks`` tests: no backend
module is imported.

``FakeRulesValidator`` also satisfies ``DesignRulesSource`` and ``BoardFrame``, as the KiCad backend does
(change c0029)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fenolite.backends.base import (
    BoardPad,
    CapabilityReport,
    ContainerLevel,
    ContainerRoundTrip,
    DesignRules,
    Document,
    DocumentSet,
    DrcItem,
    DrcOutcome,
    DrcReport,
    DrcViolation,
    FillOutcome,
    ModelScope,
    NetlistOutcome,
    PadAssignment,
    PadNetList,
    PlacedExtent,
    ProjectRead,
    ProjectSet,
    ReadResult,
    RoundTrip,
    Rt2Outcome,
    SkippedFile,
    Uncovered,
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


@dataclass
class FakeRulesValidator(FakeValidator):
    """A validator that is also a rules source and a board frame: it answers with ``rules`` (the design
    as given when ``None``) and ``pads``, and records what it was asked."""

    rules: DesignRules | None = None
    pads: tuple[BoardPad, ...] = ()
    asked: list[tuple[str, Design]] = field(default_factory=lambda: [])

    def design_rules(
        self, design: Design, project: ProjectSet, *, issues: list[Issue] | None = None
    ) -> DesignRules:
        self.asked.append(("rules", design))
        return self.rules if self.rules is not None else DesignRules(design, evidence=READ_EVIDENCE)

    def board_pads(self, design: Design, *, issues: list[Issue] | None = None) -> tuple[BoardPad, ...]:
        self.asked.append(("pads", design))
        return self.pads

    def placed_extents(
        self, design: Design, *, issues: list[Issue] | None = None
    ) -> tuple[PlacedExtent, ...]:
        return ()


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


@dataclass
class FakeFillOracle:
    result: FillOutcome = FillOutcome((), "1.0", evidence=VERIFIED)
    name: str = "fake"
    calls: list[ProjectSet] = field(default_factory=lambda: [])

    def refill(self, project: ProjectSet) -> FillOutcome:
        self.calls.append(project)
        return self.result


def netlist(source: str, *pairs: tuple[str, str], uncovered: tuple[tuple[str, str], ...] = ()) -> PadNetList:
    """A ``PadNetList`` from ``(element, label)`` pairs and ``(element, reason)`` uncovered pairs."""
    return PadNetList(
        source,
        tuple(PadAssignment(e, n) for e, n in pairs),
        tuple(Uncovered(e, r) for e, r in uncovered),
    )


def netlist_outcome(
    found: PadNetList | None, *, timeout: bool = False, evidence: Evidence = VERIFIED
) -> NetlistOutcome:
    return NetlistOutcome(
        netlist=None if timeout else found,
        tool_version="1.0",
        outcome="timeout" if timeout else "exit",
        returncode=None if timeout else (0 if found is not None else 3),
        message="" if found is not None and not timeout else "no export",
        evidence=evidence if found is not None and not timeout else Evidence(),
    )


def rt2_outcome(
    before: tuple[DrcReport, ...] = (), after: DrcReport | None = None, *, normalised: bool = True,
    timeout: bool = False, evidence: Evidence = VERIFIED, repeats: tuple[DrcReport, ...] = (),
) -> Rt2Outcome:  # fmt: skip
    complete = len(before) >= 2 and after is not None and not timeout
    return Rt2Outcome(
        before=before,
        after=after,
        normalised=normalised,
        tool_version="1.0",
        outcome="timeout" if timeout else "exit",
        returncode=None if timeout else 0,
        message="" if complete else "no report",
        evidence=evidence if complete else Evidence(),
        repeats=repeats,
    )


@dataclass
class FakeFullOracle(FakeOracle):
    """A fake that also satisfies ``NetlistOracle`` and ``RoundTripOracle``."""

    netlist_result: NetlistOutcome = field(default_factory=lambda: netlist_outcome(None))
    rt2_result: Rt2Outcome = field(default_factory=rt2_outcome)
    boards: list[Design] = field(default_factory=lambda: [])

    def netlist(self, project: ProjectSet, *, board: Design) -> NetlistOutcome:
        self.calls.append(project)
        self.boards.append(board)
        return self.netlist_result

    def rt2(self, project: ProjectSet) -> Rt2Outcome:
        self.calls.append(project)
        return self.rt2_result


def project(
    *, has_project: bool = True, has_rules: bool = True, skipped: tuple[SkippedFile, ...] = ()
) -> ProjectSet:
    files = {"board.kicad_pcb": Path("p/board.kicad_pcb")}
    return ProjectSet(Path("p"), "board.kicad_pcb", files, skipped, has_project, has_rules)


@dataclass
class FakeReader:
    """A backend that only detects, reads and reports: not a ``DocumentValidator``."""

    name: str = "fake-reader"

    def detect(self, path: Path) -> bool:
        return path.suffix == ".fake"

    def read(self, path: Path, *, issues: list[Issue] | None = None) -> ReadResult:
        return ReadResult(Design.new("fake", seed=0), (), READ_EVIDENCE)

    def capabilities(self) -> CapabilityReport:
        return CapabilityReport(self.name, ("fake",), (), (), None, "unsupported", ("detect", "read"))


def document_set(*documents: Document, missing: tuple[str, ...] = (), root: Path = Path("p")) -> DocumentSet:
    """A set of ``documents``: its project is the first document of role ``project``, its board the first of
    role ``pcb``."""
    ordered = tuple(sorted(documents, key=lambda d: d.name))
    project = next((d.name for d in ordered if d.role == "project"), None)
    board = next((d.name for d in ordered if d.role == "pcb"), None)
    return DocumentSet(root, project, board, ordered, tuple(sorted(missing)))


CONTAINER_EVIDENCE = Evidence(Level.CORPUS_VERIFIED, hypotheses=("H-FAKE-RT",))
SCH = Document("a.sch", "fake_sch", "schematic")
PCB = Document("a.pcb", "fake_pcb", "pcb")


def passing(level: ContainerLevel, *, streams: int = 2) -> ContainerRoundTrip:
    if level == "RT-A0":
        return ContainerRoundTrip(level, True, True, streams=streams, evidence=CONTAINER_EVIDENCE)
    return ContainerRoundTrip(
        level, True, True, streams=streams, records=10, bytes_equal=streams, evidence=CONTAINER_EVIDENCE
    )


@dataclass
class FakeDocumentValidator(FakeReader):
    """A reader that also satisfies ``DocumentValidator``: it answers with what it was given and records
    every call. A verdict that is a ``FormatError`` is raised; a document without a verdict passes."""

    name: str = "fake-documents"
    documents_result: DocumentSet = field(default_factory=lambda: document_set(SCH, PCB))
    schematic: ReadResult | None = None
    pcb: ReadResult | None = None
    errors: dict[str, FormatError] = field(default_factory=lambda: {})
    verdicts: dict[tuple[str, str], ContainerRoundTrip | FormatError] = field(default_factory=lambda: {})
    scope: ModelScope = field(default_factory=lambda: ModelScope({}))
    added: dict[str, Evidence] = field(default_factory=lambda: {})
    read_calls: list[DocumentSet] = field(default_factory=lambda: [])
    roundtrip_calls: list[tuple[str, str]] = field(default_factory=lambda: [])

    def documents(self, path: Path) -> DocumentSet:
        return self.documents_result

    def read_documents(self, documents: DocumentSet) -> ProjectRead:
        self.read_calls.append(documents)
        return ProjectRead(self.schematic, self.pcb, dict(self.errors))

    def container_roundtrip(self, path: Path, level: ContainerLevel) -> ContainerRoundTrip:
        self.roundtrip_calls.append((path.name, level))
        verdict = self.verdicts.get((path.name, level), passing(level))
        if isinstance(verdict, FormatError):
            raise verdict
        return verdict

    def written_scope(self) -> ModelScope:
        return self.scope

    def stage_evidence(self) -> dict[str, Evidence]:
        return dict(self.added)


def reading(
    design: Design, *, issues: tuple[Issue, ...] = (), evidence: Evidence = READ_EVIDENCE
) -> ReadResult:
    return ReadResult(design, issues, evidence)


__all__ = [
    "PCB",
    "SCH",
    "FakeDocumentValidator",
    "FakeReader",
    "document_set",
    "passing",
    "reading",
    "FakeFullOracle",
    "FakeFillOracle",
    "FakeOracle",
    "FakeValidator",
    "netlist",
    "netlist_outcome",
    "outcome",
    "project",
    "report",
    "rt2_outcome",
    "validation",
    "violation",
]

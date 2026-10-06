# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The check of an input that is a set of documents instead of one board (capability verification-loop,
"Document check pipeline"; change c0044).

A backend whose project is a set of documents (``DocumentValidator``) gives two independent readings, the
schematic side and the PCB side, and a container round trip per file. No oracle takes part: every stage
runs on what Fenolite reads. ``STAGE_ORDER`` and ``run_checks`` are not touched; the result types and the
stage helpers are shared with them.

Change c0088 adds the two stages that need no tool on any backend: ``copper.clearance`` (``checks.copper``
on the PCB reading, with the rules and the pads of the backend) and ``parity`` (``checks.parity`` on the two
readings, with the schematic side the backend builds from them). Neither holds check logic of its own: they
say what the reading left unjudged (``unjudged_copper``).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace

from fenolite.backends.base import (
    BoardFrame,
    ContainerLevel,
    ContainerRoundTrip,
    DesignRules,
    DesignRulesSource,
    DocumentParity,
    DocumentRole,
    DocumentSet,
    DocumentValidator,
    PadNetList,
    ProjectRead,
    ProjectSet,
    ReadResult,
)
from fenolite.checks import assignment_compare, erc_lite
from fenolite.checks.clearance import ClearanceResolver
from fenolite.checks.codes import issue
from fenolite.checks.containers import container_stage
from fenolite.checks.stages import CheckReport, StageResult, ran, skipped
from fenolite.checks.validate import BUILT_EVIDENCE
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design

DOCUMENT_STAGES: tuple[str, ...] = (
    "model.validate",
    "erc.lite",
    "copper.clearance",
    "parity",
    "netlist.assignment_compare",
    "roundtrip.rta0",
    "roundtrip.rta1",
    "roundtrip.rta2",
)
"""The stages of a document check, in the order they run."""
CONTAINER_LEVELS: Mapping[str, ContainerLevel] = {"roundtrip.rta0": "RT-A0", "roundtrip.rta1": "RT-A1"}
_READING_STAGES = frozenset(
    {
        "model.validate",
        "erc.lite",
        "copper.clearance",
        "parity",
        "netlist.assignment_compare",
        "roundtrip.rta2",
    }
)
_COUNTED_SKIPS = frozenset({"read-refused", "cache-unreadable"})


def refused(name: str, error: FormatError) -> Issue:
    """``check.read-refused`` for a document: built like ``stages.read_refused``, with the document's name
    as the file."""
    code = getattr(type(error), "cli_code", "FEN-3004")
    parts = (name, error.locator, "" if error.offset is None else f"@{error.offset}")
    return issue("check.read-refused", f"{code}: {error.message}", where=":".join(p for p in parts if p))


def _prefixed(found: Issue, side: str) -> Issue:
    return replace(found, where=f"{side}:{found.where}")


def _model_findings(design: Design) -> list[Issue]:
    return [found for found in design.validate() if found.code.startswith("model.")]


def _counts(design: Design) -> dict[str, int]:
    return {"components": len(design.circuit.components), "nets": len(design.circuit.nets)}


def _named(listed: PadNetList, source: str) -> PadNetList:
    return PadNetList(source, listed.assignments, listed.uncovered)


def project_of(documents: DocumentSet) -> ProjectSet | None:
    """The documents of a set as the project set that a rules source reads from: every document under its
    name, the PCB document as the board; ``None`` for a set without a PCB document."""
    if documents.board is None:
        return None
    files = {document.name: documents.root / document.name for document in documents.documents}
    return ProjectSet(documents.root, documents.board, files)


@dataclass(frozen=True, slots=True)
class _Given:
    """A rules source that returns the rules it was given, so that they are asked for once."""

    rules: DesignRules

    def design_rules(
        self, design: Design, project: ProjectSet, *, issues: list[Issue] | None = None
    ) -> DesignRules:
        return self.rules


def unjudged_copper(design: Design, rules: DesignRules | None) -> tuple[int, int]:
    """``(unpoured, zones_unjudged)`` of the board of ``design`` as the copper check sees it.

    ``unpoured`` counts the zones without a fill: their copper is not in the documents, so nothing of it is
    judged. ``zones_unjudged`` counts the filled zones without a clearance of their own for which no
    clearance is in force whatever the other item is (no rule, class or board minimum applies to copper of
    their net on a layer of theirs): they are judged for shorts, and for clearance only where a rule names
    the other item. ``rules`` is the answer of the rules source (``None``: the design's own rules)."""
    board = (rules.design if rules is not None else design).board
    if board is None:
        return 0, 0
    resolver = ClearanceResolver(
        rules.design if rules is not None else design,
        min_clearance=rules.min_clearance if rules is not None else None,
        rules_over_classes=rules.rules_over_classes if rules is not None else True,
        floor_over_rules=rules.floor_over_rules if rules is not None else False,
    )
    unpoured = unjudged = 0
    for zone in board.zones:
        if not zone.fills:
            unpoured += 1
            continue
        if zone.settings.clearance > 0:
            continue
        for layer in dict.fromkeys(fill.layer for fill in zone.fills):
            subject = resolver.subject("fill", zone.net_id, ref=None, layer=layer)
            if resolver.resolve(subject, subject).unset:
                unjudged += 1
                break
    return unpoured, unjudged


def document_copper(
    design: Design, *, project: ProjectSet, validator: DocumentValidator, evidence: Evidence
) -> StageResult:
    """The ``copper.clearance`` stage of a document check: ``checks.copper.copper_stage`` on the PCB
    reading ``design``, with the rules of ``validator`` when it is a ``DesignRulesSource`` and its pads when
    it is a ``BoardFrame``. Two counts join the summary, ``unpoured`` and ``zones_unjudged``
    (``unjudged_copper``); a count above 0 gives one warning (``copper.item-unsupported`` for the unpoured
    zones, ``copper.rules-incomplete`` for the zones without a clearance) and lowers the stage to
    ``UNVERIFIED``."""
    from fenolite.checks.copper import copper_stage

    rules = validator.design_rules(design, project) if isinstance(validator, DesignRulesSource) else None
    stage = copper_stage(
        design,
        project=project,
        rules_source=None if rules is None else _Given(rules),
        frame=validator if isinstance(validator, BoardFrame) else None,
        evidence=evidence,
    )
    unpoured, unjudged = unjudged_copper(design, rules)
    added: list[Issue] = []
    if unpoured:
        added.append(
            issue(
                "copper.item-unsupported",
                f"{unpoured} unpoured zone(s) left out of the copper check: the document holds no poured "
                "copper for them, and the fabricated board will",
                where="unpoured",
            )
        )
    if unjudged:
        added.append(
            issue(
                "copper.rules-incomplete",
                f"{unjudged} filled zone(s) judged for shorts only: no clearance that was read applies to "
                "them",
                where="zone",
            )
        )
    level = stage.evidence
    if added:
        level = Evidence(Level.UNVERIFIED, hypotheses=level.hypotheses)
    summary = {**stage.summary, "unpoured": unpoured, "zones_unjudged": unjudged}
    return ran(stage.name, [*stage.issues, *added], level, summary)


def run_document_checks(
    *,
    documents: DocumentSet,
    stages: Sequence[str],
    model: Design | None,
    built: bool,
    validator: DocumentValidator,
    cache_error: str = "",
) -> CheckReport:
    """Run the selected stages in ``DOCUMENT_STAGES`` order on ``documents`` (``model`` is the ``.fenolite/``
    model of a built project). ``validator.read_documents`` runs at most once, and
    ``validator.container_roundtrip`` at most once per document and level."""
    from fenolite.checks import parity as parity_check
    from fenolite.checks.rta2 import rta2_stage

    selected = [name for name in DOCUMENT_STAGES if name in stages]
    errors: dict[str, FormatError] = {}
    usable = None if cache_error else model
    read: ProjectRead | None = None
    if _READING_STAGES & set(selected):
        read = validator.read_documents(documents)
        errors.update(read.errors)
    schematic: ReadResult | None = read.schematic if read is not None else None
    pcb: ReadResult | None = read.pcb if read is not None else None
    added = validator.stage_evidence()

    def with_added(name: str, *parts: Evidence) -> Evidence:
        extra = added.get(name)
        return Evidence.combine(*parts, *([] if extra is None else [extra]))

    def any_refused(role: DocumentRole) -> bool:
        return any(document.name in errors for document in documents.of_role(role))

    def model_stage() -> StageResult:
        name = "model.validate"
        if built:
            if usable is None:
                return skipped(name, "cache-unreadable")
            return ran(name, _model_findings(usable), BUILT_EVIDENCE, {"model": _counts(usable)})
        sides = [(side, reading) for side, reading in (("schematic", schematic), ("pcb", pcb)) if reading]
        if not sides:
            return skipped(name, "read-refused" if errors else "not-judged")
        found: list[Issue] = []
        summary: dict[str, object] = {}
        for side, reading in sides:
            design = reading.design
            found += [i for i in reading.issues if not i.code.startswith("model.")]
            found += [_prefixed(i, side) for i in _model_findings(design)]
            summary[side] = _counts(design)
        return ran(name, found, Evidence.combine(*(reading.evidence for _, reading in sides)), summary)

    def erc() -> StageResult:
        name = "erc.lite"
        if built:
            return skipped(name, "cache-unreadable") if usable is None else erc_lite.erc_stage(usable)
        if schematic is None:
            return skipped(name, "read-refused" if any_refused("schematic") else "no-schematic")
        stage = erc_lite.erc_stage(schematic.design)
        return replace(stage, evidence=with_added(name, erc_lite.EVIDENCE, schematic.evidence))

    def copper() -> StageResult:
        name = "copper.clearance"
        project = project_of(documents)
        if project is None:
            return skipped(name, "single-source")
        if pcb is None:
            return skipped(name, "read-refused")
        stage = document_copper(pcb.design, project=project, validator=validator, evidence=pcb.evidence)
        return replace(stage, evidence=with_added(name, stage.evidence))

    def parity() -> StageResult:
        name = "parity"
        if not documents.of_role("schematic"):
            return skipped(name, "no-schematic")
        if documents.board is None:
            return skipped(name, "single-source")
        if schematic is None or pcb is None:
            return skipped(name, "read-refused")
        if not isinstance(validator, DocumentParity):
            return skipped(name, "netlist-unavailable")
        outcome = validator.parity_side(schematic.design, pcb.design)
        if outcome.side is None:
            return skipped(name, "netlist-unavailable")
        report = parity_check.compare(outcome.side, pcb.design)
        evidence = with_added(name, parity_check.EVIDENCE, outcome.evidence, schematic.evidence, pcb.evidence)
        summary: dict[str, object] = {
            "netlist": "own",
            "compared": False,
            "differences": 0,
            **report.summary,
        }
        return ran(name, [parity_check.finding_issue(f) for f in report.findings], evidence, summary)

    def assignment() -> StageResult:
        name = "netlist.assignment_compare"
        if built and usable is None:
            return skipped(name, "cache-unreadable")
        sources: dict[str, tuple[PadNetList, Design, Evidence]] = {}
        unnumbered = 0
        if built and usable is not None:
            sources["model"] = (assignment_compare.model_netlist(usable), usable, BUILT_EVIDENCE)
        if schematic is not None:
            listed = _named(assignment_compare.model_netlist(schematic.design), "schematic")
            sources["schematic"] = (listed, schematic.design, schematic.evidence)
        if pcb is not None:
            board, unnumbered = assignment_compare.board_netlist(pcb.design)
            sources["pcb"] = (_named(board, "pcb"), pcb.design, pcb.evidence)
        wanted = (("model", "schematic"), ("model", "pcb")) if built else (("schematic", "pcb"),)
        pairs = [(a, b) for a, b in wanted if a in sources and b in sources]
        if not pairs:
            return skipped(name, "single-source")
        names = {source: assignment_compare.net_names(design) for source, (_, design, _) in sources.items()}
        found: list[Issue] = []
        results: list[dict[str, object]] = []
        compared: set[str] = set()
        for a, b in pairs:
            pair = assignment_compare.compare(sources[a][0], sources[b][0], min_pins=1)
            found += assignment_compare.pair_issues(pair, names)
            results.append(assignment_compare.pair_summary(pair))
            compared |= {a, b}
        evidence = with_added(name, *(sources[source][2] for source in sorted(compared)))
        return ran(name, found, evidence, {"pairs": results, "min_pins": 1, "unnumbered": unnumbered})

    def container(name: str) -> Callable[[], StageResult]:
        level = CONTAINER_LEVELS[name]

        def run() -> StageResult:
            verdicts: dict[str, ContainerRoundTrip | None] = {}
            for document in documents.documents:
                try:
                    verdicts[document.name] = validator.container_roundtrip(
                        documents.root / document.name, level
                    )
                except FormatError as error:
                    errors.setdefault(document.name, error)
                    verdicts[document.name] = None
            return container_stage(name, level, verdicts)

        return run

    def rta2() -> StageResult:
        name = "roundtrip.rta2"
        if not built:
            return skipped(name, "native-input")
        if usable is None:
            return skipped(name, "cache-unreadable")
        if schematic is None and pcb is None:
            return skipped(name, "read-refused" if errors else "not-judged")
        stage = rta2_stage(
            usable, read if read is not None else ProjectRead(None, None), validator.written_scope()
        )
        readings = [reading.evidence for reading in (schematic, pcb) if reading is not None]
        return replace(stage, evidence=with_added(name, BUILT_EVIDENCE, *readings))

    runners: dict[str, Callable[[], StageResult]] = {
        "model.validate": model_stage,
        "erc.lite": erc,
        "copper.clearance": copper,
        "parity": parity,
        "netlist.assignment_compare": assignment,
        "roundtrip.rta0": container("roundtrip.rta0"),
        "roundtrip.rta1": container("roundtrip.rta1"),
        "roundtrip.rta2": rta2,
    }
    results = tuple(runners[name]() for name in selected)
    input_issues = [refused(name, error) for name, error in errors.items()]
    input_issues += [
        issue(
            "check.document-missing",
            "the project file lists this document, and it does not exist",
            where=name,
        )
        for name in documents.missing
    ]
    if cache_error:
        input_issues.append(issue("check.cache-unreadable", f".fenolite/ cannot be loaded: {cache_error}"))
    input_issues.sort(key=lambda found: (found.code, found.where))
    counted = [r.evidence for r in results if r.status != "skipped" or r.reason in _COUNTED_SKIPS]
    evidence = Evidence.combine(*counted) if counted else Evidence()
    only = documents.documents[0].name if len(documents.documents) == 1 else None
    read_error = errors.get(only) if only is not None else None
    issues = (*input_issues, *(found for result in results for found in result.issues))
    return CheckReport(results, issues, evidence, read_error)


__all__ = [
    "CONTAINER_LEVELS",
    "DOCUMENT_STAGES",
    "document_copper",
    "project_of",
    "refused",
    "run_document_checks",
    "unjudged_copper",
]

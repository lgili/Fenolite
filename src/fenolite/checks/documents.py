# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The check of an input that is a set of documents instead of one board (capability verification-loop,
"Document check pipeline"; change c0044).

A backend whose project is a set of documents (``DocumentValidator``) gives two independent readings, the
schematic side and the PCB side, and a container round trip per file. No oracle takes part: every stage
runs on what Fenolite reads. ``STAGE_ORDER`` and ``run_checks`` are not touched; the result types and the
stage helpers are shared with them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace

from fenolite.backends.base import (
    ContainerLevel,
    ContainerRoundTrip,
    DocumentRole,
    DocumentSet,
    DocumentValidator,
    PadNetList,
    ProjectRead,
    ReadResult,
)
from fenolite.checks import assignment_compare, erc_lite
from fenolite.checks.codes import issue
from fenolite.checks.containers import container_stage
from fenolite.checks.stages import CheckReport, StageResult, ran, skipped
from fenolite.checks.validate import BUILT_EVIDENCE
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence
from fenolite.model.design import Design

DOCUMENT_STAGES: tuple[str, ...] = (
    "model.validate",
    "erc.lite",
    "netlist.assignment_compare",
    "roundtrip.rta0",
    "roundtrip.rta1",
    "roundtrip.rta2",
)
"""The stages of a document check, in the order they run."""
CONTAINER_LEVELS: Mapping[str, ContainerLevel] = {"roundtrip.rta0": "RT-A0", "roundtrip.rta1": "RT-A1"}
_READING_STAGES = frozenset({"model.validate", "erc.lite", "netlist.assignment_compare", "roundtrip.rta2"})
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


__all__ = ["CONTAINER_LEVELS", "DOCUMENT_STAGES", "refused", "run_document_checks"]

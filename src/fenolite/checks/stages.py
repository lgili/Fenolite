# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``check`` pipeline: fixed stage order, statuses and evidence per stage (capability verification-loop,
"Check stages and statuses" and "Evidence per check stage").

``checks`` reaches a backend only through the injected ``Validator`` and ``Oracle`` of
``fenolite.backends.base``; facts come from them, and the issue codes and severities are decided here.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fenolite.backends.base import (
    BoardFrame,
    DesignRulesSource,
    FillOracle,
    Oracle,
    ParityInputs,
    Plotter,
    ProjectSet,
    Validation,
    Validator,
)
from fenolite.checks.codes import issue
from fenolite.core.errors import FenoliteError, FormatError, Issue
from fenolite.core.evidence import Evidence
from fenolite.model.design import Design

STAGE_ORDER: tuple[str, ...] = (
    "model.validate",
    "erc.kicad",
    "copper.clearance",
    "zone.fill",
    "drc.kicad",
    "parity",
    "netlist.assignment_compare",
    "roundtrip",
    "roundtrip.rt2",
    "render",
)
"""The order stages run in; a later change may insert a stage. ``copper.clearance`` (change c0029) needs no
external tool, so it runs before KiCad's DRC and is not an oracle stage. ``erc.kicad`` (change c0062) stands
where ``erc.lite`` stood: the three rules of ``checks.erc_lite`` are no stage of this pipeline any more.
``parity`` (change c0072) runs after ``drc.kicad`` because it compares its findings with KiCad's parity
entries when that stage judged them; it needs no tool itself, so it is not an oracle stage."""
OPT_IN_STAGES: tuple[str, ...] = ("roundtrip.rt2", "render")
"""Stages that run only when ``--stages`` names them: RT2 costs two re-saves and three DRC runs."""
DEFAULT_STAGES: tuple[str, ...] = tuple(name for name in STAGE_ORDER if name not in OPT_IN_STAGES)
ORACLE_STAGES: tuple[str, ...] = (
    "erc.kicad",
    "zone.fill",
    "drc.kicad",
    "netlist.assignment_compare",
    "roundtrip.rt2",
    "render",
)
"""Stages that need the external tool; selecting one runs the pre-flight and builds the oracle."""
_READING_STAGES = frozenset(
    {"roundtrip", "copper.clearance", "parity", *ORACLE_STAGES} - {"render", "erc.kicad"}
)
"""Stages that need the board read; ``erc.kicad`` needs only the schematic, and ``render`` only the files."""
StageStatus = Literal["ok", "errors", "skipped"]
StageSkip = Literal[
    "native-input",
    "read-refused",
    "cache-unreadable",
    "unsupported-oracle",
    "oracle-unsupported",
    "oracle-unstable",
    "no-schematic",
    "single-source",
    "not-judged",
    "netlist-unavailable",
    "model-predates-board",
    "no-document",
]
_COUNTED_SKIPS = frozenset({"read-refused", "cache-unreadable"})


def _sorted(issues: Iterable[Issue]) -> tuple[Issue, ...]:
    return tuple(sorted(issues, key=lambda i: (i.code, i.where, i.message)))


@dataclass(frozen=True, slots=True)
class StageResult:
    """One stage: its status, its own evidence, its issues (sorted) and its summary."""

    name: str
    status: StageStatus
    evidence: Evidence
    issues: tuple[Issue, ...] = ()
    summary: Mapping[str, object] = field(default_factory=lambda: {})
    reason: str = ""

    def to_json(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "reason": self.reason,
            "evidence": {
                "level": self.evidence.level.value,
                "oracle": self.evidence.oracle,
                "hypotheses": list(self.evidence.hypotheses),
            },
            "summary": dict(self.summary),
        }


def ran(name: str, issues: Iterable[Issue], evidence: Evidence, summary: Mapping[str, object]) -> StageResult:
    """A stage that ran: ``errors`` with any error issue, else ``ok``."""
    found = _sorted(issues)
    status: StageStatus = "errors" if any(i.severity == "error" for i in found) else "ok"
    return StageResult(name, status, evidence, found, dict(summary))


def skipped(name: str, reason: StageSkip) -> StageResult:
    return StageResult(name, "skipped", Evidence(), reason=reason)


@dataclass(frozen=True, slots=True)
class CheckReport:
    """The stages that were selected, every issue (input issues first), and the envelope evidence."""

    stages: tuple[StageResult, ...]
    issues: tuple[Issue, ...]
    evidence: Evidence
    read_error: FenoliteError | None = None
    drc_reported: bool = False


def relative_file(file: str, root: Path) -> str:
    """``file`` relative to ``root`` (POSIX) when it lies under it, else as given."""
    if not file:
        return file
    try:
        return Path(file).resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return file


def read_refused(error: FormatError, root: Path) -> Issue:
    """``check.read-refused`` for a board read error: the message starts with the error's FEN code, and
    ``where`` is ``file:locator:@offset`` with the file relative to ``root``."""
    code = getattr(type(error), "cli_code", "FEN-3004")
    parts = (
        relative_file(error.file, root),
        error.locator,
        "" if error.offset is None else f"@{error.offset}",
    )
    return issue("check.read-refused", f"{code}: {error.message}", where=":".join(p for p in parts if p))


def run_checks(
    *,
    project: ProjectSet,
    stages: Sequence[str] | None = None,
    model: Design | None,
    built: bool,
    validator: Validator | None,
    oracle: Oracle | None,
    cache_error: str = "",
    plotter: Plotter | None = None,
    fill_oracle: FillOracle | None = None,
) -> CheckReport:
    """Run the selected stages in ``STAGE_ORDER`` on ``project`` (``model`` is the ``.fenolite/`` model of a
    built project); ``validator.validate`` runs at most once."""
    from fenolite.checks.assignment_compare import assignment_stage
    from fenolite.checks.copper import copper_stage
    from fenolite.checks.drc import drc_stage
    from fenolite.checks.erc import erc_stage
    from fenolite.checks.fill import fill_stage
    from fenolite.checks.parity_stage import parity_stage
    from fenolite.checks.render import render_stage
    from fenolite.checks.roundtrip import roundtrip_stage
    from fenolite.checks.rt2 import rt2_stage
    from fenolite.checks.validate import BUILT_EVIDENCE, validate_stage

    wanted = DEFAULT_STAGES if stages is None else stages
    selected = [name for name in STAGE_ORDER if name in wanted]
    input_issues: list[Issue] = []
    validation: Validation | None = None
    read_error: FormatError | None = None
    reads = bool(_READING_STAGES & set(selected)) or ("model.validate" in selected and not built)
    if validator is not None and reads:
        try:
            validation = validator.validate(project.root / project.board)
        except FormatError as error:
            read_error = error
            input_issues.append(read_refused(error, project.root))
    if cache_error:
        input_issues.append(issue("check.cache-unreadable", f".fenolite/ cannot be loaded: {cache_error}"))

    def model_stage() -> StageResult:
        if built:
            if cache_error or model is None:
                return skipped("model.validate", "cache-unreadable")
            return validate_stage(model, built=True, evidence=BUILT_EVIDENCE)
        if validation is None:
            return skipped("model.validate", "read-refused")
        return validate_stage(validation.read.design, built=False, evidence=validation.read.evidence)

    def erc() -> StageResult:
        if oracle is None:
            raise ValueError("erc.kicad is selected but no oracle was given")
        return erc_stage(oracle, project)

    def copper() -> StageResult:
        if validation is None:
            return skipped("copper.clearance", "read-refused")
        return copper_stage(
            validation.read.design,
            project=project,
            rules_source=validator if isinstance(validator, DesignRulesSource) else None,
            frame=validator if isinstance(validator, BoardFrame) else None,
            evidence=validation.read.evidence,
        )

    def drc() -> StageResult:
        if oracle is None:
            raise ValueError("drc.kicad is selected but no oracle was given")
        design = validation.read.design if validation is not None else None
        return drc_stage(oracle, project, built=built, design=design)

    done: dict[str, StageResult] = {}

    def parity() -> StageResult:
        if validation is None:
            return skipped("parity", "read-refused")
        return parity_stage(
            validator if isinstance(validator, ParityInputs) else None,
            oracle,
            project,
            validation.read.design,
            drc=done.get("drc.kicad"),
        )

    def fill() -> StageResult:
        if validation is None:
            return skipped("zone.fill", "read-refused")
        if fill_oracle is None:
            raise ValueError("zone.fill is selected but no fill oracle was given")
        return fill_stage(fill_oracle, project, validation.read.design)

    def assignment() -> StageResult:
        usable = None if cache_error else model
        return assignment_stage(oracle, project, validation=validation, model=usable, built=built)

    def roundtrip() -> StageResult:
        return skipped("roundtrip", "read-refused") if validation is None else roundtrip_stage(validation)

    def rt2() -> StageResult:
        return skipped("roundtrip.rt2", "read-refused") if validation is None else rt2_stage(oracle, project)

    def render() -> StageResult:
        if plotter is None:
            raise ValueError("render is selected but no plotter was given")
        return skipped("render", "read-refused") if read_error is not None else render_stage(plotter, project)

    runners: dict[str, Callable[[], StageResult]] = {
        "model.validate": model_stage,
        "erc.kicad": erc,
        "copper.clearance": copper,
        "zone.fill": fill,
        "drc.kicad": drc,
        "parity": parity,
        "netlist.assignment_compare": assignment,
        "roundtrip": roundtrip,
        "roundtrip.rt2": rt2,
        "render": render,
    }
    for name in selected:
        done[name] = runners[name]()
    results = tuple(done[name] for name in selected)
    counted = [r.evidence for r in results if r.status != "skipped" or r.reason in _COUNTED_SKIPS]
    evidence = Evidence.combine(*counted) if counted else Evidence()
    drc_reported = any(
        r.name == "drc.kicad" and not any(i.code == "check.oracle-failed" for i in r.issues) for r in results
    )
    issues = (*input_issues, *(i for r in results for i in r.issues))
    return CheckReport(results, issues, evidence, read_error, drc_reported)


__all__ = [
    "DEFAULT_STAGES",
    "OPT_IN_STAGES",
    "ORACLE_STAGES",
    "STAGE_ORDER",
    "CheckReport",
    "StageResult",
    "StageSkip",
    "StageStatus",
    "ran",
    "read_refused",
    "relative_file",
    "run_checks",
    "skipped",
]

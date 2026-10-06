# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``erc.kicad`` stage (capability verification-loop, "ERC stage").

The electrical rules check of the project's schematic runs once through the injected ``ErcOracle``, on
built and on native input alike: it needs the schematic of the board's stem and no board model. Every
violation of the report becomes a located issue (``checks.erc_json``). A project without that schematic
skips the stage, and so does an oracle that cannot run an ERC; a schematic the tool cannot load is an
error of the stage, never a silent pass.
"""

from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath

from fenolite.backends.base import ErcOracle, ErcOutcome, Oracle, ProjectSet
from fenolite.checks.codes import issue
from fenolite.checks.erc_json import finding_issues, finding_types
from fenolite.checks.stages import StageResult, ran, skipped
from fenolite.core.evidence import Evidence

STAGE = "erc.kicad"
SCHEMATIC_SUFFIX = ".kicad_sch"


def schematic_of(project: ProjectSet) -> str | None:
    """The schematic of the board's stem in the copy set, or ``None`` when the set holds none."""
    name = f"{PurePosixPath(project.board).stem}{SCHEMATIC_SUFFIX}"
    return name if name in project.files else None


def _summary(outcome: ErcOutcome, oracle: str) -> dict[str, object]:
    report = outcome.report
    violations = report.violations if report is not None else ()
    return {
        "tool_version": outcome.tool_version,
        "sheets": len(report.sheets) if report is not None else 0,
        "violations": len(violations),
        "by_type": dict(sorted(Counter(v.type for v in violations).items())),
        "by_severity": dict(sorted(Counter(v.severity for v in violations).items())),
        "excluded": sum(1 for v in violations if v.excluded),
        "ignored_checks": sorted(report.ignored_checks) if report is not None else [],
        "types": finding_types(report, oracle=oracle) if report is not None else {},
        "tool_writes": sorted(outcome.tool_writes),
    }


def erc_stage(oracle: Oracle | ErcOracle, project: ProjectSet) -> StageResult:
    """One ERC run of the schematic of ``project``: its findings, its counts and the oracle's evidence."""
    schematic = schematic_of(project)
    if schematic is None:
        return skipped(STAGE, "no-schematic")
    if not isinstance(oracle, ErcOracle):
        return skipped(STAGE, "unsupported-oracle")
    outcome = oracle.erc(project)
    if outcome.report is None:
        what = "timed out" if outcome.outcome == "timeout" else "wrote no ERC report"
        detail = f": {outcome.message}" if outcome.message else ""
        failed = issue("check.oracle-failed", f"{oracle.name} {what}{detail}", where=schematic,
                       retryable=outcome.outcome == "timeout")  # fmt: skip
        return ran(STAGE, [failed], Evidence(), _summary(outcome, oracle.name))
    issues = finding_issues(outcome.report, oracle=oracle.name)
    return ran(STAGE, issues, outcome.evidence, _summary(outcome, oracle.name))


__all__ = ["STAGE", "erc_stage", "schematic_of"]

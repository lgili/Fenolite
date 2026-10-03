# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``drc.kicad`` stage (capability verification-loop, "DRC stage and the rules canary").

DRC runs once through the injected ``Oracle``. Its violations are counted, and whenever a report exists
each one becomes a located issue (``checks.drc_json``; ``violations_judged`` is then true). The oracle's
canary state becomes the rules verdict: a project whose rules were not loaded, or could not be checked, is
never a silent pass.
"""

from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath

from fenolite.backends.base import DrcOutcome, Oracle, ProjectSet
from fenolite.checks.codes import issue, oracle_code
from fenolite.checks.drc_json import finding_issues, finding_types
from fenolite.checks.stages import StageResult, ran
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.model.design import Design


def _summary(outcome: DrcOutcome, oracle: str) -> dict[str, object]:
    report = outcome.report
    violations = report.violations if report is not None else ()
    unconnected = report.unconnected_items if report is not None else ()
    return {
        "tool_version": outcome.tool_version,
        "canary": outcome.canary,
        "canary_reason": outcome.canary_reason,
        "canary_removed": outcome.canary_removed,
        "violations": len(violations),
        "by_type": dict(sorted(Counter(v.type for v in violations).items())),
        "by_severity": dict(sorted(Counter(v.severity for v in violations).items())),
        "unconnected": len(unconnected),
        "excluded": sum(1 for v in (*violations, *unconnected) if v.excluded),
        "tool_writes": sorted(outcome.tool_writes),
        "violations_judged": report is not None,
        "types": finding_types(report, oracle=oracle) if report is not None else {},
    }


def drc_stage(
    oracle: Oracle, project: ProjectSet, *, built: bool, design: Design | None = None
) -> StageResult:
    """One DRC run of ``project``: the copy skips, the rules verdict, the counts and the findings, located
    through ``design`` (the board model that ``run_checks`` read, or ``None`` when that read was refused)."""
    outcome = oracle.drc(project)
    issues: list[Issue] = [
        issue("check.copy-skipped", f"{s.name} was not copied for the DRC run ({s.reason})", where=s.name)
        for s in project.skipped
    ]
    if outcome.report is None:
        what = "timed out" if outcome.outcome == "timeout" else "wrote no DRC report"
        detail = f": {outcome.message}" if outcome.message else ""
        issues.append(issue("check.oracle-failed", f"{oracle.name} {what}{detail}", where=project.board,
                            retryable=outcome.outcome == "timeout"))  # fmt: skip
    rules = f"{PurePosixPath(project.board).stem}.kicad_dru"
    rules_alone = project.has_rules and not project.has_project
    rules_issue = False
    if outcome.canary == "absent" or (outcome.canary == "not-applicable" and rules_alone):
        why = "no project file next to the board" if rules_alone else "the canary rule did not fire"
        issues.append(issue(oracle_code(oracle.name, "rules-not-loaded"), f"the rules were not loaded: {why}",
                            severity="error" if built else "info", where=rules))  # fmt: skip
        rules_issue = True
    elif outcome.canary == "inconclusive" and outcome.canary_reason != "no-report":
        issues.append(issue(oracle_code(oracle.name, "rules-unchecked"),
                            f"whether the rules were loaded is unknown ({outcome.canary_reason})",
                            where=rules))  # fmt: skip
        rules_issue = True
    if outcome.report is not None:
        issues += finding_issues(outcome.report, oracle=oracle.name, design=design)
    evidence = outcome.evidence if outcome.report is not None and not rules_issue else Evidence()
    return ran("drc.kicad", issues, evidence, _summary(outcome, oracle.name))


__all__ = ["drc_stage"]

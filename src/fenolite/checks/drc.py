# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``drc.kicad`` stage (capability verification-loop, "DRC stage and the rules canary").

DRC runs once through the injected ``Oracle``. Its violations are counted, and whenever a report exists
each one becomes a located issue (``checks.drc_json``; ``violations_judged`` is then true). The oracle's
canary state becomes the rules verdict: a project whose rules were not loaded, or could not be checked, is
never a silent pass.

When the project has a schematic of the board's stem, the oracle also asks the tool to compare the board
with it ("Parity findings", change c0062). Its entries are findings like the others, and ``parity_judged``
says whether the comparison was made: when it was asked for and not made, the stage says so with
``<oracle>.drc.parity-unchecked`` and keeps the copper verdict and its evidence.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from pathlib import PurePosixPath

from fenolite.backends.base import (
    UNCONNECTED_ITEMS,
    DrcLimits,
    DrcOutcome,
    LimitedOracle,
    Oracle,
    ProjectSet,
)
from fenolite.checks.codes import issue, oracle_code
from fenolite.checks.drc_json import finding_issues, finding_types, type_code
from fenolite.checks.stages import StageResult, ran
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.model.design import Design


def _stated_limits(oracle: Oracle) -> DrcLimits | None:
    """The limits ``oracle`` states for its report; ``None`` when it states none (it does not satisfy
    ``LimitedOracle``, or its tool is a version nobody measured)."""
    if not isinstance(oracle, LimitedOracle):
        return None
    try:
        return oracle.report_limits()
    except ValueError:
        return None


def _limits(outcome: DrcOutcome, oracle: Oracle) -> list[dict[str, object]] | None:
    """``summary.limits`` ("DRC report limits in check"): one ``{type, reported, limit}``, sorted by type,
    for each violation type and for the unconnected items whose count in the counted report reached the
    limit the oracle states. ``[]`` says every count is complete, ``None`` that nothing is known."""
    report = outcome.report
    if report is None:
        return None
    limits = _stated_limits(oracle)
    if limits is None:
        return None
    counts = dict(Counter(v.type for v in report.violations))
    counts.pop(UNCONNECTED_ITEMS, None)  # the key stands for the report's own list of unconnected items
    if report.unconnected_items:
        counts[UNCONNECTED_ITEMS] = len(report.unconnected_items)
    return [
        {"type": type_, "reported": count, "limit": limits.limit(type_)}
        for type_, count in sorted(counts.items())
        if count >= limits.limit(type_)
    ]


def _limit_issues(limits: list[dict[str, object]] | None, oracle: str) -> list[Issue]:
    """One ``check.report-limit`` warning per entry of ``summary.limits``, sorted by ``where``."""
    found = [
        issue(
            "check.report-limit",
            f"the DRC report of {oracle} holds {entry['reported']} entries of {entry['type']} and the tool"
            f" stops writing them at {entry['limit']}: the board holds at least {entry['reported']}",
            where=type_code(oracle, str(entry["type"])),
            hint="the other findings of this type are not in the report; repair the reported ones and"
            " check again to see the next ones",
        )
        for entry in limits or ()
    ]
    return sorted(found, key=lambda i: (i.where, i.message))


def _summary(outcome: DrcOutcome, oracle: str) -> dict[str, object]:
    report = outcome.report
    violations = report.violations if report is not None else ()
    unconnected = report.unconnected_items if report is not None else ()
    parity = report.schematic_parity if report is not None else ()
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
        "parity": len(parity),
        "parity_judged": outcome.parity_judged and report is not None,
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
    schematic = f"{PurePosixPath(project.board).stem}.kicad_sch"
    if schematic in project.files and outcome.report is not None and not outcome.parity_judged:
        detail = f": {outcome.message}" if outcome.message else ""
        issues.append(
            issue(
                oracle_code(oracle.name, "parity-unchecked"),
                f"the board was not compared with its schematic{detail}",
                where=schematic,
            )
        )
    if outcome.report is not None:
        issues += finding_issues(outcome.report, oracle=oracle.name, design=design)
    evidence = outcome.evidence if outcome.report is not None and not rules_issue else Evidence()
    limits = _limits(outcome, oracle)
    result = ran("drc.kicad", issues, evidence, {**_summary(outcome, oracle.name), "limits": limits})
    # the marks describe the report, not the board: they follow the findings and decide no status
    return dataclasses.replace(result, issues=result.issues + tuple(_limit_issues(limits, oracle.name)))


__all__ = ["drc_stage"]

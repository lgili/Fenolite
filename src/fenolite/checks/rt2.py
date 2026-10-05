# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``roundtrip.rt2`` stage (capability verification-loop, "RT2 stage").

RT2 holds when the tool's DRC gives the same violations for a board and for the backend's re-dump of it.
The oracle produces the reports (runs on the original and on the re-dump); this module only judges them.
Violations are keyed without item uuids, because a re-save drops or replaces some.

A tool may not repeat its own report: on boards with hundreds of violations, two DRC runs of one file can
name other items or give another count (``H-K-RT2-STABLE-2``). A key whose count differs between the runs of
one side is therefore unstable: it is left out of both sides and counted. A difference between the
original and the re-dump is a failure only when no key is unstable, that is when every run of each side
gave the same report. Otherwise the difference cannot be told from the tool's own spread, and RT2 is not
judged: the stage says so and carries no evidence, it neither passes nor fails on noise.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from fenolite.backends.base import (
    DrcReport,
    DrcViolation,
    ErcReport,
    ErcRt2Outcome,
    Oracle,
    ProjectSet,
    RoundTripOracle,
    Rt2Outcome,
)
from fenolite.checks.codes import issue
from fenolite.checks.drc_json import format_position, sanitise
from fenolite.checks.stages import StageResult, ran, skipped
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence

Rt2Key = tuple[str, str, str, bool, tuple[tuple[str, Point], ...]]
GROUPS = ("violations", "unconnected_items")


def violation_key(group: str, violation: DrcViolation, *, source: str) -> Rt2Key:
    """``(group, type, severity, excluded, items)``: the items as the sorted descriptions and positions,
    uuids left out, and the run's temporary folder as ``<tmp>``."""
    items = sorted(
        ((sanitise(i.description, source=source), i.position) for i in violation.items),
        key=lambda item: (item[0], item[1].x, item[1].y),
    )
    return group, violation.type, violation.severity, violation.excluded, tuple(items)


def _keys(report: DrcReport) -> Counter[Rt2Key]:
    return Counter(
        violation_key(group, violation, source=report.source)
        for group in GROUPS
        for violation in getattr(report, group)
    )


@dataclass(frozen=True, slots=True)
class Rt2Difference:
    """A key whose counts differ between the original and the re-dump."""

    type: str
    severity: str
    before: int
    after: int
    where: str


@dataclass(frozen=True, slots=True)
class Rt2Verdict:
    """``holds``: no stable key differs. ``judged``: the verdict stands, which a difference does only when
    no key is unstable. ``unstable``: the keys that differ between runs of one side."""

    holds: bool
    unstable: int
    differences: tuple[Rt2Difference, ...]
    judged: bool = True


def _unstable(runs: list[Counter[Rt2Key]]) -> set[Rt2Key]:
    keys: set[Rt2Key] = set()
    for run in runs:
        keys |= run.keys()
    return {key for key in keys if len({run[key] for run in runs}) > 1}


def compare_runs(outcome: Rt2Outcome) -> Rt2Verdict | None:
    """The verdict of an RT2 run, or ``None`` with fewer than two original reports or no re-dump report."""
    if len(outcome.before) < 2 or outcome.after is None:
        return None
    originals = [_keys(report) for report in outcome.before]
    redumps = [_keys(report) for report in (outcome.after, *outcome.repeats)]
    unstable = _unstable(originals) | _unstable(redumps)
    first, after = originals[0], redumps[0]
    differences: list[Rt2Difference] = []
    for key in sorted((first.keys() | after.keys()) - unstable, key=_order):
        if first[key] != after[key]:
            items = key[4]
            where = format_position(items[0][1]) if items else ""
            differences.append(Rt2Difference(key[1], key[2], first[key], after[key], where))
    return Rt2Verdict(not differences, len(unstable), tuple(differences), not differences or not unstable)


def _order(key: Rt2Key) -> tuple[object, ...]:
    return key[0], key[1], key[2], key[3], tuple((d, p.x, p.y) for d, p in key[4])


def _counts(report: DrcReport | None) -> dict[str, int]:
    if report is None:
        return {"violations": 0, "unconnected": 0}
    return {"violations": len(report.violations), "unconnected": len(report.unconnected_items)}


def rt2_stage(oracle: Oracle | None, project: ProjectSet) -> StageResult:
    """RT2 of the project's board through ``oracle.rt2``."""
    name = "roundtrip.rt2"
    if not isinstance(oracle, RoundTripOracle):
        return skipped(name, "unsupported-oracle")
    outcome = oracle.rt2(project)
    verdict = compare_runs(outcome)
    issues: list[Issue] = []
    if verdict is None:
        what = "timed out" if outcome.outcome == "timeout" else "wrote no DRC report for RT2"
        detail = f": {outcome.message}" if outcome.message else ""
        issues.append(issue("check.oracle-failed", f"{oracle.name} {what}{detail}", where=project.board,
                            retryable=outcome.outcome == "timeout"))  # fmt: skip
    elif verdict.judged:
        issues += [
            issue(
                "check.rt2-failed",
                f"{d.type} ({d.severity}): {d.before} in the original, {d.after} in the re-dump",
                where=d.where,
            )
            for d in verdict.differences
        ]
    if verdict is not None and verdict.unstable:
        left = f"{verdict.unstable} violation key(s) differ between DRC runs of one file and were left out"
        if not verdict.judged:
            left += (
                f"; {len(verdict.differences)} more differ between the original and the re-dump, which "
                f"cannot be told from that, so RT2 is not judged on this board"
            )
        issues.append(issue("check.rt2-unstable", left, where=project.board))
    judged = verdict is not None and verdict.judged
    summary = {
        "holds": verdict is not None and verdict.holds,
        "judged": judged,
        "normalised": outcome.normalised,
        "runs": {
            "original": len(outcome.before),
            "redump": len(outcome.repeats) + (outcome.after is not None),
        },
        "before": _counts(outcome.before[0] if outcome.before else None),
        "after": _counts(outcome.after),
        "unstable": 0 if verdict is None else verdict.unstable,
        "differences": 0 if verdict is None else len(verdict.differences),
    }
    return ran(name, issues, outcome.evidence if judged else Evidence(), summary)


# --- RT2 of a schematic, through the tool's ERC (c0066) ---------------------------------------------

# A tool's ERC does not repeat its report item by item: for one violation it can name another of the pins
# or labels involved in each run (``H-K-ERC-REPEAT-2``). What its runs share is ``ErcReport.kinds()``,
# the sheet, type, severity and exclusion of every violation, and that is what RT2 compares
# (``H-K-ERC-RT2-2``). Whether the items agreed too is kept as ``exact``, for information.


class ErcRoundTripOracle(Protocol):
    """An oracle that runs ERC twice on a project and once on the backend's re-dump of its sheets."""

    def rt2_erc(self, project: ProjectSet) -> ErcRt2Outcome: ...


@dataclass(frozen=True, slots=True)
class ErcRt2Verdict:
    """RT2 of a project's schematic. ``reported`` is false when the tool wrote no report (``message`` says
    why). ``judged`` is false when the ``kinds()`` of two runs on the project as it is differ: the tool
    does not repeat itself there, so nothing passes or fails. ``holds`` when the ``kinds()`` of the
    re-dump's report are those of the first report; ``difference`` describes a judged difference.
    ``exact`` says whether the three reports also have equal ``entries()``, items included: it is
    information and changes no verdict."""

    reported: bool
    judged: bool
    holds: bool
    exact: bool = False
    difference: str = ""
    violations: int = 0
    violations_redump: int = 0
    redumped: int = 0
    kept: int = 0
    message: str = ""
    retryable: bool = False
    evidence: Evidence = Evidence()


def _erc_difference(before: ErcReport, after: ErcReport) -> str:
    """The first kind of violation that the two reports hold in other numbers, as text."""
    ours, theirs = Counter(before.kinds()), Counter(after.kinds())
    for kind in sorted(set(ours) | set(theirs)):
        if ours[kind] != theirs[kind]:
            sheet, type_, severity, _ = kind
            return (
                f"{type_} ({severity}) on sheet {sheet}: {ours[kind]} in the original, "
                f"{theirs[kind]} in the re-dump"
            )
    return ""


def erc_rt2(oracle: ErcRoundTripOracle, project: ProjectSet) -> ErcRt2Verdict:
    """RT2 of the project's schematic: ``oracle.rt2_erc`` once, judged on ``ErcReport.kinds()``. It is
    judged when the two reports of the project as it is have equal kinds, and holds when the re-dump's
    kinds are those of the first report."""
    outcome = oracle.rt2_erc(project)
    if len(outcome.before) < 2 or outcome.after is None:
        return ErcRt2Verdict(
            False, False, False, redumped=outcome.redumped, kept=outcome.kept,
            message=outcome.message or "no ERC report", retryable=outcome.outcome == "timeout",
        )  # fmt: skip
    first, second, after = outcome.before[0], outcome.before[1], outcome.after
    judged = first.kinds() == second.kinds()
    holds = judged and after.kinds() == first.kinds()
    return ErcRt2Verdict(
        reported=True,
        judged=judged,
        holds=holds,
        exact=first.entries() == second.entries() == after.entries(),
        difference=_erc_difference(first, after) if judged and not holds else "",
        violations=len(first.violations),
        violations_redump=len(after.violations),
        redumped=outcome.redumped,
        kept=outcome.kept,
        evidence=outcome.evidence if judged and holds else Evidence(),
    )


__all__ = [
    "ErcRoundTripOracle",
    "ErcRt2Verdict",
    "erc_rt2",
    "Rt2Difference",
    "Rt2Key",
    "Rt2Verdict",
    "compare_runs",
    "rt2_stage",
    "violation_key",
]

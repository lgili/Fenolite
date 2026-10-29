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
from collections.abc import Sequence
from pathlib import PurePosixPath

from fenolite.backends.base import (
    NIL_UUID,
    UNCONNECTED_ITEMS,
    DrcLimits,
    DrcOutcome,
    DrcReport,
    LimitedOracle,
    Oracle,
    ProjectSet,
    StoredExclusion,
)
from fenolite.checks.codes import issue, oracle_code
from fenolite.checks.drc_json import (
    finding_entries,
    finding_types,
    format_position,
    item_locations,
    type_code,
)
from fenolite.checks.stages import StageResult, ran
from fenolite.checks.waivers import UNREPEATABLE_TYPES, Candidate, apply_waivers, drc_waivers, judge
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.model.design import Design
from fenolite.model.findings import Waiver

STALE = "check.exclusion-stale"


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


def _pair(uuids: Sequence[str]) -> tuple[str, str]:
    """The first two uuids in lower case, the nil uuid standing for a missing one."""
    padded = [*(uuid.lower() for uuid in uuids), NIL_UUID, NIL_UUID]
    return padded[0], padded[1]


def mirrored(exclusions: Sequence[StoredExclusion]) -> dict[int, int]:
    """``index → index of its mirror`` for each stored exclusion of two items whose key in the other item
    order, at the same type and position, is stored too: one accepted exception written in both orders
    ("DRC exclusions written", change c0209)."""
    keys: dict[tuple[str, int, int, tuple[str, str]], int] = {}
    for index, exclusion in enumerate(exclusions):
        at = exclusion.position
        keys.setdefault((exclusion.type, at.x, at.y, _pair(exclusion.uuids)), index)
    found: dict[int, int] = {}
    for index, exclusion in enumerate(exclusions):
        first, second = _pair(exclusion.uuids)
        if second == NIL_UUID or first == second:
            continue
        at = exclusion.position
        other = keys.get((exclusion.type, at.x, at.y, (second, first)))
        if other is not None and other != index:
            found[index] = other
    return found


def accepted_rows(
    exclusions: Sequence[StoredExclusion], report: DrcReport | None
) -> tuple[list[dict[str, object]], dict[int, str]]:
    """``summary.accepted``: one row per exclusion stored in both item orders (``mirrored``), in file order
    of its first key: ``type``, ``items`` (the two uuids of the first key), ``comment`` and ``state``.
    The state is ``live`` when the report marks an entry of that type and those two items, in either order,
    as excluded; else ``unjudged`` for one of ``UNREPEATABLE_TYPES`` or without a report, and ``stale``
    otherwise. Also returns the state of every key that belongs to such a row."""
    pairs = mirrored(exclusions)
    excluded: set[tuple[str, frozenset[str]]] = set()
    reported: set[tuple[str, frozenset[str]]] = set()
    if report is not None:
        for entry in (*report.violations, *report.unconnected_items, *report.schematic_parity):
            key = (entry.type, frozenset(_pair([item.uuid for item in entry.items])))
            reported.add(key)
            if entry.excluded:
                excluded.add(key)
    rows: list[dict[str, object]] = []
    states: dict[int, str] = {}
    for index, exclusion in enumerate(exclusions):
        other = pairs.get(index)
        if other is None or index in states:
            continue
        pair = _pair(exclusion.uuids)
        key = (exclusion.type, frozenset(pair))
        if key in excluded:
            state = "live"
        elif report is None or exclusion.type in UNREPEATABLE_TYPES:
            state = "unjudged"
        else:
            state = "stale"
        states[index] = states[other] = state
        rows.append(
            {
                "type": exclusion.type,
                "items": list(pair),
                "comment": exclusion.comment,
                "state": state,
                "reported": key in reported,
            }
        )
    return rows, states


def exclusion_issues(
    exclusions: Sequence[StoredExclusion], report: DrcReport | None, *, oracle: str, design: Design | None
) -> tuple[list[Issue], dict[str, int]]:
    """Whether the tool still applies each stored exclusion ("Exclusions in the DRC stage", change c0114).

    An exclusion is live when an entry of the report is ``excluded`` and has its type and its item uuids,
    in order. Otherwise it is stale and gives one ``check.exclusion-stale`` warning: ``moved`` when an
    entry of that type and those uuids is reported without ``excluded`` (the tool matches the marker
    position to the nanometre), ``gone`` when none is. An exclusion of one of ``UNREPEATABLE_TYPES`` is
    not judged, and without a report none is. Returns the issues and ``summary.exclusions``.

    The two keys of an exclusion stored in both item orders (``mirrored``; change c0209) are judged
    together, as ``accepted_rows`` says: both live, both unjudged, or both stale with one warning."""
    counts = {"stored": len(exclusions), "live": 0, "stale": 0, "unjudged": 0}
    if report is None:
        return [], counts
    entries = (*report.violations, *report.unconnected_items, *report.schematic_parity)
    reported: dict[tuple[str, tuple[str, str]], list[bool]] = {}
    for entry in entries:
        key = (entry.type, _pair([item.uuid for item in entry.items]))
        reported.setdefault(key, []).append(entry.excluded)
    locations = item_locations(design, oracle)
    _, states = accepted_rows(exclusions, report)
    pairs = mirrored(exclusions)
    issues: list[Issue] = []
    for index, exclusion in enumerate(exclusions):
        state = states.get(index)
        if state in ("live", "unjudged"):
            counts[state] += 1
            continue
        if state is None and exclusion.type in UNREPEATABLE_TYPES:
            counts["unjudged"] += 1
            continue
        pair = _pair(exclusion.uuids)
        found = reported.get((exclusion.type, pair))
        if state is None and found and any(found):
            counts["live"] += 1
            continue
        counts["stale"] += 1
        if state is not None:
            if pairs[index] < index:  # the pair's warning is given once, at its first key
                continue
            found = reported.get((exclusion.type, pair)) or reported.get((exclusion.type, (pair[1], pair[0])))
        reason = "moved" if found else "gone"
        names = [
            locations.get(uuid) or format_position(exclusion.position)
            for index, uuid in enumerate(pair)
            if index == 0 or uuid != NIL_UUID
        ]
        why = (
            "the entry is reported again, at another marker position"
            if found
            else "no entry of this type names these items any more"
        )
        comment = f"; its comment is {exclusion.comment!r}" if exclusion.comment else ""
        issues.append(
            issue(
                STALE,
                f"the stored exclusion of {exclusion.type} no longer applies ({reason}): {why}{comment}",
                where=", ".join(names),
                hint="remove the exclusion in the tool's DRC dialog, or exclude the entry again there",
            )
        )
    return issues, counts


def drc_stage(
    oracle: Oracle,
    project: ProjectSet,
    *,
    built: bool,
    design: Design | None = None,
    waivers: Sequence[Waiver] = (),
    exclusions: Sequence[StoredExclusion] = (),
) -> StageResult:
    """One DRC run of ``project``: the copy skips, the rules verdict, the counts and the findings, located
    through ``design`` (the board model that ``run_checks`` read, or ``None`` when that read was refused).

    ``waivers`` are the design's waivers and ``exclusions`` the exclusions the project's own files store
    (change c0114): a finding that a ``<oracle>.drc.*`` waiver accepts is kept as ``info``, a judged waiver
    that matched nothing gives ``check.waiver-unmatched``, and a stored exclusion that the tool no longer
    applies gives ``check.exclusion-stale``. Neither changes the evidence."""
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
    limits = _limits(outcome, oracle)
    summary: dict[str, object] = {**_summary(outcome, oracle.name), "limits": limits}
    own = drc_waivers(waivers, oracle.name)
    if outcome.report is not None:
        entries = finding_entries(outcome.report, oracle=oracle.name, design=design)
        marked, counts = apply_waivers(own, (Candidate(made, names) for made, names, _ in entries))
        issues += marked
        if own:
            unrepeatable = {type_code(oracle.name, name) for name in UNREPEATABLE_TYPES}
            verdict, stale = judge(own, counts, unrepeatable=unrepeatable)
            issues += stale
            summary["waivers"] = {key: value for key, value in verdict.to_json().items() if key != "declared"}
    stale_exclusions, summary["exclusions"] = exclusion_issues(
        exclusions, outcome.report, oracle=oracle.name, design=design
    )
    summary["accepted"] = accepted_rows(exclusions, outcome.report)[0]
    issues += stale_exclusions
    evidence = outcome.evidence if outcome.report is not None and not rules_issue else Evidence()
    result = ran("drc.kicad", issues, evidence, summary)
    # the marks describe the report, not the board: they follow the findings and decide no status
    return dataclasses.replace(result, issues=result.issues + tuple(_limit_issues(limits, oracle.name)))


__all__ = ["STALE", "accepted_rows", "drc_stage", "exclusion_issues", "mirrored"]

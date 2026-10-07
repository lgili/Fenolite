# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Waivers: one accepted finding stays listed and no longer counts as an error (capability
verification-loop, "Waivers in the check"; change c0114).

A waiver (``model.findings.Waiver``) names one finding by its code and by the names of its items, as
``where`` prints them, with a reason. ``apply_waivers`` marks the findings a waiver matches: the issue keeps
its code and ``where``, takes severity ``info`` and ends with `` (waived by <name>: <reason>)``. Nothing is
removed. ``judge`` then says, for the waivers of one stage, which matched, which matched nothing (stale:
``check.waiver-unmatched``) and which were not judged.

A waiver is Fenolite's own: it is applied by the copper stage, the DRC stage and the build's copper guards,
on any backend, and it is never written into a tool's files.
"""

from __future__ import annotations

import dataclasses
import fnmatch
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from itertools import permutations

from fenolite.checks.codes import issue
from fenolite.core.errors import Issue
from fenolite.core.units import Nm
from fenolite.model.findings import Waiver

UNREPEATABLE_TYPES: tuple[str, ...] = ("clearance", "hole_clearance", "unconnected_items", "shorting_items")
"""The DRC types whose entries KiCad does not repeat from run to run (``H-K-DRC-REPEAT``,
``H-K-VIA-RENET``): a waiver or a stored exclusion of one of them is applied and never judged stale."""
COPPER_CODES: tuple[str, ...] = ("copper.short", "copper.clearance", "copper.zone-overlap")
"""The finding codes of the copper check: the codes a copper waiver can name."""
STAGE_NOT_RUN = "stage-not-run"
NOT_REPEATABLE = "not-repeatable"
UNMATCHED = "check.waiver-unmatched"


@dataclass(frozen=True, slots=True)
class Candidate:
    """One finding a waiver can match: its issue, the names of its items and, for a clearance finding,
    its gap in nanometres."""

    issue: Issue
    names: tuple[str, ...]
    gap: Nm | None = None


@dataclass(frozen=True, slots=True)
class WaiverOutcome:
    """What became of a set of waivers: ``matched`` (name → findings matched, for judged waivers),
    ``unmatched`` (the names of judged waivers that matched nothing) and ``unjudged`` (name →
    ``stage-not-run`` or ``not-repeatable``), each in name order."""

    declared: int = 0
    matched: Mapping[str, int] = field(default_factory=lambda: {})
    unmatched: tuple[str, ...] = ()
    unjudged: Mapping[str, str] = field(default_factory=lambda: {})

    def to_json(self) -> dict[str, object]:
        return {
            "declared": self.declared,
            "matched": dict(sorted(self.matched.items())),
            "unmatched": sorted(self.unmatched),
            "unjudged": dict(sorted(self.unjudged.items())),
        }


def waiver_matches(waiver: Waiver, code: str, names: Sequence[str], gap: Nm | None = None) -> bool:
    """Whether ``waiver`` accepts the finding of ``code`` whose items are named ``names``: the codes are
    equal, each item pattern matches one name, one to one and in any order (``fnmatch.fnmatchcase``, or the
    same text), and, when the waiver has a ``min_gap``, the finding's ``gap`` is known and at least that."""
    if code != waiver.code or len(names) != len(waiver.items):
        return False
    if waiver.min_gap is not None and (gap is None or gap < waiver.min_gap):
        return False
    return any(
        all(_names(pattern, name) for pattern, name in zip(order, names, strict=True))
        for order in permutations(waiver.items)
    )


def _names(pattern: str, name: str) -> bool:
    """Whether the item ``pattern`` names ``name``: as a glob, or letter for letter. The second case is for
    a locator such as ``/kicad_pcb/segment[12]``, whose brackets a glob reads as a set of characters."""
    return pattern == name or fnmatch.fnmatchcase(name, pattern)


def waived(found: Issue, waiver: Waiver) -> Issue:
    """``found`` as accepted by ``waiver``: severity ``info`` and the waiver's name and reason."""
    return dataclasses.replace(
        found, severity="info", message=f"{found.message} (waived by {waiver.name}: {waiver.reason})"
    )


def apply_waivers(
    waivers: Iterable[Waiver], candidates: Iterable[Candidate]
) -> tuple[tuple[Issue, ...], dict[str, int]]:
    """The issues of ``candidates`` in order, each marked by the first waiver in name order that matches
    it, and the number of findings that each waiver matched (waivers that matched nothing are absent)."""
    ordered = sorted(waivers, key=lambda waiver: waiver.name)
    counts: dict[str, int] = {}
    issues: list[Issue] = []
    for candidate in candidates:
        matching = [
            waiver
            for waiver in ordered
            if waiver_matches(waiver, candidate.issue.code, candidate.names, candidate.gap)
        ]
        for waiver in matching:
            counts[waiver.name] = counts.get(waiver.name, 0) + 1
        issues.append(waived(candidate.issue, matching[0]) if matching else candidate.issue)
    return tuple(issues), counts


def copper_waivers(waivers: Iterable[Waiver]) -> tuple[Waiver, ...]:
    """The waivers of a copper finding."""
    return tuple(waiver for waiver in waivers if waiver.code in COPPER_CODES)


def drc_waivers(waivers: Iterable[Waiver], oracle: str) -> tuple[Waiver, ...]:
    """The waivers of a DRC finding of ``oracle`` (``<oracle>.drc.<suffix>``)."""
    return tuple(waiver for waiver in waivers if waiver.code.startswith(f"{oracle}.drc."))


def unmatched_issue(waiver: Waiver) -> Issue:
    return issue(
        UNMATCHED,
        f"the waiver of {waiver.code} for {', '.join(waiver.items)} matched no finding: the finding is "
        "gone or its items were renamed",
        where=waiver.name,
        hint="remove the waiver from the script, or name the items as the finding's 'where' prints them",
    )


def judge(
    waivers: Iterable[Waiver], counts: Mapping[str, int], *, unrepeatable: Collection[str] = ()
) -> tuple[WaiverOutcome, tuple[Issue, ...]]:
    """The outcome of the waivers of one stage that ran with a verdict, and one ``check.waiver-unmatched``
    warning per judged waiver that matched nothing. A waiver whose code is in ``unrepeatable`` is never
    judged: it is listed as ``not-repeatable`` whether it matched or not."""
    matched: dict[str, int] = {}
    unmatched: list[str] = []
    unjudged: dict[str, str] = {}
    issues: list[Issue] = []
    ordered = sorted(waivers, key=lambda waiver: waiver.name)
    for waiver in ordered:
        if waiver.code in unrepeatable:
            unjudged[waiver.name] = NOT_REPEATABLE
        elif counts.get(waiver.name):
            matched[waiver.name] = counts[waiver.name]
        else:
            unmatched.append(waiver.name)
            issues.append(unmatched_issue(waiver))
    return WaiverOutcome(len(ordered), matched, tuple(unmatched), unjudged), tuple(issues)


def combine(waivers: Iterable[Waiver], stages: Iterable[object]) -> WaiverOutcome:
    """The outcome of every waiver of a run from the ``waivers`` entries of its stage summaries (each as
    ``WaiverOutcome.to_json`` gives it; anything else is skipped). A waiver that no stage listed is
    ``stage-not-run``: its stage was not selected, was skipped, or does not exist in this pipeline."""
    matched: dict[str, int] = {}
    unmatched: list[str] = []
    unjudged: dict[str, str] = {}
    for entry in stages:
        if not isinstance(entry, Mapping):
            continue
        found: Mapping[str, object] = entry  # pyright: ignore[reportUnknownVariableType]
        part_matched, part_unmatched, part_unjudged = (
            found.get("matched"),
            found.get("unmatched"),
            found.get("unjudged"),
        )
        if isinstance(part_matched, Mapping):
            matched.update({str(k): int(v) for k, v in part_matched.items()})  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
        if isinstance(part_unmatched, (list, tuple)):
            unmatched.extend(str(name) for name in part_unmatched)  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
        if isinstance(part_unjudged, Mapping):
            unjudged.update({str(k): str(v) for k, v in part_unjudged.items()})  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    names = [waiver.name for waiver in waivers]
    seen = set(matched) | set(unmatched) | set(unjudged)
    for name in names:
        if name not in seen:
            unjudged[name] = STAGE_NOT_RUN
    return WaiverOutcome(len(names), matched, tuple(sorted(unmatched)), unjudged)


__all__ = [
    "COPPER_CODES",
    "NOT_REPEATABLE",
    "STAGE_NOT_RUN",
    "UNMATCHED",
    "UNREPEATABLE_TYPES",
    "Candidate",
    "WaiverOutcome",
    "apply_waivers",
    "combine",
    "copper_waivers",
    "drc_waivers",
    "judge",
    "unmatched_issue",
    "waived",
    "waiver_matches",
]

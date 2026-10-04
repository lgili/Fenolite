# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What two ``KicadOracle.drc`` outcomes of one unchanged project must share (``H-K-DRC-REPEAT``;
capability kicad-oracle, "DRC repeatability on the demo boards"; change c0051).

KiCad does not repeat its DRC report on large boards. Measured over the demo boards
(``docs/evidence/kicad-check.md``): the report order changes, and on six boards so do entries of three
types. Everything else repeats, and ``repeat_problems`` holds two runs to that: the whole sorted report on
a board outside ``UNREPEATABLE_BOARDS``, every type outside ``UNREPEATABLE_TYPES`` on the others.

A board or a type joins a set only with a measurement of at least 15 runs per board recorded in
``docs/evidence/kicad-check.md`` and in the register row. Never widen a set to make a run pass.
"""

from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath

from fenolite.backends.base import DrcOutcome, DrcReport
from fenolite.backends.kicad.canary import CANARY_UUIDS, clearance_saturated

UNREPEATABLE_TYPES = frozenset({"clearance", "hole_clearance", "unconnected_items"})
"""The DRC types whose entries differ between two runs of one board (partner items, positions, counts)."""
UNREPEATABLE_BOARDS = frozenset(
    {
        "kicad-demo-10-0-6-pcb-01",
        "kicad-demo-10-0-6-pcb-07",
        "kicad-demo-10-0-6-pcb-09",
        "kicad-demo-10-0-6-pcb-11",
        "kicad-demo-10-0-6-pcb-13",
        "kicad-demo-10-0-6-pcb-16",
    }
)
"""The demo boards whose sorted report differs between two runs; on every other one it repeats whole."""
Entry = tuple[str, str, str, bool, tuple[tuple[str, int, int], ...]]


def canonical(report: DrcReport) -> tuple[Entry, ...]:
    """``report.entries()`` (sorted, without item uuids) with the run's temporary folder left out of the
    descriptions, so the report order and the folder of a run never count."""
    folder = str(PurePosixPath(report.source).parent)
    if folder in ("", ".", "/"):
        return report.entries()
    return tuple(
        (group, kind, severity, excluded, tuple((d.replace(folder, "<tmp>"), x, y) for d, x, y in items))
        for group, kind, severity, excluded, items in report.entries()
    )


def _own_problems(board_id: str, label: str, outcome: DrcOutcome) -> list[str]:
    report = outcome.report
    if report is None:
        return [f"{board_id}: {label} run has no report ({outcome.outcome}, {outcome.message})"]
    problems: list[str] = []
    if outcome.canary_removed != 0:
        problems.append(f"{board_id}: {label} run: canary_removed is {outcome.canary_removed}, not 0")
    groups = (*report.violations, *report.unconnected_items, *report.schematic_parity)
    if any(item.uuid in CANARY_UUIDS for entry in groups for item in entry.items):
        problems.append(f"{board_id}: {label} run: the counted report names a canary item")
    state = (outcome.canary, outcome.canary_reason)
    at_limit = state == ("inconclusive", "clearance-limit") and clearance_saturated(report)
    if state != ("fired", "") and not at_limit:
        problems.append(
            f"{board_id}: {label} run: canary is {outcome.canary!r} ({outcome.canary_reason!r}); it must be "
            "'fired', or 'inconclusive' ('clearance-limit') with a saturated report"
        )
    return problems


def repeat_problems(board_id: str, first: DrcOutcome, second: DrcOutcome) -> list[str]:
    """One line per rule that two outcomes of one board break; an empty list when they repeat as measured."""
    problems = _own_problems(board_id, "first", first) + _own_problems(board_id, "second", second)
    for field in ("outcome", "returncode", "tool_writes"):
        one, two = getattr(first, field), getattr(second, field)
        if one != two:
            problems.append(f"{board_id}: {field} differs: {one!r} and {two!r}")
    if first.report is None or second.report is None:
        return problems
    saturated = clearance_saturated(first.report) or clearance_saturated(second.report)
    one_state, two_state = (first.canary, first.canary_reason), (second.canary, second.canary_reason)
    if one_state != two_state and not saturated:
        problems.append(f"{board_id}: canary differs: {one_state!r} and {two_state!r}")
    one_entries, two_entries = Counter(canonical(first.report)), Counter(canonical(second.report))
    exempt = UNREPEATABLE_TYPES if board_id in UNREPEATABLE_BOARDS else frozenset[str]()
    for kind in sorted({entry[1] for entry in (*one_entries, *two_entries)} - exempt):
        mine = Counter({e: n for e, n in one_entries.items() if e[1] == kind})
        theirs = Counter({e: n for e, n in two_entries.items() if e[1] == kind})
        if mine != theirs:
            changed = sum(((mine - theirs) + (theirs - mine)).values())
            problems.append(
                f"{board_id}: {kind}: {sum(mine.values())} and {sum(theirs.values())} entries, "
                f"{changed} not in both runs"
            )
    return problems


__all__ = ["UNREPEATABLE_BOARDS", "UNREPEATABLE_TYPES", "canonical", "repeat_problems"]

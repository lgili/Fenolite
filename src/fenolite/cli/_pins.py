# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pin solve in ``fenolite build`` (change c0257; ``docs/pins.md``): the takes of the script
(``fenolite.dsl.take``) are solved against the ``[pins]`` entries of the design lock
(``fenolite.lens.pins.solve``), the choices are joined to the role nets before the design is lowered, and the
new entries replace the section in the planned lock.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.dsl import Design
from fenolite.dsl.lock import LockChange, LockValue, pin_choice_text
from fenolite.dsl.take import apply_choices, design_takes, solve_takes, unused_takes
from fenolite.dsl.take import requests as take_requests
from fenolite.lens.pins import PinSolution, TakeRequest, dropped_issues, issue

HYPOTHESIS = "H-G-PIN-SOLVE-DETERMINISTIC"


@dataclass(frozen=True)
class PinPlan:
    """The pin solve of one build: the new ``[pins]`` entries, their changes, ``result.pins``, the issues
    and the evidence of the choices (``None`` without takes)."""

    entries: Mapping[str, LockValue]
    changes: tuple[LockChange, ...]
    rows: list[dict[str, object]]
    issues: tuple[Issue, ...]
    evidence: Evidence | None


def requests(design: Design) -> list[TakeRequest]:
    """The takes of ``design`` as solve requests (``fenolite.dsl.take.requests``)."""
    return take_requests(design)


def solve_design(design: Design, locked: Mapping[str, LockValue]) -> PinSolution:
    """The solve of the takes of ``design`` against the ``[pins]`` entries ``locked``."""
    return solve_takes(design, locked)


def _changes(
    before: Mapping[str, LockValue], after: Mapping[str, LockValue], stale: Sequence[str]
) -> list[LockChange]:
    found: list[LockChange] = []
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        if old == new:
            continue
        reason = "stale" if key in stale else ("dropped" if new is None else "solved")
        found.append(
            LockChange(
                "pins",
                key,
                None if old is None or isinstance(old, str) else pin_choice_text(old),
                None if new is None or isinstance(new, str) else pin_choice_text(new),
                reason,
            )
        )
    return found


def plan_pins(design: Design, locked: Mapping[str, LockValue]) -> PinPlan:
    """Solve the takes of ``design`` against ``locked`` (the ``[pins]`` entries kept after carry and release),
    join the choices to the role nets, and give the new entries, their changes and the issues."""
    takes = design_takes(design)
    if not takes:
        apply_choices(design, {})
        entries: Mapping[str, LockValue] = MappingProxyType({})
        dropped = dropped_issues(locked, [])
        return PinPlan(entries, tuple(_changes(locked, entries, ())), [], tuple(dropped), None)
    solution = solve_design(design, locked)
    apply_choices(design, {choice.key: choice.pins for choice in solution.choices})
    entries = MappingProxyType(
        {choice.key: MappingProxyType(choice.lock_entry()) for choice in solution.choices}
    )
    unused = [
        issue(
            "pins.unused-take",
            f"take {key}: its nets reach no other pin; connect it, or remove the take",
            key,
        )
        for key in unused_takes(design)
    ]
    issues = (*solution.issues, *dropped_issues(locked, requests(design)), *unused)
    levels = [Evidence(Level.INFERRED, hypotheses=(HYPOTHESIS,))]
    if any(choice.evidence == "UNVERIFIED" for choice in solution.choices):
        levels.append(Evidence(Level.UNVERIFIED, hypotheses=(HYPOTHESIS,)))
    return PinPlan(
        entries=entries,
        changes=tuple(_changes(locked, entries, solution.stale)),
        rows=[choice.as_json() for choice in solution.choices],
        issues=issues,
        evidence=Evidence.combine(*levels),
    )


def apply_script_pins(design: Design, script: Path) -> None:
    """Join the choices of the takes of ``design`` as a build of ``script`` would, against the ``[pins]`` of
    the lock beside it (``<script stem>.lock``) when there is one: for commands that lower a script without
    building it (``sync``)."""
    if not design_takes(design):
        return
    from fenolite.dsl.lock import SUFFIX, read_lock

    lock = script.with_suffix(SUFFIX)
    locked: Mapping[str, LockValue] = {}
    if lock.is_file():
        locked = read_lock(lock.read_text(encoding="utf-8"), file=lock.name).sections["pins"]
    plan_pins(design, locked)


__all__ = ["HYPOTHESIS", "PinPlan", "apply_script_pins", "plan_pins", "requests", "solve_design"]

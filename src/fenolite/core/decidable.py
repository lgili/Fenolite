# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Decidable stages of requirement rows (change c0274; capability verification-loop, "Decidable stages of
requirement rows"; ``docs/contracts.md``, "Decidable stages").

Each row can be decided at one stage of the design: ``build`` for every ``circuit.*`` row (the model is
enough), ``place`` for the loop rows ``roles.loop-area`` and ``roles.gate-loop`` (pad positions), and
``route`` for every other judged ``roles.*`` row (copper widths, sections, vias, distances, returns). A
``place`` row is reached when every component of its subject has its pads inside the board outline; a
``route`` row when, in addition, no net of its subject has an open connection. A row whose stage is not
reached and that does not fail is ``deferred``, with no severity: nothing not reached is ever ``pass``, and
copper already too thin stays a ``fail``. The reach is measured by the caller (``roles.judge``), which reads
the board; this module holds the closed table and the rule only, in ``core`` so that both ``checks`` and
``roles`` read it.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace

from fenolite.core.requirement_table import STAGES, RequirementRow, Stage

PLACE_CHECKS: frozenset[str] = frozenset({"roles.loop-area", "roles.gate-loop"})
"""The role rows decided by pad positions."""


def stage_of(check: str) -> Stage:
    """The decidable stage of a row of ``check`` (the closed table of the module docstring)."""
    if check in PLACE_CHECKS:
        return "place"
    if check.startswith("roles."):
        return "route"
    return "build"


@dataclass(frozen=True, slots=True)
class Reach:
    """What a board has reached: the references of the components whose pads all lie inside the outline,
    and the nets that still have an open connection."""

    inside: frozenset[str] = frozenset()
    open: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class Subject:
    """The components (references) and nets a row judges."""

    refs: tuple[str, ...] = ()
    nets: tuple[str, ...] = ()


def reached(stage: Stage, subject: Subject, reach: Reach) -> bool:
    """Whether ``stage`` is reached for ``subject`` on a board of ``reach``."""
    if stage == "build":
        return True
    placed = bool(subject.refs) and all(ref in reach.inside for ref in subject.refs)
    if stage == "place":
        return placed
    return placed and not any(net in reach.open for net in subject.nets)


def decide(
    rows: Iterable[RequirementRow], subjects: Mapping[str, Subject], reach: Reach
) -> list[RequirementRow]:
    """``rows`` with their ``decidable`` stage, and ``deferred`` (no severity) for a row whose stage is not
    reached for its subject (``subjects``, by row id) and that does not fail."""
    found: list[RequirementRow] = []
    for row in rows:
        stage = stage_of(row.check)
        subject = subjects.get(row.id, Subject())
        if row.status != "fail" and not reached(stage, subject, reach):
            found.append(replace(row, decidable=stage, status="deferred", severity=None))
        else:
            found.append(replace(row, decidable=stage))
    return found


def deferred_counts(rows: Sequence[RequirementRow] | Collection[RequirementRow]) -> dict[str, int]:
    """``summary.deferred``: the deferred rows counted by their decidable stage, in stage order."""
    counts = {
        stage: sum(1 for r in rows if r.status == "deferred" and r.decidable == stage) for stage in STAGES
    }
    return {stage: count for stage, count in counts.items() if count}


__all__ = ["PLACE_CHECKS", "Reach", "Subject", "decide", "deferred_counts", "reached", "stage_of"]

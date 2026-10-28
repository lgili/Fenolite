# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What a tidy step returns: the edited design, one ``Edit`` per change with its reason, and the issues;
and the findings of a copper check that a step is judged by (capability copper-tidy)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.model.design import Design


@dataclass(frozen=True, slots=True)
class Edit:
    """One change of a step: the step (``prune`` or ``chamfer``), the reason, the net's name, the copper
    layer (empty for a via), a point of the change, and the ids of the removed, replaced and added
    items."""

    step: str
    reason: str
    net: str
    layer: str
    at: Point
    removed: tuple[str, ...] = ()
    replaced: tuple[str, ...] = ()
    added: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TidyResult:
    """The design after a step, its edits in order, and its issues (codes of ``tidy.codes``)."""

    design: Design
    edits: tuple[Edit, ...] = ()
    issues: tuple[Issue, ...] = ()


@dataclass(frozen=True, slots=True)
class Clash:
    """A finding of a copper check, as a tidy step compares them: the code, the layer, the sorted ids of
    the items it names and the gap in nanometres (0 for a short)."""

    code: str
    layer: str
    items: tuple[str, ...]
    gap: int


Check = Callable[[Design], Sequence[Clash]]
"""A copper check of a design: the CLI passes ``checks.copper.check_copper`` with the project's rules."""


def fresh_clashes(before: Iterable[Clash], after: Iterable[Clash]) -> tuple[Clash, ...]:
    """The clashes of ``after`` that ``before`` lacks: a new pair of items, or a smaller gap of a known
    pair."""
    known: dict[tuple[str, str, tuple[str, ...]], int] = {}
    for clash in before:
        key = (clash.code, clash.layer, clash.items)
        known[key] = min(clash.gap, known.get(key, clash.gap))
    out = [
        clash
        for clash in after
        if (key := (clash.code, clash.layer, clash.items)) not in known or clash.gap < known[key]
    ]
    return tuple(sorted(out, key=lambda clash: (clash.code, clash.layer, clash.items, clash.gap)))


__all__ = ["Check", "Clash", "Edit", "TidyResult", "fresh_clashes"]

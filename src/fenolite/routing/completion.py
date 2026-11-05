# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Truthful completion facts of a proposal run (change c0370; ``docs/routing.md``, "Completion").

``completion`` sorts every open subject of the board into exactly one state and states the board's physical
open count as read. It never calls a board complete: a proposal, a rejection, a timeout or an unknown
check is not a connection, and completion needs the fill and the checks that run after it
(``fenolite fill`` then ``fenolite check``). The board state is ``open`` while the board as read has an
open connection, else ``unchecked``.

Subject states, in precedence order:

- ``not-attempted``: outside the selection of ``--nets``, ``--kind`` or ``--group``;
- ``rejected``: the proposal, or every candidate of it, was rejected by a stored decision;
- ``no-candidate``: the router finished and found no candidate (the proposal's ``reason`` says why);
- ``unknown``: a bound (``--timeout``, cancellation, an explicit search or round limit) stopped the search
  before any candidate, or candidates exist but the budget ended before their facts were measured;
- ``proposed``: at least one candidate with measured facts waits for a reviewed decision.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Literal

State = Literal["not-attempted", "rejected", "no-candidate", "unknown", "proposed"]
STOPPED = frozenset({"budget", "cancelled", "state-limit", "negotiate-round-limit"})
"""The proposal reasons of a search stopped by a bound: no candidate is not a finding that none exists."""
STATES: tuple[State, ...] = ("proposed", "unknown", "no-candidate", "rejected", "not-attempted")
"""The order of the keys of ``subjects`` in the reply."""


@dataclass(frozen=True, slots=True)
class SubjectFacts:
    """What the proposal run knows of one open subject."""

    key: str
    selected: bool = True
    rejected: bool = False
    live: int = 0
    """Candidates that are not rejected."""
    measured: int = 0
    """Live candidates whose facts were measured before the budget ended."""
    stopped: bool = False
    """A bound stopped the search of this subject (its reason is one of ``STOPPED``)."""


def state_of(subject: SubjectFacts) -> State:
    if not subject.selected:
        return "not-attempted"
    if subject.rejected:
        return "rejected"
    if not subject.live:
        return "unknown" if subject.stopped else "no-candidate"
    if not subject.measured:
        return "unknown"
    return "proposed"


def completion(*, open_before: int, fill: str, subjects: Iterable[SubjectFacts]) -> dict[str, Any]:
    """The ``result.completion`` object of ``fenolite route --propose``."""
    if open_before < 0:
        raise ValueError(f"open_before must not be negative, not {open_before}")
    if fill not in ("saved", "simulated"):
        raise ValueError(f"fill must be 'saved' or 'simulated', not {fill!r}")
    sorted_out: dict[State, list[str]] = {state: [] for state in STATES}
    seen: set[str] = set()
    for subject in subjects:
        if subject.key in seen:
            raise ValueError(f"subject {subject.key!r} is listed twice")
        if subject.measured > subject.live or subject.live < 0 or subject.measured < 0:
            raise ValueError(f"subject {subject.key!r}: measured {subject.measured} > live {subject.live}")
        seen.add(subject.key)
        sorted_out[state_of(subject)].append(subject.key)
    return {
        "state": "open" if open_before else "unchecked",
        "open": open_before,
        "fill": fill,
        "subjects": {state: sorted(keys) for state, keys in sorted_out.items()},
        "checks": "not-run",
        "complete": False,
    }


__all__ = ["STATES", "STOPPED", "State", "SubjectFacts", "completion", "state_of"]

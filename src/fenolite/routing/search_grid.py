# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bounded integer A* on an authored sparse state graph (c0365, S-1309).

No geometry assumptions live here. Edges are supplied by the geometry adapter; costs must
be positive integers and the heuristic a nonnegative admissible integer lower bound.
"""

from __future__ import annotations

import heapq
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, order=True, slots=True)
class State:
    """Board-frame coordinates, copper-layer index, incoming direction, and vias used."""

    x: int
    y: int
    layer: int
    direction: int
    vias: int


StopReason = Literal["budget", "cancelled"]
Termination = Literal["found", "no-room", "state-limit", "budget", "cancelled"]
Neighbours = Callable[[State], Iterable[tuple[State, int]]]
Stop = Callable[[], StopReason | None]


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Only a complete path is returned; limits never export a partial route."""

    path: tuple[State, ...]
    cost: int
    expanded: int
    discovered: int
    termination: Termination


def astar(
    starts: Sequence[State],
    goal: Callable[[State], bool],
    neighbours: Neighbours,
    heuristic: Callable[[State], int],
    *,
    max_states: int,
    stop: Stop = lambda: None,
) -> SearchResult:
    """Search with stable ties and a cap on discovered states, not just expanded nodes.

    Reopen improved states; neither a coordinate-only visited set nor first discovery of
    a goal is sufficient. A bound can stop before a route is found, even on a solvable graph.
    """
    if type(max_states) is not int or max_states <= 0:
        raise ValueError("max_states must be a positive integer")
    distance: dict[State, int] = {}
    parent: dict[State, State] = {}
    frontier: list[tuple[int, int, State]] = []
    expanded = 0

    def ended(reason: Termination) -> SearchResult:
        return SearchResult((), 0, expanded, len(distance), reason)

    def push(state: State, cost: int) -> None:
        lower = heuristic(state)
        if type(lower) is not int or lower < 0:
            raise ValueError("heuristic must be a nonnegative integer")
        distance[state] = cost
        heapq.heappush(frontier, (cost + lower, cost, state))

    for state in sorted(set(starts)):
        if reason := stop():
            return ended(reason)
        if len(distance) == max_states:
            return ended("state-limit")
        push(state, 0)
    while frontier:
        if reason := stop():
            return ended(reason)
        _, cost, state = heapq.heappop(frontier)
        if distance[state] != cost:
            continue
        expanded += 1
        if goal(state):
            path = [state]
            while state in parent:
                state = parent[state]
                path.append(state)
            return SearchResult(tuple(reversed(path)), cost, expanded, len(distance), "found")
        for there, edge in sorted(neighbours(state)):
            if reason := stop():
                return ended(reason)
            if type(edge) is not int or edge <= 0:
                raise ValueError("edge cost must be a positive integer")
            value = cost + edge
            if there in distance and distance[there] <= value:
                continue
            if there not in distance and len(distance) == max_states:
                return ended("state-limit")
            parent[there] = state
            push(there, value)
    return ended("no-room")

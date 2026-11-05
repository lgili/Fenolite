# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independent, exhaustive shortest paths on tiny authored directed graphs.

Deliberately no priority queue, search heuristic or production search import.
"""

from collections.abc import Hashable, Mapping, Sequence
from typing import TypeVar

Node = TypeVar("Node", bound=Hashable)


def shortest(graph: Mapping[Node, Sequence[tuple[Node, int]]], start: Node, end: Node) -> int | None:
    """Label-setting Dijkstra with a linear minimum scan; tiny graphs only."""
    distances = {start: 0}
    remaining = set(graph) | {v for edges in graph.values() for v, _ in edges}
    while remaining:
        reachable = [n for n in remaining if n in distances]
        if not reachable:
            return None
        here = min(reachable, key=lambda n: (distances[n], repr(n)))
        if here == end:
            return distances[here]
        remaining.remove(here)
        for there, cost in graph.get(here, ()):
            if cost <= 0:
                raise ValueError("the authored oracle uses positive edges")
            value = distances[here] + cost
            if there in remaining and (there not in distances or value < distances[there]):
                distances[there] = value
    return None

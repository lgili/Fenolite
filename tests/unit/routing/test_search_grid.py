# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Independent minimum-path and termination proofs for c0365's sparse kernel."""

from itertools import product

import pytest
from _search_oracle import shortest

from fenolite.routing.search_grid import State, astar


def test_matches_independent_oracle_on_all_authored_obstacle_subsets() -> None:
    nodes = tuple(State(x, y, 0, 0, 0) for x, y in product(range(4), range(3)))
    start, end = nodes[0], nodes[-1]
    optional = (nodes[2], nodes[4], nodes[7], nodes[9])
    for bits in product((False, True), repeat=len(optional)):
        blocked = {n for n, bit in zip(optional, bits, strict=True) if bit}
        graph = {
            n: tuple(
                (v, 10 if n.x == v.x or n.y == v.y else 14)
                for v in nodes
                if v not in blocked and n != v and max(abs(n.x - v.x), abs(n.y - v.y)) == 1
            )
            for n in nodes
            if n not in blocked
        }
        result = astar(
            (start,),
            lambda n: n == end,
            lambda n, graph=graph: graph.get(n, ()),
            lambda n: 10 * max(abs(n.x - end.x), abs(n.y - end.y)),
            max_states=100,
        )
        expected = shortest(graph, start, end)
        assert (result.cost if result.path else None) == expected
        assert result.discovered <= 100
        if result.path:
            assert (
                sum(dict(graph[a])[b] for a, b in zip(result.path, result.path[1:], strict=False)) == expected
            )


def test_improvement_reopens_state_with_inconsistent_admissible_heuristic() -> None:
    a, b, c, end = (State(i, 0, 0, 0, 0) for i in range(4))
    graph = {a: ((b, 6), (c, 1)), b: ((end, 5),), c: ((b, 1),), end: ()}
    h = {a: 0, b: 0, c: 6, end: 0}
    result = astar((a,), lambda n: n == end, lambda n: graph[n], lambda n: h[n], max_states=20)
    assert result.cost == shortest(graph, a, end) == 7
    assert result.path == (a, c, b, end)


def test_stable_ties_do_not_depend_on_neighbour_iteration_order() -> None:
    a, b, c, end = (State(i, 0, 0, 0, 0) for i in range(4))
    graph = {a: ((c, 1), (b, 1)), b: ((end, 1),), c: ((end, 1),), end: ()}

    def run(reverse: bool):
        return astar(
            (a,),
            lambda n: n == end,
            lambda n: tuple(reversed(graph[n])) if reverse else graph[n],
            lambda _: 0,
            max_states=20,
        )

    assert run(False) == run(True)


def test_direction_layer_and_via_budget_are_not_collapsed() -> None:
    a = State(0, 0, 0, 0, 0)
    variants = (State(1, 0, 0, 0, 0), State(1, 0, 1, 0, 1), State(1, 0, 0, 1, 0), State(1, 0, 0, 0, 2))
    end = State(2, 0, 0, 0, 0)
    graph = {a: tuple((s, i + 1) for i, s in enumerate(variants)), **{s: () for s in variants}, end: ()}
    graph[variants[-1]] = ((end, 1),)
    assert astar((a,), lambda n: n == end, lambda n: graph[n], lambda _: 0, max_states=20).path == (
        a,
        variants[-1],
        end,
    )


def test_discovered_state_bound_cannot_leak_partial_path() -> None:
    start = State(0, 0, 0, 0, 0)
    result = astar(
        (start,),
        lambda _: False,
        lambda _: ((State(i, 1, 0, 0, 0), 1) for i in range(100)),
        lambda _: 0,
        max_states=5,
    )
    assert result.termination == "state-limit"
    assert result.discovered == 5 and not result.path


@pytest.mark.parametrize("why", ["budget", "cancelled"])
def test_interruption_never_returns_partial_route(why) -> None:
    count = 0

    def stop():
        nonlocal count
        count += 1
        return why if count >= 4 else None

    result = astar(
        (State(0, 0, 0, 0, 0),),
        lambda _: False,
        lambda n: ((State(n.x + 1, 0, 0, 0, 0), 1),),
        lambda _: 0,
        max_states=100,
        stop=stop,
    )
    assert result.termination == why and not result.path


def test_no_room_is_distinct_from_resource_exhaustion() -> None:
    result = astar((State(0, 0, 0, 0, 0),), lambda _: False, lambda _: (), lambda _: 0, max_states=10)
    assert result.termination == "no-room" and result.expanded == result.discovered == 1


@pytest.mark.parametrize("bound", [0, -1, True, 1.5])
def test_invalid_state_cap(bound) -> None:
    with pytest.raises(ValueError):
        astar((), lambda _: False, lambda _: (), lambda _: 0, max_states=bound)


@pytest.mark.parametrize("edge", [0, -1, True, 1.5])
def test_invalid_costs(edge) -> None:
    start = State(0, 0, 0, 0, 0)
    with pytest.raises(ValueError):
        astar(
            (start,), lambda _: False, lambda _: ((State(1, 0, 0, 0, 0), edge),), lambda _: 0, max_states=10
        )

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Validate the independent oracle before using it to judge c0365's search."""

import pytest
from _search_oracle import shortest


def test_indirect_path_beats_first_discovered_goal() -> None:
    graph = {"a": (("end", 20), ("b", 2)), "b": (("c", 3),), "c": (("end", 4),)}
    assert shortest(graph, "a", "end") == 9


def test_disconnected_and_trivial_graph() -> None:
    assert shortest({"a": (), "b": ()}, "a", "b") is None
    assert shortest({"a": ()}, "a", "a") == 0


def test_layer_direction_and_via_budget_are_distinct_states() -> None:
    start, blocked = (0, 0, 0, 1, 0), (1, 0, 0, 1, 0)
    other_layer, other_direction = (1, 0, 1, 1, 1), (1, 0, 0, 3, 0)
    end = (2, 0, 0, 1, 0)
    graph = {
        start: ((blocked, 1), (other_direction, 4), (other_layer, 2)),
        blocked: (),
        other_direction: ((end, 1),),
        other_layer: ((end, 2),),
        end: (),
    }
    assert shortest(graph, start, end) == 4


def test_oracle_refuses_nonpositive_edges() -> None:
    with pytest.raises(ValueError):
        shortest({"a": (("b", 0),)}, "a", "b")


def test_search_evidence_is_loadable_by_the_real_register_parser() -> None:
    from pathlib import Path

    from fenolite.verify import load_register

    root = Path(__file__).resolve().parents[3]
    registered = {row.id for row in load_register(root / "docs" / "hypotheses.md")}
    assert {"H-G-SEARCH-GRID", "H-G-SEARCH-GEOMETRY", "H-K-SEARCH-DRC"} <= registered

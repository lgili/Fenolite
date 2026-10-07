# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Stored fills of the readable demo boards chain into rings (capability board-analyses, "Copper fill
regions", scenario "Fills of the corpus chain"; ``H-K-FILL-SLIT``; change c0115).

Every fill of every readable board is taken apart by ``unfracture``: its slits removed, the rest chained
by exact endpoint equality, and the stored ring's shoelace area compared with the outer ring's less the
holes'. Counts go to the JSON file named by ``FENOLITE_CENSUS_OUT`` (``docs/evidence/board-analyses.md``
is written from it): no name, value or coordinate of a board is recorded.
"""

from __future__ import annotations

from collections import Counter

import pytest
from _boardcorpus import READABLE_ITEMS, read
from _boards import census
from _corpus import CorpusItem, require

from fenolite.analysis.fills import unfracture
from fenolite.geometry import area2
from fenolite.model.design import Design

pytestmark = [pytest.mark.needs_corpus, pytest.mark.slow]


def items() -> tuple[CorpusItem, ...]:
    found = tuple(item for item in READABLE_ITEMS if item.path.is_file())
    if not found:
        require(READABLE_ITEMS[0])  # skips, or fails in required-resource mode
    return found


def fill_census(design: Design) -> dict[str, int]:
    counts: Counter[str] = Counter(fills=0, fills_with_slits=0, holes=0, not_chained=0, areas_differ=0)
    assert design.board is not None
    for zone in design.board.zones:
        for fill in zone.fills:
            counts["fills"] += 1
            found = unfracture(fill.polygon)
            if found is None:
                counts["not_chained"] += 1
                continue
            outer, holes = found
            counts["holes"] += len(holes)
            counts["fills_with_slits"] += bool(holes)
            if abs(area2(fill.polygon)) != abs(area2(outer)) - sum(abs(area2(hole)) for hole in holes):
                counts["areas_differ"] += 1
    return dict(sorted(counts.items()))


def test_fills_of_the_corpus_chain() -> None:
    """Scenario "Fills of the corpus chain"."""
    total: Counter[str] = Counter()
    for item in items():
        design, _ = read(item.path)
        data = fill_census(design)
        census("fill_slits", item.id, data)
        total.update(data)
    census("fill_slits", "total", dict(sorted(total.items())) | {"boards": len(items())})
    print("fill_slits", dict(sorted(total.items())), "boards", len(items()))
    assert total["not_chained"] == 0 and total["areas_differ"] == 0

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Same-version round trip (RT1) of every readable corpus board (hypothesis H-K-PCB-READ; c0009).

RT1 holds when the rebuilt tree equals the parsed file, the re-read model equals the read model without
provenance, and the opaque counts and digests are equal. Items are named by their manifest id only.
"""

from __future__ import annotations

from collections import defaultdict

import pytest
from _boardcorpus import READABLE_ITEMS, read
from _boards import census, rt1_problems
from _corpus import CorpusItem, require

pytestmark = pytest.mark.needs_corpus
PASSED: dict[str, list[str]] = defaultdict(list)


@pytest.mark.parametrize("item", READABLE_ITEMS, ids=lambda i: i.id)
def test_rt1(item: CorpusItem) -> None:
    path = require(item)
    design, _ = read(path)
    problems = rt1_problems(path.read_bytes().decode("utf-8"), design)
    assert not problems, f"{item.id}: " + "; ".join(problems)
    PASSED[item.origin].append(item.id)


LOCKED_ITEMS = [i for i in READABLE_ITEMS if i.id == "kicad-demo-10-0-6-pcb-16"]


@pytest.mark.parametrize("item", LOCKED_ITEMS, ids=lambda i: i.id)
def test_locked_copper_is_read(item: CorpusItem) -> None:
    """Capability kicad-file-backend, "Copper locks on boards" (change c0108): the corpus board that
    holds locked copper reads with 7 locked tracks and 5 locked vias, and RT1 holds for it."""
    path = require(item)
    design, issues = read(path)
    assert design.board is not None
    assert sum(1 for track in design.board.tracks if track.locked) == 7
    assert sum(1 for via in design.board.vias if via.locked) == 5
    assert not any(arc.locked for arc in design.board.arcs)
    assert not [i for i in issues if i.code == "kicad.board.kept-opaque" and "locked" in i.message]
    assert not rt1_problems(path.read_bytes().decode("utf-8"), design)


def test_rt1_summary() -> None:
    if not PASSED:
        pytest.skip("no RT1 item ran in this session")
    summary = {origin: len(ids) for origin, ids in sorted(PASSED.items())}
    census("rt1", "passed_per_origin", summary)
    print(f"RT1 passed per origin: {summary}")

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the copper check costs on the readable demo boards (capability copper-check, "Copper check
performance is measured"; change c0029).

A measurement, never a gate: the test fails only when a board raises. Each board gets one authored test
rule, a 0.2 mm clearance on every pair, that reaches no user file. Counts and the wall time go to the JSON
file named by ``FENOLITE_CENSUS_OUT`` (``docs/evidence/copper-check.md`` is written from it), and nowhere
else: no name, value or coordinate of a board is recorded.
"""

from __future__ import annotations

import dataclasses
import time
from functools import cache

import pytest
from _boardcorpus import READABLE_ITEMS, read
from _boards import census
from _corpus import CorpusItem, require

from fenolite.backends.kicad.backend import KicadBackend
from fenolite.checks import check_copper
from fenolite.core.ids import derived_id
from fenolite.model.rules import Rule, RuleSet, Selector

pytestmark = [pytest.mark.needs_corpus, pytest.mark.slow]
TEST_RULE = Rule(
    id=derived_id("rul", "test", "copper-perf"),
    name="measurement",
    kind="clearance",
    selector_a=Selector("all"),
    min=200_000,
)
COUNTS = (
    "items",
    "pairs",
    "judged",
    "shorts",
    "clearance",
    "zone_overlaps",
    "unset_pairs",
    "unsupported",
    "approximated",
)


@cache
def items() -> tuple[CorpusItem, ...]:
    found = tuple(i for i in READABLE_ITEMS if i.path.is_file() and not i.heavy)
    if not found:
        require(READABLE_ITEMS[0])  # skips, or fails in required-resource mode
    return found


def test_copper_check_on_the_demo_boards() -> None:
    backend = KicadBackend()
    measured = 0
    for item in items():
        design, _ = read(item.path)
        rules = RuleSet(id=derived_id("rst", "test", "copper-perf"), rules=(TEST_RULE,))
        design = dataclasses.replace(design, rules=rules)
        started = time.perf_counter()
        pads = backend.board_pads(design)
        report = check_copper(design, pads=pads)
        seconds = round(time.perf_counter() - started, 1)
        data = {key: report.summary[key] for key in COUNTS}
        census("copper", item.id, {**data, "layers": len(report.summary["layers"]), "seconds": seconds})  # type: ignore[arg-type]
        print(item.id, seconds, "s", data["items"], "shorts", data["shorts"], "clearance", data["clearance"])
        measured += 1
    assert measured == len(items())

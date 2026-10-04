# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Measure two independent refills of each readable, non-heavy KiCad demo board."""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path

import pytest
from _boardcorpus import READABLE_ITEMS
from _corpus import CorpusItem
from _probes import runner
from _projects import STEM, demo_project

from fenolite.backends.kicad.fill import fill_set
from fenolite.backends.kicad.oracle import KicadOracle
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.projectset import project_set
from fenolite.checks.fill import fill_stage

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_corpus, pytest.mark.slow,
              pytest.mark.kicad_min_major(10)]  # fmt: skip
DEMOS = [item for item in READABLE_ITEMS if not item.heavy]


@pytest.mark.parametrize("item", DEMOS, ids=lambda i: i.id)
def test_two_refills_per_demo(item: CorpusItem, tmp_path: Path) -> None:
    root = demo_project(tmp_path, item)
    board = root / f"{STEM}.kicad_pcb"
    original = read_board(board)
    assert original.board is not None
    oracle = KicadOracle(runner())
    project = project_set(board)
    first = oracle.refill(project)  # the oracle makes two independent KiCad runs
    assert first.zones is not None
    a = {z.zone_id: z for z in first.zones}
    unstable = not first.stable
    original_zones = {z.id: z for z in original.board.zones if z.net_id is not None}
    unfilled = sum(
        bool(a[key].fills) and not original_zones[key].fills for key in original_zones.keys() & a.keys()
    )
    stale = sum(
        bool(original_zones[key].fills)
        and fill_set(original_zones[key])
        != fill_set(dataclasses.replace(original_zones[key], fills=a[key].fills))
        for key in original_zones.keys() & a.keys()
    )
    target = os.environ.get("FENOLITE_FILL_EVIDENCE")
    if target:
        with open(target, "a", encoding="utf-8") as out:
            out.write(
                json.dumps(
                    {
                        "zones": len(original_zones),
                        "unfilled": unfilled,
                        "stale": stale,
                        "unstable": int(unstable),
                    }
                )
                + "\n"
            )
    if unstable:

        class MeasuredOracle:
            name = "measured"

            def refill(self, _project):  # type: ignore[no-untyped-def]
                return first

        stage = fill_stage(MeasuredOracle(), project, original)
        assert stage.status == "skipped" and [i.code for i in stage.issues] == ["zone.fill-unchecked"]

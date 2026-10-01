# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Typed board reads agree with kicad-cli exports (capability kicad-oracle; hypotheses H-K-PCB-POS,
H-G-BOTTOM-PLACE, H-G-PAD-ANGLE-ABS, H-G-FLIP; change c0009).

Placements against ``pcb export pos``, pads and nets against ``pcb export ipcd356``, on the authored
board (9.0.9 and 10.0.6) and on the readable non-heavy demos (10.0.6, with the corpus). Items are named
by their manifest id only.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _boardcorpus import READABLE_ITEMS, read
from _boards import FIXTURE, census
from _corpus import require
from _frame import bottom_rotations, pad_report, pos_problems, read_pos
from _kicad import supported_version
from _upgrade import runner

from fenolite.backends.kicad.ipcd356 import read_ipcd356
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_kicad
DEMOS = [i for i in READABLE_ITEMS if not i.heavy]
BOARDS = [
    pytest.param("fixture", id="fixture"),
    *(pytest.param(i.id, id=i.id, marks=pytest.mark.needs_corpus) for i in DEMOS),
]


def _board(name: str) -> tuple[Path, Design]:
    if name == "fixture":
        return FIXTURE, read_board(FIXTURE)
    item = next(i for i in DEMOS if i.id == name)
    path = require(item)
    return path, read(path)[0]


@pytest.mark.parametrize("name", BOARDS)
def test_pos(name: str) -> None:
    version = supported_version()
    path, design = _board(name)
    rows = read_pos(runner().export_pos_csv(path))
    problems = pos_problems(design, rows)
    assert not problems, f"{name}: " + "; ".join(problems[:5])
    pairs = bottom_rotations(design, rows)
    census("frame", f"bottom_rotations:{version}:{name}", sorted(set(pairs)))
    assert all(stored % 360 == exported % 360 for stored, exported in pairs), pairs


def test_pos_fixture_placements() -> None:
    rows = {row.ref: row for row in read_pos(runner().export_pos_csv(FIXTURE))}
    r1, d1 = rows["R1"], rows["D1"]
    assert (r1.side, r1.position, r1.rotation) == ("top", Point(20_000_000, 15_000_000), 90_000_000)
    assert (d1.side, d1.position, d1.rotation) == ("bottom", Point(35_000_000, 15_000_000), 30_000_000)


@pytest.mark.parametrize("name", BOARDS)
def test_ipcd356(name: str) -> None:
    version = supported_version()
    path, design = _board(name)
    report = pad_report(design, read_ipcd356(runner().export_ipcd356(path)))
    assert not report.problems, f"{name}: " + "; ".join(report.problems[:5])
    census(
        "frame",
        f"ipcd356:{version}:{name}",
        {
            "matched": report.matched,
            "vias": report.vias,
            "truncated_keys": report.truncated_keys,
            "ambiguous_keys": report.ambiguous_keys,
            "r_fields": sorted([*k, n] for k, n in report.r_fields.items()),
        },
    )


def test_wrong_model_detected() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    d1 = next(fp for fp in design.board.footprints if design.by_id[fp.component_id].ref == "D1")  # type: ignore[attr-defined]
    wrong = design.replace_entity(dataclasses.replace(d1, rotation=0))
    report = pad_report(wrong, read_ipcd356(runner().export_ipcd356(FIXTURE)))
    assert any(p.startswith("D1 pin 2") for p in report.problems), report.problems

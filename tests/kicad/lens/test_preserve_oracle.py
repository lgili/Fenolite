# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Preserved layouts pass the oracle (capability kicad-oracle, "Preserved layouts pass the oracle";
hypothesis H-K-LENS-KEEP; change c0019): a footprint moved by token edit, re-saved by ``pcb upgrade
--force`` on 10.0.6, survives a rebuild with its route intact, judged by ``pcb export pos``, item identity
and an unchanged DRC report."""

from __future__ import annotations

import _lenscases as lc
import pytest
from _layout_edit import D1_SHIFT
from _probes import run

from fenolite.backends.kicad.versions import DowngradeRefusedError

pytestmark = pytest.mark.needs_kicad
TARGETS = [pytest.param(10, marks=pytest.mark.kicad_min_major(10), id="t10"), pytest.param(9, id="t9")]


@pytest.mark.parametrize("target", TARGETS)
def test_moved_footprint_survives(target: int) -> None:
    assert run(f"lens-keep-t{target}") == "equal"
    rows = lc.pos_rows(lc.rebuilt_files(target))
    fresh = lc.pos_rows(lc.built_files(target))
    d1, placed = rows["D1"], fresh["D1"]
    assert d1.position.x == placed.position.x + D1_SHIFT and d1.position.y == placed.position.y  # type: ignore[attr-defined]


@pytest.mark.kicad_min_major(10)
def test_second_rebuild_identical() -> None:
    first = lc.rebuilt_files(10)
    assert lc.rebuild(first, 10) == first


@pytest.mark.kicad_min_major(10)
def test_downgrade_refused() -> None:
    resaved = lc.resave(lc.edited_files(9))
    with pytest.raises(DowngradeRefusedError):
        lc.rebuild(resaved, 9)
    rebuilt = lc.rebuild(resaved, 10)
    assert lc.positions(lc.text_of(rebuilt))["D1"] == lc.positions(lc.text_of(resaved))["D1"]

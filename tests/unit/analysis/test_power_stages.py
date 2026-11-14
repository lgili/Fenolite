# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The staged bounds of a fill between two ports (change c0503; capability board-analyses, "Staged region
bounds"), on the authored regions of ``tests/_power.py``."""

from __future__ import annotations

import pytest
from _analysis import box
from _power import STRIP, dumbbell, region, split4, spokes

from fenolite.analysis.fills import FillRegion
from fenolite.analysis.power import region_bounds, stage_bounds
from fenolite.analysis.section import Port
from fenolite.geometry import Thick


def _port(name: str, x0: float, y0: float, x1: float, y1: float) -> Port:
    return Port(name, (Thick(box(x0, y0, x1, y1), 0, filled=True),))


CASES = [
    ("strip", region(STRIP), _port("A", 0, 0, 1, 5), _port("B", 19, 0, 20, 5)),
    ("dumbbell", dumbbell(), _port("A", 4, 4, 6, 6), _port("B", 17, 4, 19, 6)),
    ("split4", split4(), _port("A", 4, 4, 6, 6), _port("B", 17, 4, 19, 6)),
    ("spokes", spokes(), _port("A", 1, 1, 3, 3), _port("B", 9.8, 9.8, 10.2, 10.2)),
]


@pytest.mark.parametrize(("name", "fill", "a", "b"), CASES, ids=[case[0] for case in CASES])
def test_bounds_contain_the_exact_interval(name: str, fill: FillRegion, a: Port, b: Port) -> None:
    """Scenario "Bounds contain the exact interval": each stage's interval contains the next one's, and
    stage 2 is ``region_bounds``."""
    found = [stage_bounds(fill, a, b, sheet_uohm=400, stage=stage) for stage in (0, 1, 2)]
    assert found[2] == region_bounds(fill, a, b, sheet_uohm=400)
    assert found[0].high is None
    for wide, narrow in zip(found, found[1:], strict=False):
        assert wide.low <= narrow.low, name
        assert wide.high is None or (narrow.high is not None and wide.high >= narrow.high), name

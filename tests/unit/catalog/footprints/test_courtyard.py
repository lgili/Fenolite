# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The generated courtyard (change c0260, scenario "Courtyard contains everything")."""

from __future__ import annotations

import pytest
from _package_records import every_record

from fenolite.catalog.footprints import generate, positions_of
from fenolite.catalog.footprints.lands import LANDS
from fenolite.catalog.footprints.record import Package

PACKAGES = every_record()


@pytest.mark.parametrize("package", PACKAGES, ids=[p.file for p in PACKAGES])
def test_courtyard_contains_everything(package: Package) -> None:
    excess, grid = LANDS[1].courtyard, LANDS[1].grid
    for count in positions_of(package) or (None,):
        result = generate(package, positions=count)
        fp = result.footprint
        assert fp is not None and result.courtyard is not None, package.file
        courts = fp.graphics_on("F.CrtYd")
        assert len(courts) == 1 and courts[0].kind == "rect"
        a, b = courts[0].points
        x0, y0, x1, y1 = a.x, a.y, b.x, b.y
        assert (x0, y0, x1, y1) == result.courtyard
        assert all(value % grid == 0 for value in (x0, y0, x1, y1))
        points = [(p.position.x - p.size.w // 2, p.position.y - p.size.h // 2) for p in fp.pads]
        points += [(p.position.x + p.size.w // 2, p.position.y + p.size.h // 2) for p in fp.pads]
        points += [(q.x, q.y) for g in fp.graphics_on("F.Fab") for q in g.points]
        for x, y in points:
            assert x0 + excess <= x <= x1 - excess and y0 + excess <= y <= y1 - excess, (package.file, x, y)

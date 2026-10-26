# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Integer geometry, bounded search and recoverable composition findings."""

import pytest

from fenolite.schematic.composition import GRID, ISSUE_CODES, PLACEMENT_BUDGET, Box, fail, rotate, up


def test_box_boundaries_and_integer_grid():
    a, b = Box(0, 0, 10, 10), Box(10, 0, 20, 10)
    assert not a.overlaps(b)
    assert a.contains(Box(0, 0, 10, 10))
    assert a.move(2, 3) == Box(2, 3, 12, 13)
    assert up(-1) == 0 and up(GRID + 1) == 2 * GRID
    assert isinstance(PLACEMENT_BUDGET, int)
    with pytest.raises(ValueError):
        Box(2, 0, 1, 0)


def test_rotation_closure():
    assert [rotate((2, 3), q) for q in range(4)] == [(2, 3), (3, -2), (-2, -3), (-3, 2)]
    assert rotate((2, 3), 4) == (2, 3)


def test_issue_table_and_actionable_findings():
    assert len(ISSUE_CODES) == 8
    assert set(ISSUE_CODES.values()) == {"error", "info"}
    error = fail("overflow", "block does not fit", "sheet/input", "use a larger paper")
    assert error.issues[0].code == "composition.overflow"
    assert error.issues[0].where == "sheet/input" and error.issues[0].hint

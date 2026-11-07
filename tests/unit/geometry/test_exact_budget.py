# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The exact cut's outcome is decided by counted work, not by the clock (c0402)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from fenolite.cli.errors import from_exception
from fenolite.geometry.boolean import _exact_cut as cut
from fenolite.geometry.boolean._exact_noding import STAGE_WORK, WORK, Budget, ExactDeadline, Limits
from fenolite.geometry.errors import GeometryError
from fenolite.geometry.polygon import Polygon
from fenolite.geometry.vector import Point


def rectangle(x0: int, y0: int, x1: int, y1: int) -> Polygon:
    return Polygon((Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1)))


def diamond(cx: int, cy: int, r: int) -> Polygon:
    return Polygon((Point(cx, cy - r), Point(cx + r, cy), Point(cx, cy + r), Point(cx - r, cy)))


SUBJECT = [diamond(50 * k, 0, 40) for k in range(6)] + [rectangle(-40, -3, 290, 3)]
PIECES = [diamond(50 * k + 7, 1, 9) for k in range(6)] + [
    rectangle(50 * k + 20, -30, 50 * k + 23, 30) for k in range(5)
]


class Ticks:
    """A clock that advances ``step`` seconds on every reading: a slow machine, the same on every run."""

    def __init__(self, step: float) -> None:
        self.step, self.calls = step, 0

    def __call__(self) -> float:
        self.calls += 1
        return self.calls * self.step


def run(budget: Budget) -> tuple[str, object]:
    try:
        return "polygons", cut.exact_difference(SUBJECT, PIECES, budget, strip_edges=12).polygons
    except GeometryError as exc:
        return "refused", str(exc)


def test_a_slowed_clock_gives_the_same_polygons_and_the_same_work() -> None:
    counting = Ticks(0.0)
    fast = Budget(clock=counting)
    expected = run(fast)
    assert expected[0] == "polygons" and fast.work > 0
    # Spread 1000 s over the readings: four times the former 240 s deadline, within the safety net.
    slow_clock = Ticks(1000 / counting.calls)
    slow = Budget(clock=slow_clock)
    assert run(slow) == expected and slow.work == fast.work
    assert slow_clock() > 4 * 240


def test_a_work_refusal_is_the_same_on_a_fast_and_a_slowed_clock() -> None:
    probe = Budget()
    run(probe)
    tight = replace(Limits(), work=probe.work - 1)
    fast = run(Budget(tight, clock=Ticks(0.0)))
    slow = run(Budget(tight, clock=Ticks(0.1)))  # past the former 240 s deadline, within the net
    assert fast == slow and fast[0] == "refused" and "work budget exceeded" in str(fast[1])


def test_the_wall_time_safety_net_is_a_retryable_error_not_a_refusal() -> None:
    with pytest.raises(ExactDeadline, match="safety net") as raised:
        run(Budget(clock=Ticks(Limits().stage_seconds + 1)))
    assert not isinstance(raised.value, GeometryError)
    error = from_exception(raised.value, "fill")
    assert error.code == "FEN-1005" and error.info().retryable


def test_default_work_limits_cover_the_stage_inside_the_operation() -> None:
    assert Limits().work == WORK and Limits().stage_work == STAGE_WORK <= WORK

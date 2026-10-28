# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The comparison of two pours of one board (change c0215; capability altium-pour, "Pour comparison").

Each candidate is the authored board written again with the engine's pieces edited (and its self-check off,
since an edited pour may break a clearance on purpose), so that both sides are readings of one board.
Positions are taken from the reading, in the frame of the import.
"""

from __future__ import annotations

import dataclasses
import importlib.util
from collections.abc import Callable

import pytest
from _altium_pour import Board, clearance, pad, track, via, zone

from fenolite.backends.altium import pour as engine
from fenolite.backends.altium.pour import PolygonPour, PourReading, PourResult, read_pour
from fenolite.backends.altium.pourcompare import PourPoint, compare_pours
from fenolite.core.coords import Point
from fenolite.geometry import Polygon
from fenolite.geometry.boolean.clipper import ClipperBackend
from fenolite.model.board import ZoneSettings

pytestmark = pytest.mark.skipif(importlib.util.find_spec("pyclipper") is None, reason="needs the geo extra")
FILENAME = "pour.PcbDoc"
SPLIT = Board(
    zones=(zone("z1", "GND"),),
    tracks=(track("t1", "VIN", (20, 0.5), (20, 29.5), width=0.5),),
    vias=(via("v1", "GND", 10, 15), via("v2", "GND", 30, 15)),
    rules=(clearance(0.3),),
)
"""A ``GND`` polygon cut in two by a ``VIN`` track from edge to edge, a ``GND`` via in each half (a piece
without one is dead copper)."""
RELIEF = Board(
    zones=(zone("z1", "GND", settings=ZoneSettings(thermal_gap=500_000, thermal_spoke_width=400_000)),),
    pads=(
        pad("p1", "GND", 20, 15, kind="thru_hole", shape="circle", size=(2.0, 2.0), drill=1.0),
        pad("p2", "VIN", 10, 15, shape="circle", size=(1.0, 1.0)),
    ),
    rules=(clearance(0.3),),
)
"""A ``GND`` polygon with a relief to a through-hole ``GND`` pad and a void around an ``SMD`` ``VIN`` pad."""

Edit = Callable[[PourReading, PolygonPour], tuple[Polygon, ...]]


def _written(board: Board, monkeypatch: pytest.MonkeyPatch, edit: Edit | None = None) -> PourReading:
    """The reading of ``board`` written with ``computed``, the pieces of every poured polygon passed
    through ``edit``."""
    if edit is None:
        return read_pour(board.write().data, file=FILENAME)
    real = engine.pour_reading

    def editing(reading: PourReading, **options: object) -> PourResult:
        found = real(reading, **options)  # type: ignore[arg-type]
        polygons = tuple(
            dataclasses.replace(p, pieces=edit(reading, p)) if p.poured else p for p in found.polygons
        )
        return PourResult(polygons, found.evidence)

    with monkeypatch.context() as patch:
        patch.setattr(engine, "pour_reading", editing)
        patch.setattr(engine, "check_pour", lambda *_: ())
        data = board.write().data
    return read_pour(data, file=FILENAME)


def _box(x0: int, y0: int, x1: int, y1: int) -> Polygon:
    return Polygon((Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1)))


def test_a_pour_against_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A pour against itself": every polygon passes M1 to M5; a declaration that both sides
    contradict is a fault of the probe, not a failure."""
    reading = _written(RELIEF, monkeypatch)
    board = reading.design.board
    assert board is not None
    (gnd,) = [p for p in reading.pads if p.net == "GND"]
    (vin,) = [p for p in reading.pads if p.net == "VIN"]
    inside = Point(gnd.position.x + 5_000_000, gnd.position.y)
    points = (
        PourPoint("GND_L01_P000", inside, True),
        PourPoint("GND_L01_P000", vin.position, False),
    )
    found = compare_pours(reading, reading, points=points)
    assert found.passed and not found.unmatched and not found.probe_faults
    (verdict,) = found.polygons
    assert verdict.failed == () and verdict.xor_area == 0 and verdict.pieces == (1, 1)
    wrong = compare_pours(reading, reading, points=(PourPoint("GND_L01_P000", inside, False),))
    assert wrong.passed and len(wrong.probe_faults) == 1 and "GND_L01_P000" in wrong.probe_faults[0]


def test_a_neck_kept_on_one_side(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A neck kept on one side": a 0.2 mm bar joins the two pieces across the track in the
    candidate; M2 fails at the bar with the copper on the candidate's side, and M3 fails."""
    reference = _written(SPLIT, monkeypatch)
    board = reference.design.board
    assert board is not None
    (cut,) = board.tracks
    middle = Point((cut.start.x + cut.end.x) // 2, (cut.start.y + cut.end.y) // 2)
    bar = _box(middle.x - 1_500_000, middle.y - 100_000, middle.x + 1_500_000, middle.y + 100_000)

    def keep_neck(_reading: PourReading, polygon: PolygonPour) -> tuple[Polygon, ...]:
        return ClipperBackend().union([*polygon.pieces, bar])

    candidate = _written(SPLIT, monkeypatch, keep_neck)
    found = compare_pours(candidate, reference)
    (verdict,) = found.polygons
    assert verdict.pieces == (1, 2)
    assert "M2" in verdict.failed and "M3" in verdict.failed
    (neck,) = verdict.differences
    assert neck.side == "candidate"
    assert abs(neck.center.x - middle.x) <= 1_500_000 and abs(neck.center.y - middle.y) <= 100_000
    assert any(f.criterion == "M2" and f.at == neck.center for f in verdict.failures)


def test_two_approximations_of_one_curve(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Two approximations of one curve": a void of radius 1 mm drawn with 64 chords on one side
    and 32 on the other, both within ``ARCRESOLUTION`` (0.5 mil); M1 and M2 pass."""
    reference_board = Board(
        zones=(zone("z1", "GND"),), vias=(via("v1", "GND", 5, 5),), rules=(clearance(0.3),)
    )
    first = _written(reference_board, monkeypatch)
    (outline,) = [z.outline for z in first.design.board.zones]  # type: ignore[union-attr]
    xs, ys = [p.x for p in outline], [p.y for p in outline]
    center = Point((min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2)

    def with_void(count: int) -> Edit:
        def edit(_reading: PourReading, polygon: PolygonPour) -> tuple[Polygon, ...]:
            return ClipperBackend().difference(polygon.pieces, [_regular(center, 1_000_000, count)])

        return edit

    candidate = _written(reference_board, monkeypatch, with_void(64))
    reference = _written(reference_board, monkeypatch, with_void(32))
    found = compare_pours(candidate, reference, criteria=("M1", "M2"))
    (verdict,) = found.polygons
    assert verdict.xor_area > 0 and verdict.passed, verdict.failures


def _regular(center: Point, radius: int, count: int) -> Polygon:
    """A regular polygon of ``count`` vertices on the circle of ``radius``."""
    from fenolite.core.trig import FULL_TURN, ONE, cos_sin_fixed

    points = []
    for k in range(count):
        cos, sin = cos_sin_fixed(k * (FULL_TURN // count))
        points.append(Point(center.x + radius * cos // ONE, center.y + radius * sin // ONE))
    return Polygon(tuple(points))


def test_a_missing_conductor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A missing conductor": the candidate's relief has three of the reference's four
    conductors; M2 fails at the missing one, and M4 passes."""
    reference = _written(RELIEF, monkeypatch)
    (gnd,) = [p for p in reference.pads if p.net == "GND"]
    x, y = gnd.position.x, gnd.position.y
    cut = _box(x + 1_050_000, y - 300_000, x + 1_450_000, y + 300_000)  # inside the gap, right of the pad

    def three(_reading: PourReading, polygon: PolygonPour) -> tuple[Polygon, ...]:
        return ClipperBackend().difference(polygon.pieces, [cut])

    candidate = _written(RELIEF, monkeypatch, three)
    found = compare_pours(candidate, reference)
    (verdict,) = found.polygons
    assert "M2" in verdict.failed and "M4" not in verdict.failed, verdict.failures
    (missing,) = verdict.differences
    assert missing.side == "reference" and abs(missing.center.y - y) <= 300_000 and missing.center.x > x

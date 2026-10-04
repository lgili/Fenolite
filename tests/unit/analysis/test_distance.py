# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Measures, judging and clearance on a layer (capability board-analyses, "Measures" and "Clearance on a
layer"; change c0047)."""

from __future__ import annotations

import random

from _analysis import MM, at, discs, slot_board
from _coppercheck import Copper

from fenolite.analysis.copper import net_copper
from fenolite.analysis.distance import analyze_distances
from fenolite.analysis.report import DistanceRow, Measure, judge
from fenolite.backends.base import PadCopper
from fenolite.core.coords import Point
from fenolite.geometry import thick_gap_floor, thick_touch


def row(report: object) -> DistanceRow:
    (found,) = report.rows  # type: ignore[attr-defined]
    assert isinstance(found, DistanceRow)
    return found


def test_judge_an_interval() -> None:
    measure = Measure(5_100_000, 5_100_002, "F.Cu/B.Cu", (), ("a", "b"))
    assert judge(measure, 6_000_000) == "error"
    assert judge(measure, 5_100_001) == "warning"
    assert judge(measure, 5_100_002) == "warning"
    assert judge(measure, 5_100_000) is None and judge(measure, 5_000_000) is None
    bounded = Measure(10_000_000, None, "F.Cu", (), ("a", "b"), True)
    assert judge(bounded, 10_000_000) is None and judge(bounded, 10_000_001) == "warning"


def test_two_discs() -> None:
    found = row(analyze_distances(discs().build(), pads=None, boundary=None, pairs=(("B", "A"),)))
    assert (found.net_a, found.net_b) == ("A", "B")
    assert [(gap.layer, gap.low, gap.high) for gap in found.gaps] == [
        ("F.Cu", 9_000_000, 9_000_001),
        ("B.Cu", 9_000_000, 9_000_001),
    ]
    assert found.gaps[0].points == (at(5, 0),)
    assert found.clearance is not None and found.clearance.low == 9_000_000


def test_slot_does_not_lengthen_clearance() -> None:
    design, boundary = slot_board()
    found = row(analyze_distances(design, pads=None, boundary=boundary, pairs=(("A", "B"),)))
    assert found.clearance is not None and found.clearance.low == 9_000_000
    assert found.creepage is not None and found.creepage.low == 11_000_000


def test_touching_shapes_measure_zero() -> None:
    made = Copper()
    made.track("A", at(0, 0), at(10, 0), width=500_000)
    made.track("B", at(5, 0), at(5, 10), width=500_000)
    found = row(analyze_distances(made.build(), pads=None, boundary=None, pairs=(("A", "B"),)))
    assert [(gap.low, gap.high) for gap in found.gaps] == [(0, 0)]
    assert found.clearance is not None and (found.clearance.low, found.clearance.high) == (0, 0)


def test_inner_gaps_stay_out_of_the_clearance() -> None:
    made = Copper(layers=4)
    made.track("A", at(0, 0), at(10, 0), layer="In1.Cu")
    made.track("B", at(0, 1), at(10, 1), layer="In1.Cu")
    made.track("A", at(0, 0), at(10, 0), layer="F.Cu")
    made.track("B", at(0, 5), at(10, 5), layer="F.Cu")
    found = row(analyze_distances(made.build(), pads=None, boundary=None, pairs=(("A", "B"),)))
    assert {gap.layer: gap.low for gap in found.gaps} == {"F.Cu": 4_750_000, "In1.Cu": 750_000}
    assert found.clearance is not None and found.clearance.layer == "F.Cu"


def test_only_inner_copper_has_no_clearance() -> None:
    made = Copper(layers=4)
    made.track("A", at(0, 0), at(10, 0), layer="In1.Cu")
    made.track("B", at(0, 1), at(10, 1), layer="In1.Cu")
    found = row(analyze_distances(made.build(), pads=None, boundary=None, pairs=(("A", "B"),)))
    assert len(found.gaps) == 1 and found.clearance is None and found.creepage is None


def test_arc_band_widens_the_interval() -> None:
    made = Copper()
    made.arc("A", at(0, 0), at(5, -5), at(10, 0), width=200_000)
    made.track("B", at(0, 3), at(10, 3), width=200_000)
    found = row(analyze_distances(made.build(), pads=None, boundary=None, pairs=(("A", "B"),)))
    gap = found.gaps[0]
    assert gap.high is not None and gap.high - gap.low == 1 + 2 * 1_001


def test_pads_from_the_frame_are_measured() -> None:
    made = Copper()
    made.pad("R1", "1", "A", PadCopper("F.Cu", (at(0, 0),), MM))
    made.pad("R1", "2", "B", PadCopper("F.Cu", (at(3, 0),), MM))
    report = analyze_distances(made.build(), pads=made.pads, boundary=None, pairs=(("A", "B"),))
    found = row(report)
    assert found.gaps[0].low == 2_000_000 and found.gaps[0].items == ("R1-1", "R1-2")
    assert report.issues == ()


def test_within_finds_the_close_pairs() -> None:
    rng = random.Random(47)
    made = Copper()
    nets = ("N1", "N2", "N3", "N4", "N5")
    for _ in range(200):
        start = Point(rng.randint(0, 60 * MM), rng.randint(0, 40 * MM))
        end = Point(start.x + rng.randint(-3 * MM, 3 * MM), start.y + rng.randint(-3 * MM, 3 * MM))
        made.track(rng.choice(nets), start, end, width=200_000, layer=rng.choice(("F.Cu", "B.Cu")))
    design = made.build()
    within = 500_000
    report = analyze_distances(design, pads=None, boundary=None, within=within)
    found = {(r.net_a, r.net_b) for r in report.rows if isinstance(r, DistanceRow)}
    copper = net_copper(design, pads=None)
    wanted: set[tuple[str, str]] = set()
    names = sorted(copper.by_net)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            for one in copper.by_net[a]:
                for other in copper.by_net[b]:
                    if one.layer != other.layer:
                        continue
                    touching = thick_touch(one.shape, other.shape)
                    if touching or thick_gap_floor(one.shape, other.shape) < within:
                        wanted.add((a, b))
    assert found == wanted and 0 < len(found) <= 10


def test_pair_selection_missing() -> None:
    report = analyze_distances(discs().build(), pads=None, boundary=None)
    (found,) = report.issues
    assert report.rows == () and found.code == "analysis.input-missing" and found.where == "pair selection"


def test_unknown_net_gives_an_empty_row() -> None:
    found = row(analyze_distances(discs().build(), pads=None, boundary=None, pairs=(("A", "NOPE"),)))
    assert found.gaps == () and found.clearance is None and found.creepage is None

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The narrowest copper section of a region between two ports (capability board-analyses, "Narrowest
copper section"; ``H-G-AN-SECTION``)."""

from __future__ import annotations

import random

from _analysis import MM, at, box
from _power import CELL, SQUARE20, Cells, cells_ring, dumbbell, grid_cut, region, split4, spokes

from fenolite.analysis.section import Port, narrowest_section, port_hull
from fenolite.geometry import Thick, area2, point_in_ring
from fenolite.geometry.predicates import Location


def via(name: str, x: float, y: float, diameter: float = 1.0) -> Port:
    return Port(name, (Thick((at(x, y),), round(diameter * MM)),))


def pad(name: str, x0: float, y0: float, x1: float, y1: float) -> Port:
    return Port(name, (Thick(box(x0, y0, x1, y1), 0, filled=True),))


def test_port_hull_stays_inside_the_copper() -> None:
    hull = port_hull(via("V", 0, 0, 0.6))
    assert len(hull) >= 40 and area2(hull) > 0
    assert all(4 * (p.x * p.x + p.y * p.y) <= 600_000**2 for p in hull)
    assert {p.x for p in hull} >= {300_000, -300_000}
    assert set(port_hull(pad("P", 0, 0, 2, 1))) == set(box(0, 0, 2, 1))


def test_neck_of_a_dumbbell() -> None:
    """Scenario "Neck of a dumbbell"."""
    found = narrowest_section(dumbbell(), via("A", 5, 5), via("B", 18, 5))
    measure = found.measure
    assert measure.low == 2_000_000 and measure.high is not None and measure.high <= 2_000_001
    assert found.hull_free and measure.items == ("A", "B") and measure.layer == "F.Cu"
    assert len(measure.points) == 2
    assert {p.y for p in measure.points} == {4 * MM, 6 * MM}
    assert all(10 * MM <= p.x <= 13 * MM for p in measure.points)


def test_two_strips_add_up() -> None:
    """Scenario "Two strips add up"."""
    found = narrowest_section(split4(), via("A", 5, 5), via("B", 18, 5))
    assert found.measure.low == 2_400_000 and found.measure.high == 2_400_000
    assert len(found.measure.points) == 4 and found.hull_free


def test_around_a_via() -> None:
    """Scenario "Around a via"."""
    found = narrowest_section(region(SQUARE20), via("V", 10, 10, 0.6), pad("P", 1, 1, 3, 3))
    assert 1_880_000 <= found.measure.low <= 1_884_955
    assert found.measure.high is not None and found.measure.high <= 1_884_956 and found.hull_free


def test_thermal_spokes() -> None:
    """Scenario "Thermal spokes"."""
    found = narrowest_section(spokes(), pad("P", 9, 9, 11, 11), via("V", 2, 2))
    assert found.measure.low == 2_000_000 and found.measure.high == 2_000_000
    assert len(found.measure.points) == 8 and found.hull_free


def test_a_hole_inside_a_hull() -> None:
    """Scenario "A hole inside a hull"."""
    corners = ((9, 9), (11, 9), (11, 11), (9, 11))
    group = Port("G", tuple(Thick((at(x, y),), 600_000) for x, y in corners))
    hole = port_hull(via("H", 10, 10, 0.8))
    far = pad("P", 1, 1, 3, 3)
    assert narrowest_section(region(SQUARE20), group, far).hull_free
    found = narrowest_section(region(SQUARE20, (hole,)), group, far)
    assert not found.hull_free and found.measure.low > 0


def test_touching_hulls_and_a_port_cut_off() -> None:
    solid = region(SQUARE20)
    touching = narrowest_section(solid, pad("A", 1, 1, 3, 3), pad("B", 3, 1, 5, 3))
    assert touching.measure.low == 0 and touching.measure.high == 0
    # a moat around one port: a closed run at no cost separates the two
    moat_outer, moat_inner = box(4, 4, 16, 16), box(5, 5, 15, 15)
    ring = region(SQUARE20, (moat_outer,))
    island = region(moat_inner)
    assert narrowest_section(ring, pad("A", 1, 1, 3, 3), pad("B", 17, 17, 19, 19)).measure.low > 0
    cut = narrowest_section(island, via("A", 10, 10), pad("B", 30, 30, 32, 32))
    assert cut.measure.low == 0 and cut.measure.high == 0


def test_a_strip_beside_a_port() -> None:
    """A chord across a strip beside a round port, tangent to its hull: the strip's width."""
    strip = region(box(0, 0, 20, 5))
    found = narrowest_section(strip, via("V", 8, 2.5, 4.0), pad("P", 19, 0, 20, 5))
    assert found.measure.low == 5_000_000 and found.measure.high == 5_000_000
    # with a small via its own hull is shorter than the strip is wide
    small = narrowest_section(strip, via("V", 8, 2.5, 0.6), pad("P", 19, 0, 20, 5))
    assert 1_880_000 <= small.measure.low <= 1_884_955


def test_pads_over_the_ends_of_a_strip() -> None:
    strip = region(box(0, 0, 20, 5))
    found = narrowest_section(strip, pad("A", 0, 0, 1, 5), pad("B", 19, 0, 20, 5))
    assert found.measure.low == 5_000_000 and found.measure.high == 5_000_000 and found.hull_free
    for point in found.measure.points:
        assert point_in_ring(point, strip.outer) is Location.BOUNDARY


def test_limit_bounds_the_search() -> None:
    found = narrowest_section(dumbbell(), via("A", 5, 5), via("B", 18, 5), limit=1_500_000)
    assert found.measure.bounded and found.measure.low == 1_500_000 and found.measure.high is None
    same = narrowest_section(dumbbell(), via("A", 5, 5), via("B", 18, 5), limit=2_500_000)
    assert same.measure.low == 2_000_000 and not same.measure.bounded


def _overlap(a: Cells, b: Cells, margin: int = 0) -> bool:
    return a[0] - margin < b[2] and b[0] - margin < a[2] and a[1] - margin < b[3] and b[1] - margin < a[3]


def _generated(rng: random.Random) -> tuple[tuple[int, int], list[Cells], Cells, Cells]:
    """A rectangle of cells with up to four rectangular holes and two rectangular ports that do not
    touch each other; holes may touch or overlap each other, the ports and the rim."""
    size = (rng.randint(60, 110), rng.randint(40, 70))

    def rect(low: int, high: int) -> Cells:
        w, h = rng.randint(low, high), rng.randint(low, high)
        x, y = rng.randint(0, size[0] - w), rng.randint(0, size[1] - h)
        return (x, y, x + w, y + h)

    while True:
        first, second = rect(4, 16), rect(4, 16)
        if not _overlap(first, second, 2):
            break
    holes = [rect(3, 30) for _ in range(rng.randint(0, 4))]
    return size, holes, first, second


def _merged(holes: list[Cells], size: tuple[int, int]) -> bool:
    """Whether the holes can be given as separate rings: none touches or overlaps another or the rim."""
    rim = any(h[0] == 0 or h[1] == 0 or h[2] == size[0] or h[3] == size[1] for h in holes)
    return not rim and not any(_overlap(a, b, 1) for i, a in enumerate(holes) for b in holes[i + 1 :])


def test_grid_cut_agreement_on_generated_regions() -> None:
    """Scenario "Agreement with a grid cut": never above the grid cut plus one cell, never below the grid
    cut divided by √2 less one cell."""
    rng = random.Random(20261007)
    compared = 0
    ratios: list[int] = []
    while compared < 40:
        size, holes, first, second = _generated(rng)
        if not _merged(holes, size):
            continue
        ports = []
        for name, cells in (("A", first), ("B", second)):
            ports.append(Port(name, (Thick(cells_ring(cells), 0, filled=True),)))
        solid = region(cells_ring((0, 0, *size)), [cells_ring(hole) for hole in holes])
        found = narrowest_section(solid, ports[0], ports[1])
        cut = grid_cut(size, holes, first, second) * CELL
        low = found.measure.low
        assert low <= cut + CELL, (size, holes, first, second, low, cut)
        assert (low + CELL) * 141_422 >= cut * 100_000, (size, holes, first, second, low, cut)
        ratios.append(low * 100 // cut if cut else 100)
        assert found.measure.high is not None and found.measure.high - low <= 16
        compared += 1
    assert compared == 40
    print("section/cut in percent:", sorted(ratios))

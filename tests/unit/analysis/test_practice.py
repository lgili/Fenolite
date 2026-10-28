# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The practice checks of change c0204 (capability board-analyses, "Copper states of the practice checks",
"Connectivity and dead copper", "Decoupling distance", "Copper under part bodies" and "Thermal relief
width"), on the authored benches of ``tests/_practicebench.py``."""

from __future__ import annotations

import dataclasses

import pytest
from _practicebench import GRID, LOOP, bodies, cutout, dead, decoupling, relief

import fenolite.analysis.pour as pour_module
from fenolite.analysis.boundary import board_boundary
from fenolite.analysis.current import capacity_ma
from fenolite.analysis.pour import PourCopper, pour_copper
from fenolite.analysis.practice import (
    BodyRow,
    DeadRow,
    DecouplingRow,
    NetGroups,
    ReliefRow,
    analyze_bodies,
    analyze_dead,
    analyze_decoupling,
    analyze_groups,
    analyze_relief,
    copper_distances,
)
from fenolite.analysis.requirements import SCHEMA, load_requirements
from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.frame import board_pads
from fenolite.core.coords import Point
from fenolite.core.evidence import Level
from fenolite.model.design import Design

MM = 1_000_000
HEAD = f'schema = "{SCHEMA}"\n'


def poured(design: Design) -> tuple[tuple[BoardPad, ...], PourCopper]:
    assert design.board is not None
    pads = board_pads(design)
    return pads, pour_copper(design, pads=pads, boundary=board_boundary(design.board), grid=GRID)


def groups(design: Design) -> tuple[NetGroups, list[str], PourCopper]:
    pads, pour = poured(design)
    report = analyze_groups(design, pads=pads, pour=pour)
    (row,) = report.rows
    assert isinstance(row, NetGroups) and report.evidence.level is Level.INFERRED
    return row, [i.code for i in report.issues], pour


def test_a_pin_left_open_by_a_cutout() -> None:
    """Scenario "A pin left open by a cut-out": the fill made before the keep-out is stale, and the simulated
    pour leaves ``D1-2`` alone."""
    row, codes, pour = groups(cutout())
    (zone,) = pour.zones
    assert (zone.state, zone.reason) == ("simulated", "stale: fill inside the keep-out CUT")
    assert row.copper == ("simulated",) and row.split
    assert row.groups == (("D1-2",), ("J1-1",)) and codes == ["analysis.net-split"]


def test_states_saved_fill_and_no_fill() -> None:
    """Without the keep-out the saved fill stands and joins both pads; without a fill the zone is simulated
    and joins them too."""
    row, codes, pour = groups(cutout(keepout=False))
    assert pour.zones[0].state == "saved_fill" and row.groups == (("D1-2", "J1-1"),) and codes == []
    row, codes, pour = groups(cutout(keepout=False, fill=False))
    assert (pour.zones[0].state, pour.zones[0].reason) == ("simulated", "no-fill")
    assert row.copper == ("simulated",) and row.groups == (("D1-2", "J1-1"),) and codes == []
    # the cells kept: the zone less the clearance of 0.5 mm around the pad of D1_1 (none inside) and nothing
    # else, 52 mm by 36 mm in cells of 0.25 mm
    assert pour.zones[0].cells == (52 * MM // GRID) * (36 * MM // GRID)


def test_states_outline_when_the_raster_is_too_large(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pour_module, "MAX_CELLS", 100)
    row, _, pour = groups(cutout(fill=False))
    assert (pour.zones[0].state, pour.zones[0].reason) == ("outline", "too-large")
    # the outline is an upper bound of the copper: it joins the two pads across the keep-out
    assert row.copper == ("outline",) and row.groups == (("D1-2", "J1-1"),)


def test_connectivity_islands_dropped_and_kept() -> None:
    """A simulated island joined to no pad is dropped and counted; the kept islands list their joins."""
    _, pour = poured(cutout())
    assert pour.zones[0].dropped == 0
    assert sorted(len(island.joins) for island in pour.islands) == [1, 1]
    assert all(island.zones == (pour.zones[0].where,) for island in pour.islands)


def test_dead_island_and_far_copper() -> None:
    pads, pour = poured(dead())
    report = analyze_dead(dead(), pads=pads, pour=pour)
    (island,) = report.rows
    assert isinstance(island, DeadRow) and (island.reason, island.kind, island.copper) == (
        "island",
        "fill",
        "saved_fill",
    )
    assert island.where.endswith("#1") and [i.code for i in report.issues] == ["analysis.copper-dead"]
    far = analyze_dead(dead(), pads=pads, pour=pour, distance=5 * MM)
    rows = [row for row in far.rows if isinstance(row, DeadRow) and row.reason == "far"]
    # the B.Cu track ends 14.375 mm from J2's pad (the pad is 1 mm square: 15 mm less 0.5 mm less half the
    # track width); the far fill island lies 10.51 mm from it
    assert sorted((row.kind, row.distance) for row in rows) == [("fill", 10_511_898), ("track", 14_375_000)]
    assert [i.code for i in far.issues].count("analysis.copper-far") == 2
    assert far.summary == {"islands": 1, "far": 2, "dropped": 0}


def test_decoupling_distance_reported_without_a_finding() -> None:
    """Scenario "Decoupling distance reported without a finding"."""
    design = decoupling()
    report = analyze_decoupling(design, pads=board_pads(design))
    rows = {row.pin: row for row in report.rows if isinstance(row, DecouplingRow)}
    pin = rows["U1-4"]
    assert (pin.capacitor, pin.distance, pin.straight, pin.ret) == ("C1-1", 1_500_000, 1_500_000, "U1-2")
    assert pin.loop_area_nm2 == LOOP and report.issues == ()
    assert rows["U1-2"].capacitor == "C1-2"


def test_decoupling_far_against_a_requirement() -> None:
    design = decoupling()
    text = HEAD + '[[decoupling]]\nparts = "U*"\nmax_distance_nm = 1000000\n'
    report = analyze_decoupling(design, pads=board_pads(design), requirements=load_requirements(text))
    assert [i.code for i in report.issues] == ["analysis.decoupling-far"] * 2
    assert all(i.severity == "error" for i in report.issues)
    met = HEAD + '[[decoupling]]\nparts = "U*"\nmax_distance_nm = 1500000\n'
    assert (
        analyze_decoupling(design, pads=board_pads(design), requirements=load_requirements(met)).issues == ()
    )


def test_decoupling_nearest_along_copper() -> None:
    """``C2`` lies 10 mm along copper from ``U1-4``, through ``C1-1``."""
    design = decoupling()
    pads, pour = poured(design)
    reach = copper_distances(design, pour, pads, "+3V3", Point(20 * MM, 20 * MM))
    assert reach[Point(30 * MM, 20 * MM)] == 10 * MM


BODY = HEAD + '[[body_copper]]\nnetclass = "HV"\nparts = "C*"\nlayers = ["F.Cu", "B.Cu"]\n'


def test_bodies_copper_of_a_class_under_a_can() -> None:
    """Scenario "Copper of a class under a can": the HV track on F.Cu, not the Default track on B.Cu."""
    design = bodies()
    pads, pour = poured(design)
    report = analyze_bodies(design, pads=pads, pour=pour, extents=None, requirements=load_requirements(BODY))
    (row,) = report.rows
    assert isinstance(row, BodyRow)
    assert (row.part, row.plan, row.layer, row.nets) == ("C1", "body", "F.Cu", ("HV",))
    (found,) = report.issues
    assert (found.code, found.severity, found.where) == ("analysis.body-copper", "error", "C1")
    assert "F.Cu" in found.message and row.items[0] in found.message


def test_bodies_courtyard_without_a_body() -> None:
    design = bodies()
    assert design.board is not None
    bare = dataclasses.replace(
        design,
        board=dataclasses.replace(
            design.board,
            footprints=tuple(dataclasses.replace(fp, bodies=()) for fp in design.board.footprints),
        ),
    )
    pads, pour = poured(bare)
    extents = KicadBackend().placed_extents(bare)
    report = analyze_bodies(bare, pads=pads, pour=pour, extents=extents, requirements=load_requirements(BODY))
    (row,) = report.rows
    assert isinstance(row, BodyRow) and row.plan == "courtyard"
    nothing = analyze_bodies(bare, pads=pads, pour=pour, extents=None, requirements=load_requirements(BODY))
    assert nothing.rows == () and [i.code for i in nothing.issues] == ["analysis.input-missing"]


def test_bodies_need_a_row() -> None:
    design = bodies()
    pads, pour = poured(design)
    report = analyze_bodies(design, pads=pads, pour=pour, extents=None, requirements=None)
    assert report.rows == () and [i.code for i in report.issues] == ["analysis.input-missing"]


CURRENT = HEAD + '[[current]]\nselect = {{ net = "GND" }}\nmilliamps = {ma}\ntemp_rise_mk = 10000\n'


def test_relief_width_and_capacity() -> None:
    """Four spokes of 0.5 mm cross the ring; 2 mm of 35 um copper carry the fit's current at 10 K."""
    design = relief()
    pads, pour = poured(design)
    capacity = capacity_ma(2 * MM * 35_000, 10_000, external=True)
    report = analyze_relief(design, pads=pads, pour=pour)
    (row,) = report.rows
    assert isinstance(row, ReliefRow)
    assert (row.pad, row.copper, row.spokes, row.width) == ("P1-1", "saved_fill", 4, 2 * MM)
    assert report.issues == ()
    over = load_requirements(CURRENT.format(ma=capacity + 1))
    report = analyze_relief(design, pads=pads, pour=pour, requirements=over, copper_thickness={"*": 35_000})
    (row,) = report.rows
    assert isinstance(row, ReliefRow) and (row.milliamps, row.capacity_ma) == (capacity + 1, capacity)
    assert [i.code for i in report.issues] == ["analysis.relief-exceeded"]
    met = load_requirements(CURRENT.format(ma=capacity))
    assert (
        analyze_relief(design, pads=pads, pour=pour, requirements=met, copper_thickness={"*": 35_000}).issues
        == ()
    )
    unknown = analyze_relief(design, pads=pads, pour=pour, requirements=over)
    assert [i.code for i in unknown.issues] == ["analysis.input-missing"]


def test_relief_of_a_simulated_pour_is_not_measured() -> None:
    design = relief(fill=False)
    pads, pour = poured(design)
    (row,) = analyze_relief(design, pads=pads, pour=pour).rows
    assert isinstance(row, ReliefRow) and (row.copper, row.spokes, row.width) == ("simulated", None, None)


def test_bodies_and_decoupling_tables_load() -> None:
    loaded = load_requirements(BODY + '[[decoupling]]\nparts = "U*"\nmax_distance_nm = 2000000\n')
    assert loaded.body_copper[0].layers == ("F.Cu", "B.Cu") and loaded.decoupling[0].max_distance_nm == 2 * MM
    with pytest.raises(Exception, match="max_distance_nm"):
        load_requirements(HEAD + '[[decoupling]]\nparts = "U*"\nmax_distance_nm = 1.5\n')
    with pytest.raises(Exception, match="layers"):
        load_requirements(HEAD + '[[body_copper]]\nnetclass = "HV"\nparts = "C*"\nlayers = []\n')

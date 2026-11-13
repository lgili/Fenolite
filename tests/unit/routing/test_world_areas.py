# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule areas and other copper in the routing world (change c0501, requirement "Rule areas and other copper
in the routing world"), on authored benches."""

from __future__ import annotations

from dataclasses import replace

from _route_benches import MM, across, bench, round_pad

from fenolite.core.coords import Point
from fenolite.geometry import Location, point_in_ring
from fenolite.model.board import Graphic, Zone, ZoneFill
from fenolite.routing.octilinear import World
from fenolite.routing.search import Limits, search

LIMITS = Limits(250_000, 50_000, 0)
LINE = (Point(-3 * MM, 0), Point(3 * MM, 0))


def test_pour_only_keepout_is_crossed() -> None:
    """Scenario "A keep-out of poured copper only"."""
    b = across(no_copper_pour=True)
    out = search(b.job, b.subject, b.world, LIMITS, max_length=100 * MM)
    assert [points for _, points in out.runs] == [LINE]
    assert b.world.blocker("A", "F.Cu", LINE, 200_000) is None


def test_track_keepout_is_gone_round() -> None:
    """Scenario "A keep-out of tracks"."""
    b = across(no_tracks=True)
    found = b.world.blocker("A", "F.Cu", LINE, 200_000)
    assert found is not None and found.kind == "keepout" and found.label == "across"
    out = search(b.job, b.subject, b.world, LIMITS, max_length=100 * MM)
    assert out.runs and not out.reason
    area = b.job.design.board.keepouts[0].outline  # type: ignore[union-attr]
    for _, points in out.runs:
        assert all(point_in_ring(p, area) is Location.OUTSIDE for p in points)
        assert b.world.fits("A", "F.Cu", points, 200_000)


def test_via_keepout_refuses_a_barrel_only() -> None:
    b = across(no_vias=True)
    probe = (Point(0, 0), Point(1, 0))
    assert b.world.blocker("A", "F.Cu", LINE, 200_000) is None
    found = b.world.blocker("A", "F.Cu", probe, 600_000, via=True)
    assert found is not None and found.kind == "keepout"


def test_copper_graphic_and_kept_fill_block_other_nets() -> None:
    pads = (round_pad("P1", "A", Point(-3 * MM, 0)), round_pad("P2", "A", Point(3 * MM, 0)))
    b = bench(pads, Point(-3 * MM, 0), Point(3 * MM, 0))
    board = b.job.design.board
    assert board is not None
    graphic = Graphic(
        id="gr_1", kind="line", layer="F.Cu", points=(Point(0, -MM), Point(0, MM)), width=100_000
    )
    square = (Point(-MM, 2 * MM), Point(MM, 2 * MM), Point(MM, 4 * MM), Point(-MM, 4 * MM))
    zone = Zone(
        id="zn_1", outline=square, layers=("F.Cu",), net_id="net_A", fills=(ZoneFill("F.Cu", square),)
    )
    other = replace(zone, id="zn_2", net_id=None)
    design = replace(b.job.design, board=replace(board, graphics=(graphic,), zones=(zone, other)))
    for pours, kinds in (("refilled", {"graphic"}), ("kept", {"graphic", "zone"})):
        job = replace(b.job, design=design, extra={**b.job.extra, "pours": pours})
        world = World(job, b.pads, job.extra["outline"])  # type: ignore[arg-type]
        found = {
            hit.kind
            for line in (LINE, (Point(-3 * MM, 3 * MM), Point(3 * MM, 3 * MM)))
            if (hit := world.blocker("A", "F.Cu", line, 200_000)) is not None
        }
        assert found == kinds
        assert world.blocker("A", "B.Cu", LINE, 200_000) is None


def test_altium_keepout_layer_restrictions() -> None:
    """Scenario "Keep-Out layer of an Altium document": the keep-out track (restrictions 2) refuses a track
    on every copper layer, the keep-out fill (restrictions 24, pads only) refuses none."""
    import hashlib

    import _altium_keepouts as cases

    from fenolite.backends.altium.adapter import import_board
    from fenolite.backends.altium.backend import AltiumBackend
    from fenolite.backends.altium.read.pcb import read_pcbdoc

    data = cases.restricted_document()
    design = import_board(read_pcbdoc(data), file="r.PcbDoc", sha256=hashlib.sha256(data).hexdigest())
    areas = AltiumBackend().rule_areas(design, data)
    held = sorted((k.no_tracks, k.no_vias, k.no_pads, k.no_copper_pour) for k in areas)
    assert held == [(False, False, True, False), (True, False, False, False)]
    pads = (round_pad("P1", "A", Point(0, 0)),)
    b = bench(pads, Point(0, 0), Point(MM, 0), half=200 * MM, extra={"rule_areas": areas})
    job = replace(b.job, design=replace(b.job.design, board=replace(design.board, keepouts=())))  # type: ignore[arg-type]
    world = World(job, (), job.extra["outline"])  # type: ignore[arg-type]
    [band] = [k for k in areas if k.no_tracks]
    [fill] = [k for k in areas if k.no_pads]

    def across(area: object) -> tuple[Point, Point]:
        xs = [p.x for p in area.outline]  # type: ignore[attr-defined]
        ys = [p.y for p in area.outline]  # type: ignore[attr-defined]
        mid = (min(xs) + max(xs)) // 2
        return Point(mid, min(ys) - 3 * MM), Point(mid, max(ys) + 3 * MM)

    for layer in ("F.Cu", "B.Cu"):
        found = world.blocker("A", layer, across(band), 200_000)
        assert found is not None and found.kind == "keepout"
        assert world.blocker("A", layer, across(fill), 200_000) is None

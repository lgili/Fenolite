# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper graph paths against authored integer benches."""

from dataclasses import replace

from _topologybench import MM, bench, ident

from fenolite.checks.padpath import CopperGraph, model_pads
from fenolite.core.coords import Point
from fenolite.model.board import Arc, Track, Zone, ZoneFill


def test_shortest_copper_path_and_via_span() -> None:
    graph = CopperGraph(bench())
    path = graph.shortest("U1-1", "U2-1")
    assert path.status == "ok" and path.length_nm == 50 * MM
    assert [step.kind for step in path.steps] == ["track", "via", "track"]
    assert path.pads == ("U1-1", "U2-1")
    assert graph.shortest("U2-1", "U1-1").length_nm == path.length_nm
    design = bench()
    assert design.board is not None
    via = replace(design.board.vias[0], layers=("F.Cu", "B.Cu"))
    design = replace(design, board=replace(design.board, vias=(via,)))
    assert CopperGraph(design).shortest("U1-1", "U2-1").status == "ok"


def test_unrouted_and_zone_path_refused() -> None:
    design = bench()
    assert design.board is not None
    design = replace(design, board=replace(design.board, tracks=()))
    assert CopperGraph(design).shortest("U1-1", "U2-1").status == "unrouted"
    assert CopperGraph(design).shortest("U1-1", "U9-1").status == "unrouted"
    fp = design.board.footprints[1]
    fp = replace(fp, pads=(replace(fp.pads[0], layers=("F.Cu",)),))
    ring = (Point(-MM, -MM), Point(51 * MM, -MM), Point(51 * MM, MM), Point(-MM, MM))
    zone = Zone(
        id=ident("zon", "plane"),
        name="plane",
        net_id=design.circuit.nets[0].id,
        layers=("F.Cu",),
        outline=ring,
        fills=(ZoneFill("F.Cu", ring),),
    )
    design = replace(
        design, board=replace(design.board, footprints=(design.board.footprints[0], fp), zones=(zone,))
    )
    assert CopperGraph(design).shortest("U1-1", "U2-1").status == "path-through-zone"


def test_track_junction_splits_and_shortest_route_wins() -> None:
    design = bench()
    assert design.board is not None
    track = design.board.tracks[0]
    spur = Track(
        id=ident("trk", "spur"),
        start=Point(10 * MM, 0),
        end=Point(10 * MM, 5 * MM),
        width=track.width,
        layer=track.layer,
        net_id=track.net_id,
    )
    design = replace(design, board=replace(design.board, tracks=(*design.board.tracks, spur)))
    path = CopperGraph(design).shortest("U1-1", "U2-1")
    assert path.length_nm == 50 * MM
    assert [step.length_nm for step in path.steps if step.id == track.id] == [10 * MM, 20 * MM]


def test_arc_length_is_not_its_chord() -> None:
    design = bench()
    assert design.board is not None
    first = design.board.tracks[0]
    arc = Arc(
        id=ident("arc", "half"),
        start=first.start,
        mid=Point(15 * MM, 15 * MM),
        end=first.end,
        width=first.width,
        layer=first.layer,
        net_id=first.net_id,
    )
    design = replace(design, board=replace(design.board, tracks=design.board.tracks[1:], arcs=(arc,)))
    path = CopperGraph(design).shortest("U1-1", "U2-1")
    assert path.status == "ok" and path.length_nm == 47_123_890 + 20 * MM
    assert path.steps[0].kind == "arc"


def test_non_plated_hole_without_copper_has_no_copper_entry() -> None:
    """change c0364: an NPTH pad of size 0 used to raise ``ValueError`` (``FEN-1001`` in ``check``)."""
    from fenolite.core.coords import Size
    from fenolite.model.board import FootprintInstance, Pad

    design = bench()
    assert design.board is not None
    for kind, size in (("np_thru_hole", 0), ("np_thru_hole", 4 * MM), ("thru_hole", 0)):
        hole = FootprintInstance(
            id=ident("fp", "H1"),
            component_id=ident("cmp", "H1"),
            lib_ref="authored",
            position=Point(80 * MM, 0),
            pads=(
                Pad(
                    id=ident("pad", "H1"),
                    number="",
                    shape="circle",
                    size=Size(size, size),
                    position=Point(0, 0),
                    kind=kind,  # type: ignore[arg-type]
                    drill=3 * MM,
                    layers=("*.Cu",),
                ),
            ),
        )
        board = replace(design.board, footprints=(*design.board.footprints, hole))
        pads = {pad.footprint_id: pad for pad in model_pads(replace(design, board=board))}
        assert pads[hole.id].copper == (), (kind, size)
        assert len(pads) == 3
        CopperGraph(replace(design, board=board))  # the graph builds from the same pads

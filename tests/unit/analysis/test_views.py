# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board views (capability board-frame, "Board views"; change c0066): nets, region and neighbours.

The pad and extent records are built here, as a backend would give them: the views read no file."""

from __future__ import annotations

import dataclasses
import random
from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from strategies import designs

from fenolite.analysis.views import (
    ALL_KINDS,
    arc_length,
    neighbors_view,
    net_list,
    net_view,
    region_view,
)
from fenolite.backends.base import BoardPad, PadCopper, PlacedExtent
from fenolite.core.coords import Point, Size
from fenolite.core.ids import new_id
from fenolite.geometry import BBox, dist2_segment_segment
from fenolite.model.board import Arc, Board, FootprintInstance, Layer, Pad, Text, Track, Via, Zone
from fenolite.model.circuit import Circuit, Component, Net, NetClass, PinRef
from fenolite.model.design import Design

MM = 1_000_000
RNG = random.Random(66)


def mm(x: float, y: float) -> Point:
    return Point(round(x * MM), round(y * MM))


def ring(x0: float, y0: float, x1: float, y1: float) -> tuple[Point, ...]:
    return (mm(x0, y0), mm(x1, y0), mm(x1, y1), mm(x0, y1))


def _pad_records(design: Design) -> tuple[BoardPad, ...]:
    """Board-frame pad records of a design whose footprints are not rotated: a pad's copper is its
    rectangle around the footprint position plus the pad position, on each of its layers."""
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    names = {n.id: n.name for n in design.circuit.nets}
    records: list[BoardPad] = []
    for fp in design.board.footprints:
        for pad in fp.pads:
            at = Point(fp.position.x + pad.position.x, fp.position.y + pad.position.y)
            half_w, half_h = pad.size.w // 2, pad.size.h // 2
            corners = (
                Point(at.x - half_w, at.y - half_h), Point(at.x + half_w, at.y - half_h),
                Point(at.x + half_w, at.y + half_h), Point(at.x - half_w, at.y + half_h),
            )  # fmt: skip
            copper = tuple(PadCopper(layer, corners, 0, filled=True) for layer in pad.layers)
            records.append(
                BoardPad(
                    footprint_id=fp.id,
                    ref=refs.get(fp.component_id, ""),
                    path="",
                    pad_id=pad.id,
                    number=pad.number,
                    kind=pad.kind,
                    position=at,
                    rotation=0,
                    side=fp.side,
                    layers=pad.layers,
                    net_id=pad.net_id,
                    net=names.get(pad.net_id) if pad.net_id else None,
                    copper=copper,
                )  # fmt: skip
            )
    return tuple(records)


def _part(ref: str, at: Point, *, side: str = "top", nets: tuple[str | None, ...] = (), kind: str = "smd"):
    component = Component(id=new_id("cmp", RNG), ref=ref)
    layer = "F.Cu" if side == "top" else "B.Cu"
    pads = tuple(
        Pad(id=new_id("pad", RNG), number=str(i + 1), shape="rect", size=Size(MM // 2, MM // 2),
            position=Point((2 * i - 1) * MM // 2, 0), layers=(layer,), net_id=net, kind=kind)  # type: ignore[arg-type]
        for i, net in enumerate(nets)
    )  # fmt: skip
    footprint = FootprintInstance(
        id=new_id("fp", RNG),
        component_id=component.id,
        lib_ref="L:F",
        position=at,
        side=side,
        pads=pads,  # type: ignore[arg-type]
    )
    return component, footprint


def _board_design(parts, **board_fields) -> Design:  # type: ignore[no-untyped-def]
    base = Design.new("views", seed=1)
    layers = (
        Layer(id=new_id("lay", RNG), name="F.Cu", kind="copper", ordinal=0),
        Layer(id=new_id("lay", RNG), name="B.Cu", kind="copper", ordinal=2),
    )
    nets = board_fields.pop("nets", ())
    classes = board_fields.pop("netclasses", ())
    board = Board(id=new_id("brd", RNG), layers=layers, footprints=tuple(f for _, f in parts), **board_fields)
    circuit = Circuit(components=tuple(c for c, _ in parts), nets=tuple(nets), netclasses=tuple(classes))
    return dataclasses.replace(base, circuit=circuit, board=board)


def _track(start: Point, end: Point, layer: str, net: str | None, width: int = 250_000) -> Track:
    return Track(id=new_id("trk", RNG), start=start, end=end, width=width, layer=layer, net_id=net)


# --- nets -----------------------------------------------------------------------------------------


def _net_design() -> tuple[Design, Net]:
    power = NetClass(id=new_id("cls", RNG), name="Power")
    r1c, r1f = _part("R1", mm(0, 0), nets=(None, None))
    n = Net(id=new_id("net", RNG), name="N", netclass_id=power.id, members=(PinRef(r1c.id, "1"),))
    other = Net(id=new_id("net", RNG), name="A")
    r1f = dataclasses.replace(r1f, pads=(dataclasses.replace(r1f.pads[0], net_id=n.id), r1f.pads[1]))
    tracks = (
        _track(mm(0, 0), mm(3, 0), "F.Cu", n.id),
        _track(mm(3, 0), mm(3, 4), "F.Cu", n.id),
        _track(mm(0, 10), mm(3, 14), "B.Cu", n.id),
        _track(mm(50, 50), mm(60, 50), "F.Cu", None),
    )
    via = Via(id=new_id("via", RNG), position=mm(3, 4), diameter=600_000, drill=300_000,
              layers=("F.Cu", "B.Cu"), net_id=n.id)  # fmt: skip
    zone = Zone(id=new_id("zon", RNG), outline=ring(0, 0, 5, 5), name="POUR", layers=("B.Cu",), net_id=n.id)
    design = _board_design(
        [(r1c, r1f)], tracks=tracks, vias=(via,), zones=(zone,), nets=(n, other), netclasses=(power,)
    )
    return design, n


def test_track_length_of_a_net() -> None:
    design, _ = _net_design()
    rows = net_list(design)
    assert [row.name for row in rows] == ["A", "N"]
    row = rows[1]
    assert (row.length, row.tracks, row.vias, row.zones, row.pads, row.netclass) == (
        12 * MM,
        3,
        1,
        1,
        1,
        "Power",
    )
    assert rows[0] == type(row)("A", None, 0, 0, 0, 0, 0)
    view = net_view(design, "N", pads=_pad_records(design))
    assert [(c.layer, c.tracks, c.arcs, c.length) for c in view.copper] == [
        ("F.Cu", 2, 0, 7 * MM),
        ("B.Cu", 1, 0, 5 * MM),
    ]
    assert [(p.where, p.layers) for p in view.pads] == [("R1-1", ("F.Cu",))]
    assert [(v.position, v.layers, v.diameter, v.drill) for v in view.vias] == [
        (mm(3, 4), ("F.Cu", "B.Cu"), 600_000, 300_000)
    ]
    assert [(z.name, z.layers, z.filled) for z in view.zones] == [("POUR", ("B.Cu",), False)]
    # pad R1-1 is 0.5 mm square at (-0.5, 0); the F.Cu tracks are 0.25 mm wide; the via ends at 4.3 mm
    assert view.box == BBox(-750_000, -250_000, 3 * MM + 300_000, 14 * MM + 125_000)
    assert view.netclass == "Power"


def test_net_without_copper_and_unknown_net() -> None:
    design, _ = _net_design()
    empty = net_view(design, "A", pads=_pad_records(design))
    assert empty.box is None and empty.pads == () and empty.copper == ()
    with pytest.raises(KeyError):
        net_view(design, "GDN", pads=())


def test_arc_length_is_rounded_half_to_even_without_a_float() -> None:
    def arc(start: Point, mid: Point, end: Point) -> Arc:
        return Arc(id=new_id("arc", RNG), start=start, mid=mid, end=end, width=250_000, layer="F.Cu")

    assert arc_length(arc(mm(-1, 0), mm(0, 1), mm(1, 0))) == 3_141_593  # half a turn of radius 1 mm
    assert arc_length(arc(mm(1, 0), mm(0, 1), mm(0, -1))) == 4_712_389  # three quarters
    assert arc_length(arc(mm(1, 0), mm(0, -1), mm(-1, 0))) == 3_141_593  # the other way round
    assert arc_length(arc(mm(10, 0), mm(0, 10), mm(-10, 0))) == 31_415_927
    assert arc_length(arc(mm(0, 0), mm(1, 0), mm(3, 0))) == 3 * MM  # three points on a line
    assert arc_length(arc(mm(0, 0), mm(1, 0), mm(0, 0))) == 0  # no arc at all
    design, n = _net_design()
    assert design.board is not None
    half = dataclasses.replace(arc(mm(-1, 0), mm(0, 1), mm(1, 0)), net_id=n.id)
    more = dataclasses.replace(design, board=dataclasses.replace(design.board, arcs=(half,)))
    assert net_list(more)[1].length == 12 * MM + 3_141_593 and net_list(more)[1].tracks == 4
    view = net_view(more, "N", pads=())
    assert [(c.layer, c.arcs, c.length) for c in view.copper][0] == ("F.Cu", 1, 7 * MM + 3_141_593)


# --- region ---------------------------------------------------------------------------------------


def test_region_touches_a_track() -> None:
    track = _track(mm(0, 0), mm(10, 0), "F.Cu", None)
    design = _board_design([], tracks=(track,))
    touching = region_view(design, BBox(4 * MM, 100_000, 6 * MM, 2 * MM), pads=(), extents=())
    assert [(i.kind, i.where, i.net, i.layer) for i in touching] == [("track", track.id, None, "F.Cu")]
    assert touching[0].box == BBox(-125_000, -125_000, 10 * MM + 125_000, 125_000)
    assert region_view(design, BBox(4 * MM, 125_000, 6 * MM, 2 * MM), pads=(), extents=()) != ()
    assert region_view(design, BBox(4 * MM, 200_000, 6 * MM, 2 * MM), pads=(), extents=()) == ()
    assert region_view(design, BBox(4 * MM, 125_001, 6 * MM, 2 * MM), pads=(), extents=()) == ()


def _region_design() -> tuple[Design, tuple[BoardPad, ...], tuple[PlacedExtent, ...]]:
    gnd = Net(id=new_id("net", RNG), name="GND")
    r1 = _part("R1", mm(10, 10), nets=(gnd.id, None))
    c1 = _part("C1", mm(30, 10), side="bottom", nets=(gnd.id,))
    tracks = (_track(mm(10, 10), mm(20, 10), "F.Cu", gnd.id), _track(mm(10, 12), mm(20, 12), "B.Cu", gnd.id))
    arc = Arc(id=new_id("arc", RNG), start=mm(20, 10), mid=mm(21, 11), end=mm(20, 12), width=250_000,
              layer="F.Cu", net_id=gnd.id)  # fmt: skip
    via = Via(id=new_id("via", RNG), position=mm(20, 12), diameter=600_000, drill=300_000,
              layers=("F.Cu", "B.Cu"), net_id=gnd.id)  # fmt: skip
    zone = Zone(id=new_id("zon", RNG), outline=ring(0, 0, 40, 20), layers=("B.Cu",), net_id=gnd.id)
    text = Text(id=new_id("txt", RNG), text="T", position=mm(5, 5), layer="F.SilkS", size=Size(MM, MM),
                thickness=150_000)  # fmt: skip
    design = _board_design(
        [r1, c1], tracks=tracks, arcs=(arc,), vias=(via,), zones=(zone,), texts=(text,), nets=(gnd,)
    )
    extents = (
        PlacedExtent(r1[1].id, "top", front=(ring(8.5, 9, 11.5, 11),), source="courtyard"),
        PlacedExtent(c1[1].id, "bottom", back=(ring(29, 9, 31, 11),), source="courtyard"),
    )
    return design, _pad_records(design), extents


def test_region_lists_every_kind_sorted() -> None:
    design, pads, extents = _region_design()
    items = region_view(design, BBox(0, 0, 50 * MM, 30 * MM), pads=pads, extents=extents)
    assert [i.kind for i in items] == [
        "footprint", "footprint", "pad", "pad", "pad", "track", "track", "arc", "via", "zone", "text",
    ]  # fmt: skip
    assert [i.where for i in items[:5]] == ["C1", "R1", "C1-1", "R1-1", "R1-2"]
    assert [(i.net, i.layer) for i in items[:5]] == [
        (None, "B.Cu"), (None, "F.Cu"), ("GND", "B.Cu"), ("GND", "F.Cu"), (None, "F.Cu"),
    ]  # fmt: skip
    assert items[0].box == BBox(29 * MM, 9 * MM, 31 * MM, 11 * MM)
    assert {i.kind for i in items} == set(ALL_KINDS)
    assert all(i.box.intersects(BBox(0, 0, 50 * MM, 30 * MM)) for i in items)


def test_region_one_layer_and_one_kind() -> None:
    design, pads, extents = _region_design()
    whole = BBox(0, 0, 50 * MM, 30 * MM)
    back = region_view(design, whole, pads=pads, extents=extents, layer="B.Cu")
    assert [(i.kind, i.where) for i in back][:2] == [("footprint", "C1"), ("pad", "C1-1")]
    assert [i.kind for i in back] == ["footprint", "pad", "track", "via", "zone"]
    assert all(i.layer == "B.Cu" for i in back)
    only = region_view(design, whole, pads=pads, extents=extents, layer="B.Cu", kinds=("track",))
    assert [(i.kind, i.layer) for i in only] == [("track", "B.Cu")]
    small = region_view(design, BBox(4 * MM, 4 * MM, 6 * MM, 6 * MM), pads=pads, extents=extents)
    assert [i.kind for i in small] == ["zone", "text"]


def test_region_refuses_a_flat_box_and_an_unknown_kind() -> None:
    design, pads, extents = _region_design()
    with pytest.raises(ValueError, match="no area"):
        region_view(design, BBox(0, 0, 0, 10), pads=pads, extents=extents)
    with pytest.raises(ValueError, match="unknown kind"):
        region_view(design, BBox(0, 0, 10, 10), pads=pads, extents=extents, kinds=("tracks",))


def _brute(design: Design, pads: tuple[BoardPad, ...], box: BBox) -> set[tuple[str, str]]:
    """What touches ``box``, judged item by item with the kernel's segment distances and plain boxes."""
    assert design.board is not None
    corners = [Point(box.x0, box.y0), Point(box.x1, box.y0), Point(box.x1, box.y1), Point(box.x0, box.y1)]
    edges = list(zip(corners, corners[1:] + corners[:1], strict=True))
    found: set[tuple[str, str]] = set()
    for track in design.board.tracks:
        inside = box.contains_point(track.start) or box.contains_point(track.end)
        gap2 = min(dist2_segment_segment(track.start, track.end, a, b) for a, b in edges)
        if inside or 4 * gap2 <= Fraction(track.width * track.width):
            found.add(("track", track.id))
    for via in design.board.vias:
        dx = max(box.x0 - via.position.x, 0, via.position.x - box.x1)
        dy = max(box.y0 - via.position.y, 0, via.position.y - box.y1)
        if 4 * (dx * dx + dy * dy) <= via.diameter * via.diameter:
            found.add(("via", via.id))
    for pad in pads:
        if BBox.of_points(pad.copper[0].core).intersects(box):
            found.add(("pad", f"{pad.ref}-{pad.number}"))
    refs = {c.id: c.ref for c in design.circuit.components}
    for fp in design.board.footprints:  # without an extent a footprint is its position
        if box.contains_point(fp.position):
            found.add(("footprint", refs[fp.component_id]))
    return found


coordinate = st.integers(min_value=-(10**9) - 10**6, max_value=10**9 + 10**6)


@settings(max_examples=120, deadline=None)
@given(designs(), coordinate, coordinate, st.integers(1, 2 * 10**9), st.integers(1, 2 * 10**9), st.data())
def test_region_against_brute_force(
    design: Design, x: int, y: int, w: int, h: int, data: st.DataObject
) -> None:
    assert design.board is not None
    if design.board.tracks and data.draw(st.booleans()):  # a box that starts on a track, to hit near misses
        anchor = data.draw(st.sampled_from(design.board.tracks))
        x, y = (
            anchor.start.x + data.draw(st.integers(-3, 3)),
            anchor.start.y + anchor.width // 2 + data.draw(st.integers(-3, 3)),
        )
    box = BBox(x, y, x + w, y + h)
    pads = _pad_records(design)
    items = region_view(design, box, pads=pads, extents=())
    assert {(i.kind, i.where) for i in items} == _brute(design, pads, box)
    assert list(items) == sorted(
        items, key=lambda i: (ALL_KINDS.index(i.kind), i.where, i.layer, i.box.as_tuple())
    )


# --- neighbours -----------------------------------------------------------------------------------


def _neighbors_design() -> tuple[Design, tuple[BoardPad, ...], tuple[PlacedExtent, ...]]:
    gnd = Net(id=new_id("net", RNG), name="GND")
    vcc = Net(id=new_id("net", RNG), name="VCC")
    parts = {
        "R1": _part("R1", mm(0, 0), nets=(gnd.id, vcc.id)),
        "C1": _part("C1", mm(3, 0), nets=(gnd.id, None)),  # courtyard 1 mm to the right
        "C2": _part("C2", mm(0, 5), nets=(vcc.id, gnd.id)),  # 3 mm below
        "C3": _part("C3", mm(-11, 0), nets=(gnd.id,)),  # 8 mm to the left
        "C4": _part("C4", mm(0, 0), side="bottom", nets=(gnd.id,)),  # under R1, on the other side
    }
    design = _board_design(list(parts.values()), nets=(gnd, vcc))
    boxes = {
        "R1": (-1, -1, 1, 1),
        "C1": (2, -1, 4, 1),
        "C2": (-1, 4, 1, 6),
        "C3": (-12, -1, -9, 1),
        "C4": (-1, -1, 1, 1),
    }
    extents = tuple(
        PlacedExtent(
            parts[ref][1].id,
            parts[ref][1].side,
            front=(ring(*box),) if parts[ref][1].side == "top" else (),
            back=(ring(*box),) if parts[ref][1].side == "bottom" else (),
            source="courtyard",
        )  # fmt: skip
        for ref, box in boxes.items()
    )
    return design, _pad_records(design), extents


def test_neighbors_sorted_by_distance() -> None:
    design, pads, extents = _neighbors_design()
    view = neighbors_view(design, "R1", extents=extents, pads=pads, radius=5 * MM)
    assert [(n.ref, n.distance, n.overlap, n.side) for n in view.neighbors] == [
        ("C1", MM, False, "top"),
        ("C2", 3 * MM, False, "top"),
    ]
    assert [n.shared_nets for n in view.neighbors] == [("GND",), ("GND", "VCC")]
    assert (view.part.ref, view.part.position, view.part.rotation, view.part.side) == (
        "R1",
        mm(0, 0),
        0,
        "top",
    )
    assert view.part.box == BBox(-MM, -MM, MM, MM)
    wider = neighbors_view(design, "R1", extents=extents, pads=pads, radius=8 * MM)
    assert [n.ref for n in wider.neighbors] == ["C1", "C2", "C3"]
    assert neighbors_view(design, "R1", extents=extents, pads=pads, radius=MM - 1).neighbors == ()
    assert [
        n.ref for n in neighbors_view(design, "C4", extents=extents, pads=pads, radius=50 * MM).neighbors
    ] == []


def test_overlapping_courtyards_and_rounding_up() -> None:
    design, pads, extents = _neighbors_design()
    moved = tuple(
        dataclasses.replace(e, front=(ring(0.5, -1, 2.5, 1),)) if e.front == (ring(2, -1, 4, 1),) else e
        for e in extents
    )
    first = neighbors_view(design, "R1", extents=moved, pads=pads, radius=0).neighbors
    assert [(n.ref, n.distance, n.overlap) for n in first] == [("C1", 0, True)]
    # a corner to corner gap of √2 nm is rounded up to 2 nm
    r1, c1 = extents[0], extents[1]
    corner = (
        dataclasses.replace(r1, front=((Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)),)),
        dataclasses.replace(c1, front=((Point(11, 11), Point(20, 11), Point(20, 20), Point(11, 20)),)),
        *extents[2:],
    )
    near = neighbors_view(design, "R1", extents=corner, pads=pads, radius=2).neighbors
    assert [(n.ref, n.distance, n.overlap) for n in near] == [("C1", 2, False)]
    assert neighbors_view(design, "R1", extents=corner, pads=pads, radius=1).neighbors == ()


def test_through_hole_parts_count_on_both_sides_and_missing_extents_are_points() -> None:
    gnd = Net(id=new_id("net", RNG), name="GND")
    j1 = _part("J1", mm(0, 0), nets=(gnd.id,), kind="thru_hole")
    c1 = _part("C1", mm(0, 2), side="bottom", nets=(gnd.id,))
    design = _board_design([j1, c1], nets=(gnd,))
    pads = _pad_records(design)
    view = neighbors_view(design, "J1", extents=(), pads=pads, radius=5 * MM)
    assert [(n.ref, n.distance, n.side, n.shared_nets) for n in view.neighbors] == [
        ("C1", 2 * MM, "bottom", ("GND",))
    ]
    assert view.part.box == BBox(0, 0, 0, 0)
    with pytest.raises(KeyError):
        neighbors_view(design, "R9", extents=(), pads=pads, radius=MM)

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Free graphics and keep-outs of the Altium PCB document (capability altium-pcb-writer, "Board graphics
and keep-out records"; change c0085)."""

from __future__ import annotations

import dataclasses

import pytest
from _altium import blink_pcbdoc_spec
from _altium_board6 import IMPORT_LAYERS, LAYERS, at, bare_spec, imported_point, near, read_back

from fenolite.backends.altium import pcbrecords
from fenolite.backends.altium.adapter.copper import region_points
from fenolite.backends.altium.pcbdoc import (
    KEEPOUT_BITS,
    PcbDocSpec,
    graphic_problem,
    keepout_problem,
    keepout_restrictions,
    write_pcbdoc,
)
from fenolite.core.coords import Point
from fenolite.model.board import Graphic, Keepout

RECT = (at(22, 12), at(30, 12), at(30, 17), at(22, 17))


def graphic(key: str, kind: str, layer: str, points: tuple[Point, ...], **changes: object) -> Graphic:
    fields: dict[str, object] = {"id": f"gfx_{key}", "kind": kind, "layer": layer, "points": points}
    return Graphic(**{"width": 150_000, **fields, **changes})  # type: ignore[arg-type]


def keepout(key: str = "k", layers: tuple[str, ...] = LAYERS, **restrictions: bool) -> Keepout:
    return Keepout(id=f"kpo_{key}", outline=RECT, layers=layers, **restrictions)


GRAPHICS = (
    graphic("line", "line", "F.Fab", (at(2, 2), at(12, 2)), width=100_000),
    graphic("arc", "arc", "F.SilkS", (at(44, 4), at(45.414214, 4.585786), at(46, 6))),
    graphic("circle", "circle", "B.SilkS", (at(4, 25), at(6, 25))),
    graphic("rect", "rect", "B.Fab", (at(36, 22), at(44, 27)), width=100_000),
    graphic("outline", "polygon", "F.CrtYd", (at(10, 10), at(14, 10), at(12, 14)), width=50_000),
    graphic("solid", "polygon", "F.SilkS", (at(40, 2), at(42, 2), at(41, 3.5)), width=0, filled=True),
    graphic("pad", "rect", "F.Paste", (at(20, 20), at(22, 21)), width=0, filled=True),
)


def test_graphics_read_back() -> None:
    """Lines, arcs and drawn outlines are tracks and arcs without a net; filled shapes are regions."""
    document, design = read_back(bare_spec(graphics=GRAPHICS))
    assert len(document.tracks) == 1 + 4 + 3 and len(document.arcs) == 2
    assert len(document.regions) == len(document.shape_regions) == 2
    for record in (*document.tracks, *document.arcs, *document.regions):
        prefix = record.prefix  # type: ignore[union-attr]
        assert (prefix.net, prefix.polygon, prefix.component, prefix.flags2) == (None, None, None, 0)
    assert design.board is not None
    read = [g for g in design.board.graphics if g.layer != "Edge.Cuts"]
    by_layer: dict[str, list[Graphic]] = {}
    for found in read:
        by_layer.setdefault(found.layer, []).append(found)
    line = GRAPHICS[0]
    (got,) = by_layer["Mech.13"]
    assert got.kind == "line" and got.width == line.width
    assert all(near(a, imported_point(b)) for a, b in zip(got.points, line.points, strict=True))
    assert [g.kind for g in by_layer["Mech.14"]] == ["line"] * 4  # the rectangle's four sides
    assert [g.kind for g in by_layer["Mech.15"]] == ["line"] * 3  # the drawn polygon, closed
    (circle,) = by_layer["B.SilkS"]
    assert circle.kind == "circle" and near(circle.points[0], imported_point(at(4, 25)))
    assert abs(circle.points[1].x - circle.points[0].x - 2_000_000) <= 2
    arc, solid = sorted(by_layer["F.SilkS"], key=lambda g: g.kind)
    assert arc.kind == "arc" and {
        tuple(near(p, imported_point(q)) for p, q in zip(order, GRAPHICS[1].points, strict=True))
        for order in (arc.points, arc.points[::-1])
    } >= {(True, True, True)}
    assert solid.kind == "polygon" and solid.filled and solid.width == 0
    assert all(near(a, imported_point(b)) for a, b in zip(solid.points, GRAPHICS[5].points, strict=True))
    (pad,) = by_layer["F.Paste"]
    assert pad.filled and len(pad.points) == 4
    assert {g.layer for g in read} == {IMPORT_LAYERS.get(g.layer, g.layer) for g in GRAPHICS}


def test_region_record_forms() -> None:
    """The plain form holds doubles; the shape-based form 37-byte vertices and the first vertex again."""
    vertices = [(0, 0), (1000, 0), (1000, 500)]
    plain = pcbrecords.region_record(33, vertices)
    shaped = pcbrecords.region_record(33, vertices, shape_based=True)
    assert plain[0] == shaped[0] == 11
    text = b"V7_LAYER=TOPOVERLAY|NAME= |KIND=0|SUBPOLYINDEX=-1|UNIONINDEX=0|ARCRESOLUTION=0.5mil"
    assert text + b"|ISSHAPEBASED=FALSE|CAVITYHEIGHT=0mil\x00" in plain and text in shaped
    assert len(shaped) - len(plain) == 3 * (37 - 16) + 37
    document, _ = read_back(bare_spec(graphics=(GRAPHICS[5],)))
    (region,), (shape,) = document.regions, document.shape_regions
    assert not region.shape_based and shape.shape_based and region.hole_count == 0
    assert shape.closing is not None and (shape.closing.x, shape.closing.y) == (
        shape.outline[0].x,
        shape.outline[0].y,
    )
    assert all(vertex.is_round is False for vertex in shape.outline)
    assert region_points(region.outline) == region_points(shape.outline)
    assert [pcbrecords.v7_layer(i) for i in (1, 3, 32, 39, 56, 69)] == [
        "TOP", "MID2", "BOTTOM", "PLANE1", "KEEPOUT", "MECHANICAL13",
    ]  # fmt: skip
    with pytest.raises(ValueError, match="at least three vertices"):
        pcbrecords.region_record(33, vertices[:2])


def test_keepout_with_two_restrictions() -> None:
    """Scenario "Keep-out with two restrictions": one keep-out region for tracks and vias on all copper."""
    wanted = keepout(no_tracks=True, no_vias=True)
    document, design = read_back(bare_spec(copper_layers=LAYERS, keepouts=(wanted,)))
    (region,), (shape,) = document.regions, document.shape_regions
    for record in (region, shape):
        assert record.prefix.layer == pcbrecords.KEEPOUT_LAYER and record.prefix.flags2 == 2
        assert record.properties.get("KEEPOUTRESTRICTIONS") == "3"
        assert record.properties.get("V7_LAYER") == "KEEPOUT"
        # both keys since the decision of 2026-10-06: the saved key in its place, then KiCad's
        assert [key for key, _ in record.properties.fields[-3:]] == [
            "CAVITYHEIGHT",
            "KEEPOUTRESTRICTIONS",
            "KEEPOUTRESTRIC",
        ]
        assert record.properties.get("KEEPOUTRESTRIC") == record.properties.get("KEEPOUTRESTRICTIONS")
    assert (
        int(region.properties.text("KEEPOUTRESTRICTIONS"))
        == KEEPOUT_BITS["no_tracks"] | KEEPOUT_BITS["no_vias"]
    )
    points = region_points(region.outline)
    assert len(points) == 4 and all(near(a, imported_point(b)) for a, b in zip(points, RECT, strict=True))
    assert design.board is not None  # the import has no keep-out: it shows the region on the keep-out layer
    assert [g.layer for g in design.board.graphics if g.layer != "Edge.Cuts"] == ["Altium.KeepOut"]


def test_keepout_restriction_bits() -> None:
    assert dict(KEEPOUT_BITS) == {"no_vias": 1, "no_tracks": 2, "no_copper_pour": 4, "no_pads": 24}
    every = keepout(no_tracks=True, no_vias=True, no_pads=True, no_copper_pour=True, no_footprints=True)
    assert keepout_restrictions(every) == 31
    assert keepout_restrictions(keepout(no_pads=True)) == 24
    assert keepout_restrictions(keepout(no_footprints=True)) == 0


def test_keepout_on_some_copper_layers_is_one_region_per_layer() -> None:
    wanted = keepout(layers=("In1.Cu", "F.Cu"), no_copper_pour=True)
    document, _ = read_back(bare_spec(copper_layers=LAYERS, keepouts=(wanted,)))
    assert [(r.prefix.layer, r.prefix.flags2) for r in document.regions] == [(1, 2), (2, 2)]
    assert [r.properties.get("V7_LAYER") for r in document.regions] == ["TOP", "MID1"]
    assert {r.properties.get("KEEPOUTRESTRICTIONS") for r in document.shape_regions} == {"4"}
    assert {r.properties.get("KEEPOUTRESTRIC") for r in document.regions} == {"4"}
    two = keepout(layers=("F.Cu", "B.Cu"), no_tracks=True)  # every copper layer of a two-layer board
    document, _ = read_back(bare_spec(keepouts=(two,)))
    assert [r.prefix.layer for r in document.regions] == [pcbrecords.KEEPOUT_LAYER]


@pytest.mark.parametrize(
    ("item", "message"),
    [
        (graphic("a", "line", "F.Cu", (at(1, 1), at(2, 2))), "the layer F.Cu has no layer in the document"),
        (graphic("b", "line", "F.Fab", (at(1, 1), at(2, 2)), width=0), "needs a positive width"),
        (graphic("c", "line", "F.Fab", (at(1, 1), at(1, 1))), "the line has no extent"),
        (graphic("d", "arc", "F.Fab", (at(1, 1), at(2, 2), at(3, 3))), "lie on one line"),
        (graphic("e", "polygon", "F.Fab", (at(1, 1), at(2, 2))), "a polygon of 2 points"),
        (graphic("f", "circle", "F.Fab", (at(1, 1), at(2, 1)), filled=True), "a filled circle has no record"),
        (graphic("g", "rect", "F.Fab", (at(1, 1), at(1, 2))), "the rect has no area"),
    ],
)
def test_graphics_the_writer_refuses(item: Graphic, message: str) -> None:
    assert message in (graphic_problem(item) or "")
    with pytest.raises(ValueError, match=f"{item.id}: "):
        write_pcbdoc(bare_spec(graphics=(item,)))


@pytest.mark.parametrize(
    ("item", "message"),
    [
        (keepout(), "sets no restriction that the record carries"),
        (keepout(no_footprints=True), "sets no restriction that the record carries"),
        (keepout(layers=(), no_tracks=True), "names no layer"),
        (keepout(layers=("In9.Cu",), no_tracks=True), "In9.Cu is not a copper layer of the board"),
        (dataclasses.replace(keepout(no_tracks=True), outline=RECT[:2]), "fewer than three points"),
    ],
)
def test_keepouts_the_writer_refuses(item: Keepout, message: str) -> None:
    assert message in (keepout_problem(item, LAYERS) or "")
    with pytest.raises(ValueError, match="kpo_k: "):
        write_pcbdoc(bare_spec(copper_layers=LAYERS, keepouts=(item,)))


def test_the_outline_stays_as_written_before() -> None:
    """Graphics and keep-outs add records; the outline of the board record and every older storage keep
    their bytes."""
    from fenolite.backends.altium.read.pcb import read_pcbdoc

    spec, _model = blink_pcbdoc_spec()
    assert isinstance(spec, PcbDocSpec)
    plain = read_pcbdoc(write_pcbdoc(spec, filename="blink.PcbDoc"), strict=True)
    corner = spec.outline[0]
    triangle = (corner, Point(corner.x + 10**6, corner.y), Point(corner.x, corner.y + 10**6))
    items = (graphic("solid", "polygon", "F.SilkS", triangle, width=0, filled=True),)
    more = read_pcbdoc(
        write_pcbdoc(dataclasses.replace(spec, graphics=items), filename="blink.PcbDoc"), strict=True
    )
    assert plain.board.outline == more.board.outline and plain.regions == () and len(more.regions) == 1
    for name in ("pads", "tracks", "arcs", "vias", "texts", "polygons", "nets", "components"):
        assert [r.raw for r in getattr(plain, name)] == [r.raw for r in getattr(more, name)], name

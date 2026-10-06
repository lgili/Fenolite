# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Free primitives of a PCB document (capability altium-import, "Tracks, arcs and vias", "Zones from
polygons" and "Outline, graphics and texts"; change c0043)."""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

import _altium_records as rec
from _altium_copper import routed_model

from fenolite.backends.altium.adapter import import_board
from fenolite.backends.altium.adapter.copper import layer_of_text
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.core.coords import Point, Size
from fenolite.core.errors import Issue
from fenolite.geometry.shapes import Arc as GeometryArc
from fenolite.model.board import Board
from fenolite.model.design import Design

DATA = Path(__file__).resolve().parents[5] / "tests" / "data" / "altium"
MIL = rec.MIL
FOUR = (1, 2, 3, 32)


def board_of(issues: list[Issue] | None = None, **parts: object) -> Board:
    chain = parts.pop("chain", (1, 32))
    document = rec.document(rec.board(chain), **parts)  # type: ignore[arg-type]
    design = import_board(document, file="a.PcbDoc", sha256=rec.SHA, issues=issues)
    assert design.board is not None
    return design.board


def routed() -> Design:
    data = (DATA / "routed" / "routed.PcbDoc").read_bytes()
    return import_board(read_pcbdoc(data), file="routed.PcbDoc", sha256=hashlib.sha256(data).hexdigest())


def pairs(entity: object) -> dict[str, str]:
    ext = entity.ext  # type: ignore[attr-defined]
    return dict(ext["altium"].payload) if ext else {}


def free(board: Board) -> list[object]:
    return [g for g in board.graphics if g.layer != "Edge.Cuts"]


# --- tracks, arcs, vias ---------------------------------------------------------------------------------


def test_track_on_copper_with_its_net() -> None:
    board = board_of(nets=["A"], tracks=[rec.track((100 * MIL, 200 * MIL), (300 * MIL, 200 * MIL), net=0)])
    (track,) = board.tracks
    assert (track.start, track.end) == (Point(2_540_000, -5_080_000), Point(7_620_000, -5_080_000))
    assert (track.width, track.layer) == (254_000, "F.Cu") and track.net_id is not None
    assert track.provenance is not None and track.provenance.locator == "Tracks6/Data#0"


def test_track_with_a_polygon_index_is_poured_copper() -> None:
    issues: list[Issue] = []
    board = board_of(
        issues, tracks=[rec.track((0, 0), (9, 0), polygon=0)], arcs=[rec.arc((0, 0), 9, 0.0, 90.0, polygon=0)]
    )
    assert board.tracks == () and board.arcs == () and free(board) == []
    (unmapped,) = [i for i in issues if i.code == "altium.import.unmapped"]
    assert "pour-primitives 2" in unmapped.message


def test_track_and_via_without_size_are_bad_geometry() -> None:
    issues: list[Issue] = []
    board = board_of(
        issues,
        tracks=[rec.track((0, 0), (9, 0), width=0)],
        vias=[rec.via((0, 0), hole=0), rec.via((0, 0), diameter=0)],
        arcs=[rec.arc((0, 0), 0, 0.0, 90.0)],
    )
    assert (board.tracks, board.vias, board.arcs) == ((), (), ())
    found = [i for i in issues if i.code == "altium.import.bad-geometry"]
    assert len(found) == 4 and {i.severity for i in found} == {"warning"}


def test_arc_on_copper_keeps_three_points() -> None:
    board = board_of(nets=["A"], arcs=[rec.arc((100 * MIL, 100 * MIL), 100 * MIL, 0.0, 90.0, net=0)])
    (arc,) = board.arcs
    assert (arc.start, arc.end) == (Point(5_080_000, -2_540_000), Point(2_540_000, -5_080_000))
    assert arc.mid == Point(4_336_051, -4_336_051) and arc.layer == "F.Cu" and arc.net_id is not None
    assert GeometryArc(arc.start, arc.mid, arc.end).radius2 is not None


def test_full_circle_on_copper_is_a_circle_graphic_with_its_net() -> None:
    board = board_of(nets=["A"], arcs=[rec.arc((0, 0), 100 * MIL, 0.0, 360.0, net=0)])
    assert board.arcs == ()
    (circle,) = free(board)
    assert circle.kind == "circle" and circle.layer == "F.Cu"  # type: ignore[attr-defined]
    assert circle.points == (Point(0, 0), Point(2_540_000, 0))  # type: ignore[attr-defined]
    assert pairs(circle) == {"net": "A"}


def test_via_span_and_type() -> None:
    board = board_of(
        chain=FOUR,
        vias=[rec.via((0, 0)), rec.via((0, 0), start=1, end=2), rec.via((0, 0), start=3, end=2),
              rec.via((0, 0), start=32, end=1)],
    )  # fmt: skip
    assert [(via.layers, via.via_type) for via in board.vias] == [
        (("F.Cu", "B.Cu"), "through"),
        (("F.Cu", "In1.Cu"), "blind"),
        (("In1.Cu", "In2.Cu"), "buried"),
        (("F.Cu", "B.Cu"), "through"),
    ]
    assert (board.vias[0].diameter, board.vias[0].drill) == (1_270_000, 711_200)


def test_via_layer_outside_the_chain() -> None:
    issues: list[Issue] = []
    board = board_of(issues, vias=[rec.via((0, 0), start=1, end=5)])
    (via,) = board.vias
    assert (via.layers, via.via_type) == (("F.Cu", "B.Cu"), "through") and pairs(via) == {"via_layers": "1,5"}
    assert [i.where for i in issues if i.code == "altium.import.via-span"] == ["Vias6/Data#0"]


def test_routed_sample_copper_equals_its_model() -> None:
    mine, model = routed(), routed_model()
    assert mine.board is not None and model.board is not None
    board, want = mine.board, model.board
    assert (len(board.tracks), len(board.arcs), len(board.vias)) == (
        len(want.tracks),
        len(want.arcs),
        len(want.vias),
    )
    name = {n.id: n.name for n in mine.circuit.nets}
    theirs = {n.id: n.name for n in model.circuit.nets}
    vias = sorted(want.vias, key=lambda v: (v.position.x, v.position.y))
    first = sorted(board.vias, key=lambda v: (v.position.x, v.position.y))[0]
    dx, dy = first.position.x - vias[0].position.x, first.position.y - vias[0].position.y

    def near(a: Point, b: Point) -> bool:
        return abs(a.x - b.x - dx) <= 2 and abs(a.y - b.y - dy) <= 2

    for track in board.tracks:
        assert any(
            t.layer == track.layer and theirs.get(t.net_id or "") == name.get(track.net_id or "")
            and abs(t.width - track.width) <= 2 and near(track.start, t.start) and near(track.end, t.end)
            for t in want.tracks
        ), track  # fmt: skip
    for arc in board.arcs:
        # The writer stores an arc counter-clockwise in Altium's frame, so its ends may come back swapped.
        ends = [
            a
            for a in want.arcs
            if a.layer == arc.layer
            and theirs.get(a.net_id or "") == name.get(arc.net_id or "")
            and abs(a.width - arc.width) <= 2
            and (
                (near(arc.start, a.start) and near(arc.end, a.end))
                or (near(arc.start, a.end) and near(arc.end, a.start))
            )
        ]
        assert len(ends) == 1, arc
        assert abs(arc.mid.x - ends[0].mid.x - dx) <= 100 and abs(arc.mid.y - ends[0].mid.y - dy) <= 100
    for via in board.vias:
        assert any(
            theirs.get(v.net_id or "") == name.get(via.net_id or "") and abs(v.diameter - via.diameter) <= 2
            and abs(v.drill - via.drill) <= 2 and near(via.position, v.position)
            and tuple(v.layers) == via.layers
            for v in want.vias
        ), via  # fmt: skip


# --- zones ----------------------------------------------------------------------------------------------


def test_layer_texts() -> None:
    assert [layer_of_text(t) for t in ("TOP", "BOTTOM", "MID1", "mid30", "PLANE1", "PLANE16")] == [
        1, 32, 2, 31, 39, 54,
    ]  # fmt: skip
    assert [layer_of_text(t) for t in ("MID", "MID31", "TOPOVERLAY", "MULTILAYER", "", None, "TOP1")] == [
        None
    ] * 7


def test_unpoured_zones_of_the_routed_sample() -> None:
    mine, model = routed(), routed_model()
    assert mine.board is not None and model.board is not None
    name = {n.id: n.name for n in mine.circuit.nets}
    theirs = {n.id: n.name for n in model.circuit.nets}
    (source,) = model.board.zones
    zones = mine.board.zones
    assert sorted(z.layers for z in zones) == sorted((layer,) for layer in source.layers)
    width = max(p.x for p in source.outline) - min(p.x for p in source.outline)
    for zone in zones:
        assert name[zone.net_id or ""] == theirs[source.net_id or ""] and zone.fills == () and not zone.filled
        assert len(zone.outline) == len(source.outline)
        assert abs(max(p.x for p in zone.outline) - min(p.x for p in zone.outline) - width) <= 2
        assert zone.native_ids == {} and "pour_index" in pairs(zone)
    assert len({zone.id for zone in zones}) == 2


def test_the_zone_poured_first_has_the_highest_priority() -> None:
    board = board_of(
        nets=["A"],
        polygons=[
            rec.polygon(pour_index=2, name="late"),
            rec.polygon(pour_index=0, name="first", net_index=0),
        ],
    )
    by_name = {zone.name: zone for zone in board.zones}
    assert (by_name["first"].priority, by_name["late"].priority) == (2, 0)
    assert pairs(by_name["late"]) == {"pour_index": "2", "hatch_style": "Solid"}
    assert by_name["first"].net_id is not None and by_name["late"].net_id is None
    assert by_name["first"].outline == (
        Point(2_540_000, -2_540_000),
        Point(22_860_000, -2_540_000),
        Point(22_860_000, -17_780_000),
        Point(2_540_000, -17_780_000),
    )


def test_zone_with_a_unique_id_has_a_native_id() -> None:
    board = board_of(polygons=[rec.polygon(extra={"UNIQUEID": "ZONEUID1"})])
    assert board.zones[0].native_ids == {"altium": "zone:ZONEUID1"}


def test_outline_with_an_arc_vertex() -> None:
    issues: list[Issue] = []
    board = board_of(issues, nets=["A"], polygons=[rec.polygon(net_index=0, extra={"KIND1": "1"})])
    (zone,) = board.zones
    assert zone.outline == () and zone.net_id is not None and zone.layers == ("F.Cu",)
    (found,) = [i for i in issues if i.code == "altium.import.zone-arc"]
    assert found.message.startswith("1 zone(s)") and found.severity == "info"


def test_unreadable_length_text() -> None:
    issues: list[Issue] = []
    board = board_of(issues, polygons=[rec.polygon(extra={"VX0": "abc"})])
    assert board.zones == ()
    (bad,) = [i for i in issues if i.code == "altium.import.bad-length"]
    assert bad.where == "Polygons6/Data#0" and bad.severity == "warning"
    (unmapped,) = [i for i in issues if i.code == "altium.import.unmapped"]
    assert "polygons 1" in unmapped.message


def test_other_polygon_types_and_layers_are_unmapped() -> None:
    issues: list[Issue] = []
    polygons = [
        rec.polygon(polygon_type="Split Plane"),
        rec.polygon(layer="MID1"),
        rec.polygon(layer="TOPOVERLAY"),
    ]
    board = board_of(issues, polygons=polygons)
    assert board.zones == ()
    assert "polygons 3" in next(i.message for i in issues if i.code == "altium.import.unmapped")


def test_regions_of_a_polygon_are_its_fills() -> None:
    issues: list[Issue] = []
    square = [
        (100.0 * MIL, 100.0 * MIL),
        (200.0 * MIL, 100.0 * MIL),
        (200.0 * MIL, 200.0 * MIL),
        (100.0 * MIL, 200.0 * MIL),
    ]
    board = board_of(
        issues,
        polygons=[rec.polygon()],
        regions=[rec.region(square, polygon=0, holes=2), rec.region([*square, square[0]], polygon=0)],
        tracks=[rec.track((0, 0), (9, 0), polygon=0)],
    )
    (zone,) = board.zones
    assert zone.filled and len(zone.fills) == 2 and free(board) == []
    assert zone.fills[0].layer == "F.Cu" and zone.fills[0].polygon == zone.fills[1].polygon
    assert zone.fills[0].polygon[0] == Point(2_540_000, -2_540_000) and len(zone.fills[0].polygon) == 4
    message = next(i.message for i in issues if i.code == "altium.import.unmapped")
    assert "region-holes 2" in message and "pour-primitives 1" in message


# --- outline, graphics, texts ---------------------------------------------------------------------------


def test_outline_of_the_blink_sample() -> None:
    data = (DATA / "blink" / "blink.PcbDoc").read_bytes()
    design = import_board(read_pcbdoc(data), file="blink.PcbDoc", sha256=hashlib.sha256(data).hexdigest())
    board = design.board
    assert board is not None and board.outline is None
    edge = [g for g in board.graphics if g.layer == "Edge.Cuts"]
    assert [g.kind for g in edge] == ["line"] * 4 and {g.width for g in edge} == {0}
    for this, following in zip(edge, [*edge[1:], edge[0]], strict=True):
        assert this.points[1] == following.points[0]
    xs = [p.x for g in edge for p in g.points]
    ys = [p.y for g in edge for p in g.points]
    assert abs(max(xs) - min(xs) - 50_000_000) <= 2 and abs(max(ys) - min(ys) - 30_000_000) <= 2
    assert [i for i in design.validate() if i.severity == "error"] == []
    assert pairs(board)["origin"] == "1000mil,1000mil"


def test_outline_arc_vertex_and_zero_length_segment() -> None:
    extra = {
        "KIND1": "1", "CX1": "1000mil", "CY1": "100mil", "R1": "100mil",
        "SA1": " 2.70000000000000E+0002", "EA1": rec.ZERO,
    }  # fmt: skip
    record = rec.board(outline=((0, 0), (1000, 0), (1100, 100), (1100, 100), (0, 100)), extra=extra)
    board = board_of_record(record)
    edge = [g for g in board.graphics if g.layer == "Edge.Cuts"]
    assert [g.kind for g in edge] == ["line", "arc", "line", "line"]
    arc = edge[1]
    assert arc.points[0] == Point(25_400_000, 0) and arc.points[2] == Point(27_940_000, -2_540_000)
    assert arc.provenance is not None and arc.provenance.locator == "Board6/Data#0:V1"


def board_of_record(record: object) -> Board:
    design = import_board(rec.document(record), file="a.PcbDoc", sha256=rec.SHA)  # type: ignore[arg-type]
    assert design.board is not None
    return design.board


def test_free_graphics_off_copper() -> None:
    board = board_of(
        tracks=[rec.track((0, 0), (100 * MIL, 0), layer=33)],
        arcs=[
            rec.arc((0, 0), 100 * MIL, 0.0, 90.0, layer=34),
            rec.arc((0, 0), 50 * MIL, 0.0, 360.0, layer=57),
        ],
        fills=[
            rec.fill((0, 0), (100 * MIL, 50 * MIL)),
            rec.fill((0, 0), (100 * MIL, 50 * MIL), rotation=90.0),
            rec.fill((0, 0), (100 * MIL, 100 * MIL), rotation=45.0),
        ],
        regions=[rec.region([(0, 0), (100 * MIL, 0), (0, 100 * MIL)], layer=56)],
    )
    found = free(board)
    assert [(g.kind, g.layer, g.filled) for g in found] == [  # type: ignore[attr-defined]
        ("line", "F.SilkS", False),
        ("arc", "B.SilkS", False),
        ("circle", "Mech.1", False),
        ("rect", "F.SilkS", True),
        ("rect", "F.SilkS", True),
        ("polygon", "F.SilkS", True),
        ("polygon", "Altium.KeepOut", True),
    ]
    assert board.keepouts == () and board.zones == ()
    assert found[3].points == (Point(0, 0), Point(2_540_000, -1_270_000))  # type: ignore[attr-defined]
    turned = found[4].points  # type: ignore[attr-defined]
    assert {abs(turned[0].x - turned[1].x), abs(turned[0].y - turned[1].y)} == {1_270_000, 2_540_000}
    assert len(found[5].points) == 4 and all(not pairs(g) for g in found)  # type: ignore[attr-defined]


def test_copper_region_with_a_net() -> None:
    issues: list[Issue] = []
    board = board_of(
        issues,
        nets=["GND"],
        regions=[rec.region([(0, 0), (100 * MIL, 0), (0, 100 * MIL)], layer=1, net=0)],
        fills=[rec.fill((0, 0), (9 * MIL, 9 * MIL), layer=32)],
    )
    fill, region = free(board)
    assert (region.kind, region.layer, region.filled) == ("polygon", "F.Cu", True)  # type: ignore[attr-defined]
    assert pairs(region) == {"net": "GND"} and pairs(fill) == {} and board.zones == ()
    (found,) = [i for i in issues if i.code == "altium.import.copper-shape"]
    assert found.message.startswith("2 fill(s)")


def test_free_text() -> None:
    text = dataclasses.replace(rec.text("REV A", (100 * MIL, 50 * MIL), layer=33), rotation=90.0)
    board = board_of(texts=[text])
    (found,) = board.texts
    assert (found.text, found.position, found.layer) == ("REV A", Point(2_540_000, -1_270_000), "F.SilkS")
    assert (found.size, found.thickness, found.rotation) == (Size(1_524_000, 1_524_000), 152_400, 90_000_000)

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rule areas of a footprint in KiCad files (change c0411, kicad-file-backend "Footprint rule areas").

A library footprint holds its keep-out zones relative to its origin; a board holds a footprint's zones in
the board's frame (KiCad 10.0.6, ``docs/formats/kicad/board.md``). The model holds them in the pad frame.
"""

from __future__ import annotations

import dataclasses

import pytest

from fenolite.backends.kicad.embed import local_footprint, place_footprint
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.mod import board_footprints, read_footprint, write_footprint
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.coords import Point
from fenolite.model.board import FootprintInstance, Keepout, placed_keepout, rule_areas
from fenolite.model.circuit import Circuit, Component
from fenolite.model.design import Design

MM = 1_000_000

LIBRARY = """(footprint "KO" (version 20260206) (generator "pcbnew") (generator_version "10.0")
 (layer "F.Cu")
 (property "Reference" "REF**" (at 0 -3 0) (layer "F.SilkS") (uuid "a1a1a1a1-0000-4000-8000-000000000001")
  (effects (font (size 1 1) (thickness 0.15))))
 (property "Value" "KO" (at 0 3 0) (layer "F.Fab") (uuid "a1a1a1a1-0000-4000-8000-000000000002")
  (effects (font (size 1 1) (thickness 0.15))))
 (attr smd)
 (pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu" "F.Mask") (uuid "a1a1a1a1-0000-4000-8000-000000000003"))
 (zone (layer "F.Cu") (uuid "a1a1a1a1-0000-4000-8000-000000000004") (name "under") (hatch edge 0.5)
  (connect_pads (clearance 0)) (min_thickness 0.25)
  (keepout (tracks not_allowed) (vias not_allowed) (pads allowed) (copperpour not_allowed)
   (footprints allowed))
  (fill (thermal_gap 0.5) (thermal_bridge_width 0.5))
  (polygon (pts (xy 1 0) (xy 3 0) (xy 3 2) (xy 1 2))))
)
"""

AREA = Keepout(
    id="kpo_x",
    outline=(Point(1 * MM, 0), Point(3 * MM, 0), Point(3 * MM, 2 * MM), Point(1 * MM, 2 * MM)),
    layers=("F.Cu",),
    no_tracks=True,
    no_vias=True,
    no_copper_pour=True,
    name="under",
)


def board(points: str, rotation: int) -> str:
    """A board with one footprint at (50, 50) turned by ``rotation`` degrees whose keep-out zone has
    ``points`` (board coordinates, as KiCad writes them)."""
    return f"""(kicad_pcb (version 20250513) (generator "pcbnew") (generator_version "10.0")
 (general (thickness 1.6)) (paper "A4")
 (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (5 "F.SilkS" user) (25 "Edge.Cuts" user) (35 "F.Fab" user))
 (setup (pad_to_mask_clearance 0))
 (net 0 "")
 (footprint "t:KO" (layer "F.Cu") (uuid "b2b2b2b2-0000-4000-8000-000000000001") (at 50 50 {rotation})
  (property "Reference" "U1" (at 0 -3 {rotation}) (layer "F.SilkS")
   (uuid "b2b2b2b2-0000-4000-8000-000000000002")
   (effects (font (size 1 1) (thickness 0.15))))
  (property "Value" "KO" (at 0 3 {rotation}) (layer "F.Fab") (uuid "b2b2b2b2-0000-4000-8000-000000000003")
   (effects (font (size 1 1) (thickness 0.15))))
  (zone (net 0) (net_name "") (layer "F.Cu") (uuid "b2b2b2b2-0000-4000-8000-000000000004") (hatch edge 0.5)
   (connect_pads (clearance 0)) (min_thickness 0.25)
   (keepout (tracks not_allowed) (vias not_allowed) (pads allowed) (copperpour allowed) (footprints allowed))
   (fill (thermal_gap 0.5) (thermal_bridge_width 0.5))
   (polygon (pts {points}))))
)
"""


ROTATED = board("(xy 50 50) (xy 52 50) (xy 52 52) (xy 50 52)", 90)


def zone_points(text: str) -> list[tuple[str, str]]:
    root = parse(text)
    (fp,) = (root,) if root.name == "footprint" else root.nodes("footprint")
    (zone,) = fp.nodes("zone")
    pts = zone.find("polygon").find("pts")  # type: ignore[union-attr]
    assert pts is not None
    return [(xy.atoms()[0].value, xy.atoms()[1].value) for xy in pts.nodes("xy")]


def footprint_of(text: str) -> FootprintInstance:
    design = read_board(text)
    assert design.board is not None
    (fp,) = design.board.footprints
    return fp


def test_a_library_keep_out_zone_is_a_rule_area_of_the_definition() -> None:
    defn = read_footprint(LIBRARY, library="t")
    (area,) = defn.keepouts
    assert dataclasses.replace(area, id=AREA.id) == AREA
    assert area.id.startswith("kpo_") and not area.no_pads and not area.no_footprints


def test_an_unchanged_library_footprint_keeps_its_zone_and_a_changed_area_is_refused() -> None:
    defn = read_footprint(LIBRARY, library="t")
    assert zone_points(write_footprint(defn, target=10)) == [("1", "0"), ("3", "0"), ("3", "2"), ("1", "2")]
    changed = dataclasses.replace(defn, keepouts=(dataclasses.replace(defn.keepouts[0], no_pads=True),))
    with pytest.raises(LossyWriteError, match="keepouts"):
        write_footprint(changed, target=10)


def test_a_created_library_footprint_writes_its_rule_areas() -> None:
    defn = read_footprint(LIBRARY, library="t")
    created = dataclasses.replace(defn, ext={}, keepouts=(AREA,))
    text = write_footprint(created, target=10)
    (area,) = read_footprint(text, library="t").keepouts
    assert dataclasses.replace(area, id=AREA.id) == AREA
    # after the pads (S-1720)
    heads = [c.name for c in parse(text).children if isinstance(c, Node)]
    assert heads.index("zone") > max(i for i, h in enumerate(heads) if h == "pad")


def test_a_board_holds_a_footprint_zone_in_its_own_frame() -> None:
    fp = footprint_of(ROTATED)
    (area,) = fp.keepouts
    # (50, 50) turned 90 degrees: the board square (50..52, 50..52) is (0, 0)..(-2, 2) in the pad frame
    assert area.outline == (Point(0, 0), Point(0, 2 * MM), Point(-2 * MM, 2 * MM), Point(-2 * MM, 0))
    assert placed_keepout(fp, area).outline == (
        Point(50 * MM, 50 * MM),
        Point(52 * MM, 50 * MM),
        Point(52 * MM, 52 * MM),
        Point(50 * MM, 52 * MM),
    )
    design = read_board(ROTATED)
    assert design.board is not None
    assert rule_areas(design.board) == (placed_keepout(fp, area),)


def test_an_unchanged_board_footprint_keeps_its_zone_bytes() -> None:
    assert zone_points(write_board(read_board(ROTATED), target=10).text) == zone_points(ROTATED)


def test_a_moved_board_footprint_moves_its_zone() -> None:
    design = read_board(ROTATED)
    fp = footprint_of(ROTATED)
    moved = design.replace_entity(dataclasses.replace(fp, position=Point(60 * MM, 40 * MM)))
    text = write_board(moved, target=10).text
    assert zone_points(text) == [("60", "40"), ("62", "40"), ("62", "42"), ("60", "42")]
    assert footprint_of(text).keepouts == fp.keepouts


def test_a_changed_area_of_a_read_board_footprint_is_refused() -> None:
    design = read_board(ROTATED)
    fp = footprint_of(ROTATED)
    area = dataclasses.replace(fp.keepouts[0], no_pads=True)
    with pytest.raises(LossyWriteError) as raised:
        write_board(design.replace_entity(dataclasses.replace(fp, keepouts=(area,))), target=10)
    assert [i.code for i in raised.value.issues] == ["kicad.board.projection-read-only"]


@pytest.mark.parametrize("side", ("top", "bottom"))
def test_a_placed_library_footprint_carries_its_areas_to_the_board(side: str) -> None:
    defn = read_footprint(LIBRARY, library="t")
    part = Component(id="cmp_00000000-0000-4000-8000-000000000001", ref="U1", value="KO")
    at = Point(10 * MM, 20 * MM)
    instance = place_footprint(defn, component=part, at=at, rotation=90_000_000, side=side, key="U1")  # type: ignore[arg-type]
    (area,) = instance.keepouts
    if side == "top":
        assert area.outline == AREA.outline and area.layers == ("F.Cu",)
    else:  # mirrored about local X, on the other copper side
        assert area.outline == tuple(Point(p.x, -p.y) for p in AREA.outline) and area.layers == ("B.Cu",)
    # local (1, 0), mirrored or not, turned 90 degrees and placed at (10, 20)
    assert placed_keepout(instance, area).outline[0] == Point(10 * MM, 19 * MM)
    design = Design.new("placed", seed=1)
    assert design.board is not None
    board_ = dataclasses.replace(design.board, layers=created_layers(2), footprints=(instance,))
    design = dataclasses.replace(design, circuit=Circuit(components=(part,)), board=board_)
    text = write_board(design, target=10).text
    assert zone_points(text)[0] == ("10", "19")  # the board's frame
    assert footprint_of(text).keepouts == instance.keepouts


def test_a_board_footprint_brought_back_to_its_origin_has_local_zone_points() -> None:
    (root,) = parse(ROTATED).nodes("footprint")
    local = local_footprint(root, 90_000_000, "top", [])
    (zone,) = local.nodes("zone")
    pts = zone.find("polygon").find("pts")  # type: ignore[union-attr]
    assert pts is not None
    assert [(xy.atoms()[0].value, xy.atoms()[1].value) for xy in pts.nodes("xy")] == [
        ("0", "0"),
        ("0", "2"),
        ("-2", "2"),
        ("-2", "0"),
    ]


def test_a_board_footprint_read_as_a_definition_round_trips_its_zone() -> None:
    """A definition read from a board keeps the footprint's ``at`` and its zone in the board's frame when it
    is written as read; the footprint file reads the zone back in the footprint's own frame, as the
    writer's check does (``RoyalBlue54L-Feather`` footprint 4 of the public row ``-13``)."""
    (defn,) = board_footprints(ROTATED)
    (area,) = defn.keepouts
    assert area.outline[1] == Point(0, 2 * MM)  # the pad frame of (50, 50) turned 90 degrees
    text = write_footprint(defn, target=10)
    assert zone_points(text) == zone_points(ROTATED)  # the bytes as read
    assert read_footprint(text, library=defn.library).keepouts == defn.keepouts

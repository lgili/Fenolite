# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper items, zones, rule areas, graphics, texts and slots of a board (kicad-file-backend, c0009)."""

from __future__ import annotations

import pytest
from _boards import FIXTURE, SCENARIOS, SQUARE, board, uid, zone

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import parse
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue
from fenolite.model.base import Modeled, Opaque


def test_copper_items_of_the_authored_board() -> None:
    design = read_board(FIXTURE)
    board_ = design.board
    assert board_ is not None
    assert len(board_.tracks) == 3 and len(board_.arcs) == 1
    (via,) = board_.vias
    gnd = design.nets_by_name["GND"]
    assert (via.via_type, via.layers, via.net_id) == ("through", ("F.Cu", "B.Cu"), gnd.id)
    assert (via.diameter, via.drill) == (600_000, 300_000)
    arc = board_.arcs[0]
    assert (arc.start, arc.mid, arc.end) == (Point(30_000_000, 14_200_000), Point(32_000_000, 13_400_000),
                                             Point(34_000_000, 14_200_000))  # fmt: skip


def test_blind_via() -> None:
    design = read_board(SCENARIOS["blind-via"])
    assert design.board is not None
    (via,) = design.board.vias
    assert via.via_type == "blind" and via.layers == ("F.Cu", "In1.Cu")


def test_unknown_via_type() -> None:
    text = board(
        f'(via frob (at 1 1) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net 1) (uuid "{uid(1)}"))'
    )
    with pytest.raises(FormatError, match="frob"):
        read_board(text)


def test_teardrop_zone_stays_opaque() -> None:
    design = read_board(SCENARIOS["teardrop"])
    assert design.board is not None and design.board.zones == () and design.board.keepouts == ()
    root = slotlib.from_ext(design.board.ext["kicad"])
    assert isinstance(root[-1], Opaque) and root[-1].fragment.startswith("(zone ")


def test_zone_with_an_island_fill() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    (zone,) = design.board.zones
    assert (zone.name, zone.layers, zone.priority) == ("GND_B", ("B.Cu",), 0)
    assert zone.net_id == design.nets_by_name["GND"].id
    assert [(f.layer, f.island) for f in zone.fills] == [("B.Cu", False), ("B.Cu", True)]
    assert len(zone.outline) == 4 and zone.outline[0] == Point(5_000_000, 5_000_000)


def test_rule_area() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    (keepout,) = design.board.keepouts
    assert (keepout.no_tracks, keepout.no_vias) == (True, True)
    assert (keepout.no_pads, keepout.no_copper_pour, keepout.no_footprints) == (False, False, False)
    assert keepout.layers == ("F.Cu",) and len(keepout.outline) == 4


@pytest.mark.parametrize("scenario", ["zone-arc", "zone-two-polygons"])
def test_opaque_zone_outline(scenario: str) -> None:
    issues: list[Issue] = []
    design = read_board(SCENARIOS[scenario], issues=issues)
    assert design.board is not None
    (zone,) = design.board.zones
    assert zone.outline == ()
    polygons = [
        s for s in slotlib.from_ext(zone.ext["kicad"]) if isinstance(s, Opaque) and "polygon" in s.fragment
    ]
    assert polygons and all(s.fragment.startswith("(polygon ") for s in polygons)
    assert [i.code for i in issues] == ["kicad.board.zone-outline-opaque"]


def test_ten_format_island_flags() -> None:
    design = read_board(SCENARIOS["island-10"])
    assert design.board is not None
    (zone,) = design.board.zones
    assert [f.island for f in zone.fills] == [True, False]


def test_canonical_children_stay_modelled() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    for track in design.board.tracks:
        slots = slotlib.from_ext(track.ext["kicad"])
        assert all(isinstance(s, Modeled) for s in slots), slots
        assert [s.field for s in slots if isinstance(s, Modeled)] == [
            "start", "end", "width", "layer", "net_id", "native_ids",
        ]  # fmt: skip


def test_non_canonical_spelling() -> None:
    issues: list[Issue] = []
    design = read_board(SCENARIOS["spelling"], issues=issues)
    assert design.board is not None
    (track,) = design.board.tracks
    assert track.start == Point(12_000_000, 0)
    assert slotlib.from_ext(track.ext["kicad"])[0] == Opaque("(start 12.000000 0)", "20241229")
    assert [(i.code, i.severity) for i in issues] == [("kicad.board.kept-opaque", "info")]


def test_graphics_and_their_slots() -> None:
    design = read_board(FIXTURE)
    assert design.board is not None
    kinds = sorted((g.kind, g.layer) for g in design.board.graphics)
    assert kinds == [("circle", "F.SilkS"), *[("line", "Edge.Cuts")] * 4, ("polygon", "F.Fab")]
    circle = next(g for g in design.board.graphics if g.kind == "circle")
    assert circle.width == 120_000 and circle.filled is False
    stroke = [s for s in slotlib.from_ext(circle.ext["kicad"]) if isinstance(s, Opaque)]
    assert [parse(s.fragment).name for s in stroke] == ["stroke"]


def test_wildcard_rule_area_layers() -> None:
    settings = "(tracks not_allowed) (vias allowed) (pads allowed) (copperpour allowed) (footprints allowed)"
    keepout = f"(keepout {settings})"
    text = board(zone(1, net="(net 0)", layer='(layers "*.Cu")', inner=f"{keepout} {SQUARE}"))
    design = read_board(text)
    assert design.board is not None
    (area,) = design.board.keepouts
    assert area.layers == ("F.Cu", "In1.Cu", "B.Cu")
    assert Opaque('(layers "*.Cu")', "20241229") in slotlib.from_ext(area.ext["kicad"])

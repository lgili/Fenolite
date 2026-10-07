# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper items, zones, rule areas, graphics, texts and slots of a board (kicad-file-backend, c0009)."""

from __future__ import annotations

import dataclasses

import pytest
from _boards import FIXTURE, SCENARIOS, SQUARE, board, rt1_problems, uid, zone

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import dumps, parse
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue
from fenolite.model.base import Modeled, Opaque
from fenolite.model.design import Design


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


# --- rule-area names, text justification and dimensions (change c0103) ---------------------------------

AREA = (
    f'(zone (net 0) (net_name "") (layers "F.Cu" "B.Cu") (uuid "{uid(70)}") (name "ANT") (hatch edge 0.5)'
    f" (keepout (tracks not_allowed) (vias allowed) (pads allowed) (copperpour allowed) (footprints allowed))"
    f" {SQUARE})"
)
DIMENSION = (
    f'(dimension (type aligned) (layer "Dwgs.User") (uuid "{uid(80)}") (pts (xy 10 3) (xy 30 3)) (height -2)'
    ' (format (prefix "") (suffix "") (units 3) (units_format 1) (precision 4))'
    " (style (thickness 0.2) (arrow_length 1.27) (text_position_mode 0) (arrow_direction outward)"
    " (extension_height 0.58642) (extension_offset 0.5) (keep_text_aligned yes))"
    f' (gr_text "20.0000 mm" (at 20 -0.15 0) (layer "Dwgs.User") (uuid "{uid(80)}")'
    " (effects (font (size 1.5 1.5) (thickness 0.3)))))"
)


def same_items(design: Design, source: str) -> bool:
    """Whether the zones, texts and dimensions of ``source`` are written back as they were read, and the
    reader's own round trip holds."""

    def found(text: str) -> list[str]:
        root = parse(text)
        return [
            dumps(node, style="compact")
            for node in root.nodes()
            if node.name in ("zone", "gr_text", "dimension")
        ]

    assert rt1_problems(source) == []
    return found(write_board(design, target=9).text) == found(source)


def test_named_rule_area() -> None:
    """Scenario "Named rule area": the name is modelled, and the board is written back as read."""
    text = board(AREA)
    design = read_board(text)
    assert design.board is not None
    (area,) = design.board.keepouts
    assert area.name == "ANT" and area.no_tracks and not area.no_vias
    slots = slotlib.from_ext(area.ext["kicad"])
    names = [slot for slot in slots if isinstance(slot, Modeled) and slot.field == "name"]
    assert len(names) == 1
    assert same_items(design, text)


def test_rule_area_without_a_name() -> None:
    text = board(AREA.replace(' (name "ANT")', ""))
    design = read_board(text)
    assert design.board is not None and design.board.keepouts[0].name == ""
    assert same_items(design, text)


def test_justified_text() -> None:
    """Scenario "Justified text"."""
    item = (
        f'(gr_text "L" (at 5 40 0) (layer "F.SilkS") (uuid "{uid(71)}")'
        " (effects (font (size 1 1) (thickness 0.15)) (justify left bottom)))"
    )
    design = read_board(board(item))
    assert design.board is not None
    (text,) = design.board.texts
    assert (text.h_justify, text.v_justify) == ("left", "bottom")
    assert same_items(design, board(item))
    moved = dataclasses.replace(design.board, texts=(dataclasses.replace(text, h_justify="right"),))
    with pytest.raises(LossyWriteError) as refused:
        write_board(dataclasses.replace(design, board=moved), target=9)
    assert "h_justify" in str(refused.value.issues)
    plain = read_board(board(item.replace(" (justify left bottom)", "")))
    assert plain.board is not None
    assert (plain.board.texts[0].h_justify, plain.board.texts[0].v_justify) == ("center", "center")


def test_dimension_saved_by_kicad() -> None:
    """Scenario "Dimension saved by KiCad": the text of a dimension carries the dimension's uuid."""
    issues: list[Issue] = []
    text = board(DIMENSION)
    design = read_board(text, issues=issues)
    assert design.board is not None
    (dimension,) = design.board.dimensions
    assert (dimension.kind, dimension.layer, dimension.direction) == ("aligned", "Dwgs.User", None)
    assert (dimension.start, dimension.end) == (Point(10_000_000, 3_000_000), Point(30_000_000, 3_000_000))
    assert dimension.offset == -2_000_000 and dimension.native_ids == {"kicad": uid(80)}
    # units 3 is outside the model: the default stays; the other projections are read
    assert (dimension.units, dimension.precision, dimension.width) == ("mm", 4, 200_000)
    assert dimension.size is not None and dimension.size.w == 1_500_000 and dimension.thickness == 300_000
    slots = slotlib.from_ext(dimension.ext["kicad"])
    opaque = [parse(slot.fragment).name for slot in slots if isinstance(slot, Opaque)]
    assert opaque == ["format", "style", "gr_text"]
    assert not [i for i in issues if i.code == "kicad.board.duplicate-uuid"]
    assert same_items(design, text)


def test_dimension_projections_are_read_only() -> None:
    design = read_board(board(DIMENSION))
    assert design.board is not None
    (dimension,) = design.board.dimensions
    changed = dataclasses.replace(design.board, dimensions=(dataclasses.replace(dimension, precision=2),))
    with pytest.raises(LossyWriteError) as refused:
        write_board(dataclasses.replace(design, board=changed), target=9)
    assert "precision" in str(refused.value.issues)
    moved = dataclasses.replace(dimension, offset=3_000_000, end=Point(31_000_000, 3_000_000))
    text = write_board(
        dataclasses.replace(design, board=dataclasses.replace(design.board, dimensions=(moved,))), target=9
    ).text
    assert "(height 3)" in text and "(xy 31 3)" in text


def test_orthogonal_dimension_and_inches() -> None:
    item = DIMENSION.replace("(type aligned)", "(type orthogonal)").replace(
        "(height -2)", "(height -2) (orientation 1)"
    )
    design = read_board(
        board(item.replace("(units 3)", "(units 0)").replace("(precision 4)", "(precision 2)"))
    )
    assert design.board is not None
    (dimension,) = design.board.dimensions
    assert (dimension.kind, dimension.direction) == ("orthogonal", "vertical")
    assert (dimension.units, dimension.precision) == ("in", 2)


@pytest.mark.parametrize(
    "item",
    [
        DIMENSION.replace("(type aligned)", "(type leader)"),
        DIMENSION.replace("(type aligned)", "(type orthogonal)"),  # no orientation
        DIMENSION.replace("(xy 30 3)", "(xy 30 3) (xy 40 3)"),
    ],
)
def test_other_dimensions_stay_opaque(item: str) -> None:
    """Scenario "Other dimension types stay opaque"."""
    issues: list[Issue] = []
    design = read_board(board(item), issues=issues)
    assert design.board is not None and design.board.dimensions == ()
    root = slotlib.from_ext(design.board.ext["kicad"])
    assert [parse(s.fragment).name for s in root if isinstance(s, Opaque)].count("dimension") == 1
    assert not issues
    assert same_items(design, board(item))

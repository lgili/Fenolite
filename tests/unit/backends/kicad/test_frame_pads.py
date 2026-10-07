# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Board-frame pads: positions, rotations, copper entries and holes (capability board-frame: "Board-frame
module", "Board-frame pads", "Pad copper entries", "Pad holes"; change c0028). Hermetic."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _placed import LIBS, Part, design_of, mm, pt

import fenolite.backends.kicad as kicad
from fenolite.backends.base import BoardPad, PadCopper
from fenolite.backends.kicad import frame
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.frame import board_pads, find_pads
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point
from fenolite.geometry import Transform
from fenolite.model import canonical
from fenolite.model.circuit import Component

TWO_LAYER = Path(__file__).resolve().parents[3] / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
DEG = 1_000_000


def _by_number(pads: tuple[BoardPad, ...]) -> dict[str, list[BoardPad]]:
    found: dict[str, list[BoardPad]] = {}
    for pad in pads:
        found.setdefault(pad.number, []).append(pad)
    return found


def test_the_270_degree_case() -> None:
    design = design_of(Part("R1", "Mini_R_0603", 10, 20, 270))
    (one,) = find_pads(design, "R1", 1)
    (two,) = find_pads(design, "R1", "2")
    assert one.position == pt(10, 19.2) and one.rotation == 270 * DEG
    assert two.position == pt(10, 20.8) and two.ref == "R1" and two.side == "top"
    assert one.footprint_id == design.board.footprints[0].id  # type: ignore[union-attr]
    assert one.pad_id == design.board.footprints[0].pads[0].id  # type: ignore[union-attr]


def test_bottom_footprint() -> None:
    bottom = design_of(Part("U1", "Mini_QFP-32_7x7mm_P0.8mm", 50, 50, 0, "bottom"))
    top = design_of(Part("U1", "Mini_QFP-32_7x7mm_P0.8mm", 50, 50, 0, "top"))
    (pad,) = find_pads(bottom, "U1", "1")
    assert pad.position == pt(45.85, 52.8) and pad.side == "bottom"
    assert pad.layers == ("B.Cu", "B.Mask", "B.Paste")
    assert [entry.layer for entry in pad.copper] == ["B.Cu"]
    assert find_pads(top, "U1", "1")[0].position == pt(45.85, 47.2)


def test_pads_sharing_a_number() -> None:
    design = design_of(Part("J1", "Mini_Edge_Cases", 0, 0, path="io/J1"))
    by_path, by_ref = find_pads(design, "io/J1", "1"), find_pads(design, "J1", 1)
    assert by_path == by_ref
    assert [pad.position for pad in by_path] == [pt(-2, 0), pt(2, 0)]
    assert {pad.path for pad in by_path} == {"io/J1"} and {pad.ref for pad in by_path} == {"J1"}


def test_a_path_wins_over_a_reference() -> None:
    design = design_of(Part("R2", "Mini_R_0603", 0, 0, path="R1"), Part("R1", "Mini_R_0603", 10, 0))
    assert find_pads(design, "R1", 1)[0].ref == "R2"


def test_unknown_pad_number_and_component() -> None:
    design = design_of(Part("R1", "Mini_R_0603", 10, 20, 270))
    with pytest.raises(KeyError) as number:
        find_pads(design, "R1", "3")
    assert "R1" in str(number.value) and "1, 2" in str(number.value)
    with pytest.raises(KeyError) as component:
        find_pads(design, "R9", "1")
    assert "R9" in str(component.value) and "R1" in str(component.value)


def test_nets_and_order() -> None:
    design = design_of(
        Part("R1", "Mini_R_0603", 10, 20, nets={"1": "LED_DRV"}),
        Part("D1", "Mini_LED_THT_3mm", 20, 20, nets={"2": "LED_A"}),
    )
    pads = board_pads(design)
    assert [(pad.ref, pad.number) for pad in pads] == [("R1", "1"), ("R1", "2"), ("D1", "1"), ("D1", "2")]
    assert [pad.net for pad in pads] == ["LED_DRV", None, None, "LED_A"]
    assert pads[0].net_id == design.circuit.nets[0].id and pads[1].net_id is None


def test_the_backend_delegates_and_nothing_changes() -> None:
    design = read_board(TWO_LAYER)
    before = canonical.dump_texts(design)
    assert KicadBackend().board_pads(design) == frame.board_pads(design)
    assert KicadBackend().placed_extents(design) == frame.placed_extents(design)
    assert canonical.dump_texts(design) == before
    assert len(board_pads(design)) == sum(len(fp.pads) for fp in design.board.footprints)  # type: ignore[union-attr]


def test_package_reexports() -> None:
    for name in ("board_pads", "find_pads", "placed_extent", "placed_extents"):
        assert getattr(kicad, name) is getattr(frame, name) and name in kicad.__all__
    assert frame.COURTYARD_LAYERS == ("F.CrtYd", "B.CrtYd")


# -- entries


def test_roundrect_pad_entries() -> None:
    design = design_of(Part("R1", "Mini_R_0603", 10, 20))
    (entry,) = find_pads(design, "R1", 1)[0].copper
    assert entry == PadCopper(
        "F.Cu",
        (pt(8.975, 19.75), pt(9.425, 19.75), pt(9.425, 20.25), pt(8.975, 20.25)),
        mm(0.45),
        filled=True,
    )
    assert entry.exact
    xs, ys = [p.x for p in entry.core], [p.y for p in entry.core]
    half = entry.width // 2
    assert (max(xs) + half) - (min(xs) - half) == mm(0.9) and (max(ys) + half) - (min(ys) - half) == mm(0.95)


def test_roundrect_entries_turn_with_the_footprint() -> None:
    design = design_of(Part("R1", "Mini_R_0603", 10, 20, 90))
    (entry,) = find_pads(design, "R1", 1)[0].copper
    # pad 1 sits at (10, 20.8) at 90°; its 0.9 x 0.95 box becomes 0.95 x 0.9
    assert entry.core == (pt(9.75, 20.575), pt(10.25, 20.575), pt(10.25, 21.025), pt(9.75, 21.025))
    assert entry.width == mm(0.45) and entry.filled and entry.exact


def test_entries_of_oval_circle_anchor_and_custom_polygon() -> None:
    pads = _by_number(board_pads(design_of(Part("J1", "Mini_Edge_Cases", 0, 0))))
    oval = pads["2"][0]
    assert [(e.layer, e.core, e.width, e.filled) for e in oval.copper] == [
        (layer, (pt(0, -2.9), pt(0, -2.1)), mm(1.6), False) for layer in ("F.Cu", "B.Cu")
    ]
    disc, triangle = pads["3"][0].copper
    assert (disc.core, disc.width, disc.filled) == ((pt(4, 0),), mm(0.5), False)
    assert (triangle.core, triangle.width, triangle.filled) == (
        (pt(3.5, -0.5), pt(4.5, -0.5), pt(4, 0.5)),
        0,
        True,
    )
    assert triangle.exact and disc.exact
    assert pads[""][0].kind == "np_thru_hole" and pads[""][0].copper == ()


def test_padstack_layers() -> None:
    pads = _by_number(board_pads(design_of(Part("J1", "Mini_Edge_Cases", 0, 0), copper=4)))
    entries = {entry.layer: entry for entry in pads["4"][0].copper}
    assert list(entries) == ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
    assert (entries["F.Cu"].core, entries["F.Cu"].width) == ((pt(-4, 0),), mm(1.7))
    assert entries["In1.Cu"].width == entries["In2.Cu"].width == mm(1.2)
    assert entries["In1.Cu"].core == (pt(-4, 0),)
    assert entries["B.Cu"].core == (pt(-4.75, -0.75), pt(-3.25, -0.75), pt(-3.25, 0.75), pt(-4.75, 0.75))
    assert entries["B.Cu"].filled and entries["B.Cu"].width == 0 and entries["B.Cu"].exact


def test_entries_follow_a_30_degree_placement_within_half_a_nanometre() -> None:
    design = design_of(Part("D1", "Mini_LED_THT_3mm", 7, 3, 30))
    (pad,) = find_pads(design, "D1", 1)
    (front, back) = pad.copper
    assert front.core == back.core and len(front.core) == 4 and front.filled and front.width == 0
    # a 1.8 mm square: every side is 1.8 mm long within the rounding of two corners
    ring = front.core
    for a, b in zip(ring, ring[1:] + ring[:1], strict=True):
        length2 = (a.x - b.x) ** 2 + (a.y - b.y) ** 2
        assert abs(length2 - mm(1.8) ** 2) <= 4 * mm(1.8)
    assert sorted(ring) == sorted(set(ring)) and ring[0] == min(ring)


# -- holes


def test_round_and_oval_holes() -> None:
    pads = _by_number(board_pads(design_of(Part("J1", "Mini_Edge_Cases", 0, 0))))
    assert (pads["2"][0].hole, pads["2"][0].drill) == ((pt(0, -2.9), pt(0, -2.1)), mm(0.8))
    assert (pads["4"][0].hole, pads["4"][0].drill) == ((pt(-4, 0),), mm(1))
    assert (pads[""][0].hole, pads[""][0].drill) == ((pt(0, 2),), mm(1.2))
    assert all((pad.hole, pad.drill) == ((), None) for pad in pads["1"])


def test_holes_turn_with_the_footprint() -> None:
    pads = _by_number(board_pads(design_of(Part("J1", "Mini_Edge_Cases", 10, 10, 90))))
    # local (0, -2.5) at 90° is (-2.5, 0); the slot along Y becomes a slot along X
    assert pads["2"][0].position == pt(7.5, 10)
    assert pads["2"][0].hole == (Point(mm(7.1), mm(10)), Point(mm(7.9), mm(10)))


# -- the offset of a pad's drill (change c0068, ``H-G-FRAME-OFFSET``)


def _box(entry: PadCopper) -> tuple[Point, Point]:
    xs, ys = [p.x for p in entry.core], [p.y for p in entry.core]
    return Point(min(xs), min(ys)), Point(max(xs), max(ys))


def test_offset_drill_leaves_the_hole_at_the_pad_position() -> None:
    """Scenario "Hole of a pad with an offset drill": KiCad keeps the hole at the pad's ``at``."""
    (pad,) = find_pads(design_of(Part("J1", "Frame_Offset", 10, 10, library="Frame")), "J1", 1)
    assert pad.position == pt(10, 10)
    assert pad.hole == (pt(10, 10),), "hole: the offset of the drill must not move the hole"
    assert pad.drill == mm(0.8)


def test_offset_drill_moves_the_copper() -> None:
    """Scenario "Copper of a pad with an offset drill": the pad's box moved by (0, −0.4 mm)."""
    (pad,) = find_pads(design_of(Part("J1", "Frame_Offset", 10, 10, library="Frame")), "J1", 1)
    assert [entry.layer for entry in pad.copper] == ["F.Cu", "B.Cu"]
    for entry in pad.copper:
        assert entry.filled and entry.width == 0 and entry.exact
        assert _box(entry) == (pt(9, 8.6), pt(11, 10.6)), "copper box: the offset must move the copper"
    (hole,) = pad.hole
    low, high = _box(pad.copper[0])
    assert low.x < hole.x < high.x and low.y < hole.y < high.y


@pytest.mark.parametrize("angle", [90, 180, 270])
def test_offset_turns_with_the_footprint(angle: int) -> None:
    """Scenario "The offset turns with the footprint"."""
    design = design_of(Part("J1", "Frame_Offset", 10, 10, angle, library="Frame"))
    (pad,) = find_pads(design, "J1", 1)
    assert pad.hole == (pt(10, 10),)
    low, high = _box(pad.copper[0])
    centre = Point((low.x + high.x) // 2, (low.y + high.y) // 2)
    assert centre == Transform.placement(pad.position, pad.rotation).apply(Point(0, mm(-0.4)))
    assert (centre.x - 10 * 1_000_000) ** 2 + (centre.y - 10 * 1_000_000) ** 2 == mm(0.4) ** 2


def test_offset_on_the_bottom_side_is_mirrored_with_the_pad() -> None:
    design = design_of(Part("J1", "Frame_Offset", 10, 10, side="bottom", library="Frame"))
    (pad,) = find_pads(design, "J1", 1)
    assert pad.hole == (pt(10, 10),)
    low, high = _box(pad.copper[0])
    assert (high.x - low.x, high.y - low.y) == (mm(2), mm(2))
    centre = Point((low.x + high.x) // 2, (low.y + high.y) // 2)
    assert abs(centre.x - mm(10)) + abs(centre.y - mm(10)) == mm(0.4)


def test_offset_of_an_oval_drill_moves_the_copper_and_not_the_slot() -> None:
    """An oval drill with an offset stays opaque (``drill is None`` in the model); the frame reads it."""
    text = (LIBS / "Frame.pretty" / "Frame_Offset.kicad_mod").read_text(encoding="utf-8")
    old = "(drill 0.8\n\t\t\t(offset 0 -0.4)\n\t\t)"
    assert old in text
    defn = read_footprint(
        text.replace(old, "(drill oval 0.8 1.2\n\t\t\t(offset 0.3 0)\n\t\t)"), library="Frame"
    )
    component = Component(id="cmp_00000000-0000-4000-8000-000000000001", ref="J1")
    placed = place_footprint(defn, component=component, at=pt(10, 10), key="J1")
    base = design_of()
    assert base.board is not None
    design = dataclasses.replace(
        base,
        circuit=dataclasses.replace(base.circuit, components=(component,)),
        board=dataclasses.replace(base.board, footprints=(placed,)),
    )
    (pad,) = board_pads(design)
    assert (pad.hole, pad.drill) == ((pt(10, 9.8), pt(10, 10.2)), mm(0.8))
    assert _box(pad.copper[0]) == (pt(9.3, 9), pt(11.3, 11))


# -- the anchor bench footprint (change c0111)


def test_frame_anchor_footprint_pads() -> None:
    """``Frame_Anchor``: three 1.5 mm x 1 mm pads and one 3 mm x 3 mm pad, all off the origin."""
    pads = _by_number(board_pads(design_of(Part("U1", "Frame_Anchor", 0, 0, library="Frame"))))
    assert {n: [p.position for p in found] for n, found in pads.items()} == {
        "1": [pt(-4, -2)],
        "2": [pt(-4, 0)],
        "3": [pt(-4, 2)],
        "4": [pt(1, 0)],
    }
    for number, size in (("1", (1.5, 1)), ("2", (1.5, 1)), ("3", (1.5, 1)), ("4", (3, 3))):
        (entry,) = pads[number][0].copper
        low, high = _box(entry)
        assert entry.layer == "F.Cu" and entry.filled and entry.width == 0 and entry.exact
        assert (high.x - low.x, high.y - low.y) == (mm(size[0]), mm(size[1]))

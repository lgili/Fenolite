# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Anchor points in a part's frame (capability board-frame, "Anchor points in a part's frame"; change
c0111): ``part_frame`` and ``PartFrame.point`` against the pad records of the board frame. Hermetic."""

from __future__ import annotations

import dataclasses

import pytest
from _placed import Part, definition, design_of, mm, pt

import fenolite.backends.kicad as kicad
from fenolite.backends.kicad import frame
from fenolite.backends.kicad.frame import PartFrame, board_pads, find_pads, part_frame
from fenolite.core.coords import Point
from fenolite.model import canonical
from fenolite.model.board import Side

ANGLES = (0, 90, 180, 270, 30, 45)
SIDES: tuple[Side, ...] = ("top", "bottom")
SWEEP = (("Mini_QFP-32_7x7mm_P0.8mm", "Mini"), ("Frame_Anchor", "Frame"))


def test_part_and_pad_points_on_both_sides() -> None:
    """Scenario "Part and pad points on both sides"."""
    expected = {"bottom": pt(45.85, 52.8), "top": pt(45.85, 47.2)}
    for side in SIDES:
        design = design_of(Part("U1", "Mini_QFP-32_7x7mm_P0.8mm", 50, 50, 0, side))
        from_pad = part_frame(design, "U1", number="1")
        from_part = part_frame(design, "U1")
        assert from_pad.point() == expected[side] == find_pads(design, "U1", "1")[0].position
        assert from_part.point(Point(-4_150_000, -2_800_000)) == expected[side]
        assert from_part.base == Point(0, 0) and from_part.pad_ids == ()
        assert from_pad.base == Point(-4_150_000, -2_800_000), "the pad's position in the library footprint"
        assert from_pad.pad_ids == (find_pads(design, "U1", "1")[0].pad_id,)
        assert (from_pad.at, from_pad.rotation, from_pad.side) == (pt(50, 50), 0, side)
        assert from_pad.footprint_id == design.board.footprints[0].id  # type: ignore[union-attr]


def test_an_offset_turns_and_mirrors_with_the_part() -> None:
    """Scenario "An offset turns and mirrors with the part"."""
    expected = {"top": pt(21, 19), "bottom": pt(19, 19)}
    for side in SIDES:
        design = design_of(Part("U1", "Frame_Anchor", 20, 20, 90, side, library="Frame"))
        assert find_pads(design, "U1", 4)[0].position == pt(20, 19)
        assert part_frame(design, "U1", number="4").point(Point(0, mm(1))) == expected[side]
        assert part_frame(design, "U1", number=4).point(Point(0, mm(1))) == expected[side], "an int number"


@pytest.mark.parametrize(("name", "library"), SWEEP)
def test_every_pad_at_every_angle(name: str, library: str) -> None:
    """Scenario "Every pad at every angle": the map of an anchor is the map of the pads."""
    drawn: dict[str, list[Point]] = {}
    for pad in definition(name, library).pads:
        drawn.setdefault(pad.number, []).append(pad.position)
    checked = 0
    for side in SIDES:
        for angle in ANGLES:
            design = design_of(Part("U1", name, 33, 27, angle, side, library=library))
            whole = part_frame(design, "U1")
            seen: dict[str, int] = {}
            for pad in board_pads(design):
                k = seen.get(pad.number, 0)
                seen[pad.number] = k + 1
                where = (name, side, angle, pad.number, k)
                assert part_frame(design, "U1", number=pad.number, index=k).point() == pad.position, where
                assert whole.point(drawn[pad.number][k]) == pad.position, where
                checked += 1
    assert checked == len(definition(name, library).pads) * len(SIDES) * len(ANGLES)


def test_pads_of_one_number_at_two_positions() -> None:
    """Scenario "Pads of one number at two positions"."""
    design = design_of(Part("J1", "Mini_Edge_Cases", 0, 0, path="io/J1"))
    with pytest.raises(ValueError, match="J1") as error:
        part_frame(design, "J1", number=1)
    assert "'1'" in str(error.value) and "2 pads" in str(error.value)
    assert part_frame(design, "J1", number=1, index=1).point() == pt(2, 0)
    assert part_frame(design, "io/J1", number=1, index=0).point() == pt(-2, 0), "a component path"


def test_unknown_part_pad_and_index() -> None:
    """Scenario "Unknown part"."""
    design = design_of(Part("R1", "Mini_R_0603", 10, 20, 270))
    with pytest.raises(KeyError) as part:
        part_frame(design, "R9")
    assert "R9" in str(part.value) and "R1" in str(part.value)
    with pytest.raises(KeyError) as index:
        part_frame(design, "R1", number=1, index=1)
    message = str(index.value)
    assert "R1" in message and "'1'" in message and "index 1" in message and "1 pad(s)" in message
    with pytest.raises(KeyError) as number:
        part_frame(design, "R1", number="3")
    assert "R1" in str(number.value) and "1, 2" in str(number.value), "the message of find_pads"


def test_reexports_and_purity() -> None:
    assert kicad.part_frame is frame.part_frame and "part_frame" in kicad.__all__
    assert {"PartFrame", "part_frame"} <= set(frame.__all__)
    assert dataclasses.is_dataclass(PartFrame)
    made = PartFrame("fp", pt(1, 2), 0, "top", Point(0, 0))
    with pytest.raises(dataclasses.FrozenInstanceError):
        made.at = pt(0, 0)  # type: ignore[misc]
    assert made.point() == pt(1, 2) and made.pad_ids == ()
    design = design_of(Part("U1", "Frame_Anchor", 20, 20, 30, "bottom", library="Frame"))
    before = canonical.dump_texts(design)
    part_frame(design, "U1", number=4).point(Point(mm(1), mm(1)))
    assert canonical.dump_texts(design) == before

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint field helpers (kicad-file-backend, "Footprint field helpers"; change c0030)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _boards import FIXTURE

import fenolite.backends.kicad as kicad
from fenolite.backends.kicad import fields
from fenolite.backends.kicad.embed import place_footprint
from fenolite.backends.kicad.fields import (
    DEFAULT_GAP,
    EVIDENCE,
    field_anchor,
    field_angle,
    outside_box,
    place_outside,
    set_field,
)
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point, Size
from fenolite.core.evidence import Level
from fenolite.geometry.shapes import BBox
from fenolite.geometry.transform import Transform
from fenolite.model.board import FootprintField, FootprintInstance, Side
from fenolite.model.circuit import Component

DEG = 1_000_000
LIB = Path(__file__).resolve().parents[4] / "tests" / "data" / "libs" / "Mini.pretty"


def footprint(ref: str) -> FootprintInstance:
    design = read_board(FIXTURE)
    assert design.board is not None
    target = design.by_ref[ref].id
    return next(fp for fp in design.board.footprints if fp.component_id == target)


def field(fp: FootprintInstance, name: str) -> FootprintField:
    return next(f for f in fp.fields if f.name == name)


def placed(rotation: int, side: Side, name: str = "Mini_R_0603") -> FootprintInstance:
    defn = read_footprint(LIB / f"{name}.kicad_mod", library="Mini")
    component = Component(id="cmp_00000000-0000-4000-8000-000000000001", ref="R1", value="1k")
    return place_footprint(
        defn, component=component, at=Point(30_000_000, 20_000_000), rotation=rotation, side=side, key="R1"
    )


def test_re_exports() -> None:
    for name in ("field_anchor", "field_angle", "set_field", "place_outside"):
        assert getattr(kicad, name) is getattr(fields, name)
        assert name in kicad.__all__


def test_anchor_and_angle_of_a_rotated_field() -> None:
    r1 = footprint("R1")
    assert (r1.position, r1.rotation) == (Point(20_000_000, 15_000_000), 90 * DEG)
    reference = field(r1, "Reference")
    assert field_anchor(r1, reference) == Point(18_570_000, 15_000_000)
    assert field_angle(r1, reference) == 90 * DEG


def test_anchor_of_a_bottom_field_has_no_further_mirror() -> None:
    d1 = footprint("D1")
    reference = field(d1, "Reference")
    expected = Transform.placement(d1.position, d1.rotation).apply(reference.position)
    assert field_anchor(d1, reference) == expected
    assert field_angle(d1, reference) == 30 * DEG


@pytest.mark.parametrize(
    ("rotation", "side"), [(0, "top"), (30 * DEG, "top"), (90 * DEG, "top"), (30 * DEG, "bottom")]
)
def test_board_frame_round_trip(rotation: int, side: Side) -> None:
    fp = placed(rotation, side)
    reference = field(fp, "Reference")
    again = set_field(fp, "Reference", anchor=field_anchor(fp, reference), angle=field_angle(fp, reference))
    assert again == fp


@pytest.mark.parametrize("rotation", [0, 30 * DEG, 90 * DEG, 180 * DEG, 270 * DEG, 123_456_789])
@pytest.mark.parametrize("side", ["top", "bottom"])
def test_set_anchor_and_angle(rotation: int, side: Side) -> None:
    fp = placed(rotation, side)
    anchor = Point(31_234_567, 18_765_432)
    moved = set_field(fp, "Reference", anchor=anchor, angle=45 * DEG)
    reference = field(moved, "Reference")
    found = field_anchor(moved, reference)
    assert abs(found.x - anchor.x) <= 1 and abs(found.y - anchor.y) <= 1
    assert field_angle(moved, reference) == 45 * DEG
    # setting the anchor it now has changes nothing: no drift over repeated calls
    assert set_field(moved, "Reference", anchor=found, angle=45 * DEG) == moved
    assert [f for f in moved.fields if f.name != "Reference"] == [
        f for f in fp.fields if f.name != "Reference"
    ]
    assert dataclasses.replace(moved, fields=fp.fields) == fp


def test_inverse_placement_is_exact_at_quarter_turns() -> None:
    fp = placed(90 * DEG, "top")
    moved = set_field(fp, "Value", anchor=Point(30_000_000, 17_000_000))
    assert field(moved, "Value").position == Point(3_000_000, 0)
    assert field_anchor(moved, field(moved, "Value")) == Point(30_000_000, 17_000_000)


def test_set_every_value() -> None:
    fp = placed(0, "top")
    changed = set_field(
        fp,
        "Value",
        layer="F.SilkS",
        visible=False,
        size=Size(800_000, 900_000),
        thickness=120_000,
        justify=("left", "top"),
        mirrored=True,
    )
    value = field(changed, "Value")
    assert (value.layer, value.visible, value.size, value.thickness) == (
        "F.SilkS",
        False,
        Size(800_000, 900_000),
        120_000,
    )
    assert (value.h_justify, value.v_justify, value.mirrored) == ("left", "top", True)
    old = field(fp, "Value")
    assert (value.position, value.rotation, value.id, value.ext) == (
        old.position,
        old.rotation,
        old.id,
        old.ext,
    )
    assert set_field(fp, "Value") is fp


def test_unknown_field() -> None:
    with pytest.raises(KeyError, match="MPN"):
        set_field(placed(0, "top"), "MPN", visible=False)
    with pytest.raises(KeyError, match="MPN"):
        place_outside(placed(0, "top"), "MPN", side="top")


def test_outside_on_top_of_a_rotated_part() -> None:
    r1 = footprint("R1")
    assert outside_box(r1) == BBox(19_270_000, 13_520_000, 20_730_000, 16_480_000)
    moved = place_outside(r1, "Reference", side="top")
    reference = field(moved, "Reference")
    assert field_anchor(moved, reference) == Point(20_000_000, 13_195_000)
    assert field_angle(moved, reference) == 0
    assert (reference.h_justify, reference.v_justify) == ("center", "bottom")
    assert (reference.position, reference.rotation) == (Point(1_805_000, 0), 270 * DEG)


def test_mirrored_field_on_the_left() -> None:
    d1 = footprint("D1")
    box = outside_box(d1)
    moved = place_outside(d1, "Reference", side="left")
    reference = field(moved, "Reference")
    assert reference.h_justify == "left" and reference.mirrored
    anchor = field_anchor(moved, reference)
    assert abs(anchor.x - (box.x0 - 325_000)) <= 1
    assert field_angle(moved, reference) == 0
    right = field(place_outside(d1, "Reference", side="right"), "Reference")
    assert right.h_justify == "right"


@pytest.mark.parametrize("side", ["top", "bottom"])
@pytest.mark.parametrize("rotation", [0, 30 * DEG, 90 * DEG])
def test_four_sides(rotation: int, side: Side) -> None:
    fp = placed(rotation, side)
    box = outside_box(fp)
    cx, cy = (box.x0 + box.x1) // 2, (box.y0 + box.y1) // 2
    d = DEFAULT_GAP + 150_000 // 2
    mirrored = side == "bottom"
    expected = {
        "top": (Point(cx, box.y0 - d), "center", "bottom"),
        "bottom": (Point(cx, box.y1 + d), "center", "top"),
        "left": (Point(box.x0 - d, cy), "left" if mirrored else "right", "center"),
        "right": (Point(box.x1 + d, cy), "right" if mirrored else "left", "center"),
    }
    for where, (anchor, h, v) in expected.items():
        moved = place_outside(fp, "Reference", side=where)  # type: ignore[arg-type]
        reference = field(moved, "Reference")
        assert reference.mirrored == mirrored
        found = field_anchor(moved, reference)
        assert abs(found.x - anchor.x) <= 1 and abs(found.y - anchor.y) <= 1, where
        assert (reference.h_justify, reference.v_justify) == (h, v), where
        assert field_angle(moved, reference) == 0
        assert place_outside(moved, "Reference", side=where) == moved  # type: ignore[arg-type]


def test_gap() -> None:
    fp = placed(0, "top")
    box = outside_box(fp)
    assert box == BBox(28_500_000, 19_250_000, 31_500_000, 20_750_000)
    near = field(place_outside(fp, "Reference", side="top", gap=0), "Reference")
    assert field_anchor(fp, near) == Point(30_000_000, 19_250_000 - 75_000)
    far = field(place_outside(fp, "Reference", side="top", gap=1_000_000), "Reference")
    assert field_anchor(fp, far) == Point(30_000_000, 19_250_000 - 1_075_000)
    assert DEFAULT_GAP == 250_000


def test_negative_gap() -> None:
    with pytest.raises(ValueError, match="gap"):
        place_outside(footprint("R1"), "Reference", side="top", gap=-1)
    with pytest.raises(ValueError, match="side"):
        place_outside(footprint("R1"), "Reference", side="north")  # type: ignore[arg-type]


def test_footprint_without_courtyard_or_pads_uses_its_position() -> None:
    fp = dataclasses.replace(placed(0, "top"), pads=(), ext={})
    assert outside_box(fp) == BBox(30_000_000, 20_000_000, 30_000_000, 20_000_000)
    reference = field(place_outside(fp, "Reference", side="bottom"), "Reference")
    assert field_anchor(fp, reference) == Point(30_000_000, 20_325_000)


def test_evidence_stays_inferred() -> None:
    assert EVIDENCE.level is Level.INFERRED
    assert EVIDENCE.hypotheses == ("H-K-FIELD-FRAME", "H-K-FIELD-JUSTIFY", "H-K-FIELD-OUTSIDE")

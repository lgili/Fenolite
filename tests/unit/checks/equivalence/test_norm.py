# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The tolerance and normalisation rules (capability design-equivalence, "Tolerances and normalisation")."""

from __future__ import annotations

import dataclasses

import _cases
import pytest

from fenolite.checks.equivalence import norm
from fenolite.checks.equivalence.levels import level_footprints, level_placement
from fenolite.checks.equivalence.model import EXACT, Tolerances
from fenolite.core.coords import Point, Size
from fenolite.model.board import Pad


def test_angle_wraps() -> None:
    assert norm.angle_distance(359_999_999, 0, 360_000_000) == 1
    assert norm.normalise(-90_000_000) == 270_000_000
    assert norm.angles_equal(-90_000_000, 270_000_000, Tolerances())
    assert not norm.angles_equal(0, 1, Tolerances()) and norm.angles_equal(0, 1, Tolerances(angle_udeg=1))
    assert norm.angle_distance(170_000_000, -10_000_000, 180_000_000) == 0


def test_length_tolerance_is_per_coordinate() -> None:
    a, b = Point(0, 0), Point(10, 10)
    assert norm.points_equal(a, b, Tolerances(length_nm=10))
    assert not norm.points_equal(a, b, Tolerances(length_nm=9))
    assert norm.sizes_equal(Size(5, 5), Size(15, -5), Tolerances(length_nm=10))
    assert not norm.sizes_equal(Size(5, 5), Size(16, 5), Tolerances(length_nm=10))
    assert norm.lengths_equal(3, 3, Tolerances()) and not norm.lengths_equal(3, 4, Tolerances())


@pytest.mark.parametrize("value", [-1, True, "1"])
def test_bad_tolerance(value: object) -> None:
    with pytest.raises(ValueError, match="length_nm"):
        Tolerances(length_nm=value)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="angle_udeg"):
        Tolerances(angle_udeg=value)  # type: ignore[arg-type]


def test_footprint_name_drops_the_library() -> None:
    assert norm.footprint_name("Lib:R_0603") == "R_0603"
    assert norm.footprint_name("a:b:R_0603") == "R_0603"
    assert norm.footprint_name("R_0603") == "R_0603"
    assert norm.footprint_name("") == ""


def test_pad_symmetry_by_shape() -> None:
    exact = Tolerances()
    assert norm.pad_symmetry(_cases.pad("1", shape="circle"), exact) is None
    assert norm.pad_symmetry(_cases.pad("1", shape="oval", size=Size(9, 9)), exact) is None
    assert norm.pad_symmetry(_cases.pad("1", shape="oval", size=Size(9, 12)), exact) == 180_000_000
    assert norm.pad_symmetry(_cases.pad("1", shape="oval", size=Size(9, 12)), Tolerances(length_nm=3)) is None
    for shape in ("rect", "roundrect"):
        assert norm.pad_symmetry(_cases.pad("1", shape=shape), exact) == 180_000_000
    for shape in ("trapezoid", "custom"):
        assert norm.pad_symmetry(_cases.pad("1", shape=shape), exact) == 360_000_000


def _one(pad_a: Pad, pad_b: Pad, tolerances: Tolerances = EXACT) -> list[str]:
    a = _cases.design([("R1", "")], {"R1": [pad_a]})
    b = _cases.design([("R1", "")], {"R1": [pad_b]})
    result, _ = level_footprints(a, b, ["R1"], tolerances)
    return [d.kind for d in result.differences]


def test_rectangular_pad_turned_by_a_quarter() -> None:
    flat = _cases.pad("1", size=Size(1_000_000, 500_000), rotation=0)
    upright = _cases.pad("1", size=Size(500_000, 1_000_000), rotation=90_000_000)
    assert norm.pads_equal_turned(flat, upright, Tolerances())
    assert _one(flat, upright) == []
    assert _one(flat, dataclasses.replace(upright, rotation=-90_000_000)) == []
    assert _one(flat, dataclasses.replace(flat, rotation=45_000_000)) == ["pad-rotation"]
    assert _one(flat, dataclasses.replace(flat, rotation=180_000_000)) == []
    # the turned form needs the quarter turn: swapped sizes at the same angle are another pad
    assert _one(flat, dataclasses.replace(upright, rotation=0)) == ["pad-size"]
    assert _one(flat, dataclasses.replace(upright, rotation=90_000_001)) == ["pad-rotation", "pad-size"]
    assert _one(flat, dataclasses.replace(upright, rotation=90_000_001), Tolerances(angle_udeg=1)) == []


def test_rotation_of_other_shapes() -> None:
    round_a = _cases.pad("1", shape="circle", size=Size(9, 9))
    assert _one(round_a, dataclasses.replace(round_a, rotation=45_000_000)) == []
    custom = _cases.pad("1", shape="custom")
    assert _one(custom, dataclasses.replace(custom, rotation=180_000_000)) == ["pad-rotation"]
    assert not norm.pads_equal_turned(custom, custom, Tolerances())


def test_copper_span_reads_the_board_layers() -> None:
    board = _cases.design([("R1", "")], {"R1": []}).board
    assert board is not None
    assert norm.copper_span(_cases.pad("1", layers=("Top", "Mask")), board) == {"top"}
    assert norm.copper_span(_cases.pad("1", layers=("Top", "Mid", "Bottom")), board) == {
        "top",
        "inner",
        "bottom",
    }
    assert norm.copper_span(_cases.pad("1", layers=("Mask",)), board) == frozenset()
    assert norm.copper_span(_cases.pad("1", layers=("Top", "Nowhere")), board) is None
    assert norm.span_text(frozenset({"bottom", "top"})) == "top,bottom"


def test_translation_is_the_lower_median() -> None:
    assert norm.translation([]) == Point(0, 0)
    pairs = [(Point(0, 0), Point(5, -3)), (Point(1, 1), Point(6, -2)), (Point(2, 2), Point(9, -1))]
    assert norm.translation(pairs) == Point(5, -3)
    assert norm.translation(pairs[:2] + [(Point(0, 0), Point(7, 0)), (Point(0, 0), Point(7, 0))]) == Point(
        5, -3
    )


def test_board_moved_as_a_whole() -> None:
    at = {"R1": Point(0, 0), "R2": Point(10_000_000, 0), "R3": Point(0, 10_000_000)}
    pads = {ref: [_cases.pad("1")] for ref in at}
    parts = [(ref, "") for ref in at]
    a = _cases.design(parts, pads, at)
    moved = {ref: Point(p.x + 5_000_000, p.y - 3_000_000) for ref, p in at.items()}
    moved["R2"] = Point(moved["R2"].x + 1_000_000, moved["R2"].y)
    b = _cases.design(parts, pads, moved)
    _, pairs = level_footprints(a, b, sorted(at))
    relative, shift = level_placement(pairs, frame="relative")
    assert shift == Point(5_000_000, -3_000_000)
    assert relative.summary == {"frame": "relative", "translation": [5_000_000, -3_000_000]}
    assert [(d.kind, d.where) for d in relative.differences] == [("position", "R2")]
    absolute, shift = level_placement(pairs, frame="absolute")
    assert shift == Point(0, 0)
    assert [(d.kind, d.where) for d in absolute.differences] == [("position", ref) for ref in sorted(at)]

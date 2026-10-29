# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawn schematic value (capability design-model, "Drawn schematic value"; change c0276)."""

from __future__ import annotations

import dataclasses

import _drawn
import pytest

from fenolite.core.coords import Point, Size
from fenolite.model.drawn import (
    DrawnField,
    DrawnJunction,
    DrawnLabel,
    DrawnSchematic,
    DrawnSheet,
    DrawnSheetRef,
    DrawnSymbol,
)


def _floats(value: object) -> list[object]:
    """Every float reachable through the fields of ``value``."""
    if isinstance(value, float):
        return [value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return [f for field in dataclasses.fields(value) for f in _floats(getattr(value, field.name))]
    if isinstance(value, (tuple, list)):
        return [f for item in value for f in _floats(item)]  # pyright: ignore[reportUnknownVariableType]
    return []


def test_equality_and_hashing() -> None:
    """Scenario "Equality and hashing"."""
    first, second = _drawn.drawn("full"), _drawn.drawn("full")
    assert first == second and hash(first) == hash(second)
    assert _floats(first) == []
    assert first != _drawn.drawn("flat")


def test_instances_from_paths() -> None:
    """Scenario "Instances from paths"."""
    assert _drawn.drawn("repeat").instances() == (("", "root"), ("ch0", "channel"), ("ch1", "channel"))


def test_a_symbol_names_its_part_by_path() -> None:
    symbol = DrawnSymbol("child/R2", 1, Point(0, 0))
    assert symbol.part == "child/R2" and not hasattr(symbol, "ref")
    with pytest.raises(ValueError, match="rotation"):
        DrawnSymbol("R1", 1, Point(0, 0), 45_000_000)
    with pytest.raises(TypeError):
        DrawnSymbol("R1", 1, Point(0.5, 0))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="field"):
        DrawnField("Reference", Point(0, 0), 180_000_000)
    with pytest.raises(ValueError, match="junction"):
        DrawnJunction(Point(0, 0), -1)
    with pytest.raises(ValueError, match="kind"):
        DrawnLabel("bus", "D", Point(0, 0))  # type: ignore[arg-type]


def test_nested_modules_and_the_same_module() -> None:
    ref = DrawnSheetRef("a", "a", "", "a", Point(0, 0), Size(1, 1), "2")
    deep = DrawnSheetRef("b", "b", "x/y", "b", Point(0, 0), Size(1, 1), "3")
    drawn = DrawnSchematic(
        "root",
        (DrawnSheet("root", sheet_refs=(ref,)), DrawnSheet("a", sheet_refs=(deep,)), DrawnSheet("b")),
    )
    found, cycles, unknown = drawn.walk()
    assert [(i.module, i.sheet, i.path) for i in found] == [
        ("", "root", ""),
        ("", "a", "a"),
        ("x/y", "b", "a/b"),
    ]
    assert cycles == () and unknown == ()
    assert found[2].component("R1") == "x/y/R1" and found[1].component("R1") == "R1"


def test_segments_leave_points_out() -> None:
    sheet = DrawnSheet("root", wires=((Point(0, 0), Point(0, 0), Point(5, 0), Point(5, 5)),))
    assert sheet.segments() == ((Point(0, 0), Point(5, 0)), (Point(5, 0), Point(5, 5)))
    with pytest.raises(ValueError, match="two or more"):
        DrawnSheet("root", wires=((Point(0, 0),),))

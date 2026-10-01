# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Integer vector helpers and the package surface (capability geometry-kernel)."""

from __future__ import annotations

import subprocess
import sys

import pytest
from hypothesis import given
from strategies import small_points

import fenolite.core.coords
import fenolite.geometry as g
from fenolite.geometry import Point, add, cross, dot, neg, norm2, sub


def test_same_point_class() -> None:
    assert g.Point is fenolite.core.coords.Point
    assert g.Size is fenolite.core.coords.Size
    assert g.Vec is g.Point


def test_import_without_extras() -> None:
    code = (
        "import sys; sys.modules['shapely'] = None; sys.modules['pyclipper'] = None\n"
        "import fenolite.geometry, fenolite.geometry.boolean\n"
        "assert 'numpy' not in sys.modules"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_operations() -> None:
    a, b = Point(3, -4), Point(1, 2)
    assert add(a, b) == Point(4, -2)
    assert sub(a, b) == Point(2, -6)
    assert neg(a) == Point(-3, 4)
    assert dot(a, b) == -5
    assert cross(a, b) == 10
    assert norm2(a) == 25


@given(small_points, small_points)
def test_properties(a: Point, b: Point) -> None:
    assert sub(add(a, b), b) == a
    assert cross(a, b) == -cross(b, a)
    assert dot(a, b) == dot(b, a)
    assert norm2(a) == dot(a, a)


@pytest.mark.parametrize("bad", [Point(1.0, 2), Point(1, True), (1, 2)])  # type: ignore[arg-type]
def test_non_int_rejected_naming_argument(bad: object) -> None:
    with pytest.raises(TypeError, match=r"\bv\b"):
        norm2(bad)  # type: ignore[arg-type]


def test_no_float_in_public_api() -> None:
    import inspect

    for name in g.__all__:
        obj = getattr(g, name)
        if inspect.isfunction(obj):
            assert "float" not in str(inspect.signature(obj)), name

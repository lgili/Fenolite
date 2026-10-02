# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""DSL lengths and angles (capability design-dsl, "DSL lengths and angles"; change c0011)."""

from __future__ import annotations

import pytest

from fenolite.dsl import DslError, Length, Part, inch, mil, mm, nm
from fenolite.dsl.units import as_nm, as_udeg


def test_exact_float_conversion() -> None:
    assert (mm(0.1), mil(10), inch("0.5")) == (nm(100_000), nm(254_000), nm(12_700_000))
    assert mm(2.54) == nm(2_540_000) and mm("1.27") == nm(1_270_000) and mm(3) == nm(3_000_000)


def test_inexact_float_refused() -> None:
    with pytest.raises(DslError):
        mm(1 / 3)
    with pytest.raises(DslError):
        mm("0.0000001")


@pytest.mark.parametrize("bad", [True, None, [1], b"1"])
def test_helpers_refuse_other_types(bad: object) -> None:
    with pytest.raises(DslError):
        mm(bad)  # type: ignore[arg-type]


def test_nm_takes_ints_only() -> None:
    with pytest.raises(DslError):
        nm(1.5)  # type: ignore[arg-type]
    with pytest.raises(DslError):
        nm(True)


def test_arithmetic() -> None:
    a, b = mm(1), mm(0.5)
    assert a + b == mm(1.5) and a - b == mm(0.5) and -a == mm(-1)
    assert a * 3 == mm(3) and 3 * a == mm(3) and a // 4 == nm(250_000)
    assert hash(mm(1)) == hash(nm(1_000_000)) and {mm(1), nm(1_000_000)} == {mm(1)}
    with pytest.raises(DslError):
        _ = a * 1.5  # type: ignore[operator]
    with pytest.raises(DslError):
        _ = a + 1  # type: ignore[operator]


def test_bare_numbers_are_refused() -> None:
    with pytest.raises(DslError, match=r"\bx\b"):
        Part("R1", "Mini:Mini_R").place(10, 5)
    with pytest.raises(DslError):
        as_nm("12", name="width")
    with pytest.raises(DslError):
        as_nm(1.5, name="width")


def test_strings_with_units() -> None:
    part = Part("R1", "Mini:Mini_R")
    part.place("2.54mm", "-1.27mm")
    assert part.request is not None and (part.request.x, part.request.y) == (2_540_000, -1_270_000)
    assert as_nm(Length(5), name="x") == 5


def test_angles_are_normalised() -> None:
    rotations = []
    for rot in (-90, "30.5deg", 450, 30.25, "45"):
        part = Part("R1", "Mini:Mini_R")
        part.place(mm(0), mm(0), rot=rot)
        assert part.request is not None
        rotations.append(part.request.rotation)
    assert rotations == [270_000_000, 30_500_000, 90_000_000, 30_250_000, 45_000_000]
    with pytest.raises(DslError):
        as_udeg("1rad", name="rot")
    with pytest.raises(DslError):
        as_udeg(True, name="rot")

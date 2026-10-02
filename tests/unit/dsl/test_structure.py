# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Design structure, names and boards (capability design-dsl; change c0011)."""

from __future__ import annotations

import pytest

from fenolite.core.coords import Point
from fenolite.dsl import Design, DslError, Module, Net, Part, mm, placements, to_model
from fenolite.dsl.convert import BOARD_ORIGIN
from fenolite.dsl.part import Placement


def test_paths_from_modules() -> None:
    d, power, ldo = Design("t"), Module("power"), Module("ldo")
    c1 = Part("C1", "Mini:Mini_R")
    ldo.add(c1)
    power.add(ldo)
    d.add(power)
    assert c1.path == "power/ldo/C1" and ldo.path == "power/ldo" and set(d.parts) == {"power/ldo/C1"}
    late = Part("C2", "Mini:Mini_R")
    ldo.add(late)
    assert "power/ldo/C2" in d.parts


def test_two_nets_with_one_name() -> None:
    d = Design("t")
    d.add(Net("GND"))
    with pytest.raises(DslError, match="GND"):
        d.add(Net("GND"))


def test_same_net_twice_is_fine() -> None:
    d, gnd = Design("t"), Net("GND")
    d.add(gnd, gnd)
    assert d.nets == {"GND": gnd}


def test_placed_twice() -> None:
    r1 = Part("R1", "Mini:Mini_R")
    r1.place(mm(1), mm(1))
    with pytest.raises(DslError):
        r1.place(mm(1), mm(1))


def test_duplicate_paths() -> None:
    d = Design("t")
    d.add(Part("R1", "Mini:Mini_R"))
    with pytest.raises(DslError, match="R1"):
        d.add(Part("R1", "Mini:Mini_R"))
    d.add(Module("m"))
    with pytest.raises(DslError, match="m"):
        d.add(Module("m"))


def test_object_added_twice() -> None:
    d, r = Design("t"), Part("R1", "Mini:Mini_R")
    d.add(r)
    with pytest.raises(DslError):
        d.add(r)


def test_equal_refs_in_two_modules_are_not_a_dsl_error() -> None:
    d, a, b = Design("t"), Module("a"), Module("b")
    a.add(Part("R1", "Mini:Mini_R"))
    b.add(Part("R1", "Mini:Mini_R"))
    d.add(a, b)
    assert sorted(d.parts) == ["a/R1", "b/R1"]


@pytest.mark.parametrize("name", ["my board", "", "-x", "a/b"])
def test_invalid_design_name(name: str) -> None:
    with pytest.raises(DslError, match="must match"):
        Design(name)


@pytest.mark.parametrize("ref", ["R 1", "", "R/1"])
def test_invalid_ref(ref: str) -> None:
    with pytest.raises(DslError):
        Part(ref, "Mini:Mini_R")


def test_board() -> None:
    d = Design("t")
    with pytest.raises(DslError):
        d.board(mm(50), mm(30), copper=3)
    with pytest.raises(DslError):
        d.board(50, 30)
    with pytest.raises(DslError):
        d.board(mm(0), mm(30))
    d.board("50mm", mm(30), copper=4)
    assert d.size == (50_000_000, 30_000_000) and d.copper == 4
    with pytest.raises(DslError):
        d.board(mm(1), mm(1))


def test_side_checked() -> None:
    with pytest.raises(DslError, match="side"):
        Part("R1", "Mini:Mini_R").place(mm(0), mm(0), side="left")


def test_placement_in_board_coordinates() -> None:
    d, r1, r2 = Design("t"), Part("R1", "Mini:Mini_R"), Part("R2", "Mini:Mini_R")
    d.add(r1, r2)
    r1.place(mm(10), mm(5), rot=90, side="bottom", locked=True)
    found = placements(d)
    assert found["R1"] == Placement(Point(110_000_000, 105_000_000), 90_000_000, "bottom", True)
    assert tuple(found) == ("R1",)
    assert BOARD_ORIGIN == Point(100_000_000, 100_000_000)


def test_no_hidden_membership() -> None:
    d = Design("t")
    Part("R9", "Mini:Mini_R")
    assert all(c.ref != "R9" for c in to_model(d).circuit.components)

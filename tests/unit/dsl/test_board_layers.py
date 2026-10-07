# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Copper layer counts of ``board()``, inner layers, planes and zones on them (capability design-dsl,
"Design structure and names", "Board and placements in the DSL" and "Zones in the DSL"; change c0100)."""

from __future__ import annotations

import pytest

from fenolite.backends.kicad import layers
from fenolite.dsl import Design, DslError, Net, mm, planes, to_model
from fenolite.dsl import design as design_mod
from fenolite.dsl.design import COPPER_COUNTS, inner_layers

SIX = ("F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "B.Cu")
EIGHT = ("F.Cu", "In1.Cu", "In2.Cu", "In3.Cu", "In4.Cu", "In5.Cu", "In6.Cu", "B.Cu")


def fresh() -> tuple[Design, Net, Net]:
    d, gnd, vin = Design("layers"), Net("GND"), Net("VIN")
    d.add(gnd, vin)
    return d, gnd, vin


def test_the_two_constants_are_equal() -> None:
    assert COPPER_COUNTS == (2, 4, 6, 8) == layers.CREATED_COPPER_COUNTS
    assert not hasattr(design_mod, "INNER_LAYERS")


def test_inner_layers() -> None:
    assert inner_layers(2) == ()
    assert inner_layers(4) == ("In1.Cu", "In2.Cu")
    assert inner_layers(6) == SIX[1:-1] and inner_layers(8) == EIGHT[1:-1]
    for count in COPPER_COUNTS:
        table = [layer.name for layer in layers.created_layers(count) if layer.kind == "copper"]
        assert ("F.Cu", *inner_layers(count), "B.Cu") == tuple(table)


@pytest.mark.parametrize("count", [3, 10, True, 6.0, 0, "4", None])
def test_unsupported_copper_count(count: object) -> None:
    """Scenario "Unsupported copper count"."""
    d, _, _ = fresh()
    with pytest.raises(DslError, match="copper must be 2, 4, 6 or 8, not "):
        d.board(mm(50), mm(30), copper=count)  # type: ignore[arg-type]
    assert d.size is None and d.copper == 2  # a refused call declares nothing


def test_six_and_eight_copper_layers() -> None:
    """Scenario "Six and eight copper layers"."""
    d, _, _ = fresh()
    assert d.copper_layers == ("F.Cu", "B.Cu")  # before board()
    d.board(mm(50), mm(30), copper=6)
    assert d.copper == 6 and d.copper_layers == SIX
    other, _, _ = fresh()
    other.board(mm(50), mm(30), copper=8)
    assert other.copper_layers == EIGHT
    two, _, _ = fresh()
    two.board(mm(50), mm(30))
    four, _, _ = fresh()
    four.board(mm(50), mm(30), copper=4)
    assert two.copper_layers == ("F.Cu", "B.Cu")
    assert four.copper_layers == ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")


def test_plane_on_a_deep_inner_layer() -> None:
    """Scenario "Plane on a deep inner layer"."""
    d, gnd, _ = fresh()
    d.board(mm(50), mm(30), copper=8, planes={"In6.Cu": gnd})
    assert planes(d) == {"In6.Cu": "GND"}
    plain, _, _ = fresh()
    plain.board(mm(50), mm(30), copper=8)
    assert to_model(d) == to_model(plain)  # a plane is a build parameter
    other, gnd, _ = fresh()
    with pytest.raises(DslError, match=r"In1\.Cu, In2\.Cu, In3\.Cu, In4\.Cu\), not on 'In5\.Cu'"):
        other.board(mm(50), mm(30), copper=6, planes={"In5.Cu": gnd})
    assert other.size is None


def test_planes_in_layer_order_on_six() -> None:
    d, gnd, vin = fresh()
    d.board(mm(50), mm(30), copper=6, planes={"In4.Cu": vin, "In1.Cu": gnd, "In3.Cu": "GND"})
    assert list(planes(d).items()) == [("In1.Cu", "GND"), ("In3.Cu", "GND"), ("In4.Cu", "VIN")]


def test_planes_need_an_inner_layer() -> None:
    d, gnd, _ = fresh()
    with pytest.raises(DslError, match="planes need copper=4, 6 or 8: a board of 2 copper layers"):
        d.board(mm(50), mm(30), planes={"In1.Cu": gnd})
    with pytest.raises(DslError, match=r"\(In1\.Cu, In2\.Cu\), not on 'F\.Cu'"):
        d.board(mm(50), mm(30), copper=4, planes={"F.Cu": gnd})
    with pytest.raises(DslError, match=r"\(In1\.Cu, In2\.Cu\), not on 'In3\.Cu'"):
        d.board(mm(50), mm(30), copper=4, planes={"In3.Cu": gnd})


def test_zone_on_a_deep_inner_layer() -> None:
    """Scenario "Zone on a deep inner layer"."""
    d, gnd, vin = fresh()
    d.board(mm(50), mm(30), copper=8)
    d.zone(gnd, layers=("In6.Cu",))
    with pytest.raises(DslError, match="'In7.Cu' is not a copper layer of this board") as caught:
        d.zone(vin, layers=("In7.Cu",))
    assert f"({', '.join(EIGHT)})" in str(caught.value)
    board = to_model(d).board
    assert board is not None and [zone.layers for zone in board.zones] == [("In6.Cu",)]


def test_zone_on_every_layer_of_six() -> None:
    d, gnd, vin = fresh()
    d.board(mm(50), mm(30), copper=6)
    d.zone(gnd, layers=SIX)
    with pytest.raises(DslError, match="'In5.Cu' is not a copper layer") as caught:
        d.zone(vin, layers=("In4.Cu", "In5.Cu"))
    assert f"({', '.join(SIX)})" in str(caught.value)


def test_inner_layer_on_a_two_layer_board() -> None:
    """Scenario "Inner layer on a two-layer board"."""
    d, gnd, _ = fresh()
    d.board(mm(50), mm(30))
    with pytest.raises(DslError, match=r"'In1\.Cu' is not a copper layer of this board \(F\.Cu, B\.Cu\)"):
        d.zone(gnd, layers=("In1.Cu",))

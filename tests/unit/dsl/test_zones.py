# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Zones in the DSL (capability design-dsl, "Zones in the DSL"; design-model, "Identifier derivation",
scenario "Zone ids from the zone name"; change c0031)."""

from __future__ import annotations

import pytest

from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.dsl import KEYS, Design, DslError, Net, mm, to_model
from fenolite.dsl.units import as_nm2
from fenolite.model.board import Zone, ZoneSettings

MM = 1_000_000


def design(copper: int = 2) -> tuple[Design, Net, Net]:
    d = Design("zones")
    d.board(mm(50), mm(30), copper=copper)
    return d, Net("GND"), Net("VIN")


def zones(d: Design) -> tuple[Zone, ...]:
    board = to_model(d).board
    assert board is not None
    return board.zones


def test_pour_with_a_clearance() -> None:
    d, gnd, _ = design()
    d.zone(gnd, layers=("F.Cu", "B.Cu"), clearance=mm(0.3))
    (zone,) = zones(d)
    model = to_model(d)
    assert zone.name == "GND" and zone.layers == ("F.Cu", "B.Cu")
    assert zone.net_id == model.nets_by_name["GND"].id == derived_id("net", "dsl", "net:GND")
    assert zone.settings == ZoneSettings(clearance=300_000)
    corners = ((100, 100), (150, 100), (150, 130), (100, 130))
    assert zone.outline == tuple(Point(x * MM, y * MM) for x, y in corners)
    assert zone.id == derived_id("zon", "dsl", "zone:GND")
    assert (zone.priority, zone.locked, zone.filled, zone.fills) == (0, False, False, ())
    assert zone.provenance is None and zone.native_ids == {}


def test_every_setting() -> None:
    d, gnd, _ = design()
    d.zone(
        gnd,
        layers=["B.Cu"],
        name="GND_BOTTOM",
        outline=((mm(1), mm(1)), ("20mm", mm(1)), (mm(20), mm(10))),
        priority=2,
        clearance="0.2mm",
        min_thickness=mm(0.2),
        connection="thru_hole_only",
        thermal_gap=mm(0.4),
        thermal_spoke_width=mm(0.35),
        islands="below_area",
        min_island_area="2.5mm2",
        locked=True,
    )
    (zone,) = zones(d)
    assert zone.name == "GND_BOTTOM" and zone.id == derived_id("zon", "dsl", "zone:GND_BOTTOM")
    assert zone.outline == (Point(101 * MM, 101 * MM), Point(120 * MM, 101 * MM), Point(120 * MM, 110 * MM))
    assert (zone.priority, zone.locked) == (2, True)
    assert zone.settings == ZoneSettings(
        clearance=200_000,
        min_thickness=200_000,
        connection="thru_hole_only",
        thermal_gap=400_000,
        thermal_spoke_width=350_000,
        island_removal="below_area",
        min_island_area=2_500_000_000_000,
    )
    # hatching and smoothing are not DSL arguments
    assert zone.settings.fill_mode == "solid" and zone.settings.smoothing == "none"


def test_zone_before_the_board() -> None:
    d = Design("zones")
    with pytest.raises(DslError, match=r"board\(\)"):
        d.zone(Net("GND"), layers=("F.Cu",))


def test_inner_layer_on_a_two_layer_board() -> None:
    d, gnd, _ = design()
    with pytest.raises(DslError, match=r"In1\.Cu"):
        d.zone(gnd, layers=("In1.Cu",))
    four, gnd4, _ = design(copper=4)
    four.zone(gnd4, layers=("In1.Cu", "In2.Cu"))
    assert zones(four)[0].layers == ("In1.Cu", "In2.Cu")


@pytest.mark.parametrize("layers", [(), "F.Cu", ("F.Cu", "F.Cu"), ("F.SilkS",), None, (1,)])
def test_bad_layers(layers: object) -> None:
    d, gnd, _ = design()
    with pytest.raises(DslError, match="layers"):
        d.zone(gnd, layers=layers)  # type: ignore[arg-type]


def test_bare_number_refused() -> None:
    d, gnd, _ = design()
    with pytest.raises(DslError, match="clearance"):
        d.zone(gnd, layers=("F.Cu",), clearance=0.3)
    assert d.zones == {}  # a refused call declares nothing


@pytest.mark.parametrize(
    ("argument", "value"),
    [
        ("clearance", mm(-0.1)),
        ("min_thickness", mm(0)),
        ("thermal_gap", mm(0)),
        ("thermal_spoke_width", mm(-1)),
        ("min_thickness", 0.25),
        ("thermal_gap", "0.5"),
        ("connection", "partial"),
        ("islands", "sometimes"),
        ("priority", -1),
        ("priority", True),
        ("priority", 1.5),
        ("locked", 1),
        ("outline", ((mm(0), mm(0)), (mm(1), mm(0)))),
        ("outline", ((mm(0), mm(0)), (mm(1), mm(0)), (1, 2))),
        ("outline", ((mm(0), mm(0)), (mm(1), mm(0)), (mm(1),))),
        ("outline", "square"),
    ],
)
def test_each_violation_names_its_argument(argument: str, value: object) -> None:
    d, gnd, _ = design()
    with pytest.raises(DslError, match=argument):
        d.zone(gnd, layers=("F.Cu",), **{argument: value})  # type: ignore[arg-type]


def test_clearance_of_zero_is_accepted() -> None:
    d, gnd, _ = design()
    d.zone(gnd, layers=("F.Cu",), clearance=mm(0))
    assert zones(d)[0].settings.clearance == 0


def test_island_area_needs_below_area() -> None:
    d, gnd, vin = design()
    with pytest.raises(DslError, match="min_island_area"):
        d.zone(gnd, layers=("F.Cu",), islands="never", min_island_area="2mm2")
    with pytest.raises(DslError, match="min_island_area"):
        d.zone(gnd, layers=("F.Cu",), min_island_area="2mm2")
    d.zone(vin, layers=("B.Cu",), islands="below_area", min_island_area="2mm2")
    (zone,) = zones(d)
    assert zone.settings.island_removal == "below_area" and zone.settings.min_island_area == 2_000_000_000_000


@pytest.mark.parametrize(
    "value", ["2", "2mm", "2 mm2 x", "-1mm2", "mm2", "0.0000000000001mm2", 2, 2.5, "1e3mm2"]
)
def test_bad_island_area(value: object) -> None:
    d, gnd, _ = design()
    with pytest.raises(DslError, match="min_island_area"):
        d.zone(gnd, layers=("F.Cu",), islands="below_area", min_island_area=value)  # type: ignore[arg-type]


def test_as_nm2_is_exact() -> None:
    assert as_nm2("2.5mm2", name="a") == 2_500_000_000_000
    assert as_nm2(" 10 mm2 ", name="a") == 10_000_000_000_000
    assert as_nm2("0.000000000001mm2", name="a") == 1
    assert as_nm2("0mm2", name="a") == 0


def test_names_are_unique() -> None:
    d, gnd, _ = design()
    d.zone(gnd, layers=("F.Cu",))
    with pytest.raises(DslError, match="'GND'"):
        d.zone(gnd, layers=("B.Cu",))
    d.zone(gnd, layers=("B.Cu",), name="GND_BOTTOM")
    assert [z.name for z in zones(d)] == ["GND", "GND_BOTTOM"]


@pytest.mark.parametrize("name", ["", " GND", "GND ", 3])
def test_bad_names(name: object) -> None:
    d, gnd, _ = design()
    with pytest.raises(DslError, match="name"):
        d.zone(gnd, layers=("F.Cu",), name=name)  # type: ignore[arg-type]


def test_zone_without_a_net() -> None:
    d, _, _ = design()
    with pytest.raises(DslError, match="name"):
        d.zone(None, layers=("F.Cu",))
    d.zone(None, layers=("F.Cu",), name="FLOATING")
    (zone,) = zones(d)
    assert zone.net_id is None and zone.name == "FLOATING"
    with pytest.raises(DslError, match="net"):
        d.zone("GND", layers=("F.Cu",), name="X")  # type: ignore[arg-type]


def test_the_net_joins_the_design() -> None:
    d, gnd, _ = design()
    d.zone(gnd, layers=("F.Cu",))
    assert d.nets == {"GND": gnd}
    assert [n.name for n in to_model(d).circuit.nets] == ["GND"]
    with pytest.raises(DslError, match="two distinct nets"):
        d.zone(Net("GND"), layers=("B.Cu",), name="OTHER")


def test_zone_ids_from_the_zone_name() -> None:
    def declare(order: tuple[str, ...]) -> Design:
        d, gnd, vin = design()
        calls = {
            "GND": lambda: d.zone(gnd, layers=("F.Cu",)),
            "VIN_POUR": lambda: d.zone(vin, layers=("B.Cu",), name="VIN_POUR"),
        }
        for name in order:
            calls[name]()
        return d

    first, second = zones(declare(("GND", "VIN_POUR"))), zones(declare(("VIN_POUR", "GND")))
    assert first == second
    assert [z.name for z in first] == ["GND", "VIN_POUR"]  # name order
    assert first[0].id == derived_id("zon", "dsl", "zone:GND")
    assert first[1].id == derived_id("zon", "dsl", "zone:VIN_POUR")
    assert KEYS["zone"] == ("zon", "zone:<name>")


def test_designs_without_zones_are_unchanged() -> None:
    d, _, _ = design()
    assert zones(d) == ()


def test_zone_on_a_round_board() -> None:
    """A zone without an outline takes the box of the board ring's vertices and arc mid points (c0102)."""
    from fenolite.dsl import arc_to, shape

    d = Design("zones")
    d.board(outline=shape.circle(mm(20), mm(20), mm(40)))
    d.zone(Net("GND"), layers=("B.Cu",))
    (zone,) = zones(d)
    corners = ((100, 100), (140, 100), (140, 140), (100, 140))
    assert zone.outline == tuple(Point(x * MM, y * MM) for x, y in corners)
    # cut-outs do not change the box, and an outline given to zone() is written as before
    e = Design("zones")
    bulge = arc_to((mm(45), mm(25)), (mm(40), mm(30)))
    e.board(outline=((mm(0), mm(0)), (mm(40), mm(0)), bulge, (mm(0), mm(30))))
    e.cutout(shape.circle(mm(10), mm(10), mm(4)))
    e.zone(Net("GND"), layers=("B.Cu",))
    e.zone(Net("VIN"), layers=("F.Cu",), outline=((mm(1), mm(1)), (mm(9), mm(1)), (mm(9), mm(9))))
    gnd, vin = zones(e)
    box = ((100, 100), (145, 100), (145, 130), (100, 130))
    assert gnd.outline == tuple(Point(x * MM, y * MM) for x, y in box)
    assert vin.outline == (Point(101 * MM, 101 * MM), Point(109 * MM, 101 * MM), Point(109 * MM, 109 * MM))

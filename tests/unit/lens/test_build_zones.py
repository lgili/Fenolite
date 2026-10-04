# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Zones in a build (capability design-dsl, "Zones in a build"; change c0031): the build keeps the
zones of the model it is given, the writer writes them for both targets, and they read back."""

from __future__ import annotations

import pytest
from _buildhelp import blink, build, codes, pour_variant

from fenolite.backends.kicad.pcb import kicad_uuid, read_board
from fenolite.backends.kicad.sexpr import parse
from fenolite.core.ids import derived_id
from fenolite.dsl import mm, to_model
from fenolite.model.board import Zone, ZoneSettings

BOARD = "blink.kicad_pcb"
FLAG = "(filled_areas_thickness no)"


def text_of(target: int, **zone: object) -> str:
    out = build(pour_variant(**zone), target)
    assert not [i for i in out.issues if i.severity == "error"], codes(out)
    return out.files[BOARD].decode("utf-8")


def zone_of(text: str) -> tuple[Zone, dict[str, str]]:
    design = read_board(text)
    assert design.board is not None
    (zone,) = design.board.zones
    return zone, {n.id: n.name for n in design.circuit.nets}


@pytest.mark.parametrize("target", [9, 10])
def test_blink_with_a_pour(target: int) -> None:
    text = text_of(target)
    zone, nets = zone_of(text)
    assert zone.name == "GND" and zone.layers == ("B.Cu",)
    assert nets[zone.net_id or ""] == "GND"
    assert zone.settings.clearance == 300_000 and zone.settings.connection == "solid"
    assert (FLAG in " ".join(text.split())) == (target == 9)


@pytest.mark.parametrize("target", [9, 10])
def test_script_values_read_back(target: int) -> None:
    arguments: dict[str, object] = {
        "layers": ("F.Cu", "B.Cu"),
        "name": "GND_ALL",
        "outline": ((mm(2), mm(2)), (mm(48), mm(2)), (mm(48), mm(28)), (mm(2), mm(28))),
        "priority": 3,
        "min_thickness": mm(0.2),
        "connection": "thru_hole_only",
        "thermal_gap": mm(0.4),
        "thermal_spoke_width": mm(0.35),
        "islands": "below_area",
        "min_island_area": "2.5mm2",
        "locked": True,
    }
    design = pour_variant(**arguments)
    (wanted,) = to_model(design).board.zones  # type: ignore[union-attr]
    zone, nets = zone_of(text_of(target, **arguments))
    assert (zone.name, zone.outline, zone.layers, zone.priority, zone.locked) == (
        wanted.name,
        wanted.outline,
        wanted.layers,
        wanted.priority,
        wanted.locked,
    )
    assert nets[zone.net_id or ""] == "GND"
    assert zone.settings.effective() == wanted.settings.effective()
    assert zone.settings == ZoneSettings(
        clearance=300_000,
        min_thickness=200_000,
        connection="thru_hole_only",
        thermal_gap=400_000,
        thermal_spoke_width=350_000,
        island_removal="below_area",
        min_island_area=2_500_000_000_000,
    )
    assert zone.filled is False and zone.fills == ()


def test_the_build_keeps_the_zones_of_its_model() -> None:
    design = pour_variant()
    out = build(design)
    assert out.design.board is not None
    assert out.design.board.zones == to_model(design).board.zones  # type: ignore[union-attr]
    cached = out.files[".fenolite/board.json"].decode("utf-8")
    assert '"name": "GND"' in cached and '"clearance": 300000' in cached


@pytest.mark.parametrize("target", [9, 10])
def test_zone_uuid_from_the_name(target: int) -> None:
    first, second = build(pour_variant(), target), build(pour_variant(), target)
    assert first.files == second.files
    wanted = kicad_uuid(Zone(id=derived_id("zon", "dsl", "zone:GND"), outline=()))
    (node,) = parse(first.files[BOARD].decode("utf-8")).nodes("zone")
    uuid = node.find("uuid")
    assert uuid is not None and uuid.atoms()[0].value == wanted
    zone, _ = zone_of(first.files[BOARD].decode("utf-8"))
    assert zone.native_ids == {"kicad": wanted}


def test_created_form_of_the_built_zone() -> None:
    (node,) = parse(text_of(10)).nodes("zone")
    heads = [c.name for c in node.nodes()]
    assert heads == [
        "net",
        "layer",
        "uuid",
        "name",
        "hatch",
        "connect_pads",
        "min_thickness",
        "fill",
        "polygon",
    ]
    assert node.find("connect_pads") == parse("(connect_pads yes (clearance 0.3))")


def test_a_design_without_zones_builds_as_before() -> None:
    text = build(blink()).files[BOARD].decode("utf-8")
    assert parse(text).nodes("zone") == ()

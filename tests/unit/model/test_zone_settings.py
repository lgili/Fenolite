# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Zone settings in the board model (capability design-model, "Zone settings in the board model";
change c0031)."""

from __future__ import annotations

import dataclasses
import json
import random
from pathlib import Path
from typing import get_args

import _schema
import pytest

from fenolite.core.coords import Point, Size
from fenolite.core.ids import new_id
from fenolite.model import board as board_module
from fenolite.model.board import (
    Board,
    FootprintInstance,
    HatchBorder,
    IslandRemoval,
    Pad,
    Zone,
    ZoneConnection,
    ZoneFillMode,
    ZoneHatch,
    ZoneSettings,
    ZoneSmoothing,
)
from fenolite.model.canonical import dumps, loads

ROOT = Path(__file__).resolve().parents[3]
SCHEMAS = ROOT / "schemas" / "fenolite.model.v0"


def _zone(**kwargs: object) -> Zone:
    return Zone(id=new_id("zon", random.Random(1)), outline=(), **kwargs)  # type: ignore[arg-type]


def _pad(**kwargs: object) -> Pad:
    return Pad(
        id=new_id("pad", random.Random(2)), number="1", shape="rect", size=Size(1, 1), position=Point(0, 0),
        **kwargs,  # type: ignore[arg-type]
    )  # fmt: skip


def _board(zone: Zone, pad: Pad | None = None) -> Board:
    rng = random.Random(3)
    footprints = ()
    if pad is not None:
        footprints = (
            FootprintInstance(
                id=new_id("fp", rng), component_id="", lib_ref="L:F", position=Point(0, 0), pads=(pad,)
            ),
        )
    return Board(id=new_id("brd", rng), zones=(zone,), footprints=footprints)


def test_defaults_of_a_new_zone() -> None:
    zone, pad = _zone(), _pad()
    assert zone.settings == ZoneSettings()
    assert zone.settings.clearance == 500_000
    assert zone.settings.connection == "thermal"
    assert zone.filled is False and zone.locked is False
    assert pad.zone_connection is None


def test_default_values_are_kicads_new_zone_values() -> None:
    assert dataclasses.asdict(ZoneSettings()) == {
        "clearance": 500_000,
        "min_thickness": 250_000,
        "connection": "thermal",
        "thermal_gap": 500_000,
        "thermal_spoke_width": 500_000,
        "island_removal": "always",
        "min_island_area": 10_000_000_000_000,
        "smoothing": "none",
        "smoothing_radius": 0,
        "fill_mode": "solid",
        "hatch": {
            "thickness": 1_000_000,
            "gap": 1_500_000,
            "orientation": 0,
            "smoothing_level": 0,
            "smoothing_value": "0.1",
            "border": "hatch_thickness",
            "min_hole_area": "0.15",
        },
    }


def test_defaults_equal_the_gui_save() -> None:
    """``ZoneSettings()`` equals ``defaults.zones`` of the 10.0.6 new-project save, field by field
    (S-0020; ``H-K-ZONE-DEFAULTS``, the GUI half)."""
    project = json.loads(
        (ROOT / "tests" / "data" / "kicad" / "project" / "empty_10.kicad_pro").read_text(encoding="utf-8")
    )
    saved = project["board"]["design_settings"]["defaults"]["zones"]
    settings = ZoneSettings()
    mm = 1_000_000
    connections = {0: "none", 1: "thermal", 2: "solid", 3: "thru_hole_only"}
    islands = {0: "always", 1: "never", 2: "below_area"}
    smoothings = {0: "none", 1: "chamfer", 2: "fillet"}
    assert settings.clearance == round(saved["min_clearance"] * mm)
    assert settings.min_thickness == round(saved["min_thickness"] * mm)
    assert settings.connection == connections[saved["pad_connection"]]
    assert settings.thermal_gap == round(saved["thermal_relief_gap"] * mm)
    assert settings.thermal_spoke_width == round(saved["thermal_relief_spoke_width"] * mm)
    assert settings.island_removal == islands[saved["remove_islands"]]
    assert settings.min_island_area == round(saved["min_island_area"]) * mm * mm
    assert settings.smoothing == smoothings[saved["corner_smoothing"]]
    assert settings.smoothing_radius == round(saved["corner_radius"] * mm)
    assert settings.fill_mode == {0: "solid", 1: "hatched"}[saved["fill_mode"]]
    assert settings.hatch.thickness == round(saved["hatch_thickness"] * mm)
    assert settings.hatch.gap == round(saved["hatch_gap"] * mm)
    assert settings.hatch.orientation == round(saved["hatch_orientation"] * mm)
    assert settings.hatch.smoothing_level == saved["hatch_smoothing_level"]
    assert settings.hatch.smoothing_value == str(saved["hatch_smoothing_value"])


def test_vocabularies_are_closed() -> None:
    assert get_args(ZoneConnection) == ("solid", "thermal", "none", "thru_hole_only")
    assert get_args(IslandRemoval) == ("always", "never", "below_area")
    assert get_args(ZoneSmoothing) == ("none", "chamfer", "fillet")
    assert get_args(ZoneFillMode) == ("solid", "hatched")
    assert get_args(HatchBorder) == ("hatch_thickness", "min_thickness")
    for name in ("ZoneSettings", "ZoneHatch", "ZoneConnection", "IslandRemoval", "ZoneSmoothing"):
        assert name in board_module.__all__


def test_settings_are_frozen_value_objects() -> None:
    for cls in (ZoneSettings, ZoneHatch):
        assert dataclasses.is_dataclass(cls)
        assert "id" not in {f.name for f in dataclasses.fields(cls)}
    with pytest.raises(dataclasses.FrozenInstanceError):
        ZoneSettings().clearance = 1  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        ZoneHatch().gap = 1  # type: ignore[misc]


def test_old_documents_still_load() -> None:
    """A ``board.json`` written before the new fields: every zone and pad takes the defaults."""
    text = dumps(_board(_zone(name="GND", layers=("F.Cu",)), _pad()))
    for key in ("settings", "filled", "locked", "zone_connection"):
        assert key not in text  # defaults are omitted, so this is the old document
    board = loads(text, Board)
    assert board.zones[0].settings == ZoneSettings()
    assert board.zones[0].filled is False and board.zones[0].locked is False
    assert board.footprints[0].pads[0].zone_connection is None


def test_settings_round_trip_through_canonical_json() -> None:
    settings = ZoneSettings(
        clearance=300_000,
        connection="solid",
        island_removal="below_area",
        min_island_area=2_500_000_000_000,
        fill_mode="hatched",
        hatch=ZoneHatch(gap=2_000_000, border="min_thickness", min_hole_area="0.3"),
    )
    board = _board(_zone(settings=settings, filled=True, locked=True), _pad(zone_connection="thru_hole_only"))
    text = dumps(board)
    assert loads(text, Board) == board
    data = json.loads(text)
    assert data["zones"][0]["settings"]["hatch"] == {
        "gap": 2_000_000,
        "border": "min_thickness",
        "min_hole_area": "0.3",
    }
    assert _schema.validate(data, _schema.load("fenolite.model.v0/board.json")) == []


def test_unknown_connection_rejected() -> None:
    schema = _schema.load("fenolite.model.v0/board.json")
    data = json.loads(dumps(_board(_zone(settings=ZoneSettings(connection="solid")))))
    assert _schema.validate(data, schema) == []
    data["zones"][0]["settings"]["connection"] = "partial"
    errors = _schema.validate(data, schema)
    assert errors and any("/zones/0/settings/connection" in e for e in errors)


def test_float_rejected_in_settings() -> None:
    schema = _schema.load("fenolite.model.v0/board.json")
    data = json.loads(dumps(_board(_zone(settings=ZoneSettings(clearance=300_000)))))
    data["zones"][0]["settings"]["clearance"] = 0.3
    assert _schema.validate(data, schema)


def test_values_without_effect_are_dropped() -> None:
    settings = ZoneSettings(
        fill_mode="solid",
        hatch=ZoneHatch(gap=2_000_000),
        smoothing="none",
        smoothing_radius=1_000_000,
        island_removal="never",
        min_island_area=5_000_000_000_000,
    )
    assert settings.effective() == ZoneSettings(island_removal="never")


def test_values_with_effect_are_kept() -> None:
    settings = ZoneSettings(
        fill_mode="hatched",
        hatch=ZoneHatch(gap=2_000_000),
        smoothing="fillet",
        smoothing_radius=1_000_000,
        island_removal="below_area",
        min_island_area=5_000_000_000_000,
        clearance=300_000,
    )
    assert settings.effective() == settings
    assert ZoneSettings().effective() == ZoneSettings()


def test_schemas_list_the_new_fields() -> None:
    board = (SCHEMAS / "board.json").read_text(encoding="utf-8")
    library = (SCHEMAS / "library.json").read_text(encoding="utf-8")
    for name in ("settings", "filled", "locked", "zone_connection", "thru_hole_only", "below_area"):
        assert f'"{name}"' in board
    assert '"zone_connection"' in library

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Descriptors follow the current authored font/property/inter-sheet source contract (c0217)."""

from __future__ import annotations

import dataclasses
import tomllib

import _schema
import pytest

from fenolite.core.coords import Point, Size
from fenolite.lens.drawn import read_drawn, write_drawn
from fenolite.model.drawn import (
    DrawnField,
    DrawnFont,
    DrawnLabel,
    DrawnPin,
    DrawnPower,
    DrawnSchematic,
    DrawnSheet,
    DrawnSheetProperty,
    DrawnSheetRef,
    DrawnSymbol,
)


def drawing() -> DrawnSchematic:
    font = DrawnFont(Size(250_001, 350_003), 0, False, True, "Authored Ω")
    pose = DrawnField("Value", Point(3, 4), 90_000_000, "right bottom", True, font)
    label = DrawnLabel(
        "global",
        "SIG",
        Point(7, 8),
        font=font,
        justify="",
        intersheet_refs=dataclasses.replace(pose, name="Intersheetrefs"),
    )
    ref = DrawnSheetRef(
        "child",
        "child",
        "ch0",
        "Authored",
        Point(9, 10),
        Size(11, 12),
        "2",
        fields=(dataclasses.replace(pose, name="Sheetname"),),
        properties=(DrawnSheetProperty("author", "μV", Point(13, 14), font=font),),
        pins=(DrawnPin("SIG", "input", Point(15, 16), font=font, justify=""),),
    )
    return DrawnSchematic(
        "root",
        (
            DrawnSheet(
                "root",
                symbols=(DrawnSymbol("R1", 1, Point(1, 2), mirror="x", fields=(pose,)),),
                powers=(DrawnPower("Authored:Power", "GND", Point(5, 6), fields=(pose,), mirror="y"),),
                labels=(label,),
                sheet_refs=(ref,),
            ),
            DrawnSheet("child"),
        ),
    )


@pytest.mark.parametrize("version", ("v0", "v1"))
def test_current_drawn_contract_has_typed_closed_mirrors(version: str) -> None:
    expected = drawing()
    text = write_drawn(expected).replace("fenolite.drawn-schematic.v0", f"fenolite.drawn-schematic.{version}")
    assert read_drawn(text) == expected
    raw = tomllib.loads(text)
    schema = _schema.load("formats/fenolite.drawn-schematic.v1.json")
    assert _schema.validate({**raw, "schema": schema["$id"]}, schema) == []
    symbol_font = raw["sheet"][0]["symbol"][0]["fields"]["Value"]["font"]
    assert symbol_font["bold"] is False and symbol_font["thickness"] == 0
    symbol_font["unknown"] = True
    assert _schema.validate({**raw, "schema": schema["$id"]}, schema)

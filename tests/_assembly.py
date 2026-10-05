# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Small designs for the tests of the assembly tables (change c0064), built through the model API: no
file is read and no tool runs. Every part, value, property and number is made up for these tests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.board import Board, FootprintAttribute, FootprintInstance, Outline, Side
from fenolite.model.circuit import Circuit, Component
from fenolite.model.design import Design, DesignHeader

DATA = Path(__file__).resolve().parent / "data" / "assembly"
MM = 1_000_000
DEG = 1_000_000
R_0603 = "Mini:Mini_R_0603"
LED = "Mini:Mini_LED_THT_3mm"
QFP = "Mini:Mini_QFP-32_7x7mm_P0.8mm"


@dataclass(frozen=True)
class Part:
    """A component and its placed footprint, in millimetres and degrees of the board file's frame."""

    ref: str
    value: str = ""
    footprint: str = R_0603
    x: int = 0
    y: int = 0
    rot: int = 0
    side: Side = "top"
    attributes: tuple[FootprintAttribute, ...] = ("smd",)
    dnp: bool = False
    properties: Mapping[str, str] = field(default_factory=lambda: {})


def _id(prefix: str, name: str) -> str:
    return derived_id(prefix, "test", name)


def design_of(*parts: Part, outline: tuple[Point, ...] = ()) -> Design:
    """A design holding ``parts``; ``outline`` becomes the board's model outline."""
    components = tuple(
        Component(
            id=_id("cmp", part.ref),
            ref=part.ref,
            value=part.value,
            dnp=part.dnp,
            lib_footprint_ref=part.footprint,
            properties={"Reference": part.ref, "Value": part.value, **part.properties},
        )
        for part in parts
    )
    footprints = tuple(
        FootprintInstance(
            id=_id("fp", part.ref),
            component_id=_id("cmp", part.ref),
            lib_ref=part.footprint,
            position=Point(part.x * MM, part.y * MM),
            rotation=part.rot * DEG,
            side=part.side,
            attributes=part.attributes,
        )
        for part in parts
    )
    board = Board(
        id=_id("brd", "board"),
        outline=Outline(id=_id("out", "outline"), points=outline) if outline else None,
        footprints=footprints,
    )
    header = DesignHeader(id=_id("dsn", "design"), name="assembly", schema_version="0", fenolite_version="0")
    return Design(header=header, circuit=Circuit(components=components), board=board)


def rectangle(x: int, y: int, width: int, height: int) -> tuple[Point, ...]:
    """A rectangle in millimetres whose upper-left corner on the page is ``(x, y)``."""
    return (
        Point(x * MM, y * MM),
        Point((x + width) * MM, y * MM),
        Point((x + width) * MM, (y + height) * MM),
        Point(x * MM, (y + height) * MM),
    )


__all__ = ["DATA", "DEG", "LED", "MM", "QFP", "R_0603", "Part", "design_of", "rectangle"]

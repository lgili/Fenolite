# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawing conventions (change c0260, scenarios "Drawing 1 pin-1 marks", "No silk on copper", and
``drawing/0`` reproducing the 0.6 catalog)."""

from __future__ import annotations

from typing import Any

import pytest
from _package_records import every_record

from fenolite.catalog import get_footprint
from fenolite.catalog.footprints import generate, positions_of
from fenolite.catalog.footprints.drawing import DRAWING_1
from fenolite.catalog.footprints.record import Package, package_from
from fenolite.model.board import Pad

DRAWN = [p for p in every_record() if p.drawing == 1]


def test_drawing_1_pin1_marks() -> None:
    soic = next(p for p in DRAWN if p.name == "SOIC8_B4.9x3.9_P1.27")
    fp = generate(soic).footprint
    assert fp is not None
    chamfer = min(DRAWING_1["fab_chamfer_max"], 3_900_000 // 4)
    x0, y0 = -3_900_000 // 2, -4_900_000 // 2
    fab = [((g.points[0].x, g.points[0].y), (g.points[1].x, g.points[1].y)) for g in fp.graphics_on("F.Fab")]
    assert ((x0, y0 + chamfer), (x0 + chamfer, y0)) in fab
    circles = [g for g in fp.graphics_on("F.SilkS") if g.kind == "circle"]
    assert len(circles) == 1
    pad1 = next(p for p in fp.pads if p.number == "1")
    centre = circles[0].points[0]
    assert centre.x < x0 and centre.x < pad1.position.x - pad1.size.w // 2 and centre.y == pad1.position.y
    assert not circles[0].filled  # a stroked circle: the Altium writer keeps it


def _distance_squared_to_pad(x: int, y: int, pad: Pad) -> int:
    dx = max(pad.position.x - pad.size.w // 2 - x, 0, x - pad.position.x - pad.size.w // 2)
    dy = max(pad.position.y - pad.size.h // 2 - y, 0, y - pad.position.y - pad.size.h // 2)
    return dx * dx + dy * dy


def _segment_clear(a: Any, b: Any, pad: Pad, clearance: int) -> bool:
    """An axis-aligned segment keeps ``clearance`` from the pad rectangle (exact, integers)."""
    if a.y == b.y:
        x_lo, x_hi = sorted((a.x, b.x))
        px0, px1 = pad.position.x - pad.size.w // 2, pad.position.x + pad.size.w // 2
        x = min(max(px0, x_lo), x_hi) if px1 >= x_lo and px0 <= x_hi else (x_lo if px1 < x_lo else x_hi)
        return _distance_squared_to_pad(x, a.y, pad) >= clearance * clearance
    y_lo, y_hi = sorted((a.y, b.y))
    py0, py1 = pad.position.y - pad.size.h // 2, pad.position.y + pad.size.h // 2
    y = min(max(py0, y_lo), y_hi) if py1 >= y_lo and py0 <= y_hi else (y_lo if py1 < y_lo else y_hi)
    return _distance_squared_to_pad(a.x, y, pad) >= clearance * clearance


@pytest.mark.parametrize("package", DRAWN, ids=[p.file for p in DRAWN])
def test_no_silk_on_copper(package: Package) -> None:
    gap, piece = DRAWING_1["silk_copper_gap"], DRAWING_1["silk_min_piece"]
    for count in positions_of(package) or (None,):
        fp = generate(package, positions=count).footprint
        assert fp is not None
        silk = fp.graphics_on("F.SilkS")
        for graphic in silk:
            half = graphic.width // 2
            if graphic.kind == "circle":
                centre, edge = graphic.points
                outer = edge.x - centre.x + half
                for pad in fp.pads:
                    assert _distance_squared_to_pad(centre.x, centre.y, pad) >= (outer + gap) ** 2
                continue
            assert graphic.kind == "line"
            a, b = graphic.points
            assert a.x == b.x or a.y == b.y
            assert abs(b.x - a.x) + abs(b.y - a.y) >= piece
            for pad in fp.pads:
                assert _segment_clear(a, b, pad, gap + half), (package.file, graphic.id, pad.number)


# --- drawing/0 reproduces the 0.6 catalog --------------------------------------------------------------


def _catalog(name: str, family: str, keys: dict[str, Any], land: dict[str, Any]) -> Package:
    summary = get_footprint(f"Fenolite:{name}").description.removesuffix(
        "; land pattern remains INFERRED and requires part-specific review"
    )
    raw: dict[str, Any] = {
        "schema": "fenolite.package.v0",
        "family": family,
        "id": f"Fenolite:{name}",
        "summary": summary,
        "evidence": "INFERRED",
        **keys,
        "generate": {"drawing": 0, "lands": 1},
        "land": {"source": "the 0.6 catalog", **land},
    }
    return package_from(raw, file=f"{name}.toml")


ZERO = [
    (
        "Chip_0603",
        "chip",
        {"body": {"length": "1.6mm", "width": "0.8mm"}, "terminal": {"length": "0.3mm"}},
        {"pad": {"length": "0.9mm", "width": "1.0mm"}, "row_spacing": "1.6mm"},
    ),
    (
        "SOIC14_TI_D0014A",
        "gullwing",
        {
            "pins": 14,
            "pitch": "1.27mm",
            "arrangement": "dual",
            "body": {"length": "8.75mm", "width": "3.9mm"},
            "span": "6mm",
            "lead": {"length": "1mm", "width": "0.4mm"},
        },
        {"pad": {"length": "1.55mm", "width": "0.6mm"}, "row_spacing": "5.4mm"},
    ),
    (
        "LQFP48_TI_PT0048A",
        "gullwing",
        {
            "pins": 48,
            "pitch": "0.5mm",
            "arrangement": "quad",
            "body": {"length": "7mm", "width": "7mm"},
            "span_x": "9mm",
            "span_y": "9mm",
            "lead": {"length": "0.6mm", "width": "0.22mm"},
        },
        {"pad": {"length": "1.6mm", "width": "0.3mm"}, "row_spacing_x": "8.2mm", "row_spacing_y": "8.2mm"},
    ),
    (
        "QFN16_Diodes_W3030_A1",
        "nolead",
        {
            "pins": 16,
            "pitch": "0.5mm",
            "arrangement": "quad",
            "body": {"length": "3mm", "width": "3mm"},
            "terminal": {"length": "0.4mm", "width": "0.25mm"},
            "ep": {"length": "1.7mm", "width": "1.7mm"},
        },
        {
            "pad": {"length": "0.7mm", "width": "0.3mm"},
            "row_spacing_x": "3mm",
            "row_spacing_y": "3mm",
            "ep": {"length": "1.7mm", "width": "1.7mm"},
        },
    ),
    (
        "DFN6_Diodes_W2020_US",
        "nolead",
        {
            "pins": 6,
            "pitch": "0.65mm",
            "arrangement": "dual",
            "body": {"length": "2mm", "width": "2mm"},
            "terminal": {"length": "0.3mm", "width": "0.3mm"},
            "ep": {"length": "1.55mm", "width": "0.85mm"},
        },
        {
            "pad": {"length": "0.545mm", "width": "0.35mm"},
            "row_spacing": "1.805mm",
            "ep": {"length": "1.55mm", "width": "0.85mm"},
        },
    ),
    (
        "DIP8_Microchip_P",
        "dip",
        {
            "pins": 8,
            "pitch": "2.54mm",
            "row_spacing": "7.62mm",
            "body": {"length": "10.16mm", "width": "7.112mm"},
            "lead": {"width": "0.5mm", "thickness": "0.3mm"},
        },
        {"drill": "0.9mm", "pad_diameter": "1.8mm"},
    ),
]


@pytest.mark.parametrize(("name", "family", "keys", "land"), ZERO, ids=[z[0] for z in ZERO])
def test_drawing_0_reproduces_the_0_6_catalog(
    name: str, family: str, keys: dict[str, Any], land: dict[str, Any]
) -> None:
    generated = generate(_catalog(name, family, keys, land))
    assert generated.footprint == get_footprint(f"Fenolite:{name}")

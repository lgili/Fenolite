# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pin connection points and the layout of a generated sheet (capability kicad-schematic, "Pin connection
points" and "Deterministic sheet layout"; changes c0061 and c0070)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from _buildhelp import resolver
from hypothesis import given, settings
from hypothesis import strategies as st

from fenolite.backends.kicad import schlayout
from fenolite.backends.kicad.schgen import unit_box
from fenolite.backends.kicad.schlayout import (
    GRID,
    ORIGIN_STEP,
    PAGE_MARGIN,
    PAPERS,
    TITLE_BAND,
    RefBox,
    SymbolPlacement,
    UnitBox,
    UnitPin,
    label_angle,
    layout_units,
    pin_point,
)
from fenolite.core.coords import Point

MM = 1_000_000
SIZES = {name: (width, height) for name, width, height in PAPERS}


def box(path: str, symbol: str = "Mini:Mini_R", unit: int = 1, **labels: str) -> UnitBox:
    return unit_box(path, resolver(10).symbol(symbol), unit, {k.lstrip("p"): v for k, v in labels.items()})


def blink() -> list[UnitBox]:
    return [
        box("U1", "Mini:Mini_QFP32_IC", p9="VIN", p10="GND", p1="LED_DRV"),
        box("R1", p1="LED_DRV", p2="LED_A"),
        box("D1", "Mini:Mini_LED", p1="GND", p2="LED_A"),
    ]


def overlap(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def check(layout: schlayout.SheetLayout) -> None:
    width, height = SIZES[layout.paper]
    cells = list(layout.cells.values())
    assert not [(a, b) for i, a in enumerate(cells) for b in cells[i + 1 :] if overlap(a, b)]
    for x0, y0, x1, y1 in cells:
        assert x0 >= PAGE_MARGIN and y0 >= PAGE_MARGIN
        assert x1 <= width - PAGE_MARGIN and y1 <= height - TITLE_BAND
    assert all(p.x % ORIGIN_STEP == 0 and p.y % ORIGIN_STEP == 0 for p in layout.origins.values())


# -- the pin frame


def test_unrotated_pin() -> None:
    origin, pin = Point(50_800_000, 76_200_000), Point(-12_700_000, 16_510_000)
    assert pin_point(origin, pin, 0, "") == Point(38_100_000, 59_690_000)


def test_mirror_about_the_y_axis() -> None:
    origin, pin = Point(50_800_000, 76_200_000), Point(-12_700_000, 16_510_000)
    assert pin_point(origin, pin, 0, "y").x == 63_500_000
    assert pin_point(origin, pin, 0, "x") == Point(38_100_000, 92_710_000)


def test_rotations_turn_counter_clockwise_on_the_sheet() -> None:
    origin, left = Point(0, 0), Point(-10 * MM, 0)
    assert pin_point(origin, left, 90) == Point(0, 10 * MM)  # the left pin goes to the bottom
    assert pin_point(origin, left, 180) == Point(10 * MM, 0)
    assert pin_point(origin, left, 270) == Point(0, -10 * MM)
    assert pin_point(origin, left, 90, "y") == Point(0, -10 * MM)  # the mirror comes first
    with pytest.raises(ValueError, match="rotation"):
        pin_point(origin, left, 45)
    with pytest.raises(ValueError, match="mirror"):
        pin_point(origin, left, 0, "z")


def test_a_label_points_away_from_the_body() -> None:
    assert label_angle(0) == 180 and label_angle(180) == 0  # a pin on the left edge is drawn at angle 0
    assert label_angle(90) == 270 and label_angle(270) == 90
    assert label_angle(0, 0, "y") == 0 and label_angle(0, 90) == 270


def test_proved_frames_hold_the_plain_frame() -> None:
    assert (0, "") in schlayout.PROVED_FRAMES
    assert schlayout.PROVED_FRAMES <= {(r, m) for r in (0, 90, 180, 270) for m in ("", "x", "y")}


# -- the layout


def test_three_parts_on_a4() -> None:
    layout = layout_units(blink())
    assert layout.paper == "A4" and list(layout.origins) == ["D1", "R1", "U1"] and not layout.issues
    check(layout)
    assert layout.cells["D1"][0] < layout.cells["R1"][0] < layout.cells["U1"][0]  # one row, in this order
    assert layout_units(list(reversed(blink()))) == layout


def test_modules_start_rows() -> None:
    layout = layout_units([box("a/R1"), box("b/R1"), box("a/R2"), box("R9")])
    cells = layout.cells
    assert list(layout.origins) == ["R9", "a/R1", "a/R2", "b/R1"]
    assert cells["a/R1"][1] == cells["a/R2"][1] and cells["a/R1"][0] < cells["a/R2"][0]
    assert cells["R9"][3] <= cells["a/R1"][1] and cells["a/R1"][3] <= cells["b/R1"][1]
    assert cells["b/R1"][0] == PAGE_MARGIN
    check(layout)


def test_natural_order_and_units() -> None:
    keys = ["R10", "R2", "U1#2", "U1"]
    layout = layout_units([box(key) for key in keys])
    assert list(layout.origins) == ["R2", "R10", "U1", "U1#2"]


def test_larger_paper() -> None:
    layout = layout_units([box(f"U{n}", "Mini:Mini_QFP32_IC") for n in range(1, 41)])
    assert layout.paper not in ("A4",) and not layout.issues
    check(layout)


def test_too_large() -> None:
    layout = layout_units([box(f"U{n}", "Mini:Mini_QFP32_IC") for n in range(1, 401)])
    (found,) = layout.issues
    assert (found.code, found.severity) == ("build.schematic-too-large", "error") and "400" in found.message
    assert layout.paper == "A0"


def test_flags_take_the_last_row() -> None:
    flag = UnitBox("#flag:GND", (UnitPin("1", Point(0, 0), 90, 3),), (0, 0, 2_540_000, 2_540_000), "f:F")
    layout = layout_units(blink(), flags=[flag])
    assert layout.cells["#flag:GND"][1] >= max(layout.cells[k][3] for k in ("D1", "R1", "U1"))
    check(layout)


def test_a_placed_unit_leaves_the_flow() -> None:
    plain = layout_units(blink())
    place = SymbolPlacement(200 * 1_270_000, 100 * 1_270_000, 90, "y")
    layout = layout_units(blink(), placements={"R1": place})
    assert layout.origins["R1"] == place and not layout.issues
    assert layout.cells["U1"][0] < plain.cells["U1"][0]  # the others flow as if R1 were absent
    assert layout_units([u for u in blink() if u.key != "R1"]).cells["U1"] == layout.cells["U1"]


def test_a_short_between_two_placed_units() -> None:
    r1 = SymbolPlacement(25_400_000, 25_400_000)
    # R1's lower pin (0, -3.81) and D1's left pin (-3.81, 0), turned by 270 degrees, meet at (25.4, 29.21)
    d1 = SymbolPlacement(25_400_000, 29_210_000 + 3_810_000, 270)
    units = {u.key: u for u in blink()}
    assert pin_point(Point(r1.x, r1.y), units["R1"].pins[1].at) in {
        pin_point(Point(d1.x, d1.y), pin.at, 270) for pin in units["D1"].pins
    }
    layout = layout_units(blink(), placements={"R1": r1, "D1": d1})
    assert layout.origins["R1"] == r1
    shorts = [i for i in layout.issues if i.code == "build.symbol-short"]
    assert len(shorts) == 1 and shorts[0].severity == "error"
    assert "R1" in shorts[0].message and "D1" in shorts[0].message
    overlaps = [i.message for i in layout.issues if i.code == "build.symbol-overlap"]
    assert not [m for m in overlaps if "D1 and R1" in m]  # a short is reported once, as the error


def test_overlapping_cells_are_a_warning() -> None:
    layout = layout_units(blink(), placements={"R1": SymbolPlacement(27_940_000, 27_940_000)})
    codes = {(i.code, i.severity) for i in layout.issues}
    assert codes == {("build.symbol-overlap", "warning")}


def test_unknown_placement() -> None:
    layout = layout_units(blink(), placements={"R9": SymbolPlacement(25_400_000, 25_400_000)})
    (found,) = layout.issues
    assert (found.code, found.severity, found.where) == ("build.symbol-placement-unknown", "warning", "R9")
    assert layout.cells == layout_units(blink()).cells


def test_pin_off_the_grid() -> None:
    odd = UnitBox("X1", (UnitPin("1", Point(1_000_000, 0)),), (0, 0, GRID, GRID), "Lib:Odd")
    again = UnitBox("X2", (UnitPin("1", Point(1_000_000, 0)),), (0, 0, GRID, GRID), "Lib:Odd")
    layout = layout_units([odd, again])
    assert [(i.code, i.severity, i.where) for i in layout.issues] == [
        ("kicad.sch.pin-off-grid", "info", "Lib:Odd")
    ]


def test_two_units_with_one_key_are_refused() -> None:
    with pytest.raises(ValueError, match="share a key"):
        layout_units([box("R1"), box("R1")])


@settings(max_examples=40, deadline=None)
@given(
    st.lists(
        st.tuples(st.sampled_from(["", "a/", "b/"]), st.sampled_from(["R", "D", "U"]), st.integers(0, 20)),
        min_size=1,
        max_size=30,
        unique=True,
    ),
    st.integers(0, 12),
)
def test_cells_never_overlap(parts: list[tuple[str, str, int]], chars: int) -> None:
    symbols = {"R": "Mini:Mini_R", "D": "Mini:Mini_LED", "U": "Mini:Mini_QFP32_IC"}
    units = [box(f"{module}{kind}{n}", symbols[kind], p1="N" * chars) for module, kind, n in parts]
    layout = layout_units(units)
    assert not layout.issues and set(layout.origins) == {u.key for u in units}
    check(layout)


def test_the_layout_uses_no_float() -> None:
    source = Path(schlayout.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, float)]
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Div)]


# -- sheet references (c0070)


def test_sheet_references_take_a_row() -> None:
    refs = [RefBox("power", "power", "sheets/power.kicad_sch"), RefBox("io", "io", "sheets/io.kicad_sch")]
    flag = UnitBox("#flag:GND", (UnitPin("1", Point(0, 0), 90, 3),), (0, 0, 2_540_000, 2_540_000), "f:F")
    found = layout_units([box("U1", "Mini:Mini_QFP32_IC")], refs=refs, flags=[flag], sheet="root")
    check(found)
    io, power = (found.origins[schlayout.ref_key(path)] for path in ("io", "power"))
    assert io.y == power.y and io.x < power.x, "one row, in the natural order of the module paths"
    assert io.y >= found.cells["U1"][3], "below the cell of U1"
    assert found.origins["#flag:GND"].y > io.y + schlayout.REF_HEIGHT, "the flags take the last row"
    cell = found.cells[schlayout.ref_key("io")]
    assert cell[0] <= io.x - schlayout.CELL_MARGIN and cell[1] <= io.y - schlayout.CELL_MARGIN
    assert cell[2] >= io.x + schlayout.sheet_ref_size("io") + schlayout.CELL_MARGIN


def test_sheet_reference_size() -> None:
    assert schlayout.sheet_ref_size("io") == schlayout.REF_MIN_WIDTH == 25_400_000
    wide = schlayout.sheet_ref_size("x" * 30)
    assert wide == 50_800_000 and wide % schlayout.ORIGIN_STEP == 0  # 32 characters of 1.524 mm, rounded up
    x0, y0, x1, y1 = schlayout.ref_extent(RefBox("m", "m", "sheets/" + "m" * 40 + ".kicad_sch"))
    assert x1 > schlayout.REF_MIN_WIDTH + schlayout.CELL_MARGIN, "a long file text widens the cell"
    assert (x0, y0) == (-schlayout.CELL_MARGIN, -(schlayout.CELL_MARGIN + schlayout.REF_TEXT))
    assert all(value % schlayout.ORIGIN_STEP == 0 for value in (x0, y0, x1, y1))


def test_too_large_names_the_sheet() -> None:
    found = layout_units([box(f"U{n}", "Mini:Mini_QFP32_IC") for n in range(1, 400)], sheet="power")
    (issue,) = [i for i in found.issues if i.code == "build.schematic-too-large"]
    assert issue.severity == "error" and "sheet power" in issue.message and "399 units" in issue.message

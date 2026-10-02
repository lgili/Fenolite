# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Deterministic sheet layout on hand-made part specs (capability altium-schematic-writer, "Deterministic
sheet layout" and "Connectivity on the sheet"; change c0032)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from fenolite.backends.altium.layout import (
    MARGIN,
    SHEET_SIZES,
    PartSpec,
    PinNet,
    SheetPlan,
    layout_sheet,
    stub_length,
)
from fenolite.backends.altium.symbols import generic_symbol

LABEL_A = PinNet("A", "label")
LABEL_B = PinNet("B", "label")


def spec(key: str, nets: dict[str, PinNet], *, ref: str | None = None, comment: str = "10k") -> PartSpec:
    body = generic_symbol([(d, d) for d in nets])
    name = ref or key.rsplit("/", 1)[-1]
    return PartSpec(key, name, comment, "L.SchLib", "SYM", ("L.PcbLib", "FP"), "AAAAAAAA", body, nets)


def two_pin_parts(count: int) -> list[PartSpec]:
    return [spec(f"R{n}", {"1": LABEL_A, "2": LABEL_B}) for n in range(1, count + 1)]


def points(plan: SheetPlan) -> Iterator[tuple[int, int]]:
    """Every point the writer would write: body corners, pin ends, stub ends, marks and text locations."""
    for part in plan.parts:
        body = part.spec.body
        yield part.x, part.y
        yield part.x + body.width, part.y + body.height
        yield part.x, part.y - 100
        yield part.x, part.y + body.height + 200
        for pin in body.pins:
            for dx, dy in (pin.body_end(body.width), pin.hot_end(body.width)):
                yield part.x + dx, part.y + dy
    for stub in plan.stubs:
        yield stub.start
        yield stub.end
        yield stub.mark


def check_plan(plan: SheetPlan) -> None:
    size = plan.size
    for x, y in points(plan):
        assert x % 100 == 0 and y % 100 == 0, (x, y)
        assert MARGIN <= x <= size.width - MARGIN and MARGIN <= y <= size.height - MARGIN, (x, y)
    cells = [p.cell for p in plan.parts]
    for i, (ax0, ay0, ax1, ay1) in enumerate(cells):
        assert MARGIN <= ax0 < ax1 <= size.width - MARGIN and MARGIN <= ay0 < ay1 <= size.height - MARGIN
        for bx0, by0, bx1, by1 in cells[i + 1 :]:
            assert ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0, "cells overlap"


def test_sheet_sizes() -> None:
    assert [(s.name, s.width, s.height, s.style) for s in SHEET_SIZES] == [
        ("A4", 11_500, 7_600, 0),
        ("A3", 15_500, 11_100, 1),
        ("A2", 22_300, 15_700, 2),
        ("A1", 31_500, 22_300, 3),
        ("A0", 44_600, 31_500, 4),
    ]


def test_small_design_on_a4_in_path_order() -> None:
    parts = [spec(k, {"1": LABEL_A, "2": LABEL_B}) for k in ("U2", "J1", "power/C1", "led/D1", "R2")]
    plan = layout_sheet(parts)
    assert plan.size.name == "A4"
    order = [p.spec.key for p in plan.parts]
    assert order == ["J1", "R2", "U2", "led/D1", "power/C1"]
    positions = [(p.cell[1], p.cell[0]) for p in plan.parts]
    assert positions == sorted(positions), "left to right, then top to bottom"
    check_plan(plan)


def test_larger_sheet_when_needed() -> None:
    parts = two_pin_parts(120)
    plan = layout_sheet(parts)
    assert plan.size.name == "A2"
    before = [s for s in SHEET_SIZES if s.name == "A3"]
    assert layout_sheet(parts, sizes=before).size.name == "custom", "the packing does not fit A3"
    check_plan(plan)


def test_custom_sheet_for_many_parts() -> None:
    plan = layout_sheet(two_pin_parts(700))
    assert plan.size.name == "custom" and plan.size.style is None
    assert plan.size.width == 44_600 and plan.size.height % 1000 == 0 and plan.size.height > 31_500
    check_plan(plan)


def test_custom_sheet_for_a_wide_part() -> None:
    wide = spec("U1", {"1": PinNet("N" * 700, "label"), "2": LABEL_B})
    plan = layout_sheet([wide])
    cell = plan.parts[0].cell
    assert plan.size.name == "custom" and plan.size.width == cell[2] - cell[0] + 2 * MARGIN
    check_plan(plan)


def test_stubs_labels_and_ports() -> None:
    ground, bar = PinNet("GND", "port", "ground"), PinNet("LED_DRV", "label")
    nets = {"1": PinNet("+5V", "port", "bar"), "2": ground, "3": bar, "4": LABEL_A}
    plan = layout_sheet([spec("U2", nets)])
    part = plan.parts[0]
    stubs = {s.designator: s for s in plan.stubs}
    assert [s.designator for s in plan.stubs] == ["1", "2", "3", "4"]
    assert stub_length(ground) == 200 and stub_length(bar) == 700 and stub_length(LABEL_A) == 300
    one, three = stubs["1"], stubs["3"]
    assert one.side == "left" and one.start == (part.x - 200, part.y + 100)
    assert one.end == (part.x - 400, part.y + 100) and one.mark == one.end
    assert three.side == "right" and three.start == (part.x + 800, part.y + 100)
    assert three.end == (part.x + 1500, part.y + 100) and three.mark == (part.x + 900, part.y + 100)
    left_label = layout_sheet([spec("R1", {"1": bar, "2": LABEL_A})]).stubs[0]
    assert left_label.mark == left_label.end and left_label.start[0] - left_label.end[0] == 700


def test_pin_without_a_net_gets_no_stub() -> None:
    body = generic_symbol([("1", "1"), ("2", "2")])
    part = PartSpec("X1", "X1", "SYM", "L.SchLib", "SYM", None, "AAAAAAAA", body, {"1": LABEL_A})
    plan = layout_sheet([part])
    assert [s.designator for s in plan.stubs] == ["1"]
    check_plan(plan)


def test_deterministic_and_order_independent() -> None:
    parts = two_pin_parts(40)
    assert layout_sheet(parts) == layout_sheet(list(reversed(parts))) == layout_sheet(parts)


def test_repeated_path_is_refused() -> None:
    with pytest.raises(ValueError):
        layout_sheet([spec("R1", {"1": LABEL_A}), spec("R1", {"1": LABEL_B})])


def test_empty_design() -> None:
    plan = layout_sheet([])
    assert plan.size.name == "A4" and plan.parts == () and plan.stubs == ()

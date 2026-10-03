# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Deterministic sheet layout on hand-made part specs (capability altium-schematic-writer, "Deterministic
sheet layout" and "Connectivity on the sheet"; change c0032)."""

from __future__ import annotations

import pytest
from _altium import check_plan, sample_model, upright_symbol

from fenolite.backends.altium.altsym import AltiumSymbol, from_generic
from fenolite.backends.altium.layout import (
    MARGIN,
    PORT_GAP,
    PORT_STUB,
    SHEET_SIZES,
    NoConnectMark,
    PartSpec,
    PinNet,
    SheetPlan,
    Stub,
    layout_sheet,
    part_marks,
    part_stubs,
    stub_length,
)
from fenolite.backends.altium.project import plan_sheet
from fenolite.backends.altium.symbols import generic_symbol


def generic_body(pins: list[tuple[str, str]]) -> AltiumSymbol:
    return from_generic(generic_symbol(pins), lib_ref="SYM", prefix="U", comment="SYM", footprint=None)


LABEL_A = PinNet("A", "label")
LABEL_B = PinNet("B", "label")


def spec(key: str, nets: dict[str, PinNet], *, ref: str | None = None, comment: str = "10k") -> PartSpec:
    body = generic_body([(d, d) for d in nets])
    name = ref or key.rsplit("/", 1)[-1]
    return PartSpec(key, name, comment, "L.SchLib", "SYM", ("L.PcbLib", "FP"), "AAAAAAAA", body, nets)


def two_pin_parts(count: int) -> list[PartSpec]:
    return [spec(f"R{n}", {"1": LABEL_A, "2": LABEL_B}) for n in range(1, count + 1)]


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


def _port_reach(stub: Stub) -> int:
    """How far outward from its pin a port's symbol and text reach (100 mil plus 70 mil per character)."""
    return stub.length + 100 + 70 * len(stub.net.net)


def _adjacent_ports(plan: SheetPlan) -> list[tuple[Stub, Stub]]:
    """Pairs (upper, lower) of port stubs on pins one row apart on the same edge of one part."""
    ports = [s for s in plan.stubs if s.net.kind == "port"]
    return [
        (a, b)
        for a in ports
        for b in ports
        if a.key == b.key and a.side == b.side and a.start[0] == b.start[0] and b.start[1] - a.start[1] == 100
    ]


def test_ports_on_adjacent_pins_alternate() -> None:
    """Regression of the maintainer's KiCad 10.0.6 import (2026-10-02): ports of adjacent pins overlapped
    with 200-mil stubs. Supporting data only; the Altium rows stay H-A-SCH-OPEN and H-A-SCH-NETS."""
    names = ("VIN", "GND", "VBAT_LONG", "+5V")
    nets = {str(n): PinNet(names[(n - 1) % 4], "port", "bar") for n in range(1, 9)}
    nets["7"] = LABEL_A
    plan = layout_sheet([spec("U9", nets)])
    lengths = {s.designator: s.length for s in plan.stubs}
    assert [lengths[d] for d in ("1", "2", "3", "4")] == [200, 1100, 200, 1100], "clears both"
    assert [lengths[d] for d in ("5", "6", "7", "8")] == [200, 700, 300, 200], "a label breaks the run"
    pairs = _adjacent_ports(plan)
    assert len(pairs) == 4
    for upper, lower in pairs:
        short, long = (upper, lower) if upper.length <= lower.length else (lower, upper)
        assert short.length == PORT_STUB
        assert long.length - _port_reach(short) >= PORT_GAP, (short, long)
    check_plan(plan)
    ground, vin = PinNet("GND", "port", "ground"), PinNet("VIN", "port", "bar")
    assert stub_length(ground) == PORT_STUB and stub_length(ground, (vin,)) == 700


def test_sample_ports_on_adjacent_pins() -> None:
    """Scenario "Ports on adjacent pins": U1 pins 1 and 2 (and U2 pins 1 and 2) no longer overlap."""
    plan = plan_sheet(sample_model())
    stubs = {(s.key, s.designator): s for s in plan.stubs}
    for key in ("power/U1", "U2"):
        one, two = stubs[(key, "1")], stubs[(key, "2")]
        assert one.length == 200 and two.length == 700, key
        assert two.length - _port_reach(one) >= PORT_GAP
    assert len(_adjacent_ports(plan)) == 2
    assert plan.size.name == "A4"
    check_plan(plan)


def test_pin_without_a_net_gets_no_stub() -> None:
    body = generic_body([("1", "1"), ("2", "2")])
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


# --- library-symbol bodies (change c0034) -----------------------------------------------------------


def test_vertical_stubs_and_marks() -> None:
    port = PinNet("VCC", "port", "bar")
    nets = {"1": LABEL_A, "2": LABEL_B, "3": port}
    part = PartSpec("X1", "X1", "X", "b.SchLib", "X", None, "AAAAAAAA", upright_symbol(), nets)
    plan = layout_sheet([part])
    (placed,) = plan.parts
    stubs = {s.designator: s for s in plan.stubs}
    one, two, three = stubs["1"], stubs["2"], stubs["3"]
    assert one.side == "up" and one.start == (placed.x, placed.y - 150) and one.vertical
    assert one.end[0] == one.start[0] and one.end[1] < one.start[1]
    assert one.mark == (one.start[0], one.start[1] - 100), "an up pin's label sits 100 mil from the pin"
    assert two.side == "down" and two.mark == two.end and two.end[1] > two.start[1]
    assert three.side == "left" and three.mark == three.end and not three.vertical
    check_plan(plan, grid=10)


# --- no-connect marks (change c0036) ----------------------------------------------------------------


def test_no_connect_defaults_are_empty() -> None:
    part = spec("R1", {"1": LABEL_A})
    assert part.no_connects == frozenset()
    plan = layout_sheet([part])
    assert plan.no_connects == () and part_marks(part, 0, 0) == ()


def test_no_connect_marks_sit_on_hot_ends_in_stub_pin_order() -> None:
    nets = {"3": LABEL_A}
    part = PartSpec(
        "X1", "X1", "X", "b.SchLib", "X", None, "AAAAAAAA", upright_symbol(), nets,
        no_connects=frozenset({"2", "1"}),
    )  # fmt: skip
    plan = layout_sheet([part])
    (placed,) = plan.parts
    assert plan.no_connects == (
        NoConnectMark("X1", "1", (placed.x, placed.y - 150)),
        NoConnectMark("X1", "2", (placed.x, placed.y + 150)),
    )
    assert plan.no_connects == part_marks(part, placed.x, placed.y)
    assert [s.designator for s in plan.stubs] == ["3"], "a marked pin gets no stub"
    check_plan(plan, grid=10)


def test_no_connect_cell_is_the_cell_of_an_unconnected_pin() -> None:
    body = generic_body([("1", "1"), ("2", "2")])
    args = ("X1", "X1", "SYM", "L.SchLib", "SYM", None, "AAAAAAAA", body, {"1": LABEL_A})
    plain, marked = PartSpec(*args), PartSpec(*args, no_connects=frozenset({"2"}))
    one, two = layout_sheet([plain]), layout_sheet([marked])
    assert (one.size, one.stubs) == (two.size, two.stubs)
    assert [(p.x, p.y, p.cell) for p in one.parts] == [(p.x, p.y, p.cell) for p in two.parts]
    assert part_stubs(marked, 0, 0) == part_stubs(plain, 0, 0)
    assert [m.designator for m in two.no_connects] == ["2"]


def test_no_connect_marks_follow_component_then_part_order() -> None:
    first = spec("R2", {"1": LABEL_A, "2": LABEL_B})
    marked = [
        PartSpec(
            key,
            key,
            "SYM",
            "L.SchLib",
            "SYM",
            None,
            uid,
            generic_body([("1", "1"), ("2", "2")]),
            {},
            no_connects=frozenset({"1", "2"}),
        )  # fmt: skip
        for key, uid in (("R3", "AAAAAAAB"), ("R1", "AAAAAAAC"))
    ]
    plan = layout_sheet([first, *marked])
    assert [(m.key, m.designator) for m in plan.no_connects] == [
        ("R1", "1"), ("R1", "2"), ("R3", "1"), ("R3", "2"),
    ]  # fmt: skip

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Deterministic sheet layout on hand-made part specs (capability altium-schematic-writer, "Deterministic
sheet layout" and "Connectivity on the sheet"; change c0032)."""

from __future__ import annotations

import pytest
from _altium import check_plan, hier_model, sample_model, upright_symbol

from fenolite.backends.altium.altsym import AltiumSymbol, from_generic
from fenolite.backends.altium.hierarchy import plan_sheets
from fenolite.backends.altium.layout import (
    ENTRY_PITCH,
    MARGIN,
    PORT_GAP,
    PORT_STUB,
    SHEET_SIZES,
    SYMBOL_MIN_WIDTH,
    Crossing,
    HarnessBlock,
    NoConnectMark,
    PartSpec,
    PinNet,
    SheetPlan,
    Stub,
    SymbolSpec,
    layout_sheet,
    part_marks,
    part_stubs,
    port_width,
    stub_length,
    text_width,
)
from fenolite.backends.altium.project import part_specs, plan_sheet
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


# --- sheet symbols and ports (change c0037) ---------------------------------------------------------


def _symbol(module: str, *names: str) -> SymbolSpec:
    return SymbolSpec(module, f"d_{module}.SchDoc", "AAAAAAAA", tuple(Crossing(n) for n in names))


def test_plan_without_symbols_is_unchanged() -> None:
    """Scenario "Plan without symbols is unchanged": the keyword defaults change nothing."""
    specs = part_specs(sample_model(), name="altium_sample")
    plain = layout_sheet(specs)
    assert (
        layout_sheet(specs, symbols=(), ports=()) == plain == plan_sheet(sample_model(), name="altium_sample")
    )
    assert plain.symbols == () and plain.ports == () and plain.harnesses == () and plain.links == ()


def test_symbol_and_port_cells_come_before_the_component_cells() -> None:
    parts = two_pin_parts(2)
    plan = layout_sheet(parts, symbols=[_symbol("b", "N1"), _symbol("a")], ports=[Crossing("P1")])
    cells = [*(s.cell for s in plan.symbols), *(p.cell for p in plan.ports), *(p.cell for p in plan.parts)]
    assert [s.spec.module for s in plan.symbols] == ["b", "a"], "symbols keep the order given"
    assert [(c[1], c[0]) for c in cells] == sorted((c[1], c[0]) for c in cells), "one packing, in order"
    assert cells[0][:2] == (MARGIN, MARGIN)
    check_plan(plan)


def test_sheet_symbol_geometry() -> None:
    plan = layout_sheet([], symbols=[_symbol("mcu", "RESET_N", "A_LONGER_NET")])
    (symbol,) = plan.symbols
    assert symbol.width == SYMBOL_MIN_WIDTH == 1500 and symbol.height == 300, "(slots + 1) x 100 mil"
    assert [(e.crossing.name, e.slot) for e in symbol.entries] == [
        ("RESET_N", 1),
        ("A_LONGER_NET", 2),
    ]
    for entry in symbol.entries:
        assert entry.point == (symbol.x + symbol.width, symbol.y + ENTRY_PITCH * entry.slot)
        assert entry.block is None and entry.stub is not None
        stub = entry.stub
        assert (
            stub.side == "right"
            and stub.start == entry.point
            and stub.net == PinNet(entry.crossing.name, "label")
        )
        assert stub.length == stub_length(stub.net) and stub.mark == (stub.start[0] + 100, stub.start[1])
        assert stub.end[0] + 200 <= symbol.cell[2], "the label stays inside the cell"
    assert plan.links == tuple(e.stub for e in symbol.entries)
    assert symbol.cell[1] <= symbol.y - 400, "room for the name and file name above the symbol"
    check_plan(plan)


def test_sheet_symbol_is_wide_enough_for_its_texts() -> None:
    long = "N" * 40
    plan = layout_sheet([], symbols=[_symbol("m", long)])
    assert plan.symbols[0].width == text_width(long) == 3000
    empty = layout_sheet([], symbols=[_symbol("m")]).symbols[0]
    assert empty.entries == () and empty.height == 100 and empty.width == 1500


def test_port_geometry() -> None:
    plan = layout_sheet(two_pin_parts(1), ports=[Crossing("EN"), Crossing("A_RATHER_LONG_NET_NAME")])
    short, long = plan.ports
    assert (
        short.width == port_width("EN") == 300 and long.width == port_width("A_RATHER_LONG_NET_NAME") == 1700
    )
    for port in plan.ports:
        assert port.end == (port.x + port.width, port.y) and port.block is None and port.stub is not None
        assert port.stub.start == port.end and port.stub.side == "right"
        assert port.stub.net == PinNet(port.crossing.name, "label")
    assert plan.links == (short.stub, long.stub) and len(plan.stubs) == 2
    check_plan(plan)


def test_hierarchical_sheet_picks_its_own_size() -> None:
    many = [_symbol(f"m{n:03d}", "A", "B") for n in range(60)]
    assert layout_sheet([], symbols=many[:4]).size.name == "A4"
    larger = layout_sheet([], symbols=many)
    assert larger.size.name != "A4"
    check_plan(larger)
    wide = layout_sheet([], ports=[Crossing("N" * 700)])
    assert wide.size.name == "custom"
    check_plan(wide)


def test_repeated_port_or_entry_name_is_refused() -> None:
    with pytest.raises(ValueError, match="share a name"):
        layout_sheet([], ports=[Crossing("A"), Crossing("A")])
    with pytest.raises(ValueError, match="share a name"):
        layout_sheet([], symbols=[_symbol("m", "A", "A")])


def test_top_sheet_of_the_sample_in_the_ascii_form() -> None:
    project = plan_sheets(hier_model(), name="altium_hier", sheets="modules", form="ascii")
    top = project.top.plan
    assert [s.spec.module for s in top.symbols] == ["flash", "mcu"] and [p.spec.ref for p in top.parts] == [
        "J1"
    ]
    assert [s.spec.file for s in top.symbols] == ["altium_hier_flash.SchDoc", "altium_hier_mcu.SchDoc"]
    assert [len(s.entries) for s in top.symbols] == [5, 6]
    assert top.size.name == "A4"
    for sheet in project.sheets:
        check_plan(sheet.plan)
    assert [[p.crossing.name for p in s.plan.ports] for s in project.modules] == [
        ["FLASH_WP", "SPI_CS", "SPI_MISO", "SPI_MOSI", "SPI_SCK"],
        ["FLASH_WP", "RESET_N", "SPI_CS", "SPI_MISO", "SPI_MOSI", "SPI_SCK"],
    ]


# --- harness blocks (change c0037, design Decision 17) ----------------------------------------------

SPI = Crossing(
    "SPI", "AAAAAAAB", (("CS", "SPI_CS"), ("MISO", "SPI_MISO"), ("MOSI", "SPI_MOSI"), ("SCK", "SPI_SCK"))
)


def _check_block(block: HarnessBlock, start: tuple[int, int]) -> None:
    count = len(block.entries)
    assert block.height == (count + 1) * 100 and block.width >= 500 and block.width % 100 == 0
    assert block.position == 100 * ((count + 1) // 2)
    assert block.line == (start, (start[0] + 200, start[1])), "a 200 mil harness line on one horizontal line"
    assert (block.x, block.y + block.position) == block.line[1], "it ends on the connector's left edge"
    wired = [(k, net) for k, (_, net) in enumerate(block.entries, start=1) if net is not None]
    assert [(s.start, s.net.net) for s in block.stubs] == [(block.entry_point(k), net) for k, net in wired]
    for stub in block.stubs:
        assert stub.side == "right" and stub.length == stub_length(stub.net)
        assert stub.mark == (stub.start[0] + 100, stub.start[1])


def test_harness_block_beside_a_port() -> None:
    plan = layout_sheet(two_pin_parts(1), ports=[Crossing("EN"), SPI])
    net, harness = plan.ports
    assert net.block is None and harness.stub is None and harness.block is not None
    assert plan.harnesses == (harness.block,)
    _check_block(harness.block, harness.end)
    assert harness.block.name == "SPI" and harness.block.height == 500 and harness.block.position == 200
    assert [s.designator for s in harness.block.stubs] == ["CS", "MISO", "MOSI", "SCK"]
    assert plan.links == (net.stub, *harness.block.stubs)
    assert harness.cell[1] <= harness.block.y - 300 and harness.cell[3] >= harness.block.y + 700
    check_plan(plan)


def test_harness_entry_takes_m_plus_two_slots() -> None:
    spec = SymbolSpec("mcu", "d_mcu.SchDoc", "AAAAAAAA", (Crossing("A"), SPI, Crossing("Z")))
    plan = layout_sheet([], symbols=[spec])
    (symbol,) = plan.symbols
    first, harness, last = symbol.entries
    assert (first.slot, harness.slot, last.slot) == (1, 4, 8), "slots 2 to 7 belong to the harness"
    assert symbol.height == 900, "(8 slots + 1) x 100 mil"
    assert harness.block is not None and harness.stub is None
    _check_block(harness.block, harness.point)
    assert harness.block.y == symbol.y + 200, "the connector spans the harness's slots"
    assert harness.block.y + harness.block.height == symbol.y + 700
    ys = [s.start[1] for s in plan.links]
    assert ys == sorted(ys) and len(set(ys)) == len(ys), "no two wires share a row"
    assert plan.harnesses == (harness.block,)
    check_plan(plan)


def test_harness_blocks_of_two_harness_entries_do_not_touch() -> None:
    other = Crossing("DBG", "AAAAAAAC", (("RX", "DBG_RX"), ("TX", None), ("VREF", "DBG_VREF")))
    spec = SymbolSpec("m", "d_m.SchDoc", "AAAAAAAA", (other, SPI))
    (symbol,) = layout_sheet([], symbols=[spec]).symbols
    one, two = (entry.block for entry in symbol.entries)
    assert one is not None and two is not None
    assert [e.slot for e in symbol.entries] == [3, 8] and symbol.height == 1200
    assert one.position == 200 and one.height == 400
    assert one.y + one.height < two.y, "a free row between two connectors"
    assert [s.designator for s in one.stubs] == ["RX", "VREF"], "an entry without a net gets no wire"
    assert one.entry_point(2) not in {s.start for s in one.stubs}


def test_harness_connector_is_wide_enough_for_its_names() -> None:
    wide = Crossing("T", "AAAAAAAD", (("A_VERY_LONG_ENTRY_NAME", "N"),))
    block = layout_sheet([], ports=[wide]).harnesses[0]
    assert block.width == text_width("A_VERY_LONG_ENTRY_NAME") == 1700 and block.height == 200
    assert block.position == 100


def test_harness_top_sheet_of_the_sample() -> None:
    """Scenario "Top sheet of the sample": the cells are the symbols ``flash`` and ``mcu`` and the part
    ``J1``, nothing overlaps, every point is inside the margins, and the sheet is A4."""
    project = plan_sheets(hier_model(), name="altium_hier", sheets="modules", form="binary")
    top = project.top.plan
    assert [s.spec.module for s in top.symbols] == ["flash", "mcu"] and [p.spec.ref for p in top.parts] == [
        "J1"
    ]
    cells = [*(s.cell for s in top.symbols), *(p.cell for p in top.parts)]
    assert [(c[1], c[0]) for c in cells] == sorted((c[1], c[0]) for c in cells)
    assert top.size.name == "A4" and top.ports == ()
    flash, mcu = top.symbols
    assert [(e.crossing.name, e.slot, e.side) for e in flash.entries] == [
        ("FLASH_WP", 1, "right"),
        ("SPI", 2, "right"),
    ]
    assert [(e.crossing.name, e.slot, e.side) for e in mcu.entries] == [
        ("FLASH_WP", 1, "right"),
        ("RESET_N", 2, "right"),
        ("SPI", 2, "left"),
    ]
    assert (flash.height, mcu.height) == (300, 300)
    assert top.harnesses == () and len(top.links) == 3, "the SPI entries have no block and no label"
    (line,) = top.lines
    start, end = line
    assert start == (flash.x + flash.width, flash.y + 200) and end == (mcu.x, mcu.y + 200)
    assert start[1] == end[1] and end[0] - start[0] >= 2 * 200, "a straight line across both cell margins"
    for sheet in project.sheets:
        check_plan(sheet.plan)
        assert sheet.plan.size.name == "A4"

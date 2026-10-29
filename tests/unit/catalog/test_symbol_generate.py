# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Symbols generated from pin tables (change c0261, capability symbol-generation; hypothesis
``H-G-SYMBOL-LAYOUT``)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from fenolite.backends.kicad import symembed
from fenolite.backends.kicad.sym import resolve_extends
from fenolite.catalog.generate import symbol as gen
from fenolite.catalog.generate.symbol import G, generate_symbol, sides
from fenolite.catalog.pins import parse_pins, read_pins
from fenolite.model.canonical import dumps
from fenolite.model.library import PinRow, PinTable, SymbolDef

DATA = Path(__file__).resolve().parents[2] / "data" / "pins"
BUCK = DATA / "example_buck.toml"
DUAL = DATA / "example_dual.toml"


def _table(rows: list[PinRow], **settings_: object) -> PinTable:
    return PinTable("T", tuple(rows), namespace="Example", version="1.0.0", summary="t", **settings_)  # type: ignore[arg-type]


def _points(symbol: SymbolDef) -> list[int]:
    values: list[int] = []
    for pin in symbol.pins:
        values += [pin.position.x, pin.position.y, pin.length]
    for graphic in symbol.graphics:
        for point in graphic.points:
            values += [point.x, point.y]
    return values


def test_regulator_sides() -> None:
    base, _, issues = generate_symbol(read_pins(BUCK), library="Example")
    assert sides(base) == {"left": ("FB", "EN"), "right": ("SW", "BST"), "top": ("VIN",), "bottom": ("GND",)}
    by_name = {pin.name: pin for pin in base.pins if not pin.hidden}
    # a gap between FB (input) and EN (control); SW (output), a gap, then BST (passive moved right)
    assert by_name["FB"].position.y - by_name["EN"].position.y == 2 * G
    assert by_name["SW"].position.y - by_name["BST"].position.y == 2 * G
    assert (by_name["FB"].rotation, by_name["SW"].rotation) == (0, 180_000_000)
    assert (by_name["VIN"].rotation, by_name["GND"].rotation) == (270_000_000, 90_000_000)
    assert base.reference == "U" and base.value == "EXB6202" and base.lib_id == "Example:EXB6202"
    assert base.keywords == ("regulator", "buck")
    assert issues == ()


def test_interleaved_data_pins() -> None:
    rows = [PinRow(name, name, "input") for name in ("D10", "CLK", "D2", "D1")]
    base, _, issues = generate_symbol(_table(rows), library="L")
    assert sides(base)["left"] == ("D1", "D2", "D10", "CLK")
    gaps = [i for i in issues if i.code == "symbol.bus-gap"]
    assert len(gaps) == 1 and "bus D" in gaps[0].message and "3, 4, 5, 6, 7, 8, 9" in gaps[0].message
    assert gaps[0].severity == "info"


def test_explicit_bus_and_auto_bus_off() -> None:
    rows = [
        PinRow("1", "A3", "input", bus="ADDR"),
        PinRow("2", "X", "input"),
        PinRow("3", "A1", "input", bus="ADDR"),
    ]
    base, _, issues = generate_symbol(_table(rows, auto_bus=False), library="L")
    assert sides(base)["left"] == ("A1", "A3", "X")
    assert [i.code for i in issues] == ["symbol.bus-gap"]
    plain = [PinRow("1", "D2", "input"), PinRow("2", "X", "input"), PinRow("3", "D1", "input")]
    base, _, _ = generate_symbol(_table(plain, auto_bus=False), library="L")
    assert sides(base)["left"] == ("D2", "X", "D1")


def test_default_groups() -> None:
    assert gen.default_group(PinRow("1", "AGND", "power_in")) == "ground"
    assert gen.default_group(PinRow("1", "EP", "power_in")) == "ground"
    assert gen.default_group(PinRow("1", "VDD", "power_in")) == "supply"
    assert gen.default_group(PinRow("1", "X", "open_collector")) == "output"
    assert gen.default_group(PinRow("1", "X", "bidirectional")) == "io"
    assert gen.default_group(PinRow("1", "X", "free")) == "passive"
    assert gen.default_group(PinRow("1", "X", "no_connect")) == "nc"
    assert gen.default_group(PinRow("1", "VSS", "power_in", group="supply")) == "supply"


def test_exposed_pad_stacked_on_ground() -> None:
    base, _, _ = generate_symbol(read_pins(BUCK), library="Example")
    pins = {pin.number: pin for pin in base.pins}
    assert pins["7"].position == pins["2"].position
    assert pins["7"].hidden and pins["7"].etype == "passive" == symembed.STACKED_TYPE == gen.STACKED_TYPE
    assert pins["7"].alternates == () and not pins["2"].hidden


def test_ordering_variant() -> None:
    base, derived, _ = generate_symbol(read_pins(BUCK), library="Example")
    assert len(derived) == 1
    variant = derived[0]
    assert (variant.extends, variant.value, variant.library, variant.pins) == (
        "EXB6202",
        "EXB6202DR",
        "Example",
        (),
    )
    assert variant.units == () and variant.graphics == ()
    flat = resolve_extends([base, variant])[1]
    assert flat.pins == base.pins and flat.value == "EXB6202DR" and flat.reference == "U"


def test_footprint_and_filters() -> None:
    base, _, _ = generate_symbol(
        read_pins(BUCK), library="E", footprint="E:SOT", fp_filters=("SOT*", "TSOT*")
    )
    assert base.footprint == "E:SOT" and base.footprint_filters == ("SOT*", "TSOT*")


def _body_encloses(symbol: SymbolDef) -> None:
    for graphic in symbol.graphics:
        (x0, y0), (x1, y1) = ((p.x, p.y) for p in graphic.points)
        for pin in symbol.pins_of(graphic.unit or 1):
            dx, dy = {0: (1, 0), 90_000_000: (0, 1), 180_000_000: (-1, 0), 270_000_000: (0, -1)}[pin.rotation]
            ex, ey = pin.position.x + dx * pin.length, pin.position.y + dy * pin.length
            assert x0 <= ex <= x1 and y0 <= ey <= y1, (pin.number, ex, ey, graphic)
            on_edge = ex in (x0, x1) or ey in (y0, y1)
            assert on_edge


def test_two_bodies() -> None:
    base, derived, issues = generate_symbol(read_pins(DUAL), library="Example")
    assert [(g.unit, g.body_style, g.kind) for g in base.graphics] == [(1, 1, "rect"), (2, 1, "rect")]
    assert [(u.unit, u.name) for u in base.units] == [(1, "A"), (2, "B")]
    _body_encloses(base)
    assert derived[0].properties["ki_fp_filters"] == "SOIC* TSSOP*"
    assert issues == ()


def test_explicit_common_pins_in_every_unit() -> None:
    base, _, _ = generate_symbol(read_pins(DUAL), library="Example")
    common = [pin for pin in base.pins if pin.unit == 0]
    assert sorted(pin.name for pin in common) == ["GND", "NC", "VCC"]
    for unit in (1, 2):
        assert {p.name for p in common} <= {p.name for p in base.pins_of(unit)}
    for unit in (1, 2):  # a unit's own pins never sit on a common pin
        positions = [pin.position for pin in base.pins_of(unit)]
        assert len(set(positions)) == len(positions)


def _mcu_rows() -> list[PinRow]:
    rows: list[PinRow] = []
    rows += [PinRow(f"S{i}", f"VDD{i}", "power_in") for i in range(12)]
    for port in "ABCD":
        rows += [PinRow(f"{port}{i}", f"P{port}{i}", "bidirectional") for i in range(16)]
    rows += [PinRow(f"I{i}", f"IN{i}", "input") for i in range(32)]
    rows += [PinRow(f"G{i}", f"VSS{i}", "power_in") for i in range(12)]
    return rows


def test_a_120_pin_part() -> None:
    rows = _mcu_rows()
    assert len(rows) == 120
    base, _, issues = generate_symbol(_table(rows), library="L")
    assert base.unit_count == 3
    counts = [len([p for p in base.pins if p.unit == u]) for u in range(1, 4)]
    assert counts == [48, 48, 24]
    for unit in range(1, base.unit_count):
        names = {p.name[:2] for p in base.pins if p.unit == unit and p.name.startswith("P")}
        for port in names:  # whole buses: each port's 16 pins are in one unit
            assert len([p for p in base.pins if p.unit == unit and p.name.startswith(port)]) == 16
    power = [p for p in base.pins if p.unit == base.unit_count]
    assert len(power) == 24 and all(p.etype == "power_in" for p in power)
    assert [i.code for i in issues] == ["symbol.units-split"]
    assert "3 units" in issues[0].message
    _body_encloses(base)
    assert len(base.graphics) == 3


def test_unit_bus_split_warning() -> None:
    rows = [PinRow(str(i), f"D{i}", "bidirectional") for i in range(60)]
    rows += [PinRow(f"x{i}", f"X{i}a", "input") for i in range(50)]
    base, _, issues = generate_symbol(_table(rows), library="L")
    codes = [i.code for i in issues]
    assert "symbol.bus-split" in codes and "symbol.units-split" in codes
    assert all(len([p for p in base.pins if p.unit == u]) <= 48 for u in range(1, base.unit_count + 1))


def test_explicit_units_win() -> None:
    rows = [PinRow(str(i), f"N{i}x", "input", unit=1 + i % 3) for i in range(148)]
    rows += [PinRow("V", "VCC", "power_in", unit=0), PinRow("G", "GND", "power_in", unit=0)]
    base, _, issues = generate_symbol(_table(rows), library="L")
    assert base.unit_count == 3
    assert all("symbol.units-split" != i.code for i in issues)
    for unit in (1, 2, 3):
        assert {"VCC", "GND"} <= {p.name for p in base.pins_of(unit)}


def test_below_threshold_is_one_unit_with_a_common_body() -> None:
    rows = [PinRow(str(i), f"N{i}x", "input") for i in range(100)]
    base, _, issues = generate_symbol(_table(rows), library="L")
    assert base.unit_count == 1 and issues == ()
    assert [(g.unit, g.body_style) for g in base.graphics] == [(0, 0)]
    assert {(p.unit, p.body_style) for p in base.pins} == {(1, 1)}


# --- H-G-SYMBOL-LAYOUT: grid, purity and locality ---------------------------------------------------

_TYPES = st.sampled_from(
    ["input", "output", "bidirectional", "tri_state", "passive", "power_in", "power_out", "open_collector",
     "no_connect", "free", "unspecified", "open_emitter"]
)  # fmt: skip
_NAMES = st.from_regex(r"[A-Z]{1,6}[0-9]{0,2}", fullmatch=True)


@st.composite
def _tables(draw: st.DrawFn) -> PinTable:
    count = draw(st.integers(1, 140))
    names = draw(st.lists(_NAMES, min_size=count, max_size=count))
    rows = []
    for index, name in enumerate(names):
        etype = draw(_TYPES)
        side = draw(st.sampled_from(["", "", "", "left", "right", "top", "bottom"]))
        rows.append(
            PinRow(
                str(index + 1),
                name,
                etype,
                side=side,
                hidden=etype != "power_in" and draw(st.booleans()) and index % 7 == 0,
            )
        )  # type: ignore[arg-type]
    return _table(
        rows, split_above=draw(st.sampled_from([16, 50, 100])), unit_pins=draw(st.sampled_from([8, 24, 48]))
    )


@settings(max_examples=60, deadline=None)
@given(_tables())
def test_grid_property(table: PinTable) -> None:
    base, _, _ = generate_symbol(table, library="L")
    assert all(value % G == 0 for value in _points(base))
    again, _, _ = generate_symbol(table, library="L")
    assert dumps(again) == dumps(base)
    assert dumps(parse_pins_roundtrip(table)) == dumps(table)
    _body_encloses(base)
    for unit in range(1, base.unit_count + 1):
        visible = [p.position for p in base.pins_of(unit) if not (p.hidden and p.etype == "passive")]
        assert len(visible) == len(set(visible)) or any(r.stacked for r in table.rows)


def parse_pins_roundtrip(table: PinTable) -> PinTable:
    from fenolite.catalog.pins import pins_text

    filled = dataclasses.replace(table, licence="CC0-1.0", evidence="UNVERIFIED")
    back = parse_pins(pins_text(filled))
    return dataclasses.replace(back, licence=table.licence, evidence=table.evidence)


@settings(max_examples=60, deadline=None)
@given(_tables(), _NAMES)
def test_a_one_pin_edit_stays_local(table: PinTable, name: str) -> None:
    table = dataclasses.replace(table, split_above=1000)
    added = dataclasses.replace(table, rows=(*table.rows, PinRow("9999", name[:2], "output")))
    old, _, _ = generate_symbol(table, library="L")
    new, _, _ = generate_symbol(added, library="L")
    before = {p.number: p for p in old.pins}
    after = {p.number: p for p in new.pins}
    side_of = {0: "left", 180_000_000: "right", 270_000_000: "top", 90_000_000: "bottom"}
    moved: dict[str, set[tuple[int, int]]] = {}
    for number, pin in before.items():
        side = side_of[pin.rotation]
        if side == "right":
            continue
        delta = (after[number].position.x - pin.position.x, after[number].position.y - pin.position.y)
        moved.setdefault(side, set()).add(delta)
    grew = old.graphics[0].points != new.graphics[0].points
    for side, deltas in moved.items():
        assert len(deltas) == 1, (side, deltas)
        if not grew:
            assert deltas == {(0, 0)}


def test_layout_constants() -> None:
    assert (gen.G, gen.L, gen.A, gen.STROKE) == (2_540_000, 2_540_000, 1_016_000, 254_000)
    assert gen.G % 254_000 == 0  # the Altium writer's 10-mil grid
    assert gen.ceil2g(1) == 2 * G and gen.ceil2g(2 * G) == 2 * G
    assert gen.name_width("~{OE}") == 2 and gen.name_width("~") == 0
    assert parse_pins  # the table parser is the generator's input


def test_symbols_facts_page() -> None:
    import importlib.util
    import re

    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("_facts", root / "tests" / "unit" / "test_format_facts.py")
    assert spec is not None and spec.loader is not None
    facts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(facts)
    table_problems = facts.table_problems
    page = (root / "docs" / "formats" / "library" / "symbols.md").read_text(encoding="utf-8")
    assert table_problems("symbols.md", page, r"\bH-G-SYMBOL-LAYOUT\b") == []
    assert "| fact | source | label | hypothesis |" in page
    for name, value in (("G", gen.G), ("L", gen.L), ("A", gen.A)):
        shown = f"{value:,}".replace(",", " ")
        assert re.search(rf"\| `{name}` \| {shown} nm", page), name

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``Fenolite.KiCad.Sheet`` carrier keeps what Altium's records drop: the label kinds and their written
text, sheet symbol fields, symbol field poses under a mirror (change c0470, task 5.4)."""

from __future__ import annotations

import pytest

from fenolite.backends.altium import drawn_carrier, drawn_read
from fenolite.backends.altium.read.sch.units import SchLength
from fenolite.core.coords import Point, Size
from fenolite.model.drawn import (
    DrawnField,
    DrawnFont,
    DrawnLabel,
    DrawnPin,
    DrawnSheetProperty,
    DrawnSheetRef,
    DrawnSymbol,
)

_FONT = DrawnFont(Size(1_524_000, 1_524_000))


def test_label_restored_after_a_scope_rename() -> None:
    label = DrawnLabel("local", "CLK", Point(1_000, 2_000), font=_FONT, justify="left")
    sheet = drawn_carrier.carrier((), labels=[drawn_carrier.written_label(label)])
    assert sheet is not None
    carried = drawn_carrier.KiCadSheet.parse(sheet.value())
    read = DrawnLabel("global", "__local_ab_CLK", label.at)
    assert drawn_carrier.labels_of(carried.labels, [read]) == [label]
    other = DrawnLabel("global", "__local_ab_CLK", Point(0, 0))
    assert drawn_carrier.labels_of(carried.labels, [other]) == [other]


def test_two_labels_at_one_position_told_apart_by_text() -> None:
    at = Point(0, 0)
    a = DrawnLabel("local", "A", at, font=_FONT)
    b = DrawnLabel("hierarchical", "B", at, shape="input")
    values = [drawn_carrier.written_label(a), drawn_carrier.written_label(b)]
    read = [DrawnLabel("global", "B", at), DrawnLabel("global", "X", at)]
    assert drawn_carrier.labels_of(values, read) == [b, read[1]]


def test_two_labels_of_one_text_at_one_position_told_apart_by_rotation() -> None:
    """A local label written as a port at the point of a hierarchical label of its text: each read label
    takes the carried one of its rotation, and each carried label is restored once."""
    at = Point(0, 0)
    local = DrawnLabel("local", "SCL", at, justify="left bottom")
    port = DrawnLabel("hierarchical", "SCL", at, 180_000_000, shape="bidirectional")
    other = Point(at.x + 254_000, at.y)
    values = [drawn_carrier.written_label(local, other), drawn_carrier.written_label(port, other)]
    read = [DrawnLabel("hierarchical", "SCL", at, 180_000_000), DrawnLabel("hierarchical", "SCL", at)]
    assert drawn_carrier.labels_of(values, read) == [port, local]


def test_a_long_value_goes_in_numbered_parts() -> None:
    value = "x" * (2 * drawn_carrier.PART_SIZE + 5)
    cut = drawn_carrier.parts(value)
    assert [len(part) for part in cut] == [drawn_carrier.PART_SIZE, drawn_carrier.PART_SIZE, 5]
    names = [drawn_carrier.part_name(i) for i in range(len(cut))]
    assert names == [drawn_carrier.NAME, f"{drawn_carrier.NAME}.2", f"{drawn_carrier.NAME}.3"]
    found = {drawn_carrier.part_index(name): part for name, part in zip(names, cut, strict=True)}
    assert drawn_carrier.joined(found) == value  # pyright: ignore[reportArgumentType]
    assert drawn_carrier.part_index(f"{drawn_carrier.NAME}.1") is None
    assert drawn_carrier.part_index(f"{drawn_carrier.NAME}.02") is None
    assert drawn_carrier.part_index("Title") is None
    with pytest.raises(ValueError, match="not numbered"):
        drawn_carrier.joined({0: "a", 2: "c"})


def test_sheet_ref_fields_restored_by_position() -> None:
    at = Point(10_000, 20_000)
    ref = DrawnSheetRef(
        "k",
        "child",
        "child",
        "Child",
        at,
        Size(5_000, 5_000),
        "2",
        "child.kicad_sch",
        pins=(DrawnPin("A", "input", Point(10_000, 21_000), font=_FONT, justify="right"),),
        fields=(DrawnField("Sheetname", Point(10_000, 19_000), font=_FONT),),
        properties=(DrawnSheetProperty("Note", "x", Point(11_000, 26_000), hide=True),),
    )
    sheet = drawn_carrier.carrier((), sheet_refs=[drawn_carrier.sheet_ref_value(ref)])
    assert sheet is not None
    carried = drawn_carrier.KiCadSheet.parse(sheet.value())
    read = DrawnSheetRef(
        "k", "child", "child", "Child", at, ref.size, "2", "child.kicad_sch",
        pins=(DrawnPin("A", "input", Point(10_000, 21_000)),),
    )  # fmt: skip
    assert drawn_carrier.sheet_refs_of(carried.sheet_refs, [read]) == [ref]


def test_symbol_fields_restored_under_a_mirror_about_x() -> None:
    """Altium writes one mirror flag: a mirror about X reads back as a mirror about Y and a half turn."""
    symbol = DrawnSymbol(
        "Q1", 1, Point(0, 0), 90_000_000, "x", (DrawnField("Reference", Point(1_000, 0), font=_FONT),)
    )
    read = DrawnSymbol("Q1", 1, Point(0, 0), 270_000_000, "y")
    assert drawn_carrier.symbol_of(drawn_carrier.symbol_value(symbol), read) == symbol
    turned = DrawnSymbol("Q1", 1, Point(0, 0), 0, "y")
    assert drawn_carrier.symbol_of(drawn_carrier.symbol_value(symbol), turned) == turned


def test_carrier_without_the_new_sections_still_parses() -> None:
    sheet = drawn_carrier.carrier(("(text x)",))
    assert sheet is not None
    parsed = drawn_carrier.KiCadSheet.parse(sheet.value())
    assert parsed.labels == () and parsed.sheet_refs == ()


def test_exact_coordinates_come_back_through_the_frame() -> None:
    """A length off Altium's 127/50 nm step is rounded in the record; the carrier keeps it and the
    reader's frame puts it back for that coordinate only."""
    sheet = drawn_carrier.carrier((), exact={100_001: 254_003})
    assert sheet is not None
    carried = drawn_carrier.KiCadSheet.parse(sheet.value())
    assert carried.exact == ((100_001, 254_003),)
    frame = drawn_read.Frame(1_000_000, 500_000, "A4", exact=dict(carried.exact))
    at = frame.point((SchLength(100_001), SchLength(500_000 - 100_001)))
    assert at == Point(254_003, 254_003)
    plain = frame.point((SchLength(100_000), SchLength(400_000)))
    assert plain == Point(SchLength(100_000).nm(), SchLength(100_000).nm())


def test_carrier_without_exact_coordinates_has_no_key() -> None:
    sheet = drawn_carrier.carrier(("(text x)",))
    assert sheet is not None
    assert '"exact"' not in sheet.text()


def test_opaque_symbol_definitions_travel_by_lib_id() -> None:
    """A KiCad symbol Altium does not draw keeps its sheet's definition text for the way back."""
    text = '(kicad_symbol_lib (version 20241209) (generator "x") (symbol "Logo"))'
    sheet = drawn_carrier.carrier(('(symbol (lib_id "Graphic:Logo"))',), definitions={"Graphic:Logo": text})
    assert sheet is not None
    carried = drawn_carrier.KiCadSheet.parse(sheet.value())
    assert carried.definitions == {"Graphic:Logo": text}
    assert drawn_carrier.KiCadSheet.parse(drawn_carrier.carrier(("(text x)",)).value()).definitions == {}  # pyright: ignore[reportOptionalMemberAccess]

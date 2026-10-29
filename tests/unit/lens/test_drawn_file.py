# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``schematic.toml``, schema ``fenolite.drawn-schematic.v0`` (capability drawn-schematic, "Drawn schematic
file", "Drawn file numbers", "Drawn sheet items" and "Canonical drawn file"; change c0276)."""

from __future__ import annotations

import _drawn
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError
from fenolite.lens.drawn import mm, read_drawn, write_drawn
from fenolite.model.drawn import (
    DrawnBusEntry,
    DrawnField,
    DrawnJunction,
    DrawnLabel,
    DrawnOpaque,
    DrawnPin,
    DrawnPower,
    DrawnSchematic,
    DrawnSheet,
    DrawnSheetRef,
    DrawnSymbol,
)

MINIMAL = _drawn.text("flat")


def _fails(text: str, locator: str) -> FormatError:
    with pytest.raises(FormatError) as caught:
        read_drawn(text, file="schematic.toml")
    assert caught.value.file == "schematic.toml" and caught.value.locator == locator, caught.value
    return caught.value


def test_minimal_file() -> None:
    """Scenario "Minimal file"."""
    drawn = read_drawn(MINIMAL, file="schematic.toml")
    assert drawn.root == "root" and [s.key for s in drawn.sheets] == ["root"]
    sheet = drawn.sheets[0]
    assert [s.part for s in sheet.symbols] == ["U1", "R1"]
    assert len(sheet.segments()) == 3 and len(sheet.junctions) == 1
    assert [(label.kind, label.text) for label in sheet.labels] == [("local", "SDA")]
    assert [(p.symbol, p.net) for p in sheet.powers] == [("Mini:Mini_GND", "GND")]


def test_unknown_key_located() -> None:
    """Scenario "Unknown key located"."""
    text = MINIMAL.replace(
        "pts = [[120.65, 57.15], [120.65, 60.96]]", 'pts = [[120.65, 57.15], [120.65, 60.96]]\ncolour = "red"'
    )
    assert 'colour = "red"' in text
    _fails(text, "sheet[0].wire[1].colour")


def test_wrong_schema() -> None:
    """Scenario "Wrong schema"."""
    _fails(MINIMAL.replace("drawn-schematic.v0", "drawn-schematic.v1"), "schema")


def test_missing_key_wrong_type_duplicate_sheet_and_unknown_root() -> None:
    _fails(MINIMAL.replace('paper = "A4"\n', ""), "sheet[0].paper")
    _fails(MINIMAL.replace("unit = 1", 'unit = "one"', 1), "sheet[0].symbol[0].unit")
    _fails(MINIMAL + '\n[[sheet]]\nkey = "root"\npaper = "A4"\n', "sheet[1].key")
    _fails(MINIMAL.replace('root = "root"', 'root = "top"'), "root")
    _fails(MINIMAL.replace('paper = "A4"', 'paper = "B9"'), "sheet[0].paper")
    _fails("schema = [", "")


def test_exact_decimals() -> None:
    """Scenario "Exact decimals"."""
    text = MINIMAL.replace("at = [101.6, 76.2]", "at = [25.4, 50.8]").replace(
        "pts = [[120.65, 57.15], [120.65, 60.96]]", "pts = [[0.0001, 1.27], [120.65, 60.96]]"
    )
    sheet = read_drawn(text).sheets[0]
    assert sheet.symbols[0].at == Point(25_400_000, 50_800_000)
    assert sheet.wires[1][0] == Point(100, 1_270_000)


def test_below_a_nanometre() -> None:
    """Scenario "Below a nanometre"."""
    _fails(MINIMAL.replace("at = [120.65, 57.15]\n", "at = [1.0000001, 2]\n"), "sheet[0].junction[0].at")


def test_angles_and_mirrors() -> None:
    _fails(MINIMAL.replace("rotation = 270", "rotation = 45"), "sheet[0].label[0].rotation")
    _fails(MINIMAL.replace("rotation = 0", 'rotation = 0\nmirror = "z"', 1), "sheet[0].symbol[0].mirror")
    text = MINIMAL.replace("rotation = 0", "rotation = 0\nfields.Value = { at = [1, 2], rotation = 180 }", 1)
    _fails(text, "sheet[0].symbol[0].fields.Value.rotation")


def test_every_kind_read() -> None:
    """Scenario "Every kind read"."""
    drawn = _drawn.drawn("full")
    root, sub = drawn.sheets
    assert (len(root.symbols), len(root.powers), len(root.wires), len(root.buses)) == (2, 1, 5, 1)
    assert (len(root.bus_entries), len(root.junctions), len(root.no_connects), len(root.labels)) == (
        2,
        1,
        1,
        6,
    )
    assert (len(root.bus_aliases), len(root.sheet_refs), len(root.opaques)) == (1, 1, 2)
    assert len(root.sheet_refs[0].pins) == 1 and root.block() is not None
    assert root.title_block == (("title", "Full drawn fixture"), ("revision", "A"))
    assert len(root.wires[0]) == 4 and len(_segments(root.wires[0])) == 3
    assert [f.name for f in root.symbols[0].fields] == ["Reference", "Value"]
    assert {label.kind for label in (*root.labels, *sub.labels)} == {"local", "global", "hierarchical"}


def _segments(points: tuple[Point, ...]) -> list[tuple[Point, Point]]:
    return list(zip(points, points[1:], strict=False))


def test_one_point_wire() -> None:
    """Scenario "One-point wire"."""
    _fails(
        MINIMAL.replace("pts = [[120.65, 57.15], [120.65, 60.96]]", "pts = [[0, 0]]"), "sheet[0].wire[1].pts"
    )


def test_bad_opaque_item() -> None:
    """Scenario "Bad opaque item"."""
    text = MINIMAL + '\n[[sheet.opaque]]\nkicad = "(text \\"a\\""\n'
    _fails(text, "sheet[0].opaque[0].kicad")


@pytest.mark.parametrize("name", [*_drawn.NAMES, "example"])
def test_canonical_bytes(name: str) -> None:
    """Scenario "Stable bytes": every authored file is canonical."""
    text = _drawn.text(name)
    written = write_drawn(read_drawn(text))
    assert written == text
    assert write_drawn(read_drawn(written)) == written


def test_millimetres_are_shortest() -> None:
    assert [mm(v) for v in (0, 127_000_000, 1_270_000, 100, -2_540_000, 25_400_001)] == [
        "0", "127", "1.27", "0.0001", "-2.54", "25.400001",
    ]  # fmt: skip


coordinates = st.integers(min_value=-500_000_000, max_value=500_000_000)
points = st.builds(Point, coordinates, coordinates)
angles = st.sampled_from([0, 90_000_000, 180_000_000, 270_000_000])
texts = st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=0x2FF), min_size=1, max_size=8)


@st.composite
def drawn_values(draw: st.DrawFn) -> DrawnSchematic:
    fields = st.builds(DrawnField, st.sampled_from(["Reference", "Value", "My Field"]), points,
                       st.sampled_from([0, 90_000_000]), st.sampled_from(["", "left", "right bottom"]), st.booleans())  # fmt: skip
    symbol = st.builds(DrawnSymbol, texts, st.integers(1, 4), points, angles, st.sampled_from(["", "x", "y"]),
                       st.lists(fields, max_size=2, unique_by=lambda f: f.name).map(tuple))  # fmt: skip
    label = st.builds(DrawnLabel, st.sampled_from(["local", "global", "hierarchical"]), texts, points, angles,
                      st.sampled_from(["", "input", "passive"]))  # fmt: skip
    polyline = st.lists(points, min_size=2, max_size=4).map(tuple)
    child = DrawnSheet("child", "A3", generated=draw(st.booleans()))
    ref = DrawnSheetRef(
        "child", "child", draw(st.sampled_from(["", "m", "m/n"])), draw(texts), draw(points),
        Size(draw(st.integers(1, 10**8)), draw(st.integers(1, 10**8))), "2", draw(st.sampled_from(["", "a.kicad_sch"])),
        tuple(draw(st.lists(st.builds(DrawnPin, texts, st.just("input"), points, angles), max_size=2))),
    )  # fmt: skip
    root = DrawnSheet(
        "root",
        draw(st.sampled_from(["A4", "Letter"])),
        tuple(sorted(draw(st.lists(st.tuples(st.sampled_from(["title", "date"]), texts), max_size=2,
                                   unique_by=lambda p: p[0])), key=lambda p: p[0] != "title")),
        False,
        tuple(draw(st.lists(symbol, max_size=3))),
        tuple(draw(st.lists(st.builds(DrawnPower, texts, texts, points, angles), max_size=2))),
        tuple(draw(st.lists(polyline, max_size=3))),
        tuple(draw(st.lists(polyline, max_size=2))),
        tuple(draw(st.lists(st.builds(DrawnBusEntry, points, points), max_size=2))),
        tuple(draw(st.lists(st.builds(DrawnJunction, points, st.integers(0, 10**6)), max_size=2))),
        tuple(draw(st.lists(points, max_size=2))),
        tuple(draw(st.lists(label, max_size=3).map(lambda ls: [x for x in ls if x.kind == "local" or x.shape] ))),
        (),
        (ref,),
        tuple(draw(st.lists(st.builds(DrawnOpaque, st.just('(text "x\\"y" (at 1 2 0))'), texts), max_size=1))),
    )  # fmt: skip
    root = DrawnSheet(**{**{f: getattr(root, f) for f in root.__slots__}, "labels": tuple(  # type: ignore[arg-type]
        lab if lab.kind != "local" else DrawnLabel("local", lab.text, lab.at, lab.rotation) for lab in root.labels
    )})  # fmt: skip
    return DrawnSchematic("root", (root, child))


@settings(max_examples=60, deadline=None)
@given(drawn_values())
def test_property_written_values_read_back(value: DrawnSchematic) -> None:
    """Scenario "Property test"."""
    assert read_drawn(write_drawn(value)) == value

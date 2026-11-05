# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Candidate Draftsman write/readback, from the published fact rows; no native acceptance claim."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from fenolite.backends.altium.draftsman import (
    ARRAYS,
    BOARD,
    Dimension,
    DraftsmanItem,
    DraftsmanSheet,
    DraftsmanSpec,
    encode,
    units,
    write_draftsman,
    written_scope,
)
from fenolite.backends.altium.read.draftsman import CHUNK_SIZE, NAMESPACE, decode, read_draftsman


def sample() -> DraftsmanSpec:
    return DraftsmanSpec(
        "own drawing",
        (
            DraftsmanSheet(
                "fab",
                "Fabrication",
                "A4",
                (297_000_000, 210_000_000),
                (
                    DraftsmanItem(
                        "title", "Text", (10_000_000, 10_000_000), (60_000_000, 5_000_000), texts=("=Title",)
                    ),
                    DraftsmanItem(
                        "notes",
                        "Note",
                        (80_000_000, 30_000_000),
                        (100_000_000, 20_000_000),
                        title="Notes",
                        texts=("Authored <one>", "Second & final"),
                    ),
                    DraftsmanItem(
                        "drill",
                        "DrillViewView",
                        (20_000_000, 50_000_000),
                        (50_000_000, 30_000_000),
                        title="Drill drawing",
                    ),
                ),
            ),
        ),
        (("Title", "Fenolite authored & exact"),),
    )


def test_readback() -> None:
    spec = sample()
    first = write_draftsman(spec)
    assert first == write_draftsman(spec)
    root = read_draftsman(first).root
    scope = written_scope(root)
    assert scope.format_version == "22" and scope.parameters == ("Title",)
    (sheet,) = scope.sheets
    assert sheet.paper == "A4" and sheet.size == (units(297_000_000), units(210_000_000))
    text, note, view = sheet.items
    assert text.texts == ("=Title",)
    assert note.texts == ("Authored <one>", "Second & final") and note.title == "Notes"
    assert view.name == "drill-drawing" and view.side == "Top" and view.scale == ("1", "1")
    assert len({sheet.id, *(item.id for item in sheet.items)}) == 4
    assert (
        root.find(f"{{{NAMESPACE}}}Parameters")[0].findtext(f"{{{NAMESPACE}}}Value") == spec.parameters[0][1]
    )
    # Geometry is independently read from the XML, beyond the deliberately narrow summary.
    rect = root.find(f".//{{{NAMESPACE}}}Rect")
    assert rect is not None and rect.findtext(f"{{{NAMESPACE}}}X") == units(10_000_000)


@pytest.mark.parametrize("nm", [0, 1, -1, 25_400_000, 1_234_567_891])
def test_units_preserve_nanometres(nm: int) -> None:
    restored = Decimal(units(nm)) * 25_400_000 / 96
    assert abs(restored - nm) < Decimal("0.001")


def test_stored_container_multiple_chunks() -> None:
    text = b"x" * (CHUNK_SIZE + 127)
    found, restored = decode(encode(text))
    assert restored == text and [chunk.size for chunk in found] == [CHUNK_SIZE, 127]
    assert [chunk.flag for chunk in found] == [0, 0]


def test_duplicate_paths_and_invalid_text_are_refused() -> None:
    spec = sample()
    with pytest.raises(ValueError, match="unique"):
        write_draftsman(DraftsmanSpec(spec.name, (spec.sheets[0], spec.sheets[0])))
    with pytest.raises(ValueError, match="exactly one"):
        write_draftsman(
            DraftsmanSpec(
                "bad", (DraftsmanSheet("p", "", "A4", (1, 1), (DraftsmanItem("t", "Text", (0, 0), (1, 1)),)),)
            )
        )
    with pytest.raises(ValueError, match="integer"):
        units(True)


def test_no_board_snapshot_and_relative_candidate_binding() -> None:
    root = read_draftsman(write_draftsman(sample())).root
    assert {child.tag.rsplit("}", 1)[-1] for child in root} == {
        "Id",
        "FontStyles",
        "FormatVersion",
        "Pages",
        "Parameters",
        "SourceDocumentName",
    }
    assert root.findtext(f"{{{NAMESPACE}}}SourceDocumentName") == "own drawing.PcbDoc"
    ET.fromstring(ET.tostring(root))


def test_second_authored_scope_and_xml_character_guard() -> None:
    first = sample()
    item = DraftsmanItem(
        "view",
        "BoardAssemblyViewData",
        (20_000_000, 20_000_000),
        (50_000_000, 30_000_000),
        title="Authored bottom",
        side="Bottom",
    )
    second = replace(
        first,
        name="other",
        sheets=(*first.sheets, DraftsmanSheet("bottom", "Bottom", "A3", (420_000_000, 297_000_000), (item,))),
    )
    scope = written_scope(read_draftsman(write_draftsman(second)).root)
    assert len(scope.sheets) == 2 and scope.sheets[1].items[0].side == "Bottom"
    bad = replace(first, parameters=(("Title", "invalid\0text"),))
    with pytest.raises(ValueError, match="XML 1.0"):
        write_draftsman(bad)


def test_namespace_registry_and_text_line_endings_do_not_change_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fenolite.backends.altium.read.draftsman import INSTANCE

    spec = sample()
    item = replace(spec.sheets[0].items[0], texts=("Authored α\r\nβ\t",))
    spec = replace(spec, sheets=(replace(spec.sheets[0], items=(item,)),))
    first = write_draftsman(spec)
    monkeypatch.setattr(ET, "_namespace_map", {})
    ET.register_namespace("changed", NAMESPACE)
    ET.register_namespace("different", INSTANCE)
    assert write_draftsman(spec) == first
    assert written_scope(read_draftsman(first).root).sheets[0].items[0].texts == item.texts


# c0388 task 4.1: the tables, the legend, the note and the dimension follow the round F0 rows (S-1421).
F0_ROWS = Path(__file__).parents[4] / "docs/formats/altium/draftsman.md"
NATIVE = ("DrillTableBoardView", "LayerStackLegendView", "BillOfMaterialsView", "Note", "LinearDimension")


def f0_members(kind: str) -> list[str]:
    for line in F0_ROWS.read_text(encoding="utf-8").splitlines():
        found = re.match(
            rf"\| A {kind} saved in round F0 \(F0\.\d+\) holds (\d+) members, in this order: ([^|]+)\|", line
        )
        if found:
            names = re.findall(r"`(\w+)`", found.group(2))
            assert len(names) == int(found.group(1))
            return names
    raise AssertionError(f"no F0 member row for {kind}")


def native_spec() -> DraftsmanSpec:
    mm = 1_000_000
    items = (
        DraftsmanItem(
            "view", "DrillViewView", (20 * mm, 120 * mm), (50 * mm, 30 * mm), title="Drill drawing"
        ),
        DraftsmanItem("drill", "DrillTableBoardView", (20 * mm, 60 * mm), (80 * mm, 20 * mm)),
        DraftsmanItem("stack", "LayerStackLegendView", (110 * mm, 60 * mm), (90 * mm, 40 * mm)),
        DraftsmanItem("bom", "BillOfMaterialsView", (110 * mm, 120 * mm), (120 * mm, 10 * mm), side="Top"),
        DraftsmanItem(
            "notes", "Note", (210 * mm, 60 * mm), (60 * mm, 20 * mm), title="Notes", texts=("One", "Two")
        ),
        DraftsmanItem(
            "width",
            "LinearDimension",
            (20 * mm, 152 * mm),
            (50 * mm, 6 * mm),
            dimension=Dimension("view", (0, 0), (50 * mm, 0), (20 * mm, 120 * mm), (0, 10 * mm)),
        ),
        DraftsmanItem(
            "height",
            "LinearDimension",
            (8 * mm, 120 * mm),
            (6 * mm, 30 * mm),
            dimension=Dimension("view", (0, 0), (0, 30 * mm), (20 * mm, 120 * mm), (-10 * mm, 0)),
        ),
    )
    return DraftsmanSpec(
        "own drawing", (DraftsmanSheet("fab", "Fabrication", "A4", (297 * mm, 210 * mm), items),)
    )


def native_items(root: ET.Element) -> dict[str, list[ET.Element]]:
    from fenolite.backends.altium.read.draftsman import INSTANCE

    found: dict[str, list[ET.Element]] = {}
    for item in root.iter(f"{{{NAMESPACE}}}Item"):
        found.setdefault(item.get(f"{{{INSTANCE}}}type", ""), []).append(item)
    return found


@pytest.mark.parametrize("kind", NATIVE)
def test_native_items_hold_the_f0_members_in_order(kind: str) -> None:
    items = native_items(read_draftsman(write_draftsman(native_spec())).root)[kind]
    for item in items:
        assert [child.tag.rsplit("}", 1)[-1] for child in item] == f0_members(kind)


def test_board_source_and_dictionaries_take_the_f0_namespaces() -> None:
    data = write_draftsman(native_spec())
    text = decode(data)[1].decode("utf-8")
    root = read_draftsman(data).root
    for kind in ("DrillTableBoardView", "LayerStackLegendView", "BillOfMaterialsView"):
        (item,) = native_items(root)[kind]
        assert item.find(f"{{{BOARD}}}BoardSourceName") is not None
        assert item.findtext(f"{{{BOARD}}}BoardSourceName") == ""
    assert text.count(f'<BoardSourceName xmlns="{BOARD}">') == 3
    assert (
        f'<ColumnAligns xmlns:a="{ARRAYS}"><a:KeyValueOfDrillTableColumnDataHorizontalAlignment_SGWc8z3x>'
        in text
    )
    assert f'<PointsZ xmlns:a="{ARRAYS}"><a:double>0</a:double></PointsZ>' in text
    assert "\\" not in text and ":/" not in text.replace("http://", "")


def test_drill_table_columns_and_bom_side() -> None:
    root = read_draftsman(write_draftsman(native_spec())).root
    ns = f"{{{NAMESPACE}}}"
    (drill,) = native_items(root)["DrillTableBoardView"]
    columns = drill.find(ns + "Columns")
    assert columns is not None and len(columns) == 16
    shown = [
        v.findtext(ns + "Name")
        for v in columns.iter(f"{{{ARRAYS}}}Value")
        if v.findtext(ns + "Visible") == "true"
    ]
    assert shown == ["Symbol", "Count", "Hole Size", "Plated", "Hole Tolerance"]
    visible = drill.find(ns + "VisibilityColumns")
    assert visible is not None
    assert [e.text for e in visible] == ["DrillSymbol", "CountHoles", "HoleSize", "Plated", "HoleTolerance"]
    assert drill.findtext(ns + "Title") == "Drill Table" and drill.find(ns + "TopLayer") is not None
    (bom,) = native_items(root)["BillOfMaterialsView"]
    assert bom.findtext(ns + "ViewSide") == "Top"
    assert [c.findtext(ns + "Name") for c in bom.iter(ns + "BomColumnInfo")] == [
        "Line #",
        "Designator",
        "Comment",
        "Quantity",
    ]
    scope = written_scope(root)
    roles = {i.kind: i.role for i in scope.sheets[0].items}
    assert roles["DrillTableBoardView"] == roles["BillOfMaterialsView"] == "table"
    assert roles["Note"] == "note" and roles["LinearDimension"] == "other"


def test_linear_dimension_snaps_to_its_view() -> None:
    root = read_draftsman(write_draftsman(native_spec())).root
    ns = f"{{{NAMESPACE}}}"
    (view,) = native_items(root)["DrillViewView"]
    width, height = native_items(root)["LinearDimension"]
    for found in (width, height):
        for anchor in ("StartAnchor", "EndAnchor"):
            assert found.findtext(f"{ns}{anchor}/{ns}SnapTargetItemId") == view.findtext(ns + "Id")
    assert width.findtext(f"{ns}EndAnchor/{ns}SnapId") == f"GI|Board Outline|Point: {units(50_000_000)}, 0"
    assert width.findtext(f"{ns}EndAnchor/{ns}PointOnPage/{ns}X") == units(70_000_000)
    assert [width.findtext(f"{ns}ExtensionsDirection/{ns}{a}") for a in "XY"] == ["0", "1"]
    assert [height.findtext(f"{ns}ExtensionsDirection/{ns}{a}") for a in "XY"] == ["1", "0"]


def test_linear_dimension_needs_a_view_and_a_straight_run() -> None:
    spec = native_spec()
    sheet = spec.sheets[0]
    dimension = sheet.items[-1]
    assert dimension.dimension is not None
    for bad, message in (
        (replace(dimension, dimension=replace(dimension.dimension, target="drill")), "snap to a view"),
        (replace(dimension, dimension=replace(dimension.dimension, end=(5, 5))), "horizontal or vertical"),
        (replace(dimension, dimension=None), "needs its dimension"),
    ):
        with pytest.raises(ValueError, match=message):
            write_draftsman(replace(spec, sheets=(replace(sheet, items=(*sheet.items[:-1], bad)),)))

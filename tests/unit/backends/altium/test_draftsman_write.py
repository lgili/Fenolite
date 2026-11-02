# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Candidate Draftsman write/readback, from the published fact rows; no native acceptance claim."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import replace
from decimal import Decimal

import pytest

from fenolite.backends.altium.draftsman import (
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

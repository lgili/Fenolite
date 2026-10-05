# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Parts and display modes (capability altium-schematic-reader, "Parts and display modes")."""

from __future__ import annotations

from _altium_sch_build import SHEET, component_text, pin_payload, schdoc, schlib

from fenolite.backends.altium.read import sch
from fenolite.backends.altium.read.schlib import read_schlib
from fenolite.core.errors import Issue

DESIGNATOR = "|RECORD=34|OWNERPARTID=-1|NAME=Designator|TEXT=U?"


def _designators(records: tuple[sch.SchRecord, ...]) -> list[str]:
    out: list[str] = []
    for record in records:
        if isinstance(record, sch.Pin):
            out.append(record.designator)
        elif isinstance(record, sch.Designator):
            out.append("D")
        elif isinstance(record, sch.Rectangle):
            out.append(f"R{record.owner_display_mode}")
    return out


def test_two_parts_and_a_common_pin() -> None:
    pins = [
        (1, pin_payload(designator=str(n).encode(), part=part))
        for n, part in ((1, 1), (2, 1), (3, 2), (4, 2), (5, 0))
    ]
    library = read_schlib(schlib([("Q", [component_text("Q", part_count=3), *pins, DESIGNATOR])]))
    component = library.components[0]
    assert component.part_count == 2
    assert component.parts == range(1, 3)
    assert _designators(component.children(part=1)) == ["1", "2", "5", "D"]
    assert _designators(component.children(part=2)) == ["3", "4", "5", "D"]
    assert len(component.children()) == 6


def test_alternate_display_mode() -> None:
    records = [
        component_text("Q", display_modes=2),
        "|RECORD=14|OWNERPARTID=1",
        "|RECORD=14|OWNERPARTID=1|OWNERPARTDISPLAYMODE=1",
        DESIGNATOR,
    ]
    issues: list[Issue] = []
    library = read_schlib(schlib([("Q", records)]), issues=issues)
    component = library.components[0]
    assert component.modes == range(2)
    assert _designators(component.children(part=1, mode=0)) == ["R0", "D"]
    assert _designators(component.children(part=1, mode=1)) == ["R1", "D"]
    assert issues == []


def test_placed_part_of_a_multi_part_component() -> None:
    records = [
        SHEET,
        "|RECORD=1|PARTCOUNT=3|CURRENTPARTID=2",
        "|RECORD=2|OWNERINDEX=1|OWNERPARTID=1|DESIGNATOR=1",
        "|RECORD=2|OWNERINDEX=1|OWNERPARTID=2|DESIGNATOR=3",
        "|RECORD=2|OWNERINDEX=1|OWNERPARTID=0|DESIGNATOR=5",
        "|RECORD=34|OWNERINDEX=1|OWNERPARTID=-1|TEXT=U1B",
    ]
    document = sch.read_schematic(schdoc(records))
    component = document.records[1]
    assert isinstance(component, sch.Component)
    assert _designators(document.shown_children(component)) == ["3", "5", "D"]
    assert document.shown_children(component) == document.children_of(component, part=2, mode=0)


def test_part_out_of_range() -> None:
    records = [
        component_text("Q", part_count=2),
        (1, pin_payload(part=3)),
        "|RECORD=14|OWNERPARTDISPLAYMODE=4",
    ]
    issues: list[Issue] = []
    library = read_schlib(schlib([("Q", records)]), issues=issues)
    component = library.components[0]
    assert len(component.children()) == 2
    assert [(issue.code, issue.severity) for issue in issues] == [("altium.sch.part-out-of-range", "warning")]
    assert "part" in issues[0].message and "display mode" in issues[0].message
    assert issues[0].where == "Q/Data/record 0"


def test_part_out_of_range_in_a_document() -> None:
    issues: list[Issue] = []
    records = [SHEET, "|RECORD=1|PARTCOUNT=2", "|RECORD=2|OWNERINDEX=1|OWNERPARTID=3"]
    sch.read_schematic(schdoc(records), issues=issues)
    assert [(issue.code, issue.where) for issue in issues] == [
        ("altium.sch.part-out-of-range", "FileHeader/record 2")
    ]


def test_placed_parts_with_one_designator_stay_separate() -> None:
    records = [
        SHEET,
        "|RECORD=1|PARTCOUNT=3|CURRENTPARTID=1",
        "|RECORD=34|OWNERINDEX=1|TEXT=U1",
        "|RECORD=1|PARTCOUNT=3|CURRENTPARTID=2",
        "|RECORD=34|OWNERINDEX=3|TEXT=U1",
    ]
    document = sch.read_schematic(schdoc(records))
    assert [component.current_part for component in document.components()] == [1, 2]

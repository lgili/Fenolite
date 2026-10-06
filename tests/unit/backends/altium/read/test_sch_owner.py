# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The owner tree of a schematic document (capability altium-schematic-reader, "Owner tree of a schematic
document", "Reader interfaces for later changes")."""

from __future__ import annotations

from pathlib import Path

from _altium_sch_build import SHEET, schdoc

from fenolite.backends.altium.read import sch
from fenolite.core.errors import Issue

ROOT = Path(__file__).resolve().parents[5]
BLINK = ROOT / "tests" / "data" / "altium" / "blink" / "blink.SchDoc"


def _filler(count: int) -> list[str]:
    return [f"|RECORD=29|LOCATION.X={n}" for n in range(count)]


def test_footprint_chain() -> None:
    records = [
        SHEET,
        *_filler(4),
        "|RECORD=1|LIBREFERENCE=R",
        "|RECORD=2|OWNERINDEX=5|OWNERPARTID=1",
        "|RECORD=34|OWNERINDEX=5|TEXT=R1",
        "|RECORD=41|OWNERINDEX=5|NAME=Comment",
        "|RECORD=44|OWNERINDEX=5",
        "|RECORD=45|OWNERINDEX=9|MODELNAME=R0603",
        "|RECORD=46|OWNERINDEX=10",
        "|RECORD=48|OWNERINDEX=10",
    ]
    document = sch.read_schematic(schdoc(records))
    walked = [record.ref.index for record in document.walk(document.records[5])]
    assert walked == [5, 6, 7, 8, 9, 10, 11, 12]
    owner = document.owner_of(document.records[11])
    assert isinstance(owner, sch.Implementation)
    assert document.records[10].children == (sch.RecordRef("main", 11), sch.RecordRef("main", 12))
    assert document.children_of(document.records[5]) == tuple(document.records[6:10])


def test_owner_that_comes_later() -> None:
    records = [SHEET, *_filler(2), "|RECORD=25|OWNERINDEX=8", *_filler(6)]
    issues: list[Issue] = []
    document = sch.read_schematic(schdoc(records), issues=issues)
    assert len(document.records) == 10
    assert document.records[3].owner is None
    assert sch.RecordRef("main", 3) in document.roots
    assert [(issue.code, issue.severity) for issue in issues] == [("altium.sch.orphan-record", "warning")]
    assert "record 3" in issues[0].message and "owner 8" in issues[0].message
    assert issues[0].where == "FileHeader/record 4"


def test_negative_and_past_the_end_owners() -> None:
    issues: list[Issue] = []
    document = sch.read_schematic(
        schdoc([SHEET, "|RECORD=25|OWNERINDEX=-1", "|RECORD=25|OWNERINDEX=99"]), issues=issues
    )
    assert [record.owner for record in document.records] == [None, None, None]
    assert [issue.code for issue in issues] == ["altium.sch.orphan-record"] * 2


def test_sheet_level_records() -> None:
    document = sch.read_schematic(BLINK.read_bytes())
    for record in document.records:
        if isinstance(record, (sch.Wire, sch.NetLabel, sch.PowerPort, sch.Component, sch.Sheet)):
            assert record.owner is None, record.ref
        if isinstance(record, sch.Pin):
            assert isinstance(document.owner_of(record), sch.Component)
    assert document.sheet is document.records[0]
    assert document.roots[0] == sch.RecordRef("main", 0)


def test_every_record_is_reached_once() -> None:
    document = sch.read_schematic(BLINK.read_bytes())
    seen = [record.ref for root in document.roots for record in document.walk(document.get(root))]
    assert sorted(seen, key=lambda ref: ref.index) == [record.ref for record in document.records]


def test_no_sheet() -> None:
    issues: list[Issue] = []
    document = sch.read_schematic(schdoc(["|RECORD=25|TEXT=A"]), issues=issues)
    assert document.sheet is None
    assert [issue.code for issue in issues] == ["altium.sch.no-sheet"]
    issues.clear()
    empty = sch.read_schematic(schdoc([]), issues=issues)
    assert empty.sheet is None and [issue.code for issue in issues] == ["altium.sch.no-sheet"]


def test_accessors() -> None:
    document = sch.read_schematic(BLINK.read_bytes())
    assert document.components() == document.of_type(sch.Component)
    assert all(isinstance(wire, sch.Wire) for wire in document.wires())
    assert len(document.components()) == 3
    assert document.get(sch.RecordRef("main", 0)) is document.records[0]
    for method in (
        document.buses,
        document.ports,
        document.junctions,
        document.no_ercs,
        document.sheet_symbols,
    ):
        assert isinstance(method(), tuple)
    assert document.harnesses() == () and document.templates() == () and document.template_children() == ()


def test_template_records_for_the_sheet_template_import() -> None:
    records = [
        SHEET,
        "|RECORD=39|ISNOTACCESIBLE=T|FILENAME=A4.SchDot",
        "|RECORD=13|OWNERINDEX=1|LOCATION.X=0|CORNER.X=100",
        "|RECORD=13|OWNERINDEX=1|LOCATION.Y=0|CORNER.Y=100",
        "|RECORD=4|OWNERINDEX=1|TEXT=Title",
        "|RECORD=25|TEXT=NET",
    ]
    document = sch.read_schematic(schdoc(records))
    (template,) = document.templates()
    assert template.file_name == "A4.SchDot"
    children = document.template_children()
    assert [type(record).__name__ for record in children] == ["Line", "Line", "Label"]
    assert [record.ref.index for record in children] == [2, 3, 4]

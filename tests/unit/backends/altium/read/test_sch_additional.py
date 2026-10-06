# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``Additional`` stream and harness records (capability altium-schematic-reader, "Additional stream and
harness records")."""

from __future__ import annotations

from pathlib import Path

from _altium_sch_build import SHEET, schdoc

from fenolite.backends.altium.read import sch
from fenolite.core.errors import Issue

ROOT = Path(__file__).resolve().parents[5]
BLINK = ROOT / "tests" / "data" / "altium" / "blink" / "blink.SchDoc"
FIRST = [
    "|RECORD=215|LOCATION.X=10|LOCATION.Y=50|XSIZE=50|YSIZE=40|PRIMARYCONNECTIONPOSITION=2",
    "|RECORD=216|OWNERINDEXADDITIONALLIST=T|SIDE=1|DISTANCEFROMTOP=1|NAME=SCK",
    "|RECORD=216|OWNERINDEXADDITIONALLIST=T|SIDE=1|DISTANCEFROMTOP=2|NAME=MOSI",
    "|RECORD=217|OWNERINDEXADDITIONALLIST=T|TEXT=SpiBus",
    "|RECORD=218|LOCATIONCOUNT=2|X1=0|Y1=48|X2=10|Y2=48",
]


def test_children_of_the_first_connector() -> None:
    issues: list[Issue] = []
    document = sch.read_schematic(schdoc([SHEET], additional=FIRST), issues=issues)
    (harness,) = document.harnesses()
    assert harness.connector is document.additional[0]
    assert [entry.name for entry in harness.entries] == ["SCK", "MOSI"]
    assert harness.type is not None and harness.type.text == "SpiBus"
    assert document.additional[4].owner is None
    assert issues == []
    assert document.roots == (
        sch.RecordRef("main", 0),
        sch.RecordRef("additional", 0),
        sch.RecordRef("additional", 4),
    )


def test_second_connector() -> None:
    records = [*FIRST, "|RECORD=215|XSIZE=50", "|RECORD=216|OWNERINDEXADDITIONALLIST=T|OwnerIndex=5|NAME=X"]
    document = sch.read_schematic(schdoc([SHEET], additional=records))
    assert document.additional[6].owner == sch.RecordRef("additional", 5)
    assert len(document.harnesses()) == 2
    assert [entry.name for entry in document.harnesses()[1].entries] == ["X"]


def test_additional_record_naming_a_main_record() -> None:
    document = sch.read_schematic(
        schdoc([SHEET, "|RECORD=15|XSIZE=5"], additional=["|RECORD=41|OWNERINDEX=1"])
    )
    assert document.additional[0].owner == sch.RecordRef("main", 1)
    assert document.records[1].children == (sch.RecordRef("additional", 0),)


def test_orphan_in_the_additional_space() -> None:
    issues: list[Issue] = []
    document = sch.read_schematic(
        schdoc([SHEET], additional=["|RECORD=216|OWNERINDEXADDITIONALLIST=T", "|RECORD=216|OWNERINDEX=7"]),
        issues=issues,
    )
    assert [record.owner for record in document.additional] == [None, None]
    assert [(issue.code, issue.where) for issue in issues] == [
        ("altium.sch.orphan-record", "Additional/record 1"),
        ("altium.sch.orphan-record", "Additional/record 2"),
    ]


def test_harness_records_in_file_header_and_others_in_additional() -> None:
    issues: list[Issue] = []
    document = sch.read_schematic(
        schdoc([SHEET, *FIRST], additional=["|RECORD=25|TEXT=N", "|RECORD=27|LOCATIONCOUNT=0"]), issues=issues
    )
    assert issues == []
    assert isinstance(document.records[1], sch.HarnessConnector)
    assert isinstance(document.additional[0], sch.NetLabel)
    assert len(document.harnesses()) == 1


def test_connector_attributes() -> None:
    document = sch.read_schematic(schdoc([SHEET], additional=FIRST))
    connector = document.harnesses()[0].connector
    assert connector.side == 0
    assert connector.primary_position == sch.SchLength.of(2)
    assert connector.location == (sch.SchLength.of(10), sch.SchLength.of(50))


def test_port_and_sheet_entry_harness_type() -> None:
    document = sch.read_schematic(schdoc([SHEET, "|RECORD=18|NAME=A", "|RECORD=16|NAME=B|HARNESSTYPE=T1"]))
    port, entry = document.records[1], document.records[2]
    assert isinstance(port, sch.Port) and port.harness_type == ""
    assert isinstance(entry, sch.SheetEntry) and entry.harness_type == "T1"


def test_no_additional_stream() -> None:
    document = sch.read_schematic(BLINK.read_bytes())
    assert document.additional == ()
    assert document.additional_header is None
    assert document.harnesses() == ()

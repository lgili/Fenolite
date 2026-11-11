# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Carried settings of a source project (change c0479; capability altium-schematic-writer)."""

from __future__ import annotations

import shutil
from pathlib import Path

from _drawings import BLINK

from fenolite.backends.altium import drawn, drawn_read
from fenolite.backends.altium.prjpcb import carried_settings, retarget_variants, write_prjpcb
from fenolite.backends.altium.read.project import read_project

SETTINGS = (
    "[Design]\r\nVersion=1.0\r\nHierarchyMode=0\r\nAllowSheetEntryNetNames=0\r\n\r\n"
    "[Document1]\r\nDocumentPath=SCH\\a.SchDoc\r\n\r\n[GeneratedDocument1]\r\nDocumentPath=x.txt\r\n\r\n"
    "[Electrical Rules Check]\r\nType1=1\r\n\r\n[Parameter1]\r\nName=Rev\r\nValue=A\r\n"
)


def test_carried_settings_leave_out_documents_and_version() -> None:
    assert carried_settings(SETTINGS.encode()) == (
        "[Design]\nHierarchyMode=0\nAllowSheetEntryNetNames=0\n[Electrical Rules Check]\nType1=1\n"
        "[Parameter1]\nName=Rev\nValue=A\n"
    )
    assert carried_settings(b"[Design]\r\nVersion=1.0\r\n\r\n[Document1]\r\nDocumentPath=a.SchDoc\r\n") == ""


def test_merge() -> None:
    """The spec's scenario "Merge": a carried family replaces the written one; [Design] keys merge."""
    carried = "[Design]\nHierarchyMode=0\n[Parameter1]\nName=Rev\nValue=A\n"
    text = write_prjpcb(schematic="a.SchDoc", parameters=(("Title", "x"), ("B", "y")), carried=carried)
    assert text == (
        b"[Design]\r\nVersion=1.0\r\nHierarchyMode=0\r\n\r\n[Document1]\r\nDocumentPath=a.SchDoc\r\n"
        b"\r\n[Parameter1]\r\nName=Rev\r\nValue=A\r\n"
    )


def test_carried_design_key_replaces_the_written_one_in_place() -> None:
    text = write_prjpcb(
        schematic="a.SchDoc", harnesses=("a.Harness",), carried="[Design]\nAllowPortNetNames=1\n"
    )
    design = read_project(text).ini.section("Design")
    assert design is not None
    assert [(e.key, e.value) for e in design.entries] == [
        ("Version", "1.0"),
        ("AllowPortNetNames", "1"),
        ("AllowSheetEntryNetNames", "0"),
    ]


def test_no_carried_settings_keep_the_bytes() -> None:
    assert write_prjpcb(schematic="a.SchDoc", pcb="a.PcbDoc", carried="") == write_prjpcb(
        schematic="a.SchDoc", pcb="a.PcbDoc"
    )


def test_settings_style_no_sheet() -> None:
    key, field = drawn_read.TOPS_KEY, drawn_read.PROJECT_FIELD
    assert drawn._styling_fields({key: {field: "x"}, "label:0": {"COLOR": "1"}}) == {
        "label:0": {"COLOR": "1"}
    }
    tops = {key: {field: "x", drawn_read.TOPS_FIELD: "T"}}
    assert drawn._styling_fields(tops) == {key: {drawn_read.TOPS_FIELD: "T"}}


def test_conversion_carries_the_settings_in_the_root_sheet(tmp_path: Path) -> None:
    """The KiCad leg of the spec's scenario "Net options survive a round trip": the root sheet's carrier
    holds the source project's settings, which ``convert --to altium`` and ``build`` take back."""
    from fenolite.backends.kicad import sheet_carrier
    from fenolite.convert import convert_project

    source = tmp_path / "source"
    shutil.copytree(BLINK.parent, source)
    project = source / BLINK.name
    data = project.read_bytes().replace(
        b"Version=1.0\r\n", b"Version=1.0\r\nAllowSheetEntryNetNames=0\r\n", 1
    )
    project.write_bytes(data + b"\r\n[Electrical Rules Check]\r\nType1=1\r\n")
    files = convert_project(project, to="kicad", allow_lossy=True).files
    root = files[f"{BLINK.stem}.kicad_sch"]
    carried = sheet_carrier.take(root if isinstance(root, str) else root.decode("utf-8"))
    assert carried is not None
    fields = sheet_carrier.AltiumSheet.parse(carried).fields
    assert fields[drawn_read.TOPS_KEY][drawn_read.PROJECT_FIELD] == carried_settings(project.read_bytes())
    assert "AllowSheetEntryNetNames=0\n" in fields[drawn_read.TOPS_KEY][drawn_read.PROJECT_FIELD]


def test_variants_name_the_written_components() -> None:
    carried = (
        "[Design]\nVariation1=Designator=R1|UniqueId=\\A\n[ProjectVariant1]\nUniqueId=V\n"
        "Variation1=Designator=R1|UniqueId=\\S\\OLD|Kind=1|AlternatePart=\nVariation2=Designator=R9|UniqueId=\\K\n"
    )
    assert retarget_variants(carried, {"R1": "\\NEWS\\NEWC"}) == (
        "[Design]\nVariation1=Designator=R1|UniqueId=\\A\n[ProjectVariant1]\nUniqueId=V\n"
        "Variation1=Designator=R1|UniqueId=\\NEWS\\NEWC|Kind=1|AlternatePart=\nVariation2=Designator=R9|UniqueId=\\K\n"
    )


def test_a_net_label_of_an_altium_source_stays_a_net_label() -> None:
    """A local label that shares its text with a port or a power port of its sheet is written as one
    (``H-A-IMP-DUP-NAME``), unless it was a net label of an Altium source, which joined them in Altium."""
    from fenolite.core.coords import Point
    from fenolite.model.drawn import DrawnLabel

    label = DrawnLabel("local", "+5V", Point(0, 0))
    assert drawn.written_kind(label, {"+5V"}, set()) == "hierarchical"
    assert drawn.written_kind(label, set(), {"+5V"}) == "global"
    assert drawn.written_kind(label, {"+5V"}, {"+5V"}) == "hierarchical"
    assert drawn.written_kind(label, set(), set()) == "local"
    assert drawn.written_kind(label, {"+5V"}, {"+5V"}, native=True) == "local"
    hierarchical = DrawnLabel("hierarchical", "+5V", Point(0, 0))
    assert drawn.written_kind(hierarchical, set(), set(), native=True) == "hierarchical"

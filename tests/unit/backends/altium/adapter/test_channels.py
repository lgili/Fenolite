# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Channels of a sheet that several sheet symbols name: their designators (capability altium-import,
"Channel designators"; change c0083). The sheets are authored record by record."""

from __future__ import annotations

import _altium_records as rec
import pytest

from fenolite.backends.altium.adapter import (
    BoardInput,
    NetOptions,
    ProjectInput,
    import_circuit,
    import_project,
)
from fenolite.backends.altium.adapter.channels import (
    FLAT_STYLES,
    KEYWORDS,
    PATH_STYLES,
    channel_designator,
    fallback,
    room_name,
)
from fenolite.backends.altium.read.project import read_project
from fenolite.core.errors import Issue

FORMAT = "$Component_$RoomName"


def sheets() -> tuple[object, object]:
    top = rec.Sheet("top.SchDoc")
    top.symbol("CH1", "ch.SchDoc", (100, 200), uid="SYMBOL01")
    top.symbol("CH2", "ch.SchDoc", (300, 200), uid="SYMBOL02")
    channel = rec.Sheet("ch.SchDoc")
    channel.component("R1", [("1", 10, 10)], uid="RUID0001")
    channel.component("C12", [("1", 50, 10)], uid="CUID0001")
    return top.input(), channel.input()


def codes(issues: list[Issue]) -> list[str]:
    return sorted({i.code.removeprefix("altium.import.") for i in issues})


@pytest.mark.parametrize(
    ("form", "expected"),
    [
        ("$Component_$RoomName", "R12_CH2"),
        ("$RoomName_$Component", "CH2_R12"),
        ("$Component_$ChannelPrefix", "R12_CH2"),
        ("$ComponentPrefix_$RoomName_$ComponentIndex", "R_CH2_12"),
        ("$Component", "R12"),
    ],
)
def test_formats_of_a_plain_channel(form: str, expected: str) -> None:
    assert channel_designator(form, "R12", ["CH2"]) == expected


def test_room_names_by_style() -> None:
    names = ["BANK", "CH2"]
    assert {room_name(names, style, "_") for style in FLAT_STYLES} == {"CH2"}
    assert {room_name(names, style, "-") for style in PATH_STYLES} == {"BANK-CH2"}
    assert room_name(names, 7, "_") is None and room_name(names, None, "_") is None
    assert room_name([], 0, "_") is None
    assert channel_designator(FORMAT, "R1", names, style=2, separator="_") == "R1_BANK_CH2"
    assert channel_designator(FORMAT, "R1", names, style=0) == "R1_CH2"


@pytest.mark.parametrize(
    "form", ["$Component_$ChannelIndex", "$Component$ChannelAlpha", "$Component_$Other", "", "$Component_$"]
)
def test_formats_that_are_not_guessed(form: str) -> None:
    """The index of a Repeat statement, a keyword that does not exist, no format at all."""
    assert channel_designator(form, "R1", ["CH1"]) is None


def test_unknown_style_only_matters_for_the_room() -> None:
    assert channel_designator(FORMAT, "R1", ["CH1"], style=9) is None
    assert channel_designator("$Component_$ChannelPrefix", "R1", ["CH1"], style=9) == "R1_CH1"
    assert fallback("R1", ["BANK", "CH1"]) == "R1@BANK/CH1"
    assert KEYWORDS.index("$ComponentPrefix") < KEYWORDS.index("$Component")


def test_schematic_alone_names_channels_by_the_format() -> None:
    issues: list[Issue] = []
    options = NetOptions(channel_format=FORMAT, room_style=0)
    circuit = import_circuit(sheets(), options=options, issues=issues)  # type: ignore[arg-type]
    assert sorted((c.ref, c.path) for c in circuit.components) == [
        ("C12_CH1", "CH1/C12_CH1"),
        ("C12_CH2", "CH2/C12_CH2"),
        ("R1_CH1", "CH1/R1_CH1"),
        ("R1_CH2", "CH2/R1_CH2"),
    ]
    assert "channels" in codes(issues) and "channel-naming" not in codes(issues)
    assert "repeated-sheet" not in codes(issues)


def test_without_a_format_the_sheet_designators_stay() -> None:
    """Sheets read without their project file: nothing says how the channels are named."""
    issues: list[Issue] = []
    circuit = import_circuit(sheets(), issues=issues)  # type: ignore[arg-type]
    assert sorted(c.ref for c in circuit.components) == ["C12", "C12", "R1", "R1"]
    assert "channel-naming" not in codes(issues)


def test_unresolved_format_is_said() -> None:
    issues: list[Issue] = []
    options = NetOptions(channel_format="$Component_$ChannelIndex", room_style=0)
    circuit = import_circuit(sheets(), options=options, issues=issues)  # type: ignore[arg-type]
    assert sorted(c.ref for c in circuit.components) == ["C12@CH1", "C12@CH2", "R1@CH1", "R1@CH2"]
    (said,) = [i for i in issues if i.code == "altium.import.channel-naming"]
    assert said.severity == "warning" and "4 component(s)" in said.message


def test_single_instances_keep_their_designators() -> None:
    top = rec.Sheet("top.SchDoc")
    top.symbol("CH1", "ch.SchDoc", (100, 200), uid="SYMBOL01")
    channel = rec.Sheet("ch.SchDoc")
    channel.component("R1", [("1", 10, 10)], uid="RUID0001")
    options = NetOptions(channel_format=FORMAT, room_style=0)
    circuit = import_circuit((top.input(), channel.input()), options=options)
    assert [c.ref for c in circuit.components] == ["R1"]


def test_the_board_wins_over_the_format() -> None:
    """The board holds the designators the project was annotated to; ``SOURCEDESIGNATOR`` is the sheet's."""
    parts = [
        rec.component("R1A", unique_id="A", source_unique_id="\\SYMBOL01\\RUID0001"),
        rec.component("R1B", unique_id="B", source_unique_id="\\SYMBOL02\\RUID0001"),
    ]
    issues: list[Issue] = []
    project = ProjectInput(
        "p",
        options=NetOptions(channel_format=FORMAT, room_style=0),
        sheets=sheets(),  # type: ignore[arg-type]
        board=BoardInput("b.PcbDoc", rec.SHA, rec.document(components=parts)),
    )
    design = import_project(project, issues=issues)
    refs = sorted(c.ref for c in design.circuit.components)
    assert refs == ["C12_CH1", "C12_CH2", "R1A", "R1B"]
    (said,) = [i for i in issues if i.code == "altium.import.channel-naming"]
    assert "2 channel component(s)" in said.message and "R1A against R1_CH1" in said.message
    assert [i for i in design.validate() if i.code == "model.duplicate-ref"] == []


def test_options_of_the_project_file() -> None:
    text = (
        "[Design]\r\nVersion=1.0\r\nHierarchyMode=0\r\nChannelRoomNamingStyle=0\r\n"
        "ChannelRoomLevelSeperator=-\r\nChannelDesignatorFormatString=$Component_$RoomName\r\n"
    )
    project = read_project(text.encode("utf-8"), file="p.PrjPcb")
    assert project.options.channel_designator_format == FORMAT
    assert project.options.channel_room_naming_style == 0
    assert project.options.channel_room_level_separator == "-"
    options = NetOptions.from_project(project)
    assert (options.channel_format, options.room_style, options.room_separator) == (FORMAT, 0, "-")
    bare = read_project(b"[Design]\r\nVersion=1.0\r\n", file="p.PrjPcb")
    plain = NetOptions.from_project(bare)
    assert (plain.channel_format, plain.room_style, plain.room_separator) == ("", None, "_")

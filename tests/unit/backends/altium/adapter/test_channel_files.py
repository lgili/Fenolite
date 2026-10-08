# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored two-channel project as files (capability altium-import, "Repeated sheets as channels",
"Channel designators", "Channel nets"; change c0083): ``tests/data/altium/channels/two/`` equals what its
script writes, and reading the folder gives the channels."""

from __future__ import annotations

import shutil
from pathlib import Path

import _altium_channels as two

from fenolite.backends.altium import schdoc
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.layout import layout_sheet
from fenolite.backends.altium.read.sch import read_schematic

FOLDER = Path(__file__).resolve().parents[4] / "data" / "altium" / "channels" / "two"


def test_files_equal_what_the_script_writes() -> None:
    written = two.files()
    assert sorted(written) == sorted(p.name for p in FOLDER.iterdir() if p.suffix != ".py")
    for name, data in written.items():
        assert (FOLDER / name).read_bytes() == data, name


def fields(record: object) -> dict[str, str]:
    props = record.props  # type: ignore[attr-defined]
    return {key: props.get(key) for key in props.keys()}


def test_sheets_are_written_as_the_schematic_writer_writes() -> None:
    """Change c0146: the first files of this sample held a sheet record without an area colour, no colour
    on any record, no body and pins of length 0, and Altium showed a black page. The sheets now come from
    the schematic writer: its sheet record, a colour on every record that has one in a written sheet, a
    filled body per component and pins of 200 mil. The repeated sheet symbol and the repeated sheet entry
    differ from plain ones in their text alone."""
    plain = schdoc.sheet_record(layout_sheet([]))
    for name in (two.TOP, two.CHILD):
        document = read_schematic((FOLDER / name).read_bytes(), file=name)
        assert document.issues == () and document.additional == ()
        sheet, *rest = (fields(record) for record in document.records)
        assert list(sheet.items()) == plain and sheet["AREACOLOR"] == schdoc.SHEET_COLOR
        kinds = {int(record["RECORD"]) for record in rest}
        assert kinds <= {1, 2, 14, 15, 16, 18, 25, 26, 27, 32, 33, 34, 37, 41}
        assert all("COLOR" in record for record in rest if record["RECORD"] != "2"), name
        pins = [record for record in rest if record["RECORD"] == "2"]
        assert pins and {record["PINLENGTH"] for record in pins} == {"20"}
        components = [n for n, record in enumerate(rest, start=1) if record["RECORD"] == "1"]
        bodies = [record for record in rest if record["RECORD"] == "14"]
        assert sorted(int(body["OWNERINDEX"]) for body in bodies) == components
        assert all(body["AREACOLOR"] == schdoc.COMPONENT_FILL and body["ISSOLID"] == "T" for body in bodies)
        texts = [record for record in rest if "FONTID" in record or "TEXTFONTID" in record]
        assert texts and {record.get("FONTID", record.get("TEXTFONTID")) for record in texts} == {"1"}
    top = [fields(record) for record in read_schematic((FOLDER / two.TOP).read_bytes()).records]
    (symbol,) = [record for record in top if record["RECORD"] == "15"]
    assert (symbol["COLOR"], symbol["AREACOLOR"]) == (schdoc.SYMBOL_COLOR, schdoc.SYMBOL_FILL)
    vcc, repeated = [record for record in top if record["RECORD"] == "16"]
    assert (vcc["NAME"], repeated["NAME"]) == ("VCC", "Repeat(OUT)")
    differ = {key for key in vcc if vcc[key] != repeated[key]}
    assert differ == {"NAME", "DISTANCEFROMTOP"} and list(vcc) == list(repeated)
    (title,) = [record for record in top if record["RECORD"] == "32"]
    (file_name,) = [record for record in top if record["RECORD"] == "33"]
    assert title["TEXT"] == two.STATEMENT and file_name["TEXT"] == two.CHILD
    assert {key for key in title if title[key] != file_name[key]} == {"RECORD", "LOCATION.Y", "TEXT"}
    (bus,) = [record for record in top if record["RECORD"] == "26"]
    labels = [record["TEXT"] for record in top if record["RECORD"] == "25"]
    assert bus["COLOR"] == schdoc.BUS_COLOR and labels.count("OUT[1..2]") == 1
    child = [fields(record) for record in read_schematic((FOLDER / two.CHILD).read_bytes()).records]
    assert [record["NAME"] for record in child if record["RECORD"] == "18"] == ["VCC", "OUT"]
    # no net label names the nets of the two ports: a label would name them in every channel
    assert [record["TEXT"] for record in child if record["RECORD"] == "25"] == ["MID", "MID"]


def test_repeat_bus_and_project_forms() -> None:
    """Change c0151 (scenarios "Bus label beside the connection point" and "Project keys of the
    two-channel sample"): no net label of the top sheet lies on the connection point of a sheet entry, the
    label of the bus lies on the bus line 100 mil past the entry, and the project file's ``[Design]`` holds
    the corpus keys that name nets or order a compile, in the corpus order."""
    top = [fields(record) for record in read_schematic((FOLDER / two.TOP).read_bytes()).records]
    (symbol,) = [record for record in top if record["RECORD"] == "15"]
    right = int(symbol["LOCATION.X"]) + int(symbol["XSIZE"])
    points = {
        (right, int(symbol["LOCATION.Y"]) - 10 * int(entry["DISTANCEFROMTOP"]))
        for entry in top
        if entry["RECORD"] == "16"
    }
    labels = {(int(r["LOCATION.X"]), int(r["LOCATION.Y"])): r["TEXT"] for r in top if r["RECORD"] == "25"}
    assert not points & set(labels)
    (bus,) = [record for record in top if record["RECORD"] == "26"]
    start = (int(bus["X1"]), int(bus["Y1"]))
    assert start in points and labels[(start[0] + 10, start[1])] == "OUT[1..2]"
    text = (FOLDER / two.PROJECT).read_bytes().decode("utf-8")
    design = text.split("\r\n\r\n", 1)[0].split("\r\n")[1:]
    assert [line.split("=", 1)[0] for line in design] == [
        "Version",
        "HierarchyMode",
        "ChannelRoomNamingStyle",
        "ChannelDesignatorFormatString",
        "ChannelRoomLevelSeperator",
        *(key for key, _value in two.NETLIST_KEYS),
    ]
    assert "AllowSheetEntryNetNames=1" in design and "ReorderDocumentsOnCompile=1" in design


def test_folder_reads_as_two_channels(tmp_path: Path) -> None:
    """Scenarios "Two channels", "Designators from the naming format" and "Shared and per-channel nets",
    on the files: no PCB document and no annotation file."""
    folder = tmp_path / "two"
    shutil.copytree(FOLDER, folder, ignore=shutil.ignore_patterns("*.py"))
    backend = AltiumBackend()
    read = backend.read_documents(backend.documents(folder))
    assert read.schematic is not None and read.pcb is None
    circuit = read.schematic.design.circuit
    assert sorted(module.path for module in circuit.modules) == ["CH[1]", "CH[2]"]
    assert sorted(c.ref for c in circuit.components) == ["C12_CH1", "C12_CH2", "J1", "R1_CH1", "R1_CH2", "U1"]
    refs = {component.id: component.ref for component in circuit.components}
    nets = {net.name: sorted((refs[m.component_id], m.pin) for m in net.members) for net in circuit.nets}
    assert nets["VCC"] == [("J1", "1"), ("R1_CH1", "1"), ("R1_CH2", "1")]
    assert nets["OUT1"] == [("C12_CH1", "2"), ("U1", "1")] and nets["OUT2"] == [("C12_CH2", "2"), ("U1", "2")]
    assert sorted(name for name in nets if name.startswith("MID")) == ["MID_CH1", "MID_CH2"]
    codes = {issue.code for issue in read.schematic.issues}
    assert "altium.import.channels" in codes
    assert not codes & {"altium.import.repeated-sheet", "altium.import.channel-naming"}

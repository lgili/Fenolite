# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium drawn extractor (change c0470, tasks 2.1 to 2.4; capability drawn-schematic, "Drawn content of
read Altium sheets"). The small documents here are authored ASCII sheets (``_altium_sch_build``); every value
is authored for Fenolite."""

from __future__ import annotations

from _altium_sch_build import SHEET, ascii_doc
from _drawings import BLINK, HIER, altium_drawing, altium_sheets

from fenolite.backends.altium import drawn_read
from fenolite.backends.altium.adapter.netlist import SheetInput, resolve
from fenolite.backends.altium.read import sch
from fenolite.core.coords import Point
from fenolite.model.drawn_connect import resolve as resolve_drawn

MIL10 = 254_000
"""One 10-mil unit in nm."""
A4_HEIGHT = 760


def _doc(*lines: str, sheet: str = SHEET, file: str = "authored.SchDoc") -> drawn_read.Extracted:
    data = ascii_doc([sheet, *lines])
    return drawn_read.extract_with_pins([SheetInput(file, "", sch.read_schematic(data, file=file))])


def _at(x: int, y: int, height: int = A4_HEIGHT) -> Point:
    return Point(x * MIL10, (height - y) * MIL10)


def _part(
    ref: str, x: int, y: int, *, index: int = 1, orientation: int = 0, mirrored: bool = False, extra: str = ""
) -> list[str]:
    """A one-pin component at ``(x, y)`` whose pin ``1`` ends 10 units to its left; ``index`` is the record
    number of the component in the document (the sheet record is 0)."""
    mirror = "|ISMIRRORED=T" if mirrored else ""
    return [
        f"|RECORD=1|LIBREFERENCE=AUTHORED|CURRENTPARTID=1|PARTCOUNT=2|DISPLAYMODECOUNT=2|LOCATION.X={x}"
        f"|LOCATION.Y={y}|ORIENTATION={orientation}{mirror}|UNIQUEID=AUTH{ref}{extra}",
        f"|RECORD=2|OWNERINDEX={index}|OWNERPARTID=1|LOCATION.X={x}|LOCATION.Y={y}|PINLENGTH=10|PINCONGLOMERATE=34"
        "|DESIGNATOR=1|NAME=A|ELECTRICAL=4",
        f"|RECORD=34|OWNERINDEX={index}|OWNERPARTID=-1|LOCATION.X={x}|LOCATION.Y={y + 10}|TEXT={ref}"
        "|NAME=Designator",
    ]


# --- 2.1 symbols, wires, junctions and net labels -----------------------------------------------------------


def test_blink_symbols_wires_and_labels() -> None:
    """Task 2.1: each part of ``blink`` is one symbol at its location, with its designator and comment; the
    nets resolved from the drawing are the nets of ``altium-import``."""
    found = altium_drawing(BLINK)
    assert [i for i in found.issues if i.severity != "info"] == []
    (sheet,) = found.drawn.sheets
    assert [(s.part, s.unit, s.rotation, s.mirror) for s in sheet.symbols] == [
        ("D1", 1, 0, ""), ("R1", 1, 0, ""), ("U1", 1, 0, ""),
    ]  # fmt: skip
    assert all([f.name for f in s.fields][:2] == ["Reference", "Value"] for s in sheet.symbols)
    assert len(sheet.wires) == 7 and {label.text for label in sheet.labels} == {"LED_A", "LED_DRV"}
    sheets = altium_sheets(BLINK)
    resolved = resolve(sheets, issues=[])
    native = {
        tuple(sorted((resolved.refs[key], pin.designator) for pin in net.pins for key, cid in
                     resolved.component_ids.items() if cid == pin.component))
        for net in resolved.netlist.nets
    }  # fmt: skip
    drawn = {tuple(sorted(net.members)) for net in resolve_drawn(found.drawn, found.pins).nets}
    assert {n for n in drawn if len(n) > 1} == {n for n in native if len(n) > 1}


def test_blink_keeps_power_styles_and_part_counts() -> None:
    """Task 2.1: the Altium fields a drawn item cannot hold stay in ``altium_fields`` (design D4)."""
    found = altium_drawing(BLINK)
    fields = found.altium_fields["blink"]
    assert fields["power:0"] == {"STYLE": "4", "SHOWNETNAME": "T"}
    assert fields["symbol:0"] == {"PARTCOUNT": "2", "DISPLAYMODECOUNT": "1"}
    assert [p.symbol for p in found.drawn.sheets[0].powers] == [
        "AltiumPower:power_ground", "AltiumPower:bar", "AltiumPower:power_ground",
    ]  # fmt: skip


def test_blink_mirror_part_and_display_mode() -> None:
    """Task 2.1: Altium mirrors about the vertical axis before it turns; in KiCad's order that is ``y`` at
    0 and 180 degrees and ``x`` at 90 and 270. The part number is the unit and the display mode is kept."""
    lines = [
        *_part("R1", 200, 400, orientation=1, mirrored=True, extra="|DISPLAYMODE=1"),
        *_part("R2", 400, 400, index=4, mirrored=True),
    ]
    found = _doc(*lines)
    first, second = found.drawn.sheets[0].symbols
    assert (first.part, first.rotation, first.mirror, first.at) == ("R1", 90_000_000, "x", _at(200, 400))
    assert (second.part, second.rotation, second.mirror) == ("R2", 0, "y")
    assert found.altium_fields["authored"]["symbol:0"]["DISPLAYMODE"] == "1"


def test_blink_wire_split_at_pins_and_tee_junction() -> None:
    """Task 2.1: a wire through a pin end is split there, and a wire end inside another wire gets a junction
    (Altium joins them; KiCad needs the junction)."""
    lines = [
        *_part("R1", 300, 400),
        "|RECORD=27|LOCATIONCOUNT=2|X1=200|Y1=400|X2=400|Y2=400",
        "|RECORD=27|LOCATIONCOUNT=2|X1=250|Y1=400|X2=250|Y2=300",
        "|RECORD=25|LOCATION.X=220|LOCATION.Y=400|TEXT=NODE",
    ]
    found = _doc(*lines)
    sheet = found.drawn.sheets[0]
    assert _at(290, 400) in sheet.wires[0][1:-1]  # the pin end of R1 is a vertex of the split wire
    assert [j.at for j in sheet.junctions] == [_at(250, 400)]
    assert any(i.code == "altium.drawn.tee" for i in found.issues)
    # one sheet without sheet symbols has the global scope of ``altium-import``: its net labels are global
    assert [(label.kind, label.text) for label in sheet.labels] == [("global", "NODE")]


# --- 2.2 ports, power, sheets, buses, no-ERC ---------------------------------------------------------------


def test_hier_sheet_symbols_and_hierarchical_ports() -> None:
    """Task 2.2: ``hier`` has a root with two sheet symbols; under the hierarchical scope a port is a
    hierarchical label and a harness port a bus group of the connector's entries."""
    found = altium_drawing(HIER)
    assert [i for i in found.issues if i.severity != "info"] == []
    root, flash, mcu = found.drawn.sheets
    assert found.drawn.root == root.key == "altium_hier"
    assert [(r.key, r.sheet, r.module) for r in root.sheet_refs] == [
        ("flash", "altium_hier_flash", "flash"), ("mcu", "altium_hier_mcu", "mcu"),
    ]  # fmt: skip
    assert "FLASH_WP" in {pin.name for pin in root.sheet_refs[0].pins}
    kinds = {(label.kind, label.text) for label in flash.labels}
    assert ("hierarchical", "FLASH_WP") in kinds
    assert ("hierarchical", "SPI{CS MISO MOSI SCK}") in kinds
    assert {p.symbol for p in mcu.powers} >= {"AltiumPower:power_ground"}


def test_hier_nets_equal_altium_import() -> None:
    """Task 2.2: the nets of the drawing, harness members included, are the nets of ``altium-import``."""
    sheets = altium_sheets(HIER)
    resolved = resolve(sheets, issues=[])
    found = drawn_read.extract_with_pins(sheets, resolved=resolved)
    paths = {
        resolved.component_ids[key]: "/".join((*resolved.instances[key[0]].names, ref))
        for key, ref in resolved.refs.items()
    }
    native = {
        tuple(sorted((paths[p.component], p.designator) for p in n.pins)) for n in resolved.netlist.nets
    }
    drawn = {tuple(sorted(net.members)) for net in resolve_drawn(found.drawn, found.pins).nets}
    assert {n for n in drawn if len(n) > 1} == {n for n in native if len(n) > 1}


def test_ports_are_global_on_a_flat_sheet_and_keep_their_style() -> None:
    """Task 2.2: without sheet symbols a port is a global label at the end a wire touches, its body turned
    away from the wire; its style stays in ``altium_fields``."""
    lines = [
        "|RECORD=27|LOCATIONCOUNT=2|X1=100|Y1=500|X2=200|Y2=500",
        "|RECORD=18|LOCATION.X=200|LOCATION.Y=500|WIDTH=50|HEIGHT=10|STYLE=3|IOTYPE=2|NAME=IN_A",
        "|RECORD=27|LOCATIONCOUNT=2|X1=350|Y1=500|X2=450|Y2=500",
        "|RECORD=18|LOCATION.X=300|LOCATION.Y=500|WIDTH=50|HEIGHT=10|STYLE=3|IOTYPE=1|NAME=OUT_A",
    ]
    found = _doc(*lines)
    first, second = found.drawn.sheets[0].labels
    assert (first.kind, first.text, first.at, first.rotation, first.shape) == (
        "global", "IN_A", _at(200, 500), 0, "input",
    )  # fmt: skip
    assert (second.text, second.at, second.rotation, second.shape) == ("OUT_A", _at(350, 500), 180_000_000,
                                                                        "output")  # fmt: skip
    assert found.altium_fields["authored"]["label:0"]["STYLE"] == "3"


def test_ports_with_both_ends_on_wires_warn() -> None:
    lines = [
        "|RECORD=27|LOCATIONCOUNT=2|X1=100|Y1=500|X2=200|Y2=500",
        "|RECORD=27|LOCATIONCOUNT=2|X1=250|Y1=500|X2=350|Y2=500",
        "|RECORD=18|LOCATION.X=200|LOCATION.Y=500|WIDTH=50|HEIGHT=10|STYLE=3|NAME=BOTH",
    ]
    assert [i.code for i in _doc(*lines).issues] == ["altium.drawn.port-ends"]


def test_power_ports_and_cross_sheet_connectors() -> None:
    """Task 2.2: a power port is a power item of the ``AltiumPower`` style library; a cross-sheet connector
    is a global label."""
    lines = [
        "|RECORD=17|LOCATION.X=100|LOCATION.Y=600|STYLE=2|ORIENTATION=1|TEXT=VCC|SHOWNETNAME=T",
        "|RECORD=17|LOCATION.X=300|LOCATION.Y=600|STYLE=1|ISCROSSSHEETCONNECTOR=T|TEXT=LINK",
        "|RECORD=17|LOCATION.X=500|LOCATION.Y=600|STYLE=4",
    ]
    found = _doc(*lines)
    sheet = found.drawn.sheets[0]
    assert [(p.symbol, p.net, p.at, p.rotation) for p in sheet.powers] == [
        ("AltiumPower:bar", "VCC", _at(100, 600), 90_000_000),
    ]  # fmt: skip
    assert [(label.kind, label.text) for label in sheet.labels] == [("global", "LINK")]
    assert [(i.severity, i.code) for i in found.issues] == [("error", "altium.drawn.unrepresented")]


def test_buses_bus_entries_and_no_erc() -> None:
    lines = [
        "|RECORD=26|LOCATIONCOUNT=2|X1=100|Y1=300|X2=100|Y2=500",
        "|RECORD=37|LOCATION.X=100|LOCATION.Y=400|CORNER.X=110|CORNER.Y=410",
        "|RECORD=22|LOCATION.X=600|LOCATION.Y=600|ISACTIVE=T",
    ]
    sheet = _doc(*lines).drawn.sheets[0]
    assert sheet.buses == ((_at(100, 300), _at(100, 500)),)
    (entry,) = sheet.bus_entries
    assert (entry.at, entry.size.x, entry.size.y) == (_at(100, 400), 10 * MIL10, -10 * MIL10)
    assert sheet.no_connects == (_at(600, 600),)


# --- 2.3 typed opaque items ---------------------------------------------------------------------------------


def test_opaque_records_keep_their_fields() -> None:
    """Task 2.3: a record that no drawn item holds is an opaque item whose Altium text is the record and its
    children, each child naming its owner's line; a graphic has a KiCad stand-in."""
    lines = [
        "|RECORD=43|LOCATION.X=115|LOCATION.Y=660|NAME=Parameter Set",
        "|RECORD=41|OWNERINDEX=1|LOCATION.X=115|LOCATION.Y=660|NAME=ClassName|TEXT=PWR",
        "|RECORD=13|LOCATION.X=100|LOCATION.Y=100|CORNER.X=200|CORNER.Y=100|LINEWIDTH=1",
        "|RECORD=28|LOCATION.X=300|LOCATION.Y=100|CORNER.X=400|CORNER.Y=150|TEXT=frame text",
        "|RECORD=209|LOCATION.X=500|LOCATION.Y=100|CORNER.X=600|CORNER.Y=150|TEXT=a note|AUTHOR=fenolite",
    ]
    found = _doc(*lines)
    opaque = found.drawn.sheets[0].opaques
    assert len(opaque) == 4
    assert opaque[0].altium.splitlines() == [
        "|RECORD=43|LOCATION.X=115|LOCATION.Y=660|NAME=Parameter Set",
        "|RECORD=41|OWNERINDEX=@0|LOCATION.X=115|LOCATION.Y=660|NAME=ClassName|TEXT=PWR",
    ]
    assert opaque[0].kicad == ""
    assert opaque[1].kicad.startswith("(polyline")
    assert opaque[3].altium.startswith("|RECORD=209|")
    assert found.counts == {"sheet": 1, "directive": 1, "schematic-graphic": 1, "schematic-text": 2}


def test_opaque_harness_records() -> None:
    """Task 2.3: a harness connector is an opaque item with a rectangle stand-in and a local label per entry;
    a signal harness is a bus and an opaque item."""
    found = altium_drawing(HIER)
    flash = found.drawn.sheets[1]
    texts = [item.altium.split("|")[1] for item in flash.opaques]
    assert texts == ["RECORD=18", "RECORD=215", "RECORD=218"]
    assert flash.opaques[1].kicad.startswith("(rectangle")
    assert {label.text for label in flash.labels if label.kind == "local"} >= {"SPI.CS", "SPI.SCK"}
    assert found.counts["harness"] == 5


# --- 2.4 sheet and inexact lengths -------------------------------------------------------------------------


def test_sheet_paper_orientation_and_title_block() -> None:
    """Task 2.4: the sheet style and orientation give the paper; document parameters the title block; the
    sheet record stays in ``sheet_records`` for the carrier."""
    sheet = "|RECORD=31|FONTIDCOUNT=1|SIZE1=10|FONTNAME1=Times New Roman|SHEETSTYLE=1|WORKSPACEORIENTATION=1"
    lines = [
        "|RECORD=41|LOCATION.X=0|LOCATION.Y=0|NAME=Title|TEXT=Authored board",
        "|RECORD=41|LOCATION.X=0|LOCATION.Y=0|NAME=Revision|TEXT=B",
        "|RECORD=41|LOCATION.X=0|LOCATION.Y=0|NAME=Checker|TEXT=QA",
        "|RECORD=41|LOCATION.X=0|LOCATION.Y=0|NAME=DrawnBy|TEXT=*",
    ]
    found = _doc(*lines, sheet=sheet)
    drawn = found.drawn.sheets[0]
    assert drawn.paper == "A3 portrait"
    assert drawn.title_block == (("title", "Authored board"), ("revision", "B"), ("param.Checker", "QA"))
    assert found.sheet_records["authored"].splitlines()[0].startswith("|RECORD=31|")


def test_sheet_custom_size() -> None:
    sheet = "|RECORD=31|USECUSTOMSHEET=T|CUSTOMX=1000|CUSTOMY=500|SHEETSTYLE=0"
    found = _doc("|RECORD=29|LOCATION.X=100|LOCATION.Y=100", sheet=sheet)
    drawn = found.drawn.sheets[0]
    assert drawn.paper == f"custom:{1000 * MIL10}x{500 * MIL10}"
    assert drawn.junctions[0].at == _at(100, 100, height=500)


def test_inexact_lengths_are_rounded_and_counted() -> None:
    """Task 2.4: a fraction that is no whole nanometre is rounded and counted by ``altium.import.inexact``
    (the junction and the stand-in of the line); the opaque item keeps the exact text."""
    lines = [
        "|RECORD=29|LOCATION.X=100|LOCATION.X_FRAC=1|LOCATION.Y=100",
        "|RECORD=13|LOCATION.X=100|LOCATION.X_FRAC=1|LOCATION.Y=100|CORNER.X=200|CORNER.Y=100",
    ]
    found = _doc(*lines)
    junction = found.drawn.sheets[0].junctions[0]
    assert junction.at.x == 100 * MIL10 + 3  # 2.54 nm, rounded
    (issue,) = [i for i in found.issues if i.code == "altium.import.inexact"]
    assert issue.message.startswith("2 length(s)")
    assert "LOCATION.X_FRAC=1" in found.drawn.sheets[0].opaques[0].altium

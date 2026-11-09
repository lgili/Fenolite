# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What keeps an Altium source's drawing through KiCad (change c0470, task 5.4): the section keys of long lib
refs that share a prefix, one spelling for the labels Altium joins without letter case, the carried
``HARNESSTYPE`` of sheet entries and label texts, custom paper and the document parameters KiCad's title
block has no field for."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace
from typing import cast

import pytest
from _altium import upright_symbol

from fenolite.backends.altium import drawn, drawn_read
from fenolite.backends.altium import drawn as altium_drawn
from fenolite.backends.altium.adapter.connectivity import Lines
from fenolite.backends.altium.layout import SHEET_SIZES, PartSpec, SheetPlan
from fenolite.backends.altium.prjpcb import write_prjpcb
from fenolite.backends.altium.read.sch import SchDocument, SheetEntry
from fenolite.backends.altium.read.schlib import read_schlib
from fenolite.backends.altium.schlib import storage_names, write_schlib
from fenolite.backends.kicad import sheet_carrier
from fenolite.convert import to_altium
from fenolite.core.coords import Point, Size
from fenolite.model.board import Board
from fenolite.model.circuit import Circuit, Component, Net, Pin, PinRef
from fenolite.model.design import Design
from fenolite.model.drawn import DrawnLabel, DrawnPin, DrawnSchematic, DrawnSheet, DrawnSheetRef

_LONG = "DF40HC(3.0)-100DS-0.4V_-SoM-MAX"  # 31 characters


def test_cut_names_that_share_a_prefix_get_keys_of_their_own() -> None:
    names = storage_names([f"{_LONG}_C", f"{_LONG}_A", "R1", _LONG])
    assert names[_LONG] == _LONG and names["R1"] == "R1"  # names stored as they are keep them
    assert names[f"{_LONG}_A"] == _LONG[:29] + "_2"
    assert names[f"{_LONG}_C"] == _LONG[:29] + "_3"
    assert all(len(key) <= 31 for key in names.values())


def test_a_library_keeps_both_long_names() -> None:
    first, second = (dataclasses.replace(upright_symbol(), lib_ref=f"{_LONG}_{s}") for s in "AC")
    library = read_schlib(write_schlib([first, second], library="L.SchLib"))
    assert sorted(c.name for c in library.components) == [f"{_LONG}_A", f"{_LONG}_C"]
    assert sorted(c.storage_name for c in library.components) == [
        _LONG,
        _LONG[:29] + "_2",
    ]  # the first keeps the cut


def _label(text: str, x: int, kind: str = "local") -> DrawnLabel:
    return DrawnLabel(kind, text, Point(x, 0))  # type: ignore[arg-type]


def test_labels_that_differ_in_case_take_one_spelling_and_keep_their_own() -> None:
    labels = [
        _label("I2C_SCL_3v3", 1_000),
        _label("I2C_SCL_3V3", 2_000),
        _label("I2C_scl_3v3", 3_000, "hierarchical"),
    ]
    kept: dict[str, dict[str, str]] = {}
    drawn_read.one_spelling(labels, kept)
    assert [label.text for label in labels] == ["I2C_SCL_3V3", "I2C_SCL_3V3", "I2C_scl_3v3"]
    assert kept == {"text:1000,0": {"TEXT": "I2C_SCL_3v3"}}  # a port keeps its text: KiCad joins it by name
    again = [_label("I2C_SCL_3V3", 2_000), _label("I2C_SCL_3v3", 1_000)]
    drawn_read.one_spelling(again, {})
    assert {label.text for label in again} == {"I2C_SCL_3V3"}  # whatever the record order


def _entry(name: str, harness_type: str) -> SheetEntry:
    return cast(SheetEntry, SimpleNamespace(name=name, harness_type=harness_type))


def test_the_carrier_keeps_an_entry_type_kicad_cannot_draw() -> None:
    members = {"lcd_ctrl": ("A", "B"), "usb": ("D_P", "D_N")}
    assert drawn_read.lone_harness(_entry("LCD", "USB_CTRL"), "USB_CTRL", members) == {
        "HARNESSTYPE": "USB_CTRL"
    }
    assert drawn_read.lone_harness(_entry("BMS", ""), "LCD_CTRL", members) == {"HARNESSTYPE": ""}
    assert drawn_read.lone_harness(_entry("LCD", "LCD_CTRL"), "LCD_CTRL", members) == {}
    assert drawn_read.lone_harness(_entry("X", ""), "", members) == {}
    # an entry drawn with its child port's type keeps its own, stale type in the carrier
    assert drawn_read.lone_harness(_entry("IOs", "USB"), "LCD_CTRL", members) == {"HARNESSTYPE": "USB"}


def test_an_entry_is_drawn_with_the_type_of_its_child_port() -> None:
    entry = _entry("IOs", "USB")
    document = cast(SchDocument, None)
    lines = cast(Lines, None)
    assert drawn_read.entry_harness(document, entry, lines, {"IOs": "IOs"}) == "IOs"
    assert drawn_read.entry_harness(document, entry, lines, {}) == "USB"
    assert drawn_read.entry_harness(document, _entry("", "USB"), lines, {"": "IOs"}) == ""


def test_the_writer_reads_the_carried_fields() -> None:
    harness, spellings = drawn.carried(
        {
            "harness:Connector C:LCD_CTRL": {"HARNESSTYPE": "USB_CTRL"},
            "harness:Power:BMS": {"HARNESSTYPE": ""},
            "text:1000,-20": {"TEXT": "I2C_SCL_3v3"},
            "label:3": {"STYLE": "1"},
        }
    )
    assert harness == {("Connector C", "LCD_CTRL"): "USB_CTRL", ("Power", "BMS"): ""}
    assert spellings == {(1_000, -20): "I2C_SCL_3v3"}


def test_carried_fields_come_back_from_a_kicad_sheet() -> None:
    carrier = sheet_carrier.AltiumSheet("", (), {"harness:S:E": {"HARNESSTYPE": "T"}})
    text = sheet_carrier.put('(kicad_sch (version 20250114) (paper "A4"))', carrier.text())
    found = sheet_carrier.carried_fields(
        {"top.kicad_sch": text}, DrawnSchematic("top", (DrawnSheet("top"),)), "top.kicad_sch"
    )
    assert found == {"top": {"harness:S:E": {"HARNESSTYPE": "T"}}}


@pytest.mark.parametrize(
    ("paper", "size"),
    [("A4", ("A4", 11_500, 7_600)), ("custom:381000000x254000000", ("custom", 15_000, 10_000))],
)
def test_sheet_size_of_a_named_or_custom_paper(paper: str, size: tuple[str, int, int]) -> None:
    found = drawn.sheet_size(paper)
    assert found is not None and (found.name, found.width, found.height) == size


def test_sheet_size_refuses_a_paper_off_the_file_unit() -> None:
    assert drawn.sheet_size("custom:381000001x254000000") is None
    assert drawn.sheet_size("B5") is None


def test_document_parameters_without_a_title_block_field_come_back() -> None:
    lines = "\n".join(
        [
            "|RECORD=41|NAME=SheetNumber|TEXT=3",
            "|RECORD=41|NAME=Title|TEXT=kept by the title block",
            "|RECORD=41|NAME=Owner|TEXT=*",
            "|RECORD=41|OWNERINDEX=4|NAME=Comment|TEXT=a part's",
            "|RECORD=41|NAME=Fenolite.KiCad.Sheet|TEXT=carrier",
        ]
    )
    assert sheet_carrier.sheet_params(lines) == {"SheetNumber": "3"}


def _flagged_case() -> tuple[Design, Design]:
    parts = tuple(
        Component(
            id=f"c{ref}", ref=ref, pins=(Pin(id=f"p{ref}1", number="1"), Pin(id=f"p{ref}2", number="2"))
        )
        for ref in ("J1", "R1")
    )
    nets = (
        Net(id="n_label", name="MIPI_TX0_D0_P", members=(PinRef("cJ1", "1"),)),
        Net(id="n_open", name="unconnected-(J1-Pad2)", members=(PinRef("cJ1", "2"),)),
        Net(id="n_two", name="SDA", members=(PinRef("cR1", "1"), PinRef("cR1", "2"))),
    )
    pads = {
        "cJ1": (SimpleNamespace(number="1", net_id="n_label"), SimpleNamespace(number="2", net_id="n_open")),
        "cR1": (SimpleNamespace(number="1", net_id="n_two"), SimpleNamespace(number="2", net_id="n_two")),
    }
    board = SimpleNamespace(footprints=[SimpleNamespace(component_id=c, pads=p) for c, p in pads.items()])
    base = Design.new("flagged", seed=0)
    design = dataclasses.replace(base, circuit=Circuit(components=parts, nets=nets), board=cast(Board, board))
    marks = (PinRef("cJ1", "1"), PinRef("cJ1", "2"), PinRef("cR1", "1"))
    sch = dataclasses.replace(base, circuit=Circuit(components=parts, nets=(), no_connects=marks))
    return design, sch


def test_a_flagged_pin_on_a_labelled_net_explains_its_net() -> None:
    """KiCad's netlist lists a pin under a no-connect flag as not connected; the board, and Altium's
    netlist, name its net when a label does. Only that pin is explained: not a pin on KiCad's own
    ``unconnected-(…)`` net, nor one that shares its net."""
    design, sch = _flagged_case()
    assert to_altium._flagged_named(design, sch) == ("cJ1:1",)  # pyright: ignore[reportPrivateUsage]
    assert to_altium._flagged_named(design, None) == ()  # pyright: ignore[reportPrivateUsage]


def _channels(refs: dict[str, tuple[str, str]]) -> tuple[DrawnSchematic, dict[str, PartSpec]]:
    """A root with two sheet symbols ``1`` and ``2`` of the sheet ``cell`` (two parts ``R`` and ``C``);
    ``refs`` names each part's component per channel."""
    from fenolite.core.coords import Size
    from fenolite.model.drawn import DrawnSheetRef, DrawnSymbol

    sheet_refs = tuple(
        DrawnSheetRef(f"k{n}", "cell", f"M/{n}", n, Point(0, 1_000_000 * int(n)), Size(1_000_000, 500_000), n)
        for n in ("1", "2")
    )
    cell = DrawnSheet(
        "cell", symbols=(DrawnSymbol("R", 1, Point(0, 0)), DrawnSymbol("C", 1, Point(0, 5_000_000)))
    )
    drawn = DrawnSchematic("root", (DrawnSheet("root", sheet_refs=sheet_refs), cell))
    specs = {
        f"M/{n}/{part}": cast(PartSpec, SimpleNamespace(ref=refs[part][i], unique_id=f"U{part}{n}"))
        for part in ("R", "C")
        for i, n in enumerate(("1", "2"))
    }
    return drawn, specs


def test_a_sheet_whose_parts_follow_the_channel_names_is_written_once() -> None:
    """Altium names a component of a channel ``<designator>_<sheet symbol>`` under ``CHANNEL_KEYS``: a reused
    sheet whose every part is so named is one sheet of two channels, its records named ``R1`` and ``C1``."""
    from fenolite.model.drawn_connect import instances

    drawn, specs = _channels({"R": ("R1_1", "R1_2"), "C": ("C1_1", "C1_2")})
    found, _ = instances(drawn)
    sheets = altium_drawn.channel_sheets(found, drawn, specs)
    assert sheets == {"cell": {"M/1/R": "R1", "M/2/R": "R1", "M/1/C": "C1", "M/2/C": "C1"}}
    links = {link.ref: link for link in altium_drawn.sheet_links(found, drawn, specs, sheets)}
    assert links["R1_2"].unique_id == "UR1" and links["R1_2"].designator == "R1" and links["R1_2"].channel
    assert links["R1_1"].names == "1" and links["R1_2"].names == "2"
    assert links["R1_1"].symbols != links["R1_2"].symbols  # one sheet symbol per channel


@pytest.mark.parametrize(
    "refs",
    [
        {"R": ("R1_1", "R2_2"), "C": ("C1_1", "C1_2")},  # two designators for one part
        {"R": ("R1", "R2"), "C": ("C1_1", "C1_2")},  # a part named otherwise
        {"R": ("X_1", "X_2"), "C": ("X_1", "X_2")},  # two parts with one designator
    ],
)
def test_other_names_keep_one_sheet_per_instance(refs: dict[str, tuple[str, str]]) -> None:
    from fenolite.model.drawn_connect import instances

    drawn, specs = _channels(refs)
    found, _ = instances(drawn)
    assert altium_drawn.channel_sheets(found, drawn, specs) == {}
    links = {link.ref: link for link in altium_drawn.sheet_links(found, drawn, specs, {})}
    assert not any(link.channel for link in links.values())


def test_the_project_file_names_the_channels() -> None:
    text = write_prjpcb(schematic="top.SchDoc", channels=True).decode("ascii")
    assert "ChannelDesignatorFormatString=$Component_$RoomName\r\n" in text
    assert "ChannelRoomNamingStyle=0\r\n" in text and "ChannelRoomLevelSeperator=_\r\n" in text
    assert "Channel" not in write_prjpcb(schematic="top.SchDoc").decode("ascii")


@dataclasses.dataclass
class _Typed:
    text: str = ""
    name: str = ""


class _Connector(_Typed):
    pass


class _Type(_Typed):
    pass


class _Entry(_Typed):
    pass


def _harness_doc(kind: str, *names: str) -> SchDocument:
    connector = _Connector()
    children = [_Type(text=kind), *(_Entry(name=name) for name in names)]
    return cast(
        SchDocument,
        SimpleNamespace(
            of_type=lambda found: [connector] if found is _Connector else [],
            children_of=lambda _: children,
        ),
    )


def test_harness_members_take_a_natural_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two connectors of a type list their entries in other orders, and the documents come in other
    orders: the members of a type are named in one order."""
    for name, kind in (("HarnessConnector", _Connector), ("HarnessType", _Type), ("HarnessEntry", _Entry)):
        monkeypatch.setattr(drawn_read, name, kind)
    one = drawn_read.harness_members([_harness_doc("CAN", "CANL", "CANH")])
    two = drawn_read.harness_members([_harness_doc("CAN", "CANH", "CANL")])
    assert one == two == {"can": ("CANH", "CANL")}
    assert drawn_read.harness_members([_harness_doc("D", "D10", "D2", "D1")]) == {"d": ("D1", "D2", "D10")}


def test_a_flat_project_root_is_marked_in_its_carrier() -> None:
    """The root a flat Altium project gets in KiCad stands for no document: its carrier says so, and the
    way back writes its sheets as top documents again."""
    from fenolite.convert.schematic import flat_tops

    blank = '(kicad_sch (version 20250114) (paper "A4"))'
    marked = sheet_carrier.AltiumSheet("", (), {drawn_read.TOPS_KEY: {drawn_read.TOPS_FIELD: "T"}})
    assert flat_tops(sheet_carrier.put(blank, marked.text()))
    assert not flat_tops(sheet_carrier.put(blank, sheet_carrier.AltiumSheet("", (), {}).text()))
    assert not flat_tops(blank)


def test_a_build_keeps_a_one_member_bus_group_of_a_sheet_pin_for_a_harness() -> None:
    """A bus group ``NAME{MEMBER}`` at a sheet pin on a bus has no native bus vector: a build writes it as a
    signal harness (``harness``), as a conversion does, instead of refusing the drawing (change c0470)."""
    mm = 1_000_000
    pin = DrawnPin("BUS{SIG}", "passive", Point(10 * mm, 10 * mm))
    ref = DrawnSheetRef("child", "child", "", "Child", Point(10 * mm, 5 * mm), Size(10 * mm, 10 * mm), "2",
                        pins=(pin,))  # fmt: skip
    sheet = DrawnSheet("root", buses=((Point(10 * mm, 10 * mm), Point(20 * mm, 10 * mm)),), sheet_refs=(ref,))
    schematic = DrawnSchematic("root", (sheet,))
    with pytest.raises(drawn.FormatError, match="no exact native bus vector"):
        altium_drawn._native_buses(schematic, sheet, "root", [])  # pyright: ignore[reportPrivateUsage]
    kept = altium_drawn._native_buses(schematic, sheet, "root", [], harness=True)  # pyright: ignore[reportPrivateUsage]
    assert kept.sheet_refs[0].pins[0].name == "BUS{SIG}"


def test_a_bus_group_between_two_sheet_entries_is_a_harness_line_without_a_block() -> None:
    """One bus joins the pins ``BUS{SIG}`` of two stacked sheet symbols, and no label of the sheet names a
    member: Altium joins sheet entries on one harness line (H-A-SCH-HARN-NETS), so the bus is written as that
    line alone, with no connector block to fit between the symbols (change c0470)."""
    mil = 25_400
    x, top, bottom = 2_000 * mil, 2_000 * mil, 2_700 * mil  # 700 mil between the stacked symbols
    box = Size(2_400 * mil, 1_000 * mil)
    one = (DrawnPin("BUS{SIG}", "passive", Point(x, top), 270_000_000),)
    two = (DrawnPin("BUS{SIG}", "passive", Point(x, bottom), 90_000_000),)
    upper = DrawnSheetRef("a", "child", "", "A", Point(200 * mil, 1_000 * mil), box, "2", pins=one)
    lower = DrawnSheetRef("b", "child", "", "B", Point(200 * mil, bottom), box, "3", pins=two)
    bus = (Point(x, top), Point(x, bottom))
    sheet = DrawnSheet("root", buses=(bus,), sheet_refs=(upper, lower))
    state = altium_drawn._Sheet(  # pyright: ignore[reportPrivateUsage]
        SheetPlan(SHEET_SIZES[0], (), ()), [], False, "binary", harness=True
    )
    state.aliases = {}
    state.networks(sheet, "root")
    (group,) = state.groups
    assert group.through and group.names == ("BUS",) and group.entries == ("SIG",)
    blocks, lines, polylines, carried = state.harness_blocks()
    assert blocks == [] and lines == [] and len(polylines) == 1
    assert carried is not None and len(carried["networks"]) == 1 and "connectors" not in carried


def test_local_bus_group_labels_and_carried_bus_aliases_round_trip() -> None:
    """A local bus-group label on a bus is lowered as the harness's net label, repeated ends of one harness on
    a sheet share one connector block, and ``Fenolite.KiCad.Sheet`` carries ``bus_aliases`` (change c0470)."""
    from fenolite.backends.altium import drawn_carrier
    from fenolite.model.drawn import DrawnBusAlias

    mil = 25_400
    alias = DrawnBusAlias("I2C", ("SDA", "SCL", "~{INT}"))
    one = DrawnPin("I2C_{SYS}{I2C}", "passive", Point(1_000 * mil, 1_000 * mil))
    two = DrawnPin("I2C_{SYS}{I2C}", "passive", Point(1_000 * mil, 2_000 * mil))
    upper = DrawnSheetRef(
        "a", "child", "", "A", Point(500 * mil, 800 * mil), Size(500 * mil, 400 * mil), "2", pins=(one,)
    )
    lower = DrawnSheetRef(
        "b", "child", "", "B", Point(500 * mil, 1_800 * mil), Size(500 * mil, 400 * mil), "3", pins=(two,)
    )
    buses = (
        (Point(1_000 * mil, 1_000 * mil), Point(1_200 * mil, 1_000 * mil)),
        (Point(1_000 * mil, 2_000 * mil), Point(1_200 * mil, 2_000 * mil)),
    )
    labels = (
        DrawnLabel("local", "I2C_{SYS}{I2C}", Point(1_200 * mil, 1_000 * mil)),
        DrawnLabel("local", "I2C_{SYS}{I2C}", Point(1_200 * mil, 2_000 * mil)),
    )
    sheet = DrawnSheet("root", buses=buses, labels=labels, bus_aliases=(alias,), sheet_refs=(upper, lower))
    schematic = DrawnSchematic("root", (sheet,))
    kept = altium_drawn._native_buses(schematic, sheet, "root", [], harness=True)  # pyright: ignore[reportPrivateUsage]
    assert [label.text for label in kept.labels] == ["I2C_{SYS}{I2C}", "I2C_{SYS}{I2C}"]
    state = altium_drawn._Sheet(  # pyright: ignore[reportPrivateUsage]
        SheetPlan(SHEET_SIZES[0], (), ()), [], False, "binary", carry=True, harness=True
    )
    state.aliases = {"I2C": alias.members}
    state.networks(kept, "root")
    assert len(state.groups) == 1 and not state.groups[0].through and len(state.groups[0].network) == 2
    carried = drawn_carrier.carrier((), bus_aliases=(alias,))
    assert carried is not None
    assert drawn_carrier.KiCadSheet.parse(carried.value()).bus_aliases == (alias,)

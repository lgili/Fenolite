# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Typed records (capability altium-schematic-reader, "Typed records")."""

from __future__ import annotations

from _altium_sch_build import SHEET, pin_payload, schdoc

from fenolite.backends.altium.read import sch
from fenolite.backends.altium.read.sch.records import DataFile
from fenolite.backends.altium.read.sch.units import Color, SchLength
from fenolite.core.errors import Issue


def L(units: int, frac: int = 0) -> SchLength:  # noqa: N802
    return SchLength.of(units, frac)


def _read(*records: str | bytes, issues: list[Issue] | None = None) -> sch.SchDocument:
    return sch.read_schematic(schdoc([SHEET, *records]), issues=issues)


# --- part one: sheet and components -----------------------------------------------------------------------


def test_sheet_attributes() -> None:
    sheet_text = (
        "|RECORD=31|FONTIDCOUNT=2|SIZE1=10|FONTNAME1=Times New Roman|SIZE2=12|FONTNAME2=Arial|BOLD2=T"
        "|ITALIC2=T|UNDERLINE2=T|ROTATION2=90|SYSTEMFONT=1|SHEETSTYLE=3|USECUSTOMSHEET=T|CUSTOMX=1500|CUSTOMY=950"
        "|WORKSPACEORIENTATION=1|TITLEBLOCKON=T|BORDERON=T|AREACOLOR=16317695|TEMPLATEFILENAME=x.SchDot"
    )
    document = sch.read_schematic(schdoc([sheet_text]))
    sheet = document.sheet
    assert isinstance(sheet, sch.Sheet)
    assert sheet.fonts == (
        sch.Font(1, "Times New Roman", 10),
        sch.Font(2, "Arial", 12, italic=True, bold=True, underline=True, rotation=90),
    )
    assert (sheet.sheet_style, sheet.system_font, sheet.portrait, sheet.title_block, sheet.border) == (
        3,
        1,
        True,
        True,
        True,
    )
    assert sheet.custom_size == (L(1500), L(950))
    assert sheet.area_color == Color(0xFF, 0xFC, 0xF8)
    assert sheet.template_file_name == "x.SchDot"
    assert sheet.unknown_keys == ()


def test_sheet_without_custom_size() -> None:
    sheet = sch.read_schematic(schdoc(["|RECORD=31|CUSTOMX=10|CUSTOMY=20"])).sheet
    assert sheet is not None and sheet.custom_size is None and not sheet.portrait


def test_component_attributes() -> None:
    document = _read(
        "|RECORD=1|LIBREFERENCE=Opamp|DESIGNITEMID=OPA|SOURCELIBRARYNAME=a.SchLib|LOCATION.X=100|LOCATION.Y=200"
        "|ORIENTATION=1|ISMIRRORED=T|UNIQUEID=ABCDEFGH|PARTCOUNT=3|CURRENTPARTID=2|DISPLAYMODECOUNT=2|DISPLAYMODE=1"
        "|OWNERPARTID=-1|COMPONENTDESCRIPTION=Dual"
    )
    component = document.records[1]
    assert isinstance(component, sch.Component)
    assert (component.lib_reference, component.design_item_id, component.source_library) == (
        "Opamp",
        "OPA",
        "a.SchLib",
    )
    assert component.location == (L(100), L(200))
    assert (component.orientation, component.mirrored, component.unique_id) == (1, True, "ABCDEFGH")
    assert (component.part_count, component.current_part) == (2, 2)
    assert (component.display_mode_count, component.display_mode) == (2, 1)
    assert component.description == "Dual"
    assert component.owner_part == -1


def test_component_defaults() -> None:
    component = _read("|RECORD=1").records[1]
    assert isinstance(component, sch.Component)
    assert (component.part_count, component.current_part, component.display_mode_count) == (1, 1, 1)
    assert component.display_mode == 0
    one = _read("|RECORD=1|PARTCOUNT=1").records[1]
    assert isinstance(one, sch.Component) and one.part_count == 1


def test_text_pin_attributes() -> None:
    document = _read(
        "|RECORD=1",
        "|RECORD=2|OWNERINDEX=1|OWNERPARTID=1|NAME=IN|DESIGNATOR=1|ELECTRICAL=4|PINCONGLOMERATE=62"
        "|PINLENGTH=20|LOCATION.X=-30|LOCATION.Y=10|FORMALTYPE=1|SYMBOL_INNEREDGE=3|SYMBOL_OUTEREDGE=1",
    )
    pin = document.records[2]
    assert isinstance(pin, sch.Pin)
    assert (pin.name, pin.designator, pin.electrical, pin.direction) == ("IN", "1", 4, 2)
    assert (pin.hidden, pin.name_shown, pin.designator_shown) == (True, True, True)
    assert pin.location == (L(-30), L(10))
    assert pin.length == L(20)
    assert pin.hot_end == (L(-50), L(10))
    assert (pin.inner_edge, pin.outer_edge, pin.formal_type) == (3, 1, 1)
    assert pin.binary is False and pin.strings_read == 0 and pin.tail == b""


def test_binary_pin_in_a_schematic_document() -> None:
    document = _read("|RECORD=1", (1, pin_payload()))
    pin = document.records[2]
    assert isinstance(pin, sch.Pin) and pin.binary
    assert pin.owner is None  # a binary pin carries no OWNERINDEX: in a document it stays at the sheet level


def test_pin_hot_end_in_every_direction() -> None:
    for conglomerate, end in ((0, (L(15), L(5))), (1, (L(5), L(15))), (2, (L(-5), L(5))), (3, (L(5), L(-5)))):
        pin = _read(
            f"|RECORD=2|PINCONGLOMERATE={conglomerate}|PINLENGTH=10|LOCATION.X=5|LOCATION.Y=5"
        ).records[1]
        assert isinstance(pin, sch.Pin)
        assert pin.hot_end == end


def test_designator_and_parameter() -> None:
    document = _read(
        "|RECORD=1",
        "|RECORD=34|OWNERINDEX=1|OWNERPARTID=-1|NAME=Designator|TEXT=U1|LOCATION.X=1|LOCATION.Y=2|FONTID=1",
        "|RECORD=41|OWNERINDEX=1|OWNERPARTID=-1|NAME=Comment|TEXT==Value|ISHIDDEN=T|SHOWNAME=T",
    )
    designator, parameter = document.records[2], document.records[3]
    assert isinstance(designator, sch.Designator) and designator.text == "U1" and designator.font_id == 1
    assert isinstance(parameter, sch.Parameter)
    assert (parameter.name, parameter.text, parameter.hidden, parameter.show_name) == (
        "Comment",
        "=Value",
        True,
        True,
    )


def test_implementation_chain() -> None:
    document = _read(
        "|RECORD=1",
        "|RECORD=44|OWNERINDEX=1",
        "|RECORD=45|OWNERINDEX=2|MODELNAME=SOT23|MODELTYPE=PCBLIB|DATAFILECOUNT=1|MODELDATAFILEENTITY0=SOT23"
        "|MODELDATAFILEKIND0=PCBLIB|MODELDATAFILE0=x.PcbLib|ISCURRENT=T",
        "|RECORD=46|OWNERINDEX=3",
        "|RECORD=47|OWNERINDEX=4|DESINTF=1|DESIMPCOUNT=2|DESIMP0=1|DESIMP1=3",
        "|RECORD=48|OWNERINDEX=3",
    )
    kinds = [type(record).__name__ for record in document.records[2:]]
    assert kinds == [
        "ImplementationList",
        "Implementation",
        "MapDefinerList",
        "MapDefiner",
        "ImplementationParameters",
    ]
    implementation = document.records[3]
    assert isinstance(implementation, sch.Implementation)
    assert (implementation.model_name, implementation.model_type, implementation.is_current) == (
        "SOT23",
        "PCBLIB",
        True,
    )
    assert implementation.data_files == (DataFile(0, "SOT23", "PCBLIB", "x.PcbLib"),)
    definer = document.records[5]
    assert isinstance(definer, sch.MapDefiner)
    assert (definer.interface, definer.implementations) == ("1", ("1", "3"))


def test_template_and_image() -> None:
    document = _read(
        "|RECORD=39|ISNOTACCESIBLE=T|FILENAME=C:\\templates\\A4.SchDot",
        "|RECORD=30|EMBEDIMAGE=T|FILENAME=logo.bmp|LOCATION.X=1|LOCATION.Y=2|CORNER.X=30|CORNER.Y=40|KEEPASPECT=T",
    )
    template, image = document.records[1], document.records[2]
    assert isinstance(template, sch.Template) and template.file_name == "C:\\templates\\A4.SchDot"
    assert isinstance(image, sch.Image)
    assert (image.file_name, image.embedded, image.keep_aspect) == ("logo.bmp", True, True)
    assert (image.location, image.corner) == ((L(1), L(2)), (L(30), L(40)))


def test_sheet_level_wire_value_that_is_not_an_integer() -> None:
    issues: list[Issue] = []
    wire = _read("|RECORD=27|LOCATIONCOUNT=two", issues=issues).records[1]
    assert isinstance(wire, sch.Wire)
    assert [(issue.code, issue.where) for issue in issues] == [
        ("altium.sch.bad-value", "FileHeader/record 2")
    ]
    assert "LOCATIONCOUNT" in issues[0].message and "Wire" in issues[0].message
    assert wire.points == ()
    assert "LOCATIONCOUNT" in wire.unknown_keys


def test_parameter_bad_orientation_is_unknown() -> None:
    issues: list[Issue] = []
    parameter = _read("|RECORD=41|ORIENTATION=7", issues=issues).records[1]
    assert isinstance(parameter, sch.Parameter)
    assert parameter.unknown_keys == ("ORIENTATION",)
    assert [issue.code for issue in issues] == ["altium.sch.bad-value"]


# --- part two: connectivity and hierarchy -----------------------------------------------------------------


def test_wire_with_an_unknown_key() -> None:
    text = b"|RECORD=27|OWNERPARTID=-1|LINEWIDTH=1|COLOR=8388608|LOCATIONCOUNT=2|X1=10|Y1=20|X2=30|Y2=20"
    text += b"|FUTUREKEY=7"
    wire = _read(text).records[1]
    assert isinstance(wire, sch.Wire)
    assert wire.points == ((L(10), L(20)), (L(30), L(20)))
    assert wire.color == Color(0, 0, 128)
    assert wire.unknown_keys == ("FUTUREKEY",)
    assert wire.props is not None and wire.props.to_bytes() == text


def test_bus_and_bus_entry_and_junction() -> None:
    document = _read(
        "|RECORD=26|LOCATIONCOUNT=2|X1=0|Y1=0|X2=100|Y2=0",
        "|RECORD=37|LOCATION.X=10|LOCATION.Y=0|CORNER.X=20|CORNER.Y=10",
        "|RECORD=29|LOCATION.X=5|LOCATION.Y=6|LOCKED=T",
    )
    bus, entry, junction = document.records[1:4]
    assert isinstance(bus, sch.Bus) and len(bus.points) == 2
    assert isinstance(entry, sch.BusEntry) and entry.corner == (L(20), L(10))
    assert isinstance(junction, sch.Junction) and junction.location == (L(5), L(6)) and junction.locked
    assert document.buses() == (bus,) and document.junctions() == (junction,)


def test_net_label_power_port_and_port() -> None:
    document = _read(
        "|RECORD=25|LOCATION.X=10|LOCATION.Y=20|TEXT=SDA|ORIENTATION=1",
        "|RECORD=17|LOCATION.X=1|LOCATION.Y=2|STYLE=4|ORIENTATION=3|TEXT=GND|SHOWNETNAME=T",
        "|RECORD=18|LOCATION.X=1|LOCATION.Y=2|NAME=CLK|WIDTH=50|HEIGHT=10|IOTYPE=3|HARNESSTYPE=Bus4|UNIQUEID=QWERTYUI",
    )
    label, power, port = document.records[1:4]
    assert isinstance(label, sch.NetLabel) and (label.text, label.location, label.orientation) == (
        "SDA",
        (L(10), L(20)),
        1,
    )
    assert isinstance(power, sch.PowerPort)
    assert (power.text, power.style, power.orientation, power.show_net_name) == ("GND", 4, 3, True)
    assert isinstance(port, sch.Port)
    assert (port.name, port.width, port.height, port.io_type) == ("CLK", L(50), L(10), 3)
    assert (port.harness_type, port.unique_id) == ("Bus4", "QWERTYUI")
    assert (
        document.net_labels() == (label,)
        and document.power_ports() == (power,)
        and document.ports() == (port,)
    )


def test_no_erc() -> None:
    no_erc = _read("|RECORD=22|LOCATION.X=3|LOCATION.Y=4|ISACTIVE=T|SUPPRESSALL=T|SYMBOL=Thin Cross").records[
        1
    ]
    assert isinstance(no_erc, sch.NoErc)
    assert (no_erc.location, no_erc.active, no_erc.suppress_all, no_erc.symbol) == (
        (L(3), L(4)),
        True,
        True,
        "Thin Cross",
    )


def test_sheet_symbol_and_entry() -> None:
    document = _read(
        "|RECORD=15|LOCATION.X=100|LOCATION.Y=500|XSIZE=150|YSIZE=80|ISSOLID=T|UNIQUEID=AAAAAAAA",
        "|RECORD=16|OWNERINDEX=1|SIDE=1|DISTANCEFROMTOP=2|NAME=SPI|IOTYPE=2|HARNESSTYPE=SpiBus",
        "|RECORD=32|OWNERINDEX=1|TEXT=Flash",
        "|RECORD=33|OWNERINDEX=1|TEXT=..\\..\\x.SchDoc",
    )
    symbol, entry, name, file_name = document.records[1:5]
    assert isinstance(symbol, sch.SheetSymbol)
    assert (symbol.location, symbol.x_size, symbol.y_size, symbol.unique_id) == (
        (L(100), L(500)),
        L(150),
        L(80),
        "AAAAAAAA",
    )
    assert isinstance(entry, sch.SheetEntry)
    assert (entry.name, entry.side, entry.distance, entry.io_type, entry.harness_type) == (
        "SPI",
        1,
        L(20),
        2,
        "SpiBus",
    )
    assert isinstance(name, sch.SheetName) and name.text == "Flash"
    assert isinstance(file_name, sch.SheetFileName) and file_name.text == "..\\..\\x.SchDoc"
    assert document.sheet_symbols() == (symbol,)


def test_sheet_entry_without_harness() -> None:
    entry = _read("|RECORD=16|NAME=A").records[1]
    assert isinstance(entry, sch.SheetEntry) and entry.harness_type == "" and entry.side == 0


def test_harness_connector_side_key() -> None:
    document = _read(
        "|RECORD=215|HARNESSCONNECTORSIDE=1|PRIMARYCONNECTIONPOSITION=3|XSIZE=50|YSIZE=40",
        "|RECORD=215|SIDE=1",
    )
    first, second = document.records[1:3]
    assert isinstance(first, sch.HarnessConnector) and isinstance(second, sch.HarnessConnector)
    assert first.side == 1 and second.side == 1
    assert first.unknown_keys == () and second.unknown_keys == ()
    assert first.primary_position == L(3)
    assert (first.x_size, first.y_size) == (L(50), L(40))


def test_harness_entry_type_and_signal_harness() -> None:
    document = _read(
        "|RECORD=216|NAME=SCK|SIDE=1|DISTANCEFROMTOP=1",
        "|RECORD=217|TEXT=SpiBus|LOCATION.X=1|LOCATION.Y=2",
        "|RECORD=218|LOCATIONCOUNT=2|X1=1|Y1=1|X2=5|Y2=1",
    )
    entry, harness_type, line = document.records[1:4]
    assert isinstance(entry, sch.HarnessEntry) and (entry.name, entry.side, entry.distance) == (
        "SCK",
        1,
        L(10),
    )
    assert isinstance(harness_type, sch.HarnessType) and harness_type.text == "SpiBus"
    assert isinstance(line, sch.SignalHarness) and line.points == ((L(1), L(1)), (L(5), L(1)))


# --- part three: graphics ---------------------------------------------------------------------------------


def test_graphics_classes() -> None:
    document = _read(
        "|RECORD=3|SYMBOL=4|SCALEFACTOR=6",
        "|RECORD=4|TEXT=Note|FONTID=2|ORIENTATION=2|LOCATION.X=1|LOCATION.Y=1",
        "|RECORD=5|LOCATIONCOUNT=4|X1=0|Y1=0|X2=1|Y2=1|X3=2|Y3=1|X4=3|Y4=0",
        "|RECORD=6|LOCATIONCOUNT=2|X1=0|Y1=0|X2=1|Y2=1|STARTLINESHAPE=1",
        "|RECORD=7|LOCATIONCOUNT=3|X1=0|Y1=0|X2=1|Y2=0|X3=0|Y3=1|ISSOLID=T",
        "|RECORD=8|RADIUS=5|SECONDARYRADIUS=3",
        "|RECORD=9|RADIUS=5|STARTANGLE=10|ENDANGLE=20",
        "|RECORD=10|CORNERXRADIUS=2|CORNERYRADIUS=3|CORNER.X=10|CORNER.Y=10",
        "|RECORD=11|RADIUS=5|SECONDARYRADIUS=2|STARTANGLE=0|ENDANGLE=90.25",
        "|RECORD=12|RADIUS=5|RADIUS_FRAC=50000",
        "|RECORD=13|CORNER.X=10|CORNER.Y=0",
        "|RECORD=14|CORNER.X=10|CORNER.Y=5|ISSOLID=T|TRANSPARENT=T",
        "|RECORD=28|TEXT=Box|CORNER.X=10|CORNER.Y=5|WORDWRAP=T",
        "|RECORD=43|NAME=Parameter Set|ORIENTATION=1",
        "|RECORD=226|TEXT=Docs|URL=https://example.invalid/",
    )
    names = [type(record).__name__ for record in document.records[1:]]
    assert names == [
        "IeeeSymbol",
        "Label",
        "Bezier",
        "Polyline",
        "Polygon",
        "Ellipse",
        "PieChart",
        "RoundRectangle",
        "EllipticalArc",
        "Arc",
        "Line",
        "Rectangle",
        "TextFrame",
        "WarningSign",
        "Hyperlink",
    ]
    label = document.records[2]
    assert isinstance(label, sch.Label) and (label.text, label.font_id, label.orientation) == ("Note", 2, 2)
    assert all(record.unknown_keys == () for record in document.records)
    arc = document.records[10]
    assert isinstance(arc, sch.Arc) and arc.radius == L(5, 50_000)
    elliptical = document.records[9]
    assert isinstance(elliptical, sch.EllipticalArc) and elliptical.end_angle == 90_250_000
    hyperlink = document.records[15]
    assert isinstance(hyperlink, sch.Hyperlink) and hyperlink.url == "https://example.invalid/"


def test_unknown_record_id() -> None:
    issues: list[Issue] = []
    document = _read(
        "|RECORD=27|LOCATIONCOUNT=0",
        "|RECORD=209|TEXT=a|AUTHOR=b",
        "|RECORD=209|TEXT=c",
        "|RECORD=25|TEXT=N",
        issues=issues,
    )
    unknown = [record for record in document.records if isinstance(record, sch.UnknownRecord)]
    assert [record.record_id for record in unknown] == [209, 209]
    assert unknown[0].props is not None and unknown[0].props.to_bytes() == b"|RECORD=209|TEXT=a|AUTHOR=b"
    assert [issue.code for issue in issues] == ["altium.sch.unknown-record"]
    assert "209" in issues[0].message and "2 record(s)" in issues[0].message
    assert isinstance(document.records[4], sch.NetLabel) and document.records[4].ref == sch.RecordRef(
        "main", 4
    )


def test_record_without_record_id_is_malformed() -> None:
    issues: list[Issue] = []
    record = _read("|TEXT=x", issues=issues).records[1]
    assert isinstance(record, sch.UnknownRecord) and record.record_id is None
    assert [issue.code for issue in issues] == ["altium.sch.malformed-record"]


def test_record_types_table() -> None:
    assert len(sch.RECORD_TYPES) == 43
    assert sch.RECORD_TYPES[27] is sch.Wire and sch.RECORD_TYPES[226] is sch.Hyperlink
    assert all(cls.RECORD_ID == record_id for record_id, cls in sch.RECORD_TYPES.items())

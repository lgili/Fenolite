# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The records of an ASCII schematic, in their fixed order (capability altium-schematic-writer).

Record 0 is the sheet. On the top sheet of a hierarchical project (change c0037) the sheet symbols follow,
each with its sheet entries, its name and its file name. Then, per component in component-path order and
per part of its symbol: the
component record of that part, every rectangle and pin of the symbol (with their ``OWNERPARTID``), its
designator, its comment and, when it has a footprint, the footprint chain 44 → 45 → 46, 48. Then, per
component, part and pin drawn on that part, the pin's wire stub followed by its net label or power port.
Before these pin stubs come the labelled wires of the sheet entries (top sheet) and the ports of a module
sheet, each followed by its labelled wire or the wires of its harness block.
Then come the No ERC directives of the pins marked as intentionally unconnected (change c0036), and last
the net class directives (change c0048), each with its ``ClassName`` parameter, so a design without marks
and without a net class keeps its bytes.
Bodies come from the library symbol, placed with its origin at the component's location (change c0034).
Every record and key is a fact of ``docs/formats/altium/schematic-ascii.md``; the key order
and the values marked as choices are Fenolite's.
"""

from __future__ import annotations

from fenolite.backends.altium.ascii import Field, coord_fields, encode_records, to_units
from fenolite.backends.altium.layout import (
    COMMENT_DROP,
    DESIGNATOR_RISE,
    PORT_HEIGHT,
    SHEET_NAME_RISE,
    ClassMark,
    HarnessBlock,
    NoConnectMark,
    PlacedEntry,
    PlacedPart,
    PlacedPort,
    PlacedSymbol,
    SheetPlan,
    Stub,
)

FONT_NAME = "Times New Roman"
"""The sheet's one font (a Fenolite choice)."""
FONT_SIZE = 10
COMPONENT_COLOR = "128"
COMPONENT_FILL = "11599871"
TEXT_COLOR = "8388608"
SHEET_COLOR = "16317695"
PORT_STYLES = {"bar": "2", "ground": "4"}
PORT_ORIENTATION = {"left": "2", "right": "0", "up": "1", "down": "3"}
"""A port points away from the body: leftwards on a left pin, rightwards on a right pin, up or down on a
top or bottom pin."""
SYMBOL_COLOR = "128"
"""The border of a sheet symbol, a sheet entry and a port, and the text of the last two (change c0037)."""
SYMBOL_FILL = "8454016"
"""The fill of a sheet symbol."""
ENTRY_FILL = "8454143"
"""The fill of a sheet entry and of a port."""
RIGHT_SIDE = "1"
"""``SIDE`` of a sheet entry on the right side of its symbol."""
ENTRY_ARROW = "Block & Triangle"
CONNECTOR_COLOR = "13213327"
"""The border of a harness connector."""
CONNECTOR_FILL = "16511725"
HARNESS_ENTRY_COLOR = "7354880"
"""The border and the text of a harness entry; its fill is ``ENTRY_FILL``."""
HARNESS_LINE_COLOR = "15187117"
VERTICAL_TEXT = "1"
"""``ORIENTATION`` of a net label that runs upwards along a vertical stub."""
NO_ERC_COLOR = "255"
"""Red in the page's colour encoding (a Fenolite choice)."""
NO_ERC_SYMBOL = "Thin Cross"
DIRECTIVE_COLOR = "255"
"""The colour of a Parameter Set directive, as a saved sheet holds it (change c0048)."""
DIRECTIVE_NAME = "Parameter Set"
DIRECTIVE_DOWN = "3"
"""``ORIENTATION`` of a directive on a horizontal stub: downwards, away from the label text above the wire."""
CLASS_PARAMETER = "ClassName"
"""The parameter of a directive that puts its net in a net class."""

Record = list[Field]


def sheet_record(plan: SheetPlan) -> Record:
    """``RECORD=31``: one font, border and grids, and the ISO style or the custom size."""
    record: Record = [
        ("RECORD", "31"),
        ("FONTIDCOUNT", "1"),
        ("SIZE1", str(FONT_SIZE)),
        ("FONTNAME1", FONT_NAME),
        ("SYSTEMFONT", "1"),
        ("BORDERON", "T"),
        ("SNAPGRIDON", "T"),
        ("SNAPGRIDSIZE", "10"),
        ("VISIBLEGRIDON", "T"),
        ("VISIBLEGRIDSIZE", "10"),
        ("HOTSPOTGRIDON", "T"),
        ("HOTSPOTGRIDSIZE", "4"),
        ("DISPLAY_UNIT", "4"),
        ("AREACOLOR", SHEET_COLOR),
    ]
    size = plan.size
    if size.style is not None:
        record.append(("SHEETSTYLE", str(size.style)))
    else:
        record += [
            ("USECUSTOMSHEET", "T"),
            ("CUSTOMX", str(to_units(size.width))),
            ("CUSTOMY", str(to_units(size.height))),
        ]
    return record


class _Writer:
    """Collects records and numbers them from 0, so children can name their owner."""

    def __init__(self, plan: SheetPlan) -> None:
        self.plan = plan
        self.height = plan.size.height
        self.records: list[Record] = []

    def add(self, record: Record) -> int:
        self.records.append(record)
        return len(self.records) - 1

    def at(self, name: str, x: int, y: int) -> tuple[Field, Field]:
        """A point of the layout frame (Y downwards) as fields of the file frame (Y upwards)."""
        return coord_fields(name, x, self.height - y)

    def component(self, placed: PlacedPart) -> None:
        spec, body = placed.spec, placed.spec.body
        owner = self.add(
            [
                ("RECORD", "1"),
                ("LIBREFERENCE", spec.symbol),
                ("DESIGNITEMID", spec.symbol),
                ("SOURCELIBRARYNAME", spec.library),
                ("PARTCOUNT", str(body.parts + 1)),
                ("DISPLAYMODECOUNT", "1"),
                ("CURRENTPARTID", str(placed.part)),
                ("OWNERPARTID", "-1"),
                *self.at("LOCATION", placed.x, placed.y),
                ("UNIQUEID", spec.part_id(placed.part)),
                ("COLOR", COMPONENT_COLOR),
                ("AREACOLOR", COMPONENT_FILL),
            ]
        )
        for rect in body.rectangles:
            self.add(
                [
                    ("RECORD", "14"),
                    ("OWNERINDEX", str(owner)),
                    ("OWNERPARTID", str(rect.part)),
                    *self.at("LOCATION", *placed.at(rect.x0, rect.y0)),
                    *self.at("CORNER", *placed.at(rect.x1, rect.y1)),
                    ("LINEWIDTH", "1"),
                    ("COLOR", COMPONENT_COLOR),
                    ("AREACOLOR", COMPONENT_FILL),
                    ("ISSOLID", "T"),
                ]
            )
        for pin in body.pins:
            edges: list[Field] = []
            if pin.inner_edge:
                edges.append(("SYMBOL_INNEREDGE", str(pin.inner_edge)))
            if pin.outer_edge:
                edges.append(("SYMBOL_OUTEREDGE", str(pin.outer_edge)))
            self.add(
                [
                    ("RECORD", "2"),
                    ("OWNERINDEX", str(owner)),
                    ("OWNERPARTID", str(pin.part)),
                    *edges,
                    ("FORMALTYPE", "1"),
                    ("ELECTRICAL", str(pin.electrical)),
                    ("PINCONGLOMERATE", str(pin.conglomerate)),
                    ("PINLENGTH", str(to_units(pin.length))),
                    *self.at("LOCATION", *placed.at(pin.x, pin.y)),
                    ("NAME", pin.name),
                    ("DESIGNATOR", pin.designator),
                ]
            )
        first = body.rectangle(1)
        left, top = placed.at(first.x0, first.y1)
        bottom = placed.at(first.x0, first.y0)[1]
        for record, name, text, ty in (
            ("34", "Designator", spec.ref, top - DESIGNATOR_RISE),
            ("41", "Comment", spec.comment, bottom + COMMENT_DROP),
        ):
            self.add(
                [
                    ("RECORD", record),
                    ("OWNERINDEX", str(owner)),
                    ("OWNERPARTID", "-1"),
                    ("NAME", name),
                    ("TEXT", text),
                    *self.at("LOCATION", left, ty),
                    ("FONTID", "1"),
                    ("COLOR", TEXT_COLOR),
                ]
            )
        if spec.footprint is not None:
            library, footprint = spec.footprint
            listing = self.add([("RECORD", "44"), ("OWNERINDEX", str(owner))])
            model = self.add(
                [
                    ("RECORD", "45"),
                    ("OWNERINDEX", str(listing)),
                    ("MODELNAME", footprint),
                    ("MODELTYPE", "PCBLIB"),
                    ("DATAFILECOUNT", "1"),
                    ("MODELDATAFILEENTITY0", footprint),
                    ("MODELDATAFILEKIND0", "PCBLIB"),
                    ("MODELDATAFILE0", library),
                    ("ISCURRENT", "T"),
                ]
            )
            self.add([("RECORD", "46"), ("OWNERINDEX", str(model))])
            self.add([("RECORD", "48"), ("OWNERINDEX", str(model))])

    def sheet_symbol(self, symbol: PlacedSymbol) -> None:
        """Records 15, 16 per entry, 32 and 33 of one sheet symbol (change c0037, "Sheet symbols and sheet
        entries"): the symbol's location is its top-left corner."""
        spec = symbol.spec
        owner = self.add(
            [
                ("RECORD", "15"),
                ("OWNERPARTID", "-1"),
                *self.at("LOCATION", symbol.x, symbol.y),
                ("XSIZE", str(to_units(symbol.width))),
                ("YSIZE", str(to_units(symbol.height))),
                ("COLOR", SYMBOL_COLOR),
                ("AREACOLOR", SYMBOL_FILL),
                ("ISSOLID", "T"),
                ("UNIQUEID", spec.unique_id),
                ("SYMBOLTYPE", "Normal"),
            ]
        )
        for entry in symbol.entries:
            crossing = entry.crossing
            self.add(
                [
                    ("RECORD", "16"),
                    ("OWNERINDEX", str(owner)),
                    ("OWNERPARTID", "-1"),
                    *((("SIDE", RIGHT_SIDE),) if entry.side == "right" else ()),
                    ("DISTANCEFROMTOP", str(entry.slot)),
                    ("COLOR", SYMBOL_COLOR),
                    ("AREACOLOR", ENTRY_FILL),
                    ("TEXTCOLOR", SYMBOL_COLOR),
                    ("TEXTFONTID", "1"),
                    ("TEXTSTYLE", "Full"),
                    ("NAME", crossing.name),
                    *((("HARNESSTYPE", crossing.name),) if crossing.harness else ()),
                    ("ARROWKIND", ENTRY_ARROW),
                ]
            )
        for record, text, rise in (("32", spec.module, SHEET_NAME_RISE), ("33", spec.file, 0)):
            self.add(
                [
                    ("RECORD", record),
                    ("OWNERINDEX", str(owner)),
                    ("OWNERPARTID", "-1"),
                    *self.at("LOCATION", symbol.x, symbol.y - rise),
                    ("COLOR", TEXT_COLOR),
                    ("FONTID", "1"),
                    ("TEXT", text),
                ]
            )

    def port(self, port: PlacedPort) -> None:
        """Record 18 (change c0037, "Ports on module sheets"): the location is the port's left end."""
        crossing = port.crossing
        self.add(
            [
                ("RECORD", "18"),
                ("OWNERPARTID", "-1"),
                ("WIDTH", str(to_units(port.width))),
                *self.at("LOCATION", port.x, port.y),
                ("COLOR", SYMBOL_COLOR),
                ("FONTID", "1"),
                ("AREACOLOR", ENTRY_FILL),
                ("TEXTCOLOR", SYMBOL_COLOR),
                ("NAME", crossing.name),
                *((("HARNESSTYPE", crossing.name),) if crossing.harness else ()),
                ("UNIQUEID", crossing.port_id),
                ("HEIGHT", str(to_units(PORT_HEIGHT))),
            ]
        )

    def links(self, item: PlacedPort | PlacedEntry) -> None:
        """The labelled wires of a port or sheet entry: its own stub, or those of its harness block."""
        if item.stub is not None:
            self.stub(item.stub)
        if item.block is not None:
            for stub in item.block.stubs:
                self.stub(stub)

    def stub(self, stub: Stub) -> None:
        (x1, y1), (x2, y2) = stub.start, stub.end
        self.add(
            [
                ("RECORD", "27"),
                ("OWNERPARTID", "-1"),
                ("LINEWIDTH", "1"),
                ("COLOR", TEXT_COLOR),
                ("LOCATIONCOUNT", "2"),
                ("X1", str(to_units(x1))),
                ("Y1", str(to_units(self.height - y1))),
                ("X2", str(to_units(x2))),
                ("Y2", str(to_units(self.height - y2))),
            ]
        )
        mx, my = stub.mark
        net = stub.net
        if net.kind == "label":
            self.add(
                [
                    ("RECORD", "25"),
                    ("OWNERPARTID", "-1"),
                    *self.at("LOCATION", mx, my),
                    *((("ORIENTATION", VERTICAL_TEXT),) if stub.vertical else ()),
                    ("TEXT", net.net),
                    ("FONTID", "1"),
                    ("COLOR", TEXT_COLOR),
                ]
            )
        else:
            self.add(
                [
                    ("RECORD", "17"),
                    ("OWNERPARTID", "-1"),
                    *self.at("LOCATION", mx, my),
                    ("STYLE", PORT_STYLES[net.style or "bar"]),
                    ("ORIENTATION", PORT_ORIENTATION[stub.side]),
                    ("SHOWNETNAME", "T"),
                    ("TEXT", net.net),
                    ("FONTID", "1"),
                    ("COLOR", TEXT_COLOR),
                ]
            )

    def no_connect(self, mark: NoConnectMark) -> None:
        """``RECORD=22``: a No ERC directive in the "Suppress All Violations" mode at a pin's hot end."""
        self.add(
            [
                ("RECORD", "22"),
                ("OWNERPARTID", "-1"),
                *self.at("LOCATION", *mark.at),
                ("COLOR", NO_ERC_COLOR),
                ("ISACTIVE", "T"),
                ("SUPPRESSALL", "T"),
                ("SYMBOL", NO_ERC_SYMBOL),
            ]
        )

    def class_mark(self, mark: ClassMark) -> None:
        """Records 43 and 41 (change c0048, "Net class directives on the sheet"): a Parameter Set directive
        inside a stub of the net, and its hidden ``ClassName`` parameter holding the class name."""
        owner = self.add(
            [
                ("RECORD", "43"),
                ("OWNERPARTID", "-1"),
                *self.at("LOCATION", *mark.at),
                ("COLOR", DIRECTIVE_COLOR),
                *(() if mark.vertical else (("ORIENTATION", DIRECTIVE_DOWN),)),
                ("NAME", DIRECTIVE_NAME),
                ("UNIQUEID", mark.unique_id),
            ]
        )
        self.add(
            [
                ("RECORD", "41"),
                ("OWNERINDEX", str(owner)),
                ("OWNERPARTID", "-1"),
                *self.at("LOCATION", *mark.at),
                ("COLOR", TEXT_COLOR),
                ("FONTID", "1"),
                ("ISHIDDEN", "T"),
                ("TEXT", mark.name),
                ("NAME", CLASS_PARAMETER),
                ("UNIQUEID", mark.parameter_id),
            ]
        )


def schdoc_records(plan: SheetPlan) -> list[Record]:
    """Every record after the header, in file order."""
    writer = _Writer(plan)
    writer.add(sheet_record(plan))
    for symbol in plan.symbols:
        writer.sheet_symbol(symbol)
    for placed in plan.parts:
        writer.component(placed)
    for symbol in plan.symbols:
        for entry in symbol.entries:
            writer.links(entry)
    for port in plan.ports:
        writer.port(port)
        writer.links(port)
    for stub in plan.stubs:
        writer.stub(stub)
    for mark in plan.no_connects:
        writer.no_connect(mark)
    for item in plan.class_marks:
        writer.class_mark(item)
    return writer.records


def block_records(block: HarnessBlock, index: int, height: int) -> list[Record]:
    """The records of one harness block, whose connector is record ``index`` of the ``Additional`` list
    (counted from 0 after the header), on a sheet ``height`` mil high: the connector (215), its entries
    (216), its type (217) and the signal harness line (218). Entries and type name their connector through
    ``OWNERINDEX``, which is left out when it is 0 (``docs/formats/altium/schematic-binary.md``,
    "Additional stream and harness records")."""
    owner: tuple[Field, ...] = (("OWNERINDEX", str(index)),) if index else ()
    found: list[Record] = [
        [
            ("RECORD", "215"),
            ("OWNERPARTID", "-1"),
            *coord_fields("LOCATION", block.x, height - block.y),
            ("XSIZE", str(to_units(block.width))),
            ("YSIZE", str(to_units(block.height))),
            ("LINEWIDTH", "1"),
            ("COLOR", CONNECTOR_COLOR),
            ("AREACOLOR", CONNECTOR_FILL),
            ("PRIMARYCONNECTIONPOSITION", str(to_units(block.position))),
        ]
    ]
    for k, (entry, _net) in enumerate(block.entries, start=1):
        found.append(
            [
                ("RECORD", "216"),
                *owner,
                ("OWNERINDEXADDITIONALLIST", "T"),
                ("OWNERPARTID", "-1"),
                ("SIDE", RIGHT_SIDE),
                ("DISTANCEFROMTOP", str(k)),
                ("COLOR", HARNESS_ENTRY_COLOR),
                ("AREACOLOR", ENTRY_FILL),
                ("TEXTCOLOR", HARNESS_ENTRY_COLOR),
                ("TEXTFONTID", "1"),
                ("TEXTSTYLE", "Full"),
                ("NAME", entry),
            ]
        )
    found.append(
        [
            ("RECORD", "217"),
            *owner,
            ("OWNERINDEXADDITIONALLIST", "T"),
            ("OWNERPARTID", "-1"),
            *coord_fields("LOCATION", block.x, height - block.y),
            ("COLOR", TEXT_COLOR),
            ("FONTID", "1"),
            ("TEXT", block.name),
        ]
    )
    found.append(line_record(*block.line, height))
    return found


def line_record(start: tuple[int, int], end: tuple[int, int], height: int) -> Record:
    """``RECORD=218``: a signal harness line of two points, on a sheet ``height`` mil high."""
    (x1, y1), (x2, y2) = start, end
    return [
        ("RECORD", "218"),
        ("OWNERPARTID", "-1"),
        ("LINEWIDTH", "2"),
        ("COLOR", HARNESS_LINE_COLOR),
        ("LOCATIONCOUNT", "2"),
        ("X1", str(to_units(x1))),
        ("Y1", str(to_units(height - y1))),
        ("X2", str(to_units(x2))),
        ("Y2", str(to_units(height - y2))),
    ]


def additional_records(plan: SheetPlan) -> list[Record]:
    """The records of the ``Additional`` stream after its header (change c0037, "Harness records"): per
    harness block of ``plan``, in block order, the connector, its entries in code-point order of their
    names, the type and the line; then one line per pair of sheet entries that a signal harness line joins
    directly (``plan.lines``). A sheet without a block and without a line gives no record."""
    found: list[Record] = []
    for block in plan.harnesses:
        found += block_records(block, len(found), plan.size.height)
    for start, end in plan.lines:
        found.append(line_record(start, end, plan.size.height))
    return found


def write_schdoc(plan: SheetPlan) -> bytes:
    """The bytes of the ASCII schematic of ``plan``. A plan with a harness block is refused: the place of
    harness records in the ASCII form is not documented (``hierarchy.plan_sheets`` makes none for it)."""
    if plan.lines:
        raise ValueError("the ASCII form cannot carry a signal harness line: harness records are binary only")
    if plan.harnesses:
        names = ", ".join(sorted({block.name for block in plan.harnesses}))
        raise ValueError(f"the ASCII form cannot carry the harness {names}: harness records are binary only")
    return encode_records(schdoc_records(plan))


__all__ = [
    "FONT_NAME",
    "additional_records",
    "block_records",
    "line_record",
    "schdoc_records",
    "sheet_record",
    "write_schdoc",
]

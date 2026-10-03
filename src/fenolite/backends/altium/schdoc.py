# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The records of an ASCII schematic, in their fixed order (capability altium-schematic-writer).

Record 0 is the sheet. Then, per component in component-path order and per part of its symbol: the
component record of that part, every rectangle and pin of the symbol (with their ``OWNERPARTID``), its
designator, its comment and, when it has a footprint, the footprint chain 44 → 45 → 46, 48. Then, per
component, part and pin drawn on that part, the pin's wire stub followed by its net label or power port.
Last come the No ERC directives of the pins marked as intentionally unconnected (change c0036), so a
design without marks keeps its bytes.
Bodies come from the library symbol, placed with its origin at the component's location (change c0034).
Every record and key is a fact of ``docs/formats/altium/schematic-ascii.md``; the key order
and the values marked as choices are Fenolite's.
"""

from __future__ import annotations

from fenolite.backends.altium.ascii import Field, coord_fields, encode_records, to_units
from fenolite.backends.altium.layout import (
    COMMENT_DROP,
    DESIGNATOR_RISE,
    NoConnectMark,
    PlacedPart,
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
VERTICAL_TEXT = "1"
"""``ORIENTATION`` of a net label that runs upwards along a vertical stub."""
NO_ERC_COLOR = "255"
"""Red in the page's colour encoding (a Fenolite choice)."""
NO_ERC_SYMBOL = "Thin Cross"

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


def schdoc_records(plan: SheetPlan) -> list[Record]:
    """Every record after the header, in file order."""
    writer = _Writer(plan)
    writer.add(sheet_record(plan))
    for placed in plan.parts:
        writer.component(placed)
    for stub in plan.stubs:
        writer.stub(stub)
    for mark in plan.no_connects:
        writer.no_connect(mark)
    return writer.records


def write_schdoc(plan: SheetPlan) -> bytes:
    """The bytes of the ASCII schematic of ``plan``."""
    return encode_records(schdoc_records(plan))


__all__ = ["FONT_NAME", "schdoc_records", "sheet_record", "write_schdoc"]

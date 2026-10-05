# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reader of Altium schematic documents and templates (change c0040, capability ``altium-schematic-reader``).

``read_schematic(data)`` reads a ``.SchDoc`` or ``.SchDot`` in the binary or the ASCII form into a
``SchDocument`` of typed records with an owner tree; ``detect(data)`` tells the forms apart by content.
Nothing is lost: every record keeps its payload and property list, every stream the reader does not read is
kept as bytes, and ``encode_stream`` rebuilds each stream byte for byte. Lengths are exact ``SchLength``
counts of 1/100 000 of the 10-mil unit. The reader opens, resolves and decompresses nothing.

Facts: ``docs/formats/altium/schematic-records.md``, ``schematic-ascii.md``, ``schematic-binary.md`` and
``schematic-library.md``. The library reader is ``fenolite.backends.altium.read.schlib``.
"""

from __future__ import annotations

from fenolite.backends.altium.read.sch.document import (
    MAX_EMBEDDED,
    EmbeddedFile,
    Harness,
    SchDocument,
    check_identity,
    detect,
    encode_stream,
    read_schematic,
)
from fenolite.backends.altium.read.sch.issues import ISSUE_CODES
from fenolite.backends.altium.read.sch.props import DEFAULT_CODEPAGE, Prop, PropertyList
from fenolite.backends.altium.read.sch.records import (
    RECORD_TYPES,
    Arc,
    Bezier,
    Bus,
    BusEntry,
    Component,
    Designator,
    Ellipse,
    EllipticalArc,
    Font,
    HarnessConnector,
    HarnessEntry,
    HarnessType,
    Hyperlink,
    IeeeSymbol,
    Image,
    Implementation,
    ImplementationList,
    ImplementationParameters,
    Junction,
    Label,
    Line,
    MapDefiner,
    MapDefinerList,
    NetLabel,
    NoErc,
    Parameter,
    PieChart,
    Pin,
    Polygon,
    Polyline,
    Port,
    PowerPort,
    PropertyRecord,
    RecordRef,
    Rectangle,
    RoundRectangle,
    SchRecord,
    Sheet,
    SheetEntry,
    SheetFileName,
    SheetName,
    SheetSymbol,
    SignalHarness,
    Template,
    TextFrame,
    UnknownRecord,
    WarningSign,
    Wire,
)
from fenolite.backends.altium.read.sch.units import UNIT_NM, Color, SchLength
from fenolite.core.evidence import Evidence, Level

HYPOTHESES = (
    "H-A-RD-SCH-FRAME",
    "H-A-RD-SCH-IDENT",
    "H-A-RD-SCH-HEADER",
    "H-A-RD-SCH-CASE",
    "H-A-RD-SCH-TEXT",
    "H-A-RD-SCH-TEXT-2",
    "H-A-RD-SCH-OWNER",
    "H-A-RD-SCH-ADDOWNER",
    "H-A-RD-SCH-LIBOWNER",
    "H-A-RD-SCH-FRAC",
    "H-A-RD-SCH-PARTS",
    "H-A-RD-SCH-PIN",
    "H-A-RD-SCH-PINSIDE",
    "H-A-RD-SCH-STORAGE",
    "H-A-RD-SCH-ASCII",
    "H-A-RD-SCH-KICAD",
)
"""Every registered ``H-A-RD-SCH-*`` id (``docs/hypotheses.md``)."""
EVIDENCE = Evidence(Level.INFERRED, hypotheses=HYPOTHESES)
"""The lowest level among the registered rows: ``INFERRED`` while ``H-A-RD-SCH-ASCII`` and
``H-A-RD-SCH-PARTS`` stay so (``docs/evidence/altium-read-schematic.md``)."""

__all__ = [
    "DEFAULT_CODEPAGE",
    "EVIDENCE",
    "HYPOTHESES",
    "ISSUE_CODES",
    "MAX_EMBEDDED",
    "RECORD_TYPES",
    "UNIT_NM",
    "Arc",
    "Bezier",
    "Bus",
    "BusEntry",
    "Color",
    "Component",
    "Designator",
    "Ellipse",
    "EllipticalArc",
    "EmbeddedFile",
    "Font",
    "Harness",
    "HarnessConnector",
    "HarnessEntry",
    "HarnessType",
    "Hyperlink",
    "IeeeSymbol",
    "Image",
    "Implementation",
    "ImplementationList",
    "ImplementationParameters",
    "Junction",
    "Label",
    "Line",
    "MapDefiner",
    "MapDefinerList",
    "NetLabel",
    "NoErc",
    "Parameter",
    "PieChart",
    "Pin",
    "Polygon",
    "Polyline",
    "Port",
    "PowerPort",
    "Prop",
    "PropertyList",
    "PropertyRecord",
    "RecordRef",
    "Rectangle",
    "RoundRectangle",
    "SchDocument",
    "SchLength",
    "SchRecord",
    "Sheet",
    "SheetEntry",
    "SheetFileName",
    "SheetName",
    "SheetSymbol",
    "SignalHarness",
    "Template",
    "TextFrame",
    "UnknownRecord",
    "WarningSign",
    "Wire",
    "check_identity",
    "detect",
    "encode_stream",
    "read_schematic",
]

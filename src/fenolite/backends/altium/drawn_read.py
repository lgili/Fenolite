# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawn content of read Altium sheets (capability ``drawn-schematic``, "Drawn content of read Altium
sheets"; change c0470, design D1; ``docs/drawn-schematic.md``).

``extract`` turns the read documents of a project (the ``SheetInput`` list that ``adapter.netlist.resolve``
takes) into a ``DrawnSchematic``: each placed part a symbol pose, each wire, bus, bus entry, junction, net
label, port, power port, sheet symbol and No ERC marker its drawn item, and every other root record (harness
items, parameter sets, notes, texts, graphics, images, the sheet template) a typed opaque item that keeps its
record fields as ``|KEY=value`` lines, with a KiCad stand-in where KiCad has a like shape. Nothing here reads
a file.

Points: one Altium fraction unit is 127/50 nm (``schematic-records.md``); the drawn frame has Y down from the
top of the sheet's drawing area. A value that is not a whole number of nanometres is rounded to the nearest
and counted per sheet by ``altium.import.inexact``. Port scope follows ``altium-import`` ("Connectivity
within a sheet"): hierarchical ports under the hierarchical scope, global ones otherwise; net labels are
global under the global scope. Every format fact is ``INFERRED`` until the kit report (``EVIDENCE``).
"""

from __future__ import annotations

import dataclasses
import re
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import PureWindowsPath
from types import MappingProxyType
from typing import cast

import fenolite.backends.altium.drawn_carrier as drawn_carrier
import fenolite.backends.altium.drawn_symbols as drawn_symbols
from fenolite.backends.altium.adapter.connectivity import (
    SIDE_LEFT,
    SIDE_RIGHT,
    SIDE_TOP,
    VERTICAL_PORT_STYLES,
    Lines,
    connector_point,
    entry_point,
    harness_lines,
    on_segment,
    port_ends,
    pt,
    wire_lines,
)
from fenolite.backends.altium.adapter.netlist import Resolved, SheetInput, resolve
from fenolite.backends.altium.adapter.parts import part_groups
from fenolite.backends.altium.adapter.pins import pin_etype
from fenolite.backends.altium.read.sch import (
    Bus,
    BusEntry,
    Component,
    Designator,
    HarnessConnector,
    HarnessEntry,
    HarnessType,
    Junction,
    NetLabel,
    NoErc,
    Parameter,
    Pin,
    Port,
    PowerPort,
    SchDocument,
    SchLength,
    SchRecord,
    Sheet,
    SheetEntry,
    SheetFileName,
    SheetName,
    SheetSymbol,
    SignalHarness,
    Wire,
)
from fenolite.backends.altium.symbols import natural_key
from fenolite.core.coords import Point, Size
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.drawn import (
    DrawnBusEntry,
    DrawnField,
    DrawnJunction,
    DrawnLabel,
    DrawnLabelKind,
    DrawnOpaque,
    DrawnPin,
    DrawnPower,
    DrawnSchematic,
    DrawnShape,
    DrawnSheet,
    DrawnSheetRef,
    DrawnSymbol,
)
from fenolite.model.drawn_connect import PinKey, PinPoint

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-DRAWN-READ",))
FRAC = 100_000
"""Fraction units per 10-mil unit."""
QUARTER = 90_000_000
SHEET_STYLES: tuple[tuple[int, int, str], ...] = (
    (1150, 760, "A4"), (1550, 1110, "A3"), (2230, 1570, "A2"), (3150, 2230, "A1"), (4460, 3150, "A0"),
    (950, 750, ""), (1500, 950, ""), (2000, 1500, ""), (3200, 2000, ""), (4200, 3200, ""),
    (1100, 850, "Letter"), (1400, 850, "Legal"), (1700, 1100, "Tabloid"),
    (990, 790, ""), (1540, 990, ""), (2060, 1560, ""), (3260, 2060, ""), (4280, 3280, ""),
)  # fmt: skip
"""Per ``SHEETSTYLE`` 0 to 17: the drawing area in 10-mil units, landscape, and the paper of the drawn sheet
(``""``: a custom paper of the area's size); the areas of ``read.sheet.SHEET_STYLES``."""
POWER_STYLES: tuple[str, ...] = (
    "circle", "arrow", "bar", "wave", "power_ground", "signal_ground", "earth", "gost_arrow",
    "gost_power_ground", "gost_earth", "gost_bar",
)  # fmt: skip
"""The power port styles 0 to 10 (``schematic-records.md``, "Power port")."""
POWER_LIBRARY = "AltiumPower"
"""The library of the power symbols a drawn Altium power port names (``AltiumPower:<style>``)."""
IO_SHAPES: Mapping[int, DrawnShape] = MappingProxyType(
    {0: "passive", 1: "output", 2: "input", 3: "bidirectional"}
)
"""Port and sheet entry ``IOTYPE`` (unspecified, output, input, bidirectional) to a drawn label shape."""
_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")
_NAMESPACE = uuid.UUID("5f0c4d2e-7b1a-4c39-9a57-0c470a1d2a00")

KINDS: tuple[str, ...] = (
    "sheet", "schematic-symbol", "symbol-graphic", "pin", "wire", "junction", "label", "port", "power",
    "bus", "bus-entry", "sheet-symbol", "harness", "no-connect", "directive", "schematic-text",
    "schematic-graphic", "image", "title-block",
)  # fmt: skip
"""The report kinds of a written drawing (design D5), in report order."""
RECORD_KINDS: Mapping[str, str] = MappingProxyType(
    {
        "Sheet": "sheet",
        "Component": "schematic-symbol",
        "Wire": "wire",
        "Junction": "junction",
        "NetLabel": "label",
        "Port": "port",
        "PowerPort": "power",
        "Bus": "bus",
        "BusEntry": "bus-entry",
        "SheetSymbol": "sheet-symbol",
        "HarnessConnector": "harness",
        "SignalHarness": "harness",
        "NoErc": "no-connect",
        "WarningSign": "directive",
        "CompileMask": "directive",
        "Label": "schematic-text",
        "TextFrame": "schematic-text",
        "Note": "schematic-text",
        "Hyperlink": "schematic-text",
        "Line": "schematic-graphic",
        "Polyline": "schematic-graphic",
        "Polygon": "schematic-graphic",
        "Rectangle": "schematic-graphic",
        "RoundRectangle": "schematic-graphic",
        "Ellipse": "schematic-graphic",
        "EllipticalArc": "schematic-graphic",
        "Arc": "schematic-graphic",
        "PieChart": "schematic-graphic",
        "Bezier": "schematic-graphic",
        "IeeeSymbol": "schematic-graphic",
        "Image": "image",
        "Parameter": "title-block",
        "Template": "title-block",
    }
)
"""The report kind of each root record class (``record_class``)."""
MODELLED: frozenset[str] = frozenset(
    {"Sheet", "Component", "Wire", "Junction", "NetLabel", "Port", "PowerPort", "Bus", "BusEntry",
     "SheetSymbol", "NoErc", "Parameter"}
)  # fmt: skip
"""Root record classes that become modelled drawn items (or the sheet's paper and title block)."""
TITLE_PARAMETERS: Mapping[str, str] = MappingProxyType(
    {
        "title": "title",
        "revision": "revision",
        "date": "date",
        "organization": "organization",
        "companyname": "organization",
        "documentnumber": "doc_id",
        "drawnby": "responsible",
        "approvedby": "approver",
    }
)
"""Document parameter name (folded) → title-block field; the names of ``lens.altium.SHEET_PARAMETERS`` and
Altium's ``CompanyName``. Other parameters with a value become ``param.<name>`` pairs."""


ITEM_FIELDS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "symbol": ("DISPLAYMODE", "PARTCOUNT", "DISPLAYMODECOUNT"),
        "label": (
            "STYLE",
            "IOTYPE",
            "ALIGNMENT",
            "WIDTH",
            "WIDTH_FRAC",
            "HEIGHT",
            "HEIGHT_FRAC",
            "BORDERWIDTH",
            "AREACOLOR",
            "TEXTCOLOR",
            "COLOR",
            "FONTID",
            "JUSTIFICATION",
        ),
        "power": ("STYLE", "SHOWNETNAME", "ISCROSSSHEETCONNECTOR"),
    }
)
"""Per modelled item kind, the record fields that ``Extracted.altium_fields`` keeps when the record has
them."""


def item_fields(record: SchRecord, kind: str) -> dict[str, str]:
    """The ``ITEM_FIELDS`` of ``kind`` that ``record`` holds, as text."""
    props = record.props
    if props is None:
        return {}
    present = set(props.keys())
    return {key: props.text(key) for key in ITEM_FIELDS[kind] if key in present}


def opaque_kind(text: str) -> str:
    """The report kind of an opaque item from the ``RECORD`` of its first line (``RECORD_KINDS``)."""
    from fenolite.backends.altium.read.sch.records import RECORD_TYPES

    match = re.match(r"\|RECORD=(\d+)", text)
    number = int(match.group(1)) if match else -1
    name = {209: "Note", 225: "CompileMask"}.get(number) or getattr(RECORD_TYPES.get(number), "__name__", "")
    return RECORD_KINDS.get(name, "schematic-graphic")


def record_class(record: SchRecord) -> str:
    """The class name of a root record for ``RECORD_KINDS``: ``Note`` for record 209 and ``CompileMask`` for
    record 225, which the reader keeps as unknown records."""
    name = type(record).__name__
    if name == "UnknownRecord" and record.props is not None:
        number = record.props.raw("RECORD")
        if number == b"209":
            return "Note"
        if number == b"225":
            return "CompileMask"
    return name


def _issue(code: str, severity: str, message: str, where: str = "") -> Issue:
    return Issue(code, severity, message, where=where)  # type: ignore[arg-type]


# --- frame -----------------------------------------------------------------------------------------------


@dataclass
class Frame:
    """The frame of one document: its drawing area in fraction units and the count of rounded values."""

    width: int
    height: int
    paper: str
    rounded: int = 0
    exact: Mapping[int, int] = field(default_factory=lambda: {})
    """The carried nm length of each coordinate a KiCad length off the 127/50 nm step was rounded to."""

    def nm(self, value: int) -> int:
        length = SchLength(value)
        if not length.exact:
            self.rounded += 1
        return length.nm()

    def coordinate(self, value: int) -> int:
        carried = self.exact.get(value)
        return carried if carried is not None else self.nm(value)

    def point(self, at: tuple[SchLength, SchLength]) -> Point:
        return Point(self.coordinate(at[0].value), self.coordinate(self.height - at[1].value))


def _carried(document: SchDocument) -> drawn_carrier.KiCadSheet | None:
    """``document``'s ``Fenolite.KiCad.Sheet`` carrier, read before its records so that every point comes
    back as KiCad wrote it and the writer's harness blocks are dropped; ``None`` when the carrier is missing
    or unreadable (the record loop reports it)."""
    parts: dict[int, str] = {}
    for record in document.all_records():
        part = drawn_carrier.part_index(record.name) if isinstance(record, Parameter) else None
        if isinstance(record, Parameter) and record.owner is None and part is not None:
            parts[part] = record.text
    if not parts:
        return None
    try:
        return drawn_carrier.KiCadSheet.parse(drawn_carrier.joined(parts))
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class _Generated:
    """The items of the writer's harness blocks (``drawn_harness``), in nm, which the reader drops."""

    wires: frozenset[tuple[Point, ...]] = frozenset()
    lines: frozenset[tuple[Point, ...]] = frozenset()
    labels: frozenset[tuple[str, Point]] = frozenset()
    connectors: frozenset[Point] = frozenset()
    networks: frozenset[tuple[Point, ...]] = frozenset()
    ends: frozenset[Point] = frozenset()
    paper: str = ""

    @classmethod
    def of(cls, carried: drawn_carrier.KiCadSheet | None) -> _Generated:
        value = carried.generated if carried is not None else None
        if not value:
            return cls()

        def point(item: object) -> Point:
            x, y = cast(list[int], item)
            return Point(int(x), int(y))

        def items(key: str) -> list[drawn_carrier.Json]:
            return cast(list[drawn_carrier.Json], value.get(key, []))

        return cls(
            frozenset(tuple(point(p) for p in item["pts"]) for item in items("wires")),
            frozenset(tuple(point(p) for p in item["pts"]) for item in items("lines")),
            frozenset((str(item["text"]), point(item["at"])) for item in items("labels")),
            frozenset(point(item["at"]) for item in items("connectors")),
            frozenset(tuple(point(p) for p in item["pts"]) for item in items("networks")),
            frozenset(point(item["at"]) for item in items("ends")),
            str(value.get("paper", "")),
        )


def frame_of(document: SchDocument) -> Frame:
    """The drawing area of ``document``'s sheet record and the paper of its drawn sheet: a named paper for
    the ISO and US styles, else ``custom:<width>x<height>`` in nm; `` portrait`` is appended for a portrait
    sheet. A document without a sheet record is an A4 landscape sheet."""
    sheet = document.sheet
    props = sheet.props if sheet is not None else None
    if props is None:
        return Frame(1150 * FRAC, 760 * FRAC, "A4")
    if props.bool("USECUSTOMSHEET"):
        width = props.int("CUSTOMX") * FRAC + props.int("CUSTOMX_FRAC")
        height = props.int("CUSTOMY") * FRAC + props.int("CUSTOMY_FRAC")
        paper = ""
    else:
        style = props.int("SHEETSTYLE")
        units_x, units_y, paper = SHEET_STYLES[style] if 0 <= style < len(SHEET_STYLES) else SHEET_STYLES[0]
        width, height = units_x * FRAC, units_y * FRAC
    portrait = props.int("WORKSPACEORIENTATION") == 1
    if portrait:
        width, height = height, width
    if not paper:
        paper = f"custom:{SchLength(width).nm()}x{SchLength(height).nm()}"
    elif portrait:
        paper += " portrait"
    return Frame(width, height, paper)


# --- record text -----------------------------------------------------------------------------------------


def record_line(record: SchRecord, owner: int | None = None) -> str:
    """The fields of ``record`` as one ``|KEY=value`` line, in file order, each key once (its ``%UTF8%`` twin
    folded into the text); ``OWNERINDEX`` is ``@<owner>`` (the line of the owner in the same item) or left
    out for a root record."""
    props = record.props
    if props is None:
        return ""
    fields: list[str] = []
    for key in props.keys():
        if key == "OWNERINDEX":
            if owner is not None:
                fields.append(f"OWNERINDEX=@{owner}")
            continue
        fields.append(f"{key}={props.text(key)}")
    if owner is not None and "OWNERINDEX" not in props.keys():
        fields.append(f"OWNERINDEX=@{owner}")
    return "|" + "|".join(fields)


def subtree_text(document: SchDocument, record: SchRecord) -> str:
    """``record`` and its descendants, depth first in stream order, one line each; a child names its owner's
    line with ``OWNERINDEX=@<line>``."""
    lines: list[str] = []
    stack: list[tuple[SchRecord, int | None]] = [(record, None)]
    while stack:
        current, owner = stack.pop(0)
        line = record_line(current, owner)
        if not line:
            continue
        lines.append(line)
        number = len(lines) - 1
        stack[0:0] = [(document.get(ref), number) for ref in current.children]
    return "\n".join(lines)


# --- KiCad stand-ins ----------------------------------------------------------------------------------------


def _mm(nm: int) -> str:
    text = f"{nm / 1_000_000:.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _xy(at: Point) -> str:
    return f"(xy {_mm(at.x)} {_mm(at.y)})"


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def item_uuid(file: str, record: SchRecord) -> str:
    """A stable uuid for the KiCad stand-in of ``record`` of ``file``."""
    return str(uuid.uuid5(_NAMESPACE, f"{file.casefold()}:{record.ref.stream}:{record.ref.index}"))


def _stroke(record: SchRecord) -> str:
    width = {0: 0, 1: 254_000, 2: 762_000, 3: 1_270_000}.get(
        record.props.int("LINEWIDTH") if record.props else 0, 0
    )
    return f"(stroke (width {_mm(width)}) (type default))"


def stand_in(record: SchRecord, frame: Frame, ident: str) -> str:
    """The KiCad S-expression drawn for an opaque root record, or ``""`` when KiCad has no like shape. The
    record text travels in the carrier; the stand-in only shows it."""
    props = record.props
    if props is None:
        return ""
    name = record_class(record)

    def point(prefix: str) -> Point:
        x = props.int(f"{prefix}.X") * FRAC + props.int(f"{prefix}.X_FRAC")
        y = props.int(f"{prefix}.Y") * FRAC + props.int(f"{prefix}.Y_FRAC")
        return frame.point((SchLength(x), SchLength(y)))

    def points() -> list[Point]:
        count = props.int("LOCATIONCOUNT")
        found: list[Point] = []
        for n in range(1, count + 1):
            x = props.int(f"X{n}") * FRAC + props.int(f"X{n}_FRAC")
            y = props.int(f"Y{n}") * FRAC + props.int(f"Y{n}_FRAC")
            found.append(frame.point((SchLength(x), SchLength(y))))
        return found

    tail = f"(uuid {_quote(ident)})"
    if name in ("Line",):
        return f"(polyline (pts {_xy(point('LOCATION'))} {_xy(point('CORNER'))}) {_stroke(record)} {tail})"
    if name in ("Polyline", "SignalHarness", "Bezier", "Polygon"):
        found = points()
        if len(found) < 2:
            return ""
        if name == "Polygon":
            found.append(found[0])
        pts = " ".join(_xy(p) for p in found)
        return f"(polyline (pts {pts}) {_stroke(record)} {tail})"
    if name in ("Rectangle", "RoundRectangle", "TextFrame", "Note", "HarnessConnector", "Image"):
        if name == "HarnessConnector":
            start = point("LOCATION")
            x_size = SchLength(props.int("XSIZE") * FRAC + props.int("XSIZE_FRAC")).nm()
            y_size = SchLength(props.int("YSIZE") * FRAC + props.int("YSIZE_FRAC")).nm()
            a, b = start, Point(start.x + x_size, start.y + y_size)
        else:
            a, b = point("LOCATION"), point("CORNER")
        lo, hi = Point(min(a.x, b.x), min(a.y, b.y)), Point(max(a.x, b.x), max(a.y, b.y))
        if name in ("TextFrame", "Note") and props.text("TEXT"):
            text = props.text("TEXT").replace("~1", "\n")
            return (
                f"(text_box {_quote(text)} (exclude_from_sim no) (at {_mm(lo.x)} {_mm(lo.y)} 0) "
                f"(size {_mm(hi.x - lo.x)} {_mm(hi.y - lo.y)}) {_stroke(record)} (fill (type none)) "
                f"(effects (font (size 1.27 1.27)) (justify left top)) {tail})"
            )
        return (
            f"(rectangle (start {_mm(lo.x)} {_mm(lo.y)}) (end {_mm(hi.x)} {_mm(hi.y)}) {_stroke(record)} "
            f"(fill (type none)) {tail})"
        )
    if name in ("Ellipse", "Arc"):
        center = point("LOCATION")
        radius = SchLength(props.int("RADIUS") * FRAC + props.int("RADIUS_FRAC")).nm()
        if (
            name == "Ellipse"
            or props.text("STARTANGLE") in ("", "0")
            and props.text("ENDANGLE") in ("", "360")
        ):
            return (
                f"(circle (center {_mm(center.x)} {_mm(center.y)}) (radius {_mm(radius)}) "
                f"{_stroke(record)} (fill (type none)) {tail})"
            )
        return ""
    if name in ("Label", "Hyperlink"):
        text = props.text("TEXT")
        if not text:
            return ""
        at = point("LOCATION")
        angle = props.int("ORIENTATION") % 4 * 90
        return (
            f"(text {_quote(text)} (exclude_from_sim no) (at {_mm(at.x)} {_mm(at.y)} {angle}) "
            f"(effects (font (size 1.27 1.27)) (justify left bottom)) {tail})"
        )
    return ""


# --- harnesses, wire splits and junctions ----------------------------------------------------------------


def harness_members(documents: Sequence[SchDocument]) -> dict[str, tuple[str, ...]]:
    """Per harness type (folded), its entry names in natural order: connectors of a type may list them in
    other orders, and documents come in other orders (change c0470)."""
    found: dict[str, list[str]] = {}
    for document in documents:
        for connector in document.of_type(HarnessConnector):
            children = document.children_of(connector)
            kind = next((c.text for c in children if isinstance(c, HarnessType)), "")
            names = found.setdefault(kind.casefold(), [])
            for entry in children:
                if isinstance(entry, HarnessEntry) and entry.name and entry.name not in names:
                    names.append(entry.name)
    return {kind: tuple(sorted(names, key=lambda n: (natural_key(n), n))) for kind, names in found.items()}


def group_text(name: str, members: Sequence[str]) -> str:
    """The KiCad bus group that stands for a harness: ``NAME{A B}`` (members ``NAME.A`` and ``NAME.B``)."""
    return f"{name}{{{' '.join(members)}}}"


# --- carried harness records (change c0470) -------------------------------------------------------------

HARNESS_RECORDS = frozenset({"215", "218"})
"""The root records of a harness that KiCad cannot draw: a harness connector and a signal harness."""


def _first_fields(text: str) -> dict[str, str]:
    line = text.split("\n", 1)[0]
    found: dict[str, str] = {}
    for item in line.split("|"):
        key, separator, value = item.partition("=")
        if separator:
            found.setdefault(key.upper(), value)
    return found


def is_harness_text(text: str) -> bool:
    """Whether the carried Altium ``text`` (``subtree_text``) is a harness record: a connector, a signal
    harness or a port of a harness type."""
    fields = _first_fields(text)
    record = fields.get("RECORD", "")
    return record in HARNESS_RECORDS or (record == "18" and bool(fields.get("HARNESSTYPE")))


def carried_document(texts: Sequence[str]) -> SchDocument:
    """A document of the carried Altium subtrees ``texts`` (``subtree_text``), in the ASCII form after a
    bare sheet record, each child's ``OWNERINDEX=@<line>`` made the index of its owner."""
    from fenolite.backends.altium.read.sch import read_schematic
    from fenolite.backends.altium.read.sch.document import ASCII_HEADER

    lines = ["|RECORD=31|OWNERPARTID=-1"]
    for text in texts:
        base = len(lines)
        for line in text.splitlines():
            owner = re.search(r"\|OWNERINDEX=@(\d+)", line)
            if owner is not None:
                line = line.replace(owner[0], f"|OWNERINDEX={base + int(owner[1])}")
            lines.append(line)
    head = f"|HEADER={ASCII_HEADER}|WEIGHT={len(lines)}"
    data = "\r\n".join((head, *lines)) + "\r\n"
    return read_schematic(data.encode("utf-8"), file="carried.SchDoc")


@dataclass(frozen=True, slots=True)
class HarnessStandIns:
    """The KiCad items that the reader draws for the harness records of one sheet, in native points: the bus
    of each signal harness, and the local label of each connector entry and the label of each harness port
    as ``(text, point)``."""

    buses: frozenset[tuple[tuple[int, int], ...]]
    labels: frozenset[tuple[str, tuple[int, int]]]


def harness_stand_ins(document: SchDocument, members: Mapping[str, tuple[str, ...]]) -> HarnessStandIns:
    """The stand-ins of ``document``'s harness records (``carried_document``), as the extractor draws them;
    ``members`` are the entries per folded harness type (``harness_members``)."""
    harness = harness_lines(document)
    buses = frozenset(tuple(pt(p) for p in line.points) for line in document.of_type(SignalHarness))
    labels: set[tuple[str, tuple[int, int]]] = set()
    for connector in document.of_type(HarnessConnector):
        kind = next((c.text for c in document.children_of(connector) if isinstance(c, HarnessType)), "")
        name = _harness_name(document, connector, harness) or kind
        for entry in document.children_of(connector):
            point = entry_point(document, entry) if isinstance(entry, HarnessEntry) else None
            if point is not None and entry.name:  # type: ignore[union-attr]
                labels.add((f"{name}.{entry.name}", point))  # type: ignore[union-attr]
    for port in document.of_type(Port):
        if port.harness_type and port.name:
            text = group_text(port.name, members.get(port.harness_type.casefold(), ()))
            labels.update((text, end) for end in port_ends(port))
    return HarnessStandIns(buses, frozenset(labels))


def split_lines(lines: Sequence[tuple[Point, ...]], points: Sequence[Point]) -> list[tuple[Point, ...]]:
    """``lines`` with a vertex added where one of ``points`` lies inside a segment; KiCad joins a pin to a
    wire at the wire's ends only, Altium anywhere on it."""
    wanted = sorted(set(points), key=lambda p: (p.x, p.y))
    out: list[tuple[Point, ...]] = []
    for line in lines:
        result: list[Point] = [line[0]]
        for a, b in zip(line, line[1:], strict=False):
            inside = [
                p for p in wanted
                if p not in (a, b) and on_segment((p.x, p.y), (a.x, a.y), (b.x, b.y))
            ]  # fmt: skip
            inside.sort(key=lambda p: abs(p.x - a.x) + abs(p.y - a.y))
            result += [*inside, b]
        out.append(tuple(result))
    return out


def tee_points(lines: Sequence[tuple[Point, ...]]) -> list[Point]:
    """The ends of a line that lie inside a segment of another line (a T), where Altium joins the lines and
    KiCad wants a junction."""
    found: list[Point] = []
    for number, line in enumerate(lines):
        for end in (line[0], line[-1]):
            for other, points in enumerate(lines):
                if other == number:
                    continue
                if any(
                    end not in (a, b) and on_segment((end.x, end.y), (a.x, a.y), (b.x, b.y))
                    for a, b in zip(points, points[1:], strict=False)
                ):
                    found.append(end)
                    break
    return list(dict.fromkeys(found))


# --- the drawing -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Extracted:
    """A drawing extracted from read Altium sheets: the value, the pin points of its symbols, the issues,
    each drawn sheet's records that no drawn item holds (the sheet record, its document parameters and its
    template, as ``|KEY=value`` lines), the root record count per report kind, and the count per drawn sheet
    of each record class at the root."""

    drawn: DrawnSchematic
    pins: Mapping[PinKey, tuple[PinPoint, ...]]
    issues: tuple[Issue, ...] = ()
    sheet_records: Mapping[str, str] = field(default_factory=lambda: {})
    counts: Mapping[str, int] = field(default_factory=lambda: {})
    classes: Mapping[str, Mapping[str, int]] = field(default_factory=lambda: {})
    files: Mapping[str, str] = field(default_factory=lambda: {})
    """Drawn sheet key → the Altium document it was read from."""
    altium_fields: Mapping[str, Mapping[str, Mapping[str, str]]] = field(default_factory=lambda: {})
    """Drawn sheet key → item (``symbol:<i>``, ``label:<i>``, ``power:<i>``) → the Altium fields that the
    drawn item does not hold (``ITEM_FIELDS``): display mode, port and power style. Design D4 carries them."""
    placed: Mapping[tuple[str, int], tuple[str, int, Component]] = field(default_factory=lambda: {})
    """(drawn sheet key, symbol index) → the full component path, the index of its document in the input and
    its component record."""
    origins: Mapping[str, drawn_carrier.Json] = field(default_factory=lambda: {})
    """Drawn sheet key → the ``origin`` its ``Fenolite.KiCad.Sheet`` carrier names: the KiCad sheet it is
    one instance's copy of, and the part name of each designator there (change c0470)."""
    definitions: Mapping[str, str] = field(default_factory=lambda: {})
    """The KiCad library text of each carried opaque symbol's definition, by its lib id (change c0470)."""


TOPS_KEY = "project"
TOPS_FIELD = "TOPS"
PROJECT_FIELD = "PRJPCB"
"""The field of ``TOPS_KEY`` that holds the source project's settings (``prjpcb.carried_settings``, c0479)."""
"""The carrier field of the root sheet that the drawing adds over the top sheets of a project without one
(a flat project): the Altium writer writes those sheets as top documents again (change c0470)."""


def _sheet_key(file: str, taken: set[str]) -> str:
    stem = PureWindowsPath(file).stem
    base = _UNSAFE.sub("_", stem) or "sheet"
    if not re.match(r"[A-Za-z_]", base):
        base = f"_{base}"
    key, number = base, 2
    while key.casefold() in taken:
        key, number = f"{base}_{number}", number + 1
    taken.add(key.casefold())
    return key


def _ref_key(text: str, taken: set[str]) -> str:
    """The key of a sheet reference, as ``backends.kicad.drawn`` gives the reference read back."""
    base = _UNSAFE.sub("_", text) or "sheet"
    if not re.match(r"[A-Za-z_]", base):
        base = f"_{base}"
    key, number = base, 2
    while key in taken:
        key, number = f"{base}_{number}", number + 1
    taken.add(key)
    return key


def _mirror(component: Component) -> str:
    """Altium mirrors the part about its vertical axis before it turns it; in the KiCad order (turn, then
    mirror) that is ``y`` for 0 and 180 degrees and ``x`` for 90 and 270."""
    if not component.mirrored:
        return ""
    return "y" if component.orientation % 2 == 0 else "x"


_H = {0: "left", 1: "", 2: "right"}
_V = {0: "bottom", 1: "", 2: "top"}
_FLIP = {"left": "right", "right": "left", "top": "bottom", "bottom": "top", "": ""}


def _text_pose(record: SchRecord, frame: Frame, name: str, hidden: bool) -> DrawnField:
    props = record.props
    justification = props.int("JUSTIFICATION") if props is not None else 0
    orientation = props.int("ORIENTATION") % 4 if props is not None else 0
    horizontal, vertical = _H[justification % 3], _V[min(justification // 3, 2)]
    if orientation >= 2:
        horizontal, vertical = _FLIP[horizontal], _FLIP[vertical]
    words = " ".join(word for word in (horizontal, vertical) if word)
    at = frame.point(record._point("LOCATION"))  # pyright: ignore[reportPrivateUsage]
    return DrawnField(name, at, (orientation % 2) * QUARTER, words, hidden)


def _fields(document: SchDocument, component: Component, frame: Frame) -> tuple[DrawnField, ...]:
    found: list[DrawnField] = []
    seen: set[str] = set()
    children = document.children_of(component)
    has_comment = any(isinstance(c, Parameter) and c.name == "Comment" for c in children)
    for child in children:
        if isinstance(child, Designator):
            name = "Reference"
        elif isinstance(child, Parameter) and child.name:
            if child.name == "Value" and has_comment:
                continue
            name = "Value" if child.name == "Comment" else child.name
            if child.hidden and name != "Value":
                continue
        else:
            continue
        if name in seen:
            continue
        seen.add(name)
        found.append(_text_pose(child, frame, name, child.hidden))
    return tuple(found)


def _port_label(port: Port, frame: Frame, wires: object, kind: DrawnLabelKind) -> tuple[DrawnLabel, bool]:
    """The drawn label of ``port``: at the end that a wire touches (the location when none or both do), the
    body turned away from it; and whether both ends touch a wire."""
    first, second = port_ends(port)
    touched = [bool(wires.at(end)) for end in (first, second)]  # type: ignore[attr-defined]
    vertical = port.style in VERTICAL_PORT_STYLES
    use_second = touched[1] and not touched[0]
    end = second if use_second else first
    at = frame.point((SchLength(end[0]), SchLength(end[1])))
    rotation = (3 if vertical else 2) * QUARTER if use_second else (1 if vertical else 0) * QUARTER
    shape: DrawnShape = IO_SHAPES.get(port.io_type, "passive")
    return DrawnLabel(kind, port.name, at, rotation, shape), all(touched)


def entry_harness(
    document: SchDocument, entry: SheetEntry, harness: Lines, child_ports: Mapping[str, str]
) -> str:
    """The harness type a sheet entry is drawn with: the harness type of the port of its name on the child
    sheet (``child_ports``) for an entry that carries a harness, its record's ``HARNESSTYPE`` or a signal
    harness line at it (``connectivity.md``: such an entry carries a harness whether or not its record
    holds the key); the record's own type when the child has no such port; "" for an entry without one.
    The child's port decides: harness entries join by name within a harness group, so the type the record
    of the entry holds, which can differ from the port's, does not change the nets (change c0470)."""
    if not entry.name:
        return ""
    if not entry.harness_type:
        point = entry_point(document, entry)
        if point is None or not harness.at(point):
            return ""
    return child_ports.get(entry.name) or entry.harness_type


def lone_harness(entry: SheetEntry, kind: str, members: Mapping[str, tuple[str, ...]]) -> dict[str, str]:
    """What the carrier keeps of the ``HARNESSTYPE`` of a sheet entry drawn with harness type ``kind``
    (``entry_harness``, change c0470): the record's own type when it differs from ``kind`` ("" for a
    record that holds none), or ``kind`` when no connector defines it (KiCad draws the entry as the empty
    bus group ``NAME{}``); else nothing."""
    if not kind or not entry.name:
        return {}
    if entry.harness_type != kind or not members.get(kind.casefold()):
        return {"HARNESSTYPE": entry.harness_type}
    return {}


def label_harness(document: SchDocument, label: NetLabel, harness: Lines) -> str:
    """The harness type of the signal harness line that ``label`` sits on: the type of a port, sheet entry
    or harness connector on that line; "" for a label on no harness line (change c0470)."""
    groups = harness.groups()
    start = harness.at(pt(label.location))
    if not start:
        return ""
    wanted = {groups[number] for number in start}

    def on(point: tuple[int, int] | None) -> bool:
        return point is not None and any(groups[number] in wanted for number in harness.at(point))

    for port in document.of_type(Port):
        if port.harness_type and any(on(end) for end in port_ends(port)):
            return port.harness_type
    for entry in document.of_type(SheetEntry):
        if entry.harness_type and on(entry_point(document, entry)):
            return entry.harness_type
    for connector in document.of_type(HarnessConnector):
        if on(connector_point(connector)):
            return next((c.text for c in document.children_of(connector) if isinstance(c, HarnessType)), "")
    return ""


def child_harness_ports(document: SchDocument) -> dict[str, str]:
    """Port name → harness type of each port of ``document`` that holds one (the first of a name)."""
    found: dict[str, str] = {}
    for port in document.of_type(Port):
        if port.name and port.harness_type:
            found.setdefault(port.name, port.harness_type)
    return found


def one_spelling(labels: list[DrawnLabel], kept: dict[str, dict[str, str]]) -> None:
    """The net labels of one sheet whose texts differ only in letter case, which Altium joins
    (``connectivity.md``: names are compared without letter case) and KiCad does not, take the first of
    their texts in code-point order, whatever the order of their records; ``kept`` holds each changed
    label's own text by its position (``text:<x>,<y>``), which ``sheet_carrier.restore`` gives back
    (change c0470)."""
    spelled: dict[str, str] = {}
    for label in labels:
        if label.kind != "hierarchical":
            key = label.text.casefold()
            spelled[key] = min(spelled.get(key, label.text), label.text)
    for index, label in enumerate(labels):
        if label.kind == "hierarchical":
            continue
        first = spelled[label.text.casefold()]
        if first != label.text:
            kept[f"text:{label.at.x},{label.at.y}"] = {"TEXT": label.text}
            labels[index] = dataclasses.replace(label, text=first)


def _entry_pin(
    document: SchDocument, entry: SheetEntry, frame: Frame, members: Mapping[str, tuple[str, ...]], kind: str
) -> DrawnPin | None:
    point = entry_point(document, entry)
    if point is None or not entry.name:
        return None
    rotation = {SIDE_LEFT: 2, SIDE_RIGHT: 0, SIDE_TOP: 1}.get(entry.side, 3) * QUARTER
    shape: DrawnShape = IO_SHAPES.get(entry.io_type, "passive")
    name = entry.name
    if kind:
        name = group_text(name, members.get(kind.casefold(), ()))
    return DrawnPin(name, shape, frame.point((SchLength(point[0]), SchLength(point[1]))), rotation)


def _restore_stand_ins(
    carriers: Sequence[drawn_carrier.KiCadSheet],
    powers: Sequence[DrawnPower],
    uids: Sequence[str],
    labels: list[DrawnLabel],
    kept: dict[str, dict[str, str]],
) -> list[DrawnPower]:
    """The power items of a sheet with the KiCad items of its carriers (change c0470, design D4): a power
    port that stands for a KiCad global label becomes that label (appended to ``labels``), one that stands
    for a KiCad power symbol becomes that symbol, each with the net and position of the port; the carried
    power flags are added. ``kept`` (the Altium fields by ``power:<index>``) follows the new indices."""
    stand_ins = {uid: entry for carrier in carriers for uid, entry in carrier.stand_ins.items()}
    out: list[DrawnPower] = []
    moved: dict[str, dict[str, str]] = {}
    for index, power in enumerate(powers):
        entry = stand_ins.get(uids[index]) if uids[index] else None
        found = kept.pop(f"power:{index}", None)
        pstyle = kept.pop(f"power_style:{index}", None)
        if entry is not None and "label" in entry:
            labels.append(drawn_carrier.label_of(entry["label"], power.net, power.at, power.rotation))
            continue
        if entry is not None and "power" in entry:
            out.append(drawn_carrier.power_of(entry["power"], power.net, power.at, power.rotation))
            continue
        if entry is not None and "pin" in entry:
            continue  # the port at a hidden KiCad power pin, which joins the net its name gives
        if found is not None:
            moved[f"power:{len(out)}"] = found
        if pstyle is not None:
            moved[f"power_style:{len(out)}"] = pstyle
        out.append(power)
    kept.update(moved)
    out += [drawn_carrier.flag_of(value) for carrier in carriers for value in carrier.powers]
    return out


def _title(document: SchDocument) -> tuple[tuple[str, str], ...]:
    fields: dict[str, str] = {}
    params: dict[str, str] = {}
    for record in document.all_records():
        if not isinstance(record, Parameter) or record.owner is not None or not record.name:
            continue
        if drawn_carrier.part_index(record.name) is not None:
            continue  # the carrier of KiCad items (change c0470), not a title-block field
        value = record.text
        if not value or value == "*":
            continue
        name = TITLE_PARAMETERS.get(record.name.casefold())
        if name is not None:
            fields.setdefault(name, value)
        else:
            params.setdefault(record.name, value)
    order = ("title", "date", "revision", "organization", "doc_id", "responsible", "approver")
    pairs = [(name, fields[name]) for name in order if name in fields]
    pairs += [(f"param.{name}", value) for name, value in sorted(params.items())]
    return tuple(pairs)


def _harness_name(document: SchDocument, connector: HarnessConnector, harness: Lines) -> str:
    """The name of the harness of ``connector``: the port, sheet entry or net label on its harness line, or
    the port or sheet entry on its connection point (change c0470). A net label takes the spelling of a
    harness port or sheet entry of its sheet whose name differs from it only in letter case: Altium joins
    them (``connectivity.md``), and KiCad names the members of the port's bus group with the port's
    spelling (change c0470)."""
    groups = harness.groups()
    point = connector_point(connector)
    start = harness.at(point)
    if not start:  # a port or sheet entry on the connection point itself, with no harness line between
        for port in document.of_type(Port):
            if port.harness_type and point in port_ends(port):
                return port.name
        for entry in document.of_type(SheetEntry):
            if entry.harness_type and entry_point(document, entry) == point:
                return entry.name
        return ""
    wanted = {groups[number] for number in start}

    def on(point: tuple[int, int]) -> bool:
        return any(groups[number] in wanted for number in harness.at(point))

    for port in document.of_type(Port):
        if port.harness_type and any(on(end) for end in port_ends(port)):
            return port.name
    for entry in document.of_type(SheetEntry):
        point = entry_point(document, entry)
        if entry.harness_type and point is not None and on(point):
            return entry.name
    for label in document.of_type(NetLabel):
        if label.text and on(pt(label.location)):
            named = [p.name for p in document.of_type(Port) if p.harness_type]
            named += [e.name for e in document.of_type(SheetEntry) if e.harness_type]
            return next((n for n in named if n.casefold() == label.text.casefold()), label.text)
    return ""


def _relative(path: str, module: str) -> str:
    if module and path.startswith(module + "/"):
        return path[len(module) + 1 :]
    return path


def _common(modules: Sequence[str]) -> str:
    split = [m.split("/") if m else [] for m in modules]
    common: list[str] = []
    for parts in zip(*split, strict=False):
        if all(p == parts[0] for p in parts):
            common.append(parts[0])
        else:
            break
    return "/".join(common)


def extract_with_pins(
    sheets: Sequence[SheetInput],
    *,
    components: Mapping[str, str] | None = None,
    resolved: Resolved | None = None,
) -> Extracted:
    """``extract`` with the pin points of every drawn symbol (``drawn_connect.resolve`` takes them) and the
    records that no drawn item holds. ``resolved`` is the netlist of ``sheets`` when the caller has it."""
    issues: list[Issue] = []
    if resolved is None:
        resolved = resolve(sheets, issues=[])
    scope = resolved.netlist.scope
    data = resolved.sheets
    members = harness_members([sheet.input.document for sheet in data])
    taken: set[str] = set()
    keys = [_sheet_key(sheet.input.file, taken) for sheet in data]
    tops = [instance for instance in resolved.instances if instance.parent is None]
    first_instance: dict[int, int] = {}
    for instance in resolved.instances:
        first_instance.setdefault(instance.sheet, instance.index)
    primary_paths: dict[str, str] = {}
    primary_rank: dict[str, tuple[int, int, int]] = {}
    for inst in resolved.instances:
        for grp_index, grp in enumerate(data[inst.sheet].groups):
            native = resolved.component_ids.get((inst.index, grp_index), "")
            ref = resolved.refs.get((inst.index, grp_index), grp.ref)
            if not native or not ref:
                continue
            rank = (min((max(1, p.current_part) for p in grp.parts), default=1), inst.index, grp_index)
            if native not in primary_rank or rank < primary_rank[native]:
                primary_rank[native] = rank
                primary_paths[native] = "/".join((*inst.names, ref))
    sheet_modules: dict[int, str] = {}
    for number, sheet in enumerate(data):
        idx = first_instance.get(number)
        if idx is None:
            sheet_modules[number] = ""
            continue
        inst = resolved.instances[idx]
        if inst.parent is None:
            sheet_modules[number] = ""
            continue
        found_modules: list[str] = []
        for grp_index, grp in enumerate(sheet.groups):
            ref = resolved.refs.get((idx, grp_index), grp.ref)
            native = resolved.component_ids.get((idx, grp_index), "")
            default_path = primary_paths.get(native) or "/".join((*inst.names, ref))
            comp_path = (components or {}).get(ref, default_path)
            if comp_path:
                found_modules.append(comp_path.rpartition("/")[0])
        sheet_modules[number] = _common(found_modules) if found_modules else "/".join(inst.names)
    repeated = Counter(instance.sheet for instance in resolved.instances)
    for number, count in sorted(repeated.items()):
        if count > 1:
            issues.append(
                _issue(
                    "altium.drawn.repeated",
                    "warning",
                    f"the sheet {data[number].input.file} has {count} instances; its drawing names the "
                    "parts of the first",
                    data[number].input.file,
                )
            )
    sheets_out: list[DrawnSheet] = []
    pins: dict[PinKey, tuple[PinPoint, ...]] = {}
    sheet_records: dict[str, str] = {}
    counts: Counter[str] = Counter()
    classes: dict[str, dict[str, int]] = {}
    files: dict[str, str] = {}
    extra: dict[str, dict[str, dict[str, str]]] = {}
    placed: dict[tuple[str, int], tuple[str, int, Component]] = {}
    origins: dict[str, drawn_carrier.Json] = {}
    definitions: dict[str, str] = {}
    children_of: dict[int, list[int]] = {}
    for instance in resolved.instances:
        if instance.parent is not None:
            children_of.setdefault(instance.parent, []).append(instance.index)
    for number, sheet in enumerate(data):
        document = sheet.input.document
        key = keys[number]
        files[key] = sheet.input.file
        frame = frame_of(document)
        carried_first = _carried(document)
        frame.exact = dict(carried_first.exact) if carried_first is not None else {}
        generated = _Generated.of(carried_first)
        index = first_instance.get(number)
        instance = resolved.instances[index] if index is not None else None
        module = sheet_modules.get(number, "")
        wires = wire_lines(document)
        label_kind: DrawnLabelKind = "global" if scope == "global" else "local"
        port_kind: DrawnLabelKind = (
            "hierarchical" if scope in ("hierarchical", "strict_hierarchical") else "global"
        )
        symbols: list[DrawnSymbol] = []
        pins_of_sheet: list[list[Point]] = []
        harness = harness_lines(document)
        powers: list[DrawnPower] = []
        labels: list[DrawnLabel] = []
        refs: list[DrawnSheetRef] = []
        opaques: list[DrawnOpaque] = []
        held: list[str] = []
        per_class: Counter[str] = Counter()
        kept: dict[str, dict[str, str]] = {}
        carriers: list[drawn_carrier.KiCadSheet] = []
        carrier_parts: dict[int, str] = {}
        power_uids: list[str] = []
        group_of: dict[int, int] = {}
        groups = sheet.groups if sheet.groups else part_groups(document)
        for g, group in enumerate(groups):
            for part in group.parts:
                group_of[part.ref.index] = g
        for record in document.all_records():
            if record.owner is not None:
                continue
            name = record_class(record)
            per_class[name] += 1
            counts[RECORD_KINDS.get(name, "schematic-graphic")] += 1
        for record in document.all_records():
            if record.owner is not None or not isinstance(record, Component):
                continue
            where = f"{sheet.input.file}:{record.ref.stream}[{record.ref.index}]"
            g = group_of.get(record.ref.index)
            if g is None:
                issues.append(_issue("altium.drawn.unrepresented", "error",
                                     "a component of no part group", where))  # fmt: skip
                continue
            group = groups[g]
            ref = resolved.refs.get((index, g), group.ref) if index is not None else group.ref
            native = resolved.component_ids.get((index, g), "") if index is not None else ""
            default_path = primary_paths.get(native) or (
                "/".join((*instance.names, ref)) if instance else ref
            )
            path = (components or {}).get(ref, default_path)
            drawn = DrawnSymbol(
                _relative(path, module),
                max(1, record.current_part),
                frame.point(record.location),
                (record.orientation % 4) * QUARTER,
                _mirror(record),
                _fields(document, record, frame),
            )
            pins[(key, "symbol", len(symbols))] = tuple(
                PinPoint(
                    pin.designator,
                    frame.point(pin.hot_end),
                    pin_etype(pin)[0],
                    pin.hidden,
                    pin.name,
                )
                for pin in document.shown_children(record)
                if isinstance(pin, Pin)
            )
            if found := item_fields(record, "symbol"):
                kept[f"symbol:{len(symbols)}"] = found
            gfx_lines = [
                record_line(child, 0)
                for child in document.children_of(record)
                if child.owner_display_mode == record.display_mode
                and child.owner_part in (0, max(1, record.current_part))
                and isinstance(child, drawn_symbols.BODY)
                and not isinstance(child, Pin)
            ]
            gfx_lines = [line for line in gfx_lines if line]
            comp_gfx: dict[str, str] = {}
            if gfx_lines:
                comp_gfx["POSE"] = f"{drawn.at.x},{drawn.at.y},{drawn.rotation},{drawn.mirror}"
                comp_gfx["RECORDS"] = "\n".join(gfx_lines)
            des_rec = next((c for c in document.children_of(record) if isinstance(c, Designator)), None)
            com_rec = next(
                (c for c in document.children_of(record) if isinstance(c, Parameter) and c.name == "Comment"),
                None,
            )
            if des_rec is not None and des_rec.props is not None and "FONTID" in set(des_rec.props.keys()):
                comp_gfx["DESIGNATOR_FONTID"] = des_rec.props.text("FONTID")
            if com_rec is not None and com_rec.props is not None and "FONTID" in set(com_rec.props.keys()):
                comp_gfx["COMMENT_FONTID"] = com_rec.props.text("FONTID")
            if com_rec is not None and not com_rec.text:
                comp_gfx["COMMENT_EMPTY"] = "T"
            if comp_gfx:
                kept[f"comp_gfx:{len(symbols)}"] = comp_gfx
            placed[(key, len(symbols))] = (path, number, record)
            symbols.append(drawn)
            pins_of_sheet.append([p.at for p in pins[(key, "symbol", len(symbols) - 1)]])
        # second pass: the other items, each list in stream order
        sheet_wires: list[tuple[Point, ...]] = []
        sheet_buses: list[tuple[Point, ...]] = []
        entries: list[DrawnBusEntry] = []
        junctions: list[DrawnJunction] = []
        marks: list[Point] = []
        for record in document.all_records():
            if record.owner is not None:
                continue
            where = f"{sheet.input.file}:{record.ref.stream}[{record.ref.index}]"
            name = record_class(record)
            if isinstance(record, Component):
                continue
            if isinstance(record, Wire | Bus):
                points = tuple(frame.point(p) for p in record.points)
                if isinstance(record, Wire) and points in generated.wires:
                    continue  # a member wire of a harness block (``drawn_harness``)
                if len(points) >= 2:
                    (sheet_wires if isinstance(record, Wire) else sheet_buses).append(points)
                continue
            if isinstance(record, BusEntry):
                at = frame.point(record.location)
                end = frame.point(record.corner)
                entries.append(DrawnBusEntry(at, Point(end.x - at.x, end.y - at.y)))
                continue
            if isinstance(record, Junction):
                junctions.append(DrawnJunction(frame.point(record.location)))
                continue
            if isinstance(record, NoErc):
                marks.append(frame.point(record.location))
                continue
            if isinstance(record, NetLabel):
                if (record.text, frame.point(record.location)) in generated.labels:
                    continue
                if record.text:  # a KiCad global label always has a shape: passive, as KiCad reads one
                    shape: DrawnShape = "passive" if label_kind == "global" else ""
                    at = frame.point(record.location)
                    text = record.text
                    kind_on_line = label_harness(document, record, harness)
                    if label_kind == "local" and (
                        harness_entries := members.get(kind_on_line.casefold(), ())
                    ):
                        # a net label that names a harness: KiCad's bus group of its members (c0470)
                        text = group_text(record.text, harness_entries)
                        kept[f"text:{at.x},{at.y}"] = {"TEXT": record.text}
                    if found := item_fields(record, "label"):
                        kept[f"label:{len(labels)}"] = found
                        kept[f"label_at:{label_kind}:{at.x},{at.y}"] = found
                    labels.append(DrawnLabel(label_kind, text, at,
                                             (record.orientation % 4) * QUARTER, shape))  # fmt: skip
                continue
            if isinstance(record, Port):
                if not record.name:
                    opaques.append(DrawnOpaque("", subtree_text(document, record)))
                    continue
                if record.harness_type:
                    label, _ = _port_label(record, frame, harness, port_kind)
                    text = group_text(record.name, members.get(record.harness_type.casefold(), ()))
                    labels.append(DrawnLabel(label.kind, text, label.at, label.rotation, label.shape))
                    if label.at not in generated.ends:
                        opaques.append(DrawnOpaque("", subtree_text(document, record)))
                    continue
                label, both = _port_label(record, frame, wires, port_kind)
                if both:
                    issues.append(_issue("altium.drawn.port-ends", "warning",
                                         "both ends of the port touch a wire; the drawn label keeps "
                                         "the first",
                                         where))  # fmt: skip
                if found := item_fields(record, "label"):
                    kept[f"label:{len(labels)}"] = found
                    kept[f"label_at:{label.kind}:{label.at.x},{label.at.y}"] = found
                labels.append(label)
                continue
            if isinstance(record, PowerPort):
                if not record.text:
                    issues.append(
                        _issue("altium.drawn.unrepresented", "error", "a power port without a net", where)
                    )
                    continue
                style = POWER_STYLES[record.style] if 0 <= record.style < len(POWER_STYLES) else "bar"
                if record.cross_sheet:
                    kept[f"label:{len(labels)}"] = item_fields(record, "power")
                    labels.append(DrawnLabel("global", record.text, frame.point(record.location),
                                             (record.orientation % 4) * QUARTER, "passive"))  # fmt: skip
                    continue
                if found := item_fields(record, "power"):
                    kept[f"power:{len(powers)}"] = found
                if record.props is not None:
                    p_keys = set(record.props.keys())
                    if pstyle := {k: record.props.text(k) for k in ("COLOR", "FONTID") if k in p_keys}:
                        kept[f"power_style:{len(powers)}"] = pstyle
                power_uids.append(record.props.text("UNIQUEID") if record.props is not None else "")
                at = frame.point(record.location)
                # Altium draws the net name by the port's style; the drawn Value sits on the port, shown as
                # the port shows its net name (the Reference of a power symbol is hidden and not drawn)
                fields = (DrawnField("Value", at, 0, "", not record.show_net_name),)
                powers.append(
                    DrawnPower(
                        f"{POWER_LIBRARY}:{style}",
                        record.text,
                        at,
                        (record.orientation % 4) * QUARTER,
                        fields,
                    )  # fmt: skip
                )
                continue
            if isinstance(record, SheetSymbol):
                child_index = (
                    next(
                        (
                            c
                            for c in children_of.get(index, [])
                            if resolved.instances[c].symbol == record.ref.index
                        ),
                        None,
                    )
                    if index is not None
                    else None
                )
                title = next((c.text for c in document.children_of(record) if isinstance(c, SheetName)), "")
                file_name = next(
                    (c.text for c in document.children_of(record) if isinstance(c, SheetFileName)), ""
                )
                if child_index is None:
                    issues.append(_issue("drawn.sheet-unknown", "warning",
                                         f"the sheet symbol {title!r} names {file_name!r}, which is not read",
                                         where))  # fmt: skip
                    opaques.append(DrawnOpaque("", subtree_text(document, record)))
                    continue
                child = resolved.instances[child_index]
                ports = child_harness_ports(data[child.sheet].input.document)
                kinds = {
                    id(entry): entry_harness(document, entry, harness, ports)
                    for entry in document.children_of(record)
                    if isinstance(entry, SheetEntry)
                }
                entries_out = tuple(
                    pin
                    for entry in document.children_of(record)
                    if isinstance(entry, SheetEntry)
                    and (pin := _entry_pin(document, entry, frame, members, kinds[id(entry)])) is not None
                )
                taken_refs = {ref.key for ref in refs}
                ref_key = _ref_key(title or child.names[-1], taken_refs)
                for entry in document.children_of(record):
                    if isinstance(entry, SheetEntry) and (
                        found := lone_harness(entry, kinds[id(entry)], members)
                    ):
                        kept[f"harness:{title or child.names[-1]}:{entry.name}"] = found
                ref_style: dict[str, str] = {}
                if record.props is not None:
                    r_keys = set(record.props.keys())
                    for k in ("COLOR", "AREACOLOR"):
                        if k in r_keys:
                            ref_style[k] = record.props.text(k)
                sname = next((c for c in document.children_of(record) if isinstance(c, SheetName)), None)
                if sname is not None:
                    ref_style["NAME_X"] = str(sname.location[0].value)
                    ref_style["NAME_Y"] = str(sname.location[1].value)
                    if sname.props is not None:
                        s_keys = set(sname.props.keys())
                        for k in ("FONTID", "COLOR"):
                            if k in s_keys:
                                ref_style[f"NAME_{k}"] = sname.props.text(k)
                sfile = next((c for c in document.children_of(record) if isinstance(c, SheetFileName)), None)
                if sfile is not None:
                    ref_style["FILE_X"] = str(sfile.location[0].value)
                    ref_style["FILE_Y"] = str(sfile.location[1].value)
                    if sfile.props is not None:
                        f_keys = set(sfile.props.keys())
                        for k in ("FONTID", "COLOR"):
                            if k in f_keys:
                                ref_style[f"FILE_{k}"] = sfile.props.text(k)
                kept_entries = [
                    entry
                    for entry in document.children_of(record)
                    if isinstance(entry, SheetEntry)
                    and _entry_pin(document, entry, frame, members, kinds[id(entry)]) is not None
                ]
                for entry_idx, entry in enumerate(kept_entries):
                    if entry.props is not None:
                        e_keys = set(entry.props.keys())
                        for k in ("TEXTFONTID", "COLOR", "AREACOLOR", "TEXTCOLOR"):
                            if k in e_keys:
                                ref_style[f"ENTRY_{k}:{entry_idx}"] = entry.props.text(k)
                if ref_style:
                    kept[f"ref:{len(refs)}"] = ref_style
                corner = frame.point(record.location)
                child_module = sheet_modules.get(child.sheet, "")
                rel_module = (
                    (child.names[-1] if child.names else "")
                    if child_module == "/".join(child.names if index == first_instance.get(number) else ())
                    or repeated[child.sheet] > 1
                    else ("" if child_module == module else _relative(child_module, module))
                )
                refs.append(
                    DrawnSheetRef(
                        ref_key,
                        keys[child.sheet],
                        rel_module,
                        title or child.names[-1],
                        corner,
                        Size(
                            max(1, SchLength(record.x_size.value).nm()),
                            max(1, SchLength(record.y_size.value).nm()),
                        ),
                        str(child_index + 1),
                        f"{keys[child.sheet]}.kicad_sch",
                        entries_out,
                    )
                )
                continue
            part = drawn_carrier.part_index(record.name) if isinstance(record, Parameter) else None
            if isinstance(record, Parameter) and record.owner is None and part is not None:
                carrier_parts[part] = record.text  # change c0470, design D4
                continue
            if isinstance(record, Sheet) or (isinstance(record, Parameter)):
                held.append(subtree_text(document, record))
                continue
            if name == "Template":
                held.append(subtree_text(document, record))
                continue
            if isinstance(record, SignalHarness):
                points = tuple(frame.point(p) for p in record.points)
                if points in generated.lines:
                    continue
                if points in generated.networks:  # a KiCad bus of a bus group (``drawn_harness``)
                    sheet_buses.append(points)
                    continue
                if len(points) >= 2:
                    sheet_buses.append(points)
                opaques.append(DrawnOpaque("", subtree_text(document, record)))
                continue
            if isinstance(record, HarnessConnector):
                if frame.point(record.location) in generated.connectors:
                    continue
                kind = next((c.text for c in document.children_of(record) if isinstance(c, HarnessType)), "")
                name = _harness_name(document, record, harness) or kind
                for entry in document.children_of(record):
                    point = entry_point(document, entry) if isinstance(entry, HarnessEntry) else None
                    if point is None or not entry.name:  # type: ignore[union-attr]
                        continue
                    rotation = {SIDE_LEFT: 2, SIDE_RIGHT: 0, SIDE_TOP: 1}.get(entry.side, 3)  # type: ignore[union-attr]
                    labels.append(
                        DrawnLabel(
                            "local",
                            f"{name}.{entry.name}",  # type: ignore[union-attr]
                            frame.point((SchLength(point[0]), SchLength(point[1]))),
                            ((rotation + 2) % 4) * QUARTER,
                        )
                    )
                opaques.append(
                    DrawnOpaque(
                        stand_in(record, frame, item_uuid(sheet.input.file, record)),
                        subtree_text(document, record),
                    )
                )
                continue
            if record.props is None:
                issues.append(_issue("altium.drawn.unrepresented", "error",
                                     f"the {name} record holds no fields", where))  # fmt: skip
                continue
            text = subtree_text(document, record)
            opaques.append(DrawnOpaque(stand_in(record, frame, item_uuid(sheet.input.file, record)), text))
        if carrier_parts:
            try:
                carried = drawn_carrier.KiCadSheet.parse(drawn_carrier.joined(carrier_parts))
            except ValueError as error:
                issues.append(_issue("altium.drawn.unrepresented", "error", str(error), sheet.input.file))
            else:
                opaques += [DrawnOpaque(text) for text in carried.opaques]
                carriers.append(carried)
                if carried.origin is not None:
                    origins[key] = carried.origin
                definitions.update(carried.definitions)
        if carriers:
            labels[:] = drawn_carrier.labels_of([v for c in carriers for v in c.labels], labels)
            powers = _restore_stand_ins(carriers, powers, power_uids, labels, kept)
            poses = {k: v for carrier in carriers for k, v in carrier.symbols.items()}
            symbols = [
                drawn_carrier.symbol_of(poses[k], s) if (k := drawn_carrier.symbol_key(s)) in poses else s
                for s in symbols
            ]
            junctions = drawn_carrier.junctions_of([j for c in carriers for j in c.junctions], junctions)
            refs = drawn_carrier.sheet_refs_of([v for c in carriers for v in c.sheet_refs], refs)
            for index, power in enumerate(powers):
                if power.symbol.partition(":")[2] == drawn_carrier.POWER_FLAG:
                    # KiCad's power flag: one power-output pin at its origin, joined only there
                    pins[(key, "power", index)] = (PinPoint("1", power.at, "power_out", False, "pwr"),)
        stops = [point for points in pins_of_sheet for point in points]
        stops += [power.at for power in powers]
        stops += [pin.at for ref in refs for pin in ref.pins]
        sheet_wires = split_lines(sheet_wires, stops)
        known = {junction.at for junction in junctions}
        added = [point for point in tee_points(sheet_wires) if point not in known]
        junctions += [DrawnJunction(point) for point in added]
        if added:
            issues.append(
                _issue(
                    "altium.drawn.tee",
                    "info",
                    f"{len(added)} wire end(s) of {sheet.input.file} end inside another wire; a junction is "
                    "drawn there, as Altium joins them",
                    sheet.input.file,
                )
            )
        if frame.rounded:
            issues.append(
                _issue(
                    "altium.import.inexact",
                    "info",
                    f"{frame.rounded} length(s) of {sheet.input.file} are not whole nanometres and are "
                    "rounded",
                    sheet.input.file,
                )
            )
        sheet_records[key] = "\n".join(held)
        if any(
            line.startswith("|RECORD=39|")
            or (
                line.startswith("|RECORD=31|")
                and (
                    "|AREACOLOR=" in line or ("|FONTIDCOUNT=" in line and "|FONTIDCOUNT=1|" not in line + "|")
                )
            )
            for line in held
        ):
            kept["__sheet__"] = {"RECORDS": sheet_records[key]}
        classes[key] = dict(sorted(per_class.items()))
        one_spelling(labels, kept)
        if kept:
            extra[key] = kept
        sheets_out.append(
            DrawnSheet(
                key,
                generated.paper or frame.paper,
                _title(document),
                False,
                tuple(symbols),
                tuple(powers),
                tuple(sheet_wires),
                tuple(sheet_buses),
                tuple(entries),
                tuple(junctions),
                tuple(marks),
                tuple(labels),
                tuple(alias for c in carriers for alias in c.bus_aliases),
                tuple(refs),
                tuple(opaques),
            )
        )
    if len(tops) == 1:
        root = keys[tops[0].sheet]
    else:
        root = _sheet_key("project", taken)
        top_refs: list[DrawnSheetRef] = []
        names: set[str] = set()
        x = 2_540_000
        for top in tops:
            ref_key = _ref_key(keys[top.sheet], names)
            top_refs.append(
                DrawnSheetRef(ref_key, keys[top.sheet], "", keys[top.sheet], Point(x, 2_540_000),
                              Size(25_400_000, 12_700_000), str(top.index + 1),
                              f"{keys[top.sheet]}.kicad_sch")
            )  # fmt: skip
            x += 30_480_000
        sheets_out.insert(0, DrawnSheet(root, "A4", (), False, sheet_refs=tuple(top_refs)))
        extra[root] = {TOPS_KEY: {TOPS_FIELD: "T"}}  # no document of the source: its carrier says so (c0470)
        issues.append(
            _issue(
                "altium.drawn.top-sheets",
                "info",
                f"the project has {len(tops)} top sheets; the drawing adds the root sheet {root} that "
                "refers to each",
                root,
            )
        )
    drawing = DrawnSchematic(root, tuple(sheets_out))
    return Extracted(
        drawing,
        MappingProxyType(pins),
        tuple(issues),
        MappingProxyType(sheet_records),
        MappingProxyType(dict(counts)),
        MappingProxyType(classes),
        MappingProxyType(files),
        MappingProxyType(extra),
        MappingProxyType(placed),
        MappingProxyType(origins),
        MappingProxyType(definitions),
    )


def extract(
    sheets: Sequence[SheetInput], *, components: Mapping[str, str] | None = None
) -> tuple[DrawnSchematic, tuple[Issue, ...]]:
    """The drawn schematic of read Altium documents and its issues. ``components`` maps a designator to its
    component path (the designator, below the sheet symbols of its instance, when it is left out)."""
    found = extract_with_pins(sheets, components=components)
    return found.drawn, found.issues


__all__ = [
    "label_harness",
    "PROJECT_FIELD",
    "TOPS_FIELD",
    "TOPS_KEY",
    "EVIDENCE",
    "ITEM_FIELDS",
    "KINDS",
    "MODELLED",
    "POWER_LIBRARY",
    "POWER_STYLES",
    "RECORD_KINDS",
    "Extracted",
    "Frame",
    "extract",
    "extract_with_pins",
    "frame_of",
    "child_harness_ports",
    "entry_harness",
    "item_fields",
    "lone_harness",
    "one_spelling",
    "item_uuid",
    "opaque_kind",
    "record_class",
    "record_line",
    "stand_in",
    "subtree_text",
]

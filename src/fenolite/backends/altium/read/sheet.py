# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Import of an Altium sheet template (``.SchDot``, or the template graphics of a ``.SchDoc``) into the
neutral drawing sheet (change c0046, capability ``sheet-templates``).

``import_sheet(data)`` reads the bytes with ``read.sch.read_schematic`` and returns a ``SheetImport``: a
``DrawingSheet`` of corner-anchored lines, rectangles, texts and PNG bitmaps, where the sheet came from, and a
report that accounts for every template record. The form is taken from the content, never from a file name.
Nothing is written, no other file is opened, and no clock, random generator or environment value is used.

Facts and Fenolite's own rules (centring, anchoring, text size, border, rounding):
``docs/formats/altium/sheet-template.md``. Every format fact is ``INFERRED``; see ``EVIDENCE``.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

from fenolite.backends.altium.read.sch import (
    RECORD_TYPES,
    Image,
    Label,
    Line,
    Parameter,
    Polygon,
    Polyline,
    PropertyList,
    Rectangle,
    SchDocument,
    SchLength,
    SchRecord,
    Sheet,
    Template,
    read_schematic,
)
from fenolite.core.errors import FenoliteError, FormatError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm
from fenolite.model.presentation import (
    PAPER_SIZES,
    PARAM_NAME,
    Corner,
    DrawingSheet,
    HJustify,
    PaperSize,
    SheetBitmap,
    SheetItem,
    SheetPoint,
    SheetSetup,
    SheetShape,
    SheetText,
    VJustify,
)

SHEET_STYLES: tuple[tuple[int, int, PaperSize], ...] = (
    (1150, 760, "A4"),
    (1550, 1110, "A3"),
    (2230, 1570, "A2"),
    (3150, 2230, "A1"),
    (4460, 3150, "A0"),
    (950, 750, "custom"),
    (1500, 950, "custom"),
    (2000, 1500, "custom"),
    (3200, 2000, "custom"),
    (4200, 3200, "custom"),
    (1100, 850, "Letter"),
    (1400, 850, "Legal"),
    (1700, 1100, "Tabloid"),
    (990, 790, "custom"),
    (1540, 990, "custom"),
    (2060, 1560, "custom"),
    (3260, 2060, "custom"),
    (4280, 3280, "custom"),
)
"""Per ``SHEETSTYLE`` 0 to 17: the drawing area's width and height in units of 10 mil, landscape, and the
neutral paper (``H-A-RD-SHT-AREA``)."""

LINE_WIDTHS: Mapping[int, Nm] = MappingProxyType({0: 102_000, 1: 254_000, 2: 508_000, 3: 1_016_000})
"""``LINEWIDTH`` 0 (or missing) to 3: 4, 10, 20 and 40 mil, to the micrometre (``H-A-RD-SHT-WIDTH``)."""

ALTIUM_SHEET_TOKENS: Mapping[str, str] = MappingProxyType(
    {
        "Title": "title",
        "DocumentNumber": "doc_id",
        "Revision": "revision",
        "SheetNumber": "sheet",
        "SheetTotal": "sheets",
        "Date": "date",
        "Organization": "organization",
        "DrawnBy": "responsible",
        "ApprovedBy": "approver",
        "DocumentName": "filename",
    }
)
"""The special-string names that map to a neutral token, matched without regard to letter case
(``H-A-RD-SHT-STRINGS``). No name gives ``paper``."""

DYNAMIC_STRINGS: frozenset[str] = frozenset(
    {
        "CurrentDate",
        "CurrentTime",
        "ModifiedDate",
        "Time",
        "DocumentFullPathAndName",
        "ImagePath",
        "Application_BuildNumber",
        "VariantName",
        "Rule",
    }
)
"""Special-string names whose value a tool computes; kept as parameters and reported."""

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "altium.sheet.not-representable": "warning",
        "altium.sheet.not-template-content": "warning",
        "altium.sheet.builtin-not-drawn": "warning",
        "altium.sheet.outside": "warning",
        "altium.sheet.image-not-kept": "warning",
        "altium.sheet.image-size": "warning",
        "altium.sheet.unknown-string": "warning",
        "altium.sheet.dynamic-string": "warning",
        "altium.sheet.style-dropped": "warning",
        "altium.sheet.appearance": "info",
        "altium.sheet.rounded": "info",
        "altium.sheet.builtin-drawn": "info",
    }
)
"""Every issue code of the import with its severity. A warning is a loss."""

HYPOTHESES = (
    "H-A-RD-SHT-AREA",
    "H-A-RD-SHT-BORDER",
    "H-A-RD-SHT-IMAGE",
    "H-A-RD-SHT-OWNER",
    "H-A-RD-SHT-SAME",
    "H-A-RD-SHT-STRINGS",
    "H-A-RD-SHT-TEXT",
    "H-A-RD-SHT-WIDTH",
)
EVIDENCE = Evidence(Level.INFERRED, hypotheses=HYPOTHESES)
"""The import is inferred from public sources; no second reader of an Altium schematic exists as an oracle."""

NOT_REPRESENTABLE: Mapping[int, str] = MappingProxyType(
    {
        5: "Bezier",
        8: "ellipse",
        9: "pie",
        10: "rounded rectangle",
        11: "elliptical arc",
        12: "arc",
        28: "text frame",
        209: "note",
    }
)
"""Graphic record kinds that have no neutral item."""
KIND_NAMES: Mapping[int, str] = MappingProxyType(
    {4: "label", 6: "polyline", 7: "polygon", 13: "line", 14: "rectangle", 30: "image", **NOT_REPRESENTABLE}
)
TEMPLATE_KIND = 39
PARAMETER_KIND = 41
UM = 1_000
NM_PER_INCH = 25_400_000
POINTS_PER_INCH = 72
DEFAULT_FONT_SIZE = 10
"""The size used when the sheet has no font table entry for the system font (a Fenolite choice)."""
SETUP_LINE_WIDTH: Nm = 254_000
SETUP_TEXT_LINE_WIDTH: Nm = 127_000
BORDER_WIDTH: Nm = 254_000
MAX_LETTER_ZONES = 26
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
COLOUR_KEYS = ("COLOR", "AREACOLOR", "TEXTCOLOR")
LOSS_HINT = (
    "pass --allow-lossy (allow_lossy=True) to import what the neutral sheet can hold; read 'issues' for "
    "what is left out"
)
_JUSTIFY: tuple[tuple[VJustify, HJustify], ...] = tuple(
    (v, h) for v in ("bottom", "center", "top") for h in ("left", "center", "right")
)
"""``JUSTIFICATION`` 0 to 8: bottom, center, top by left, center, right (``H-A-RD-SHT-TEXT``)."""
_FOLDED_TOKENS = {name.casefold(): token for name, token in ALTIUM_SHEET_TOKENS.items()}
_FOLDED_DYNAMIC = frozenset(name.casefold() for name in DYNAMIC_STRINGS)

XY = tuple[Nm, Nm]


class SheetLossError(FenoliteError):
    """The import would leave something out and ``allow_lossy`` is not set (FEN-7001). ``issues`` holds every
    issue of the import, in record order."""

    cli_code = "FEN-7001"

    def __init__(self, issues: tuple[Issue, ...]) -> None:
        self.issues = issues
        self.hint = LOSS_HINT
        losses = [issue for issue in issues if issue.severity == "warning"]
        more = f" (and {len(losses) - 1} more)" if len(losses) > 1 else ""
        super().__init__(f"the import would lose content: {losses[0].message}{more}")


@dataclass(frozen=True, slots=True)
class SheetSource:
    """Where the sheet came from: the file's ``form``, the ``SHEETSTYLE`` number (``None`` for a custom
    sheet), the neutral ``paper``, the orientation, and the drawing area as oriented (nm)."""

    form: Literal["binary", "ascii"]
    style: int | None
    paper: PaperSize
    portrait: bool
    width: Nm
    height: Nm


@dataclass(frozen=True, slots=True)
class SheetImport:
    """The result of ``import_sheet``. ``imported`` maps a record kind to the number of its records that
    gave at least one item; ``reported`` lists the ``where`` of the records that gave none, in record order;
    ``strings`` pairs each distinct special string with its neutral text; ``parameters`` holds the names of
    the sheet-level parameters, without their values."""

    sheet: DrawingSheet
    source: SheetSource
    issues: tuple[Issue, ...]
    imported: dict[int, int] = field(default_factory=dict[int, int])
    reported: tuple[str, ...] = ()
    strings: tuple[tuple[str, str], ...] = ()
    parameters: tuple[str, ...] = ()


# --- lengths ------------------------------------------------------------------------------------------------


def _round_um(length: SchLength) -> tuple[Nm, bool]:
    """``length`` in nanometres, rounded to the nearest micrometre, half to even, and whether it rounded. One
    step of ``SchLength.value`` is 127/50 nm, so a micrometre is 50 000/127 steps."""
    quotient, remainder = divmod(length.value * 127, 50 * UM)
    if remainder * 2 > 50 * UM or (remainder * 2 == 50 * UM and quotient % 2 == 1):
        quotient += 1
    return quotient * UM, remainder != 0


def _text_size(size: int) -> Nm:
    """A font size as a text size: ``size`` points in nanometres, rounded to the nearest micrometre (a
    Fenolite choice, ``H-A-RD-SHT-TEXT``)."""
    quotient, remainder = divmod(size * NM_PER_INCH, POINTS_PER_INCH * UM)
    if remainder * 2 > POINTS_PER_INCH * UM or (remainder * 2 == POINTS_PER_INCH * UM and quotient % 2 == 1):
        quotient += 1
    return quotient * UM


def _floor_um(value: int) -> Nm:
    return value - value % UM


def _length(props: PropertyList, key: str) -> SchLength:
    return SchLength.of(props.int(key), props.int(f"{key}_FRAC"))


# --- the import ---------------------------------------------------------------------------------------------


@dataclass(slots=True)
class _Fonts:
    sizes: dict[int, int]
    bold: dict[int, bool]
    italic: dict[int, bool]
    underline: dict[int, bool]
    system: int

    def pick(self, font_id: int) -> int:
        """``font_id`` when the table holds it, else the system font."""
        return font_id if font_id in self.sizes else self.system

    def size(self, font_id: int) -> Nm:
        return _text_size(self.sizes.get(self.pick(font_id), DEFAULT_FONT_SIZE))


@dataclass(slots=True)
class _Import:
    """The state of one import: the drawing area, the items and the report."""

    document: SchDocument
    width: Nm
    height: Nm
    fonts: _Fonts
    items: list[SheetItem] = field(default_factory=list[SheetItem])
    issues: list[Issue] = field(default_factory=list[Issue])
    imported: dict[int, int] = field(default_factory=dict[int, int])
    reported: list[str] = field(default_factory=list[str])
    strings: dict[str, str] = field(default_factory=dict[str, str])
    parameters: set[str] = field(default_factory=set[str])
    rounded: int = 0
    pending: int = 0
    coloured: int = 0

    # --- report -------------------------------------------------------------------------------------------

    def issue(self, code: str, message: str, where: str) -> None:
        self.issues.append(Issue(code, ISSUE_CODES[code], message, where))

    def refuse(self, code: str, record: SchRecord, kind: int | None, message: str) -> None:
        """Report ``record`` as not imported."""
        where = _where(record)
        self.issue(code, f"{_kind_name(kind)}: {message}", where)
        self.reported.append(where)

    def accept(self, record: SchRecord, kind: int, items: list[SheetItem]) -> None:
        self.items += items
        self.imported[kind] = self.imported.get(kind, 0) + 1
        self.rounded += self.pending
        if record.props is not None and any(record.props.has(key) for key in COLOUR_KEYS):
            self.coloured += 1

    # --- geometry -----------------------------------------------------------------------------------------

    def nm(self, length: SchLength) -> Nm:
        value, rounded = _round_um(length)
        self.pending += rounded
        return value

    def xy(self, point: tuple[SchLength, SchLength]) -> XY:
        return (self.nm(point[0]), self.nm(point[1]))

    def inside(self, points: list[XY]) -> bool:
        return all(0 <= x <= self.width and 0 <= y <= self.height for x, y in points)

    def corner(self, points: list[XY]) -> Corner:
        """The corner nearest to the centre of the bounding box of ``points``."""
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        left = min(xs) + max(xs) < self.width
        bottom = min(ys) + max(ys) < self.height
        if left:
            return "lb" if bottom else "lt"
        return "rb" if bottom else "rt"

    def point(self, corner: Corner, xy: XY) -> SheetPoint:
        """``xy``, measured from the bottom-left corner with y upwards, as an offset from ``corner``."""
        x, y = xy
        return SheetPoint(
            corner,
            x if corner[0] == "l" else self.width - x,
            y if corner[1] == "b" else self.height - y,
        )

    def segments(self, points: list[XY], width: Nm, corner: Corner | None = None) -> list[SheetItem]:
        """One line per pair of consecutive points, all anchored to one corner."""
        chosen = corner or self.corner(points)
        return [
            SheetShape("line", self.point(chosen, start), self.point(chosen, end), width=width)
            for start, end in zip(points, points[1:], strict=False)
        ]


def _where(record: SchRecord) -> str:
    stream = "record" if record.ref.stream == "main" else record.ref.stream
    return f"{stream}[{record.ref.index}]"


def _kind_name(kind: int | None) -> str:
    if kind is None:
        return "a record without a kind"
    name = KIND_NAMES.get(kind)
    if name is None:
        cls = RECORD_TYPES.get(kind)
        name = cls.__name__ if cls is not None else "unknown"
    return f"record kind {kind} ({name})"


def _source(document: SchDocument, sheet: Sheet) -> tuple[SheetSource, SheetSetup, int]:
    """The paper, the orientation, the drawing area and the setup of ``sheet``, and the number of lengths of
    a custom size that were rounded."""
    props = sheet.props
    assert props is not None
    style: int | None
    paper: PaperSize
    rounded = 0
    if props.bool("USECUSTOMSHEET"):
        style, paper = None, "custom"
        sizes = [_round_um(_length(props, key)) for key in ("CUSTOMX", "CUSTOMY")]
        rounded = sum(changed for _, changed in sizes)
        width, height = sizes[0][0], sizes[1][0]
    else:
        style = props.int("SHEETSTYLE")
        if not 0 <= style < len(SHEET_STYLES):
            raise FormatError(
                f"sheet style {style} is not one of the {len(SHEET_STYLES)} known styles (0 to 17)",
                file=document.file,
                locator="record[0].SHEETSTYLE",
            )
        units_x, units_y, paper = SHEET_STYLES[style]
        width, height = _round_um(SchLength.of(units_x))[0], _round_um(SchLength.of(units_y))[0]
    portrait = props.int("WORKSPACEORIENTATION") == 1
    if portrait:
        width, height = height, width
    left = top = 0
    if paper != "custom":
        page_w, page_h = PAPER_SIZES[paper]
        if not portrait:
            page_w, page_h = page_h, page_w
        spare_x, spare_y = page_w - width, page_h - height
        if spare_x < 0 or spare_y < 0 or spare_x % (2 * UM) or spare_y % (2 * UM):
            paper = "custom"
        else:
            left, top = spare_x // 2, spare_y // 2
    fonts = _fonts(sheet)
    size = _text_size(fonts.sizes.get(fonts.system, DEFAULT_FONT_SIZE))
    setup = SheetSetup(
        text_size=(size, size),
        line_width=SETUP_LINE_WIDTH,
        text_line_width=SETUP_TEXT_LINE_WIDTH,
        left_margin=left,
        right_margin=left,
        top_margin=top,
        bottom_margin=top,
    )
    return SheetSource(document.form, style, paper, portrait, width, height), setup, rounded


def _fonts(sheet: Sheet) -> _Fonts:
    table = sheet.fonts
    return _Fonts(
        {font.index: font.size for font in table if font.size > 0},
        {font.index: font.bold for font in table},
        {font.index: font.italic for font in table},
        {font.index: font.underline for font in table},
        sheet.system_font,
    )


def _template_records(document: SchDocument) -> tuple[list[SchRecord], list[SchRecord]]:
    """The template records of the main stream, in file order, and the records of ``Additional`` that no
    record of ``Additional`` owns. A template record has no owner, or its owner is a template record of
    kind 39 (``H-A-RD-SHT-OWNER``)."""
    chosen: set[int] = set()
    out: list[SchRecord] = []
    for record in document.records[1:]:
        owner = record.owner
        if owner is None or (
            owner.stream == "main"
            and owner.index in chosen
            and document.records[owner.index].record_id == TEMPLATE_KIND
        ):
            chosen.add(record.ref.index)
            out.append(record)
    extra = [r for r in document.additional if r.owner is None or r.owner.stream != "additional"]
    return out, extra


# --- border and zones -----------------------------------------------------------------------------------


def _border(state: _Import, sheet: Sheet) -> None:
    """The border and the reference zones of a custom sheet, or the warnings for what no source gives
    (``H-A-RD-SHT-BORDER``)."""
    props = sheet.props
    assert props is not None
    border, zones = props.bool("BORDERON"), props.bool("REFERENCEZONESON")
    custom = props.bool("USECUSTOMSHEET")
    drawn = False
    if border:
        margin, rounded = _round_um(_length(props, "CUSTOMMARGINWIDTH"))
        if not custom:
            state.issue(
                "altium.sheet.builtin-not-drawn",
                "the border of a standard sheet style is not drawn: no public source gives its margin",
                "record[0].BORDERON",
            )
        elif margin <= 0 or 2 * margin >= min(state.width, state.height):
            state.issue(
                "altium.sheet.builtin-not-drawn",
                f"the border is not drawn: a margin width of {margin} nm leaves no border to draw",
                "record[0].BORDERON",
            )
        else:
            drawn = True
            state.rounded += rounded
            for inset in (0, margin):
                state.items.append(
                    SheetShape(
                        "rect",
                        SheetPoint("lt", inset, inset),
                        SheetPoint("rb", inset, inset),
                        width=BORDER_WIDTH,
                    )
                )
            state.issue(
                "altium.sheet.builtin-drawn",
                f"the border is drawn from the sheet flags with a margin of {margin} nm; its tick and label "
                "rule is Fenolite's",
                "record[0].BORDERON",
            )
            if zones:
                _zones(state, props, margin)
    if zones and border and not drawn:
        state.issue(
            "altium.sheet.builtin-not-drawn",
            "the reference zones are not drawn: they lie in the border, which is not drawn",
            "record[0].REFERENCEZONESON",
        )
    if props.bool("TITLEBLOCKON"):
        state.issue(
            "altium.sheet.builtin-not-drawn",
            "the built-in title-block is not drawn: its geometry is the tool's, not the file's",
            "record[0].TITLEBLOCKON",
        )


def _zones(state: _Import, props: PropertyList, margin: Nm) -> None:
    nx, ny = props.int("CUSTOMXZONES"), props.int("CUSTOMYZONES")
    if nx < 1 or not 1 <= ny <= MAX_LETTER_ZONES:
        state.issue(
            "altium.sheet.builtin-not-drawn",
            f"the reference zones are not drawn: {nx} by {ny} zones (1 or more across, 1 to "
            f"{MAX_LETTER_ZONES} down are drawn)",
            "record[0].REFERENCEZONESON",
        )
        return
    width, height = state.width, state.height
    xs = [_floor_um(i * width // nx) for i in range(nx + 1)]
    ys = [_floor_um(j * height // ny) for j in range(ny + 1)]  # measured from the top
    for x in xs[1:-1]:
        state.items += state.segments([(x, height), (x, height - margin)], BORDER_WIDTH)
    for x in xs[1:-1]:
        state.items += state.segments([(x, 0), (x, margin)], BORDER_WIDTH)
    for y in ys[1:-1]:
        state.items += state.segments([(0, height - y), (margin, height - y)], BORDER_WIDTH)
    for y in ys[1:-1]:
        state.items += state.segments([(width, height - y), (width - margin, height - y)], BORDER_WIDTH)
    size = _floor_um(margin // 2)
    half = _floor_um(margin // 2)

    def text(value: str, xy: XY) -> None:
        state.items.append(
            SheetText(
                value,
                state.point(state.corner([xy]), xy),
                size=(size, size),
                justify="center",
                vjustify="center",
            )
        )

    centres_x = [_floor_um((a + b) // 2) for a, b in zip(xs, xs[1:], strict=False)]
    centres_y = [_floor_um((a + b) // 2) for a, b in zip(ys, ys[1:], strict=False)]
    for band_y in (height - half, half):
        for number, x in enumerate(centres_x, start=1):
            text(str(number), (x, band_y))
    for band_x in (half, width - half):
        for number, y in enumerate(centres_y):
            text(chr(ord("A") + number), (band_x, height - y))


# --- graphics -------------------------------------------------------------------------------------------


def _line_width(state: _Import, record: SchRecord, kind: int) -> Nm:
    assert record.props is not None
    value = record.props.int("LINEWIDTH")
    width = LINE_WIDTHS.get(value)
    if width is None:
        state.issue(
            "altium.sheet.style-dropped",
            f"{_kind_name(kind)}: line-width {value} is unknown; drawn 254 000 nm wide",
            _where(record),
        )
        return LINE_WIDTHS[1]
    return width


def _dropped(state: _Import, record: SchRecord, kind: int, what: str, detail: str) -> None:
    state.issue(
        "altium.sheet.style-dropped", f"{_kind_name(kind)}: {what} dropped ({detail})", _where(record)
    )


def _shape(state: _Import, record: Line | Rectangle, kind: int) -> None:
    points = [state.xy(record.location), state.xy(record.corner)]
    if not state.inside(points):
        state.refuse("altium.sheet.outside", record, kind, "a point lies outside the drawing area")
        return
    assert record.props is not None
    width = _line_width(state, record, kind)
    if record.props.int("LINESTYLE") != 0:
        _dropped(state, record, kind, "line-style", "drawn solid")
    if isinstance(record, Rectangle) and record.solid:
        _dropped(state, record, kind, "fill", "drawn as an outline")
    corner = state.corner(points)
    shape = SheetShape(
        "line" if isinstance(record, Line) else "rect",
        state.point(corner, points[0]),
        state.point(corner, points[1]),
        width=width,
    )
    state.accept(record, kind, [shape])


def _path(state: _Import, record: Polyline | Polygon, kind: int) -> None:
    points = [state.xy(point) for point in record.points]
    if len(points) < 2:
        state.refuse(
            "altium.sheet.not-representable", record, kind, f"{len(points)} point(s) give no line to draw"
        )
        return
    if not state.inside(points):
        state.refuse("altium.sheet.outside", record, kind, "a point lies outside the drawing area")
        return
    assert record.props is not None
    width = _line_width(state, record, kind)
    if record.props.int("LINESTYLE") != 0:
        _dropped(state, record, kind, "line-style", "drawn solid")
    if record.props.int("STARTLINESHAPE") != 0 or record.props.int("ENDLINESHAPE") != 0:
        _dropped(state, record, kind, "line-end shape", "drawn without arrowheads")
    corner = state.corner(points)
    if isinstance(record, Polygon):
        if record.solid:
            _dropped(state, record, kind, "fill", "drawn as an outline")
        points = [*points, points[0]]
    state.accept(record, kind, state.segments(points, width, corner))


def neutral_text(text: str) -> tuple[str, str]:
    """The neutral text of a label's ``text`` and what it is: ``"token"`` or ``"param"`` for a special string
    that maps to a token or a parameter, ``"dynamic"`` for one whose value a tool computes, ``"unknown"`` for
    a text that starts with ``=`` without a parameter name, and ``"literal"`` otherwise. Literal braces are
    doubled (``H-A-RD-SHT-STRINGS``)."""
    literal = text.replace("{", "{{").replace("}", "}}")
    if not text.startswith("="):
        return literal, "literal"
    name = text[1:]
    if PARAM_NAME.fullmatch(name) is None:
        return literal, "unknown"
    folded = name.casefold()
    if folded in _FOLDED_DYNAMIC:
        return f"{{param:{name}}}", "dynamic"
    token = _FOLDED_TOKENS.get(folded)
    if token is not None:
        return f"{{{token}}}", "token"
    return f"{{param:{name}}}", "param"


def _label(state: _Import, record: Label, kind: int) -> None:
    position = state.xy(record.location)
    if not state.inside([position]):
        state.refuse("altium.sheet.outside", record, kind, "its anchor lies outside the drawing area")
        return
    source = record.text
    text, what = neutral_text(source)
    where = _where(record)
    if what == "unknown":
        state.issue(
            "altium.sheet.unknown-string",
            f"{_kind_name(kind)}: the text starts with '=' but names no parameter; kept as literal text",
            where,
        )
    elif what == "dynamic":
        state.issue(
            "altium.sheet.dynamic-string",
            f"{_kind_name(kind)}: the value of {source} is computed by the source tool; kept as {text}",
            where,
        )
    if what in ("token", "param", "dynamic"):
        state.strings[source] = text
    justification = record.justification
    if not 0 <= justification < len(_JUSTIFY):
        _dropped(state, record, kind, f"justification {justification}", "anchored bottom-left")
        justification = 0
    vjustify, justify = _JUSTIFY[justification]
    font = state.fonts.pick(record.font_id)
    if state.fonts.underline.get(font, False):
        _dropped(state, record, kind, "underline", "drawn without it")
    if record.mirrored:
        _dropped(state, record, kind, "mirror", "drawn unmirrored")
    size = state.fonts.size(record.font_id)
    item = SheetText(
        text,
        state.point(state.corner([position]), position),
        size=(size, size),
        bold=state.fonts.bold.get(font, False),
        italic=state.fonts.italic.get(font, False),
        justify=justify,
        vjustify=vjustify,
        rotation=(record.orientation % 4) * 90_000_000,
    )
    state.accept(record, kind, [item])


def _base_name(path: str) -> str:
    """The last component of a Windows or POSIX path: folders may hold a user's or an organisation's name."""
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def _image(state: _Import, record: Image, kind: int) -> None:
    name = _base_name(record.file_name)

    def not_kept(reason: str) -> None:
        state.refuse("altium.sheet.image-not-kept", record, kind, f"not kept ({reason}): {name}")

    if not record.embedded:
        not_kept("linked")
        return
    found = state.document.image_data(record)
    if found is None:
        not_kept("missing")
        return
    try:
        data = found.data()
    except FormatError:
        not_kept("missing")
        return
    if not data.startswith(PNG_SIGNATURE):
        not_kept("not-png")
        return
    low, high = state.xy(record.location), state.xy(record.corner)
    if not state.inside([low, high]):
        state.refuse("altium.sheet.outside", record, kind, "a corner lies outside the drawing area")
        return
    centre = (_floor_um((low[0] + high[0]) // 2), _floor_um((low[1] + high[1]) // 2))
    bitmap = SheetBitmap(state.point(state.corner([centre]), centre), base64.b64encode(data).decode("ascii"))
    state.issue(
        "altium.sheet.image-size",
        f"{_kind_name(kind)}: the box of {abs(high[0] - low[0])} nm by {abs(high[1] - low[1])} nm is not "
        "kept; the image is drawn at its own size",
        _where(record),
    )
    state.accept(record, kind, [bitmap])


def _record(state: _Import, record: SchRecord) -> None:
    kind = record.record_id
    state.pending = 0
    if isinstance(record, Template):
        return
    if isinstance(record, Parameter):
        name = record.name
        if name:
            state.parameters.add(name)
        return
    if isinstance(record, Line | Rectangle) and kind is not None:
        _shape(state, record, kind)
    elif isinstance(record, Polyline | Polygon) and kind is not None:
        _path(state, record, kind)
    elif isinstance(record, Label) and kind is not None:
        _label(state, record, kind)
    elif isinstance(record, Image) and kind is not None:
        _image(state, record, kind)
    elif kind in NOT_REPRESENTABLE:
        state.refuse("altium.sheet.not-representable", record, kind, "the neutral sheet has no such item")
    else:
        children = sum(1 for _ in state.document.walk(record)) - 1
        state.refuse(
            "altium.sheet.not-template-content",
            record,
            kind,
            f"not sheet graphics; left out with its {children} owned record(s)",
        )


def _check_accounting(state: _Import, records: list[SchRecord]) -> None:
    """Every template record other than kind 39 and a sheet-level kind 41 is counted exactly once."""
    drawable = [r for r in records if not isinstance(r, Template | Parameter)]
    main = [where for where in state.reported if where.startswith("record[")]
    if sum(state.imported.values()) + len(main) != len(drawable) or len(set(main)) != len(main):
        raise AssertionError(
            f"sheet import accounting: {len(drawable)} template records, "
            f"{sum(state.imported.values())} imported and {len(main)} reported"
        )


def import_sheet(
    data: bytes, *, file: str = "", name: str = "imported", allow_lossy: bool = False
) -> SheetImport:
    """Import the bytes of an Altium sheet template, or of a schematic with an applied template, into a
    neutral ``DrawingSheet``. ``file`` labels errors only: the form is taken from the content. Raises
    ``FormatError`` when the reader refuses the bytes, when record 0 is not the sheet record or when the
    sheet style is unknown, and ``SheetLossError`` when a warning exists and ``allow_lossy`` is not set."""
    document = read_schematic(data, file=file)
    sheet = document.sheet
    if sheet is None or sheet.props is None:
        raise FormatError("record 0 is not the sheet record (RECORD=31)", file=file, locator="record[0]")
    source, setup, rounded = _source(document, sheet)
    state = _Import(document, source.width, source.height, _fonts(sheet), rounded=rounded)
    _border(state, sheet)
    records, additional = _template_records(document)
    for record in records:
        _record(state, record)
    for record in additional:
        state.pending = 0
        state.refuse(
            "altium.sheet.not-template-content",
            record,
            record.record_id,
            "a record of the Additional stream is not sheet graphics",
        )
    _check_accounting(state, records)
    names = sorted({font.name for font in sheet.fonts if font.name})
    if state.coloured or names:
        state.issue(
            "altium.sheet.appearance",
            f"colours of {state.coloured} record(s) and the font names are not kept: {', '.join(names)}"
            if names
            else f"colours of {state.coloured} record(s) are not kept",
            "",
        )
    if state.rounded:
        state.issue(
            "altium.sheet.rounded", f"{state.rounded} length(s) rounded to the nearest micrometre", ""
        )
    issues = tuple(state.issues)
    if not allow_lossy and any(issue.severity == "warning" for issue in issues):
        raise SheetLossError(issues)
    drawing = DrawingSheet(
        id=derived_id("wks", "altium", name), name=name, setup=setup, items=tuple(state.items)
    )
    return SheetImport(
        sheet=drawing,
        source=source,
        issues=issues,
        imported=dict(sorted(state.imported.items())),
        reported=tuple(state.reported),
        strings=tuple(sorted(state.strings.items())),
        parameters=tuple(sorted(state.parameters)),
    )


__all__ = [
    "ALTIUM_SHEET_TOKENS",
    "DYNAMIC_STRINGS",
    "EVIDENCE",
    "HYPOTHESES",
    "ISSUE_CODES",
    "LINE_WIDTHS",
    "NOT_REPRESENTABLE",
    "SHEET_STYLES",
    "SheetImport",
    "SheetLossError",
    "SheetSource",
    "import_sheet",
    "neutral_text",
]

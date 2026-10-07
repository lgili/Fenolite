# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A neutral drawing sheet written as an Altium sheet template (``.SchDot``) and as the frame of a built
schematic (capability sheet-templates, "Altium sheet template writing"; change c0087).

``sheet_frame`` draws a ``DrawingSheet`` on one page, as ``templates.layout`` predicts it, and returns the
root records (polylines and labels), the fonts they need and the size of the custom sheet as a
``SheetFrame``. ``write_template`` puts them into a schematic document without components;
``schdoc.schdoc_records`` appends them to a built sheet. It is the inverse of ``read.sheet.import_sheet``
inside the written scope of ``docs/sheet-templates.md``.

Facts and choices: ``docs/formats/altium/sheet-template.md``, "Writing a template". A part the form cannot
carry is reported with the import's ``altium.sheet.*`` codes, and a warning needs ``allow_lossy``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from fenolite.backends.altium.ascii import Field, encode_records, text_problem
from fenolite.backends.altium.binary import (
    FILE_HEADER_STREAM,
    STORAGE_STREAM,
    file_header_stream,
    storage_stream,
)
from fenolite.backends.altium.cfb import write_compound
from fenolite.backends.altium.read.sheet import (
    ALTIUM_SHEET_TOKENS,
    ISSUE_CODES,
    LINE_WIDTHS,
    SheetLossError,
)
from fenolite.backends.altium.schdoc import FONT_NAME, FONT_SIZE, SHEET_COLOR, TEXT_COLOR
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm
from fenolite.model.presentation import (
    DrawingSheet,
    SheetBitmap,
    SheetItem,
    SheetPoint,
    SheetShape,
    SheetText,
    SheetToken,
    split_tokens,
)

EVIDENCE = Evidence(
    Level.INFERRED, hypotheses=("H-A-SCHDOT-OPEN", "H-A-SCHDOT-READBACK", "H-A-SCHDOT-STRINGS")
)
"""Own readback is supporting data; that Altium opens the template and fills its strings waits for Part W
of the author report."""
SCHDOT_KIND = "altium_schdot"
"""The write kind of a sheet template."""
TemplateForm = Literal["binary", "ascii"]
FORMS: tuple[TemplateForm, ...] = ("binary", "ascii")
SPECIAL_STRINGS: Mapping[str, str] = MappingProxyType(
    {token: name for name, token in ALTIUM_SHEET_TOKENS.items()}
)
"""Neutral token → the special string that shows it: the inverse of the import's table. ``paper`` has
none and is written as the paper's name."""
PAPER_TOKEN = "paper"
STEPS_PER_UNIT = 100_000
"""A length is written in 1/100 000 of the 10-mil unit; one step is 127/50 nm."""
NM_PER_INCH = 25_400_000
POINTS_PER_INCH = 72
QUARTER = 90_000_000
SIZE_KEYS = (
    "SHEETSTYLE",
    "USECUSTOMSHEET",
    "CUSTOMX",
    "CUSTOMX_FRAC",
    "CUSTOMY",
    "CUSTOMY_FRAC",
    "WORKSPACEORIENTATION",
    "BORDERON",
    "TITLEBLOCKON",
    "REFERENCEZONESON",
)
"""The keys of a sheet record that a frame replaces or switches off."""
_V_ORDER = ("bottom", "center", "top")
_H_ORDER = ("left", "center", "right")
_FOLDED_SPECIAL = frozenset(name.casefold() for name in ALTIUM_SHEET_TOKENS)

Record = tuple[Field, ...]
Font = tuple[int, bool, bool]
"""Size in points, bold, italic."""
SYSTEM_FONT: Font = (FONT_SIZE, False, False)
"""Font 1 of the schematic writer's sheet record: a text of the drawing sheet in this font names font 1 and
adds no entry, so the table holds each distinct font once (change c0146)."""


def to_steps(length: Nm) -> int:
    """``length`` in file steps, to the nearest step, half to even. A whole micrometre is at most 1.27 nm
    off, so a reader that rounds to the micrometre gets it back."""
    quotient, remainder = divmod(length * 50, 127)
    if remainder * 2 > 127 or (remainder * 2 == 127 and quotient % 2 == 1):
        quotient += 1
    return quotient


def length_fields(key: str, steps: int) -> tuple[Field, ...]:
    """``key`` in whole units and, when it is not zero, ``key_FRAC``."""
    if steps < 0:
        raise ValueError(f"{key}: a negative length ({steps} steps)")
    units, frac = divmod(steps, STEPS_PER_UNIT)
    return ((key, str(units)), (f"{key}_FRAC", str(frac))) if frac else ((key, str(units)),)


def points_of(height: Nm) -> int:
    """The font size of a text ``height`` high: the nearest whole number of points, at least 1 (the inverse
    of the import's text-size rule)."""
    return max(1, (2 * height * POINTS_PER_INCH + NM_PER_INCH) // (2 * NM_PER_INCH))


def width_code(width: Nm) -> int:
    """``LINEWIDTH`` of the nearest of the four widths; the narrower one on a tie."""
    return min(LINE_WIDTHS, key=lambda code: (abs(LINE_WIDTHS[code] - width), code))


@dataclass(frozen=True, slots=True)
class SheetFrame:
    """A drawing sheet drawn on one page: the page in file steps, the fonts of its texts that the sheet
    record does not hold yet (numbered from ``first_font``), and the root records in drawing order, the
    sheet parameters last."""

    width: int
    height: int
    fonts: tuple[Font, ...]
    records: tuple[Record, ...]
    first_font: int = 2

    def sheet_record(self, base: Sequence[Field]) -> list[Field]:
        """``base`` (a sheet record with ``first_font - 1`` fonts) as the custom sheet of this page: the
        fonts appended to its table, the style, the orientation and the built-in border, title block and
        zones removed, and the custom size at the end. ``ValueError`` when the font count differs, or when
        a font of the frame is in the table twice: one that ``base`` holds already, or one the frame names
        twice (change c0146)."""
        keys = dict(base)
        count = keys.get("FONTIDCOUNT")
        if count != str(self.first_font - 1):
            raise ValueError(f"the sheet record holds {count} font(s), not {self.first_font - 1}")
        held: list[Font] = [
            (int(keys.get(f"SIZE{n}", "0")), keys.get(f"BOLD{n}") == "T", keys.get(f"ITALIC{n}") == "T")
            for n in range(1, self.first_font)
            if keys.get(f"FONTNAME{n}") == FONT_NAME
        ]
        for font in self.fonts:
            if font in held:
                size, bold, italic = font
                style = (" bold" if bold else "") + (" italic" if italic else "")
                raise ValueError(f"the font of {size} points{style} would be in the font table twice")
            held.append(font)
        table: list[Field] = []
        for number, (size, bold, italic) in enumerate(self.fonts, start=self.first_font):
            table += [(f"SIZE{number}", str(size)), (f"FONTNAME{number}", FONT_NAME)]
            if bold:
                table.append((f"BOLD{number}", "T"))
            if italic:
                table.append((f"ITALIC{number}", "T"))
        last = f"FONTNAME{self.first_font - 1}"
        record: list[Field] = []
        for key, value in base:
            if key in SIZE_KEYS:
                continue
            if key == "FONTIDCOUNT":
                value = str(self.first_font - 1 + len(self.fonts))
            record.append((key, value))
            if key == last:
                record += table
        record.append(("USECUSTOMSHEET", "T"))
        record += length_fields("CUSTOMX", self.width)
        record += length_fields("CUSTOMY", self.height)
        return record


@dataclass(frozen=True, slots=True)
class FrameResult:
    """What ``sheet_frame`` made: the frame, the issues, and the counts of the written records.
    ``parameters`` are the names of the sheet parameter records, ``strings`` the distinct special strings."""

    frame: SheetFrame
    issues: tuple[Issue, ...]
    lines: int
    texts: int
    parameters: tuple[str, ...]
    strings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TemplateWrite:
    """The bytes of a written template and the ``FrameResult`` they hold."""

    data: bytes
    form: TemplateForm
    result: FrameResult

    @property
    def issues(self) -> tuple[Issue, ...]:
        return self.result.issues


class _Page:
    """The margin box of the sheet on the page; the rules of ``templates.layout`` (``H-K-WKS-CORNER``)."""

    def __init__(self, sheet: DrawingSheet, width: Nm, height: Nm) -> None:
        setup = sheet.setup
        self.width, self.height = width, height
        self.left, self.right = setup.left_margin, width - setup.right_margin
        self.top, self.bottom = setup.top_margin, height - setup.bottom_margin

    def place(self, point: SheetPoint, dx: Nm, dy: Nm) -> tuple[Nm, Nm]:
        """The page point of ``point`` moved by ``(dx, dy)`` in its corner frame, y downwards."""
        x, y = point.x + dx, point.y + dy
        px = self.left + x if point.corner in ("lt", "lb") else self.right - x
        py = self.top + y if point.corner in ("lt", "rt") else self.bottom - y
        return px, py

    def in_box(self, x: Nm, y: Nm) -> bool:
        return self.left <= x <= self.right and self.top <= y <= self.bottom

    def on_page(self, x: Nm, y: Nm) -> bool:
        return 0 <= x <= self.width and 0 <= y <= self.height


def _stepped(text: str, k: int, step: int) -> str:
    """The text of copy ``k``: a one-letter text steps through the alphabet, a number by its value
    (``H-K-WKS-REPEAT``)."""
    if not step or not k:
        return text
    if len(text) == 1 and text.isalpha():
        return chr(ord(text) + k * step)
    if text.isdigit():
        return str(int(text) + k * step)
    return text


class _Frame:
    """The state of one ``sheet_frame`` call."""

    def __init__(self, sheet: DrawingSheet, width: Nm, height: Nm, paper: str, first_font: int) -> None:
        self.sheet = sheet
        self.page = _Page(sheet, width, height)
        self.paper = paper
        self.first_font = first_font
        self.records: list[Record] = []
        self.issues: list[Issue] = []
        self.fonts: list[Font] = []
        self.params: list[str] = []
        self.strings: set[str] = set()
        self.lines = 0
        self.texts = 0
        self.replaced = 0

    def issue(self, code: str, index: int, message: str) -> None:
        self.issues.append(Issue(code, ISSUE_CODES[code], message, where=f"items[{index}]"))

    def xy(self, key_x: str, key_y: str, point: tuple[Nm, Nm]) -> tuple[Field, ...]:
        """A page point (y downwards) as the fields of the file frame (y upwards)."""
        x, y = point
        return (
            *length_fields(key_x, to_steps(x)),
            *length_fields(key_y, to_steps(self.page.height - y)),
        )

    def font(self, font: Font) -> int:
        """The number of ``font`` in the table: 1 for the system font of the writer's sheet record, else
        its place among the fonts of the frame, added on first use."""
        if font == SYSTEM_FONT and self.first_font == 2:
            return 1
        if font not in self.fonts:
            self.fonts.append(font)
        return self.first_font + self.fonts.index(font)

    # --- shapes -------------------------------------------------------------------------------------------

    def shape(self, index: int, item: SheetShape, dx: Nm, dy: Nm) -> None:
        (x1, y1), (x2, y2) = self.page.place(item.start, dx, dy), self.page.place(item.end, dx, dy)
        if not (self.page.on_page(x1, y1) and self.page.on_page(x2, y2)):
            self.issue("altium.sheet.outside", index, f"a {item.kind} reaches past the page; not written")
            return
        width = item.width if item.width is not None else self.sheet.setup.line_width
        code = width_code(width)
        self.replaced += LINE_WIDTHS[code] != width
        points = [(x1, y1), (x2, y2)]
        if item.kind == "rect":
            points = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
        record: list[Field] = [("RECORD", "6"), ("OWNERPARTID", "-1")]
        if code:
            record.append(("LINEWIDTH", str(code)))
        record.append(("LOCATIONCOUNT", str(len(points))))
        for number, point in enumerate(points, start=1):
            record += self.xy(f"X{number}", f"Y{number}", point)
        self.records.append(tuple(record))
        self.lines += len(points) - 1

    # --- texts --------------------------------------------------------------------------------------------

    def written_text(self, index: int, text: str) -> str | None:
        """The text of a label for the neutral ``text``, or ``None`` after reporting why there is none."""
        try:
            parts = list(split_tokens(text))
        except ValueError as error:
            self.issue("altium.sheet.not-representable", index, f"a text is not written: {error}")
            return None
        if not parts:
            return None
        if len(parts) > 1:
            self.issue(
                "altium.sheet.not-representable",
                index,
                f"the text {text!r} mixes a token with other text or holds several tokens; a special "
                "string is one whole text, so it is not written",
            )
            return None
        part = parts[0]
        if isinstance(part, SheetToken):
            if part.param:
                if part.name.casefold() in _FOLDED_SPECIAL:
                    self.issue(
                        "altium.sheet.not-representable",
                        index,
                        f"the parameter {part.name} has the name of a special string and would be read "
                        "back as that string; not written",
                    )
                    return None
                if part.name not in self.params:
                    self.params.append(part.name)
                written = f"={part.name}"
            elif part.name == PAPER_TOKEN:
                return self.paper if text_problem(self.paper) is None else None
            else:
                written = f"={SPECIAL_STRINGS[part.name]}"
            self.strings.add(written)
            return written
        problem = text_problem(part)
        if problem is None and part.startswith("="):
            problem = "starts with '=', which Altium reads as a special string"
        if problem is not None:
            self.issue("altium.sheet.not-representable", index, f"the text {part!r} {problem}; not written")
            return None
        return part

    def text(self, index: int, item: SheetText, k: int, dx: Nm, dy: Nm) -> None:
        position = self.page.place(item.pos, dx, dy)
        if not self.page.on_page(*position):
            self.issue("altium.sheet.outside", index, "the anchor of a text lies outside the page")
            return
        written = self.written_text(index, _stepped(item.text, k, item.repeat.label_step))
        if written is None:
            return
        turns, off = divmod(item.rotation, QUARTER)
        if off:
            turns = (2 * item.rotation + QUARTER) // (2 * QUARTER)
            self.issue(
                "altium.sheet.style-dropped",
                index,
                f"a rotation of {item.rotation} microdegrees is not a quarter turn; written as {turns % 4} "
                "quarter turn(s)",
            )
        for name, value in (("max_len", item.max_len), ("max_height", item.max_height)):
            if value is not None and not k:
                self.issue(
                    "altium.sheet.style-dropped", index, f"{name} of a text is dropped: a label has no limit"
                )
        height = (item.size if item.size is not None else self.sheet.setup.text_size)[1]
        points = points_of(height)
        self.replaced += points * NM_PER_INCH != height * POINTS_PER_INCH
        justification = _V_ORDER.index(item.vjustify) * 3 + _H_ORDER.index(item.justify)
        record: list[Field] = [
            ("RECORD", "4"),
            ("OWNERPARTID", "-1"),
            *self.xy("LOCATION.X", "LOCATION.Y", position),
        ]
        if turns % 4:
            record.append(("ORIENTATION", str(turns % 4)))
        if justification:
            record.append(("JUSTIFICATION", str(justification)))
        record += [("FONTID", str(self.font((points, item.bold, item.italic)))), ("TEXT", written)]
        self.records.append(tuple(record))
        self.texts += 1

    # --- items --------------------------------------------------------------------------------------------

    def item(self, index: int, item: SheetItem) -> None:
        if item.scope == "not_first":
            return
        if isinstance(item, SheetBitmap):
            self.issue(
                "altium.sheet.image-not-kept",
                index,
                "a bitmap is not written: this writer embeds no image (not kept: not-written)",
            )
            return
        repeat = item.repeat
        start = item.start if isinstance(item, SheetShape) else item.pos
        for k in range(max(repeat.count, 1)):
            dx, dy = k * repeat.step_x, k * repeat.step_y
            if not self.page.in_box(*self.page.place(start, dx, dy)):
                break
            if isinstance(item, SheetShape):
                self.shape(index, item, dx, dy)
            else:
                self.text(index, item, k, dx, dy)


def parameter_record(name: str, value: str | None) -> Record:
    """A sheet parameter: record 41 without an owner, hidden, with ``NAME`` and, when it has one, its value
    as ``TEXT``. ``ValueError`` for a name or a value a record cannot hold."""
    for text, what, parameter in ((name, "name", False), (value, "value", True)):
        if text is None:
            continue
        problem = text_problem(text, parameter=parameter)
        if problem is not None:
            raise ValueError(f"the {what} {text!r} of the sheet parameter {name!r} {problem}")
    record: list[Field] = [
        ("RECORD", "41"),
        ("OWNERPARTID", "-1"),
        ("COLOR", TEXT_COLOR),
        ("FONTID", "1"),
        ("ISHIDDEN", "T"),
    ]
    if value is not None:
        record.append(("TEXT", value))
    record.append(("NAME", name))
    return tuple(record)


def sheet_frame(
    sheet: DrawingSheet,
    *,
    width: Nm,
    height: Nm,
    paper: str,
    parameters: Sequence[tuple[str, str]] = (),
    first_font: int = 2,
    allow_lossy: bool = False,
) -> FrameResult:
    """``sheet`` drawn on the first page of a ``width`` by ``height`` page (nm) whose paper is shown as
    ``paper``: polylines and labels in drawing order, repeats written as copies, then one sheet parameter
    record per pair of ``parameters`` (name, value) in the order given and one without a value per
    parameter token that ``parameters`` does not name. With ``first_font`` 2 (the schematic writer's sheet
    record) a text in ``SYSTEM_FONT`` names font 1 and the frame holds only the other fonts.
    ``SheetLossError`` when a part cannot be carried and ``allow_lossy`` is not set; ``ValueError`` for a
    page that is not positive, a parameter named twice or one that a record cannot hold."""
    if width <= 0 or height <= 0:
        raise ValueError(f"a page of {width} nm by {height} nm is not positive")
    names = [name for name, _value in parameters]
    if len(set(names)) != len(names):
        raise ValueError("a sheet parameter is named twice")
    state = _Frame(sheet, width, height, paper, first_font)
    for index, item in enumerate(sheet.items):
        state.item(index, item)
    if state.replaced:
        state.issues.append(
            Issue(
                "altium.sheet.rounded",
                ISSUE_CODES["altium.sheet.rounded"],
                f"{state.replaced} line width(s) and text height(s) replaced by the nearest the form has "
                "(4, 10, 20 or 40 mil; whole points)",
            )
        )
    issues = tuple(state.issues)
    if not allow_lossy and any(found.severity == "warning" for found in issues):
        raise SheetLossError(issues)
    extra = [name for name in state.params if name not in names]
    records = [
        *state.records,
        *(parameter_record(name, value) for name, value in parameters),
        *(parameter_record(name, None) for name in extra),
    ]
    frame = SheetFrame(to_steps(width), to_steps(height), tuple(state.fonts), tuple(records), first_font)
    return FrameResult(
        frame, issues, state.lines, state.texts, (*names, *extra), tuple(sorted(state.strings))
    )


@dataclass(frozen=True, slots=True, order=True)
class ScopeLine:
    """A drawn line inside the written scope: its ends on the page (nm, y downwards, the lower end first)
    and its ``LINEWIDTH`` code."""

    start: tuple[Nm, Nm]
    end: tuple[Nm, Nm]
    width: int


@dataclass(frozen=True, slots=True, order=True)
class ScopeText:
    """A drawn text inside the written scope: its anchor on the page, its neutral text with ``{paper}``
    read as the paper's name, its size in whole points, and its justification, quarter turns and style."""

    x: Nm
    y: Nm
    text: str
    points: int
    justify: str
    vjustify: str
    turns: int
    bold: bool
    italic: bool


def _um(value: Nm) -> Nm:
    """``value`` rounded to the nearest micrometre, half to even."""
    quotient, remainder = divmod(value, 1_000)
    if remainder * 2 > 1_000 or (remainder * 2 == 1_000 and quotient % 2 == 1):
        quotient += 1
    return quotient * 1_000


def _scope_text(text: str, paper: str) -> str:
    try:
        parts = split_tokens(text)
    except ValueError:
        return text
    if len(parts) == 1 and parts[0] == SheetToken(PAPER_TOKEN):
        return paper.replace("{", "{{").replace("}", "}}")
    return text


def written_scope(
    sheet: DrawingSheet, *, width: Nm, height: Nm, paper: str
) -> tuple[tuple[ScopeLine, ...], tuple[ScopeText, ...]]:
    """What a template holds of ``sheet`` on the first page of a ``width`` by ``height`` page, sorted: the
    written scope of ``docs/sheet-templates.md``. Two sheets with equal scopes are drawn alike by this
    writer; a sheet and the import of its written template have equal scopes when the write reports no
    warning. Positions are rounded to the micrometre."""
    page = _Page(sheet, width, height)
    lines: list[ScopeLine] = []
    texts: list[ScopeText] = []
    for item in sheet.items:
        if item.scope == "not_first" or isinstance(item, SheetBitmap):
            continue
        repeat = item.repeat
        start = item.start if isinstance(item, SheetShape) else item.pos
        for k in range(max(repeat.count, 1)):
            dx, dy = k * repeat.step_x, k * repeat.step_y
            if not page.in_box(*page.place(start, dx, dy)):
                break
            if isinstance(item, SheetShape):
                (x1, y1), (x2, y2) = page.place(item.start, dx, dy), page.place(item.end, dx, dy)
                (x1, y1, x2, y2) = (_um(x1), _um(y1), _um(x2), _um(y2))
                code = width_code(item.width if item.width is not None else sheet.setup.line_width)
                ends = [((x1, y1), (x2, y2))]
                if item.kind == "rect":
                    ends = [
                        ((x1, y1), (x2, y1)),
                        ((x2, y1), (x2, y2)),
                        ((x2, y2), (x1, y2)),
                        ((x1, y2), (x1, y1)),
                    ]
                lines += [ScopeLine(min(a, b), max(a, b), code) for a, b in ends]
            else:
                x, y = page.place(item.pos, dx, dy)
                text = _stepped(item.text, k, repeat.label_step)
                if not text:
                    continue
                size = item.size if item.size is not None else sheet.setup.text_size
                turns = ((2 * item.rotation + QUARTER) // (2 * QUARTER)) % 4
                texts.append(
                    ScopeText(
                        _um(x),
                        _um(y),
                        _scope_text(text, paper),
                        points_of(size[1]),
                        item.justify,
                        item.vjustify,
                        turns,
                        item.bold,
                        item.italic,
                    )
                )
    return tuple(sorted(lines)), tuple(sorted(texts))


def base_sheet_record() -> list[Field]:
    """The sheet record of a template before its frame: the one font, the grids and the colour of the
    schematic writer's sheet record, without a size."""
    return [
        ("RECORD", "31"),
        ("FONTIDCOUNT", "1"),
        ("SIZE1", str(FONT_SIZE)),
        ("FONTNAME1", FONT_NAME),
        ("SYSTEMFONT", "1"),
        ("SNAPGRIDON", "T"),
        ("SNAPGRIDSIZE", "10"),
        ("VISIBLEGRIDON", "T"),
        ("VISIBLEGRIDSIZE", "10"),
        ("HOTSPOTGRIDON", "T"),
        ("HOTSPOTGRIDSIZE", "4"),
        ("DISPLAY_UNIT", "4"),
        ("AREACOLOR", SHEET_COLOR),
    ]


def template_records(frame: SheetFrame) -> list[list[Field]]:
    """Every record of a template after the header: the sheet record, then the frame's records."""
    return [frame.sheet_record(base_sheet_record()), *(list(record) for record in frame.records)]


def write_template(
    sheet: DrawingSheet,
    *,
    width: Nm,
    height: Nm,
    paper: str,
    form: TemplateForm = "binary",
    allow_lossy: bool = False,
) -> TemplateWrite:
    """``sheet`` as an Altium sheet template for a ``width`` by ``height`` page: a schematic document
    without components, in the binary (compound file) or the ASCII form. The bytes depend on the arguments
    only. ``SheetLossError`` as ``sheet_frame``; ``ValueError`` for an unknown form."""
    if form not in FORMS:
        raise ValueError(f"unknown template form {form!r}")
    result = sheet_frame(sheet, width=width, height=height, paper=paper, allow_lossy=allow_lossy)
    records = template_records(result.frame)
    if form == "ascii":
        data = encode_records(records)
    else:
        data = write_compound(
            [(FILE_HEADER_STREAM, file_header_stream(records)), (STORAGE_STREAM, storage_stream())]
        )
    return TemplateWrite(data, form, result)


__all__ = [
    "EVIDENCE",
    "FORMS",
    "SCHDOT_KIND",
    "SPECIAL_STRINGS",
    "SYSTEM_FONT",
    "FrameResult",
    "ScopeLine",
    "ScopeText",
    "SheetFrame",
    "TemplateForm",
    "TemplateWrite",
    "base_sheet_record",
    "length_fields",
    "parameter_record",
    "points_of",
    "sheet_frame",
    "template_records",
    "to_steps",
    "width_code",
    "write_template",
    "written_scope",
]

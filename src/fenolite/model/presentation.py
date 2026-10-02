# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Presentation layer: drawing sheets, the board's paper and title block (normative text: openspec
capability ``design-model``, change c0012).

A ``DrawingSheet`` is a definition outside ``Design``: one sheet serves many boards and sizes, so it is
never stored in the ``.fenolite/`` layer files. Every point is an offset from a corner of the margin box
(the page minus the setup margins), so one sheet fits every page size. Texts hold neutral tokens only
(``{title}``, ``{param:NAME}``); each backend maps them to its own variables.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

from fenolite.core.units import Nm, Udeg
from fenolite.model.base import Entity

Corner = Literal["lt", "lb", "rt", "rb"]
PageScope = Literal["all", "first_only", "not_first"]
HJustify = Literal["left", "center", "right"]
VJustify = Literal["top", "center", "bottom"]
ShapeKind = Literal["line", "rect"]
PaperSize = Literal["A0", "A1", "A2", "A3", "A4", "A5", "Letter", "Legal", "Tabloid", "custom"]
ORDERED = {"ordered": True}


@dataclass(frozen=True, slots=True)
class SheetPoint:
    """An offset from ``corner`` of the margin box, positive toward the interior (nm)."""

    corner: Corner = "rb"
    x: Nm = 0
    y: Nm = 0


@dataclass(frozen=True, slots=True)
class SheetRepeat:
    """Copies of an item, each offset by one more step; ``label_step`` steps a one-letter or number text."""

    count: int = 1
    step_x: Nm = 0
    step_y: Nm = 0
    label_step: int = 1


@dataclass(frozen=True, slots=True)
class SheetSetup:
    """Default text size and line widths, and the four page margins (nm)."""

    text_size: tuple[Nm, Nm]
    line_width: Nm
    text_line_width: Nm
    left_margin: Nm
    right_margin: Nm
    top_margin: Nm
    bottom_margin: Nm


@dataclass(frozen=True, slots=True)
class SheetShape:
    """A line or a rectangle between two points. ``kind`` has no default, so it is always written."""

    kind: ShapeKind
    start: SheetPoint
    end: SheetPoint
    width: Nm | None = None
    repeat: SheetRepeat = SheetRepeat()
    scope: PageScope = "all"
    name: str = ""
    comment: str = ""


@dataclass(frozen=True, slots=True)
class SheetText:
    """A text at ``pos``; ``rotation`` in µdeg, ``size`` (width, height) in nm or the setup size."""

    text: str
    pos: SheetPoint
    size: tuple[Nm, Nm] | None = None
    bold: bool = False
    italic: bool = False
    justify: HJustify = "left"
    vjustify: VJustify = "center"
    rotation: Udeg = 0
    max_len: Nm | None = None
    max_height: Nm | None = None
    repeat: SheetRepeat = SheetRepeat()
    scope: PageScope = "all"
    name: str = ""
    comment: str = ""


@dataclass(frozen=True, slots=True)
class SheetBitmap:
    """A PNG image (base64 text) at ``pos``; ``scale_ppm`` is the scale in parts per million."""

    pos: SheetPoint
    png: str
    scale_ppm: int = 1_000_000
    repeat: SheetRepeat = SheetRepeat()
    scope: PageScope = "all"
    name: str = ""
    comment: str = ""


SheetItem = SheetShape | SheetText | SheetBitmap


@dataclass(frozen=True, slots=True, kw_only=True)
class DrawingSheet(Entity):
    """A drawing-sheet definition: its setup and its items, in drawing order."""

    name: str
    setup: SheetSetup
    items: tuple[SheetItem, ...] = field(default=(), metadata=ORDERED)


# ---------------------------------------------------------------------------------------------- tokens

SHEET_TOKENS: frozenset[str] = frozenset(
    {
        "title",
        "doc_id",
        "revision",
        "sheet",
        "sheets",
        "date",
        "organization",
        "responsible",
        "approver",
        "filename",
        "paper",
    }
)
PARAM_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@dataclass(frozen=True, slots=True)
class SheetToken:
    """A neutral token of a sheet text: a name of ``SHEET_TOKENS``, or a user parameter."""

    name: str
    param: bool = False


def split_tokens(text: str) -> tuple[str | SheetToken, ...]:
    """``text`` split into literal strings and tokens: ``{name}``, ``{param:NAME}``, and ``{{``/``}}`` for
    literal braces. Raises ``ValueError`` naming an unknown or malformed token."""
    parts: list[str | SheetToken] = []
    literal: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char in "{}" and text[i : i + 2] == char * 2:
            literal.append(char)
            i += 2
            continue
        if char == "}":
            raise ValueError(f"unmatched '}}' at offset {i} of {text!r}; write '}}}}' for a literal brace")
        if char != "{":
            literal.append(char)
            i += 1
            continue
        end = text.find("}", i + 1)
        if end == -1:
            raise ValueError(f"unclosed token {text[i:]!r} in {text!r}")
        body = text[i + 1 : end]
        if body.startswith("param:"):
            name = body.removeprefix("param:")
            if not PARAM_NAME.fullmatch(name):
                raise ValueError(f"malformed parameter token {{{body}}} in {text!r}")
            token = SheetToken(name, param=True)
        elif body in SHEET_TOKENS:
            token = SheetToken(body)
        else:
            known = ", ".join(sorted(SHEET_TOKENS))
            raise ValueError(f"unknown token {{{body}}} in {text!r} (tokens: {known})")
        if literal:
            parts.append("".join(literal))
            literal = []
        parts.append(token)
        i = end + 1
    if literal:
        parts.append("".join(literal))
    return tuple(parts)


def join_tokens(parts: tuple[str | SheetToken, ...] | list[str | SheetToken]) -> str:
    """The neutral text of ``parts``, braces in literals doubled (the inverse of ``split_tokens``)."""
    out: list[str] = []
    for part in parts:
        if isinstance(part, SheetToken):
            out.append(f"{{param:{part.name}}}" if part.param else f"{{{part.name}}}")
        else:
            out.append(part.replace("{", "{{").replace("}", "}}"))
    return "".join(out)


# ---------------------------------------------------------------------------------------------- paper

_MM = 1_000_000
_INCH = 25_400_000
PAPER_SIZES: Mapping[str, tuple[Nm, Nm]] = MappingProxyType(
    {
        "A0": (841 * _MM, 1189 * _MM),
        "A1": (594 * _MM, 841 * _MM),
        "A2": (420 * _MM, 594 * _MM),
        "A3": (297 * _MM, 420 * _MM),
        "A4": (210 * _MM, 297 * _MM),
        "A5": (148 * _MM, 210 * _MM),
        "Letter": (17 * _INCH // 2, 11 * _INCH),
        "Legal": (17 * _INCH // 2, 14 * _INCH),
        "Tabloid": (11 * _INCH, 17 * _INCH),
    }
)
"""Portrait width and height of each named size: A0 to A4 from S-0077, A5 and the US sizes from S-0079
(inches at exactly 25.4 mm)."""
US_SIZES = ("Letter", "Legal", "Tabloid")


@dataclass(frozen=True, slots=True)
class TitleBlock:
    """The title-block fields of a board and the user parameters its sheet may show."""

    title: str = ""
    date: str = ""
    revision: str = ""
    organization: str = ""
    doc_id: str = ""
    responsible: str = ""
    approver: str = ""
    params: dict[str, str] = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class SheetFrameRef:
    """The board's paper and the drawing sheet its project names (a project-relative path)."""

    paper: PaperSize = "A4"
    portrait: bool = False
    width: Nm | None = None
    height: Nm | None = None
    drawing_sheet: str | None = None


__all__ = [
    "PAPER_SIZES",
    "PARAM_NAME",
    "SHEET_TOKENS",
    "US_SIZES",
    "Corner",
    "DrawingSheet",
    "HJustify",
    "PageScope",
    "PaperSize",
    "ShapeKind",
    "SheetBitmap",
    "SheetFrameRef",
    "SheetItem",
    "SheetPoint",
    "SheetRepeat",
    "SheetSetup",
    "SheetShape",
    "SheetText",
    "SheetToken",
    "TitleBlock",
    "VJustify",
    "join_tokens",
    "split_tokens",
]

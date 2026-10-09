# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The drawing specification file of ``export --drawing-spec`` (capability manufacturing-exports,
"Drawing specification files"; change c0117; user guide ``docs/drawings.md``).

A TOML file of the user's: the paper and the sheet of the pages, the tables, dimensions and notes of the
fabrication drawing, and the options and notes of the assembly drawings. The key set is closed, lengths
are strings with a unit, and every problem of a file is reported at once, in file order. Fenolite ships
no note text and no tolerance, class, material or finish: a drawing states what the board and this file
say.
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, cast

from fenolite.core.errors import FormatError
from fenolite.core.units import Nm, parse_length
from fenolite.model.presentation import PAPER_SIZES

SCHEMA = "fenolite.drawing-spec.v0"
AUTO = "auto"
TABLE_NAMES = ("board", "stackup", "drill", "impedance", "notes")
"""The blocks of the fabrication page, in the order they are placed. ``impedance`` is a valid name
whose block has no content yet (the model holds no impedance target), so the schema id need not change
when a later change gives it rows."""
ASSEMBLY_BLOCKS = ("notes",)
SIDES = ("top", "bottom")
DNP_MODES = ("crossout", "hide", "show")
SHEET_SUFFIXES = (".kicad_wks", ".sheet.toml")
MAX_PRECISION = 4
Dnp = Literal["crossout", "hide", "show"]
Corner = tuple[Nm, Nm]


@dataclass(frozen=True, slots=True)
class PageSpec:
    """What every page shares: the paper (``auto`` or a name of ``PAPER_SIZES``), the orientation, the
    drawing sheet (a path as the file gives it, or ``""`` for the project's or KiCad's), the height of
    generated text, the distance kept between blocks, and the width of a note."""

    paper: str = AUTO
    portrait: bool = False
    drawing_sheet: str = ""
    text_size: Nm = 1_500_000
    gap: Nm = 5_000_000
    notes_width: Nm = 120_000_000


@dataclass(frozen=True, slots=True)
class FabSpec:
    """The fabrication page: its title, its tables in the order of ``TABLE_NAMES``, the overall
    dimensions, the notes, and fixed corners of blocks (block name → top-left corner)."""

    title: str = "Fabrication drawing"
    tables: tuple[str, ...] = TABLE_NAMES
    dimensions: bool = True
    dimension_offset: Nm = 8_000_000
    dimension_precision: int = 2
    notes: tuple[str, ...] = ()
    at: tuple[tuple[str, Corner], ...] = ()


@dataclass(frozen=True, slots=True)
class AssemblySpec:
    """The assembly pages: their titles, the sides drawn, how a do-not-populate part is shown, whether
    values and pad outlines are drawn, the added designators, and the notes of the top page."""

    title_top: str = "Assembly drawing, top side"
    title_bottom: str = "Assembly drawing, bottom side"
    sides: tuple[str, ...] = SIDES
    dnp: Dnp = "crossout"
    values: bool = False
    pads: bool = False
    designators: bool = True
    designator_size: Nm = 1_000_000
    notes: tuple[str, ...] = ()
    at: tuple[tuple[str, Corner], ...] = ()


@dataclass(frozen=True, slots=True)
class DrawingSpec:
    page: PageSpec = PageSpec()
    fab: FabSpec = FabSpec()
    assembly: AssemblySpec = AssemblySpec()


DEFAULT = DrawingSpec()
"""The specification of an export without ``--drawing-spec``: every default, and no note."""


class SpecError(FormatError):
    """A drawing specification that cannot be used. ``problems`` holds every problem of the file in
    file order, each with its dotted key."""

    def __init__(self, problems: tuple[tuple[str, str], ...], *, file: str = "") -> None:
        self.problems = problems
        text = "; ".join(f"{key}: {message}" if key else message for key, message in problems)
        super().__init__(text, file=file, locator=problems[0][0] if problems else "")


class _Problem(Exception):
    pass


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise _Problem("must be a text")
    return value


def _bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise _Problem("must be true or false")
    return value


def _length(value: object) -> Nm:
    if not isinstance(value, str):
        raise _Problem('must be a length with a unit, for example "5mm"')
    try:
        length = parse_length(value)
    except ValueError as error:
        raise _Problem(str(error)) from None
    return length


def _positive(value: object) -> Nm:
    length = _length(value)
    if length <= 0:
        raise _Problem("must be a positive length")
    return length


def _paper(value: object) -> str:
    if not isinstance(value, str) or (value != AUTO and value not in PAPER_SIZES):
        raise _Problem(f'must be "{AUTO}" or one of {", ".join(sorted(PAPER_SIZES))}')
    return value


def _sheet(value: object) -> str:
    if not isinstance(value, str) or not value.endswith(SHEET_SUFFIXES):
        raise _Problem(f"must be a path ending in {' or '.join(SHEET_SUFFIXES)}")
    return value


def _precision(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_PRECISION:
        raise _Problem(f"must be an integer from 0 to {MAX_PRECISION}")
    return value


def _choice(allowed: tuple[str, ...]) -> Callable[[object], str]:
    def read(value: object) -> str:
        if not isinstance(value, str) or value not in allowed:
            raise _Problem(f"must be one of {', '.join(allowed)}")
        return value

    return read


def _names(allowed: tuple[str, ...]) -> Callable[[object], tuple[str, ...]]:
    def read(value: object) -> tuple[str, ...]:
        items = cast(list[object], value) if isinstance(value, list) else None
        if items is None or any(not isinstance(item, str) or item not in allowed for item in items):
            raise _Problem(f"must be a list of {', '.join(allowed)}")
        found = cast(list[str], items)
        if len(set(found)) != len(found):
            raise _Problem("names an entry twice")
        return tuple(name for name in allowed if name in found)

    return read


def _notes(value: object) -> tuple[str, ...]:
    items = cast(list[object], value) if isinstance(value, list) else None
    if items is None or any(not isinstance(item, str) for item in items):
        raise _Problem("must be a list of texts")
    notes = cast(list[str], items)
    for index, note in enumerate(notes, 1):
        if any((ord(char) < 32 and char != "\n") or ord(char) == 127 for char in note):
            raise _Problem(f"note {index} holds a control character other than a line feed")
        if not note.strip():
            raise _Problem(f"note {index} is empty")
    return tuple(notes)


def _corners(blocks: tuple[str, ...]) -> Callable[[object], tuple[tuple[str, Corner], ...]]:
    def read(value: object) -> tuple[tuple[str, Corner], ...]:
        if not isinstance(value, dict):
            raise _Problem("must be a table of block name to two lengths")
        found: list[tuple[str, Corner]] = []
        for name, corner in cast(dict[str, object], value).items():
            if name not in blocks:
                raise _Problem(f"names the block {name!r}; this page has {', '.join(blocks)}")
            pair = cast(list[object], corner) if isinstance(corner, list) else []
            if len(pair) != 2:
                raise _Problem(f"{name} must be two lengths, x and y")
            found.append((name, (_length(pair[0]), _length(pair[1]))))
        return tuple(found)

    return read


_Reader = Callable[[object], object]
TABLES: Mapping[str, Mapping[str, _Reader]] = {
    "page": {
        "paper": _paper,
        "portrait": _bool,
        "drawing_sheet": _sheet,
        "text_size": _positive,
        "gap": _positive,
        "notes_width": _positive,
    },
    "fab": {
        "title": _text,
        "tables": _names(TABLE_NAMES),
        "dimensions": _bool,
        "dimension_offset": _positive,
        "dimension_precision": _precision,
        "notes": _notes,
        "at": _corners(TABLE_NAMES),
    },
    "assembly": {
        "title_top": _text,
        "title_bottom": _text,
        "sides": _names(SIDES),
        "dnp": _choice(DNP_MODES),
        "values": _bool,
        "pads": _bool,
        "designators": _bool,
        "designator_size": _positive,
        "notes": _notes,
        "at": _corners(ASSEMBLY_BLOCKS),
    },
}
"""Table → key → the reader of its value: the closed key set of the format."""


def read_spec(text: str, *, file: str = "") -> DrawingSpec:
    """The specification of a TOML text. A text that is not TOML raises ``FormatError``; a wrong schema
    id, an unknown table or key and a value outside its set raise ``SpecError`` with every problem."""
    try:
        data = tomllib.loads(text, parse_float=Decimal)
    except tomllib.TOMLDecodeError as error:
        raise FormatError(f"not TOML: {error}", file=file) from error
    problems: list[tuple[str, str]] = []
    if data.get("schema") != SCHEMA:
        problems.append(("schema", f"is {data.get('schema')!r}, not {SCHEMA!r}"))
    found: dict[str, dict[str, object]] = {name: {} for name in TABLES}
    for name, table in data.items():
        if name == "schema":
            continue
        if name not in TABLES or not isinstance(table, dict):
            problems.append((name, f"unknown table; a drawing specification holds {', '.join(TABLES)}"))
            continue
        for key, value in cast(dict[str, object], table).items():
            where = f"{name}.{key}"
            reader = TABLES[name].get(key)
            if reader is None:
                problems.append((where, f"unknown key; [{name}] holds {', '.join(TABLES[name])}"))
                continue
            try:
                found[name][key] = reader(value)
            except _Problem as problem:
                problems.append((where, str(problem)))
        if name == "page" and found[name].get("portrait") is True and found[name].get("paper", AUTO) == AUTO:
            problems.append(("page.portrait", f'needs a named paper; "{AUTO}" chooses a landscape page'))
    page = found["page"]
    if problems:
        raise SpecError(tuple(problems), file=file)
    return DrawingSpec(PageSpec(**page), FabSpec(**found["fab"]), AssemblySpec(**found["assembly"]))  # type: ignore[arg-type]


__all__ = [
    "ASSEMBLY_BLOCKS",
    "AUTO",
    "DEFAULT",
    "DNP_MODES",
    "SCHEMA",
    "SIDES",
    "TABLES",
    "TABLE_NAMES",
    "AssemblySpec",
    "DrawingSpec",
    "FabSpec",
    "PageSpec",
    "SpecError",
    "read_spec",
]

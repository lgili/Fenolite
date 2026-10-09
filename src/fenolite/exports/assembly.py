# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The column template of the assembly tables, and their CSV rendering (capability assembly-outputs,
"Assembly template" and "CSV rendering"; user guide ``docs/assembly.md``).

A template is a TOML file the user writes: which columns a bill of materials and a placement table have,
what they are called, how lines are grouped, and the units, origin, side names and rotation rule of the
placement table. Fenolite holds one template, ``DEFAULT``, whose columns carry Fenolite's own field
names. It ships no template of any assembly service, distributor or company.

The key set is closed. Every problem of a file is collected in file order and raised as one
``TemplateError``. Numbers are read with ``parse_float=Decimal`` and no float is ever created: lengths
stay integer nanometres and angles integer microdegrees until they are printed as exact decimals.
"""

from __future__ import annotations

import csv
import io
import re
import tomllib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal, cast

from fenolite.core.errors import FormatError, Issue
from fenolite.core.units import LENGTH_UNITS, Nm, Udeg, round_half_even_div
from fenolite.exports.codes import issue

SCHEMA = "fenolite.assembly-template.v0"
PROPERTY_PREFIX = "property:"
BOM_FIELDS: tuple[str, ...] = (
    "refs",
    "quantity",
    "value",
    "footprint",
    "footprint_name",
    "description",
    "datasheet",
    "dnp",
    "item",
)
"""The fields of a BOM column, besides ``property:<NAME>``."""
BOM_GROUP_FIELDS: tuple[str, ...] = tuple(f for f in BOM_FIELDS if f not in ("refs", "quantity", "item"))
"""The fields ``group_by`` may name, besides ``property:<NAME>``: those a single part has."""
PLACEMENT_FIELDS: tuple[str, ...] = (
    "ref",
    "value",
    "footprint",
    "footprint_name",
    "x",
    "y",
    "rotation",
    "side",
    "fiducial",
)
"""The fields of a placement column, besides ``property:<NAME>``; ``fiducial`` prints ``yes`` for a
footprint with a fiducial pad and nothing otherwise."""
UNITS: tuple[str, ...] = ("mm", "in", "mil")
MAX_DECIMALS = 6
FULL_TURN: Udeg = 360_000_000
DNP_TEXT = "DNP"

Quote = Literal["minimal", "all"]
LineEnd = Literal["lf", "crlf"]
Encoding = Literal["utf-8", "utf-8-sig"]
Units = Literal["mm", "in", "mil"]
Origin = Literal["page", "outline"]
YAxis = Literal["up", "down"]

_UDEG_PER_DEG = 1_000_000
_DIGITS = re.compile(r"(\d+)")


class TemplateError(FormatError):
    """A template that cannot be used: every problem, one ``Issue`` each; ``locator`` is the key path of
    the first problem in file order. The command line maps it to ``FEN-3004``."""

    cli_code = "FEN-3004"

    def __init__(self, issues: tuple[Issue, ...], *, file: str = "") -> None:
        self.issues = issues
        summary = "; ".join(f"{i.where}: {i.message}" if i.where else i.message for i in issues)
        super().__init__(summary or "invalid template", file=file, locator=issues[0].where if issues else "")


@dataclass(frozen=True, slots=True)
class Column:
    """One column: the ``name`` printed in the header and the ``field`` whose value fills it."""

    name: str
    field: str


@dataclass(frozen=True, slots=True)
class CsvOptions:
    delimiter: str = ","
    quote: Quote = "minimal"
    line_end: LineEnd = "lf"
    header: bool = True
    encoding: Encoding = "utf-8"


def _named(*fields: str) -> tuple[Column, ...]:
    return tuple(Column(name, name) for name in fields)


@dataclass(frozen=True, slots=True)
class BomTemplate:
    columns: tuple[Column, ...] = _named("refs", "quantity", "value", "footprint")
    group_by: tuple[str, ...] = ("value", "footprint")
    ref_separator: str = ","
    exclude_dnp: bool = True


@dataclass(frozen=True, slots=True)
class SideNames:
    """What the ``side`` field prints for each side of the board."""

    top: str = "top"
    bottom: str = "bottom"


@dataclass(frozen=True, slots=True)
class SideRotation:
    """The rule of one side: ``sign × rotation + offset``, with ``offset`` in microdegrees."""

    sign: int = 1
    offset: Udeg = 0


@dataclass(frozen=True, slots=True)
class FootprintRotation:
    """An ``offset`` (microdegrees) added for the footprints whose lib id fits ``match``."""

    match: str
    offset: Udeg


@dataclass(frozen=True, slots=True)
class RotationRule:
    top: SideRotation = SideRotation()
    bottom: SideRotation = SideRotation()
    footprint: tuple[FootprintRotation, ...] = ()


@dataclass(frozen=True, slots=True)
class PlacementTemplate:
    columns: tuple[Column, ...] = _named("ref", "value", "footprint_name", "x", "y", "rotation", "side")
    units: Units = "mm"
    decimals: int = 4
    rotation_decimals: int = 2
    origin: Origin = "page"
    y_axis: YAxis = "up"
    sides: SideNames = SideNames()
    exclude_dnp: bool = True
    smd_only: bool = False
    rotation: RotationRule = RotationRule()
    fiducials: bool = True


@dataclass(frozen=True, slots=True)
class AssemblyTemplate:
    """The three tables of a template file; a missing table or key has the value of ``DEFAULT``."""

    csv: CsvOptions = field(default_factory=CsvOptions)
    bom: BomTemplate = field(default_factory=BomTemplate)
    placement: PlacementTemplate = field(default_factory=PlacementTemplate)


DEFAULT = AssemblyTemplate()
"""The template used when the user gives none: Fenolite's own field names as column names, a BOM grouped
by value and footprint, and a placement table with the content of KiCad's own position file (millimetres,
the page origin, Y up, stored rotations)."""


def natural_key(text: str) -> tuple[tuple[int, int | str], ...]:
    """A sort key that puts ``R2`` before ``R10``: digit runs compare as numbers."""
    return tuple((0, int(part)) if part.isdigit() else (1, part) for part in _DIGITS.split(text) if part)


def footprint_name(lib_id: str) -> str:
    """The footprint's name without its library: ``Lib:Name`` gives ``Name``."""
    return lib_id.partition(":")[2] or lib_id


def property_name(field_name: str) -> str | None:
    """The ``NAME`` of ``property:NAME``, or ``None`` for any other field."""
    if field_name.startswith(PROPERTY_PREFIX) and len(field_name) > len(PROPERTY_PREFIX):
        return field_name[len(PROPERTY_PREFIX) :]
    return None


# --- reading a template ---------------------------------------------------------------------------

_SKIP = object()
_Convert = Callable[["_Reader", Any, str], Any]


class _Reader:
    """Problems in the order the file is walked, which is file order."""

    def __init__(self) -> None:
        self.issues: list[Issue] = []

    def bad(self, where: str, message: str) -> Any:
        self.issues.append(issue("assembly.template-invalid", message, where=where))
        return _SKIP


def _choice(choices: Sequence[str]) -> _Convert:
    def convert(reader: _Reader, value: Any, where: str) -> Any:
        if not isinstance(value, str) or value not in choices:
            return reader.bad(where, f"expected one of {', '.join(choices)}, got {value!r}")
        return value

    return convert


def _boolean(reader: _Reader, value: Any, where: str) -> Any:
    if not isinstance(value, bool):
        return reader.bad(where, f"expected true or false, got {value!r}")
    return value


def _text(reader: _Reader, value: Any, where: str) -> Any:
    if not isinstance(value, str) or not value or "\n" in value or "\r" in value:
        return reader.bad(where, f"expected a non-empty string on one line, got {value!r}")
    return value


def _delimiter(reader: _Reader, value: Any, where: str) -> Any:
    if not isinstance(value, str) or len(value) != 1 or value in '"\r\n':
        return reader.bad(where, f"expected one character other than a quote or a line break, got {value!r}")
    return value


def _decimals(reader: _Reader, value: Any, where: str) -> Any:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_DECIMALS:
        return reader.bad(where, f"expected an integer from 0 to {MAX_DECIMALS}, got {value!r}")
    return value


def _sign(reader: _Reader, value: Any, where: str) -> Any:
    if isinstance(value, bool) or not isinstance(value, int) or value not in (1, -1):
        return reader.bad(where, f"expected 1 or -1, got {value!r}")
    return value


def _degrees(reader: _Reader, value: Any, where: str) -> Any:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        return reader.bad(where, f"expected a number of degrees, got {value!r}")
    number = Decimal(value)
    if not number.is_finite():
        return reader.bad(where, f"expected a number of degrees, got {value!r}")
    udeg = number * _UDEG_PER_DEG
    if udeg != udeg.to_integral_value():
        return reader.bad(where, f"{value} degrees is not a whole number of microdegrees")
    return int(udeg)


def _field_of(vocabulary: Sequence[str], what: str) -> _Convert:
    def convert(reader: _Reader, value: Any, where: str) -> Any:
        if isinstance(value, str) and (value in vocabulary or property_name(value) is not None):
            return value
        known = ", ".join((*vocabulary, f"{PROPERTY_PREFIX}<NAME>"))
        return reader.bad(where, f"unknown {what} {value!r}; the fields are {known}")

    return convert


def _table(reader: _Reader, data: Any, where: str, handlers: Mapping[str, _Convert]) -> dict[str, Any]:
    """The converted values of the known keys of ``data``; an unknown key is a problem."""
    if not isinstance(data, dict):
        reader.bad(where, f"{where} must be a table")
        return {}
    found: dict[str, Any] = {}
    for key, value in cast(dict[str, Any], data).items():
        path = f"{where}.{key}"
        handler = handlers.get(key)
        if handler is None:
            reader.bad(path, f"unknown key {key!r} in {where}")
            continue
        converted = handler(reader, value, path)
        if converted is not _SKIP:
            found[key] = converted
    return found


def _columns(vocabulary: Sequence[str]) -> _Convert:
    field_of = _field_of(vocabulary, "field")

    def convert(reader: _Reader, value: Any, where: str) -> Any:
        if not isinstance(value, list) or not value:
            return reader.bad(where, "expected a list of at least one { name, field } column")
        before = len(reader.issues)
        columns: list[Column] = []
        seen: set[str] = set()
        for index, item in enumerate(cast(list[Any], value)):
            path = f"{where}[{index}]"
            found = _table(reader, item, path, {"name": _text, "field": field_of})
            for key in ("name", "field"):
                if isinstance(item, dict) and key not in item:
                    reader.bad(f"{path}.{key}", f"a column needs {key!r}")
            name = found.get("name")
            if name is not None and name in seen:
                reader.bad(f"{path}.name", f"two columns are named {name!r}")
            if name is not None:
                seen.add(name)
            if "name" in found and "field" in found:
                columns.append(Column(found["name"], found["field"]))
        return tuple(columns) if len(reader.issues) == before else _SKIP

    return convert


def _group_by(reader: _Reader, value: Any, where: str) -> Any:
    if not isinstance(value, list):
        return reader.bad(where, "expected a list of fields")
    field_of = _field_of(BOM_GROUP_FIELDS, "grouping field")
    items = [field_of(reader, item, f"{where}[{index}]") for index, item in enumerate(cast(list[Any], value))]
    if any(item is _SKIP for item in items):
        return _SKIP
    if len(set(items)) != len(items):
        return reader.bad(where, "a field is listed twice")
    return tuple(items)


def _sides(reader: _Reader, value: Any, where: str) -> Any:
    return SideNames(**_table(reader, value, where, {"top": _text, "bottom": _text}))


def _side_rotation(reader: _Reader, value: Any, where: str) -> Any:
    return SideRotation(**_table(reader, value, where, {"sign": _sign, "offset": _degrees}))


def _footprint_rotations(reader: _Reader, value: Any, where: str) -> Any:
    if not isinstance(value, list):
        return reader.bad(where, "expected a list of { match, offset } entries")
    entries: list[FootprintRotation] = []
    for index, item in enumerate(cast(list[Any], value)):
        path = f"{where}[{index}]"
        found = _table(reader, item, path, {"match": _text, "offset": _degrees})
        for key in ("match", "offset"):
            if isinstance(item, dict) and key not in item:
                reader.bad(f"{path}.{key}", f"a footprint entry needs {key!r}")
        if "match" in found and "offset" in found:
            entries.append(FootprintRotation(found["match"], found["offset"]))
    return tuple(entries)


def _rotation(reader: _Reader, value: Any, where: str) -> Any:
    handlers = {"top": _side_rotation, "bottom": _side_rotation, "footprint": _footprint_rotations}
    return RotationRule(**_table(reader, value, where, handlers))


def _csv(reader: _Reader, value: Any, where: str) -> Any:
    handlers: dict[str, _Convert] = {
        "delimiter": _delimiter,
        "quote": _choice(("minimal", "all")),
        "line_end": _choice(("lf", "crlf")),
        "header": _boolean,
        "encoding": _choice(("utf-8", "utf-8-sig")),
    }
    return CsvOptions(**_table(reader, value, where, handlers))


def _bom(reader: _Reader, value: Any, where: str) -> Any:
    handlers: dict[str, _Convert] = {
        "columns": _columns(BOM_FIELDS),
        "group_by": _group_by,
        "ref_separator": _text,
        "exclude_dnp": _boolean,
    }
    return BomTemplate(**_table(reader, value, where, handlers))


def _placement(reader: _Reader, value: Any, where: str) -> Any:
    handlers: dict[str, _Convert] = {
        "columns": _columns(PLACEMENT_FIELDS),
        "units": _choice(UNITS),
        "decimals": _decimals,
        "rotation_decimals": _decimals,
        "origin": _choice(("page", "outline")),
        "y_axis": _choice(("up", "down")),
        "sides": _sides,
        "exclude_dnp": _boolean,
        "smd_only": _boolean,
        "fiducials": _boolean,
        "rotation": _rotation,
    }
    return PlacementTemplate(**_table(reader, value, where, handlers))


def _schema(reader: _Reader, value: Any, where: str) -> Any:
    if value != SCHEMA:
        return reader.bad(where, f"expected {SCHEMA!r}, got {value!r}")
    return _SKIP


_ROOT: Mapping[str, _Convert] = {"schema": _schema, "csv": _csv, "bom": _bom, "placement": _placement}


def read_template(text: str, *, file: str = "") -> AssemblyTemplate:
    """The template of a TOML ``text``; raises one ``TemplateError`` that names every problem."""
    try:
        data = tomllib.loads(text, parse_float=Decimal)
    except tomllib.TOMLDecodeError as exc:
        problem = issue("assembly.template-invalid", f"TOML syntax error: {exc}")
        raise TemplateError((problem,), file=file) from None
    reader = _Reader()
    found: dict[str, Any] = {}
    for key, value in data.items():
        handler = _ROOT.get(key)
        if handler is None:
            reader.bad(key, f"unknown table or key {key!r}")
            continue
        converted = handler(reader, value, key)
        if converted is not _SKIP:
            found[key] = converted
    if reader.issues:
        raise TemplateError(tuple(reader.issues), file=file)
    return AssemblyTemplate(**found)


# --- printing -------------------------------------------------------------------------------------


def _decimal(numerator: int, denominator: int, decimals: int) -> str:
    """``numerator / denominator`` as a decimal with ``decimals`` places, rounded half to even."""
    scaled = round_half_even_div(numerator * 10**decimals, denominator)
    sign = "-" if scaled < 0 else ""
    whole, fraction = divmod(abs(scaled), 10**decimals)
    return f"{sign}{whole}.{fraction:0{decimals}d}" if decimals else f"{sign}{whole}"


def format_length(nm: Nm, units: str, decimals: int) -> str:
    """A length in ``mm``, ``in`` (25.4 mm) or ``mil`` (0.0254 mm), with trailing zeros kept."""
    if units not in UNITS:
        raise ValueError(f"unknown unit {units!r} (one of {', '.join(UNITS)})")
    return _decimal(nm, LENGTH_UNITS[units], decimals)


def format_angle(udeg: Udeg, decimals: int) -> str:
    """An angle in degrees, with trailing zeros kept."""
    return _decimal(udeg, _UDEG_PER_DEG, decimals)


def render_csv(header: Sequence[str], rows: Iterable[Sequence[str]], options: CsvOptions) -> bytes:
    """The table as CSV bytes under ``options``: every line ends with the line end, the last included."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(
        buffer,
        delimiter=options.delimiter,
        quotechar='"',
        doublequote=True,
        quoting=csv.QUOTE_ALL if options.quote == "all" else csv.QUOTE_MINIMAL,
        lineterminator="\r\n" if options.line_end == "crlf" else "\n",
    )
    if options.header:
        writer.writerow(list(header))
    for row in rows:
        writer.writerow(list(row))
    return buffer.getvalue().encode(options.encoding)


__all__ = [
    "BOM_FIELDS",
    "BOM_GROUP_FIELDS",
    "DEFAULT",
    "DNP_TEXT",
    "FULL_TURN",
    "PLACEMENT_FIELDS",
    "PROPERTY_PREFIX",
    "SCHEMA",
    "UNITS",
    "AssemblyTemplate",
    "BomTemplate",
    "Column",
    "CsvOptions",
    "FootprintRotation",
    "PlacementTemplate",
    "RotationRule",
    "SideNames",
    "SideRotation",
    "TemplateError",
    "footprint_name",
    "format_angle",
    "format_length",
    "natural_key",
    "property_name",
    "read_template",
    "render_csv",
]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``fenolite.family.v1`` record: a series described by its ordering-code grammar (change c0263,
``docs/picking.md``, "Families with ordering codes").

A grammar family states its ``pattern`` (literal text and ``{field}`` placeholders), its ``fields`` (each
code with closed attributes; one value field with a value-code scheme), its validity matrix (``[[valid]]``
and ``[[exclude]]`` rows), an optional opaque ``tail`` and the common keys of a library record (change
c0259: ``id``, ``version``, ``licence``, ``evidence``, ``sources``, ``reviewed_by``). ``read_family``
checks the form: an unknown key, a float or a malformed value raises ``DeviceFormatError`` (``FEN-3004``)
naming the file and the key, a newer schema ``DeviceFormatTooNewError`` (``FEN-3002``). What a well-formed
grammar may still get wrong (a placeholder without a field, an ambiguous code, a matrix row naming a missing
code) is the lint's (``fenolite.pick.grammar.lint``).
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import cast

from fenolite.catalog.devices import (
    EVIDENCE,
    ID,
    DeviceFormatError,
    DeviceFormatTooNewError,
)
from fenolite.catalog.records import LICENCE, VERSION, record_uid
from fenolite.core.partquery import KEYS, KINDS, PINS, VALUE_UNITS, Constraint
from fenolite.core.quantities import QuantityError, parse
from fenolite.pick.grammar.valuecodes import SCHEMES
from fenolite.pick.rows import is_grammar, tolerance_of
from fenolite.pick.series import SERIES, member, values

SCHEMA = "fenolite.family.v1"
KIND = "family"
"""The record kind of a grammar family for c0259's stable id (``record_uid(KIND, id)``)."""
TOP_KEYS: tuple[str, ...] = (
    "schema",
    "id",
    "kind",
    "summary",
    "manufacturer",
    "version",
    "licence",
    "evidence",
    "sources",
    "datasheet",
    "symbol",
    "footprint",
    "pins",
    "pattern",
    "tail",
    "fields",
    "valid",
    "exclude",
    "reviewed_by",
)
"""Every top-level key of a grammar family."""
REQUIRED: tuple[str, ...] = (
    "schema",
    "id",
    "kind",
    "summary",
    "manufacturer",
    "version",
    "licence",
    "evidence",
    "sources",
    "pattern",
    "fields",
    "valid",
)
FIELD_KEYS: tuple[str, ...] = ("role", "prefer", "codes", "scheme", "unit", "series")
SPAN_KEYS: tuple[str, ...] = ("min", "max", "series", "values")
REVIEW_KEYS: tuple[str, ...] = ("who", "date", "version", "digest", "evidence", "sheet")
TEXT_ATTRIBUTES: tuple[str, ...] = ("footprint", "symbol", "packing")
"""The attributes a code may state beside the constraint keys of its family's kind."""
NUMERIC_UNITS: Mapping[str, str] = MappingProxyType(
    {
        "power": "watt",
        "voltage": "volt",
        "rating": "volt",
        "current": "ampere",
        "saturation": "ampere",
        "dcr": "ohm",
        "tempco": "ppm",
    }
)
"""The numeric code attributes and the unit each is read in."""
ROLES: tuple[str, ...] = ("electrical", "ordering")
TAILS: tuple[str, ...] = ("none", "opaque")
DEFAULT_PINS: tuple[tuple[str, str], ...] = ((PINS[0], PINS[0]), (PINS[1], PINS[1]))
"""``(symbol pin, pad)`` of a family without ``pins``: pin ``1`` on pad ``1``, ``2`` on ``2``."""
FIELD_NAME = re.compile(r"[a-z][a-z0-9_]*")
CODE = re.compile(r"[A-Z0-9-]+")
TOKEN = re.compile(r"\{([a-z][a-z0-9_]*)\}|([A-Z0-9-]+)")
URL = re.compile(r"https?://[^\s]+")


@dataclass(frozen=True, slots=True)
class Code:
    """One code of a field: its text, the attributes it gives by query key (parsed) and every attribute as
    the file wrote it (``texts``, with ``footprint``, ``symbol`` and ``packing``)."""

    code: str
    attributes: Mapping[str, Constraint]
    texts: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class Field:
    """One field of the pattern: a code field (``codes`` in code-point order, its ``role`` and the code an
    ordering field ``prefer``s) or the value field (``scheme``, ``unit`` as written and its ``scale``, the
    value of one unit, and the default ``series`` of its domain)."""

    name: str
    role: str = "electrical"
    codes: tuple[Code, ...] = ()
    prefer: str = ""
    scheme: str = ""
    unit: str = ""
    scale: Fraction = Fraction(1)
    series: str = ""

    @property
    def is_value(self) -> bool:
        return bool(self.scheme)

    def code(self, text: str) -> Code | None:
        for found in self.codes:
            if found.code == text:
                return found
        return None


@dataclass(frozen=True, slots=True)
class Span:
    """The value span of a matrix row: ``low``..``high`` (both included, ``None`` unbounded), restricted to
    the row's ``series`` or its explicit ``values``."""

    low: Fraction | None = None
    high: Fraction | None = None
    series: str = ""
    values: tuple[Fraction, ...] | None = None

    def admits(self, value: Fraction, default_series: str, *, need_series: bool) -> bool:
        """Whether ``value`` lies in the span; ``need_series`` restricts it to the series (a ``[[valid]]``
        row) or not (an ``[[exclude]]`` row without its own series or values)."""
        if self.low is not None and value < self.low:
            return False
        if self.high is not None and value > self.high:
            return False
        if self.values is not None:
            return value in self.values
        series = self.series or (default_series if need_series else "")
        return _member(series, value) if series else True

    def domain(
        self, default_series: str, low: Fraction | None = None, high: Fraction | None = None
    ) -> Iterator[Fraction]:
        """The values of the span within ``low``..``high``, rising (a ``[[valid]]`` row's span is bounded)."""
        lows = [item for item in (self.low, low) if item is not None]
        highs = [item for item in (self.high, high) if item is not None]
        lo = max(lows) if lows else None
        hi = min(highs) if highs else None
        if self.values is not None:
            yield from (
                value
                for value in sorted(self.values)
                if (lo is None or value >= lo) and (hi is None or value <= hi)
            )
            return
        series = self.series or default_series
        if not series or lo is None or hi is None or lo > hi or lo <= 0:
            return
        yield from values(series, lo, hi)


@lru_cache(maxsize=65536)
def _member(series: str, value: Fraction) -> bool:
    return member(series, value)


@dataclass(frozen=True, slots=True)
class MatrixRow:
    """One ``[[valid]]`` or ``[[exclude]]`` row: the codes it allows per field it names (a field it omits is
    free) and its value span (``None``: any value)."""

    index: int
    codes: Mapping[str, tuple[str, ...]]
    span: Span | None


@dataclass(frozen=True, slots=True)
class GrammarFamily:
    """A grammar family, read and checked for form. ``tokens`` is the pattern as ``("literal", text)`` and
    ``("field", name)`` pairs; ``fields`` keep the file's order."""

    id: str
    kind: str
    summary: str
    manufacturer: str
    version: str
    licence: str
    evidence: str
    sources: tuple[str, ...]
    sources_by: Mapping[str, tuple[str, ...]]
    pattern: str
    tokens: tuple[tuple[str, str], ...]
    fields: Mapping[str, Field]
    valid: tuple[MatrixRow, ...]
    exclude: tuple[MatrixRow, ...] = ()
    tail: str = "none"
    datasheet: str = ""
    symbol: str = ""
    footprint: str = ""
    pins: tuple[tuple[str, str], ...] = DEFAULT_PINS
    """``(symbol pin, pad)`` of the two ends; by default pin ``1`` on pad ``1`` and ``2`` on ``2``."""
    reviewed_by: tuple[tuple[tuple[str, str], ...], ...] = ()
    file: str = ""
    texts: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    @property
    def value_field(self) -> Field | None:
        """The first field with a scheme (the lint requires exactly one)."""
        return next((found for found in self.fields.values() if found.is_value), None)

    @property
    def placeholders(self) -> tuple[str, ...]:
        return tuple(text for kind, text in self.tokens if kind == "field")

    @property
    def uid(self) -> str:
        """The stable id of the record (change c0259), computed, never stored."""
        return record_uid(KIND, self.id)

    @property
    def literal_prefix(self) -> str:
        """The literal text before the first placeholder."""
        out = ""
        for kind, text in self.tokens:
            if kind != "literal":
                break
            out += text
        return out


# ----------------------------------------------------------------------------------------- reading


class _Reader:
    def __init__(self, file: str) -> None:
        self.file = file

    def fail(self, key: str, message: str) -> DeviceFormatError:
        return DeviceFormatError(f"{key}: {message}", file=self.file, locator=key)

    def text(self, value: object, key: str) -> str:
        if not isinstance(value, str) or not value or not value.isprintable():
            raise self.fail(key, f"must be a non-empty string, not {value!r}")
        return value

    def table(self, value: object, key: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise self.fail(key, "must be a table")
        return cast(dict[str, object], value)

    def closed(self, table: Mapping[str, object], keys: tuple[str, ...], where: str) -> None:
        for key in table:
            if key not in keys:
                raise self.fail(f"{where}.{key}", f"unknown key; {where} takes {', '.join(keys)}")

    def texts(self, value: object, key: str) -> tuple[str, ...]:
        items: list[object] = cast(list[object], value) if isinstance(value, list) else [value]
        if not items:
            raise self.fail(key, "must name at least one code")
        return tuple(self.text(item, key) for item in items)


def _no_float(read: _Reader, value: object, key: str) -> None:
    if isinstance(value, Decimal):
        raise read.fail(key, f"{value} is a float; write quantities as strings such as '100nF'")
    if isinstance(value, dict):
        for name, item in cast(dict[str, object], value).items():
            _no_float(read, item, f"{key}.{name}" if key else name)
    elif isinstance(value, list):
        for index, item in enumerate(cast(list[object], value)):
            _no_float(read, item, f"{key}[{index}]")


def _amount(read: _Reader, unit: str, text: str, key: str) -> Fraction:
    if unit == "ppm":
        number = text.removesuffix("ppm/K").strip()
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", number):
            raise read.fail(key, f"{text!r} is not a number of ppm/K")
        return Fraction(number)
    try:
        value = parse(unit, text)
    except QuantityError as error:
        raise read.fail(key, str(error)) from None
    if value < 0:
        raise read.fail(key, "must not be negative")
    return value


def _attribute(read: _Reader, kind: str, name: str, text: str, key: str) -> Constraint | None:
    """The parsed value of code attribute ``name`` (``None`` for a text attribute that is no query key)."""
    if name in TEXT_ATTRIBUTES:
        return None
    if name == "tolerance":
        return tolerance_of(text, read.file, key)
    if name == "case":
        if not re.fullmatch(r"[0-9]{4}", text):
            raise read.fail(key, f"must be an EIA inch code such as '0603', not {text!r}")
        return text
    if name == "series":
        if text not in SERIES:
            raise read.fail(key, f"must be one of {', '.join(SERIES)}, not {text!r}")
        return text
    if name == "dielectric":
        return text
    return _amount(read, NUMERIC_UNITS[name], text, key)


def attribute_names(kind: str) -> tuple[str, ...]:
    """The attributes a code of a ``kind`` family may state: its constraint keys but ``row``, then
    ``footprint``, ``symbol`` and ``packing``."""
    return (*(found.name for found in KEYS[kind] if found.name != "row"), *TEXT_ATTRIBUTES)


def _code(read: _Reader, kind: str, field_name: str, code: str, value: object) -> Code:
    where = f"fields.{field_name}.codes.{code}"
    if not CODE.fullmatch(code):
        raise read.fail(where, f"a code is [A-Z0-9-]+, not {code!r}")
    table = read.table(value, where)
    allowed = attribute_names(kind)
    attributes: dict[str, Constraint] = {}
    texts: dict[str, str] = {}
    for name in sorted(table):
        if name not in allowed:
            raise read.fail(
                f"{where}.{name}", f"is not an attribute of a {kind}; codes state {', '.join(allowed)}"
            )
        text = read.text(table[name], f"{where}.{name}")
        texts[name] = text
        parsed = _attribute(read, kind, name, text, f"{where}.{name}")
        if parsed is not None:
            attributes[name] = parsed
    return Code(code, MappingProxyType(attributes), MappingProxyType(texts))


def _field(read: _Reader, kind: str, name: str, value: object) -> Field:
    where = f"fields.{name}"
    if not FIELD_NAME.fullmatch(name):
        raise read.fail(where, "a field name is [a-z][a-z0-9_]*")
    table = read.table(value, where)
    read.closed(table, FIELD_KEYS, where)
    role = read.text(table.get("role", "electrical"), f"{where}.role")
    if role not in ROLES:
        raise read.fail(f"{where}.role", f"must be one of {', '.join(ROLES)}, not {role!r}")
    if "scheme" in table:
        scheme = read.text(table["scheme"], f"{where}.scheme")
        if scheme not in SCHEMES:
            raise read.fail(f"{where}.scheme", f"must be one of {', '.join(SCHEMES)}, not {scheme!r}")
        for key in ("codes", "prefer"):
            if key in table:
                raise read.fail(f"{where}.{key}", "a value field has a scheme, not codes")
        if role != "electrical":
            raise read.fail(f"{where}.role", "a value field is electrical")
        if "unit" not in table:
            raise read.fail(f"{where}.unit", "is missing: the unit one step of the code counts, such as 'pF'")
        unit = read.text(table["unit"], f"{where}.unit")
        scale = _amount(read, VALUE_UNITS[kind], f"1{unit}", f"{where}.unit")
        if scale <= 0:
            raise read.fail(f"{where}.unit", "must be above zero")
        series = read.text(table["series"], f"{where}.series") if "series" in table else ""
        if series and series not in SERIES:
            raise read.fail(f"{where}.series", f"must be one of {', '.join(SERIES)}, not {series!r}")
        return Field(name, scheme=scheme, unit=unit, scale=scale, series=series)
    for key in ("unit", "series"):
        if key in table:
            raise read.fail(f"{where}.{key}", "belongs to the value field (the one with a scheme)")
    codes_table = read.table(table.get("codes"), f"{where}.codes")
    if not codes_table:
        raise read.fail(f"{where}.codes", "must name at least one code")
    codes = tuple(_code(read, kind, name, code, codes_table[code]) for code in sorted(codes_table))
    prefer = read.text(table["prefer"], f"{where}.prefer") if "prefer" in table else ""
    return Field(name, role=role, codes=codes, prefer=prefer)


def _span(read: _Reader, kind: str, value: object, where: str) -> Span:
    table = read.table(value, where)
    read.closed(table, SPAN_KEYS, where)
    unit = VALUE_UNITS[kind]
    bounds: dict[str, Fraction] = {}
    for key in ("min", "max"):
        if key in table:
            bounds[key] = _amount(read, unit, read.text(table[key], f"{where}.{key}"), f"{where}.{key}")
    if "min" in bounds and "max" in bounds and bounds["min"] > bounds["max"]:
        raise read.fail(where, "min is above max")
    series = read.text(table["series"], f"{where}.series") if "series" in table else ""
    if series and series not in SERIES:
        raise read.fail(f"{where}.series", f"must be one of {', '.join(SERIES)}, not {series!r}")
    listed: tuple[Fraction, ...] | None = None
    if "values" in table:
        if series:
            raise read.fail(f"{where}.values", "a span takes series or values, not both")
        listed = tuple(
            sorted(
                {
                    _amount(read, unit, text, f"{where}.values")
                    for text in read.texts(table["values"], f"{where}.values")
                }
            )
        )
    return Span(bounds.get("min"), bounds.get("max"), series, listed)


def _row(
    read: _Reader, kind: str, fields: Mapping[str, Field], value: object, where: str, index: int
) -> MatrixRow:
    table = read.table(value, where)
    codes: dict[str, tuple[str, ...]] = {}
    span: Span | None = None
    for name in table:
        key = f"{where}.{name}"
        found = fields.get(name)
        if found is None:
            raise read.fail(key, f"names no field; the fields are {', '.join(fields)}")
        if found.is_value:
            span = _span(read, kind, table[name], key)
        else:
            codes[name] = tuple(sorted(set(read.texts(table[name], key))))
    return MatrixRow(index, MappingProxyType(dict(sorted(codes.items()))), span)


def _sources(read: _Reader, kind: str, value: object) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    if isinstance(value, dict):
        table = cast(dict[str, object], value)
        allowed = (*attribute_names(kind), "value")
        out: dict[str, tuple[str, ...]] = {}
        for name in sorted(table):
            if name not in allowed:
                raise read.fail(f"sources.{name}", f"names no attribute; sources name {', '.join(allowed)}")
            out[name] = read.texts(table[name], f"sources.{name}")
        return (), out
    if not isinstance(value, list):
        raise read.fail("sources", "must be a list of sources, or a table: attribute → list of sources")
    return tuple(read.text(item, "sources") for item in cast(list[object], value)), {}


def _tokens(read: _Reader, pattern: str) -> tuple[tuple[str, str], ...]:
    tokens: list[tuple[str, str]] = []
    position = 0
    while position < len(pattern):
        found = TOKEN.match(pattern, position)
        if found is None:
            raise read.fail(
                "pattern",
                f"character {position} ({pattern[position]!r}) is neither [A-Z0-9-] nor a {{field}}",
            )
        if found.group(1) is not None:
            tokens.append(("field", found.group(1)))
        elif tokens and tokens[-1][0] == "literal":
            tokens[-1] = ("literal", tokens[-1][1] + found.group(2))
        else:
            tokens.append(("literal", found.group(2)))
        position = found.end()
    if not tokens:
        raise read.fail("pattern", "is empty")
    return tuple(tokens)


def _pins(read: _Reader, value: object) -> tuple[tuple[str, str], ...]:
    table = read.table(value, "pins")
    if sorted(table) != list(PINS):
        raise read.fail("pins", f"maps exactly the symbol pins {PINS[0]} and {PINS[1]} to their pads")
    return tuple((pin, read.text(table[pin], f"pins.{pin}")) for pin in PINS)


def _reviews(read: _Reader, value: object) -> tuple[tuple[tuple[str, str], ...], ...]:
    if not isinstance(value, list):
        raise read.fail("reviewed_by", "must be a list of tables")
    out: list[tuple[tuple[str, str], ...]] = []
    for index, item in enumerate(cast(list[object], value)):
        where = f"reviewed_by[{index}]"
        table = read.table(item, where)
        read.closed(table, REVIEW_KEYS, where)
        out.append(tuple((key, read.text(table[key], f"{where}.{key}")) for key in sorted(table)))
    return tuple(out)


def parse_family(text: str, *, file: str = "") -> GrammarFamily:
    """The grammar family of the TOML ``text``; ``DeviceFormatError`` (``FEN-3004``) or
    ``DeviceFormatTooNewError`` (``FEN-3002``) naming ``file`` and the key."""
    read = _Reader(file)
    try:
        data = tomllib.loads(text, parse_float=Decimal)
    except tomllib.TOMLDecodeError as error:
        raise DeviceFormatError(f"not TOML: {error}", file=file) from None
    schema = data.get("schema")
    if isinstance(schema, str) and schema != SCHEMA:
        newer = re.fullmatch(r"fenolite\.family\.v(\d+)", schema)
        if newer is not None and int(newer.group(1)) > 1:
            raise DeviceFormatTooNewError(
                f"schema: {schema!r} is newer than this version reads", file=file, locator="schema"
            )
        raise read.fail("schema", f"must be {SCHEMA!r}, not {schema!r}")
    for key in data:
        if key not in TOP_KEYS:
            raise read.fail(key, f"unknown key; a grammar family takes {', '.join(TOP_KEYS)}")
    for key in REQUIRED:
        if key not in data:
            raise read.fail(key, "is missing")
    _no_float(read, data, "")
    texts: dict[str, str] = {}
    for key in ("id", "kind", "summary", "manufacturer", "version", "licence", "evidence", "pattern"):
        texts[key] = read.text(data[key], key)
    if not ID.fullmatch(texts["id"]):
        raise read.fail("id", f"must be <namespace>:<name>, not {texts['id']!r}")
    kind = texts["kind"]
    if kind not in KINDS:
        raise read.fail("kind", f"must be one of {', '.join(KINDS)}, not {kind!r}")
    if not VERSION.fullmatch(texts["version"]):
        raise read.fail("version", f"must be MAJOR.MINOR.PATCH, not {texts['version']!r}")
    if not LICENCE.fullmatch(texts["licence"]):
        raise read.fail("licence", f"{texts['licence']!r} is not an SPDX expression")
    if not EVIDENCE.fullmatch(texts["evidence"]):
        raise read.fail("evidence", f"{texts['evidence']!r} is not a label of the evidence vocabulary")
    for key in ("datasheet", "symbol", "footprint", "tail"):
        if key in data:
            texts[key] = read.text(data[key], key)
    if "datasheet" in texts and not URL.fullmatch(texts["datasheet"]):
        raise read.fail("datasheet", "must be an http(s) URL")
    tail = texts.get("tail", "none")
    if tail not in TAILS:
        raise read.fail("tail", f"must be one of {', '.join(TAILS)}, not {tail!r}")
    tokens = _tokens(read, texts["pattern"])
    fields_table = read.table(data["fields"], "fields")
    if not fields_table:
        raise read.fail("fields", "must name at least one field")
    fields = {name: _field(read, kind, name, fields_table[name]) for name in fields_table}
    valid_raw = data["valid"]
    if not isinstance(valid_raw, list) or not valid_raw:
        raise read.fail("valid", "must hold at least one [[valid]] row")
    valid = tuple(
        _row(read, kind, fields, item, f"valid[{index}]", index)
        for index, item in enumerate(cast(list[object], valid_raw))
    )
    value_field = next((found for found in fields.values() if found.is_value), None)
    if value_field is not None:
        for row in valid:
            where = f"valid[{row.index}].{value_field.name}"
            if row.span is None:
                raise read.fail(where, "is missing: a [[valid]] row states its value span")
            if row.span.values is None and (row.span.low is None or row.span.high is None):
                raise read.fail(where, "states min and max, or values")
            if row.span.values is None and not (row.span.series or value_field.series):
                raise read.fail(where, "names no series: give one in the row or in the value field")
    exclude_raw = data.get("exclude", [])
    if not isinstance(exclude_raw, list):
        raise read.fail("exclude", "must be a list of [[exclude]] rows")
    exclude = tuple(
        _row(read, kind, fields, item, f"exclude[{index}]", index)
        for index, item in enumerate(cast(list[object], exclude_raw))
    )
    sources, sources_by = _sources(read, kind, data["sources"])
    return GrammarFamily(
        id=texts["id"],
        kind=kind,
        summary=texts["summary"],
        manufacturer=texts["manufacturer"],
        version=texts["version"],
        licence=texts["licence"],
        evidence=texts["evidence"],
        sources=sources,
        sources_by=MappingProxyType(sources_by),
        pattern=texts["pattern"],
        tokens=tokens,
        fields=MappingProxyType(fields),
        valid=valid,
        exclude=exclude,
        tail=tail,
        datasheet=texts.get("datasheet", ""),
        symbol=texts.get("symbol", ""),
        footprint=texts.get("footprint", ""),
        pins=_pins(read, data["pins"]) if "pins" in data else DEFAULT_PINS,
        reviewed_by=_reviews(read, data["reviewed_by"]) if "reviewed_by" in data else (),
        file=file,
        texts=MappingProxyType(texts),
    )


def read_family(path: Path, *, file: str = "") -> GrammarFamily:
    """The grammar family of the file ``path`` (``file`` names it in errors, default the path)."""
    return parse_family(path.read_text(encoding="utf-8"), file=file or path.as_posix())


__all__ = [
    "KIND",
    "REQUIRED",
    "SCHEMA",
    "TOP_KEYS",
    "Code",
    "Field",
    "GrammarFamily",
    "MatrixRow",
    "Span",
    "attribute_names",
    "is_grammar",
    "parse_family",
    "read_family",
]

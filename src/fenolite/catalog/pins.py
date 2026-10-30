# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pin tables: the ``fenolite.pins.v0`` records a symbol is generated from (change c0261).

A pin table is one TOML file: a record header, an optional ``[symbol]`` table, one ``[[pin]]`` row per pin
and optional ``[[variant]]`` rows. ``parse_pins`` reads it exactly into a ``PinTable`` (no float is ever
created), ``pins_text`` writes the canonical text back and ``read_pins`` reads a file. The format is
described in ``docs/symbols.md``.

The record header (``schema``, ``id``, ``version``, ``summary``, ``licence``, ``evidence``, ``sources``,
``category``) is the minimum of change c0259's common header that a table needs; the other header keys,
the stable record id and the data tree are c0259's.
"""

from __future__ import annotations

import re
import tomllib
from decimal import Decimal
from pathlib import Path
from typing import Any, get_args

from fenolite.core.errors import FormatError
from fenolite.core.evidence import Level
from fenolite.model.circuit import PinType
from fenolite.model.library import (
    PinAlternate,
    PinGroup,
    PinRow,
    PinShape,
    PinSide,
    PinTable,
    PinVariant,
)

SCHEMA = "fenolite.pins.v0"
FORMAT_VERSION = 0
PIN_TYPES: frozenset[str] = frozenset(get_args(PinType))
PIN_SHAPES: frozenset[str] = frozenset(get_args(PinShape))
GROUPS: frozenset[str] = frozenset(g for g in get_args(PinGroup) if g)
SIDES: frozenset[str] = frozenset(s for s in get_args(PinSide) if s)
SPLIT_ABOVE = (16, 1000)
"""The bounds of ``[symbol].split_above``."""
UNIT_PINS = (8, 200)
"""The bounds of ``[symbol].unit_pins``."""

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$")
_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_REFERENCE = re.compile(r"^[A-Z][A-Z_]*$")
_SCHEMA = re.compile(r"^fenolite\.pins\.v([0-9]+)$")
_EVIDENCE = re.compile(r"^ORACLE-VERIFIED\([^()\s][^()]*\)$")
_HEADER = ("schema", "id", "version", "summary", "licence", "evidence", "sources", "category")
_TOP = frozenset((*_HEADER, "symbol", "pin", "variant"))
_REQUIRED = ("schema", "id", "version", "summary", "licence", "evidence")
_SYMBOL_KEYS = frozenset(
    ("reference", "description", "keywords", "split_above", "unit_pins", "auto_bus", "unit")
)
_ROW_KEYS = frozenset(
    ("number", "name", "type", "group", "side", "bus", "unit", "shape", "hidden", "stacked", "alternates")
)
_VARIANT_KEYS = frozenset(
    ("name", "value", "description", "datasheet", "footprint", "keywords", "fp_filters")
)


class PinsSchemaError(FormatError):
    """A pin table of a newer format version than this Fenolite reads (``FEN-3002``)."""

    cli_code = "FEN-3002"


class _Reader:
    def __init__(self, file: str) -> None:
        self.file = file

    def fail(self, where: str, message: str) -> FormatError:
        return FormatError(message, file=self.file, locator=where)

    def table(self, value: object, where: str, keys: frozenset[str]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise self.fail(where, "must be a table")
        found: dict[str, Any] = value  # pyright: ignore[reportUnknownVariableType]
        for key in found:
            if key not in keys:
                raise self.fail(f"{where}.{key}" if where else key, f"unknown key {key!r}")
        return found

    def text(self, data: dict[str, Any], key: str, where: str, *, required: bool = False) -> str:
        if key not in data:
            if required:
                raise self.fail(f"{where}.{key}" if where else key, f"missing key {key!r}")
            return ""
        value = data[key]
        if not isinstance(value, str) or not value or not value.isprintable():
            raise self.fail(f"{where}.{key}" if where else key, f"{key!r} must be non-empty printable text")
        return value

    def texts(self, data: dict[str, Any], key: str, where: str) -> tuple[str, ...]:
        value = data.get(key, [])
        here = f"{where}.{key}" if where else key
        if not isinstance(value, list):
            raise self.fail(here, f"{key!r} must be a list of text")
        items: list[object] = value  # pyright: ignore[reportUnknownVariableType]
        for item in items:
            if not isinstance(item, str) or not item or not item.isprintable():
                raise self.fail(here, f"{key!r} must be a list of non-empty printable text")
        return tuple(items)  # type: ignore[arg-type]

    def integer(self, data: dict[str, Any], key: str, where: str, low: int, high: int | None) -> int | None:
        if key not in data:
            return None
        value = data[key]
        here = f"{where}.{key}" if where else key
        bound = f"{low} … {high}" if high is not None else f"≥ {low}"
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < low
            or (high is not None and value > high)
        ):
            raise self.fail(here, f"{key!r} must be an integer {bound}")
        return value

    def boolean(self, data: dict[str, Any], key: str, where: str, default: bool) -> bool:
        if key not in data:
            return default
        value = data[key]
        if not isinstance(value, bool):
            raise self.fail(f"{where}.{key}", f"{key!r} must be true or false")
        return value

    def choice(
        self, data: dict[str, Any], key: str, where: str, allowed: frozenset[str], default: str
    ) -> str:
        if key not in data:
            return default
        value = data[key]
        if not isinstance(value, str) or value not in allowed:
            raise self.fail(f"{where}.{key}", f"{key!r} must be one of {', '.join(sorted(allowed))}")
        return value

    def rows(self, data: dict[str, Any], key: str) -> list[object]:
        value = data.get(key, [])
        if not isinstance(value, list):
            raise self.fail(key, f"{key!r} must be an array of tables ([[{key}]])")
        return value  # pyright: ignore[reportUnknownVariableType]


def _schema(data: dict[str, Any], reader: _Reader) -> None:
    value = data.get("schema")
    if value is None:
        raise reader.fail("schema", "missing key 'schema'")
    found = _SCHEMA.fullmatch(value) if isinstance(value, str) else None
    if found is None:
        raise reader.fail("schema", f"'schema' must be {SCHEMA!r}")
    if int(found.group(1)) > FORMAT_VERSION:
        raise PinsSchemaError(
            f"pin table schema {value!r} is newer than {SCHEMA!r}", file=reader.file, locator="schema"
        )
    if value != SCHEMA:
        raise reader.fail("schema", f"'schema' must be {SCHEMA!r}")


def _evidence(value: str, reader: _Reader) -> str:
    if value not in {level.value for level in Level} and not _EVIDENCE.fullmatch(value):
        raise reader.fail("evidence", f"'evidence' {value!r} is not an evidence label")
    return value


def _alternates(value: object, where: str, reader: _Reader) -> tuple[PinAlternate, ...]:
    if not isinstance(value, list):
        raise reader.fail(where, "'alternates' must be a list of { name, type, shape } tables")
    found: list[PinAlternate] = []
    items: list[object] = value  # pyright: ignore[reportUnknownVariableType]
    for index, item in enumerate(items):
        here = f"{where}[{index}]"
        data = reader.table(item, here, frozenset(("name", "type", "shape")))
        name = reader.text(data, "name", here, required=True)
        if "type" not in data:
            raise reader.fail(f"{here}.type", "missing key 'type'")
        etype = reader.choice(data, "type", here, PIN_TYPES, "")
        shape = reader.choice(data, "shape", here, PIN_SHAPES, "line")
        if any(alt.name == name for alt in found):
            raise reader.fail(f"{here}.name", f"alternate {name!r} is repeated")
        found.append(PinAlternate(name, etype, shape))  # type: ignore[arg-type]
    return tuple(found)


def _row(item: object, index: int, reader: _Reader) -> PinRow:
    where = f"pin[{index}]"
    data = reader.table(item, where, _ROW_KEYS)
    number = reader.text(data, "number", where, required=True)
    name = reader.text(data, "name", where, required=True)
    if "type" not in data:
        raise reader.fail(f"{where}.type", "missing key 'type'")
    etype = reader.choice(data, "type", where, PIN_TYPES, "")
    hidden = reader.boolean(data, "hidden", where, False)
    if hidden and etype == "power_in":
        raise reader.fail(
            f"{where}.hidden",
            "'hidden' is refused on a power_in pin: a hidden power input connects by name in one target "
            "and not in the other",
        )
    return PinRow(
        number=number,
        name=name,
        etype=etype,  # type: ignore[arg-type]
        group=reader.choice(data, "group", where, GROUPS, ""),  # type: ignore[arg-type]
        side=reader.choice(data, "side", where, SIDES, ""),  # type: ignore[arg-type]
        bus=reader.text(data, "bus", where),
        unit=reader.integer(data, "unit", where, 0, None),
        shape=reader.choice(data, "shape", where, PIN_SHAPES, "line"),  # type: ignore[arg-type]
        hidden=hidden,
        stacked=reader.texts(data, "stacked", where),
        alternates=_alternates(data["alternates"], f"{where}.alternates", reader)
        if "alternates" in data
        else (),
    )


def _check_rows(rows: list[PinRow], reader: _Reader) -> None:
    if not rows:
        raise reader.fail("pin", "a pin table needs at least one [[pin]] row")
    seen: dict[str, int] = {}
    for index, row in enumerate(rows):
        for key, number in (("number", row.number), *(("stacked", n) for n in row.stacked)):
            if number in seen:
                raise reader.fail(
                    f"pin[{index}].{key}", f"pin number {number!r} is repeated (first in pin[{seen[number]}])"
                )
            seen[number] = index
    with_unit = [row.unit is not None for row in rows]
    if any(with_unit) and not all(with_unit):
        index = with_unit.index(False)
        raise reader.fail(f"pin[{index}].unit", "'unit' must be given on every row or on none")
    units = sorted({row.unit for row in rows if row.unit})
    if any(with_unit) and units != list(range(1, len(units) + 1)):
        raise reader.fail("pin", f"units must be numbered 1 … n without a gap; the table has {units}")


def _symbol(data: dict[str, Any], reader: _Reader) -> dict[str, Any]:
    if "symbol" not in data:
        return {}
    table = reader.table(data["symbol"], "symbol", _SYMBOL_KEYS)
    found: dict[str, Any] = {}
    if "reference" in table:
        reference = table["reference"]
        if not isinstance(reference, str) or not _REFERENCE.fullmatch(reference):
            raise reader.fail("symbol.reference", "'reference' must match [A-Z][A-Z_]*")
        found["reference"] = reference
    if "description" in table:
        found["description"] = reader.text(table, "description", "symbol")
    if "keywords" in table:
        found["keywords"] = reader.texts(table, "keywords", "symbol")
    split = reader.integer(table, "split_above", "symbol", *SPLIT_ABOVE)
    if split is not None:
        found["split_above"] = split
    size = reader.integer(table, "unit_pins", "symbol", *UNIT_PINS)
    if size is not None:
        found["unit_pins"] = size
    found["auto_bus"] = reader.boolean(table, "auto_bus", "symbol", True)
    names: list[tuple[int, str]] = []
    if "unit" in table:
        value = table["unit"]
        if not isinstance(value, list):
            raise reader.fail("symbol.unit", "'unit' must be an array of tables ([[symbol.unit]])")
        items: list[object] = value  # pyright: ignore[reportUnknownVariableType]
        for index, item in enumerate(items):
            here = f"symbol.unit[{index}]"
            row = reader.table(item, here, frozenset(("number", "name")))
            if "number" not in row:
                raise reader.fail(f"{here}.number", "missing key 'number'")
            number = reader.integer(row, "number", here, 1, None)
            assert number is not None
            if any(n == number for n, _ in names):
                raise reader.fail(f"{here}.number", f"unit {number} is named twice")
            names.append((number, reader.text(row, "name", here, required=True)))
    found["unit_names"] = tuple(sorted(names))
    return found


def _variant(item: object, index: int, base: str, reader: _Reader) -> PinVariant:
    where = f"variant[{index}]"
    data = reader.table(item, where, _VARIANT_KEYS)
    name = reader.text(data, "name", where, required=True)
    if not _NAME.fullmatch(name) or name == base:
        raise reader.fail(f"{where}.name", f"variant name {name!r} must be a symbol name other than {base!r}")
    datasheet = reader.text(data, "datasheet", where)
    if datasheet and not datasheet.startswith("https://"):
        raise reader.fail(f"{where}.datasheet", "'datasheet' must be an https:// address")
    return PinVariant(
        name=name,
        value=reader.text(data, "value", where),
        description=reader.text(data, "description", where),
        datasheet=datasheet,
        footprint=reader.text(data, "footprint", where),
        keywords=reader.texts(data, "keywords", where),
        fp_filters=reader.texts(data, "fp_filters", where),
    )


def parse_pins(text: str, *, file: str = "") -> PinTable:
    """The pin table of ``text``, a ``fenolite.pins.v0`` record. ``FormatError`` (``FEN-3004``) names the
    file, the row and the key of a malformed table; ``PinsSchemaError`` (``FEN-3002``) a newer schema."""
    reader = _Reader(file)
    try:
        data = tomllib.loads(text, parse_float=Decimal)
    except tomllib.TOMLDecodeError as exc:
        raise reader.fail("", f"not TOML: {exc}") from None
    _schema(data, reader)
    reader.table(data, "", _TOP)
    for key in _REQUIRED:
        if key not in data:
            raise reader.fail(key, f"missing key {key!r}")
    record_id = reader.text(data, "id", "", required=True)
    namespace, _, name = record_id.partition(":")
    if not _NAME.fullmatch(namespace) or not _NAME.fullmatch(name):
        raise reader.fail("id", f"'id' {record_id!r} must be '<namespace>:<name>' of [A-Za-z0-9_.+-]")
    version = reader.text(data, "version", "", required=True)
    if not _VERSION.fullmatch(version):
        raise reader.fail("version", f"'version' {version!r} must be MAJOR.MINOR.PATCH")
    header = {
        "summary": reader.text(data, "summary", "", required=True),
        "licence": reader.text(data, "licence", "", required=True),
        "evidence": _evidence(reader.text(data, "evidence", "", required=True), reader),
        "sources": reader.texts(data, "sources", ""),
        "category": reader.text(data, "category", ""),
    }
    rows = [_row(item, index, reader) for index, item in enumerate(reader.rows(data, "pin"))]
    _check_rows(rows, reader)
    symbol = _symbol(data, reader)
    units = sorted({row.unit for row in rows if row.unit})
    for number, _ in symbol.get("unit_names", ()):
        if units and number > units[-1]:
            raise reader.fail("symbol.unit", f"unit {number} is named but the table has {len(units)} unit(s)")
    variants = [
        _variant(item, index, name, reader) for index, item in enumerate(reader.rows(data, "variant"))
    ]
    for index, variant in enumerate(variants):
        if any(other.name == variant.name for other in variants[:index]):
            raise reader.fail(f"variant[{index}].name", f"variant {variant.name!r} is repeated")
    return PinTable(
        name=name,
        rows=tuple(rows),
        namespace=namespace,
        version=version,
        variants=tuple(variants),
        **header,
        **symbol,
    )


def read_pins(path: str | Path) -> PinTable:
    """The pin table of the file ``path`` (UTF-8)."""
    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise FormatError(f"not UTF-8 text: {exc}", file=str(path)) from None
    return parse_pins(text, file=str(path))


# --------------------------------------------------------------------------------------------- writing


def _q(value: str) -> str:
    out: list[str] = []
    for ch in value:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04X}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def _list(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(_q(v) for v in values) + "]"


def pins_text(table: PinTable) -> str:
    """The canonical TOML of ``table``: fixed key order, rows in table order, keys at their default left
    out, LF line ends and one final newline. ``parse_pins(pins_text(t)) == t``."""
    lines = [
        f"schema = {_q(SCHEMA)}",
        f"id = {_q(f'{table.namespace}:{table.name}' if table.namespace else table.name)}",
        f"version = {_q(table.version)}",
        f"summary = {_q(table.summary)}",
        f"licence = {_q(table.licence)}",
        f"evidence = {_q(table.evidence)}",
    ]
    if table.sources:
        lines.append(f"sources = {_list(table.sources)}")
    if table.category:
        lines.append(f"category = {_q(table.category)}")
    settings: list[str] = []
    if table.reference != "U":
        settings.append(f"reference = {_q(table.reference)}")
    if table.description:
        settings.append(f"description = {_q(table.description)}")
    if table.keywords:
        settings.append(f"keywords = {_list(table.keywords)}")
    if table.split_above != 100:
        settings.append(f"split_above = {table.split_above}")
    if table.unit_pins != 48:
        settings.append(f"unit_pins = {table.unit_pins}")
    if not table.auto_bus:
        settings.append("auto_bus = false")
    if settings or table.unit_names:
        lines += ["", "[symbol]", *settings]
    for number, name in table.unit_names:
        lines += ["", "[[symbol.unit]]", f"number = {number}", f"name = {_q(name)}"]
    for row in table.rows:
        lines += [
            "",
            "[[pin]]",
            f"number = {_q(row.number)}",
            f"name = {_q(row.name)}",
            f"type = {_q(row.etype)}",
        ]
        for key, value in (("group", row.group), ("side", row.side), ("bus", row.bus)):
            if value:
                lines.append(f"{key} = {_q(value)}")
        if row.unit is not None:
            lines.append(f"unit = {row.unit}")
        if row.shape != "line":
            lines.append(f"shape = {_q(row.shape)}")
        if row.hidden:
            lines.append("hidden = true")
        if row.stacked:
            lines.append(f"stacked = {_list(row.stacked)}")
        if row.alternates:
            alternates = ", ".join(
                f"{{ name = {_q(a.name)}, type = {_q(a.etype)}"
                + (f", shape = {_q(a.shape)}" if a.shape != "line" else "")
                + " }"
                for a in row.alternates
            )
            lines.append(f"alternates = [{alternates}]")
    for variant in table.variants:
        lines += ["", "[[variant]]", f"name = {_q(variant.name)}"]
        for key, text in (
            ("value", variant.value),
            ("description", variant.description),
            ("datasheet", variant.datasheet),
            ("footprint", variant.footprint),
        ):
            if text:
                lines.append(f"{key} = {_q(text)}")
        for key, items in (("keywords", variant.keywords), ("fp_filters", variant.fp_filters)):
            if items:
                lines.append(f"{key} = {_list(items)}")
    return "\n".join(lines) + "\n"


__all__ = [
    "FORMAT_VERSION",
    "GROUPS",
    "PIN_SHAPES",
    "PIN_TYPES",
    "SCHEMA",
    "SIDES",
    "SPLIT_ABOVE",
    "UNIT_PINS",
    "PinsSchemaError",
    "parse_pins",
    "pins_text",
    "read_pins",
]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library records: pins, packages, devices and orderable parts as TOML files (change c0259,
``docs/library-records.md``).

Every record carries one header: a stable ``id``, a semantic ``version``, a ``licence``, its ``evidence``
and ``sources``, and optionally its ``origin`` (a record taken from a CC0-1.0 library), its reviews, the id
it ``replaces`` and a ``deprecated`` notice. A pins record with a ``[symbol]`` table gives a ``SymbolDef``;
a package record with ``generator = "explicit"`` gives a ``FootprintDef``; a device record is the device of
change c0248 with orderable ``[[part]]`` tables. ``parse_record`` reads one file, ``record_text`` writes the
canonical text, ``record_uid`` is a UUIDv5 of the kind and the id (never stored), and ``load_tree`` reads a
folder of records. The shipped catalog is the tree under ``fenolite/catalog/data/`` (``shipped_tree``).
"""

from __future__ import annotations

import datetime
import hashlib
import re
import tomllib
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal
from functools import cache
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Literal, cast

from fenolite.catalog import devices as devicelib
from fenolite.catalog.devices import DeviceFormatError, DeviceFormatTooNewError
from fenolite.core.coords import Point, Size
from fenolite.core.errors import Issue, Severity
from fenolite.core.ids import FENOLITE_NS, derived_id
from fenolite.core.quantities import QuantityError, angle_text, length_text, parse_angle, parse_length
from fenolite.model import canonical
from fenolite.model.board import Graphic, Pad, Padstack, PadstackLayer
from fenolite.model.library import (
    DeviceDef,
    FootprintDef,
    FootprintKind,
    PinAlternate,
    Rating,
    SymbolDef,
    SymbolGraphic,
    SymbolPin,
    SymbolUnit,
)

Kind = Literal["pins", "package", "device", "part"]
SCHEMAS: Mapping[str, Kind] = {
    "fenolite.pins.v0": "pins",
    "fenolite.package.v0": "package",
    "fenolite.device.v1": "device",
    "fenolite.device.v0": "device",
    "fenolite.part.v0": "part",
}
"""Schema → record kind. ``fenolite.device.v0`` is change c0248's format, still read."""
SCHEMA_OF: Mapping[Kind, str] = {
    "pins": "fenolite.pins.v0",
    "package": "fenolite.package.v0",
    "device": "fenolite.device.v1",
    "part": "fenolite.part.v0",
}
HEADER_KEYS: tuple[str, ...] = (
    "schema",
    "id",
    "version",
    "summary",
    "category",
    "licence",
    "evidence",
    "sources",
    "origin",
    "replaces",
    "deprecated",
    "reviewed_by",
)
HEADER_REQUIRED: tuple[str, ...] = ("schema", "id", "version", "summary", "licence", "evidence")
SHIPPED_LICENCES: tuple[str, ...] = ("CC0-1.0",)
"""The licences a ``Fenolite:`` record may carry."""
CC0 = "CC0-1.0"
VERSION = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
LICENCE = re.compile(r"[A-Za-z0-9.+-]+(?: (?:AND|OR|WITH) [A-Za-z0-9.+-]+)*")
"""An SPDX expression without parentheses: identifiers joined by ``AND``, ``OR`` or ``WITH``."""
COMMIT = re.compile(r"[0-9a-f]{40}")
LIFECYCLES: tuple[str, ...] = ("active", "nrnd", "last-time-buy", "obsolete", "unknown")
PART_KEYS: tuple[str, ...] = (
    "mpn",
    "extends",
    "summary",
    "manufacturer",
    "packing",
    "lifecycle",
    "grade",
    "datasheet",
    "properties",
    "ratings",
)
INTERFACE_KEYS: tuple[str, ...] = (
    "symbol",
    "footprint",
    "pins",
    "ground",
    "unused_pads",
    "ends",
    "ref_prefix",
)
"""Keys a part may not hold: a different interface is a different device."""
PIN_TYPES: tuple[str, ...] = (
    "input",
    "output",
    "bidirectional",
    "tri_state",
    "passive",
    "free",
    "unspecified",
    "power_in",
    "power_out",
    "open_collector",
    "open_emitter",
    "no_connect",
)
GENERATORS: tuple[str, ...] = ("explicit",)
"""The package generators this version provides; a family name of change c0260 is stored and refused at
use with ``library.generator-missing``."""
DIMENSION_KEYS: tuple[str, ...] = ("pins", "pitch", "body", "span", "lead", "land")
INFERRED_LAND = "; land pattern remains INFERRED and requires part-specific review"
"""The end of the description of an ``INFERRED`` footprint (living "Source and evidence labels")."""
LIBRARY = "fenolite.catalog"
"""The backend part of the model ids of record definitions (the catalog's ids before the move)."""
LIBRARY_ISSUE_CODES: Mapping[str, Severity] = {
    "library.deprecated": "warning",
    "library.review-stale": "info",
    "library.generator-missing": "error",
}
"""The issue codes of records used by a build (change c0259)."""


# ------------------------------------------------------------------------------------------- types


@dataclass(frozen=True, slots=True)
class Origin:
    """Where a record taken from a CC0-1.0 library came from."""

    library: str
    version: str
    element: str
    licence: str


@dataclass(frozen=True, slots=True)
class Review:
    """One review of a record: who, when, of which version and digest, and the label asserted."""

    who: str
    date: str
    version: str
    digest: str
    evidence: str
    sheet: str = ""


@dataclass(frozen=True, slots=True)
class Deprecation:
    by: str
    since: str
    reason: str


@dataclass(frozen=True, slots=True)
class Header:
    """The header every record carries. ``sources`` is the list form, ``sources_by`` the table form
    (attribute → source ids)."""

    schema: str
    id: str
    version: str
    summary: str
    licence: str
    evidence: str
    category: str = ""
    sources: tuple[str, ...] = field(default=(), metadata={"ordered": True})
    sources_by: dict[str, tuple[str, ...]] = field(default_factory=lambda: {})
    origin: Origin | None = None
    replaces: str = ""
    deprecated: Deprecation | None = None
    reviewed_by: tuple[Review, ...] = field(default=(), metadata={"ordered": True})

    @property
    def namespace(self) -> str:
        return self.id.split(":", 1)[0]

    @property
    def name(self) -> str:
        return self.id.split(":", 1)[1]


@dataclass(frozen=True, slots=True)
class PinEntry:
    """A pin of a pins record."""

    number: str
    name: str
    type: str
    shape: str = "line"
    hidden: bool = False
    unit: int = 1
    group: str = ""
    alternates: tuple[PinAlternate, ...] = field(default=(), metadata={"ordered": True})


@dataclass(frozen=True, slots=True)
class PinPlacement:
    """Where the ``[symbol]`` table of a pins record draws one pin."""

    number: str
    at: Point
    rotation: int = 0
    length: int = 0
    body_style: int = 1


@dataclass(frozen=True, slots=True)
class SymbolDrawing:
    """The explicit drawing of a pins record."""

    reference: str
    value: str = ""
    pin_names_hidden: bool = False
    pin_numbers_hidden: bool = False
    pin_name_offset: int | None = None
    units: tuple[SymbolUnit, ...] = field(default=(SymbolUnit(1, 1),), metadata={"ordered": True})
    placements: tuple[PinPlacement, ...] = field(default=(), metadata={"ordered": True})
    graphics: tuple[SymbolGraphic, ...] = field(default=(), metadata={"ordered": True})


@dataclass(frozen=True, slots=True)
class PinsRecord:
    header: Header
    pins: tuple[PinEntry, ...] = field(default=(), metadata={"ordered": True})
    symbol: SymbolDrawing | None = None
    polarity: str = ""


@dataclass(frozen=True, slots=True)
class PadstackEntry:
    hole_shape: str = "round"
    hole_length: int | None = None
    hole_rotation: int = 0
    layers: tuple[PadstackLayer, ...] = field(default=(), metadata={"ordered": True})


@dataclass(frozen=True, slots=True)
class PadEntry:
    """A pad of an explicit package; ``key`` names its model id when it is not the number."""

    number: str
    shape: str
    size: Size
    at: Point
    key: str = ""
    kind: str = "smd"
    rotation: int = 0
    drill: int | None = None
    layers: tuple[str, ...] = field(default=(), metadata={"ordered": True})
    corner_ratio: int | None = None
    mask_margin: int | None = None
    padstack: PadstackEntry | None = None


@dataclass(frozen=True, slots=True)
class GraphicEntry:
    """A graphic of an explicit package; ``key`` names its model id when it is not the layer."""

    kind: str
    layer: str
    points: tuple[Point, ...] = field(default=(), metadata={"ordered": True})
    width: int = 0
    filled: bool = False
    key: str = ""


@dataclass(frozen=True, slots=True)
class PackageRecord:
    header: Header
    generator: str = "explicit"
    kind: str = "unspecified"
    flags: tuple[str, ...] = field(default=(), metadata={"ordered": True})
    dimensions: dict[str, tuple[int, ...]] = field(default_factory=lambda: {})
    pad1: str = ""
    pads: tuple[PadEntry, ...] = field(default=(), metadata={"ordered": True})
    graphics: tuple[GraphicEntry, ...] = field(default=(), metadata={"ordered": True})


@dataclass(frozen=True, slots=True)
class PartEntry:
    """An orderable variant of a device: only orderable facts, never its interface."""

    mpn: str
    extends: str = ""
    summary: str = ""
    manufacturer: str = ""
    packing: str = ""
    lifecycle: str = ""
    grade: str = ""
    datasheet: str = ""
    properties: dict[str, str] = field(default_factory=lambda: {})
    ratings: tuple[Rating, ...] = field(default=(), metadata={"ordered": True})


@dataclass(frozen=True, slots=True)
class DeviceRecord:
    header: Header
    device: DeviceDef
    parts: tuple[PartEntry, ...] = field(default=(), metadata={"ordered": True})


@dataclass(frozen=True, slots=True)
class PartRecord:
    header: Header
    device: str
    part: PartEntry


Record = PinsRecord | PackageRecord | DeviceRecord | PartRecord


def kind_of(record: Record) -> Kind:
    if isinstance(record, PinsRecord):
        return "pins"
    if isinstance(record, PackageRecord):
        return "package"
    if isinstance(record, DeviceRecord):
        return "device"
    return "part"


# ----------------------------------------------------------------------------------------- reading

_Reader = devicelib._Reader  # pyright: ignore[reportPrivateUsage]
_NONE: list[object] = []


class GeneratorMissingError(ValueError):
    """A pins or package record without explicit geometry, whose generator this version lacks."""


def _length(read: _Reader, value: object, key: str) -> int:
    text = read.text(value, key)
    try:
        return parse_length(text)
    except QuantityError as error:
        raise read.fail(key, str(error)) from None


def _angle(read: _Reader, value: object, key: str) -> int:
    text = read.text(value, key)
    try:
        return parse_angle(text)
    except QuantityError as error:
        raise read.fail(key, str(error)) from None


def _pair(read: _Reader, value: object, key: str) -> tuple[int, int]:
    if not isinstance(value, list) or len(cast(list[object], value)) != 2:
        raise read.fail(key, 'must be a two-element array of lengths, such as ["0.8mm", "0mm"]')
    items = cast(list[object], value)
    return _length(read, items[0], key), _length(read, items[1], key)


def _point(read: _Reader, value: object, key: str) -> Point:
    return Point(*_pair(read, value, key))


def _int(read: _Reader, value: object, key: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise read.fail(key, f"must be an integer of at least {minimum}")
    return value


def _bool(read: _Reader, value: object, key: str) -> bool:
    if not isinstance(value, bool):
        raise read.fail(key, "must be a boolean")
    return value


def _choice(read: _Reader, value: object, key: str, choices: Sequence[str]) -> str:
    text = read.text(value, key)
    if text not in choices:
        raise read.fail(key, f"must be one of {', '.join(choices)}, not {text!r}")
    return text


def _closed(read: _Reader, table: Mapping[str, object], keys: Sequence[str], where: str) -> None:
    unknown = sorted(set(table) - set(keys))
    if unknown:
        name = f"{where}.{unknown[0]}" if where else unknown[0]
        raise read.fail(name, f"unknown key; {where or 'the record'} takes {', '.join(keys)}")


def _tables(read: _Reader, value: object, key: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise read.fail(key, "must be an array of tables")
    return [read.table(item, key) for item in cast(list[object], value)]


def _sources(read: _Reader, value: object) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    def ids(items: object, key: str) -> tuple[str, ...]:
        found = read.texts(items, key)
        for source in found:
            if not devicelib.SOURCE.fullmatch(source):
                raise read.fail(key, f"{source!r} is not a source id (S-NNNN)")
        return found

    if isinstance(value, dict):
        table = cast(dict[str, object], value)
        return (), {key: ids(table[key], f"sources.{key}") for key in sorted(table)}
    return ids(value, "sources"), {}


def _header(read: _Reader, data: Mapping[str, object], kind: Kind) -> Header:
    schema = read.text(data.get("schema"), "schema")
    for key in HEADER_REQUIRED:
        if key not in data:
            raise read.fail(key, "is missing")
    record_id = read.text(data["id"], "id")
    checked = record_id.split("@", 1)[0] if kind == "part" else record_id
    if not devicelib.ID.fullmatch(checked):
        raise read.fail(
            "id", f"must be <namespace>:<name>, each matching [A-Za-z0-9_.+-]+, not {record_id!r}"
        )
    version = read.text(data["version"], "version")
    if not VERSION.fullmatch(version):
        raise read.fail("version", f"must be MAJOR.MINOR.PATCH without leading zeros, not {version!r}")
    licence = read.text(data["licence"], "licence")
    if not LICENCE.fullmatch(licence):
        raise read.fail("licence", f"{licence!r} is not an SPDX expression")
    evidence = read.text(data["evidence"], "evidence")
    if not devicelib.EVIDENCE.fullmatch(evidence):
        raise read.fail("evidence", f"{evidence!r} is not a label of the evidence vocabulary")
    sources, sources_by = _sources(read, data.get("sources", _NONE))
    shipped = record_id.split(":", 1)[0] == devicelib.SHIPPED_NAMESPACE
    if shipped and not (sources or sources_by):
        raise read.fail("sources", f"a {devicelib.SHIPPED_NAMESPACE}: record needs its sources")
    origin = None
    if "origin" in data:
        table = read.table(data["origin"], "origin")
        names = ("library", "version", "element", "licence")
        _closed(read, table, names, "origin")
        for name in names:
            if name not in table:
                raise read.fail(f"origin.{name}", "is missing")
        origin = Origin(*(read.text(table[name], f"origin.{name}") for name in names))
        if origin.licence != CC0:
            raise read.fail("origin.licence", f"must be {CC0}: only data of a CC0-1.0 library may be used")
        if licence != CC0:
            raise read.fail("licence", f"a record with an origin is {CC0}")
    if shipped and licence not in SHIPPED_LICENCES:
        raise read.fail(
            "licence", f"a {devicelib.SHIPPED_NAMESPACE}: record is {' or '.join(SHIPPED_LICENCES)}"
        )
    deprecated = None
    if "deprecated" in data:
        table = read.table(data["deprecated"], "deprecated")
        _closed(read, table, ("by", "since", "reason"), "deprecated")
        for name in ("by", "since", "reason"):
            if name not in table:
                raise read.fail(f"deprecated.{name}", "is missing")
        deprecated = Deprecation(
            *(read.text(table[name], f"deprecated.{name}") for name in ("by", "since", "reason"))
        )
        if not devicelib.ID.fullmatch(deprecated.by) or not VERSION.fullmatch(deprecated.since):
            raise read.fail("deprecated", "names the successor's id and a MAJOR.MINOR.PATCH version")
    reviews: list[Review] = []
    for index, table in enumerate(_tables(read, data.get("reviewed_by", _NONE), "reviewed_by")):
        where = f"reviewed_by[{index}]"
        names = ("who", "date", "version", "digest", "evidence", "sheet")
        _closed(read, table, names, where)
        values = {
            name: read.text(table.get(name, ""), f"{where}.{name}", empty=name == "sheet") for name in names
        }
        if "@" in values["who"]:
            raise read.fail(f"{where}.who", "names a person, never an e-mail address")
        try:
            datetime.date.fromisoformat(values["date"])
        except ValueError:
            raise read.fail(f"{where}.date", "must be an ISO 8601 date") from None
        if not VERSION.fullmatch(values["version"]) or not devicelib.DIGEST.fullmatch(values["digest"]):
            raise read.fail(where, "holds a MAJOR.MINOR.PATCH version and a 64-hex digest")
        if not devicelib.EVIDENCE.fullmatch(values["evidence"]):
            raise read.fail(f"{where}.evidence", "is not a label of the evidence vocabulary")
        if values["sheet"].startswith(("/", "\\")) or ".." in values["sheet"].split("/"):
            raise read.fail(f"{where}.sheet", "is a path relative to the tree")
        reviews.append(Review(**values))
    replaces = read.text(data.get("replaces", ""), "replaces", empty=True)
    if replaces and not devicelib.ID.fullmatch(replaces):
        raise read.fail("replaces", "names an id")
    return Header(
        schema=schema,
        id=record_id,
        version=version,
        summary=read.text(data["summary"], "summary"),
        licence=licence,
        evidence=evidence,
        category=read.text(data.get("category", ""), "category", empty=True),
        sources=sources,
        sources_by=sources_by,
        origin=origin,
        replaces=replaces,
        deprecated=deprecated,
        reviewed_by=tuple(reviews),
    )


_PIN_SHAPES = ("line", "inverted", "clock", "inverted_clock", "input_low", "clock_low", "output_low",
               "edge_clock_high", "non_logic")  # fmt: skip
_PIN_KEYS = ("number", "name", "type", "shape", "hidden", "unit", "group", "alternates")
_SYMBOL_KEYS = ("reference", "value", "pin_names_hidden", "pin_numbers_hidden", "pin_name_offset", "units",
                "pins", "graphic")  # fmt: skip


def _pins_record(read: _Reader, header: Header, data: Mapping[str, object]) -> PinsRecord:
    _closed(read, data, (*HEADER_KEYS, "pin", "symbol", "polarity"), "")
    pins: list[PinEntry] = []
    for index, table in enumerate(_tables(read, data.get("pin", _NONE), "pin")):
        where = f"pin[{index}]"
        _closed(read, table, _PIN_KEYS, where)
        if "number" not in table or "type" not in table or "name" not in table:
            raise read.fail(where, "needs number, name and type")
        number = read.text(table["number"], f"{where}.number")
        if any(pin.number == number for pin in pins):
            raise read.fail(where, f"pin {number} is listed twice")
        alternates = tuple(
            PinAlternate(
                read.text(item.get("name"), f"{where}.alternates.name"),
                cast("object", _choice(read, item.get("type"), f"{where}.alternates.type", PIN_TYPES)),  # type: ignore[arg-type]
                cast(
                    "object",
                    _choice(read, item.get("shape", "line"), f"{where}.alternates.shape", _PIN_SHAPES),
                ),  # type: ignore[arg-type]
            )
            for item in _tables(read, table.get("alternates", _NONE), f"{where}.alternates")
        )
        pins.append(
            PinEntry(
                number=number,
                name=read.text(table["name"], f"{where}.name", empty=True),
                type=_choice(read, table["type"], f"{where}.type", PIN_TYPES),
                shape=_choice(read, table.get("shape", "line"), f"{where}.shape", _PIN_SHAPES),
                hidden=_bool(read, table.get("hidden", False), f"{where}.hidden"),
                unit=_int(read, table.get("unit", 1), f"{where}.unit"),
                group=read.text(table.get("group", ""), f"{where}.group", empty=True),
                alternates=alternates,
            )
        )
    if not pins:
        raise read.fail("pin", "a pins record lists at least one pin")
    symbol = None
    if "symbol" in data:
        table = read.table(data["symbol"], "symbol")
        _closed(read, table, _SYMBOL_KEYS, "symbol")
        numbers = [pin.number for pin in pins]
        placements: list[PinPlacement] = []
        for item in _tables(read, table.get("pins", _NONE), "symbol.pins"):
            _closed(read, item, ("number", "at", "rotation", "length", "body_style"), "symbol.pins")
            number = read.text(item.get("number"), "symbol.pins.number")
            if number not in numbers:
                raise read.fail("symbol.pins", f"places pin {number}, which the record does not list")
            if any(found.number == number for found in placements):
                raise read.fail("symbol.pins", f"places pin {number} twice")
            placements.append(
                PinPlacement(
                    number,
                    _point(read, item.get("at"), f"symbol.pins.{number}.at"),
                    _angle(read, item.get("rotation", "0deg"), f"symbol.pins.{number}.rotation"),
                    _length(read, item.get("length", "0mm"), f"symbol.pins.{number}.length"),
                    _int(read, item.get("body_style", 1), f"symbol.pins.{number}.body_style"),
                )
            )
        missing = [number for number in numbers if all(found.number != number for found in placements)]
        if missing:
            raise read.fail("symbol.pins", f"places no pin {missing[0]}")
        units = tuple(
            SymbolUnit(
                _int(read, item.get("unit"), "symbol.units.unit"),
                _int(read, item.get("body_style", 1), "symbol.units.body_style"),
                read.text(item.get("name", ""), "symbol.units.name", empty=True),
            )
            for item in _tables(read, table.get("units", [{"unit": 1, "body_style": 1}]), "symbol.units")
        )
        graphics: list[SymbolGraphic] = []
        for index, item in enumerate(_tables(read, table.get("graphic", _NONE), "symbol.graphic")):
            where = f"symbol.graphic[{index}]"
            _closed(read, item, ("kind", "points", "width", "filled"), where)
            points = item.get("points", _NONE)
            if not isinstance(points, list):
                raise read.fail(f"{where}.points", "must be an array of points")
            graphics.append(
                SymbolGraphic(
                    cast(
                        "object",
                        _choice(
                            read, item.get("kind"), f"{where}.kind", ("line", "circle", "rect", "polygon")
                        ),
                    ),  # type: ignore[arg-type]
                    tuple(_point(read, point, f"{where}.points") for point in cast(list[object], points)),
                    _length(read, item.get("width", "0.254mm"), f"{where}.width"),
                    _bool(read, item.get("filled", False), f"{where}.filled"),
                )
            )
        offset = table.get("pin_name_offset")
        symbol = SymbolDrawing(
            reference=read.text(table.get("reference"), "symbol.reference"),
            value=read.text(table.get("value", header.name), "symbol.value", empty=True),
            pin_names_hidden=_bool(read, table.get("pin_names_hidden", False), "symbol.pin_names_hidden"),
            pin_numbers_hidden=_bool(
                read, table.get("pin_numbers_hidden", False), "symbol.pin_numbers_hidden"
            ),
            pin_name_offset=None if offset is None else _length(read, offset, "symbol.pin_name_offset"),
            units=units,
            placements=tuple(sorted(placements, key=lambda found: numbers.index(found.number))),
            graphics=tuple(graphics),
        )
    polarity = read.text(data.get("polarity", ""), "polarity", empty=True)
    if polarity not in ("", "anode-first"):
        raise read.fail("polarity", "is 'anode-first' or absent")
    return PinsRecord(header, tuple(pins), symbol, polarity)


_PAD_KEYS = ("number", "key", "shape", "size", "at", "kind", "rotation", "drill", "layers", "corner_ratio",
             "mask_margin", "padstack")  # fmt: skip
_PAD_SHAPES = ("circle", "rect", "oval", "roundrect", "trapezoid", "chamfered_rect", "custom")
_PAD_KINDS = ("smd", "thru_hole", "np_thru_hole", "connect")


def _dimensions(read: _Reader, data: Mapping[str, object]) -> dict[str, tuple[int, ...]]:
    found: dict[str, tuple[int, ...]] = {}

    def bound(value: object, key: str) -> tuple[int, ...]:
        text = read.text(value, key)
        if ".." in text:
            low, high = (_length(read, part, key) for part in text.split("..", 1))
            if low > high:
                raise read.fail(key, "the minimum of the range is above its maximum")
            return (low, high)
        return (_length(read, text, key),)

    if "pins" in data:
        found["pins"] = (_int(read, data["pins"], "pins", minimum=1),)
    if "pitch" in data:
        found["pitch"] = bound(data["pitch"], "pitch")
    for key in ("body", "span", "lead", "land"):
        if key in data:
            table = read.table(data[key], key)
            for name in sorted(table):
                found[f"{key}.{name}"] = bound(table[name], f"{key}.{name}")
    return found


def _package_record(read: _Reader, header: Header, data: Mapping[str, object]) -> PackageRecord:
    _closed(
        read,
        data,
        (*HEADER_KEYS, "generator", "kind", "flags", "pad1", "pad", "graphic", *DIMENSION_KEYS),
        "",
    )
    if "generator" not in data or "kind" not in data:
        raise read.fail("generator" if "generator" not in data else "kind", "is missing")
    generator = read.text(data["generator"], "generator")
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", generator):
        raise read.fail("generator", "is 'explicit' or the name of a package family")
    pads: list[PadEntry] = []
    for index, table in enumerate(_tables(read, data.get("pad", _NONE), "pad")):
        where = f"pad[{index}]"
        _closed(read, table, _PAD_KEYS, where)
        for name in ("number", "shape", "size", "at"):
            if name not in table:
                raise read.fail(f"{where}.{name}", "is missing")
        padstack = None
        if "padstack" in table:
            stack = read.table(table["padstack"], f"{where}.padstack")
            _closed(
                read, stack, ("hole_shape", "hole_length", "hole_rotation", "layers"), f"{where}.padstack"
            )
            layers = tuple(
                PadstackLayer(
                    read.text(item.get("layer"), f"{where}.padstack.layers.layer"),
                    cast(
                        "object",
                        _choice(read, item.get("shape"), f"{where}.padstack.layers.shape", _PAD_SHAPES),
                    ),  # type: ignore[arg-type]
                    Size(*_pair(read, item.get("size"), f"{where}.padstack.layers.size")),
                    _point(read, item.get("offset", ["0mm", "0mm"]), f"{where}.padstack.layers.offset"),
                )
                for item in _tables(read, stack.get("layers", _NONE), f"{where}.padstack.layers")
            )
            hole_length = stack.get("hole_length")
            padstack = PadstackEntry(
                _choice(
                    read, stack.get("hole_shape", "round"), f"{where}.padstack.hole_shape", ("round", "slot")
                ),
                None if hole_length is None else _length(read, hole_length, f"{where}.padstack.hole_length"),
                _angle(read, stack.get("hole_rotation", "0deg"), f"{where}.padstack.hole_rotation"),
                layers,
            )
        drill, ratio, margin = table.get("drill"), table.get("corner_ratio"), table.get("mask_margin")
        pads.append(
            PadEntry(
                number=read.text(table["number"], f"{where}.number", empty=True),
                shape=_choice(read, table["shape"], f"{where}.shape", _PAD_SHAPES),
                size=Size(*_pair(read, table["size"], f"{where}.size")),
                at=_point(read, table["at"], f"{where}.at"),
                key=read.text(table.get("key", ""), f"{where}.key", empty=True),
                kind=_choice(read, table.get("kind", "smd"), f"{where}.kind", _PAD_KINDS),
                rotation=_angle(read, table.get("rotation", "0deg"), f"{where}.rotation"),
                drill=None if drill is None else _length(read, drill, f"{where}.drill"),
                layers=read.texts(table.get("layers", _NONE), f"{where}.layers"),
                corner_ratio=None if ratio is None else _int(read, ratio, f"{where}.corner_ratio"),
                mask_margin=None if margin is None else _signed_length(read, margin, f"{where}.mask_margin"),
                padstack=padstack,
            )
        )
    graphics: list[GraphicEntry] = []
    for index, table in enumerate(_tables(read, data.get("graphic", _NONE), "graphic")):
        where = f"graphic[{index}]"
        _closed(read, table, ("kind", "layer", "points", "width", "filled", "key"), where)
        points = table.get("points", _NONE)
        if not isinstance(points, list):
            raise read.fail(f"{where}.points", "must be an array of points")
        graphics.append(
            GraphicEntry(
                kind=_choice(
                    read,
                    table.get("kind"),
                    f"{where}.kind",
                    ("line", "rect", "circle", "arc", "polygon", "curve"),
                ),
                layer=read.text(table.get("layer"), f"{where}.layer"),
                points=tuple(_point(read, point, f"{where}.points") for point in cast(list[object], points)),
                width=_length(read, table.get("width", "0mm"), f"{where}.width"),
                filled=_bool(read, table.get("filled", False), f"{where}.filled"),
                key=read.text(table.get("key", ""), f"{where}.key", empty=True),
            )
        )
    pad1 = read.text(data.get("pad1", ""), "pad1", empty=True)
    if pad1 not in ("", "cathode"):
        raise read.fail("pad1", "is 'cathode' or absent")
    return PackageRecord(
        header=header,
        generator=generator,
        kind=_choice(read, data["kind"], "kind", ("smd", "through_hole", "unspecified")),
        flags=read.texts(data.get("flags", _NONE), "flags"),
        dimensions=_dimensions(read, data),
        pad1=pad1,
        pads=tuple(pads),
        graphics=tuple(graphics),
    )


def _signed_length(read: _Reader, value: object, key: str) -> int:
    return _length(read, value, key)


def _part(read: _Reader, table: Mapping[str, object], where: str) -> PartEntry:
    for key in INTERFACE_KEYS:
        if key in table:
            raise DeviceFormatError(
                f"{where}.{key}: a part may not set {key}; a different interface is a different device",
                file=read.file,
                locator=f"{where}.{key}",
            )
    _closed(read, table, PART_KEYS, where)
    if "mpn" not in table:
        raise read.fail(f"{where}.mpn", "is missing")
    lifecycle = read.text(table.get("lifecycle", ""), f"{where}.lifecycle", empty=True)
    if lifecycle and lifecycle not in LIFECYCLES:
        raise read.fail(f"{where}.lifecycle", f"is one of {', '.join(LIFECYCLES)}")
    datasheet = read.text(table.get("datasheet", ""), f"{where}.datasheet", empty=True)
    if datasheet and not datasheet.startswith("https://"):
        raise read.fail(f"{where}.datasheet", "must be an https:// URL")
    ratings: list[Rating] = []
    if "ratings" in table:
        rated = read.table(table["ratings"], f"{where}.ratings")
        for key in sorted(rated):
            if key not in devicelib.RATINGS:
                raise read.fail(
                    f"{where}.ratings.{key}", f"unknown rating; use {', '.join(devicelib.RATINGS)}"
                )
            ratings.append(devicelib._rating(read, key, rated[key], f"{where}.ratings.{key}"))  # pyright: ignore[reportPrivateUsage]
    properties = (
        devicelib._properties(read, table["properties"]) if "properties" in table else {}  # pyright: ignore[reportPrivateUsage]
    )
    return PartEntry(
        mpn=read.text(table["mpn"], f"{where}.mpn"),
        extends=read.text(table.get("extends", ""), f"{where}.extends", empty=True),
        summary=read.text(table.get("summary", ""), f"{where}.summary", empty=True),
        manufacturer=read.text(table.get("manufacturer", ""), f"{where}.manufacturer", empty=True),
        packing=read.text(table.get("packing", ""), f"{where}.packing", empty=True),
        lifecycle=lifecycle,
        grade=read.text(table.get("grade", ""), f"{where}.grade", empty=True),
        datasheet=datasheet,
        properties=properties,
        ratings=tuple(ratings),
    )


def _check_parts(read: _Reader, device: DeviceDef, parts: Sequence[PartEntry]) -> None:
    """Unique MPNs, known ``extends`` without cycles, and part ratings within the device's."""
    by_mpn: dict[str, PartEntry] = {}
    for part in parts:
        if part.mpn in by_mpn:
            raise read.fail("part.mpn", f"part {part.mpn} is listed twice")
        by_mpn[part.mpn] = part
    for part in parts:
        seen = [part.mpn]
        step = part
        while step.extends:
            if step.extends not in by_mpn:
                raise read.fail(
                    "part.extends", f"part {step.mpn} extends {step.extends}, which the device lacks"
                )
            if step.extends in seen:
                raise read.fail(
                    "part.extends", f"parts {' and '.join(sorted({*seen, step.extends}))} extend each other"
                )
            seen.append(step.extends)
            step = by_mpn[step.extends]
        for rating in part.ratings:
            own = device.rating(rating.key)
            if own is None:
                continue
            low = own.min is not None and (rating.min is None or rating.min < own.min)
            high = own.max is not None and (rating.max is None or rating.max > own.max)
            if low or high:
                raise read.fail(
                    f"part.{part.mpn}.ratings.{rating.key}",
                    f"is wider than the device's {rating.key}; a part may only narrow a rating",
                )


def _device_record(read: _Reader, header: Header, data: Mapping[str, object]) -> DeviceRecord:
    body = {key: value for key, value in data.items() if key not in HEADER_KEYS and key != "part"}
    sources = header.sources or tuple(sorted({s for ids in header.sources_by.values() for s in ids}))
    legacy: dict[str, object] = {
        **body,
        "schema": devicelib.SCHEMA,
        "id": header.id,
        "summary": header.summary,
        "evidence": header.evidence,
    }
    if sources:
        legacy["sources"] = list(sources)
    for key in devicelib.RESERVED:
        if key in body:
            raise DeviceFormatTooNewError(
                f"{key}: reserved for a later device format ({devicelib.RESERVED[key]})",
                file=read.file,
                locator=key,
            )
    unknown = sorted(set(body) - set(devicelib.KEYS))
    if unknown:
        raise read.fail(unknown[0], "unknown key")
    device = devicelib.parse_device_data(legacy, file=read.file)
    parts = tuple(
        _part(read, table, f"part[{index}]")
        for index, table in enumerate(_tables(read, data.get("part", _NONE), "part"))
    )
    _check_parts(read, device, parts)
    return DeviceRecord(header, device, parts)


def _part_record(read: _Reader, header: Header, data: Mapping[str, object]) -> PartRecord:
    if "device" not in data:
        raise read.fail("device", "is missing")
    device = read.text(data["device"], "device")
    if not devicelib.ID.fullmatch(device):
        raise read.fail("device", "names a device id")
    table = {key: value for key, value in data.items() if key not in HEADER_KEYS and key != "device"}
    part = _part(read, table, "part")
    if header.id != f"{device}@{part.mpn}":
        raise read.fail("id", f"a part's id is <device id>@<mpn>: {device}@{part.mpn}")
    return PartRecord(header, device, part)


def _newer(schema: str) -> bool:
    match = re.fullmatch(r"fenolite\.(pins|package|device|part)\.v(\d+)", schema)
    if match is None:
        return False
    known = max(int(name.rsplit(".v", 1)[1]) for name in SCHEMAS if name.split(".")[1] == match.group(1))
    return int(match.group(2)) > known


def parse_record(text: str, *, file: str = "") -> Record:
    """The record of the TOML ``text`` (capability library-records, "Library record kinds"). ``file`` names
    it in errors. A malformed record raises ``DeviceFormatError`` (FEN-3004), a newer schema
    ``DeviceFormatTooNewError`` (FEN-3002)."""
    read = _Reader(file)
    try:
        data = tomllib.loads(text, parse_float=Decimal)
    except tomllib.TOMLDecodeError as error:
        raise DeviceFormatError(f"not TOML: {error}", file=file) from None
    schema = data.get("schema")
    if not isinstance(schema, str):
        raise read.fail("schema", "is missing")
    if schema not in SCHEMAS:
        if _newer(schema):
            raise DeviceFormatTooNewError(
                f"schema: {schema!r} is newer than this version reads", file=file, locator="schema"
            )
        raise read.fail("schema", f"must be one of {', '.join(SCHEMAS)}, not {schema!r}")
    kind = SCHEMAS[schema]
    if schema == devicelib.SCHEMA:
        device = devicelib.parse_device_data(data, file=file)
        return DeviceRecord(
            Header(schema, device.id, "0.0.0", device.summary, "", device.evidence, sources=device.sources),
            device,
        )
    header = _header(read, data, kind)
    record: Record
    if kind == "pins":
        record = _pins_record(read, header, data)
    elif kind == "package":
        record = _package_record(read, header, data)
    elif kind == "device":
        record = _device_record(read, header, data)
    else:
        record = _part_record(read, header, data)
    if header.origin is not None and header.evidence != "UNVERIFIED":
        digest = record_digest(record)
        if not any(review.digest == digest for review in header.reviewed_by):
            raise read.fail(
                "evidence", "a record with an origin stays UNVERIFIED until a review of its current digest"
            )
    return record


# ----------------------------------------------------------------------------------------- writing

_string = devicelib._string  # pyright: ignore[reportPrivateUsage]
_key = devicelib._key  # pyright: ignore[reportPrivateUsage]
_strings = devicelib._strings  # pyright: ignore[reportPrivateUsage]


def _len(value: int) -> str:
    return _string(length_text(value))


def _ang(value: int) -> str:
    return _string(angle_text(value))


def _pt(point: Point) -> str:
    return f"[{_len(point.x)}, {_len(point.y)}]"


def _inline(pairs: Sequence[tuple[str, str]]) -> str:
    return "{ " + ", ".join(f"{key} = {value}" for key, value in pairs) + " }"


def _header_lines(header: Header, kind: Kind) -> list[str]:
    lines = [
        f"schema = {_string(SCHEMA_OF[kind])}",
        f"id = {_string(header.id)}",
        f"version = {_string(header.version)}",
        f"summary = {_string(header.summary)}",
    ]
    if header.category:
        lines.append(f"category = {_string(header.category)}")
    lines += [f"licence = {_string(header.licence)}", f"evidence = {_string(header.evidence)}"]
    if header.sources:
        lines.append(f"sources = {_strings(header.sources)}")
    elif header.sources_by:
        lines.append(
            "sources = " + _inline([(_key(k), _strings(v)) for k, v in sorted(header.sources_by.items())])
        )  # pyright: ignore[reportPrivateUsage]
    if header.origin is not None:
        o = header.origin
        lines.append(
            "origin = "
            + _inline(
                [
                    (k, _string(v))
                    for k, v in (
                        ("library", o.library),
                        ("version", o.version),
                        ("element", o.element),
                        ("licence", o.licence),
                    )
                ]
            )
        )
    if header.replaces:
        lines.append(f"replaces = {_string(header.replaces)}")
    if header.deprecated is not None:
        d = header.deprecated
        lines.append(
            "deprecated = "
            + _inline([("by", _string(d.by)), ("since", _string(d.since)), ("reason", _string(d.reason))])
        )
    return lines


def _review_lines(header: Header) -> list[str]:
    lines: list[str] = []
    for review in header.reviewed_by:
        lines += ["", "[[reviewed_by]]"]
        for key in ("who", "date", "version", "digest", "evidence", "sheet"):
            value = getattr(review, key)
            if value:
                lines.append(f"{key} = {_string(value)}")
    return lines


def _pins_text(record: PinsRecord) -> list[str]:
    lines = _header_lines(record.header, "pins")
    if record.polarity:
        lines.append(f"polarity = {_string(record.polarity)}")
    for pin in record.pins:
        lines += [
            "",
            "[[pin]]",
            f"number = {_string(pin.number)}",
            f"name = {_string(pin.name)}",
            f"type = {_string(pin.type)}",
        ]
        if pin.shape != "line":
            lines.append(f"shape = {_string(pin.shape)}")
        if pin.hidden:
            lines.append("hidden = true")
        if pin.unit != 1:
            lines.append(f"unit = {pin.unit}")
        if pin.group:
            lines.append(f"group = {_string(pin.group)}")
        if pin.alternates:
            items = [
                _inline([("name", _string(a.name)), ("type", _string(a.etype)), ("shape", _string(a.shape))])
                for a in pin.alternates
            ]
            lines.append("alternates = [" + ", ".join(items) + "]")
    drawing = record.symbol
    if drawing is not None:
        lines += ["", "[symbol]", f"reference = {_string(drawing.reference)}"]
        if drawing.value != record.header.name:
            lines.append(f"value = {_string(drawing.value)}")
        if drawing.pin_names_hidden:
            lines.append("pin_names_hidden = true")
        if drawing.pin_numbers_hidden:
            lines.append("pin_numbers_hidden = true")
        if drawing.pin_name_offset is not None:
            lines.append(f"pin_name_offset = {_len(drawing.pin_name_offset)}")
        if drawing.units != (SymbolUnit(1, 1),):
            units = [
                _inline(
                    [("unit", str(u.unit)), ("body_style", str(u.body_style))]
                    + ([("name", _string(u.name))] if u.name else [])
                )
                for u in drawing.units
            ]
            lines.append("units = [" + ", ".join(units) + "]")
        lines.append("pins = [")
        for place in drawing.placements:
            pairs = [("number", _string(place.number)), ("at", _pt(place.at))]
            if place.rotation:
                pairs.append(("rotation", _ang(place.rotation)))
            if place.length:
                pairs.append(("length", _len(place.length)))
            if place.body_style != 1:
                pairs.append(("body_style", str(place.body_style)))
            lines.append(f"  {_inline(pairs)},")
        lines.append("]")
        for graphic in drawing.graphics:
            lines += ["", "[[symbol.graphic]]", f"kind = {_string(graphic.kind)}"]
            lines.append("points = [" + ", ".join(_pt(p) for p in graphic.points) + "]")
            if graphic.width != 254_000:
                lines.append(f"width = {_len(graphic.width)}")
            if graphic.filled:
                lines.append("filled = true")
    return lines


def _bound(values: tuple[int, ...]) -> str:
    return _string("..".join(length_text(value) for value in values))


def _package_text(record: PackageRecord) -> list[str]:
    lines = _header_lines(record.header, "package")
    lines += [f"generator = {_string(record.generator)}", f"kind = {_string(record.kind)}"]
    if record.flags:
        lines.append(f"flags = {_strings(record.flags)}")
    if record.pad1:
        lines.append(f"pad1 = {_string(record.pad1)}")
    dims = record.dimensions
    if "pins" in dims:
        lines.append(f"pins = {dims['pins'][0]}")
    if "pitch" in dims:
        lines.append(f"pitch = {_bound(dims['pitch'])}")
    for group in ("body", "span", "lead", "land"):
        names = sorted(key.split(".", 1)[1] for key in dims if key.startswith(f"{group}."))
        if names:
            lines.append(f"{group} = " + _inline([(_key(n), _bound(dims[f"{group}.{n}"])) for n in names]))  # pyright: ignore[reportPrivateUsage]
    for pad in record.pads:
        lines += ["", "[[pad]]", f"number = {_string(pad.number)}"]
        if pad.key:
            lines.append(f"key = {_string(pad.key)}")
        lines += [
            f"shape = {_string(pad.shape)}",
            f"size = [{_len(pad.size.w)}, {_len(pad.size.h)}]",
            f"at = {_pt(pad.at)}",
        ]
        if pad.kind != "smd":
            lines.append(f"kind = {_string(pad.kind)}")
        if pad.rotation:
            lines.append(f"rotation = {_ang(pad.rotation)}")
        if pad.drill is not None:
            lines.append(f"drill = {_len(pad.drill)}")
        if pad.layers:
            lines.append(f"layers = {_strings(pad.layers)}")
        if pad.corner_ratio is not None:
            lines.append(f"corner_ratio = {pad.corner_ratio}")
        if pad.mask_margin is not None:
            lines.append(f"mask_margin = {_len(pad.mask_margin)}")
        if pad.padstack is not None:
            stack = pad.padstack
            pairs = [("hole_shape", _string(stack.hole_shape))]
            if stack.hole_length is not None:
                pairs.append(("hole_length", _len(stack.hole_length)))
            if stack.hole_rotation:
                pairs.append(("hole_rotation", _ang(stack.hole_rotation)))
            if stack.layers:
                layers = [
                    _inline(
                        [
                            ("layer", _string(layer.layer)),
                            ("shape", _string(layer.shape)),
                            ("size", f"[{_len(layer.size.w)}, {_len(layer.size.h)}]"),
                            ("offset", _pt(layer.offset)),
                        ]
                    )
                    for layer in stack.layers
                ]
                pairs.append(("layers", "[" + ", ".join(layers) + "]"))
            lines.append(f"padstack = {_inline(pairs)}")
    for graphic in record.graphics:
        lines += ["", "[[graphic]]"]
        if graphic.key:
            lines.append(f"key = {_string(graphic.key)}")
        lines += [f"kind = {_string(graphic.kind)}", f"layer = {_string(graphic.layer)}"]
        lines.append("points = [" + ", ".join(_pt(p) for p in graphic.points) + "]")
        if graphic.width:
            lines.append(f"width = {_len(graphic.width)}")
        if graphic.filled:
            lines.append("filled = true")
    return lines


def _part_lines(part: PartEntry) -> list[str]:
    lines = [f"mpn = {_string(part.mpn)}"]
    for key in ("extends", "summary", "manufacturer", "packing", "lifecycle", "grade", "datasheet"):
        value = getattr(part, key)
        if value:
            lines.append(f"{key} = {_string(value)}")
    if part.properties:
        lines.append(
            "properties = " + _inline([(_string(k), _string(v)) for k, v in sorted(part.properties.items())])
        )
    if part.ratings:
        lines.append("ratings = " + _inline([(r.key, devicelib._rating_text(r)) for r in part.ratings]))  # pyright: ignore[reportPrivateUsage]
    return lines


def _device_text(record: DeviceRecord) -> list[str]:
    if record.header.schema == devicelib.SCHEMA:
        return devicelib.device_text(record.device).rstrip("\n").split("\n")
    lines = _header_lines(record.header, "device")
    lines += devicelib.device_text(record.device, header=False).rstrip("\n").split("\n")
    for part in record.parts:
        lines += ["", "[[part]]", *_part_lines(part)]
    return lines


def record_text(record: Record) -> str:
    """The canonical TOML of ``record``: a fixed key order per kind, the arrays in their order, LF line ends
    and one final newline; ``parse_record(record_text(r)) == r``."""
    if isinstance(record, PinsRecord):
        lines = _pins_text(record)
    elif isinstance(record, PackageRecord):
        lines = _package_text(record)
    elif isinstance(record, DeviceRecord):
        lines = _device_text(record)
    else:
        lines = [
            *_header_lines(record.header, "part"),
            f"device = {_string(record.device)}",
            *_part_lines(record.part),
        ]
    if not (isinstance(record, DeviceRecord) and record.header.schema == devicelib.SCHEMA):
        lines += _review_lines(record.header)
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------ definitions


def symbol_def(record: PinsRecord) -> SymbolDef:
    """The ``SymbolDef`` of a pins record with a ``[symbol]`` table; ``GeneratorMissingError`` without one."""
    drawing = record.symbol
    header = record.header
    if drawing is None:
        raise GeneratorMissingError(
            f"{header.id}: the pins record has no [symbol] drawing and no symbol generator is installed"
        )
    places = {place.number: place for place in drawing.placements}
    return SymbolDef(
        id=derived_id("sym", LIBRARY, header.id),
        native_ids={"fenolite": header.id},
        name=header.name,
        library=header.namespace,
        properties={"Reference": drawing.reference, "Value": drawing.value, "Description": header.summary},
        pin_names_hidden=drawing.pin_names_hidden,
        pin_numbers_hidden=drawing.pin_numbers_hidden,
        pin_name_offset=drawing.pin_name_offset,
        units=drawing.units,
        pins=tuple(
            SymbolPin(
                number=pin.number,
                name=pin.name,
                etype=cast("object", pin.type),  # type: ignore[arg-type]
                position=places[pin.number].at,
                shape=cast("object", pin.shape),  # type: ignore[arg-type]
                rotation=places[pin.number].rotation,
                length=places[pin.number].length,
                unit=pin.unit,
                body_style=places[pin.number].body_style,
                hidden=pin.hidden,
                alternates=pin.alternates,
            )
            for pin in record.pins
        ),
        graphics=drawing.graphics,
    )


def footprint_def(record: PackageRecord) -> FootprintDef:
    """The ``FootprintDef`` of an explicit package record; ``GeneratorMissingError`` for a family package
    whose generator this version lacks."""
    header = record.header
    if record.generator not in GENERATORS:
        raise GeneratorMissingError(
            f"{header.id}: the package generator {record.generator!r} is not installed"
        )
    name = header.name
    description = header.summary + (INFERRED_LAND if header.evidence == "INFERRED" else "")
    pads: list[Pad] = []
    for pad in record.pads:
        key = f"{name}:{pad.key or pad.number}"
        stack = pad.padstack
        pads.append(
            Pad(
                id=derived_id("pad", LIBRARY, key),
                number=pad.number,
                shape=cast("object", pad.shape),  # type: ignore[arg-type]
                size=pad.size,
                position=pad.at,
                kind=cast("object", pad.kind),  # type: ignore[arg-type]
                rotation=pad.rotation,
                drill=pad.drill,
                layers=pad.layers,
                corner_ratio=pad.corner_ratio,
                mask_margin=pad.mask_margin,
                padstack=None
                if stack is None
                else Padstack(
                    id=derived_id("pst", LIBRARY, key),
                    layers=stack.layers,
                    hole_shape=cast("object", stack.hole_shape),  # type: ignore[arg-type]
                    hole_length=stack.hole_length,
                    hole_rotation=stack.hole_rotation,
                ),
            )
        )
    graphics = tuple(
        Graphic(
            id=derived_id("gfx", LIBRARY, f"{name}:{graphic.key or graphic.layer}"),
            kind=cast("object", graphic.kind),  # type: ignore[arg-type]
            layer=graphic.layer,
            points=graphic.points,
            width=graphic.width,
            filled=graphic.filled,
        )
        for graphic in record.graphics
    )
    return FootprintDef(
        id=derived_id("fpd", LIBRARY, header.id),
        native_ids={"fenolite": header.id},
        name=name,
        library=header.namespace,
        description=description,
        kind=cast(FootprintKind, record.kind),
        flags=record.flags,
        pads=tuple(pads),
        graphics=graphics,
    )


def _chain(parts: Sequence[PartEntry], mpn: str) -> list[PartEntry]:
    """The ``extends`` chain of part ``mpn``, from the root to the part; ``KeyError`` for an unknown MPN."""
    by_mpn = {part.mpn: part for part in parts}
    chain: list[PartEntry] = []
    step: PartEntry | None = by_mpn[mpn]
    while step is not None and step not in chain:
        chain.insert(0, step)
        step = by_mpn.get(step.extends) if step.extends else None
    return chain


def resolved_part(parts: Sequence[PartEntry], mpn: str) -> PartEntry:
    """The part ``mpn`` with everything it inherits: each ancestor of its ``extends`` chain from the root,
    then the part; a later level replaces a key, properties merge by key and ratings replace by key."""
    result = PartEntry(mpn=mpn)
    for part in _chain(parts, mpn):
        ratings = {rating.key: rating for rating in result.ratings} | {
            rating.key: rating for rating in part.ratings
        }
        result = PartEntry(
            mpn=mpn,
            extends=part.extends if part.mpn == mpn else result.extends,
            summary=part.summary or result.summary,
            manufacturer=part.manufacturer or result.manufacturer,
            packing=part.packing or result.packing,
            lifecycle=part.lifecycle or result.lifecycle,
            grade=part.grade or result.grade,
            datasheet=part.datasheet or result.datasheet,
            properties={**result.properties, **part.properties},
            ratings=tuple(ratings[key] for key in sorted(ratings)),
        )
    return result


def effective_part(device: DeviceDef, parts: Sequence[PartEntry], mpn: str) -> DeviceDef:
    """The device ``device`` as the orderable part ``mpn`` of ``parts`` (``resolved_part`` on top of the
    device): its MPN, manufacturer, datasheet, summary, properties (merged by key) and ratings (replaced by
    key). Its id is ``<device id>@<mpn>``. ``KeyError`` when no part has the MPN."""
    part = resolved_part(parts, mpn)
    ratings = {rating.key: rating for rating in device.ratings} | {
        rating.key: rating for rating in part.ratings
    }
    return replace(
        device,
        id=f"{device.id}@{mpn}",
        mpn=mpn,
        summary=part.summary or device.summary,
        manufacturer=part.manufacturer or device.manufacturer,
        datasheet=part.datasheet or device.datasheet,
        properties={**device.properties, **part.properties},
        ratings=tuple(ratings[key] for key in sorted(ratings)),
    )


# ----------------------------------------------------------------------------------------- digests


def record_uid(kind: str, record_id: str) -> str:
    """The stable uid of a record: a UUIDv5 of its kind and id in Fenolite's namespace (never stored)."""
    return str(uuid.uuid5(FENOLITE_NS, f"fenolite.library:{kind}:{record_id}"))


def _sha(value: object) -> str:
    return hashlib.sha256(canonical.dumps(value).encode("utf-8")).hexdigest()


def record_digest(record: Record) -> str:
    """The SHA-256 of the canonical JSON of ``record`` without its reviews."""
    return _sha(replace(record, header=replace(record.header, reviewed_by=())))


def output_digest(record: Record) -> str:
    """The SHA-256 of the canonical JSON of the definition ``record`` gives (for a pins or package record
    without geometry: of the record's data without its header)."""
    if isinstance(record, PinsRecord):
        return _sha(symbol_def(record)) if record.symbol is not None else _sha(replace(record, header=_BLANK))
    if isinstance(record, PackageRecord):
        if record.generator in GENERATORS:
            return _sha(footprint_def(record))
        return _sha(replace(record, header=_BLANK))
    if isinstance(record, DeviceRecord):
        return _sha(DeviceRecord(_BLANK, replace(record.device, provenance=None), record.parts))
    return _sha(replace(record, header=_BLANK))


_BLANK = Header("", "", "", "", "", "")


@dataclass(frozen=True, slots=True)
class _Interface:
    kind: str
    items: tuple[tuple[str, ...], ...]


def interface_digest(record: Record) -> str:
    """The SHA-256 of the interface of ``record``: a pins record's pins (number, name, type) and units, a
    package's pad numbers and kind, a device's symbol, footprint and functions with their pins and pads, a
    part's device and MPN."""
    if isinstance(record, PinsRecord):
        units = record.symbol.units if record.symbol is not None else ()
        items = tuple(sorted((pin.number, pin.name, pin.type, str(pin.unit)) for pin in record.pins))
        items += tuple(("unit", str(unit.unit), str(unit.body_style)) for unit in units)
    elif isinstance(record, PackageRecord):
        items = (("kind", record.kind), *sorted({("pad", pad.number) for pad in record.pads if pad.number}))
    elif isinstance(record, DeviceRecord):
        device = record.device
        items = (("symbol", device.symbol), ("footprint", device.footprint))
        items += tuple((pin.function, *(f"{a}:{b}" for a, b in pin.pin_pads)) for pin in device.pins)
    else:
        items = (("device", record.device), ("mpn", record.part.mpn))
    return _sha(_Interface(kind_of(record), items))


def stale_reviews(record: Record) -> bool:
    """Whether the record has reviews and its newest names another digest."""
    reviews = record.header.reviewed_by
    return bool(reviews) and reviews[-1].digest != record_digest(record)


# ------------------------------------------------------------------------------------------- trees


@dataclass(frozen=True, slots=True)
class LibraryTree:
    """The records of one folder: ``records`` in path order (part files joined to the devices of the same
    tree in ``parts``), ``files`` the path of each record by kind and id."""

    records: tuple[Record, ...] = ()
    files: Mapping[tuple[str, str], str] = field(default_factory=lambda: {})
    parts: Mapping[str, tuple[PartEntry, ...]] = field(default_factory=lambda: {})

    def get(self, kind: Kind, record_id: str) -> Record | None:
        for record in self.records:
            if kind_of(record) == kind and record.header.id == record_id:
                return record
        return None

    def of_kind(self, kind: Kind) -> tuple[Record, ...]:
        return tuple(record for record in self.records if kind_of(record) == kind)

    def devices(self) -> tuple[DeviceDef, ...]:
        return tuple(record.device for record in self.records if isinstance(record, DeviceRecord))


def _walk(root: Traversable, prefix: str = "") -> list[tuple[str, Traversable]]:
    found: list[tuple[str, Traversable]] = []
    for entry in root.iterdir():
        path = f"{prefix}{entry.name}"
        if entry.is_dir():
            found += _walk(entry, f"{path}/")
        elif entry.name.endswith(".toml") and entry.name != "VERSIONS.toml":
            found.append((path, entry))
    return found


def load_tree(root: Path | Traversable, *, label: str = "", shipped: bool = False) -> LibraryTree:
    """Every record below ``root`` in POSIX path order. ``label`` prefixes the paths in errors. Two
    records of one kind and id raise ``DeviceFormatError`` naming both files; a ``replaces`` must name a
    record of the tree deprecated by it. ``shipped`` refuses c0248's ``v0`` device files."""
    if isinstance(root, Path) and not root.is_dir():
        return LibraryTree()
    records: list[Record] = []
    files: dict[tuple[str, str], str] = {}
    for path, entry in sorted(_walk(root), key=lambda item: item[0]):
        name = f"{label}{path}"
        record = parse_record(entry.read_text(encoding="utf-8"), file=name)
        key = (kind_of(record), record.header.id)
        if key in files:
            raise DeviceFormatError(
                f"id: {key[0]} {key[1]} is defined in {files[key]} and in {name}", file=name, locator="id"
            )
        if shipped and record.header.schema == devicelib.SCHEMA:
            raise DeviceFormatError(
                "schema: a shipped device is fenolite.device.v1", file=name, locator="schema"
            )
        files[key] = name
        records.append(record)
    for record in records:
        target_id = record.header.replaces
        if not target_id:
            continue
        target = next(
            (r for r in records if kind_of(r) == kind_of(record) and r.header.id == target_id), None
        )
        if (
            target is None
            or target.header.deprecated is None
            or target.header.deprecated.by != record.header.id
        ):
            name = files[(kind_of(record), record.header.id)]
            raise DeviceFormatError(
                f"replaces: {target_id} is not deprecated by {record.header.id} in this tree",
                file=name,
                locator="replaces",
            )
    parts: dict[str, list[PartEntry]] = {}
    for record in records:
        if isinstance(record, DeviceRecord):
            parts.setdefault(record.header.id, []).extend(record.parts)
    for record in records:
        if isinstance(record, PartRecord):
            joined = parts.setdefault(record.device, [])
            if any(part.mpn == record.part.mpn for part in joined):
                name = files[("part", record.header.id)]
                raise DeviceFormatError(
                    f"mpn: part {record.part.mpn} of {record.device} is defined twice",
                    file=name,
                    locator="mpn",
                )
            joined.append(record.part)
    for record in records:
        if isinstance(record, DeviceRecord):
            name = files[("device", record.header.id)]
            _check_parts(_Reader(name), record.device, parts[record.header.id])
    return LibraryTree(tuple(records), files, {key: tuple(value) for key, value in parts.items()})


DATA = "data"


@cache
def shipped_tree() -> LibraryTree:
    """The shipped catalog: every record under ``fenolite/catalog/data/``, read once per process."""
    return load_tree(resources.files("fenolite.catalog") / DATA, label="fenolite/catalog/data/", shipped=True)


def library_issue(code: str, message: str, where: str, hint: str = "") -> Issue:
    return Issue(code, LIBRARY_ISSUE_CODES[code], message, where=where, hint=hint)


def used_record_issues(records: Sequence[Record]) -> list[Issue]:
    """``library.deprecated`` and ``library.review-stale``, once per record that a build uses."""
    found: list[Issue] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (kind_of(record), record.header.id)
        if key in seen:
            continue
        seen.add(key)
        notice = record.header.deprecated
        if notice is not None:
            found.append(
                library_issue(
                    "library.deprecated",
                    f"{key[0]} {key[1]} is deprecated since {notice.since}: {notice.reason}; use {notice.by}",
                    key[1],
                    f"move to {notice.by}",
                )
            )
        if stale_reviews(record):
            found.append(
                library_issue(
                    "library.review-stale",
                    f"{key[0]} {key[1]} changed after its last review",
                    key[1],
                    "review the record again",
                )
            )
    return found


# ---------------------------------------------------------------------------------------- versions

VERSIONS_FILE = "VERSIONS.toml"
UPDATE_HINT = "run `uv run python tools/catalog/versions.py --update` after the review"


@dataclass(frozen=True, slots=True)
class VersionEntry:
    """What ``VERSIONS.toml`` records of one shipped id."""

    kind: str
    id: str
    version: str = ""
    digest: str = ""
    output: str = ""
    interface: str = ""
    removed: bool = False


@dataclass(frozen=True, slots=True)
class Versions:
    catalog_version: str
    entries_sha256: str
    entries: tuple[VersionEntry, ...]


def version_entry(record: Record) -> VersionEntry:
    return VersionEntry(
        kind_of(record),
        record.header.id,
        record.header.version,
        record_digest(record),
        output_digest(record),
        interface_digest(record),
    )


def _entries_text(entries: Sequence[VersionEntry]) -> str:
    lines: list[str] = []
    for entry in sorted(entries, key=lambda item: (item.kind, item.id)):
        lines += ["", "[[entry]]", f"kind = {_string(entry.kind)}", f"id = {_string(entry.id)}"]
        if entry.removed:
            lines.append("removed = true")
        for key in ("version", "digest", "output", "interface"):
            value = getattr(entry, key)
            if value:
                lines.append(f"{key} = {_string(value)}")
    return "\n".join(lines) + "\n"


def entries_sha256(entries: Sequence[VersionEntry]) -> str:
    return hashlib.sha256(_entries_text(entries).encode("utf-8")).hexdigest()


def versions_text(versions: Versions) -> str:
    head = [
        "# The version of every shipped library record (change c0259, docs/library-records.md).",
        "# Written by tools/catalog/versions.py --update; tests/unit/catalog/test_versions.py checks it.",
        "",
        "[catalog]",
        f"version = {_string(versions.catalog_version)}",
        f"entries = {_string(versions.entries_sha256)}",
    ]
    return "\n".join(head) + "\n" + _entries_text(versions.entries)


def read_versions(text: str, *, file: str = VERSIONS_FILE) -> Versions:
    read = _Reader(file)
    data = tomllib.loads(text)
    catalog_table = read.table(data.get("catalog"), "catalog")
    entries: list[VersionEntry] = []
    for table in _tables(read, data.get("entry", _NONE), "entry"):
        entries.append(
            VersionEntry(
                kind=read.text(table.get("kind"), "entry.kind"),
                id=read.text(table.get("id"), "entry.id"),
                version=read.text(table.get("version", ""), "entry.version", empty=True),
                digest=read.text(table.get("digest", ""), "entry.digest", empty=True),
                output=read.text(table.get("output", ""), "entry.output", empty=True),
                interface=read.text(table.get("interface", ""), "entry.interface", empty=True),
                removed=_bool(read, table.get("removed", False), "entry.removed"),
            )
        )
    return Versions(
        read.text(catalog_table.get("version"), "catalog.version"),
        read.text(catalog_table.get("entries"), "catalog.entries"),
        tuple(entries),
    )


def _parts(version: str) -> tuple[int, int, int]:
    major, minor, patch = (int(part) for part in version.split("."))
    return major, minor, patch


def version_problems(records: Sequence[Record], versions: Versions) -> list[str]:
    """The ways ``records`` (the shipped tree) break the version rules against ``versions``: a missing
    entry, a reused removed id, a MAJOR other than 1, an interface changed under an id, a changed
    definition without a MINOR version, a changed record without a new version, a stale file."""
    problems: list[str] = []
    recorded = {(entry.kind, entry.id): entry for entry in versions.entries}
    present: set[tuple[str, str]] = set()
    for record in records:
        current = version_entry(record)
        key = (current.kind, current.id)
        present.add(key)
        if VERSION.fullmatch(current.version) and _parts(current.version)[0] != 1:
            problems.append(
                f"{current.id}: MAJOR stays 1 for the life of an id; an interface change is a new id"
            )
        old = recorded.get(key)
        if old is None:
            problems.append(f"{current.id}: not in {VERSIONS_FILE}; {UPDATE_HINT}")
            continue
        if old.removed:
            problems.append(f"{current.id}: the id was removed and must not be used again; choose a new id")
            continue
        if old == current:
            continue
        if old.interface != current.interface:
            problems.append(
                f"{current.id}: its interface changed; an interface change needs a new id with replaces, "
                "and a deprecation of this one"
            )
        elif old.output != current.output and not (
            _parts(current.version)[0] == _parts(old.version)[0]
            and _parts(current.version)[1] > _parts(old.version)[1]
        ):
            problems.append(
                f"{current.id}: its definition changed; give it a MINOR version above {old.version}"
            )
        elif old.digest != current.digest and _parts(current.version) <= _parts(old.version):
            problems.append(f"{current.id}: the record changed; give it a PATCH version above {old.version}")
        else:
            problems.append(f"{current.id}: {VERSIONS_FILE} is stale; {UPDATE_HINT}")
    for entry in versions.entries:
        if not entry.removed and (entry.kind, entry.id) not in present:
            problems.append(f"{entry.id}: in {VERSIONS_FILE} but not shipped; mark it removed = true")
    if entries_sha256(versions.entries) != versions.entries_sha256:
        problems.append(f"{VERSIONS_FILE}: the catalog entries digest is stale; {UPDATE_HINT}")
    return problems


def updated_versions(records: Sequence[Record], versions: Versions) -> Versions:
    """``versions`` rewritten for ``records``: removed ids kept and marked, the catalog version raised
    (PATCH) when any entry changed."""
    current = {(kind_of(record), record.header.id): version_entry(record) for record in records}
    entries = list(current.values())
    for entry in versions.entries:
        if (entry.kind, entry.id) not in current:
            entries.append(VersionEntry(entry.kind, entry.id, removed=True))
    digest = entries_sha256(entries)
    catalog_version = versions.catalog_version
    if digest != entries_sha256(versions.entries):
        major, minor, patch = _parts(catalog_version)
        catalog_version = f"{major}.{minor}.{patch + 1}"
    return Versions(catalog_version, digest, tuple(sorted(entries, key=lambda item: (item.kind, item.id))))


@cache
def shipped_versions() -> Versions:
    text = (resources.files("fenolite.catalog") / DATA / VERSIONS_FILE).read_text(encoding="utf-8")
    return read_versions(text, file=f"fenolite/catalog/data/{VERSIONS_FILE}")


def catalog_version() -> str:
    """``CATALOG_VERSION``: the version of the shipped catalog, raised whenever an entry of
    ``VERSIONS.toml`` changes."""
    return shipped_versions().catalog_version


__all__ = [
    "CC0",
    "COMMIT",
    "DATA",
    "DIMENSION_KEYS",
    "GENERATORS",
    "HEADER_KEYS",
    "HEADER_REQUIRED",
    "INFERRED_LAND",
    "INTERFACE_KEYS",
    "LIBRARY",
    "LIBRARY_ISSUE_CODES",
    "LICENCE",
    "LIFECYCLES",
    "PART_KEYS",
    "PIN_TYPES",
    "SCHEMAS",
    "SCHEMA_OF",
    "SHIPPED_LICENCES",
    "UPDATE_HINT",
    "VERSION",
    "VERSIONS_FILE",
    "Deprecation",
    "DeviceRecord",
    "GeneratorMissingError",
    "GraphicEntry",
    "Header",
    "Kind",
    "LibraryTree",
    "Origin",
    "PackageRecord",
    "PadEntry",
    "PadstackEntry",
    "PartEntry",
    "PartRecord",
    "PinEntry",
    "PinPlacement",
    "PinsRecord",
    "Record",
    "Review",
    "SymbolDrawing",
    "VersionEntry",
    "Versions",
    "catalog_version",
    "effective_part",
    "entries_sha256",
    "footprint_def",
    "interface_digest",
    "kind_of",
    "library_issue",
    "load_tree",
    "output_digest",
    "parse_record",
    "read_versions",
    "record_digest",
    "record_text",
    "record_uid",
    "resolved_part",
    "shipped_tree",
    "shipped_versions",
    "stale_reviews",
    "symbol_def",
    "updated_versions",
    "used_record_issues",
    "version_entry",
    "version_problems",
    "versions_text",
]

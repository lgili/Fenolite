# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Device records (``fenolite.device.v0``; change c0248, ``docs/devices.md``).

A device is one reviewed TOML record that joins a symbol, a footprint, the map from pin function to pins and
pads, an identity, ratings and an evidence label. ``parse_device`` reads one record into a
``fenolite.model.library.DeviceDef`` (no float is created: TOML floats are read as ``Decimal`` and refused),
``device_text`` writes the canonical text, ``device_digest`` is the SHA-256 of the record without its
provenance, ``load_devices`` reads the ``*.toml`` files of a folder and ``check_device`` compares a device
with the symbol and the footprint it names. The shipped ``Fenolite:`` devices live in ``devices/`` beside
this module and are read by ``shipped_devices``.

Change c0274 splits every limit into ``abs_max`` and ``operating`` (the single ``{ min, max }`` form is
refused), adds ``[[limits]]`` between two functions, logic thresholds on pins, the ``class`` key and
temperatures in millikelvin.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from functools import cache
from importlib import resources
from pathlib import Path
from typing import cast

from fenolite.core.errors import FormatError, Issue
from fenolite.core.quantities import MICRO_UNITS, QuantityError, celsius_text, decimal_digits, micro_units
from fenolite.model import canonical
from fenolite.model.library import (
    DeviceDef,
    DevicePin,
    DeviceProvenance,
    FootprintDef,
    LimitKind,
    PinPairLimit,
    Rating,
    RatingUnit,
    SymbolDef,
    Threshold,
    ThresholdKey,
)
from fenolite.model.rules import PART_CLASSES

SCHEMA = "fenolite.device.v0"
SHIPPED_NAMESPACE = "Fenolite"
KEYS: tuple[str, ...] = (
    "schema",
    "id",
    "summary",
    "manufacturer",
    "mpn",
    "datasheet",
    "symbol",
    "footprint",
    "ref_prefix",
    "class",
    "value",
    "evidence",
    "sources",
    "ground",
    "unused_pads",
    "ends",
    "properties",
    "pins",
    "ratings",
    "limits",
    "provenance",
)
"""Every key of a record, in the order of the canonical text."""
REQUIRED: tuple[str, ...] = ("schema", "id", "summary", "symbol", "footprint", "evidence", "pins")
RESERVED: Mapping[str, str] = {"interfaces": "c0252", "options": "c0257"}
"""Keys kept for a later format, with the change that defines each."""
ID = re.compile(r"[A-Za-z0-9_.+-]+:[A-Za-z0-9_.+-]+")
FUNCTION = re.compile(r"[A-Za-z_][A-Za-z0-9_+.~-]*")
REF_PREFIX = re.compile(r"[A-Z][A-Z_]*")
SOURCE = re.compile(r"S-\d{4,}")
EVIDENCE = re.compile(
    r"KICAD-VERIFIED|CORPUS-VERIFIED|INFERRED|UNKNOWN|UNVERIFIED"
    r"|ORACLE-VERIFIED\([^()\s][^()]*\)|ALTIUM-VERIFIED\((kit|author-report)(;[^()]*)?\)"
)
"""One label of the evidence vocabulary (``AGENTS.md``, "Conventions")."""
RATINGS: Mapping[str, str] = {
    "voltage": "volt",
    "current": "ampere",
    "power": "watt",
    "temperature": "kelvin",
}
"""Rating key → the unit its values are read in (a temperature in kelvin, from ``K`` or ``degC`` texts)."""
LIMIT_KINDS: tuple[LimitKind, ...] = ("abs_max", "operating")
"""The kinds of a limit (change c0274), in the order of the canonical text."""
THRESHOLDS: Mapping[str, str] = {
    "input_high_min": "volt",
    "input_low_max": "volt",
    "output_current_max": "ampere",
    "output_high_min": "volt",
    "output_low_max": "volt",
}
"""Logic threshold of a pin → the unit it is read in (change c0274)."""
PIN_RATINGS: tuple[str, ...] = ("voltage", "current")
PIN_KEYS: tuple[str, ...] = ("pins", "map", "voltage", "current", *THRESHOLDS, "must_connect")
LIMIT_KEYS: tuple[str, ...] = ("between", "voltage")
"""The keys of a ``[[limits]]`` table."""
SPLIT_HINT = "say abs_max (an absolute maximum rating) or operating (the range the part needs to work)"
RESERVED_PROPERTIES: frozenset[str] = frozenset(
    {"Reference", "Value", "Footprint", "Datasheet", "Description", "Manufacturer", "MPN"}
)
"""Names a device property cannot take (compared after ``str.casefold``): the part's own fields, and the
two that the device's ``manufacturer`` and ``mpn`` give."""
RESERVED_PREFIXES: tuple[str, ...] = ("fenolite.", "ki_")
DIGEST = re.compile(r"[0-9a-f]{64}")
IMPORT_TOOL = "fenolite catalog import"
EDITED_CODE = "device.edited"
MISMATCH_CODE = "build.device-mismatch"
_BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")
_NONE: list[object] = []


class DeviceFormatError(FormatError):
    """A malformed device record (FEN-3004); the message names the file and the key."""

    cli_code = "FEN-3004"

    @property
    def code(self) -> str:
        return self.cli_code


class DeviceLimitFormError(DeviceFormatError):
    """A limit that does not say ``abs_max`` or ``operating`` (FEN-3004; change c0274)."""

    hint = SPLIT_HINT


class DeviceFormatTooNewError(DeviceFormatError):
    """A device record of a newer schema, or with a key reserved for a later format (FEN-3002)."""

    cli_code = "FEN-3002"
    hint = "upgrade fenolite, or remove the key until the format that defines it is supported"


# ----------------------------------------------------------------------------------------- reading


class _Reader:
    """The checks of one record; every error names ``file`` and the key path."""

    def __init__(self, file: str) -> None:
        self.file = file

    def fail(self, key: str, message: str) -> DeviceFormatError:
        return DeviceFormatError(f"{key}: {message}", file=self.file, locator=key)

    def text(self, value: object, key: str, *, empty: bool = False) -> str:
        if not isinstance(value, str):
            raise self.fail(key, f"must be a string, not {_kind(value)}")
        if not empty and not value:
            raise self.fail(key, "must not be empty")
        if not value.isprintable():
            raise self.fail(key, "must be printable text on one line")
        return value

    def texts(self, value: object, key: str) -> tuple[str, ...]:
        if not isinstance(value, list):
            raise self.fail(key, f"must be a list of strings, not {_kind(value)}")
        items = tuple(self.text(item, key) for item in cast(list[object], value))
        if len(set(items)) != len(items):
            raise self.fail(key, "lists an entry twice")
        return items

    def table(self, value: object, key: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise self.fail(key, f"must be a table, not {_kind(value)}")
        return cast(dict[str, object], value)


def _kind(value: object) -> str:
    if isinstance(value, Decimal):
        return "a number with a fraction (no float is read)"
    if isinstance(value, bool):
        return "a boolean"
    if isinstance(value, int):
        return "an integer"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "a table"
    return type(value).__name__


def _amount_of(read: _Reader, key: str, unit: str, value: object, where: str) -> int:
    text = read.text(value, where)
    try:
        return micro_units(unit, text)
    except QuantityError as error:
        raise read.fail(where, f"{error} (a {key} is read in {unit})") from None


def _bounds(read: _Reader, key: str, value: object, where: str) -> tuple[int | None, int | None]:
    """The bounds of one kind of a limit: a string is the maximum, a table holds ``min``, ``max`` or both."""
    unit = RATINGS[key]
    if isinstance(value, str):
        return None, _amount_of(read, key, unit, value, where)
    table = read.table(value, where)
    unknown = sorted(set(table) - {"min", "max"})
    if unknown:
        raise read.fail(f"{where}.{unknown[0]}", "unknown key; a limit takes min and max")
    if not table:
        raise read.fail(where, "needs min, max or both")
    low = _amount_of(read, key, unit, table["min"], f"{where}.min") if "min" in table else None
    high = _amount_of(read, key, unit, table["max"], f"{where}.max") if "max" in table else None
    if low is not None and high is not None and low > high:
        raise read.fail(where, "min is above max")
    return low, high


def _limit(read: _Reader, key: str, value: object, where: str) -> tuple[Rating, ...]:
    """The limits of ``key``: a table of ``abs_max`` and/or ``operating`` (change c0274). The single
    ``{ min, max }`` form, and an ``operating`` range outside its ``abs_max`` range, are refused."""
    if not isinstance(value, dict):
        message = f"{where}: must be a table of abs_max and/or operating, not {_kind(value)}; {SPLIT_HINT}"
        raise DeviceLimitFormError(message, file=read.file, locator=where)
    table = cast(dict[str, object], value)
    if "min" in table or "max" in table:
        message = f"{where}: a limit is not a bare {{ min, max }} table; {SPLIT_HINT}"
        raise DeviceLimitFormError(message, file=read.file, locator=where)
    unknown = sorted(set(table) - set(LIMIT_KINDS))
    if unknown:
        raise read.fail(f"{where}.{unknown[0]}", "unknown key; a limit takes abs_max and operating")
    if not table:
        raise read.fail(where, f"needs abs_max, operating or both; {SPLIT_HINT}")
    unit = cast(RatingUnit, MICRO_UNITS[RATINGS[key]][0])
    found: dict[str, Rating] = {}
    for kind in LIMIT_KINDS:
        if kind in table:
            low, high = _bounds(read, key, table[kind], f"{where}.{kind}")
            found[kind] = Rating(key, unit, low, high, kind)
    absolute, operating = found.get("abs_max"), found.get("operating")
    if absolute is not None and operating is not None:
        below = absolute.min is not None and operating.min is not None and operating.min < absolute.min
        above = absolute.max is not None and operating.max is not None and operating.max > absolute.max
        if below or above:
            raise read.fail(f"{where}.operating", "lies outside the abs_max range")
    return tuple(found.values())


def _thresholds(read: _Reader, table: Mapping[str, object], where: str) -> tuple[Threshold, ...]:
    found: list[Threshold] = []
    for key in sorted(set(table) & set(THRESHOLDS)):
        unit = THRESHOLDS[key]
        value = _amount_of(read, key, unit, table[key], f"{where}.{key}")
        found.append(Threshold(cast(ThresholdKey, key), cast(RatingUnit, MICRO_UNITS[unit][0]), value))
    return tuple(found)


def _pin(read: _Reader, function: str, value: object) -> DevicePin:
    where = f"pins.{function}"
    if isinstance(value, str):
        pin = read.text(value, where)
        return DevicePin(function, ((pin, pin),))
    if isinstance(value, list):
        pins = read.texts(cast(object, value), where)
        if not pins:
            raise read.fail(where, "lists no pin")
        return DevicePin(function, tuple((pin, pin) for pin in sorted(pins)))
    table = read.table(value, where)
    unknown = sorted(set(table) - set(PIN_KEYS))
    if unknown:
        raise read.fail(f"{where}.{unknown[0]}", f"unknown key; a function takes {', '.join(PIN_KEYS)}")
    if ("pins" in table) == ("map" in table):
        raise read.fail(where, "takes exactly one of pins and map")
    pairs: list[tuple[str, str]] = []
    if "pins" in table:
        pins = read.texts(table["pins"], f"{where}.pins")
        if not pins:
            raise read.fail(f"{where}.pins", "lists no pin")
        pairs = [(pin, pin) for pin in sorted(pins)]
    else:
        mapping = read.table(table["map"], f"{where}.map")
        if not mapping:
            raise read.fail(f"{where}.map", "maps no pin")
        for pin in sorted(mapping):
            read.text(pin, f"{where}.map")
            target = mapping[pin]
            pads = (read.text(target, f"{where}.map.{pin}"),) if isinstance(target, str) else None
            if pads is None:
                pads = read.texts(target, f"{where}.map.{pin}")
            if not pads:
                raise read.fail(f"{where}.map.{pin}", "gives the pin no pad")
            pairs += [(pin, pad) for pad in pads]
    ratings = [
        rating
        for key in PIN_RATINGS
        if key in table
        for rating in _limit(read, key, table[key], f"{where}.{key}")
    ]
    thresholds = _thresholds(read, table, where)
    must_connect = table.get("must_connect", False)
    if not isinstance(must_connect, bool):
        raise read.fail(f"{where}.must_connect", f"must be a boolean, not {_kind(must_connect)}")
    ratings.sort(key=lambda rating: (rating.key, rating.limit))
    return DevicePin(function, tuple(pairs), tuple(ratings), thresholds, must_connect)


def _pair_limits(read: _Reader, value: object, functions: set[str]) -> tuple[PinPairLimit, ...]:
    """The ``[[limits]]`` tables (change c0274): each names two distinct functions and a voltage limit."""
    if not isinstance(value, list):
        raise read.fail("limits", f"must be an array of tables ([[limits]]), not {_kind(value)}")
    found: dict[tuple[str, ...], PinPairLimit] = {}
    for index, item in enumerate(cast(list[object], value)):
        where = f"limits[{index}]"
        table = read.table(item, where)
        unknown = sorted(set(table) - set(LIMIT_KEYS))
        if unknown:
            raise read.fail(f"{where}.{unknown[0]}", f"unknown key; [[limits]] takes {', '.join(LIMIT_KEYS)}")
        for key in LIMIT_KEYS:
            if key not in table:
                raise read.fail(f"{where}.{key}", "is missing")
        between = read.texts(table["between"], f"{where}.between")
        if len(between) != 2:
            raise read.fail(f"{where}.between", "names exactly two distinct functions")
        for function in between:
            if function not in functions:
                raise read.fail(f"{where}.between", f"names no function of the device: {function!r}")
        if tuple(sorted(between)) in {tuple(sorted(pair)) for pair in found}:
            raise read.fail(f"{where}.between", f"the pair {between[0]}, {between[1]} has a limit already")
        found[between] = PinPairLimit(between, _limit(read, "voltage", table["voltage"], f"{where}.voltage"))
    return tuple(found[pair] for pair in sorted(found))


def _pins(read: _Reader, value: object) -> tuple[DevicePin, ...]:
    table = read.table(value, "pins")
    if not table:
        raise read.fail("pins", "names no function")
    folded: dict[str, str] = {}
    for function in table:
        if not FUNCTION.fullmatch(function):
            raise read.fail(f"pins.{function}", f"a function name must match {FUNCTION.pattern}")
        other = folded.get(function.casefold())
        if other is not None:
            raise read.fail(
                f"pins.{function}", f"functions {other!r} and {function!r} differ only in letter case"
            )
        folded[function.casefold()] = function
    pins = tuple(_pin(read, function, table[function]) for function in sorted(table))
    owner: dict[str, str] = {}
    pad_owner: dict[str, str] = {}
    for pin in pins:
        for number in pin.pins:
            if number in owner:
                raise read.fail(
                    f"pins.{pin.function}", f"symbol pin {number!r} is also in function {owner[number]!r}"
                )
            owner[number] = pin.function
        for number, pad in pin.pin_pads:
            held = pad_owner.get(pad)
            if held is not None:
                raise read.fail(
                    f"pins.{pin.function}", f"pad {pad!r} is on symbol pins {held!r} and {number!r}"
                )
            pad_owner[pad] = number
    return pins


def _properties(read: _Reader, value: object) -> dict[str, str]:
    table = read.table(value, "properties")
    folded: set[str] = set()
    out: dict[str, str] = {}
    for name in sorted(table):
        where = f"properties.{name}"
        if not name or name != name.strip() or not name.isprintable():
            raise read.fail(where, "a property name is printable text without surrounding spaces")
        key = name.casefold()
        if any(reserved.casefold() == key for reserved in RESERVED_PROPERTIES) or key.startswith(
            RESERVED_PREFIXES
        ):
            raise read.fail(where, "is a reserved property name")
        if key in folded:
            raise read.fail(where, "differs from another property only in letter case")
        folded.add(key)
        out[name] = read.text(table[name], where, empty=True)
    return out


def _provenance(read: _Reader, value: object) -> DeviceProvenance:
    table = read.table(value, "provenance")
    names = ("tool", "source", "date", "sha256")
    unknown = sorted(set(table) - set(names))
    if unknown:
        raise read.fail(f"provenance.{unknown[0]}", f"unknown key; provenance takes {', '.join(names)}")
    for name in names:
        if name not in table:
            raise read.fail(f"provenance.{name}", "is missing")
    tool, source, date, digest = (read.text(table[name], f"provenance.{name}") for name in names)
    if source.startswith(("/", "\\", "~")) or re.match(r"[A-Za-z]:[\\/]", source) or "\\" in source:
        raise read.fail("provenance.source", "names lib ids, never a path")
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        raise read.fail("provenance.date", "must be an ISO 8601 date (YYYY-MM-DD)") from None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        raise read.fail("provenance.date", "must be an ISO 8601 date (YYYY-MM-DD)")
    if not DIGEST.fullmatch(digest):
        raise read.fail("provenance.sha256", "must be 64 lowercase hex digits")
    return DeviceProvenance(tool, source, date, digest)


@cache
def _catalog_reference(symbol: str) -> str:
    from fenolite.catalog import get_symbol

    try:
        return get_symbol(symbol).reference
    except KeyError:
        return ""


def parse_device(text: str, *, file: str = "") -> DeviceDef:
    """The ``DeviceDef`` of the TOML record ``text`` (capability fenolite-component-catalog, "Device
    records"). ``file`` names the record in errors. A malformed record raises ``DeviceFormatError``
    (FEN-3004); a newer schema or a reserved key raises ``DeviceFormatTooNewError`` (FEN-3002)."""
    read = _Reader(file)
    try:
        data = tomllib.loads(text, parse_float=Decimal)
    except tomllib.TOMLDecodeError as error:
        raise DeviceFormatError(f"not TOML: {error}", file=file) from None
    schema = data.get("schema")
    if isinstance(schema, str) and schema != SCHEMA:
        newer = re.fullmatch(r"fenolite\.device\.v(\d+)", schema)
        if newer is not None and int(newer.group(1)) > 0:
            raise DeviceFormatTooNewError(
                f"schema: {schema!r} is newer than {SCHEMA!r}", file=file, locator="schema"
            )
        raise read.fail("schema", f"must be {SCHEMA!r}, not {schema!r}")
    for key in sorted(data):
        if key in RESERVED:
            raise DeviceFormatTooNewError(
                f"{key}: reserved for a later device format ({RESERVED[key]})", file=file, locator=key
            )
    unknown = sorted(set(data) - set(KEYS))
    if unknown:
        raise read.fail(unknown[0], "unknown key")
    for key in REQUIRED:
        if key not in data:
            raise read.fail(key, "is missing")
    read.text(schema, "schema")
    device_id = read.text(data["id"], "id")
    if not ID.fullmatch(device_id):
        raise read.fail(
            "id", f"must be <namespace>:<name>, each matching [A-Za-z0-9_.+-]+, not {device_id!r}"
        )
    namespace, name = device_id.split(":", 1)
    fields = {key: read.text(data[key], key) for key in ("summary", "symbol", "footprint")}
    optional = {
        key: read.text(data.get(key, ""), key, empty=True)
        for key in ("manufacturer", "mpn", "value", "ground")
    }
    datasheet = read.text(data.get("datasheet", ""), "datasheet", empty=True)
    if datasheet and (not datasheet.startswith("https://") or " " in datasheet or len(datasheet) <= 8):
        raise read.fail("datasheet", "must be an https:// URL")
    evidence = read.text(data["evidence"], "evidence")
    if not EVIDENCE.fullmatch(evidence):
        raise read.fail("evidence", f"{evidence!r} is not a label of the evidence vocabulary")
    sources = read.texts(data.get("sources", _NONE), "sources")
    for source in sources:
        if not SOURCE.fullmatch(source):
            raise read.fail("sources", f"{source!r} is not a source id of docs/evidence/sources.md (S-NNNN)")
    if namespace == SHIPPED_NAMESPACE and not sources:
        raise read.fail("sources", f"a {SHIPPED_NAMESPACE}: device needs its sources")
    pins = _pins(read, data["pins"])
    functions = {pin.function for pin in pins}
    ref_prefix = read.text(data.get("ref_prefix", ""), "ref_prefix", empty=True)
    if not ref_prefix:
        ref_prefix = _catalog_reference(fields["symbol"])
        if not REF_PREFIX.fullmatch(ref_prefix):
            raise read.fail(
                "ref_prefix", "is required: the symbol is not a catalog symbol with a reference prefix"
            )
    elif not REF_PREFIX.fullmatch(ref_prefix):
        raise read.fail("ref_prefix", f"must match {REF_PREFIX.pattern}")
    ground = optional["ground"]
    if ground and ground not in functions:
        raise read.fail("ground", f"names no function of the device: {ground!r}")
    if not ground and "GND" in functions:
        ground = "GND"
    unused = read.texts(data.get("unused_pads", _NONE), "unused_pads")
    mapped = {pad for pin in pins for pad in pin.pads}
    for pad in unused:
        if pad in mapped:
            raise read.fail("unused_pads", f"pad {pad!r} is mapped to a pin")
    ends = read.texts(data.get("ends", _NONE), "ends")
    if ends and len(ends) != 2:
        raise read.fail("ends", "names exactly two functions")
    for end in ends:
        if end not in functions:
            raise read.fail("ends", f"names no function of the device: {end!r}")
    ratings: list[Rating] = []
    if "ratings" in data:
        table = read.table(data["ratings"], "ratings")
        for key in sorted(table):
            if key not in RATINGS:
                raise read.fail(f"ratings.{key}", f"unknown rating; use {', '.join(RATINGS)}")
            ratings += _limit(read, key, table[key], f"ratings.{key}")
    limits = _pair_limits(read, data["limits"], functions) if "limits" in data else ()
    cls = read.text(data.get("class", ""), "class", empty=True)
    if cls and cls not in PART_CLASSES:
        raise read.fail("class", f"{cls!r} is not a part class; use one of: {', '.join(PART_CLASSES)}")
    return DeviceDef(
        id=device_id,
        summary=fields["summary"],
        symbol=fields["symbol"],
        footprint=fields["footprint"],
        manufacturer=optional["manufacturer"],
        mpn=optional["mpn"],
        datasheet=datasheet,
        ref_prefix=ref_prefix,
        value=optional["value"] or optional["mpn"] or name,
        evidence=evidence,
        sources=sources,
        ground=ground,
        unused_pads=tuple(sorted(unused)),
        ends=ends,
        properties=_properties(read, data["properties"]) if "properties" in data else {},
        pins=pins,
        ratings=tuple(ratings),
        limits=limits,
        cls=cls,
        provenance=_provenance(read, data["provenance"]) if "provenance" in data else None,
    )


# ----------------------------------------------------------------------------------------- writing


def _string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _key(value: str) -> str:
    return value if _BARE_KEY.fullmatch(value) else _string(value)


def _strings(values: Sequence[str]) -> str:
    return "[" + ", ".join(_string(value) for value in values) + "]"


def _amount(unit: str, value: int) -> str:
    """The text of one bound or threshold in ``unit``, at the largest SI prefix (``u``, ``m``, none, ``k``)
    that keeps the number at least 1, the way ``Quantity.text()`` prints; a temperature prints in degrees
    Celsius without prefix (``-40degC``)."""
    _, exponent = MICRO_UNITS[unit]
    if unit == "kelvin":
        return celsius_text(Fraction(value, 10**exponent), "degC")
    size = Fraction(abs(value), 10**exponent)
    prefix, scale = "", 0
    if size:
        prefix, scale = "u", -6
        for name, power in (("m", -3), ("", 0), ("k", 3)):
            if size >= Fraction(10**power) if power >= 0 else size >= Fraction(1, 10**-power):
                prefix, scale = name, power
    shown = size / (Fraction(10**scale) if scale >= 0 else Fraction(1, 10**-scale))
    whole, part = decimal_digits(shown, "a rating")
    symbol = {"volt": "V", "ampere": "A", "watt": "W"}[unit]
    return f"{'-' if value < 0 else ''}{whole}{'.' + part if part else ''}{prefix}{symbol}"


def _bounds_text(rating: Rating) -> str:
    unit = RATINGS[rating.key]
    if rating.min is None and rating.max is not None:
        return _string(_amount(unit, rating.max))
    bounds = [
        f"{name} = {_string(_amount(unit, bound))}"
        for name, bound in (("min", rating.min), ("max", rating.max))
        if bound is not None
    ]
    return "{ " + ", ".join(bounds) + " }"


def _limit_lines(ratings: Sequence[Rating]) -> list[str]:
    """One ``key = { abs_max = ..., operating = ... }`` line per key of ``ratings``, in key order."""
    lines: list[str] = []
    for key in sorted({rating.key for rating in ratings}):
        kinds = sorted((rating for rating in ratings if rating.key == key), key=lambda rating: rating.limit)
        lines.append(f"{key} = {{ " + ", ".join(f"{r.limit} = {_bounds_text(r)}" for r in kinds) + " }")
    return lines


def _identity(pin: DevicePin) -> bool:
    return all(number == pad for number, pad in pin.pin_pads) and len(pin.pins) == len(pin.pin_pads)


def device_text(device: DeviceDef) -> str:
    """The canonical TOML of ``device``: a fixed key order, one table per long-form function, LF line ends
    and one final newline (capability fenolite-component-catalog, "Canonical device text")."""
    lines = [f"schema = {_string(SCHEMA)}"]
    scalars = (
        ("id", device.id),
        ("summary", device.summary),
        ("manufacturer", device.manufacturer),
        ("mpn", device.mpn),
        ("datasheet", device.datasheet),
        ("symbol", device.symbol),
        ("footprint", device.footprint),
        ("ref_prefix", device.ref_prefix),
        ("class", device.cls),
        ("value", device.value),
        ("evidence", device.evidence),
    )
    lines += [f"{key} = {_string(value)}" for key, value in scalars if value]
    for key, values in (("sources", device.sources), ("ground", ()), ("unused_pads", device.unused_pads)):
        if key == "ground":
            if device.ground:
                lines.append(f"ground = {_string(device.ground)}")
        elif values:
            lines.append(f"{key} = {_strings(values)}")
    if device.ends:
        lines.append(f"ends = {_strings(device.ends)}")
    if device.properties:
        lines += ["", "[properties]"]
        lines += [
            f"{_string(name)} = {_string(device.properties[name])}" for name in sorted(device.properties)
        ]
    lines += ["", "[pins]"]
    long_form: list[DevicePin] = []
    for pin in device.pins:
        plain = _identity(pin) and not pin.ratings and not pin.thresholds and not pin.must_connect
        if not plain:
            long_form.append(pin)
        elif len(pin.pins) == 1:
            lines.append(f"{_key(pin.function)} = {_string(pin.pins[0])}")
        else:
            lines.append(f"{_key(pin.function)} = {_strings(pin.pins)}")
    for pin in long_form:
        lines += ["", f"[pins.{_key(pin.function)}]"]
        if _identity(pin):
            lines.append(f"pins = {_strings(pin.pins)}")
        else:
            entries: list[str] = []
            for number in pin.pins:
                pads = [pad for owner, pad in pin.pin_pads if owner == number]
                target = _string(pads[0]) if len(pads) == 1 else _strings(pads)
                entries.append(f"{_string(number)} = {target}")
            lines.append("map = { " + ", ".join(entries) + " }")
        lines += _limit_lines([rating for rating in pin.ratings if rating.key == "voltage"])
        lines += _limit_lines([rating for rating in pin.ratings if rating.key == "current"])
        lines += [
            f"{found.key} = {_string(_amount(THRESHOLDS[found.key], found.value))}"
            for found in pin.thresholds
        ]
        if pin.must_connect:
            lines.append("must_connect = true")
    if device.ratings:
        lines += ["", "[ratings]"]
        lines += _limit_lines(device.ratings)
    for limit in device.limits:
        lines += ["", "[[limits]]", f"between = {_strings(limit.between)}"]
        lines += _limit_lines(limit.ratings)
    if device.provenance is not None:
        stamp = device.provenance
        lines += ["", "[provenance]"]
        lines += [
            f"{key} = {_string(value)}"
            for key, value in (
                ("tool", stamp.tool),
                ("source", stamp.source),
                ("date", stamp.date),
                ("sha256", stamp.sha256),
            )
        ]
    return "\n".join(lines) + "\n"


def device_digest(device: DeviceDef) -> str:
    """The lowercase hex SHA-256 of the canonical JSON of ``device`` with ``provenance`` cleared, so a
    change of formatting or of key order is not a change of the device."""
    return hashlib.sha256(canonical.dumps(replace(device, provenance=None)).encode("utf-8")).hexdigest()


def is_edited(device: DeviceDef) -> bool:
    """Whether a stamped record differs from the record its stamp was made for; never for one without
    provenance."""
    return device.provenance is not None and device.provenance.sha256 != device_digest(device)


def stamped(device: DeviceDef, *, tool: str, source: str, date: str) -> DeviceDef:
    """``device`` with a provenance stamp of ``tool``, ``source`` and ``date`` whose SHA-256 is its digest."""
    return replace(device, provenance=DeviceProvenance(tool, source, date, device_digest(device)))


# ----------------------------------------------------------------------------------------- loading


def edited_issue(device: DeviceDef, where: str = "") -> Issue:
    """``device.edited`` (info) for a stamped record that was changed after its stamp."""
    return Issue(
        EDITED_CODE,
        "info",
        f"device {device.id} was edited after {device.provenance.tool if device.provenance else 'its stamp'}"
        " wrote it; its evidence label is kept as written",
        where=where or device.id,
        hint="review the change; a re-import over it is refused unless --allow-lossy is given",
    )


def load_devices(folder: Path) -> tuple[tuple[DeviceDef, ...], tuple[Issue, ...]]:
    """The devices of the ``*.toml`` files of ``folder`` in file-name order, and a ``device.edited`` info
    for each edited record. A folder that does not exist holds none. Two files with one id raise
    ``DeviceFormatError`` naming both files."""
    if not folder.is_dir():
        return (), ()
    devices: list[DeviceDef] = []
    issues: list[Issue] = []
    seen: dict[str, str] = {}
    for path in sorted(folder.glob("*.toml"), key=lambda found: found.name):
        name = f"{folder.name}/{path.name}"
        device = parse_device(path.read_text(encoding="utf-8"), file=name)
        if device.id in seen:
            raise DeviceFormatError(
                f"id: device {device.id} is defined in {seen[device.id]} and in {name}",
                file=name,
                locator="id",
            )
        seen[device.id] = name
        devices.append(device)
        if is_edited(device):
            issues.append(edited_issue(device, name))
    return tuple(devices), tuple(issues)


@cache
def shipped_devices() -> tuple[DeviceDef, ...]:
    """The shipped ``Fenolite:`` devices, read from the package data, in id order."""
    folder = resources.files("fenolite.catalog") / "devices"
    found = [
        parse_device(entry.read_text(encoding="utf-8"), file=f"fenolite/catalog/devices/{entry.name}")
        for entry in sorted(folder.iterdir(), key=lambda item: item.name)
        if entry.name.endswith(".toml")
    ]
    return tuple(sorted(found, key=lambda device: device.id))


def shipped_device(device_id: str) -> DeviceDef:
    """The shipped device ``device_id``; ``KeyError`` when there is none."""
    for device in shipped_devices():
        if device.id == device_id:
            return device
    raise KeyError(device_id)


# ----------------------------------------------------------------------------------------- checking


def _mismatch(device: DeviceDef, message: str, where: str) -> Issue:
    return Issue(
        MISMATCH_CODE,
        "error",
        f"device {device.id}: {message}",
        where=where,
        hint="correct the device's pin map, or name the symbol and footprint it was reviewed for",
    )


def check_device(
    device: DeviceDef, symbol: SymbolDef, footprint: FootprintDef, *, where: str = ""
) -> tuple[Issue, ...]:
    """``build.device-mismatch`` errors for each way ``device`` disagrees with ``symbol`` and
    ``footprint``: a symbol pin that no function lists, a device pin the symbol lacks, a mapped pad or an
    unused pad the footprint lacks. ``where`` locates the issues (default: the device id)."""
    at = where or device.id
    numbers = sorted({pin.number for pin in symbol.pins})
    pads = {pad.number for pad in footprint.pads if pad.number}
    owner = {number: pin.function for pin in device.pins for number in pin.pins}
    found: list[Issue] = []
    for number in numbers:
        if number not in owner:
            found.append(_mismatch(device, f"symbol pin {number} of {symbol.lib_id} is in no function", at))
    for pin in device.pins:
        for number in pin.pins:
            if number not in numbers:
                found.append(
                    _mismatch(
                        device, f"function {pin.function} lists pin {number}, which {symbol.lib_id} lacks", at
                    )
                )
        for pad in dict.fromkeys(pin.pads):
            if pad not in pads:
                found.append(
                    _mismatch(
                        device, f"function {pin.function} maps pad {pad}, which {footprint.lib_id} lacks", at
                    )
                )
    for pad in device.unused_pads:
        if pad not in pads:
            found.append(_mismatch(device, f"unused pad {pad} is not a pad of {footprint.lib_id}", at))
    return tuple(found)


__all__ = [
    "EDITED_CODE",
    "IMPORT_TOOL",
    "KEYS",
    "LIMIT_KINDS",
    "MISMATCH_CODE",
    "RATINGS",
    "SCHEMA",
    "THRESHOLDS",
    "DeviceFormatError",
    "DeviceFormatTooNewError",
    "DeviceLimitFormError",
    "check_device",
    "device_digest",
    "device_text",
    "edited_issue",
    "is_edited",
    "load_devices",
    "parse_device",
    "shipped_device",
    "shipped_devices",
    "stamped",
]

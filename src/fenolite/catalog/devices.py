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
from fenolite.core.quantities import MICRO_UNITS, QuantityError, decimal_digits, micro_units
from fenolite.model import canonical
from fenolite.model.library import (
    DeviceDef,
    DevicePin,
    DeviceProvenance,
    FootprintDef,
    Rating,
    RatingUnit,
    SymbolDef,
)

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
    "value",
    "kind",
    "case",
    "tolerance",
    "dielectric",
    "evidence",
    "sources",
    "ground",
    "unused_pads",
    "ends",
    "properties",
    "pins",
    "ratings",
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
    "temperature": "celsius",
}
"""Rating key → the unit its values are read in."""
PIN_RATINGS: tuple[str, ...] = ("voltage", "current")
PIN_KEYS: tuple[str, ...] = ("pins", "map", "voltage", "current", "must_connect")
RESERVED_PROPERTIES: frozenset[str] = frozenset(
    {"Reference", "Value", "Footprint", "Datasheet", "Description", "Manufacturer", "MPN"}
)
"""Names a device property cannot take (compared after ``str.casefold``): the part's own fields, and the
two that the device's ``manufacturer`` and ``mpn`` give."""
RESERVED_PREFIXES: tuple[str, ...] = ("fenolite.", "ki_")
PICK_KEYS: Mapping[str, re.Pattern[str]] = {
    "kind": re.compile(r"resistor|capacitor|inductor"),
    "case": re.compile(r"[0-9]{4}"),
    "tolerance": re.compile(r"[0-9]+(?:\.[0-9]+)?%|-[0-9]+(?:\.[0-9]+)?%\.\.\+[0-9]+(?:\.[0-9]+)?%"),
    "dielectric": re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+-]*"),
}
"""The optional keys that make a device a pickable row (change c0254, ``docs/picking.md``), and their form."""
FAMILY_SCHEMA = "fenolite.family.v0"
"""A family record (change c0254) may share the ``devices/`` folder; ``load_devices`` leaves it to
``fenolite.pick.rows``."""
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


def _rating(read: _Reader, key: str, value: object, where: str) -> Rating:
    table = read.table(value, where)
    unknown = sorted(set(table) - {"min", "max"})
    if unknown:
        raise read.fail(f"{where}.{unknown[0]}", "unknown key; a rating takes min and max")
    if not table:
        raise read.fail(where, "needs min, max or both")
    unit = RATINGS[key]
    bounds: dict[str, int] = {}
    for bound in ("min", "max"):
        if bound in table:
            text = read.text(table[bound], f"{where}.{bound}")
            try:
                bounds[bound] = micro_units(unit, text)
            except QuantityError as error:
                raise read.fail(f"{where}.{bound}", f"{error} (a {key} is read in {unit})") from None
    low, high = bounds.get("min"), bounds.get("max")
    if low is not None and high is not None and low > high:
        raise read.fail(where, "min is above max")
    return Rating(key, cast(RatingUnit, MICRO_UNITS[unit][0]), low, high)


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
    ratings = {key: _rating(read, key, table[key], f"{where}.{key}") for key in PIN_RATINGS if key in table}
    must_connect = table.get("must_connect", False)
    if not isinstance(must_connect, bool):
        raise read.fail(f"{where}.must_connect", f"must be a boolean, not {_kind(must_connect)}")
    return DevicePin(function, tuple(pairs), ratings.get("voltage"), ratings.get("current"), must_connect)


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
        for key in ("manufacturer", "mpn", "value", "ground", "kind", "case", "tolerance", "dielectric")
    }
    for key, pattern in PICK_KEYS.items():
        if optional[key] and not pattern.fullmatch(optional[key]):
            raise read.fail(key, f"{optional[key]!r} does not match {pattern.pattern}")
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
            ratings.append(_rating(read, key, table[key], f"ratings.{key}"))
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
        kind=optional["kind"],
        case=optional["case"],
        tolerance=optional["tolerance"],
        dielectric=optional["dielectric"],
        evidence=evidence,
        sources=sources,
        ground=ground,
        unused_pads=tuple(sorted(unused)),
        ends=ends,
        properties=_properties(read, data["properties"]) if "properties" in data else {},
        pins=pins,
        ratings=tuple(ratings),
        provenance=_provenance(read, data["provenance"]) if "provenance" in data else None,
    )


# ----------------------------------------------------------------------------------------- writing


def _string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _key(value: str) -> str:
    return value if _BARE_KEY.fullmatch(value) else _string(value)


def _strings(values: Sequence[str]) -> str:
    return "[" + ", ".join(_string(value) for value in values) + "]"


def _amount(rating: Rating, value: int) -> str:
    """The text of one bound in the unit of its key, at the largest SI prefix (``u``, ``m``, none, ``k``)
    that keeps the number at least 1, the way ``Quantity.text()`` prints; a temperature takes no prefix."""
    unit = RATINGS[rating.key]
    _, exponent = MICRO_UNITS[unit]
    size = Fraction(abs(value), 10**exponent)
    prefix, scale = "", 0
    if unit != "celsius" and size:
        prefix, scale = "u", -6
        for name, power in (("m", -3), ("", 0), ("k", 3)):
            if size >= Fraction(10**power) if power >= 0 else size >= Fraction(1, 10**-power):
                prefix, scale = name, power
    shown = size / (Fraction(10**scale) if scale >= 0 else Fraction(1, 10**-scale))
    whole, part = decimal_digits(shown, "a rating")
    symbol = {"volt": "V", "ampere": "A", "watt": "W", "celsius": "degC"}[unit]
    return f"{'-' if value < 0 else ''}{whole}{'.' + part if part else ''}{prefix}{symbol}"


def _rating_text(rating: Rating) -> str:
    bounds = [
        f"{name} = {_string(_amount(rating, bound))}"
        for name, bound in (("min", rating.min), ("max", rating.max))
        if bound is not None
    ]
    return "{ " + ", ".join(bounds) + " }"


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
        ("value", device.value),
        ("kind", device.kind),
        ("case", device.case),
        ("tolerance", device.tolerance),
        ("dielectric", device.dielectric),
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
        plain = _identity(pin) and pin.voltage is None and pin.current is None and not pin.must_connect
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
        for rating in (pin.voltage, pin.current):
            if rating is not None:
                lines.append(f"{rating.key} = {_rating_text(rating)}")
        if pin.must_connect:
            lines.append("must_connect = true")
    if device.ratings:
        lines += ["", "[ratings]"]
        lines += [f"{rating.key} = {_rating_text(rating)}" for rating in device.ratings]
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
        text = path.read_text(encoding="utf-8")
        if is_family(text):
            continue
        device = parse_device(text, file=name)
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


def is_family(text: str) -> bool:
    """Whether the TOML ``text`` names the schema of a family record (``fenolite.family.v0``)."""
    return re.search(r'^schema\s*=\s*"fenolite\.family\.v0"', text, re.MULTILINE) is not None


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
    "FAMILY_SCHEMA",
    "IMPORT_TOOL",
    "KEYS",
    "MISMATCH_CODE",
    "RATINGS",
    "SCHEMA",
    "DeviceFormatError",
    "DeviceFormatTooNewError",
    "check_device",
    "device_digest",
    "device_text",
    "edited_issue",
    "is_edited",
    "is_family",
    "load_devices",
    "parse_device",
    "shipped_device",
    "shipped_devices",
    "stamped",
]

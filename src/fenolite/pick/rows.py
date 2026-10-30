# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pickable rows: families (``fenolite.family.v0``) and device records that state a kind and a value
(change c0254, ``docs/picking.md``, "Rows").

A family is one TOML record (a case, a tolerance, a series and a span of values, no MPN) that expands to
one candidate per series value of its span, with the device id ``<family id>@<value code>`` (IEC 60062
letter code: ``10R``, ``61k9``, ``100n``). A device record of change c0248 is a row of its own when it
states ``kind`` and a ``value`` of the kind's unit. Shipped families live in ``fenolite/catalog/families``;
project rows in ``devices/`` beside the script (families and devices side by side) and, unreviewed, in
``devices/proposed/``. This reader is deliberately small and local: it reads what picking needs and no more.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from functools import cache
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import Literal, cast

from fenolite.catalog import FAMILIES_VERSION
from fenolite.catalog.devices import (
    EVIDENCE,
    SOURCE,
    device_text,
    is_family,
)
from fenolite.catalog.records import DeviceRecord, parse_record
from fenolite.core.errors import FormatError
from fenolite.core.partquery import KEYS, KINDS, PINS, PREFIXES, VALUE_UNITS, Constraint, PartQuery, Percent
from fenolite.core.quantities import MICRO_UNITS, QuantityError, decimal_digits, parse, power
from fenolite.core.quantities import PREFIXES as SI_PREFIXES
from fenolite.model.library import DeviceDef, DevicePin, Rating, RatingUnit
from fenolite.pick.series import SERIES, values

SCHEMA = "fenolite.family.v0"
FAMILY_KEYS: tuple[str, ...] = (
    "schema",
    "id",
    "kind",
    "summary",
    "symbol",
    "footprint",
    "case",
    "series",
    "values",
    "tolerance",
    "power",
    "voltage",
    "rating",
    "current",
    "saturation",
    "dcr",
    "tempco",
    "dielectric",
    "evidence",
    "sources",
)
"""Every key of a family record, in the order of its canonical text."""
REQUIRED: tuple[str, ...] = (
    "schema",
    "id",
    "kind",
    "summary",
    "symbol",
    "footprint",
    "case",
    "series",
    "values",
    "tolerance",
    "evidence",
)
"""The keys every family states; ``sources`` is required of a shipped ``Fenolite:`` family only."""
ATTRIBUTE_UNITS: Mapping[str, str] = MappingProxyType(
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
"""The optional numeric attributes of a family and the unit each is read in."""
CASE_ORDER: tuple[str, ...] = ("0201", "0402", "0603", "0805", "1206", "1210", "1812", "2010", "2512")
"""The EIA inch cases from the smallest; ranking prefers the smaller case, an unlisted case comes last."""
ID = re.compile(r"[A-Za-z0-9_.+-]+:[A-Za-z0-9_.+-]+")
TOLERANCE = re.compile(r"([0-9]+(?:\.[0-9]+)?)%|-([0-9]+(?:\.[0-9]+)?)%\.\.\+([0-9]+(?:\.[0-9]+)?)%")
SHIPPED = "shipped"
PROJECT = "project"
PROPOSED_DIR = "proposed"
Origin = Literal["shipped", "project"]


def is_grammar(text: str) -> bool:
    """Whether the TOML ``text`` names the schema of a grammar family (``fenolite.family.v1``, change
    c0263); ``pick/rows.py`` dispatches on the schema."""
    return re.search(r'^schema\s*=\s*"fenolite\.family\.v1"', text, re.MULTILINE) is not None


def catalog_name() -> str:
    """The ``catalog`` value of a pick of a shipped row: ``fenolite-catalog <FAMILIES_VERSION>``."""
    return f"fenolite-catalog {FAMILIES_VERSION}"


@dataclass(frozen=True, slots=True)
class Family:
    """A family record, checked: its fields, the numeric attributes by name and the sources per attribute."""

    id: str
    kind: str
    summary: str
    symbol: str
    footprint: str
    case: str
    series: str
    low: Fraction
    high: Fraction
    tolerance: Percent
    attributes: Mapping[str, Fraction | str]
    evidence: str
    sources: Mapping[str, tuple[str, ...]]
    texts: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    """Every key as the file wrote it (strings), for the canonical text."""


@dataclass(frozen=True, slots=True)
class Row:
    """One candidate: the ``device`` id a pick names, the ``row`` (family or device id), ``kind``, exact
    ``value``, its attributes by query key, where it comes from, the ``catalog`` value of a pick, the
    SHA-256 of the row's canonical text, its evidence and the device record a picked part takes."""

    device: str
    row: str
    kind: str
    value: Fraction
    attributes: Mapping[str, Constraint]
    origin: Origin
    catalog: str
    sha256: str
    evidence: str
    record: DeviceDef

    @property
    def unverified(self) -> bool:
        return self.evidence == "UNVERIFIED"

    @property
    def tolerance(self) -> Percent | None:
        found = self.attributes.get("tolerance")
        return found if isinstance(found, Percent) else None


# ----------------------------------------------------------------------------------------- reading


def _fail(file: str, key: str, message: str) -> FormatError:
    return FormatError(f"{key}: {message}", file=file, locator=key)


def _text(data: Mapping[str, object], key: str, file: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value or not value.isprintable():
        raise _fail(file, key, f"must be a non-empty string, not {value!r}")
    return value


def tolerance_of(text: str, file: str = "", key: str = "tolerance") -> Percent:
    """The per-cent tolerance of ``text`` (``1%`` or ``-20%..+80%``)."""
    found = TOLERANCE.fullmatch(text)
    if found is None:
        raise _fail(file, key, f"{text!r} is not a tolerance such as '1%' or '-20%..+80%'")
    if found.group(1) is not None:
        size = Fraction(found.group(1))
        return Percent(-size, size)
    return Percent(-Fraction(found.group(2)), Fraction(found.group(3)))


def _amount(unit: str, text: str, file: str, key: str) -> Fraction:
    if unit == "ppm":
        number = text.removesuffix("ppm/K").strip()
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", number):
            raise _fail(file, key, f"{text!r} is not a number of ppm/K")
        return Fraction(number)
    try:
        value = parse(unit, text)
    except QuantityError as error:
        raise _fail(file, key, str(error)) from None
    if value <= 0 and key.startswith("values"):
        raise _fail(file, key, "must be above zero")
    if value < 0:
        raise _fail(file, key, "must not be negative")
    return value


def parse_family(text: str, *, file: str = "") -> Family:
    """The family of the TOML ``text``; a malformed record raises ``FormatError`` (``FEN-3004``) naming
    ``file`` and the key."""
    try:
        data = tomllib.loads(text, parse_float=Decimal)
    except tomllib.TOMLDecodeError as error:
        raise FormatError(f"not TOML: {error}", file=file) from None
    for key in data:
        if key not in FAMILY_KEYS:
            raise _fail(file, key, f"unknown key; a family takes {', '.join(FAMILY_KEYS)}")
    for key in REQUIRED:
        if key not in data:
            raise _fail(file, key, "is missing")
    if data["schema"] != SCHEMA:
        raise _fail(file, "schema", f"must be {SCHEMA!r}, not {data['schema']!r}")
    family_id = _text(data, "id", file)
    if not ID.fullmatch(family_id):
        raise _fail(file, "id", f"must be <namespace>:<name>, not {family_id!r}")
    kind = _text(data, "kind", file)
    if kind not in KINDS:
        raise _fail(file, "kind", f"must be one of {', '.join(KINDS)}, not {kind!r}")
    texts: dict[str, str] = {"schema": SCHEMA, "id": family_id, "kind": kind}
    for key in ("summary", "symbol", "footprint", "case", "series", "tolerance", "evidence"):
        texts[key] = _text(data, key, file)
    if not re.fullmatch(r"[0-9]{4}", texts["case"]):
        raise _fail(file, "case", f"must be an EIA inch code such as '0603', not {texts['case']!r}")
    if texts["series"] not in SERIES:
        raise _fail(file, "series", f"must be one of {', '.join(SERIES)}, not {texts['series']!r}")
    if not EVIDENCE.fullmatch(texts["evidence"]):
        raise _fail(file, "evidence", f"{texts['evidence']!r} is not a label of the evidence vocabulary")
    span = data["values"]
    if not isinstance(span, dict) or set(cast(dict[str, object], span)) != {"min", "max"}:
        raise _fail(file, "values", "must be a table of min and max")
    bounds: dict[str, Fraction] = {}
    for bound in ("min", "max"):
        raw = cast(dict[str, object], span)[bound]
        where = f"values.{bound}"
        if not isinstance(raw, str):
            raise _fail(file, where, f"must be a string such as '10k', not {raw!r}")
        texts[where] = raw
        bounds[bound] = _amount(VALUE_UNITS[kind], raw, file, where)
    if bounds["min"] > bounds["max"]:
        raise _fail(file, "values", "min is above max")
    attributes: dict[str, Fraction | str] = {}
    allowed = {item.name for item in KEYS[kind]}
    for key, unit in ATTRIBUTE_UNITS.items():
        if key not in data:
            continue
        if key not in allowed:
            raise _fail(file, key, f"is not an attribute of a {kind}")
        texts[key] = _text(data, key, file)
        attributes[key] = _amount(unit, texts[key], file, key)
    if "dielectric" in data:
        if kind != "capacitor":
            raise _fail(file, "dielectric", f"is not an attribute of a {kind}")
        texts["dielectric"] = attributes["dielectric"] = _text(data, "dielectric", file)
    if family_id.startswith("Fenolite:") and "sources" not in data:
        raise _fail(file, "sources", "a Fenolite: family names the source of every attribute")
    sources_raw = data.get("sources", {})
    if not isinstance(sources_raw, dict):
        raise _fail(file, "sources", "must be a table: attribute → list of source ids")
    sources: dict[str, tuple[str, ...]] = {}
    numeric = {"values", "tolerance", "case", *attributes}
    for name, ids in sorted(cast(dict[str, object], sources_raw).items()):
        where = f"sources.{name}"
        if name not in numeric and name not in ("series", "dielectric"):
            raise _fail(file, where, "names no attribute of the family")
        if not isinstance(ids, list) or not ids:
            raise _fail(file, where, "must be a non-empty list of source ids")
        for item in cast(list[object], ids):
            if not isinstance(item, str) or not SOURCE.fullmatch(item):
                raise _fail(file, where, f"{item!r} is not a source id (S-NNNN)")
        sources[name] = tuple(cast(list[str], ids))
    return Family(
        id=family_id,
        kind=kind,
        summary=texts["summary"],
        symbol=texts["symbol"],
        footprint=texts["footprint"],
        case=texts["case"],
        series=texts["series"],
        low=bounds["min"],
        high=bounds["max"],
        tolerance=tolerance_of(texts["tolerance"], file),
        attributes=MappingProxyType(attributes),
        evidence=texts["evidence"],
        sources=MappingProxyType(sources),
        texts=MappingProxyType(texts),
    )


def family_text(family: Family) -> str:
    """The canonical text of ``family``: the keys in ``FAMILY_KEYS`` order, LF line ends, one final
    newline; its SHA-256 is what a pick of the family records."""
    lines: list[str] = []
    for key in FAMILY_KEYS:
        if key == "values":
            low, high = family.texts["values.min"], family.texts["values.max"]
            lines.append(f"values = {{ min = {json.dumps(low)}, max = {json.dumps(high)} }}")
        elif key == "sources":
            entries = ", ".join(
                f"{name} = [{', '.join(json.dumps(item) for item in ids)}]"
                for name, ids in sorted(family.sources.items())
            )
            if entries:
                lines.append(f"sources = {{ {entries} }}")
        elif key in family.texts:
            lines.append(f"{key} = {json.dumps(family.texts[key], ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------ values


def value_code(unit: str, value: Fraction) -> str:
    """The IEC 60062 letter code of ``value`` (``10R``, ``61k9``, ``1M``, ``100n``, ``4u7``)."""
    prefix, exponent = "", 0
    for name, size in SI_PREFIXES:
        if value >= power(size):
            prefix, exponent = name, size
    if value < power(SI_PREFIXES[0][1]):
        prefix, exponent = SI_PREFIXES[0]
    whole, part = decimal_digits(value / power(exponent), "a value")
    letter = prefix or ("R" if unit == "ohm" else {"farad": "F", "henry": "H"}.get(unit, ""))
    return f"{whole}{letter}{part}"


def value_text(unit: str, value: Fraction) -> str:
    """``61.9kΩ``: the value at the largest SI prefix that keeps it at least 1, and the unit's symbol."""
    from fenolite.core.quantities import UNITS

    prefix, exponent = SI_PREFIXES[0]
    for name, size in SI_PREFIXES:
        if value >= power(size):
            prefix, exponent = name, size
    whole, part = decimal_digits(value / power(exponent), "a value")
    return f"{whole}{'.' + part if part else ''}{prefix}{UNITS[unit]}"


def _micro(unit: str, value: Fraction) -> int | None:
    scaled = value * power(MICRO_UNITS[unit][1])
    return scaled.numerator if scaled.denominator == 1 else None


def _record(family: Family, value: Fraction) -> DeviceDef:
    """The device a pick of ``family`` at ``value`` gives a part: the family's symbol and footprint, pins
    ``P1``/``P2`` on symbol pins ``1``/``2``, its power and voltage ratings, no MPN."""
    unit = VALUE_UNITS[family.kind]
    ratings: list[Rating] = []
    for key, rating_key in (
        ("current", "current"),
        ("power", "power"),
        ("rating", "voltage"),
        ("voltage", "voltage"),
    ):
        amount = family.attributes.get(key)
        if isinstance(amount, Fraction):
            rating_unit = {"current": "ampere", "power": "watt", "voltage": "volt"}[rating_key]
            micro = _micro(rating_unit, amount)
            if micro is not None:
                ratings.append(Rating(rating_key, cast(RatingUnit, MICRO_UNITS[rating_unit][0]), None, micro))
    sources = tuple(sorted({item for ids in family.sources.values() for item in ids}))
    shown = value_text(unit, value)
    # the part value: the letter code for a resistor (``61k9``), Windows-1252 text that every target writes
    part_value = value_code(unit, value) if unit == "ohm" else shown
    return DeviceDef(
        id=f"{family.id}@{value_code(unit, value)}",
        summary=f"{family.summary}, {shown}",
        symbol=family.symbol,
        footprint=family.footprint,
        ref_prefix=PREFIXES[family.kind],
        value=part_value,
        kind=family.kind,
        case=family.case,
        tolerance=family.texts["tolerance"],
        dielectric=str(family.attributes.get("dielectric", "")),
        evidence=family.evidence,
        sources=sources,
        ends=("P1", "P2"),
        pins=(DevicePin("P1", ((PINS[0], PINS[0]),)), DevicePin("P2", ((PINS[1], PINS[1]),))),
        ratings=tuple(sorted(ratings, key=lambda found: found.key)),
    )


def expand(family: Family, *, origin: Origin, catalog: str) -> tuple[Row, ...]:
    """One row per series value of ``family`` within its span, in value order."""
    sha = digest(family_text(family))
    attributes: dict[str, Constraint] = {
        "tolerance": family.tolerance,
        "case": family.case,
        "series": family.series,
        **family.attributes,
    }
    out: list[Row] = []
    for value in values(family.series, family.low, family.high):
        record = _record(family, value)
        out.append(
            Row(
                record.id,
                family.id,
                family.kind,
                value,
                MappingProxyType(attributes),
                origin,
                catalog,
                sha,
                family.evidence,
                record,
            )
        )
    return tuple(out)


def _symbol_pins(symbol: str) -> tuple[str, ...] | None:
    from fenolite.catalog import get_symbol

    try:
        return tuple(sorted({pin.number for pin in get_symbol(symbol).pins}))
    except KeyError:
        return None


def device_row(device: DeviceDef, *, origin: Origin, catalog: str, file: str = "") -> Row | None:
    """The row of a c0248 device that states ``kind`` and a value of the kind's unit, else ``None``. A row
    whose functions map other pins than ``1`` and ``2`` raises ``FormatError`` naming it."""
    if not device.kind:
        return None
    unit = VALUE_UNITS[device.kind]
    try:
        value = parse(unit, device.value)
    except QuantityError:
        raise _fail(
            file or device.id,
            "value",
            f"device {device.id} of kind {device.kind}: {device.value!r} is not a value in {unit}",
        ) from None
    mapped = tuple(sorted(number for pin in device.pins for number in pin.pins))
    if mapped != PINS:
        raise _fail(
            file or device.id,
            "pins",
            f"the pickable row {device.id} maps the symbol pins {', '.join(mapped)}; a {device.kind} "
            "row maps "
            f"exactly {PINS[0]} and {PINS[1]}",
        )
    attributes: dict[str, Constraint] = {}
    if device.tolerance:
        attributes["tolerance"] = tolerance_of(device.tolerance, file, "tolerance")
    if device.case:
        attributes["case"] = device.case
    if device.dielectric:
        attributes["dielectric"] = device.dielectric
    for rating in device.ratings:
        # a part's rated value is its absolute maximum (the abs_max limit of change c0274)
        if rating.max is None or rating.key == "temperature" or rating.limit != "abs_max":
            continue
        unit_name = {"voltage": "volt", "current": "ampere", "power": "watt"}[rating.key]
        amount = Fraction(rating.max, 10 ** MICRO_UNITS[unit_name][1])
        name = {"voltage": "rating" if device.kind == "capacitor" else "voltage"}.get(rating.key, rating.key)
        if name in {item.name for item in KEYS[device.kind]}:
            attributes[name] = amount
    return Row(
        device.id,
        device.id,
        device.kind,
        value,
        MappingProxyType(attributes),
        origin,
        catalog,
        digest(device_text(device)),
        device.evidence,
        device,
    )


@cache
def shipped_families() -> tuple[Family, ...]:
    """The shipped families, read from the package data, in id order."""
    folder = resources.files("fenolite.catalog") / "families"
    found = [
        parse_family(entry.read_text(encoding="utf-8"), file=f"fenolite/catalog/families/{entry.name}")
        for entry in sorted(folder.iterdir(), key=lambda item: item.name)
        if entry.name.endswith(".toml") and entry.name != "VERSIONS.toml"
    ]
    return tuple(sorted(found, key=lambda family: family.id))


@cache
def shipped_rows() -> tuple[Row, ...]:
    """The rows of the shipped families (shipped c0248 devices state no kind, so none of them is a row)."""
    rows: list[Row] = []
    for family in shipped_families():
        rows.extend(expand(family, origin=SHIPPED, catalog=catalog_name()))
    return tuple(rows)


def _check_pins(family: Family, file: str) -> None:
    pins = _symbol_pins(family.symbol)
    if pins is not None and pins != PINS:
        raise _fail(
            file, "symbol", f"the family {family.id} names {family.symbol}, whose pins are not 1 and 2"
        )


def folder_rows(
    folder: Path, prefix: str, *, queries: Iterable[PartQuery] = (), devices: Iterable[str] = ()
) -> tuple[Row, ...]:
    """The rows of the ``*.toml`` files of ``folder`` (families and pickable devices), in file-name order;
    ``prefix`` is the folder relative to the script (``devices`` or ``devices/proposed``). A grammar family
    (``fenolite.family.v1``, change c0263) gives the candidates of ``queries`` and the locked ``devices``
    of it, never its whole expansion."""
    if not folder.is_dir():
        return ()
    rows: list[Row] = []
    queries = tuple(queries)
    devices = tuple(devices)
    for path in sorted(folder.glob("*.toml"), key=lambda found: found.name):
        file = f"{prefix}/{path.name}"
        text = path.read_text(encoding="utf-8")
        catalog = f"project:{file}"
        if is_grammar(text):
            from fenolite.pick.grammar.candidates import checked, grammar_rows
            from fenolite.pick.grammar.schema import parse_family as parse_grammar

            grammar = checked(parse_grammar(text, file=file))
            rows.extend(
                grammar_rows(grammar, queries=queries, devices=devices, origin=PROJECT, catalog=catalog)
            )
            continue
        if is_family(text):
            family = parse_family(text, file=file)
            _check_pins(family, file)
            rows.extend(expand(family, origin=PROJECT, catalog=catalog))
            continue
        # a device record of either schema (c0248's v0, c0259's v1); another record kind is no row
        record = parse_record(text, file=file)
        if not isinstance(record, DeviceRecord):
            continue
        row = device_row(record.device, origin=PROJECT, catalog=catalog, file=file)
        if row is not None:
            rows.append(row)
    return tuple(rows)


def project_rows(
    script_folder: Path,
    devices_dir: str = "devices",
    *,
    queries: Iterable[PartQuery] = (),
    devices: Iterable[str] = (),
) -> tuple[Row, ...]:
    """The project rows beside a script: ``devices/*.toml`` and then ``devices/proposed/*.toml``."""
    base = script_folder / devices_dir
    queries, devices = tuple(queries), tuple(devices)
    return (
        *folder_rows(base, devices_dir, queries=queries, devices=devices),
        *folder_rows(base / PROPOSED_DIR, f"{devices_dir}/{PROPOSED_DIR}", queries=queries, devices=devices),
    )


def design_rows(records: Iterable[DeviceDef]) -> tuple[Row, ...]:
    """The rows of the records a design registered with ``devices()``."""
    found = (device_row(record, origin=PROJECT, catalog="project:design") for record in records)
    return tuple(row for row in found if row is not None)


def all_rows(
    script_folder: Path | None,
    records: Sequence[DeviceDef] = (),
    *,
    queries: Iterable[PartQuery] = (),
    devices: Iterable[str] = (),
) -> tuple[Row, ...]:
    """Every row a build of the script in ``script_folder`` can pick: design records, project rows, then
    the shipped rows. A grammar family among the project rows gives the candidates of ``queries`` and the
    locked ``devices`` (device ids) of it (change c0263)."""
    project = (
        project_rows(script_folder, queries=queries, devices=devices) if script_folder is not None else ()
    )
    return (*design_rows(records), *project, *shipped_rows())


def case_rank(case: object) -> int:
    """The index of ``case`` in ``CASE_ORDER``; an unlisted or missing case ranks after every listed one."""
    return CASE_ORDER.index(case) if isinstance(case, str) and case in CASE_ORDER else len(CASE_ORDER)


__all__ = [
    "ATTRIBUTE_UNITS",
    "CASE_ORDER",
    "FAMILY_KEYS",
    "PROPOSED_DIR",
    "SCHEMA",
    "Family",
    "Row",
    "all_rows",
    "case_rank",
    "catalog_name",
    "design_rows",
    "device_row",
    "digest",
    "expand",
    "family_text",
    "is_grammar",
    "folder_rows",
    "parse_family",
    "project_rows",
    "shipped_families",
    "shipped_rows",
    "tolerance_of",
    "value_code",
    "value_text",
]

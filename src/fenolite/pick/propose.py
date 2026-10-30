# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Supplier proposals: candidate rows for review (change c0254, ``docs/picking.md``, "Proposals").

``fenolite pick --propose QUERY`` turns rows from a file the user exported (``--from FILE``, CSV or JSON
with the columns of ``COLUMNS``) or from a supplier plugin (``--supplier NAME``) into device records with
``evidence = "UNVERIFIED"`` under ``devices/proposed/`` beside the script, each with the line of the file or
the plugin it came from. A proposal never writes the design lock, and an ``UNVERIFIED`` row is picked only
when a query names it (``row=``): the user reads the datasheet, moves the record out of ``proposed/`` and
raises its label. Fenolite ships no plugin, and the core opens no network connection: a plugin registered
under the entry-point group ``fenolite.suppliers`` that sends data offsite runs only with
``--allow-offsite``.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import metadata
from typing import Protocol, cast

from fenolite.catalog.devices import ID, device_text
from fenolite.core.errors import FormatError
from fenolite.core.partquery import PINS, PREFIXES, VALUE_UNITS, PartQuery
from fenolite.core.quantities import MICRO_UNITS, QuantityError, micro_units, parse
from fenolite.model.library import DeviceDef, DevicePin, Rating, RatingUnit
from fenolite.pick.match import failure
from fenolite.pick.rows import PROJECT, device_row, tolerance_of

GROUP = "fenolite.suppliers"
"""The entry-point group of supplier plugins."""
COLUMNS: tuple[str, ...] = (
    "id",
    "kind",
    "value",
    "summary",
    "symbol",
    "footprint",
    "case",
    "tolerance",
    "dielectric",
    "voltage",
    "power",
    "current",
    "manufacturer",
    "mpn",
    "datasheet",
)
"""The columns a proposal row may give; ``id``, ``kind``, ``value`` and ``footprint`` are required."""
REQUIRED: tuple[str, ...] = ("id", "kind", "value", "footprint")
SYMBOLS = {
    "resistor": "Fenolite:Resistor",
    "capacitor": "Fenolite:Capacitor",
    "inductor": "Fenolite:Inductor",
}


class Supplier(Protocol):
    """A supplier plugin: its ``name``, whether it sends data off this machine, and ``propose``, which
    returns rows with the columns of ``COLUMNS`` for a query."""

    name: str
    sends_data_offsite: bool

    def propose(self, query: PartQuery) -> Sequence[Mapping[str, str]]: ...


@dataclass(frozen=True, slots=True)
class Proposal:
    """One proposed record: its file name under ``devices/proposed/``, the device and its text."""

    file: str
    device: DeviceDef
    text: str


def read_rows(text: str, *, file: str) -> list[tuple[int, dict[str, str]]]:
    """The rows of a CSV (header line first) or JSON (a list of objects) text, each with its line (CSV) or
    index (JSON, from 1)."""
    stripped = text.lstrip()
    if stripped.startswith("[") or file.endswith(".json"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise FormatError(f"not JSON: {error}", file=file) from None
        if not isinstance(data, list):
            raise FormatError("a JSON proposal file is a list of objects", file=file)
        rows: list[tuple[int, dict[str, str]]] = []
        for index, item in enumerate(cast(list[object], data), start=1):
            if not isinstance(item, dict):
                raise FormatError(f"row {index} is not an object", file=file, locator=str(index))
            rows.append((index, {str(k): str(v) for k, v in cast(dict[object, object], item).items()}))
        return rows
    reader = csv.DictReader(io.StringIO(text))
    return [(reader.line_num, {k: (v or "").strip() for k, v in row.items() if k}) for row in reader]


def _rating(key: str, unit: str, text: str, where: str, file: str) -> Rating:
    try:
        amount = micro_units(unit, text)
    except QuantityError as error:
        raise FormatError(f"{key}: {error}", file=file, locator=where) from None
    return Rating(key, cast(RatingUnit, MICRO_UNITS[unit][0]), None, amount)


def record(row: Mapping[str, str], *, file: str, line: int) -> DeviceDef:
    """The ``UNVERIFIED`` device record of one proposal row; ``FormatError`` naming the file and line."""
    where = f"line {line}"
    for name in row:
        if name not in COLUMNS:
            raise FormatError(
                f"unknown column {name!r}; the columns are {', '.join(COLUMNS)}", file=file, locator=where
            )
    for name in REQUIRED:
        if not row.get(name):
            raise FormatError(f"{name} is missing", file=file, locator=where)
    device_id, kind = row["id"], row["kind"]
    if not ID.fullmatch(device_id) or device_id.startswith("Fenolite:"):
        raise FormatError(
            f"id {device_id!r} must be <namespace>:<name> outside the Fenolite namespace",
            file=file,
            locator=where,
        )
    if kind not in VALUE_UNITS:
        raise FormatError(f"kind {kind!r} is not resistor, capacitor or inductor", file=file, locator=where)
    try:
        parse(VALUE_UNITS[kind], row["value"])
    except QuantityError as error:
        raise FormatError(f"value: {error}", file=file, locator=where) from None
    if row.get("tolerance"):
        tolerance_of(row["tolerance"], file, where)
    ratings: list[Rating] = []
    for name, unit in (("current", "ampere"), ("power", "watt"), ("voltage", "volt")):
        if row.get(name):
            ratings.append(_rating(name, unit, row[name], where, file))
    return DeviceDef(
        id=device_id,
        summary=row.get("summary") or f"Proposed {kind} {row['value']}",
        symbol=row.get("symbol") or SYMBOLS[kind],
        footprint=row["footprint"],
        manufacturer=row.get("manufacturer", ""),
        mpn=row.get("mpn", ""),
        datasheet=row.get("datasheet", ""),
        ref_prefix=PREFIXES[kind],
        value=row["value"],
        kind=kind,
        case=row.get("case", ""),
        tolerance=row.get("tolerance", ""),
        dielectric=row.get("dielectric", ""),
        evidence="UNVERIFIED",
        ends=("P1", "P2"),
        pins=(DevicePin("P1", ((PINS[0], PINS[0]),)), DevicePin("P2", ((PINS[1], PINS[1]),))),
        ratings=tuple(sorted(ratings, key=lambda found: found.key)),
    )


def file_name(device_id: str) -> str:
    """The file of a proposed record: its id in lower case, ``:`` and other marks as ``_``."""
    return re.sub(r"[^a-z0-9._+-]", "_", device_id.lower()) + ".toml"


def proposals(
    query: PartQuery, rows: Sequence[tuple[int, Mapping[str, str]]], *, source: str
) -> tuple[list[Proposal], list[str]]:
    """The proposals of ``rows`` that meet ``query`` (their evidence aside), and a note per row left out.
    ``source`` names the file or plugin in each record's source line."""
    found: list[Proposal] = []
    skipped: list[str] = []
    for line, row in rows:
        device = record(row, file=source, line=line)
        candidate = device_row(device, origin=PROJECT, catalog="proposal", file=source)
        if candidate is None or candidate.kind != query.kind:
            skipped.append(f"{source} line {line}: {device.id} is not a {query.kind}")
            continue
        missed = failure(query, candidate)
        if missed is not None and missed.reason != "unverified":
            skipped.append(f"{source} line {line}: {device.id} misses {missed.text}")
            continue
        header = (
            "# SPDX-License-Identifier: CC0-1.0\n"
            f"# Proposed by fenolite pick --propose from {source}, line {line}; UNVERIFIED until reviewed.\n"
        )
        found.append(Proposal(file_name(device.id), device, header + device_text(device)))
    return found, skipped


def suppliers() -> dict[str, metadata.EntryPoint]:
    """The supplier plugins installed, by name (the entry-point group ``fenolite.suppliers``)."""
    return {entry.name: entry for entry in metadata.entry_points(group=GROUP)}


def load_supplier(name: str) -> Supplier:
    """The plugin ``name``; ``KeyError`` when none is installed under that name."""
    entry = suppliers()[name]
    loaded = entry.load()
    return cast(Supplier, loaded() if isinstance(loaded, type) else loaded)


__all__ = [
    "COLUMNS",
    "GROUP",
    "Proposal",
    "Supplier",
    "file_name",
    "load_supplier",
    "proposals",
    "read_rows",
    "record",
    "suppliers",
]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The bill of materials that ``kicad-cli sch export bom`` writes, read back row by row (capability
assembly-outputs, "BOM parts from kicad-cli"; facts: ``docs/formats/kicad/cli.md``, "Bill of materials").

``KicadCli.export_bom`` asks for one row per reference with a known list of fields as the header. This
module names that list and reads the CSV into one ``BomRow`` per reference. Grouping and column names are
not KiCad's here: ``fenolite.exports.bom`` groups the rows of either source in one place.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-BOM-CSV",))
"""``KICAD-VERIFIED``: ``H-K-BOM-CSV`` holds on 9.0.9 and 10.0.6 (c0064 task 8.2)."""
DNP_FIELD = "${DNP}"
BASE_FIELDS: tuple[str, ...] = ("Reference", "Value", "Footprint", "Datasheet", "Description", DNP_FIELD)
"""The fields every export asks for, in this order; the user properties follow, sorted."""
FIELD_SEPARATOR = ","
"""``--fields`` is one comma-separated argument, so a field name cannot hold a comma."""


@dataclass(frozen=True, slots=True)
class BomRow:
    """One row of the export: a reference and what the schematic holds for it. ``properties`` has the
    cells of the user properties that are not empty."""

    ref: str
    value: str = ""
    footprint: str = ""
    datasheet: str = ""
    description: str = ""
    dnp: bool = False
    properties: Mapping[str, str] = field(default_factory=lambda: {})


def unsupported_fields(properties: Iterable[str]) -> tuple[str, ...]:
    """The property names that cannot be passed in ``--fields``, sorted."""
    return tuple(sorted({name for name in properties if FIELD_SEPARATOR in name}))


def bom_fields(properties: Iterable[str]) -> tuple[str, ...]:
    """``BASE_FIELDS`` followed by the user ``properties``, sorted and without repeats or base names."""
    names = sorted({name for name in properties if name not in BASE_FIELDS})
    bad = unsupported_fields(names)
    if bad:
        raise ValueError(f"a field name with a comma cannot be exported: {', '.join(bad)}")
    return (*BASE_FIELDS, *names)


def read_bom_csv(text: str, *, fields: tuple[str, ...], file: str = "") -> tuple[BomRow, ...]:
    """The rows of a CSV that ``KicadCli.export_bom`` asked for with ``fields``, in file order.

    The header must equal ``fields``, and every row must have one cell per field and a reference;
    anything else raises ``FormatError`` naming the first difference.
    """
    if tuple(fields[: len(BASE_FIELDS)]) != BASE_FIELDS:
        raise ValueError(f"fields must start with {', '.join(BASE_FIELDS)}")
    rows = list(csv.reader(io.StringIO(text, newline="")))
    if not rows:
        raise FormatError("the bill of materials is empty: no header line", file=file, locator="line 1")
    header = rows[0]
    for index, wanted in enumerate(fields):
        found = header[index] if index < len(header) else None
        if found != wanted:
            shown = "no cell" if found is None else repr(found)
            raise FormatError(
                f"header cell {index + 1} is {shown}, expected {wanted!r}", file=file, locator="line 1"
            )
    if len(header) != len(fields):
        raise FormatError(
            f"the header has {len(header)} cells, expected {len(fields)}; the first extra one is "
            f"{header[len(fields)]!r}",
            file=file,
            locator="line 1",
        )
    found_rows: list[BomRow] = []
    for number, cells in enumerate(rows[1:], start=2):
        if not cells:
            continue
        if len(cells) != len(fields):
            raise FormatError(
                f"the row has {len(cells)} cells, expected {len(fields)}", file=file, locator=f"line {number}"
            )
        by_field = dict(zip(fields, cells, strict=True))
        if not by_field["Reference"]:
            raise FormatError("the row has no reference", file=file, locator=f"line {number}")
        found_rows.append(
            BomRow(
                ref=by_field["Reference"],
                value=by_field["Value"],
                footprint=by_field["Footprint"],
                datasheet=by_field["Datasheet"],
                description=by_field["Description"],
                dnp=bool(by_field[DNP_FIELD]),
                properties={name: by_field[name] for name in fields[len(BASE_FIELDS) :] if by_field[name]},
            )
        )
    return tuple(found_rows)


__all__ = [
    "BASE_FIELDS",
    "DNP_FIELD",
    "EVIDENCE",
    "BomRow",
    "bom_fields",
    "read_bom_csv",
    "unsupported_fields",
]

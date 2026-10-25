# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An Altium ActiveBOM document, ``.BomDoc`` (``docs/formats/altium/bom-document.md``; change c0190).

The file is text, one record per line: ``|RECORD=<kind>|KEY=VALUE|…``. It holds the BOM's settings and its
catalog, not the BOM's lines (``H-A-PRJ-BOMDOC``, INFERRED):

* the visible columns with their widths (``VisibleOrderOptions2``, ``BASEVIEW``; else
  ``VisibleOrderOptions``), their aliases (``ColumnsAliases``), the sort (``SortOrderOptions``), the
  parameters parts are grouped by (``CheckGroupCompParamsOptions``, ``Name=1`` for a grouping one) and the
  line numbering;
* one ``CatalogItem`` per part type (``ITEMTYPE`` ``Automatic-…`` for a part of the design, matched by its
  ``DESIGNITEMID``; ``Manual-…`` for a line the user added), each followed by its part choices and one
  ``Solution`` (the chosen manufacturer and part number);
* one ``Item`` per manual line, by the ``UNIQUEID`` of its catalog item, with its ``QUANTITY``.

Supplier data (prices, stock) is not read. Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-PRJ-BOMDOC",))
FIRST = "BOM"


@dataclass(frozen=True)
class CatalogItem:
    """One part type of the BOM: what it matches, its description and its chosen manufacturer part."""

    unique_id: str
    design_item_id: str
    manual: bool
    description: str
    manufacturer: str = ""
    part_number: str = ""


@dataclass(frozen=True)
class BomDocument:
    """The settings and the catalog of a ``.BomDoc``."""

    columns: tuple[str, ...]
    aliases: dict[str, str] = field(default_factory=lambda: {})
    sort: tuple[tuple[str, bool], ...] = ()
    """(column, ascending) pairs, first key first."""
    group_by: tuple[str, ...] = ()
    numbering: tuple[int, int] = (1, 1)
    """Start value and increment of ``Line #``."""
    catalog: tuple[CatalogItem, ...] = ()
    manual: tuple[tuple[str, int], ...] = ()
    """(catalog unique id, quantity) of each manual line, in file order."""


def records(data: bytes, *, file: str = "") -> list[dict[str, str]]:
    """The records of ``data``, each a dict of its pairs; ``FormatError`` when the first is not
    ``RECORD=BOM``."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    out: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        pairs = (part.partition("=") for part in line.strip("|").split("|"))
        out.append({key: value for key, sep, value in pairs if sep})
    if not out or out[0].get("RECORD") != FIRST:
        raise FormatError(
            f"{file or 'the file'} is not an ActiveBOM document: it does not start with |RECORD=BOM"
        )
    return out


def _pairs(text: str) -> list[tuple[str, str]]:
    """``A=1!B=2`` as pairs, in order."""
    return [(k, v) for k, _sep, v in (part.partition("=") for part in text.split("!")) if k]


def read_bomdoc(data: bytes, *, file: str = "") -> BomDocument:
    """The settings and catalog of the ActiveBOM document ``data`` (module docstring)."""
    found = records(data, file=file)
    first: dict[str, dict[str, str]] = {}
    catalog: list[CatalogItem] = []
    manual: list[tuple[str, int]] = []
    current: dict[str, str] | None = None
    solution: tuple[str, str] = ("", "")

    def close() -> None:
        if current is not None:
            catalog.append(
                CatalogItem(
                    current.get("UNIQUEID", ""),
                    current.get("DESIGNITEMID", ""),
                    current.get("ITEMTYPE", "").startswith("Manual"),
                    current.get("DESCRIPTION", ""),
                    *solution,
                )
            )

    for record in found:
        kind = record.get("RECORD", "")
        if kind == "CatalogItem":
            close()
            current, solution = record, ("", "")
        elif kind == "Solution" and current is not None:
            solution = (record.get("MANUFACTURER", ""), record.get("MANUFACTURERPARTNO", ""))
        elif kind == "Item":
            try:
                quantity = int(record.get("QUANTITY", "1") or "1")
            except ValueError:
                quantity = 1
            manual.append((record.get("UNIQUEID", ""), quantity))
        else:
            first.setdefault(kind, record)
    close()
    view = first.get("VisibleOrderOptions2", {}).get("BASEVIEW") or first.get("VisibleOrderOptions", {}).get(
        "VISIBLEORDER", ""
    )
    groups = first.get("CheckGroupCompParamsOptions", {}).get("CHECKGROUPCOMPPARAMS", "")
    numbering = first.get("LineNumberingOptions", {})
    try:
        start, step = int(numbering.get("STARTVALUE", "1") or 1), int(numbering.get("INCREMENT", "1") or 1)
    except ValueError:
        start, step = 1, 1
    return BomDocument(
        columns=tuple(name for name, _width in _pairs(view)),
        aliases=dict(_pairs(first.get("ColumnsAliases", {}).get("COLUMNSALIASES", ""))),
        sort=tuple(
            (name, way != "Down")
            for name, way in _pairs(first.get("SortOrderOptions", {}).get("SORTORDER", ""))
        ),
        group_by=tuple(k for k, _s, v in (p.partition("=") for p in groups.split(",")) if k and v == "1"),
        numbering=(start, step),
        catalog=tuple(catalog),
        manual=tuple(manual),
    )


__all__ = ["EVIDENCE", "BomDocument", "CatalogItem", "read_bomdoc", "records"]

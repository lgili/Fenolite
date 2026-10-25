# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The scene of an Altium ActiveBOM document for the viewer page (capability documentation-view, change
c0190).

A ``.BomDoc`` holds the BOM's settings and catalog, not its lines (``read.bomdoc``). ``bom_scene(path)`` gives
a table scene (``kind`` ``"table"``) of the document alone: one row per catalog item. ``with_parts(scene,
sheets)`` gives the BOM as Altium builds it from the project's parts (the sheet scenes of the project, by
document name): the parts grouped by the document's grouping parameters (``Comment`` and ``Footprint`` when it
names none), one row per group with its designators and quantity, then one row per manual line; the
description, manufacturer and part number come from the catalog item of the group's design item id. The
columns are ``Line #`` when the document shows it, ``Designator``, ``Comment``, ``Footprint``, ``Quantity``,
then the document's other visible columns without the supplier columns (``Supplier…``, ``…@…``); headers take
the document's aliases; rows follow its sort. Each row's ``refs`` lists its designators, which the page
selects on the board. Standard library only.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

from fenolite.backends.altium.read.bomdoc import EVIDENCE, BomDocument, CatalogItem, read_bomdoc

SCHEMA = "fenolite.view_table.v0"
LEAD = ("Designator", "Comment", "Footprint", "Quantity")
DEFAULT_GROUP = ("Comment", "Footprint")
_SUPPLIER = re.compile(r"^(Supplier|Price)|@")


def _natural(text: str) -> list[Any]:
    return [int(t) if t.isdigit() else t.casefold() for t in re.split(r"(\d+)", text)]


def _columns(doc: BomDocument) -> list[str]:
    shown = [c for c in doc.columns if not _SUPPLIER.search(c)]
    lead = (["Line #"] if "Line #" in shown else []) + list(LEAD)
    return lead + [c for c in shown if c not in lead]


def _doc_json(doc: BomDocument) -> dict[str, Any]:
    return {
        "columns": _columns(doc),
        "aliases": doc.aliases,
        "sort": [list(s) for s in doc.sort],
        "group_by": list(doc.group_by),
        "numbering": list(doc.numbering),
        "catalog": [vars(item) for item in doc.catalog],
        "manual": [list(m) for m in doc.manual],
    }


def _value(column: str, comp: dict[str, Any]) -> str:
    keys = {"Comment": "comment", "Footprint": "footprint", "Description": "description", "Designator": "ref"}
    if column in keys:
        return str(comp.get(keys[column]) or "")
    params = cast("dict[str, Any]", comp.get("params") or {})
    found = next((v for k, v in params.items() if k.casefold() == column.casefold()), "")
    return str(found)


def _table(
    doc: dict[str, Any], lines: list[dict[str, Any]]
) -> tuple[list[str], list[list[str]], list[list[str]]]:
    """Headers, rows and refs of ``lines`` (dicts of column values with ``refs``), sorted and numbered."""
    columns = cast("list[str]", doc["columns"])
    for name, ascending in reversed(cast("list[list[Any]]", doc["sort"])):
        if name in columns:
            lines.sort(key=lambda line, n=name: _natural(str(line.get(n, ""))), reverse=not ascending)
    start, step = cast("list[int]", doc["numbering"])
    for k, line in enumerate(lines):
        line["Line #"] = str(start + k * step)
    aliases = cast("dict[str, str]", doc["aliases"])
    headers = [aliases.get(c, c) for c in columns]
    rows = [[str(line.get(c, "")) for c in columns] for line in lines]
    return headers, rows, [list(line.get("refs", [])) for line in lines]


def _catalog_line(item: dict[str, Any], quantity: str) -> dict[str, Any]:
    return {
        "Description": item["description"],
        "Manufacturer": item["manufacturer"],
        "Manufacturer Part Number": item["part_number"],
        "Comment": item["design_item_id"] if not item["manual"] else "",
        "Quantity": quantity,
        "refs": [],
    }


def bom_scene(path: Path) -> dict[str, Any]:
    """The table scene of the BOM document at ``path`` alone: its catalog (module docstring)."""
    data = path.read_bytes()
    doc = _doc_json(read_bomdoc(data, file=path.name))
    quantities = {uid: q for uid, q in cast("list[list[Any]]", doc["manual"])}
    lines = [
        _catalog_line(item, str(quantities.get(item["unique_id"], "")) if item["manual"] else "")
        for item in cast("list[dict[str, Any]]", doc["catalog"])
    ]
    headers, rows, refs = _table(doc, lines)
    return {
        "schema": SCHEMA,
        "kind": "table",
        "table": "bom",
        "meta": {
            "name": path.name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "backend": "altium",
            "evidence": EVIDENCE.level.value,
            "counts": {"lines": len(rows), "catalog": len(lines)},
            "notes": [
                "The document's catalog alone: open the BOM from its project to count the parts. Supplier "
                "columns (prices, stock) are not shown."
            ],
        },
        "title": f"Bill of materials {path.stem}",
        "columns": headers,
        "rows": rows,
        "docs": [[] for _ in rows],
        "refs": refs,
        "bomdoc": doc,
    }


def with_parts(scene: dict[str, Any], sheets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The BOM ``scene`` built from the parts of the project's ``sheets`` (module docstring); ``scene`` itself
    when the sheets hold no part."""
    doc = cast("dict[str, Any]", scene.get("bomdoc") or {})
    parts: dict[str, dict[str, Any]] = {}
    for sheet in sheets.values():
        for comp in cast("list[dict[str, Any]]", sheet.get("comps", [])):
            ref = str(comp.get("group") or comp.get("ref") or "")
            if ref and not ref.startswith("#") and not ref.endswith("?"):
                parts.setdefault(ref, comp | {"ref": ref})
    if not doc or not parts:
        return scene
    group_by = cast("list[str]", doc["group_by"]) or list(DEFAULT_GROUP)
    catalog = {
        i["design_item_id"]: i for i in cast("list[dict[str, Any]]", doc["catalog"]) if not i["manual"]
    }
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for comp in parts.values():
        groups[tuple(_value(g, comp) for g in group_by)].append(comp)
    lines: list[dict[str, Any]] = []
    for members in groups.values():
        members.sort(key=lambda c: _natural(c["ref"]))
        first = members[0]
        item = catalog.get(str(first.get("lib") or ""))
        line = {c: _value(c, first) for c in cast("list[str]", doc["columns"])}
        line |= {
            "Designator": ", ".join(c["ref"] for c in members),
            "Quantity": str(len(members)),
            "Description": (item or {}).get("description") or _value("Description", first),
            "refs": [c["ref"] for c in members],
        }
        if item is not None:
            line |= {"Manufacturer": item["manufacturer"], "Manufacturer Part Number": item["part_number"]}
        lines.append(line)
    manual = {i["unique_id"]: i for i in cast("list[dict[str, Any]]", doc["catalog"]) if i["manual"]}
    for uid, quantity in cast("list[list[Any]]", doc["manual"]):
        if uid in manual:
            lines.append(_catalog_line(manual[uid], str(quantity)))
    headers, rows, refs = _table(doc, lines)
    meta = dict(cast("dict[str, Any]", scene["meta"]))
    meta["counts"] = {"lines": len(rows), "parts": len(parts), "manual": len(doc["manual"])}
    meta["notes"] = [
        f"Built from the {len(parts)} parts of the project's sheets, grouped by {', '.join(group_by)}, "
        "with the "
        "document's catalog, columns, aliases and sort. Supplier columns (prices, stock) are not shown."
    ]
    return scene | {"columns": headers, "rows": rows, "refs": refs, "docs": [[] for _ in rows], "meta": meta}


__all__ = ["SCHEMA", "CatalogItem", "bom_scene", "with_parts"]

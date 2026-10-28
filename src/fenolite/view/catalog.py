# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Installed catalog definitions composed into the existing standalone library viewer (c0234)."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from fenolite.backends import registry
from fenolite.backends.base import BoardFrame
from fenolite.backends.kicad.sexpr import parse
from fenolite.backends.kicad.sym import write_symbol_library
from fenolite.model.library import FootprintDef, SymbolDef
from fenolite.view import export, themes
from fenolite.view.kicad_schematic import symbol_scene
from fenolite.view.library import SCHEMA, footprint_item

_NOTES = [
    "Fenolite-authored installed catalog. Evidence: INFERRED; "
    "source IDs identify the public evidence register.",
    "Generic symbol roles are not device pinouts. "
    "Check the chosen part's pin map and land pattern before fabrication.",
]


@dataclass(frozen=True, slots=True)
class CatalogItem:
    """Resolved metadata and geometry supplied by the caller; no catalog lookup is performed."""

    lib_id: str
    category: str
    summary: str
    evidence: str
    sources: tuple[str, ...]
    definition: SymbolDef | FootprintDef

    @property
    def kind(self) -> Literal["symbol", "footprint"]:
        return "symbol" if isinstance(self.definition, SymbolDef) else "footprint"


def _bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _metadata(entry: CatalogItem) -> dict[str, Any]:
    return {
        "name": entry.lib_id,
        "lib_id": entry.lib_id,
        "category": entry.category,
        "summary": entry.summary,
        "description": f"{entry.category} · {entry.summary}",
        "evidence": entry.evidence,
        "sources": list(entry.sources),
        "info": [
            ["Library ID", entry.lib_id],
            ["Category", entry.category],
            ["Description", entry.summary],
            ["Evidence", entry.evidence],
            ["Public source IDs", ", ".join(entry.sources)],
        ],
    }


def _selection(entry: CatalogItem) -> dict[str, Any]:
    """Facts of the exact injected definition, never a guessed device/package match."""
    definition = entry.definition
    if isinstance(definition, SymbolDef):
        return {
            "kind": "symbol",
            "reference": definition.properties.get("Reference", "U"),
            "pins": [{"number": pin.number, "name": pin.name, "type": pin.etype} for pin in definition.pins],
        }
    centers = sorted({(pad.position.x, pad.position.y) for pad in definition.pads if pad.number})
    squared = [
        (x1 - x2) ** 2 + (y1 - y2) ** 2 for i, (x1, y1) in enumerate(centers) for x2, y2 in centers[i + 1 :]
    ]
    return {
        "kind": "footprint",
        "mounting": definition.kind,
        "pad_count": len(definition.pads),
        "pad_numbers": sorted({pad.number for pad in definition.pads if pad.number}),
        "pads": [
            {
                "number": pad.number,
                "x_nm": pad.position.x,
                "y_nm": pad.position.y,
                "width_nm": pad.size.w,
                "height_nm": pad.size.h,
                "rotation_udeg": pad.rotation,
            }
            for pad in definition.pads
        ],
        "min_center_spacing_nm": math.isqrt(min(squared)) if squared else None,
        "spacing_basis": (
            "Minimum distance between distinct numbered-pad centres; floor in nm, not manufacturer pitch."
        ),
    }


def _items(entries: Sequence[CatalogItem], kind: str) -> list[dict[str, Any]]:
    palette = themes.palette("kicad")
    selected = sorted((entry for entry in entries if entry.kind == kind), key=lambda entry: entry.lib_id)
    items: list[dict[str, Any]] = []
    if kind == "symbol":
        definitions = [entry.definition for entry in selected if isinstance(entry.definition, SymbolDef)]
        root = parse(write_symbol_library(definitions))
        nodes = {node.atoms()[0].value: node for node in root.nodes("symbol")}
        for entry, definition in zip(selected, definitions, strict=True):
            scene = symbol_scene(
                nodes[definition.name], nodes, name=entry.lib_id, palette=palette, show_properties=False
            )
            item = _metadata(entry)
            item.update(pins=len(definition.pins), scene=scene)
            item["info"].append(["Pins", str(len(definition.pins))])
            item["info"].extend(
                [key, value] for key in ("Reference", "Value") if (value := definition.properties.get(key))
            )
            item["info"].extend([f"Pin {pin.number}", f"{pin.name} · {pin.etype}"] for pin in definition.pins)
            items.append(item)
    else:
        backend = registry.get("kicad")
        assert isinstance(backend, BoardFrame)
        for entry in selected:
            definition = entry.definition
            assert isinstance(definition, FootprintDef)
            item = footprint_item(
                definition, frame=backend, backend="kicad", evidence=entry.evidence, palette=palette
            )
            facts = item["info"]
            item.update(_metadata(entry))
            item["info"].extend(row for row in facts if row[0] == "Pads")
            item["info"].extend(
                [
                    ["Pad inspection", "Click a pad for its size, shape, rotation, drill and layers."],
                ]
            )
            for layer in item["scene"]["layers"]:
                if layer["kind"] in {"fabrication", "courtyard"}:
                    layer["visible"] = True
            items.append(item)
    for item in items:
        scene = item["scene"]
        scene["meta"]["sha256"] = hashlib.sha256(_bytes(scene)).hexdigest()
    for item, entry in zip(items, selected, strict=True):
        item["catalog_selection"] = _selection(entry)
    return items


def catalog_page(entries: Sequence[CatalogItem]) -> str:
    """A deterministic standalone page of selected definitions; empty selections are rejected."""
    if not entries:
        raise ValueError("no catalog entries to display")
    scenes: dict[str, dict[str, Any]] = {}
    documents: list[dict[str, Any]] = []
    for kind, title, lib in (("symbol", "Symbols", "schematic"), ("footprint", "Footprints", "pcb")):
        items = _items(entries, kind)
        if not items:
            continue
        data = _bytes(items)
        doc_id = f"catalog-{kind}"
        scenes[doc_id] = {
            "schema": SCHEMA,
            "kind": "library",
            "lib": lib,
            "meta": {
                "name": f"Fenolite catalog · {title}",
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "backend": "fenolite",
                "evidence": "INFERRED",
                "counts": {"items": len(items)},
                "notes": list(_NOTES),
            },
            "items": items,
            "overlays": [],
        }
        documents.append(
            {
                "id": doc_id,
                "name": title,
                "path": f"Fenolite/{title}",
                "kind": f"{lib}-library",
                "group": "Libraries",
                "present": True,
                "viewable": True,
                "size": len(data),
            }
        )
    tree = {
        "name": "Fenolite catalog",
        "source": "catalog",
        "project_file": "",
        "groups": [{"name": "Libraries", "documents": documents}],
        "issues": [],
    }
    return export.page(tree, scenes, open_id=documents[0]["id"])


__all__ = ["CatalogItem", "catalog_page"]

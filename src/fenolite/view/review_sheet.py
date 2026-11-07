# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Standalone review content composed with the existing library viewer and visual diff (c0262)."""

from __future__ import annotations

import copy
import hashlib
import html
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from fenolite.backends.kicad.sexpr import parse
from fenolite.backends.kicad.sym import write_symbol_library
from fenolite.model.library import FootprintDef, SymbolDef
from fenolite.view import export, themes
from fenolite.view.catalog import CatalogItem, catalog_page
from fenolite.view.kicad_schematic import symbol_scene

CONTENT_SCHEMA = "fenolite.review-content.v1"
REVIEW_SECTION = '<section id="review-content">'
_SRCDOC = re.compile(r'srcdoc="[^"]*"')


def _all_units(page: str, entries: Sequence[CatalogItem]) -> str:
    data = export.embedded(page)
    assert data is not None
    library = data["scenes"].get("catalog-symbol")
    if library is None:
        return page
    items: list[dict[str, Any]] = []
    for entry, original in zip(
        (e for e in entries if isinstance(e.definition, SymbolDef)), library["items"], strict=True
    ):
        definition = entry.definition
        assert isinstance(definition, SymbolDef)
        root = parse(write_symbol_library([definition]))
        nodes = {n.atoms()[0].value: n for n in root.nodes("symbol")}
        styles = sorted(
            {u.body_style or 1 for u in definition.units} | {p.body_style or 1 for p in definition.pins}
        )
        for unit in range(1, definition.unit_count + 1):
            for style in styles:
                item = copy.deepcopy(original)
                item["name"] = f"{entry.lib_id} unit {unit}, style {style}"
                item["scene"] = symbol_scene(
                    nodes[definition.name],
                    nodes,
                    unit=unit,
                    style=style,
                    name=item["name"],
                    palette=themes.palette("kicad"),
                    show_properties=False,
                )
                item["info"].extend([["Unit", str(unit)], ["Body style", str(style)]])
                items.append(item)
    library["items"] = items
    library["meta"]["counts"]["items"] = len(items)
    return export.page(data["project"], data["scenes"], open_id=data["open"])


def review_sheet(
    record_id: str,
    *,
    metadata: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
    symbol: SymbolDef | None = None,
    footprint: FootprintDef | None = None,
    old_symbol: SymbolDef | None = None,
    old_footprint: FootprintDef | None = None,
) -> bytes:
    """Render immutable review content. Live trust state belongs to ``library review``'s result."""
    from fenolite.view.catalog import _items  # pyright: ignore[reportPrivateUsage]
    from fenolite.view.compare import compare

    entries: list[CatalogItem] = []
    overlays: list[dict[str, Any]] = []
    for kind, definition, old in (("symbol", symbol, old_symbol), ("footprint", footprint, old_footprint)):
        if definition is None:
            continue
        # The caller supplies exact definitions with stable generated trust metadata.
        description = definition.description
        entry = CatalogItem(definition.lib_id, "Library review", description, "INFERRED", (), definition)
        entries.append(entry)
        if old is not None:
            old_entry = CatalogItem(old.lib_id, "Library review", old.description, "INFERRED", (), old)
            new_scene, old_scene = _items([entry], kind)[0]["scene"], _items([old_entry], kind)[0]["scene"]
            new_scene["diff"] = compare(new_scene, old_scene)
            overlays.append({"kind": kind, "scene": new_scene, "diff": new_scene["diff"]})
    page = (
        _all_units(catalog_page(entries), entries)
        if entries
        else '<!doctype html><html><head><meta charset="utf-8"></head><body></body></html>'
    )
    sections = [
        f"{REVIEW_SECTION}<h1>{html.escape(record_id)}</h1>",
        "<p>Review state: prepared content. Run <code>fenolite library review</code> "
        "for live acceptance and freshness.</p>",
    ]
    for title, value in metadata.items():
        details = html.escape(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False))
        sections.append(f"<h2>{html.escape(title)}</h2><pre>{details}</pre>")
    finding_text = html.escape(json.dumps(list(findings), sort_keys=True, indent=2))
    sections.append(f"<h2>Findings</h2><pre>{finding_text}</pre></section>")
    # Overlay payload uses c0184's exact comparison. Standalone embedded viewer provides interaction.
    for index, overlay in enumerate(overlays):
        payload = json.dumps(overlay, sort_keys=True, separators=(",", ":"), ensure_ascii=False).replace(
            "<", "\\u003c"
        )
        sections.append(
            f'<h2>Visual diff: {overlay["kind"]}</h2><script type="application/json" '
            f'id="review-diff-{index}">{payload}</script>'
        )
        scene = overlay["scene"]
        doc = {
            "id": "diff",
            "name": "Visual diff",
            "path": "review/diff",
            "kind": "pcb" if overlay["kind"] == "footprint" else "schematic",
            "group": "Review",
            "present": True,
            "viewable": True,
            "size": 0,
        }
        nested = export.page(
            {
                "name": "Visual diff",
                "source": "review",
                "project_file": "",
                "groups": [{"name": "Review", "documents": [doc]}],
                "issues": [],
            },
            {"diff": scene},
            open_id="diff",
        )
        sections.append(
            '<iframe title="Visual diff" style="width:100%;height:600px" '
            f'srcdoc="{html.escape(nested, quote=True)}"></iframe>'
        )
    extra = "\n".join(sections)
    return page.replace("</body>", extra + "\n</body>").encode("utf-8")


def content_digest(sheet: bytes) -> str:
    """Hash what a review sheet shows, not the viewer that shows it (c0415).

    The embedded data with each scene unpacked, and the review section (record id, metadata, findings and
    visual-diff payloads) with iframe ``srcdoc`` page copies emptied. ``page.html``, ``viewer.css``,
    ``viewer.js`` and the scene packing are left out, so a viewer change keeps the digest."""
    text = sheet.decode("utf-8")
    start, end = text.find(REVIEW_SECTION), text.rfind("</body>")
    section = _SRCDOC.sub('srcdoc=""', text[start:end]) if 0 <= start < end else ""
    payload = {"schema": CONTENT_SCHEMA, "embedded": export.embedded(text), "review": section}
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()

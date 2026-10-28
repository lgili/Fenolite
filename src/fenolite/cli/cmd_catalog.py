# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite catalog``: inspect the built-in offline component definitions."""

from __future__ import annotations

import argparse
import hashlib

from fenolite.catalog import ENTRIES, CatalogEntry, get_footprint, get_symbol, list_entries
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.core.evidence import Evidence, Level
from fenolite.model.library import FootprintDef, SymbolDef

CATALOG_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-CATALOG",))
"""The catalog is authored for Fenolite and shown as stored."""


def _register(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "catalog_action",
        choices=("list", "show", "view"),
        help="list entries, show one ID or export a browser",
    )
    parser.add_argument("lib_id", nargs="?", help="catalog ID required by show")
    parser.add_argument("--kind", choices=("symbol", "footprint"), default=None)
    parser.add_argument("--query", default=None, help="case-insensitive search in id, category and summary")
    parser.add_argument("--out", metavar="FILE", help="required by view: write a standalone HTML browser")


def _entry(entry: CatalogEntry) -> dict[str, object]:
    return {
        "lib_id": entry.lib_id,
        "kind": entry.kind,
        "category": entry.category,
        "summary": entry.summary,
        "evidence": entry.evidence,
        "sources": list(entry.sources),
    }


def _run(args: argparse.Namespace, _: Context) -> Result:
    if args.catalog_action == "view":
        if args.lib_id is not None or not args.out:
            raise CliError("FEN-2001", "catalog view requires --out FILE and takes no lib id")
        entries = list_entries(kind=args.kind, query=args.query)
        if not entries:
            raise CliError(
                "FEN-3001",
                "no catalog entries match the filters",
                hint="change or remove --query and --kind; inspect matches with catalog list",
            )
        from fenolite.view.catalog import CatalogItem, catalog_page

        items = [
            CatalogItem(
                lib_id=entry.lib_id,
                category=entry.category,
                summary=entry.summary,
                evidence=entry.evidence,
                sources=entry.sources,
                definition=(
                    get_symbol(entry.lib_id) if entry.kind == "symbol" else get_footprint(entry.lib_id)
                ),
            )
            for entry in entries
        ]
        html = catalog_page(items).encode("utf-8")
        return Result(
            result={
                "count": len(entries),
                "counts": {
                    "symbols": sum(entry.kind == "symbol" for entry in entries),
                    "footprints": sum(entry.kind == "footprint" for entry in entries),
                },
                "out": args.out,
                "filters": {"kind": args.kind, "query": args.query},
                "export": {"bytes": len(html), "sha256": hashlib.sha256(html).hexdigest()},
            },
            evidence=CATALOG_EVIDENCE,
            writes=(PlannedWrite(path=args.out, data=html, kind="catalog-view"),),
        )
    if args.out is not None:
        raise CliError("FEN-2001", "--out is only available with catalog view")
    if args.catalog_action == "list":
        if args.lib_id is not None:
            raise CliError("FEN-2001", "catalog list takes no ID")
        entries = list_entries(kind=args.kind, query=args.query)
        return Result(
            result={"entries": [_entry(item) for item in entries], "count": len(entries)},
            evidence=CATALOG_EVIDENCE,
        )
    if args.lib_id is None:
        raise CliError("FEN-2001", "catalog show requires a lib id")
    entry = next((item for item in ENTRIES if item.lib_id == args.lib_id), None)
    if entry is None:
        raise CliError("FEN-3001", f"unknown built-in catalog id {args.lib_id!r}")
    detail: dict[str, object]
    if entry.kind == "symbol":
        definition: SymbolDef = get_symbol(entry.lib_id)
        detail = {
            "pins": [{"number": pin.number, "name": pin.name, "etype": pin.etype} for pin in definition.pins],
            "graphics": len(definition.graphics),
        }
    else:
        footprint: FootprintDef = get_footprint(entry.lib_id)
        detail = {
            "pads": [{"number": pad.number, "size_nm": [pad.size.w, pad.size.h]} for pad in footprint.pads],
            "graphics": len(footprint.graphics),
            "description": footprint.description,
        }
    return Result(result={**_entry(entry), "definition": detail}, evidence=CATALOG_EVIDENCE)


COMMAND = Command(
    "catalog",
    "inspect the built-in component catalog or export its visual browser (view --out FILE)",
    True,
    _register,
    _run,
    example_args=("list",),
    mutation_example_args=("view", "--out", "catalog.html", "--kind", "symbol", "--query", "resistor"),
)

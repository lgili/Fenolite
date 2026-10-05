# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite catalog``: inspect the built-in offline component definitions."""

from __future__ import annotations

import argparse

from fenolite.catalog import ENTRIES, CatalogEntry, get_footprint, get_symbol, list_entries
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.core.evidence import Evidence, Level
from fenolite.model.library import FootprintDef, SymbolDef


def _register(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("catalog_action", choices=("list", "show"), help="list entries or show one ID")
    parser.add_argument("lib_id", nargs="?", help="catalog ID required by show")
    parser.add_argument("--kind", choices=("symbol", "footprint"), default=None)
    parser.add_argument("--query", default=None, help="case-insensitive search in id, category and summary")


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
    if args.catalog_action == "list":
        if args.lib_id is not None:
            raise CliError("FEN-2001", "catalog list takes no ID")
        entries = list_entries(kind=args.kind, query=args.query)
        return Result(
            result={"entries": [_entry(item) for item in entries], "count": len(entries)},
            evidence=Evidence(Level.INFERRED),
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
    return Result(result={**_entry(entry), "definition": detail}, evidence=Evidence(Level.INFERRED))


COMMAND = Command(
    "catalog",
    "inspect the built-in component catalog",
    False,
    _register,
    _run,
    example_args=("list",),
)

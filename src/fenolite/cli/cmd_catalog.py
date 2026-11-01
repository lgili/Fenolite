# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite catalog``: inspect the built-in offline component definitions and devices, export a browser,
or write a device template from a symbol and a footprint (``import``; change c0248, ``docs/devices.md``)."""

from __future__ import annotations

import argparse
import datetime
import hashlib
from pathlib import Path

from fenolite.catalog import ENTRIES, CatalogEntry, get_footprint, get_symbol, list_entries
from fenolite.catalog.devices import (
    DeviceFormatError,
    check_device,
    device_digest,
    device_text,
    is_edited,
    parse_device,
    shipped_devices,
)
from fenolite.cli._library_import import target_folder
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.library.importer.templates import definitions, legacy_template, pin_template
from fenolite.model import canonical
from fenolite.model.library import DeviceDef, FootprintDef, SymbolDef
from fenolite.pick.rows import Family, catalog_name, family_text, shipped_families

CATALOG_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-CATALOG",))
"""The catalog is authored for Fenolite and shown as stored."""
DEVICE_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-CATALOG", "H-G-DEVICE-RECORD"))
"""Devices are shown as stored; ``digest`` and ``edited`` rest on the canonical digest (change c0248)."""
FAMILY_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-CATALOG", "H-G-PICK-DETERMINISTIC"))
"""Families are shown as stored, each attribute with its sources (change c0254)."""


def _register(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "catalog_action",
        choices=("list", "show", "view", "import"),
        help="list entries, show one ID, export a browser, or import a device template from a symbol and a "
        "footprint",
    )
    parser.add_argument("lib_id", nargs="?", help="catalog ID required by show")
    parser.add_argument(
        "--kind",
        choices=("symbol", "footprint", "device", "family"),
        default=None,
        help="list or show only this kind; show takes it when a device id equals a symbol or footprint id",
    )
    parser.add_argument("--query", default=None, help="case-insensitive search in id, category and summary")
    parser.add_argument(
        "--out",
        metavar="FILE",
        help="required by view (a standalone HTML browser) and by import (the device TOML to write)",
    )
    parser.add_argument("--symbol", metavar="LIB:SYM", help="import: the symbol the device joins")
    parser.add_argument("--footprint", metavar="LIB:FP", help="import: the footprint the device joins")
    parser.add_argument("--id", dest="device_id", metavar="NS:NAME", help="import: the id of the device")
    parser.add_argument(
        "--pin",
        action="append",
        default=[],
        metavar="FUNCTION=PIN[:PAD[+PAD]]",
        help="import: put symbol pin PIN in FUNCTION, on the given pads (default: the pad of its number)",
    )
    parser.add_argument("--manufacturer", default="", help="import: the manufacturer, printable text")
    parser.add_argument("--mpn", default="", help="import: the manufacturer part number, printable text")
    parser.add_argument("--datasheet", default="", help="import: an https:// URL")
    parser.add_argument("--ref-prefix", dest="ref_prefix", default="", help="import: the reference prefix")


def _entry(entry: CatalogEntry) -> dict[str, object]:
    return {
        "lib_id": entry.lib_id,
        "kind": entry.kind,
        "category": entry.category,
        "summary": entry.summary,
        "evidence": entry.evidence,
        "sources": list(entry.sources),
        "version": entry.version,
        "licence": entry.licence,
        "uid": entry.uid,
    }


def _device_entry(device: DeviceDef) -> dict[str, object]:
    from fenolite.catalog.records import record_uid, shipped_tree

    record = shipped_tree().get("device", device.id)
    return {
        "lib_id": device.id,
        "id": device.id,
        "kind": "device",
        "category": "Device",
        "summary": device.summary,
        "evidence": device.evidence,
        "sources": list(device.sources),
        "version": record.header.version if record is not None else "",
        "licence": record.header.licence if record is not None else "",
        "uid": record_uid("device", device.id),
    }


def _families(query: str | None) -> list[Family]:
    found = list(shipped_families())
    if query:
        needle = query.casefold()
        found = [family for family in found if needle in f"{family.id} family {family.summary}".casefold()]
    return found


def _family_entry(family: Family) -> dict[str, object]:
    return {
        "lib_id": family.id,
        "id": family.id,
        "kind": "family",
        "category": family.kind,
        "summary": family.summary,
        "evidence": family.evidence,
        "sources": {name: list(ids) for name, ids in sorted(family.sources.items())},
        "series": family.series,
        "case": family.case,
        "values": {"min": family.texts["values.min"], "max": family.texts["values.max"]},
    }


def _devices(query: str | None) -> list[DeviceDef]:
    found = list(shipped_devices())
    if query:
        needle = query.casefold()
        found = [device for device in found if needle in f"{device.id} device {device.summary}".casefold()]
    return sorted(found, key=lambda device: device.id)


def _show_device(device: DeviceDef) -> Result:
    from fenolite.dsl.devices import shadowed

    issues: tuple[Issue, ...] = ()
    catalog_ids = {entry.lib_id for entry in ENTRIES}
    if device.symbol in catalog_ids and device.footprint in catalog_ids:
        issues = check_device(device, get_symbol(device.symbol), get_footprint(device.footprint))
    return Result(
        result={
            **_device_entry(device),
            "record": canonical.to_data(device),
            "digest": device_digest(device),
            "edited": is_edited(device),
            "shadowed": list(shadowed(device)),
        },
        issues=issues,
        evidence=DEVICE_EVIDENCE,
    )


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if args.catalog_action == "import":
        return _import(args, ctx)
    for option in ("symbol", "footprint", "device_id", "manufacturer", "mpn", "datasheet", "ref_prefix"):
        if getattr(args, option):
            raise CliError("FEN-2001", f"--{option.replace('_', '-')} is only available with catalog import")
    if args.pin:
        raise CliError("FEN-2001", "--pin is only available with catalog import")
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
        if args.kind == "family":  # the parametric families of change c0254 are listed on request only
            families = [_family_entry(found) for found in _families(args.query)]
            return Result(result={"entries": families, "count": len(families)}, evidence=FAMILY_EVIDENCE)
        rows = (
            []
            if args.kind == "device"
            else [_entry(item) for item in list_entries(kind=args.kind, query=args.query)]
        )
        if args.kind in (None, "device"):
            rows += [_device_entry(device) for device in _devices(args.query)]
        rows.sort(key=lambda row: (str(row["lib_id"]), str(row["kind"])))
        return Result(
            result={"entries": rows, "count": len(rows)},
            evidence=DEVICE_EVIDENCE if args.kind == "device" else CATALOG_EVIDENCE,
        )
    if args.lib_id is None:
        raise CliError("FEN-2001", "catalog show requires a lib id")
    entry = next(
        (item for item in ENTRIES if item.lib_id == args.lib_id and args.kind in (None, item.kind)), None
    )
    if entry is None and args.kind in (None, "family"):
        family = next((found for found in _families(None) if found.id == args.lib_id), None)
        if family is not None:
            return Result(
                result={**_family_entry(family), "record": family_text(family), "catalog": catalog_name()},
                evidence=FAMILY_EVIDENCE,
            )
    if entry is None:
        device = next((found for found in shipped_devices() if found.id == args.lib_id), None)
        if device is not None and args.kind in (None, "device"):
            return _show_device(device)
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


def _import(args: argparse.Namespace, ctx: Context) -> Result:
    """``catalog import``: a device template from a symbol and a footprint, planned for ``--out``."""
    missing = [name for name in ("symbol", "footprint", "device_id", "out") if not getattr(args, name)]
    if missing or args.lib_id is not None:
        names = ", ".join("--id" if name == "device_id" else f"--{name}" for name in missing)
        raise CliError(
            "FEN-2001",
            f"catalog import requires --symbol, --footprint, --id and --out (missing: {names or '-'})"
            + ("" if args.lib_id is None else "; it takes no positional id"),
        )
    if args.kind is not None or args.query is not None:
        raise CliError("FEN-2001", "catalog import takes neither --kind nor --query")
    out = Path(args.out)
    target_folder(out.parent.as_posix(), ctx.cwd)
    target = out if out.is_absolute() else ctx.cwd / out
    symbol, footprint = definitions(args.symbol, args.footprint, target.parent, ctx.kicad_target)
    pins, issues = pin_template(symbol, footprint, args.pin)
    if any(found.severity == "error" for found in issues):
        return Result(
            result={"device": args.device_id, "out": args.out},
            issues=(
                *issues,
                Issue(
                    "catalog.import-deprecated",
                    "info",
                    "catalog import is deprecated; use fenolite library import",
                ),
            ),
            evidence=DEVICE_EVIDENCE,
        )
    device = legacy_template(
        symbol,
        pins,
        device_id=args.device_id,
        symbol_id=args.symbol,
        footprint_id=args.footprint,
        date=ctx.timestamp.astimezone(datetime.UTC).date().isoformat(),
        manufacturer=args.manufacturer,
        mpn=args.mpn,
        datasheet=args.datasheet,
        ref_prefix=args.ref_prefix,
        file=args.out,
    )
    data = device_text(device).encode("utf-8")
    replaced = False
    if target.is_file():
        replaced = True
        try:
            existing = parse_device(target.read_text(encoding="utf-8"), file=args.out)
            edited = is_edited(existing)
        except (DeviceFormatError, UnicodeDecodeError):
            edited = True
        if edited and not ctx.allow_lossy:
            raise CliError(
                "FEN-7001",
                f"{args.out} was edited after it was imported (or is not a device record); a re-import would "
                "overwrite the edit",
                hint="keep the file, write the template to another --out, or pass --allow-lossy to overwrite",
                where=args.out,
            )
    return Result(
        result={
            "device": device.id,
            "out": args.out,
            "functions": [pin.function for pin in device.pins],
            "digest": device_digest(device),
            "replaces": replaced,
            "evidence": device.evidence,
        },
        issues=(
            *issues,
            Issue(
                "catalog.import-deprecated",
                "info",
                "catalog import is deprecated; use fenolite library import",
            ),
        ),
        evidence=DEVICE_EVIDENCE,
        writes=(PlannedWrite(path=args.out, data=data, kind="device"),),
    )


COMMAND = Command(
    "catalog",
    "inspect the built-in component catalog and devices, export its visual browser (view --out FILE) or "
    "import a device template (import --symbol --footprint --id --out)",
    True,
    _register,
    _run,
    example_args=("list",),
    mutation_example_args=("view", "--out", "catalog.html", "--kind", "symbol", "--query", "resistor"),
)

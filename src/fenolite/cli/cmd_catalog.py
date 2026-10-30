# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite catalog``: inspect the built-in offline component definitions and devices, export a browser,
or write a device template from a symbol and a footprint (``import``; change c0248, ``docs/devices.md``)."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import re
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from fenolite.catalog import ENTRIES, CatalogEntry, get_footprint, get_symbol, list_entries
from fenolite.catalog.devices import (
    FUNCTION,
    IMPORT_TOOL,
    REF_PREFIX,
    DeviceFormatError,
    check_device,
    device_digest,
    device_text,
    is_edited,
    parse_device,
    shipped_devices,
    stamped,
)
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.model import canonical
from fenolite.model.library import DeviceDef, DevicePin, FootprintDef, SymbolDef
from fenolite.pick.rows import Family, catalog_name, family_text, shipped_families

CATALOG_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-CATALOG",))
"""The catalog is authored for Fenolite and shown as stored."""
DEVICE_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-CATALOG", "H-G-DEVICE-RECORD"))
"""Devices are shown as stored; ``digest`` and ``edited`` rest on the canonical digest (change c0248)."""
FAMILY_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-CATALOG", "H-G-PICK-DETERMINISTIC"))
"""Families are shown as stored, each attribute with its sources (change c0254)."""
CATALOG_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {"catalog.pin-without-pad": "error", "catalog.pad-unmapped": "warning"}
)
"""The issue codes of ``catalog import`` (change c0248)."""
PIN_OPTION = re.compile(r"(?P<function>[^=]+)=(?P<pin>[^:]+)(?::(?P<pads>[^+]+(?:\+[^+]+)*))?")
"""``--pin FUNCTION=PIN[:PAD[+PAD]]``."""


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


def _issue(code: str, message: str, where: str, hint: str) -> Issue:
    return Issue(code, CATALOG_ISSUE_CODES[code], message, where=where, hint=hint)


def _definitions(
    symbol_id: str, footprint_id: str, out: Path, ctx: Context
) -> tuple[SymbolDef, FootprintDef]:
    """The symbol and the footprint of an import: catalog ids offline, other ids through the build's
    ``LibraryResolver`` with the project folder set to the folder of ``--out``."""
    catalog_ids = {entry.lib_id: entry.kind for entry in ENTRIES}
    resolver = None
    if catalog_ids.get(symbol_id) != "symbol" or catalog_ids.get(footprint_id) != "footprint":
        from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver

        resolver = LibraryResolver(LibraryConfig(target_major=ctx.kicad_target, project_dir=out.parent))
    if catalog_ids.get(symbol_id) == "symbol":
        symbol = get_symbol(symbol_id)
    else:
        from fenolite.backends.kicad import sym

        assert resolver is not None
        symbol = sym.resolve_extends(resolver.symbol_chain(symbol_id))[0]
    if catalog_ids.get(footprint_id) == "footprint":
        footprint = get_footprint(footprint_id)
    else:
        assert resolver is not None
        footprint = resolver.footprint(footprint_id)
    return symbol, footprint


def _pin_options(values: list[str]) -> dict[str, tuple[str, tuple[str, ...] | None]]:
    """``--pin`` options: symbol pin → (function, pads or ``None`` for the pad of its number)."""
    found: dict[str, tuple[str, tuple[str, ...] | None]] = {}
    for value in values:
        match = PIN_OPTION.fullmatch(value)
        if match is None or not FUNCTION.fullmatch(match["function"]):
            raise CliError(
                "FEN-2001",
                f"--pin {value!r}: write FUNCTION=PIN[:PAD[+PAD]], the function matching {FUNCTION.pattern}",
                where="--pin",
            )
        if match["pin"] in found:
            raise CliError("FEN-2001", f"--pin names symbol pin {match['pin']!r} twice", where="--pin")
        pads = tuple(match["pads"].split("+")) if match["pads"] else None
        found[match["pin"]] = (match["function"], pads)
    return found


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
    target = out if out.is_absolute() else ctx.cwd / out
    symbol, footprint = _definitions(args.symbol, args.footprint, target, ctx)
    options = _pin_options(args.pin)
    numbers = list(dict.fromkeys(pin.number for pin in symbol.pins))
    unknown = sorted(set(options) - set(numbers))
    if unknown:
        raise CliError(
            "FEN-2001", f"--pin names symbol pin {unknown[0]!r}, which {args.symbol} lacks", where="--pin"
        )
    names = {pin.number: pin.name for pin in symbol.pins}
    pads = [pad.number for pad in footprint.pads if pad.number]
    issues: list[Issue] = []
    groups: dict[str, list[tuple[str, str]]] = {}
    folded: dict[str, str] = {}
    for number in numbers:
        if number in options:
            function, given = options[number]
            targets = given if given is not None else (number,)
        else:
            name = names[number]
            function = name if name and name != "~" and FUNCTION.fullmatch(name) else f"P{number}"
            targets = (number,)
        other = folded.get(function.casefold())
        if other is not None and other != function:
            function = f"P{number}"
        folded.setdefault(function.casefold(), function)
        for pad in targets:
            if pad not in pads:
                issues.append(
                    _issue(
                        "catalog.pin-without-pad",
                        f"symbol pin {number} of {args.symbol} has no pad {pad} on {args.footprint}",
                        number,
                        f"map it with --pin FUNCTION={number}:PAD, or choose the footprint the symbol is "
                        "meant for",
                    )
                )
        groups.setdefault(function, []).extend((number, pad) for pad in targets)
    used = {pad for pairs in groups.values() for _, pad in pairs}
    for pad in dict.fromkeys(pads):
        if pad not in used:
            issues.append(
                _issue(
                    "catalog.pad-unmapped",
                    f"pad {pad} of {args.footprint} is named by no symbol pin and is left out",
                    pad,
                    "list it in unused_pads when you review the file, or map it with --pin",
                )
            )
    if any(found.severity == "error" for found in issues):
        return Result(
            result={"device": args.device_id, "out": args.out}, issues=tuple(issues), evidence=DEVICE_EVIDENCE
        )
    ref_prefix = args.ref_prefix or symbol.reference
    if not REF_PREFIX.fullmatch(ref_prefix):
        raise CliError(
            "FEN-2001",
            f"the symbol's reference prefix {ref_prefix!r} is not [A-Z][A-Z_]*; give --ref-prefix",
            where="--ref-prefix",
        )
    pins = tuple(
        DevicePin(function, tuple(sorted(pairs, key=lambda pair: (pair[0], pairs.index(pair)))))
        for function, pairs in sorted(groups.items())
    )
    try:
        record = parse_device(
            device_text(
                DeviceDef(
                    id=args.device_id,
                    summary=f"{args.symbol} on {args.footprint} (imported template, not reviewed)",
                    symbol=args.symbol,
                    footprint=args.footprint,
                    manufacturer=args.manufacturer,
                    mpn=args.mpn,
                    datasheet=args.datasheet,
                    ref_prefix=ref_prefix,
                    evidence="UNVERIFIED",
                    pins=pins,
                )
            ),
            file=args.out,
        )
    except DeviceFormatError as error:
        raise CliError(
            "FEN-2001", f"the imported device is not valid: {error.message}", where=error.locator
        ) from None
    date = ctx.timestamp.astimezone(datetime.UTC).date().isoformat()
    device = stamped(record, tool=IMPORT_TOOL, source=f"{args.symbol} {args.footprint}", date=date)
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
        issues=tuple(issues),
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

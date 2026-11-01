# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The shared c0248 pin template; c0264 file imports and the compatibility alias use it."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from fenolite.catalog import ENTRIES, get_footprint, get_symbol
from fenolite.catalog.devices import (
    FUNCTION,
    IMPORT_TOOL,
    REF_PREFIX,
    DeviceFormatError,
    device_text,
    parse_device,
    stamped,
)
from fenolite.core.errors import Issue, Severity
from fenolite.library.importer.sources import ImportUsageError
from fenolite.model.library import DeviceDef, DevicePin, FootprintDef, SymbolDef

CATALOG_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "catalog.pin-without-pad": "error",
        "catalog.pad-unmapped": "warning",
        "catalog.import-deprecated": "info",
    }
)
PIN_OPTION = re.compile(r"(?P<function>[^=]+)=(?P<pin>[^:]+)(?::(?P<pads>[^+]+(?:\+[^+]+)*))?")


def _issue(code: str, message: str, where: str, hint: str) -> Issue:
    return Issue(code, CATALOG_ISSUE_CODES[code], message, where=where, hint=hint)


def definitions(
    symbol_id: str, footprint_id: str, project_dir: Path, target: int
) -> tuple[SymbolDef, FootprintDef]:
    """The symbol and the footprint of an import: catalog ids offline, other ids through the build's
    ``LibraryResolver`` with the project folder set to the folder of ``--out``."""
    catalog_ids = {entry.lib_id: entry.kind for entry in ENTRIES}
    resolver = None
    if catalog_ids.get(symbol_id) != "symbol" or catalog_ids.get(footprint_id) != "footprint":
        from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver

        resolver = LibraryResolver(LibraryConfig(target_major=target, project_dir=project_dir))
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


def pin_options(values: list[str]) -> dict[str, tuple[str, tuple[str, ...] | None]]:
    """``--pin`` options: symbol pin → (function, pads or ``None`` for the pad of its number)."""
    found: dict[str, tuple[str, tuple[str, ...] | None]] = {}
    for value in values:
        match = PIN_OPTION.fullmatch(value)
        if match is None or not FUNCTION.fullmatch(match["function"]):
            raise ImportUsageError(
                f"--pin {value!r}: write FUNCTION=PIN[:PAD[+PAD]], the function matching {FUNCTION.pattern}",
                locator="--pin",
            )
        if match["pin"] in found:
            raise ImportUsageError(f"--pin names symbol pin {match['pin']!r} twice", locator="--pin")
        pads = tuple(match["pads"].split("+")) if match["pads"] else None
        found[match["pin"]] = (match["function"], pads)
    return found


def pin_template(
    symbol: SymbolDef, footprint: FootprintDef, values: list[str]
) -> tuple[tuple[DevicePin, ...], tuple[Issue, ...]]:
    options = pin_options(values)
    numbers = list(dict.fromkeys(pin.number for pin in symbol.pins))
    unknown = sorted(set(options) - set(numbers))
    if unknown:
        raise ImportUsageError(
            f"--pin names symbol pin {unknown[0]!r}, which {symbol.lib_id} lacks", locator="--pin"
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
                        f"symbol pin {number} of {symbol.lib_id} has no pad {pad} on {footprint.lib_id}",
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
                    f"pad {pad} of {footprint.lib_id} is named by no symbol pin and is left out",
                    pad,
                    "list it in unused_pads when you review the file, or map it with --pin",
                )
            )
    pins = tuple(
        DevicePin(function, tuple(sorted(pairs, key=lambda pair: (pair[0], pairs.index(pair)))))
        for function, pairs in sorted(groups.items())
    )
    return pins, tuple(issues)


def legacy_template(
    symbol: SymbolDef,
    pins: tuple[DevicePin, ...],
    *,
    device_id: str,
    symbol_id: str,
    footprint_id: str,
    date: str,
    manufacturer: str = "",
    mpn: str = "",
    datasheet: str = "",
    ref_prefix: str = "",
    file: str = "",
) -> DeviceDef:
    """The byte-compatible c0248 record, now shared by the local-import compatibility adapter."""
    ref_prefix = ref_prefix or symbol.reference
    if not REF_PREFIX.fullmatch(ref_prefix):
        raise ImportUsageError(
            f"the symbol's reference prefix {ref_prefix!r} is not [A-Z][A-Z_]*; give --ref-prefix",
            locator="--ref-prefix",
        )
    try:
        record = parse_device(
            device_text(
                DeviceDef(
                    id=device_id,
                    summary=f"{symbol_id} on {footprint_id} (imported template, not reviewed)",
                    symbol=symbol_id,
                    footprint=footprint_id,
                    manufacturer=manufacturer,
                    mpn=mpn,
                    datasheet=datasheet,
                    ref_prefix=ref_prefix,
                    evidence="UNVERIFIED",
                    pins=pins,
                )
            ),
            file=file,
        )
    except DeviceFormatError as error:
        raise ImportUsageError(
            f"the imported device is not valid: {error.message}", locator=error.locator
        ) from None
    device = stamped(record, tool=IMPORT_TOOL, source=f"{symbol_id} {footprint_id}", date=date)
    return device

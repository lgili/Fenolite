# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Read a user's local model files through Fenolite's existing clean-room adapters (c0264)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TypeVar

from fenolite.backends.altium.adapter.library import import_footprints, import_symbols
from fenolite.backends.altium.read.pcblib import read_pcblib
from fenolite.backends.altium.read.schlib import read_schlib
from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.sym import read_symbol_library, resolve_extends
from fenolite.catalog.generate.symbol import generate_symbol
from fenolite.core.errors import FormatError, Issue
from fenolite.library.importer.zipsafe import MAX_MEMBER, MAX_TOTAL, SUPPORTED, read_zip
from fenolite.model.library import FootprintDef, PinRow, PinTable, SymbolDef


class ImportUsageError(FormatError):
    """An import choice that needs a different argument (FEN-2001)."""

    cli_code = "FEN-2001"

    def __init__(self, message: str, *, hint: str = "", file: str = "", locator: str = "") -> None:
        super().__init__(message, file=file, locator=locator)
        self.hint = hint


@dataclass(frozen=True, slots=True)
class Source:
    file: str
    member: str
    kind: str
    sha256: str
    data: bytes = b""

    def to_data(self) -> dict[str, str]:
        return {"file": self.file, "member": self.member, "kind": self.kind, "sha256": self.sha256}

    @property
    def label(self) -> str:
        return f"{self.file}!{self.member}" if self.member else self.file


@dataclass(frozen=True, slots=True)
class Skipped:
    file: str
    member: str
    reason: str

    def to_data(self) -> dict[str, str]:
        return {"file": self.file, "member": self.member, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class Selection:
    symbol: SymbolDef
    footprint: FootprintDef
    alternatives: tuple[FootprintDef, ...]
    steps: tuple[Source, ...]
    sources: tuple[Source, ...]
    skipped: tuple[Skipped, ...]
    issues: tuple[Issue, ...]
    altium_symbol: bool = False


Definition = TypeVar("Definition", SymbolDef, FootprintDef)


def _choose(
    items: list[tuple[str, Definition]], name: str | None, preferred: str, what: str
) -> tuple[str, Definition]:
    candidates = [item for item in items if item[0] == preferred] or items
    if name is not None:
        candidates = [item for item in candidates if item[1].name == name]
    if len(candidates) != 1:
        names = sorted({item.name for _, item in items})
        listed = ", ".join(names[:24]) + (", …" if len(names) > 24 else "")
        raise ImportUsageError(
            f"choose one {what}" if name is None else f"{what} {name!r} is not a unique item",
            hint=f"pass --{what} NAME; available: {listed or 'none'}",
        )
    return candidates[0]


def _source(file: str, member: str, kind: str, data: bytes) -> Source:
    return Source(file, member, kind, hashlib.sha256(data).hexdigest(), data)


def _read_file(path: Path, limit: int) -> bytes:
    try:
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
    except OSError as error:
        raise FormatError(f"source cannot be read: {error.strerror}", file=path.name) from None
    if len(data) > limit:
        raise FormatError(f"source exceeds {limit} byte limit", file=path.name)
    return data


def read_sources(
    paths: tuple[Path, ...] | list[Path],
    *,
    symbol: str | None = None,
    footprint: str | None = None,
    prefer: str = "kicad",
) -> Selection:
    """Read supported sources, choose exactly one symbol/footprint and retain source digests.

    Only basenames and archive-relative member names reach the returned records. No temporary files,
    external programs, network requests or vendor parser imports are used.
    """
    sources: list[Source] = []
    skipped: list[Skipped] = []
    for path in sorted(paths, key=lambda p: (p.name, str(p))):
        suffix = path.suffix.casefold()
        if suffix == ".intlib":
            raise ImportUsageError(
                "IntLib import is not supported",
                file=path.name,
                hint="export the .SchLib and .PcbLib from Altium, or wait for the IntLib reader",
            )
        if suffix not in SUPPORTED | {".zip"}:
            raise ImportUsageError(
                f"unsupported source {path.name!r}", hint="give KiCad, SchLib, PcbLib, STEP or zip files"
            )
        data = _read_file(path, MAX_TOTAL if suffix == ".zip" else MAX_MEMBER)
        source = _source(path.name, "", suffix[1:], data)
        sources.append(source)
        if suffix == ".zip":
            archive = read_zip(data, file=path.name)
            for entry in archive.members:
                sources.append(
                    _source(
                        path.name, entry.name, PurePosixPath(entry.name).suffix.casefold()[1:], entry.data
                    )
                )
            skipped.extend(Skipped(path.name, item.name, item.reason) for item in archive.skipped)
    symbols: list[tuple[str, SymbolDef]] = []
    footprints: list[tuple[str, FootprintDef]] = []
    steps: list[Source] = []
    issues: list[Issue] = []
    for source in sources:
        library = PurePosixPath(source.member or source.file).stem
        try:
            if source.kind == "kicad_sym":
                symbols.extend(
                    ("kicad", item)
                    for item in resolve_extends(
                        read_symbol_library(
                            source.data.decode("utf-8"), library=library, file=source.label, issues=issues
                        )
                    )
                )
            elif source.kind == "kicad_mod":
                footprints.append(
                    (
                        "kicad",
                        read_footprint(
                            source.data.decode("utf-8"), library=library, file=source.label, issues=issues
                        ),
                    )
                )
            elif source.kind == "schlib":
                result = import_symbols(
                    read_schlib(source.data, file=source.label),
                    name=library,
                    file=source.label,
                    sha256=source.sha256,
                    issues=issues,
                )
                symbols.extend(("altium", item) for item in result.symbols)
            elif source.kind == "pcblib":
                result = import_footprints(
                    read_pcblib(source.data, file=source.label),
                    name=library,
                    file=source.label,
                    sha256=source.sha256,
                    issues=issues,
                )
                footprints.extend(("altium", item) for item in result.footprints)
            elif source.kind in {"step", "stp"}:
                if not source.data.startswith(b"ISO-10303-21;") or b"FILE_SCHEMA" not in source.data:
                    raise FormatError(
                        "STEP must start with ISO-10303-21; and hold FILE_SCHEMA", file=source.label
                    )
                steps.append(source)
        except UnicodeDecodeError:
            raise FormatError("source is not UTF-8", file=source.label) from None
    chosen_kind, chosen_symbol = _choose(symbols, symbol, prefer, "symbol")
    footprint_kind, chosen_footprint = _choose(footprints, footprint, prefer, "footprint")
    alternatives = tuple(item for kind, item in footprints if kind != footprint_kind)
    if len(alternatives) > 1:
        _, other = _choose(
            [(kind, item) for kind, item in footprints if kind != footprint_kind],
            footprint,
            prefer,
            "footprint",
        )
        alternatives = (other,)
    if len(steps) > 1:
        raise ImportUsageError(
            "more than one STEP body", hint="give a single STEP body for the selected device"
        )
    altium = chosen_kind == "altium"
    if altium:
        table = PinTable(
            chosen_symbol.name,
            rows=tuple(
                PinRow(
                    pin.number,
                    pin.name,
                    pin.etype,
                    shape=pin.shape,
                    hidden=pin.hidden,
                    alternates=pin.alternates,
                )
                for pin in chosen_symbol.pins
            ),
            reference=chosen_symbol.reference.rstrip("?") or "U",
        )
        chosen_symbol, _, generated_issues = generate_symbol(table, library=chosen_symbol.library)
        issues.extend(generated_issues)
        issues.append(
            Issue(
                "library.import-symbol-regenerated",
                "info",
                "Altium symbol drawn from its pins; source body graphics are unmapped",
            )
        )
    issues.extend(
        Issue("library.import-skipped", "info", item.reason, where=f"{item.file}!{item.member}")
        for item in skipped
    )
    return Selection(
        chosen_symbol,
        chosen_footprint,
        alternatives,
        tuple(steps),
        tuple(sources),
        tuple(skipped),
        tuple(issues),
        altium,
    )


__all__ = ["ImportUsageError", "Selection", "Source", "read_sources"]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""CLI adapter for local library imports (c0264); all writes use the shared mutation protocol."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import tomllib
from pathlib import Path

import fenolite
from fenolite.backends.kicad.mod import write_footprint
from fenolite.backends.kicad.sym import write_symbol_library
from fenolite.catalog.devices import ID
from fenolite.catalog.footprints import read_package
from fenolite.catalog.footprints.record import Package
from fenolite.catalog.records import DeviceRecord, ImportOrigin, PackageRecord, parse_record, shipped_tree
from fenolite.cli.api import Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.library.cache import library_dir
from fenolite.library.importer import crosscheck
from fenolite.library.importer.crosscheck import Crosscheck, sources_disagree
from fenolite.library.importer.records import make_records, record_edited
from fenolite.library.importer.sources import Selection, Source, read_sources
from fenolite.library.importer.templates import definitions, pin_template

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-LIBRARY-IMPORT",))
SCHEMA = "fenolite.library-import.v0"
EXAMPLE = str(Path(fenolite.__file__).resolve().parents[2] / "tests/data/library_import/exb6202.zip")
IMPORT_OPTIONS = (
    "into",
    "device_id",
    "symbol",
    "footprint",
    "package",
    "pin",
    "manufacturer",
    "mpn",
    "datasheet",
    "ref_prefix",
    "no_crosscheck",
)


def register(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("local library import")
    group.add_argument(
        "--into", metavar="DIR", help="import/seed: output folder; import requires a project-relative path"
    )
    group.add_argument(
        "--id", dest="device_id", metavar="NS:NAME", help="import: device id (default Imported:<symbol>)"
    )
    group.add_argument(
        "--symbol", metavar="NAME", help="import: select a source symbol, or a lib id without sources"
    )
    group.add_argument(
        "--footprint", metavar="NAME", help="import: select a source footprint, or a lib id without sources"
    )
    group.add_argument(
        "--prefer",
        choices=("kicad", "altium"),
        default=None,
        help="import: preferred source tool (default kicad)",
    )
    group.add_argument(
        "--package", metavar="NAME", help="import: package record file or shipped id for comparison"
    )
    group.add_argument(
        "--pin",
        action="append",
        default=[],
        metavar="FUNCTION=PIN[:PAD[+PAD]]",
        help="import: pin-to-pad mapping",
    )
    group.add_argument("--manufacturer", default="", help="import: manufacturer")
    group.add_argument("--mpn", default="", help="import: manufacturer part number")
    group.add_argument(
        "--datasheet", default="", help="import: https:// URL; propose/review: local datasheet PDF"
    )
    group.add_argument("--ref-prefix", default="", help="import: reference prefix")
    group.add_argument(
        "--no-crosscheck", action="store_true", help="import: skip the inferred package comparison"
    )


def only_import(args: argparse.Namespace, form: str, *, allow_datasheet: bool = False) -> None:
    for name in (*IMPORT_OPTIONS, "prefer"):
        if name == "datasheet" and allow_datasheet:
            continue
        if getattr(args, name):
            raise CliError("FEN-2001", f"--{name.replace('_', '-')} belongs to library import, not {form}")


def target_folder(into: str | None, cwd: Path) -> Path:
    if not into:
        raise CliError("FEN-2001", "library import requires --into DIR")
    path = Path(into)
    if path.is_absolute() or ".." in path.parts or "\\" in into or ":" in into:
        raise CliError("FEN-2001", "--into must be a relative folder inside the project", where="--into")
    target = (cwd / path).resolve()
    forbidden = (Path(fenolite.__file__).resolve().parent, library_dir().resolve())
    if (
        not target.is_relative_to(cwd.resolve())
        or "fenolite_library" in target.parts
        or any(target.is_relative_to(folder) for folder in forbidden)
    ):
        raise CliError(
            "FEN-2001",
            "--into cannot name the installed package, a vendored library, the library cache "
            "or a folder outside the project",
            where="--into",
        )
    if target.is_dir():
        for marker in target.rglob("device.toml"):
            try:
                record = tomllib.loads(marker.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
                continue
            if record.get("licence") == "CC0-1.0" and "origin" not in record:
                raise CliError(
                    "FEN-2001", "--into contains shipped CC0 devices without an origin", where="--into"
                )
    return target


def _libids(args: argparse.Namespace, ctx: Context) -> tuple[Selection, list[Path]]:
    if not args.symbol or not args.footprint:
        raise CliError(
            "FEN-2001", "without sources, library import requires --symbol LIB:SYM and --footprint LIB:FP"
        )
    symbol, footprint = definitions(args.symbol, args.footprint, ctx.cwd, ctx.kicad_target)
    # The resolved canonical bytes identify lib-id sources, including the built-in catalog offline.
    bodies = (
        (
            f"{symbol.name}.kicad_sym",
            "lib-id-symbol",
            write_symbol_library([symbol], target=ctx.kicad_target).encode(),
        ),
        (
            f"{footprint.name}.kicad_mod",
            "lib-id-footprint",
            write_footprint(footprint, target=ctx.kicad_target).encode(),
        ),
    )
    sources = tuple(
        Source(name, "", kind, hashlib.sha256(data).hexdigest(), data) for name, kind, data in bodies
    )
    paths = [
        Path(item.provenance.file)
        for item in (symbol, footprint)
        if item.provenance is not None and Path(item.provenance.file).is_file()
    ]
    return Selection(symbol, footprint, (), (), sources, (), ()), paths


def _package(name: str | None, ctx: Context) -> tuple[Package | PackageRecord | None, Path | None]:
    if name is None:
        return None, None
    path = Path(name) if Path(name).is_absolute() else ctx.cwd / name
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        raw = tomllib.loads(text)
        if raw.get("generator") == "explicit":
            record = parse_record(text, file=path.name)
            if not isinstance(record, PackageRecord):
                raise CliError("FEN-2001", "--package must name a package record")
            return record, path
        return read_package(text, file=path.name), path
    record = shipped_tree().get("package", name if ":" in name else f"Fenolite:{name}")
    if isinstance(record, PackageRecord):
        return record, None
    raise CliError(
        "FEN-2001", f"unknown package {name!r}", hint="pass a package record file or a shipped package id"
    )


def _existing(folder: Path, *, allow_lossy: bool) -> DeviceRecord | None:
    if not folder.exists():
        return None
    marker = folder / "device.toml"
    try:
        record = parse_record(marker.read_text(encoding="utf-8"), file="device.toml")
        if not isinstance(record, DeviceRecord) or not isinstance(record.header.origin, ImportOrigin):
            raise ValueError("not a local import")
        edited = record_edited(record)
        for output in record.header.origin.output:
            path = folder / output.file
            edited = (
                edited or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != output.sha256
            )
    except (OSError, UnicodeDecodeError, FormatError, ValueError):
        record, edited = None, True
    if edited and not allow_lossy:
        raise CliError(
            "FEN-7001",
            "the device folder was edited after import or is not an imported device",
            where=folder.name,
            hint="keep the folder, import under another --id, "
            "or pass --allow-lossy to replace the edited files",
        )
    return record


def run(args: argparse.Namespace, ctx: Context) -> Result:
    for name in (
        "out",
        "diff",
        "library",
        "positions",
        "no_step",
        "no_pcblib",
        "item",
        "base",
        "proof",
        "release_version",
        "upstream",
        "keep",
        "with_current",
        "release",
    ):
        if getattr(args, name, None):
            raise CliError("FEN-2001", f"--{name.replace('_', '-')} is not an import option")
    root = target_folder(args.into, ctx.cwd)
    names = args.path[1:]
    paths = [Path(name) if Path(name).is_absolute() else ctx.cwd / name for name in names]
    if paths:
        selection = read_sources(
            paths, symbol=args.symbol, footprint=args.footprint, prefer=args.prefer or "kicad"
        )
    else:
        selection, paths = _libids(args, ctx)
    device_id: str = args.device_id or f"Imported:{selection.symbol.name}"
    if not ID.fullmatch(device_id) or device_id.startswith("Fenolite:"):
        raise CliError("FEN-2001", "--id must name a project NS:NAME")
    namespace, name = device_id.split(":", 1)
    folder = root / namespace / name
    if not folder.resolve().is_relative_to(root):
        raise CliError("FEN-2001", "device folder resolves outside --into")
    target_folder(folder.relative_to(ctx.cwd.resolve()).as_posix(), ctx.cwd)
    existing = _existing(folder, allow_lossy=ctx.allow_lossy)
    package, package_path = _package(args.package, ctx)
    compared = (
        crosscheck(selection.footprint, package)
        if not args.no_crosscheck
        else Crosscheck(
            None,
            None,
            (Issue("library.import-crosscheck-skipped", "info", "cross-check skipped by --no-crosscheck"),),
        )
    )
    pins, pin_issues = pin_template(selection.symbol, selection.footprint, args.pin)
    date = ctx.timestamp.astimezone(datetime.UTC).date().isoformat()
    if existing is not None and isinstance(existing.header.origin, ImportOrigin):
        old_sources = [(s.file, s.member, s.sha256) for s in existing.header.origin.source]
        if old_sources == [(s.file, s.member, s.sha256) for s in selection.sources]:
            date = existing.header.origin.date
    imported = make_records(
        selection,
        device_id=device_id,
        date=date,
        target=ctx.kicad_target,
        family=compared.family or "imported",
        nominal=compared.match.nominal if compared.match is not None else None,
        pins=pins,
        manufacturer=args.manufacturer,
        mpn=args.mpn,
        datasheet=args.datasheet,
        ref_prefix=args.ref_prefix,
    )
    issues = (
        *imported.issues,
        *pin_issues,
        *compared.issues,
        *(i for other in selection.alternatives for i in sources_disagree(selection.footprint, other)),
    )
    relative = folder.relative_to(ctx.cwd.resolve()).as_posix()
    unchanged = False
    prior_files: set[str] = (
        {
            path.relative_to(folder).as_posix()
            for path in folder.rglob("*")
            if path.is_file() and not path.name.endswith(".bak")
        }
        if folder.is_dir()
        else set()
    )
    if prior_files - imported.files.keys():
        raise CliError(
            "FEN-7001",
            "re-import would remove previous output files; this importer supports file replacement only",
            where=relative,
            hint="keep the folder and import under another --id; --allow-lossy cannot remove files",
        )
    if existing is not None and isinstance(existing.header.origin, ImportOrigin):
        # Flags and identity changes must still take effect even if all source digests stayed equal.
        unchanged = not record_edited(existing) and all(
            (folder / filename).is_file() and (folder / filename).read_bytes() == data
            for filename, data in imported.files.items()
        )
    result: dict[str, object] = {
        "schema": SCHEMA,
        "device": device_id,
        "folder": relative,
        "sources": [s.to_data() for s in selection.sources],
        "skipped": [s.to_data() for s in selection.skipped],
        "symbol": device_id,
        "footprint": device_id,
        "step": f"{relative}/{name}.step" if selection.steps else None,
        "family": compared.family,
        "crosscheck": compared.to_data(),
        "unchanged": unchanged,
        "evidence": "UNVERIFIED",
    }
    writes = (
        ()
        if unchanged or any(i.severity == "error" for i in issues)
        else tuple(
            PlannedWrite(f"{relative}/{filename}", data, "library-import")
            for filename, data in sorted(imported.files.items())
        )
    )
    existing_paths = sorted(p for p in folder.rglob("*") if p.is_file()) if folder.is_dir() else []
    return Result(
        result=result,
        issues=issues,
        evidence=EVIDENCE,
        writes=writes,
        depends=depends_on(ctx.cwd, *paths, package_path, *existing_paths),
    )


__all__ = ["EXAMPLE", "SCHEMA", "only_import", "register", "run", "target_folder"]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite inspect``: a KiCad summary or an MS-CFB stream tree, without running any tool.

Boards, footprint files and symbol libraries are read by their backend; schematics and drawing sheets
are read header-only. ``model.*`` findings are counted, not reported: ``inspect`` describes a file,
``check`` judges it.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path
from typing import Any

from fenolite.backends import registry
from fenolite.backends.kicad import pcb, versions
from fenolite.backends.kicad.sexpr import Node, parse_bytes
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design
from fenolite.model.library import Library

HELP = "summarise a KiCad file or list an Altium compound file's streams (runs no tool)"
HEADER_ONLY = frozenset({versions.FileKind.SCHEMATIC, versions.FileKind.WORKSHEET})
HEADER_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-TOK-CONSTANTS",))
DEFERRED = (".kicad_pro", ".kicad_dru")
READS = "inspect reads .kicad_pcb, .kicad_mod, .kicad_sym(dir), .kicad_sch and .kicad_wks"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'inspect'."
    parser.add_argument("file", metavar="FILE", help="a board, footprint, symbol library, schematic or sheet")
    parser.add_argument("--summary", action="store_true", help="header and counts (the default view)")
    parser.add_argument("--streams", action="store_true", help="list storages and streams in an MS-CFB file")
    parser.add_argument("--limit-bytes", type=_positive_int, metavar="N", help="maximum compound-file size")


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def _stream_view(path: Path, limit_bytes: int | None) -> Result:
    # Keep the container dependency lazy: ordinary KiCad inspection does not import the Altium reader.
    from fenolite.backends.altium.read import cfb as compound_reader

    if not path.is_file():
        raise CliError("FEN-3001", f"{path.name} is not a regular file", where=path.name)
    limits = compound_reader.DEFAULT_LIMITS
    if limit_bytes is not None:
        limits = compound_reader.Limits(
            max_file_bytes=limit_bytes,
            max_entries=limits.max_entries,
            max_depth=limits.max_depth,
        )
    compound = compound_reader.read_compound(path, limits=limits)
    entries: list[dict[str, Any]] = []
    for node in compound.nodes()[1:]:
        if node.kind == "storage":
            entries.append({"path": node.path, "type": "storage", "children": len(node.children)})
        else:
            stream = compound.read(node.path)
            entries.append(
                {
                    "path": node.path,
                    "type": "stream",
                    "size": node.size,
                    "sha256": hashlib.sha256(stream).hexdigest(),
                }
            )
    result = {
        "kind": "compound_file",
        "format_version": str(compound.header.major),
        "major": compound.header.major,
        "minor": compound.header.minor,
        "sector_size": compound.header.sector_size,
        "mini_sector_size": compound.header.mini_sector_size,
        "sectors": compound.header.sector_count,
        "fat_sectors": compound.header.fat_sectors,
        "difat_sectors": compound.header.difat_sectors,
        "directory_entries": compound.header.directory_entries,
        "root_clsid": compound.root.clsid.hex() if any(compound.root.clsid) else None,
        "counts": {
            "storages": len(compound.storages()),
            "streams": len(compound.streams()),
            "bytes": sum(compound.node(name).size for name in compound.streams()),
        },
        "entries": entries,
    }
    return Result(
        result=result,
        issues=compound.notes,
        evidence=compound.evidence,
        input=InputRef(
            path=path.name,
            sha256=compound.file_sha256,
            kind="compound_file",
            format_version=str(compound.header.major),
        ),
    )


def _header(path: Path) -> tuple[Node, versions.FormatInfo]:
    """The parsed root of ``path`` (a folder: its first ``.kicad_sym`` file) and its format."""
    target = path
    if path.is_dir():
        found = sorted(path.glob("*.kicad_sym"))
        if not found:
            raise CliError("FEN-3001", f"{path.name} holds no .kicad_sym file", where=path.name)
        target = found[0]
    root = parse_bytes(target.read_bytes(), file=target.name)
    return root, versions.inspect(root, file=target.name)


def _counts(content: Design | Library) -> dict[str, int]:
    if isinstance(content, Design):
        board = content.board
        if board is None:
            return {"footprints": 0, "pads": 0, "nets": len(content.circuit.nets)}
        return {
            "footprints": len(board.footprints),
            "pads": sum(len(fp.pads) for fp in board.footprints),
            "nets": len(content.circuit.nets),
            "tracks": len(board.tracks),
            "arcs": len(board.arcs),
            "vias": len(board.vias),
            "zones": len(board.zones),
            "fills": sum(len(z.fills) for z in board.zones),
            "keepouts": len(board.keepouts),
            "graphics": len(board.graphics),
            "texts": len(board.texts),
        }
    if content.footprints:
        fp = content.footprints[0]
        return {"pads": len(fp.pads), "graphics": len(fp.graphics), "models": len(fp.models)}
    return {
        "symbols": len(content.symbols),
        "units": sum(len(s.units) for s in content.symbols),
        "pins": sum(len(s.pins) for s in content.symbols),
    }


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    given = Path(args.file)
    path = given if given.is_absolute() else ctx.cwd / given
    if not path.exists():
        raise CliError("FEN-3001", f"{args.file} does not exist", where=path.name)
    if args.summary and getattr(args, "streams", False):
        raise CliError(
            "FEN-2001", "--summary and --streams are mutually exclusive", where="--summary,--streams"
        )
    if getattr(args, "streams", False):
        return _stream_view(path, args.limit_bytes)
    if args.limit_bytes is not None:
        raise CliError("FEN-2001", "--limit-bytes requires --streams", where="--limit-bytes")
    kind = versions.kind_for_suffix(path.name)
    if path.suffix in DEFERRED or (kind is None and path.suffix != ".kicad_symdir"):
        with path.open("rb") as handle:
            compound_signature = handle.read(8) == bytes.fromhex("D0CF11E0A1B11AE1")
        hint = "pass --streams to inspect this compound file" if compound_signature else READS
        raise CliError("FEN-2001", f"inspect does not read {path.name} yet", hint=hint)
    root, info = _header(path)
    result: dict[str, Any] = {
        "kind": info.kind.value,
        "format_version": info.version,
        "major": info.major,
        "status": info.status.value,
        "generator": info.generator,
        "generator_version": info.generator_version,
    }
    issues: tuple[Any, ...] = ()
    if kind in HEADER_ONLY:
        heads = Counter(child.name for child in root.nodes())
        result.update(counts=dict(sorted(heads.items())), opaque_count=None, model_findings={})
        evidence = HEADER_EVIDENCE
    else:
        backend = registry.for_path(path)
        if backend is None:
            raise CliError("FEN-2001", f"no backend reads {path.name}")
        read = backend.read(path)
        findings = Counter(i.severity for i in read.issues if i.code.startswith("model."))
        content = read.content
        result.update(
            counts=_counts(content),
            opaque_count=pcb.opaque_count(content) if isinstance(content, Design) else None,
            model_findings=dict(sorted(findings.items())),
        )
        issues = tuple(i for i in read.issues if not i.code.startswith("model."))
        evidence = read.evidence
    data = b"" if path.is_dir() else path.read_bytes()
    return Result(
        result=result,
        issues=issues,
        evidence=evidence,
        input=InputRef(
            path=path.name,
            sha256=hashlib.sha256(data).hexdigest() if data else None,
            kind=info.kind.value,
            format_version=str(info.version),
        ),  # fmt: skip
    )


COMMAND = Command(
    name="inspect",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_BOARD, "--summary"),
)

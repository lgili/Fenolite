# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite inspect``: a KiCad summary, an Altium summary or an MS-CFB stream tree, without running any
tool.

Boards, footprint files and symbol libraries are read by their backend; schematics and drawing sheets
are read header-only. ``model.*`` findings are counted, not reported: ``inspect`` describes a file,
``check`` judges it. A file of a backend whose project is a set of documents (an Altium document, library
or project file; change c0044) is summarised from that backend's reading and from its RT-A1 verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from collections import Counter
from pathlib import Path
from typing import Any

from fenolite.backends import registry
from fenolite.backends.base import DocumentValidator, ReadResult
from fenolite.backends.kicad import pcb, versions
from fenolite.backends.kicad.sexpr import Node, parse_bytes
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.model.board import Stackup
from fenolite.model.design import Design
from fenolite.model.library import Library

HELP = "summarise a KiCad or an Altium file, or list a compound file's streams (runs no tool)"
HEADER_ONLY = frozenset({versions.FileKind.SCHEMATIC, versions.FileKind.WORKSHEET})
HEADER_EVIDENCE = versions.EVIDENCE
DEFERRED = (".kicad_pro", ".kicad_dru")
READS = (
    "inspect reads .kicad_pcb, .kicad_mod, .kicad_sym(dir), .kicad_sch and .kicad_wks, and the Altium files "
    ".PcbDoc, .SchDoc, .PcbLib, .SchLib and .PrjPcb"
)
SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
"""The first eight bytes of a compound file."""


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'inspect'."
    parser.add_argument(
        "file",
        metavar="FILE",
        help="a KiCad board, footprint, symbol library, schematic or sheet; or an Altium document, library "
        "or project file",
    )
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


_VERSION = re.compile(r"(\d+\.\d+)")


def _version_text(header: str | None) -> str | None:
    """The version of a header text such as ``PCB 6.0 Binary File``, as it reads."""
    found = _VERSION.search(header or "")
    return found.group(1) if found else None


def _altium_facts(path: Path, kind: str, content: Design | Library) -> tuple[str | None, dict[str, int], int]:
    """``(format_version, counts, streams)`` of an Altium file: the header's version text, the counts of
    "Altium file summary" (capability altium-verification) and the number of streams of the container (1
    for a text file). The record counts come from the product readers, the model counts from ``content``."""
    # Lazy: ordinary KiCad inspection imports no Altium reader.
    from fenolite.backends.altium.read import cfb as compound_reader
    from fenolite.backends.altium.read import pcb as pcb_reader
    from fenolite.backends.altium.read import pcblib as pcblib_reader
    from fenolite.backends.altium.read import sch as sch_reader
    from fenolite.backends.altium.read import schlib as schlib_reader

    data = path.read_bytes()
    streams = (
        len(compound_reader.open_compound(data, file=path.name).streams()) if data[:8] == SIGNATURE else 1
    )
    if kind == "altium_pcbdoc":
        assert isinstance(content, Design)
        counts = _counts(content) | {
            "components": len(content.circuit.components),
            "rules": len(content.rules.rules) if content.rules is not None else 0,
        }
        return _version_text(pcb_reader.read_pcbdoc(data, file=path.name).header_text), counts, streams
    if kind == "altium_pcblib":
        assert isinstance(content, Library)
        counts = {
            "footprints": len(content.footprints),
            "pads": sum(len(fp.pads) for fp in content.footprints),
            "graphics": sum(len(fp.graphics) for fp in content.footprints),
        }
        return _version_text(pcblib_reader.read_pcblib(data, file=path.name).header_text), counts, streams
    if kind == "altium_schlib":
        assert isinstance(content, Library)
        header = schlib_reader.read_schlib(data, file=path.name).header.props
        return _version_text(header.get("HEADER") if header is not None else None), _counts(content), streams
    assert isinstance(content, Design)
    document = sch_reader.read_schematic(data, file=path.name)
    records = document.all_records()

    def of(cls: type) -> int:
        return sum(isinstance(record, cls) for record in records)

    circuit = content.circuit
    counts = {
        "components": len(circuit.components),
        "pins": sum(len(component.pins) for component in circuit.components),
        "nets": len(circuit.nets),
        "wires": of(sch_reader.Wire),
        "labels": of(sch_reader.NetLabel),
        "power_ports": of(sch_reader.PowerPort),
        "ports": of(sch_reader.Port),
        "sheet_symbols": of(sch_reader.SheetSymbol),
        "no_connects": len(circuit.no_connects),
    }
    header = document.header.props
    return _version_text(header.get("HEADER") if header is not None else None), counts, streams


def _document_summary(path: Path, backend: DocumentValidator, read: ReadResult) -> Result:
    """The summary of one file of a backend that reads document sets (capability altium-verification,
    "Altium file summary"): the keys of the KiCad summary, plus ``streams`` and, for a project file,
    ``documents``. ``opaque_count`` is that of the file's RT-A1 verdict."""
    documents = backend.documents(path)
    document = documents.named(path.name)
    verdict = backend.container_roundtrip(path, "RT-A1")
    findings = Counter(i.severity for i in read.issues if i.code.startswith("model."))
    result: dict[str, Any] = {
        "kind": document.kind,
        "format_version": None,
        "major": None,
        "status": "supported",
        "generator": None,
        "generator_version": None,
    }
    if document.role == "project":
        listed = [
            *({"name": d.name, "kind": d.kind, "role": d.role, "exists": True} for d in documents.documents),
            *({"name": name, "kind": None, "role": None, "exists": False} for name in documents.missing),
        ]
        listed = sorted(
            (entry for entry in listed if entry["name"] != document.name), key=lambda e: str(e["name"])
        )
        roles = Counter(str(entry["role"]) for entry in listed if entry["exists"])
        counts = {"documents": len(listed), "missing": len(documents.missing)} | dict(sorted(roles.items()))
        result.update(counts=counts, documents=listed)
        streams = 1
    else:
        version, counts, streams = _altium_facts(path, document.kind, read.content)
        result.update(format_version=version, counts=counts)
    result.update(
        opaque_count=verdict.opaque_count,
        model_findings=dict(sorted(findings.items())),
        streams={"typed": verdict.streams, "opaque": streams - verdict.streams},
    )
    return Result(
        result=result,
        issues=tuple(i for i in read.issues if not i.code.startswith("model.")),
        evidence=read.evidence,
        input=InputRef(
            path=path.name,
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            kind=document.kind,
            format_version=result["format_version"],
        ),
    )


def _stackup(stackup: Stackup | None) -> dict[str, Any] | None:
    """``result.stackup`` of a board (cli-contract, "Stack-up in inspect"): the total thickness, the
    finish, the impedance-control flag and one object per entry, top to bottom, with the values that
    are set."""
    if stackup is None:
        return None
    layers: list[dict[str, Any]] = []
    for entry in stackup.layers:
        row: dict[str, Any] = {"name": entry.name, "kind": entry.kind, "thickness": entry.thickness}
        for key in ("dielectric_kind", "material", "epsilon_r", "loss_tangent", "color"):
            value = getattr(entry, key)
            if value:
                row[key] = value
        layers.append(row)
    return {
        "thickness": stackup.thickness(),
        "finish": stackup.finish,
        "impedance_controlled": stackup.impedance_controlled,
        "layers": layers,
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
    reader = registry.for_path(path) if path.is_file() else None
    if reader is not None and isinstance(reader, DocumentValidator):
        return _document_summary(path, reader, reader.read(path))
    kind = versions.kind_for_suffix(path.name)
    if path.suffix in DEFERRED or (kind is None and path.suffix != ".kicad_symdir"):
        with path.open("rb") as handle:
            compound_signature = handle.read(8) == SIGNATURE
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
        if isinstance(content, Design) and content.board is not None and kind == versions.FileKind.BOARD:
            result["stackup"] = _stackup(content.board.stackup)
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

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite inspect FILE --summary``: the header and counts of one KiCad file, without running any tool
(capability cli-contract, "Inspect command"; ``docs/cli-contract.md``, "inspect").

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

HELP = "summarise one KiCad file: header, counts and opaque content (runs no tool)"
HEADER_ONLY = frozenset({versions.FileKind.SCHEMATIC, versions.FileKind.WORKSHEET})
HEADER_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-TOK-CONSTANTS",))
DEFERRED = (".kicad_pro", ".kicad_dru")
READS = "inspect reads .kicad_pcb, .kicad_mod, .kicad_sym(dir), .kicad_sch and .kicad_wks"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'inspect'."
    parser.add_argument("file", metavar="FILE", help="a board, footprint, symbol library, schematic or sheet")
    parser.add_argument("--summary", action="store_true", help="header and counts (the default view)")


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
    kind = versions.kind_for_suffix(path.name)
    if path.suffix in DEFERRED or (kind is None and path.suffix != ".kicad_symdir"):
        raise CliError("FEN-2001", f"inspect does not read {path.name} yet",
                       hint=READS)  # fmt: skip
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

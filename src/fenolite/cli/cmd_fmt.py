# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite fmt PATH [--check]``: Fenolite's canonical print of a KiCad S-expression file (capability
cli-contract, "Fmt command"; ``docs/cli-contract.md``, "fmt").

The canonical print is ``dumps(parse(text))``: the tree does not change, only the layout. It is meant for
diffs under version control and is not KiCad's own formatter: KiCad may lay the file out again when it
saves it.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from fenolite.backends.kicad import versions
from fenolite.backends.kicad.sexpr import dumps, first_line_difference, parse_bytes
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level

HELP = "give a KiCad S-expression file Fenolite's canonical print, or check it with --check"
KINDS = frozenset(
    {
        versions.FileKind.BOARD,
        versions.FileKind.FOOTPRINT,
        versions.FileKind.SCHEMATIC,
        versions.FileKind.SYMBOL_LIB,
        versions.FileKind.WORKSHEET,
    }
)
EVIDENCE = Evidence(Level.CORPUS_VERIFIED, hypotheses=("H-K-FMT-IDEMPOTENT",))
"""The fixed point of the canonical print, measured over the corpus (``test_fmt_idempotent.py``)."""
ISSUE_CODES: Mapping[str, Severity] = MappingProxyType({"fmt.would-change": "error"})
READS = "fmt formats .kicad_pcb, .kicad_mod, .kicad_sch, .kicad_sym and .kicad_wks"
PROJECT_HINT = "project files are JSON and are kept byte for byte; " + READS
EXAMPLE_COPY = "fenolite-fmt-example.kicad_pcb"
"""The file of ``mutation_example_args``: a copy of an authored board that is not canonical, which the
test suites write into their empty folder (``tests/_cliexamples.py``)."""


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'fmt'."
    parser.add_argument("path", metavar="PATH", help="a board, footprint, schematic, symbol library or sheet")
    parser.add_argument("--check", action="store_true", help="report whether the file would change")


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    given = Path(args.path)
    path = given if given.is_absolute() else ctx.cwd / given
    if not path.is_file():
        raise CliError("FEN-3001", f"{path.name} is not a file", where=path.name)
    kind = versions.kind_for_suffix(path.name)
    if kind not in KINDS:
        hint = PROJECT_HINT if path.suffix == ".kicad_pro" else READS
        raise CliError("FEN-2001", f"fmt does not format {path.name}", hint=hint, where=path.name)
    assert kind is not None
    data = path.read_bytes()
    root = parse_bytes(data, file=path.name)
    try:
        canonical = dumps(root)
    except ValueError as exc:  # comments below the root: printing would drop or move them
        raise CliError(
            "FEN-7001", f"{path.name} cannot be printed: {exc}", hint="remove the comments below the root",
            where=path.name,
        ) from exc  # fmt: skip
    text = data.decode("utf-8")
    formatted = canonical.encode("utf-8") == data
    first = first_line_difference(text, canonical)
    result: dict[str, Any] = {
        "kind": kind.value,
        "formatted": formatted,
        "lines": len(text.splitlines()),
        "first_difference": first,
    }
    issues: tuple[Issue, ...] = ()
    writes: tuple[PlannedWrite, ...] = ()
    if not formatted and args.check:
        issues = (
            Issue(
                code="fmt.would-change",
                severity="error",
                message=f"{path.name} is not in its canonical print",
                where=f"{path.name}:{first}",
                hint="run 'fenolite fmt' on it with --confirm",
            ),
        )
    elif not formatted:
        target = Path(os.path.relpath(path, ctx.cwd)).as_posix()
        writes = (PlannedWrite(path=target, data=canonical.encode("utf-8"), kind=kind.value),)
    return Result(
        result=result,
        issues=issues,
        evidence=EVIDENCE,
        input=InputRef(
            path=path.name, sha256=hashlib.sha256(data).hexdigest(), kind=kind.value, format_version=None
        ),
        writes=writes,
    )


COMMAND = Command(
    name="fmt",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_BOARD, "--check"),
    mutation_example_args=(EXAMPLE_COPY,),
)

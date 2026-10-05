# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite diff A B``: the differences between two boards, two libraries or two built models, and a
tree view of two KiCad files (capability cli-contract, "Diff command"; ``docs/cli-contract.md``, "diff").

A difference is a result, not a finding: the exit code is 0 either way and ``result.equal`` says it.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fenolite.backends import registry
from fenolite.backends.kicad import sch, versions
from fenolite.backends.kicad.sexpr import Node, first_difference, parse_bytes, tree_equal
from fenolite.checks.diff import DiffReport, diff_designs, diff_libraries, diff_sheets
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.canonical import load_dir
from fenolite.model.design import Design
from fenolite.model.library import Library
from fenolite.model.schematic import SchematicSheet

HELP = "list the differences between two boards, libraries or built models (runs no tool)"
MODEL_KIND = "fenolite_model"
MODEL_EVIDENCE = Evidence(Level.INFERRED)
TREE_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-SEXPR-STRICT",))
TREE_KINDS = frozenset(
    {
        versions.FileKind.BOARD,
        versions.FileKind.FOOTPRINT,
        versions.FileKind.SCHEMATIC,
        versions.FileKind.SYMBOL_LIB,
        versions.FileKind.WORKSHEET,
    }
)
READS = "diff reads .kicad_pcb, .kicad_mod, .kicad_sym(dir), .kicad_sch and a folder with .fenolite/meta.json"
TREE_READS = "it reads .kicad_pcb, .kicad_mod, .kicad_sch, .kicad_sym and .kicad_wks; else use --view model"
DEFAULT_LIMIT = 200


@dataclass(frozen=True, slots=True)
class _Input:
    name: str
    kind: str
    content: Design | Library | SchematicSheet
    issues: tuple[Issue, ...]
    evidence: Evidence
    sha256: str | None


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'diff'."
    parser.add_argument(
        "a", metavar="A", help="a board, schematic, footprint file, symbol library or project"
    )
    parser.add_argument("b", metavar="B", help="the input to compare with A")
    parser.add_argument(
        "--view", choices=("model", "tree"), default="model", help="model entities (default) or file trees"
    )
    parser.add_argument("--ext", action="store_true", help="also compare the opaque content, as a hash")


def _path(given: str, ctx: Context) -> Path:
    path = Path(given)
    path = path if path.is_absolute() else ctx.cwd / path
    if not path.exists():
        raise CliError("FEN-3001", f"{path.name} does not exist", where=path.name)
    return path


def _digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _read(path: Path) -> _Input:
    if path.is_dir() and (path / ".fenolite" / "meta.json").is_file():
        design = load_dir(path / ".fenolite")
        return _Input(path.name, MODEL_KIND, design, (), MODEL_EVIDENCE, None)
    if path.is_file() and versions.kind_for_suffix(path.name) is versions.FileKind.SCHEMATIC:
        sheet_issues: list[Issue] = []
        sheet = sch.read_schematic(path, issues=sheet_issues)
        kind_name = versions.FileKind.SCHEMATIC.value
        return _Input(path.name, kind_name, sheet, tuple(sheet_issues), sch.EVIDENCE, _digest(path))
    backend = registry.for_path(path)
    if backend is None:
        raise CliError("FEN-2001", f"diff does not read {path.name}", hint=READS, where=path.name)
    found: list[Issue] = []
    read = backend.read(path, issues=found)
    kind = versions.kind_for_suffix(path.name)
    name = kind.value if kind is not None else versions.FileKind.SYMBOL_LIB.value
    return _Input(path.name, name, read.content, tuple(found), read.evidence, _digest(path))


def _model(a: _Input, b: _Input, *, ext: bool) -> DiffReport:
    if isinstance(a.content, Design) and isinstance(b.content, Design):
        return diff_designs(a.content, b.content, ext=ext)
    if isinstance(a.content, Library) and isinstance(b.content, Library):
        return diff_libraries(a.content, b.content, ext=ext)
    if isinstance(a.content, SchematicSheet) and isinstance(b.content, SchematicSheet):
        return diff_sheets(a.content, b.content, ext=ext)
    raise CliError(
        "FEN-2001",
        f"{a.name} ({a.kind}) and {b.name} ({b.kind}) are not of one family",
        hint="compare two boards or built models, two libraries, or two schematics",
    )


def _tree(path: Path) -> tuple[versions.FileKind, Node]:
    if path.is_dir():
        raise CliError(
            "FEN-2001",
            f"the tree view compares two KiCad files, and {path.name} is a folder",
            hint="use --view model for a built model",
            where=path.name,
        )
    kind = versions.kind_for_suffix(path.name)
    if kind not in TREE_KINDS:
        raise CliError(
            "FEN-2001",
            f"the tree view does not read {path.name}",
            hint=TREE_READS,
            where=path.name,
        )
    assert kind is not None
    return kind, parse_bytes(path.read_bytes(), file=path.name)


def _heads(root: Node) -> Counter[str]:
    return Counter(child.name for child in root.nodes())


def _tree_view(a: Path, b: Path) -> Result:
    kind_a, root_a = _tree(a)
    kind_b, root_b = _tree(b)
    if kind_a is not kind_b:
        raise CliError(
            "FEN-2001",
            f"{a.name} ({kind_a.value}) and {b.name} ({kind_b.value}) are not of one kind",
            hint="the tree view compares two files of one kind",
        )
    heads_a, heads_b = _heads(root_a), _heads(root_b)
    result: dict[str, Any] = {
        "view": "tree",
        "equal": tree_equal(root_a, root_b),
        "a": {"path": a.name, "kind": kind_a.value},
        "b": {"path": b.name, "kind": kind_b.value},
        "first_difference": first_difference(root_a, root_b),
        "heads": {
            head: {"a": heads_a[head], "b": heads_b[head]}
            for head in sorted(set(heads_a) | set(heads_b))
            if heads_a[head] != heads_b[head]
        },
        "summary": {},
        "differences": [],
        "total": 0,
        "truncated": False,
    }
    return Result(
        result=result,
        evidence=TREE_EVIDENCE,
        input=InputRef(path=a.name, sha256=_digest(a), kind=kind_a.value, format_version=None),
    )


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    path_a, path_b = _path(args.a, ctx), _path(args.b, ctx)
    if args.view == "tree":
        if args.ext:
            raise CliError("FEN-2001", "--ext belongs to the model view; the tree view compares every atom")
        return _tree_view(path_a, path_b)
    a, b = _read(path_a), _read(path_b)
    report = _model(a, b, ext=bool(args.ext))
    result: dict[str, Any] = {
        "view": "model",
        "equal": report.equal,
        "a": {"path": a.name, "kind": a.kind},
        "b": {"path": b.name, "kind": b.kind},
    }
    body = report.to_json(None)
    result.update({key: body[key] for key in ("summary", "differences", "total", "truncated")})
    return Result(
        result=result,
        issues=(*a.issues, *b.issues),
        evidence=Evidence.combine(a.evidence, b.evidence),
        input=InputRef(path=a.name, sha256=a.sha256, kind=a.kind, format_version=None),
    )


COMMAND = Command(
    name="diff",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    paged="differences",
    default_limit=DEFAULT_LIMIT,
    example_args=(EXAMPLE_BOARD, EXAMPLE_BOARD),
)

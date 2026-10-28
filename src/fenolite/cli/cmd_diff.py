# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite diff A B``: the differences between two boards, two libraries or two built models, and a
tree view of two KiCad files (capability cli-contract, "Diff command"; ``docs/cli-contract.md``, "diff").

A difference is a result, not a finding: the exit code is 0 either way and ``result.equal`` says it.

The inputs of a backend whose project is a set of documents are read too (change c0044; "Diff of document
inputs and the records view"): an Altium document, library, project file or project folder in the model
view, and two Altium files of one kind, record by record, in the records view.

Change c0207 (capability file-safety, "Gated differences", "Three-way difference of KiCad boards" and
"Resave differences of Altium documents"): ``--allow KINDS`` makes each change of another kind an error
finding (exit 5); ``--three-way THEIRS --out FILE`` plans ``THEIRS`` with the root items that changed from
``A`` to ``B`` applied, under the mutation protocol; and the records view leaves out the records that differ
only in the spelling of their values (``resave``).
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fenolite.backends import registry
from fenolite.backends.kicad import merge as kicad_merge
from fenolite.backends.kicad import sch, versions
from fenolite.backends.kicad.sexpr import Node, first_difference, parse_bytes, tree_equal
from fenolite.checks.diff import Change, DiffReport, diff_designs, diff_libraries, diff_sheets
from fenolite.checks.diffgate import ISSUE_CODES as DIFF_CODES
from fenolite.checks.diffgate import gate, parse_kinds
from fenolite.cli._documents import find_documents, validator_for
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.cmd_snapshot import shown
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.canonical import load_dir
from fenolite.model.design import Design
from fenolite.model.library import Library
from fenolite.model.schematic import SchematicSheet

HELP = (
    "list the differences between two boards, libraries, built models or Altium files, gate them by kind, "
    "or merge them into a third KiCad board (runs no tool)"
)
MODEL_KIND = "fenolite_model"
MODEL_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-MODEL-OWN",))
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
READS = (
    "diff reads .kicad_pcb, .kicad_mod, .kicad_sym(dir), .kicad_sch, a folder with .fenolite/meta.json, "
    "and the Altium files .PcbDoc, .SchDoc, .PcbLib, .SchLib and .PrjPcb (or a project folder)"
)
RECORDS_HINT = "the records view compares two Altium files of one kind; use --view model for these inputs"
TREE_READS = "it reads .kicad_pcb, .kicad_mod, .kicad_sch, .kicad_sym and .kicad_wks; else use --view model"
DEFAULT_LIMIT = 200
THREE_WAY_HINT = (
    "--three-way merges three KiCad boards (.kicad_pcb) in the model view; see docs/cli-contract.md"
)


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
        "a",
        metavar="A",
        help="a board, schematic, footprint file, symbol library, built project or Altium file",
    )
    parser.add_argument("b", metavar="B", help="the input to compare with A")
    parser.add_argument(
        "--view",
        choices=("model", "tree", "records"),
        default="model",
        help="model entities (default), the trees of two KiCad files, or the records of two Altium files",
    )
    parser.add_argument("--ext", action="store_true", help="also compare the opaque content, as a hash")
    parser.add_argument(
        "--allow",
        default=None,
        metavar="KINDS",
        help="comma-separated change kinds (track,via,...); a change of any other kind is an error (exit 5)",
    )
    parser.add_argument(
        "--three-way",
        default=None,
        metavar="THEIRS",
        help="a third KiCad board: write it with the changes from A to B applied (needs --out)",
    )
    parser.add_argument("--out", default=None, metavar="FILE", help="the merged board of --three-way")


def _path(given: str, ctx: Context) -> Path:
    path = Path(given)
    path = path if path.is_absolute() else ctx.cwd / path
    if not path.exists():
        raise CliError("FEN-3001", f"{path.name} does not exist", where=path.name)
    return path


def _digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _document_kind(path: Path) -> str | None:
    """The read kind of the file ``path`` when its backend reads document sets (an Altium file), else
    ``None``."""
    backend = validator_for(path) if path.is_file() else None
    return None if backend is None else backend.documents(path).named(path.name).kind


def _read(path: Path) -> _Input:
    if path.is_dir() and (path / ".fenolite" / "meta.json").is_file():
        design = load_dir(path / ".fenolite")
        return _Input(path.name, MODEL_KIND, design, (), MODEL_EVIDENCE, None)
    if path.is_file() and versions.kind_for_suffix(path.name) is versions.FileKind.SCHEMATIC:
        sheet_issues: list[Issue] = []
        sheet = sch.read_schematic(path, issues=sheet_issues)
        kind_name = versions.FileKind.SCHEMATIC.value
        return _Input(path.name, kind_name, sheet, tuple(sheet_issues), sch.EVIDENCE, _digest(path))
    if path.is_dir() and registry.for_path(path) is None:
        located = find_documents(path)
        if located is not None:  # a project folder is read through its project file
            path = located[1].root / str(located[1].project)
    backend = registry.for_path(path)
    if backend is None:
        raise CliError("FEN-2001", f"diff does not read {path.name}", hint=READS, where=path.name)
    found: list[Issue] = []
    read = backend.read(path, issues=found)
    name = _document_kind(path)
    if name is None:
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


def _records_view(a: Path, b: Path) -> Result:
    """The records of two Altium files of one read kind, stream by stream (capability altium-verification,
    "Records view of two Altium files")."""
    kind_a, kind_b = _document_kind(a), _document_kind(b)
    if kind_a is None or kind_b is None:
        refused = a if kind_a is None else b
        raise CliError(
            "FEN-2001",
            f"the records view does not read {refused.name}",
            hint=RECORDS_HINT,
            where=refused.name,
        )
    # Lazy: only this view needs the record codecs of the Altium readers.
    from fenolite.backends.altium.roundtrip import CODECS, READER_EVIDENCE, diff_records

    if kind_a != kind_b or kind_a not in CODECS:
        raise CliError(
            "FEN-2001",
            f"{a.name} ({kind_a}) and {b.name} ({kind_b}) are not of one kind",
            hint=RECORDS_HINT,
        )
    from fenolite.backends.altium.resave import EVIDENCE as RESAVE_EVIDENCE

    resave: list[Change] = []
    report = diff_records(a.read_bytes(), b.read_bytes(), kind=kind_a, resave=resave)
    result: dict[str, Any] = {
        "view": "records",
        "equal": report.equal,
        "a": {"path": a.name, "kind": kind_a},
        "b": {"path": b.name, "kind": kind_b},
    }
    body = report.to_json(None)
    result.update({key: body[key] for key in ("summary", "differences", "total", "truncated")})
    streams: dict[str, int] = {}
    for change in resave:
        stream = change.path[1:].rpartition("#")[0]
        streams[stream] = streams.get(stream, 0) + 1
    result["resave"] = {"total": len(resave), "streams": dict(sorted(streams.items()))}
    return Result(
        result=result,
        evidence=Evidence.combine(READER_EVIDENCE[kind_a], RESAVE_EVIDENCE)
        if resave
        else READER_EVIDENCE[kind_a],
        input=InputRef(path=a.name, sha256=_digest(a), kind=kind_a, format_version=None),
    )


@dataclass(frozen=True, slots=True)
class _Merged:
    """What ``--three-way`` adds to a result: the ``merge`` object, findings, a write and the inputs."""

    result: dict[str, Any]
    issues: tuple[Issue, ...]
    writes: tuple[PlannedWrite, ...]
    depends: tuple[str, ...]


def _merge_issues(merged: kicad_merge.Merge, names: tuple[str, str, str]) -> list[Issue]:
    base, ours, theirs = names
    issues: list[Issue] = []
    if merged.refused is not None:
        issues.append(
            Issue(
                "diff.unmergeable",
                DIFF_CODES["diff.unmergeable"],
                f"{base}, {ours} and {theirs} cannot be merged: {merged.refused}",
                where=theirs,
                hint="re-save the three boards with one KiCad version, then merge again",
            )
        )
    issues += [
        Issue(
            "diff.conflict",
            DIFF_CODES["diff.conflict"],
            f"{item.key}: {item.change} from {base} to {ours}, and changed in {theirs}",
            where=item.key,
            hint="merge this item by hand in KiCad, or undo it on one side, then merge again",
        )
        for item in merged.conflicts
    ]
    return issues


def _three_way(path_a: Path, path_b: Path, args: argparse.Namespace, ctx: Context) -> _Merged:
    """The merge of ``--three-way`` into ``--out``."""
    if args.out is None:
        raise CliError("FEN-2001", "--three-way needs --out FILE", where="--out", hint=THREE_WAY_HINT)
    theirs = _path(args.three_way, ctx)
    out = Path(args.out) if Path(args.out).is_absolute() else ctx.cwd / args.out
    for path in (path_a, path_b, theirs, out):
        if path.is_dir() or versions.kind_for_suffix(path.name) is not versions.FileKind.BOARD:
            raise CliError(
                "FEN-2001", f"--three-way does not merge {path.name}", where=path.name, hint=THREE_WAY_HINT
            )
    merged = kicad_merge.three_way(path_a.read_bytes(), path_b.read_bytes(), theirs.read_bytes())
    result: dict[str, Any] = {
        "theirs": theirs.name,
        "out": shown(out, ctx.cwd),
        "items": [{"key": i.key, "change": i.change, "status": i.status} for i in merged.items],
        "applied": sum(1 for i in merged.items if i.status == "applied"),
        "already": sum(1 for i in merged.items if i.status == "already"),
        "conflicts": len(merged.conflicts),
        "refused": merged.refused,
    }
    writes: tuple[PlannedWrite, ...] = ()
    if merged.data is not None:
        writes = (PlannedWrite(shown(out, ctx.cwd), merged.data, versions.FileKind.BOARD.value),)
    inputs = [path for path in (path_a, path_b, theirs) if path.resolve() != out.resolve()]
    issues = _merge_issues(merged, (path_a.name, path_b.name, theirs.name))
    return _Merged(result, tuple(issues), writes, depends_on(ctx.cwd, *inputs))


def _allowed(args: argparse.Namespace) -> frozenset[str] | None:
    if args.view != "model":
        for flag, value in (("--allow", args.allow), ("--three-way", args.three_way)):
            if value is not None:
                raise CliError("FEN-2001", f"{flag} belongs to the model view", where=flag)
    if args.out is not None and args.three_way is None:
        raise CliError("FEN-2001", "--out names the merged board of --three-way", where="--out")
    if args.allow is None:
        return None
    try:
        return parse_kinds(args.allow)
    except ValueError as exc:
        raise CliError(
            "FEN-2001",
            f"--allow: {exc}",
            where="--allow",
            hint="the kinds are the keys of result.summary: track, via, footprint, rule, ...",
        ) from exc


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    path_a, path_b = _path(args.a, ctx), _path(args.b, ctx)
    allowed = _allowed(args)
    if args.view == "records":
        if args.ext:
            raise CliError("FEN-2001", "--ext belongs to the model view; the records view compares every key")
        return _records_view(path_a, path_b)
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
    issues: list[Issue] = [*a.issues, *b.issues]
    evidence = Evidence.combine(a.evidence, b.evidence)
    if allowed is not None:
        issues += gate(report, allowed)
        result["allow"] = sorted(allowed)
    merged = _Merged({}, (), (), ())
    if args.three_way is not None:
        merged = _three_way(path_a, path_b, args, ctx)
        result["merge"] = merged.result
        issues += merged.issues
        evidence = Evidence.combine(evidence, kicad_merge.EVIDENCE)
    return Result(
        result=result,
        issues=tuple(issues),
        evidence=evidence,
        input=InputRef(path=a.name, sha256=a.sha256, kind=a.kind, format_version=None),
        writes=merged.writes,
        depends=merged.depends,
    )


COMMAND = Command(
    name="diff",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    paged="differences",
    default_limit=DEFAULT_LIMIT,
    example_args=(EXAMPLE_BOARD, EXAMPLE_BOARD),
    mutation_example_args=(
        EXAMPLE_BOARD,
        EXAMPLE_BOARD,
        "--three-way",
        EXAMPLE_BOARD,
        "--out",
        "merged.kicad_pcb",
    ),
)

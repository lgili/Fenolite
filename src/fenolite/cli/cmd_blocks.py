# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite blocks VERB``: the catalog of block records (``docs/blocks.md``; ``docs/cli-contract.md``,
"blocks"; change c0268).

- ``list [--from FILE.py]... [--category C]``: one row per block, sorted by id and then by source;
- ``show ID [--from FILE.py]...``: the ``fenolite.block.v0`` record of one block;
- ``doc ID [--from FILE.py]... (--text | --out DIR)``: its generated Markdown page, printed, or planned as
  ``DIR/<namespace>/<name>.md`` and written under ``--confirm``;
- ``where ID [PATH]...``: every design lock below the paths whose ``[blocks]`` section uses the block.

Only ``doc --out`` writes. No verb opens a network connection or runs a tool; ``--from`` imports the
file, which runs its code. ``where`` imports nothing and runs no script.
"""

from __future__ import annotations

import argparse
import difflib
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.blocksrc import CatalogEntry, duplicate_issues, find_blocks
from fenolite.cli.errors import CliError
from fenolite.core.errors import FormatError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.dsl.lock import SUFFIX, read_lock
from fenolite.dsl.record import CATEGORIES, page, record_data, replacement_problems

HELP = "list, show, document and find the uses of block records (list, show, doc, where)"
VERBS: tuple[str, ...] = ("list", "show", "doc", "where")
"""The verbs of ``fenolite blocks`` (c0270 adds ``test``, c0271 ``capture``, c0273 ``upgrade``)."""
DOC_KIND = "block-doc"
ISSUE_CODES: dict[str, Severity] = {
    "blocks.duplicate-id": "error",
    "blocks.lock-unreadable": "warning",
}
"""The issue codes of ``fenolite blocks``."""
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-BLOCK-RECORDS",))
"""Records, digests and the catalog are Fenolite's own; a block's evidence label is its author's statement
and is never raised by the catalog."""


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'blocks'."
    parser.add_argument("verb", choices=VERBS, metavar="VERB", help="list, show, doc or where")
    parser.add_argument(
        "target",
        nargs="*",
        metavar="ID",
        help="the block id (show, doc, where); for where, then the folders to search (default .)",
    )
    parser.add_argument(
        "--from",
        dest="files",
        action="append",
        default=[],
        metavar="FILE.py",
        help="also list the blocks of this Python file; importing it runs its code (repeatable)",
    )
    parser.add_argument("--category", choices=CATEGORIES, help="list: only the blocks of this category")
    parser.add_argument("--out", metavar="DIR", help="doc: write the page under DIR/<namespace>/<name>.md")


def _catalog(args: argparse.Namespace, ctx: Context) -> tuple[CatalogEntry, ...]:
    try:
        return find_blocks(files=list(args.files), cwd=ctx.cwd)
    except FormatError as error:
        raise CliError(
            "FEN-3004", str(error), where=error.file, hint="fix the block module and run again"
        ) from error


def _row(entry: CatalogEntry) -> dict[str, Any]:
    header = entry.definition.header
    return {
        "id": entry.id,
        "version": header.version if header is not None else None,
        "summary": header.summary if header is not None else "",
        "category": header.category if header is not None else "other",
        "licence": header.licence if header is not None else None,
        "evidence": header.evidence if header is not None else None,
        "source": entry.source,
        "where": entry.where,
        "deprecated": header is not None and header.deprecated is not None,
        "digest": record_data(entry.record)["digests"]["record"],  # type: ignore[index]
    }


def _list(args: argparse.Namespace, ctx: Context) -> Result:
    entries = _catalog(args, ctx)
    rows = [_row(entry) for entry in entries]
    if args.category is not None:
        rows = [row for row in rows if row["category"] == args.category]
    return Result(
        result={"blocks": rows},
        issues=tuple(duplicate_issues(entries)),
        evidence=EVIDENCE,
        depends=depends_on(ctx.cwd, *args.files),
    )


def _one_id(args: argparse.Namespace) -> str:
    if len(args.target) != 1:
        raise CliError(
            "FEN-2001",
            f"blocks {args.verb} takes one block id",
            where="ID",
            hint=f"fenolite blocks {args.verb} Acme:divider",
        )
    return str(args.target[0])


def _chosen(args: argparse.Namespace, ctx: Context) -> tuple[CatalogEntry, tuple[CatalogEntry, ...]]:
    """The entry of the id of ``args`` and the whole catalog; FEN-2001 for an unknown id, FEN-3004 for a
    duplicate id, a block that cannot be elaborated or a replacement without deprecation."""
    wanted = _one_id(args)
    entries = _catalog(args, ctx)
    found = [entry for entry in entries if entry.id == wanted]
    if not found:
        close = difflib.get_close_matches(wanted, sorted({e.id for e in entries}), n=5, cutoff=0.0)
        raise CliError(
            "FEN-2001",
            f"no block has the id {wanted}",
            where=wanted,
            hint=f"the closest ids are: {', '.join(close)}"
            if close
            else "fenolite blocks list shows the ids",
        )
    if len(found) > 1:
        sources = " and ".join(f"{e.source} {e.where}" for e in found)
        raise CliError("FEN-3004", f"the block id {wanted} is held by {sources}", where=wanted)
    entry = found[0]
    error = (entry.record.elaboration or {}).get("error")
    if error is not None:
        raise CliError("FEN-3004", f"the block {wanted} cannot be elaborated: {error}", where=wanted)
    problems = replacement_problems(entry.definition.header, {e.id: e.definition.header for e in entries})
    if problems:
        raise CliError(
            "FEN-3004",
            problems[0],
            where=wanted,
            hint="add deprecated={'by': ..., 'since': ..., 'reason': ...} to the replaced block",
        )
    return entry, entries


def _show(args: argparse.Namespace, ctx: Context) -> Result:
    entry, _ = _chosen(args, ctx)
    block = {**record_data(entry.record), "source": entry.source, "where": entry.where}
    return Result(result={"block": block}, evidence=EVIDENCE, depends=depends_on(ctx.cwd, *args.files))


def _doc(args: argparse.Namespace, ctx: Context) -> Result:
    entry, _ = _chosen(args, ctx)
    text = page(entry.record)
    result: dict[str, Any] = {"id": entry.id, "source": entry.source}
    writes: tuple[PlannedWrite, ...] = ()
    if args.out is not None:
        out = Path(args.out)
        if out.is_absolute() or ".." in out.parts:
            raise CliError("FEN-2001", "--out is a folder relative to the working directory", where="--out")
        namespace, _, name = entry.id.rpartition(":")
        target = (out / (namespace or "project") / f"{name}.md").as_posix()
        result["page"] = target
        writes = (PlannedWrite(target, text.encode("utf-8"), DOC_KIND),)
    else:
        result["text"] = text
    return Result(
        result=result,
        evidence=EVIDENCE,
        writes=writes,
        text=text if args.out is None else None,
        depends=depends_on(ctx.cwd, *args.files),
    )


def _locks(roots: Sequence[Path]) -> list[Path]:
    found: set[Path] = set()
    for root in roots:
        if root.is_file() and root.suffix == SUFFIX:
            found.add(root)
            continue
        for folder, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__pycache__")
            found.update(Path(folder) / name for name in files if name.endswith(SUFFIX))
    return sorted(found)


def _relative(path: Path, cwd: Path) -> str:
    try:
        return path.resolve().relative_to(cwd.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _where(args: argparse.Namespace, ctx: Context) -> Result:
    if not args.target:
        raise CliError(
            "FEN-2001",
            "blocks where takes a block id",
            where="ID",
            hint="fenolite blocks where Acme:divider .",
        )
    if args.files or args.category or args.out:
        raise CliError("FEN-2001", "blocks where reads locks only; it takes no --from, --category or --out")
    wanted, *given = (str(item) for item in args.target)
    roots = [Path(item) if Path(item).is_absolute() else ctx.cwd / item for item in (given or ["."])]
    for root, text in zip(roots, given or ["."], strict=True):
        if not root.exists():
            raise CliError("FEN-3001", f"{text} does not exist", where=text)
    uses: list[dict[str, str]] = []
    issues: list[Issue] = []
    for path in _locks(roots):
        shown = _relative(path, ctx.cwd)
        try:
            lock = read_lock(path.read_text(encoding="utf-8"), file=shown)
        except (FormatError, UnicodeDecodeError, OSError) as error:
            issues.append(
                Issue(
                    "blocks.lock-unreadable",
                    "warning",
                    f"{shown} is no design lock this version reads, so it was skipped: {error}",
                    where=shown,
                )
            )
            continue
        for instance, value in lock.sections["blocks"].items():
            block_id, _, version = str(value).rpartition("@")
            if block_id == wanted:
                uses.append({"lock": shown, "design": lock.design, "instance": instance, "version": version})
    uses.sort(key=lambda use: (use["lock"], use["instance"]))
    return Result(result={"id": wanted, "uses": uses}, issues=tuple(issues), evidence=EVIDENCE)


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    verb = str(args.verb)
    if verb != "doc" and args.out is not None:
        raise CliError("FEN-2001", "--out belongs to blocks doc", where="--out")
    if verb != "list" and args.category is not None:
        raise CliError("FEN-2001", "--category belongs to blocks list", where="--category")
    if verb == "list":
        if args.target:
            raise CliError("FEN-2001", "blocks list takes no id; use blocks show ID", where="ID")
        return _list(args, ctx)
    if verb == "show":
        return _show(args, ctx)
    if verb == "doc":
        return _doc(args, ctx)
    return _where(args, ctx)


COMMAND = Command(
    name="blocks",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    paged="blocks|uses",
    example_args=("list",),
    mutation_example_args=("doc", "Acme:divider", "--from", "divider.py", "--out", "docs"),
    discovery=(("verbs", tuple(f"blocks {verb}" for verb in VERBS)),),
)

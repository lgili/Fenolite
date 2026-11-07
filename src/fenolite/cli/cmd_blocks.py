# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite blocks VERB``: the catalog of block records (``docs/blocks.md``; ``docs/cli-contract.md``,
"blocks"; change c0268).

- ``list [--from FILE.py]... [--category C]``: one row per block, sorted by id and then by source;
- ``show ID [--from FILE.py]...``: the ``fenolite.block.v0`` record of one block;
- ``doc ID [--from FILE.py]... (--text | --out DIR)``: its generated Markdown page, printed, or planned as
  ``DIR/<namespace>/<name>.md`` and written under ``--confirm``;
- ``where ID [PATH]...``: every design lock below the paths whose ``[blocks]`` section uses the block;
- ``test [ID...]``: tool-free usage builds, circuit/rules goldens and plain test functions;
- ``capture BOARD --instance PATH [-o FILE]``: a checked block-local layout asset.

``doc --out``, ``test --golden`` and ``capture`` write under the mutation protocol.
No verb opens a network connection or runs a tool; ``--from`` imports the file, which runs its code.
``where`` imports nothing and runs no script.

``index`` and ``upgrade`` add reviewed record-file and lock writes (c0273). Discovery of vendored
records imports no item code; ``index`` and ``upgrade`` explicitly execute the package or design.
No verb opens a network connection. ``where`` imports nothing and runs no script.
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fenolite.cli._blocks_index import register_index, run_index
from fenolite.cli._blocks_upgrade import register_upgrade, run_upgrade
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.blocksrc import CatalogEntry, duplicate_issues, find_blocks
from fenolite.cli.blockvendored import ISSUE_CODES as VENDORED_CODES
from fenolite.cli.errors import CliError
from fenolite.core.errors import FormatError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.dsl.lock import SUFFIX, read_lock
from fenolite.dsl.record import CATEGORIES, page, record_data, replacement_problems

HELP = "inspect and test blocks, capture layouts, index packages and review upgrades"
VERBS: tuple[str, ...] = ("list", "show", "doc", "where", "test", "capture", "index", "upgrade")
"""The verbs of ``fenolite blocks`` (c0270 adds ``test``, c0271 ``capture``, c0273 ``upgrade``)."""
DOC_KIND = "block-doc"
ISSUE_CODES: dict[str, Severity | tuple[Severity, ...]] = {
    "blocks.duplicate-id": "error",
    "blocks.lock-unreadable": "warning",
    "blocks.capture-unplaced": "error",
    "blocks.capture-check-failed": "error",
    "blocks.capture-escape": "warning",
    "blocks.capture-copper-left": "info",
    **VENDORED_CODES,
    "blocks.index-stale": ("error", "warning"),
}
"""The issue codes of ``fenolite blocks``."""
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-BLOCK-RECORDS",))
"""Records, digests and the catalog are Fenolite's own; a block's evidence label is its author's statement
and is never raised by the catalog."""


def _register(parser: argparse.ArgumentParser) -> None:
    from fenolite.cli._blocks_capture import register_capture
    from fenolite.cli._blocks_test import register_test

    register_capture(parser)
    parser.description = HELP + "; see docs/cli-contract.md, 'blocks'."
    parser.add_argument(
        "verb", choices=VERBS, metavar="VERB", help="catalog, test, capture, index or upgrade verb"
    )
    parser.add_argument(
        "target",
        nargs="*",
        metavar="ID",
        help="the block id (show, doc, where) or board folder (capture); where also takes search folders",
    )
    parser.add_argument(
        "--from",
        dest="files",
        action="append",
        default=[],
        metavar="FILE.py",
        help="also list the blocks of this Python file; importing it runs its code (repeatable)",
    )
    parser.add_argument("--category", choices=CATEGORIES, help="list/test: only the blocks of this category")
    parser.add_argument(
        "--out", metavar="PATH", help="doc: page folder; index: record file; upgrade: previous build folder"
    )
    register_test(parser)
    register_index(parser)
    register_upgrade(parser)
    parser.add_argument(
        "--script",
        metavar="FILE",
        help="list/show/doc/test: find vendored blocks beside FILE (default design.py)",
    )


def _catalog(
    args: argparse.Namespace, ctx: Context, *, issues: list[Issue] | None = None
) -> tuple[CatalogEntry, ...]:
    try:
        script = Path(args.script) if args.script else Path("design.py")
        path = script if script.is_absolute() else ctx.cwd / script
        folder = path.parent if args.script or path.is_file() else None
        return find_blocks(files=list(args.files), cwd=ctx.cwd, script_dir=folder, issues=issues)
    except FormatError as error:
        raise CliError(
            "FEN-3004", str(error), where=error.file, hint="fix the block module and run again"
        ) from error


def _row(entry: CatalogEntry) -> dict[str, Any]:
    header = entry.record.header
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
    issues: list[Issue] = []
    entries = _catalog(args, ctx, issues=issues)
    rows = [_row(entry) for entry in entries]
    if args.category is not None:
        rows = [row for row in rows if row["category"] == args.category]
    return Result(
        result={"blocks": rows},
        issues=(*issues, *duplicate_issues(entries)),
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


def _chosen(
    args: argparse.Namespace, ctx: Context, *, issues: list[Issue] | None = None
) -> tuple[CatalogEntry, tuple[CatalogEntry, ...]]:
    """The entry of the id of ``args`` and the whole catalog; FEN-2001 for an unknown id, FEN-3004 for a
    duplicate id, a block that cannot be elaborated or a replacement without deprecation."""
    wanted = _one_id(args)
    entries = _catalog(args, ctx, issues=issues)
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
    problems = replacement_problems(entry.record.header, {e.id: e.record.header for e in entries})
    if problems:
        raise CliError(
            "FEN-3004",
            problems[0],
            where=wanted,
            hint="add deprecated={'by': ..., 'since': ..., 'reason': ...} to the replaced block",
        )
    return entry, entries


def _show(args: argparse.Namespace, ctx: Context) -> Result:
    from fenolite.testing.blocks import convention_of_entry

    issues: list[Issue] = []
    entry, entries = _chosen(args, ctx, issues=issues)
    block = {
        **record_data(entry.record),
        "source": entry.source,
        "where": entry.where,
        "layout": entry.record.layout,
        **convention_of_entry(entry).paths(),
    }
    return Result(
        result={"block": block},
        issues=tuple(issues),
        evidence=EVIDENCE,
        depends=_catalog_inputs(ctx, args, entries),
    )


def _doc(args: argparse.Namespace, ctx: Context) -> Result:
    issues: list[Issue] = []
    entry, entries = _chosen(args, ctx, issues=issues)
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
        issues=tuple(issues),
        evidence=EVIDENCE,
        writes=writes,
        text=text if args.out is None else None,
        depends=_catalog_inputs(ctx, args, entries),
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


def _catalog_inputs(
    ctx: Context, args: argparse.Namespace, entries: Sequence[CatalogEntry]
) -> tuple[str, ...]:
    return depends_on(
        ctx.cwd,
        *args.files,
        *(
            entry.item_root / name
            for entry in entries
            if entry.item_root is not None
            for name in ("block.json", "item.json")
        ),
    )


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
    if verb != "test" and (args.golden or args.only):
        raise CliError("FEN-2001", "--golden and --only belong to blocks test")
    if verb != "capture" and any(
        value is not None
        for value in (args.instance, args.capture_output, args.origin, args.anchor, args.capture_copper)
    ):
        raise CliError("FEN-2001", "--instance, -o, --origin, --anchor and --copper belong to blocks capture")
    if args.script and verb not in ("list", "show", "doc", "test"):
        raise CliError("FEN-2001", "--script belongs to blocks list, show, doc and test", where="--script")
    if verb != "upgrade" and (args.upgrade_blocks or args.allow_major):
        raise CliError("FEN-2001", "--block and --allow-major belong to blocks upgrade")
    if verb != "index" and args.index_check:
        raise CliError("FEN-2001", "--check belongs to blocks index", where="--check")
    if verb == "capture":
        from fenolite.cli._blocks_capture import run_capture

        return run_capture(args, ctx)
    if verb == "upgrade":
        if args.files or args.category or args.index_check:
            raise CliError("FEN-2001", "blocks upgrade takes no --from, --category or --check")
        return run_upgrade(args, ctx)
    if verb == "index":
        if args.files or args.category:
            raise CliError("FEN-2001", "blocks index takes no --from or --category")
        return run_index(args, ctx)
    if verb != "doc" and args.out is not None:
        raise CliError("FEN-2001", "--out belongs to blocks doc", where="--out")
    if verb not in ("list", "test") and args.category is not None:
        raise CliError("FEN-2001", "--category belongs to blocks list or test", where="--category")
    if verb == "test":
        from fenolite.cli._blocks_test import run_test

        issues: list[Issue] = []
        entries = _catalog(args, ctx, issues=issues)
        if any(found.severity == "error" for found in issues):
            return Result(result={"blocks": []}, issues=tuple(issues), evidence=EVIDENCE)
        tested = run_test(args, ctx, entries)
        return dataclasses.replace(tested, issues=(*issues, *tested.issues))
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

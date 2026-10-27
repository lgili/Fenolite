# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite refs PATH [--repoint OLD=NEW]``: the paths a project's documents hold, and their rewrite
(capability file-safety, "Project references"; ``docs/file-safety.md``; ``docs/cli-contract.md``, "refs").

Without ``--repoint`` the command lists every path with its document and plans no write. With it, the
paths that start with ``OLD`` are rewritten to start with ``NEW`` in the KiCad documents, under the
mutation protocol; an Altium project file that holds such a path is reported, not touched.
"""

from __future__ import annotations

import argparse
import dataclasses
from pathlib import Path

from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.cmd_snapshot import refuse_online, shown
from fenolite.cli.errors import CliError
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.safety import files as safety_files
from fenolite.safety.codes import ISSUE_CODES as SAFETY_CODES
from fenolite.safety.refs import project_refs, repoint

HELP = "list the paths a project's documents hold, and rewrite them with --repoint OLD=NEW"
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-PROJECT-REFS",))


def _register(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "path", metavar="PATH", help="a design file (with its companions) or a project folder"
    )
    parser.add_argument(
        "--repoint",
        default=None,
        metavar="OLD=NEW",
        help="rewrite the paths that start with OLD to start with NEW (KiCad documents only)",
    )


def _issue(code: str, message: str, where: str, hint: str = "") -> Issue:
    return Issue(code, SAFETY_CODES[code], message, where=where, hint=hint)


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    given = Path(args.path)
    source = given if given.is_absolute() else ctx.cwd / given
    if not source.exists():
        raise CliError("FEN-3001", f"{args.path} does not exist", where=source.name)
    old = new = None
    if args.repoint is not None:
        old, eq, new = args.repoint.partition("=")
        if not eq or not old:
            raise CliError(
                "FEN-2001",
                f"--repoint: {args.repoint!r} is not OLD=NEW",
                where="--repoint",
                hint="--repoint C:/old=D:/new",
            )
    root = safety_files.project_root(source)
    files = safety_files.companions(source)
    refuse_online(root, files)
    refs = project_refs(root, files)
    issues: list[Issue] = []
    for ref in refs:
        where = f"{ref.document}: {ref.value}"
        if ref.resolved is None:
            issues.append(
                _issue("refs.unresolved", f"{ref.document} names {ref.value}, through a variable", where)
            )
        elif ref.outside:
            issues.append(
                _issue(
                    "refs.outside",
                    f"{ref.document} names {ref.value}, outside the project folder",
                    where,
                    hint="a copy of the project still depends on that folder; --repoint can move the path",
                )
            )
        elif not ref.exists:
            issues.append(
                _issue("refs.missing", f"{ref.document} names {ref.value}, which does not exist", where)
            )
    writes: list[PlannedWrite] = []
    rewritten: list[str] = []
    if old is not None and new is not None:
        changed, kept = repoint(root, files, old, new)
        for name in kept:
            issues.append(
                _issue(
                    "refs.not-writable",
                    f"{name} holds paths that start with {old}, and Fenolite does not rewrite this document",
                    name,
                    hint="change those paths in the tool that owns the document",
                )
            )
        for name, data in sorted(changed.items()):
            rewritten.append(name)
            writes.append(PlannedWrite(shown(root / name, ctx.cwd), data, "project_refs"))
    result: dict[str, object] = {
        "root": shown(root, ctx.cwd),
        "refs": [dataclasses.asdict(ref) for ref in refs],
        "count": len(refs),
        "rewritten": rewritten,
    }
    if old is not None:
        result["repoint"] = {"old": old, "new": new}
    return Result(result=result, issues=tuple(issues), writes=tuple(writes), evidence=EVIDENCE)


COMMAND = Command(
    name="refs",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_BOARD,),
    mutation_example_args=(EXAMPLE_BOARD, "--repoint", "/fenolite-example-old=/fenolite-example-new"),
)

__all__ = ["COMMAND"]

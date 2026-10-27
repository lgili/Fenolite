# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite snapshot PATH --out DIR``: a copy of a project that no save interrupted (capability
file-safety, "Stable snapshot"; ``docs/file-safety.md``; ``docs/cli-contract.md``, "snapshot").

The command copies a design file with its companion files (``safety.files.companions``), or every project
file of a folder, and accepts the copy only when every file has the same SHA-256 before and after all were
read. ``DIR/snapshot.json`` lists the files and their hashes: it is the receipt that ``fenolite publish``
checks before it puts an edited copy back.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.safety import files as safety_files
from fenolite.safety.codes import ISSUE_CODES as SAFETY_CODES
from fenolite.safety.placeholders import online_only

HELP = "copy a project that no save interrupted, with the hashes of its files (snapshot.json)"
SCHEMA = "fenolite.snapshot.v0"
MANIFEST = "snapshot.json"
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-SNAPSHOT-STABLE",))
HOOK: safety_files.ReadHook | None = None
"""Called after each read (a test seam: the suites save a file during the copy)."""


def _register(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "path", metavar="PATH", help="a design file (with its companions) or a project folder"
    )
    parser.add_argument("--out", required=True, metavar="DIR", help="the folder of the copy")


def shown(path: Path, cwd: Path) -> str:
    """``path`` relative to ``cwd`` in POSIX form when it lies inside it, else absolute."""
    full = Path(os.path.abspath(path))
    try:
        return full.relative_to(Path(os.path.abspath(cwd))).as_posix()
    except ValueError:
        return full.as_posix()


def refuse_online(root: Path, files: list[Path] | tuple[Path, ...]) -> None:
    """``FEN-3007`` when a sync client keeps one of ``files`` (relative to ``root``) only online."""
    online = online_only([root / rel for rel in files])
    if online:
        names = ", ".join(path.relative_to(root).as_posix() for path in online[:5])
        more = f" and {len(online) - 5} more" if len(online) > 5 else ""
        raise CliError("FEN-3007", f"kept only online: {names}{more}", where=names.split(", ")[0])


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    given = Path(args.path)
    source = given if given.is_absolute() else ctx.cwd / given
    if not source.exists():
        raise CliError("FEN-3001", f"{args.path} does not exist", where=source.name)
    out = Path(args.out) if Path(args.out).is_absolute() else ctx.cwd / args.out
    root = safety_files.project_root(source)
    if Path(os.path.abspath(out)).is_relative_to(Path(os.path.abspath(root))):
        raise CliError(
            "FEN-2001",
            f"--out {args.out} lies inside the project folder, so a later snapshot would copy the copy",
            where="--out",
            hint="name a folder beside the project",
        )
    files = safety_files.companions(source)
    refuse_online(root, files)
    read = safety_files.read_stable(root, files, hook=HOOK)
    rows = [{"path": item.path, "sha256": item.sha256, "size": len(item.data)} for item in read.files]
    result: dict[str, object] = {
        "source": shown(root, ctx.cwd),
        "out": shown(out, ctx.cwd),
        "files": rows,
        "count": len(rows),
        "retries": read.retries,
    }
    if read.unstable:
        issue = Issue(
            "safety.unstable",
            SAFETY_CODES["safety.unstable"],
            f"{', '.join(read.unstable)} changed during each of {safety_files.RETRIES + 1} reads; "
            "nothing is copied",
            where=read.unstable[0],
            hint="close the tool that keeps saving the file, or wait until it is done, and run again",
        )
        return Result(result=result, issues=(issue,), evidence=EVIDENCE)
    manifest = {"schema": SCHEMA, "source": shown(root, ctx.cwd), "files": rows}
    writes = [
        PlannedWrite(shown(out / item.path, ctx.cwd), item.data, "snapshot_file") for item in read.files
    ]
    data = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    writes.append(PlannedWrite(shown(out / MANIFEST, ctx.cwd), data, "snapshot_manifest"))
    return Result(result=result, writes=tuple(writes), evidence=EVIDENCE)


COMMAND = Command(
    name="snapshot",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_BOARD, "--out", "snapshot-example", "--dry-run"),
    mutation_example_args=(EXAMPLE_BOARD, "--out", "snapshot-example"),
)

__all__ = ["COMMAND", "HOOK", "MANIFEST", "SCHEMA", "refuse_online", "shown"]

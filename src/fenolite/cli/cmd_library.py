# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite library BOARD --out LIB.pretty [--diff LIBRARY]``: a footprint library made from a KiCad
board, or how a library differs from the board's footprints (capability design-conversion, "Library made
from a board" and "Library command result"; ``docs/cli-contract.md``, "library"; change c0223).

The footprints come from ``fenolite.library``; this module reads the board, plans one ``.kicad_mod`` file
per footprint under ``--out``, or with ``--diff`` writes nothing and reports the drift.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

from fenolite.backends.kicad.pcb import read_board, source_info
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.library import EVIDENCE, derive_library, drift, drift_issues

HELP = "write a footprint library made from a KiCad board, or report how a library differs from it"
PRETTY = ".pretty"
WRITE_KIND = "kicad_mod"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'library'."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, .kicad_pro or project folder")
    parser.add_argument("--out", metavar="LIB.pretty", help="the library folder to write, relative")
    parser.add_argument(
        "--diff", metavar="LIBRARY", help="a .pretty folder to compare with the board; writes nothing"
    )


def _relative(path: Path, cwd: Path) -> str:
    try:
        return Path(os.path.relpath(path, cwd)).as_posix()
    except ValueError:  # another Windows drive
        return path.as_posix()


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if args.out is None and args.diff is None:
        raise CliError("FEN-2001", "library needs --out or --diff", hint="pass --out lib.pretty")
    if args.out is not None and (Path(args.out).is_absolute() or not args.out.endswith(PRETTY)):
        raise CliError(
            "FEN-2001", "--out must be a relative .pretty folder", where="--out", hint="pass --out lib.pretty"
        )
    board_path = resolve_board(Path(args.path) if Path(args.path).is_absolute() else ctx.cwd / args.path)
    data = board_path.read_bytes()
    text = data.decode("utf-8")
    source = source_info(read_board(text, file=board_path.name))
    major = source.major if source is not None and source.major is not None else ctx.kicad_target
    library_name = Path(args.out).name.removesuffix(PRETTY) if args.out else board_path.stem
    derived = derive_library(text, library=library_name, target=major, file=board_path.name)
    issues = list(derived.issues)
    result: dict[str, object] = {"board": board_path.name}
    writes: tuple[PlannedWrite, ...] = ()
    depends = [board_path]
    if args.diff is not None:
        folder = Path(args.diff) if Path(args.diff).is_absolute() else ctx.cwd / args.diff
        if not folder.is_dir():
            raise CliError("FEN-3001", f"--diff: {args.diff} is not a folder", where="--diff")
        rows = drift(derived, folder)
        issues.extend(drift_issues(rows))
        result["library"] = _relative(folder, ctx.cwd)
        result["drift"] = [{"name": name, "kinds": list(kinds)} for name, kinds in rows]
        depends.extend(sorted(folder.glob("*.kicad_mod")))
    else:
        out = Path(str(args.out)).as_posix()
        result["library"] = out
        result["footprints"] = [
            {"name": fp.name, "source": fp.source, "refs": list(fp.refs)} for fp in derived.footprints
        ]
        writes = tuple(
            PlannedWrite(f"{out}/{name}", body.encode("utf-8"), WRITE_KIND)
            for name, body in sorted(derived.files().items())
        )
    return Result(
        result=result,
        issues=tuple(issues),
        evidence=EVIDENCE,
        input=InputRef(
            board_path.name,
            hashlib.sha256(data).hexdigest(),
            "kicad_pcb",
            str(source.version) if source is not None else None,
        ),
        writes=writes,
        depends=depends_on(ctx.cwd, *depends),
    )


_EXAMPLE = (EXAMPLE_BOARD, "--out", "fenolite-lib.pretty")
COMMAND = Command(
    name="library",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    paged="drift|footprints",
    example_args=(*_EXAMPLE, "--dry-run"),
    mutation_example_args=_EXAMPLE,
)

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite init DIR``: write a starter project of the packaged agent guide into ``DIR`` (capability
cli-contract, "Init command"; ``docs/cli-contract.md``, "init"). Runs no tool."""

from __future__ import annotations

import argparse
import re
import shlex
from pathlib import Path

from fenolite.agent import guide
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError

HELP = "write a starter project (a design script that builds with the built-in catalog) into a folder"
DEFAULT_STARTER = "blink"
DESIGN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
SCRIPT = "design.py"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'init'."
    parser.add_argument("dir", metavar="DIR", help="the project folder; it is created when missing")
    parser.add_argument(
        "--starter", metavar="NAME", default=DEFAULT_STARTER, help=f"the starter to write ({DEFAULT_STARTER})"
    )
    parser.add_argument("--name", metavar="NAME", help="the design name (default: the last part of DIR)")
    parser.add_argument("--force", action="store_true", help=f"replace an existing DIR/{SCRIPT}")


def next_commands(design: str, folder: str) -> list[str]:
    """The two commands to run after ``init``: the build's dry run, then the confirmed build."""
    base = f"fenolite build {shlex.quote(design)} --out {shlex.quote(folder + '/build')}"
    return [f"{base} --dry-run --json", f"{base} --confirm --json"]


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    known = [starter.name for starter in guide.starters()]
    if args.starter not in known:
        raise CliError(
            "FEN-2001",
            f"unknown starter {args.starter!r}",
            hint=f"the starters are: {', '.join(known)}",
            where="--starter",
        )
    folder = Path(args.dir)
    name = args.name if args.name is not None else (ctx.cwd / folder).resolve().name
    if DESIGN_NAME.fullmatch(name) is None:
        raise CliError(
            "FEN-2001",
            f"{name!r} is not a design name: letters, digits, '_', '.' and '-', the first a letter or digit",
            hint="pass --name NAME",
            where="--name" if args.name is not None else "DIR",
        )
    design = (folder / SCRIPT).as_posix()
    if (ctx.cwd / folder / SCRIPT).exists() and not args.force:
        raise CliError(
            "FEN-2001",
            f"{design} exists",
            hint="pass --force to replace it (a .bak copy is kept), or name another folder",
            where=design,
        )
    writes = tuple(
        PlannedWrite(path=(folder / file).as_posix(), data=data, kind="starter")
        for file, data in guide.render_starter(args.starter, name).items()
    )
    return Result(
        result={
            "starter": args.starter,
            "name": name,
            "design": design,
            "next": next_commands(design, folder.as_posix()),
        },
        writes=writes,
    )


COMMAND = Command(
    name="init",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=("proj", "--dry-run"),
    mutation_example_args=("proj",),
)

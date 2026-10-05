# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite sync DESIGN.py --out DIR --to-source [--check]``: copy the layout of a built project into
the source tree (``docs/cli-contract.md``, "sync"; ``docs/lens.md``, "sync").

The board in ``DIR`` is the layout's truth. ``sync --to-source`` writes its placements to
``placements.toml`` beside the design script, which ``build`` reads, and reports what the next build would
drop or overwrite. ``--check`` writes nothing and fails when the committed file is stale. The command runs
``DESIGN.py`` as ``build`` does and starts no external tool.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import fenolite
from fenolite.cli._script import DesignScriptError, run_design_script
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.cmd_build import MINIMAL
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FormatError, Issue
from fenolite.dsl import BOARD_ORIGIN, DslError, module_moves, moves, net_moves, to_model
from fenolite.lens.moved import Aliases
from fenolite.lens.placements import FILE_NAME
from fenolite.lens.preserve import read_existing
from fenolite.lens.sync import EVIDENCE, issue, plan_sync

HELP = (
    "copy the layout of a built project into the source tree (runs DESIGN.py as your own code: never run "
    "it on an untrusted script)"
)
EXAMPLE_SYNC_OUT = str(Path(fenolite.__file__).resolve().parents[2] / "tests/data/lens/sync_minimal")
"""A committed target-10 build of the packaged minimal script, kept equal to a fresh build by a test."""
KIND = "placements-toml"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = (
        HELP + ". Writes placements.toml beside DESIGN.py; build reads it. --check writes nothing and "
        "exits 5 when the file would change."
    )
    parser.add_argument("design", metavar="DESIGN.py", help="the design script (executed in-process)")
    parser.add_argument("--out", required=True, metavar="DIR", help="the built project folder to read")
    parser.add_argument(
        "--to-source",
        action="store_true",
        help="the direction: from the board in DIR to the files beside DESIGN.py (required)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="write nothing; report each file that would change as an error (for CI)",
    )


def first_difference(old: str | None, new: str) -> str:
    """The header of the first table of ``new`` whose text ``old`` does not hold, or ``schema``."""
    held = set((old or "").split("\n\n"))
    for block in new.split("\n\n"):
        if block not in held:
            line = block.splitlines()[0] if block else ""
            return line.strip("[]") if line.startswith("[") else "schema"
    return "schema"


def _text(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        raise FormatError(f"not UTF-8 text: {error}", file=path.name) from error


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if not args.to_source:
        raise CliError(
            "FEN-2001",
            "sync needs its direction: --to-source",
            where="--to-source",
            hint="add --to-source: the board in --out is copied to the files beside the script",
        )
    if args.check and getattr(args, "confirm", False):
        raise CliError("FEN-2001", "--check writes nothing, so it does not take --confirm", where="--check")
    script = Path(args.design)
    script_path = script if script.is_absolute() else ctx.cwd / script
    out = Path(args.out)
    out_dir = out if out.is_absolute() else ctx.cwd / out
    run = run_design_script(script_path)
    design = run.design
    try:
        model = to_model(design)
        aliases = Aliases(moves(design), module_moves(design), net_moves(design))
    except DslError as error:
        raise DesignScriptError(str(error), file=str(args.design)) from error
    existing = read_existing(out_dir, design.name)
    if existing.board is None:
        raise CliError(
            "FEN-3001",
            f"{design.name}.kicad_pcb is not in {args.out}: there is no layout to copy",
            where=f"{design.name}.kicad_pcb",
            hint="run fenolite build first",
        )
    folder = script.parent
    current = _text(script_path.resolve().parent / FILE_NAME)
    plan = plan_sync(
        model, existing, name=design.name, aliases=aliases, origin=BOARD_ORIGIN, placements_text=current
    )
    issues: list[Issue] = list(plan.issues)
    writes: tuple[PlannedWrite, ...] = ()
    if args.check:
        for name, text in sorted(plan.files.items()):
            table = first_difference(current if name == FILE_NAME else None, text)
            issues.append(
                issue(
                    "sync.would-change",
                    f"{name} is not current: sync would change it, first at [{table}]"
                    if table != "schema"
                    else f"{name} is not current: sync would write it",
                    name,
                    "run fenolite sync --to-source --confirm and commit the file",
                )
            )
    else:
        writes = tuple(
            PlannedWrite(path=str(folder / name), data=text.encode("utf-8"), kind=KIND)
            for name, text in sorted(plan.files.items())
        )
    result = {"design": design.name, "out": str(out), **plan.result, "script_output": run.output}
    return Result(
        result=result,
        issues=tuple(issues),
        evidence=EVIDENCE,
        input=InputRef(
            path=str(args.design),
            sha256=hashlib.sha256(script_path.read_bytes()).hexdigest(),
            kind="fenolite-dsl",
            format_version=None,
        ),
        writes=writes,
    )


_EXAMPLE = (str(MINIMAL), "--out", EXAMPLE_SYNC_OUT, "--to-source")
COMMAND = Command(
    name="sync",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(*_EXAMPLE, "--dry-run"),
    # no mutation example: the command writes beside the design script, not under the working directory,
    # so its example would write into the package folder; tests/unit/cli/test_sync_cmd.py runs the
    # mutation protocol on a copy of a design
    mutation_example_args=None,
)

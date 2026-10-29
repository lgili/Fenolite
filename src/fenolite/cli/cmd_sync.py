# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite sync DESIGN.py --out DIR --to-source [--check]``: copy the layout of a built project into
the source tree (``docs/cli-contract.md``, "sync"; ``docs/lens.md``, "sync").

The board in ``DIR`` is the layout's truth. ``sync --to-source`` records what KiCad changed against the
script in ``edits.toml`` beside the design script (positions, rotations, values and footprints, each over
the script value it was made over; change c0250), which ``build`` reads, and reports what the next build
would drop or overwrite. A ``sync.conflict`` writes nothing: ``build --take`` resolves it. ``--check``
writes nothing and fails when a committed file is stale or a property is in conflict. The command runs
``DESIGN.py`` as ``build`` does and starts no external tool.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import fenolite
from fenolite.backends.kicad import sch
from fenolite.cli._padmap import apply_default_pad_maps
from fenolite.cli._script import DesignScriptError, run_design_script
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.cmd_build import MINIMAL, code_placements
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence
from fenolite.dsl import BOARD_ORIGIN, DslError, module_moves, moves, net_moves, placements, to_model
from fenolite.lens import edits as edits_mod
from fenolite.lens.moved import Aliases
from fenolite.lens.placements import FILE_NAME
from fenolite.lens.preserve import read_existing
from fenolite.lens.sync import EVIDENCE, SYMBOL_FILE_NAME, issue, plan_sync
from fenolite.model.schematic import SchematicSheet

HELP = (
    "copy the layout of a built project into the source tree (runs DESIGN.py as your own code: never run "
    "it on an untrusted script)"
)
EXAMPLE_SYNC_OUT = str(Path(fenolite.__file__).resolve().parents[2] / "tests/data/lens/sync_minimal")
"""A committed target-10 build of the packaged minimal script, kept equal to a fresh build by a test."""
KIND = "placements-toml"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = (
        HELP + ". KiCad writes edits.toml; Altium captures native schematic layout beside DESIGN.py. "
        "Build reads these files. --check writes nothing and "
        "exits 5 when the file would change."
    )
    parser.add_argument("design", metavar="DESIGN.py", help="the design script (executed in-process)")
    parser.add_argument("--out", required=True, metavar="DIR", help="the built project folder to read")
    parser.add_argument(
        "--target",
        choices=("kicad", "altium"),
        default="kicad",
        help="the backend to synchronise (default kicad)",
    )
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
    parser.add_argument(
        "--take",
        action="append",
        default=None,
        metavar="SIDE[:TARGET]",
        help="refused: sync records and never resolves; resolve a conflict with fenolite build --take",
    )


def first_difference(old: str | None, new: str) -> str:
    """The header of the first table of ``new`` whose text ``old`` does not hold, or ``schema`` when
    the difference is before the tables."""
    held = {block.strip() for block in (old or "").split("\n\n")}
    for block in new.split("\n\n"):
        if block.strip() not in held:
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


def _sheets(root: Path) -> list[SchematicSheet] | None:
    """The sheets of the schematic ``root``: the root file and every sheet file it names, each read once.
    ``None`` when the project has no schematic."""
    if not root.is_file():
        return None
    tree = sch.sheet_files(root)
    return [sch.read_schematic(root.parent / name, file=name) for name in tree.files]


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if not args.to_source:
        raise CliError(
            "FEN-2001",
            "sync needs its direction: --to-source",
            where="--to-source",
            hint="add --to-source: the board in --out is copied to the files beside the script",
        )
    if getattr(args, "take", None):
        raise CliError(
            "FEN-2001",
            "--take is an option of fenolite build: sync records, it never resolves",
            where="--take",
            hint="resolve the conflict with fenolite build --take, then sync",
        )
    if args.check and getattr(args, "confirm", False):
        raise CliError("FEN-2001", "--check writes nothing, so it does not take --confirm", where="--check")
    script = Path(args.design)
    script_path = script if script.is_absolute() else ctx.cwd / script
    out = Path(args.out)
    out_dir = out if out.is_absolute() else ctx.cwd / out
    run = run_design_script(script_path)
    design = run.design
    if args.target == "altium":
        from fenolite.cli.altium_schematic_layout import sync_native

        return sync_native(
            name=design.name,
            script=script_path,
            out=out_dir,
            ctx=ctx,
            check=bool(args.check),
            script_output=run.output,
        )
    try:
        model, _defaulted = apply_default_pad_maps(
            to_model(design), authored_symbols=design.symbols, authored_footprints=design.footprints
        )
        aliases = Aliases(moves(design), module_moves(design), net_moves(design))
        # relative requests, block poses and strategies are the code side too (change c0255)
        requests = code_placements(design, model, placements(design), script_path, ctx, str(args.design))
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
    source = script_path.resolve().parent
    edits_text = _text(source / edits_mod.EDITS_FILE)
    legacy = _text(source / FILE_NAME) if edits_text is None else None
    sheets = _sheets(out_dir / f"{design.name}.kicad_sch")
    held = {edits_mod.EDITS_FILE: edits_text, SYMBOL_FILE_NAME: _text(source / SYMBOL_FILE_NAME)}
    base_text = _text(out_dir / edits_mod.BASE_FILE)
    base = (
        edits_mod.read_base(base_text, target="kicad", file=edits_mod.BASE_FILE)
        if base_text is not None
        else edits_mod.BaseRecord.absent("kicad")
    )
    plan = plan_sync(
        model,
        existing,
        name=design.name,
        aliases=aliases,
        origin=BOARD_ORIGIN,
        edits_text=edits_text,
        placements_text=legacy,
        symbol_placements_text=held[SYMBOL_FILE_NAME],
        sheets=sheets,
        base=base,
        requests=requests,
    )
    issues: list[Issue] = [*base.issues, *plan.issues]
    writes: tuple[PlannedWrite, ...] = ()
    if args.check:
        for name, text in sorted(plan.files.items()):
            table = first_difference(held.get(name), text)
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
        evidence=Evidence.combine(EVIDENCE, edits_mod.EVIDENCE)
        if base.present or edits_text is not None
        else EVIDENCE,
        input=InputRef(
            path=str(args.design),
            sha256=hashlib.sha256(script_path.read_bytes()).hexdigest(),
            kind="fenolite-dsl",
            format_version=None,
        ),
        writes=writes,
        depends=depends_on(
            ctx.cwd,
            script_path,
            *(
                file
                for file in (out_dir / f"{design.name}.kicad_pcb", out_dir / f"{design.name}.kicad_sch")
                if file.is_file()
            ),
        ),
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

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite convert SRC --to {kicad,altium} --out DIR``: a project converted to another backend or KiCad
major, with a report of what is kept, changed or lost, and verified (capability design-conversion,
"Convert command", "Convert output folder" and "Convert result and exit codes"; ``docs/cli-contract.md``,
"convert"; ``docs/conversion.md``; change c0159).

The command parses its arguments, calls ``fenolite.api.convert`` and plans every file of the converted
project under ``DIR``; the dispatcher writes them under ``--confirm``, all or none, and keeps a ``.bak`` of
each file it overwrites. ``DIR`` never is the source's folder or a folder that holds it. A refused loss
exits 7 (``FEN-7001``) with one ``convert.lossy`` issue per kind; a difference of the read-back that no
loss explains is a ``convert.unexplained`` error, which plans no write and exits 5.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from fenolite.api.conversion import convert
from fenolite.backends.altium import project
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli._manifest import joined
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.convert.direction import BODIES, TARGETS

HELP = "convert a project to another backend or KiCad major, reporting what is lost"
KINDS = {
    ".kicad_pcb": "kicad_pcb",
    ".kicad_pro": "kicad_pro",
    ".kicad_dru": "kicad_dru",
    ".kicad_sch": "kicad_sch",
    ".prjpcb": "altium_prjpcb",
    ".pcbdoc": project.PCBDOC_KIND,
    ".pcblib": project.PCBLIB_KIND,
    ".schdoc": project.SCHDOC_KINDS["binary"],
    ".schlib": project.SCHLIB_KIND,
    ".harness": project.HARNESS_KIND,
    ".outjob": "altium_outjob",
}
"""The kind of a planned file by its suffix, as ``build`` names them."""
EXAMPLE_OUT = "fenolite-convert"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'convert'."
    parser.add_argument(
        "src",
        metavar="SRC",
        help="a KiCad project, board or folder",
    )
    parser.add_argument("--to", required=True, choices=TARGETS, help="the target backend")
    parser.add_argument("--out", required=True, metavar="DIR", help="the target folder (not the source's)")
    parser.add_argument("--name", metavar="NAME", help="the file stem")
    parser.add_argument(
        "--altium-bodies",
        choices=BODIES,
        default="extruded",
        help="Altium bodies: extruded (default) or none",
    )
    parser.add_argument("--report-ids", action="store_true", help="list item ids in the report")
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="skip the read-back (evidence UNVERIFIED)",
    )


def _absolute(given: str, ctx: Context) -> Path:
    path = Path(given)
    return Path(os.path.abspath(path if path.is_absolute() else ctx.cwd / path))


def _source_folder(source: Path) -> Path:
    return source if source.is_dir() else source.parent


def _check_out(out: Path, source: Path) -> None:
    """``FEN-2001`` when ``out`` is the source's folder or holds it: a conversion never writes over its
    source."""
    folder = _source_folder(source).resolve()
    target = out.resolve()
    if target == folder or folder.is_relative_to(target):
        raise CliError(
            "FEN-2001",
            f"--out {out.name} is the folder of the source or holds it; a conversion never writes over its "
            "source",
            where="--out",
            hint="name another folder with --out",
        )


def _kind(name: str) -> str:
    return KINDS.get(Path(name).suffix.lower(), "file")


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    source = _absolute(args.src, ctx)
    if not source.exists():
        raise CliError("FEN-3001", f"{source.name} does not exist", where=source.name)
    _check_out(_absolute(args.out, ctx), source)
    if args.name is not None and (not args.name or set(args.name) & set('\\/:*?"<>|')):
        raise CliError("FEN-2001", f"--name {args.name!r} is no file stem", where="--name")
    found = convert(
        source,
        to=args.to,
        kicad_version=ctx.kicad_target,
        allow_lossy=ctx.allow_lossy,
        bodies=args.altium_bodies,
        name=args.name,
        verify=not args.no_verify,
    )
    conversion = found.conversion
    read = conversion.source
    result: dict[str, Any] = {
        "source": {
            "path": read.path.name,
            "backend": read.backend,
            "kind": read.kind,
            "format_version": read.format_version,
        },
        "target": {
            "backend": conversion.target,
            "major": ctx.kicad_target if conversion.target == "kicad" else None,
        },
        "files": [{"name": name, "bytes": len(data)} for name, data in conversion.files.items()],
        "report": conversion.report.to_json(ids=args.report_ids),
        "equivalence": found.equivalence_json(),
        "experimental": conversion.direction.experimental,
    }
    writes = tuple(
        PlannedWrite(path=joined(args.out, name), data=data, kind=_kind(name))
        for name, data in conversion.files.items()
    )
    return Result(
        result=result,
        issues=found.issues,
        evidence=found.evidence,
        input=InputRef(
            path=read.path.name,
            sha256=read.sha256,
            kind=read.kind,
            format_version=None if read.format_version is None else str(read.format_version),
        ),
        writes=writes,
        depends=depends_on(ctx.cwd, read.path, *read.files.values()),
    )


COMMAND = Command(
    name="convert",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_BOARD, "--to", "altium", "--out", EXAMPLE_OUT, "--dry-run"),
    mutation_example_args=(EXAMPLE_BOARD, "--to", "altium", "--out", EXAMPLE_OUT),
)

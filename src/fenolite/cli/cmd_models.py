# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite models PATH [--vendor]``: the 3D model files that the footprints of a board name, and where
Fenolite finds each (capability cli-contract, "Models command"; ``docs/cli-contract.md``, "models"; user
guide ``docs/exports.md``, "3D models").

The command runs no tool and makes no request. ``--vendor`` plans copies of the located official models
into the project's ``3dmodels/`` folder, which a STEP export reads before any other source; the board and
its model paths never change.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from pathlib import Path
from typing import Any

from fenolite.backends.kicad import models
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli._kicadtool import board_format
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.output import InputRef

HELP = "list the 3D model files a board's footprints name and where each is found (runs no tool)"
WRITE_KIND = "3d-model"
_OFFICIAL = re.compile(r"^\$\{KICAD\d+_3DMODEL_DIR\}[/\\]")


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/exports.md, '3D models'."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument(
        "--vendor",
        action="store_true",
        help="copy the located official models into the project's 3dmodels/ folder (needs --confirm)",
    )


def _target(board: Path, name: str, ctx: Context) -> str:
    """``<board folder>/<name>`` relative to the working directory, with ``/``."""
    path = board.parent / name
    try:
        return Path(os.path.relpath(path, ctx.cwd)).as_posix()
    except ValueError:  # another drive on Windows: no relative path exists
        return path.as_posix()


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    given = Path(args.path)
    board = resolve_board(given if given.is_absolute() else ctx.cwd / given)
    data = board.read_bytes()
    plan = models.board_plan(board)
    located = [use for use in plan.uses if use.source not in (models.MISSING, models.IN_PLACE)]
    result: dict[str, Any] = {
        "board": board.name,
        "models": [models.use_dict(use) for use in plan.uses],
        "counts": {
            "paths": len(plan.uses),
            "located": len(plan.uses) - sum(1 for use in plan.uses if use.source == models.MISSING),
            "missing": sum(1 for use in plan.uses if use.source == models.MISSING),
        },
    }
    writes: list[PlannedWrite] = []
    if args.vendor:
        # one copy per official model (``${KICAD<N>_3DMODEL_DIR}/<rel>``) that is not in the project yet
        for use in located:
            official = _OFFICIAL.match(use.path)
            if official is None or use.source == "project":
                continue
            name = f"{models.MODEL_FOLDER}/{use.path[official.end() :]}".replace("\\", "/")
            source = plan.files.get(name)
            if source is not None:
                writes.append(PlannedWrite(_target(board, name, ctx), Path(source).read_bytes(), WRITE_KIND))
    version = board_format(board)
    return Result(
        result=result,
        issues=plan.issues,
        evidence=models.EVIDENCE,
        input=InputRef(
            path=board.name,
            sha256=hashlib.sha256(data).hexdigest(),
            kind="kicad_pcb",
            format_version=None if version is None else str(version),
        ),
        writes=tuple(writes),
    )


COMMAND = Command(
    name="models",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    paged="models",
    example_args=(EXAMPLE_BOARD,),
    mutation_example_args=(EXAMPLE_BOARD, "--vendor"),
)

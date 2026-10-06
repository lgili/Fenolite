# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite render PATH --out DIR``: review views of a board through ``kicad-cli``, on a copy of the
project (capability manufacturing-exports, "Render views"; ``docs/cli-contract.md``, "render").

A view is a review artefact, never a gate: a view that cannot be produced is a warning, and the exit code
stays 0.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
from pathlib import Path, PurePosixPath
from typing import Any

from fenolite.backends.kicad.plot import DEFAULT_HEIGHT, DEFAULT_WIDTH, VIEWS, plot_view
from fenolite.backends.kicad.projectset import project_set, resolve_board
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT, board_format, preflight
from fenolite.cli._manifest import with_manifest
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import Issue
from fenolite.exports import EVIDENCE, manifest
from fenolite.exports.codes import issue

HELP = "render review views of a board through kicad-cli on a copy of the project (writes under DIR)"
MIN_SIZE, MAX_SIZE = 64, 8192
MANIFEST_KIND = "render"
"""The kind of every view in the manifest; ``result.views`` keeps ``svg`` and ``png``."""


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/exports.md."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument("-o", "--out", required=True, metavar="DIR", help="the folder to write under")
    parser.add_argument("--svg", action="store_true", help="front.svg and back.svg (plots)")
    parser.add_argument("--png", action="store_true", help="top.png and bottom.png (rendered images)")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, metavar="PX", help="PNG width (1600)")
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT, metavar="PX", help="PNG height (1200)")
    parser.add_argument(
        "--manifest", action="store_true", help=f"also add the views to {manifest.FILE_NAME} in DIR"
    )
    parser.add_argument("--kicad-cli", dest="kicad_cli", metavar="PATH", help="the kicad-cli to run")
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SECONDS", help="per kicad-cli run (300)"
    )


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    kinds = [kind for kind in ("svg", "png") if getattr(args, kind)]
    if not kinds:
        raise CliError("FEN-2001", "no view selected", hint="pass --svg, --png or both")
    for name in ("width", "height"):
        value = getattr(args, name)
        if not MIN_SIZE <= value <= MAX_SIZE:
            raise CliError("FEN-2001", f"--{name} {value} is outside {MIN_SIZE}..{MAX_SIZE}")
    given = Path(args.path)
    board = resolve_board(given if given.is_absolute() else ctx.cwd / given)
    project = project_set(board)
    cli = preflight(args.kicad_cli, args.timeout, board)
    others = {name: path for name, path in project.files.items() if name != project.board}
    issues: list[Issue] = []
    writes: list[PlannedWrite] = []
    views: list[dict[str, Any]] = []
    out = PurePosixPath(Path(args.out).as_posix())
    for name, view in sorted(VIEWS.items()):
        if view.kind not in kinds:
            continue
        data, message = plot_view(cli, name, board, others, width=args.width, height=args.height)
        if data is None:
            issues.append(issue("render.failed", f"{name} was not produced: {message}", where=name))
            continue
        writes.append(PlannedWrite((out / name).as_posix(), data, view.kind))
        views.append(
            {"path": name, "kind": view.kind, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        )
    version = cli.version()
    source = board.read_bytes()
    number = board_format(board)
    if args.manifest:  # a view that failed has no entry; an unreadable manifest in DIR refuses every write
        tool = manifest.ToolRef("kicad-cli", version)
        sha = hashlib.sha256(source).hexdigest()
        entries = [
            manifest.file_entry(
                PurePosixPath(w.path).name,
                MANIFEST_KIND,
                w.data,
                evidence=EVIDENCE.level.value,
                from_={"board": sha},
                tool=f"{tool.name} {tool.version}",
            )
            for w in writes
        ]
        merged, refused = with_manifest(
            writes, args.out, ctx, entries, board=manifest.BoardRef(project.board, sha, number), tool=tool
        )
        writes = list(merged)
        issues += refused
    return Result(
        result={"board": project.board, "out": str(args.out), "views": views, "tool_version": version},
        issues=tuple(issues),
        evidence=dataclasses.replace(EVIDENCE, oracle=f"kicad-cli {version}"),
        input=InputRef(
            path=board.name,
            sha256=hashlib.sha256(source).hexdigest(),
            kind="kicad_pcb",
            format_version=None if number is None else str(number),
        ),
        writes=tuple(writes),
    )


_EXAMPLE = (EXAMPLE_BOARD, "--out", "views", "--svg", "--png")
COMMAND = Command(
    name="render",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(*_EXAMPLE, "--dry-run"),
    mutation_example_args=_EXAMPLE,
    example_tools=("kicad-cli",),
)

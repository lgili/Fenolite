# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Refill a KiCad board through KiCad 10 on copies, then plan one same-major board write."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import os
from pathlib import Path
from typing import Any

from fenolite.backends.kicad.cli import KicadCliError
from fenolite.backends.kicad.fill import EVIDENCE, fill_board
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.projectset import project_set, resolve_board
from fenolite.backends.kicad.sexpr import parse
from fenolite.backends.kicad.versions import inspect
from fenolite.cli._examples import EXAMPLE_REFILLED, EXAMPLE_UNFILLED
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT, board_format, preflight
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import Issue
from fenolite.core.evidence import Level

HELP = "fill a KiCad board through kicad-cli 10 on a copy, preserving its format major"
TOOL_HINT = "install KiCad 10, pass --from REFILLED or --kicad-cli docker:<image>"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'fill'."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, .kicad_pro or project folder")
    parser.add_argument(
        "--from", dest="from_board", metavar="REFILLED", help="a board already refilled by KiCad"
    )
    parser.add_argument(
        "-o", "--out", metavar="FILE", help="write to this file instead of replacing PATH's board"
    )
    parser.add_argument(
        "--kicad-cli", dest="kicad_cli", metavar="PATH", help="KiCad 10 binary or docker:<image>"
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SECONDS")


def _source(path: str, ctx: Context) -> Path:
    given = Path(path)
    return given if given.is_absolute() else ctx.cwd / given


REFILL = "refill"
"""The one unit of progress of ``fill``: KiCad's refill of the board."""


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if args.out and Path(args.out).is_absolute():
        raise CliError("FEN-2001", "--out must be relative to the working directory")
    board = resolve_board(_source(args.path, ctx))
    data = board.read_bytes()
    text = data.decode("utf-8")
    input_ref = InputRef(
        board.name,
        hashlib.sha256(data).hexdigest(),
        "kicad_pcb",
        str(board_format(board)) if board_format(board) is not None else None,
    )
    read_issues: list[Issue] = []
    design = read_board(text, file=board.name, issues=read_issues)
    zones = () if design.board is None else tuple(z for z in design.board.zones if z.net_id is not None)
    target = args.out or os.path.relpath(board, ctx.cwd)
    if not zones:
        return Result(
            result={
                "board": board.name,
                "target": target,
                "changed": False,
                "zones": [],
                "tool_version": None,
                "tool_writes": [],
            },
            issues=(*read_issues, Issue("zone.none", "info", "board has no copper zones with a net")),
            evidence=EVIDENCE,
            input=input_ref,
        )
    tool_writes: list[str] = []
    if args.from_board:
        source = _source(args.from_board, ctx)
        read: list[Path] = [source]
        saved_text = source.read_text(encoding="utf-8")
        version = inspect(parse(saved_text)).generator_version or "unknown"
        evidence = dataclasses.replace(EVIDENCE, level=Level.INFERRED, oracle=f"kicad-cli {version}")
    else:
        cli = preflight(args.kicad_cli, args.timeout, board, hint=TOOL_HINT)
        if cli.major() < 10:
            raise CliError("FEN-6002", f"kicad-cli {cli.version()} cannot refill zones", hint=TOOL_HINT)
        project = project_set(board)
        read = list(project.files.values())
        others = {name: path for name, path in project.files.items() if name != project.board}
        ctx.progress.step(REFILL, index=1, total=1)
        result = cli.refill(project.files[project.board], files=others)
        ctx.progress.done(REFILL, detail=result.run.outcome)
        if result.run.outcome == "timeout":
            raise KicadCliError("kicad-cli zone refill timed out", result.run)
        if result.run.returncode != 0:
            raise KicadCliError(f"kicad-cli zone refill exited {result.run.returncode}", result.run)
        if result.board is None:
            raise KicadCliError("kicad-cli saved no refilled board", result.run)
        saved_text = result.board.decode("utf-8")
        version = cli.version()
        tool_writes = sorted(result.run.outputs)
        evidence = dataclasses.replace(EVIDENCE, oracle=f"kicad-cli {version}")
    filled = fill_board(text, saved_text, file=board.name)
    original_zones = {z.id: z for z in zones}
    details: list[dict[str, Any]] = []
    for zone in sorted(filled.zones, key=lambda z: (original_zones[z.zone_id].name, z.zone_id)):
        before = original_zones[zone.zone_id]
        details.append(
            {
                "id": zone.zone_id,
                "name": before.name,
                "layers": list(before.layers),
                "fills": len(zone.fills),
                "islands": sum(f.island for f in zone.fills),
                "filled": zone.filled,
            }
        )
    changed = filled.text is not None and filled.text != text
    writes = (
        (PlannedWrite(target, filled.text.encode("utf-8"), "kicad_pcb"),) if changed and filled.text else ()
    )
    return Result(
        result={
            "board": board.name,
            "target": target,
            "changed": changed,
            "zones": details,
            "tool_version": version,
            "tool_writes": tool_writes,
        },
        issues=(*read_issues, *filled.issues),
        evidence=evidence,
        input=input_ref,
        writes=writes,
        depends=depends_on(ctx.cwd, board, *read),
    )


_EXAMPLE = (EXAMPLE_UNFILLED, "--from", EXAMPLE_REFILLED, "--out", "fenolite-filled.kicad_pcb")
COMMAND = Command(
    name="fill",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(*_EXAMPLE, "--dry-run"),
    mutation_example_args=_EXAMPLE,
)

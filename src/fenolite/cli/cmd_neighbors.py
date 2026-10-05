# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite neighbors PATH REF``: the footprints near one part (capability cli-contract, "Neighbors
command"; ``docs/cli-contract.md``, "neighbors"). Runs no tool."""

from __future__ import annotations

import argparse
from typing import Any

from fenolite.analysis.views import neighbors_view
from fenolite.cli._boardview import closest, length, load_board, to_json
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError

HELP = "list the footprints near one part, by the distance between their courtyards (runs no tool)"
DEFAULT_RADIUS = "5mm"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'neighbors'."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument("ref", metavar="REF", help="the reference of the part, such as R1")
    parser.add_argument("--radius", default=DEFAULT_RADIUS, metavar="L", help="how far to look (default 5mm)")


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    radius = length(args.radius, "--radius")
    if radius < 0:
        raise CliError("FEN-2001", "--radius: the radius is at least 0", where="--radius")
    view = load_board(args.path, ctx)
    try:
        found = neighbors_view(view.design, args.ref, extents=view.extents, pads=view.pads, radius=radius)
    except KeyError:
        placed = {fp.component_id for fp in (view.design.board.footprints if view.design.board else ())}
        refs = (c.ref for c in view.design.circuit.components if c.id in placed)
        raise CliError(
            "FEN-2001",
            f"the board has no footprint {args.ref!r}",
            hint=closest(args.ref, refs),
            where=args.ref,
        ) from None
    result: dict[str, Any] = {
        "part": to_json(found.part),
        "radius": radius,
        "neighbors": to_json(found.neighbors),
    }
    return Result(result=result, issues=view.issues, evidence=view.evidence, input=view.input)


COMMAND = Command(
    name="neighbors",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    paged="neighbors",
    example_args=(EXAMPLE_BOARD, "R1"),
)

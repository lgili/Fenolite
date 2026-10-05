# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite net PATH [NAME]``: the nets of a board, or one net, from the board model (capability
cli-contract, "Net command"; ``docs/cli-contract.md``, "net"). Runs no tool.

The view says what a net holds, never whether it is connected: missing connections are KiCad's
``unconnected_items`` (``fenolite check``).
"""

from __future__ import annotations

import argparse
from typing import Any

from fenolite.analysis.views import net_list, net_view
from fenolite.cli._boardview import closest, load_board, to_json
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError

HELP = "list the nets of a board, or describe one net: pads, copper per layer, vias, zones (runs no tool)"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'net'."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument("name", metavar="NAME", nargs="?", help="the net to describe (default: list all)")


def _class(row: dict[str, Any]) -> dict[str, Any]:
    """The record with ``class`` for ``netclass``, as the contract names the key."""
    return {("class" if key == "netclass" else key): value for key, value in row.items()}


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    view = load_board(args.path, ctx)
    if args.name is None:
        result: dict[str, Any] = {"nets": [_class(to_json(row)) for row in net_list(view.design)]}
    else:
        try:
            found = net_view(view.design, args.name, pads=view.pads)
        except KeyError:
            names = (net.name for net in view.design.circuit.nets)
            raise CliError(
                "FEN-2001", f"the board has no net {args.name!r}", hint=closest(args.name, names),
                where=args.name,
            ) from None  # fmt: skip
        result = {"net": _class(to_json(found))}
    return Result(result=result, issues=view.issues, evidence=view.evidence, input=view.input)


COMMAND = Command(
    name="net",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    paged="nets|net.pads",
    example_args=(EXAMPLE_BOARD,),
)

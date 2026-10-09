# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite net PATH [NAME]``: the nets of a board, or one net, from the board model (capability
cli-contract, "Net command"; ``docs/cli-contract.md``, "net"). Runs no tool.

The view says what a net holds and, since change c0108, what is open: ``islands`` and ``open`` per net
are the copper islands and the open connections that ``analysis.connectivity`` computes from the board
("Open connections in the net command"). ``fenolite check`` stays the gate, with KiCad's
``unconnected_items``.
"""

from __future__ import annotations

import argparse
from typing import Any

from fenolite.analysis import connectivity as conn
from fenolite.analysis.views import net_list, net_view
from fenolite.cli._boardview import closest, load_board, to_json
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.core.evidence import Evidence

HELP = "list the nets of a board, or one net: pads, copper, vias, zones, open connections (runs no tool)"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'net'."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument("name", metavar="NAME", nargs="?", help="the net to describe (default: list all)")


def _class(row: dict[str, Any]) -> dict[str, Any]:
    """The record with ``class`` for ``netclass``, as the contract names the key."""
    return {("class" if key == "netclass" else key): value for key, value in row.items()}


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    view = load_board(args.path, ctx)
    wanted = None if args.name is None else (args.name,)
    report = conn.connectivity(view.design, pads=view.pads, nets=wanted)
    if args.name is None:
        rows = net_list(view.design, pads=view.pads, report=report)
        result: dict[str, Any] = {"nets": [_class(to_json(row)) for row in rows]}
    else:
        try:
            found = net_view(view.design, args.name, pads=view.pads, report=report)
        except KeyError:
            names = (net.name for net in view.design.circuit.nets)
            raise CliError(
                "FEN-2001", f"the board has no net {args.name!r}", hint=closest(args.name, names),
                where=args.name,
            ) from None  # fmt: skip
        result = {"net": _class(to_json(found))}
    issues = tuple(dict.fromkeys((*view.issues, *report.issues)))
    evidence = Evidence.combine(view.evidence, report.evidence)
    return Result(result=result, issues=issues, evidence=evidence, input=view.input)


COMMAND = Command(
    name="net",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    paged="nets|net.pads",
    example_args=(EXAMPLE_BOARD,),
)

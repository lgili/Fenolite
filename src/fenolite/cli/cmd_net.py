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
from fenolite.analysis.ties import item_names
from fenolite.analysis.views import net_list, net_view
from fenolite.cli._boardview import BoardView, closest, load_board, to_json
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.core.evidence import Evidence

HELP = "list the nets of a board, or one net: pads, copper, vias, zones, open connections (runs no tool)"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'net'."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument("name", metavar="NAME", nargs="?", help="the net to describe (default: list all)")
    parser.add_argument(
        "--islands", action="store_true", help="with NAME: list each island of the net with its members"
    )
    parser.add_argument(
        "--without", action="append", default=[], metavar="ITEM[,ITEM...]",
        help="with NAME: the islands without these tracks, arcs, vias or zones (id, native id or locator)",
    )  # fmt: skip


def _class(row: dict[str, Any]) -> dict[str, Any]:
    """The record with ``class`` for ``netclass``, as the contract names the key."""
    return {("class" if key == "netclass" else key): value for key, value in row.items()}


def _island(island: conn.NetIsland) -> dict[str, Any]:
    members = [
        {"kind": m.kind, "id": m.id, "where": m.where, "layers": list(m.layers)} for m in island.members
    ]
    return {"pads": list(island.pads), "members": members, "zones": sorted(island.zones)}


def _islands(view: BoardView, name: str, without: list[str], *, zoned: bool) -> dict[str, Any]:
    """``island_list`` and, with ``without``, ``cut`` (change c0500; ``islands`` stays the count)."""
    try:
        after = conn.net_islands(view.design, pads=view.pads, nets=(name,), without=without).get(name, ())
    except KeyError as missing:
        [unknown] = missing.args
        held = {n for names in item_names(view.design).values() for n in names}
        raise CliError(
            "FEN-2001", f"the board has no track, arc, via or zone {unknown!r}", hint=closest(unknown, held),
            where=unknown,
        ) from None  # fmt: skip
    out: dict[str, Any] = {"island_list": [_island(i) for i in after]}
    if without:
        before = conn.net_islands(view.design, pads=view.pads, nets=(name,)).get(name, ())
        wheres = {m.id: m.where for island in before for m in island.members}
        cut: dict[str, Any] = {
            "removed": sorted(wheres.get(i, i) for i in conn.removed_ids(view.design, without)),
            "islands_before": len(before),
            "islands_after": len(after),
            "split": len(after) > len(before),
        }
        if zoned:
            cut["note"] = "saved fills are not repoured"
        out["cut"] = cut
    return out


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    view = load_board(args.path, ctx)
    if (args.islands or args.without) and args.name is None:
        raise CliError(
            "FEN-2001", "--islands and --without need NAME", hint="fenolite net PATH NAME --islands"
        )
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
        if args.islands or args.without:
            without = [n for v in args.without for n in v.split(",") if n]
            result["net"].update(_islands(view, args.name, without, zoned=bool(found.zones)))
    issues = tuple(dict.fromkeys((*view.issues, *report.issues)))
    evidence = Evidence.combine(view.evidence, report.evidence)
    return Result(result=result, issues=issues, evidence=evidence, input=view.input)


COMMAND = Command(
    name="net",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    paged="nets|net.pads|net.island_list",
    example_args=(EXAMPLE_BOARD,),
)

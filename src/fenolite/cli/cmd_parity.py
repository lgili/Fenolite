# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite parity PATH``: the board of a KiCad project compared with its schematic, and the pins of each
symbol with the pads of its footprint (capability cli-contract, "Parity command"; ``docs/cli-contract.md``,
"parity"; change c0072).

The comparison is Fenolite's own (``checks.parity``) and needs no tool for a project that ``build`` wrote:
the nets of such a schematic are read from the sheet. For any other schematic the nets come from
``kicad-cli sch export netlist``, run on copies. Nothing is written.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

from fenolite.backends.kicad import netlist as netlistmod
from fenolite.backends.kicad import oracle as oraclemod
from fenolite.backends.kicad import parity_inputs, sch_netlist
from fenolite.backends.kicad.netlist import KicadNetlist
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.projectset import ProjectNotFoundError, project_set, resolve_board
from fenolite.checks import parity
from fenolite.cli._examples import EXAMPLE_PARITY
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT, supported_tool
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence

HELP = (
    "compare the board of a KiCad project with its schematic, and symbol pins with footprint pads: without "
    "kicad-cli for a project that fenolite build wrote (writes nothing)"
)
NETLISTS: tuple[str, ...] = ("auto", "own", "kicad")
SCHEMATIC_SUFFIX = ".kicad_sch"
NO_TOOL_HINT = (
    "install KiCad 9 or 10, set FENOLITE_KICAD_CLI or pass --kicad-cli: the nets of a schematic that "
    "fenolite build did not write are read by kicad-cli"
)


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'parity'."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument(
        "--netlist",
        choices=NETLISTS,
        default="auto",
        help="where the nets of the schematic come from. auto (default): Fenolite's own reading of a "
        "schematic it generated, else kicad-cli; own: never a tool; kicad: always kicad-cli",
    )
    parser.add_argument("--kicad-cli", dest="kicad_cli", metavar="PATH", help="the kicad-cli to run")
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SECONDS", help="kicad-cli timeout (300)"
    )


def _export(schematic: Path, board: Path, args: argparse.Namespace) -> tuple[KicadNetlist, Evidence]:
    """The netlist that ``kicad-cli`` exports from copies of the project."""
    cli = supported_tool(args.kicad_cli, args.timeout, hint=NO_TOOL_HINT)
    files = oraclemod.with_sheets(schematic, dict(project_set(board).files))
    export = oraclemod.export_netlist_of(cli, schematic.name, files)
    if export.netlist is None:
        if export.outcome == "timeout":
            raise CliError(
                "FEN-6001",
                f"kicad-cli timed out after {args.timeout:g} s on {schematic.name}",
                hint="pass a longer --timeout",
                where=schematic.name,
                retryable=True,
            )
        raise CliError(
            "FEN-3004",
            f"kicad-cli wrote no netlist of {schematic.name}: {export.message}",
            hint="open the schematic in KiCad; fenolite inspect names what Fenolite reads of it",
            where=schematic.name,
        )
    combined = Evidence.combine(netlistmod.EVIDENCE, oraclemod.EVIDENCE)
    return export.netlist, Evidence(combined.level, f"kicad-cli {cli.version()}", combined.hypotheses)


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    given = Path(args.path)
    board = resolve_board(given if given.is_absolute() else ctx.cwd / given)
    schematic = board.with_suffix(SCHEMATIC_SUFFIX)
    if not schematic.is_file():
        raise ProjectNotFoundError(f"{board.name} has no schematic {schematic.name} next to it")
    sheets = parity_inputs.read_sheets(schematic)
    refused = parity_inputs.grammar_issues(sheets)
    inside = not refused and len(sheets) == 1
    if args.netlist == "own" and not inside:
        raise sch_netlist.NetlistUnsupportedError(refused)
    if args.netlist == "kicad" or not inside:
        found, evidence = _export(schematic, board, args)
        source = "kicad"
    else:
        found, evidence = parity_inputs.own_netlist(sheets, project=schematic.stem), sch_netlist.EVIDENCE
        source = "own"
    side = parity_inputs.side_of(schematic, sheets, parity_inputs.netlist_nodes(found))
    data = board.read_bytes()
    read: list[Issue] = []
    design = read_board(data.decode("utf-8"), file=board.name, issues=read)
    issues: list[Issue] = []
    report = parity.compare(side, design, issues=issues)
    result: dict[str, Any] = {
        "board": board.name,
        "schematic": schematic.name,
        "netlist": source,
        "summary": dict(report.summary),
        "findings": [finding.to_json() for finding in report.findings],
    }
    combined = Evidence.combine(report.evidence, evidence)
    return Result(
        result=result,
        issues=tuple(issues),
        evidence=Evidence(combined.level, evidence.oracle, combined.hypotheses),
        input=InputRef(
            path=board.name, sha256=hashlib.sha256(data).hexdigest(), kind="kicad_pcb", format_version=None
        ),
    )


COMMAND = Command(
    name="parity",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_PARITY,),
)

__all__ = ["COMMAND", "NETLISTS"]

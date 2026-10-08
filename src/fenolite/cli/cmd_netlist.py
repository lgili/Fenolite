# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite netlist PATH``: the components and nets of a KiCad project's schematic as JSON (capability
cli-contract, "Netlist command"; ``docs/cli-contract.md``, "netlist"; change c0063).

Two sources. ``kicad`` (the default) runs ``kicad-cli sch export netlist`` on copies and reads the export:
it works for every schematic KiCad loads. ``fenolite`` reads a schematic that ``build`` generated without
any tool, and refuses every other sheet (``kicad.sch.netlist-unsupported``): Fenolite does not
re-implement KiCad's connection graph. Nothing is written, and the result holds no date and no path of a
run.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

from fenolite.backends.kicad import netlist as netlistmod
from fenolite.backends.kicad import oracle as oraclemod
from fenolite.backends.kicad import sch, sch_netlist
from fenolite.backends.kicad.netlist import KicadNetlist
from fenolite.backends.kicad.netnames import UNCONNECTED_PREFIX
from fenolite.backends.kicad.projectset import ProjectNotFoundError, project_set, resolve_board
from fenolite.cli._examples import EXAMPLE_SCHEMATIC
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT, supported_tool
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.evidence import Evidence

HELP = (
    "list the components and nets of a KiCad schematic: from kicad-cli, or from Fenolite's own reading of "
    "a schematic it generated (writes nothing)"
)
SOURCES: tuple[str, ...] = ("kicad", "fenolite")
SCHEMATIC_SUFFIX = ".kicad_sch"
NO_TOOL_HINT = (
    "install KiCad 9 or 10, set FENOLITE_KICAD_CLI or pass --kicad-cli; for a schematic that "
    "fenolite build wrote, --source fenolite needs no tool"
)


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'netlist'."
    parser.add_argument(
        "path", metavar="PATH", help="a .kicad_sch, a .kicad_pcb, a .kicad_pro or a project folder"
    )
    parser.add_argument(
        "--source",
        choices=SOURCES,
        default="kicad",
        help="kicad: kicad-cli sch export netlist (default); fenolite: read a generated sheet, no tool",
    )
    parser.add_argument(
        "--min-pins",
        dest="min_pins",
        type=int,
        default=1,
        metavar="N",
        help="leave out the nets with fewer pins (default 1: every net)",
    )
    parser.add_argument("--kicad-cli", dest="kicad_cli", metavar="PATH", help="the kicad-cli to run")
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SECONDS", help="kicad-cli timeout (300)"
    )


def find_schematic(path: Path) -> Path:
    """The schematic ``path`` names: a ``.kicad_sch`` itself, else ``<stem>.kicad_sch`` beside the board
    that ``resolve_board`` finds. ``FEN-3001`` for a missing path or schematic."""
    if path.suffix == SCHEMATIC_SUFFIX:
        if not path.is_file():
            raise ProjectNotFoundError(f"{path.name} does not exist")
        return path
    board = resolve_board(path)
    schematic = board.with_suffix(SCHEMATIC_SUFFIX)
    if not schematic.is_file():
        raise ProjectNotFoundError(f"{board.name} has no schematic {schematic.name} next to it")
    return schematic


def _from_kicad(schematic: Path, args: argparse.Namespace) -> tuple[KicadNetlist, Evidence]:
    cli = supported_tool(args.kicad_cli, args.timeout, hint=NO_TOOL_HINT)
    board = schematic.with_suffix(".kicad_pcb")
    project = schematic.with_suffix(".kicad_pro")
    files: dict[str, Path] = {}
    if board.is_file():
        files = dict(project_set(board).files)
    elif project.is_file():
        files = {project.name: project}
    export = oraclemod.export_netlist_of(cli, schematic.name, oraclemod.with_sheets(schematic, files))
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


def _own(schematic: Path) -> tuple[KicadNetlist, Evidence]:
    """Fenolite's own netlist of the root sheet and of the child sheets it names (c0070). Each sheet file
    is read once and keyed by its path from the root's folder; a file that is missing or outside that
    folder is not read, so the grammar check reports the reference that names it."""
    sheet = sch.read_schematic(schematic.read_text(encoding="utf-8"), file=schematic.name)
    folder = schematic.parent
    children = {
        name: sch.read_schematic((folder / name).read_text(encoding="utf-8"), file=name)
        for name in sch.sheet_files(schematic).files[1:]
        if not name.startswith("../") and (folder / name).is_file()
    }
    found = sch_netlist.own_netlist(sheet, project=schematic.stem, children=children)
    return found, sch_netlist.evidence_of(sheet, children)


def is_unconnected(name: str, pins: int) -> bool:
    """Whether a net is one KiCad made for a single pin on no net."""
    return pins == 1 and name.startswith(UNCONNECTED_PREFIX)


def netlist_result(found: KicadNetlist, *, schematic: str, source: str, min_pins: int) -> dict[str, Any]:
    """The ``result`` of the command: components, the nets with at least ``min_pins`` pins, and counts
    over every net."""
    nets: list[dict[str, Any]] = []
    below = 0
    for net in found.nets:
        if len(net.nodes) < min_pins:
            below += 1
            continue
        nets.append(
            {
                "name": net.name,
                "class": net.netclass,
                "unconnected": is_unconnected(net.name, len(net.nodes)),
                "pins": [{"ref": n.ref, "pin": n.pin, "type": n.pintype} for n in net.nodes],
            }
        )
    return {
        "schematic": schematic,
        "source": source,
        "components": [
            {"ref": c.ref, "value": c.value, "footprint": c.footprint, "properties": dict(c.properties)}
            for c in found.components
        ],
        "nets": nets,
        "counts": {
            "components": len(found.components),
            "nets": len(found.nets),
            "pins": sum(len(net.nodes) for net in found.nets),
            "unconnected": sum(1 for net in found.nets if is_unconnected(net.name, len(net.nodes))),
            "below_min_pins": below,
        },
    }


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if args.min_pins < 1:
        raise CliError(
            "FEN-2001", f"--min-pins {args.min_pins} is below 1", where="--min-pins", hint="pass 1 or more"
        )
    given = Path(args.path)
    schematic = find_schematic(given if given.is_absolute() else ctx.cwd / given)
    found, evidence = _own(schematic) if args.source == "fenolite" else _from_kicad(schematic, args)
    return Result(
        result=netlist_result(found, schematic=schematic.name, source=args.source, min_pins=args.min_pins),
        evidence=evidence,
        input=InputRef(
            path=schematic.name,
            sha256=hashlib.sha256(schematic.read_bytes()).hexdigest(),
            kind="kicad_sch",
            format_version=None,
        ),
    )


COMMAND = Command(
    name="netlist",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_SCHEMATIC,),
    example_tools=("kicad-cli",),
)

__all__ = ["COMMAND", "SOURCES", "find_schematic", "is_unconnected", "netlist_result"]

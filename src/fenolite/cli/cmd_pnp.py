# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite pnp PATH``: the placement (pick-and-place) table of a board, rendered through a column
template the user writes (capability cli-contract, "Pnp command"; user guide ``docs/assembly.md``).

The rows come from the board file, in every case: ``place``, ``route`` and ``fill`` write the board and not
the ``.fenolite/`` model, so the board is the one description of where the parts are. No tool runs. The
table is JSON in the envelope; ``--out FILE`` also plans it as a CSV file.
"""

from __future__ import annotations

import argparse
from typing import Any

from fenolite.backends.kicad.outline import board_outline
from fenolite.cli._assembly import board_input, objects, planned, read_design, template_of
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli._manifest import needs_out, table_manifest
from fenolite.cli.api import Command, Context, Result
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.exports import manifest, placement

HELP = "the placement (pick-and-place) table of a board, through a column template (writes FILE with --out)"
SIDES = ("top", "bottom", "both")


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/assembly.md."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument("--template", metavar="FILE", help="the column template (TOML); default: built in")
    parser.add_argument("--side", choices=SIDES, default="both", help="the side to list (default both)")
    parser.add_argument("-o", "--out", metavar="FILE", help="also write the table as a CSV file")
    parser.add_argument(
        "--manifest", action="store_true", help=f"also add FILE to {manifest.FILE_NAME} in its folder"
    )


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    needs_out("pnp", args.manifest, args.out)
    board = board_input(args.path, ctx)
    template, name = template_of(args.template, ctx)
    design, read_evidence = read_design(board)
    rules = template.placement
    source = placement.rows_from_model(design)
    issues: list[Issue] = []
    placed = placement.apply(source, rules, outline=board_outline(design), issues=issues)
    rows = tuple(row for row in placed if args.side in ("both", row.side))
    header = [column.name for column in rules.columns]
    cells = placement.table(rows, rules)
    footprints = 0 if design.board is None else len(design.board.footprints)
    result: dict[str, Any] = {
        "template": name,
        "columns": header,
        "rows": objects(header, cells),
        "counts": {
            "rows": len(rows),
            "top": sum(1 for row in rows if row.side == "top"),
            "bottom": sum(1 for row in rows if row.side == "bottom"),
            "dnp": sum(1 for row in source if row.dnp),
            "left_out": footprints - len(rows),
        },
        "units": rules.units,
        "origin": rules.origin,
        "y_axis": rules.y_axis,
    }
    failed = any(found.severity == "error" for found in issues)
    evidence = Evidence.combine(placement.EVIDENCE, read_evidence)
    writes = () if failed else planned(args.out, "pnp", header, cells, template.csv)
    if args.manifest and writes:
        writes, refused = table_manifest(
            writes, ctx, evidence=evidence.level.value, board=board.manifest_ref()
        )
        issues += refused
    return Result(result=result, issues=tuple(issues), evidence=evidence, input=board.ref(), writes=writes)


COMMAND = Command(
    name="pnp",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_BOARD,),
    mutation_example_args=(EXAMPLE_BOARD, "--out", "pnp.csv"),
)

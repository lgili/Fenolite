# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite bom PATH``: the bill of materials of a project, rendered through a column template the user
writes (capability cli-contract, "Bom command"; user guide ``docs/assembly.md``).

The ``model`` source lists the parts of the ``.fenolite/`` model of a built project, or of the board read
for any other project, and runs no tool. The ``kicad`` source, a bill exported by ``kicad-cli`` from the
project's schematic, is the default by contract and is not available yet: it waits for the schematic
writer. Until then the command says so and names ``--source model``; it never falls back silently.

The table is JSON in the envelope; ``--out FILE`` also plans it as a CSV file.
"""

from __future__ import annotations

import argparse
import dataclasses
from typing import Any

from fenolite.cli._assembly import (
    BoardInput,
    board_input,
    built_model,
    objects,
    planned,
    read_design,
    template_of,
)
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.exports import bom
from fenolite.exports.assembly import BomTemplate, property_name
from fenolite.exports.codes import issue
from fenolite.model.design import Design

HELP = "the bill of materials of a project, through a column template (writes FILE with --out)"
SOURCES = ("kicad", "model")
MODEL_HINT = "pass --source model to list the parts of the model or of the board"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/assembly.md."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument(
        "--source",
        choices=SOURCES,
        default="kicad",
        help="where the parts come from: kicad (the schematic, through kicad-cli; not available yet) or "
        "model (the built model, or the board); default kicad",
    )
    parser.add_argument("--template", metavar="FILE", help="the column template (TOML); default: built in")
    parser.add_argument("-o", "--out", metavar="FILE", help="also write the table as a CSV file")
    parser.add_argument("--against", metavar="OTHER", help="another project: also list what changed from it")


def _schematic(board: BoardInput) -> bool:
    return board.path.with_suffix(".kicad_sch").is_file()


def _refuse_kicad(board: BoardInput) -> None:
    """The ``kicad`` source cannot answer yet: say why for this project, and name the other source."""
    if not _schematic(board):
        raise CliError(
            "FEN-3001",
            f"{board.path.name} has no schematic {board.path.with_suffix('.kicad_sch').name} next to it",
            hint=MODEL_HINT,
            where=board.path.name,
        )
    raise CliError(
        "FEN-2001",
        "the kicad source of bom is not available in this version of Fenolite",
        hint=MODEL_HINT,
        where="--source",
    )


def _model(board: BoardInput) -> tuple[Design, Evidence]:
    """The design the ``model`` source lists, and the evidence of its parts: ``bom.EVIDENCE_MODEL`` for a
    built project that has a schematic, and ``INFERRED`` for any other input."""
    inferred = dataclasses.replace(bom.EVIDENCE_MODEL, level=Level.INFERRED)
    if not board.built:
        design, read_evidence = read_design(board)
        return design, Evidence.combine(inferred, read_evidence)
    return built_model(board), bom.EVIDENCE_MODEL if _schematic(board) else inferred


def _lines(design: Design, template: BomTemplate) -> tuple[tuple[bom.BomPart, ...], tuple[bom.BomLine, ...]]:
    parts = bom.parts_from_model(design)
    return parts, bom.group(parts, template)


def _missing_properties(parts: tuple[bom.BomPart, ...], template: BomTemplate) -> list[Issue]:
    issues: list[Issue] = []
    for column in template.columns:
        name = property_name(column.field)
        if name is not None and not any(name in part.properties for part in parts):
            issues.append(
                issue(
                    "bom.property-missing",
                    f"no part has the property {name!r}; the column {column.name!r} is empty",
                    where=column.name,
                )
            )
    return issues


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    board = board_input(args.path, ctx)
    other = None if args.against is None else board_input(args.against, ctx)
    template, name = template_of(args.template, ctx)
    if args.source == "kicad":
        _refuse_kicad(board)
    design, evidence = _model(board)
    rules = template.bom
    parts, lines = _lines(design, rules)
    header = [column.name for column in rules.columns]
    cells = bom.table(lines, rules)
    footprints = 0 if design.board is None else len(design.board.footprints)
    result: dict[str, Any] = {
        "source": args.source,
        "template": name,
        "columns": header,
        "lines": objects(header, cells),
        "counts": {
            "parts": sum(line.quantity for line in lines),
            "lines": len(lines),
            "dnp": sum(1 for part in parts if part.dnp),
            "left_out": footprints - len(parts),
        },
    }
    if other is not None:
        before, other_evidence = _model(other)
        evidence = Evidence.combine(evidence, other_evidence)
        result["changes"] = [
            {"key": list(c.key), "change": c.change, "a_refs": list(c.a_refs), "b_refs": list(c.b_refs)}
            for c in bom.difference(_lines(before, rules)[1], lines)
        ]
    return Result(
        result=result,
        issues=tuple(_missing_properties(parts, rules)),
        evidence=evidence,
        input=board.ref(),
        writes=planned(args.out, "bom", header, cells, template.csv),
    )


_EXAMPLE = (EXAMPLE_BOARD, "--source", "model")
COMMAND = Command(
    name="bom",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=_EXAMPLE,
    mutation_example_args=(*_EXAMPLE, "--out", "bom.csv"),
)

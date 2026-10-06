# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite bom PATH``: the bill of materials of a project, rendered through a column template the user
writes (capability cli-contract, "Bom command"; user guide ``docs/assembly.md``).

The ``kicad`` source, the default, asks ``kicad-cli`` for the parts of the project's schematic, on a copy:
KiCad is the judge of what a schematic holds. The ``model`` source lists the parts of the ``.fenolite/``
model of a built project, or of the board read for any other project, and runs no tool. Neither source
falls back to the other: a project without a schematic gets an error that names ``--source model``.

The table is JSON in the envelope; ``--out FILE`` also plans it as a CSV file.
"""

from __future__ import annotations

import argparse
import dataclasses
from pathlib import Path
from typing import Any

from fenolite.backends.kicad import bom as kicad_bom
from fenolite.backends.kicad.cli import BOM, CONFIG_DIR
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
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT, preflight
from fenolite.cli._manifest import needs_out, table_manifest
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.exports import bom, manifest
from fenolite.exports.assembly import BomTemplate, property_name
from fenolite.exports.codes import issue

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
        help="where the parts come from: kicad (the schematic, through kicad-cli) or "
        "model (the built model, or the board); default kicad",
    )
    parser.add_argument("--template", metavar="FILE", help="the column template (TOML); default: built in")
    parser.add_argument("-o", "--out", metavar="FILE", help="also write the table as a CSV file")
    parser.add_argument(
        "--manifest", action="store_true", help=f"also add FILE to {manifest.FILE_NAME} in its folder"
    )
    parser.add_argument("--against", metavar="OTHER", help="another project: also list what changed from it")
    parser.add_argument("--kicad-cli", dest="kicad_cli", metavar="PATH", help="the kicad-cli to run")
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SECONDS", help="per kicad-cli run (300)"
    )


Parts = tuple[bom.BomPart, ...]
SKIPPED_FOLDERS = ("-backups",)
"""Folder-name endings that hold no sheet of the project (KiCad's own backup folder)."""


def _schematic(board: BoardInput) -> Path:
    return board.path.with_suffix(".kicad_sch")


def _sheet_files(board: BoardInput) -> dict[str, Path]:
    """What ``kicad-cli`` gets next to the root schematic: the project file and every other ``.kicad_sch``
    under the project folder (the sheets of a hierarchy), by relative name. Hidden folders, KiCad's backup
    folder and the run's own configuration folder are left out."""
    root, schematic = board.root, _schematic(board)
    files: dict[str, Path] = {}
    project = board.path.with_suffix(".kicad_pro")
    if project.is_file():
        files[project.name] = project
    for path in sorted(root.rglob("*.kicad_sch")):
        parts = path.relative_to(root).parts
        folders = parts[:-1]
        if path == schematic or not path.is_file():
            continue
        if any(f.startswith(".") or f == CONFIG_DIR or f.endswith(SKIPPED_FOLDERS) for f in folders):
            continue
        files["/".join(parts)] = path
    return files


def _from_kicad(args: argparse.Namespace, board: BoardInput, fields: tuple[str, ...]) -> tuple[Parts, str]:
    """The parts that ``kicad-cli`` lists for the schematic of ``board``, and the tool's version."""
    schematic = _schematic(board)
    if not schematic.is_file():
        raise CliError(
            "FEN-3001",
            f"{board.path.name} has no schematic {schematic.name} next to it",
            hint=MODEL_HINT,
            where=board.path.name,
        )
    cli = preflight(args.kicad_cli, args.timeout, board.path)
    run = cli.export_bom(schematic, fields=fields, files=_sheet_files(board))
    data = run.outputs.get(BOM)
    if not run.ok or data is None:
        reason = "timed out" if run.outcome == "timeout" else f"exited with {run.returncode}"
        detail = run.stderr.strip().splitlines()[-1:] or [""]
        raise CliError(
            "FEN-3004",
            f"kicad-cli wrote no bill of materials for {schematic.name}: it {reason}"
            + (f" ({detail[0]})" if detail[0] else ""),
            hint="open the schematic in KiCad, or " + MODEL_HINT,
            where=schematic.name,
            retryable=run.outcome == "timeout",
        )
    rows = kicad_bom.read_bom_csv(data.decode("utf-8"), fields=fields, file=f"{schematic.name}:{BOM}")
    return bom.parts_from_kicad(rows), cli.version()


def _from_model(board: BoardInput) -> tuple[Parts, Evidence, int]:
    """The parts of the model, their evidence, and how many footprints of the board are not parts.

    The evidence is ``bom.EVIDENCE_MODEL`` for a built project that has a schematic, and ``INFERRED`` for
    any other input: only there has ``kicad-cli`` been compared with the model."""
    inferred = dataclasses.replace(bom.EVIDENCE_MODEL, level=Level.INFERRED)
    if board.built:
        design = built_model(board)
        evidence = bom.EVIDENCE_MODEL if _schematic(board).is_file() else inferred
    else:
        design, read_evidence = read_design(board)
        evidence = Evidence.combine(inferred, read_evidence)
    parts = bom.parts_from_model(design)
    footprints = 0 if design.board is None else len(design.board.footprints)
    return parts, evidence, footprints - len(parts)


def _parts(
    args: argparse.Namespace, board: BoardInput, fields: tuple[str, ...]
) -> tuple[Parts, Evidence, int | None]:
    """``(parts, evidence, left out)`` from the source that ``--source`` names. KiCad does not say what it
    leaves off a bill, so the ``kicad`` source gives no count."""
    if args.source == "model":
        return _from_model(board)
    parts, version = _from_kicad(args, board, fields)
    return parts, dataclasses.replace(bom.EVIDENCE_KICAD, oracle=f"kicad-cli {version}"), None


def _missing_properties(parts: Parts, template: BomTemplate) -> list[Issue]:
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
    needs_out("bom", args.manifest, args.out)
    board = board_input(args.path, ctx)
    other = None if args.against is None else board_input(args.against, ctx)
    template, name = template_of(args.template, ctx)
    rules = template.bom
    fields = bom.kicad_fields(rules) if args.source == "kicad" else ()
    parts, evidence, left_out = _parts(args, board, fields)
    lines = bom.group(parts, rules)
    header = [column.name for column in rules.columns]
    cells = bom.table(lines, rules)
    result: dict[str, Any] = {
        "source": args.source,
        "template": name,
        "columns": header,
        "lines": objects(header, cells),
        "counts": {
            "parts": sum(line.quantity for line in lines),
            "lines": len(lines),
            "dnp": sum(1 for part in parts if part.dnp),
            "left_out": left_out,
        },
    }
    if other is not None:
        before, other_evidence, _ = _parts(args, other, fields)
        evidence = Evidence.combine(evidence, other_evidence)
        result["changes"] = [
            {"key": list(c.key), "change": c.change, "a_refs": list(c.a_refs), "b_refs": list(c.b_refs)}
            for c in bom.difference(bom.group(before, rules), lines)
        ]
    issues = _missing_properties(parts, rules)
    writes = planned(args.out, "bom", header, cells, template.csv)
    if args.manifest:  # either source lists the parts of the board's project: the board names it
        writes, refused = table_manifest(
            writes, ctx, evidence=evidence.level.value, board=board.manifest_ref()
        )
        issues += refused
    return Result(result=result, issues=tuple(issues), evidence=evidence, input=board.ref(), writes=writes)


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

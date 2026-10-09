# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite impedance PATH [--estimate] [--out FILE]``: the impedance table of a project for the
fabricator (capability cli-contract, "Impedance command"; user guide ``docs/impedance.md``; change c0105).

The design is the ``.fenolite/`` model of a built project, else the KiCad board read with its project, whose
tuning profiles that a class names become targets. ``--estimate`` adds, for single-ended microstrip and
stripline rows, the ``INFERRED`` estimates of ``analysis.impedance``. The table is JSON in the envelope;
``--out FILE`` also plans it as a CSV file. No tool runs.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
from typing import Any

from fenolite.analysis import impedance as estimates
from fenolite.backends.kicad import pro
from fenolite.cli._assembly import BoardInput, board_input, built_model, read_design
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.exports import impedance as table
from fenolite.model.design import Design

HELP = (
    "the impedance table of a project for the fabricator, with --estimate rough estimates "
    "(writes FILE with --out)"
)


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = (
        HELP + "; the estimates omit solder mask, etch, frequency and loss and are advice only. "
        "See docs/impedance.md."
    )
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument(
        "--estimate",
        action="store_true",
        help="add the estimates of single-ended microstrip and stripline rows (INFERRED)",
    )
    parser.add_argument("-o", "--out", metavar="FILE", help="also write the table as a CSV file")


def _design(board: BoardInput, issues: list[Issue]) -> tuple[Design, Evidence, str]:
    """The design, the evidence of its source and the source's name: ``model`` or ``project``."""
    if board.built:
        return built_model(board), Evidence(Level.INFERRED), "model"
    design, evidence = read_design(board)
    project = board.path.with_suffix(".kicad_pro")
    if project.is_file():
        try:
            info = pro.read_project(project, issues=issues)
            design = pro.apply_project(design, info, issues=issues)
        except FormatError as error:
            raise CliError(
                "FEN-3004", f"{project.name} cannot be read: {error.message}", where=project.name
            ) from None
        evidence = Evidence.combine(evidence, pro.EVIDENCE)
    return design, evidence, "project"


def _row_object(row: table.ImpedanceRow) -> dict[str, Any]:
    return {
        "target": row.target,
        "kind": row.kind,
        "structure": row.structure,
        "layer": row.layer,
        "references": list(row.references),
        "ohms": row.ohms,
        "tolerance_percent": row.tolerance_percent,
        "width": row.width,
        "gap": row.gap,
        "heights": None if row.heights is None else list(row.heights),
        "epsilon_r": row.epsilon_r,
        "classes": list(row.classes),
        "nets": list(row.nets),
    }


def _ohms_mohm(text: str) -> int | None:
    return int(Decimal(text) * 1000) if text else None


def _estimates(
    design: Design, rows: tuple[table.ImpedanceRow, ...], objects: list[dict[str, Any]]
) -> tuple[list[tuple[int | None, int | None]], list[Issue], int, int]:
    """Each row's estimate (also set on its object), the issues, and the counts estimated and left out."""
    stackup = design.board.stackup if design.board is not None else None
    copper = table.copper_layers(design)
    found: list[tuple[int | None, int | None]] = []
    unsupported: list[str] = []
    missing: list[str] = []
    issues: list[Issue] = []
    for row, obj in zip(rows, objects, strict=True):
        geometry = next(
            g
            for t in (design.rules.impedance if design.rules is not None else ())
            if t.name == row.target
            for g in t.layers
            if g.layer == row.layer
        )
        value = estimates.estimate(stackup, copper, geometry)
        target = _ohms_mohm(row.ohms)
        suggested = None
        if value.mohm is not None and target is not None:
            suggested = estimates.solve_width(target, stackup, copper, geometry)
        obj["estimate"] = {
            "mohm": value.mohm,
            "suggested_width": suggested,
            "in_range": value.in_range,
            "form": value.form,
            "reason": value.reason,
        }
        found.append((value.mohm, suggested))
        label = f"{row.target} on {row.layer}"
        if value.reason in ("differential", "structure"):
            unsupported.append(label)
        elif value.reason == "stackup":
            missing.append(label)
        if value.mohm is None:
            continue
        if value.mixed:
            issues.append(
                table.issue(
                    "impedance.mixed-dielectric",
                    f"{label}: the height crosses dielectrics of different permittivity, combined in series "
                    f"as {value.epsilon_r}",
                    where=row.target,
                )
            )
        if value.in_range is False:
            issues.append(
                table.issue(
                    "impedance.out-of-range",
                    f"{label}: the row lies outside the range in which the source claims the accuracy of "
                    f"the {value.form} form",
                    where=row.target,
                )
            )
        if target is not None and row.tolerance_percent:
            band = Decimal(target) * Decimal(row.tolerance_percent) / 100
            if abs(Decimal(value.mohm) - Decimal(target)) > band:
                issues.append(
                    table.issue(
                        "impedance.off-target",
                        f"{label}: the estimate {table.milliohm_text(value.mohm)} Ω lies outside "
                        f"{row.ohms} Ω ± {row.tolerance_percent} %",
                        where=row.target,
                        hint=f"the width nearest the target is {table.millimetres(suggested)} mm (INFERRED)",
                    )
                )
    if unsupported:
        issues.append(
            table.issue(
                "impedance.estimate-unsupported",
                f"no closed form for {len(unsupported)} row(s): {', '.join(unsupported)}; Fenolite estimates "
                "single-ended microstrip and stripline only",
                where="impedance",
            )
        )
    if missing:
        issues.append(
            table.issue(
                "impedance.no-stackup",
                f"{len(missing)} row(s) need a stack-up with their layers and the permittivity of their "
                f"dielectrics: {', '.join(missing)}",
                where="impedance",
                hint="declare design.stackup() with epsilon_r on each dielectric",
            )
        )
    estimated = sum(1 for mohm, _ in found if mohm is not None)
    return found, issues, estimated, len(missing)


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    board = board_input(args.path, ctx)
    issues: list[Issue] = []
    design, evidence, source = _design(board, issues)
    rows = table.impedance_table(design)
    objects = [_row_object(row) for row in rows]
    targets = design.rules.impedance if design.rules is not None else ()
    counts: dict[str, int] = {"targets": len(targets), "rows": len(rows), "estimated": 0, "left_out": 0}
    if not targets:
        issues.append(
            table.issue("impedance.none", "the design holds no impedance target", where="impedance")
        )
    evidence = Evidence.combine(evidence, table.EVIDENCE)
    found: list[tuple[int | None, int | None]] | None = None
    if args.estimate:
        found, estimate_issues, counts["estimated"], counts["left_out"] = _estimates(design, rows, objects)
        issues += estimate_issues
        evidence = Evidence.combine(evidence, estimates.EVIDENCE)
        if counts["left_out"]:
            evidence = Evidence(Level.UNVERIFIED, hypotheses=evidence.hypotheses)
    writes: tuple[PlannedWrite, ...] = ()
    if args.out is not None:
        writes = (PlannedWrite(path=str(args.out), data=table.render_csv(rows, found), kind="impedance"),)
    project = board.path.with_suffix(".kicad_pro")
    return Result(
        result={"source": source, "columns": list(table.COLUMNS), "rows": objects, "counts": counts},
        issues=tuple(issues),
        evidence=evidence,
        input=board.ref(),
        writes=writes,
        depends=depends_on(
            ctx.cwd, board.path, project if project.is_file() and source == "project" else None
        ),
    )


COMMAND = Command(
    name="impedance",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_BOARD,),
    mutation_example_args=(EXAMPLE_BOARD, "--out", "impedance.csv"),
)

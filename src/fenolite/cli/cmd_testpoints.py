# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite testpoints PATH``: the test points, fiducials and non-plated holes of a board, which nets
a probe reaches, and what that says against the values the user passes (capability cli-contract,
"Testpoints command"; user guide ``docs/assembly.md``, "Test points").

The rows come from the board file, as ``pnp`` reads it, and no tool runs. A test point is a pad that
carries KiCad's test-point mark and a fiducial a footprint with a fiducial pad: marks are read, never
footprint names. The report is JSON in the envelope; ``--out FILE`` also plans it as a CSV file in the
frame of the template's placement table.
"""

from __future__ import annotations

import argparse
from typing import Any

from fenolite.backends.kicad import frame
from fenolite.backends.kicad.outline import board_outline
from fenolite.cli._assembly import board_input, planned, read_design, template_of
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli._manifest import needs_out, table_manifest
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.core.units import Nm, parse_length
from fenolite.exports import manifest, testpoints

HELP = (
    "the test points, fiducials and holes of a board, and its net coverage, from its pad marks "
    "(writes FILE with --out)"
)
SIDES = ("top", "bottom", "both")
KIND = "testpoints"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/assembly.md."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument(
        "--side", choices=SIDES, default="both", help="the side a probe comes from (default both)"
    )
    parser.add_argument(
        "--template", metavar="FILE", help="the template whose [placement] frame the CSV file uses"
    )
    parser.add_argument(
        "--min-coverage", metavar="PERCENT", help="an error below this share of covered nets (0 to 100)"
    )
    parser.add_argument(
        "--min-pitch", metavar="LENGTH", help="an error for two test points closer than this (1.27mm)"
    )
    parser.add_argument(
        "--min-fiducials", metavar="N", help="an error for a side with parts and fewer global fiducials"
    )
    parser.add_argument("-o", "--out", metavar="FILE", help="also write the report as a CSV file")
    parser.add_argument(
        "--manifest", action="store_true", help=f"also add FILE to {manifest.FILE_NAME} in its folder"
    )


def _integer(text: str | None, flag: str, low: int, high: int | None) -> int | None:
    if text is None:
        return None
    bounds = f"from {low} to {high}" if high is not None else f"of at least {low}"
    try:
        value = int(text)
    except ValueError:
        value = low - 1
    if value < low or (high is not None and value > high) or not text.strip().isdigit():
        raise CliError("FEN-2001", f"{flag}: expected an integer {bounds}, got {text!r}", where=flag)
    return value


def _pitch(text: str | None) -> Nm | None:
    if text is None:
        return None
    try:
        value = parse_length(text.strip())
    except ValueError as error:
        raise CliError(
            "FEN-2001", f"--min-pitch: {error}", where="--min-pitch", hint="a length with a unit: 1.27mm"
        ) from None
    if value <= 0:
        raise CliError("FEN-2001", "--min-pitch: the length must be positive", where="--min-pitch")
    return value


def _point(row: testpoints.TestPointRow) -> dict[str, Any]:
    return {
        "ref": row.ref,
        "path": row.path,
        "pad": row.pad,
        "net": row.net,
        "position": [row.position.x, row.position.y],
        "side": row.side,
        "access": row.access,
        "shape": row.shape,
        "size": [row.size.w, row.size.h],
        "drill": row.drill,
    }


def _fiducial(row: testpoints.FiducialRow) -> dict[str, Any]:
    return {
        "ref": row.ref,
        "path": row.path,
        "position": [row.position.x, row.position.y],
        "side": row.side,
        "scope": row.scope,
        "size": [row.size.w, row.size.h],
    }


def _hole(row: testpoints.HoleRow) -> dict[str, Any]:
    return {
        "ref": row.ref,
        "path": row.path,
        "position": [row.position.x, row.position.y],
        "drill": row.drill,
        "length": row.length,
        "tooling": row.tooling,
    }


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    needs_out(KIND, args.manifest, args.out)
    min_coverage = _integer(args.min_coverage, "--min-coverage", 0, 100)
    min_fiducials = _integer(args.min_fiducials, "--min-fiducials", 1, None)
    min_pitch = _pitch(args.min_pitch)
    board = board_input(args.path, ctx)
    template, name = template_of(args.template, ctx)
    design, read_evidence = read_design(board)
    rules = template.placement
    report = testpoints.report(design, frame.board_pads(design), side=args.side)
    issues: list[Issue] = list(
        testpoints.findings(
            report, design, min_coverage=min_coverage, min_pitch=min_pitch, min_fiducials=min_fiducials
        )
    )
    coverage = report.coverage
    result: dict[str, Any] = {
        "side": report.side,
        "test_points": [_point(row) for row in report.test_points],
        "fiducials": [_fiducial(row) for row in report.fiducials],
        "holes": [_hole(row) for row in report.holes],
        "coverage": {
            "eligible": coverage.eligible,
            "covered": coverage.covered,
            "uncovered": list(coverage.uncovered),
        },
        "counts": {
            "test_points": len(report.test_points),
            "fiducials_top": sum(1 for row in report.fiducials if row.side == "top"),
            "fiducials_bottom": sum(1 for row in report.fiducials if row.side == "bottom"),
            "holes": len(report.holes),
            "tooling_holes": sum(1 for row in report.holes if row.tooling),
        },
        "template": name,
        "units": rules.units,
        "origin": rules.origin,
        "y_axis": rules.y_axis,
    }
    evidence = Evidence.combine(testpoints.EVIDENCE, read_evidence)
    writes = ()
    if args.out is not None and not any(found.severity == "error" for found in issues):
        cells = testpoints.csv_table(report, rules, outline=board_outline(design), issues=issues)
        if not any(found.severity == "error" for found in issues):
            writes = planned(args.out, KIND, testpoints.CSV_HEADER, cells, template.csv)
    if args.manifest and writes:
        writes, refused = table_manifest(
            writes, ctx, evidence=evidence.level.value, board=board.manifest_ref()
        )
        issues += refused
    return Result(result=result, issues=tuple(issues), evidence=evidence, input=board.ref(), writes=writes)


COMMAND = Command(
    name="testpoints",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    paged="test_points",
    example_args=(EXAMPLE_BOARD,),
    mutation_example_args=(EXAMPLE_BOARD, "--out", "testpoints.csv"),
)

__all__ = ["COMMAND"]

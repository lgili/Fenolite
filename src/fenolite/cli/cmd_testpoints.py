# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite testpoints PATH``: the test points, fiducials and non-plated holes of a board, which nets
a probe reaches, and what that says against the values the user passes (capability cli-contract,
"Testpoints command"; user guide ``docs/assembly.md``, "Test points").

The rows come from the board file, as ``pnp`` reads it, and no tool runs. A test point is a pad that
carries KiCad's test-point mark and a fiducial a footprint with a fiducial pad: marks are read, never
footprint names. The report is JSON in the envelope; ``--out FILE`` also plans it as a CSV file in the
frame of the template's placement table.

``--place --side top|bottom`` adds a probe for every eligible net that the side does not reach
(``exports.testpoint_place``; capability assembly-test-features, "Test-point placement"; change c0229):
a board-only footprint of ``design.test_point`` and its track, checked with Fenolite's copper check before
the board is written under the mutation protocol, and with ``kicad-cli`` DRC before and after on ``--drc``.
The report then describes the board as it would be written.
"""

from __future__ import annotations

import argparse
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad import frame
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.cli import KicadCli, KicadCliError
from fenolite.backends.kicad.mod import prepare_authored_definition
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.pcb import read_board, source_info, write_board
from fenolite.cli._assembly import BoardInput, board_input, planned, read_design, template_of
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT, preflight
from fenolite.cli._manifest import needs_out, table_manifest
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.place_reuse import CopperChecker, files_beside, project_beside
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm, parse_length
from fenolite.dsl import assembly
from fenolite.exports import manifest, testpoints
from fenolite.exports import testpoint_place as place
from fenolite.exports.codes import issue
from fenolite.model.design import Design
from fenolite.silk.board import silkscreen_ink
from fenolite.tidy.edits import fresh_clashes

HELP = (
    "the test points, fiducials and holes of a board, and its net coverage, from its pad marks "
    "(writes FILE with --out)"
)
SIDES = ("top", "bottom", "both")
KIND = "testpoints"
CLEARANCE_FLOOR: Nm = 200_000
"""The least clearance the placement keeps to other copper and holes, whatever the project says: a Fenolite
choice, so that a board without a project file is not judged with no clearance at all."""
LIBRARY_TYPES = frozenset({"lib_footprint_issues", "lib_footprint_mismatch"})
"""DRC types about the footprint library table, left out of the comparison of ``--drc``: a probe's library
``Fenolite_Assembly`` is in no table of an edited board (``H-K-TP-PLACE``)."""
PLACE_ONLY = ("grid", "reach", "size", "nets", "drc", "kicad_cli")


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
        "--place", action="store_true", help="add a probe and its track for each net --side does not reach"
    )
    parser.add_argument("--grid", metavar="LENGTH", help="with --place, the grid of probe sites (2.54mm)")
    parser.add_argument(
        "--reach", metavar="LENGTH", help="with --place, the farthest site from the net (5mm)"
    )
    parser.add_argument("--size", metavar="LENGTH", help="with --place, the probe pad's diameter (1mm)")
    parser.add_argument(
        "--nets", action="append", metavar="GLOB", help="with --place, only these nets (repeatable)"
    )
    parser.add_argument("--drc", action="store_true", help="with --place, kicad-cli DRC before and after")
    parser.add_argument(
        "--kicad-cli", dest="kicad_cli", metavar="PATH", help="kicad-cli binary or docker:<image> for --drc"
    )
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


def _pitch(text: str | None, flag: str = "--min-pitch") -> Nm | None:
    if text is None:
        return None
    try:
        value = parse_length(text.strip())
    except ValueError as error:
        raise CliError(
            "FEN-2001", f"{flag}: {error}", where=flag, hint="a length with a unit: 1.27mm"
        ) from None
    if value <= 0:
        raise CliError("FEN-2001", f"{flag}: the length must be positive", where=flag)
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


@dataclass(frozen=True, slots=True)
class _Placing:
    """What ``--place`` gives the report: the board as it would be written, ``result.place``, the issues,
    the evidence, the board write (``None`` when nothing is placed) and the project files beside the board."""

    design: Design
    result: dict[str, Any]
    issues: tuple[Issue, ...]
    evidence: Evidence
    write: PlannedWrite | None
    beside: dict[str, Path]


def _drc_counts(report: DrcReport) -> Counter[str]:
    return Counter(
        found.type
        for found in (*report.violations, *report.unconnected_items)
        if not found.excluded and found.type not in LIBRARY_TYPES
    )


def _drc(
    cli: KicadCli, board_path: Path, beside: dict[str, Path], placed: bytes
) -> tuple[dict[str, object], list[Issue], Evidence | None]:
    """``kicad-cli`` DRC on the board as it is and as ``--place`` would write it, in copies."""
    others: dict[str, Path | bytes] = {path.name: path for path in beside.values()}
    runs: list[DrcReport] = []
    for board_bytes in (None, placed):
        files = dict(others) if board_bytes is None else {**others, board_path.name: board_bytes}
        run = cli.drc(board_path, files=files)  # type: ignore[arg-type]
        if run.report is None:
            raise KicadCliError("kicad-cli wrote no DRC report", run.run)
        runs.append(run.report)
    before, after = (_drc_counts(report) for report in runs)
    grown = sorted(kind for kind in after if after[kind] > before.get(kind, 0))
    version = cli.version()
    found = [
        issue(
            "testpoint.drc-new",
            f"kicad-cli {version} DRC finds {after[kind]} {kind} on the board with the probes and "
            f"{before.get(kind, 0)} on the board as it is; nothing is written",
            where=kind,
            hint="report the board: every probe and track passed Fenolite's own copper check",
        )
        for kind in grown
    ]
    result: dict[str, object] = {
        "tool_version": version,
        "before": dict(sorted(before.items())),
        "after": dict(sorted(after.items())),
        "new": grown,
    }
    evidence = None if grown else Evidence(Level.KICAD_VERIFIED, f"kicad-cli {version}", (place.HYPOTHESIS,))
    return result, found, evidence


def _settings(args: argparse.Namespace, min_pitch: Nm | None, clearance: Nm, edge: Nm) -> place.Settings:
    return place.Settings(
        side=args.side,
        grid=_pitch(args.grid, "--grid") or place.DEFAULT_GRID,
        reach=_pitch(args.reach, "--reach") or place.DEFAULT_REACH,
        size=_pitch(args.size, "--size") or place.DEFAULT_SIZE,
        min_pitch=min_pitch or place.DEFAULT_MIN_PITCH,
        nets=tuple(args.nets or ("*",)),
        clearance=clearance,
        edge_clearance=edge,
    )


def _place(args: argparse.Namespace, ctx: Context, board: BoardInput, min_pitch: Nm | None) -> _Placing:
    """``--place``: the probes, checked, and the board to write (see the module)."""
    board_path = board.path
    if board_path.suffix != ".kicad_pcb":
        raise CliError(
            "FEN-2001", f"--place writes KiCad boards only, not {board_path.name}", where="--place"
        )
    cli = preflight(args.kicad_cli, DEFAULT_TIMEOUT, board_path) if args.drc else None
    text = board_path.read_bytes().decode("utf-8")
    issues: list[Issue] = []
    design = read_board(text, file=board_path.name, issues=issues)
    backend = KicadBackend()
    beside = files_beside(board_path)
    project = project_beside(board_path, beside)
    rules = backend.design_rules(design, project, issues=[])
    classes = {cls.id: cls for cls in rules.design.circuit.netclasses}
    clearance = max(
        CLEARANCE_FLOOR,
        rules.min_clearance or 0,
        *(cls.clearance for cls in classes.values() if cls.clearance is not None),
    )
    widths = {
        net.name: width
        for net in rules.design.circuit.nets
        if (cls := classes.get(net.netclass_id or "")) is not None and (width := cls.track_width)
    }
    settings = _settings(args, min_pitch, clearance, max(rules.min_edge_clearance or 0, clearance))
    pads = backend.board_pads(design, issues=issues)
    extents = backend.placed_extents(design, issues=issues)
    edges = backend.board_edges(design, issues=issues)
    before = testpoints.report(design, pads, side=settings.side)
    footprint = prepare_authored_definition(
        assembly.test_point_footprint(settings.size, shape="circle", drill=None, courtyard=None).definition
    )
    ink = silkscreen_ink(design, pads=pads, extents=extents, edges=edges, side=settings.side)
    outcome = place.place_probes(
        design, pads, extents, edges, before, settings, footprint=footprint, widths=widths, ink=ink
    )
    issues.extend(outcome.issues)
    checker = CopperChecker(project, issues)
    fresh = fresh_clashes(checker(design), checker(outcome.design)) if outcome.probes else ()
    named = {item for clash in fresh for item in clash.items}
    failed = [probe for probe in outcome.probes if named & set(outcome.items[probe.ref])]
    for probe in failed:
        clash = next(c for c in fresh if set(c.items) & set(outcome.items[probe.ref]))
        issues.append(
            issue(
                "testpoint.check-failed",
                f"probe {probe.ref} of net {probe.net} is not written: Fenolite's copper check finds "
                f"{clash.code} on {clash.layer} with it",
                where=probe.net,
                hint="a clearance rule of the project is larger than the clearance of the search; report it",
            )
        )
    probes = [probe for probe in outcome.probes if probe not in failed]
    placed, _ = (
        place.write_probes(design, probes, footprint, settings.side) if failed else (outcome.design, {})
    )
    evidence = place.EVIDENCE
    drc: dict[str, object] | None = None
    write: PlannedWrite | None = None
    if probes:
        source = source_info(design)
        major = source.major if source is not None and source.major is not None else ctx.kicad_target
        board_text = write_board(placed, target=major, allow_lossy=ctx.allow_lossy).text
        if cli is not None:
            drc, drc_issues, drc_evidence = _drc(cli, board_path, beside, board_text.encode("utf-8"))
            issues.extend(drc_issues)
            evidence = drc_evidence or evidence
        write = PlannedWrite(os.path.relpath(board_path, ctx.cwd), board_text.encode("utf-8"), "kicad_pcb")
        issues.append(
            issue(
                "testpoint.board-only",
                f"{len(probes)} probe(s) are footprints of the board only, without fenolite.path: a rebuild "
                "keeps them and their tracks (layout.board-only)",
                where=",".join(probe.ref for probe in probes),
                hint="to author them in the design script instead, add design.test_point() calls and delete "
                "the probes from the board",
            )
        )
    after = testpoints.report(placed, backend.board_pads(placed), side=settings.side)
    result: dict[str, Any] = {
        "side": settings.side,
        "grid": settings.grid,
        "reach": settings.reach,
        "size": settings.size,
        "min_pitch": settings.min_pitch,
        "clearance": settings.clearance,
        "edge_clearance": settings.edge_clearance,
        "nets": list(settings.nets),
        "before": {"eligible": before.coverage.eligible, "covered": before.coverage.covered},
        "after": {"eligible": after.coverage.eligible, "covered": after.coverage.covered},
        "probes": [probe.to_json() for probe in probes],
        "unplaced": [row.to_json() for row in outcome.unplaced],
        "drc": drc,
    }
    return _Placing(placed, result, tuple(issues), evidence, write, beside)


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    needs_out(KIND, args.manifest, args.out)
    min_coverage = _integer(args.min_coverage, "--min-coverage", 0, 100)
    min_fiducials = _integer(args.min_fiducials, "--min-fiducials", 1, None)
    min_pitch = _pitch(args.min_pitch)
    if not args.place:
        for option in PLACE_ONLY:
            if getattr(args, option):
                flag = "--" + option.replace("_", "-")
                raise CliError("FEN-2001", f"{flag} needs --place", where=flag)
    elif args.side == "both":
        raise CliError(
            "FEN-2001", "--place needs --side top or --side bottom", where="--side", hint="add --side bottom"
        )
    board = board_input(args.path, ctx)
    template, name = template_of(args.template, ctx)
    placing: _Placing | None = None
    if args.place:
        placing = _place(args, ctx, board, min_pitch)
        design, read_evidence = placing.design, placing.evidence
    else:
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
    writes: tuple[PlannedWrite, ...] = ()
    depends: tuple[str, ...] = ()
    if placing is not None:
        issues = [*placing.issues, *issues]
        result["place"] = placing.result
        depends = depends_on(ctx.cwd, board.path, *placing.beside.values())
        if placing.write is not None and not any(found.severity == "error" for found in issues):
            writes = (placing.write,)
    if args.out is not None and not any(found.severity == "error" for found in issues):
        cells = testpoints.csv_table(report, rules, outline=board_outline(design), issues=issues)
        if not any(found.severity == "error" for found in issues):
            writes += planned(args.out, KIND, testpoints.CSV_HEADER, cells, template.csv)
    if args.manifest and writes:
        writes, refused = table_manifest(
            writes, ctx, evidence=evidence.level.value, board=board.manifest_ref()
        )
        issues += refused
    return Result(
        result=result,
        issues=tuple(issues),
        evidence=evidence,
        input=board.ref(),
        writes=writes,
        depends=depends,
    )


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

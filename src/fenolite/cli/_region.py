# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite render PATH --region X1,Y1,X2,Y2 --out DIR``: one rectangle of the board drawn by Fenolite
from the model into ``DIR/region.svg``, without a tool (change c0211; capability manufacturing-exports,
"Region renders"; ``docs/cli-contract.md``, "render"; ``docs/exports.md``, "Region renders")."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
from pathlib import Path, PurePosixPath
from typing import Any

from fenolite.analysis.boundary import board_boundary
from fenolite.analysis.connectivity import connectivity
from fenolite.analysis.crossings import Cut, analyze_crossings
from fenolite.analysis.pour import DEFAULT_GRID_NM, pour_copper
from fenolite.analysis.region import EVIDENCE, Region, check_grid, draw_region, mm
from fenolite.backends import registry
from fenolite.backends.base import BoardFrame, BoardPad
from fenolite.backends.kicad.projectset import project_set, resolve_board
from fenolite.cli._kicadtool import board_format
from fenolite.cli._manifest import FENOLITE, FENOLITE_TOOL, with_manifest
from fenolite.cli.api import Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.core.units import Nm, parse_length
from fenolite.exports import manifest
from fenolite.exports.codes import issue
from fenolite.model.design import Design

REGION_FILE = "region.svg"
MANIFEST_KIND = "render"
MIN_WIDTH, MAX_WIDTH = 64, 8192


def register_region(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("region (drawn by Fenolite from the model, no tool)")
    group.add_argument(
        "--region",
        metavar="X1,Y1,X2,Y2",
        help=f"draw this rectangle of the board into DIR/{REGION_FILE}, lengths with units: 0mm,0mm,9mm,9mm",
    )
    group.add_argument("--nets", action="store_true", help="with --region: label each pad with its net")
    group.add_argument("--open", action="store_true", help="with --region: draw the open connections")
    group.add_argument("--grid", metavar="LENGTH", help="with --region: the grid step (default: automatic)")
    group.add_argument(
        "--cut",
        action="append",
        default=[],
        metavar="X1,Y1,X2,Y2",
        help="with --region: a barrier cut and its ways per layer, as analyze --kinds crossings (repeatable)",
    )
    group.add_argument(
        "--cut-width", metavar="LENGTH", help="with --cut: the width of a track to fit (default: its class's)"
    )
    group.add_argument(
        "--cut-clearance",
        metavar="LENGTH",
        help="with --cut: the clearance of a new track (default: its class's)",
    )


def _four(text: str, option: str) -> tuple[Nm, Nm, Nm, Nm]:
    parts = text.split(",")
    if len(parts) != 4:
        raise CliError(
            "FEN-2001",
            f"{option}: {text!r} is not X1,Y1,X2,Y2",
            where=option,
            hint=f"{option} 0mm,0mm,20mm,20mm",
        )
    try:
        x1, y1, x2, y2 = (parse_length(part.strip()) for part in parts)
    except ValueError as error:
        raise CliError(
            "FEN-2001", f"{option}: {error}", where=option, hint="lengths need a unit: 10mm"
        ) from None
    return x1, y1, x2, y2


def parse_region(text: str) -> Region:
    """The rectangle of ``--region``, its corners in either order; one of no area exits 2."""
    x1, y1, x2, y2 = _four(text, "--region")
    if x1 == x2 or y1 == y2:
        raise CliError("FEN-2001", f"--region: {text!r} has no area", where="--region")
    return Region(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))


def _cuts(values: list[str]) -> tuple[Cut, ...]:
    cuts: list[Cut] = []
    for text in values:
        x1, y1, x2, y2 = _four(text, "--cut")
        if (x1, y1) == (x2, y2):
            raise CliError("FEN-2001", f"--cut: {text!r} has two equal ends", where="--cut")
        cuts.append(Cut(text, Point(x1, y1), Point(x2, y2)))
    return tuple(cuts)


def _positive(text: str | None, option: str) -> Nm | None:
    if text is None:
        return None
    try:
        value = parse_length(text.strip())
    except ValueError as error:
        raise CliError(
            "FEN-2001", f"{option}: {error}", where=option, hint="lengths need a unit: 0.2mm"
        ) from None
    if value <= 0:
        raise CliError("FEN-2001", f"{option}: must be above 0", where=option)
    return value


def _point(point: Point) -> dict[str, int]:
    return {"x": point.x, "y": point.y}


def run_region(args: argparse.Namespace, ctx: Context) -> Result:
    if not MIN_WIDTH <= args.width <= MAX_WIDTH:
        raise CliError(
            "FEN-2001", f"--width {args.width} is outside {MIN_WIDTH}..{MAX_WIDTH}", where="--width"
        )
    region = parse_region(args.region)
    grid: int | None = None
    if args.grid is not None:
        try:
            grid = parse_length(args.grid.strip())
            check_grid(region, grid)
        except ValueError as error:
            raise CliError("FEN-2001", f"--grid: {error}", where="--grid", hint="--grid 1mm") from None
    cuts = _cuts(args.cut)
    track = {
        name: _positive(getattr(args, f"cut_{name}"), f"--cut-{name}") for name in ("width", "clearance")
    }
    for name, value in track.items():
        if value is not None and not cuts:
            raise CliError("FEN-2001", f"--cut-{name} needs --cut", where=f"--cut-{name}")
    given = Path(args.path)
    board = resolve_board(given if given.is_absolute() else ctx.cwd / given)
    project = project_set(board)
    backend = registry.for_path(board)
    if backend is None:
        raise CliError("FEN-2001", f"no backend reads {board.name}", hint="pass a board file")
    read = backend.read(board)
    design = read.content
    if not isinstance(design, Design) or design.board is None:
        raise CliError("FEN-2001", f"{board.name} is not a board", hint="pass a board file")
    issues: list[Issue] = [found for found in read.issues if found.severity == "error"]
    pads: tuple[BoardPad, ...] | None = None
    if isinstance(backend, BoardFrame):
        pads = backend.board_pads(design, issues=[])
    boundary = board_boundary(design.board)
    ctx.progress.step("pour")
    pour = pour_copper(design, pads=pads, boundary=boundary, grid=DEFAULT_GRID_NM)
    ctx.progress.done("pour")
    evidences: list[Evidence] = [EVIDENCE]
    opened = None
    if args.open:
        opened = connectivity(design, pads=pads, pour=pour)
        issues += opened.issues
        evidences.append(opened.evidence)
    crossings = None
    if cuts:
        crossings = analyze_crossings(
            design,
            pads=pads,
            cuts=cuts,
            boundary=boundary,
            width=track["width"],
            clearance=track["clearance"],
        )
        issues += [
            dataclasses.replace(found, hint="pass --cut-width and --cut-clearance")
            if found.code == "analysis.input-missing"
            else found
            for found in crossings.issues
        ]
        evidences.append(crossings.evidence)
    drawing = draw_region(
        design,
        region=region,
        pads=pads,
        boundary=boundary,
        pour=pour,
        grid=grid,
        nets=args.nets,
        opened=opened,
        crossings=crossings,
        width_px=args.width,
    )
    box = f"{mm(region.x0)},{mm(region.y0)},{mm(region.x1)},{mm(region.y1)} mm"
    if not any(count for name, count in drawing.counts.items() if name not in ("grid", "edge")):
        issues.append(
            issue(
                "render.region-empty",
                f"the region {box} holds no copper, hole or open connection of the board",
                where="--region",
                hint="check the corners and their units against the board's coordinates (fenolite inspect)",
            )
        )
    for zone in drawing.zones:
        if zone.state != "saved_fill":
            issues.append(
                issue(
                    "render.copper-simulated",
                    f"the zone {zone.where} on {zone.layer} is drawn as {zone.state} ({zone.reason}), "
                    "not as a saved fill",
                    where=zone.where,
                    hint="run fenolite fill to store the fill KiCad computes",
                )
            )
    out = PurePosixPath(Path(args.out).as_posix())
    data = drawing.svg
    writes: list[PlannedWrite] = [PlannedWrite((out / REGION_FILE).as_posix(), data, "svg")]
    source = board.read_bytes()
    sha = hashlib.sha256(source).hexdigest()
    number = board_format(board)
    evidence = Evidence.combine(*evidences)
    if args.manifest:
        entry = manifest.file_entry(
            REGION_FILE,
            MANIFEST_KIND,
            data,
            evidence=evidence.level.value,
            from_={"board": sha},
            tool=FENOLITE,
        )
        merged, refused = with_manifest(
            writes,
            args.out,
            ctx,
            [entry],
            board=manifest.BoardRef(project.board, sha, number),
            tool=FENOLITE_TOOL,
        )
        writes = list(merged)
        issues += refused
    view = {
        "path": REGION_FILE,
        "kind": "svg",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    result: dict[str, Any] = {
        "board": project.board,
        "out": str(args.out),
        "views": [view],
        "tool_version": None,
        "region": {
            "x0": region.x0,
            "y0": region.y0,
            "x1": region.x1,
            "y1": region.y1,
            "grid": drawing.grid,
            "counts": dict(drawing.counts),
            "copper": sorted({zone.state for zone in drawing.zones}),
            "zones": [
                {"zone": z.where, "net": z.net, "layer": z.layer, "state": z.state, "reason": z.reason}
                for z in drawing.zones
            ],
            "pour_grid": pour.grid,
            "open": [
                {
                    "net": net,
                    "a": {"where": link.a.where, **_point(link.a.position)},
                    "b": {"where": link.b.where, **_point(link.b.position)},
                    "length": link.length,
                }
                for net, link in drawing.open
            ],
            "cuts": [
                {"cut": row.cut, "supply": row.supply, "open": row.open, "routed": row.routed}
                for row in (crossings.rows if crossings is not None else ())
            ],
        },
    }
    return Result(
        result=result,
        issues=tuple(issues),
        evidence=evidence,
        input=InputRef(
            path=board.name,
            sha256=sha,
            kind="kicad_pcb",
            format_version=None if number is None else str(number),
        ),
        writes=tuple(writes),
        depends=depends_on(ctx.cwd, board, *project.files.values()),
    )


__all__ = ["REGION_FILE", "parse_region", "register_region", "run_region"]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite analyze PATH``: current capacity, clearance and creepage of a board (capability
board-analyses, "Analyze command"; ``docs/analyses.md``; ``docs/cli-contract.md``, "analyze").

The command reads the board through the backend that detects it, measures, and judges the measures only
against the requirements the user gives. It runs no tool and writes no file. Fenolite assumes no
thickness, no temperature rise and no requirement value.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from fenolite.analysis import EVIDENCE
from fenolite.analysis.boundary import board_boundary
from fenolite.analysis.copper import ARC_TOL_NM
from fenolite.analysis.current import analyze_current
from fenolite.analysis.distance import analyze_distances
from fenolite.analysis.report import AnalysisReport, sorted_issues
from fenolite.analysis.requirements import Requirements, load_requirements
from fenolite.backends import registry
from fenolite.backends.base import BoardFrame, BoardPad
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence
from fenolite.core.units import Nm, parse_length
from fenolite.model.design import Design

HELP = "measure current capacity, clearance and creepage of a board (read-only)"
KINDS = ("current", "clearance", "creepage")
ALL_LAYERS = "*"
_CLEARANCE_CODES = ("analysis.clearance-below", "analysis.clearance-undecided", "analysis.embedded-below")
_CREEPAGE_CODES = ("analysis.creepage-below", "analysis.creepage-undecided")


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = (
        HELP + ". Fenolite measures and the user decides: no reply claims conformance to a standard, and "
        "findings exist only against the requirements you give; see docs/analyses.md."
    )
    parser.add_argument("path", metavar="PATH", help="a board file that a backend reads")
    parser.add_argument(
        "--kinds", default=None, metavar="K,K", help=f"analyses to run (default: all): {','.join(KINDS)}"
    )
    parser.add_argument(
        "--requirements", default=None, metavar="FILE", help="your requirements, a TOML file of integers"
    )
    parser.add_argument(
        "--temp-rise", default=None, metavar="KELVIN", help="temperature rise for the capacity, e.g. 10"
    )
    parser.add_argument(
        "--copper-thickness",
        action="append",
        default=[],
        metavar="[LAYER=]LENGTH",
        help="copper thickness of every layer, or of one layer (repeatable), e.g. 35um or In1.Cu=18um",
    )
    parser.add_argument("--via-plating", default=None, metavar="LENGTH", help="plating of a via barrel")
    parser.add_argument("--board-thickness", default=None, metavar="LENGTH", help="thickness of the board")
    parser.add_argument(
        "--pair",
        action="append",
        nargs="+",
        default=[],
        metavar="NET",
        help="measure the distances of this pair of nets: --pair NET_A NET_B (repeatable)",
    )
    parser.add_argument(
        "--within", default=None, metavar="LENGTH", help="measure every pair of nets closer than this"
    )
    parser.add_argument(
        "--arc-tol", default=None, metavar="LENGTH", help="chord error of polygonised copper arcs"
    )


def _length(text: str, option: str) -> Nm:
    try:
        value = parse_length(text.strip())
    except ValueError as error:
        raise CliError(
            "FEN-2001", f"{option}: {error}", where=option, hint="lengths need a unit: 35um"
        ) from None
    if value <= 0:
        raise CliError("FEN-2001", f"{option}: must be above 0", where=option)
    return value


def _kinds(text: str | None) -> tuple[str, ...]:
    if text is None:
        return KINDS
    names = [name.strip() for name in text.split(",") if name.strip()]
    unknown = [name for name in names if name not in KINDS]
    if unknown or not names:
        raise CliError(
            "FEN-2001",
            f"--kinds: unknown kind {', '.join(unknown) or text!r}",
            where="--kinds",
            hint=f"kinds: {','.join(KINDS)}",
        )
    return tuple(kind for kind in KINDS if kind in names)


def _temp_rise(text: str | None) -> int | None:
    """Kelvin as a decimal number of at most three decimals, in millikelvin."""
    if text is None:
        return None
    hint = "a temperature rise in kelvin with at most three decimals: 10 or 12.5"
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        raise CliError(
            "FEN-2001", f"--temp-rise: cannot read {text!r}", where="--temp-rise", hint=hint
        ) from None
    scaled = value * 1000
    if not value.is_finite() or scaled != scaled.to_integral_value() or scaled <= 0:
        raise CliError("FEN-2001", f"--temp-rise: cannot use {text!r}", where="--temp-rise", hint=hint)
    return int(scaled)


def _copper_thickness(values: list[str]) -> dict[str, Nm] | None:
    if not values:
        return None
    found: dict[str, Nm] = {}
    for text in values:
        layer, eq, length = text.rpartition("=")
        found[layer.strip() if eq else ALL_LAYERS] = _length(length, "--copper-thickness")
    return found


def _pairs(values: list[list[str]]) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for names in values:
        if len(names) != 2 or names[0] == names[1]:
            raise CliError(
                "FEN-2001",
                f"--pair takes two different net names, got {' '.join(names)!r}",
                where="--pair",
                hint="--pair NET_A NET_B",
            )
        pairs.append((names[0], names[1]))
    return tuple(pairs)


def _requirements(name: str | None, cwd: Path) -> Requirements | None:
    if name is None:
        return None
    path = Path(name) if Path(name).is_absolute() else cwd / name
    try:
        return load_requirements(path.read_text(encoding="utf-8"), file=path.name)
    except (OSError, UnicodeDecodeError) as error:
        reason = error.strerror if isinstance(error, OSError) and error.strerror else type(error).__name__
        raise CliError(
            "FEN-3004", f"{path.name}: cannot read the requirements file: {reason}", where=path.name
        ) from None
    except FormatError as error:
        raise CliError("FEN-3004", str(error), where=error.locator or path.name) from None


def _json(value: Any) -> Any:
    """A record, a tuple or a point as JSON data, with the field names of the records."""
    if isinstance(value, Point):
        return {"x": value.x, "y": value.y}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _json(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in cast(Sequence[Any], value)]
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in cast(dict[Any, Any], value).items()}
    return value


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    kinds = _kinds(args.kinds)
    temp_rise = _temp_rise(args.temp_rise)
    copper_thickness = _copper_thickness(args.copper_thickness)
    via_plating = None if args.via_plating is None else _length(args.via_plating, "--via-plating")
    thickness = None if args.board_thickness is None else _length(args.board_thickness, "--board-thickness")
    within = None if args.within is None else _length(args.within, "--within")
    arc_tol = ARC_TOL_NM if args.arc_tol is None else _length(args.arc_tol, "--arc-tol")
    pairs = _pairs(args.pair)
    requirements = _requirements(args.requirements, ctx.cwd)

    given = Path(args.path)
    path = given if given.is_absolute() else ctx.cwd / given
    if not path.exists():
        raise CliError("FEN-3001", f"{args.path} does not exist", where=path.name)
    backend = registry.for_path(path)
    if backend is None:
        raise CliError("FEN-2001", f"no backend reads {path.name}", hint="pass a board file")
    read = backend.read(path)
    design = read.content
    if not isinstance(design, Design) or design.board is None:
        raise CliError("FEN-2001", f"{path.name} is not a board", hint="pass a board file")

    reports: list[AnalysisReport] = []
    issues: list[Issue] = [found for found in read.issues if found.severity == "error"]
    result: dict[str, Any] = {}
    summary: dict[str, Any] = {}
    boundary = board_boundary(design.board, thickness=thickness)
    if "current" in kinds:
        current = analyze_current(
            design,
            temp_rise_mk=temp_rise,
            copper_thickness=copper_thickness,
            via_plating=via_plating,
            requirements=requirements,
        )
        reports.append(current)
        issues += current.issues
        result["current"] = [_json(row) for row in current.rows]
        summary["current"] = _json(dict(current.summary))
    if "clearance" in kinds or "creepage" in kinds:
        pad_issues: list[Issue] = []
        pads: tuple[BoardPad, ...] | None = None
        if isinstance(backend, BoardFrame):
            pads = backend.board_pads(design, issues=pad_issues)
        distances = analyze_distances(
            design,
            pads=pads,
            boundary=boundary,
            pairs=pairs,
            within=within,
            requirements=requirements,
            arc_tol=arc_tol,
        )
        reports.append(distances)
        dropped = (() if "clearance" in kinds else _CLEARANCE_CODES) + (
            () if "creepage" in kinds else _CREEPAGE_CODES
        )
        issues += [found for found in distances.issues if found.code not in dropped]
        rows: list[dict[str, Any]] = []
        for row in distances.rows:
            data: dict[str, Any] = _json(row)
            if "clearance" not in kinds:
                del data["gaps"], data["clearance"]
            if "creepage" not in kinds:
                del data["creepage"]
            rows.append(data)
        result["distances"] = rows
        summary["distances"] = _json(dict(distances.summary))
    result["summary"] = summary
    result["inputs"] = {
        "kinds": list(kinds),
        "temp_rise_mk": temp_rise,
        "copper_thickness": copper_thickness,
        "via_plating": via_plating,
        "board_thickness": boundary.thickness,
        "pairs": [list(pair) for pair in pairs],
        "within": within,
        "arc_tol": arc_tol,
        "requirements": None if args.requirements is None else Path(args.requirements).name,
        "boundary": {"source": boundary.source, "band": boundary.band, "cutouts": len(boundary.cutouts)},
    }
    unique = sorted_issues(dict.fromkeys(issues))
    evidence = Evidence.combine(EVIDENCE, read.evidence, *(report.evidence for report in reports))
    raw = b"" if path.is_dir() else path.read_bytes()
    return Result(
        result=result,
        issues=unique,
        evidence=evidence,
        input=InputRef(
            path=path.name,
            sha256=hashlib.sha256(raw).hexdigest() if raw else None,
            kind="board",
            format_version=None,
        ),
    )


COMMAND = Command(
    name="analyze",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    example_args=(EXAMPLE_BOARD, "--kinds", "current", "--temp-rise", "10", "--copper-thickness", "35um"),
)

__all__ = ["COMMAND", "KINDS"]

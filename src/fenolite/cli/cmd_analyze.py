# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite analyze PATH``: current capacity, clearance and creepage of a board, and on request its
power paths, the insulation between its layers and the lengths of its nets (capability board-analyses,
"Analyze command", "Power and insulation kinds" and "Length kind in the analyze command";
``docs/analyses.md``; ``docs/cli-contract.md``, "analyze").

The command reads the board through the backend that detects it, measures, and judges the measures only
against the requirements the user gives. It runs no tool and writes no file. Fenolite assumes no
thickness, no temperature rise, no resistivity, no groove width and no requirement value.
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
from fenolite.analysis.boundary import OVERLAP_NEEDS_GEO, board_boundary
from fenolite.analysis.copper import ARC_TOL_NM
from fenolite.analysis.coupling import analyze_coupling
from fenolite.analysis.crossings import Cut, analyze_crossings
from fenolite.analysis.current import analyze_current
from fenolite.analysis.distance import analyze_distances
from fenolite.analysis.length import measure_lengths
from fenolite.analysis.pour import DEFAULT_GRID_NM, PourCopper, pour_copper
from fenolite.analysis.power import analyze_power
from fenolite.analysis.practice import (
    analyze_bodies,
    analyze_dead,
    analyze_decoupling,
    analyze_groups,
    analyze_relief,
)
from fenolite.analysis.report import AnalysisReport, sorted_issues
from fenolite.analysis.requirements import Requirements, load_requirements
from fenolite.analysis.returns import analyze_returns
from fenolite.analysis.shapes import analyze_balance, analyze_loops, analyze_necks, loop_areas
from fenolite.analysis.split import analyze_split
from fenolite.analysis.ties import Tie, analyze_ties, isolation_islands
from fenolite.backends import registry
from fenolite.backends.base import BoardFrame, BoardPad, LengthFacts, LengthSource, ProjectSet
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.coords import Point
from fenolite.core.errors import FenoliteError, FormatError, Issue
from fenolite.core.evidence import Evidence
from fenolite.core.units import Nm, parse_length
from fenolite.geometry.errors import BACKEND_UNAVAILABLE
from fenolite.model.design import Design

HELP = "measure current capacity, clearance and creepage of a board (read-only)"
"""The opt-in kinds are described with their options: power paths and insulation between layers."""
KINDS = ("current", "clearance", "creepage")
"""The kinds that run without ``--kinds``."""
OPT_IN_KINDS = (
    "power",
    "insulation",
    "length",
    "ties",
    "domains",
    "crossings",
    "returns",
    "decoupling",
    "connectivity",
    "bodies",
    "relief",
    "dead",
    "coupling",
    "necks",
    "loops",
    "balance",
)
POUR_KINDS = ("connectivity", "bodies", "relief", "dead", "necks", "loops", "balance")
"""The practice kinds that read the zones in their copper states (changes c0204 and c0213)."""
ALL_KINDS = (*KINDS, *OPT_IN_KINDS)
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
        "--kinds",
        default=None,
        metavar="K,K",
        help=f"analyses to run (default: {','.join(KINDS)}; on request: {','.join(OPT_IN_KINDS)})",
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
    parser.add_argument(
        "--path",
        dest="power_paths",
        action="append",
        nargs=2,
        default=[],
        metavar=("FROM", "TO"),
        help="with --kinds power: measure the copper between two sets of pads, each REF-PIN[,REF-PIN...] "
        "(repeatable); an estimate against your limits, not a simulation",
    )
    parser.add_argument(
        "--resistivity",
        default=None,
        metavar="NANOOHM_METRES",
        help="with --kinds power: the resistivity of your copper at your temperature, e.g. 17.2; "
        "Fenolite assumes none",
    )
    parser.add_argument(
        "--groove-width",
        default=None,
        metavar="LENGTH",
        help="with creepage: a groove narrower than this is bridged on the creepage path",
    )
    parser.add_argument(
        "--net",
        dest="length_nets",
        action="append",
        default=[],
        metavar="GLOB",
        help="with --kinds length or returns: the nets whose name matches this pattern (repeatable); a "
        "length total is counted as KiCad of --kicad-version counts it",
    )
    parser.add_argument(
        "--from",
        dest="length_from",
        action="append",
        default=[],
        metavar="REF",
        help="with --kinds length: measure the paths of a net from this part or pad, REF or REF-PIN "
        "(repeatable; default: the first pad of each net)",
    )
    parser.add_argument(
        "--tie",
        dest="tie_parts",
        action="append",
        default=[],
        metavar="REF",
        help="with --kinds ties: prove that this part (a net tie) is the only joint of its nets (repeatable)",
    )
    parser.add_argument(
        "--tie-item",
        dest="tie_items",
        action="append",
        default=[],
        metavar="ID[,ID...]",
        help="with --kinds ties: prove that these copper items (tracks, arcs, vias, zones; by id, uuid or "
        "locator) are the only joint of their net; one tie per option (repeatable)",
    )
    parser.add_argument(
        "--domains",
        default=None,
        metavar="A=GLOB,B=GLOB",
        help="with --kinds ties: two named groups of pads by REF-PIN pattern; a name may repeat",
    )
    parser.add_argument(
        "--sense",
        action="append",
        default=[],
        metavar="NET[,NET...]",
        help="with --kinds ties: sense nets whose copper may touch other nets only through a net-tie "
        "part (repeatable)",
    )
    parser.add_argument(
        "--cut",
        action="append",
        default=[],
        metavar="X1,Y1,X2,Y2",
        help="with --kinds crossings: a segment across a barrier, ends with units (repeatable)",
    )
    parser.add_argument(
        "--width",
        default=None,
        metavar="LENGTH",
        help="with --kinds crossings: the width of a track to fit (default: the narrowest class width)",
    )
    parser.add_argument(
        "--clearance",
        default=None,
        metavar="LENGTH",
        help="with --kinds crossings: the clearance of a new track (default: that of its class)",
    )
    parser.add_argument(
        "--reference",
        action="append",
        default=[],
        metavar="NET[,NET...]",
        help="with --kinds returns: the reference nets (default: every other net with a fill on the "
        "neighbouring layer) (repeatable)",
    )
    parser.add_argument(
        "--via-distance",
        default=None,
        metavar="LENGTH",
        help="with --kinds returns: a signal via farther than this from every reference via is a finding",
    )
    parser.add_argument(
        "--pour-grid",
        default=None,
        metavar="LENGTH",
        help="with a kind that pours zones (connectivity, bodies, relief, dead, necks, loops, balance) or "
        "--split: the cell of the raster of the copper (default 0.1mm)",
    )
    parser.add_argument(
        "--split",
        action="store_true",
        help="with --kinds power: the share of each track, fill and via in the path's current, on a raster",
    )
    parser.add_argument(
        "--loop-baseline",
        default=None,
        metavar="FILE",
        help="with --kinds loops: measure the same loops on this board and give the change",
    )
    parser.add_argument(
        "--dead-distance",
        default=None,
        metavar="LENGTH",
        help="with --kinds dead: copper farther than this from every pad of its net is a finding",
    )
    parser.add_argument(
        "--aggressor",
        action="append",
        default=[],
        metavar="GLOB",
        help="with --kinds coupling: the aggressor nets (repeatable; required)",
    )
    parser.add_argument(
        "--victim",
        action="append",
        default=[],
        metavar="GLOB",
        help="with --kinds coupling: the victim nets (repeatable; required)",
    )
    parser.add_argument(
        "--barrier",
        action="append",
        default=[],
        metavar="REF[,REF...]",
        help="with --kinds domains: parts (isolators, transformers) that separate the islands of nets "
        "(repeatable)",
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
    unknown = [name for name in names if name not in ALL_KINDS]
    if unknown or not names:
        raise CliError(
            "FEN-2001",
            f"--kinds: unknown kind {', '.join(unknown) or text!r}",
            where="--kinds",
            hint=f"kinds: {','.join(ALL_KINDS)}",
        )
    return tuple(kind for kind in ALL_KINDS if kind in names)


def _resistivity(text: str | None) -> int | None:
    """Nanoohm-metres as a decimal number of at most three decimals, in picoohm-metres."""
    if text is None:
        return None
    hint = "a resistivity in nanoohm-metres with at most three decimals: 17.2"
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        raise CliError(
            "FEN-2001", f"--resistivity: cannot read {text!r}", where="--resistivity", hint=hint
        ) from None
    scaled = value * 1000
    if not value.is_finite() or scaled != scaled.to_integral_value() or scaled <= 0:
        raise CliError("FEN-2001", f"--resistivity: cannot use {text!r}", where="--resistivity", hint=hint)
    return int(scaled)


def _paths(values: list[list[str]]) -> tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]:
    paths: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    for given in values:
        ends: list[tuple[str, ...]] = []
        for text in given:
            names = tuple(name.strip() for name in text.split(","))
            for name in names:
                ref, dash, pin = name.rpartition("-")
                if not dash or not ref or not pin:
                    raise CliError(
                        "FEN-2001",
                        f"--path: {name!r} is not a pad name REF-PIN",
                        where="--path",
                        hint="--path J1-1 U1-1, or --path J1-1,J1-2 U1-1",
                    )
            ends.append(names)
        paths.append((ends[0], ends[1]))
    return tuple(paths)


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


def _cuts(values: list[str]) -> tuple[Cut, ...]:
    cuts: list[Cut] = []
    for text in values:
        parts = text.split(",")
        if len(parts) != 4:
            raise CliError(
                "FEN-2001",
                f"--cut: {text!r} is not X1,Y1,X2,Y2",
                where="--cut",
                hint="--cut 10mm,20mm,27.78mm,20mm",
            )
        try:
            x1, y1, x2, y2 = (parse_length(part.strip()) for part in parts)
        except ValueError as error:
            raise CliError(
                "FEN-2001", f"--cut: {error}", where="--cut", hint="lengths need a unit: 10mm"
            ) from None
        if (x1, y1) == (x2, y2):
            raise CliError("FEN-2001", f"--cut: {text!r} has two equal ends", where="--cut")
        cuts.append(Cut(text, Point(x1, y1), Point(x2, y2)))
    return tuple(cuts)


def _list(values: list[str], option: str) -> tuple[str, ...]:
    """The comma-separated names of a repeatable option, in order, without repeats."""
    names: list[str] = []
    for text in values:
        parts = [name.strip() for name in text.split(",")]
        if not all(parts):
            raise CliError("FEN-2001", f"{option}: empty name in {text!r}", where=option)
        names += parts
    return tuple(dict.fromkeys(names))


def _domains(text: str | None) -> dict[str, tuple[str, ...]] | None:
    if text is None:
        return None
    found: dict[str, list[str]] = {}
    for part in text.split(","):
        name, eq, glob = part.partition("=")
        if not eq or not name.strip() or not glob.strip():
            raise CliError(
                "FEN-2001",
                f"--domains: {part!r} is not NAME=GLOB",
                where="--domains",
                hint="--domains PWR=Q*,CTL=U*",
            )
        found.setdefault(name.strip(), []).append(glob.strip())
    if len(found) != 2:
        raise CliError(
            "FEN-2001",
            f"--domains names {len(found)} domain(s); it takes two",
            where="--domains",
            hint="--domains PWR=Q*,CTL=U*",
        )
    return {name: tuple(globs) for name, globs in found.items()}


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


def _thickness_source(option: Nm | None, used: Nm | None) -> str | None:
    """Where the board thickness of the reply came from: ``option``, ``stackup`` or ``None``."""
    if option is not None:
        return "option"
    return "stackup" if used is not None else None


def _stackup_inputs(design: Design) -> dict[str, Any] | None:
    """``inputs.stackup``: the total and the copper thicknesses of the board's stack-up, or ``None``."""
    stackup = design.board.stackup if design.board is not None else None
    if stackup is None:
        return None
    copper = {entry.name: entry.thickness for entry in stackup.layers if entry.kind == "copper"}
    return {"thickness": stackup.thickness(), "copper": copper}


def _loop_baseline(
    name: str | None,
    cwd: Path,
    requirements: Requirements | None,
    grid: int,
    thickness: Nm | None,
    arc_tol: int,
) -> dict[str, int | None] | None:
    """The area of each ``[[loop]]`` row on the baseline board ``name``, read and poured as the board is."""
    if name is None:
        return None
    path = Path(name) if Path(name).is_absolute() else cwd / name
    if not path.exists():
        raise CliError("FEN-3001", f"{name} does not exist", where="--loop-baseline")
    backend = registry.for_path(path)
    design = backend.read(path).content if backend is not None else None
    if not isinstance(design, Design) or design.board is None:
        raise CliError("FEN-2001", f"--loop-baseline: {path.name} is not a board", where="--loop-baseline")
    pad_issues: list[Issue] = []
    pads = backend.board_pads(design, issues=pad_issues) if isinstance(backend, BoardFrame) else None
    boundary = board_boundary(design.board, thickness=thickness)
    pour = pour_copper(design, pads=pads, boundary=boundary, grid=grid, arc_tol=arc_tol)
    rows, _ = loop_areas(design, pads=pads, pour=pour, requirements=requirements)
    return {row.name: row.area_nm2 for row in rows}


def _project(board: Path) -> ProjectSet | None:
    """The project files next to a KiCad board, for the length facts; ``None`` when they cannot be set
    up, and the facts then count as without a project file."""
    from fenolite.backends.kicad.projectset import project_set

    try:
        return project_set(board)
    except (OSError, ValueError, FenoliteError):
        return None


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    kinds = _kinds(args.kinds)
    temp_rise = _temp_rise(args.temp_rise)
    copper_thickness = _copper_thickness(args.copper_thickness)
    via_plating = None if args.via_plating is None else _length(args.via_plating, "--via-plating")
    thickness = None if args.board_thickness is None else _length(args.board_thickness, "--board-thickness")
    within = None if args.within is None else _length(args.within, "--within")
    arc_tol = ARC_TOL_NM if args.arc_tol is None else _length(args.arc_tol, "--arc-tol")
    pairs = _pairs(args.pair)
    paths = _paths(args.power_paths)
    resistivity = _resistivity(args.resistivity)
    groove = None if args.groove_width is None else _length(args.groove_width, "--groove-width")
    ties = [Tie.of_part(ref) for ref in _list(args.tie_parts, "--tie")]
    ties += [Tie.of_items(_list([text], "--tie-item")) for text in args.tie_items]
    domains = _domains(args.domains)
    sense = _list(args.sense, "--sense")
    barriers = _list(args.barrier, "--barrier")
    cuts = _cuts(args.cut)
    track_width = None if args.width is None else _length(args.width, "--width")
    track_clearance = None if args.clearance is None else _length(args.clearance, "--clearance")
    reference = _list(args.reference, "--reference")
    via_distance = None if args.via_distance is None else _length(args.via_distance, "--via-distance")
    pour_grid = None if args.pour_grid is None else _length(args.pour_grid, "--pour-grid")
    dead_distance = None if args.dead_distance is None else _length(args.dead_distance, "--dead-distance")
    aggressors = _list(args.aggressor, "--aggressor")
    victims = _list(args.victim, "--victim")
    for option, given, kind in (
        ("--path", bool(paths), "power"),
        ("--resistivity", resistivity is not None, "power"),
        ("--split", bool(args.split), "power"),
        ("--loop-baseline", args.loop_baseline is not None, "loops"),
        ("--groove-width", groove is not None, "creepage"),
        ("--net", bool(args.length_nets) and "returns" not in kinds, "length"),
        ("--from", bool(args.length_from), "length"),
        ("--tie", bool(args.tie_parts), "ties"),
        ("--tie-item", bool(args.tie_items), "ties"),
        ("--domains", domains is not None, "ties"),
        ("--sense", bool(sense), "ties"),
        ("--barrier", bool(barriers), "domains"),
        ("--cut", bool(cuts), "crossings"),
        ("--width", track_width is not None, "crossings"),
        ("--clearance", track_clearance is not None, "crossings"),
        ("--reference", bool(reference), "returns"),
        ("--via-distance", via_distance is not None, "returns"),
        ("--dead-distance", dead_distance is not None, "dead"),
        ("--aggressor", bool(aggressors), "coupling"),
        ("--victim", bool(victims), "coupling"),
    ):
        if given and kind not in kinds:
            raise CliError(
                "FEN-2001",
                f"{option} needs the kind {kind}, which is not among --kinds",
                where=option,
                hint=f"add {kind} to --kinds",
            )
    for kind, given, needs in (
        ("ties", bool(ties or sense), "--tie, --tie-item or --sense"),
        ("domains", bool(barriers), "--barrier"),
        ("crossings", bool(cuts), "--cut"),
        ("returns", bool(args.length_nets), "--net"),
        ("coupling", bool(aggressors and victims), "--aggressor and --victim"),
    ):
        if kind in kinds and not given:
            raise CliError(
                "FEN-2001",
                f"the kind {kind} needs {needs}",
                where="--kinds",
                hint=f"add {needs.split(',')[0]}",
            )
    if pour_grid is not None and not set(POUR_KINDS) & set(kinds) and not args.split:
        raise CliError(
            "FEN-2001",
            f"--pour-grid needs --split or one of the kinds {', '.join(POUR_KINDS)}, none of which is given",
            where="--pour-grid",
            hint="add connectivity to --kinds",
        )
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
    if boundary.problem == OVERLAP_NEEDS_GEO and {"clearance", "creepage", "insulation", "crossings"} & set(
        kinds
    ):
        # the union of overlapping cut-outs and slots needs the geo extra (change c0167)
        raise CliError(
            "FEN-6001",
            f"{BACKEND_UNAVAILABLE}: the cut-outs and slots of the board outline overlap, and their union "
            "needs the geo extra",
            where=BACKEND_UNAVAILABLE,
            hint="pip install 'fenolite[geo]'",
        )
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
    pad_issues: list[Issue] = []
    pads: tuple[BoardPad, ...] | None = None
    if isinstance(backend, BoardFrame) and set(kinds) - {"current"}:
        pads = backend.board_pads(design, issues=pad_issues)
    if "clearance" in kinds or "creepage" in kinds or "insulation" in kinds:
        distances = analyze_distances(
            design,
            pads=pads,
            boundary=boundary,
            pairs=pairs,
            within=within,
            requirements=requirements,
            arc_tol=arc_tol,
            groove=groove,
            insulation="insulation" in kinds,
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
            if "insulation" not in kinds:
                del data["insulation"], data["sheets"]
            rows.append(data)
        result["distances"] = rows
        summary["distances"] = _json(dict(distances.summary))
    evidences: list[Evidence] = [report.evidence for report in reports]
    power = None
    if "power" in kinds:
        power = analyze_power(
            design,
            pads=pads,
            paths=paths,
            requirements=requirements,
            temp_rise_mk=temp_rise,
            copper_thickness=copper_thickness,
            via_plating=via_plating,
            resistivity_pohm_m=resistivity,
            arc_tol=arc_tol,
        )
        issues += power.issues
        evidences.append(power.evidence)
        result["power"] = [_json(row) for row in power.rows]
        summary["power"] = _json(dict(power.summary))
    if "length" in kinds:
        facts: LengthFacts | None = None
        fact_issues: list[Issue] = []
        if isinstance(backend, LengthSource):
            facts = backend.length_facts(
                design, project=_project(path), major=ctx.kicad_target, issues=fact_issues
            )
        lengths = measure_lengths(
            design, pads=pads, facts=facts, nets=tuple(args.length_nets), starts=tuple(args.length_from)
        )
        issues += [*fact_issues, *lengths.issues]
        evidences.append(lengths.evidence)
        result["lengths"] = [_json(row) for row in lengths.rows]
        result["pairs"] = [_json(row) for row in lengths.pairs]
        summary["length"] = _json(dict(lengths.summary))
    if "ties" in kinds:
        tied = analyze_ties(design, pads=pads, ties=ties, domains=domains, sense=sense, arc_tol=arc_tol)
        issues += tied.issues
        evidences.append(tied.evidence)
        result["ties"] = [_json(row) for row in tied.rows]
        result["sense"] = [_json(row) for row in tied.sense]
        summary["ties"] = dict(tied.summary)
    if "domains" in kinds:
        islands = isolation_islands(design, barriers=barriers)
        issues += islands.issues
        evidences.append(islands.evidence)
        result["domains"] = [_json(island) for island in islands.islands]
        summary["domains"] = {"islands": len(islands.islands)}
    if "crossings" in kinds:
        crossed = analyze_crossings(
            design,
            pads=pads,
            cuts=cuts,
            boundary=boundary,
            width=track_width,
            clearance=track_clearance,
            arc_tol=arc_tol,
        )
        issues += crossed.issues
        evidences.append(crossed.evidence)
        result["crossings"] = [_json(row) for row in crossed.rows]
        summary["crossings"] = dict(crossed.summary)
    if "returns" in kinds:
        returns = analyze_returns(
            design,
            pads=pads,
            nets=tuple(args.length_nets),
            reference=reference,
            via_distance=via_distance,
            arc_tol=arc_tol,
        )
        issues += returns.issues
        evidences.append(returns.evidence)
        result["returns"] = [_json(row) for row in returns.rows]
        summary["returns"] = dict(returns.summary)
    pour: PourCopper | None = None
    if set(POUR_KINDS) & set(kinds) or args.split:
        pour = pour_copper(
            design,
            pads=pads,
            boundary=boundary,
            grid=DEFAULT_GRID_NM if pour_grid is None else pour_grid,
            arc_tol=arc_tol,
        )
        result["pours"] = [_json(zone) for zone in pour.zones]
    if power is not None and pour is not None and args.split:
        split = analyze_split(
            design,
            pads=pads,
            pour=pour,
            power=power,
            copper_thickness=copper_thickness,
            via_plating=via_plating,
            resistivity_pohm_m=resistivity,
        )
        issues += split.issues
        evidences.append(split.evidence)
        result["split"] = [_json(row) for row in split.rows]
        summary["split"] = _json(dict(split.summary))
    if "decoupling" in kinds:
        decoupling = analyze_decoupling(
            design,
            pads=pads,
            pour=pour,
            requirements=requirements,
        )
        issues += decoupling.issues
        evidences.append(decoupling.evidence)
        result["decoupling"] = [_json(row) for row in decoupling.rows]
        summary["decoupling"] = dict(decoupling.summary)
    if "connectivity" in kinds and pour is not None:
        groups = analyze_groups(design, pads=pads, pour=pour)
        issues += groups.issues
        evidences.append(groups.evidence)
        result["connectivity"] = [_json(row) for row in groups.rows]
        summary["connectivity"] = dict(groups.summary)
    if "bodies" in kinds and pour is not None:
        extents = backend.placed_extents(design) if isinstance(backend, BoardFrame) else None
        bodies = analyze_bodies(design, pads=pads, pour=pour, extents=extents, requirements=requirements)
        issues += bodies.issues
        evidences.append(bodies.evidence)
        result["bodies"] = [_json(row) for row in bodies.rows]
        summary["bodies"] = dict(bodies.summary)
    if "relief" in kinds and pour is not None:
        relief = analyze_relief(
            design, pads=pads, pour=pour, requirements=requirements, copper_thickness=copper_thickness
        )
        issues += relief.issues
        evidences.append(relief.evidence)
        result["relief"] = [_json(row) for row in relief.rows]
        summary["relief"] = dict(relief.summary)
    if "dead" in kinds and pour is not None:
        dead = analyze_dead(design, pads=pads, pour=pour, distance=dead_distance)
        issues += dead.issues
        evidences.append(dead.evidence)
        result["dead"] = [_json(row) for row in dead.rows]
        summary["dead"] = dict(dead.summary)
    if "necks" in kinds and pour is not None:
        necks = analyze_necks(design, pour=pour, requirements=requirements)
        issues += necks.issues
        evidences.append(necks.evidence)
        result["necks"] = [_json(row) for row in necks.rows]
        summary["necks"] = dict(necks.summary)
    if "loops" in kinds and pour is not None:
        baseline = _loop_baseline(args.loop_baseline, ctx.cwd, requirements, pour.grid, thickness, arc_tol)
        loops = analyze_loops(design, pads=pads, pour=pour, requirements=requirements, baseline=baseline)
        issues += loops.issues
        evidences.append(loops.evidence)
        result["loops"] = [_json(row) for row in loops.rows]
        summary["loops"] = dict(loops.summary)
    if "balance" in kinds and pour is not None:
        balance = analyze_balance(design, pads=pads, pour=pour)
        issues += balance.issues
        evidences.append(balance.evidence)
        result["balance"] = [_json(row) for row in balance.rows]
        summary["balance"] = dict(balance.summary)
    if "coupling" in kinds:
        coupled = analyze_coupling(
            design,
            pads=pads,
            aggressors=aggressors,
            victims=victims,
            board_thickness=boundary.thickness,
            arc_tol=arc_tol,
        )
        issues += coupled.issues
        evidences.append(coupled.evidence)
        result["coupling"] = [_json(row) for row in coupled.rows]
        result["coupling_victims"] = [_json(row) for row in coupled.victims]
        summary["coupling"] = {**coupled.summary, "heights": dict(coupled.heights)}
    result["summary"] = summary
    result["inputs"] = {
        "kinds": list(kinds),
        "temp_rise_mk": temp_rise,
        "copper_thickness": copper_thickness,
        "via_plating": via_plating,
        "board_thickness": boundary.thickness,
        "board_thickness_source": _thickness_source(thickness, boundary.thickness),
        "stackup": _stackup_inputs(design),
        "pairs": [list(pair) for pair in pairs],
        "within": within,
        "arc_tol": arc_tol,
        "paths": [[list(start), list(end)] for start, end in paths],
        "resistivity_pohm_m": resistivity,
        "groove_nm": groove,
        "requirements": None if args.requirements is None else Path(args.requirements).name,
        "boundary": {"source": boundary.source, "band": boundary.band, "cutouts": len(boundary.cutouts)},
    }
    if "length" in kinds:
        result["inputs"] |= {
            "nets": list(args.length_nets),
            "from": list(args.length_from),
            "kicad_version": ctx.kicad_target,
        }
    if "ties" in kinds:
        result["inputs"] |= {
            "ties": [tie.name for tie in ties],
            "domains": None if domains is None else {name: list(globs) for name, globs in domains.items()},
            "sense": list(sense),
        }
    if "domains" in kinds:
        result["inputs"]["barriers"] = list(barriers)
    if "returns" in kinds:
        result["inputs"] |= {
            "nets": list(args.length_nets),
            "reference": list(reference),
            "via_distance": via_distance,
        }
    if pour is not None:
        result["inputs"]["pour_grid"] = pour.grid
    if "dead" in kinds:
        result["inputs"]["dead_distance"] = dead_distance
    if "power" in kinds:
        result["inputs"]["split"] = bool(args.split)
    if "loops" in kinds:
        result["inputs"]["loop_baseline"] = (
            None if args.loop_baseline is None else Path(args.loop_baseline).name
        )
    if "coupling" in kinds:
        result["inputs"] |= {"aggressors": list(aggressors), "victims": list(victims)}
    if "crossings" in kinds:
        result["inputs"] |= {
            "cuts": [cut.name for cut in cuts],
            "width": track_width,
            "clearance": track_clearance,
        }
    unique = sorted_issues(dict.fromkeys(issues))
    evidence = Evidence.combine(EVIDENCE, read.evidence, *evidences)
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
    paged="issues",
    example_args=(EXAMPLE_BOARD, "--kinds", "current", "--temp-rise", "10", "--copper-thickness", "35um"),
)

__all__ = ["ALL_KINDS", "COMMAND", "KINDS", "OPT_IN_KINDS"]

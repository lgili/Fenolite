# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Place the designators of a KiCad board on its silkscreen, each one checked, and cut its silkscreen at
the mask openings (capability silkscreen-layout, "Designator placement" and "Silkscreen clipping";
``docs/cli-contract.md``, "silk"; ``docs/assembly.md``, "Designators" and "Clipping").

The work lives in ``fenolite.silk``; this module is the glue: it reads the board and the project beside it
(the least text height and stroke and the ``silk_clearance`` rules), cuts the silkscreen with ``--clip``
(``silk.clip``, first), measures the ink of every text with ``kicad-cli`` when one is found
(``--measure``), runs the designator search, checks the written designators once more, and with ``--drc``
runs ``kicad-cli`` DRC on the board before and after.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import cast

from fenolite.backends.base import BoardPad, DrcReport
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.cli import KicadCli, KicadCliError, find_kicad_cli
from fenolite.backends.kicad.dru import read_rules
from fenolite.backends.kicad.pcb import read_board, source_info, write_board
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.backends.kicad.textink import InkRequest, measure_ink
from fenolite.cli._examples import EXAMPLE_SILK
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT, preflight
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.units import Nm, parse_length
from fenolite.model.design import Design
from fenolite.silk.board import (
    DEFAULT_CLEARANCE,
    DEFAULT_GAP,
    MIN_HEIGHT,
    MIN_STROKE,
    Settings,
    check_designators,
    gather,
    ink_keys,
    place_designators,
)
from fenolite.silk.clip import HYPOTHESIS as CLIP_HYPOTHESIS
from fenolite.silk.clip import MASK_HYPOTHESIS, ClipOutcome, board_mask_margin, clip_board
from fenolite.silk.codes import issue
from fenolite.silk.extents import (
    ESTIMATE_HYPOTHESIS,
    MEASURE_HYPOTHESIS,
    InkBox,
    InkCache,
    Measure,
    TextKey,
    cache_folder,
    ink_boxes,
)

HELP = (
    "place the designators of a KiCad board on its silkscreen, clear of pads, holes, texts and the edge, "
    "or cut its silkscreen at the mask openings"
)
HYPOTHESIS = "H-K-SILK-DRC"
"""The register row that designators Fenolite's own check passes give KiCad's DRC no new finding."""
MEASURES = ("auto", "kicad", "estimate")
ANGLES = {"0": 0, "90": 90_000_000}
DEG = 1_000_000


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'silk'."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, .kicad_pro or project folder")
    parser.add_argument("--designators", action="store_true", help="place the Reference text of every part")
    parser.add_argument(
        "--clip",
        action="store_true",
        help="cut the silkscreen strokes at mask openings and pad holes (first)",
    )
    parser.add_argument(
        "--margin",
        metavar="LENGTH",
        help="with --clip, the gap from a stroke to an opening (default: the silk_clearance rule, else 0)",
    )
    parser.add_argument("--keep", action="store_true", help="move only designators that meet an obstacle")
    parser.add_argument(
        "--refs",
        action="append",
        default=[],
        metavar="GLOB",
        help="place only matching references (repeatable)",
    )
    parser.add_argument(
        "--sizes",
        metavar="LENGTHS",
        help="text heights to try (default: the field's, then the board's least text height)",
    )
    parser.add_argument("--angles", metavar="LIST", default="0,90", help="board angles to try: 0, 90 or 0,90")
    parser.add_argument(
        "--clearance",
        metavar="LENGTH",
        help="least distance from a designator to anything else (default 0.15mm)",
    )
    parser.add_argument(
        "--gap", metavar="LENGTH", help="distance from the part's courtyard to its designator (default 0.1mm)"
    )
    parser.add_argument(
        "--measure",
        choices=MEASURES,
        default="auto",
        help="text ink: rendered by kicad-cli (kicad), from the glyph table (estimate), or kicad when found",
    )
    parser.add_argument(
        "-o", "--out", metavar="FILE", help="write to this file instead of replacing PATH's board"
    )
    parser.add_argument("--drc", action="store_true", help="run kicad-cli DRC on the board before and after")
    parser.add_argument(
        "--kicad-cli", dest="kicad_cli", metavar="PATH", help="kicad-cli binary or docker:<image>"
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SECONDS")


def _length(text: str | None, option: str, default: Nm, *, zero: bool = True) -> Nm:
    if text is None:
        return default
    try:
        value = parse_length(text.strip())
    except ValueError as error:
        raise CliError(
            "FEN-2001", f"{option}: {error}", where=option, hint="lengths need a unit: 0.15mm"
        ) from None
    if value < 0 or (value == 0 and not zero):
        raise CliError("FEN-2001", f"{option}: must be above 0", where=option)
    return value


def _sizes(text: str | None, floor: Nm) -> tuple[Nm, ...] | None:
    if text is None:
        return None
    found: list[Nm] = []
    for part in text.split(","):
        value = _length(part, "--sizes", 0, zero=False)
        if value < floor:
            raise CliError(
                "FEN-2001",
                f"--sizes: {part.strip()} is below the board's least text height",
                where="--sizes",
                hint="a smaller text is not readable; KiCad's DRC reports it as text_height",
            )
        found.append(value)
    return tuple(found)


def _angles(text: str) -> tuple[int, ...]:
    words = [word.strip() for word in text.split(",") if word.strip()]
    if not words or any(word not in ANGLES for word in words):
        raise CliError("FEN-2001", f"--angles: {text!r} is not 0, 90 or 0,90", where="--angles")
    return tuple(dict.fromkeys(ANGLES[word] for word in words))


def _relative(path: Path, cwd: Path) -> str:
    try:
        return os.path.relpath(path, cwd)
    except ValueError:  # another Windows drive
        return str(path)


def _mm(value: object) -> Nm | None:
    try:
        return int(Decimal(str(value)) * 1_000_000)
    except (InvalidOperation, ValueError):
        return None


def text_floor(project: Path | None) -> tuple[Nm, Nm]:
    """``(min height, min stroke)`` of silkscreen text in the project's board rules, else KiCad's
    defaults of 0.8 mm and 0.08 mm."""
    height, stroke = MIN_HEIGHT, MIN_STROKE
    if project is None:
        return height, stroke
    try:
        data = json.loads(project.read_text(encoding="utf-8"))
        rules = cast(dict[str, object], data["board"]["design_settings"]["rules"])
        found_height = _mm(rules.get("min_text_height", "0.8"))
        found_stroke = _mm(rules.get("min_text_thickness", "0.08"))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return height, stroke
    return found_height or height, found_stroke or stroke


def rule_margin(rules: Path | None) -> Nm | None:
    """The largest ``min`` of the ``silk_clearance`` rules of a ``.kicad_dru``, or ``None``."""
    if rules is None:
        return None
    try:
        ruleset = read_rules(rules.read_text(encoding="utf-8"), file=rules.name, issues=[])
    except (OSError, ValueError, FenoliteError):
        return None
    found = [rule.min for rule in ruleset.rules if rule.kind == "silk_clearance" and rule.min is not None]
    return max(found) if found else None


def _measure(cli: KicadCli) -> Measure:
    def measure(keys: Sequence[TextKey]) -> Mapping[TextKey, InkBox | None]:
        requests: dict[InkRequest, TextKey] = {
            (k.text, k.width, k.height, k.stroke, k.h_justify, k.v_justify): k for k in keys
        }
        boxes = measure_ink(cli, list(requests))
        return {key: None if boxes[r] is None else InkBox(*boxes[r]) for r, key in requests.items()}  # type: ignore[misc]

    return measure


def _drc_counts(report: DrcReport) -> Counter[str]:
    return Counter(
        found.type for found in (*report.violations, *report.unconnected_items) if not found.excluded
    )


def _drc(
    cli: KicadCli, board_path: Path, beside: dict[str, Path], placed: bytes, hypotheses: tuple[str, ...]
) -> tuple[dict[str, object], list[Issue], Evidence | None]:
    """``kicad-cli`` DRC on the board as it is and as ``silk`` would write it, in copies."""
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
            "silk.drc-new",
            f"kicad-cli {version} DRC finds {after[kind]} {kind} on the board silk would write and "
            f"{before.get(kind, 0)} on the board as it is; nothing is written",
            where=kind,
            hint="report the board: every placed designator and cut piece passed Fenolite's own check",
        )
        for kind in grown
    ]
    result: dict[str, object] = {
        "tool_version": version,
        "before": dict(sorted(before.items())),
        "after": dict(sorted(after.items())),
        "new": grown,
    }
    evidence = None if grown else Evidence(Level.KICAD_VERIFIED, f"kicad-cli {version}", hypotheses)
    return result, found, evidence


def _clip(
    args: argparse.Namespace,
    design: Design,
    text: str,
    pads: Sequence[BoardPad],
    beside: Mapping[str, Path],
    refs: tuple[str, ...],
) -> tuple[ClipOutcome, Nm, str]:
    """The clip of ``--clip``: the outcome, the margin and where it came from."""
    rule = rule_margin(beside.get(".kicad_dru"))
    if args.margin is not None:
        margin, source = _length(args.margin, "--margin", 0), "option"
    elif rule is not None:
        margin, source = rule, "rule"
    else:
        margin, source = 0, "default"
    outcome = clip_board(design, pads, margin=margin, board_margin=board_mask_margin(text), refs=refs)
    return outcome, margin, source


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    if not args.designators and not args.clip:
        raise CliError(
            "FEN-2001",
            "say what to do: --designators, --clip or both",
            hint="fenolite silk BOARD --designators --dry-run",
        )
    if args.margin is not None and not args.clip:
        raise CliError("FEN-2001", "--margin needs --clip", where="--margin")
    if args.out and Path(args.out).is_absolute():
        raise CliError("FEN-2001", "--out must be relative to the working directory")
    board_path = resolve_board(Path(args.path) if Path(args.path).is_absolute() else ctx.cwd / args.path)
    beside = {
        suffix: board_path.with_suffix(suffix)
        for suffix in (".kicad_pro", ".kicad_dru")
        if board_path.with_suffix(suffix).is_file()
    }
    min_height, min_stroke = text_floor(beside.get(".kicad_pro"))
    settings = Settings(
        clearance=_length(args.clearance, "--clearance", DEFAULT_CLEARANCE),
        gap=_length(args.gap, "--gap", DEFAULT_GAP),
        heights=_sizes(args.sizes, min_height),
        angles=_angles(args.angles),
        keep=bool(args.keep),
        refs=tuple(args.refs or ("*",)),
        min_height=min_height,
        min_stroke=min_stroke,
    )
    data = board_path.read_bytes()
    text = data.decode("utf-8")
    issues: list[Issue] = []
    design = read_board(text, file=board_path.name, issues=issues)
    source = source_info(design)
    input_ref = InputRef(
        board_path.name,
        hashlib.sha256(data).hexdigest(),
        "kicad_pcb",
        str(source.version) if source is not None else None,
    )
    backend = KicadBackend()
    pads = backend.board_pads(design, issues=issues)
    major = source.major if source is not None and source.major is not None else ctx.kicad_target
    target = args.out or _relative(board_path, ctx.cwd)
    hypotheses: tuple[str, ...] = ()
    clip: dict[str, object] | None = None
    library: dict[str, object] | None = None
    clipped = False
    if args.clip:
        clip_outcome, margin, margin_source = _clip(args, design, text, pads, beside, settings.refs)
        issues.extend(clip_outcome.issues)
        design = clip_outcome.design
        clipped = bool(clip_outcome.rows)
        hypotheses += (CLIP_HYPOTHESIS, MASK_HYPOTHESIS)
        clip = {
            "margin": margin,
            "margin_source": margin_source,
            "openings": clip_outcome.openings,
            "items": clip_outcome.items,
            "pieces": clip_outcome.pieces,
            "dropped": clip_outcome.dropped,
            "cuts": list(clip_outcome.rows),
        }
        if clip_outcome.changed:
            library = {
                "changed": sorted(clip_outcome.changed),
                "command": f"fenolite library {Path(target).as_posix()} --out LIB.pretty",
            }
    cli: KicadCli | None = None
    wants_tool = args.drc or (
        args.designators and (args.measure == "kicad" or (args.measure == "auto" and args.kicad_cli))
    )
    if wants_tool:
        cli = preflight(args.kicad_cli, args.timeout, board_path)
    elif args.designators and args.measure == "auto" and find_kicad_cli(args.kicad_cli) is not None:
        try:
            cli = preflight(args.kicad_cli, args.timeout, board_path)
        except CliError:
            cli = None
    placed_keys: list[str] = []
    failed_check: list[Issue] = []
    rows: tuple[dict[str, object], ...] = ()
    aligned: object = []
    measure: dict[str, object] | None = None
    if args.designators:
        scene = gather(
            design,
            pads=pads,
            extents=backend.placed_extents(design),
            edges=backend.board_edges(design),
            settings=settings,
        )
        measured = cli is not None and args.measure != "estimate"
        cache = InkCache(cache_folder()) if measured else None
        tool = f"kicad-cli {cli.version()}" if measured and cli is not None else ""
        inks = ink_boxes(
            ink_keys(scene, settings),
            measure=_measure(cli) if measured and cli is not None else None,
            tool=tool,
            cache=cache,
        )
        if not measured:
            issues.append(
                issue(
                    "silk.estimated",
                    "the ink of the texts is estimated from Fenolite's glyph table, not measured with "
                    "kicad-cli",
                    hint="install KiCad or pass --kicad-cli to measure it",
                )
            )
        outcome = place_designators(design, scene, inks, settings)
        issues.extend(outcome.issues)
        placed_keys = list(outcome.plan.placed)
        failed_check = check_designators(outcome.design, scene, inks, settings, placed_keys)
        issues.extend(failed_check)
        design = outcome.design
        rows = outcome.rows
        aligned = outcome.plan.aligned
        hypotheses += (HYPOTHESIS, MEASURE_HYPOTHESIS if measured else ESTIMATE_HYPOTHESIS)
        measure = {
            "source": tool or "estimate",
            "texts": len(inks),
            "cached": cache.hits if cache is not None else 0,
        }
    changed = (bool(placed_keys) and not failed_check) or clipped
    board_text = write_board(design, target=major, allow_lossy=ctx.allow_lossy).text if changed else text
    evidence = Evidence(Level.INFERRED, hypotheses=hypotheses)
    drc: dict[str, object] | None = None
    if args.drc and changed and cli is not None:
        drc, drc_issues, drc_evidence = _drc(cli, board_path, beside, board_text.encode("utf-8"), hypotheses)
        issues.extend(drc_issues)
        if drc_evidence is not None:
            evidence = drc_evidence
    failed = any(found.severity == "error" for found in issues)
    writes = (
        (PlannedWrite(target, board_text.encode("utf-8"), "kicad_pcb"),)
        if changed and not failed and (args.out is not None or board_text != text)
        else ()
    )
    statuses = Counter(str(row["status"]) for row in rows)
    return Result(
        result={
            "board": board_path.name,
            "target": target,
            "changed": bool(writes),
            "measure": measure,
            "settings": {
                "clearance": settings.clearance,
                "gap": settings.gap,
                "sizes": list(settings.heights) if settings.heights is not None else None,
                "angles": [angle // DEG for angle in settings.angles],
                "keep": settings.keep,
                "min_height": settings.min_height,
                "min_stroke": settings.min_stroke,
            },
            "placements": list(rows),
            "placed": statuses.get("placed", 0),
            "kept": statuses.get("kept", 0),
            "unplaced": statuses.get("unplaced", 0),
            "aligned": aligned,
            "clip": clip,
            "library": library,
            "drc": drc,
        },
        issues=tuple(issues),
        evidence=evidence,
        input=input_ref,
        writes=writes,
        depends=depends_on(ctx.cwd, board_path, *beside.values()),
    )


_EXAMPLE = (EXAMPLE_SILK, "--designators", "--measure", "estimate", "--out", "fenolite-silk.kicad_pcb")
COMMAND = Command(
    name="silk",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    paged="placements",
    example_args=(*_EXAMPLE, "--dry-run"),
    mutation_example_args=_EXAMPLE,
)

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite build DESIGN.py --out DIR``: a design script built into a self-contained KiCad project, or,
with ``--target altium``, into an experimental Altium project (``docs/altium.md``), whose schematic is
binary by default and ASCII with ``--altium-format ascii``, and is one sheet by default or, with
``--altium-sheets modules``, a top sheet with one sheet per top-level module (change c0037).

``build`` executes ``design.py`` as your own code and must never be run on an untrusted script
(``docs/dsl.md``, "Scripts"). Outputs changed since the last build are refused until c0019 preserves
layouts; ``--discard-layout`` replaces them, keeping backups. ``--vendor all`` (the default) copies the
placed footprints of every library into ``DIR/lib/``; ``--vendor project`` copies only those of project
tables (``docs/dsl.md``, "Vendored libraries").

Before a KiCad build plans its writes, the copper guard judges the triad it is about to write with
``checks.copper.check_copper`` (change c0029; capability design-dsl, "Copper guard before writing"): a
short or a clearance error refuses the build unless ``--copper-check warn`` is given.

The placement guard then judges the same planned board with ``placement.legality.check`` (change c0022;
capability design-dsl, "Placement legality in a build"): courtyard overlaps and parts outside the outline
are reported as warnings and never refuse a build.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, cast

import fenolite.dsl
from fenolite.backends.altium.project import (
    DEFAULT_FORM,
    DEFAULT_SHEETS,
    HARNESS_KIND,
    PCBDOC_KIND,
    PCBLIB_KIND,
    SCHDOC_KINDS,
    SCHLIB_KIND,
    SchematicForm,
    SheetMode,
)
from fenolite.backends.kicad import copperrules
from fenolite.backends.kicad import pcb as kicad_pcb
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.embed import PATH_PROPERTY
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.replace import footprint_ref
from fenolite.checks.copper import LOWERING_CODES, check_copper, rules_issues, rules_summary
from fenolite.cli._script import DesignScriptError, ScriptRun, run_design_script
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.dsl import DslError, copper, fields, moves, placements, planes, to_model
from fenolite.lens.altium import TARGET as ALTIUM_TARGET
from fenolite.lens.altium import CopperSource, build_altium, kicad_footprint_ids, kicad_lib_ids
from fenolite.lens.build import (
    VENDOR_MODES,
    PlacementRequest,
    build_design,
    check_existing,
    plane_issues,
    read_record,
)
from fenolite.lens.preserve import prepare, read_existing
from fenolite.model.design import Design as ModelDesign
from fenolite.placement import legality

MINIMAL = Path(fenolite.dsl.__file__).parent / "_minimal.py"
HELP = (
    "build a design script into a KiCad project (runs DESIGN.py as your own code: never run it on an "
    "untrusted script)"
)
TARGETS = ("kicad", ALTIUM_TARGET)
ALTIUM_FORMATS: tuple[SchematicForm, ...] = ("binary", "ascii")
ALTIUM_SHEETS: tuple[SheetMode, ...] = ("flat", "modules")
COPPER_CHECK_MODES = ("refuse", "warn")
"""``refuse`` (the default): a copper error stops the build before anything is written. ``warn``: copper
errors are reported as warnings and the build writes. There is no ``off``."""
WARN_NOTE = " (copper guard in warn mode)"
_KINDS = {
    ".kicad_pcb": "kicad_pcb",
    ".kicad_pro": "kicad_pro",
    ".kicad_dru": "kicad_dru",
    ".kicad_mod": "kicad_mod",
    ".PrjPcb": "altium_prjpcb",
    ".SchLib": SCHLIB_KIND,
    ".PcbLib": PCBLIB_KIND,
    ".PcbDoc": PCBDOC_KIND,
    ".Harness": HARNESS_KIND,
}


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = (
        HELP + ". Outputs changed since the last build are refused; --discard-layout replaces them."
    )
    parser.add_argument("design", metavar="DESIGN.py", help="the design script (executed in-process)")
    parser.add_argument("--out", required=True, metavar="DIR", help="the project folder to write")
    parser.add_argument(
        "--discard-layout",
        action="store_true",
        help="replace outputs changed since the last build (backups kept)",
    )
    parser.add_argument(
        "--target",
        choices=TARGETS,
        default="kicad",
        help="kicad (default), or altium: an experimental Altium project file and schematic instead",
    )
    parser.add_argument(
        "--altium-format",
        choices=ALTIUM_FORMATS,
        default=None,
        help=f"the form of the Altium schematic with --target altium: binary (default, Altium's own) or "
        f"ascii; a usage error with --target kicad (default form: {DEFAULT_FORM})",
    )
    parser.add_argument(
        "--altium-sheets",
        choices=ALTIUM_SHEETS,
        default=None,
        help=f"the sheets of the Altium schematic with --target altium: flat (default, one sheet) or modules "
        f"(a top sheet with sheet symbols and one sheet per top-level module, with ports, sheet entries and "
        f"signal harnesses); a usage error with --target kicad (default: {DEFAULT_SHEETS})",
    )
    parser.add_argument(
        "--copper-from",
        metavar="BOARD.kicad_pcb",
        default=None,
        help=f"with --target {ALTIUM_TARGET}: copy the tracks, arcs, vias and zones of a routed KiCad board "
        "of the same design into the PCB document, after checking that the board matches the design; the "
        "board's placements win; a usage error with --target kicad",
    )
    parser.add_argument(
        "--copper-check",
        choices=COPPER_CHECK_MODES,
        default=None,
        help="what a short or a clearance error in the copper of the board about to be written does: "
        f"refuse (default; exit 5, nothing written) or warn (reported as warnings, files written); a usage "
        f"error with --target {ALTIUM_TARGET}",
    )
    parser.add_argument(
        "--vendor",
        choices=VENDOR_MODES,
        default="all",
        help="all: copy the placed footprints of every library into DIR/lib/ (the copies keep their "
        "library's licence); project: copy only those of project tables",
    )


def _kind(rel: str, form: SchematicForm | None = None) -> str:
    if rel.startswith(".fenolite/"):
        return "fenolite"
    if rel == "fp-lib-table":
        return "fp-lib-table"
    if form is not None and Path(rel).suffix == ".SchDoc":
        return SCHDOC_KINDS[form]
    return _KINDS.get(Path(rel).suffix, "file")


def _evidence_json(evidence: Evidence) -> dict[str, object]:
    return {
        "level": evidence.level.value,
        "oracle": evidence.oracle,
        "hypotheses": list(evidence.hypotheses),
    }


def copper_guard(
    files: Mapping[str, bytes], *, name: str, mode: str, target: int
) -> tuple[tuple[Issue, ...], dict[str, object]]:
    """The copper issues of the triad ``files`` that a build is about to write, and ``result.copper_check``.

    The planned board text is read back with ``read_board``, the planned project and rules texts are
    applied with ``design_rules_from_texts`` for ``target`` (the build's KiCad major), the pads come from the
    KiCad board frame, and ``check_copper`` judges the result: the bytes that will be written, preserved
    copper included. With ``mode == "warn"`` every error is reported as a warning with ``WARN_NOTE``.
    Nothing is read from disk and nothing is written.
    """
    if mode not in COPPER_CHECK_MODES:
        raise ValueError(f"unknown copper-check mode {mode!r}; use one of {', '.join(COPPER_CHECK_MODES)}")

    def text(suffix: str) -> str | None:
        data = files.get(f"{name}{suffix}")
        return None if data is None else data.decode("utf-8")

    board_text = text(".kicad_pcb")
    if board_text is None:
        return (), {"mode": mode, "ran": False}
    design = kicad_pcb.read_board(board_text, file=f"{name}.kicad_pcb")
    rules = copperrules.design_rules_from_texts(
        design,
        project_text=text(".kicad_pro"),
        rules_text=text(".kicad_dru"),
        major=target,
        file_stem=name,
    )
    report = check_copper(
        rules.design,
        pads=KicadBackend().board_pads(rules.design),
        min_clearance=rules.min_clearance,
        rules_over_classes=rules.rules_over_classes,
        floor_over_rules=rules.floor_over_rules,
        inputs=(kicad_pcb.EVIDENCE, rules.evidence),
    )
    found = [*report.issues, *rules_issues(rules)]
    evidence = Evidence.combine(report.evidence, kicad_pcb.EVIDENCE, rules.evidence)
    if any(issue.code in LOWERING_CODES for issue in found):
        evidence = Evidence(Level.UNVERIFIED, hypotheses=evidence.hypotheses)
    if mode == "warn":
        found = [
            dataclasses.replace(issue, severity="warning", message=issue.message + WARN_NOTE)
            if issue.severity == "error"
            else issue
            for issue in found
        ]
    summary: dict[str, object] = {
        "mode": mode,
        "ran": True,
        "shorts": report.summary["shorts"],
        "clearance": report.summary["clearance"],
        "rules": rules_summary(rules),
        "evidence": _evidence_json(evidence),
    }
    return tuple(found), summary


def placement_guard(
    files: Mapping[str, bytes], *, name: str, staged: Sequence[str] = (), edge_clearance: int = 0
) -> tuple[tuple[Issue, ...], dict[str, object]]:
    """The placement issues of the board that a build is about to write, and ``result.placement``.

    The planned board text is read back with ``read_board``, the courtyards come from the KiCad board
    frame and the outline from ``board_outline``, and ``legality.check`` judges every footprint whose
    component path is not in ``staged``. Every issue is at most a warning: a build never refuses for
    placement. Nothing is read from disk and nothing is written.
    """
    data = files.get(f"{name}.kicad_pcb")
    if data is None:
        return (), {"ran": False, "counts": {}}
    design = kicad_pcb.read_board(data.decode("utf-8"), file=f"{name}.kicad_pcb")
    footprints = design.board.footprints if design.board is not None else ()
    components = {c.id: c for c in design.circuit.components}
    names: dict[str, str] = {}
    left_out: set[str] = set()
    for footprint in footprints:
        ref = footprint_ref(design, footprint)
        names[footprint.id] = ref
        component = components.get(footprint.component_id)
        path = component.properties.get(PATH_PROPERTY, ref) if component is not None else ref
        if path in staged:
            left_out.add(footprint.id)
    extents = [e for e in KicadBackend().placed_extents(design) if e.footprint_id not in left_out]
    found = legality.check(extents, board_outline(design).rings, edge_clearance=edge_clearance, names=names)
    issues = tuple(
        dataclasses.replace(issue, severity="warning") if issue.severity == "error" else issue
        for issue in found
    )
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.code] = counts.get(issue.code, 0) + 1
    return issues, {"ran": True, "counts": dict(sorted(counts.items()))}


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    script = Path(args.design)
    script_path = script if script.is_absolute() else ctx.cwd / script
    out = Path(args.out)
    out_dir = out if out.is_absolute() else ctx.cwd / out
    if out_dir.resolve() == script_path.resolve().parent:
        raise CliError("FEN-2001", "--out must not be the folder of the design script", where="--out")
    if args.altium_format is not None and args.target != ALTIUM_TARGET:
        raise CliError(
            "FEN-2001",
            f"--altium-format needs --target {ALTIUM_TARGET}; the target is {args.target}",
            where="--altium-format",
            hint=f"add --target {ALTIUM_TARGET}, or drop --altium-format",
        )
    if args.altium_sheets is not None and args.target != ALTIUM_TARGET:
        raise CliError(
            "FEN-2001",
            f"--altium-sheets needs --target {ALTIUM_TARGET}; the target is {args.target}",
            where="--altium-sheets",
            hint=f"add --target {ALTIUM_TARGET}, or drop --altium-sheets",
        )
    if args.copper_check is not None and args.target == ALTIUM_TARGET:
        raise CliError(
            "FEN-2001",
            f"--copper-check judges the KiCad board of a build; the target is {args.target}",
            where="--copper-check",
            hint=f"drop --copper-check, or drop --target {ALTIUM_TARGET}",
        )
    board_path: Path | None = None
    if args.copper_from is not None:
        if args.target != ALTIUM_TARGET:
            raise CliError(
                "FEN-2001",
                f"--copper-from needs --target {ALTIUM_TARGET}; the target is {args.target}",
                where="--copper-from",
                hint=f"add --target {ALTIUM_TARGET}, or drop --copper-from",
            )
        given = Path(args.copper_from)
        board_path = given if given.is_absolute() else ctx.cwd / given
        if not board_path.is_file():
            raise CliError(
                "FEN-2001",
                f"--copper-from: {args.copper_from} is not a file",
                where="--copper-from",
                hint="pass the routed .kicad_pcb of the same design",
            )
    run = run_design_script(script_path)
    design = run.design
    try:
        model = to_model(design)
        requested = placements(design)
        aliases = moves(design)
        plane_nets = planes(design)
        intents = copper(design)
        field_requests = fields(design)
    except DslError as error:
        raise DesignScriptError(str(error), file=str(args.design)) from error
    if args.target == ALTIUM_TARGET:
        return _run_altium(
            args, ctx, run, model, requested, plane_nets, script_path, out, out_dir, board_path
        )
    resolver = LibraryResolver(
        LibraryConfig(target_major=ctx.kicad_target, project_dir=script_path.resolve().parent)
    )
    record = read_record(out_dir)
    prepared = None
    if not args.discard_layout:
        prepared = prepare(
            model, requested, read_existing(out_dir, design.name), name=design.name, moves=aliases
        )
    built = build_design(
        model,
        prepared.placements if prepared is not None else requested,
        name=design.name,
        copper=design.copper,  # type: ignore[arg-type]
        resolver=resolver,
        target=ctx.kicad_target,
        allow_lossy=ctx.allow_lossy,
        vendor=cast(Literal["all", "project"], args.vendor),
        record=record,
        prepared=prepared,
        copper_intents=intents,
        fields=field_requests,
    )
    files = dict(built.files)
    mode = args.copper_check or COPPER_CHECK_MODES[0]
    copper_issues: tuple[Issue, ...] = ()
    copper_check: dict[str, object] = {"mode": mode, "ran": False}
    placement_issues, placement = placement_guard(
        files,
        name=design.name,
        staged=cast(Sequence[str], built.summary.get("staged", ())),
        edge_clearance=legality.edge_clearance(built.design),
    )
    if files:
        copper_issues, copper_check = copper_guard(
            files, name=design.name, mode=mode, target=ctx.kicad_target
        )
        if any(issue.severity == "error" for issue in copper_issues):
            files = {}  # refused: a build with an error issue plans no write
    if files:
        merged = {f"{design.name}{suffix}" for suffix in (".kicad_pcb", ".kicad_pro", ".kicad_dru")}
        guarded = {rel: data for rel, data in files.items() if rel not in merged}
        check_existing(out_dir, guarded, record=record, discard_layout=bool(args.discard_layout))
    writes = tuple(
        PlannedWrite(path=str(out / rel), data=data, kind=_kind(rel)) for rel, data in sorted(files.items())
    )
    result: dict[str, Any] = {
        "design": design.name,
        "target": ctx.kicad_target,
        "out": str(out),
        "files": [w.path for w in writes],
        **built.summary,
        "copper_check": copper_check,
        "placement": placement,
        "script_output": run.output,
    }
    data = script_path.read_bytes()
    return Result(
        result=result,
        issues=(*built.issues, *plane_issues(plane_nets), *copper_issues, *placement_issues),
        evidence=built.evidence,
        input=InputRef(
            path=str(args.design),
            sha256=hashlib.sha256(data).hexdigest(),
            kind="fenolite-dsl",
            format_version=None,
        ),
        writes=writes,
    )


def _run_altium(
    args: argparse.Namespace,
    ctx: Context,
    run: ScriptRun,
    model: ModelDesign,
    requested: Mapping[str, PlacementRequest],
    plane_nets: Mapping[str, str],
    script_path: Path,
    out: Path,
    out_dir: Path,
    board_path: Path | None = None,
) -> Result:
    """The ``--target altium`` branch (capability altium-build, "Altium build target"): only the symbol
    libraries of KiCad lib ids and the footprint libraries of KiCad footprint links are read, through a
    resolver built as for ``--target kicad`` and only when
    the design has such lib ids; no external tool runs; the project file is planned only when ``DIR`` has
    none. ``--altium-sheets`` picks one sheet or one sheet per top-level module (change c0037); every planned
    sheet and harness definition file follows the edited-output rule on its own.

    With ``--copper-from`` (change c0038, "Copper from a routed KiCad board") the board ``board_path`` is
    read in this process with ``backends.kicad.pcb.read_board`` and handed to the build as a
    ``CopperSource`` of origin ``board``; the reader's issues and evidence join the build's."""
    name = run.design.name
    form = cast(SchematicForm, args.altium_format or DEFAULT_FORM)
    sheets = cast(SheetMode, args.altium_sheets or DEFAULT_SHEETS)
    resolver = None
    if kicad_lib_ids(model) or kicad_footprint_ids(model):
        resolver = LibraryResolver(
            LibraryConfig(target_major=ctx.kicad_target, project_dir=script_path.resolve().parent)
        )
    source: CopperSource | None = None
    reader_issues: list[Issue] = []
    copper_input: dict[str, object] | None = None
    if board_path is not None:
        board = kicad_pcb.read_board(board_path, issues=reader_issues)
        source = CopperSource(board, "board", str(args.copper_from))
        if model.board is not None and model.board.zones:
            # the routed board is the one copper source: its zones stand for the script's zone() calls
            # (c0031), which the KiCad build wrote into it
            model = dataclasses.replace(model, board=dataclasses.replace(model.board, zones=()))
        info = kicad_pcb.source_info(board)
        copper_input = {
            "path": str(args.copper_from),
            "sha256": hashlib.sha256(board_path.read_bytes()).hexdigest(),
            "kind": "kicad-board",
            "format_version": str(info.version) if info is not None else None,
        }
    built = build_altium(
        model,
        name=name,
        placed=tuple(requested),
        placements=requested,
        project_exists=(out_dir / f"{name}.PrjPcb").is_file(),
        form=form,
        resolver=resolver,
        sheets=sheets,
        copper=run.design.copper,
        planes=plane_nets,
        copper_source=source,
    )
    files = dict(built.files)
    if files:
        check_existing(out_dir, files, record=read_record(out_dir), discard_layout=bool(args.discard_layout))
    writes = tuple(
        PlannedWrite(path=str(out / rel), data=data, kind=_kind(rel, form))
        for rel, data in sorted(files.items())
    )
    summary = built.summary
    kept = cast(Sequence[str], summary["kept"])
    result: dict[str, Any] = {
        "design": name,
        "target": ALTIUM_TARGET,
        "out": str(out),
        "files": [w.path for w in writes],
        **{
            key: summary[key]
            for key in ("components", "nets", "labels", "power_ports", "no_connects", "sheet")
        },
        "kept": [str(out / rel) for rel in kept],
        "schematic_format": form,
        **{key: summary[key] for key in ("sheet_mode", "sheets", "ports", "sheet_entries", "harnesses")},
        "libraries": [str(out / rel) for rel in cast(Sequence[str], summary["libraries"])],
        "symbols": summary["symbols"],
        "footprints": summary["footprints"],
        "pcb_document": str(out / str(summary["pcb_document"])) if summary["pcb_document"] else None,
        "copper": summary["copper"],
        "experimental": summary["experimental"],
        "script_output": run.output,
    }
    if copper_input is not None:
        result["copper_input"] = copper_input
    data = script_path.read_bytes()
    evidence = built.evidence if source is None else Evidence.combine(built.evidence, kicad_pcb.EVIDENCE)
    return Result(
        result=result,
        issues=(*reader_issues, *built.issues),
        evidence=evidence,
        input=InputRef(
            path=str(args.design),
            sha256=hashlib.sha256(data).hexdigest(),
            kind="fenolite-dsl",
            format_version=None,
        ),
        writes=writes,
    )


COMMAND = Command(
    name="build",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    example_args=(str(MINIMAL), "--out", "fenolite-minimal", "--dry-run"),
    mutation_example_args=(str(MINIMAL), "--out", "fenolite-minimal"),
)

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

A KiCad build also writes the schematic of the design, ``<name>.kicad_sch``, with its symbol libraries and
``sym-lib-table`` (change c0061; ``docs/schematic.md``): ``--schematic skip`` leaves them out. The sheet is
a view of the script, so an edited schematic is replaced, with a warning and a backup; symbol positions are
fixed in ``schematic-placements.toml`` beside the script. ``--schematic-layout readable`` (the default,
change c0070) gives each module a sheet of its own under ``sheets/`` and puts 2-pin parts beside the IC
pins they connect to; ``grid`` keeps the one flat sheet of v0.2a.

Before a KiCad build plans its writes, the copper guard judges the triad it is about to write with
``checks.copper.check_copper`` (change c0029; capability design-dsl, "Copper guard before writing"): a
short or a clearance error refuses the build unless ``--copper-check warn`` is given.

An Altium build has the same guard on the PCB document it is about to write (change c0088; capability
altium-build, "Copper guard in an Altium build"): ``altium_copper_guard`` reads the planned bytes back
with the Altium backend and refuses a short; a clearance finding is reported and does not refuse.

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
from fenolite.backends.altium.altsym import DEFAULT_BODIES, SymbolBodies
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.outjob import OUTJOB_KIND
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
from fenolite.backends.altium.read.project import read_project
from fenolite.backends.kicad import copper as kicad_copper
from fenolite.backends.kicad import copperrules, wks
from fenolite.backends.kicad import frame as kicad_frame
from fenolite.backends.kicad import pcb as kicad_pcb
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.copper import CopperIntentLike
from fenolite.backends.kicad.embed import PATH_PROPERTY
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver
from fenolite.backends.kicad.outline import board_outline
from fenolite.backends.kicad.replace import footprint_ref
from fenolite.backends.kicad.schgen import LAYOUTS as SCHEMATIC_LAYOUTS
from fenolite.backends.kicad.schgen import SHEETS_DIR
from fenolite.catalog import (
    ENTRIES as CATALOG_ENTRIES,
)
from fenolite.catalog import (
    get_footprint as catalog_footprint,
)
from fenolite.catalog import (
    get_symbol as catalog_symbol,
)
from fenolite.checks.copper import LOWERING_CODES, check_copper, rules_issues, rules_summary
from fenolite.cli._script import DesignScriptError, ScriptRun, run_design_script
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.cmd_export import preset_file
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.dsl import (
    BOARD_ORIGIN,
    DslError,
    copper,
    drawing_sheet_source,
    fields,
    module_moves,
    moves,
    net_moves,
    pad_zones,
    placements,
    planes,
    to_model,
)
from fenolite.dsl import Design as DslDesign
from fenolite.lens.altium import TARGET as ALTIUM_TARGET
from fenolite.lens.altium import (
    CopperSource,
    build_altium,
    kicad_footprint_ids,
    kicad_lib_ids,
    refused_altium,
)
from fenolite.lens.altium import issue as altium_issue
from fenolite.lens.build import (
    SCHEMATIC_MODES,
    SHEET_SUFFIX,
    VENDOR_MODES,
    PlacementRequest,
    build_design,
    check_existing,
    plane_issues,
    read_record,
)
from fenolite.lens.placements import FILE_NAME as PLACEMENTS_FILE
from fenolite.lens.placements import SourcePlacement, read_placements
from fenolite.lens.preserve import ExistingProject, FilePlacement, Prepared, prepare, read_existing
from fenolite.lens.schplacements import FILE_NAME as SYMBOL_PLACEMENTS_FILE
from fenolite.lens.schplacements import read_placements as read_symbol_placements
from fenolite.model.design import Design as ModelDesign
from fenolite.model.presentation import DrawingSheet
from fenolite.placement import legality
from fenolite.templates import build_sheet, load_spec

MINIMAL = Path(fenolite.dsl.__file__).parent / "_minimal.py"
HELP = (
    "build a design script into a KiCad project (runs DESIGN.py as your own code: never run it on an "
    "untrusted script)"
)
TARGETS = ("kicad", ALTIUM_TARGET)
ALTIUM_FORMATS: tuple[SchematicForm, ...] = ("binary", "ascii")
ALTIUM_SHEETS: tuple[SheetMode, ...] = ("flat", "modules")
ALTIUM_SYMBOLS: tuple[SymbolBodies, ...] = ("generic", "graphics")
"""The values of ``--altium-symbols`` (change c0086)."""
ALTIUM_DIRECTIONS: tuple[str, ...] = ("on", "off")
"""The values of ``--altium-directions`` (change c0086)."""
DEFAULT_DIRECTIONS = "on"
COPPER_CHECK_MODES = ("refuse", "warn")
"""``refuse`` (the default): a copper error stops the build before anything is written. ``warn``: copper
errors are reported as warnings and the build writes. There is no ``off``."""
WARN_NOTE = " (copper guard in warn mode)"
SCRIPT_COPPER_CODES: tuple[str, ...] = ("kicad.copper.", "kicad.frame.", "layout.unplaced")
"""The warnings and infos of the in-memory KiCad build that an Altium build with script copper reports
(change c0053): what the copper intents created or left out, and the parts that build staged. Its other
warnings and infos concern KiCad files that are not written. Every error passes."""
REPLACED_CODE = "build.schematic-replaced"
_KINDS = {
    ".kicad_sch": "kicad_sch",
    ".kicad_sym": "kicad_sym",
    ".kicad_pcb": "kicad_pcb",
    ".kicad_pro": "kicad_pro",
    ".kicad_dru": "kicad_dru",
    ".kicad_mod": "kicad_mod",
    ".PrjPcb": "altium_prjpcb",
    ".SchLib": SCHLIB_KIND,
    ".PcbLib": PCBLIB_KIND,
    ".PcbDoc": PCBDOC_KIND,
    ".Harness": HARNESS_KIND,
    ".OutJob": OUTJOB_KIND,
}
OUTJOB_MODES = ("on", "off")
"""``--altium-outjob``: write ``<name>.OutJob`` beside a PCB document (the default), or not."""


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
        "--altium-outjob",
        choices=OUTJOB_MODES,
        default=None,
        help=f"with --target {ALTIUM_TARGET}: on (default) writes <name>.OutJob, an output job with Gerber, "
        "NC drill, pick-and-place, bill-of-materials, schematic-print and PCB-print outputs, when the build "
        "writes a PCB document; off writes none; a usage error with --target kicad",
    )
    parser.add_argument(
        "--altium-outjob-preset",
        metavar="FILE",
        default=None,
        help="the export preset (the TOML file of export --preset) the output job is made for: its options "
        "are listed in result.outjob.defaults, to be set in Altium; a usage error with --target kicad or "
        "with --altium-outjob off",
    )
    parser.add_argument(
        "--altium-symbols",
        choices=ALTIUM_SYMBOLS,
        default=None,
        help=f"with --target altium: graphics (default) draws each resolved symbol from its own graphics, "
        f"generic draws one rectangle per part (the output of 0.2.0 and earlier); a usage error with "
        f"--target kicad (default: {DEFAULT_BODIES})",
    )
    parser.add_argument(
        "--altium-directions",
        choices=ALTIUM_DIRECTIONS,
        default=None,
        help=f"with --target altium: on (default) gives each port and sheet entry the I/O type that follows "
        f"from the pin types on its net, off leaves them all unspecified; a usage error with --target kicad "
        f"(default: {DEFAULT_DIRECTIONS})",
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
        f"refuse (default; exit 5, nothing written) or warn (reported as warnings, files written); with "
        f"--target {ALTIUM_TARGET} only a short refuses, and a clearance error is reported as a warning",
    )
    parser.add_argument(
        "--vendor",
        choices=VENDOR_MODES,
        default="all",
        help="all: copy the placed footprints of every library into DIR/lib/ (the copies keep their "
        "library's licence); project: copy only those of project tables",
    )
    parser.add_argument(
        "--schematic",
        choices=SCHEMATIC_MODES,
        default=None,
        help="write (default): also write DIR/<name>.kicad_sch, its symbol libraries under DIR/lib/ and "
        "sym-lib-table, and name the pads of unconnected pins as KiCad does; skip: write the board without "
        f"a schematic; a usage error with --target {ALTIUM_TARGET}",
    )
    parser.add_argument(
        "--schematic-layout",
        dest="schematic_layout",
        choices=SCHEMATIC_LAYOUTS,
        default=None,
        help="readable (default): one sheet per module under DIR/sheets/, and 2-pin parts beside the IC "
        "pins they connect to, joined by a wire; grid: one flat sheet with a label on every pin, the form "
        f"of v0.2a; a usage error with --target {ALTIUM_TARGET}",
    )


def _kind(rel: str, form: SchematicForm | None = None) -> str:
    if rel.startswith(".fenolite/"):
        return "fenolite"
    if rel in ("fp-lib-table", "sym-lib-table"):
        return rel
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


CLEARANCE_NOTE = " (reported, not refused: the Altium copper guard refuses shorts)"


def altium_copper_guard(
    files: Mapping[str, bytes], *, name: str, mode: str
) -> tuple[tuple[Issue, ...], dict[str, object]]:
    """The copper issues of the PCB document ``<name>.PcbDoc`` of ``files`` that an Altium build is about
    to write, and ``result.copper_check`` (capability altium-build, "Copper guard in an Altium build").

    The planned bytes are read back with the Altium backend's own reader and adapter, the rules are those
    the document holds (``AltiumBackend.rules_from_bytes`` on the planned bytes), the pads come from the
    Altium board frame, and ``check_copper`` judges the result. A ``copper.short`` keeps its severity, so the
    build refuses; every other error is reported as a warning with ``CLEARANCE_NOTE``. With
    ``mode == "warn"`` the short is a warning too, with ``WARN_NOTE``. Nothing is read from disk and
    nothing is written; a build without a PCB document is not judged (``ran`` false)."""
    if mode not in COPPER_CHECK_MODES:
        raise ValueError(f"unknown copper-check mode {mode!r}; use one of {', '.join(COPPER_CHECK_MODES)}")
    document = f"{name}.PcbDoc"
    data = files.get(document)
    if data is None:
        return (), {"mode": mode, "ran": False}
    backend = AltiumBackend()
    read = backend.board_from_bytes(data, file=document)
    design = read.design
    rules = backend.rules_from_bytes(design, data, file=document)
    report = check_copper(
        rules.design,
        pads=backend.board_pads(rules.design),
        min_clearance=rules.min_clearance,
        rules_over_classes=rules.rules_over_classes,
        floor_over_rules=rules.floor_over_rules,
        inputs=(read.evidence, rules.evidence),
    )
    unpoured = sum(1 for zone in rules.design.board.zones if not zone.fills) if rules.design.board else 0
    found: list[Issue] = []
    for issue in (*report.issues, *rules_issues(rules)):
        if issue.severity != "error":
            found.append(issue)
        elif issue.code != "copper.short":
            found.append(
                dataclasses.replace(issue, severity="warning", message=issue.message + CLEARANCE_NOTE)
            )
        elif mode == "warn":
            found.append(dataclasses.replace(issue, severity="warning", message=issue.message + WARN_NOTE))
        else:
            found.append(issue)
    evidence = Evidence.combine(report.evidence, read.evidence, rules.evidence)
    if unpoured or any(issue.code in LOWERING_CODES for issue in found):
        evidence = Evidence(Level.UNVERIFIED, hypotheses=evidence.hypotheses)
    summary: dict[str, object] = {
        "mode": mode,
        "ran": True,
        "shorts": report.summary["shorts"],
        "clearance": report.summary["clearance"],
        "unpoured": unpoured,
        "rules": rules_summary(rules),
        "evidence": _evidence_json(evidence),
    }
    return tuple(found), summary


def _catalog_definitions(
    design: ModelDesign,
    authored_footprints: Mapping[str, Any],
    authored_symbols: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], frozenset[str]]:
    """Select only built-ins used by this design; project definitions override exact lib ids."""
    symbol_ids = {entry.lib_id for entry in CATALOG_ENTRIES if entry.kind == "symbol"}
    footprint_ids = {entry.lib_id for entry in CATALOG_ENTRIES if entry.kind == "footprint"}
    symbols: dict[str, Any] = {}
    footprints: dict[str, Any] = {}
    used_builtin: set[str] = set()
    for component in design.circuit.components:
        symbol_id = component.lib_symbol_ref
        if symbol_id in symbol_ids and symbol_id not in authored_symbols:
            symbols[symbol_id] = catalog_symbol(symbol_id)
            used_builtin.add(symbol_id)
        symbol = authored_symbols.get(symbol_id) or symbols.get(symbol_id)
        fp_id = component.lib_footprint_ref or (symbol.properties.get("Footprint", "") if symbol else "")
        if fp_id in footprint_ids and fp_id not in authored_footprints:
            footprints[fp_id] = catalog_footprint(fp_id)
            used_builtin.add(fp_id)
    return {**footprints, **authored_footprints}, {**symbols, **authored_symbols}, frozenset(used_builtin)


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


def read_source(
    script_path: Path,
) -> tuple[Mapping[str, SourcePlacement], tuple[Issue, ...], str | None]:
    """The entries of ``placements.toml`` beside the script, its issues and its SHA-256; no entry and no
    hash without the file (``design-dsl``, "Placements file in a build")."""
    path = script_path.resolve().parent / PLACEMENTS_FILE
    if not path.is_file():
        return {}, (), None
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FormatError(f"not UTF-8 text: {error}", file=PLACEMENTS_FILE) from error
    found = read_placements(text, origin=BOARD_ORIGIN, file=PLACEMENTS_FILE)
    return found.entries, found.issues, hashlib.sha256(data).hexdigest()


def read_drawing_sheet_source(
    design: DslDesign, script_path: Path
) -> tuple[DrawingSheet | None, tuple[Issue, ...], dict[str, object] | None]:
    """The drawing sheet that ``design.sheet(drawing_sheet=…)`` names, read from the script's folder: a
    ``.kicad_wks`` file through the drawing-sheet reader, a ``*.sheet.toml`` specification through the
    sheet-template builder. Returns the sheet, the reader's issues and ``result.drawing_sheet``.

    A missing file is an input error: KiCad falls back to its default frame without a word for a sheet it
    does not find (``H-K-WKS-FALLBACK``)."""
    named = drawing_sheet_source(design)
    if named is None:
        return None, (), None
    path = script_path.resolve().parent / named
    try:
        data = path.read_bytes()
    except OSError as error:
        raise CliError(
            "FEN-3001",
            f"the drawing sheet {named} of sheet() cannot be read: {error.strerror or error}",
            where=named,
            hint="name a .kicad_wks or *.sheet.toml file beside the design script",
        ) from None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FormatError(f"not UTF-8 text: {error}", file=named) from error
    found: list[Issue] = []
    if named.endswith(".sheet.toml"):
        sheet = build_sheet(load_spec(text, file=named), base_dir=path.parent, issues=found)
    else:
        sheet = wks.read_drawing_sheet(text, file=Path(named).name, issues=found)
    result: dict[str, object] = {
        "source": named,
        "file": f"{design.name}{SHEET_SUFFIX}",
        "items": len(sheet.items),
    }
    return sheet, tuple(found), result


def source_summary(prepared: Prepared | None, issues: Sequence[Issue], *, read: bool) -> dict[str, object]:
    """``result.preserved.source``: the file read, the parts placed from it, and its stale and unknown
    tables."""
    placed: Mapping[str, object] = prepared.placements if prepared is not None else {}
    return {
        "file": PLACEMENTS_FILE if read else None,
        "used": sorted(path for path, found in placed.items() if isinstance(found, FilePlacement)),
        "stale": sorted(i.where for i in issues if i.code == "layout.source-stale"),
        "unknown": sorted(i.where for i in issues if i.code == "layout.source-unknown"),
    }


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
    for option, value in (
        ("--altium-outjob", args.altium_outjob),
        ("--altium-outjob-preset", args.altium_outjob_preset),
    ):
        if value is not None and args.target != ALTIUM_TARGET:
            raise CliError(
                "FEN-2001",
                f"{option} needs --target {ALTIUM_TARGET}; the target is {args.target}",
                where=option,
                hint=f"add --target {ALTIUM_TARGET}, or drop {option}",
            )
    if args.altium_outjob_preset is not None and args.altium_outjob == "off":
        raise CliError(
            "FEN-2001",
            "--altium-outjob-preset names the preset of an output job, and --altium-outjob off writes none",
            where="--altium-outjob-preset",
            hint="drop one of the two options",
        )
    if args.altium_symbols is not None and args.target != ALTIUM_TARGET:
        raise CliError(
            "FEN-2001",
            f"--altium-symbols needs --target {ALTIUM_TARGET}; the target is {args.target}",
            where="--altium-symbols",
            hint=f"add --target {ALTIUM_TARGET}, or drop --altium-symbols",
        )
    if args.altium_directions is not None and args.target != ALTIUM_TARGET:
        raise CliError(
            "FEN-2001",
            f"--altium-directions needs --target {ALTIUM_TARGET}; the target is {args.target}",
            where="--altium-directions",
            hint=f"add --target {ALTIUM_TARGET}, or drop --altium-directions",
        )
    if args.schematic is not None and args.target == ALTIUM_TARGET:
        raise CliError(
            "FEN-2001",
            f"--schematic is an option of the KiCad target; the target is {args.target}",
            where="--schematic",
            hint=f"drop --schematic: --target {ALTIUM_TARGET} always writes its own schematic",
        )
    if args.schematic_layout is not None and args.target == ALTIUM_TARGET:
        raise CliError(
            "FEN-2001",
            f"--schematic-layout is an option of the KiCad target; the target is {args.target}",
            where="--schematic-layout",
            hint=f"drop --schematic-layout: --altium-sheets chooses the sheets of --target {ALTIUM_TARGET}",
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
        module_aliases = module_moves(design)
        net_aliases = net_moves(design)
        plane_nets = planes(design)
        intents = copper(design)
        field_requests = fields(design)
        pad_zone_requests = pad_zones(design)
    except DslError as error:
        raise DesignScriptError(str(error), file=str(args.design)) from error
    frame_sheet, sheet_issues, sheet_result = read_drawing_sheet_source(design, script_path)
    source, source_issues, source_sha = read_source(script_path)
    refused = any(found.severity == "error" for found in source_issues)
    if args.target == ALTIUM_TARGET:
        # both targets place a part from the file: the lens runs without an existing project (c0069)
        from_file = prepare(model, requested, ExistingProject(), name=design.name, source=source)
        made = _run_altium(
            args,
            ctx,
            run,
            model,
            cast(Mapping[str, PlacementRequest], from_file.placements),
            plane_nets,
            script_path,
            out,
            out_dir,
            board_path,
            intents,
            frame_sheet,
            sheet_result,
        )
        return dataclasses.replace(
            made,
            issues=(*source_issues, *sheet_issues, *from_file.issues, *made.issues),
            writes=() if refused else made.writes,
        )
    resolver = LibraryResolver(
        LibraryConfig(target_major=ctx.kicad_target, project_dir=script_path.resolve().parent)
    )
    record = read_record(out_dir)
    prepared = None
    if not args.discard_layout:
        prepared = prepare(
            model,
            requested,
            read_existing(out_dir, design.name),
            name=design.name,
            moves=aliases,
            module_moves=module_aliases,
            net_moves=net_aliases,
            source=source,
        )
    elif source:
        # the file is source, like the script: it applies to a discarded layout too, and no output is read
        prepared = prepare(model, requested, ExistingProject(), name=design.name, source=source)
    authored_footprints, authored_symbols, builtin_ids = _catalog_definitions(
        model,
        {key: fp.definition for key, fp in design.footprints.items()},
        {key: symbol.definition for key, symbol in design.symbols.items()},  # type: ignore[attr-defined]
    )
    schematic = cast(Literal["write", "skip"], args.schematic or SCHEMATIC_MODES[0])
    symbol_issues: list[Issue] = []
    symbol_placements = None
    placements_path = script_path.resolve().parent / SYMBOL_PLACEMENTS_FILE
    if schematic == "write" and placements_path.is_file():
        symbol_placements = read_symbol_placements(
            placements_path.read_text(encoding="utf-8"), file=SYMBOL_PLACEMENTS_FILE, issues=symbol_issues
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
        pad_zones=pad_zone_requests,
        authored_footprints=authored_footprints,
        authored_symbols=authored_symbols,
        source_sha256=source_sha,
        drawing_sheet=frame_sheet,
        schematic=schematic,
        symbol_placements=symbol_placements,
        schematic_layout=cast(Literal["readable", "grid"], args.schematic_layout or SCHEMATIC_LAYOUTS[0]),
    )
    files = {} if refused else dict(built.files)
    if any(found.severity == "error" for found in symbol_issues):
        files = {}  # a placements file with an error plans no write
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
        # the root sheet and the child sheets under sheets/: views of the script, replaced when edited
        sheets = [f"{design.name}.kicad_sch", *sorted(rel for rel in files if _child_sheet(rel))]
        merged = {f"{design.name}{suffix}" for suffix in (".kicad_pcb", ".kicad_pro", ".kicad_dru")}
        guarded = {rel: data for rel, data in files.items() if rel not in merged and rel not in sheets}
        check_existing(out_dir, guarded, record=record, discard_layout=bool(args.discard_layout))
        for sheet in sheets:
            symbol_issues += _replaced_sheet(out_dir, out, sheet, files.get(sheet), record)
    writes = tuple(
        PlannedWrite(path=str(out / rel), data=data, kind=_kind(rel)) for rel, data in sorted(files.items())
    )
    result: dict[str, Any] = {
        "design": design.name,
        "target": ctx.kicad_target,
        "out": str(out),
        "files": [w.path for w in writes],
        **built.summary,
        "libraries": {
            key: ("builtin" if key in builtin_ids else origin)
            for key, origin in cast(Mapping[str, str], built.summary["libraries"]).items()
        },
        "copper_check": copper_check,
        "placement": placement,
        "drawing_sheet": sheet_result,
        "script_output": run.output,
    }
    result["preserved"] = {
        **cast(Mapping[str, object], built.summary["preserved"]),
        "source": source_summary(prepared, built.issues, read=source_sha is not None),
    }
    data = script_path.read_bytes()
    return Result(
        result=result,
        issues=(
            *sheet_issues,
            *source_issues,
            *built.issues,
            *symbol_issues,
            *plane_issues(plane_nets),
            *copper_issues,
            *placement_issues,
        ),
        evidence=built.evidence,
        input=InputRef(
            path=str(args.design),
            sha256=hashlib.sha256(data).hexdigest(),
            kind="fenolite-dsl",
            format_version=None,
        ),
        writes=writes,
    )


def _child_sheet(rel: str) -> bool:
    """Whether ``rel`` is the file of a child sheet of the generated schematic."""
    return rel.startswith(f"{SHEETS_DIR}/") and rel.endswith(".kicad_sch")


def _replaced_sheet(
    out_dir: Path, out: Path, sheet: str, planned: bytes | None, record: Mapping[str, str] | None
) -> list[Issue]:
    """One ``build.schematic-replaced`` warning when the schematic file ``sheet`` in ``out_dir``, the root
    or a child sheet, holds neither the planned bytes nor those of the last build: the sheet is
    regenerated, and the mutation protocol keeps a backup. The file is hashed and never parsed."""
    path = out_dir / sheet
    if planned is None or not path.is_file():
        return []
    current = path.read_bytes()
    if current == planned:
        return []
    if record is not None and record.get(sheet) == hashlib.sha256(current).hexdigest():
        return []
    return [
        Issue(
            REPLACED_CODE,
            "warning",
            f"{out / sheet} was changed since the last build and is replaced: the schematic is generated "
            "from the script",
            where=str(out / sheet),
            hint=f"fix symbol positions in {SYMBOL_PLACEMENTS_FILE} beside the script; the edited file is "
            "kept as a .bak copy unless --no-backup is given",
        )
    ]


def _outjob_result(summary: object, out: Path, preset: Mapping[str, str] | None) -> dict[str, object] | None:
    """``result.outjob`` (change c0087): the lens summary with the file under ``--out`` and the preset as
    given with its SHA-256; ``None`` without a job."""
    if not isinstance(summary, Mapping):
        return None
    found = dict(cast(Mapping[str, object], summary))
    return {**found, "file": str(out / str(found["file"])), "preset": dict(preset) if preset else None}


def _sheet_result(
    summary: object, out: Path, source: Mapping[str, object] | None
) -> dict[str, object] | None:
    """``result.drawing_sheet`` (change c0087): the sheet as written in the script, its item count and the
    page of every schematic document; ``None`` without a drawing sheet or without a written sheet."""
    if not isinstance(summary, Mapping) or source is None:
        return None
    found = cast(Mapping[str, object], summary)
    pages = [
        {**page, "file": str(out / str(page["file"]))}
        for page in cast(Sequence[Mapping[str, object]], found["pages"])
    ]
    return {"source": source["source"], "items": found["items"], "pages": pages}


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
    intents: Sequence[CopperIntentLike] = (),
    drawing_sheet: DrawingSheet | None = None,
    sheet_result: Mapping[str, object] | None = None,
) -> Result:
    """The ``--target altium`` branch (capability altium-build, "Altium build target"): only the symbol
    libraries of KiCad lib ids and the footprint libraries of KiCad footprint links are read, through a
    resolver built as for ``--target kicad`` and only when
    the design has such lib ids; no external tool runs; the project file is planned only when ``DIR`` has
    none. ``--altium-sheets`` picks one sheet or one sheet per top-level module (change c0037); every planned
    sheet and harness definition file follows the edited-output rule on its own.

    With ``--copper-from`` (change c0038, "Copper from a routed KiCad board") the board ``board_path`` is
    read in this process with ``backends.kicad.pcb.read_board`` and handed to the build as a
    ``CopperSource`` of origin ``board``; the reader's issues and evidence join the build's.

    Without ``--copper-from``, the script's copper ``intents`` (change c0053, "Script copper in an Altium
    build") are resolved by the KiCad build of the script, run in memory with ``lens.build.build_design``:
    none of its files is planned. Its model is the ``CopperSource`` of origin ``script``, and the script's
    zones travel with it. An error of that build refuses this one; its ``SCRIPT_COPPER_CODES`` issues pass.
    With ``--copper-from`` the board wins: the intents are not resolved, and one ``altium.not-lowered``
    info names them.

    Change c0087: unless ``--altium-outjob off``, the build writes ``<name>.OutJob`` beside a PCB
    document, for the preset of ``--altium-outjob-preset``; a kept project file is read to see whether it
    lists the job. ``drawing_sheet`` (the sheet that ``sheet(drawing_sheet=…)`` names, with its
    ``sheet_result``) is drawn on every schematic document; a loss needs ``--allow-lossy``."""
    name = run.design.name
    form = cast(SchematicForm, args.altium_format or DEFAULT_FORM)
    sheets = cast(SheetMode, args.altium_sheets or DEFAULT_SHEETS)
    # change c0086: the symbols and footprints the script authored or took from the catalog are written
    # like resolved ones, as in a KiCad build, so their graphics reach the libraries
    authored_footprints, authored_symbols, _builtin = _catalog_definitions(
        model,
        {key: fp.definition for key, fp in run.design.footprints.items()},
        {key: symbol.definition for key, symbol in run.design.symbols.items()},  # type: ignore[attr-defined]
    )
    resolver = None
    if kicad_lib_ids(model) or kicad_footprint_ids(model) or intents:
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
        if intents:
            keys = ", ".join(intent.key for intent in intents)
            reader_issues.append(
                altium_issue(
                    "altium.not-lowered",
                    f"{len(intents)} copper intent(s) of the script ({keys}) are not resolved: "
                    f"{args.copper_from} is the copper source, and --copper-from wins",
                    str(args.copper_from),
                    "the board of a KiCad build of this script already holds its script copper",
                )
            )
    script_issues: list[Issue] = []
    refused = False
    project_exists = (out_dir / f"{name}.PrjPcb").is_file()
    with_job = args.altium_outjob != "off"
    preset, preset_result = preset_file(args.altium_outjob_preset, ctx.cwd)
    job_listed = False
    if project_exists and with_job:
        # a kept project file is never rewritten; it is read only to see whether it lists the job, and one
        # that cannot be read lists nothing
        try:
            kept_project = read_project((out_dir / f"{name}.PrjPcb").read_bytes(), file=f"{name}.PrjPcb")
        except (FormatError, OSError):
            kept_project = None
        job_name = f"{name}.OutJob".casefold()
        job_listed = kept_project is not None and any(
            document.path.casefold() == job_name for document in kept_project.documents
        )
    if intents and source is None:
        assert resolver is not None
        resolved = build_design(
            model,
            requested,
            name=name,
            copper=run.design.copper,  # type: ignore[arg-type]
            resolver=resolver,
            target=ctx.kicad_target,
            copper_intents=intents,
            authored_footprints={key: fp.definition for key, fp in run.design.footprints.items()},
        )
        refused = not resolved.files or any(found.severity == "error" for found in resolved.issues)
        script_issues = [
            found
            for found in resolved.issues
            if found.severity == "error" or found.code.startswith(SCRIPT_COPPER_CODES)
        ]
        if not refused:
            source = CopperSource(resolved.design, "script")
            if model.board is not None and model.board.zones:
                # one copper source: the KiCad build kept the script's zones, so the source holds them
                model = dataclasses.replace(model, board=dataclasses.replace(model.board, zones=()))
    if refused:
        built = refused_altium(
            model, name=name, issues=script_issues, project_exists=project_exists, form=form, sheets=sheets
        )
        script_issues = []
    else:
        built = build_altium(
            model,
            name=name,
            placed=tuple(requested),
            placements=requested,
            project_exists=project_exists,
            form=form,
            resolver=resolver,
            sheets=sheets,
            copper=run.design.copper,
            planes=plane_nets,
            copper_source=source,
            outjob=with_job,
            outjob_preset=preset,
            outjob_listed=job_listed,
            drawing_sheet=drawing_sheet,
            allow_lossy=ctx.allow_lossy,
            authored_footprints=authored_footprints,
            directions=(args.altium_directions or DEFAULT_DIRECTIONS) == "on",
            symbol_bodies=args.altium_symbols or DEFAULT_BODIES,
            authored_symbols=authored_symbols,
        )
    files = dict(built.files)
    mode = args.copper_check or COPPER_CHECK_MODES[0]
    copper_issues: tuple[Issue, ...] = ()
    copper_check: dict[str, object] = {"mode": mode, "ran": False}
    if files:
        copper_issues, copper_check = altium_copper_guard(files, name=name, mode=mode)
        if any(found.severity == "error" for found in copper_issues):
            files = {}  # refused: a build with an error issue plans no write
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
        "schematic": summary["schematic"],
        "libraries": [str(out / rel) for rel in cast(Sequence[str], summary["libraries"])],
        "symbols": summary["symbols"],
        "footprints": summary["footprints"],
        "pcb_document": str(out / str(summary["pcb_document"])) if summary["pcb_document"] else None,
        "copper": summary["copper"],
        "copper_check": copper_check,
        "outjob": _outjob_result(summary["outjob"], out, preset_result),
        "drawing_sheet": _sheet_result(summary["drawing_sheet"], out, sheet_result),
        "rules": summary["rules"],
        "experimental": summary["experimental"],
        "script_output": run.output,
    }
    if copper_input is not None:
        result["copper_input"] = copper_input
    data = script_path.read_bytes()
    evidence = built.evidence
    if board_path is not None:
        evidence = Evidence.combine(evidence, kicad_pcb.EVIDENCE)
    elif intents:
        evidence = Evidence.combine(evidence, kicad_copper.EVIDENCE, kicad_frame.EVIDENCE)
    return Result(
        result=result,
        issues=(*reader_issues, *script_issues, *built.issues, *copper_issues),
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

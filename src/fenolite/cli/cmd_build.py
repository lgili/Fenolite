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
import functools
import hashlib
import json
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
from fenolite.backends.kicad import generate as kicad_generate
from fenolite.backends.kicad import pcb as kicad_pcb
from fenolite.backends.kicad import sch as kicad_sch
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.copper import CopperIntentLike
from fenolite.backends.kicad.embed import PATH_PROPERTY
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver
from fenolite.backends.kicad.meander import MeanderIntentLike
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
from fenolite.catalog.devices import check_device, device_digest, edited_issue, is_edited
from fenolite.checks import placement as placement_rules
from fenolite.checks.circuit import circuit_issues
from fenolite.checks.copper import (
    LOWERING_CODES,
    CopperReport,
    check_copper,
    frame_edges,
    rules_issues,
    rules_summary,
    waived_issues,
)
from fenolite.checks.waivers import copper_waivers
from fenolite.cli import _layout
from fenolite.cli._contracts import classes_of
from fenolite.cli._lock import lock_location, plan_lock, with_lock
from fenolite.cli._padmap import DefaultPadMap, apply_default_pad_maps
from fenolite.cli._picks import picking, proposed_files
from fenolite.cli._script import DesignScriptError, ScriptRun, run_design_script
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.cmd_export import preset_file
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.dsl import (
    BOARD_ORIGIN,
    DslError,
    block_schematics,
    copper,
    drawing_sheet_source,
    drawn_schematic,
    fields,
    generated,
    heights,
    meanders,
    module_moves,
    moves,
    net_moves,
    outline_locked,
    pad_zones,
    placements,
    planes,
    role_copper,
    schematic_composition,
    stackup_locked,
    to_model,
    via_protection_locked,
)
from fenolite.dsl import Design as DslDesign
from fenolite.dsl.convert import two_terminal, unused_marks
from fenolite.dsl.relative import has_layout
from fenolite.geometry.errors import BackendUnavailable
from fenolite.lens import edits as edits_mod
from fenolite.lens.altium import TARGET as ALTIUM_TARGET
from fenolite.lens.altium import (
    CopperSource,
    build_altium,
    kept_documents,
    kicad_footprint_ids,
    kicad_lib_ids,
    refused_altium,
    sheet_parameters,
)
from fenolite.lens.altium import issue as altium_issue
from fenolite.lens.build import (
    BUILD_EVIDENCE,
    RECORD_FILE,
    SCHEMATIC_MODES,
    SHEET_SUFFIX,
    VENDOR_MODES,
    PlacementRequest,
    build_design,
    check_existing,
    plane_issues,
    read_record,
    script_codes,
)
from fenolite.lens.build import issue as build_issue
from fenolite.lens.drawn import read_drawn
from fenolite.lens.placements import FILE_NAME as PLACEMENTS_FILE
from fenolite.lens.placements import SourcePlacement, read_placements
from fenolite.lens.preserve import (
    ExistingProject,
    FilePlacement,
    Prepared,
    legacy_edits,
    prepare,
    read_existing,
)
from fenolite.lens.rolecopper import RoleCopperPlanner
from fenolite.lens.schplacements import FILE_NAME as SYMBOL_PLACEMENTS_FILE
from fenolite.lens.schplacements import read_placements as read_symbol_placements
from fenolite.model.circuit import PinRef
from fenolite.model.design import Design as ModelDesign
from fenolite.model.drawn import DrawnSchematic
from fenolite.model.drawn_connect import issue as drawn_issue
from fenolite.model.findings import Waiver
from fenolite.model.library import DeviceDef, flatten_symbol
from fenolite.model.presentation import DrawingSheet
from fenolite.model.schematic import SchematicSheet
from fenolite.placement import legality
from fenolite.placement.codes import RELATIVE_EVIDENCE
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
ALTIUM_BODIES: tuple[str, ...] = ("off", "extruded")
"""The values of ``--altium-bodies`` (change c0121)."""
DEFAULT_ALTIUM_BODIES = "extruded"
"""The extruded component bodies are written unless ``off`` is asked (change c0155, the maintainer's
decision of 2026-10-09): Altium Designer 26.5 opened the written bodies with their two stand-in keys
(``H-A-PCBX-BODY-OPEN``, step X8 of the author report)."""
ALTIUM_POUR: tuple[str, ...] = ("computed", "outline")
"""The values of ``--altium-pour`` (change c0215)."""
DEFAULT_ALTIUM_POUR = "computed"
"""The pour of every polygon is computed by Fenolite unless ``outline`` is asked (the maintainer's decision
of 2026-10-26; experimental until a round of kit group K6 passes)."""
COPPER_CHECK_MODES = ("refuse", "warn")
"""``refuse`` (the default): a copper error stops the build before anything is written. ``warn``: copper
errors are reported as warnings and the build writes. There is no ``off``."""
WARN_NOTE = " (copper guard in warn mode)"
SCRIPT_COPPER_CODES: tuple[str, ...] = (
    "kicad.copper.",
    "kicad.frame.",
    "kicad.meander.",
    "kicad.generate.",
    "roles.",
    "layout.unplaced",
)
"""The warnings and infos of the in-memory KiCad build that an Altium build with script copper reports
(change c0053): what the copper intents, the generated copper and the role copper (change c0243) created
or left out, and the parts that build staged. Its other warnings and infos concern KiCad files that are not
written. Every error passes."""
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
        "--altium-template",
        metavar="FILE.SchDot",
        default=None,
        help="apply a native binary sheet template to every Altium schematic, preserving page settings, "
        "fonts and embedded images; requires binary Altium output and no drawing_sheet in the script",
    )
    parser.add_argument(
        "--discard-layout",
        action="store_true",
        help="replace outputs changed since the last build (backups kept)",
    )
    parser.add_argument(
        "--lock",
        metavar="FILE",
        default=None,
        help="the design lock to read and write, in place of <script stem>.lock beside the script",
    )
    parser.add_argument(
        "--frozen",
        action="store_true",
        help="refuse with exit 7 (FEN-7004) when the design lock would change; never write it",
    )
    parser.add_argument(
        "--take",
        action="append",
        default=None,
        metavar="SIDE[:TARGET]",
        help="resolve a sync.conflict: SIDE is code, cad, board or schematic, TARGET a component path or "
        "PATH#PROPERTY (every conflict without one); repeatable",
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
        help="the export preset (the TOML file of export --preset) the output job is made for: its "
        "gerbers.precision is the decimals of the job's Gerber settings (result.outjob.gerber), and its "
        "other options are listed in result.outjob.defaults, to be set in Altium; a usage error with "
        "--target kicad or with --altium-outjob off",
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
        "--altium-bodies",
        choices=ALTIUM_BODIES,
        default=None,
        help=f"with --target altium: extruded writes the extruded component bodies of the board's "
        f"footprints (experimental), off writes none and reports each body, as earlier versions did; a "
        f"usage error with --target kicad (default: {DEFAULT_ALTIUM_BODIES})",
    )
    parser.add_argument(
        "--altium-pour",
        choices=ALTIUM_POUR,
        default=None,
        help=f"with --target altium: computed writes the poured copper of each polygon as Fenolite "
        f"computes it with Altium's rules (experimental; needs the geo extra, without which the default "
        f"writes the outline with a warning), outline writes the polygons unpoured, as earlier versions did; "
        f"a usage error with --target kicad (default: {DEFAULT_ALTIUM_POUR})",
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
    parser.add_argument(
        "--altium-layout",
        choices=("grid", "blocks"),
        default=None,
        help="Altium arrangement: grid preserves legacy layout; blocks composes functional blocks",
    )


def role_planner(record: object | None, script_path: Path, out_dir: Path | None) -> RoleCopperPlanner | None:
    """The role-copper planner the build is given for ``design.role_copper()`` (change c0243): the roles
    that ``fenolite roles`` confirmed in the project's ``.fenolite/rules.json`` (when ``out_dir`` holds one)
    and the record's requirements file (beside the script) bound to ``fenolite.roles.copper.run``; ``None``
    without a record."""
    if record is None:
        return None
    from fenolite.cli.cmd_analyze import requirements_option
    from fenolite.roles.copper import run
    from fenolite.roles.judge import split_roles
    from fenolite.roles.store import read_rules_roles

    stored = None
    if out_dir is not None:
        _, stored = split_roles(read_rules_roles(out_dir / ".fenolite" / "rules.json"))
    name = getattr(record, "requirements", None)
    requirements = requirements_option(name, script_path.resolve().parent) if isinstance(name, str) else None
    return cast(RoleCopperPlanner, functools.partial(run, stored=stored, requirements=requirements))


def _keep_confirmed_roles(out_dir: Path, files: dict[str, bytes]) -> None:
    """Keep in the planned ``.fenolite/rules.json`` the net roles that ``fenolite roles`` confirmed in the
    project's current one (change c0222; ``docs/roles.md``, "Where roles are kept")."""
    rel = ".fenolite/rules.json"
    if rel in files and (out_dir / rel).is_file():
        from fenolite.roles.store import kept_confirmed

        files[rel] = kept_confirmed(files[rel], out_dir / rel)


def _kind(rel: str, form: SchematicForm | None = None) -> str:
    if rel.startswith(".fenolite/"):
        return "fenolite"
    if rel in ("fp-lib-table", "sym-lib-table"):
        return rel
    if form is not None and Path(rel).suffix == ".SchDoc":
        return SCHDOC_KINDS[form]
    if Path(rel).suffix.lower() == ".schdot":
        return "altium_schdot"
    return _KINDS.get(Path(rel).suffix, "file")


def _evidence_json(evidence: Evidence) -> dict[str, object]:
    return {
        "level": evidence.level.value,
        "oracle": evidence.oracle,
        "hypotheses": list(evidence.hypotheses),
    }


def guard_waivers(
    report: CopperReport, waivers: Sequence[Waiver]
) -> tuple[tuple[Issue, ...], dict[str, object]]:
    """The issues of ``report`` after the design's ``copper.*`` waivers (a matched finding is ``info``, so
    no mode of a guard refuses it or turns it into a warning), and ``result.copper_check.waivers``:
    ``matched`` (name → findings) and ``unmatched`` (names), in name order. A guard emits no
    ``check.waiver-unmatched``: ``fenolite check`` reports stale waivers (change c0114)."""
    own = copper_waivers(waivers)
    found, counts = waived_issues(report, own)
    names = sorted(waiver.name for waiver in own)
    return found, {
        "matched": {name: counts[name] for name in names if counts.get(name)},
        "unmatched": [name for name in names if not counts.get(name)],
    }


def copper_guard(
    files: Mapping[str, bytes], *, name: str, mode: str, target: int, waivers: Sequence[Waiver] = ()
) -> tuple[tuple[Issue, ...], dict[str, object]]:
    """The copper issues of the triad ``files`` that a build is about to write, and ``result.copper_check``.
    ``waivers`` are the design's waivers: they are applied before the mode (``guard_waivers``).

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
    frame = KicadBackend()
    edges, edge_issues = frame_edges(frame, rules.design)
    report = check_copper(
        rules.design,
        pads=frame.board_pads(rules.design),
        min_clearance=rules.min_clearance,
        rules_over_classes=rules.rules_over_classes,
        floor_over_rules=rules.floor_over_rules,
        inputs=(kicad_pcb.EVIDENCE, rules.evidence),
        edges=edges,
        min_edge_clearance=rules.min_edge_clearance,
        edge_floor_over_rules=rules.edge_floor_over_rules,
    )
    judged, waived = guard_waivers(report, waivers)
    found = [*judged, *rules_issues(rules), *edge_issues]
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
        "edge_clearance": report.summary["edge_clearance"],
        "rules": rules_summary(rules),
        "evidence": _evidence_json(evidence),
        "waivers": waived,
    }
    return tuple(found), summary


CLEARANCE_NOTE = " (reported, not refused: the Altium copper guard refuses shorts)"


def altium_copper_guard(
    files: Mapping[str, bytes], *, name: str, mode: str, waivers: Sequence[Waiver] = ()
) -> tuple[tuple[Issue, ...], dict[str, object]]:
    """The copper issues of the PCB document ``<name>.PcbDoc`` of ``files`` that an Altium build is about
    to write, and ``result.copper_check`` (capability altium-build, "Copper guard in an Altium build").

    The planned bytes are read back with the Altium backend's own reader and adapter, the rules are those
    the document holds (``AltiumBackend.rules_from_bytes`` on the planned bytes), the pads come from the
    Altium board frame, and ``check_copper`` judges the result. A ``copper.short`` keeps its severity, so the
    build refuses; every other error is reported as a warning with ``CLEARANCE_NOTE``. With
    ``mode == "warn"`` the short is a warning too, with ``WARN_NOTE``. Nothing is read from disk and
    nothing is written; a build without a PCB document is not judged (``ran`` false). ``waivers`` are the
    design's waivers, applied before the mode as on the KiCad target (``guard_waivers``): a waived short is
    ``info`` and does not refuse the build."""
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
    edges, edge_issues = frame_edges(backend, rules.design)
    report = check_copper(
        rules.design,
        pads=backend.board_pads(rules.design),
        min_clearance=rules.min_clearance,
        rules_over_classes=rules.rules_over_classes,
        floor_over_rules=rules.floor_over_rules,
        inputs=(read.evidence, rules.evidence),
        edges=edges,
        min_edge_clearance=rules.min_edge_clearance,
        edge_floor_over_rules=rules.edge_floor_over_rules,
    )
    unpoured = sum(1 for zone in rules.design.board.zones if not zone.fills) if rules.design.board else 0
    judged, waived = guard_waivers(report, waivers)
    found: list[Issue] = []
    for issue in (*judged, *rules_issues(rules), *edge_issues):
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
        "edge_clearance": report.summary["edge_clearance"],
        "unpoured": unpoured,
        "rules": rules_summary(rules),
        "evidence": _evidence_json(evidence),
        "waivers": waived,
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
        if symbol is not None and getattr(symbol, "extends", ""):
            # a derived authored symbol names the footprint of its base unless it names one (change c0261)
            symbol = flatten_symbol(
                symbol, [s for s in authored_symbols.values() if s.library == symbol.library]
            )
        fp_id = component.lib_footprint_ref or (symbol.properties.get("Footprint", "") if symbol else "")
        if fp_id in footprint_ids and fp_id not in authored_footprints:
            footprints[fp_id] = catalog_footprint(fp_id)
            used_builtin.add(fp_id)
    return {**footprints, **authored_footprints}, {**symbols, **authored_symbols}, frozenset(used_builtin)


def contract_devices(design: DslDesign) -> dict[str, DeviceDef]:
    """The device records of the parts by device id, as the stage ``circuit.rules`` takes them (c0253)."""
    return {
        part.device.id: part.device for _, part in sorted(design.parts.items()) if part.device is not None
    }


def design_devices(design: DslDesign) -> dict[str, DeviceDef]:
    """The device of each part placed from one, by component path (change c0248)."""
    return {path: part.device for path, part in sorted(design.parts.items()) if part.device is not None}


def device_rows(design: DslDesign) -> list[dict[str, object]]:
    """``result.devices``: each device the design uses, in id order, with its origin, evidence label,
    whether it was edited after its stamp, its digest and the paths of its parts."""
    rows: dict[str, dict[str, Any]] = {}
    for path, part in sorted(design.parts.items()):
        device = part.device
        if device is None:
            continue
        row = rows.setdefault(
            device.id,
            {
                "id": device.id,
                "origin": part.device_origin,
                "evidence": device.evidence,
                "edited": is_edited(device),
                "sha256": device_digest(device),
                "parts": [],
            },
        )
        row["parts"].append(path)
    return [rows[key] for key in sorted(rows)]


def device_issues(design: DslDesign) -> list[Issue]:
    """``device.overrides-builtin`` and ``device.edited`` (info), once per device the design uses."""
    found: list[Issue] = []
    seen: set[str] = set()
    for _path, part in sorted(design.parts.items()):
        device = part.device
        if device is None or device.id in seen:
            continue
        seen.add(device.id)
        if part.device_overrides:
            found.append(
                build_issue(
                    "device.overrides-builtin",
                    f"the project device {device.id} is used in place of the shipped device of that id",
                    device.id,
                    "give the project device an id of its own namespace if the override is not meant",
                )
            )
        if is_edited(device):
            found.append(edited_issue(device))
    return found


def project_definitions(
    run: ScriptRun, model: ModelDesign
) -> tuple[dict[str, Any], dict[str, Any], list[Issue]]:
    """The footprints and symbols of the project's package and pins records (``devices/`` beside the
    script, change c0259), which override catalog definitions of the same id, and the issues of the records
    the design uses: ``library.generator-missing`` (error) for a record without geometry whose generator
    is not installed, ``library.deprecated`` and ``library.review-stale``."""
    from fenolite.catalog import records as rec

    tree, shipped = run.library, rec.shipped_tree()
    footprints: dict[str, Any] = {}
    symbols: dict[str, Any] = {}
    for record in tree.records:
        if isinstance(record, rec.PinsRecord) and record.symbol is not None:
            symbols[record.header.id] = rec.symbol_def(record)
        elif isinstance(record, rec.PackageRecord) and record.generator in rec.GENERATORS:
            footprints[record.header.id] = rec.footprint_def(record)
    used: list[rec.Record] = []
    issues: list[Issue] = []

    def find(kind: rec.Kind, record_id: str) -> rec.Record | None:
        return tree.get(kind, record_id) or shipped.get(kind, record_id)

    for component in sorted(model.circuit.components, key=lambda found: found.ref):
        for kind, record_id in (("pins", component.lib_symbol_ref), ("package", component.lib_footprint_ref)):
            record = find(cast(rec.Kind, kind), record_id) if record_id else None
            if record is None:
                continue
            used.append(record)
            missing = (isinstance(record, rec.PinsRecord) and record.symbol is None) or (
                isinstance(record, rec.PackageRecord) and record.generator not in rec.GENERATORS
            )
            if missing and record not in used[:-1]:
                what = "symbol generator" if kind == "pins" else f"package generator {record.generator!r}"  # type: ignore[union-attr]
                issues.append(
                    rec.library_issue(
                        "library.generator-missing",
                        f"{kind} record {record_id} has no explicit geometry and the {what} is not installed",
                        record_id,
                        "write the geometry into the record, or wait for the generator of its family",
                    )
                )
    for part in run.design.parts.values():
        if part.device is not None:
            record = find("device", part.device.id.split("@", 1)[0])
            if record is not None:
                used.append(record)
    return footprints, symbols, [*issues, *rec.used_record_issues(used)]


def lower_device_functions(model: ModelDesign, devices: Mapping[str, DeviceDef]) -> ModelDesign:
    """``model`` with each net member and no-connect mark of a device part that names a function replaced
    by the function's symbol pins, for targets whose writer resolves pin numbers only (the Altium build;
    the KiCad build resolves functions itself, ``lens.build``)."""
    functions: dict[str, dict[str, tuple[str, ...]]] = {}
    for component in model.circuit.components:
        device = devices.get(component.properties.get(PATH_PROPERTY, component.ref))
        if device is not None:
            functions[component.id] = {pin.function: pin.pins for pin in device.pins}
    if not functions:
        return model

    def lowered(refs: Sequence[PinRef]) -> tuple[PinRef, ...]:
        out: list[PinRef] = []
        for ref in refs:
            names = functions.get(ref.component_id, {})
            out += [PinRef(ref.component_id, pin) for pin in names.get(ref.pin, (ref.pin,))]
        return tuple(sorted(set(out)))

    circuit = model.circuit
    nets = tuple(dataclasses.replace(net, members=lowered(net.members)) for net in circuit.nets)
    return dataclasses.replace(
        model,
        circuit=dataclasses.replace(circuit, nets=nets, no_connects=lowered(circuit.no_connects)),
    )


def pad_map_issues(applied: Sequence[DefaultPadMap]) -> list[Issue]:
    """One ``build.pad-map-default`` warning per part that got the catalog's default pin-to-pad map
    (capability design-dsl, "Default pin-to-pad map is reported"; change c0147)."""
    found: list[Issue] = []
    for part in applied:
        written = json.dumps(dict(part.pairs))
        pins = ", ".join(f"pin {pin} on pad {pad}" for pin, pad in part.pairs)
        identity = json.dumps({pin: pin for pin, _pad in part.pairs})
        found.append(
            build_issue(
                "build.pad-map-default",
                f"{part.ref} ({part.symbol} on {part.footprint}) gives no pad_map; the build applies the "
                f"catalog's map pad_map={written} ({pins}): pad 1 of this land is the cathode",
                part.path,
                hint=f"write pad_map={written} on the part to keep this map and silence the warning, and "
                f"connect it by pin name (A, K); a design that wired it by pin number for the pad order of "
                f"earlier builds keeps that order with pad_map={identity}",
            )
        )
    return found


def placement_guard(
    files: Mapping[str, bytes],
    *,
    name: str,
    staged: Sequence[str] = (),
    edge_clearance: int = 0,
    rules: placement_rules.PlacementRules | None = None,
    model: ModelDesign | None = None,
) -> tuple[tuple[Issue, ...], dict[str, object]]:
    """The placement issues of the board that a build is about to write, and ``result.placement``.

    The planned board text is read back with ``read_board``, the courtyards come from the KiCad board
    frame, the outline from ``board_outline`` and the keep-outs from the board, and ``legality.check``
    judges every footprint whose component path is not in ``staged``. ``rules`` are the placement rules of
    the built model (``checks.placement.rules_of``), judged on the pads of the same board; its height
    limits are judged on the same extents with the heights of ``model``, the built model, whose footprints
    hold the bodies of ``Part(height=…)`` (change c0140). Every issue is at most a warning: a build never
    refuses for placement. Nothing is read from disk and nothing is written.
    """
    data = files.get(f"{name}.kicad_pcb")
    if data is None:
        return (), {"ran": False, "counts": {}, "rules": placement_rules.empty_counts()}
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
    keepouts = design.board.keepouts if design.board is not None else ()
    found = legality.check(
        extents,
        board_outline(design).rings,
        edge_clearance=edge_clearance,
        names=names,
        keepouts=keepouts,
    )
    report = placement_rules.RuleReport()
    if rules:
        report = placement_rules.judge(design, rules, pads=KicadBackend().board_pads(design))
    judged = {family: dict(family_counts) for family, family_counts in report.counts.items()}
    heights = placement_rules.RuleReport((), {})
    if rules is not None and rules.heights:
        heights = placement_rules.judge_heights(
            design, rules.heights, placement_rules.heights_of(design, model), extents=extents
        )
        judged.update({family: dict(family_counts) for family, family_counts in heights.counts.items()})
    issues = tuple(
        dataclasses.replace(issue, severity="warning") if issue.severity == "error" else issue
        for issue in (*found, *report.issues, *heights.issues)
    )
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.code] = counts.get(issue.code, 0) + 1
    return issues, {"ran": True, "counts": dict(sorted(counts.items())), "rules": judged}


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


def read_edit_source(
    script_path: Path,
) -> tuple[Mapping[str, edits_mod.PartEdits] | None, str | None, tuple[Issue, ...], str | None]:
    """The edits beside the script (``design-dsl``, "Placements file in a build"): those of ``edits.toml``
    when it exists, otherwise the entries of ``placements.toml`` as legacy position edits. Returns the
    edits (``None`` without a file), the name of the file read, its issues and its SHA-256."""
    folder = script_path.resolve().parent
    path = folder / edits_mod.EDITS_FILE
    legacy = folder / PLACEMENTS_FILE
    if not path.is_file():
        entries, issues, sha = read_source(script_path)
        if sha is None:
            return None, None, (), None
        return legacy_edits(entries), PLACEMENTS_FILE, issues, sha
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FormatError(f"not UTF-8 text: {error}", file=edits_mod.EDITS_FILE) from error
    found = edits_mod.read_edits(text, origin=BOARD_ORIGIN, file=edits_mod.EDITS_FILE)
    issues = list(found.issues)
    if legacy.is_file():
        issues.append(
            edits_mod.issue(
                "edit.legacy-file",
                f"{PLACEMENTS_FILE} is not read: {edits_mod.EDITS_FILE} is beside it",
                PLACEMENTS_FILE,
                f"delete {PLACEMENTS_FILE}; {edits_mod.EDITS_FILE} replaces it",
            )
        )
    return found.parts, edits_mod.EDITS_FILE, tuple(issues), hashlib.sha256(data).hexdigest()


def read_base_record(out_dir: Path) -> edits_mod.BaseRecord:
    """The base record of the output folder, or ``BaseRecord.absent`` when it holds none."""
    path = out_dir / edits_mod.BASE_FILE
    if not path.is_file():
        return edits_mod.BaseRecord.absent("kicad")
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        return edits_mod.read_base(f"\0{error}", target="kicad", file=edits_mod.BASE_FILE)
    return edits_mod.read_base(text, target="kicad", file=edits_mod.BASE_FILE)


def schematic_sheets(root: Path) -> list[SchematicSheet] | None:
    """The sheets of the schematic ``root``: the root file and every sheet file it names, each read once.
    ``None`` when the project has no schematic."""
    if not root.is_file():
        return None
    tree = kicad_sch.sheet_files(root)
    return [kicad_sch.read_schematic(root.parent / name, file=name) for name in tree.files]


def parse_take_option(values: Sequence[str] | None) -> tuple[edits_mod.Take, ...]:
    """The takes of ``--take``; a malformed or contradictory value is a usage error."""
    try:
        return edits_mod.parse_takes(values or ())
    except ValueError as error:
        raise CliError(
            "FEN-2001",
            str(error),
            where="--take",
            hint="give --take code|cad|board|schematic[:PATH[#PROPERTY]], one side per target",
        ) from None


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


def read_drawn_source(path: Path, named: str) -> DrawnSchematic:
    """The drawn schematic that ``design.load_schematic()`` names, read from the script's folder (change
    c0276); a missing or unreadable file is ``FormatError`` (``FEN-3004``, exit 3) naming the file."""
    try:
        data = path.read_bytes()
    except OSError as error:
        raise FormatError(
            f"the drawn schematic {named} of load_schematic() cannot be read: {error.strerror or error}",
            file=named,
        ) from None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FormatError(f"not UTF-8 text: {error}", file=named) from error
    return read_drawn(text, file=named)


def source_summary(
    prepared: Prepared | None, issues: Sequence[Issue], *, read: bool, file: str | None = None
) -> dict[str, object]:
    """``result.preserved.source``: the file read, the parts placed from it, and its stale and unknown
    tables."""
    placed: Mapping[str, object] = prepared.placements if prepared is not None else {}
    return {
        "file": (file or PLACEMENTS_FILE) if read else None,
        "used": sorted(path for path, found in placed.items() if isinstance(found, FilePlacement)),
        "stale": sorted(i.where for i in issues if i.code == "layout.source-stale"),
        "unknown": sorted(i.where for i in issues if i.code == "layout.source-unknown"),
    }


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    # the inputs a review can see: the design script and, when the build reads one, the copper source
    read = depends_on(
        ctx.cwd,
        args.design,
        getattr(args, "copper_from", None),
        getattr(args, "altium_template", None),
        _existing(lock_location(args.design, getattr(args, "lock", None), ctx.cwd)[1]),
    )
    built = _built(args, ctx)
    read = (
        *read,
        *depends_on(
            ctx.cwd,
            *proposed_files(Path(args.design) if Path(args.design).is_absolute() else ctx.cwd / args.design),
        ),
    )
    files = cast(Sequence[Mapping[str, str]], built.result.get("device_files", []))
    if files:
        # the project devices beside the script are inputs too: a changed file changes the plan (c0248)
        script = Path(args.design)
        folder = (script if script.is_absolute() else ctx.cwd / script).parent
        read = (*read, *depends_on(ctx.cwd, *(folder / row["path"] for row in files)))
    return dataclasses.replace(built, depends=tuple(sorted(set((*read, *built.depends)))))


def _existing(path: Path) -> Path | None:
    """``path`` when it is a file (the lock read by a build), else ``None``; a lock the build creates is a
    target of the plan, which the dispatcher already guards."""
    return path if path.is_file() else None


def _built(args: argparse.Namespace, ctx: Context) -> Result:
    script = Path(args.design)
    script_path = script if script.is_absolute() else ctx.cwd / script
    out = Path(args.out)
    out_dir = out if out.is_absolute() else ctx.cwd / out
    if out_dir.resolve() == script_path.resolve().parent:
        raise CliError("FEN-2001", "--out must not be the folder of the design script", where="--out")
    native_path = getattr(args, "altium_template", None)
    if native_path is not None and (args.target != ALTIUM_TARGET or args.altium_format == "ascii"):
        raise CliError(
            "FEN-2001",
            "--altium-template requires --target altium and binary schematic output",
            where="--altium-template",
        )
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
    if args.altium_layout is not None and args.target != ALTIUM_TARGET:
        raise CliError("FEN-2001", "--altium-layout requires --target altium", where="--altium-layout")
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
    if args.altium_bodies is not None and args.target != ALTIUM_TARGET:
        raise CliError(
            "FEN-2001",
            f"--altium-bodies needs --target {ALTIUM_TARGET}; the target is {args.target}",
            where="--altium-bodies",
            hint=f"add --target {ALTIUM_TARGET}, or drop --altium-bodies",
        )
    if args.altium_pour is not None and args.target != ALTIUM_TARGET:
        raise CliError(
            "FEN-2001",
            f"--altium-pour needs --target {ALTIUM_TARGET}; the target is {args.target}",
            where="--altium-pour",
            hint=f"add --target {ALTIUM_TARGET}, or drop --altium-pour",
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
    if args.altium_layout == "grid" and (design.schematic_flow is not None or design.schematic_blocks):
        raise CliError(
            "FEN-2001",
            "--altium-layout grid contradicts the script's block composition",
            where="--altium-layout",
            hint="select blocks or remove the script's layout declarations",
        )
    lock_given, lock_path = lock_location(args.design, getattr(args, "lock", None), ctx.cwd)
    try:
        schematic_composition(design, target=args.target, enabled=args.altium_layout == "blocks")
        with picking(script_path) as picks:  # the query parts get their devices here (change c0254)
            lock = plan_lock(
                design,
                script=script_path,
                given=lock_given,
                path=lock_path,
                frozen=bool(getattr(args, "frozen", False)),
            )
        if picks.resolution is not None and picks.resolution.refused:
            # a stale, missing or unmatched pick, or an unachievable generator: nothing is built
            return with_lock(Result(result={**picks.summary(), "devices": []}), lock)
        model = to_model(design, refs=lock.refs)
        requested = placements(design)
        aliases = moves(design)
        module_aliases = module_moves(design)
        net_aliases = net_moves(design)
        plane_nets = planes(design)
        intents = copper(design)
        meander_intents = meanders(design)
        generated_records = generated(design)
        role_record = role_copper(design)
        field_requests = fields(design)
        pad_zone_requests = pad_zones(design)
    except DslError as error:
        raise DesignScriptError(str(error), file=str(args.design)) from error
    model, defaulted = apply_default_pad_maps(
        model, authored_symbols=design.symbols, authored_footprints=design.footprints
    )
    default_issues = [*pad_map_issues(defaulted), *device_issues(design)]
    devices = design_devices(design)
    record_footprints, record_symbols, library_issues = project_definitions(run, model)
    default_issues += library_issues
    if any(found.severity == "error" for found in library_issues):
        # a record without geometry: nothing can be resolved for it, so nothing is built (c0259)
        return Result(
            result={
                "design": design.name,
                "target": ctx.kicad_target,
                "out": str(out),
                "files": [],
                "devices": device_rows(design),
                "device_files": [{"path": file.path, "sha256": file.sha256} for file in run.device_files],
            },
            issues=tuple(default_issues),
            evidence=BUILD_EVIDENCE,
            input=InputRef(
                path=str(args.design),
                sha256=hashlib.sha256(script_path.read_bytes()).hexdigest(),
                kind="fenolite-dsl",
                format_version=None,
            ),
        )
    plan, layout_issues, model = _plan_layout(design, model, requested, script_path, ctx, args.design)
    if native_path is not None and drawing_sheet_source(design) is not None:
        raise CliError(
            "FEN-2001", "--altium-template conflicts with sheet(drawing_sheet=...)", where="--altium-template"
        )
    frame_sheet, sheet_issues, sheet_result = read_drawing_sheet_source(design, script_path)
    takes = parse_take_option(getattr(args, "take", None))
    edits, edits_file, source_issues, source_sha = read_edit_source(script_path)
    refused = any(found.severity == "error" for found in source_issues)
    if args.target == ALTIUM_TARGET:
        if (generated_records or role_record is not None) and board_path is not None:
            # with --copper-from the board wins: the records would be lost, so the build is refused (c0243)
            keys = ", ".join(
                [record.key for record in generated_records]
                + (["role_copper"] if role_record is not None else [])
            )
            source_issues = [
                *source_issues,
                kicad_generate.issue(
                    "kicad.generate.altium",
                    f"the generated-copper calls {keys} are not resolved: {args.copper_from} is the copper "
                    "source, and --copper-from wins",
                    keys,
                    "drop --copper-from to have the script's copper resolved, or build the board for KiCad",
                ),
            ]
            refused = True
        # both targets place a part from the file, and apply its value and footprint edits: the lens runs
        # without an existing project (c0069, c0250); device functions are lowered to pin numbers (c0248)
        model = lower_device_functions(model, devices)
        from_file = prepare(
            model,
            requested,
            ExistingProject(),
            name=design.name,
            edits=edits or {},
            edits_file=edits_file,
            takes=takes,
            resolver=plan.resolver if plan is not None else None,
        )
        made = _run_altium(
            args,
            ctx,
            run,
            from_file.design or model,
            cast(Mapping[str, PlacementRequest], from_file.placements),
            plane_nets,
            script_path,
            out,
            out_dir,
            board_path,
            intents,
            frame_sheet,
            sheet_result,
            meanders=meander_intents,
            generated_records=generated_records,
            role_record=role_record,
            codes=from_file.codes,
        )
        if edits is not None:
            made = dataclasses.replace(made, evidence=Evidence.combine(made.evidence, edits_mod.EVIDENCE))
        refused = refused or any(found.severity == "error" for found in from_file.issues)
        if plan is not None:
            layout_issues = [*layout_issues, *_resolution_issues(plan)]
            refused = refused or any(found.severity == "error" for found in layout_issues)
            made = dataclasses.replace(
                made,
                result={**made.result, "placement": {**plan.summary()}},
                evidence=Evidence.combine(made.evidence, RELATIVE_EVIDENCE),
            )
        return with_lock(
            dataclasses.replace(
                made,
                result={**made.result, **picks.summary()},
                issues=(
                    *source_issues,
                    *sheet_issues,
                    *default_issues,
                    *from_file.issues,
                    *layout_issues,
                    *made.issues,
                ),  # fmt: skip
                writes=() if refused else made.writes,
            ),
            lock,
        )
    resolver = LibraryResolver(
        LibraryConfig(target_major=ctx.kicad_target, project_dir=script_path.resolve().parent)
    )
    record = read_record(out_dir)
    schematic = cast(Literal["write", "skip"], args.schematic or SCHEMATIC_MODES[0])
    prepared = None
    base: edits_mod.BaseRecord | None = None
    if not args.discard_layout:
        existing = read_existing(out_dir, design.name)
        base = read_base_record(out_dir) if existing.board is not None else None
        old_poses = _layout.read_layout_record(out_dir) if plan is not None else _layout.NO_POSES
        if plan is not None and base is not None:
            base = plan.adjust_base(base, old_poses)
        sheets = (
            schematic_sheets(out_dir / f"{design.name}.kicad_sch")
            if existing.board is not None and schematic == "write"
            else None
        )
        prepared = prepare(
            model,
            requested,
            existing,
            name=design.name,
            moves=aliases,
            module_moves=module_aliases,
            net_moves=net_aliases,
            edits=edits or {},
            edits_file=edits_file,
            base=base,
            takes=takes,
            sheets=sheets,
            resolver=plan.resolver if plan is not None else None,
            adjust=plan.adjust(old_poses) if plan is not None else None,
        )
    elif edits or takes:
        # the file is source, like the script: it applies to a discarded layout too, and no output is read
        prepared = prepare(
            model, requested, ExistingProject(), name=design.name, edits=edits or {}, edits_file=edits_file,
            takes=takes, resolver=plan.resolver if plan is not None else None,
        )  # fmt: skip
    authored_footprints, authored_symbols, builtin_ids = _catalog_definitions(
        model,
        {**record_footprints, **{key: fp.definition for key, fp in design.footprints.items()}},
        {**record_symbols, **{key: symbol.definition for key, symbol in design.symbols.items()}},  # type: ignore[attr-defined]
    )
    symbol_issues: list[Issue] = []
    symbol_placements = None
    drawn_name = drawn_schematic(design)
    drawn_value = None
    drawn_depends: tuple[str, ...] = ()
    if schematic == "write" and drawn_name is not None:
        drawn_path = script_path.resolve().parent / drawn_name
        drawn_value = read_drawn_source(drawn_path, drawn_name)
        drawn_depends = depends_on(ctx.cwd, drawn_path)
    placements_path = script_path.resolve().parent / SYMBOL_PLACEMENTS_FILE
    if schematic == "write" and placements_path.is_file() and drawn_value is not None:
        symbol_issues.append(
            drawn_issue(
                "drawn.placements-ignored",
                f"{SYMBOL_PLACEMENTS_FILE} is not read: the design loads the drawn schematic {drawn_name}, "
                "which owns the symbol positions",
                SYMBOL_PLACEMENTS_FILE,
                f"delete {SYMBOL_PLACEMENTS_FILE}; move symbols in {drawn_name} or in KiCad and run sync",
            )
        )
    elif schematic == "write" and placements_path.is_file():
        symbol_placements = read_symbol_placements(
            placements_path.read_text(encoding="utf-8"), file=SYMBOL_PLACEMENTS_FILE, issues=symbol_issues
        )
    if plan is not None and prepared is None:
        requested = plan.placements()
    built = build_design(
        prepared.design if prepared is not None and prepared.design is not None else model,
        prepared.placements if prepared is not None else requested,
        name=design.name,
        copper=design.copper,
        resolver=resolver,
        target=ctx.kicad_target,
        allow_lossy=ctx.allow_lossy,
        vendor=cast(Literal["all", "project"], args.vendor),
        record=record,
        prepared=prepared,
        copper_intents=intents,
        meanders=meander_intents,
        generated_copper=generated_records,
        role_copper=role_record,
        role_planner=role_planner(role_record, script_path, out_dir),
        fields=field_requests,
        pad_zones=pad_zone_requests,
        authored_footprints=authored_footprints,
        authored_symbols=authored_symbols,
        source_sha256=source_sha,
        source_file=edits_file or PLACEMENTS_FILE,
        drawing_sheet=frame_sheet,
        schematic=schematic,
        symbol_placements=symbol_placements,
        schematic_groups={found.path: found.groups for found in block_schematics(design) if found.groups},
        schematic_layout=cast(Literal["readable", "grid"], args.schematic_layout or SCHEMATIC_LAYOUTS[0]),
        lock_stackup=stackup_locked(design),
        lock_via_protection=via_protection_locked(design),
        planes=plane_nets,
        lock_outline=outline_locked(design),
        heights=heights(design),
        unused=unused_marks(design),
        two_terminal=two_terminal(design),
        write_base=True,
        devices=devices,
        device_check=check_device,
        layout_record=plan.record() if plan is not None else None,
        drawn=drawn_value,
        drawn_file=drawn_name or "schematic.toml",
    )
    if plan is not None:
        layout_issues = [*layout_issues, *_resolution_issues(plan)]
        refused = refused or any(found.severity == "error" for found in layout_issues)
    files = {} if refused else dict(built.files)
    circuit_found = circuit_issues(
        built.design, devices=contract_devices(design), classes=classes_of(built.design)
    )  # the contracts of change c0253 judge the model with the records this build placed
    if any(found.severity == "error" for found in circuit_found):
        files = {}  # a circuit error stops the write, as every build error does (change c0252)
    _keep_confirmed_roles(out_dir, files)
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
        rules=placement_rules.rules_of(built.design),
        model=built.design,
    )
    if files:
        copper_issues, copper_check = copper_guard(
            files,
            name=design.name,
            mode=mode,
            target=ctx.kicad_target,
            waivers=built.design.findings.waivers,
        )
        if any(issue.severity == "error" for issue in copper_issues):
            files = {}  # refused: a build with an error issue plans no write
    if files:
        # the root sheet and the child sheets under sheets/: views of the script, replaced when edited
        sheets = [f"{design.name}.kicad_sch", *sorted(rel for rel in files if _child_sheet(rel))]
        if built.schematic is not None:  # a drawn sheet may lie outside sheets/ (c0276)
            sheets += sorted(rel for rel in built.schematic.children if rel in files and rel not in sheets)
        merged = {f"{design.name}{suffix}" for suffix in (".kicad_pcb", ".kicad_pro", ".kicad_dru")}
        guarded = {rel: data for rel, data in files.items() if rel not in merged and rel not in sheets}
        if record is None:
            # without the cache the base record cannot be told from a hand edit; the merge never needs the
            # cache, so a clone without .fenolite/ builds as the original does (change c0250)
            guarded.pop(edits_mod.BASE_FILE, None)
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
        "placement": placement if plan is None else {**placement, **plan.summary()},
        "drawing_sheet": sheet_result,
        "script_output": run.output,
        "devices": device_rows(design),
        "device_files": [{"path": file.path, "sha256": file.sha256} for file in run.device_files],
        **picks.summary(),
    }
    result["preserved"] = {
        **cast(Mapping[str, object], built.summary["preserved"]),
        "source": source_summary(prepared, built.issues, read=source_sha is not None, file=edits_file),
    }
    data = script_path.read_bytes()
    built_result = Result(
        result=result,
        issues=(
            *sheet_issues,
            *source_issues,
            *default_issues,
            *built.issues,
            *circuit_found,
            *symbol_issues,
            *plane_issues(plane_nets, built.layout or built.design),
            *copper_issues,
            *placement_issues,
            *layout_issues,
        ),
        evidence=Evidence.combine(
            Evidence.combine(built.evidence, edits_mod.EVIDENCE)
            if edits is not None or (base is not None and base.present)
            else built.evidence,
            RELATIVE_EVIDENCE if plan is not None else built.evidence,
        ),
        input=InputRef(
            path=str(args.design),
            sha256=hashlib.sha256(data).hexdigest(),
            kind="fenolite-dsl",
            format_version=None,
        ),
        writes=writes,
        depends=drawn_depends,
    )
    return with_lock(built_result, lock)


def _plan_layout(
    design: DslDesign,
    model: ModelDesign,
    requested: Mapping[str, PlacementRequest],
    script_path: Path,
    ctx: Context,
    given: str,
) -> tuple[_layout.LayoutPlan | None, list[Issue], ModelDesign]:
    """The placement in code of the script (change c0255; ``cli._layout``): ``None`` for a design that
    asks for none, which then builds as before. With a block reuse of ``copper=True`` the model gains the
    copied copper."""
    try:
        if not has_layout(design):
            return None, [], model
        authored, _symbols, _builtin = _catalog_definitions(
            model,
            {key: fp.definition for key, fp in design.footprints.items()},
            {key: symbol.definition for key, symbol in design.symbols.items()},  # type: ignore[attr-defined]
        )
        plan = _layout.plan_layout(
            design,
            model,
            requested=cast(Mapping[str, Any], requested),
            authored=authored,
            script_path=script_path,
            ctx=ctx,
        )
    except DslError as error:
        raise DesignScriptError(str(error), file=given) from error
    if plan is None:
        return None, [], model
    model, copper_issues, _count = _layout.reuse_copper(plan, design, model)
    return plan, [*plan.issues, *copper_issues], model


def code_placements(
    design: DslDesign,
    model: ModelDesign,
    requested: Mapping[str, PlacementRequest],
    script_path: Path,
    ctx: Context,
    given: str,
) -> Mapping[str, PlacementRequest]:
    """The code placements of the script, its relative requests, poses and strategies resolved without a
    board (change c0255): what ``sync`` compares the board with. ``requested`` when it asks for none."""
    plan, _issues, _model = _plan_layout(design, model, requested, script_path, ctx, given)
    return requested if plan is None else cast(Mapping[str, PlacementRequest], plan.placements())


def _resolution_issues(plan: _layout.LayoutPlan) -> tuple[Issue, ...]:
    """The issues of the last resolution the lens asked for (cycles, unresolved references, overflow)."""
    resolution = plan.last or plan.code
    return resolution.issues


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
    """``result.outjob`` (changes c0087 and c0138): the lens summary (``file``, ``media``, ``outputs``,
    ``gerber``, ``defaults``) with the file under ``--out``, and then the preset as given with its SHA-256;
    ``None`` without a job."""
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


def _hand_over(model: ModelDesign, resolved: ModelDesign) -> tuple[ModelDesign, ModelDesign]:
    """The script's model with the rule areas and the rules that the in-memory KiCad build added (the
    generated and role copper of change c0243: corridors, barriers, ``role.sw.*`` and ``role.hv.*``), and that
    build's design without its rule areas, which the model now holds: the Altium build writes the model's
    rule areas as keep-outs and lowers its rules, and copies only copper from a source."""
    board, done = model.board, resolved.board
    if board is None or done is None:
        return model, resolved
    held = {area.id for area in board.keepouts}
    added = tuple(area for area in done.keepouts if area.id not in held)
    rules = model.rules
    if resolved.rules is not None:
        names = {rule.name for rule in rules.rules} if rules is not None else set[str]()
        fresh = tuple(rule for rule in resolved.rules.rules if rule.name not in names)
        if fresh:
            base = rules if rules is not None else dataclasses.replace(resolved.rules, rules=())
            rules = dataclasses.replace(base, rules=(*base.rules, *fresh))
    model = dataclasses.replace(
        model, board=dataclasses.replace(board, keepouts=(*board.keepouts, *added)), rules=rules
    )
    return model, dataclasses.replace(resolved, board=dataclasses.replace(done, keepouts=()))


def altium_base(
    model: ModelDesign,
    placements: Mapping[str, PlacementRequest],
    codes: Mapping[str, Mapping[str, edits_mod.Value | None]] | None,
) -> str:
    """The base record of an Altium build: the code values and the values written, which are the code
    values there, since an Altium build has no CAD side (change c0250)."""
    script = script_codes(model, placements)
    written: dict[str, dict[str, edits_mod.Value]] = {}
    for path, values in script.items():
        written[path] = {prop: value for prop, value in values.items() if value is not None}
    held = {path: {**values, **(codes or {}).get(path, {})} for path, values in script.items()}
    return edits_mod.write_base(edits_mod.base_record(held, written, target="altium"))


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
    *,
    meanders: Sequence[MeanderIntentLike] = (),
    generated_records: Sequence[kicad_generate.GeneratedLike] = (),
    role_record: object | None = None,
    codes: Mapping[str, Mapping[str, edits_mod.Value | None]] | None = None,
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
    info names them. Change c0243: the in-memory build also runs for the generated-copper records and the
    ``role_copper`` record (with the planner of ``role_planner``), whose zones, rule areas, vias and rules
    reach the source; with ``--copper-from`` they give ``kicad.generate.altium`` (in ``execute``).

    Change c0087: unless ``--altium-outjob off``, the build writes ``<name>.OutJob`` beside a PCB
    document, for the preset of ``--altium-outjob-preset``; a kept project file is read to see whether it
    lists the job. ``drawing_sheet`` (the sheet that ``sheet(drawing_sheet=…)`` names, with its
    ``sheet_result``) is drawn on every schematic document; a loss needs ``--allow-lossy``."""
    name = run.design.name
    form = cast(SchematicForm, args.altium_format or DEFAULT_FORM)
    sheets = cast(SheetMode, args.altium_sheets or DEFAULT_SHEETS)
    # change c0086: the symbols and footprints the script authored or took from the catalog are written
    # like resolved ones, as in a KiCad build, so their graphics reach the libraries
    record_footprints, record_symbols, _ = project_definitions(run, model)
    authored_footprints, authored_symbols, _builtin = _catalog_definitions(
        model,
        {**record_footprints, **{key: fp.definition for key, fp in run.design.footprints.items()}},
        {**record_symbols, **{key: symbol.definition for key, symbol in run.design.symbols.items()}},  # type: ignore[attr-defined]
    )
    resolver = None
    scripted = bool(intents or generated_records or role_record is not None)
    if kicad_lib_ids(model) or kicad_footprint_ids(model) or scripted:
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
    project_digest: str | None = None
    project_listed: frozenset[str] | None = None
    if project_exists:
        # An existing project file is kept, with one exception (change c0138): a file with the bytes the
        # folder's state records (it is as a build wrote it) is written again when it lacks the job. The
        # lens decides, from the digest, which is None for a file changed since or without a record. The
        # file is read only to see whether it lists the job; one that cannot be read lists nothing.
        try:
            project_data = (out_dir / f"{name}.PrjPcb").read_bytes()
        except OSError:
            project_data = None
        known = (read_record(out_dir) or {}).get(f"{name}.PrjPcb")
        if project_data is not None and known == hashlib.sha256(project_data).hexdigest():
            project_digest = known
        # What the file lists is read with Fenolite's own project reader, so that the infos about a kept
        # project file name only what it lacks; a file that cannot be read gets them for every document.
        try:
            kept_project = None if project_data is None else read_project(project_data, file=f"{name}.PrjPcb")
        except FormatError:
            kept_project = None
        if kept_project is not None:
            project_listed = kept_documents([document.path for document in kept_project.documents])
            job_listed = f"{name}.OutJob".casefold() in project_listed
    if scripted and source is None:
        assert resolver is not None
        resolved = build_design(
            model,
            requested,
            name=name,
            copper=run.design.copper,
            resolver=resolver,
            target=ctx.kicad_target,
            copper_intents=intents,
            meanders=meanders,
            generated_copper=generated_records,
            role_copper=role_record,
            role_planner=role_planner(role_record, script_path, out_dir),
            # the catalog definitions too: a design that names only catalog ids has no library (c0077)
            authored_footprints=authored_footprints,
            authored_symbols=authored_symbols,
        )
        refused = not resolved.files or any(found.severity == "error" for found in resolved.issues)
        script_issues = [
            found
            for found in resolved.issues
            if found.severity == "error" or found.code.startswith(SCRIPT_COPPER_CODES)
        ]
        if not refused:
            model, handed = _hand_over(model, resolved.design)
            source = CopperSource(handed, "script")
            if model.board is not None and model.board.zones:
                # one copper source: the KiCad build kept the script's zones, so the source holds them
                model = dataclasses.replace(model, board=dataclasses.replace(model.board, zones=()))
    if refused:
        built = refused_altium(
            model, name=name, issues=script_issues, project_exists=project_exists, form=form, sheets=sheets
        )
        script_issues = []
    else:
        try:
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
                project_digest=project_digest,
                project_listed=project_listed,
                project_unreadable=project_exists and project_listed is None,
                drawing_sheet=drawing_sheet,
                allow_lossy=ctx.allow_lossy,
                authored_footprints=authored_footprints,
                directions=(args.altium_directions or DEFAULT_DIRECTIONS) == "on",
                symbol_bodies=args.altium_symbols or DEFAULT_BODIES,
                bodies=args.altium_bodies or DEFAULT_ALTIUM_BODIES,
                pour=args.altium_pour,
                authored_symbols=authored_symbols,
                heights=heights(run.design),
                unused=unused_marks(run.design),
                two_terminal=two_terminal(run.design),
                composition=schematic_composition(
                    run.design, target="altium", enabled=args.altium_layout == "blocks"
                ),
            )
        except BackendUnavailable as error:
            raise CliError(
                "FEN-6001",
                "--altium-pour computed needs the geo extra, which is not installed",
                where="--altium-pour",
                hint="pip install 'fenolite[geo]', or use --altium-pour outline",
            ) from error
    files = dict(built.files)
    circuit_found = circuit_issues(model, devices=contract_devices(run.design), classes=classes_of(model))
    if any(found.severity == "error" for found in circuit_found):
        files = {}  # a circuit error stops the write (change c0252)
    _keep_confirmed_roles(out_dir, files)
    if files and RECORD_FILE in files:
        # the base record of the Altium folder: what the build was given and wrote (change c0250)
        files[edits_mod.BASE_FILE] = altium_base(model, requested, codes).encode("utf-8")
        record = json.loads(files[RECORD_FILE])
        record["files"][edits_mod.BASE_FILE] = hashlib.sha256(files[edits_mod.BASE_FILE]).hexdigest()
        files[RECORD_FILE] = (json.dumps(record, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode(
            "utf-8"
        )
    native_info: dict[str, object] | None = None
    native_path = getattr(args, "altium_template", None)
    if native_path is not None:
        from fenolite.backends.altium.native_template import TEMPLATE_PATH, NativeTemplate

        path = Path(native_path)
        if not path.is_absolute():
            path = ctx.cwd / path
        if path.suffix.lower() != ".schdot":
            raise CliError("FEN-3001", "--altium-template must name a .SchDot file", where=str(path))
        try:
            template_data = path.read_bytes()
            native = NativeTemplate.read(template_data)
            applied = sorted(rel for rel in files if rel.endswith(".SchDoc"))
            block = run.design.block or (model.board.title_block if model.board is not None else None)
            for number, rel in enumerate(applied, 1):
                parameters = sheet_parameters(block, number, len(applied), script_issues)
                if any(found.severity == "error" for found in script_issues):
                    files = {}
                    break
                files[rel] = native.apply(files[rel], parameters=parameters)
        except (OSError, ValueError, FormatError) as error:
            raise CliError(
                "FEN-3001", f"cannot apply native Altium template: {error}", where=str(path)
            ) from None
        if files:
            files[TEMPLATE_PATH] = template_data
            record = json.loads(files[RECORD_FILE])
            for rel in (*applied, TEMPLATE_PATH):
                record["files"][rel] = hashlib.sha256(files[rel]).hexdigest()
            files[RECORD_FILE] = (
                json.dumps(record, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
            ).encode("utf-8")
            native_info = {
                "source": str(native_path),
                "file": str(out / TEMPLATE_PATH),
                "sha256": hashlib.sha256(template_data).hexdigest(),
                "pages": [str(out / rel) for rel in applied],
                "evidence": "INFERRED",
            }
    from fenolite.cli.altium_schematic_layout import prepare_files
    from fenolite.lens.altium_schematic import FILE_NAME as ALTIUM_LAYOUT_FILE
    from fenolite.lens.altium_schematic import LayoutConflict

    layout_path = script_path.resolve().parent / ALTIUM_LAYOUT_FILE
    layout_issues: tuple[Issue, ...] = ()
    native_forms: dict[str, SchematicForm] = {}
    if files:
        snapshot = layout_path.read_text(encoding="utf-8") if layout_path.is_file() else None
        try:
            files = prepare_files(files, snapshot)
            if snapshot is not None:
                from fenolite.backends.altium.read import sch as native_sch

                for relative, data in files.items():
                    if relative.startswith(".fenolite/") or not relative.lower().endswith(".schdoc"):
                        continue
                    actual = native_sch.detect(data)
                    if actual not in ("ascii", "binary"):
                        raise FormatError("saved layout is not a schematic document", file=relative)
                    native_forms[relative] = actual
        except LayoutConflict as error:
            layout_issues = error.issues
            files = {}
    mode = args.copper_check or COPPER_CHECK_MODES[0]
    copper_issues: tuple[Issue, ...] = ()
    copper_check: dict[str, object] = {"mode": mode, "ran": False}
    if files:
        copper_issues, copper_check = altium_copper_guard(
            files, name=name, mode=mode, waivers=model.findings.waivers
        )
        if any(found.severity == "error" for found in copper_issues):
            files = {}  # refused: a build with an error issue plans no write
    if files:
        check_existing(out_dir, files, record=read_record(out_dir), discard_layout=bool(args.discard_layout))
    writes = tuple(
        PlannedWrite(path=str(out / rel), data=data, kind=_kind(rel, native_forms.get(rel, form)))
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
        "pcb": summary["pcb"],
        "copper_check": copper_check,
        "outjob": _outjob_result(summary["outjob"], out, preset_result),
        "drawing_sheet": _sheet_result(summary["drawing_sheet"], out, sheet_result),
        "rules": summary["rules"],
        "experimental": summary["experimental"],
        "script_output": run.output,
    }
    if copper_input is not None:
        result["copper_input"] = copper_input
    if native_info is not None:
        result["native_template"] = native_info
    if native_forms:
        result["schematic_layout"] = {"file": str(layout_path), "formats": dict(sorted(native_forms.items()))}
    from fenolite.schematic.report import REPORT_FILE

    if REPORT_FILE in files:
        result["schematic_composition"] = json.loads(files[REPORT_FILE])
    data = script_path.read_bytes()
    evidence = built.evidence
    if board_path is not None:
        evidence = Evidence.combine(evidence, kicad_pcb.EVIDENCE)
    elif intents:
        evidence = Evidence.combine(evidence, kicad_copper.EVIDENCE, kicad_frame.EVIDENCE)
    if native_info is not None:
        from fenolite.backends.altium.native_template import EVIDENCE as native_evidence

        evidence = Evidence.combine(evidence, native_evidence)
    return Result(
        result=result,
        issues=(
            *reader_issues,
            *script_issues,
            *built.issues,
            *circuit_found,
            *copper_issues,
            *layout_issues,
        ),
        evidence=evidence,
        input=InputRef(
            path=str(args.design),
            sha256=hashlib.sha256(data).hexdigest(),
            kind="fenolite-dsl",
            format_version=None,
        ),
        writes=writes,
        depends=depends_on(ctx.cwd, layout_path),
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

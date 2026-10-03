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
"""

from __future__ import annotations

import argparse
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
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver
from fenolite.cli._script import DesignScriptError, ScriptRun, run_design_script
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.dsl import DslError, moves, placements, planes, to_model
from fenolite.lens.altium import TARGET as ALTIUM_TARGET
from fenolite.lens.altium import build_altium, kicad_footprint_ids, kicad_lib_ids
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

MINIMAL = Path(fenolite.dsl.__file__).parent / "_minimal.py"
HELP = (
    "build a design script into a KiCad project (runs DESIGN.py as your own code: never run it on an "
    "untrusted script)"
)
TARGETS = ("kicad", ALTIUM_TARGET)
ALTIUM_FORMATS: tuple[SchematicForm, ...] = ("binary", "ascii")
ALTIUM_SHEETS: tuple[SheetMode, ...] = ("flat", "modules")
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
    run = run_design_script(script_path)
    design = run.design
    try:
        model = to_model(design)
        requested = placements(design)
        aliases = moves(design)
        plane_nets = planes(design)
    except DslError as error:
        raise DesignScriptError(str(error), file=str(args.design)) from error
    if args.target == ALTIUM_TARGET:
        return _run_altium(args, ctx, run, model, requested, plane_nets, script_path, out, out_dir)
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
    )
    files = dict(built.files)
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
        "script_output": run.output,
    }
    data = script_path.read_bytes()
    return Result(
        result=result,
        issues=(*built.issues, *plane_issues(plane_nets)),
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
) -> Result:
    """The ``--target altium`` branch (capability altium-build, "Altium build target"): only the symbol
    libraries of KiCad lib ids and the footprint libraries of KiCad footprint links are read, through a
    resolver built as for ``--target kicad`` and only when
    the design has such lib ids; no external tool runs; the project file is planned only when ``DIR`` has
    none. ``--altium-sheets`` picks one sheet or one sheet per top-level module (change c0037); every planned
    sheet and harness definition file follows the edited-output rule on its own."""
    name = run.design.name
    form = cast(SchematicForm, args.altium_format or DEFAULT_FORM)
    sheets = cast(SheetMode, args.altium_sheets or DEFAULT_SHEETS)
    resolver = None
    if kicad_lib_ids(model) or kicad_footprint_ids(model):
        resolver = LibraryResolver(
            LibraryConfig(target_major=ctx.kicad_target, project_dir=script_path.resolve().parent)
        )
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
    data = script_path.read_bytes()
    return Result(
        result=result,
        issues=built.issues,
        evidence=built.evidence,
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

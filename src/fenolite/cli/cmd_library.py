# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite library BOARD --out LIB.pretty [--diff LIBRARY]``: a footprint library made from a KiCad
board, or how a library differs from the board's footprints (capability design-conversion, "Library made
from a board" and "Library command result"; ``docs/cli-contract.md``, "library"; change c0223).

The footprints come from ``fenolite.library``; this module reads the board, plans one ``.kicad_mod`` file
per footprint under ``--out``, or with ``--diff`` writes nothing and reports the drift.

Change c0261 adds action words: a first positional of ``ACTIONS`` is an action, any other the board of the
form above. ``fenolite library symbol PINS... --out FILE.kicad_sym|FILE.SchLib`` plans one symbol library
generated from pin tables (``fenolite.catalog.pins``, ``fenolite.catalog.generate.symbol``). Change c0260
adds ``fenolite library generate PACKAGE... --out DIR``: the footprints of package records drawn by
``fenolite.catalog.footprints``, with their STEP models and one Altium PCB library. The other actions are
reserved for later changes.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from decimal import Decimal
from pathlib import Path

from fenolite.backends import step as step_mod
from fenolite.backends.altium import pcblib
from fenolite.backends.altium.altsym import from_symbol_def
from fenolite.backends.altium.project import PCBLIB_KIND, SCHLIB_KIND
from fenolite.backends.altium.schlib import write_schlib
from fenolite.backends.kicad.mod import prepare_authored_definition, write_footprint
from fenolite.backends.kicad.pcb import read_board, source_info
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.backends.kicad.sym import write_symbol_library
from fenolite.catalog.footprints import DEFAULT_LIBRARY, Generated, generate, positions_of, read_package
from fenolite.catalog.generate.symbol import generate_symbol, sides
from fenolite.catalog.pins import read_pins
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.library import EVIDENCE, derive_library, drift, drift_issues
from fenolite.model.library import FootprintDef, SymbolDef

HELP = (
    "write a footprint library made from a KiCad board, or report how a library differs from it; "
    "'library symbol PINS... --out FILE' writes symbols generated from pin tables; "
    "'library generate PACKAGE... --out DIR' writes footprints, STEP models and a PcbLib from package records"
)
PRETTY = ".pretty"
WRITE_KIND = "kicad_mod"
ACTIONS = ("symbol", "generate", "check", "review", "import", "propose", "fetch")
"""The action words of ``fenolite library`` (change c0261; ``generate`` change c0260); a first positional of
another text is a board."""
AVAILABLE = frozenset({"symbol", "generate"})
"""The actions this version runs; the others are reserved (``FEN-2001``) until their changes land: ``check``
and ``review`` (c0262), ``import`` (c0264), ``propose`` (c0265) and ``fetch`` (c0266)."""
SYMBOL_SUFFIXES = {".kicad_sym": "kicad_sym", ".SchLib": SCHLIB_KIND}
_LIBRARY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$")
SYMBOL_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-SYMBOL-LAYOUT", "H-K-SYM-UNITS-WRITE"))
"""A generated KiCad symbol library: the layout rule is Fenolite's; see
``H-K-SYM-UNITS-WRITE``."""
SCHLIB_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-SYMBOL-LAYOUT", "H-A-SCHLIB-GEN-PARTS"))
GENERATE_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-LAND-CALC", "H-K-STEP-MODELS"))
"""Generated footprints: the land calculator and the conventions are Fenolite's (``H-G-LAND-CALC``);
KiCad's reading of the STEP models is ``H-K-STEP-MODELS``."""
STEP_KIND = "step"


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'library'."
    parser.add_argument(
        "path",
        metavar="PATH",
        nargs="+",
        help="a .kicad_pcb, .kicad_pro or project folder; or the action 'symbol' followed by pin tables, "
        "or 'generate' followed by package records",
    )
    parser.add_argument(
        "--out",
        metavar="LIB.pretty",
        help="the library folder to write, relative; for 'symbol', a relative .kicad_sym or .SchLib file; "
        "for 'generate', a relative folder",
    )
    parser.add_argument(
        "--diff", metavar="LIBRARY", help="a .pretty folder to compare with the board; writes nothing"
    )
    parser.add_argument(
        "--library",
        metavar="NAME",
        help="'symbol' and 'generate' only: the library name (default: the stem of --out for 'symbol', "
        "Local for 'generate')",
    )
    parser.add_argument(
        "--positions",
        metavar="N",
        type=int,
        help="'generate' only: the one position count to draw of a connector series (default: every count)",
    )
    parser.add_argument(
        "--no-step",
        action="store_true",
        help="'generate' only: plan no .step model (the footprint keeps its path)",
    )
    parser.add_argument("--no-pcblib", action="store_true", help="'generate' only: plan no Altium .PcbLib")


def _relative(path: Path, cwd: Path) -> str:
    try:
        return Path(os.path.relpath(path, cwd)).as_posix()
    except ValueError:  # another Windows drive
        return path.as_posix()


def _symbol_row(symbol: SymbolDef, flat: SymbolDef, issues: list[Issue]) -> dict[str, object]:
    row: dict[str, object] = {"name": symbol.name}
    if symbol.extends:
        row["extends"] = symbol.extends
    names = {unit.unit: unit.name for unit in flat.units}
    row["units"] = [
        {
            "unit": unit,
            "name": names.get(unit, ""),
            "pins": {k: list(v) for k, v in sides(flat, unit).items()},
        }
        for unit in range(1, flat.unit_count + 1)
    ]
    row["issues"] = sorted({issue.code for issue in issues})
    return row


def _symbols(args: argparse.Namespace, ctx: Context) -> Result:
    """``fenolite library symbol PINS... --out FILE``: one library of the symbols of the pin tables."""
    tables = list(args.path[1:])
    if not tables:
        raise CliError("FEN-2001", "library symbol needs at least one pin table", hint="pass pins/NAME.toml")
    if args.diff is not None:
        raise CliError("FEN-2001", "library symbol takes no --diff", where="--diff")
    out = args.out
    suffix = next((s for s in SYMBOL_SUFFIXES if isinstance(out, str) and out.endswith(s)), None)
    if out is None or Path(out).is_absolute() or suffix is None:
        raise CliError(
            "FEN-2001",
            "library symbol needs --out, a relative .kicad_sym or .SchLib file",
            where="--out",
            hint="pass --out lib/NAME.kicad_sym",
        )
    library = args.library if args.library is not None else Path(out).name.removesuffix(suffix)
    if not _LIBRARY.fullmatch(library):
        raise CliError("FEN-2001", f"unsafe library name {library!r}", where="--library")
    issues: list[Issue] = []
    symbols: list[SymbolDef] = []
    rows: list[dict[str, object]] = []
    paths: list[Path] = []
    first: tuple[str, bytes] | None = None
    for name in tables:
        path = Path(name) if Path(name).is_absolute() else ctx.cwd / name
        if not path.is_file():
            raise CliError("FEN-3001", f"pin table {name} is not a file", where=name)
        data = path.read_bytes()
        first = first or (path.name, data)
        paths.append(path)
        table = read_pins(path)
        base, derived, found = generate_symbol(table, library=library)
        issues += found
        for symbol in (base, *derived):
            if any(s.name == symbol.name for s in symbols):
                raise CliError("FEN-3004", f"two pin tables give the symbol {symbol.name!r}", where=name)
            flat = base if symbol is not base else symbol
            rows.append(_symbol_row(symbol, flat, list(found) if symbol is base else []))
            symbols.append(symbol)
    kind = SYMBOL_SUFFIXES[suffix]
    if kind == "kicad_sym":
        data = write_symbol_library(symbols, target=ctx.kicad_target).encode("utf-8")
        evidence = SYMBOL_EVIDENCE
    else:
        bases = [s for s in symbols if not s.extends]
        mapped = [
            from_symbol_def(s, lib_ref=s.name, footprint=None, issues=issues, parents=bases) for s in symbols
        ]
        data = write_schlib(mapped, library=Path(out).name)
        evidence = SCHLIB_EVIDENCE
    assert first is not None
    written = Path(str(out)).as_posix()
    return Result(
        result={"library": library, "out": written, "format": kind, "symbols": rows},
        issues=tuple(issues),
        evidence=evidence,
        input=InputRef(first[0], hashlib.sha256(first[1]).hexdigest(), "pins", "0"),
        writes=(PlannedWrite(written, data, kind),),
        depends=depends_on(ctx.cwd, *paths),
    )


def _only_generate(args: argparse.Namespace, form: str) -> None:
    for flag, given in (
        ("--positions", args.positions is not None),
        ("--no-step", args.no_step),
        ("--no-pcblib", args.no_pcblib),
    ):
        if given:
            raise CliError("FEN-2001", f"{flag} belongs to 'library generate', not to '{form}'", where=flag)


def _corner_extras(defn: FootprintDef) -> dict[str, pcblib.PadExtras]:
    """The pad extras of a generated footprint: its rounded rectangles carry ``Pad.corner_ratio``."""
    return {
        pad.id: pcblib.PadExtras(None if pad.corner_ratio is None else Decimal(pad.corner_ratio) / 1_000_000)
        for pad in defn.pads
    }


def _package_row(generated: Generated, family: str, library: str, files: list[str]) -> dict[str, object]:
    land = generated.land
    footprint = generated.footprint
    row: dict[str, object] = {
        "name": generated.name,
        "family": family,
        "id": f"{library}:{generated.name}",
        "stamp": generated.stamp,
        "land": {
            "source": land.source,
            "evidence": land.evidence,
            "table": land.table,
            "z": land.z,
            "g": land.g,
            "x": land.x,
            "pad": None if land.pad is None else list(land.pad),
            "drill": land.drill,
            "pad_diameter": land.pad_diameter,
            "deltas": dict(sorted(land.deltas.items())),
        },
        "courtyard": None if generated.courtyard is None else list(generated.courtyard),
        "bodies": {
            "count": 0 if footprint is None else len(footprint.bodies),
            "top": max((b.z_max for b in footprint.bodies if b.z_max is not None), default=None)
            if footprint is not None
            else None,
        },
        "files": files,
        "issues": sorted({issue.code for issue in generated.issues}),
    }
    return row


def _generate(args: argparse.Namespace, ctx: Context) -> Result:
    """``fenolite library generate PACKAGE... --out DIR``: the footprints of package records, their STEP
    models and one PCB library, all planned together."""
    records = list(args.path[1:])
    if not records:
        raise CliError(
            "FEN-2001", "library generate needs at least one package record", hint="pass packages/NAME.toml"
        )
    if args.diff is not None:
        raise CliError("FEN-2001", "library generate takes no --diff", where="--diff")
    out = args.out
    if out is None or Path(out).is_absolute() or Path(out).suffix in (PRETTY, ".PcbLib", ".kicad_sym"):
        raise CliError(
            "FEN-2001",
            "library generate needs --out, a relative folder",
            where="--out",
            hint="pass --out lib",
        )
    library = args.library if args.library is not None else DEFAULT_LIBRARY
    if not _LIBRARY.fullmatch(library):
        raise CliError("FEN-2001", f"unsafe library name {library!r}", where="--library")
    folder = Path(str(out)).as_posix().rstrip("/")
    issues: list[Issue] = []
    rows: list[dict[str, object]] = []
    writes: list[PlannedWrite] = []
    drawn: list[FootprintDef] = []
    paths: list[Path] = []
    first: tuple[str, bytes] | None = None
    for name in records:
        path = Path(name) if Path(name).is_absolute() else ctx.cwd / name
        if not path.is_file():
            raise CliError("FEN-3001", f"package record {name} is not a file", where=name)
        data = path.read_bytes()
        first = first or (path.name, data)
        paths.append(path)
        package = read_package(data.decode("utf-8"), file=path.name)
        counts = positions_of(package)
        if args.positions is not None:
            if not counts:
                raise CliError(
                    "FEN-2001",
                    f"--positions applies to a connector series, not to the {package.family} record {name}",
                    where="--positions",
                )
            counts = (args.positions,)
        for count in counts or (None,):
            generated = generate(package, positions=count, library=library)
            issues += generated.issues
            files: list[str] = []
            footprint = generated.footprint
            if footprint is not None:
                if any(d.name == footprint.name for d in drawn):
                    raise CliError(
                        "FEN-3004", f"two records give the footprint {footprint.name!r}", where=name
                    )
                drawn.append(footprint)
                mod_path = f"{folder}/{library}.pretty/{footprint.name}.kicad_mod"
                text = write_footprint(
                    prepare_authored_definition(footprint),
                    target=ctx.kicad_target,
                    allow_lossy=ctx.allow_lossy,
                )
                writes.append(PlannedWrite(mod_path, text.encode("utf-8"), WRITE_KIND))
                files.append(mod_path)
                if footprint.bodies and not args.no_step:
                    step_path = f"{folder}/{library}.3dshapes/{footprint.name}.step"
                    writes.append(
                        PlannedWrite(
                            step_path, step_mod.write_bodies(footprint.name, footprint.bodies), STEP_KIND
                        )
                    )
                    files.append(step_path)
            rows.append(_package_row(generated, package.family, library, files))
    pcblib_path = None
    if drawn and not args.no_pcblib:
        kept: list[pcblib.LibFootprint] = []
        for defn in drawn:
            extras = _corner_extras(defn)
            check = pcblib.check_footprint(defn, extras)
            where = f"{library}:{defn.name}"
            if check.refusal is not None:
                issues.append(
                    Issue(
                        "altium.footprint-unsupported",
                        "warning",
                        f"{where}: {check.refusal}; the footprint is not written to the PcbLib",
                        where=where,
                    )
                )
                continue
            if check.dropped:
                counted = sorted({d: check.dropped.count(d) for d in check.dropped}.items())
                left = ", ".join(f"{n} x {d}" if n > 1 else d for d, n in counted)
                issues.append(
                    Issue("altium.primitive-dropped", "warning", f"{where}: left out: {left}", where=where)
                )
            kept.append(pcblib.LibFootprint(defn, extras))
        if kept:
            pcblib_path = f"{folder}/{library}.PcbLib"
            data = pcblib.write_pcblib(kept, filename=f"{library}.PcbLib")
            writes.append(PlannedWrite(pcblib_path, data, PCBLIB_KIND))
    assert first is not None
    return Result(
        result={"library": library, "out": folder, "pcblib": pcblib_path, "packages": rows},
        issues=tuple(issues),
        evidence=GENERATE_EVIDENCE,
        input=InputRef(first[0], hashlib.sha256(first[1]).hexdigest(), "package", "0"),
        writes=tuple(writes),
        depends=depends_on(ctx.cwd, *paths),
    )


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    action = args.path[0]
    if action in ACTIONS:
        if action not in AVAILABLE:
            raise CliError(
                "FEN-2001",
                f"library {action} is not available in this version",
                where=action,
                hint="pass ./" + action + " for a board folder of that name",
            )
        if action == "generate":
            return _generate(args, ctx)
        _only_generate(args, "library symbol")
        return _symbols(args, ctx)
    _only_generate(args, "library")
    if len(args.path) > 1:
        raise CliError("FEN-2001", f"library takes one board, not {len(args.path)} paths", where=args.path[1])
    if args.library is not None:
        raise CliError("FEN-2001", "--library belongs to 'library symbol'", where="--library")
    args.path = action
    if args.out is None and args.diff is None:
        raise CliError("FEN-2001", "library needs --out or --diff", hint="pass --out lib.pretty")
    if args.out is not None and (Path(args.out).is_absolute() or not args.out.endswith(PRETTY)):
        raise CliError(
            "FEN-2001", "--out must be a relative .pretty folder", where="--out", hint="pass --out lib.pretty"
        )
    board_path = resolve_board(Path(args.path) if Path(args.path).is_absolute() else ctx.cwd / args.path)
    data = board_path.read_bytes()
    text = data.decode("utf-8")
    source = source_info(read_board(text, file=board_path.name))
    major = source.major if source is not None and source.major is not None else ctx.kicad_target
    library_name = Path(args.out).name.removesuffix(PRETTY) if args.out else board_path.stem
    derived = derive_library(text, library=library_name, target=major, file=board_path.name)
    issues = list(derived.issues)
    result: dict[str, object] = {"board": board_path.name}
    writes: tuple[PlannedWrite, ...] = ()
    depends = [board_path]
    if args.diff is not None:
        folder = Path(args.diff) if Path(args.diff).is_absolute() else ctx.cwd / args.diff
        if not folder.is_dir():
            raise CliError("FEN-3001", f"--diff: {args.diff} is not a folder", where="--diff")
        rows = drift(derived, folder)
        issues.extend(drift_issues(rows))
        result["library"] = _relative(folder, ctx.cwd)
        result["drift"] = [{"name": name, "kinds": list(kinds)} for name, kinds in rows]
        depends.extend(sorted(folder.glob("*.kicad_mod")))
    else:
        out = Path(str(args.out)).as_posix()
        result["library"] = out
        result["footprints"] = [
            {"name": fp.name, "source": fp.source, "refs": list(fp.refs)} for fp in derived.footprints
        ]
        writes = tuple(
            PlannedWrite(f"{out}/{name}", body.encode("utf-8"), WRITE_KIND)
            for name, body in sorted(derived.files().items())
        )
    return Result(
        result=result,
        issues=tuple(issues),
        evidence=EVIDENCE,
        input=InputRef(
            board_path.name,
            hashlib.sha256(data).hexdigest(),
            "kicad_pcb",
            str(source.version) if source is not None else None,
        ),
        writes=writes,
        depends=depends_on(ctx.cwd, *depends),
    )


_EXAMPLE = (EXAMPLE_BOARD, "--out", "fenolite-lib.pretty")
COMMAND = Command(
    name="library",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    paged="drift|footprints|symbols|packages",
    example_args=(*_EXAMPLE, "--dry-run"),
    mutation_example_args=_EXAMPLE,
)

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite library BOARD --out LIB.pretty [--diff LIBRARY]``: a footprint library made from a KiCad
board, or how a library differs from the board's footprints (capability design-conversion, "Library made
from a board" and "Library command result"; ``docs/cli-contract.md``, "library"; change c0223).

The footprints come from ``fenolite.library``; this module reads the board, plans one ``.kicad_mod`` file
per footprint under ``--out``, or with ``--diff`` writes nothing and reports the drift.

Change c0261 adds action words: a first positional of ``ACTIONS`` is an action, any other the board of the
form above. ``fenolite library symbol PINS... --out FILE.kicad_sym|FILE.SchLib`` plans one symbol library
generated from pin tables (``fenolite.catalog.pins``, ``fenolite.catalog.generate.symbol``); the other
actions are reserved for later changes.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from pathlib import Path

from fenolite.backends.altium.altsym import from_symbol_def
from fenolite.backends.altium.project import SCHLIB_KIND
from fenolite.backends.altium.schlib import write_schlib
from fenolite.backends.kicad.pcb import read_board, source_info
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.backends.kicad.sym import write_symbol_library
from fenolite.catalog.generate.symbol import generate_symbol, sides
from fenolite.catalog.pins import read_pins
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.library import EVIDENCE, derive_library, drift, drift_issues
from fenolite.model.library import SymbolDef

HELP = (
    "write a footprint library made from a KiCad board, or report how a library differs from it; "
    "'library symbol PINS... --out FILE' writes symbols generated from pin tables"
)
PRETTY = ".pretty"
WRITE_KIND = "kicad_mod"
ACTIONS = ("symbol", "check", "review", "import", "propose", "fetch")
"""The action words of ``fenolite library`` (change c0261); a first positional of another text is a board."""
AVAILABLE = frozenset({"symbol"})
"""The actions this version runs; the others are reserved (``FEN-2001``) until their changes land: ``check``
and ``review`` (c0262), ``import`` (c0264), ``propose`` (c0265) and ``fetch`` (c0266)."""
SYMBOL_SUFFIXES = {".kicad_sym": "kicad_sym", ".SchLib": SCHLIB_KIND}
_LIBRARY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$")
SYMBOL_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-SYMBOL-LAYOUT", "H-K-SYM-UNITS-WRITE"))
"""A generated KiCad symbol library: the layout rule is Fenolite's; see
``H-K-SYM-UNITS-WRITE``."""
SCHLIB_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-SYMBOL-LAYOUT", "H-A-SCHLIB-GEN-PARTS"))


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'library'."
    parser.add_argument(
        "path",
        metavar="PATH",
        nargs="+",
        help="a .kicad_pcb, .kicad_pro or project folder; or the action 'symbol' followed by pin tables",
    )
    parser.add_argument(
        "--out",
        metavar="LIB.pretty",
        help="the library folder to write, relative; for 'symbol', a relative .kicad_sym or .SchLib file",
    )
    parser.add_argument(
        "--diff", metavar="LIBRARY", help="a .pretty folder to compare with the board; writes nothing"
    )
    parser.add_argument(
        "--library", metavar="NAME", help="'symbol' only: the library name (default: the stem of --out)"
    )


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
        return _symbols(args, ctx)
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
    paged="drift|footprints|symbols",
    example_args=(*_EXAMPLE, "--dry-run"),
    mutation_example_args=_EXAMPLE,
)

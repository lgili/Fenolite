# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite import PATH --to python --out DIR``: a KiCad board turned into a Fenolite project folder
(change c0275; capability board-to-code; ``docs/import.md``; ``docs/cli-contract.md``, "import").

The folder holds ``design.py``, ``copper.py`` (the copper as tables), the vendored ``lib/`` with its project
tables, ``design.lock`` and ``PROVENANCE.json``, and copies of the ``--licence-file`` files. Before anything
is planned the emitted code is built in a private temporary folder and compared with the source at
equivalence levels 1 to 5; an unexplained difference is ``import.unequal`` (exit 5) and nothing is written.
An item the DSL cannot express refuses the import (exit 7, ``FEN-7001``) unless ``--allow-lossy``.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from fenolite import __version__
from fenolite.api import convert, read_board, run
from fenolite.backends.altium.read.project import read_project
from fenolite.backends.kicad.cli import find_kicad_cli
from fenolite.cli.api import Command, Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.evidence import Evidence
from fenolite.importer import EVIDENCE
from fenolite.importer.adopt import Adopted, adopt
from fenolite.importer.check import self_check
from fenolite.importer.codes import issue
from fenolite.importer.coverage import Unexpressed, lossy_issues
from fenolite.importer.emit import Emission, Options, emit
from fenolite.importer.emit.design import design_name
from fenolite.importer.provenance import Provenance, record
from fenolite.importer.source import InputFile, InputKindError, Source, input_kind, read_kicad
from fenolite.importer.upgrade import upgrader

HELP = "turn a KiCad or Altium board into a Fenolite project folder (design.py, copper tables, library)"
TARGETS = ("python",)
EXAMPLE = str(Path(__file__).resolve().parents[3] / "tests/data/import_python/two_sheet/two_sheet.kicad_pro")
"""The authored two-sheet project of the test data."""
WRITE_KINDS = {".py": "python", ".lock": "lock", ".json": "json", ".kicad_mod": "kicad_mod",
               ".kicad_sym": "kicad_sym", ".kicad_pcb": "kicad_pcb", ".kicad_pro": "kicad_pro"}  # fmt: skip


class LossyImportError(FenoliteError):
    """Items of the source no DSL call expresses, and no ``--allow-lossy`` (``FEN-7001``): ``issues`` holds
    one ``import.item-unexpressed`` per kind."""

    cli_code = "FEN-7001"

    def __init__(self, rows: tuple[Unexpressed, ...]) -> None:
        self.issues = lossy_issues(rows)
        self.hint = "re-run with --allow-lossy to leave them out, each kind reported"
        super().__init__(
            f"the DSL cannot express {sum(r.count for r in rows)} item(s) of the source "
            f"({', '.join(r.kind for r in rows)})"
        )


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/import.md."
    parser.add_argument(
        "path", metavar="PATH", help="a .kicad_pro, .kicad_pcb, .kicad_sch, .PrjPcb or .PcbDoc"
    )
    parser.add_argument("--to", choices=TARGETS, required=True, help="the target: python (the Fenolite DSL)")
    parser.add_argument("--out", metavar="DIR", required=True, help="the project folder to write")
    parser.add_argument("--name", help="the design name; default: the project's stem")
    parser.add_argument("--licence", metavar="SPDX", help="the upstream licence as an SPDX expression")
    parser.add_argument(
        "--copyright", metavar="TEXT", action="append", default=[], help="an upstream copyright holder"
    )
    parser.add_argument("--source", metavar="URL", help="where the upstream board lives")
    parser.add_argument("--revision", metavar="REV", help="the upstream revision imported")
    parser.add_argument(
        "--licence-file",
        metavar="FILE",
        action="append",
        default=[],
        help="an upstream LICENSE, NOTICE or COPYING file, copied unchanged",
    )
    parser.add_argument(
        "--adopt",
        action="store_true",
        help="also write adopted/: the source board with the identities a build derives",
    )
    parser.add_argument("--no-upgrade", action="store_true", help="refuse a file below the read floor")
    parser.add_argument("--no-verify", action="store_true", help="skip the self-check build")


def _absolute(path: str, ctx: Context) -> Path:
    given = Path(path)
    return given if given.is_absolute() else ctx.cwd / given


def _check_out(out: Path, folder: Path) -> None:
    out_full, folder_full = Path(os.path.abspath(out)), Path(os.path.abspath(folder))
    if out_full == folder_full or folder_full.is_relative_to(out_full):
        raise CliError(
            "FEN-2001",
            f"--out {out.name} is the folder of the source or holds it; an import never writes over its "
            "source",
            where="--out",
            hint="name another folder with --out",
        )


def _altium(path: Path, args: argparse.Namespace, ctx: Context) -> tuple[Source, list[Issue]]:
    """An Altium project or PCB document read through Fenolite's Altium reader and converted in memory to
    a KiCad project (``fenolite.api.convert``, verified against the source), whose board the one emitter
    imports; the inputs recorded are the Altium files (design decision 14)."""
    if args.adopt:
        raise CliError(
            "FEN-2001",
            "--adopt takes a KiCad board; the input is Altium",
            where="--adopt",
            hint="drop --adopt",
        )
    found = convert(path, to="kicad", kicad_version=ctx.kicad_target, allow_lossy=ctx.allow_lossy)
    conversion = found.conversion
    with tempfile.TemporaryDirectory(prefix="fenolite-import-altium-") as folder:
        root = Path(folder)
        for name, data in conversion.files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        project = next(root.glob("*.kicad_pro"), None) or next(root.glob("*.kicad_pcb"))
        read = read_kicad(project)
    origin = conversion.source
    listed = set(origin.files.values())
    if origin.path.suffix.lower() == ".prjpcb":
        project = read_project(origin.path.read_bytes(), file=origin.path.name)
        listed |= {origin.path.parent / document.path for document in project.documents}
    files = [origin.path, *sorted({p for p in listed if p.is_file()} - {origin.path}, key=lambda p: p.name)]
    inputs = tuple(
        InputFile(p.name, hashlib.sha256(p.read_bytes()).hexdigest(), p.suffix.lower().lstrip("."), None)
        for p in files
        if p.is_file()
    )
    source = dataclasses.replace(
        read, name=origin.path.stem, backend="altium", inputs=inputs, paths=tuple(files), folder=origin.root,
        sheets=0,
    )  # fmt: skip
    return source, [i for i in found.issues if i.severity == "error" or i.code != "convert.no-verify"]


def _read(path: Path, args: argparse.Namespace, ctx: Context) -> tuple[Source, list[Issue]]:
    try:
        kind = input_kind(path)
    except InputKindError as error:
        raise CliError("FEN-2001", str(error), where=path.name, hint=error.hint) from None
    if kind == "altium":
        return _altium(path, args, ctx)
    upgrade = None if args.no_upgrade else upgrader(find_kicad_cli())
    return read_kicad(path, upgrade=upgrade), []


def _build(emission: Emission, name: str, major: int, ctx: Context) -> tuple[list[Issue], Any, str]:
    """The emitted files built in a private temporary folder for KiCad ``major``: the issues, the built
    design and its board text."""
    with tempfile.TemporaryDirectory(prefix="fenolite-import-") as folder:
        root = Path(folder)
        for relative, data in emission.files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        reply = run(
            "build", "design.py", "--out", "built", "--confirm", "--kicad-version", str(major),
            "--copper-check", "warn", "--schematic", "skip",
            cwd=root, timestamp=ctx.timestamp,
        )  # fmt: skip
        if reply.exit_code != 0:
            message = (reply.error or {}).get("message", "the build failed")
            found = [i for i in (reply.envelope or {}).get("issues", []) if i.get("severity") == "error"]
            shown = "; ".join(f"{i['code']}: {i['message']}" for i in found[:3]) or message
            return (
                [issue("import.unequal", f"the emitted code does not build: {shown}", where="build")],
                None,
                "",
            )
        board = root / "built" / f"{name}.kicad_pcb"
        return [], read_board(board).design, board.read_text(encoding="utf-8")


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    path = _absolute(args.path, ctx)
    if not path.exists():
        raise CliError("FEN-3001", f"{path.name} does not exist", where=path.name)
    out = _absolute(args.out, ctx)
    _check_out(out, path.parent)
    licence_files = [_absolute(name, ctx) for name in args.licence_file]
    for given in licence_files:
        if not given.is_file():
            raise CliError("FEN-3001", f"--licence-file {given.name} does not exist", where="--licence-file")
    if args.adopt and args.no_verify:
        raise CliError(
            "FEN-2001",
            "--adopt needs the build of the self-check; it cannot be combined with --no-verify",
            where="--adopt",
            hint="drop --no-verify",
        )
    source, converted = _read(path, args, ctx)
    name = design_name(args.name or source.name)
    issues: list[Issue] = [*source.issues, *converted]
    stamped = getattr(args, "timestamp", None) is not None
    if not stamped:
        issues.append(
            issue(
                "import.timestamp-missing",
                "no --timestamp: the header and PROVENANCE.json carry today's date, so the output is not "
                "reproducible",
                hint="pass --timestamp to make the bytes reproducible",
            )
        )
    if args.licence is None or not args.copyright or args.source is None:
        missing = [flag for flag, value in (("--licence", args.licence), ("--copyright", args.copyright),
                                            ("--source", args.source)) if not value]  # fmt: skip
        issues.append(
            issue(
                "import.provenance-missing",
                f"no {', '.join(missing)}: the header says NOASSERTION where the upstream is not stated",
                hint="state the upstream licence, copyright and location; converted boards are published "
                "only with them",
            )
        )
    notices = tuple(sorted({given.name for given in licence_files}))
    provenance = Provenance(
        licence=args.licence,
        copyright=tuple(args.copyright),
        source=args.source,
        revision=args.revision,
        fenolite=__version__,
        date=ctx.timestamp.date().isoformat(),
        notices=notices,
    )
    target = source.major if source.major in (9, 10) else ctx.kicad_target
    emission = emit(source, Options(name, provenance, target=target))
    if emission.unexpressed and not ctx.allow_lossy:
        raise LossyImportError(emission.unexpressed)
    issues += emission.issues
    issues += lossy_issues(emission.unexpressed)
    for row in source.upgrades:
        issues.append(
            issue(
                "import.upgraded",
                f"{row.file} was upgraded from format version {row.from_version} to {row.to_version} by "
                f"kicad-cli {row.tool_version} on a private copy; the source is unchanged",
                where=row.file,
            )
        )
    if source.sheets:
        issues.append(
            issue(
                "import.schematic-generated",
                f"the source has {source.sheets} schematic sheet(s); the build generates its own schematic "
                "until "
                "the drawn schematic (c0276) is imported",
                where="schematic",
            )
        )
    equivalence: dict[str, object] | None = None
    adopted: Adopted | None = None
    if args.no_verify:
        issues.append(issue("import.unverified", "--no-verify: the emitted code was not built and compared"))
    else:
        build_issues, built, built_text = _build(emission, name, target, ctx)
        issues += build_issues
        if built is not None:
            checked = self_check(source.design, built, emission.unexpressed, variants=emission.variants)
            issues += checked.issues
            equivalence = checked.as_json()
            if args.adopt:
                adopted = adopt(source.board_text, source.design, built_text, built)
        else:
            equivalence = {"levels": [], "equivalent": False}
    findings = Counter(found.code for found in issues if found.code.startswith("import."))
    for row in emission.unexpressed:
        findings[f"unexpressed.{row.kind}"] = row.count
    files = dict(emission.files)
    files["PROVENANCE.json"] = record(
        provenance,
        design=name,
        inputs=source.inputs,
        upgrades=source.upgrades,
        findings=dict(findings),
        equivalence=equivalence,
        tools={row.tool: row.tool_version for row in source.upgrades},
    ).encode("utf-8")
    for given in licence_files:
        files[given.name] = given.read_bytes()
    if adopted is not None:
        files[f"adopted/{name}.kicad_pcb"] = adopted.text.encode("utf-8")
        project = next((p for p in source.paths if p.suffix == ".kicad_pro"), None)
        if project is not None:
            files[f"adopted/{name}.kicad_pro"] = project.read_bytes()
    shown_out = Path(args.out).as_posix()
    writes = tuple(
        PlannedWrite(f"{shown_out}/{relative}", data, WRITE_KINDS.get(Path(relative).suffix, "text"))
        for relative, data in sorted(files.items())
    )
    read_file = source.paths[0]
    version = next((row.version for row in source.inputs if row.file == read_file.name), None)
    result: dict[str, Any] = {
        "source": {
            "file": read_file.name,
            "backend": source.backend,
            "versions": {row.file: row.version for row in source.inputs if row.version is not None},
        },
        "out": shown_out,
        "design": name,
        "files": [{"path": relative, "bytes": len(data)} for relative, data in sorted(files.items())],
        "modules": list(emission.modules),
        "counts": dict(emission.counts),
        "unexpressed": [row.as_json() for row in emission.unexpressed],
        "upgrade": [row.as_json() for row in source.upgrades],
        "equivalence": equivalence,
        "provenance": {"licence": provenance.spdx, "source": args.source, "revision": args.revision},
        "adopted": None if adopted is None else {"board": f"adopted/{name}.kicad_pcb", **adopted.as_json()},
    }
    return Result(
        result=result,
        issues=tuple(issues),
        evidence=Evidence(
            EVIDENCE.level,
            hypotheses=(
                *EVIDENCE.hypotheses,
                *(("H-A-IMPORT-CODE",) if source.backend == "altium" else ()),
                *(("H-K-IMPORT-UPGRADE",) if source.upgrades else ()),
                *(("H-K-IMPORT-ADOPT",) if adopted is not None else ()),
            ),
        ),
        input=InputRef(
            read_file.name,
            hashlib.sha256(read_file.read_bytes()).hexdigest(),
            read_file.suffix.lower().lstrip("."),
            None if version is None else str(version),
        ),
        writes=writes,
        depends=depends_on(ctx.cwd, *source.paths, *licence_files),
    )


_EXAMPLE = (EXAMPLE, "--to", "python", "--out", "fenolite-import")
COMMAND = Command(
    name="import",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    paged="files|unexpressed",
    example_args=(*_EXAMPLE, "--dry-run"),
    mutation_example_args=_EXAMPLE,
)

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite manifest PATH``: the project manifest, with the SHA-256 and a state for every design file and
artefact (capability cli-contract, "Manifest command"; manufacturing-exports, "Project manifest";
``docs/cli-contract.md``, "manifest"; user guide ``docs/exports.md``).

The command hashes every file again, runs the stages of ``check`` exactly as ``check`` does, and writes
one file. A state is read from a stage result, never judged here: ``fenolite.exports.states`` holds the
rules. ``--verify`` compares an existing manifest with the files on disk and writes nothing.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from fenolite.backends.kicad import sch
from fenolite.backends.kicad.libs import read_lib_table
from fenolite.backends.kicad.projectset import project_set, resolve_board
from fenolite.checks import DEFAULT_STAGES, STAGE_ORDER
from fenolite.cli._examples import EXAMPLE_BOARD
from fenolite.cli._kicadtool import DEFAULT_TIMEOUT, board_format
from fenolite.cli._manifest import FENOLITE, FENOLITE_TOOL, read_folder
from fenolite.cli.api import Command, Context, PlannedWrite, Result
from fenolite.cli.cmd_check import Checked, parse_stages, run_stages
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FenoliteError, FormatError, Issue
from fenolite.core.evidence import Evidence
from fenolite.exports import manifest, states
from fenolite.exports.codes import issue
from fenolite.lens.build import read_record

HELP = "write the project manifest: every design file and artefact with its SHA-256 and a state"
NO_TOOL_HINT = (
    "install KiCad 9 or 10, set FENOLITE_KICAD_CLI or pass --kicad-cli; or pass --no-check to record "
    "hashes only, or --stages model.validate,copper.clearance,roundtrip to run the stages that need no tool"
)
CACHE_DIR = ".fenolite"
BACKUP_SUFFIX = ".bak"
KICAD_SUFFIX = ".kicad_"
SYMBOL_TABLE = "sym-lib-table"
_KIPRJMOD = re.compile(r"^\$\{KIPRJMOD\}[/\\](.+)$")
ENTRY_KEYS = ("path", "kind", "state", "stale", "held")


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/exports.md."
    parser.add_argument("path", metavar="PATH", help="a .kicad_pcb, a .kicad_pro or a project folder")
    parser.add_argument(
        "--artifacts",
        action="append",
        default=[],
        metavar="DIR",
        help=f"a folder inside the project whose {manifest.FILE_NAME} lists artefacts to add (repeatable)",
    )
    parser.add_argument(
        "--stages",
        metavar="A,B",
        help=f"stages to run, of {','.join(STAGE_ORDER)} (default: {','.join(DEFAULT_STAGES)})",
    )
    parser.add_argument("--no-check", action="store_true", help="run no stage: record hashes only")
    parser.add_argument(
        "--verify", action="store_true", help="compare the manifest with the files on disk; write nothing"
    )
    parser.add_argument(
        "-o", "--out", metavar="FILE", help=f"the manifest file (default: {manifest.FILE_NAME} by the board)"
    )
    parser.add_argument("--kicad-cli", dest="kicad_cli", metavar="PATH", help="the kicad-cli to run")
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT, metavar="SECONDS", help="kicad-cli timeout (300)"
    )


# --- paths ----------------------------------------------------------------------------------------


def _inside(path: Path, root: Path) -> str | None:
    """``path`` relative to ``root`` (POSIX; ``""`` for the root itself), or ``None`` outside it."""
    try:
        relative = path.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return None
    return "" if relative == Path() else relative.as_posix()


def _target(out: str | None, ctx: Context, root: Path) -> tuple[Path, str]:
    """The manifest file, and its path as the result and the plan show it: as ``--out`` wrote it, else
    relative to the working directory."""
    if out is not None:
        given = Path(out)
        return (given if given.is_absolute() else ctx.cwd / given), given.as_posix()
    path = root / manifest.FILE_NAME
    try:
        return path, Path(os.path.relpath(path, ctx.cwd)).as_posix()
    except ValueError:  # another drive on Windows: no relative path exists
        return path, path.as_posix()


def _skipped(relative: str) -> bool:
    """True for a file that no manifest lists: Fenolite's cache, a backup, a manifest, a hidden file."""
    parts = PurePosixPath(relative).parts
    name = parts[-1]
    return (
        CACHE_DIR in parts
        or name.endswith(BACKUP_SUFFIX)
        or name == manifest.FILE_NAME
        or any(part.startswith(".") for part in parts)
    )


def _files_under(folder: Path, root: Path) -> list[str]:
    """Every file under ``folder`` that a manifest may list, relative to ``root`` and sorted."""
    found: list[str] = []
    for path in folder.rglob("*"):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            if not _skipped(relative):
                found.append(relative)
    return sorted(found)


# --- design files ---------------------------------------------------------------------------------


def _sheets(root: Path, stem: str) -> list[str]:
    """The schematic of the project and the sheets it names below the project folder."""
    name = f"{stem}.kicad_sch"
    if not (root / name).is_file():
        return []
    try:
        files = sch.sheet_files(root / name).files
    except (FenoliteError, OSError, ValueError):
        return [name]  # a root sheet Fenolite cannot read is still a file of the project
    return [f for f in files if manifest.relative_posix(f) and (root / f).is_file()]


def _symbol_side(root: Path) -> list[str]:
    """The symbol table and the ``${KIPRJMOD}`` libraries it names."""
    table = root / SYMBOL_TABLE
    if not table.is_file():
        return []
    found = [SYMBOL_TABLE]
    try:
        rows = read_lib_table(table).rows
    except (FenoliteError, OSError, ValueError):
        return found
    for row in rows:
        match = _KIPRJMOD.match(row.uri)
        if row.disabled or row.type == "Table" or match is None:
            continue
        target = root / match.group(1).replace("\\", "/")
        relative = _inside(target, root)
        if not relative:
            continue
        if target.is_file():
            found.append(relative)
        elif target.is_dir():
            found += _files_under(root / relative, root)
    return found


def design_files(board: Path) -> list[str]:
    """The design files of the project of ``board``, relative to its folder and sorted: the copy set of
    ``check`` (a library folder file by file), the schematic with its sheets, and the symbol side."""
    root = board.parent
    names: set[str] = set()
    for name, path in project_set(board).files.items():
        names.update(_files_under(path, root) if path.is_dir() else [name])
    names.update(_sheets(root, board.stem))
    names.update(_symbol_side(root))
    return sorted(name for name in names if name == board.name or not _skipped(name))


def _design_entries(board: Path, *, skip: str | None) -> list[manifest.ArtifactEntry]:
    root = board.parent
    record = read_record(root) or {}
    entries: list[manifest.ArtifactEntry] = []
    for name in design_files(board):
        if name == skip:
            continue
        data = (root / name).read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        tool = FENOLITE if record.get(name) == sha else None
        entries.append(manifest.file_entry(name, manifest.design_kind(name), data, tool=tool))
    return entries


def _ref(root: Path, name: str | None) -> manifest.BoardRef | None:
    if name is None:
        return None
    data = (root / name).read_bytes()
    return manifest.BoardRef(name, hashlib.sha256(data).hexdigest(), board_format(root / name))


# --- artefact folders -----------------------------------------------------------------------------


def _folder(given: str, ctx: Context, root: Path) -> str:
    """An ``--artifacts DIR`` relative to the project folder; outside it is a usage error."""
    path = Path(given)
    path = path if path.is_absolute() else ctx.cwd / path
    if not path.is_dir():
        raise CliError("FEN-3001", f"{Path(given).name} is not a folder", where="--artifacts")
    relative = _inside(path, root)
    if relative is None:
        raise CliError(
            "FEN-2001",
            f"the artefact folder {Path(given).name} is not inside the project folder",
            hint="export into a folder of the project: a manifest names its files by relative paths",
            where="--artifacts",
        )
    return relative


def _join(folder: str, path: str) -> str:
    return (PurePosixPath(folder) / path).as_posix() if folder else path


def _artefacts(
    root: Path, folders: Sequence[str], taken: set[str], issues: list[Issue]
) -> list[manifest.ArtifactEntry]:
    """The entries of the manifests of ``folders``, hashed again. A listed file that is gone is left
    out; one whose bytes changed is listed as it is now, without its tool and source."""
    entries: list[manifest.ArtifactEntry] = []
    for folder in folders:
        where = _join(folder, manifest.FILE_NAME)
        listed, problem = read_folder(root / folder, where=where)
        if problem is not None:
            issues.append(problem)
        if listed is None:
            continue
        for item in listed.artifacts:
            path = _join(folder, item.path)
            if item.kind not in states.DERIVED or path in taken:
                continue  # the design files are listed from the project itself
            taken.add(path)
            file = root / path
            if not file.is_file():
                text = f"{path} is listed by {where} and does not exist; it is left out"
                issues.append(issue("manifest.missing", text, where=path))
                continue
            data = file.read_bytes()
            same = hashlib.sha256(data).hexdigest() == item.sha256
            if not same:
                text = f"{path} is not the file that {where} lists; it is listed as it is now"
                hint = "produce the file again with the command that wrote it, with --manifest"
                issues.append(issue("manifest.changed", text, where=path, hint=hint))
            entries.append(
                manifest.file_entry(
                    path,
                    item.kind,
                    data,
                    layer=item.layer,
                    evidence=item.evidence,
                    from_=item.from_ if same else None,
                    tool=item.tool if same else None,
                )
            )
    return entries


def _unlisted(
    root: Path, folders: Iterable[str], listed: set[str], *, code_severity: None = None
) -> list[Issue]:
    """One ``manifest.unlisted`` per file under ``folders`` that no entry lists. A KiCad file there is
    a design file or KiCad's own local state, never an artefact, and is not reported."""
    names: set[str] = set()
    for folder in folders:
        for name in _files_under(root / folder, root):
            kicad = (
                PurePosixPath(name).suffix.startswith(KICAD_SUFFIX) or manifest.design_kind(name) != "file"
            )
            if name not in listed and not kicad:
                names.add(name)
    return [
        issue("manifest.unlisted", f"{name} lies in an artefact folder and no entry lists it", where=name)
        for name in sorted(names)
    ]


# --- the check ------------------------------------------------------------------------------------


def _sheet_verdicts(root: Path, entries: Sequence[manifest.ArtifactEntry]) -> dict[str, bool]:
    """The RT1 verdict of every sheet, as ``fenolite roundtrip`` takes it; a sheet Fenolite cannot read
    did not survive."""
    verdicts: dict[str, bool] = {}
    for item in entries:
        if item.kind != states.SHEET_KIND:
            continue
        try:
            text = (root / item.path).read_bytes().decode("utf-8")
            verdicts[item.path] = sch.roundtrip_schematic(text, file=item.path).passed
        except (FenoliteError, OSError, ValueError):
            verdicts[item.path] = False
    return verdicts


def _check_ref(checked: Checked) -> manifest.CheckRef:
    stages = [
        manifest.StageRef(s.name, s.status, s.evidence.level.value, s.evidence.oracle)
        for s in checked.report.stages
    ]
    return manifest.CheckRef(stages, checked.tool_version)


def _shown(entries: Iterable[manifest.ArtifactEntry]) -> list[dict[str, Any]]:
    return [{key: getattr(item, key) for key in ENTRY_KEYS} for item in entries]


def _input(board: Path) -> InputRef:
    number = board_format(board)
    return InputRef(
        path=board.name,
        sha256=hashlib.sha256(board.read_bytes()).hexdigest(),
        kind="kicad_pcb",
        format_version=None if number is None else str(number),
    )


# --- verify ---------------------------------------------------------------------------------------


def _artefact_folders(root: Path, entries: Iterable[manifest.ArtifactEntry]) -> set[str]:
    """The folders the derived entries came from: for each, the nearest folder above the file, below the
    project folder, that holds a manifest; the project folder itself for a file directly in it."""
    folders: set[str] = set()
    for item in entries:
        if item.kind not in states.DERIVED:
            continue
        parents = [
            parent.as_posix() for parent in PurePosixPath(item.path).parents if parent.as_posix() != "."
        ]
        if not parents:
            folders.add("")
        for parent in parents:
            if (root / parent / manifest.FILE_NAME).is_file():
                folders.add(parent)
                break
    return folders


def _present_sources(
    board: Path, entries: Iterable[manifest.ArtifactEntry], present: Mapping[str, str]
) -> dict[str, set[str]]:
    """The hashes a ``from`` may hold now, per source: the board file, and the schematic of the project
    with every listed sheet that is still there."""
    sheets = {
        present[item.path] for item in entries if item.kind == states.SHEET_KIND and item.path in present
    }
    schematic = board.with_suffix(".kicad_sch")
    if schematic.is_file():
        sheets.add(hashlib.sha256(schematic.read_bytes()).hexdigest())
    return {"board": {hashlib.sha256(board.read_bytes()).hexdigest()}, "schematic": sheets}


def _verify(board: Path, target: Path, shown: str) -> Result:
    if not target.is_file():
        raise CliError(
            "FEN-3001",
            f"{shown} does not exist",
            hint="write it with 'fenolite manifest PATH --confirm', or name it with --out",
            where=shown,
        )
    try:
        listed = manifest.load(target.read_bytes().decode("utf-8"), file=target.name)
    except (FormatError, UnicodeDecodeError) as exc:
        reason = exc.message if isinstance(exc, FormatError) else "not UTF-8 text"
        raise CliError(
            "FEN-3004", f"{shown} is not a manifest Fenolite reads: {reason}", where=shown
        ) from None
    # a project manifest names its files from the project folder; the manifest of an artefact folder
    # (written by --manifest of a producing command) lists no design file and names them from its own
    whole = any(item.kind in manifest.DESIGN_KINDS for item in listed.artifacts)
    base = board.parent if whole else target.parent
    found: list[Issue] = []
    present: dict[str, str] = {}
    for item in listed.artifacts:
        file = base / item.path
        if not file.is_file():
            found.append(
                issue(
                    "manifest.missing",
                    f"{item.path} is listed and does not exist",
                    where=item.path,
                    severity="error",
                )
            )
            continue
        present[item.path] = hashlib.sha256(file.read_bytes()).hexdigest()
        if present[item.path] != item.sha256:
            text = f"{item.path} is not the file the manifest lists: its SHA-256 differs"
            found.append(issue("manifest.changed", text, where=item.path, severity="error"))
    differing = {item.where for item in found}
    sources = _present_sources(board, listed.artifacts, present)
    for item in listed.artifacts:
        if item.kind not in states.DERIVED or item.path in differing:
            continue
        for name, sha in sorted(item.from_.items()):
            if name in sources and sha not in sources[name]:
                text = f"{item.path} was made from a {name} that has another SHA-256 now"
                found.append(issue("manifest.stale", text, where=item.path))
                break
    names = {item.path for item in listed.artifacts}
    inside = _inside(target, base)
    folders = _artefact_folders(base, listed.artifacts) if whole else {""}
    found += _unlisted(base, folders, names | ({inside} if inside else set()))
    found.sort(key=lambda item: (item.where, item.code))
    result: dict[str, Any] = {
        "manifest": shown,
        "project": None if listed.project is None else dataclasses.asdict(listed.project),
        "states": dict(listed.states),
        "artifacts": _shown(listed.artifacts),
        "verified": not any(item.severity == "error" for item in found),
        "differences": [{"path": item.where, "code": item.code} for item in found],
    }
    return Result(result=result, issues=tuple(found), evidence=Evidence(), input=_input(board))


# --- the command ----------------------------------------------------------------------------------


def _usage(args: argparse.Namespace) -> None:
    if args.verify:
        for flag, given in (
            ("--no-check", args.no_check),
            ("--stages", args.stages),
            ("--artifacts", args.artifacts),
        ):
            if given:
                raise CliError(
                    "FEN-2001",
                    f"--verify does not combine with {flag}: it reads the manifest and runs no check",
                    where=flag,
                )
    if args.no_check and args.stages is not None:
        raise CliError("FEN-2001", "--no-check runs no stage; --stages does not apply", where="--stages")


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    _usage(args)
    stages = None if args.no_check or args.verify else parse_stages(args.stages)
    given = Path(args.path)
    board = resolve_board(given if given.is_absolute() else ctx.cwd / given)
    root = board.parent
    target, shown = _target(args.out, ctx, root)
    if args.verify:
        return _verify(board, target, shown)
    folders = sorted({_folder(folder, ctx, root) for folder in args.artifacts})
    checked: Checked | None = None
    if stages is not None:
        checked = run_stages(board, stages, kicad_cli=args.kicad_cli, timeout=args.timeout, hint=NO_TOOL_HINT)

    own = _inside(target, root)
    entries = _design_entries(board, skip=own)
    taken = {item.path for item in entries}
    found: list[Issue] = []
    entries += _artefacts(root, folders, taken, found)
    found += _unlisted(root, folders, taken | ({own} if own else set()))

    evidence = Evidence()
    stage_map: Mapping[str, tuple[str, str]] = {}
    verdicts: dict[str, bool] = {}
    if checked is not None:
        stage_map = {s.name: (s.status, s.evidence.level.value) for s in checked.report.stages}
        verdicts = _sheet_verdicts(root, entries)
        evidence = (
            Evidence.combine(checked.report.evidence, sch.EVIDENCE) if verdicts else checked.report.evidence
        )
    current = {item.path: item.sha256 for item in entries}
    assigned = sorted(
        states.assign(entries, stages=stage_map, sheets_ok=verdicts, current=current),
        key=lambda item: item.path,
    )
    for item in assigned:
        if item.stale:
            text = f"{item.path} was made from a design file that has another SHA-256 now"
            found.append(
                issue("manifest.stale", text, where=item.path, hint="produce the file again, with --manifest")
            )
    found.sort(key=lambda item: (item.where, item.code))

    schematic = f"{board.stem}.kicad_sch"
    project = manifest.ProjectRef(
        _ref(root, board.name), _ref(root, schematic if schematic in current else None)
    )
    assert project.board is not None
    tool = FENOLITE_TOOL
    if checked is not None and checked.tool_version is not None:
        tool = manifest.ToolRef("kicad-cli", checked.tool_version)
    written = manifest.Manifest(
        schema=manifest.SCHEMA,
        fenolite=FENOLITE_TOOL.version,
        generated=ctx.timestamp.isoformat(),
        board=project.board,
        tool=tool,
        artifacts=assigned,
        project=project,
        check=None if checked is None else _check_ref(checked),
        states=manifest.count_states(assigned),
    )
    data = manifest.to_data(written)
    result: dict[str, Any] = {
        "manifest": shown,
        "project": data["project"],
        "states": data["states"],
        "artifacts": _shown(assigned),
        "check": data["check"],
    }
    return Result(
        result=result,
        issues=(*(() if checked is None else checked.report.issues), *found),
        evidence=evidence,
        input=_input(board),
        writes=(PlannedWrite(shown, manifest.dumps(data).encode("utf-8"), "manifest"),),
    )


_EXAMPLE = (EXAMPLE_BOARD, "--no-check", "--out", manifest.FILE_NAME)
COMMAND = Command(
    name="manifest",
    help=HELP,
    mutates=True,
    register=_register,
    run=_run,
    paged="differences|artifacts",
    example_args=(*_EXAMPLE, "--dry-run"),
    mutation_example_args=_EXAMPLE,
)

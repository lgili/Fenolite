# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The closed copy set of a KiCad project for an oracle run (capability kicad-oracle, "Check project copy
set"; ``docs/formats/kicad/cli.md``).

``kicad-cli`` writes into the folder it runs in, so it only ever sees copies, and only of the files a DRC
run reads: the board, the project and rules files of its stem, the project ``fp-lib-table`` and the
``${KIPRJMOD}`` library folders it names, and the project's drawing sheet (S-0045, S-0046;
``H-K-CHECK-COPYSET``). This module plans the set and writes nothing; the runner copies it.

When the board has a schematic of its stem, the set also holds what an ERC run and the parity test of a
DRC run read (change c0062, ``H-K-ERC-COPYSET``): that schematic, the sheet files its hierarchy reaches,
the project ``sym-lib-table`` with the ``${KIPRJMOD}`` symbol libraries it names, and the schematic's
drawing sheet. One set serves both runs, so that they see the same project.
"""

# evidence: see oracle

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from fenolite.backends.base import ProjectSet, SkippedFile, SkipReason
from fenolite.backends.kicad import _json
from fenolite.backends.kicad.cli import RESERVED_DIRS
from fenolite.backends.kicad.libs import LibRow, read_lib_table
from fenolite.backends.kicad.pro import read_project
from fenolite.core.errors import FenoliteError, FormatError

MAX_COPY_BYTES = 256 * 2**20
WORKSHEET_POINTER = "/pcbnew/page_layout_descr_file"
"""The project key naming the board's drawing sheet (kept local; equal to ``pro.PAGE_LAYOUT_POINTER``)."""
SCHEMATIC_WORKSHEET_POINTER = "/schematic/page_layout_descr_file"
"""The project key naming the schematic's drawing sheet."""
TABLE = "fp-lib-table"
SYMBOL_TABLE = "sym-lib-table"
_KIPRJMOD = re.compile(r"^\$\{KIPRJMOD\}[/\\](.+)$")


class ProjectResolutionError(FenoliteError):
    """A folder that does not name one board: several candidates, or none."""

    cli_code = "FEN-2001"

    def __init__(self, message: str, candidates: tuple[str, ...] = (), hint: str = "") -> None:
        self.candidates = candidates
        named = f"pass one of: {', '.join(candidates)}" if candidates else "pass a .kicad_pcb or .kicad_pro"
        self.hint = hint or named
        super().__init__(message)


class ProjectNotFoundError(FenoliteError):
    """A missing path, or a project file without its board."""

    cli_code = "FEN-3001"


def resolve_board(path: Path) -> Path:
    """The board that ``path`` names: a ``.kicad_pcb``, the board of a ``.kicad_pro``'s stem, or the board
    of a folder's only ``.kicad_pro`` (else its only ``.kicad_pcb``)."""
    path = Path(path)
    if not path.exists():
        raise ProjectNotFoundError(f"{path} does not exist")
    if path.is_dir():
        projects = sorted(path.glob("*.kicad_pro"))
        if len(projects) == 1:
            return _board_of(projects[0])
        candidates = projects or sorted(path.glob("*.kicad_pcb"))
        if len(candidates) == 1:
            return candidates[0]
        names = tuple(p.name for p in candidates)
        what = "project files" if projects else "boards"
        if names:
            raise ProjectResolutionError(f"{path} holds several {what}: {', '.join(names)}", names)
        raise ProjectResolutionError(f"{path} holds no .kicad_pro or .kicad_pcb file")
    if path.suffix == ".kicad_pcb":
        return path
    if path.suffix == ".kicad_pro":
        return _board_of(path)
    raise ProjectResolutionError(f"{path} is not a .kicad_pcb, a .kicad_pro or a folder")


def _board_of(project: Path) -> Path:
    board = project.with_suffix(".kicad_pcb")
    if not board.is_file():
        raise ProjectNotFoundError(f"{project.name} has no board {board.name} next to it")
    return board


def _size(path: Path) -> int:
    if path.is_dir():
        return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
    return path.stat().st_size


class _Planner:
    def __init__(self, root: Path, max_bytes: int) -> None:
        self.root = root
        self.real_root = root.resolve()
        self.max_bytes = max_bytes
        self.files: dict[str, Path] = {}
        self.skipped: list[SkippedFile] = []
        self.total = 0

    def always(self, name: str) -> None:
        path = self.root / name
        self.files[name] = path
        self.total += _size(path)

    def skip(self, name: str, reason: SkipReason) -> None:
        self.skipped.append(SkippedFile(name, reason))

    def inside(self, written: str, rel: str, *, folder: bool | None) -> None:
        """Copy ``rel`` (relative to the root, as ``written`` in the project) when it qualifies: a folder,
        a file, or either one when ``folder`` is ``None`` (a symbol library is a file or a folder)."""
        target = (self.root / rel).resolve()
        if not target.is_relative_to(self.real_root):
            return self.skip(written, "outside-root")
        name = PurePosixPath(target.relative_to(self.real_root).as_posix()).as_posix()
        if name in self.files:
            return None
        if name.split("/")[0] in RESERVED_DIRS:
            return self.skip(name, "reserved-name")
        exists = target.exists() if folder is None else (target.is_dir() if folder else target.is_file())
        if not exists:
            return self.skip(name, "missing")
        size = _size(target)
        if self.total + size > self.max_bytes:
            return self.skip(name, "too-large")
        self.files[name] = self.root / name
        self.total += size
        return None

    def named(self, written: str, *, folder: bool | None, kind: str) -> None:
        """A path as a project names it: ``${KIPRJMOD}/…``, another variable, absolute or relative."""
        match = _KIPRJMOD.match(written)
        if match:
            return self.inside(written, match.group(1).replace("\\", "/"), folder=folder)
        if "${" in written:
            return self.skip(written, "variable")
        if Path(written).is_absolute() or written.startswith(("/", "\\")):
            return None  # read in place by KiCad (a rooted path counts as absolute on Windows too)
        if kind == "library":
            return self.skip(written, "relative")
        return self.inside(written, written.replace("\\", "/"), folder=folder)


def _rows(table: Path) -> Sequence[LibRow]:
    """The rows of a library table, or none when it cannot be read: it is copied all the same."""
    try:
        return read_lib_table(table).rows
    except (FormatError, OSError, UnicodeDecodeError):
        return ()


def _libraries(plan: _Planner, table: Path, *, folder: bool | None) -> None:
    for row in _rows(table):
        if row.disabled:
            continue
        if row.type == "Table":
            plan.skip(row.uri, "nested-table")
            continue
        plan.named(row.uri, folder=folder, kind="library")


def _sheets(plan: _Planner, schematic: Path) -> None:
    """The sheet files that the hierarchy of ``schematic`` reaches, in tree order. A root that Fenolite
    cannot read brings no other file: KiCad judges it alone."""
    from fenolite.backends.kicad.sch import sheet_files

    try:
        tree = sheet_files(schematic)
    except (FormatError, OSError, UnicodeDecodeError, ValueError):
        return
    for name in tree.files[1:]:
        plan.inside(name, name, folder=False)
    for name in tree.missing:
        plan.skip(name, "missing")


def project_set(path: Path, *, max_bytes: int = MAX_COPY_BYTES) -> ProjectSet:
    """The files ``kicad-cli pcb drc`` and ``kicad-cli sch erc`` read for the board ``path`` names,
    planned without writing."""
    board = resolve_board(path)
    root = board.parent
    plan = _Planner(root, max_bytes)
    plan.always(board.name)
    project, rules, table = (f"{board.stem}.kicad_pro", f"{board.stem}.kicad_dru", TABLE)
    schematic = f"{board.stem}.kicad_sch"
    has_project, has_rules = (root / project).is_file(), (root / rules).is_file()
    has_schematic = (root / schematic).is_file()
    has_symbols = has_schematic and (root / SYMBOL_TABLE).is_file()
    for name, present in (
        (project, has_project),
        (rules, has_rules),
        (table, (root / table).is_file()),
        (SYMBOL_TABLE, has_symbols),
        (schematic, has_schematic),
    ):
        if present:
            plan.always(name)
    if has_project:
        try:
            info = read_project(root / project)
        except (FormatError, OSError, UnicodeDecodeError):
            info = None  # copied all the same; KiCad decides, and no sheet is looked up
        pointers = (WORKSHEET_POINTER, *((SCHEMATIC_WORKSHEET_POINTER,) if has_schematic else ()))
        for pointer in pointers:
            sheet = _json.get(info.data, pointer) if info is not None else None
            if isinstance(sheet, str) and sheet:
                plan.named(sheet, folder=False, kind="sheet")
    if has_schematic:
        _sheets(plan, root / schematic)
    if (root / table).is_file():
        _libraries(plan, root / table, folder=True)
    if has_symbols:
        _libraries(plan, root / SYMBOL_TABLE, folder=None)
    return ProjectSet(
        root=root,
        board=board.name,
        files=plan.files,
        skipped=tuple(plan.skipped),
        has_project=has_project,
        has_rules=has_rules,
    )


__all__ = [
    "MAX_COPY_BYTES",
    "SCHEMATIC_WORKSHEET_POINTER",
    "SYMBOL_TABLE",
    "TABLE",
    "WORKSHEET_POINTER",
    "ProjectNotFoundError",
    "ProjectResolutionError",
    "project_set",
    "resolve_board",
]

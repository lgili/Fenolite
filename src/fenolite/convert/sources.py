# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The source of a conversion (capability design-conversion, "Conversion sources"; change c0159).

A KiCad source is a ``.kicad_pro``, a ``.kicad_pcb`` or a folder, resolved as ``fenolite check`` resolves
it (``projectset.resolve_board``). Its design is the board read, completed by
``KicadBackend.design_rules`` with the project's files: a board read alone holds no net class and no
custom rule. An Altium source is a ``.PrjPcb``, a ``.PcbDoc`` or a folder that holds one project file (else
one PCB document), read by the Altium backend. Nothing is written.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pcb import source_info
from fenolite.backends.kicad.projectset import ProjectNotFoundError, project_set, resolve_board
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.evidence import Evidence
from fenolite.model.design import Design

KICAD = "kicad"
ALTIUM = "altium"
KICAD_SUFFIXES = (".kicad_pro", ".kicad_pcb")
ALTIUM_PROJECT = ".prjpcb"
ALTIUM_BOARD = ".pcbdoc"


class SourceError(FenoliteError, ValueError):
    """A source that is no project a direction reads (``FEN-2001``): another kind of file, a folder that
    holds none or several, or a folder that holds projects of two backends."""

    cli_code = "FEN-2001"

    def __init__(self, message: str, *, where: str = "", hint: str = "") -> None:
        self.where = where
        self.hint = hint or "pass a .kicad_pro, a .kicad_pcb, a .PrjPcb, a .PcbDoc or a project folder"
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class SourceProject:
    """A source as read: the path given, the file read (the board of a KiCad project, the project file or
    the PCB document of an Altium one), the folder that holds the project, the backend, the input kind,
    the design, the reader's warnings and infos, the evidence of the read, the format version and major of
    a KiCad board, and the project's files by name (relative to ``root``)."""

    given: Path
    path: Path
    root: Path
    backend: str
    kind: str
    design: Design
    issues: tuple[Issue, ...] = ()
    evidence: Evidence = Evidence()
    format_version: int | None = None
    major: int | None = None
    files: Mapping[str, Path] = field(default_factory=lambda: MappingProxyType({}))

    @property
    def name(self) -> str:
        """The stem of the file read: the name of the project."""
        return self.path.stem

    @property
    def sha256(self) -> str:
        """The SHA-256 of the file read."""
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


def _altium_in(folder: Path) -> Path | None:
    """The only ``.PrjPcb`` of ``folder``, else its only ``.PcbDoc``, else ``None``; ``SourceError`` for
    several."""
    for suffix in (ALTIUM_PROJECT, ALTIUM_BOARD):
        found = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == suffix)
        if len(found) > 1:
            names = ", ".join(p.name for p in found)
            raise SourceError(f"{folder.name} holds several Altium files: {names}", where=folder.name)
        if found:
            return found[0]
    return None


def _kicad(given: Path) -> SourceProject:
    board = resolve_board(given)
    project = project_set(board)
    found: list[Issue] = []
    backend = KicadBackend()
    read = backend.read(board, issues=found)
    rules = backend.design_rules(read.design, project, issues=found)
    info = source_info(rules.design)
    named = given.suffix == ".kicad_pro" or (given.is_dir() and project.has_project)
    kind = "kicad_pro" if named else "kicad_pcb"
    return SourceProject(
        given=given,
        path=board,
        root=board.parent,
        backend=KICAD,
        kind=kind,
        design=rules.design,
        issues=tuple(i for i in found if i.severity != "error"),
        # the rules' evidence is that of the project files they come from; a board alone has none
        evidence=Evidence.combine(read.evidence, rules.evidence)
        if project.has_project or project.has_rules
        else read.evidence,
        format_version=info.version if info is not None else None,
        major=info.major if info is not None else None,
        files=MappingProxyType({name: project.root / name for name in sorted(project.files)}),
    )


def _altium(given: Path, path: Path) -> SourceProject:
    found: list[Issue] = []
    read = AltiumBackend().read(path, issues=found)
    if not isinstance(read.content, Design):
        raise SourceError(f"{path.name} is a library, not a project", where=path.name)
    kind = "altium_prjpcb" if path.suffix.lower() == ALTIUM_PROJECT else "altium_pcbdoc"
    return SourceProject(
        given=given,
        path=path,
        root=path.parent,
        backend=ALTIUM,
        kind=kind,
        design=read.content,
        issues=tuple(i for i in read.issues if i.severity != "error"),
        evidence=read.evidence,
        files=MappingProxyType({path.name: path}),
    )


def read_source(path: Path) -> SourceProject:
    """The source project that ``path`` names. ``ProjectNotFoundError`` (``FEN-3001``) for a path that does
    not exist; ``SourceError`` (``FEN-2001``, a ``ValueError``) for anything that is no KiCad or Altium
    project; a reader's error keeps its type."""
    given = Path(path)
    if not given.exists():
        raise ProjectNotFoundError(f"{given.name} does not exist")
    if given.is_dir():
        kicad = sorted(p.name for p in given.iterdir() if p.is_file() and p.name.endswith(KICAD_SUFFIXES))
        altium = _altium_in(given)
        if kicad and altium is not None:
            raise SourceError(
                f"{given.name} holds projects of two backends",
                where=given.name,
                hint=f"pass one of them: {', '.join([*kicad, altium.name])}",
            )
        if altium is not None:
            return _altium(given, altium)
        if not kicad:
            raise SourceError(f"{given.name} holds no KiCad or Altium project", where=given.name)
        return _kicad(given)
    if given.suffix in KICAD_SUFFIXES:
        return _kicad(given)
    if given.suffix.lower() in (ALTIUM_PROJECT, ALTIUM_BOARD):
        return _altium(given, given)
    raise SourceError(f"{given.name} is no KiCad or Altium project", where=given.name)


__all__ = ["ALTIUM", "KICAD", "SourceError", "SourceProject", "read_source"]

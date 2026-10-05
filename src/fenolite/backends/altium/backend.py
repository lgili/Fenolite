# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium backend as seen through ``fenolite.backends.base``: detection and reading (change c0043,
capability altium-import, "Altium backend").

It reads ``.PrjPcb``, ``.SchDoc`` (binary or ASCII), ``.SchLib``, ``.PcbDoc`` and ``.PcbLib`` into the
neutral model and writes nothing: the Altium writers stay experimental features of ``build``. This module
imports no reader and no adapter until ``read`` is called, so registering the backend stays cheap.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from fenolite.backends.altium.import_evidence import EVIDENCE
from fenolite.backends.base import Backend, CapabilityReport, ReadResult
from fenolite.core.errors import FormatError, Issue

READ_KINDS = (
    "altium_pcbdoc",
    "altium_pcblib",
    "altium_prjpcb",
    "altium_schdoc_ascii",
    "altium_schdoc_binary",
    "altium_schlib",
)
SUFFIXES = frozenset({".prjpcb", ".schdoc", ".schlib", ".pcbdoc", ".pcblib"})
CAPABILITIES = CapabilityReport(
    name="altium",
    read_kinds=READ_KINDS,
    write_kinds=(),
    targets=(),
    default_target=None,
    downgrade="unsupported",
    operations=("detect", "read"),
    evidence=EVIDENCE,
)
"""What the backend offers: ``detect`` and ``read``, at the evidence of the import (``INFERRED``)."""
_PROJECT_SKIPS = ("altium.project.document-outside", "altium.project.document-missing")
_DOCUMENT_INDEX = re.compile(r"\bdocument (\d+)\b")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class AltiumBackend:
    """Altium files read by Fenolite's own readers and adapter."""

    name = "altium"

    def detect(self, path: Path) -> bool:
        """True for the five Altium suffixes, compared without letter case; the file is not opened."""
        return path.suffix.lower() in SUFFIXES

    def capabilities(self) -> CapabilityReport:
        return CAPABILITIES

    def read(self, path: Path, *, issues: list[Issue] | None = None) -> ReadResult:
        """Read a PCB document, a schematic document or a project into a ``Design``, or a library into a
        ``Library``. For a design the result's issues are the readers', then the adapter's, then those of
        ``design.validate()``; the first two are added to ``issues``. A reader error of ``path`` itself is
        raised unchanged; ``ValueError`` for any other suffix."""
        suffix = path.suffix.lower()
        found: list[Issue] = []
        if suffix == ".pcbdoc":
            result = self._board(path, found)
        elif suffix == ".schdoc":
            result = self._sheet(path, found)
        elif suffix == ".prjpcb":
            result = self._project(path, found)
        elif suffix == ".pcblib":
            result = self._footprints(path, found)
        elif suffix == ".schlib":
            result = self._symbols(path, found)
        else:
            raise ValueError(f"{path.name!r} is not an Altium project, document or library")
        if issues is not None:
            issues.extend(found)
        return result

    def _board(self, path: Path, found: list[Issue]) -> ReadResult:
        from fenolite.backends.altium.adapter import import_board
        from fenolite.backends.altium.read.pcb import read_pcbdoc

        data = path.read_bytes()
        document = read_pcbdoc(data, file=path.name)
        found.extend(document.issues)
        design = import_board(document, file=path.name, sha256=_digest(data), issues=found)
        return ReadResult(design, (*found, *design.validate()), EVIDENCE)

    def _sheet(self, path: Path, found: list[Issue]) -> ReadResult:
        from fenolite.backends.altium.adapter.board import header
        from fenolite.backends.altium.adapter.circuit import KIND, build_circuit
        from fenolite.backends.altium.adapter.ids import Ids
        from fenolite.backends.altium.adapter.netlist import SheetInput, resolve
        from fenolite.backends.altium.read.sch import read_schematic
        from fenolite.model.design import Design

        data = path.read_bytes()
        document = read_schematic(data, file=path.name, issues=found)
        digest = _digest(data)
        ids = Ids(KIND, EVIDENCE)
        head = header(ids, path.stem, file=path.name, sha256=digest, locator="FileHeader#0")
        resolved = resolve([SheetInput(path.name, digest, document)], issues=found)
        design = Design(header=head, circuit=build_circuit(resolved, ids, found).circuit, board=None)
        return ReadResult(design, (*found, *design.validate()), EVIDENCE)

    def _project(self, path: Path, found: list[Issue]) -> ReadResult:
        from fenolite.backends.altium.adapter.netlist import NetOptions, SheetInput
        from fenolite.backends.altium.adapter.project import BoardInput, ProjectInput, import_project
        from fenolite.backends.altium.read.pcb import read_pcbdoc
        from fenolite.backends.altium.read.project import load_project
        from fenolite.backends.altium.read.sch import read_schematic

        loaded = load_project(path)
        wanted = {d.document.index for d in loaded.documents if d.document.kind in ("schematic", "pcb")}
        found.extend(i for i in loaded.issues if not self._replaced(i, wanted))
        sheets: list[SheetInput] = []
        board: BoardInput | None = None
        extra = 0
        skipped: list[Issue] = []
        for item in loaded.documents:
            document = item.document
            if document.kind not in ("schematic", "pcb"):
                continue
            name = Path(document.posix).name
            reason = "outside-root" if item.file is None else ("missing" if not item.present else "")
            if document.kind == "pcb" and board is not None and not reason:
                extra += 1
                continue
            if not reason and item.file is not None:
                try:
                    data = item.file.read_bytes()
                    if document.kind == "schematic":
                        sheet = read_schematic(data, file=name, issues=found)
                        sheets.append(SheetInput(name, _digest(data), sheet))
                    else:
                        pcb = read_pcbdoc(data, file=name)
                        found.extend(pcb.issues)
                        board = BoardInput(name, _digest(data), pcb)
                    continue
                except (FormatError, OSError) as error:
                    reason = f"unreadable ({type(error).__name__})"
            skipped.append(self._skipped(document.index, document.kind, reason, path.name))
        found.extend(skipped)
        if not sheets and board is None:
            raise FormatError(
                "the project names no readable sheet and no readable PCB document", file=path.name
            )
        project = ProjectInput(
            name=loaded.name,
            options=NetOptions.from_project(loaded),
            sheets=tuple(sheets),
            board=board,
            file=path.name,
            sha256=_digest(path.read_bytes()),
            extra_boards=extra,
        )
        design = import_project(project, issues=found)
        return ReadResult(design, (*found, *design.validate()), EVIDENCE)

    @staticmethod
    def _replaced(found: Issue, wanted: set[int]) -> bool:
        """Whether a project reader's issue is replaced by ``altium.import.document-skipped``."""
        if found.code not in _PROJECT_SKIPS:
            return False
        match = _DOCUMENT_INDEX.search(found.message)
        return match is not None and int(match.group(1)) in wanted

    @staticmethod
    def _skipped(index: int, kind: str, reason: str, file: str) -> Issue:
        from fenolite.backends.altium.adapter.codes import issue

        return issue(
            "altium.import.document-skipped",
            f"document {index} ({kind}) is skipped: {reason}; the design is built from the rest",
            file,
        )

    def _footprints(self, path: Path, found: list[Issue]) -> ReadResult:
        from fenolite.backends.altium.adapter.library import import_footprints
        from fenolite.backends.altium.read.pcblib import read_pcblib

        data = path.read_bytes()
        library = read_pcblib(data, file=path.name)
        found.extend(library.issues)
        content = import_footprints(
            library, name=path.stem, file=path.name, sha256=_digest(data), issues=found
        )
        return ReadResult(content, tuple(found), EVIDENCE)

    def _symbols(self, path: Path, found: list[Issue]) -> ReadResult:
        from fenolite.backends.altium.adapter.library import import_symbols
        from fenolite.backends.altium.read.schlib import read_schlib

        data = path.read_bytes()
        library = read_schlib(data, file=path.name, issues=found)
        content = import_symbols(library, name=path.stem, file=path.name, sha256=_digest(data), issues=found)
        return ReadResult(content, tuple(found), EVIDENCE)


_BACKEND: Backend = AltiumBackend()
"""The Altium backend satisfies ``Backend`` (checked by pyright)."""

__all__ = ["CAPABILITIES", "READ_KINDS", "SUFFIXES", "AltiumBackend"]

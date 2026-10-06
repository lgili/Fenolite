# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium backend as seen through ``fenolite.backends.base``: detection and reading (change c0043,
capability altium-import, "Altium backend").

It reads ``.PrjPcb``, ``.SchDoc`` (binary or ASCII), ``.SchLib``, ``.PcbDoc`` and ``.PcbLib`` into the
neutral model and writes nothing: the Altium writers stay experimental features of ``build``. This module
imports no reader and no adapter until ``read`` is called, so registering the backend stays cheap.
"""

# evidence: none, the facade of the registered backend: every read returns the evidence of import_evidence

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import Path

from fenolite.backends.altium.import_evidence import EVIDENCE
from fenolite.backends.base import (
    Backend,
    CapabilityReport,
    ContainerLevel,
    ContainerRoundTrip,
    DocumentSet,
    DocumentValidator,
    ModelScope,
    ProjectRead,
    ReadResult,
)
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence

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

    def documents(self, path: Path) -> DocumentSet:
        """The documents that ``path`` names (a document, a project file or a project folder), from the
        project file and the first eight bytes of each document (``docset.document_set``)."""
        from fenolite.backends.altium.docset import document_set

        return document_set(path)

    def read_documents(self, documents: DocumentSet) -> ProjectRead:
        """The two readings of a set, apart: every schematic document as one design without a board
        (``adapter.import_circuit``, with the project's net options), and the document ``board`` as a design
        (``adapter.import_board``). Nothing of one side is merged into the other. A document whose reading
        raises ``FormatError`` is recorded under its name, and its side is ``None``."""
        errors: dict[str, FormatError] = {}
        schematic = self._schematic_side(documents, errors)
        pcb = self._pcb_side(documents, errors)
        return ProjectRead(schematic, pcb, errors)

    def container_roundtrip(self, path: Path, level: ContainerLevel) -> ContainerRoundTrip:
        """RT-A0 or RT-A1 of the file at ``path`` (``roundtrip.rt_a0`` and ``rt_a1``), with the read kind that
        ``docset`` gives it. The reader's ``FormatError`` is raised; a level that cannot be judged is a
        verdict with a reason."""
        from fenolite.backends.altium.docset import kind_of
        from fenolite.backends.altium.roundtrip import rt_a0, rt_a1

        if level not in ("RT-A0", "RT-A1"):
            raise ValueError(f"{level!r} is not a container round-trip level: RT-A0, RT-A1")
        judge = rt_a0 if level == "RT-A0" else rt_a1
        return judge(path.read_bytes(), kind=kind_of(path), file=path.name)

    def written_scope(self) -> ModelScope:
        """The model fields that the Altium writers write, with the length tolerance of a written unit:
        ``roundtrip.RT_A2_SCOPE``."""
        from fenolite.backends.altium.roundtrip import RT_A2_SCOPE

        return RT_A2_SCOPE

    def stage_evidence(self) -> Mapping[str, Evidence]:
        """The evidence this backend adds to a check stage, by stage name (``roundtrip.STAGE_EVIDENCE``)."""
        from fenolite.backends.altium.roundtrip import STAGE_EVIDENCE

        return STAGE_EVIDENCE

    def _schematic_side(self, documents: DocumentSet, errors: dict[str, FormatError]) -> ReadResult | None:
        from fenolite.backends.altium.adapter import import_circuit
        from fenolite.backends.altium.adapter.board import header
        from fenolite.backends.altium.adapter.circuit import KIND
        from fenolite.backends.altium.adapter.ids import Ids
        from fenolite.backends.altium.adapter.netlist import DEFAULT_OPTIONS, NetOptions, SheetInput
        from fenolite.backends.altium.read.project import read_project
        from fenolite.backends.altium.read.sch import read_schematic
        from fenolite.model.design import Design

        names = [document.name for document in documents.of_role("schematic")]
        if not names:
            return None
        root = documents.root
        options = DEFAULT_OPTIONS
        head_name = names[0]
        if documents.project is not None:
            head_name = documents.project
            try:
                listed = read_project((root / documents.project).read_bytes(), file=documents.project)
            except FormatError as error:
                errors[documents.project] = error
                return None
            options = NetOptions.from_project(listed)
            order = {entry.posix.lower(): position for position, entry in enumerate(listed.documents)}
            names.sort(key=lambda name: (order.get(name.lower(), len(order)), name))
        found: list[Issue] = []
        sheets: list[SheetInput] = []
        refused = False
        for name in names:
            data = (root / name).read_bytes()
            try:
                sheet = read_schematic(data, file=Path(name).name, issues=found)
            except FormatError as error:
                errors[name] = error
                refused = True
                continue
            sheets.append(SheetInput(Path(name).name, _digest(data), sheet))
        if refused:
            return None
        circuit = import_circuit(sheets, options=options, issues=found)
        head = header(
            Ids(KIND, EVIDENCE),
            Path(head_name).stem,
            file=Path(head_name).name,
            sha256=_digest((root / head_name).read_bytes()),
            locator="FileHeader#0",
        )
        design = Design(header=head, circuit=circuit, board=None)
        return ReadResult(design, (*found, *design.validate()), EVIDENCE)

    def _pcb_side(self, documents: DocumentSet, errors: dict[str, FormatError]) -> ReadResult | None:
        if documents.board is None:
            return None
        found: list[Issue] = []
        try:
            return self._board(documents.root / documents.board, found)
        except FormatError as error:
            errors[documents.board] = error
            return None

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


def document_validator() -> DocumentValidator:
    """The Altium backend as a ``DocumentValidator``: pyright checks that it has the protocol's methods."""
    return AltiumBackend()


__all__ = ["CAPABILITIES", "READ_KINDS", "SUFFIXES", "AltiumBackend", "document_validator"]

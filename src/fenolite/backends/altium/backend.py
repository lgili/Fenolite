# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium backend as seen through ``fenolite.backends.base``: detection and reading (change c0043,
capability altium-import, "Altium backend"), and what the checks of a document set ask of it (change
c0088): the board frame, the clearance rules of the PCB document and the schematic side of the parity
comparison.

It reads ``.PrjPcb``, ``.SchDoc`` (binary or ASCII), ``.SchLib``, ``.PcbDoc`` and ``.PcbLib`` into the
neutral model and writes nothing: the Altium writers stay experimental features of ``build``. This module
imports no reader and no adapter until ``read`` is called, so registering the backend stays cheap.
"""

# evidence: none, the facade of the registered backend: every read returns the evidence of import_evidence

from __future__ import annotations

import dataclasses
import hashlib
import re
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING

from fenolite.backends.altium.import_evidence import EVIDENCE
from fenolite.backends.base import (
    Backend,
    BoardFrame,
    BoardPad,
    CapabilityReport,
    Change,
    ContainerLevel,
    ContainerRoundTrip,
    DesignRules,
    DesignRulesSource,
    DiffReport,
    DocumentParity,
    DocumentSet,
    DocumentValidator,
    ModelCompare,
    ModelRoundTrip,
    ModelScope,
    ModelWriter,
    PlacedExtent,
    ProjectRead,
    ProjectSet,
    ReadResult,
    SideOutcome,
)
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence
from fenolite.model.circuit import with_normal_pin_maps
from fenolite.model.design import Design

if TYPE_CHECKING:
    from fenolite.backends.altium.lower import ProjectWrite
    from fenolite.model.board import Layer, Via

Compare = ModelCompare

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
BACKEND = "altium"
LAYER_ID_KEY = "layer_id"
PAD_REMOVED_KEY = "pad_removed"
"""The bag key of a via without a pad shape on some layers: their Altium layer ids
(``adapter.copper.PAD_REMOVED_KEY``; change c0132)."""
"""The pair of a layer's ``altium`` bag that holds its Altium id (``adapter.layers``)."""
PLANE_CUTS_KEY = "plane_cuts"
"""The pair of a plane layer's bag that counts the objects the import left out on it (change c0124)."""
PLANE_IDS = range(39, 55)
"""The Altium ids of the internal planes (``docs/formats/altium/pcb-records.md``, "Layers")."""
CLEARANCE_KIND = "Clearance"
"""The ``RULEKIND`` of the rule records the copper check reads."""
FILE_UNIT_NM = Fraction(127, 50)
"""The unit in which a PCB document counts: 1/10 000 mil, 2.54 nm (``docs/formats/units.md``)."""
SLACK_UNITS_PER_ITEM = 1
"""The rule of the slack (change c0131, decided by the maintainer on 2026-10-06): the copper check gives
each of the two items of a pair one file unit."""
PAIR_SLACK_NM = 2 * SLACK_UNITS_PER_ITEM * FILE_UNIT_NM
"""The slack of a pair, 5.08 nm: copper of two nets is no clearance finding while its gap is not below the
rule's value less this."""
UNIT_SLACK_NM = PAIR_SLACK_NM.numerator // PAIR_SLACK_NM.denominator
"""By how much the clearance rules of the copper check are lowered: ``PAIR_SLACK_NM`` in whole nanometres,
5. A rule holds whole nanometres, so the slack is rounded down, never up: a gap between 5 and 5.08 nm below
a rule's value is reported, and no gap is passed that the stated rule reports.

Why a unit per item (``docs/formats/altium/import.md``, "Clearance of the copper check", has the
derivation): the document counts in units and the model in whole nanometres, half to even, so a coordinate
moves by up to 0.5 nm, a point by up to 0.71 nm, and the half of a width or of a size by up to 0.25 nm. A
track or a via is off by up to 0.96 nm, a vertex of a pour by 0.71 nm (1.21 nm at the bridge of a hole), a
round or oval pad by 2.37 nm (its centre goes through the frame of its footprint: three roundings) and a
rectangular pad by 3.18 nm (each corner is rounded once more). One unit, 2.54 nm, covers every item but a
rectangular pad; the slack of a pair covers every pair but a rectangular pad against a pad. An arc is
judged with a band of 1 001 nm, which is far above all of these. Measured on the eight public PCB
documents: every finding that the slack takes away is 1 to 4 nm short."""
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
        return self.board_from_bytes(path.read_bytes(), file=path.name, issues=found)

    def board_from_bytes(self, data: bytes, *, file: str, issues: list[Issue] | None = None) -> ReadResult:
        """The design of the PCB document whose bytes are ``data``, as ``read`` gives it for a file:
        a build judges the bytes it is about to write with it. The readers' and the adapter's issues are
        added to ``issues``; the reader's ``FormatError`` is raised unchanged."""
        from fenolite.backends.altium.adapter import import_board
        from fenolite.backends.altium.read.pcb import read_pcbdoc

        found: list[Issue] = []
        document = read_pcbdoc(data, file=file)
        found.extend(document.issues)
        design = import_board(document, file=file, sha256=_digest(data), issues=found)
        if issues is not None:
            issues.extend(found)
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

    def write(
        self,
        design: Design,
        *,
        target: int | None = None,
        allow_lossy: bool = False,
        rewrite: bool = False,
        bodies: str = "off",
    ) -> ProjectWrite:
        """The files of an Altium project written from ``design`` alone (change c0090,
        ``lower.write_design``): the PCB document of its board, and the schematic, its libraries and the
        project file of its circuit. No script, library or other file is read. ``target`` must be
        ``None``: the Altium writers have one form. ``lower.LossyWriteError`` (``FEN-7001``) when the
        documents would not hold an item of the board's copper, footprints or nets and ``allow_lossy`` is
        false. ``rewrite`` (change c0128) says that ``design`` is the reading of an Altium document and
        that the write gives it back: a via whose drill equals its diameter is then written as it was
        read; ``ValueError`` when the board was not read from an Altium document. ``bodies`` (change
        c0121) is ``off`` or ``extruded``: with ``extruded`` the extruded component bodies of the board's
        footprints are written, and every other body is counted as not written. The write is
        experimental: ``capabilities()`` names no write kind until the writers leave that state."""
        from fenolite.backends.altium.lower import write_design

        if target is not None:
            raise ValueError(f"the Altium writers have one form; target {target!r} is not one")
        return write_design(design, allow_lossy=allow_lossy, rewrite=rewrite, bodies=bodies)

    def in_model_frame(self, model: Design, reading: Design) -> Design:
        """``reading`` in the frame of ``model``, the design it was written from (``lower.in_frame_of``)."""
        from fenolite.backends.altium.lower import in_frame_of

        return in_frame_of(model, reading)

    def body_differences(self, model: Design, reading: Design) -> tuple[tuple[Change, ...], Evidence]:
        """The differences of the kind ``body`` between ``model``, the model a build stored, and
        ``reading``, the model of the PCB document it wrote (``bodydiff.body_differences``; change c0121),
        and the evidence of that comparison. The stored board holds exactly the bodies that were written,
        so a build without them gives none."""
        from fenolite.backends.altium.bodydiff import body_differences
        from fenolite.backends.altium.roundtrip import EVIDENCE_BODIES, body_changes

        return body_changes(body_differences(model, reading)), EVIDENCE_BODIES

    def model_roundtrip(self, path: Path, *, compare: Compare, bodies: str = "off") -> ModelRoundTrip:
        """RT-A3 of the document at ``path`` (a PCB document, a schematic document or a project file):
        read it, write its model with ``lower.write_design(..., allow_lossy=True, rewrite=True)`` into a
        temporary folder of its own, read the written document of the same kind, and let ``rta3.rt_a3``
        judge the two models; ``compare`` is ``checks.diff.diff_designs`` under a scope. Nothing is written
        beside the input, and the folder is removed. The reader's ``FormatError`` on the input is raised.
        ``bodies`` (change c0121) is passed to the write: with ``extruded`` the extruded component bodies
        are written and compared; the stage ``roundtrip.rta3`` runs with ``off``."""
        import tempfile

        from fenolite.backends.altium.lower import write_design
        from fenolite.backends.altium.rta3 import rt_a3

        first = self.read(path).design
        written = write_design(first, allow_lossy=True, rewrite=True, bodies=bodies)
        suffix = path.suffix.lower()
        board: Path | None = path if suffix == ".pcbdoc" else None
        if suffix == ".prjpcb":
            listed = self.documents(path).board
            board = path.parent / listed if listed is not None else None
        census = self._census(board) if board is not None else {}
        wanted = next((name for name in written.files if name.lower().endswith(suffix)), None)
        second: Design | None = None
        if wanted is not None:
            with tempfile.TemporaryDirectory(prefix="fenolite-rta3-") as folder:
                for name, data in written.files.items():
                    (Path(folder) / name).write_bytes(data)
                second = self.read(Path(folder) / wanted).design
        with_bodies = written.inputs.bodies == "extruded"

        def body_compare(reference: Design, reading: Design) -> tuple[Change, ...]:
            return self.body_differences(reference, reading)[0]

        def judged(one: Design, other: Design, scope: ModelScope) -> DiffReport:
            # two equal pin-to-pad maps may list their pins in another order (change c0123)
            return compare(
                dataclasses.replace(one, circuit=with_normal_pin_maps(one.circuit)),
                dataclasses.replace(other, circuit=with_normal_pin_maps(other.circuit)),
                scope,
            )

        return rt_a3(
            first,
            written,
            second,
            compare=judged,
            census=census,
            from_board=suffix == ".pcbdoc",
            bodies=body_compare if with_bodies else None,
        )

    @staticmethod
    def _census(path: Path) -> dict[str, int]:
        """The records of the PCB document at ``path`` that the import maps to no model entity, by the
        category of ``adapter.codes.Census``."""
        from fenolite.backends.altium.adapter.board import KIND, read_board
        from fenolite.backends.altium.adapter.ids import Ids
        from fenolite.backends.altium.read.pcb import read_pcbdoc

        document = read_pcbdoc(path.read_bytes(), file=path.name)
        return read_board(document, file=path.name, sha256="", ids=Ids(KIND, EVIDENCE)).census.categories()

    def stage_evidence(self) -> Mapping[str, Evidence]:
        """The evidence this backend adds to a check stage, by stage name (``roundtrip.STAGE_EVIDENCE``)."""
        from fenolite.backends.altium.roundtrip import STAGE_EVIDENCE

        return STAGE_EVIDENCE

    def board_pads(self, design: Design, *, issues: list[Issue] | None = None) -> tuple[BoardPad, ...]:
        """Every pad of an imported board in the board frame (``frame.board_pads``; ``BoardFrame``)."""
        from fenolite.backends.altium import frame

        return frame.board_pads(design, issues=issues)

    def placed_extents(
        self, design: Design, *, issues: list[Issue] | None = None
    ) -> tuple[PlacedExtent, ...]:
        """The hull of every footprint's pads in the board frame (``frame.placed_extents``)."""
        from fenolite.backends.altium import frame

        return frame.placed_extents(design, issues=issues)

    def design_rules(
        self, design: Design, project: ProjectSet, *, issues: list[Issue] | None = None
    ) -> DesignRules:
        """The clearance rules of the PCB document ``project.board``, applied to ``design``, the import
        of that document (``DesignRulesSource``; ``docs/formats/altium/import.md``, "Clearance of the
        copper check").

        The import already holds the rules that map. What this adds is what the copper check must know
        beyond them: a polygon has no clearance of its own, so the clearance of every zone is 0 (the value
        ``checks.clearance`` reads as "none") and the clearance rules alone decide; every clearance rule is
        lowered by ``UNIT_SLACK_NM``, so that copper at exactly its clearance in the document's unit is no
        finding in nanometres; and ``opaque_clearance_rules`` counts the ``Clearance`` records that the
        rule table does not map and that apply to something (not disabled, and not scoped to a kind of
        layer the board lacks: ``read.rules.NOT_APPLYING``), read from ``Rules6/Data`` alone and mapped
        with the copper layers of ``design``, as the import maps them. A governing rule replaces class
        values, and there is no board minimum. An internal plane is drawn in negative: the objects on its
        layer cut the plane and are no copper, and the import makes no entity of them (change c0124), so
        nothing is taken out here; ``left_out`` names the planes, whose own copper the document does not
        hold, with the number of objects the import left out. A via without a pad shape on some layers is
        given with its hole as its copper there (``_with_removed_pads``). A document that cannot be read
        is named in ``unread``; nothing is raised for it."""
        del issues  # the import reported the rule records already
        try:
            data = (project.root / project.board).read_bytes()
        except OSError as error:
            return self.rules_from_bytes(design, None, file=project.board, unread=type(error).__name__)
        return self.rules_from_bytes(design, data, file=project.board)

    def rules_from_bytes(
        self, design: Design, data: bytes | None, *, file: str, unread: str = ""
    ) -> DesignRules:
        """``design_rules`` for a PCB document given as bytes (``None`` with ``unread``, the reason it
        could not be read): a build judges the bytes it is about to write with it."""
        from fenolite.backends.altium import frame
        from fenolite.backends.altium.adapter.layers import copper_layers_of
        from fenolite.backends.altium.read.pcb import read_rule_fields
        from fenolite.backends.altium.read.rules import NOT_APPLYING, map_rules

        checked = _with_unit_slack(_without_zone_clearance(_with_removed_pads(design)))
        opaque = 0
        cells = (0, 0)
        failed: tuple[tuple[str, str], ...] = ((file, unread),) if data is None else ()
        try:
            layers = copper_layers_of(design.board.layers) if design.board is not None else None
            fields = read_rule_fields(data, file=file) if data else ()
            mapping = map_rules(fields, origin=file, layers=layers)
            opaque = sum(
                1
                for record in mapping.unmapped
                if record.kind == CLEARANCE_KIND and record.reason not in NOT_APPLYING
            )
            cells = (
                sum(judged for _, judged, _ in mapping.matrix_cells),
                sum(other for _, _, other in mapping.matrix_cells),
            )
        except FormatError as error:
            failed = ((file, error.message or type(error).__name__),)
        return DesignRules(
            checked,
            min_clearance=None,
            rules_over_classes=True,
            floor_over_rules=False,
            opaque_clearance_rules=opaque,
            unread=failed,
            evidence=Evidence.combine(EVIDENCE, frame.EVIDENCE),
            left_out=_planes_left_out(design),
            clearance_cells=cells,
        )

    def parity_side(self, schematic: Design, board: Design) -> SideOutcome:
        """The schematic side of the parity comparison (``DocumentParity``) from the two readings of a
        set: ``adapter.parity.side_of(schematic, board)``, at the evidence of the import. ``side`` is
        ``None`` for a schematic reading without a component."""
        from fenolite.backends.altium.adapter.parity import side_of

        if not schematic.circuit.components:
            return SideOutcome(None, message="the schematic documents hold no component")
        return SideOutcome(side_of(schematic, board), EVIDENCE)

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


def _without_zone_clearance(design: Design) -> Design:
    """``design`` with the clearance of every zone at 0: an Altium polygon holds none, and the default
    of the model is no value of the document."""
    board = design.board
    if board is None or all(zone.settings.clearance == 0 for zone in board.zones):
        return design
    zones = tuple(
        dataclasses.replace(zone, settings=dataclasses.replace(zone.settings, clearance=0))
        for zone in board.zones
    )
    return dataclasses.replace(design, board=dataclasses.replace(board, zones=zones))


def _with_removed_pads(design: Design) -> Design:
    """``design`` with every via that has no pad shape on some layers given as the copper it has on each
    layer (change c0132; ``docs/formats/altium/import.md``, "Clearance of the copper check").

    The import keeps the Altium layer ids without a pad shape in the pair ``pad_removed`` of the via's bag;
    the model's ``Via`` holds one diameter, and the copper check draws a via with that diameter on one
    range of layers. Such a via is therefore given as one via per run of consecutive copper layers of its
    span that are alike: its diameter where it has a pad, and its DRILL as diameter where it has none, the
    hole through which it passes that layer (copper of another net inside the hole meets the barrel, and
    a polygon keeps its clearance to the hole). A part spans exactly its run (``layers`` are its first and
    last layer, the type ``buried`` so that the check takes that range) and keeps the via's id, provenance,
    net, position and drill, so a finding names the via that was read. A layer id that is no copper layer
    of the span is ignored; a pair that does not parse leaves the via as it is; a via without the pair is
    the same object. Nothing is taken out of the check."""
    board = design.board
    if board is None or not any(PAD_REMOVED_KEY in _pairs(via) for via in board.vias):
        return design
    copper = [layer for layer in board.layers if layer.kind == "copper"]
    names = [layer.name for layer in copper]
    by_id = {_pairs(layer).get(LAYER_ID_KEY, ""): layer.name for layer in copper}
    vias: list[Via] = []
    for via in board.vias:
        text = _pairs(via).get(PAD_REMOVED_KEY)
        parts = text.split(",") if text else []
        if not parts or not all(part.isdecimal() for part in parts):
            vias.append(via)
            continue
        ends = via.layers
        span = names
        if via.via_type != "through" and len(ends) == 2 and ends[0] in names and ends[1] in names:
            first, last = sorted((names.index(ends[0]), names.index(ends[1])))
            span = names[first : last + 1]
        bare = {by_id[part] for part in parts if part in by_id} & set(span)
        if not bare:
            vias.append(via)
            continue
        start = 0
        for index in range(1, len(span) + 1):
            if index < len(span) and (span[index] in bare) == (span[start] in bare):
                continue
            vias.append(
                dataclasses.replace(
                    via,
                    layers=(span[start], span[index - 1]),
                    via_type="buried",
                    diameter=via.drill if span[start] in bare else via.diameter,
                )
            )
            start = index
    return dataclasses.replace(design, board=dataclasses.replace(board, vias=tuple(vias)))


def _pairs(entity: Via | Layer) -> dict[str, str]:
    """The pairs of the ``altium`` bag of ``entity`` (the last value of a repeated key)."""
    held = entity.ext.get(BACKEND)
    return dict(held.payload) if held is not None else {}


def _planes_left_out(design: Design) -> tuple[tuple[str, int, str], ...]:
    """The ``left_out`` entry of the internal planes of an imported board: their number (the copper layers
    whose ``altium`` bag holds a ``layer_id`` of ``PLANE_IDS``) and, in the reason, the number of objects
    that the import left out on them (the sum of ``plane_cuts``). Empty for a board without a plane."""
    board = design.board
    if board is None:
        return ()
    planes = cuts = 0
    for layer in board.layers:
        if layer.kind != "copper" or BACKEND not in layer.ext:
            continue
        pairs = dict(layer.ext[BACKEND].payload)
        ident = pairs.get(LAYER_ID_KEY, "")
        if not (ident.isdecimal() and int(ident) in PLANE_IDS):
            continue
        planes += 1
        count = pairs.get(PLANE_CUTS_KEY, "")
        cuts += int(count) if count.isdecimal() else 0
    if not planes:
        return ()
    reason = (
        "an internal plane is drawn in negative, so its copper is not in the document; the import left "
        f"the {cuts} object(s) drawn on such a layer out of the board: they cut the plane and are no copper"
    )
    return (("plane", planes, reason),)


def _with_unit_slack(design: Design) -> Design:
    """``design`` with every clearance rule lowered by ``UNIT_SLACK_NM``, the slack of one file unit per
    item of a pair in whole nanometres (a value at or below it is kept). Every pair has two items, so
    lowering each rule by one constant is the rule applied pair by pair."""
    held = design.rules
    if held is None or not any(rule.kind == "clearance" for rule in held.rules):
        return design
    rules = tuple(
        dataclasses.replace(rule, min=rule.min - UNIT_SLACK_NM)
        if rule.kind == "clearance" and rule.min is not None and rule.min > UNIT_SLACK_NM
        else rule
        for rule in held.rules
    )
    return dataclasses.replace(design, rules=dataclasses.replace(held, rules=rules))


_BACKEND: Backend = AltiumBackend()
"""The Altium backend satisfies ``Backend`` (checked by pyright)."""
_FRAME: BoardFrame = AltiumBackend()
"""The Altium backend satisfies ``BoardFrame`` (checked by pyright)."""
_RULES_SOURCE: DesignRulesSource = AltiumBackend()
"""The Altium backend satisfies ``DesignRulesSource`` (checked by pyright)."""
_PARITY: DocumentParity = AltiumBackend()
"""The Altium backend satisfies ``DocumentParity`` (checked by pyright)."""


_WRITER: ModelWriter = AltiumBackend()
"""The Altium backend satisfies ``ModelWriter`` (checked by pyright)."""


def document_validator() -> DocumentValidator:
    """The Altium backend as a ``DocumentValidator``: pyright checks that it has the protocol's methods."""
    return AltiumBackend()


__all__ = ["CAPABILITIES", "READ_KINDS", "SUFFIXES", "AltiumBackend", "document_validator"]

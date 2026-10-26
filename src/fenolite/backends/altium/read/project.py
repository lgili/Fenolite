# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The project file (``.PrjPcb``) read byte for byte (capability altium-project-reader, change c0042).

``read_project`` types what the import (c0043) needs: the documents and their kinds by extension, the
generated documents, the project parameters and seven ``[Design]`` options with the hierarchy mode.
Every other section stays raw in ``ProjectFile.ini``. Facts: ``docs/formats/altium/project.md``, "The
project file as Altium saves it".
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from fenolite.backends.altium.read.annotation import AnnotationFile, read_annotation
from fenolite.backends.altium.read.ini import IniDocument, IniSection, parse_ini
from fenolite.backends.altium.read.outjob import OutJobFile, read_outjob
from fenolite.backends.altium.read.rul import RuleFile, read_rule_file
from fenolite.backends.altium.read.rules import RuleMapping, map_rules
from fenolite.backends.altium.read.stackup import StackupFile, read_stackup
from fenolite.backends.altium.read.textfile import text_issue
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=(
        "H-A-RD-PRJ-DOCS",
        "H-A-RD-PRJ-ENC-2",
        "H-A-RD-PRJ-HIER",
        "H-A-RD-PRJ-INI",
        "H-A-RD-PRJ-OUTJOB",
        "H-A-RD-PRJ-PARAM",
        "H-A-RD-PRJ-RUL-EXPORT",
        "H-A-RD-PRJ-RUL-SUMMARY",
        "H-A-RD-PRJ-RULE-MAP",
        "H-A-RD-PRJ-SCOPE",
        "H-A-RD-PRJ-STACKUP",
    ),
)
"""The project file and the text files it names (output job, rule file, stack-up): every
``H-A-RD-PRJ-*`` row that is not refuted. ``INFERRED``, the lowest level among them (declared by
change c0067)."""

DocumentKind = Literal[
    "schematic",
    "pcb",
    "schematic-library",
    "pcb-library",
    "integrated-library",
    "output-job",
    "rules",
    "stackup",
    "harness",
    "sheet-template",
    "bom",
    "draftsman",
    "annotation",
    "other",
]
DOCUMENT_KINDS: dict[str, DocumentKind] = {
    ".SchDoc": "schematic",
    ".PcbDoc": "pcb",
    ".SchLib": "schematic-library",
    ".PcbLib": "pcb-library",
    ".IntLib": "integrated-library",
    ".OutJob": "output-job",
    ".RUL": "rules",
    ".stackup": "stackup",
    ".Harness": "harness",
    ".SchDot": "sheet-template",
    ".BomDoc": "bom",
    ".PCBDwf": "draftsman",
    ".Annotation": "annotation",
}
"""The kind of a document by its extension, compared without case (``project.md``, "Document kinds");
any other extension is ``other``."""
_KINDS_BY_SUFFIX: dict[str, DocumentKind] = {suffix.lower(): kind for suffix, kind in DOCUMENT_KINDS.items()}

NetScope = Literal["automatic", "flat", "hierarchical", "strict-hierarchical", "global"]
HIERARCHY_MODES: dict[int, NetScope] = {0: "automatic"}
"""The net identifier scope of each ``HierarchyMode`` number that the fact page states
(``H-A-RD-PRJ-HIER``). The other four scopes are added from the author report, never guessed."""

DESIGN = "Design"
FLAG_KEYS = (
    "AllowPortNetNames",
    "AllowSheetEntryNetNames",
    "AppendSheetNumberToLocalNets",
    "PowerPortNamesTakePriority",
)


def document_kind(path: str) -> DocumentKind:
    """The kind of the document at ``path`` (``\\`` or ``/`` between folders) from its extension."""
    suffix = PurePosixPath(path.replace("\\", "/")).suffix.lower()
    return _KINDS_BY_SUFFIX.get(suffix, "other")


@dataclass(frozen=True, slots=True)
class ProjectDocument:
    """One section ``Document<n>`` (or ``GeneratedDocument<n>``): ``index`` is ``n`` and ``path`` the
    ``DocumentPath`` value as written."""

    index: int
    path: str
    kind: DocumentKind
    unique_id: str = ""

    @property
    def posix(self) -> str:
        """``path`` with ``\\`` replaced by ``/``."""
        return self.path.replace("\\", "/")


@dataclass(frozen=True, slots=True)
class ProjectParameter:
    """One section ``Parameter<n>`` with its ``Name`` and ``Value`` (``""`` when a key is absent)."""

    index: int
    name: str
    value: str


@dataclass(frozen=True, slots=True)
class ProjectOptions:
    """The typed options of ``[Design]``; ``raw`` holds every entry of the section in order. A flag is
    ``True`` for ``1``, ``False`` for ``0`` and ``None`` for anything else or an absent key."""

    hierarchy_mode: int | None = None
    net_scope: NetScope | None = None
    output_path: str | None = None
    allow_port_net_names: bool | None = None
    allow_sheet_entry_net_names: bool | None = None
    append_sheet_number_to_local_nets: bool | None = None
    power_port_names_take_priority: bool | None = None
    channel_designator_format: str | None = None
    """``ChannelDesignatorFormatString``: how the components of a repeated sheet are named."""
    channel_room_naming_style: int | None = None
    channel_room_level_separator: str | None = None
    """``ChannelRoomLevelSeperator``, the key as the project file spells it."""
    raw: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ProjectFile:
    """A project file: its INI view (``ini``), ``Version`` of ``[Design]``, the typed options, documents,
    generated documents and parameters, and every issue of reading it."""

    ini: IniDocument
    version: str | None
    options: ProjectOptions
    documents: tuple[ProjectDocument, ...]
    generated: tuple[ProjectDocument, ...]
    parameters: tuple[ProjectParameter, ...]
    issues: tuple[Issue, ...]

    def to_bytes(self) -> bytes:
        return self.ini.to_bytes()


def _number(text: str | None) -> int | None:
    return int(text) if text is not None and text.isascii() and text.isdigit() else None


def _flag(section: IniSection, key: str) -> bool | None:
    return {"1": True, "0": False}.get(section.get(key) or "")


def _documents(ini: IniDocument, stem: str) -> tuple[ProjectDocument, ...]:
    found: list[ProjectDocument] = []
    for index, section in ini.numbered(stem):
        path = section.get("DocumentPath")
        if path is None:
            continue
        found.append(ProjectDocument(index, path, document_kind(path), section.get("DocumentUniqueId") or ""))
    return tuple(found)


def _options(design: IniSection, file: str, issues: list[Issue]) -> ProjectOptions:
    text = design.get("HierarchyMode")
    mode: int | None = None
    scope: NetScope | None = None
    if text is not None:
        mode = int(text) if text.isascii() and text.isdigit() else None
        scope = HIERARCHY_MODES.get(mode) if mode is not None else None
        if scope is None:
            issues.append(
                text_issue(
                    "altium.project.hierarchy-mode-unknown",
                    f"HierarchyMode={text} is not a number of HIERARCHY_MODES: the net identifier scope "
                    "is not known and is not guessed",
                    file,
                )
            )
    allow_port, allow_entry, append_number, power_first = (_flag(design, key) for key in FLAG_KEYS)
    return ProjectOptions(
        hierarchy_mode=mode,
        net_scope=scope,
        output_path=design.get("OutputPath"),
        allow_port_net_names=allow_port,
        allow_sheet_entry_net_names=allow_entry,
        append_sheet_number_to_local_nets=append_number,
        power_port_names_take_priority=power_first,
        channel_designator_format=design.get("ChannelDesignatorFormatString"),
        channel_room_naming_style=_number(design.get("ChannelRoomNamingStyle")),
        channel_room_level_separator=design.get("ChannelRoomLevelSeperator"),
        raw=tuple((entry.key, entry.value) for entry in design.entries),
    )


def read_project(data: bytes, *, file: str = "") -> ProjectFile:
    """Read the project file ``data``; ``to_bytes()`` of the result equals ``data``. ``FormatError`` for
    a compound file or a NUL byte. Warnings: ``altium.project.no-design-section``,
    ``altium.project.hierarchy-mode-unknown``; info ``altium.project.document-kind-unknown`` per
    document of an unknown extension."""
    ini = parse_ini(data, file=file)
    issues = list(ini.issues)
    design = ini.section(DESIGN)
    if design is None:
        issues.append(
            text_issue(
                "altium.project.no-design-section",
                "the project file has no [Design] section: every option is unknown",
                file,
            )
        )
        options = ProjectOptions()
        version = None
    else:
        options = _options(design, file, issues)
        version = design.get("Version")
    documents = _documents(ini, "Document")
    for document in documents:
        if document.kind == "other":
            suffix = PurePosixPath(document.posix).suffix or "(none)"
            issues.append(
                text_issue(
                    "altium.project.document-kind-unknown",
                    f"document {document.index}: the extension {suffix} is not in DOCUMENT_KINDS; "
                    "listed with the kind 'other'",
                    file,
                )
            )
    parameters = tuple(
        ProjectParameter(index, section.get("Name") or "", section.get("Value") or "")
        for index, section in ini.numbered("Parameter")
    )
    return ProjectFile(
        ini=ini,
        version=version,
        options=options,
        documents=documents,
        generated=_documents(ini, "GeneratedDocument"),
        parameters=parameters,
        issues=tuple(issues),
    )


# --- loading a project folder (the entry point of the import, c0043) ---------------------------------


@dataclass(frozen=True, slots=True)
class LoadedDocument:
    """A listed document: ``file`` is its path inside the project folder (``None`` for a path that leaves
    the folder, which is never opened) and ``present`` says whether it is a file."""

    document: ProjectDocument
    file: Path | None
    present: bool


@dataclass(frozen=True, slots=True)
class AltiumProject:
    """A project folder: the folder (``root``), the project's name, the project file, its documents, the
    text companions read (as ``(document index, result)`` pairs), the rule mapping of each rule file,
    and the issues of the project file followed by those of each document in document order.
    ``annotations`` holds the annotation files read (change c0083), in the same pairs."""

    root: Path
    name: str
    project: ProjectFile
    documents: tuple[LoadedDocument, ...]
    outjobs: tuple[tuple[int, OutJobFile], ...]
    rule_files: tuple[tuple[int, RuleFile], ...]
    stackups: tuple[tuple[int, StackupFile], ...]
    rules: tuple[tuple[int, RuleMapping], ...]
    issues: tuple[Issue, ...]
    annotations: tuple[tuple[int, AnnotationFile], ...] = ()

    def annotation_designators(self) -> dict[str, str]:
        """Unique-id path → designator over every annotation file read, the first file's entry first."""
        found: dict[str, str] = {}
        for _, annotation in self.annotations:
            for path, designator in annotation.designators().items():
                found.setdefault(path, designator)
        return found


_DRIVE = re.compile(r"^[A-Za-z]:")


def _inside(posix: str) -> bool:
    """Whether a document path stays inside the project folder: not absolute, no drive letter, no
    ``\\`` share, and no ``..`` that climbs above the folder."""
    if not posix or posix.startswith("/") or _DRIVE.match(posix):
        return False
    depth = 0
    for part in posix.split("/"):
        if part == "..":
            depth -= 1
            if depth < 0:
                return False
        elif part not in ("", "."):
            depth += 1
    return True


def _locate(root: Path, posix: str) -> Path | None:
    """The file of ``posix`` under ``root`` (a path that stays inside, its ``..`` resolved by name): as
    written, else, folder by folder, the one entry that matches without case; ``None`` when there is no
    such file."""
    normal = posixpath.normpath(posix)
    exact = root / normal
    if exact.is_file():
        return exact
    current = root
    for part in (p for p in normal.split("/") if p not in ("", ".")):
        candidate = current / part
        if candidate.exists():
            current = candidate
            continue
        try:
            matches = [entry for entry in current.iterdir() if entry.name.lower() == part.lower()]
        except OSError:
            return None
        if len(matches) != 1:
            return None
        current = matches[0]
    return current if current.is_file() else None


def _read_companion(
    loaded: LoadedDocument, issues: list[Issue], file: str
) -> OutJobFile | RuleFile | StackupFile | AnnotationFile | None:
    document = loaded.document
    if loaded.file is None:
        return None
    try:
        data = loaded.file.read_bytes()
        if document.kind == "output-job":
            result: OutJobFile | RuleFile | StackupFile | AnnotationFile = read_outjob(
                data, file=document.posix
            )
        elif document.kind == "rules":
            result = read_rule_file(data, file=document.posix)
        elif document.kind == "annotation":
            result = read_annotation(data, file=document.posix)
        else:
            result = read_stackup(data, file=document.posix)
    except (FormatError, OSError) as error:
        reason = error.message if isinstance(error, FormatError) else (error.strerror or type(error).__name__)
        issues.append(
            text_issue(
                "altium.project.companion-unreadable",
                f"document {document.index} ({document.kind}) could not be read: {reason}",
                file,
            )
        )
        return None
    issues.extend(result.issues)
    return result


def load_project(path: str | Path) -> AltiumProject:
    """Read the project file at ``path`` and the text companions it lists inside its folder: output jobs,
    rule files (each mapped with ``map_rules``), stack-up files and annotation files (c0083). Schematics,
    boards, libraries and every other kind are listed, not opened; generated documents are not opened.
    ``FileNotFoundError`` for a missing ``path``, ``FormatError`` for a project file that cannot be read.
    Warnings: ``altium.project.document-outside`` (naming the document index, not the path),
    ``altium.project.document-missing`` and ``altium.project.companion-unreadable``. Nothing is
    written."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"no project file at {path.name!r}")
    root = path.parent
    project = read_project(path.read_bytes(), file=path.name)
    issues = list(project.issues)
    resolved_root = root.resolve()
    documents: list[LoadedDocument] = []
    outjobs: list[tuple[int, OutJobFile]] = []
    rule_files: list[tuple[int, RuleFile]] = []
    stackups: list[tuple[int, StackupFile]] = []
    annotations: list[tuple[int, AnnotationFile]] = []
    rules: list[tuple[int, RuleMapping]] = []
    for document in project.documents:
        posix = document.posix
        found = _locate(root, posix) if _inside(posix) else None
        if not _inside(posix) or (found is not None and not found.resolve().is_relative_to(resolved_root)):
            documents.append(LoadedDocument(document, None, False))
            issues.append(
                text_issue(
                    "altium.project.document-outside",
                    f"document {document.index} leaves the project folder; it is not opened",
                    path.name,
                )
            )
            continue
        loaded = LoadedDocument(document, found or root / posix, found is not None)
        documents.append(loaded)
        if found is None:
            issues.append(
                text_issue(
                    "altium.project.document-missing",
                    f"document {document.index} ({document.kind}) is not a file in the project folder",
                    path.name,
                )
            )
            continue
        if document.kind not in ("output-job", "rules", "stackup", "annotation"):
            continue
        result = _read_companion(loaded, issues, path.name)
        if isinstance(result, OutJobFile):
            outjobs.append((document.index, result))
        elif isinstance(result, RuleFile):
            rule_files.append((document.index, result))
            records = [record.fields for record in result.records]
            mapping = map_rules(records, origin=posix, summary=result.kind == "summary")
            rules.append((document.index, mapping))
        elif isinstance(result, StackupFile):
            stackups.append((document.index, result))
        elif isinstance(result, AnnotationFile):
            annotations.append((document.index, result))
    return AltiumProject(
        root=root,
        name=path.stem,
        project=project,
        documents=tuple(documents),
        outjobs=tuple(outjobs),
        rule_files=tuple(rule_files),
        stackups=tuple(stackups),
        rules=tuple(rules),
        issues=tuple(issues),
        annotations=tuple(annotations),
    )


__all__ = [
    "DOCUMENT_KINDS",
    "AltiumProject",
    "LoadedDocument",
    "load_project",
    "FLAG_KEYS",
    "HIERARCHY_MODES",
    "DocumentKind",
    "NetScope",
    "ProjectDocument",
    "ProjectFile",
    "ProjectOptions",
    "ProjectParameter",
    "document_kind",
    "read_project",
]

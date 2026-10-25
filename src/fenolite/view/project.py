# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The tree of a project's documents for the viewer's side panel (capability board-viewer, "Project tree").

An Altium project file lists its documents; a KiCad project is the folder of its project file; a folder
gives the tree of its one project file, or of its boards; a board is a tree of one document. Documents are
grouped as the native tools group them: "Source Documents", "Libraries", "Settings", "Documentation" and
"Other". Boards, Altium sheets (change c0177), KiCad sheets (change c0178) and symbol and footprint
libraries (change c0179) can be viewed; every other document is listed with its kind and size.
Nothing is written, and a path that leaves the project folder is listed and never opened.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fenolite.backends.altium.read.project import document_kind, load_project

GROUPS = ("Source Documents", "Libraries", "Settings", "Documentation", "Other")
GROUP_OF: dict[str, str] = {
    "schematic": "Source Documents",
    "pcb": "Source Documents",
    "harness": "Source Documents",
    "schematic-library": "Libraries",
    "pcb-library": "Libraries",
    "integrated-library": "Libraries",
    "output-job": "Settings",
    "rules": "Settings",
    "stackup": "Settings",
    "sheet-template": "Settings",
    "library-table": "Settings",
    "project": "Settings",
    "draftsman": "Documentation",
    "annotation": "Documentation",
    "bom": "Documentation",
}
VIEWABLE = frozenset({"pcb", "schematic", "pcb-library", "schematic-library", "draftsman"})
VIEWABLE_LIBRARIES = (".pcblib", ".schlib", ".kicad_sym", ".kicad_mod", ".pretty")
"""The library files that have a scene (change c0179); integrated libraries are listed, not viewed."""
VIEWABLE_SCHEMATICS = (".schdoc", ".kicad_sch")
"""The schematic files that have a scene: Altium sheets (c0177) and KiCad sheets (c0178)."""
BOARD_SUFFIXES = (".pcbdoc", ".kicad_pcb")
PROJECT_SUFFIXES = (".prjpcb", ".kicad_pro")
KICAD_KINDS: dict[str, str] = {
    ".kicad_pcb": "pcb",
    ".kicad_sch": "schematic",
    ".kicad_sym": "schematic-library",
    ".kicad_dru": "rules",
    ".kicad_wks": "sheet-template",
}


@dataclass(frozen=True, slots=True)
class Document:
    """One document of the tree: ``id`` is stable for a project (its order in the tree), ``path`` is
    relative to the project folder with ``/`` between folders, ``file`` is ``None`` for a path that leaves
    the folder."""

    id: str
    name: str
    path: str
    kind: str
    group: str
    present: bool
    viewable: bool
    size: int | None
    file: Path | None

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "kind": self.kind,
            "group": self.group,
            "present": self.present,
            "viewable": self.viewable,
            "size": self.size,
        }


@dataclass(frozen=True, slots=True)
class ProjectTree:
    """A project: its name, its source (``altium``, ``kicad``, ``folder`` or ``board``), its folder, its
    project file relative to the folder (``""`` when there is none) and its documents in tree order."""

    name: str
    source: str
    root: Path
    project_file: str
    documents: tuple[Document, ...]
    issues: tuple[str, ...] = ()

    def document(self, key: str) -> Document | None:
        """The document whose id, path or name is ``key``."""
        for doc in self.documents:
            if key in (doc.id, doc.path, doc.name):
                return doc
        return None

    def first_viewable(self) -> Document | None:
        """The board named as the project, else the first board, else the first viewable document."""
        shown = [doc for doc in self.documents if doc.viewable and doc.present]
        shown = [doc for doc in shown if doc.kind == "pcb"] + [doc for doc in shown if doc.kind != "pcb"]
        same = [doc for doc in shown if doc.name.rsplit(".", 1)[0].lower() == self.name.lower()]
        return (same or shown or [None])[0]

    def to_json(self) -> dict[str, Any]:
        groups: list[dict[str, Any]] = []
        for group in GROUPS:
            docs = [doc.to_json() for doc in self.documents if doc.group == group]
            if docs:
                groups.append({"name": group, "documents": docs})
        return {
            "name": self.name,
            "source": self.source,
            "project_file": self.project_file,
            "groups": groups,
            "issues": list(self.issues),
        }


def _size(path: Path | None) -> int | None:
    try:
        return path.stat().st_size if path is not None and path.is_file() else None
    except OSError:
        return None


def _viewable(kind: str, rel: str) -> bool:
    if kind == "schematic":
        return rel.lower().endswith(VIEWABLE_SCHEMATICS)
    if kind in ("pcb-library", "schematic-library"):
        return rel.lower().endswith(VIEWABLE_LIBRARIES)
    return kind in VIEWABLE


def _documents(entries: list[tuple[str, str, Path | None]]) -> tuple[Document, ...]:
    """(relative path, kind, file) entries as documents, sorted by group then path, with stable ids."""
    rows = sorted(entries, key=lambda e: (GROUPS.index(GROUP_OF.get(e[1], "Other")), e[0].lower()))
    docs: list[Document] = []
    for k, (rel, kind, file) in enumerate(rows, start=1):
        present = file is not None and file.exists()
        docs.append(
            Document(
                id=f"doc{k}",
                name=rel.rsplit("/", 1)[-1],
                path=rel,
                kind=kind,
                group=GROUP_OF.get(kind, "Other"),
                present=present,
                viewable=_viewable(kind, rel),
                size=_size(file),
                file=file,
            )
        )
    return tuple(docs)


def _altium(path: Path) -> ProjectTree:
    project = load_project(path)
    entries: list[tuple[str, str, Path | None]] = []
    for loaded in project.documents:
        entries.append((loaded.document.posix, loaded.document.kind, loaded.file if loaded.present else None))
    issues = tuple(f"{issue.code}: {issue.message}" for issue in project.issues if issue.severity != "info")
    return ProjectTree(path.stem, "altium", path.parent, path.name, _documents(entries), issues)


def _kicad(path: Path) -> ProjectTree:
    root = path.parent
    entries: list[tuple[str, str, Path | None]] = [(path.name, "project", path)]
    for file in sorted(root.rglob("*")):
        rel = file.relative_to(root)
        if len(rel.parts) > 3 or any(part.startswith(".") for part in rel.parts):
            continue
        suffix = file.suffix.lower()
        if file.is_dir() and suffix == ".pretty":
            entries.append((rel.as_posix(), "pcb-library", file))
        elif file.is_file() and suffix in KICAD_KINDS:
            entries.append((rel.as_posix(), KICAD_KINDS[suffix], file))
        elif file.is_file() and file.name in ("fp-lib-table", "sym-lib-table"):
            entries.append((rel.as_posix(), "library-table", file))
    return ProjectTree(path.stem, "kicad", root, path.name, _documents(entries))


def _boards(root: Path) -> list[tuple[str, str, Path | None]]:
    found: list[tuple[str, str, Path | None]] = []
    for file in sorted(root.iterdir()):
        if file.is_file() and file.suffix.lower() in BOARD_SUFFIXES:
            found.append((file.name, "pcb", file))
    return found


def load_tree(path: Path) -> ProjectTree:
    """The tree of ``path``: an Altium or KiCad project file, a folder, or a board.

    ``FileNotFoundError`` for a missing path; ``ValueError`` for a file that is neither a project file nor
    a board."""
    if not path.exists():
        raise FileNotFoundError(f"no file or folder at {path.name!r}")
    if path.is_dir() and path.suffix.lower() == ".pretty":
        return ProjectTree(
            path.stem, "library", path.parent, "", _documents([(path.name, "pcb-library", path)])
        )
    if path.is_dir():
        projects = [f for f in sorted(path.iterdir()) if f.is_file() and f.suffix.lower() in PROJECT_SUFFIXES]
        if len(projects) == 1:
            return load_tree(projects[0])
        return ProjectTree(path.name, "folder", path, "", _documents(_boards(path)))
    suffix = path.suffix.lower()
    if suffix == ".prjpcb":
        return _altium(path)
    if suffix == ".kicad_pro":
        return _kicad(path)
    if suffix in BOARD_SUFFIXES:
        kind = "pcb"
        return ProjectTree(path.stem, "board", path.parent, "", _documents([(path.name, kind, path)]))
    if suffix in VIEWABLE_LIBRARIES:
        kind = "schematic-library" if suffix in (".schlib", ".kicad_sym") else "pcb-library"
        return ProjectTree(path.stem, "library", path.parent, "", _documents([(path.name, kind, path)]))
    if suffix in VIEWABLE_SCHEMATICS:
        return ProjectTree(path.stem, "sheet", path.parent, "", _documents([(path.name, "schematic", path)]))
    if suffix == ".pcbdwf":
        documents = _documents([(path.name, "draftsman", path)])
        return ProjectTree(path.stem, "drawing", path.parent, "", documents)
    if document_kind(path.name) != "other":
        raise ValueError(
            f"{path.name} is a {document_kind(path.name)} document; open its project, a board or a sheet"
        )
    raise ValueError(f"{path.name} is neither a project file, a board, a sheet, a library nor a drawing")


__all__ = ["GROUPS", "Document", "ProjectTree", "load_tree"]

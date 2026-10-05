# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The documents that an Altium input names (capability altium-verification, "Altium document sets";
change c0044).

``document_set`` takes a document, a project file or a project folder and returns the neutral
``DocumentSet`` of ``fenolite.backends.base``. It reads the project file and the first eight bytes of each
document (to tell a compound file from a text file) and nothing else, and it never writes.
"""

# evidence: see import_evidence

from __future__ import annotations

import posixpath
import re
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from fenolite.backends.base import Document, DocumentRole, DocumentSet

COMPOUND_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
"""The first eight bytes of a compound file ([MS-CFB]); ``read.cfb.SIGNATURE`` holds the same value."""
PROJECT_SUFFIX = ".prjpcb"
SUFFIX_KINDS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        ".prjpcb": ("altium_prjpcb",),
        ".schdoc": ("altium_schdoc_binary", "altium_schdoc_ascii"),
        ".pcbdoc": ("altium_pcbdoc",),
        ".schlib": ("altium_schlib",),
        ".pcblib": ("altium_pcblib",),
    }
)
"""The read kinds of each suffix (lower case). A schematic document has two: the first when the file starts
with the compound file signature, the second otherwise."""
ROLES: Mapping[str, DocumentRole] = MappingProxyType(
    {
        "altium_prjpcb": "project",
        "altium_schdoc_ascii": "schematic",
        "altium_schdoc_binary": "schematic",
        "altium_pcbdoc": "pcb",
        "altium_schlib": "symbol-library",
        "altium_pcblib": "footprint-library",
    }
)
"""The role of each read kind of the Altium backend."""
_DRIVE = re.compile(r"^[A-Za-z]:")


def kind_of(path: Path) -> str:
    """The read kind of the file at ``path`` from its suffix and, for a schematic document, from its first
    eight bytes. ``ValueError`` for another suffix."""
    kinds = SUFFIX_KINDS.get(path.suffix.lower())
    if kinds is None:
        raise ValueError(f"{path.name!r} is not an Altium project, document or library")
    if len(kinds) == 1:
        return kinds[0]
    with path.open("rb") as handle:
        head = handle.read(len(COMPOUND_SIGNATURE))
    return kinds[0] if head == COMPOUND_SIGNATURE else kinds[1]


def _document(root: Path, name: str) -> Document:
    kind = kind_of(root / name)
    return Document(name, kind, ROLES[kind])


def _listed_name(path: str) -> str | None:
    """A listed document path as a POSIX name relative to the project folder; ``None`` when it leaves the
    folder (absolute, a drive letter, a share, or ``..`` above the folder)."""
    posix = path.replace("\\", "/")
    if not posix or posix.startswith("/") or _DRIVE.match(posix):
        return None
    normal = posixpath.normpath(posix)
    if normal in (".", "..") or normal.startswith("../"):
        return None
    return normal


def _on_disk(root: Path, name: str) -> str | None:
    """The name of the file ``name`` under ``root`` as the folder spells it: folder by folder, the entry of
    that name, else the one entry that matches without letter case; ``None`` when there is no such file. The
    folder is listed, so the answer does not depend on whether the file system folds case."""
    current = root
    spelled: list[str] = []
    for part in name.split("/"):
        try:
            entries = sorted(entry.name for entry in current.iterdir())
        except OSError:
            return None
        matches = [part] if part in entries else [e for e in entries if e.lower() == part.lower()]
        if len(matches) != 1:
            return None
        spelled.append(matches[0])
        current = current / matches[0]
    return "/".join(spelled) if current.is_file() else None


def _project_file(folder: Path) -> Path:
    found = sorted(e for e in folder.iterdir() if e.is_file() and e.suffix.lower() == PROJECT_SUFFIX)
    if len(found) != 1:
        names = ", ".join(entry.name for entry in found) or "none"
        raise ValueError(f"{folder.name!r} holds {len(found)} project files, expected one: {names}")
    return found[0]


def _board(project: str | None, documents: list[Document]) -> str | None:
    boards = sorted(document.name for document in documents if document.role == "pcb")
    if project is not None:
        stem = Path(project).stem.lower()
        for name in boards:
            if Path(name).stem.lower() == stem:
                return name
    return boards[0] if boards else None


def _project_set(path: Path) -> DocumentSet:
    from fenolite.backends.altium.read.project import read_project

    root = path.parent
    resolved_root = root.resolve()
    listed = read_project(path.read_bytes(), file=path.name)
    names = {path.name}
    missing: set[str] = set()
    for entry in listed.documents:
        name = _listed_name(entry.path)
        if name is None or Path(name).suffix.lower() not in SUFFIX_KINDS:
            continue
        found = _on_disk(root, name)
        if found is None:
            missing.add(name)
        elif (root / found).resolve().is_relative_to(resolved_root):
            names.add(found)
    documents = [_document(root, name) for name in sorted(names)]
    return DocumentSet(
        root, path.name, _board(path.name, documents), tuple(documents), tuple(sorted(missing))
    )


def document_set(path: Path) -> DocumentSet:
    """The documents of the Altium input at ``path``.

    - A document or a library: a set whose root is the file's folder and whose only document is the file.
    - A project file: the project file and every document it lists that has one of the five suffixes and
      lies under the project's folder; a listed document that does not exist goes to ``missing``.
    - A folder: the set of its only project file; ``ValueError`` naming the candidates otherwise.

    ``board`` is the PCB document whose stem equals the project file's without letter case, else the first
    PCB document by name. ``FileNotFoundError`` for a missing path, ``ValueError`` for another suffix, and the
    project reader's ``FormatError`` for a project file it cannot read.
    """
    if path.is_dir():
        return _project_set(_project_file(path))
    if not path.is_file():
        raise FileNotFoundError(f"no file at {path.name!r}")
    if path.suffix.lower() == PROJECT_SUFFIX:
        return _project_set(path)
    document = _document(path.parent, path.name)
    board = document.name if document.role == "pcb" else None
    return DocumentSet(path.parent, None, board, (document,))


__all__ = ["COMPOUND_SIGNATURE", "ROLES", "SUFFIX_KINDS", "document_set", "kind_of"]

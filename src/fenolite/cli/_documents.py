# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Document input of the commands (change c0044): the input of a backend whose project is a set of
documents (``backends.base.DocumentValidator``), found through the registry only.

``check``, ``inspect`` and ``diff`` share these helpers: finding the backend and the document set of a
path, telling a built folder from a native one, and the result of a document check.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fenolite.backends import registry
from fenolite.backends.base import DocumentSet, DocumentValidator
from fenolite.cli.errors import CliError
from fenolite.cli.output import InputRef
from fenolite.core.errors import FenoliteError
from fenolite.model.canonical import load_dir
from fenolite.model.design import Design

BUILT_MARKERS = ("meta.json", "build.json")
"""A folder is built when its ``.fenolite/`` holds one of these files."""
KICAD_SUFFIXES = (".kicad_pro", ".kicad_pcb")


def relative_text(text: str, root: Path) -> str:
    """``text`` with every spelling of ``root`` taken out, so that no message holds an absolute path."""
    for spelling in sorted({str(root.resolve()), str(root)}, key=len, reverse=True):
        text = text.replace(spelling + "/", "").replace(spelling, ".")
    return text


def built_cache(root: Path) -> tuple[bool, Design | None, str]:
    """``(built, model, cache_error)`` from ``<root>/.fenolite/``."""
    cache = root / ".fenolite"
    if not any((cache / marker).is_file() for marker in BUILT_MARKERS):
        return False, None, ""
    try:
        return True, load_dir(cache), ""
    except (OSError, ValueError, KeyError, TypeError, FenoliteError) as exc:
        return True, None, relative_text(f"{type(exc).__name__}: {exc}", root)


def validator_for(path: Path) -> DocumentValidator | None:
    """The backend of the file ``path`` when it reads its input as a set of documents, else ``None``."""
    backend = registry.for_path(path)
    return backend if isinstance(backend, DocumentValidator) else None


def _folder_validators(folder: Path) -> list[DocumentValidator]:
    found: dict[str, DocumentValidator] = {}
    for entry in sorted(folder.iterdir()):
        if entry.is_file():
            backend = validator_for(entry)
            if backend is not None:
                found.setdefault(backend.name, backend)
    return list(found.values())


def find_documents(path: Path) -> tuple[DocumentValidator, DocumentSet] | None:
    """The backend and the document set of ``path`` when it is document input, else ``None``.

    - A file whose backend satisfies ``DocumentValidator``: its set (``FEN-3001`` when it does not exist).
    - A folder that holds files of such a backend: the set of its only project file. With a KiCad project
      or board beside that project file the folder is ambiguous (``FEN-2001``, naming both); without
      exactly one project file and without a KiCad file it is refused (``FEN-2001``, naming the
      candidates). A folder with KiCad files and no single project file is KiCad input.
    """
    if not path.is_dir():
        backend = validator_for(path)
        if backend is None:
            return None
        if not path.is_file():
            raise CliError("FEN-3001", f"{path.name} does not exist", where=path.name)
        return backend, backend.documents(path)
    validators = _folder_validators(path)
    if not validators:
        return None
    kicad = sorted(e.name for e in path.iterdir() if e.is_file() and e.name.endswith(KICAD_SUFFIXES))
    found: list[tuple[DocumentValidator, DocumentSet]] = []
    refusals: list[str] = []
    for backend in validators:
        try:
            found.append((backend, backend.documents(path)))
        except ValueError as error:
            refusals.append(relative_text(str(error), path))
    if kicad and found:
        names = [*kicad, *(str(documents.project) for _, documents in found)]
        raise CliError(
            "FEN-2001",
            f"{path.name} holds projects of two backends",
            hint=f"pass one of them: {', '.join(names)}",
            where=path.name,
        )
    if kicad:
        return None
    if len(found) != 1:
        hint = "; ".join(refusals) if refusals else ", ".join(str(d.project) for _, d in found)
        raise CliError(
            "FEN-2001", f"{path.name} does not hold exactly one project file", hint=hint, where=path.name
        )
    return found[0]


def given_document(path: Path, documents: DocumentSet) -> str:
    """The name, relative to the set's root, of the file that ``path`` names: the file itself, or the
    project file for a folder."""
    if path.is_dir():
        assert documents.project is not None
        return documents.project
    return path.name


def input_ref(path: Path, documents: DocumentSet) -> InputRef:
    """The envelope's ``input`` for document input: the file ``path`` names, its SHA-256 and read kind."""
    name = given_document(path, documents)
    digest = hashlib.sha256((documents.root / name).read_bytes()).hexdigest()
    return InputRef(path=name, sha256=digest, kind=documents.named(name).kind, format_version=None)


def project_result(backend: DocumentValidator, documents: DocumentSet, *, built: bool) -> dict[str, Any]:
    """``result.project`` of a document check: names relative to the set's root, sorted."""
    return {
        "backend": backend.name,
        "project": documents.project,
        "board": documents.board,
        "built": built,
        "files": [document.name for document in documents.documents],
        "documents": [
            {"name": document.name, "kind": document.kind, "role": document.role}
            for document in documents.documents
        ],
        "skipped": [{"name": name, "reason": "missing"} for name in documents.missing],
    }


__all__ = [
    "BUILT_MARKERS",
    "built_cache",
    "find_documents",
    "given_document",
    "input_ref",
    "project_result",
    "relative_text",
    "validator_for",
]

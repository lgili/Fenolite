# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The paths that the documents of a project hold (capability file-safety, "Project references").

A copied or moved project often still points at its old folder: a library table with an absolute path, a 3D
model, a drawing sheet. ``project_refs`` lists every such path with its document, and whether it resolves
inside the project; ``repoint`` rewrites the paths that start with a prefix, in the documents Fenolite can
write. What each document holds is recorded in ``docs/formats/kicad/project.md`` and
``docs/formats/altium/project.md``:

- KiCad library tables (``fp-lib-table``, ``sym-lib-table``): the ``uri`` of each ``lib``;
- KiCad schematics: the ``Sheetfile`` property of each ``sheet``;
- KiCad boards and footprints: the first atom of each ``model``;
- the KiCad project file: ``page_layout_descr_file`` of ``pcbnew`` and of ``schematic``;
- the Altium project file: each ``DocumentPath=`` line. Fenolite does not rewrite it.

``${KIPRJMOD}`` is the project folder; another ``${VAR}`` is not resolved. A relative path resolves from
the folder of its document. A rewrite replaces the written atom of each matching path, and nothing else.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, parse

PROJECT_VAR = "${KIPRJMOD}"
_VAR = re.compile(r"\$\{[^}]*\}|\$\([^)]*\)")
_ALTIUM_LINE = re.compile(r"^(DocumentPath=)(.*?)\r?$", re.IGNORECASE | re.MULTILINE)
_PAGE_LAYOUT = (("pcbnew", "page_layout_descr_file"), ("schematic", "page_layout_descr_file"))


@dataclass(frozen=True, slots=True)
class Ref:
    """A path a document holds. ``document`` is relative to the project folder; ``kind`` is ``library``,
    ``sheet``, ``model``, ``worksheet`` or ``document``; ``value`` is the path as written. ``resolved``
    is the absolute path it names (``None`` when a variable other than ``${KIPRJMOD}`` stays), ``exists``
    whether that file or folder exists, ``outside`` whether it lies outside the project folder, and
    ``writable`` whether Fenolite can rewrite the document."""

    document: str
    kind: str
    value: str
    resolved: str | None
    exists: bool | None
    outside: bool
    writable: bool


@dataclass(slots=True)
class _Found:
    kind: str
    value: str
    written: str
    """The text of the value in the file: the atom, or the JSON string."""


def _resolve(value: str, base: Path, root: Path) -> Path | None:
    text = value.replace(PROJECT_VAR, root.as_posix())
    if _VAR.search(text):
        return None
    if re.match(r"^[A-Za-z]:[\\/]", text) or text.startswith("\\\\"):
        windows = PureWindowsPath(text)
        return Path(windows) if Path(windows).is_absolute() else None
    path = Path(text.replace("\\", "/"))
    return path if path.is_absolute() else (base / path)


def _walk(node: Node) -> Iterator[Node]:
    yield node
    for child in node.children:
        if type(child) is Node:
            yield from _walk(child)


def _string(atom: Atom | None) -> str | None:
    return atom.value if atom is not None and atom.kind == AtomKind.STRING else None


def _sexpr_refs(text: str, name: str) -> list[_Found]:
    root = parse(text, file=name)
    found: list[_Found] = []
    for node in _walk(root):
        atoms = node.atoms()
        if node.name == "lib":
            uri = node.find("uri")
            value = _string(uri.atoms()[0]) if uri is not None and uri.atoms() else None
            if value is not None and uri is not None:
                found.append(_Found("library", value, uri.atoms()[0].text))
        elif node.name == "property" and len(atoms) >= 2 and atoms[0].value in ("Sheetfile", "Sheet file"):
            if (value := _string(atoms[1])) is not None:
                found.append(_Found("sheet", value, atoms[1].text))
        elif node.name == "model" and atoms and (value := _string(atoms[0])) is not None:
            found.append(_Found("model", value, atoms[0].text))
    return found


def _project_refs(text: str) -> list[_Found]:
    data = json.loads(text)
    found: list[_Found] = []
    for section, key in _PAGE_LAYOUT:
        value = data.get(section, {}).get(key) if isinstance(data.get(section), dict) else None
        if isinstance(value, str) and value:
            found.append(_Found("worksheet", value, json.dumps(value)))
    return found


def _altium_refs(text: str) -> list[_Found]:
    return [_Found("document", match.group(2), match.group(2)) for match in _ALTIUM_LINE.finditer(text)]


def _reader(rel: Path) -> tuple[str, bool] | None:
    """How a document is read (``sexpr``, ``project`` or ``altium``) and whether Fenolite rewrites it."""
    suffix = rel.suffix.lower()
    if rel.name in ("fp-lib-table", "sym-lib-table") or suffix in (".kicad_sch", ".kicad_pcb", ".kicad_mod"):
        return ("sexpr", True)
    if suffix == ".kicad_pro":
        return ("project", True)
    if suffix == ".prjpcb":
        return ("altium", False)
    return None


def _found(rel: Path, text: str) -> list[_Found]:
    how = _reader(rel)
    if how is None:
        return []
    if how[0] == "sexpr":
        return _sexpr_refs(text, rel.name)
    if how[0] == "project":
        return _project_refs(text)
    return _altium_refs(text)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def project_refs(root: Path, files: Sequence[Path]) -> tuple[Ref, ...]:
    """The paths held by the documents ``files`` (relative to the project folder ``root``), in file order
    and in the order of each document."""
    refs: list[Ref] = []
    for rel in files:
        how = _reader(rel)
        if how is None:
            continue
        text = (root / rel).read_text(encoding="utf-8-sig", errors="replace")
        for item in _found(rel, text):
            target = _resolve(item.value, (root / rel).parent, root)
            refs.append(
                Ref(
                    document=PurePosixPath(rel.as_posix()).as_posix(),
                    kind=item.kind,
                    value=item.value,
                    resolved=None if target is None else target.as_posix(),
                    exists=None if target is None else target.exists(),
                    outside=target is not None and not _inside(target, root),
                    writable=how[1],
                )
            )
    return tuple(refs)


def repoint(
    root: Path, files: Sequence[Path], old: str, new: str
) -> tuple[dict[str, bytes], tuple[str, ...]]:
    """The new bytes of each writable document that holds a path starting with ``old``, that prefix replaced
    by ``new``; and the documents that hold such a path but that Fenolite does not rewrite."""
    changed: dict[str, bytes] = {}
    kept: list[str] = []
    for rel in files:
        how = _reader(rel)
        if how is None:
            continue
        raw = (root / rel).read_bytes()
        text = raw.decode("utf-8-sig", errors="strict")
        matching = [item for item in _found(rel, text) if item.value.startswith(old)]
        if not matching:
            continue
        if not how[1]:
            kept.append(rel.as_posix())
            continue
        updated = text
        for item in {item.written: item for item in matching}.values():
            value = new + item.value[len(old) :]
            written = json.dumps(value) if how[0] == "project" else Atom.string(value).text
            updated = updated.replace(item.written, written)
        bom = b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b""
        if updated != text:
            changed[rel.as_posix()] = bom + updated.encode("utf-8")
    return changed, tuple(kept)


__all__ = ["PROJECT_VAR", "Ref", "project_refs", "repoint"]

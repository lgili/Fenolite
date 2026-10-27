# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The files of a project and a stable read of them (capability file-safety, "Stable snapshot").

A project is the folder of a design file, or a folder given directly. Its files are those whose suffix or
name is a design document of KiCad or Altium, and the files inside the library folders of KiCad
(``*.pretty``, ``*.3dshapes``) that lie in it; backups, lock files, Fenolite's own state and hidden folders
are left out.

A read is stable when every file has the same SHA-256 before and after all of them were read. A file that a
save changed during the read is read again, at most ``RETRIES`` times.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from fenolite.core.io import sha256_bytes, sha256_of

DOCUMENT_SUFFIXES = frozenset(
    {
        # KiCad
        ".kicad_pcb", ".kicad_sch", ".kicad_pro", ".kicad_dru", ".kicad_sym", ".kicad_mod", ".kicad_wks",
        ".kicad_jobset",
        # Altium
        ".prjpcb", ".pcbdoc", ".schdoc", ".pcblib", ".schlib", ".outjob", ".pcbdwf", ".harness", ".schdot",
        ".bomdoc", ".prjpcbstructure",
        # Fenolite
        ".py", ".toml",
    }
)  # fmt: skip
"""The suffixes of the documents of a project, in lower case."""
DOCUMENT_NAMES = frozenset({"fp-lib-table", "sym-lib-table", "design-block-lib-table"})
LIBRARY_FOLDERS = (".pretty", ".3dshapes")
"""KiCad library folders whose files belong to the project when they lie inside its folder."""
SKIPPED_FOLDERS = frozenset({"__pycache__", "node_modules"})
SKIPPED_SUFFIXES = (".bak", ".lck", "-bak", "~")
RETRIES = 3

ReadHook = Callable[[Path, int], None]
"""Called after each read of a file with its path and the attempt (0 for the first): a test seam."""


@dataclass(frozen=True, slots=True)
class StableFile:
    """A file read whole: its path relative to the project folder (POSIX form), its bytes and their hash."""

    path: str
    data: bytes
    sha256: str


@dataclass(frozen=True, slots=True)
class StableRead:
    """The files of a stable read, sorted by path; ``retries`` counts the files read again; ``unstable``
    names those that never settled."""

    root: Path
    files: tuple[StableFile, ...]
    retries: int = 0
    unstable: tuple[str, ...] = ()


def _skipped(rel: Path) -> bool:
    if any(part.startswith(".") or part in SKIPPED_FOLDERS for part in rel.parts[:-1]):
        return True
    name = rel.name
    return name.startswith(("~", ".")) or name.endswith(SKIPPED_SUFFIXES) or "-backups" in rel.parts[0]


def _wanted(rel: Path) -> bool:
    if rel.name in DOCUMENT_NAMES or rel.suffix.lower() in DOCUMENT_SUFFIXES:
        return True
    return any(part.endswith(LIBRARY_FOLDERS) for part in rel.parts[:-1])


def project_root(path: Path) -> Path:
    """The project folder of ``path``: the folder itself, or the folder of a file."""
    return path if path.is_dir() else path.parent


def project_files(path: Path) -> tuple[Path, ...]:
    """The files of the project of ``path``, relative to its folder, sorted."""
    root = project_root(path)
    found: list[Path] = []
    for item in root.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(root)
        if not _skipped(rel) and _wanted(rel):
            found.append(rel)
    return tuple(sorted(found, key=lambda rel: rel.as_posix()))


def companions(path: Path) -> tuple[Path, ...]:
    """The files of the project of the file ``path``, relative to its folder: the documents of its stem,
    the library tables beside it, and every file inside the folder that one of those names (a sheet, a
    library, a library folder's files), followed until no new file appears. A folder gives
    ``project_files``."""
    from fenolite.safety.refs import project_refs

    if path.is_dir():
        return project_files(path)
    root = path.parent
    wanted = set(project_files(root))
    held = {
        rel
        for rel in wanted
        if rel.parent == Path(".") and (rel.stem == path.stem or rel.name in DOCUMENT_NAMES)
    }
    held.add(Path(path.name))
    todo = sorted(held, key=lambda rel: rel.as_posix())
    while todo:
        found: set[Path] = set()
        for ref in project_refs(root, todo):
            if ref.resolved is None or ref.outside or not ref.exists:
                continue
            target = Path(ref.resolved).resolve().relative_to(root.resolve())
            if (root / target).is_dir():
                found |= {rel for rel in wanted if rel.is_relative_to(target)}
            else:
                found.add(target)
        todo = sorted(found - held, key=lambda rel: rel.as_posix())
        held |= found
    return tuple(sorted(held, key=lambda rel: rel.as_posix()))


def read_stable(root: Path, files: Sequence[Path], *, hook: ReadHook | None = None) -> StableRead:
    """Read ``files`` (relative to ``root``) and check that each still has the hash it was read with once
    all were read; a changed file is read again, at most ``RETRIES`` times."""
    held: dict[Path, StableFile] = {}
    retries = 0
    todo = list(files)
    attempt = 0
    while todo:
        for rel in todo:
            data = (root / rel).read_bytes()
            held[rel] = StableFile(rel.as_posix(), data, sha256_bytes(data))
            if hook is not None:
                hook(root / rel, attempt)
        moved = [rel for rel in todo if sha256_of(root / rel) != held[rel].sha256]
        if not moved:
            break
        if attempt == RETRIES:
            unstable = tuple(rel.as_posix() for rel in moved)
            ordered = tuple(held[rel] for rel in sorted(held, key=lambda r: r.as_posix()))
            return StableRead(root, ordered, retries, unstable)
        retries += len(moved)
        todo = moved
        attempt += 1
    ordered = tuple(held[rel] for rel in sorted(held, key=lambda r: r.as_posix()))
    return StableRead(root, ordered, retries)


__all__ = [
    "DOCUMENT_NAMES",
    "DOCUMENT_SUFFIXES",
    "RETRIES",
    "StableFile",
    "StableRead",
    "companions",
    "project_files",
    "project_root",
    "read_stable",
]

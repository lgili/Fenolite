# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The schematic rows of the corpus: their place in the demo tree and their content tags (capability
corpus-policy, "Schematic corpus rows"; change c0060).

A row is one ``.kicad_sch`` of the demo folders at a tag. A file that is identical at both tags is listed
once, under its 10.0.6 id, and carries the use ``sch-9``. ``layout`` rebuilds the demo tree of one tag in
a temporary folder (links to the cached files), so a hierarchy can be walked as KiCad walks it. Nothing
here names a row by anything but its id.
"""

from __future__ import annotations

import os
import re
import shutil
import tomllib
import urllib.parse
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from _corpus import MANIFEST
from _resources import corpus_cache_dir

from fenolite.backends.kicad import sch
from fenolite.backends.kicad.sexpr import Node, parse_bytes
from fenolite.backends.kicad.versions import READ_FLOOR, FileKind, detect_version

TAGS = ("10.0.6", "9.0.9.1")
SHARED = "sch-9"
"""The use of a row whose file is in the demos at tag 9.0.9.1 (every row of that tag, and the rows of tag
10.0.6 that are identical there): what the ``kicad-9`` job fetches."""
CONTENT_TAGS = ("sch-root", "sch-bus", "sch-multi", "sch-old")
BUS_HEADS = frozenset({"bus", "bus_entry", "bus_alias"})
LABEL_HEADS = frozenset({"label", "global_label", "hierarchical_label"})
_VECTOR = re.compile(r"\[\d+\.\.\d+\]")
_GROUP = re.compile(r"(?<!\$)\{[^{}]*\}")
_DEMO = re.compile(r"/-/raw/([^/]+)/(demos/.+)$")


@dataclass(frozen=True)
class SchRow:
    id: str
    ref: str
    path: str  # the path in the source tree for demo rows, "" for other origins
    file: Path
    uses: tuple[str, ...]
    roots: Mapping[str, bool]  # tag → a project file of the same stem is beside it

    @property
    def origin(self) -> str:
        return next((u.removeprefix("origin:") for u in self.uses if u.startswith("origin:")), "unknown")

    @property
    def tags(self) -> tuple[str, ...]:
        """The tags at which this file is in the demo tree."""
        if self.origin != "kicad-demos":
            return ()
        return (self.ref, "9.0.9.1") if self.ref == "10.0.6" and SHARED in self.uses else (self.ref,)

    @property
    def content(self) -> set[str]:
        return set(self.uses) & set(CONTENT_TAGS)


def rows() -> tuple[SchRow, ...]:
    """Every manifest row with the use ``sch``."""
    data = tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", [])
    cache = corpus_cache_dir()
    projects = {
        (m.group(1), urllib.parse.unquote(m.group(2)))
        for row in data
        if row["url"].endswith(".kicad_pro") and (m := _DEMO.search(row["url"]))
    }
    found: list[SchRow] = []
    for row in data:
        uses = tuple(row.get("uses", []))
        if "sch" not in uses:
            continue
        url = urllib.parse.urlparse(row["url"]).path
        name = urllib.parse.unquote(Path(url).name)
        match = _DEMO.search(row["url"])
        path = urllib.parse.unquote(match.group(2)) if match else ""
        project = str(PurePosixPath(path).with_suffix(".kicad_pro")) if path else ""
        # a project row of tag 10.0.6 with no row of its own at 9.0.9.1 is the same file at both tags
        roots = (
            {
                "10.0.6": ("10.0.6", project) in projects,
                "9.0.9.1": any((t, project) in projects for t in TAGS),
            }
            if path
            else {}
        )
        found.append(SchRow(row["id"], row["ref"], path, cache / row["id"] / name, uses, roots))
    return tuple(found)


def at_tag(tag: str, items: Iterable[SchRow] | None = None) -> dict[str, SchRow]:
    """Source path → row, for the demo tree of ``tag``."""
    return {r.path: r for r in (rows() if items is None else items) if tag in r.tags}


def layout(folder: Path, tag: str, items: Iterable[SchRow] | None = None) -> dict[str, Path]:
    """The cached schematics of ``tag`` placed at their source paths under ``folder``: path → file."""
    placed: dict[str, Path] = {}
    for path, row in at_tag(tag, items).items():
        if not row.file.is_file():
            continue
        target = folder / path
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(row.file, target)
        except OSError:
            shutil.copyfile(row.file, target)
        placed[path] = target
    return placed


def version_of(file: Path) -> int:
    return detect_version(parse_bytes(file.read_bytes(), file=file.name), file=file.name)


def has_bus(root: Node) -> bool:
    """A bus item, or a label whose text is a bus vector or a bus group."""
    for child in root.nodes():
        if child.name in BUS_HEADS:
            return True
        if child.name in LABEL_HEADS:
            atoms = child.atoms()
            text = atoms[0].value if atoms else ""
            if _VECTOR.search(text) or _GROUP.search(text):
                return True
    return False


def multi_symbol(sheet: object) -> bool:
    """A symbol with more than one use under one project."""
    for symbol in sheet.symbols:  # type: ignore[attr-defined]
        projects = [use.project for use in symbol.uses]
        if len(projects) != len(set(projects)):
            return True
    return False


def root_at(row: SchRow, tag: str) -> bool:
    return bool(row.roots.get(tag))


def computed_tags(folder: Path, items: Iterable[SchRow] | None = None) -> dict[str, set[str]]:
    """Row id → its content tags, recomputed from the cached files (rows without a cached file are left
    out). ``folder`` is an empty temporary folder for the two demo trees."""
    items = tuple(rows() if items is None else items)
    found: dict[str, set[str]] = {}
    old: set[str] = set()
    for row in items:
        if not row.file.is_file():
            continue
        tags: set[str] = set()
        if any(root_at(row, tag) for tag in row.tags):
            tags.add("sch-root")
        root = parse_bytes(row.file.read_bytes(), file=row.id)
        if detect_version(root, file=row.id) < READ_FLOOR[FileKind.SCHEMATIC]:
            tags.add("sch-old")
            old.add(row.id)
        else:
            if has_bus(root):
                tags.add("sch-bus")
            if multi_symbol(sch.read_schematic(root, file=row.id)):
                tags.add("sch-multi")
        found[row.id] = tags
    for tag in TAGS:
        placed = layout(folder / tag, tag, items)
        by_path = at_tag(tag, items)
        for path, row in by_path.items():
            if not root_at(row, tag) or path not in placed or row.id in old:
                continue
            try:
                tree = sch.sheet_files(placed[path])
            except Exception:  # noqa: BLE001  (a hierarchy with an unreadable sheet: no reference count)
                continue
            base = PurePosixPath(path).parent
            for name, count in tree.references.items():
                if count > 1:
                    target = by_path.get(os.path.normpath(str(base / name)).replace(os.sep, "/"))
                    if target is not None and target.id in found:
                        found[target.id].add("sch-multi")
    return found


def project_files(placed_root: Path) -> list[Path]:
    """The files of the hierarchy under a placed root, the root first (files outside its folder left out)."""
    tree = sch.sheet_files(placed_root)
    return [placed_root.parent / name for name in tree.files if not name.startswith("../")]


__all__ = [
    "CONTENT_TAGS",
    "SHARED",
    "TAGS",
    "SchRow",
    "at_tag",
    "computed_tags",
    "has_bus",
    "layout",
    "multi_symbol",
    "project_files",
    "root_at",
    "rows",
    "version_of",
]

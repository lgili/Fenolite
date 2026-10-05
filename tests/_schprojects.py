# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Corpus schematics as projects in ``tmp_path`` for the ERC oracle tests (capability kicad-oracle, "ERC
facts proved per major" and "Schematic RT2 over the corpus"; change c0062).

A project is one schematic row with the tag ``sch-root`` at a demo tag: its folder of the demo tree is
rebuilt from the cached rows, so the cache is only read. Every cached row of that folder is placed (sheet
files, the project file, symbol libraries, tables), and a board of the root's stem is authored when the
folder has none, because a copy set is planned from a board. Rows are named by their ids only.
"""

from __future__ import annotations

import re
import shutil
import tomllib
import urllib.parse
from dataclasses import dataclass
from functools import cache
from pathlib import Path, PurePosixPath

import _schcorpus
from _corpus import MANIFEST
from _resources import corpus_cache_dir

from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind

ACCEPTANCE_EXCLUDED = frozenset({"sch-bus", "sch-multi", "sch-old"})
"""A root row with none of these tags is on the acceptance list of v0.2a (change c0060)."""
MAJOR_TAGS = {10: "10.0.6", 9: "9.0.9.1"}
STUB_BOARD = (
    '(kicad_pcb\n\t(version 20241229)\n\t(generator "fenolite-test")\n\t(generator_version "9.0")\n)\n'
)
"""An authored empty board for a demo folder without one: ``sch erc`` does not read it."""
_DEMO = re.compile(r"/-/raw/([^/]+)/(demos/.+)$")


@dataclass(frozen=True)
class DemoFile:
    id: str
    tag: str
    path: str  # the path in the source tree
    file: Path
    uses: tuple[str, ...]


@cache
def demo_files() -> tuple[DemoFile, ...]:
    """Every manifest row of the demo tree, cached or not."""
    data = tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", [])
    store = corpus_cache_dir()
    found: list[DemoFile] = []
    for row in data:
        match = _DEMO.search(row["url"])
        if match is None:
            continue
        path = urllib.parse.unquote(match.group(2))
        name = PurePosixPath(path).name
        uses = tuple(row.get("uses", []))
        found.append(DemoFile(row["id"], match.group(1), path, store / row["id"] / name, uses))
    return tuple(found)


def roots(major: int) -> tuple[_schcorpus.SchRow, ...]:
    """The root rows the running major can load, sorted by id: every ``sch-root`` row of tag 10.0.6 on
    major 10; on major 9 those of tag 9.0.9.1 whose format is not above the one 9.0 writes."""
    tag = MAJOR_TAGS[major]
    found = [
        r for r in _schcorpus.rows()
        if "sch-root" in r.uses and tag in r.tags and _schcorpus.root_at(r, tag)
    ]  # fmt: skip
    return tuple(sorted(found, key=lambda r: r.id))


def loadable(row: _schcorpus.SchRow, major: int) -> bool:
    """Whether every cached sheet of the row's folder is at a format the running major reads."""
    limit = FORMAT_VERSIONS[FileKind.SCHEMATIC][major]
    folder = str(PurePosixPath(row.path).parent)
    tag = MAJOR_TAGS[major]
    sheets = [r for p, r in _schcorpus.at_tag(tag).items() if str(PurePosixPath(p).parent) == folder]
    return all(not r.file.is_file() or _schcorpus.version_of(r.file) <= limit for r in sheets)


def acceptance(row: _schcorpus.SchRow) -> bool:
    return not (ACCEPTANCE_EXCLUDED & set(row.uses))


def _at_tag(tag: str) -> dict[str, DemoFile]:
    """Source path → file of the demo tree at ``tag``: the rows of that tag, and for 9.0.9.1 also the
    rows of 10.0.6 that are the same file there (schematics with the use ``sch-9``, and project files)."""
    found = {f.path: f for f in demo_files() if f.tag == tag}
    if tag != "10.0.6":
        for item in demo_files():
            shared = _schcorpus.SHARED in item.uses or item.path.endswith(".kicad_pro")
            if item.tag == "10.0.6" and shared and item.path not in found:
                found[item.path] = item
    return found


def project_folder(tmp_path: Path, row: _schcorpus.SchRow, major: int) -> Path | None:
    """The demo folder of ``row`` rebuilt under ``tmp_path`` from the cached rows (copies), with the root
    schematic at its own name; ``None`` when the root itself is not cached."""
    if not row.file.is_file():
        return None
    tag = MAJOR_TAGS[major]
    source = PurePosixPath(row.path).parent
    root = tmp_path / row.id
    root.mkdir(parents=True)
    for path, item in sorted(_at_tag(tag).items()):
        inside = PurePosixPath(path)
        if source not in inside.parents or not item.file.is_file():
            continue
        target = root / inside.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item.file, target)
    stem = PurePosixPath(row.path).stem
    board = root / f"{stem}.kicad_pcb"
    if not board.is_file():
        board.write_text(STUB_BOARD, encoding="utf-8", newline="\n")
    return root


__all__ = [
    "ACCEPTANCE_EXCLUDED",
    "MAJOR_TAGS",
    "STUB_BOARD",
    "acceptance",
    "demo_files",
    "loadable",
    "project_folder",
    "roots",
]

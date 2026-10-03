# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Demo projects resolve their own footprints (capability corpus-policy, "Demo library corpus rows";
change c0021).

Each demo folder that has ``libs`` rows is rebuilt under ``tmp_path`` from the cached corpus files, at the
paths their URLs give. Every footprint that a rebuilt board places through a row of the rebuilt project
table must resolve, with no other library source. Footprints of other nicknames are counted by issue code
in the file named by ``FENOLITE_CENSUS_OUT``. Supporting data from one origin: no label changes.

Folders are named by tag and index only; names appear in manifest URLs alone.
"""

from __future__ import annotations

import shutil
import tomllib
import urllib.parse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from _boards import census
from _corpus import MANIFEST, manifest_items, require

from fenolite.backends.kicad.liberrors import LibraryError
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver, read_lib_table, split_lib_id
from fenolite.backends.kicad.pcb import read_board

TAGS = ("10.0.6", "9.0.9.1")
TABLE = "fp-lib-table"


@dataclass(frozen=True)
class Row:
    id: str
    path: str  # inside the demos folder, URL-decoded
    tags: tuple[str, ...]
    uses: tuple[str, ...]


def _rows() -> list[Row]:
    found: list[Row] = []
    entries: list[dict[str, Any]] = tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", [])
    for entry in entries:
        uses = tuple(entry["uses"])
        url = urllib.parse.unquote(urllib.parse.urlparse(str(entry["url"])).path)
        if "origin:kicad-demos" not in uses or "rt0" not in uses or "heavy" in uses or "/demos/" not in url:
            continue
        notes = str(entry["notes"])
        tags = tuple(t for t in TAGS if entry["ref"] == t or f"identical at tag {t} " in notes)
        found.append(Row(str(entry["id"]), url.split("/demos/", 1)[1], tags, uses))
    return found


def folders(rows: list[Row], tag: str) -> dict[str, list[Row]]:
    """Demo folder to its files at ``tag``: the ``libs`` rows and the board rows of each folder that has a
    listed project table. A file belongs to the deepest such folder that holds it."""
    at = [r for r in rows if tag in r.tags]
    tops = sorted(
        (r.path.rsplit("/", 1)[0] for r in at if "libs" in r.uses and r.path.endswith("/" + TABLE)),
        key=len,
        reverse=True,
    )
    grouped: dict[str, list[Row]] = {top: [] for top in tops}
    for row in at:
        if "libs" not in row.uses and not row.path.endswith(".kicad_pcb"):
            continue
        top = next((t for t in tops if row.path.startswith(t + "/")), None)
        if top is not None:
            grouped[top].append(row)
    return grouped


def _resolver(project: Path, major: int, empty: Path) -> LibraryResolver:
    """A resolver that knows only the project table: empty environment and configuration, no install."""
    (empty / "config").mkdir()
    config = LibraryConfig(
        target_major=major,
        project_dir=project,
        env={},
        config_home=empty / "config",
        install_dir=empty / "no-install",
        home=empty / "home",
    )
    return LibraryResolver(config)


def judge(
    boards: list[Path], project: Path, resolver: LibraryResolver
) -> tuple[int, list[str], Counter[str]]:
    """``(resolved, failures, others)`` over the footprints of ``boards``: those whose nickname is a row of
    the project table must resolve; the others are counted by issue code."""
    nicknames = {row.nickname for row in read_lib_table(project / TABLE).rows}
    resolved = 0
    failures: list[str] = []
    others: Counter[str] = Counter()
    for board in boards:
        for footprint in read_board(board).board.footprints:
            try:
                nickname, _ = split_lib_id(footprint.lib_ref)
                resolver.locate(footprint.lib_ref, "footprint")
            except LibraryError as error:
                nickname = footprint.lib_ref.partition(":")[0]
                if nickname in nicknames:
                    failures.append(f"{error.issue.code}: {error.issue.message}")
                else:
                    others[error.issue.code] += 1
                continue
            if nickname in nicknames:
                resolved += 1
            else:
                others["resolved-elsewhere"] += 1
    return resolved, failures, others


CASES = [(tag, index) for tag in TAGS for index in range(len(folders(_rows(), tag)))]
IDS = [f"{tag}-folder-{index + 1:02d}" for tag, index in CASES]


@pytest.mark.needs_corpus
@pytest.mark.parametrize(("tag", "index"), CASES, ids=IDS)
def test_demo_project_resolves_its_footprints(tag: str, index: int, tmp_path: Path) -> None:
    top, rows = sorted(folders(_rows(), tag).items())[index]
    cached = {item.id: item for item in manifest_items("rt0")}
    project = tmp_path / "project"
    boards: list[Path] = []
    for row in rows:
        target = project / row.path[len(top) + 1 :]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(require(cached[row.id]), target)
        if target.suffix == ".kicad_pcb":
            boards.append(target)
    assert boards, f"{tag} folder {index + 1}: no board row to rebuild"
    resolver = _resolver(project, int(tag.split(".", 1)[0]), tmp_path)
    resolved, failures, others = judge(boards, project, resolver)
    census(
        "demo_libs",
        f"{tag}-folder-{index + 1:02d}",
        {"boards": len(boards), "resolved": resolved, "other_nicknames": dict(sorted(others.items()))},
    )
    assert not failures, f"{tag} folder {index + 1}: {len(failures)} unresolved; first: {failures[0]}"
    assert resolved > 0, f"{tag} folder {index + 1}: no footprint goes through the project table"


def test_other_nicknames_are_counted(tmp_path: Path) -> None:
    """Hermetic, on authored files: a board whose two footprints name a library that the project table
    does not list. They are counted under ``kicad.lib.unknown-nickname`` and fail nothing."""
    data = Path(__file__).resolve().parents[1] / "data"
    project = data / "libs" / "project"
    board = data / "kicad" / "board" / "two_layer.kicad_pcb"
    resolved, failures, others = judge([board], project, _resolver(project, 10, tmp_path))
    assert (resolved, failures) == (0, [])
    assert others == Counter({"kicad.lib.unknown-nickname": 2})


def test_folders_group_by_the_deepest_table() -> None:
    rows = [
        Row("t1", "a/fp-lib-table", ("10.0.6",), ("rt0", "libs")),
        Row("t2", "a/sub/fp-lib-table", ("10.0.6", "9.0.9.1"), ("rt0", "libs")),
        Row("m1", "a/x.pretty/f.kicad_mod", ("10.0.6",), ("rt0", "libs")),
        Row("b1", "a/sub/b.kicad_pcb", ("10.0.6", "9.0.9.1"), ("rt0",)),
        Row("b2", "c/b.kicad_pcb", ("10.0.6",), ("rt0",)),
        Row("s1", "a/a.kicad_sch", ("10.0.6",), ("rt0",)),
    ]
    assert {k: [r.id for r in v] for k, v in folders(rows, "10.0.6").items()} == {
        "a/sub": ["t2", "b1"],
        "a": ["t1", "m1"],
    }
    assert {k: [r.id for r in v] for k, v in folders(rows, "9.0.9.1").items()} == {"a/sub": ["t2", "b1"]}

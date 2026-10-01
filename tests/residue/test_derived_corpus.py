# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Files derived from non-embeddable corpus items stay out of the repository (capability corpus-policy).

A ``.kicad_*`` file under ``tests/data/`` or ``examples/`` is reported when it is tree-equal to a cached
corpus item or shares at least three identifier values (``uuid``/``tstamp`` atoms, lowercased, without
``-`` and leading zeros, counted when at least 8 hex digits remain) with one.
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Iterable
from functools import cache
from pathlib import Path

import pytest
from _corpus import CorpusItem, corpus_items

from fenolite.backends.kicad import Node, dumps, load, parse, tree_equal, walk
from fenolite.core.errors import FormatError

pytestmark = pytest.mark.needs_corpus
ROOT = Path(__file__).resolve().parents[2]
IDENTIFIER_HEADS = ("uuid", "tstamp")
_HEX = re.compile(r"[0-9a-f]{8,}")


def identifiers(node: Node) -> set[str]:
    found: set[str] = set()
    for _, current in walk(node):
        if current.name in IDENTIFIER_HEADS:
            for atom in current.atoms():
                value = atom.value.lower().replace("-", "").lstrip("0")
                if _HEX.fullmatch(value):
                    found.add(value)
    return found


@cache
def _corpus_tree(path: Path) -> Node:
    return load(path)


@cache
def _corpus_identifiers(path: Path) -> frozenset[str]:
    return frozenset(identifiers(_corpus_tree(path)))


def derived_reports(candidates: Iterable[Path], corpus: list[CorpusItem]) -> list[str]:
    reports: list[str] = []
    for path in candidates:
        try:
            tree = load(path)
        except FormatError:
            continue
        mine = identifiers(tree)
        for item in corpus:
            shared = len(mine & _corpus_identifiers(item.path))
            if shared >= 3 or tree_equal(tree, _corpus_tree(item.path)):
                reports.append(f"{path}: derived from corpus item {item.id} ({shared} shared identifiers)")
    return reports


def _repository_files() -> list[Path]:
    return sorted(
        p for top in ("tests/data", "examples") for p in (ROOT / top).rglob("*.kicad_*") if p.is_file()
    )


def _boards() -> list[CorpusItem]:
    boards = [i for i in corpus_items("rt0") if i.path.suffix == ".kicad_pcb"]
    if not boards:
        pytest.skip("no cached corpus board")
    return boards


def test_repository_has_no_derived_copies() -> None:
    reports = derived_reports(_repository_files(), corpus_items("rt0"))
    assert not reports, "\n".join(reports)


def test_authored_fixtures_pass() -> None:
    fixtures = sorted((ROOT / "tests" / "data" / "kicad" / "sexpr").rglob("*.kicad_pcb"))
    assert fixtures and derived_reports(fixtures, _boards()) == []


def _board_with_footprint(boards: list[CorpusItem]) -> tuple[CorpusItem, Node]:
    for item in boards:
        root = _corpus_tree(item.path)
        for footprint in root.nodes("footprint") + root.nodes("module"):
            if len(identifiers(footprint)) >= 3:
                return item, footprint
    pytest.skip("no cached board has a footprint with three identifiers")


def test_partial_copy_detected(tmp_path: Path) -> None:
    item, footprint = _board_with_footprint(_boards())
    planted = tmp_path / "planted.kicad_pcb"
    planted.write_text(dumps(parse(f"(kicad_pcb (version 20241229) {dumps(footprint, style='compact')})")))
    reports = derived_reports([planted], [item])
    assert len(reports) == 1 and item.id in reports[0] and str(planted) in reports[0]


@pytest.mark.needs_kicad
@pytest.mark.kicad_min_major(10)
def test_upgraded_copy_detected(tmp_path: Path) -> None:
    from _kicad import run

    item = next((i for i in _boards() if len(identifiers(_corpus_tree(i.path))) >= 3), None)
    if item is None:
        pytest.skip("no cached board with identifiers")
    copy = tmp_path / "copy.kicad_pcb"
    shutil.copy(item.path, copy)
    run("pcb", "upgrade", "--force", copy)
    assert not tree_equal(load(copy), _corpus_tree(item.path))
    reports = derived_reports([copy], [item])
    assert len(reports) == 1 and item.id in reports[0]


def test_identifier_normalisation() -> None:
    node = parse('(a (uuid "00ABCDEF-0123-4567") (tstamp 5E8C0F2A) (uuid "x") (tstamp 0000001))')
    assert identifiers(node) == {"abcdef01234567", "5e8c0f2a"}

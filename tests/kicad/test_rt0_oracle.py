# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Re-dumped corpus boards against kicad-cli (H-K-FMT-RESAVE, H-K-SEXPR-NUM-WRITE/-2).

Copies are made in ``tmp_path`` only; nothing derived from the corpus is kept.
"""

from __future__ import annotations

import re
import shutil
from collections import defaultdict
from pathlib import Path

import pytest
from _corpus import CorpusItem, manifest_items, require
from _kicad import loads, major, run

from fenolite.backends.kicad import Atom, AtomKind, Node, dumps, first_difference, load, tree_equal, walk

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_corpus]
BOARDS = [i for i in manifest_items("oracle") if "rt0" in i.uses]
MASKED = ("uuid", "tstamp")
NON_DETERMINISTIC: list[str] = []
CENSUS: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])


def _mask(node: Node) -> Node:
    if node.name in MASKED:
        return node.with_children(Atom.symbol("masked") if isinstance(c, Atom) else c for c in node.children)
    return node.with_children(_mask(c) if isinstance(c, Node) else c for c in node.children)


def _upgraded(source: Path, target: Path) -> Node:
    shutil.copy(source, target)
    run("pcb", "upgrade", "--force", target)
    return load(target)


@pytest.mark.parametrize("item", BOARDS, ids=lambda i: i.id)
def test_redump_loads(item: CorpusItem, tmp_path: Path) -> None:
    path = require(item)
    original = tmp_path / "original.kicad_pcb"
    shutil.copy(path, original)
    if not loads(original):
        pytest.skip(f"{item.id}: the original does not load in kicad-cli")
    redump = tmp_path / "redump.kicad_pcb"
    redump.write_text(dumps(load(path)), encoding="utf-8")
    assert loads(redump), f"{item.id}: the re-dumped board does not load"


@pytest.mark.parametrize("item", BOARDS, ids=lambda i: i.id)
def test_resave_equal(item: CorpusItem, tmp_path: Path) -> None:
    if major() != 10:
        pytest.skip("pcb upgrade exists only in the 10.0 CLI")
    path = require(item)
    first = _mask(_upgraded(path, tmp_path / "a.kicad_pcb"))
    second = _mask(_upgraded(path, tmp_path / "b.kicad_pcb"))
    _census(item.id, load(tmp_path / "a.kicad_pcb"))
    if not tree_equal(first, second):
        NON_DETERMINISTIC.append(item.id)
        pytest.skip(f"{item.id}: two upgrades of the original differ at {first_difference(first, second)}")
    redump = tmp_path / "redump.kicad_pcb"
    redump.write_text(dumps(load(path)), encoding="utf-8")
    third = _mask(_upgraded(redump, tmp_path / "c.kicad_pcb"))
    assert tree_equal(third, first), f"{item.id}: re-saves differ at {first_difference(third, first)}"


# Values that are not lengths and that KiCad writes with full double precision (observed 10.0.6):
# 3D model offset/scale/rotation, pad corner ratios, and angles (third atom of ``at``).
NON_LENGTH: set[tuple[str, int | None]] = {("xyz", None), ("roundrect_rratio", None), ("chamfer_ratio", None),
                                           ("angle", None), ("at", 2)}  # fmt: skip
OVER_PRECISE: list[str] = []


def _census(ident: str, root: Node) -> None:
    counts = CENSUS[ident]
    counts[0] = 1
    for locator, node in walk(root):
        for index, atom in enumerate(node.atoms()):
            if atom.kind != AtomKind.NUMBER:
                continue
            mantissa = re.split(r"[eE]", atom.text)[0]
            counts[1] += "e" in atom.text.lower()
            if "." in mantissa and len(mantissa.split(".")[1]) > 6:
                counts[2] += 1
                if (node.name, None) not in NON_LENGTH and (node.name, index) not in NON_LENGTH:
                    OVER_PRECISE.append(f"{ident} {locator} {atom.text}")


def test_number_census_upgraded() -> None:
    """H-K-SEXPR-NUM-WRITE-2: files written by kicad-cli 10.0.x have no exponent, and numbers with more
    than 6 decimals only where the value is not a length (H-K-SEXPR-NUM-WRITE as stated is refuted)."""
    if not CENSUS:
        pytest.skip("no board was upgraded in this session (run test_resave_equal first)")
    exponent = sum(c[1] for c in CENSUS.values())
    precise = sum(c[2] for c in CENSUS.values())
    unstable = NON_DETERMINISTIC or "none"
    print(f"upgraded copies: {len(CENSUS)}; exponent atoms {exponent}; >6 decimals {precise} "
          f"({len(OVER_PRECISE)} in length contexts); non-deterministic re-saves: {unstable}")  # fmt: skip
    assert exponent == 0
    assert not OVER_PRECISE, "\n".join(OVER_PRECISE)

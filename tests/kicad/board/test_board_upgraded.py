# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Upgraded copies of the corpus boards (capabilities corpus-policy and kicad-oracle; hypotheses
H-K-PCB-READ and H-K-UUID-KEEP; change c0009).

``pcb upgrade --force`` exists on KiCad 10 only. Each copy is made through the package runner from the
cached file, kept in memory, and counts as its row's origin. Items are named by their manifest id only.
"""

from __future__ import annotations

from collections import Counter, defaultdict

import pytest
from _boardcorpus import (
    BOARD_ITEMS,
    Entry,
    census_headers,
    census_kept_opaque,
    census_numbers,
    census_pintypes,
    census_uuids,
    census_validation,
    census_zones,
)
from _boards import census, rt1_problems
from _corpus import CorpusItem, require
from _upgrade import upgraded

from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.sexpr import Node, load, parse, walk
from fenolite.core.errors import Issue

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_corpus, pytest.mark.kicad_min_major(10)]
# The upgrade set: the non-heavy demos at tag 10.0.6 and the third-party boards (the 9.0.9.1 demos and
# the malformed row are not upgraded).
ITEMS = [
    i
    for i in BOARD_ITEMS
    if not i.heavy and (i.origin == "third-party" or i.id.startswith("kicad-demo-10-0-6-"))
]
DEMOS = [i for i in ITEMS if i.origin == "kicad-demos"]
PASSED: dict[str, list[str]] = defaultdict(list)


@pytest.mark.parametrize("item", ITEMS, ids=lambda i: i.id)
def test_upgraded_read_rt1(item: CorpusItem) -> None:
    text = upgraded(require(item))
    issues: list[Issue] = []
    design = read_board(text, issues=issues)
    errors = [f"{i.code} at {i.where}" for i in issues if i.severity == "error"]
    assert not errors, f"{item.id} (upgraded): " + "; ".join(errors)
    problems = rt1_problems(text, design)
    assert not problems, f"{item.id} (upgraded): " + "; ".join(problems)
    PASSED[item.origin].append(item.id)


def _items(root: Node) -> dict[str, list[Node]]:
    """Every node that carries a ``(uuid U)`` child, by ``U``."""
    found: dict[str, list[Node]] = {}
    for _, node in walk(root):
        uuid = node.find("uuid")
        if uuid is not None and uuid.atoms():
            found.setdefault(uuid.atoms()[0].value, []).append(node)
    return found


def _dropped_kind(node: Node) -> str | None:
    """The kinds of item a 10.0.6 re-save drops or replaces, or ``None``."""
    if node.name == "zone":
        attr = node.find("attr")
        return "teardrop zone" if attr is not None and attr.find("teardrop") is not None else None
    if node.name == "property" and node.atoms() and node.atoms()[0].value == "Footprint":
        return "Footprint property"
    return "fp_text" if node.name == "fp_text" else None


@pytest.mark.parametrize("item", DEMOS, ids=lambda i: i.id)
def test_uuid_keep(item: CorpusItem) -> None:
    """``H-K-UUID-KEEP-2`` (demo half): a 10.0.6 re-save keeps the uuid of every item it keeps.

    It drops teardrop zones and a footprint's ``Footprint`` property, and replaces ``fp_text`` items with
    properties that have new uuids (``H-K-UUID-KEEP`` stated every uuid; refuted on 10.0.6).
    """
    path = require(item)
    original, copy = _items(load(path)), _items(parse(upgraded(path)))
    lost = [v for v in original if v not in copy]
    gained = [v for v in copy if v not in original]
    kinds = Counter(_dropped_kind(n) or n.name for v in lost for n in original[v])
    census("uuid_keep", item.id, {"lost": dict(kinds), "gained": len(gained)})
    unexplained = [v for v in lost if any(_dropped_kind(n) is None for n in original[v])]
    assert not unexplained, f"{item.id}: uuid {unexplained[0]} disappeared from a kept item"
    strange = [v for v in gained if any(n.name != "property" for n in copy[v])]
    assert not strange, f"{item.id}: new uuid {strange[0]} on an item that is not a property"
    moved = [
        v for v in original.keys() & copy.keys() if {n.name for n in original[v]} != {n.name for n in copy[v]}
    ]
    assert not moved, f"{item.id}: uuid {moved[0]} moved to another kind of item"


def test_upgraded_census() -> None:
    """The census of the corpus tests on the upgraded third-party copies, as origin ``third-party``."""
    copies = []
    for item in ITEMS:
        if item.origin != "third-party" or not item.path.is_file():
            continue
        text = upgraded(item.path)
        issues: list[Issue] = []
        design = read_board(text, issues=issues)
        copies.append(Entry(item.origin, item.id, parse(text), design, tuple(issues)))
    if not copies:
        pytest.skip("no third-party board is cached")
    counts, problems = census_zones(copies)
    assert not problems, ", ".join(problems)
    census("upgraded", "numbers", census_numbers(copies))
    census("upgraded", "kept_opaque", census_kept_opaque(copies))
    census("upgraded", "uuids", census_uuids(copies))
    census("upgraded", "zones", counts)
    census("upgraded", "validation", census_validation(copies))
    census("upgraded", "headers", census_headers(copies))
    census("upgraded", "pins", census_pintypes(copies))


def test_upgraded_summary() -> None:
    if not PASSED:
        pytest.skip("no upgraded copy ran in this session")
    summary = {origin: len(ids) for origin, ids in sorted(PASSED.items())}
    census("rt1", "upgraded_passed_per_origin", summary)
    print(f"RT1 on upgraded copies, passed per origin: {summary}")

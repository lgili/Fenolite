# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprint fields of the readable corpus boards (kicad-file-backend, "Footprint fields on boards",
scenario "Round trip with fields"; hypotheses H-K-PCB-READ and H-K-FIELD-RESAVE; change c0030).

Every placed ``property`` that is the first of its name in its footprint is a field, so every ``Reference``
and ``Value`` of the corpus is one. Counts only, keyed by manifest id: no content is printed. The upgraded
third-party copies are made by ``pcb upgrade --force`` on KiCad 10, kept in memory and never written.
"""

from __future__ import annotations

from collections import Counter
from functools import cache
from pathlib import Path

import pytest
from _boardcorpus import OLD_ITEMS, READABLE_ITEMS, census_fields, entry, read
from _boards import census, rt1_problems
from _corpus import CorpusItem, require
from _resources import kicad_cli

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.pcb import is_placed_property, read_board
from fenolite.backends.kicad.sexpr import Node, load, parse
from fenolite.model.design import Design

pytestmark = pytest.mark.needs_corpus
ITEMS = [i for i in READABLE_ITEMS if not i.heavy]
COUNTS: dict[str, dict[str, int]] = {}


def expected_fields(root: Node) -> tuple[list[list[str]], Counter[str]]:
    """Per footprint, the names of its placed properties that are the first of their name; and counts of
    the property kinds of the whole board."""
    names: list[list[str]] = []
    counts: Counter[str] = Counter()
    for footprint in root.nodes():
        if footprint.name != "footprint":
            continue
        seen: set[str] = set()
        found: list[str] = []
        for child in footprint.nodes():
            if child.name != "property":
                continue
            counts["properties"] += 1
            if not is_placed_property(child):
                counts["bare"] += 1
                continue
            name = child.atoms()[0].value
            if name in seen:
                counts["repeated"] += 1
                continue
            seen.add(name)
            found.append(name)
        names.append(found)
    return names, counts


def check(item_id: str, root: Node, design: Design) -> dict[str, int]:
    assert design.board is not None
    names, counts = expected_fields(root)
    footprints = design.board.footprints
    assert len(footprints) == len(names), item_id
    inexact = 0
    for footprint, wanted in zip(footprints, names, strict=True):
        got = [f.name for f in footprint.fields]
        if got != wanted:
            # an inexact property stays projected: the model then holds a sub-sequence
            assert [n for n in wanted if n in got] == got, item_id
            inexact += len(wanted) - len(got)
        for name in ("Reference", "Value"):
            assert (name in wanted) == (name in got), f"{item_id}: a placed {name} is not a field"
        assert len({f.id for f in footprint.fields}) == len(footprint.fields), item_id
    counts["fields"] = sum(len(f.fields) for f in footprints)
    counts["inexact"] = inexact
    counts["hidden"] = sum(1 for fp in footprints for f in fp.fields if not f.visible)
    counts["mirrored"] = sum(1 for fp in footprints for f in fp.fields if f.mirrored)
    counts["without_thickness"] = sum(1 for fp in footprints for f in fp.fields if f.thickness is None)
    return dict(sorted(counts.items()))


@pytest.mark.parametrize("item", ITEMS, ids=lambda i: i.id)
def test_placed_properties_are_fields(item: CorpusItem) -> None:
    path = require(item)
    design, _ = read(path)
    COUNTS[item.id] = check(item.id, load(path), design)


def test_field_counts() -> None:
    if not COUNTS:
        pytest.skip("no board ran in this session")
    total: Counter[str] = Counter()
    for counts in COUNTS.values():
        total.update(counts)
    census("fields", "per_board", COUNTS)
    census("fields", "total", dict(sorted(total.items())))
    print(f"fields over {len(COUNTS)} boards: {dict(sorted(total.items()))}")
    assert total["fields"] + total["bare"] + total["repeated"] + total["inexact"] == total["properties"]
    assert total["fields"] > 0


def test_field_census() -> None:
    entries = tuple(entry(i) for i in ITEMS if i.path.is_file())
    if not entries:
        require(ITEMS[0])
    data = census_fields(entries)
    census("fields", "native", data)
    print("field census:", data)


# --- upgraded third-party copies (KiCad 10 only) ---------------------------------------------------


@cache
def _upgraded(path: Path) -> str:
    cli = kicad_cli()
    assert cli is not None
    return KicadCli(Path(cli), timeout=600).upgrade_board(path).decode("utf-8")


@pytest.mark.needs_kicad
@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("item", [i for i in OLD_ITEMS if not i.heavy], ids=lambda i: i.id)
def test_upgraded_third_party_fields(item: CorpusItem) -> None:
    """A 10.0.6 re-save turns the ``fp_text reference`` and ``value`` items of older boards into
    properties, which then read as fields, and RT1 holds for the copy."""
    text = _upgraded(require(item))
    design = read_board(text)
    counts = check(f"{item.id} (upgraded)", parse(text), design)
    assert counts["fields"] > 0
    assert design.board is not None
    for footprint in design.board.footprints:
        names = [f.name for f in footprint.fields]
        assert "Reference" in names and "Value" in names, f"{item.id} (upgraded)"
    assert not rt1_problems(text, design), f"{item.id} (upgraded)"
    census("fields", f"upgraded:{item.id}", counts)

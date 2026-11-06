# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rule kinds and their reading (capability altium-project-reader, "Rule kinds and their reading", scenario
"Every corpus kind is listed"; change c0462, design D6). The documents are those of the manifest rows of use
``altium-pcbdoc``, read from the corpus cache with Fenolite's own readers; counts only."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from _corpus import CorpusItem, manifest_items, require

from fenolite.backends.altium.adapter.layers import copper_layers_of
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.pcb import read_rule_fields
from fenolite.backends.altium.read.rules import (
    CARRIED_KINDS,
    CHECKED_KINDS,
    READ_KINDS,
    RULE_KIND_MAP,
    map_rules,
)

pytestmark = pytest.mark.needs_corpus

ROWS = (
    *manifest_items("altium-pcbdoc"),
    *(row for row in manifest_items("rta") if row.id == "altium-third-party-pcbdoc-08"),
)
"""The 8 public rows of the pour census (S-2210)."""
PAGE = Path(__file__).resolve().parents[2] / "docs" / "formats" / "altium" / "rule-file.md"
HEADER = "| RULEKIND | reading | rules, part or reason |"
READINGS = {"neutral": set(RULE_KIND_MAP), "read": set(READ_KINDS), "checked": set(CHECKED_KINDS)}
READINGS["carried"] = set(CARRIED_KINDS)
REFUSED = {"MatchedLengths": ("delay-units", 15), "RoutingVias": ("template", 4)}
"""Kind → the reason of change c0462 that refuses its records on the public rows, and their count."""


def page_rows() -> dict[str, str]:
    """The rows of the table "Rule kinds and their reading": kind → reading."""
    lines = PAGE.read_text(encoding="utf-8").splitlines()
    start = lines.index(HEADER) + 2
    rows: dict[str, str] = {}
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip("|").split(" | ")]
        assert cells[0].strip("`") not in rows, cells[0]
        rows[cells[0].strip("`")] = cells[1]
    return rows


def test_the_table_is_the_code() -> None:
    """The page lists exactly the kinds of the four tables, each with its reading."""
    rows = page_rows()
    assert {kind: reading for kind, reading in rows.items()} == {
        kind: reading for reading, kinds in READINGS.items() for kind in kinds
    }
    assert list(rows) == sorted(rows)


def _records(item: CorpusItem) -> list[tuple[str, str, str]]:
    path = require(item)
    design = AltiumBackend().read(path).design
    layers = copper_layers_of(design.board.layers) if design.board is not None else None
    fields = read_rule_fields(path.read_bytes(), file=path.name)
    mapping = map_rules(fields, origin=path.name, layers=layers)
    reasons = {unmapped.index: unmapped.reason for unmapped in mapping.unmapped}
    return [
        (dict(f).get("RULEKIND", ""), reasons.get(index, "mapped"), item.id) for index, f in enumerate(fields)
    ]


@pytest.mark.parametrize("item", ROWS, ids=lambda item: item.id)
def test_every_corpus_kind_is_listed(item: CorpusItem) -> None:
    """Each kind of the row is in the table, and no record of a neutral or read kind is reported with
    ``no-counterpart``; a read kind is reported ``read-elsewhere``, a checked kind ``checked``."""
    found = _records(item)
    assert found, "no rule record read"
    listed = page_rows()
    assert sorted({kind for kind, _reason, _row in found} - set(listed)) == []
    wrong = [
        kind
        for kind, reason, _row in found
        if listed[kind] in ("neutral", "read") and reason == "no-counterpart"
    ]
    assert wrong == []
    assert all(reason == "read-elsewhere" for kind, reason, _row in found if listed[kind] == "read")
    assert all(reason == "checked" for kind, reason, _row in found if listed[kind] == "checked")


def test_refusals_of_c0462_keep_their_counts() -> None:
    """Over the 8 rows, the records that change c0462 refuses by a named reason keep their counts."""
    by_kind = Counter((kind, reason) for item in ROWS for kind, reason, _row in _records(item))
    for kind, (reason, count) in REFUSED.items():
        assert by_kind[(kind, reason)] == count, (kind, reason)

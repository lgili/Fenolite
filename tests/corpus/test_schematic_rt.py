# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""RT0 and RT1 on every readable demo schematic of the corpus (capability corpus-policy, "Schematic
corpus rows"; hypotheses ``H-K-SCH-READ`` and ``H-K-SCH-RT1``; change c0060).

Rows older than the read floor are counted with their format version and never read. Ids and counts
only; results go to the JSON file named by ``FENOLITE_CENSUS_OUT``.
"""

from __future__ import annotations

from collections import Counter
from functools import cache

import _schcorpus
import pytest
from _boards import census
from _corpus import manifest_items, require

from fenolite.backends.kicad import sch
from fenolite.backends.kicad.sexpr import dumps, parse, tree_equal
from fenolite.backends.kicad.versions import UnsupportedFormatError
from fenolite.core.errors import Issue

pytestmark = pytest.mark.needs_corpus
DEMOS = tuple(r for r in _schcorpus.rows() if r.origin == "kicad-demos")
READABLE = tuple(r for r in DEMOS if "sch-old" not in r.uses)
OLD = tuple(r for r in _schcorpus.rows() if "sch-old" in r.uses)


@cache
def text_of(row_id: str) -> str:
    item = next(i for i in manifest_items("sch") if i.id == row_id)
    return require(item).read_text(encoding="utf-8")


@pytest.mark.parametrize("row", READABLE, ids=lambda r: r.id)
def test_rt0_and_rt1(row: _schcorpus.SchRow) -> None:
    text = text_of(row.id)
    original = parse(text, file=row.id)
    assert tree_equal(parse(dumps(original)), original), f"{row.id}: RT0"
    issues: list[Issue] = []
    sheet = sch.read_schematic(text, file=row.id, issues=issues)
    verdict = sch.roundtrip_schematic(text, file=row.id)
    assert verdict.passed, f"{row.id}: RT1 differs at {verdict.difference}"
    census(
        "schematic_rt",
        row.id,
        {
            "format_version": _schcorpus.version_of(
                next(i for i in manifest_items("sch") if i.id == row.id).path
            ),
            "opaque_count": verdict.opaque_count,
            "symbols": len(sheet.symbols),
            "labels": len(sheet.labels),
            "no_connects": len(sheet.no_connects),
            "sheets": len(sheet.sheets),
            "lib_symbols": len(sheet.lib_symbols),
            "issues": dict(sorted(Counter(i.code for i in issues).items())),
        },
    )


@pytest.mark.parametrize("row", OLD, ids=lambda r: r.id)
def test_old_rows_are_not_read(row: _schcorpus.SchRow) -> None:
    text = text_of(row.id)
    with pytest.raises(UnsupportedFormatError):
        sch.read_schematic(text, file=row.id)
    version = _schcorpus.version_of(next(i for i in manifest_items("sch") if i.id == row.id).path)
    census("schematic_not_read", row.id, {"format_version": version, "reason": "older than the read floor"})


def test_acceptance_list_is_a_query() -> None:
    selected = [r for r in _schcorpus.rows() if not ({"sch-bus", "sch-multi", "sch-old"} & set(r.uses))]
    assert selected and all(r in READABLE for r in selected)
    census("schematic", "acceptance_rows", len(selected))


def test_summary() -> None:
    for row in (*READABLE, *OLD):
        text_of(row.id)  # skips, or fails in required-resource mode, when the cache is incomplete
    data = {
        "demo_rows": len(DEMOS),
        "read": len(READABLE),
        "not_read_older_than_floor": len([r for r in OLD if r.origin == "kicad-demos"]),
        "third_party_rows_not_read_here": len([r for r in OLD if r.origin != "kicad-demos"]),
    }
    census("schematic", "rt_summary", data)
    print("schematic RT:", data)
